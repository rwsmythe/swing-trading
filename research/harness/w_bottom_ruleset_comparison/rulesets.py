"""Six exit rulesets for D2 W-bottom ruleset comparison backtest.

Rulesets A/B/C reimplement D1's baseline rulesets against the D2 generalized
Action protocol (FullExit / ScaleOut). Algorithmic semantics preserve D1's
post-Codex behavior verbatim.

Rulesets D/E/F are NEW literature-canonical variants per dispatch brief
Section 3:

  D -- Minervini Stage-2 progression (NEW):
       Initial stop = trough_2 * 0.99
       +2R close arms BREAKEVEN (stop raised to entry_price)
       Post-arm trail: stop = max(prior, SMA10 * 0.99) daily
       Hard exit (close <= SMA50) ARMED only if SMA50 > entry * 1.05

  E -- O'Neil cup-with-handle + Bulkowski measured-move (NEW):
       Initial stop = max(trough_2 * 0.99, entry * 0.92)  [tighter wins]
       Target = entry + (center_peak - min(trough_1, trough_2))
       Exit at TARGET price on first close >= target; stop_hit on close <= stop
       NO trail, NO momentum gate, NO 50d hard exit

  F -- Qullamaggie momentum-burst (NEW):
       Initial stop = trough_2 * 0.99
       Initial ATR14 captured at entry bar
       Momentum gate: by end of session 5, close - entry must reach >= 1.0 x ATR14
                      If not, exit at session 6 OPEN (momentum_gate_fail)
       Scale-out 1/3 of position at +2R close; raise stop on remaining to entry (BE)
       After scale-out: trail stop daily to max(prior, SMA20)
       Hard exit (close <= SMA50) ARMED only if SMA50 > entry * 1.05

Source citations:
  - D: reference/methodology/minervini-trend-template.md (Stage 2 advance phase)
       + Minervini "Trade Like a Stock Market Wizard" Ch 13 quantitative anchor
       (M.2 sell-at-multiple-of-stop -> stop_to_BE at +2R)
       + dispatch brief Section 3.4 specification
  - E: O'Neil "How to Make Money in Stocks" cup-with-handle chapter
       (8% max stop loss convention) + Bulkowski "Encyclopedia of Chart Patterns"
       double-bottom measured-move target convention
       + dispatch brief Section 3.5 specification
  - F: Qullamaggie corpus via mcp__qullamaggie__* MCP server queries:
       * "Sell half after 3-5 days, move stop to breakeven, then trail the rest
          with close below 10-day MA" (scale-out + BE pattern)
       * "If a stock doesn't go anywhere for 3-5 days, sell it"
          (momentum-gate-fail discipline)
       * "For lower ADR stocks (sub 5-6%), use 20-day MA as trailing stop instead
          of 10-day" (20-day SMA trail rationale)
       * "Stop at low of breakout day, trail with 10 day MA" (initial stop pattern)
       + dispatch brief Section 3.6 specification
       + D1 V2 candidate #3 (close-below-50d arming gate to avoid mis-fire on
         entries near 50d SMA per D1 Amendment 2 close_below_50d mis-calibration)

All rulesets use CLOSE-based exit semantics throughout (no intraday Low/High
triggers) per dispatch brief Section 3 + D1 precedent. The momentum_gate_fail
in F is an OPEN-based exit at session 6 by canonical spec design.

Stop equality conventions (Codex R1 m#2):
  - A/B/C/D/F use `close < current_stop` (STRICT less-than) for the stop_hit
    branch, preserving D1 Ruleset A/B/C precedent semantics. This means a
    close EXACTLY AT the stop price holds the position one more bar.
  - E uses `close <= initial_stop` (less-than-or-equal) per dispatch brief
    Section 3.5's literal text ("close <= initial stop fires stop_hit"). The
    asymmetry is in the brief itself; preserved literally here.

Trail-ordering convention (Codex R1 M#3):
  - D / F evaluate the CLOSE-vs-CURRENT-STOP check BEFORE raising the trail
    stop with today's SMA. This is the "check-then-raise" pattern preserved
    from D1 Ruleset A: today's close exits only against the stop set by
    YESTERDAY's data; today's SMA-derived stop applies starting NEXT bar.
    Equivalent to "trail the stop daily on close-of-bar, evaluate exit on
    open-of-next-bar (or close-of-same-bar already past)" in operator
    practice.
  - Codex R1 M#3 flagged the alternative "raise-then-check" interpretation:
    that would tighten the exit. The D1 + D2 implementation EXPLICITLY chose
    check-then-raise for consistency with D1 + the literal "trail daily"
    semantic. V2 candidate: test BOTH orderings as separate ruleset variants.
"""
from __future__ import annotations

