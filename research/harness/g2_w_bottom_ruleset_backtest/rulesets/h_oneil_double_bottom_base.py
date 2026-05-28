"""Ruleset H -- O'Neil double-bottom base (G2 dispatch brief Sec 2.2).

Source: William J. O'Neil, *How to Make Money in Stocks*, "double bottom"
as a Stage 2 base variant; 8% max-loss convention. Encoded per dispatch
brief Sec 2.2 specification.

Entry:
  - First close > pivot_price (= center_peak_price) within the trigger
    search window
  - AND breakout_bar_volume > 1.4 x trailing 50-bar mean volume (strict)
  - Entry price = NEXT session's Open per harness convention.

Initial stop (entry-relative; mirrors O'Neil's 8% max-loss + RulesetE's
arm but WITHOUT the trough_2 * 0.99 max() comparison):
  - stop_price = entry_price * 0.92

Target (same measured-move as G):
  - pattern_height = center_peak_price - min(trough_1_price, trough_2_price)
  - target_price = entry_price + pattern_height
  - Exit at target on first close >= target.

Failure (first to fire):
  - Close < stop_price -> exit at the bar's close ('stop_hit')
  - Close < 50-bar SMA -> exit at the bar's close ('close_below_50d';
    O'Neil's stage-2-break invalidation)
  - Stop check is evaluated BEFORE SMA-break check, so both-breaking the
    same bar yields stop_hit (deterministic order).

Volume-confirmation predicate: see `oneil_trigger_predicate` below.
"""
from __future__ import annotations

import pandas as pd

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.w_bottom_ruleset_comparison.walkforward import (
    Action,
    FullExit,
    State,
    sma_at,
)


# Brief Sec 2.2 constants
H_STOP_PCT = 0.92  # entry * 0.92 (8% max loss per O'Neil)
H_BREAKOUT_VOLUME_MULTIPLIER = 1.4  # strict inequality
H_VOLUME_LOOKBACK_BARS = 50
H_HARD_EXIT_SMA_WINDOW = 50  # O'Neil stage-2-break invalidation


class RulesetH:
    """O'Neil double-bottom base -- entry*0.92 stop + measured-move target +
    SMA50 stage-2-break invalidation."""

    name = "H_oneil_double_bottom_base"

    def initial_stop(
        self, *, verdict: PrimaryVerdict, entry_price: float
    ) -> float:
        """entry * 0.92 (8% below entry; independent of trough_2)."""
        return entry_price * H_STOP_PCT

    def init_state(
        self,
        *,
        verdict: PrimaryVerdict,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> State:
        pattern_height = verdict.center_peak_price - min(
            verdict.trough_1_price, verdict.trough_2_price
        )
        target_price = entry_price + pattern_height
        state = State(current_stop=initial_stop)
        state.extra["target_price"] = target_price
        return state

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
        close = float(bars["Close"].iloc[bar_idx])

        # 1. Stop check (close-based; strict inequality). Evaluated FIRST so
        # stop_hit takes precedence over close_below_50d when both break the
        # same bar (deterministic order).
        if close < state.current_stop:
            return FullExit(close, "stop_hit")

        # 2. Target check (first close >= target).
        target_price = float(state.extra["target_price"])
        if close >= target_price:
            return FullExit(target_price, "target_measured_move")

        # 3. SMA50 stage-2-break invalidation.
        sma50 = sma_at(bars, bar_idx, H_HARD_EXIT_SMA_WINDOW)
        if sma50 is not None and close < sma50:
            return FullExit(close, "close_below_50d")

        return None


def oneil_trigger_predicate(
    bars: pd.DataFrame, candidate_idx: int, verdict: PrimaryVerdict
) -> bool:
    """Volume confirmation per O'Neil: breakout-bar volume must exceed
    H_BREAKOUT_VOLUME_MULTIPLIER (1.4) x trailing H_VOLUME_LOOKBACK_BARS-mean
    volume (strict inequality).

    The trailing window is the 50 bars STRICTLY BEFORE the candidate bar
    (indices candidate_idx - 50 .. candidate_idx - 1 inclusive).
    Insufficient prior history returns False.
    """
    if candidate_idx < H_VOLUME_LOOKBACK_BARS:
        return False
    trailing = bars["Volume"].iloc[
        candidate_idx - H_VOLUME_LOOKBACK_BARS : candidate_idx
    ]
    trailing_mean = float(trailing.mean())
    if trailing_mean <= 0:
        return False
    breakout_volume = float(bars["Volume"].iloc[candidate_idx])
    return breakout_volume > H_BREAKOUT_VOLUME_MULTIPLIER * trailing_mean
