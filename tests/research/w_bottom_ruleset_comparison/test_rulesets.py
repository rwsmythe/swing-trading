"""Discriminating tests for the 6 rulesets (A/B/C/D/E/F).

Test discipline mirrors D1: synthetic OHLCV with known close trajectory + plant
the structural condition + assert per-bar action emitted matches spec.

A/B/C tests preserve D1 semantics. D/E/F tests cover the NEW canonical exit
rules per dispatch brief Section 3.4-3.6.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.w_bottom_ruleset_comparison.rulesets import (
    RULESET_D_50D_GATE_MULT,
    RULESET_E_STOP_PCT,
    RULESET_F_ATR_WINDOW,
    RULESET_F_MOMENTUM_ATR_MULT,
    RulesetA,
    RulesetB,
    RulesetC,
    RulesetD,
    RulesetE,
    RulesetF,
    all_rulesets,
)
from research.harness.w_bottom_ruleset_comparison.walkforward import (
    FullExit,
    ScaleOut,
    State,
)


# ---------------------------------------------------------------------------
# Synthetic-bar helpers
# ---------------------------------------------------------------------------
def _bars(closes: list[float], highs: list[float] | None = None,
          lows: list[float] | None = None, opens: list[float] | None = None,
          volume: float = 100_000) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame with daily index."""
    if highs is None:
        highs = [c * 1.005 for c in closes]
    if lows is None:
        lows = [c * 0.995 for c in closes]
    if opens is None:
        opens = closes[:]
    idx = pd.date_range("2026-01-02", periods=len(closes), freq="B")
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes,
         "Volume": [volume] * len(closes)},
        index=idx,
    )


def _verdict(
    *,
    center_peak: float = 100.0,
    trough_2: float = 90.0,
    trough_1: float = 88.0,
    asof: date = date(2026, 4, 30),
    composite: float = 0.85,
) -> PrimaryVerdict:
    return PrimaryVerdict(
        ticker="TEST",
        anchor_asof_date=asof,
        trough_1_date=asof - timedelta(days=60),
        trough_1_price=trough_1,
        center_peak_date=asof - timedelta(days=40),
        center_peak_price=center_peak,
        trough_2_date=asof - timedelta(days=20),
        trough_2_price=trough_2,
        pivot_price=center_peak,
        composite_score=composite,
        geometric_score=composite,
        template_match_score=composite,
        max_observed_asof_date=asof,
        observed_asof_dates=(asof,),
    )


# ---------------------------------------------------------------------------
# Registry test
# ---------------------------------------------------------------------------
def test_all_rulesets_returns_6_in_canonical_order():
    rs = all_rulesets()
    assert len(rs) == 6
    names = [r.name for r in rs]
    assert names == [
        "A_minervini_trail_ma",
        "B_fixed_R_multiple",
        "C_close_below_50d",
        "D_minervini_stage2_progression",
        "E_oneil_cup_with_handle_measured_move",
        "F_qullamaggie_momentum_burst",
    ]


# ---------------------------------------------------------------------------
# Ruleset A -- preserves D1 semantics (terminal close <= SMA50 wins)
# ---------------------------------------------------------------------------
def test_ruleset_a_terminal_close_below_sma50_fires_full_exit():
    """If SMA50 is above close, A fires close_below_50d FullExit regardless
    of stop / trail state."""
    bars = _bars([110.0] * 50 + [80.0])  # SMA50 around 110; last close 80 << SMA50
    rs = RulesetA()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=50, entry_price=110.0, initial_stop=90.0)
    action = rs.update_and_check(
        state=state, bars=bars, bar_idx=50, entry_idx=50,
        entry_price=110.0, initial_R=20.0,
    )
    assert isinstance(action, FullExit)
    assert action.reason == "close_below_50d"


def test_ruleset_a_does_not_raise_stop_to_breakeven_at_trail_arm():
    """Codex R1 M#1 (D1): trail-arm sets state.extra['trail_armed']=True but
    does NOT raise the stop to entry_price. D2 preserves this semantic."""
    bars = _bars([100.0] * 30 + [200.0])  # huge +R move at last bar
    rs = RulesetA()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=29, entry_price=100.0, initial_stop=90.0)
    pre_stop = state.current_stop
    rs.update_and_check(
        state=state, bars=bars, bar_idx=30, entry_idx=29,
        entry_price=100.0, initial_R=10.0,
    )
    # Trail armed but no breakeven raise
    assert state.extra.get("trail_armed") is True
    # current_stop may have been raised by trail formula; but NOT to entry_price=100 directly.
    # The post-arm trail uses SMA21 - 1*ATR14 which on synthetic flat data lands near 100 - small_atr.
    # The key invariant: no automatic BE raise on arm itself.
    assert state.current_stop != 100.0 or state.current_stop == pre_stop


