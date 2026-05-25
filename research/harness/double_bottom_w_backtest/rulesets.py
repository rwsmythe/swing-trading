"""Exit rulesets for the D1 double_bottom_w walk-forward backtest.

Three rulesets per dispatch brief Section 3 (DIVERGES from V2 backtest semantics
where noted; the D1 brief specifies its own thresholds + fill semantics):

  A -- Minervini trail-MA: initial stop = trough_2_price * 0.99; +2R extension
       triggers trail arm; post-arm daily trail = max(prior, SMA21(close) - ATR14);
       TERMINAL hard exit on first close <= SMA50 regardless of trail state.
  B -- Fixed R-multiple: initial stop = trough_2_price * 0.99; daily close >=
       entry + 3R fires `target_3R` at target_price; daily close < initial_stop
       fires `stop_hit` at close. No breakeven; no trail. ALL exits on CLOSE.
  C -- Close-below-50d-SMA: initial stop = trough_2_price * 0.99; NO trail;
       daily close < initial_stop fires `stop_hit` at close; daily close <
       SMA50 fires `close_below_50d` at close.

ALL three rulesets use CLOSE-based exit semantics (no intraday Low/High triggers).
This is a deliberate methodology choice DIFFERENT from V2 backtest -- the D1
brief specifies close-based fills throughout, which is more conservative against
intraday whipsaw on the small-N cohort.

SMA computation: bars are the FULL archive (indexed ascending by date) with
the entry happening at some interior bar_idx; SMA windows look back from
bar_idx through the archive's history, so SMA21 / SMA50 are computable from
day 1 of the position (no warmup-required short-circuit).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import pandas as pd


RULESET_A_TRAIL_TRIGGER_R = 2.0
RULESET_A_TRAIL_SMA_WINDOW = 21
RULESET_A_TRAIL_ATR_WINDOW = 14
RULESET_A_TRAIL_ATR_MULT = 1.0
RULESET_A_HARD_EXIT_SMA_WINDOW = 50

RULESET_B_TARGET_R = 3.0

RULESET_C_HARD_EXIT_SMA_WINDOW = 50


@dataclass
class _State:
    current_stop: float
    trail_armed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class Ruleset(Protocol):
    name: str

    def init_state(
        self,
        *,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> _State: ...

    def update_and_check_exit(
        self,
        *,
        state: _State,
        bars: pd.DataFrame,
        bar_idx: int,
        entry_price: float,
        initial_R: float,
    ) -> tuple[float | None, str | None]:
        """Returns (exit_price, exit_reason) if exiting THIS bar; else (None, None)."""
        ...


def _sma_at(bars: pd.DataFrame, bar_idx: int, window: int) -> float | None:
    """Mean of Close over (bar_idx - window + 1 .. bar_idx) inclusive.

    Returns None if insufficient bars (bar_idx + 1 < window).
    """
    if bar_idx + 1 < window:
        return None
    closes = bars["Close"].iloc[bar_idx + 1 - window : bar_idx + 1]
    return float(closes.mean())


def _atr_at(bars: pd.DataFrame, bar_idx: int, window: int) -> float | None:
    """Average True Range over the last `window` bars ending at bar_idx
    (inclusive). Uses Wilder's TR definition averaged via simple mean over
    `window` bars; requires bar_idx + 1 >= window + 1 (need one prior close
    for TR of bar_idx-window+1).

    Returns None if insufficient bars.
    """
    if bar_idx + 1 < window + 1:
        return None
    highs = bars["High"].iloc[bar_idx + 1 - window : bar_idx + 1]
    lows = bars["Low"].iloc[bar_idx + 1 - window : bar_idx + 1]
    prev_closes = bars["Close"].iloc[bar_idx - window : bar_idx]
    # Align indices for vectorized arithmetic
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


# --------------------------------------------------------------------------
# Ruleset A -- Minervini trail-MA (+2R arm; SMA21-ATR14 trail; TERMINAL SMA50)
# --------------------------------------------------------------------------
class RulesetA:
    name = "A_minervini_trail_ma"

    def init_state(
        self,
        *,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> _State:
        return _State(current_stop=initial_stop, trail_armed=False)

    def update_and_check_exit(
        self,
        *,
        state: _State,
        bars: pd.DataFrame,
        bar_idx: int,
        entry_price: float,
        initial_R: float,
    ) -> tuple[float | None, str | None]:
        close = float(bars["Close"].iloc[bar_idx])

        # TERMINAL hard exit: first close <= SMA50 regardless of trail state.
        # Per brief Section 3.1 "Hard exit: close <= 50-day SMA after entry (terminal
        # stop regardless of trail state)."
        sma50 = _sma_at(bars, bar_idx, RULESET_A_HARD_EXIT_SMA_WINDOW)
        if sma50 is not None and close <= sma50:
            return close, "close_below_50d"

        # Stop check (close-based): first close < current_stop.
        if close < state.current_stop:
            return close, ("stop_hit" if not state.trail_armed else "trail_stop")

        # Trail-arm: close >= entry + 2R (use close, not intraday High).
        # Dispatch brief Section 3.1 specifies the post-arm trail rule as
        # `max(prior_stop, SMA21 - 1*ATR)`. The brief does NOT prescribe a
        # breakeven raise on arm; this implementation follows the brief
        # literally (Codex R1 M#1 fix).
        if not state.trail_armed and close >= entry_price + RULESET_A_TRAIL_TRIGGER_R * initial_R:
            state.trail_armed = True

        # Post-arm trail: stop = max(prior, SMA21 - 1*ATR14).
        if state.trail_armed:
            sma21 = _sma_at(bars, bar_idx, RULESET_A_TRAIL_SMA_WINDOW)
            atr14 = _atr_at(bars, bar_idx, RULESET_A_TRAIL_ATR_WINDOW)
            if sma21 is not None and atr14 is not None:
                proposed = sma21 - RULESET_A_TRAIL_ATR_MULT * atr14
                state.current_stop = max(state.current_stop, proposed)

        return None, None


# --------------------------------------------------------------------------
# Ruleset B -- Fixed R-multiple (close <= stop OR close >= +3R target)
# --------------------------------------------------------------------------
class RulesetB:
    name = "B_fixed_R_multiple"

    def init_state(
        self,
        *,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> _State:
        return _State(current_stop=initial_stop, trail_armed=False)

    def update_and_check_exit(
        self,
        *,
        state: _State,
        bars: pd.DataFrame,
        bar_idx: int,
        entry_price: float,
        initial_R: float,
    ) -> tuple[float | None, str | None]:
        close = float(bars["Close"].iloc[bar_idx])

        # Stop hit (close-based, NO trail): close < initial_stop fires.
        if close < state.current_stop:
            return close, "stop_hit"

        # +3R target (close-based): close >= entry + 3R fires; exit at TARGET price.
        target_price = entry_price + RULESET_B_TARGET_R * initial_R
        if close >= target_price:
            return target_price, "target_3R"

        return None, None


# --------------------------------------------------------------------------
# Ruleset C -- Close-below-50d-SMA (NO trail; close <= stop OR close < SMA50)
# --------------------------------------------------------------------------
class RulesetC:
    name = "C_close_below_50d"

    def init_state(
        self,
        *,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> _State:
        return _State(current_stop=initial_stop, trail_armed=False)

    def update_and_check_exit(
        self,
        *,
        state: _State,
        bars: pd.DataFrame,
        bar_idx: int,
        entry_price: float,
        initial_R: float,
    ) -> tuple[float | None, str | None]:
        close = float(bars["Close"].iloc[bar_idx])

        # Stop hit (close-based, NO trail): close < initial_stop fires.
        if close < state.current_stop:
            return close, "stop_hit"

        # Hard exit: close < SMA50 fires (regardless of trail-arm state -- there's
        # no trail in Ruleset C; the initial stop never moves).
        sma50 = _sma_at(bars, bar_idx, RULESET_C_HARD_EXIT_SMA_WINDOW)
        if sma50 is not None and close < sma50:
            return close, "close_below_50d"

        return None, None


def all_rulesets() -> list[Ruleset]:
    return [RulesetA(), RulesetB(), RulesetC()]