import pandas as pd

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.w_bottom_ruleset_comparison.walkforward import (
    Action,
    FullExit,
    Ruleset,
    ScaleOut,
    State,
    atr_at,
    sma_at,
)


# ---------------------------------------------------------------------------
# Shared thresholds
# ---------------------------------------------------------------------------
RULESET_A_TRAIL_TRIGGER_R = 2.0
RULESET_A_TRAIL_SMA_WINDOW = 21
RULESET_A_TRAIL_ATR_WINDOW = 14
RULESET_A_TRAIL_ATR_MULT = 1.0
RULESET_A_HARD_EXIT_SMA_WINDOW = 50

RULESET_B_TARGET_R = 3.0

RULESET_C_HARD_EXIT_SMA_WINDOW = 50

RULESET_D_BE_ARM_R = 2.0
RULESET_D_TRAIL_SMA_WINDOW = 10
RULESET_D_TRAIL_BUFFER = 0.99  # stop = SMA10 * 0.99
RULESET_D_50D_GATE_MULT = 1.05  # 50d > entry * 1.05 arms close_below_50d
RULESET_D_HARD_EXIT_SMA_WINDOW = 50

RULESET_E_STOP_PCT = 0.92  # entry * 0.92 floor (O'Neil 8% max loss)
RULESET_E_TROUGH_BUFFER = 0.99  # trough_2 * 0.99 (W-bottom stop convention)

RULESET_F_ATR_WINDOW = 14
RULESET_F_MOMENTUM_GATE_SESSIONS = 5  # close-and-exit at session 6 if not armed
RULESET_F_MOMENTUM_ATR_MULT = 1.0  # threshold = 1.0 * ATR14_at_entry
RULESET_F_SCALE_OUT_R = 2.0
RULESET_F_SCALE_OUT_FRACTION = 1.0 / 3.0
RULESET_F_TRAIL_SMA_WINDOW = 20
RULESET_F_50D_GATE_MULT = 1.05
RULESET_F_HARD_EXIT_SMA_WINDOW = 50