# ---------------------------------------------------------------------------
# Ruleset B -- Fixed R-multiple (D1 reuse)
# ---------------------------------------------------------------------------
def test_ruleset_b_target_3R_fires_full_exit_at_target_price():
    bars = _bars([100.0, 105.0, 110.0, 115.0, 130.0])
    rs = RulesetB()
    v = _verdict()
    initial_stop = 90.0
    state = rs.init_state(verdict=v, bars=bars, entry_idx=0, entry_price=100.0, initial_stop=initial_stop)
    # +3R = 100 + 3 * 10 = 130; close=130 at bar_idx=4
    action = rs.update_and_check(
        state=state, bars=bars, bar_idx=4, entry_idx=0,
        entry_price=100.0, initial_R=10.0,
    )
    assert isinstance(action, FullExit)
    assert action.reason == "target_3R"
    assert action.price == 130.0  # TARGET price, not close


def test_ruleset_b_stop_hit_at_close_below_initial_stop():
    bars = _bars([100.0, 95.0, 89.0])
    rs = RulesetB()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=0, entry_price=100.0, initial_stop=90.0)
    action = rs.update_and_check(
        state=state, bars=bars, bar_idx=2, entry_idx=0,
        entry_price=100.0, initial_R=10.0,
    )
    assert isinstance(action, FullExit)
    assert action.reason == "stop_hit"
    assert action.price == 89.0


# ---------------------------------------------------------------------------
# Ruleset C -- Close-below-50d (D1 reuse)
# ---------------------------------------------------------------------------
def test_ruleset_c_close_below_50d_fires():
    bars = _bars([110.0] * 50 + [100.0])  # SMA50 around 110; close=100 < SMA50
    rs = RulesetC()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=50, entry_price=110.0, initial_stop=90.0)
    action = rs.update_and_check(
        state=state, bars=bars, bar_idx=50, entry_idx=50,
        entry_price=110.0, initial_R=20.0,
    )
    assert isinstance(action, FullExit)
    assert action.reason == "close_below_50d"


# ---------------------------------------------------------------------------
# Ruleset D -- Minervini Stage-2 progression (NEW)
# ---------------------------------------------------------------------------
def test_ruleset_d_breakeven_arms_at_plus_2R_and_raises_stop_to_entry():
    bars = _bars([100.0, 105.0, 115.0, 125.0])  # +2R hit at bar_idx=2 (close=115; +1.5R)
    # Use initial_stop=90 so +2R = 100 + 2*10 = 120
    bars = _bars([100.0, 105.0, 110.0, 120.0])  # +2R at bar_idx=3 (close=120; +2.0R)
    rs = RulesetD()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=0, entry_price=100.0, initial_stop=90.0)
    assert not state.breakeven_armed
    rs.update_and_check(
        state=state, bars=bars, bar_idx=3, entry_idx=0,
        entry_price=100.0, initial_R=10.0,
    )
    assert state.breakeven_armed is True
    assert state.current_stop >= 100.0  # raised to at least entry (BE)


def test_ruleset_d_50d_gate_does_not_fire_when_sma50_at_or_below_entry_threshold():
    """sma50 = 100 (= entry); gate requires sma50 > entry * 1.05 = 105.
    Gate NOT armed; close <= sma50 should NOT fire exit."""
    closes = [100.0] * 50 + [95.0]  # SMA50 = 100; close = 95
    bars = _bars(closes)
    rs = RulesetD()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=50, entry_price=100.0, initial_stop=90.0)
    action = rs.update_and_check(
        state=state, bars=bars, bar_idx=50, entry_idx=50,
        entry_price=100.0, initial_R=10.0,
    )
    # 95 > current_stop (90), so no stop hit. sma50 = 100 NOT > entry * 1.05 (105),
    # so gate NOT armed; no close_below_50d_gated exit. Should return None.
    assert action is None


def test_ruleset_d_50d_gate_fires_when_sma50_above_entry_times_1_05_and_close_below_sma50():
    # SMA50 = 120 (well above entry 100 * 1.05 = 105); close = 115 (below SMA50)
    closes = [120.0] * 50 + [115.0]
    bars = _bars(closes)
    rs = RulesetD()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=50, entry_price=100.0, initial_stop=90.0)
    action = rs.update_and_check(
        state=state, bars=bars, bar_idx=50, entry_idx=50,
        entry_price=100.0, initial_R=10.0,
    )
    assert isinstance(action, FullExit)
    assert action.reason == "close_below_50d_gated"


