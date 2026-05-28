"""Walk-forward engine variant supporting per-ruleset trigger predicates.

Sibling to research/harness/w_bottom_ruleset_comparison/walkforward.py
(byte-stable). The g2 variant accepts a `trigger_predicate(bars, candidate_idx,
verdict) -> bool` callback that gates whether a candidate trigger-bar (close >
center_peak_price within the search window) is admitted as the entry trigger.

The predicate is the structural differentiator of G/H/I rulesets vs A-F:
W-bottom-literature rulesets require volume confirmation at the breakout bar
(Bulkowski 1.3x 20-bar mean; O'Neil 1.4x 50-bar mean; Edwards-Magee 1.5x
rally-from-trough_2). A-F apply no such gate and use the bare close>threshold
check via `find_trigger_index`.

Brief Sec 2.1-2.3 LOCK -- G/H/I execution-price model:
  - Entry: at the TRIGGER BAR's CLOSE (NOT next-session open). Per brief
    line 146 "Entry price = close of breakout bar"; line 147 "Entry date
    = breakout bar date". DIVERGES from existing A-F's next-session-open
    convention; G2 represents idealized execution at close-of-breakout-bar
    per the canonical Bulkowski / O'Neil / Edwards-Magee literature.
  - Stop / SMA-break exit: at NEXT-BAR OPEN (NOT same-bar close). Per
    brief line 160 "Close < stop_price -> exit at next-bar open (with
    realistic slippage assumption per existing harness)". Rulesets emit
    `DeferredExit(reason)`; the ENGINE resolves exit_idx_canonical to
    i+1 (next-bar open) OR i (data tail) and assigns exit_price +
    exit_date + days_held coherently from exit_idx_canonical. At data
    tail (no bar i+1), status is 'open' + reason carries
    '_pending_at_tail' suffix per Codex R3 MAJOR #1 closure (the
    next-bar-open execution hasn't actually happened; the operator's
    market-on-open order resolves outside the backtest data window).
  - Target exit: at TARGET PRICE on first close >= target (limit-style
    fill assumption; unchanged from existing convention).

This engine duplicates the body of walk_forward to preserve byte-stability of
the existing harness. ZERO production swing/ writes; ZERO new Schwab API
calls; ZERO yfinance fetches at backtest time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Protocol

import pandas as pd

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.w_bottom_ruleset_comparison.walkforward import (
    FullExit,
    MAX_TRIGGER_SEARCH_BUSINESS_DAYS,
    ScaleOut,
    State,
    Trade,
    _emit_final_close,
    _emit_untriggered,
    _weighted_R,
    compute_pnl_dollars_fractional,
    trigger_search_upper_bound,
)


TriggerPredicate = Callable[[pd.DataFrame, int, PrimaryVerdict], bool]


class GhiRuleset(Protocol):
    """G2-specific ruleset protocol; extends the existing harness's
    Ruleset protocol with DeferredExit as a valid return type from
    `update_and_check`.

    Per Codex R3 MINOR #3 closure: the imported `Ruleset` protocol from
    research.harness.w_bottom_ruleset_comparison.walkforward declares
    `update_and_check -> FullExit | ScaleOut | None` (the existing
    harness's action set). G/H/I rulesets additionally emit
    DeferredExit for next-bar-open exit semantics (brief Sec 2.1-2.3
    LOCK). This local Protocol makes the wider G2-specific contract
    explicit for type-checking + future implementer reference.
    """

    name: str

    def initial_stop(
        self, *, verdict: PrimaryVerdict, entry_price: float
    ) -> float: ...

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
    ) -> "FullExit | ScaleOut | DeferredExit | None":
        """Returns ONE action this bar (FullExit / ScaleOut / DeferredExit)
        or None to hold."""
        ...


@dataclass(frozen=True)
class DeferredExit:
    """G2-specific action: signals 'exit on the NEXT bar at its open
    price', with data-tail fallback to current-bar close.

    Per brief Sec 2.1-2.3 LOCK (Codex R2 MAJOR #2 closure): when a
    ruleset detects a stop / SMA-break event at bar i, the exit happens
    on bar i+1 at its OPEN (a market-on-open order placed overnight).
    Both `exit_price` AND `exit_date` AND `days_held` reflect bar i+1.
    At data tail (no bar i+1), fall back to current-bar close + current
    bar's date + (bar_idx - entry_idx) holding period.

    Engine handles this action explicitly so the ruleset doesn't need to
    encode the offset in price/reason strings.
    """

    reason: str


# Backward-compat helper retained for tests that exercise the next-bar-open
# price computation directly. Engine no longer uses this; rulesets now
# emit DeferredExit and the engine computes price + offset.
def next_bar_open_price_or_close_at_tail(
    bars: pd.DataFrame, bar_idx: int
) -> float:
    """Return next bar's Open if next bar exists; else current bar's Close.

    Per Codex R2 MAJOR #2 closure, rulesets should prefer emitting
    `DeferredExit(reason=...)` for stop / SMA-break events; the engine
    handles price + exit_date + days_held consistently. This helper is
    retained for callsites that need only the price (e.g., diagnostics).
    """
    if bar_idx + 1 < len(bars):
        return float(bars["Open"].iloc[bar_idx + 1])
    return float(bars["Close"].iloc[bar_idx])


def find_trigger_index_with_predicate(
    bars: pd.DataFrame,
    *,
    verdict: PrimaryVerdict,
    trigger_threshold: float,
    lower_bound_exclusive: date,
    upper_bound_inclusive: date,
    trigger_predicate: TriggerPredicate,
) -> int | None:
    """First index i where bars.index[i].date() > lower_bound_exclusive AND
    <= upper_bound_inclusive AND bars["Close"].iloc[i] > trigger_threshold AND
    trigger_predicate(bars, i, verdict) returns True.

    Per brief Sec 2.1-2.3 LOCK + Codex R2 MAJOR #1 closure: entry is at
    the trigger bar's CLOSE (not next-bar open), so NO requirement that
    bar i+1 exists. The final bar of data is a valid trigger candidate.

    Mirrors find_trigger_index from the existing harness with the predicate
    extension applied AFTER the close>threshold gate. Predicate-rejected
    bars are skipped; the loop continues searching forward through the
    window until an eligible bar is found OR the window upper bound is
    reached.

    Per brief Sec 2.1-2.3 LOCK (Codex R2 MAJOR #1 closure): entry is at
    the trigger bar's CLOSE (not next-bar open), so the trigger bar
    itself can be the LAST bar of data -- no requirement that bar i+1
    exists for entry. The search loop iterates `range(n)` to include
    the final bar as a valid trigger candidate. Trades triggered on the
    final bar will exit at data tail with status='open'.
    """
    dates = pd.Index([d.date() if hasattr(d, "date") else d for d in bars.index])
    closes = bars["Close"].to_numpy()
    n = len(closes)
    for i in range(n):
        d = dates[i]
        if d <= lower_bound_exclusive:
            continue
        if d > upper_bound_inclusive:
            return None
        if closes[i] <= trigger_threshold:
            continue
        if not trigger_predicate(bars, i, verdict):
            continue
        return i
    return None


def walk_forward_with_trigger_predicate(
    verdict: PrimaryVerdict,
    bars: pd.DataFrame,
    ruleset: GhiRuleset,
    *,
    trigger_predicate: TriggerPredicate,
    max_trigger_search_business_days: int = MAX_TRIGGER_SEARCH_BUSINESS_DAYS,
) -> Trade:
    """Walk forward through `bars` for one (verdict, ruleset, predicate).

    Mirrors walk_forward from the existing harness, except trigger-bar
    selection consults `trigger_predicate` to admit/reject each candidate
    close>threshold bar. Predicate-rejected bars are SKIPPED (the search
    continues forward); rejection of all candidates emits an untriggered
    trade row.

    The predicate signature is (bars_df, candidate_idx, verdict) -> bool;
    candidate_idx is the trigger-bar position in `bars`. Per brief Sec
    2.1-2.3 LOCK, entry is at the TRIGGER BAR'S CLOSE (bars.iloc[
    candidate_idx]['Close']), NOT the next-bar open.
    """
    if not callable(trigger_predicate):
        raise TypeError(
            "trigger_predicate must be callable; got "
            f"{type(trigger_predicate).__name__}"
        )

    backtest_asof = verdict.effective_asof_date
    days_t2_to_asof = (backtest_asof - verdict.trough_2_date).days
    n_total = len(bars)

    if n_total == 0:
        return _emit_untriggered(
            verdict, ruleset, "ohlcv_empty", days_t2_to_asof, 0, None, None
        )

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

    trigger_idx = find_trigger_index_with_predicate(
        bars,
        verdict=verdict,
        trigger_threshold=verdict.trigger_threshold,
        lower_bound_exclusive=lower_bound,
        upper_bound_inclusive=upper_bound,
        trigger_predicate=trigger_predicate,
    )
    if trigger_idx is None:
        return _emit_untriggered(
            verdict, ruleset, "untriggered", days_t2_to_asof, n_fwd_window,
            max_close, max_close_pct,
        )

    # Brief Sec 2.1-2.3 LOCK: entry at the TRIGGER BAR's close (NOT next-
    # session open). Diverges from existing harness convention; faithful
    # to brief line 146 + 147.
    entry_idx = trigger_idx
    entry_date = (
        bars.index[entry_idx].date()
        if hasattr(bars.index[entry_idx], "date")
        else bars.index[entry_idx]
    )
    entry_price = float(bars["Close"].iloc[entry_idx])
    initial_stop = ruleset.initial_stop(verdict=verdict, entry_price=entry_price)
    R = entry_price - initial_stop

    if R <= 0:
        return Trade(
            pattern_id=verdict.pattern_id, ticker=verdict.ticker,
            ruleset_name=ruleset.name,
            anchor_asof_date=verdict.anchor_asof_date,
            trough_1_date=verdict.trough_1_date,
            effective_asof_date=verdict.effective_asof_date,
            max_observed_asof_date=verdict.max_observed_asof_date,
            center_peak_price=verdict.center_peak_price,
            trough_2_price=verdict.trough_2_price,
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

        # Per brief Sec 2.1-2.3 LOCK + Codex R2 MAJOR #2 closure: when
        # the ruleset emits DeferredExit, compute the exit bar idx (i+1
        # if exists; else i for data-tail fallback). exit_price +
        # exit_date + days_held all reflect the SAME bar so per_trade
        # detail + median_time_in_trade_sessions stay coherent.
        #
        # Codex R3 MAJOR #1 closure: at data tail (no bar i+1), the
        # next-bar-open execution hasn't happened yet. Mark status='open'
        # with reason '<original>_pending_at_tail' so the trade counts
        # toward open_at_tail_count (per brief Sec 1.4 metric #8
        # "Unresolved fraction") rather than contaminating closed-trade
        # performance metrics. The exit_price = current-bar close (best-
        # known last price for unrealized-R reporting); a real operator
        # would resolve the position on the first available next session
        # outside the backtest data window.
        if isinstance(action, DeferredExit):
            if i + 1 < n_total:
                exit_idx_canonical = i + 1
                exit_price_canonical = float(bars["Open"].iloc[i + 1])
                status_canonical = "closed"
                reason_suffix = ""
            else:
                exit_idx_canonical = i
                exit_price_canonical = float(bars["Close"].iloc[i])
                status_canonical = "open"
                reason_suffix = "_pending_at_tail"
            exit_date_i = (
                bars.index[exit_idx_canonical].date()
                if hasattr(bars.index[exit_idx_canonical], "date")
                else bars.index[exit_idx_canonical]
            )
            final_R_remainder = (exit_price_canonical - entry_price) / R
            weighted_R = _weighted_R(state, final_R_remainder)
            # Codex R3 MAJOR #2 closure: peak_R was computed BEFORE
            # update_and_check using bar i's High; for next-bar-open
            # exits, bar i+1's open price may exceed prior peak, making
            # weighted_R > peak_R and drawdown_to_exit_R negative.
            # Defensively widen peak to include the actual exit R.
            peak_R = max(peak_R, weighted_R)
            synthetic_exit_price = entry_price + weighted_R * R
            pnl_dollars = compute_pnl_dollars_fractional(
                entry_price, synthetic_exit_price, initial_stop
            )
            base_reason = (
                f"{action.reason}_after_scaleout"
                if state.scale_out_fired
                else action.reason
            )
            exit_reason = f"{base_reason}{reason_suffix}"
            return Trade(
                pattern_id=verdict.pattern_id, ticker=verdict.ticker,
                ruleset_name=ruleset.name,
                anchor_asof_date=verdict.anchor_asof_date,
                trough_1_date=verdict.trough_1_date,
                effective_asof_date=verdict.effective_asof_date,
                max_observed_asof_date=verdict.max_observed_asof_date,
                center_peak_price=verdict.center_peak_price,
                trough_2_price=verdict.trough_2_price,
                composite_score=verdict.composite_score,
                initial_stop=initial_stop,
                entry_date=entry_date, entry_price=entry_price,
                exit_date=exit_date_i, exit_price=exit_price_canonical,
                exit_reason=exit_reason, r_multiple=weighted_R,
                days_held=(exit_idx_canonical - entry_idx),
                status=status_canonical,
                triggered=True,
                trade_pnl_dollars=pnl_dollars,
                peak_unrealized_R=peak_R,
                drawdown_to_exit_R=(peak_R - weighted_R),
                forward_bars_available=n_fwd_window,
                max_forward_close=max_close, max_close_pct_of_peak=max_close_pct,
                days_t2_to_asof=days_t2_to_asof,
            )

        exit_date_i = (
            bars.index[i].date()
            if hasattr(bars.index[i], "date")
            else bars.index[i]
        )
        if isinstance(action, ScaleOut):
            if state.scale_out_fired:
                fallback_price = float(bars["Close"].iloc[i])
                return _emit_final_close(
                    verdict, ruleset.name, state, bars, n_total, peak_R,
                    entry_idx, entry_date, entry_price, initial_stop, R,
                    exit_date_i, fallback_price, "second_scaleout_invalid",
                    n_fwd_window, max_close, max_close_pct, days_t2_to_asof,
                )
            state.scale_out_fired = True
            state.scale_out_R = (action.price - entry_price) / R
            state.scale_out_fraction = action.fraction
            state.scale_out_date = exit_date_i
            state.scale_out_price = action.price
            continue
        assert isinstance(action, FullExit)
        final_R_remainder = (action.price - entry_price) / R
        weighted_R = _weighted_R(state, final_R_remainder)
        synthetic_exit_price = entry_price + weighted_R * R
        pnl_dollars = compute_pnl_dollars_fractional(
            entry_price, synthetic_exit_price, initial_stop
        )
        exit_reason = (
            f"{action.reason}_after_scaleout"
            if state.scale_out_fired
            else action.reason
        )
        return Trade(
            pattern_id=verdict.pattern_id, ticker=verdict.ticker,
            ruleset_name=ruleset.name,
            anchor_asof_date=verdict.anchor_asof_date,
            trough_1_date=verdict.trough_1_date,
            effective_asof_date=verdict.effective_asof_date,
            max_observed_asof_date=verdict.max_observed_asof_date,
            center_peak_price=verdict.center_peak_price,
            trough_2_price=verdict.trough_2_price,
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

    last_idx = n_total - 1
    last_close = float(bars.iloc[last_idx]["Close"])
    last_date = (
        bars.index[last_idx].date()
        if hasattr(bars.index[last_idx], "date")
        else bars.index[last_idx]
    )
    tail_R_remainder = (last_close - entry_price) / R
    weighted_R = _weighted_R(state, tail_R_remainder)
    synthetic_exit_price = entry_price + weighted_R * R
    pnl_dollars = compute_pnl_dollars_fractional(
        entry_price, synthetic_exit_price, initial_stop
    )
    tail_reason = (
        "open_at_data_tail_after_scaleout"
        if state.scale_out_fired
        else "open_at_data_tail"
    )
    return Trade(
        pattern_id=verdict.pattern_id, ticker=verdict.ticker,
        ruleset_name=ruleset.name,
        anchor_asof_date=verdict.anchor_asof_date,
        trough_1_date=verdict.trough_1_date,
        effective_asof_date=verdict.effective_asof_date,
        max_observed_asof_date=verdict.max_observed_asof_date,
        center_peak_price=verdict.center_peak_price,
        trough_2_price=verdict.trough_2_price,
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
