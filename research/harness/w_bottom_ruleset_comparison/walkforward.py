"""Walk-forward backtest engine for D2 W-bottom ruleset comparison.

Extends D1's walk_forward (research/harness/double_bottom_w_backtest/walkforward.py)
with a generalized Ruleset protocol that supports SCALE-OUT semantics required
by Ruleset F (Qullamaggie momentum-burst). All other rulesets (A/B/C/D/E) use
the same protocol with at-most-one FullExit action per trade.

Per-bar protocol: `update_and_check` returns at most one Action per bar:
  - FullExit(price, reason): closes the entire remaining position; trade ends.
  - ScaleOut(fraction, price, reason): partial close of `fraction` of the
    INITIAL position; trade continues with `1 - cumulative_scale_out` remaining.
  - None: hold; no action this bar.

V1 supports at most ONE scale-out event per trade (Ruleset F: scale 1/3 at +2R
then trail remainder; brief Section 3.6). The state's `scale_out_fired` flag
prevents repeat scale-outs.

Trade outcomes preserve the 27-column D1 schema (brief Section 4.1) by folding
scale-out into:
  - exit_reason: the FINAL event's reason (e.g., `close_below_50d_gated_after_scaleout`)
  - r_multiple: weighted final R = fraction_sold_at_scale * R_at_scale +
                                   (1 - fraction_sold_at_scale) * R_at_final_exit
  - peak_unrealized_R: peak across all bars regardless of scale-out
  - drawdown_to_exit_R: peak_R - final_weighted_R

Entry rule (all rulesets, per dispatch brief Section 2 + D1 precedent):
  - Trigger search window: from max(trough_1, trough_2, effective_asof) + 1
    business day to effective_asof + 60 business days.
  - Trigger: first daily close > center_peak_price within search window.
  - Entry: NEXT session's Open after the trigger session.
  - Initial stop: trough_2 * 0.99 (Rulesets A/B/C/D/F);
                  max(trough_2 * 0.99, entry * 0.92) (Ruleset E).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

import numpy as np
import pandas as pd

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict


MAX_TRIGGER_SEARCH_BUSINESS_DAYS = 60

# Capital base for per-trade share-sizing dollar P&L (CLAUDE.md operator
# memory project_capital_risk_floor: max($7500 floor, actual_balance);
# floor is the artificial population-of-actionable-stocks baseline).
DEFAULT_CAPITAL_FLOOR_DOLLARS = 7500.0
# cfg.risk.max_risk_pct = 0.005 per CLAUDE.md gotcha (0.5% per trade).
DEFAULT_RISK_PCT = 0.005


# ---------------------------------------------------------------------------
# Actions emitted by rulesets per-bar
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FullExit:
    """Close entire remaining position at `price` with `reason` label."""

    price: float
    reason: str


@dataclass(frozen=True)
class ScaleOut:
    """Close `fraction` of the INITIAL position (not the remaining); trade
    continues with `1 - cumulative_fraction` remaining."""

    fraction: float
    price: float
    reason: str


Action = FullExit | ScaleOut


# ---------------------------------------------------------------------------
# Ruleset state (generic; rulesets stash their own data in `extra`)
# ---------------------------------------------------------------------------
@dataclass
class State:
    """Per-trade mutable state shared across all rulesets.

    Rulesets stash ruleset-specific data in `extra` (dict) to keep this
    dataclass shape minimal + generic.
    """

    current_stop: float
    breakeven_armed: bool = False
    scale_out_fired: bool = False
    scale_out_R: float | None = None
    scale_out_fraction: float | None = None
    scale_out_date: date | None = None
    scale_out_price: float | None = None
    momentum_gate_armed: bool = False
    initial_atr14: float | None = None  # captured at entry for F's gate
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ruleset protocol
# ---------------------------------------------------------------------------
class Ruleset(Protocol):
    name: str

    def initial_stop(
        self,
        *,
        verdict: PrimaryVerdict,
        entry_price: float,
    ) -> float:
        """Return the initial stop price for this ruleset.

        Default for A/B/C/D/F: verdict.initial_stop (trough_2 * 0.99).
        Ruleset E overrides: max(trough_2 * 0.99, entry * 0.92).
        """
        ...

    def init_state(
        self,
        *,
        verdict: PrimaryVerdict,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> State: ...

    def update_and_check(
        self,
        *,
        state: State,
        bars: pd.DataFrame,
        bar_idx: int,
        entry_idx: int,
        entry_price: float,
        initial_R: float,
    ) -> Action | None:
        """Returns ONE action this bar (FullExit / ScaleOut) or None to hold."""
        ...


# ---------------------------------------------------------------------------
# Trade dataclass (preserves D1's 27-column shape; brief Section 4.1)
# ---------------------------------------------------------------------------
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
    triggered: bool = False
    trade_pnl_dollars: float | None = None
    peak_unrealized_R: float | None = None
    drawdown_to_exit_R: float | None = None
    forward_bars_available: int = 0
    max_forward_close: float | None = None
    max_close_pct_of_peak: float | None = None
    days_t2_to_asof: int | None = None
    effective_asof_date: date | None = None
    max_observed_asof_date: date | None = None


# ---------------------------------------------------------------------------
# Indicator helpers (SMA / ATR; shared across rulesets)
# ---------------------------------------------------------------------------
def sma_at(bars: pd.DataFrame, bar_idx: int, window: int) -> float | None:
    """Simple moving average of Close over (bar_idx - window + 1 .. bar_idx)
    inclusive. Returns None if insufficient bars."""
    if bar_idx + 1 < window:
        return None
    closes = bars["Close"].iloc[bar_idx + 1 - window : bar_idx + 1]
    return float(closes.mean())


def atr_at(bars: pd.DataFrame, bar_idx: int, window: int) -> float | None:
    """Average True Range over the last `window` bars ending at bar_idx
    (inclusive). Requires bar_idx + 1 >= window + 1 for one prior close.

    Returns None if insufficient bars.
    """
    if bar_idx + 1 < window + 1:
        return None
    highs = bars["High"].iloc[bar_idx + 1 - window : bar_idx + 1]
    lows = bars["Low"].iloc[bar_idx + 1 - window : bar_idx + 1]
    prev_closes = bars["Close"].iloc[bar_idx - window : bar_idx]
    highs = highs.reset_index(drop=True)
    lows = lows.reset_index(drop=True)
    prev_closes = prev_closes.reset_index(drop=True)
    tr = pd.concat(
        [
            highs - lows,
            (highs - prev_closes).abs(),
            (lows - prev_closes).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return float(tr.mean())


# ---------------------------------------------------------------------------
# P&L helpers (same as D1)
# ---------------------------------------------------------------------------
def compute_share_count(entry_price: float, initial_stop: float) -> int:
    """Audit-only integer share count under fixed-risk sizing.

    PnL computation uses fractional notional per `compute_pnl_dollars_fractional`
    so wide-R patterns don't silently floor to 0 shares + $0 PnL.
    """
    R_unit = entry_price - initial_stop
    if R_unit <= 0:
        return 0
    risk_dollars = DEFAULT_CAPITAL_FLOOR_DOLLARS * DEFAULT_RISK_PCT
    return int(risk_dollars / R_unit)


def compute_pnl_dollars_fractional(
    entry_price: float, exit_price: float, initial_stop: float
) -> float:
    """Theoretical fractional-share dollar P&L; equals R_multiple * risk_dollars.

    For scale-out trades, caller passes the WEIGHTED-equivalent exit_price
    (entry + r_multiple_final * R_unit) so the helper returns the correct
    blended dollar PnL.
    """
    R_unit = entry_price - initial_stop
    if R_unit <= 0:
        return 0.0
    risk_dollars = DEFAULT_CAPITAL_FLOOR_DOLLARS * DEFAULT_RISK_PCT
    return (exit_price - entry_price) * (risk_dollars / R_unit)


# ---------------------------------------------------------------------------
# Trigger-search helpers (same semantic as D1)
# ---------------------------------------------------------------------------
def trigger_search_upper_bound(
    asof_date: date, max_business_days: int = MAX_TRIGGER_SEARCH_BUSINESS_DAYS
) -> date:
    """asof_date + max_business_days BUSINESS days (np.busday_offset)."""
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
    """First index i where bars.index[i].date() > lower_bound_exclusive AND
    <= upper_bound_inclusive AND bars["Close"].iloc[i] > trigger_threshold AND
    i+1 < len(bars) (next session exists for entry-open).
    """
    dates = pd.Index([d.date() if hasattr(d, "date") else d for d in bars.index])
    closes = bars["Close"].to_numpy()
    n = len(closes)
    for i in range(n - 1):
        d = dates[i]
        if d <= lower_bound_exclusive:
            continue
        if d > upper_bound_inclusive:
            return None
        if closes[i] > trigger_threshold:
            return i
    return None


# ---------------------------------------------------------------------------
# Walk-forward engine
# ---------------------------------------------------------------------------
def walk_forward(
    verdict: PrimaryVerdict,
    bars: pd.DataFrame,
    ruleset: Ruleset,
    *,
    max_trigger_search_business_days: int = MAX_TRIGGER_SEARCH_BUSINESS_DAYS,
) -> Trade:
    """Walk forward through `bars` for one (verdict, ruleset).

    Supports scale-out via the Ruleset protocol: ScaleOut actions reduce
    remaining position; the trade continues until FullExit or data tail.
    Weighted final R folds scale-out + final-exit R per their fractions.
    """
    backtest_asof = verdict.effective_asof_date
    days_t2_to_asof = (backtest_asof - verdict.trough_2_date).days
    n_total = len(bars)

    if n_total == 0:
        return _emit_untriggered(
            verdict, ruleset, "ohlcv_empty", days_t2_to_asof, 0, None, None
        )

    # Forward-search-window diagnostics for untriggered visibility (D1 parity).
    lower_bound = verdict.trigger_lower_bound_date
    upper_bound = trigger_search_upper_bound(
        backtest_asof, max_trigger_search_business_days
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
    initial_stop = ruleset.initial_stop(verdict=verdict, entry_price=entry_price)
    R = entry_price - initial_stop

    # Degenerate: entry gap-down through stop. Same as D1.
    if R <= 0:
        return Trade(
            pattern_id=verdict.pattern_id, ticker=verdict.ticker, ruleset_name=ruleset.name,
            anchor_asof_date=verdict.anchor_asof_date, trough_1_date=verdict.trough_1_date,
            effective_asof_date=verdict.effective_asof_date,
            max_observed_asof_date=verdict.max_observed_asof_date,
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
        verdict=verdict, bars=bars, entry_idx=entry_idx,
        entry_price=entry_price, initial_stop=initial_stop,
    )
    peak_R = 0.0

    for i in range(entry_idx, n_total):
        bar_high = float(bars["High"].iloc[i])
        bar_R = (bar_high - entry_price) / R
        if bar_R > peak_R:
            peak_R = bar_R
        action = ruleset.update_and_check(
            state=state, bars=bars, bar_idx=i, entry_idx=entry_idx,
            entry_price=entry_price, initial_R=R,
        )
        if action is None:
            continue
        exit_date_i = bars.index[i].date() if hasattr(bars.index[i], "date") else bars.index[i]
        if isinstance(action, ScaleOut):
            # Record the scale-out event + continue trading the remaining fraction.
            # V1 supports AT MOST ONE scale-out per trade; guard idempotency.
            if state.scale_out_fired:
                # Defensive: rulesets MUST NOT emit a second ScaleOut. Treat as
                # full-exit-at-current-close to surface the misbehavior.
                fallback_price = float(bars["Close"].iloc[i])
                return _emit_final_close(
                    verdict, ruleset.name, state, bars, n_total, peak_R, entry_idx,
                    entry_date, entry_price, initial_stop, R, exit_date_i,
                    fallback_price, "second_scaleout_invalid",
                    n_fwd_window, max_close, max_close_pct, days_t2_to_asof,
                )
            state.scale_out_fired = True
            state.scale_out_R = (action.price - entry_price) / R
            state.scale_out_fraction = action.fraction
            state.scale_out_date = exit_date_i
            state.scale_out_price = action.price
            # Continue loop to next bar; remainder rides per ruleset's trail rules.
            continue
        # FullExit: close remaining position.
        assert isinstance(action, FullExit)
        final_R_remainder = (action.price - entry_price) / R
        weighted_R = _weighted_R(state, final_R_remainder)
        synthetic_exit_price = entry_price + weighted_R * R
        pnl_dollars = compute_pnl_dollars_fractional(entry_price, synthetic_exit_price, initial_stop)
        exit_reason = (
            f"{action.reason}_after_scaleout" if state.scale_out_fired else action.reason
        )
        return Trade(
            pattern_id=verdict.pattern_id, ticker=verdict.ticker, ruleset_name=ruleset.name,
            anchor_asof_date=verdict.anchor_asof_date, trough_1_date=verdict.trough_1_date,
            effective_asof_date=verdict.effective_asof_date,
            max_observed_asof_date=verdict.max_observed_asof_date,
            center_peak_price=verdict.center_peak_price, trough_2_price=verdict.trough_2_price,
            composite_score=verdict.composite_score, initial_stop=initial_stop,
            entry_date=entry_date, entry_price=entry_price,
            exit_date=exit_date_i, exit_price=action.price,
            exit_reason=exit_reason, r_multiple=weighted_R,
            days_held=(i - entry_idx),
            status="closed",
            triggered=True,
            trade_pnl_dollars=pnl_dollars,
            peak_unrealized_R=peak_R,
            drawdown_to_exit_R=(peak_R - weighted_R),
            forward_bars_available=n_fwd_window,
            max_forward_close=max_close, max_close_pct_of_peak=max_close_pct,
            days_t2_to_asof=days_t2_to_asof,
        )

    # Data tail reached: open position; remainder unrealized.
    last_idx = n_total - 1
    last_close = float(bars.iloc[last_idx]["Close"])
    last_date = bars.index[last_idx].date() if hasattr(bars.index[last_idx], "date") else bars.index[last_idx]
    tail_R_remainder = (last_close - entry_price) / R
    weighted_R = _weighted_R(state, tail_R_remainder)
    synthetic_exit_price = entry_price + weighted_R * R
    pnl_dollars = compute_pnl_dollars_fractional(entry_price, synthetic_exit_price, initial_stop)
    tail_reason = (
        "open_at_data_tail_after_scaleout"
        if state.scale_out_fired
        else "open_at_data_tail"
    )
    return Trade(
        pattern_id=verdict.pattern_id, ticker=verdict.ticker, ruleset_name=ruleset.name,
        anchor_asof_date=verdict.anchor_asof_date, trough_1_date=verdict.trough_1_date,
        effective_asof_date=verdict.effective_asof_date,
        max_observed_asof_date=verdict.max_observed_asof_date,
        center_peak_price=verdict.center_peak_price, trough_2_price=verdict.trough_2_price,
        composite_score=verdict.composite_score, initial_stop=initial_stop,
        entry_date=entry_date, entry_price=entry_price,
        exit_date=last_date, exit_price=last_close,
        exit_reason=tail_reason,
        r_multiple=weighted_R,
        days_held=(last_idx - entry_idx),
        status="open",
        triggered=True,
        trade_pnl_dollars=pnl_dollars,
        peak_unrealized_R=peak_R,
        drawdown_to_exit_R=(peak_R - weighted_R),
        forward_bars_available=n_fwd_window,
        max_forward_close=max_close, max_close_pct_of_peak=max_close_pct,
        days_t2_to_asof=days_t2_to_asof,
    )


def _weighted_R(state: State, final_R_remainder: float) -> float:
    """Combine scale-out R + remainder R per their position fractions.

    Without scale-out: returns final_R_remainder verbatim.
    With scale-out: weighted = scale_R * scale_fraction + final_R * (1 - scale_fraction).
    """
    if not state.scale_out_fired or state.scale_out_R is None or state.scale_out_fraction is None:
        return final_R_remainder
    sf = state.scale_out_fraction
    return state.scale_out_R * sf + final_R_remainder * (1.0 - sf)


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
        effective_asof_date=verdict.effective_asof_date,
        max_observed_asof_date=verdict.max_observed_asof_date,
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


def _emit_final_close(
    verdict: PrimaryVerdict,
    ruleset_name: str,
    state: State,
    bars: pd.DataFrame,
    n_total: int,
    peak_R: float,
    entry_idx: int,
    entry_date: date,
    entry_price: float,
    initial_stop: float,
    R: float,
    exit_date_i: date,
    exit_price: float,
    exit_reason: str,
    n_fwd_window: int,
    max_close: float | None,
    max_close_pct: float | None,
    days_t2_to_asof: int,
) -> Trade:
    """Defensive emit when an unexpected per-bar state arises (e.g., second
    ScaleOut). Closes remaining position at given exit_price with given reason.
    """
    final_R_remainder = (exit_price - entry_price) / R
    weighted_R = _weighted_R(state, final_R_remainder)
    synthetic_exit_price = entry_price + weighted_R * R
    pnl_dollars = compute_pnl_dollars_fractional(entry_price, synthetic_exit_price, initial_stop)
    return Trade(
        pattern_id=verdict.pattern_id, ticker=verdict.ticker, ruleset_name=ruleset_name,
        anchor_asof_date=verdict.anchor_asof_date, trough_1_date=verdict.trough_1_date,
        effective_asof_date=verdict.effective_asof_date,
        max_observed_asof_date=verdict.max_observed_asof_date,
        center_peak_price=verdict.center_peak_price, trough_2_price=verdict.trough_2_price,
        composite_score=verdict.composite_score, initial_stop=initial_stop,
        entry_date=entry_date, entry_price=entry_price,
        exit_date=exit_date_i, exit_price=exit_price,
        exit_reason=exit_reason, r_multiple=weighted_R,
        days_held=None,
        status="closed",
        triggered=True,
        trade_pnl_dollars=pnl_dollars,
        peak_unrealized_R=peak_R,
        drawdown_to_exit_R=(peak_R - weighted_R),
        forward_bars_available=n_fwd_window,
        max_forward_close=max_close, max_close_pct_of_peak=max_close_pct,
        days_t2_to_asof=days_t2_to_asof,
    )
