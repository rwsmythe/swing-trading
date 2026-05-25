"""Walk-forward backtest engine for a single (PrimaryVerdict, ruleset) tuple.

Entry rule (all rulesets, per dispatch brief §2):
  - Trigger search window: from max(trough_1, trough_2, anchor_asof) + 1
    business day to min(anchor_asof + MAX_TRIGGER_SEARCH_BUSINESS_DAYS,
    archive_tail).
  - Trigger: first daily close > center_peak_price within search window.
  - Entry: NEXT session's Open after the trigger session. If no next session
    exists in the archive (e.g., trigger fires on archive tail), pattern is
    `untriggered` and the next-bar-open requirement disqualifies the late
    trigger.
  - Initial stop: trough_2_price * 0.99 (canonical W right-shoulder buffer).

Walk-forward: AFTER entry the engine walks ALL subsequent bars in the FULL
archive (not just within the 60-BD search window) -- this lets the trade
run its course until a ruleset's exit condition fires OR data tail is
reached. SMA21/SMA50 use the full archive's history for backward lookback.

Trade outcome: closed (any exit_reason in ruleset's lexicon),
untriggered (no qualifying close-above-peak found in search window),
open (entered but data tail reached without exit), or one of:
  - ohlcv_missing (read raised; pre-call exception)
  - degenerate_entry_gap_below_stop (entry bar open <= initial_stop)

R-multiple = (exit_price - entry_price) / (entry_price - initial_stop)
when entry + stop both defined; None otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.double_bottom_w_backtest.rulesets import Ruleset


MAX_TRIGGER_SEARCH_BUSINESS_DAYS = 60

# Capital base for per-trade share-sizing dollar P&L (per CLAUDE.md operator
# memory `project_capital_risk_floor`: max($7500 floor, actual_balance);
# floor is the artificial population-of-actionable-stocks baseline).
DEFAULT_CAPITAL_FLOOR_DOLLARS = 7500.0
# cfg.risk.max_risk_pct = 0.005 per CLAUDE.md gotcha (0.5% per trade).
DEFAULT_RISK_PCT = 0.005


@dataclass(frozen=True)
class Trade:
    pattern_id: str
    ticker: str
    ruleset_name: str
    anchor_asof_date: date
    trough_1_date: date
    center_peak_price: float
    trough_2_price: float
    composite_score: float
    initial_stop: float
    entry_date: date | None
    entry_price: float | None
    exit_date: date | None
    exit_price: float | None
    exit_reason: str
    r_multiple: float | None
    days_held: int | None
    status: str  # 'closed' | 'untriggered' | 'open' | 'error'
    triggered: bool = False  # Codex R1 M#7
    trade_pnl_dollars: float | None = None  # Codex R1 M#7
    peak_unrealized_R: float | None = None  # Codex R1 M#7
    drawdown_to_exit_R: float | None = None  # Codex R1 M#7 (peak_R - exit_R)
    forward_bars_available: int = 0
    max_forward_close: float | None = None
    max_close_pct_of_peak: float | None = None
    days_t2_to_asof: int | None = None

    @property
    def R(self) -> float | None:
        if self.entry_price is None:
            return None
        denom = self.entry_price - self.initial_stop
        if denom <= 0:
            return None
        return denom


def _compute_share_count(entry_price: float, initial_stop: float) -> int:
    """Per-trade share count under fixed-risk sizing.

    Capital base = max($7500 floor, actual_balance) per
    `project_capital_risk_floor` memory. V1 backtest uses floor (no live
    balance integration); shares = floor(capital * risk_pct / R_unit).
    """
    R_unit = entry_price - initial_stop
    if R_unit <= 0:
        return 0
    risk_dollars = DEFAULT_CAPITAL_FLOOR_DOLLARS * DEFAULT_RISK_PCT
    return int(risk_dollars / R_unit)


def _compute_pnl_dollars(
    entry_price: float, exit_price: float, shares: int
) -> float:
    return (exit_price - entry_price) * shares


def _trigger_search_upper_bound(
    asof_date: date, max_business_days: int = MAX_TRIGGER_SEARCH_BUSINESS_DAYS
) -> date:
    """asof_date + max_business_days BUSINESS days (np.busday_offset semantics).

    Example: asof=2026-05-22 (Fri), +60 BD → roughly 2026-08-15.
    """
    return np.busday_offset(asof_date, max_business_days, roll="forward").astype(
        "datetime64[D]"
    ).astype(date)


def find_trigger_index(
    bars: pd.DataFrame,
    *,
    trigger_threshold: float,
    lower_bound_exclusive: date,
    upper_bound_inclusive: date,
) -> int | None:
    """Find first index i where bars.index[i].date() > lower_bound_exclusive AND
    <= upper_bound_inclusive AND bars["Close"].iloc[i] > trigger_threshold AND
    i+1 < len(bars) (next session exists for entry-open).

    Returns the TRIGGER index (i); entry happens at i+1.
    """
    dates = pd.Index([d.date() if hasattr(d, "date") else d for d in bars.index])
    closes = bars["Close"].to_numpy()
    n = len(closes)
    for i in range(n - 1):  # need i+1 for entry-open
        d = dates[i]
        if d <= lower_bound_exclusive:
            continue
        if d > upper_bound_inclusive:
            return None  # search window exhausted; no later bar will qualify
        if closes[i] > trigger_threshold:
            return i
    return None


def walk_forward(
    verdict: PrimaryVerdict,
    bars: pd.DataFrame,
    ruleset: Ruleset,
    *,
    max_trigger_search_business_days: int = MAX_TRIGGER_SEARCH_BUSINESS_DAYS,
) -> Trade:
    """Walk forward through the FULL archive `bars` for one (verdict, ruleset).

    `bars` is the full archive (ascending DatetimeIndex; Open/High/Low/Close/Volume).
    Entry trigger search is bounded to (max(structural anchors)+1 day,
    asof+max_BD]; walk-forward AFTER entry uses bars to archive end.
    """
    days_t2_to_asof = (verdict.anchor_asof_date - verdict.trough_2_date).days
    n_total = len(bars)

    # Trivial-no-bars short-circuit
    if n_total == 0:
        return _emit_untriggered(
            verdict, ruleset, "ohlcv_empty", days_t2_to_asof, 0, None, None
        )

    # Build helper-window summary for diagnostic columns (max close in
    # forward search window for near-miss reporting).
    lower_bound = verdict.trigger_lower_bound_date
    upper_bound = _trigger_search_upper_bound(
        verdict.anchor_asof_date, max_trigger_search_business_days
    )
    dates_idx = pd.Index([d.date() if hasattr(d, "date") else d for d in bars.index])
    in_window_mask = (dates_idx > lower_bound) & (dates_idx <= upper_bound)
    fwd_window_bars = bars.loc[in_window_mask.tolist()]
    n_fwd_window = len(fwd_window_bars)
    if n_fwd_window:
        max_close = float(fwd_window_bars["Close"].max())
        max_close_pct = (
            max_close / verdict.center_peak_price * 100
            if verdict.center_peak_price
            else None
        )
    else:
        max_close = None
        max_close_pct = None

    trigger_idx = find_trigger_index(
        bars,
        trigger_threshold=verdict.trigger_threshold,
        lower_bound_exclusive=lower_bound,
        upper_bound_inclusive=upper_bound,
    )
    if trigger_idx is None:
        return _emit_untriggered(
            verdict, ruleset, "untriggered", days_t2_to_asof, n_fwd_window,
            max_close, max_close_pct,
        )

    entry_idx = trigger_idx + 1
    entry_bar = bars.iloc[entry_idx]
    entry_date = bars.index[entry_idx].date() if hasattr(bars.index[entry_idx], "date") else bars.index[entry_idx]
    entry_price = float(entry_bar["Open"])
    initial_stop = verdict.initial_stop
    R = entry_price - initial_stop

    # Degenerate: entry gap-down through stop. Position never opens; record as
    # synthetic closed trade with r_multiple=0 (no fill scenario but emit row
    # for transparency).
    if R <= 0:
        return Trade(
            pattern_id=verdict.pattern_id, ticker=verdict.ticker, ruleset_name=ruleset.name,
            anchor_asof_date=verdict.anchor_asof_date, trough_1_date=verdict.trough_1_date,
            center_peak_price=verdict.center_peak_price, trough_2_price=verdict.trough_2_price,
            composite_score=verdict.composite_score, initial_stop=initial_stop,
            entry_date=entry_date, entry_price=entry_price,
            exit_date=entry_date, exit_price=entry_price,
            exit_reason="entry_gap_below_stop",
            r_multiple=0.0, days_held=0, status="closed",
            triggered=True,
            trade_pnl_dollars=0.0,
            peak_unrealized_R=0.0,
            drawdown_to_exit_R=0.0,
            forward_bars_available=n_fwd_window,
            max_forward_close=max_close, max_close_pct_of_peak=max_close_pct,
            days_t2_to_asof=days_t2_to_asof,
        )

    state = ruleset.init_state(
        bars=bars, entry_idx=entry_idx, entry_price=entry_price, initial_stop=initial_stop,
    )
    shares = _compute_share_count(entry_price, initial_stop)
    # Peak unrealized R tracked across bars for the drawdown_to_exit_R metric
    # per dispatch brief §4.1 + Codex R1 M#7. Uses intraday High (favorable
    # excursion) to capture true peak; symmetric to the close-based exit
    # semantic of the rulesets but conventional MFE accounting.
    peak_R = 0.0

    for i in range(entry_idx, n_total):
        bar_high = float(bars["High"].iloc[i])
        bar_R = (bar_high - entry_price) / R
        if bar_R > peak_R:
            peak_R = bar_R
        exit_price, exit_reason = ruleset.update_and_check_exit(
            state=state, bars=bars, bar_idx=i,
            entry_price=entry_price, initial_R=R,
        )
        if exit_price is not None and exit_reason is not None:
            exit_date = bars.index[i].date() if hasattr(bars.index[i], "date") else bars.index[i]
            r_mult = (exit_price - entry_price) / R
            pnl_dollars = _compute_pnl_dollars(entry_price, exit_price, shares)
            return Trade(
                pattern_id=verdict.pattern_id, ticker=verdict.ticker, ruleset_name=ruleset.name,
                anchor_asof_date=verdict.anchor_asof_date, trough_1_date=verdict.trough_1_date,
                center_peak_price=verdict.center_peak_price, trough_2_price=verdict.trough_2_price,
                composite_score=verdict.composite_score, initial_stop=initial_stop,
                entry_date=entry_date, entry_price=entry_price,
                exit_date=exit_date, exit_price=exit_price,
                exit_reason=exit_reason, r_multiple=r_mult,
                days_held=(exit_date - entry_date).days,
                status="closed",
                triggered=True,
                trade_pnl_dollars=pnl_dollars,
                peak_unrealized_R=peak_R,
                drawdown_to_exit_R=(peak_R - r_mult),
                forward_bars_available=n_fwd_window,
                max_forward_close=max_close, max_close_pct_of_peak=max_close_pct,
                days_t2_to_asof=days_t2_to_asof,
            )

    # Data tail reached without exit
    last_idx = n_total - 1
    last_close = float(bars.iloc[last_idx]["Close"])
    last_date = bars.index[last_idx].date() if hasattr(bars.index[last_idx], "date") else bars.index[last_idx]
    tail_r = (last_close - entry_price) / R
    tail_pnl = _compute_pnl_dollars(entry_price, last_close, shares)
    return Trade(
        pattern_id=verdict.pattern_id, ticker=verdict.ticker, ruleset_name=ruleset.name,
        anchor_asof_date=verdict.anchor_asof_date, trough_1_date=verdict.trough_1_date,
        center_peak_price=verdict.center_peak_price, trough_2_price=verdict.trough_2_price,
        composite_score=verdict.composite_score, initial_stop=initial_stop,
        entry_date=entry_date, entry_price=entry_price,
        exit_date=last_date, exit_price=last_close,
        exit_reason="open_at_data_tail",
        r_multiple=tail_r,
        days_held=(last_date - entry_date).days,
        status="open",
        triggered=True,
        trade_pnl_dollars=tail_pnl,
        peak_unrealized_R=peak_R,
        drawdown_to_exit_R=(peak_R - tail_r),
        forward_bars_available=n_fwd_window,
        max_forward_close=max_close, max_close_pct_of_peak=max_close_pct,
        days_t2_to_asof=days_t2_to_asof,
    )


def _emit_untriggered(
    verdict: PrimaryVerdict,
    ruleset: Ruleset,
    exit_reason: str,
    days_t2_to_asof: int,
    n_fwd_window: int,
    max_close: float | None,
    max_close_pct: float | None,
) -> Trade:
    return Trade(
        pattern_id=verdict.pattern_id, ticker=verdict.ticker, ruleset_name=ruleset.name,
        anchor_asof_date=verdict.anchor_asof_date, trough_1_date=verdict.trough_1_date,
        center_peak_price=verdict.center_peak_price, trough_2_price=verdict.trough_2_price,
        composite_score=verdict.composite_score, initial_stop=verdict.initial_stop,
        entry_date=None, entry_price=None,
        exit_date=None, exit_price=None,
        exit_reason=exit_reason, r_multiple=None, days_held=None,
        status="untriggered",
        triggered=False,
        trade_pnl_dollars=None,
        peak_unrealized_R=None,
        drawdown_to_exit_R=None,
        forward_bars_available=n_fwd_window,
        max_forward_close=max_close, max_close_pct_of_peak=max_close_pct,
        days_t2_to_asof=days_t2_to_asof,
    )