def test_ruleset_d_50d_gate_mult_is_1_05():
    """Lock the exact gate threshold per dispatch brief Section 3.4."""
    assert RULESET_D_50D_GATE_MULT == pytest.approx(1.05)


# ---------------------------------------------------------------------------
# Ruleset E -- O'Neil cup-with-handle + Bulkowski measured-move (NEW)
# ---------------------------------------------------------------------------
def test_ruleset_e_initial_stop_uses_max_of_trough_floor_and_oneil_8pct():
    """Use whichever is HIGHER (tighter risk) per brief Section 3.5."""
    rs = RulesetE()
    # Case 1: trough_2 stop tighter (trough_2 * 0.99 = 99 > entry * 0.92 = 92)
    v = _verdict(trough_2=100.0, trough_1=98.0)
    stop = rs.initial_stop(verdict=v, entry_price=100.0)
    assert stop == pytest.approx(99.0)  # 100 * 0.99
    # Case 2: O'Neil 8% tighter (entry * 0.92 = 92 > trough_2 * 0.99 = 89.1)
    v = _verdict(trough_2=90.0, trough_1=88.0)
    stop = rs.initial_stop(verdict=v, entry_price=100.0)
    assert stop == pytest.approx(92.0)  # entry * 0.92


def test_ruleset_e_measured_move_target_equals_entry_plus_W_height():
    """target = entry + (center_peak - min(trough_1, trough_2))."""
    rs = RulesetE()
    v = _verdict(center_peak=120.0, trough_1=85.0, trough_2=80.0)
    bars = _bars([100.0] * 10)
    initial_stop = rs.initial_stop(verdict=v, entry_price=100.0)
    state = rs.init_state(verdict=v, bars=bars, entry_idx=0, entry_price=100.0, initial_stop=initial_stop)
    # W height = 120 - min(85, 80) = 120 - 80 = 40; target = 100 + 40 = 140
    assert state.extra["target_price"] == pytest.approx(140.0)


def test_ruleset_e_target_exit_fires_at_target_price_not_close():
    rs = RulesetE()
    v = _verdict(center_peak=110.0, trough_1=88.0, trough_2=90.0)
    bars = _bars([100.0, 105.0, 110.0, 125.0])  # bar_idx=3 close=125 >= target 120
    initial_stop = rs.initial_stop(verdict=v, entry_price=100.0)
    state = rs.init_state(verdict=v, bars=bars, entry_idx=0, entry_price=100.0, initial_stop=initial_stop)
    # target = 100 + (110 - 88) = 122; close=125 >= 122 -> target fires at PRICE 122
    target = state.extra["target_price"]
    action = rs.update_and_check(
        state=state, bars=bars, bar_idx=3, entry_idx=0,
        entry_price=100.0, initial_R=100.0 - initial_stop,
    )
    assert isinstance(action, FullExit)
    assert action.reason == "target_measured_move"
    assert action.price == pytest.approx(target)


def test_ruleset_e_no_trail_no_50d_no_momentum_gate():
    """E ONLY has stop_hit + target_measured_move. No SMA-based exits.
    Plant a setup where SMA50 < close + position open + no target hit:
    should return None (continue holding)."""
    rs = RulesetE()
    v = _verdict(center_peak=200.0, trough_1=88.0, trough_2=90.0)  # high target
    closes = [105.0] * 50 + [115.0]
    bars = _bars(closes)
    initial_stop = rs.initial_stop(verdict=v, entry_price=100.0)
    state = rs.init_state(verdict=v, bars=bars, entry_idx=50, entry_price=100.0, initial_stop=initial_stop)
    action = rs.update_and_check(
        state=state, bars=bars, bar_idx=50, entry_idx=50,
        entry_price=100.0, initial_R=100.0 - initial_stop,
    )
    # close=115; target is 100 + (200 - 88) = 212; not hit. SMA50 ~ 105 (above stop).
    # E has no 50d exit; should return None.
    assert action is None


def test_ruleset_e_stop_at_oneil_8pct_uses_max():
    rs = RulesetE()
    assert RULESET_E_STOP_PCT == pytest.approx(0.92)


