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

This engine duplicates the body of walk_forward to preserve byte-stability of
the existing harness. The duplicated section is the per-bar simulation loop +
the trade-emit helpers; the only material change vs walk_forward is the
trigger-search step which calls `find_trigger_index_with_predicate` instead
of `find_trigger_index`.

ZERO production swing/ writes; ZERO new Schwab API calls; ZERO yfinance
fetches at backtest time.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Protocol

import pandas as pd

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.w_bottom_ruleset_comparison.walkforward import (
    FullExit,
    MAX_TRIGGER_SEARCH_BUSINESS_DAYS,
    Ruleset,
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
    i+1 < len(bars) (next session exists for entry-open) AND
    trigger_predicate(bars, i, verdict) returns True.

    Mirrors find_trigger_index from the existing harness with the predicate
    extension applied AFTER the close>threshold gate. Predicate-rejected
    bars are skipped; the loop continues searching forward through the
    window until an eligible bar is found OR the window upper bound is
    reached.
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
        if closes[i] <= trigger_threshold:
            continue
        if not trigger_predicate(bars, i, verdict):
            continue
        return i
    return None


def walk_forward_with_trigger_predicate(
    verdict: PrimaryVerdict,
    bars: pd.DataFrame,
    ruleset: Ruleset,
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
    candidate_idx is the trigger-bar position in `bars` (entry would be at
    bars.iloc[candidate_idx + 1]).
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

    entry_idx = trigger_idx + 1
    entry_bar = bars.iloc[entry_idx]
    entry_date = (
        bars.index[entry_idx].date()
        if hasattr(bars.index[entry_idx], "date")
        else bars.index[entry_idx]
    )
    entry_price = float(entry_bar["Open"])
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
