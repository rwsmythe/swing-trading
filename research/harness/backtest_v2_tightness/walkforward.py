"""Walk-forward backtest engine for a single (pattern, ruleset) tuple.

Pure function: consumes pivot/initial_stop + forward OHLCV bars; emits Trade outcome.
No DB writes; no archive writes; no production-state mutation.

Entry rule (all rulesets):
  - Trigger = first session AFTER first_data_asof_date where Close > pivot.
  - Entry = NEXT session's Open after the trigger session.
  - Initial stop = V1-persisted candidates.initial_stop.

Exit rules: see rulesets.py — each ruleset implements `update_stop_and_check_exit`.

Untriggered: if no session crosses pivot before data tail (final available bar),
status='untriggered'; R-multiple is None; excluded from win/loss tally.

Open positions at data tail (final bar 2026-05-22 or last available): status='open';
R-multiple computed relative to last close; flagged separately.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from research.harness.backtest_v2_tightness.patterns import Pattern
from research.harness.backtest_v2_tightness.rulesets import Ruleset


@dataclass(frozen=True)
class Trade:
    pattern_id: str
    ticker: str
    ruleset_name: str
    pivot: float
    initial_stop: float
    entry_date: date | None
    entry_price: float | None
    exit_date: date | None
    exit_price: float | None
    exit_reason: str  # 'stop_hit' | 'trail_stop' | 'target_3R' | 'close_below_50d' | 'untriggered' | 'open'
    r_multiple: float | None
    days_held: int | None
    status: str  # 'closed' | 'untriggered' | 'open'
    n_eval_runs_in_pattern: int = 1
    forward_bars_available: int = 0
    max_forward_close: float | None = None  # max Close in forward window (for near-miss diagnostic)
    max_close_pct_of_pivot: float | None = None  # max_close / pivot * 100

    @property
    def R(self) -> float | None:
        """Per-share R unit (entry - initial_stop)."""
        if self.entry_price is None:
            return None
        return self.entry_price - self.initial_stop


def find_entry_index(forward_bars: pd.DataFrame, pivot: float) -> int | None:
    """Find first index i in forward_bars where Close[i] > pivot AND i+1 < len.

    Returns the TRIGGER index (i) — entry occurs at forward_bars.iloc[i+1].Open.
    Returns None if no triggering session has a next-session Open available.
    """
    closes = forward_bars["Close"].to_numpy()
    n = len(closes)
    for i in range(n - 1):  # need i+1 next session
        if closes[i] > pivot:
            return i
    return None


def walk_forward(
    pattern: Pattern,
    forward_bars: pd.DataFrame,
    ruleset: Ruleset,
) -> Trade:
    """Walk forward through `forward_bars` (bars AFTER pattern.first_data_asof_date)
    applying entry trigger + ruleset stop-update + exit logic.

    forward_bars must be sorted ascending by date with index = DatetimeIndex,
    columns Open/High/Low/Close/Volume.
    """
    # Always compute the near-miss diagnostic for the Trade row (informative
    # for negative findings where most patterns never break out).
    n_forward = len(forward_bars)
    max_close = float(forward_bars["Close"].max()) if n_forward else None
    max_close_pct = (max_close / pattern.pivot * 100) if (max_close and pattern.pivot) else None

    trigger_idx = find_entry_index(forward_bars, pattern.pivot)
    if trigger_idx is None:
        return Trade(
            pattern_id=pattern.pattern_id,
            ticker=pattern.ticker,
            ruleset_name=ruleset.name,
            pivot=pattern.pivot,
            initial_stop=pattern.initial_stop,
            entry_date=None,
            entry_price=None,
            exit_date=None,
            exit_price=None,
            exit_reason="untriggered",
            r_multiple=None,
            days_held=None,
            status="untriggered",
            n_eval_runs_in_pattern=pattern.n_runs,
            forward_bars_available=n_forward,
            max_forward_close=max_close,
            max_close_pct_of_pivot=max_close_pct,
        )

    entry_idx = trigger_idx + 1
    entry_bar = forward_bars.iloc[entry_idx]
    entry_date = forward_bars.index[entry_idx].date()
    entry_price = float(entry_bar["Open"])
    R = entry_price - pattern.initial_stop
    if R <= 0:
        # Degenerate: entry price <= initial stop (entry gap-down through stop on entry session).
        return Trade(
            pattern_id=pattern.pattern_id,
            ticker=pattern.ticker,
            ruleset_name=ruleset.name,
            pivot=pattern.pivot,
            initial_stop=pattern.initial_stop,
            entry_date=entry_date,
            entry_price=entry_price,
            exit_date=entry_date,
            exit_price=entry_price,
            exit_reason="entry_gap_below_stop",
            r_multiple=0.0,
            days_held=0,
            status="closed",
            n_eval_runs_in_pattern=pattern.n_runs,
            forward_bars_available=n_forward,
            max_forward_close=max_close,
            max_close_pct_of_pivot=max_close_pct,
        )

    # Initialize ruleset state. We pass the FULL forward_bars + entry_idx;
    # each ruleset has access to historical bars for SMA computations.
    state = ruleset.init_state(
        pattern=pattern,
        forward_bars=forward_bars,
        entry_idx=entry_idx,
        entry_price=entry_price,
        initial_stop=pattern.initial_stop,
    )

    n = len(forward_bars)
    for i in range(entry_idx, n):
        bar = forward_bars.iloc[i]
        exit_price, exit_reason = ruleset.update_stop_and_check_exit(
            state=state,
            bar_idx=i,
            bar=bar,
            forward_bars=forward_bars,
            entry_price=entry_price,
            initial_R=R,
        )
        if exit_price is not None and exit_reason is not None:
            exit_date = forward_bars.index[i].date()
            r_mult = (exit_price - entry_price) / R
            return Trade(
                pattern_id=pattern.pattern_id,
                ticker=pattern.ticker,
                ruleset_name=ruleset.name,
                pivot=pattern.pivot,
                initial_stop=pattern.initial_stop,
                entry_date=entry_date,
                entry_price=entry_price,
                exit_date=exit_date,
                exit_price=exit_price,
                exit_reason=exit_reason,
                r_multiple=r_mult,
                days_held=(exit_date - entry_date).days,
                status="closed",
                n_eval_runs_in_pattern=pattern.n_runs,
                forward_bars_available=n_forward,
                max_forward_close=max_close,
                max_close_pct_of_pivot=max_close_pct,
            )

    # Data tail reached without exit -- open position.
    last_idx = n - 1
    last_close = float(forward_bars.iloc[last_idx]["Close"])
    last_date = forward_bars.index[last_idx].date()
    return Trade(
        pattern_id=pattern.pattern_id,
        ticker=pattern.ticker,
        ruleset_name=ruleset.name,
        pivot=pattern.pivot,
        initial_stop=pattern.initial_stop,
        entry_date=entry_date,
        entry_price=entry_price,
        exit_date=last_date,
        exit_price=last_close,
        exit_reason="open_at_data_tail",
        r_multiple=(last_close - entry_price) / R,
        days_held=(last_date - entry_date).days,
        status="open",
        n_eval_runs_in_pattern=pattern.n_runs,
        forward_bars_available=n_forward,
        max_forward_close=max_close,
        max_close_pct_of_pivot=max_close_pct,
    )