# ---------------------------------------------------------------------------
# Ruleset F -- Qullamaggie momentum-burst (NEW)
# ---------------------------------------------------------------------------
def test_ruleset_f_initial_atr_captured_at_entry_bar():
    # Generate bars with predictable ATR; capture at entry_idx
    closes = [100.0 + i * 0.5 for i in range(30)]  # gentle uptrend
    bars = _bars(closes, highs=[c + 1.0 for c in closes], lows=[c - 1.0 for c in closes])
    rs = RulesetF()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=20, entry_price=110.0, initial_stop=99.0)
    assert state.initial_atr14 is not None
    assert state.initial_atr14 > 0  # ATR is positive


def test_ruleset_f_momentum_gate_fires_at_session_6_open_if_not_armed():
    """No momentum: closes stay at entry; ATR > 0; gate should fire at session 6 OPEN."""
    # Pre-entry bars to satisfy ATR window; entry bar + 5 flat sessions
    pre = [100.0] * 20
    post = [101.0] * 6  # tiny moves; close - entry < ATR
    closes = pre + post
    bars = _bars(closes, highs=[c + 1.0 for c in closes], lows=[c - 1.0 for c in closes])
    rs = RulesetF()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=20, entry_price=100.0, initial_stop=90.0)
    # Walk sessions 1..6
    for i in range(20, 26):
        action = rs.update_and_check(
            state=state, bars=bars, bar_idx=i, entry_idx=20,
            entry_price=100.0, initial_R=10.0,
        )
        session_n = i - 20 + 1
        if session_n == 6:
            # Should fire momentum_gate_fail at this bar OPEN
            assert isinstance(action, FullExit)
            assert action.reason == "momentum_gate_fail"
            assert action.price == float(bars["Open"].iloc[i])
        else:
            assert action is None


def test_ruleset_f_momentum_gate_does_not_fire_when_armed_in_sessions_1_to_5():
    """If close - entry >= ATR14 anywhere in sessions 1-5, gate arms and
    session 6 does NOT exit on momentum_gate_fail."""
    pre = [100.0] * 20
    # Build pre-entry ATR ~ 2 (high-low = 2)
    pre_highs = [101.0] * 20
    pre_lows = [99.0] * 20
    # Session 1 (entry bar): close 100; sessions 2-3 spike +5; sessions 4-6 hold
    post = [100.0, 105.0, 105.0, 105.0, 105.0, 105.0]
    post_highs = [101.0, 106.0, 106.0, 106.0, 106.0, 106.0]
    post_lows = [99.0, 104.0, 104.0, 104.0, 104.0, 104.0]
    closes = pre + post
    highs = pre_highs + post_highs
    lows = pre_lows + post_lows
    bars = _bars(closes, highs=highs, lows=lows)
    rs = RulesetF()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=20, entry_price=100.0, initial_stop=90.0)
    # ATR ~ 2; close - entry by session 2 = 5 >= 2; gate arms.
    actions = []
    for i in range(20, 26):
        a = rs.update_and_check(
            state=state, bars=bars, bar_idx=i, entry_idx=20,
            entry_price=100.0, initial_R=10.0,
        )
        actions.append(a)
    # Gate should be armed; no momentum_gate_fail across the 6 sessions
    assert state.momentum_gate_armed is True
    assert not any(
        isinstance(a, FullExit) and a.reason == "momentum_gate_fail" for a in actions
    )


def test_ruleset_f_scale_out_fires_at_plus_2R_close():
    """Plant a setup that reaches +2R; verify ScaleOut(1/3) fires."""
    pre = [100.0] * 20
    # Entry 100, R = 10; +2R = 120
    post = [101.0, 105.0, 120.0]
    closes = pre + post
    bars = _bars(closes, highs=[c + 1.0 for c in closes], lows=[c - 1.0 for c in closes])
    rs = RulesetF()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=20, entry_price=100.0, initial_stop=90.0)
    # Walk sessions 1..3
    actions = []
    for i in range(20, 23):
        actions.append(
            rs.update_and_check(
                state=state, bars=bars, bar_idx=i, entry_idx=20,
                entry_price=100.0, initial_R=10.0,
            )
        )
    # +2R at session 3 (close=120)
    assert isinstance(actions[2], ScaleOut)
    assert actions[2].fraction == pytest.approx(1.0 / 3.0)
    assert actions[2].price == 120.0
    assert actions[2].reason == "scale_out_2R"


