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

Target (canonical Bulkowski measured-move; PATTERN-ANCHORED):
  - pattern_height = center_peak_price - min(trough_1_price, trough_2_price)
  - target_price = center_peak_price + pattern_height
    (brief Sec 2.1 line 156 LOCK: pattern-absolute measured-move, NOT
    entry-relative; the measured-move is a PROPERTY of the W pattern
    itself, anchored at the neckline = center_peak, not at the
    operator's entry price; this differs from existing RulesetE which
    uses entry_price + pattern_height per its own convention)
  - Exit at the target price on first close >= target.

Failure:
  - Close < stop -> exit at NEXT-BAR OPEN (brief Sec 2.1 line 160 LOCK:
    'exit at next-bar open with realistic slippage assumption'). At
    data tail (no next bar), fall back to current-bar close. This
    diverges from existing RulesetE's same-bar-close exit convention
    for literature fidelity.
  - NO time-stop in V1 (Bulkowski does not specify a time-stop; V2 candidate).

Volume-confirmation predicate: see `bulkowski_trigger_predicate` below.
"""
from __future__ import annotations

import pandas as pd

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.g2_w_bottom_ruleset_backtest.walkforward_ghi import (
    next_bar_open_price_or_close_at_tail,
)
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
        """Compute Bulkowski measured-move target from W height; stash in extra.

        Per brief Sec 2.1 line 156 LOCK: target_price = center_peak_price +
        pattern_height (PATTERN-ANCHORED, not entry-relative). Diverges
        from existing RulesetE's convention (entry_price + pattern_height)
        for literature fidelity.
        """
        pattern_height = verdict.center_peak_price - min(
            verdict.trough_1_price, verdict.trough_2_price
        )
        target_price = verdict.center_peak_price + pattern_height
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
        # "close below the second trough" failure rule). Per brief Sec 2.1
        # line 160 LOCK: exit at NEXT-BAR OPEN (at data tail, fall back to
        # current-bar close). The exit price is the actionable price at
        # next session's open (realistic slippage); the exit_date stays as
        # the detection bar by engine convention.
        if close < state.current_stop:
            exit_price = next_bar_open_price_or_close_at_tail(bars, bar_idx)
            return FullExit(exit_price, "stop_hit")

        # 2. Measured-move target on first close >= target. Target exits
        # are limit-style (assume the target was hit intraday by the bar
        # closing above it); exit at target_price unchanged.
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
