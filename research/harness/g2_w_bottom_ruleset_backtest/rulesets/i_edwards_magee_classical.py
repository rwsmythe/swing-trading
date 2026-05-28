"""Ruleset I -- Edwards & Magee classical double-bottom (G2 dispatch brief Sec 2.3).

Source: Robert D. Edwards & John Magee, *Technical Analysis of Stock Trends*,
double-bottom chapter. Encoded per dispatch brief Sec 2.3 specification.

Entry (brief Sec 2.3 LOCK + Codex R1 CRITICAL #2 closure):
  - First close > center_peak_price within the trigger search window
  - AND breakout_bar_volume > 1.5 x mean(volume between trough_2_date and
    breakout_bar_date - 1) (the rally-from-trough_2 volume baseline; strict).
  - Entry price = the TRIGGER BAR's CLOSE (NOT next-session open;
    brief line 200 + 201 LOCK). Entry date = trigger bar's date.

Throwback-aware semantic (brief Sec 2.3):
  - The brief specifies 'do NOT re-enter on second break' when an entered
    position retraces into the [trough_2, center_peak] zone and then
    re-breaks above. This aligns naturally with the harness's single-entry
    convention -- the engine enters once + holds through retracements
    until stop/target/data-tail. No additional code; verified via
    discriminating throwback test.

Initial stop (LOWER-TROUGH-RELATIVE):
  - stop_price = min(trough_1_price, trough_2_price) * (1 - 0.01)
  - Wider than RulesetG (which uses trough_2 only) when trough_1 < trough_2.

Target (same measured-move as G + H; PATTERN-ANCHORED per brief Sec 2.3 LOCK):
  - pattern_height = center_peak_price - min(trough_1_price, trough_2_price)
  - target_price = center_peak_price + pattern_height
    (pattern-absolute measured-move, NOT entry-relative; matches G/H).

Failure:
  - Close < stop_price -> exit at NEXT-BAR OPEN (brief Sec 2.3 line 211
    LOCK; at data tail, fall back to current-bar close).

Volume-confirmation predicate: see `edwards_magee_trigger_predicate` below.
"""
from __future__ import annotations

import pandas as pd

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.g2_w_bottom_ruleset_backtest.walkforward_ghi import (
    DeferredExit,
)
from research.harness.w_bottom_ruleset_comparison.walkforward import (
    FullExit,
    State,
)


# Brief Sec 2.3 constants
I_STOP_BUFFER = 0.01  # 1% below min(trough_1, trough_2)
I_BREAKOUT_VOLUME_MULTIPLIER = 1.5  # strict inequality vs rally_from_t2 mean


class RulesetI:
    """Edwards-Magee classical double-bottom -- lower-trough stop +
    measured-move target + rally-volume confirmation."""

    name = "I_edwards_magee_classical_double_bottom"

    def initial_stop(
        self, *, verdict: PrimaryVerdict, entry_price: float
    ) -> float:
        """min(trough_1, trough_2) * 0.99 (lower-trough; wider than G when
        trough_1 < trough_2)."""
        lower_trough = min(verdict.trough_1_price, verdict.trough_2_price)
        return lower_trough * (1 - I_STOP_BUFFER)

    def init_state(
        self,
        *,
        verdict: PrimaryVerdict,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> State:
        """Per brief Sec 2.3 LOCK: target = center_peak + pattern_height
        (PATTERN-ANCHORED; matches G/H; diverges from existing RulesetE)."""
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
    ) -> FullExit | DeferredExit | None:
        close = float(bars["Close"].iloc[bar_idx])

        # 1. Stop check. Per brief Sec 2.3 LOCK + Codex R2 MAJOR #2 closure:
        # DeferredExit for next-bar-open exit semantics with coherent
        # exit_date + days_held.
        if close < state.current_stop:
            return DeferredExit("stop_hit")

        # 2. Measured-move target (limit-style exit at target).
        target_price = float(state.extra["target_price"])
        if close >= target_price:
            return FullExit(target_price, "target_measured_move")

        return None


def edwards_magee_trigger_predicate(
    bars: pd.DataFrame, candidate_idx: int, verdict: PrimaryVerdict
) -> bool:
    """Volume confirmation per Edwards-Magee: breakout-bar volume must
    exceed I_BREAKOUT_VOLUME_MULTIPLIER (1.5) x the mean volume of bars
    between verdict.trough_2_date (exclusive) and the candidate bar
    (exclusive).

    The rally-volume baseline is the mean of bars in the open interval
    (trough_2_date, candidate_bar_date). If the interval contains no bars
    (breakout bar is the bar immediately after trough_2 with no trading
    bars between), the predicate returns False (no baseline can be
    established). Strict inequality.
    """
    # Locate the candidate bar's date.
    cand_date_raw = bars.index[candidate_idx]
    cand_date = (
        cand_date_raw.date() if hasattr(cand_date_raw, "date") else cand_date_raw
    )
    # Build a per-bar date list for masking.
    dates = pd.Index(
        [d.date() if hasattr(d, "date") else d for d in bars.index]
    )
    # Rally window: bars strictly AFTER trough_2_date and strictly BEFORE
    # candidate bar's date.
    mask = (dates > verdict.trough_2_date) & (dates < cand_date)
    rally_bars = bars.loc[mask.tolist()]
    if len(rally_bars) == 0:
        return False
    rally_mean = float(rally_bars["Volume"].mean())
    if rally_mean <= 0:
        return False
    breakout_volume = float(bars["Volume"].iloc[candidate_idx])
    return breakout_volume > I_BREAKOUT_VOLUME_MULTIPLIER * rally_mean