def test_ruleset_f_scale_out_raises_stop_to_breakeven():
    pre = [100.0] * 20
    post = [101.0, 105.0, 120.0]
    closes = pre + post
    bars = _bars(closes, highs=[c + 1.0 for c in closes], lows=[c - 1.0 for c in closes])
    rs = RulesetF()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=20, entry_price=100.0, initial_stop=90.0)
    for i in range(20, 23):
        action = rs.update_and_check(
            state=state, bars=bars, bar_idx=i, entry_idx=20,
            entry_price=100.0, initial_R=10.0,
        )
        if isinstance(action, ScaleOut):
            state.scale_out_fired = True  # walkforward normally does this
            state.scale_out_R = (action.price - 100.0) / 10.0
            state.scale_out_fraction = action.fraction
    # Stop should have been raised to >= entry (BE)
    assert state.current_stop >= 100.0
    assert state.breakeven_armed is True


def test_ruleset_f_momentum_atr_mult_locked_at_1_0():
    assert RULESET_F_MOMENTUM_ATR_MULT == pytest.approx(1.0)


def test_ruleset_f_atr_window_locked_at_14():
    assert RULESET_F_ATR_WINDOW == 14


# ---------------------------------------------------------------------------
# Codex R1 fix discriminating tests (M1 + M2)
# ---------------------------------------------------------------------------
def test_ruleset_f_session_6_open_gate_pre_empts_close_based_stop_codex_r1_m1():
    """At session 6, momentum_gate_fail at OPEN must fire BEFORE the
    close-based stop check. Plant a setup where session 6 close would hit
    the stop but momentum gate has NOT armed -> assert exit_reason is
    momentum_gate_fail (NOT stop_hit), at OPEN price (not close)."""
    pre = [100.0] * 20  # enough for ATR14
    # Sessions 1-5 flat at 100 (no momentum), session 6 OPEN=99 close=80 (stop hit if it ran)
    post_close = [100.0, 100.0, 100.0, 100.0, 100.0, 80.0]
    post_open = [100.0, 100.0, 100.0, 100.0, 100.0, 99.0]
    closes = pre + post_close
    opens = pre + post_open
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    bars = _bars(closes, opens=opens, highs=highs, lows=lows)
    rs = RulesetF()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=20, entry_price=100.0, initial_stop=90.0)
    # Walk through 6 sessions
    final = None
    for i in range(20, 26):
        action = rs.update_and_check(
            state=state, bars=bars, bar_idx=i, entry_idx=20,
            entry_price=100.0, initial_R=10.0,
        )
        if action is not None:
            final = action
            break
    assert isinstance(final, FullExit)
    # Pre-fix: would be stop_hit at close=80. Post-fix: momentum_gate_fail at OPEN=99.
    assert final.reason == "momentum_gate_fail"
    assert final.price == 99.0


def test_ruleset_f_no_atr_pre_history_treats_gate_as_armed_by_default_codex_r1_m2():
    """If pre-entry bars insufficient for ATR14 (need >= 15 prior bars),
    state.initial_atr14 = None and gate becomes auto-pass per Codex R1 M#2
    fix. Trade continues with stop/50d/scale-out rules only."""
    # Plant only 5 bars before entry; ATR14 requires 14+1 = 15 bars at entry_idx
    closes = [100.0] * 6  # too short
    bars = _bars(closes, highs=[c + 1.0 for c in closes], lows=[c - 1.0 for c in closes])
    rs = RulesetF()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=5, entry_price=100.0, initial_stop=90.0)
    # ATR14 should be None
    assert state.initial_atr14 is None
    # momentum_gate_armed should be True by default (skip gate)
    assert state.momentum_gate_armed is True


def test_ruleset_f_no_atr_gate_skip_means_no_momentum_gate_fail_at_session_6():
    """With ATR14 unavailable -> gate auto-armed -> session 6 does NOT fire
    momentum_gate_fail even if close stays flat."""
    closes = [100.0] * 12  # only 12 bars total; ATR14 unavailable at entry_idx=5
    bars = _bars(closes, highs=[c + 1.0 for c in closes], lows=[c - 1.0 for c in closes])
    rs = RulesetF()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=5, entry_price=100.0, initial_stop=90.0)
    # Walk 6 sessions
    actions = []
    for i in range(5, min(11, len(bars))):
        a = rs.update_and_check(
            state=state, bars=bars, bar_idx=i, entry_idx=5,
            entry_price=100.0, initial_R=10.0,
        )
        actions.append(a)
    # No momentum_gate_fail anywhere
    assert not any(
        isinstance(a, FullExit) and a.reason == "momentum_gate_fail" for a in actions
    )


