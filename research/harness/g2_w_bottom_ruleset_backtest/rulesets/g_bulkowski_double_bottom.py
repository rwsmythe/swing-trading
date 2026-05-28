"""Ruleset G -- Bulkowski double-bottom (G2 dispatch brief Sec 2.1).

Source: Thomas N. Bulkowski, *Encyclopedia of Chart Patterns*, 2nd ed.,
"Double Bottoms" chapter. Encoded per dispatch brief Sec 2.1 specification.

Entry:
  - First close > center_peak_price within the trigger search window
  - AND breakout_bar_volume > 1.3 x trailing 20-bar mean volume
  - Entry price = NEXT session's Open per harness convention (the engine
    uses next-session-open after the trigger bar; the "close of breakout
    bar" wording in brief Sec 2.1 is the trigger semantic, not the
    entry-price semantic).

Initial stop (TIGHT; the key differentiator from RulesetE):
  - stop_price = trough_2_price * (1 - 0.01) = trough_2_price * 0.99
  - NO entry-relative arm (RulesetE uses max(trough_2 * 0.99, entry * 0.92);
    G omits the entry * 0.92 floor per Bulkowski's "pattern fails on close
    below the second trough" rule).

Target (canonical Bulkowski measured-move):
  - pattern_height = center_peak_price - min(trough_1_price, trough_2_price)
  - target_price = entry_price + pattern_height
  - Exit at the target price on first close >= target.

Failure:
  - Close < stop -> exit at the bar's close.
  - NO time-stop in V1 (Bulkowski does not specify a time-stop; V2 candidate).

Volume-confirmation predicate: see `bulkowski_trigger_predicate` below.
"""
from __future__ import annotations

import pandas as pd

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.w_bottom_ruleset_comparison.walkforward import (
    Action,
    FullExit,
    State,
)


# Brief Sec 2.1 constants
G_STOP_BUFFER = 0.01  # 1% below trough_2
G_BREAKOUT_VOLUME_MULTIPLIER = 1.3  # strict inequality
G_VOLUME_LOOKBACK_BARS = 20


class RulesetG:
    """Bulkowski double-bottom -- tight trough_2 stop + measured-move target."""

    name = "G_bulkowski_double_bottom"

    def initial_stop(
        self, *, verdict: PrimaryVerdict, entry_price: float
    ) -> float:
        """trough_2 * 0.99 (tight; NO entry-relative arm)."""
        return verdict.trough_2_price * (1 - G_STOP_BUFFER)

    def init_state(
        self,
        *,
        verdict: PrimaryVerdict,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> State:
        """Compute Bulkowski measured-move target from W height; stash in extra."""
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

        # 1. Stop check (close-based; STRICT inequality matches Bulkowski's
        # "close below the second trough" failure rule).
        if close < state.current_stop:
            return FullExit(close, "stop_hit")

        # 2. Measured-move target on first close >= target.
        target_price = float(state.extra["target_price"])
        if close >= target_price:
            return FullExit(target_price, "target_measured_move")

        return None


def bulkowski_trigger_predicate(
    bars: pd.DataFrame, candidate_idx: int, verdict: PrimaryVerdict
) -> bool:
    """Volume confirmation per Bulkowski: breakout-bar volume must exceed
    G_BREAKOUT_VOLUME_MULTIPLIER (1.3) x trailing G_VOLUME_LOOKBACK_BARS-mean
    volume (strict inequality).

    The trailing window is the G_VOLUME_LOOKBACK_BARS bars STRICTLY BEFORE
    the candidate bar (indices candidate_idx - 20 .. candidate_idx - 1
    inclusive). Insufficient prior history returns False; the search will
    continue forward (no rejection of the W; just the specific trigger bar).
    """
    if candidate_idx < G_VOLUME_LOOKBACK_BARS:
        return False
    trailing = bars["Volume"].iloc[
        candidate_idx - G_VOLUME_LOOKBACK_BARS : candidate_idx
    ]
    trailing_mean = float(trailing.mean())
    if trailing_mean <= 0:
        return False
    breakout_volume = float(bars["Volume"].iloc[candidate_idx])
    return breakout_volume > G_BREAKOUT_VOLUME_MULTIPLIER * trailing_mean
