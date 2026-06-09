from __future__ import annotations

import math

import pytest

from research.harness.shadow_expectancy.io import Bar
from research.harness.shadow_expectancy.simulator import SimParams, simulate


def _params(**kw):
    base = dict(initial_shares=100.0, partial_session_n=3, partial_pct=0.5,
                breakeven_r_trigger=1.0, maturity_fast_ma_r=2.0, ma_fast_period=10,
                ma_slow_period=20, horizon_sessions=126)
    base.update(kw)
    return SimParams(**base)


def test_golden_a_gap_up_entry_single_fill_ambiguity_flag():
    # detection pivot 10; entry bar gaps up: open 10.5 > pivot -> entry_fill = 10.5.
    # MECHANICAL initial stop = entry_bar.low = 10.2 (C1: NOT a candidate input).
    # entry_bar.low(10.2) < entry_fill(10.5) -> ambiguous subset; rps = 10.5 - 10.2 = 0.3.
    entry_bar = Bar("2026-06-01", open=10.5, high=11.0, low=10.2, close=10.8)
    # one calm forward bar that never trips the entry-bar-low stop, then horizon.
    fwd = [Bar("2026-06-02", 10.8, 11.2, 10.6, 11.0)]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=1))
    assert res.entry_fill == 10.5
    assert res.initial_stop == 10.2                 # C1: derived from entry_bar.low
    assert res.entry_bar_ambiguous is True          # low(10.2) < entry_fill(10.5)
    assert res.degenerate is False
    assert math.isclose(res.risk_per_share, 0.3)    # 10.5 - 10.2


def test_golden_b_gap_down_stop_blows_through_1R():
    # entry_fill 10.0, MECHANICAL initial stop = entry_bar.low = 9.0 (rps = 1.0).
    # Next bar gaps down: open 8.5 (< stop), low 8.0. realistic fills at min(stop,open)=8.5
    # -> single-leg R = (8.5-10.0)*100 / (1.0*100) = -1.5; favorable fills at stop 9.0 -> -1R.
    entry_bar = Bar("2026-06-01", open=10.0, high=10.4, low=9.0, close=10.2)
    fwd = [Bar("2026-06-02", open=8.5, high=8.6, low=8.0, close=8.2)]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd, params=_params())
    assert res.initial_stop == 9.0                  # C1: entry_bar.low
    assert math.isclose(res.risk_per_share, 1.0)
    assert res.exit_reason == "initial_stop"
    assert math.isclose(res.realized_r["realistic"], -1.5)
    assert math.isclose(res.realized_r["favorable_reprice"], -1.0)
    assert res.realized_r["favorable_reprice"] >= res.realized_r["realistic"]


def test_golden_f_degenerate_risk_excluded():
    # C1: degenerate requires entry_fill <= entry_bar.low. Since entry_fill = max(pivot,open)
    # and low <= open, this happens only when entry_bar.low == entry_bar.open AND pivot <= open
    # (a flat-bottomed bar that opens on its low). pivot 9.0, open 9.0, low 9.0 -> entry_fill 9.0,
    # initial_stop 9.0, rps 0 -> degenerate.
    entry_bar = Bar("2026-06-01", open=9.0, high=9.5, low=9.0, close=9.2)
    res = simulate(pivot=9.0, entry_bar=entry_bar, forward_bars=[], params=_params())
    assert res.degenerate is True
    assert res.exit_reason == "degenerate_risk"
    assert res.realized_r is None


def test_golden_e_not_in_profit_at_N_no_partial():
    # entry_fill 10.0, mechanical stop = entry_bar.low = 9.0. session 3 close 9.8
    # (< entry_fill) -> NO partial. (lows kept >= 9.0 so no stop-out before s3.)
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.1)
    fwd = [
        Bar("2026-06-02", 10.1, 10.3, 9.7, 9.9),   # s1
        Bar("2026-06-03", 9.9, 10.0, 9.6, 9.85),   # s2
        Bar("2026-06-04", 9.85, 9.95, 9.6, 9.8),   # s3 close 9.8 < entry -> no partial
    ]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=3))
    assert res.initial_stop == 9.0
    assert all(leg.action != "partial" for leg in res.legs)


def test_partial_fires_at_session_3_when_in_profit():
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.1)   # stop = low = 9.0
    fwd = [
        Bar("2026-06-02", 10.2, 10.6, 10.0, 10.5),
        Bar("2026-06-03", 10.5, 10.9, 10.3, 10.8),
        Bar("2026-06-04", 10.8, 11.4, 10.7, 11.2),   # s3 close 11.2 > entry -> partial
    ]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=3))
    partials = [leg for leg in res.legs if leg.action == "partial"]
    assert len(partials) == 1 and partials[0].qty == 50.0 and partials[0].price == 11.2


def test_breakeven_raises_stop_to_entry_after_1R():
    # entry_fill 10.0, mechanical stop = entry_bar.low = 9.0 (rps 1). s1 close 11.2 ->
    # r_so_far >= 1 -> stop -> 10.0. s2 low 9.9 <= BE stop 10.0 (and > old 9.0) -> BE exit.
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.1)
    fwd = [
        Bar("2026-06-02", 10.5, 11.3, 10.4, 11.2),  # s1 close -> +1.2R, BE raise
        Bar("2026-06-03", 11.0, 11.1, 9.9, 10.0),   # s2 low 9.9 <= BE stop 10.0 -> exit
    ]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=2))
    assert res.exit_reason == "breakeven_stop"


def test_precedence_stop_wins_over_partial_and_ma_same_bar():
    # A bar where stop-eligibility AND partial-eligibility both hold: stop (step 1) wins.
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.1)   # stop = low = 9.0
    fwd = [
        Bar("2026-06-02", 10.2, 10.6, 10.0, 10.5),
        Bar("2026-06-03", 10.5, 10.9, 10.3, 10.8),
        # s3: low 8.9 <= stop 9.0 (stop test) AND close 11.0 > entry (partial-eligible)
        Bar("2026-06-04", 10.8, 11.2, 8.9, 11.0),
    ]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=3))
    assert res.exit_reason == "initial_stop"
    assert all(leg.action != "partial" for leg in res.legs)  # stop terminated before partial


def test_multi_leg_r_uses_fixed_denominator_golden_1p6R():
    # Codex C2 golden: assert the multi-leg R helper directly (the load-bearing denominator
    # math). Two 50-share legs at +1.2R-equiv (11.2) and +2.0R-equiv (12.0); entry_fill 10.0,
    # rps 1.0, initial_shares 100. FIXED denominator: total_pnl = (11.2-10)*50 + (12.0-10)*50
    # = 60 + 100 = 160; R = 160/(1.0*100) = 1.6R. The OLD buggy per-leg sum would have been
    # 60/(1*50) + 100/(1*50) = 1.2 + 2.0 = 3.2R -- so 1.6 vs 3.2 discriminates the fix.
    from research.harness.shadow_expectancy.simulator import _r_for_legs
    total = _r_for_legs(entry_fill=10.0, rps=1.0, initial_shares=100.0,
                        legs_priced=[(50.0, 11.2), (50.0, 12.0)])
    assert math.isclose(total, 1.6)
    per_leg_buggy = (11.2 - 10.0) * 50 / (1.0 * 50) + (12.0 - 10.0) * 50 / (1.0 * 50)
    assert math.isclose(per_leg_buggy, 3.2) and per_leg_buggy != total