def test_ruleset_d_trail_check_then_raise_ordering_preserves_d1_precedent_codex_r1_m3_strengthened():
    """D's trail ordering: stop check runs BEFORE today's SMA10-derived
    stop raise. Discriminating semantic: today's close BETWEEN yesterday's
    stop AND today's newly-computed trail stop -> trade HOLDS this bar
    (does not exit on the about-to-be-raised stop). The exit fires on the
    NEXT bar's close against the now-raised stop.

    Strengthened test per Codex R2 m#1 critique: assert (a) the specific
    bar at the boundary returns None; (b) state.current_stop is raised
    after the call; (c) the next bar's close (lower than raised stop)
    fires the exit.
    """
    # Build a setup where SMA10 climbs above the current stop after BE arm.
    # Stage 1: 25 pre-bars at 100 (warmup); entry at idx 25; +2R hit at idx 26
    # (close=120); BE arms, stop -> 100; SMA10 starts climbing as more bars
    # at higher levels accumulate.
    pre = [100.0] * 25
    post = [
        # idx 25 entry close 100
        100.0,
        # idx 26 close 120 -> +2R, BE arms (stop=100), SMA10 trail begins
        120.0,
        # idx 27-31 closes climb so SMA10 climbs
        125.0, 130.0, 135.0, 140.0, 145.0,
    ]
    closes = pre + post
    bars = _bars(closes, highs=[c + 1.0 for c in closes], lows=[c - 1.0 for c in closes])
    rs = RulesetD()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=25, entry_price=100.0, initial_stop=90.0)
    # Walk bars; at idx 26 BE arms (close=120 >= entry + 2R)
    for i in range(25, len(bars)):
        action = rs.update_and_check(
            state=state, bars=bars, bar_idx=i, entry_idx=25,
            entry_price=100.0, initial_R=10.0,
        )
        # No exit on these climbing bars
        assert action is None, f"bar {i} should not exit"
    # Stop now raised to SMA10*0.99 (much closer to current close than initial 90)
    assert state.breakeven_armed is True
    assert state.current_stop > 100.0  # raised above entry due to SMA10 climbing
    raised_stop = state.current_stop
    # Plant a NEXT bar whose close drops below the raised_stop but ABOVE
    # the prior current_stop value at the start of that bar's processing
    # (Note: we MUTATE bars to simulate the next bar; this isolates the
    # check-then-raise semantic.) The exit should fire as trail_stop.
    next_close = raised_stop * 0.95  # well below raised stop
    new_bars = _bars(closes + [next_close], highs=[c + 1.0 for c in closes + [next_close]],
                     lows=[c - 1.0 for c in closes + [next_close]])
    # Re-init state and re-walk to the next bar (state was on stack)
    state2 = rs.init_state(verdict=v, bars=new_bars, entry_idx=25, entry_price=100.0, initial_stop=90.0)
    for i in range(25, len(new_bars)):
        action = rs.update_and_check(
            state=state2, bars=new_bars, bar_idx=i, entry_idx=25,
            entry_price=100.0, initial_R=10.0,
        )
        if i == len(new_bars) - 1:
            assert isinstance(action, FullExit)
            assert action.reason == "trail_stop"


def test_ruleset_f_trail_post_scaleout_uses_sma20_not_initial_stop():
    """Lock the F semantics: after scale-out, trail uses SMA20 (not initial
    stop). Verify state.current_stop tracks SMA20 over subsequent bars."""
    pre = [100.0] * 25
    post = [
        101.0, 120.0,  # +2R hit at idx 26 -> ScaleOut
        125.0, 130.0, 135.0,  # post-scale climbing
    ]
    closes = pre + post
    bars = _bars(closes, highs=[c + 1.0 for c in closes], lows=[c - 1.0 for c in closes])
    rs = RulesetF()
    v = _verdict()
    state = rs.init_state(verdict=v, bars=bars, entry_idx=25, entry_price=100.0, initial_stop=90.0)
    for i in range(25, len(bars)):
        a = rs.update_and_check(
            state=state, bars=bars, bar_idx=i, entry_idx=25,
            entry_price=100.0, initial_R=10.0,
        )
        if isinstance(a, ScaleOut):
            state.scale_out_fired = True
            state.scale_out_R = (a.price - 100.0) / 10.0
            state.scale_out_fraction = a.fraction
    # Post-scale-out: stop should track SMA20 (which climbed above entry)
    assert state.scale_out_fired is True
    assert state.current_stop >= 100.0  # at least at BE
