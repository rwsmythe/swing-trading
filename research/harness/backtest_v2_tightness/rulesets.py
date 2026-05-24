"""Exit rulesets for the V2 tightness-range-factor walk-forward backtest.

Three rulesets per dispatch brief §3:
  A — Minervini trail-MA (per reference/methodology/minervini-sell-side-rules.md M.2
      + reference/methodology/dst-take-profit-and-trail.md D.3): initial stop at
      consolidation_low, +2R extension trigger moves stop to breakeven, then trail
      50d SMA on close, hard exit on first close below 50d SMA after trail fires.
  B — Fixed R-multiple: initial stop, +1R triggers breakeven, +3R target OR trail
      21d SMA on close (post-BE). Hard exit at stop or +3R target or data tail.
  C — Close-below-50d-SMA (per Stage-2 simplification): initial stop, trail trigger
      when close > 50d SMA AND 50d SMA is rising, trail stop = 50d SMA on close,
      hard exit on first close below 50d SMA after trail fires.

Stop semantics: intraday Low <= current_stop triggers stop-hit exit at current_stop
(market-stop assumption -- worst-case fill). Close-below-MA exits fill at the bar's
Close (the rule is a close-confirmed signal per DST D.3 +
reference/methodology/dst-take-profit-and-trail.md L122).

Ratchet: trailing stops only move UP for longs (max(prior_stop, new_proposed)).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import pandas as pd

from research.harness.backtest_v2_tightness.patterns import Pattern


# Ruleset A: +2R extension trigger (per Minervini M.2 TLSMW p.296 example: 20%/7% = ~2.86R).
RULESET_A_TRAIL_TRIGGER_R = 2.0

# Ruleset B: +1R breakeven; +3R target.
RULESET_B_BREAKEVEN_TRIGGER_R = 1.0
RULESET_B_TARGET_R = 3.0

# Ruleset C: 50d SMA slope window (5-bar lookback for rising-MA check).
RULESET_C_SLOPE_WINDOW = 5


@dataclass
class _State:
    current_stop: float
    trail_armed: bool = False
    breakeven_armed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class Ruleset(Protocol):
    name: str

    def init_state(
        self,
        *,
        pattern: Pattern,
        forward_bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> _State: ...

    def update_stop_and_check_exit(
        self,
        *,
        state: _State,
        bar_idx: int,
        bar: pd.Series,
        forward_bars: pd.DataFrame,
        entry_price: float,
        initial_R: float,
    ) -> tuple[float | None, str | None]:
        """Returns (exit_price, exit_reason) if exiting THIS bar; else (None, None)."""
        ...


def _sma_at(forward_bars: pd.DataFrame, bar_idx: int, window: int) -> float | None:
    """Mean of Close over (bar_idx - window + 1 .. bar_idx) inclusive.

    Returns None if insufficient bars.
    """
    if bar_idx + 1 < window:
        return None
    closes = forward_bars["Close"].iloc[bar_idx + 1 - window : bar_idx + 1]
    return float(closes.mean())


def _sma_rising(forward_bars: pd.DataFrame, bar_idx: int, window: int, slope_window: int) -> bool:
    """True if SMA[bar_idx] > SMA[bar_idx - slope_window]."""
    if bar_idx - slope_window < window - 1:
        return False
    now = _sma_at(forward_bars, bar_idx, window)
    then = _sma_at(forward_bars, bar_idx - slope_window, window)
    if now is None or then is None:
        return False
    return now > then


# --------------------------------------------------------------------------
# Ruleset A — Minervini trail-MA (+2R extension trigger; 50d SMA trail)
# --------------------------------------------------------------------------
class RulesetA:
    name = "A_minervini_trail_ma"

    def init_state(
        self,
        *,
        pattern: Pattern,
        forward_bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> _State:
        return _State(current_stop=initial_stop, trail_armed=False, breakeven_armed=False)

    def update_stop_and_check_exit(
        self,
        *,
        state: _State,
        bar_idx: int,
        bar: pd.Series,
        forward_bars: pd.DataFrame,
        entry_price: float,
        initial_R: float,
    ) -> tuple[float | None, str | None]:
        low = float(bar["Low"])
        high = float(bar["High"])
        close = float(bar["Close"])

        # Hard intraday stop check first (worst case fill at stop).
        if low <= state.current_stop:
            return state.current_stop, ("stop_hit" if not state.trail_armed else "trail_stop")

        # Trail-trigger arm: when High reaches entry + 2R intraday.
        if not state.trail_armed and high >= entry_price + RULESET_A_TRAIL_TRIGGER_R * initial_R:
            state.trail_armed = True
            # Per M.2: move stop to breakeven OR trail to lock in majority of gain.
            # We choose: move stop to max(current_stop, breakeven) THEN start 50d trail.
            state.current_stop = max(state.current_stop, entry_price)

        # Post-arm: trail 50d SMA on close.
        if state.trail_armed:
            sma50 = _sma_at(forward_bars, bar_idx, 50)
            if sma50 is not None:
                state.current_stop = max(state.current_stop, sma50)
                # Hard exit: first close below 50d SMA after trail fires.
                if close < sma50:
                    return close, "close_below_50d"

        return None, None


# --------------------------------------------------------------------------
# Ruleset B — Fixed R-multiple (+1R BE; +3R target; 21d SMA trail post-BE)
# --------------------------------------------------------------------------
class RulesetB:
    name = "B_fixed_R_multiple"

    def init_state(
        self,
        *,
        pattern: Pattern,
        forward_bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> _State:
        return _State(current_stop=initial_stop, breakeven_armed=False)

    def update_stop_and_check_exit(
        self,
        *,
        state: _State,
        bar_idx: int,
        bar: pd.Series,
        forward_bars: pd.DataFrame,
        entry_price: float,
        initial_R: float,
    ) -> tuple[float | None, str | None]:
        low = float(bar["Low"])
        high = float(bar["High"])
        close = float(bar["Close"])

        # Hard intraday stop check first.
        if low <= state.current_stop:
            return state.current_stop, ("stop_hit" if not state.breakeven_armed else "trail_stop")

        # +3R target — exit at target intraday.
        target_price = entry_price + RULESET_B_TARGET_R * initial_R
        if high >= target_price:
            return target_price, "target_3R"

        # Breakeven arm: when High reaches +1R.
        if not state.breakeven_armed and high >= entry_price + RULESET_B_BREAKEVEN_TRIGGER_R * initial_R:
            state.breakeven_armed = True
            state.current_stop = max(state.current_stop, entry_price)

        # Post-BE: 21d SMA trail on close (per brief OQ-2 default (b)).
        if state.breakeven_armed:
            sma21 = _sma_at(forward_bars, bar_idx, 21)
            if sma21 is not None:
                state.current_stop = max(state.current_stop, sma21)

        return None, None


# --------------------------------------------------------------------------
# Ruleset C — Close-below-50d-SMA (initial stop + trail 50d SMA on close)
# --------------------------------------------------------------------------
class RulesetC:
    name = "C_close_below_50d"

    def init_state(
        self,
        *,
        pattern: Pattern,
        forward_bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> _State:
        return _State(current_stop=initial_stop, trail_armed=False)

    def update_stop_and_check_exit(
        self,
        *,
        state: _State,
        bar_idx: int,
        bar: pd.Series,
        forward_bars: pd.DataFrame,
        entry_price: float,
        initial_R: float,
    ) -> tuple[float | None, str | None]:
        low = float(bar["Low"])
        close = float(bar["Close"])

        # Hard intraday stop check first.
        if low <= state.current_stop:
            return state.current_stop, ("stop_hit" if not state.trail_armed else "trail_stop")

        sma50 = _sma_at(forward_bars, bar_idx, 50)

        # Trail-arm: close > 50d SMA AND 50d SMA is rising.
        if not state.trail_armed and sma50 is not None:
            if close > sma50 and _sma_rising(forward_bars, bar_idx, 50, RULESET_C_SLOPE_WINDOW):
                state.trail_armed = True
                state.current_stop = max(state.current_stop, sma50)

        # Post-arm: trail 50d SMA on close; hard exit on first close below 50d.
        if state.trail_armed and sma50 is not None:
            state.current_stop = max(state.current_stop, sma50)
            if close < sma50:
                return close, "close_below_50d"

        return None, None


def all_rulesets() -> list[Ruleset]:
    return [RulesetA(), RulesetB(), RulesetC()]
