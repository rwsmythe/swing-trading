"""9-metric scorecard for G2 W-bottom ruleset backtest (brief Sec 1.4).

Reports nine metrics per (ruleset, substrate) cell:
  1. expectancy_R = mean(R per closed trade)
  2. win_rate = N(R > 0) / N_closed
  3. avg_win_R = mean(R) over closed-and-profitable trades
  4. avg_loss_R = abs(mean(R)) over closed-and-unprofitable trades
  5. profit_factor = sum(R from winners) / abs(sum(R from losers))
  6. trigger_conversion_rate = N_triggered / N_patterns
  7. median_time_in_trade_sessions = median(days_held) over closed trades
  8. open_at_tail_count = N(trades with status='open')
  9. estimated_dollar_per_period = N_triggered_per_year x expectancy_R x
       R_DOLLAR_SIZE_AT_7500_FLOOR ($75/R per brief Sec 11 Q4)

Edge cases (brief Sec 4.2):
  - 0 closed trades -> expectancy/win_rate/profit_factor/avg_win/avg_loss/
    median_time = None
  - 0 triggered -> trigger_conversion_rate = 0.0; estimated_dollar = 0.0;
    open_at_tail_count = 0
  - 0 losses -> profit_factor = None (cannot divide by zero loss magnitude)
  - 0 winners -> avg_win_R = None

Cohort-validity discipline (gotcha #33 + brief Sec 1.4):
  The scorecard is METRIC-ONLY. NO categorical verdict labels (PARTIAL
  POSITIVE / NEGATIVE / POSITIVE) emitted by this module. Headline
  interpretation is narrative across the 9 metrics; the findings doc emits
  DESCRIPTIVE labels only.

Administrative sentinel handling: trades emitted with exit_reason in
{ohlcv_missing, ohlcv_empty, second_scaleout_invalid} reflect harness
/ data issues, NOT strategy performance. They are EXCLUDED from
n_triggered + n_closed metrics; they remain part of n_patterns for the
trigger_conversion_rate denominator.
"""
from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass, fields as dc_fields
from pathlib import Path

from research.harness.w_bottom_ruleset_comparison.walkforward import Trade


# Brief Sec 1.4 + Sec 11 Q4 LOCK
R_DOLLAR_SIZE_AT_7500_FLOOR = 75.0  # = 0.01 * 7500


# Administrative sentinels: trades emitted for these reasons reflect harness
# / data issues rather than strategy P&L. Excluded from triggered/closed
# performance metrics.
_ADMINISTRATIVE_EXIT_REASONS = frozenset(
    {"ohlcv_missing", "ohlcv_empty", "second_scaleout_invalid"}
)


@dataclass(frozen=True)
class ScorecardRow:
    """One row of the 9-metric scorecard for (ruleset, substrate).

    Note on metric #8 (open-at-tail): brief Sec 1.4 line 100 defines this
    as `N(open) / N_triggered` (a rate) while the field NAME suggests a
    count. Codex R1 MAJOR #6 closure: surface BOTH for unambiguous
    downstream consumption. `open_at_tail_count` is the raw integer
    count of trades with status='open'; `open_at_tail_rate` is the
    same count divided by `n_triggered` (None if n_triggered == 0).
    """

    ruleset_name: str
    substrate_name: str
    n_patterns: int
    n_triggered: int
    n_closed: int
    expectancy_R: float | None
    win_rate: float | None
    avg_win_R: float | None
    avg_loss_R: float | None
    profit_factor: float | None
    trigger_conversion_rate: float
    median_time_in_trade_sessions: float | None
    open_at_tail_count: int
    open_at_tail_rate: float | None
    estimated_dollar_per_period: float | None
    substrate_window_days: int