# ---------------------------------------------------------------------------
# Ruleset A -- Minervini trail-MA (D1 baseline; preserved semantics)
# ---------------------------------------------------------------------------
class RulesetA:
    name = "A_minervini_trail_ma"

    def initial_stop(self, *, verdict: PrimaryVerdict, entry_price: float) -> float:
        return verdict.initial_stop

    def init_state(
        self,
        *,
        verdict: PrimaryVerdict,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> State:
        return State(current_stop=initial_stop)

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

        # TERMINAL hard exit: first close <= SMA50 regardless of trail state.
        # Per D1 brief Section 3.1; preserved post-Codex R1 M#1.
        sma50 = sma_at(bars, bar_idx, RULESET_A_HARD_EXIT_SMA_WINDOW)
        if sma50 is not None and close <= sma50:
            return FullExit(close, "close_below_50d")

        # Stop check (close-based)
        if close < state.current_stop:
            reason = "trail_stop" if state.extra.get("trail_armed") else "stop_hit"
            return FullExit(close, reason)

        # Trail-arm at +2R close
        if (
            not state.extra.get("trail_armed")
            and close >= entry_price + RULESET_A_TRAIL_TRIGGER_R * initial_R
        ):
            state.extra["trail_armed"] = True

        # Post-arm trail: max(prior, SMA21 - 1*ATR14)
        if state.extra.get("trail_armed"):
            sma21 = sma_at(bars, bar_idx, RULESET_A_TRAIL_SMA_WINDOW)
            atr14 = atr_at(bars, bar_idx, RULESET_A_TRAIL_ATR_WINDOW)
            if sma21 is not None and atr14 is not None:
                proposed = sma21 - RULESET_A_TRAIL_ATR_MULT * atr14
                state.current_stop = max(state.current_stop, proposed)

        return None


# ---------------------------------------------------------------------------
# Ruleset B -- Fixed R-multiple (D1 baseline; preserved semantics)
# ---------------------------------------------------------------------------
class RulesetB:
    name = "B_fixed_R_multiple"

    def initial_stop(self, *, verdict: PrimaryVerdict, entry_price: float) -> float:
        return verdict.initial_stop

    def init_state(
        self,
        *,
        verdict: PrimaryVerdict,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> State:
        return State(current_stop=initial_stop)

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

        if close < state.current_stop:
            return FullExit(close, "stop_hit")

        target_price = entry_price + RULESET_B_TARGET_R * initial_R
        if close >= target_price:
            return FullExit(target_price, "target_3R")

        return None


# ---------------------------------------------------------------------------
# Ruleset C -- Close-below-50d-SMA (D1 baseline; preserved semantics)
# ---------------------------------------------------------------------------
class RulesetC:
    name = "C_close_below_50d"

    def initial_stop(self, *, verdict: PrimaryVerdict, entry_price: float) -> float:
        return verdict.initial_stop

    def init_state(
        self,
        *,
        verdict: PrimaryVerdict,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> State:
        return State(current_stop=initial_stop)

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

        if close < state.current_stop:
            return FullExit(close, "stop_hit")

        sma50 = sma_at(bars, bar_idx, RULESET_C_HARD_EXIT_SMA_WINDOW)
        if sma50 is not None and close < sma50:
            return FullExit(close, "close_below_50d")

        return None


# ---------------------------------------------------------------------------
# Ruleset D -- Minervini Stage-2 progression (NEW; close-below-50d arming gate)
# ---------------------------------------------------------------------------
class RulesetD:
    name = "D_minervini_stage2_progression"

    def initial_stop(self, *, verdict: PrimaryVerdict, entry_price: float) -> float:
        return verdict.initial_stop

    def init_state(
        self,
        *,
        verdict: PrimaryVerdict,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> State:
        return State(current_stop=initial_stop)

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

        # 1. Stop check (close-based)
        if close < state.current_stop:
            reason = "trail_stop" if state.breakeven_armed else "stop_hit"
            return FullExit(close, reason)

        # 2. Gated 50d hard exit: only ARMED when SMA50 > entry * 1.05
        sma50 = sma_at(bars, bar_idx, RULESET_D_HARD_EXIT_SMA_WINDOW)
        if (
            sma50 is not None
            and sma50 > entry_price * RULESET_D_50D_GATE_MULT
            and close <= sma50
        ):
            return FullExit(close, "close_below_50d_gated")

        # 3. BE arm at +2R close: raise stop to entry_price
        if (
            not state.breakeven_armed
            and close >= entry_price + RULESET_D_BE_ARM_R * initial_R
        ):
            state.breakeven_armed = True
            state.current_stop = max(state.current_stop, entry_price)

        # 4. Post-BE trail: max(prior, SMA10 * 0.99)
        if state.breakeven_armed:
            sma10 = sma_at(bars, bar_idx, RULESET_D_TRAIL_SMA_WINDOW)
            if sma10 is not None:
                proposed = sma10 * RULESET_D_TRAIL_BUFFER
                state.current_stop = max(state.current_stop, proposed)

        return None


# ---------------------------------------------------------------------------
# Ruleset E -- O'Neil cup-with-handle + Bulkowski measured-move (NEW)
# ---------------------------------------------------------------------------
class RulesetE:
    name = "E_oneil_cup_with_handle_measured_move"

    def initial_stop(self, *, verdict: PrimaryVerdict, entry_price: float) -> float:
        """max(trough_2 * 0.99, entry * 0.92).

        The MAX gives the HIGHER (tighter / less aggressive risk) of the two
        candidate floors per dispatch brief Section 3.5: "use whichever is
        HIGHER as the actual stop for risk-control".
        """
        return max(
            verdict.trough_2_price * RULESET_E_TROUGH_BUFFER,
            entry_price * RULESET_E_STOP_PCT,
        )

    def init_state(
        self,
        *,
        verdict: PrimaryVerdict,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> State:
        """Compute Bulkowski measured-move target from W height and store in
        state.extra for per-bar lookup."""
        target_price = entry_price + (
            verdict.center_peak_price
            - min(verdict.trough_1_price, verdict.trough_2_price)
        )
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

        # 1. Stop check
        if close <= state.current_stop:
            return FullExit(close, "stop_hit")

        # 2. Measured-move target: exit at TARGET price on first close >= target
        target_price = float(state.extra["target_price"])
        if close >= target_price:
            return FullExit(target_price, "target_measured_move")

        return None


# ---------------------------------------------------------------------------
# Ruleset F -- Qullamaggie momentum-burst extension (NEW)
# ---------------------------------------------------------------------------
class RulesetF:
    name = "F_qullamaggie_momentum_burst"

    def initial_stop(self, *, verdict: PrimaryVerdict, entry_price: float) -> float:
        return verdict.initial_stop

    def init_state(
        self,
        *,
        verdict: PrimaryVerdict,
        bars: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        initial_stop: float,
    ) -> State:
        """Capture ATR14 at the entry bar for the momentum gate threshold.

        ATR14 NULL handling (Codex R1 M#2): if `atr_at()` returns None due to
        insufficient pre-entry bars (need >= 15), the momentum gate CANNOT be
        evaluated. Rather than implicitly auto-failing every such trade at
        session 6 (a silent losing-rule variant), we treat the gate as
        ARMED-BY-DEFAULT so the trade continues per the other Ruleset F rules
        (scale-out / BE / SMA20 trail / gated 50d exit). This preserves the
        spec's "momentum confirmation" intent without penalizing trades that
        the archive cannot evaluate. Documented limitation; banked as a V2
        candidate (use a fallback threshold like 1% of entry_price when ATR
        unavailable).
        """
        atr14_at_entry = atr_at(bars, entry_idx, RULESET_F_ATR_WINDOW)
        gate_armed_by_default = atr14_at_entry is None or atr14_at_entry <= 0
        return State(
            current_stop=initial_stop,
            initial_atr14=atr14_at_entry,
            momentum_gate_armed=gate_armed_by_default,
        )

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
        # session_n: 1 = entry bar; 2..N = subsequent sessions.
        session_n = bar_idx - entry_idx + 1

        # 1. Momentum gate fail at session 6 OPEN -- PRE-EMPTS all other
        # actions this bar (Codex R1 M#1). The position is exited at OPEN
        # PRICE; the close of session 6 never executes. Same-day close-below-
        # stop and close-below-SMA50 checks must NOT fire on this bar.
        if (
            not state.momentum_gate_armed
            and not state.scale_out_fired
            and session_n == RULESET_F_MOMENTUM_GATE_SESSIONS + 1
        ):
            open_price = float(bars["Open"].iloc[bar_idx])
            return FullExit(open_price, "momentum_gate_fail")

        # 2. Stop check (close-based; once scale-out fired the stop is BE/SMA20)
        if close < state.current_stop:
            reason = "trail_stop" if state.scale_out_fired else "stop_hit"
            return FullExit(close, reason)

        # 3. Gated 50d hard exit: only ARMED when SMA50 > entry * 1.05
        sma50 = sma_at(bars, bar_idx, RULESET_F_HARD_EXIT_SMA_WINDOW)
        if (
            sma50 is not None
            and sma50 > entry_price * RULESET_F_50D_GATE_MULT
            and close <= sma50
        ):
            return FullExit(close, "close_below_50d_gated")

        # 4. Scale-out 1/3 at +2R close (only fires once per trade)
        if (
            not state.scale_out_fired
            and close >= entry_price + RULESET_F_SCALE_OUT_R * initial_R
        ):
            state.breakeven_armed = True
            state.current_stop = max(state.current_stop, entry_price)
            return ScaleOut(
                fraction=RULESET_F_SCALE_OUT_FRACTION,
                price=close,
                reason="scale_out_2R",
            )

        # 5. Post-scale-out trail: max(prior, SMA20)
        if state.scale_out_fired:
            sma20 = sma_at(bars, bar_idx, RULESET_F_TRAIL_SMA_WINDOW)
            if sma20 is not None:
                state.current_stop = max(state.current_stop, sma20)

        # 6. Arm momentum gate: within first 5 sessions, close - entry must
        # reach >= 1.0 x ATR14_at_entry.
        if (
            not state.momentum_gate_armed
            and not state.scale_out_fired
            and session_n <= RULESET_F_MOMENTUM_GATE_SESSIONS
            and state.initial_atr14 is not None
            and (close - entry_price)
            >= RULESET_F_MOMENTUM_ATR_MULT * state.initial_atr14
        ):
            state.momentum_gate_armed = True

        return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def all_rulesets() -> list[Ruleset]:
    """Six rulesets in canonical iteration order: A, B, C, D, E, F."""
    return [RulesetA(), RulesetB(), RulesetC(), RulesetD(), RulesetE(), RulesetF()]