def build_scorecard_row(
    *,
    ruleset_name: str,
    substrate_name: str,
    trades: list[Trade],
    n_patterns: int,
    substrate_window_days: int,
) -> ScorecardRow:
    """Compute the 9-metric scorecard row from a list of Trade objects.

    Filters `trades` to only those whose `ruleset_name` matches the
    requested `ruleset_name`. Administrative sentinel exit_reasons (see
    `_ADMINISTRATIVE_EXIT_REASONS`) are excluded from triggered/closed
    counts but `n_patterns` (the conversion-rate denominator) is taken
    as supplied by the caller (= the pattern-cohort size).
    """
    own_trades = [t for t in trades if t.ruleset_name == ruleset_name]
    perf_trades = [
        t for t in own_trades
        if t.exit_reason not in _ADMINISTRATIVE_EXIT_REASONS
    ]
    triggered = [t for t in perf_trades if t.triggered]
    closed = [t for t in triggered if t.status == "closed"]
    open_at_tail = [t for t in perf_trades if t.status == "open"]

    n_triggered = len(triggered)
    n_closed = len(closed)
    open_at_tail_count = len(open_at_tail)

    trigger_conversion_rate = (
        n_triggered / n_patterns if n_patterns > 0 else 0.0
    )

    if n_closed == 0:
        expectancy_R: float | None = None
        win_rate: float | None = None
        avg_win_R: float | None = None
        avg_loss_R: float | None = None
        profit_factor: float | None = None
        median_time_in_trade: float | None = None
    else:
        r_values = [
            t.r_multiple for t in closed if t.r_multiple is not None
        ]
        # In V1, closed trades always have r_multiple set; defensive guard
        # here surfaces any data-shape drift.
        if not r_values:
            expectancy_R = None
            win_rate = None
            avg_win_R = None
            avg_loss_R = None
            profit_factor = None
            median_time_in_trade = None
        else:
            expectancy_R = sum(r_values) / len(r_values)
            winners = [r for r in r_values if r > 0]
            losers = [r for r in r_values if r <= 0]
            win_rate = len(winners) / len(r_values)
            avg_win_R = (
                sum(winners) / len(winners) if winners else None
            )
            avg_loss_R = (
                abs(sum(losers) / len(losers)) if losers else None
            )
            sum_wins = sum(winners) if winners else 0.0
            sum_losses_abs = abs(sum(losers)) if losers else 0.0
            if sum_losses_abs == 0.0:
                # No losses; profit_factor is undefined (infinite ratio sentinel).
                profit_factor = None
            else:
                profit_factor = sum_wins / sum_losses_abs
            days_held_values = [
                t.days_held for t in closed if t.days_held is not None
            ]
            median_time_in_trade = (
                statistics.median(days_held_values)
                if days_held_values else None
            )

    if n_triggered == 0:
        # Brief Sec 1.4 edge case: '0 triggered -> estimated_dollar = 0.0'.
        # Pre-empts the expectancy=None branch so all-untriggered substrates
        # render a clean zero rather than a missing sentinel.
        estimated_dollar_per_period: float | None = 0.0
    elif expectancy_R is None or substrate_window_days <= 0:
        # Codex R1 MAJOR #7 ACCEPTED-with-rationale: when triggered>0 but
        # expectancy is None (all open at data tail), the dollar projection
        # is INDETERMINATE -- closed-trade-derived expectancy hasn't formed
        # yet. Returning None (not 0.0) preserves the distinction between
        # 'no trades to extrapolate' (0.0) and 'trades pending resolution'
        # (None). Operator-paired: forward projection at this state would
        # require an assumed mid-trade R, which the brief does not specify.
        # Substrates with this pattern should be re-run after time elapses
        # so trades resolve, or characterized as 'forward-resolution
        # required' in the findings doc.
        estimated_dollar_per_period = None
    else:
        n_triggered_per_year = (n_triggered / substrate_window_days) * 365.0
        estimated_dollar_per_period = (
            n_triggered_per_year * expectancy_R * R_DOLLAR_SIZE_AT_7500_FLOOR
        )

    open_at_tail_rate = (
        open_at_tail_count / n_triggered if n_triggered > 0 else None
    )

    return ScorecardRow(
        ruleset_name=ruleset_name,
        substrate_name=substrate_name,
        n_patterns=n_patterns,
        n_triggered=n_triggered,
        n_closed=n_closed,
        expectancy_R=expectancy_R,
        win_rate=win_rate,
        avg_win_R=avg_win_R,
        avg_loss_R=avg_loss_R,
        profit_factor=profit_factor,
        trigger_conversion_rate=trigger_conversion_rate,
        median_time_in_trade_sessions=median_time_in_trade,
        open_at_tail_count=open_at_tail_count,
        open_at_tail_rate=open_at_tail_rate,
        estimated_dollar_per_period=estimated_dollar_per_period,
        substrate_window_days=substrate_window_days,
    )


# Field-name list used for CSV header emission; LOCKED via discriminating
# test in test_scorecard.py (test_scorecard_row_dataclass_shape_includes_all_9_metrics).
SCORECARD_CSV_HEADER: tuple[str, ...] = tuple(
    f.name for f in dc_fields(ScorecardRow)
)


def write_scorecard_csv(rows: list[ScorecardRow], output_path: Path) -> None:
    """Emit scorecard rows as CSV (one row per (ruleset, substrate) cell).

    Field order matches `SCORECARD_CSV_HEADER` (== ScorecardRow dataclass
    field declaration order).
    """
    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(SCORECARD_CSV_HEADER)
        for row in rows:
            writer.writerow(
                _csv_format_field(getattr(row, name))
                for name in SCORECARD_CSV_HEADER
            )


def _csv_format_field(value):
    """Format a scorecard field for CSV emission.

    - None -> empty string (NOT 'None' literal; downstream CSV consumers
      should treat empty as missing per pandas read_csv default semantics).
    - float -> 6-decimal-place fixed (consistent precision across rows).
    - int -> str.
    - str -> str (verbatim).
    """
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)
