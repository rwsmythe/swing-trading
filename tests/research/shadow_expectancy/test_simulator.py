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


def test_golden_b_gap_down_stop_blows_through_1r():
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


def test_golden_e_not_in_profit_at_n_no_partial():
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


def test_breakeven_raises_stop_to_entry_after_1r():
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


def test_multi_leg_r_uses_fixed_denominator_golden_1p6r():
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


def test_golden_c_partial_then_ma_close_below_trail_winner():
    # Codex M1: construct so ONLY ma_close_below can fire. entry_fill 10.0, mechanical stop
    # = entry_bar.low = 9.0 (rps 1.0); after the s1 +1R close the BE stop raises to 10.0, and
    # EVERY post-entry low is kept >= 10.5 (> the BE stop) so no price-stop can pre-empt. A
    # steadily-rising series sits ABOVE its own SMA, so the trail only fires on the engineered
    # drop bar (i=20), which closes BELOW the SMA while its LOW (10.5) stays above the stop.
    # i=21 exists as the next bar so the realistic MA fill is its open (next-session open).
    from datetime import date, timedelta
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.5)   # entry_fill 10.0, stop 9.0
    closes = [10.6 + 0.1 * i for i in range(22)]           # steady rise, all closes >= 10.6
    d = date(2026, 6, 2)
    fwd = [Bar((d + timedelta(days=i)).isoformat(), c - 0.05, c + 0.2, c - 0.1, c)
           for i, c in enumerate(closes)]                  # lows = c - 0.1 >= 10.5 > stop 10.0
    # engineer the MA-exit on bar i=20 (NOT the last bar): close drops below the trailing MA
    # but the low stays at 10.6 (> BE stop 10.0). i=21 remains as the next bar (next-open fill).
    drop = fwd[20]
    fwd[20] = Bar(drop.session, drop.open, drop.high, 10.6, 11.0)  # close 11.0 < SMA; low 10.6
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=22))
    assert res.exit_reason == "ma_close_below"            # EXACTLY -- no stop pre-empts (M1)
    assert any(leg.action == "partial" for leg in res.legs)   # multi-leg: partial at s3
    # realistic terminal fill is the NEXT bar's open (5.6); favorable >= realistic.
    assert res.realized_r["favorable_reprice"] >= res.realized_r["realistic"]


def test_ma_close_below_at_horizon_edge_exits_at_signal_close():
    # Codex M2: the MA-close-below fires on the LAST available bar (no next session). The exit
    # must fill at the SIGNAL close (realistic) / favorable per 5.6 -- NOT silently censor.
    from datetime import date, timedelta
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.5)
    closes = [10.6 + 0.1 * i for i in range(21)]
    d = date(2026, 6, 2)
    fwd = [Bar((d + timedelta(days=i)).isoformat(), c - 0.05, c + 0.2, c - 0.1, c)
           for i, c in enumerate(closes)]
    drop = fwd[-1]                                          # the LAST bar fires the trail
    fwd[-1] = Bar(drop.session, drop.open, drop.high, 10.6, 11.0)
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=21))
    assert res.exit_reason == "ma_close_below"             # NOT horizon_mtm / censored
    assert res.open_at_horizon is False
    # signal-close fill on the edge: realistic == favorable (both at the signal close, no
    # next open to gap) -- 11.0 is the terminal leg price.
    term = [leg for leg in res.legs if leg.action == "exit"][-1]
    assert term.price == 11.0


def test_golden_d_horizon_censored_runner_four_scenarios():
    # A monotonic runner that never stops/MA-exits within a SHORT horizon -> open_at_horizon.
    from datetime import date, timedelta
    entry_bar = Bar("2026-06-01", 10.0, 10.2, 9.0, 10.1)   # stop = low = 9.0
    d = date(2026, 6, 2)
    fwd = [Bar((d + timedelta(days=i)).isoformat(), 10.1 + i, 10.3 + i, 10.0 + i, 10.2 + i)
           for i in range(5)]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=5))
    assert res.open_at_horizon is True
    sc = res.censoring_scenarios
    assert set(sc) == {"closed_only", "mtm_at_horizon",
                       "forced_exit_at_horizon_open", "stop_level_adverse"}
    # This runner takes the s3 50% partial at close 12.2 (= +1.1R-equiv on the 50-share leg,
    # = (12.2-10.0)*50/(1.0*100) = 1.1R). closed_only counts ONLY that realized partial leg
    # (the still-open 50-share remainder is EXCLUDED): closed_only == 1.1R.
    assert math.isclose(sc["closed_only"]["realistic"], 1.1)
    # realistic == favorable for an open trade under MTM/forced/stop-adverse (5.8).
    for scenario in ("mtm_at_horizon", "forced_exit_at_horizon_open", "stop_level_adverse"):
        assert sc[scenario]["realistic"] == sc[scenario]["favorable_reprice"]
    # stop_level_adverse marks the open remainder at the current (breakeven-raised) stop.
    assert sc["stop_level_adverse"]["realistic"] <= sc["mtm_at_horizon"]["realistic"]
    # this log has NO post-horizon bar -> forced-exit collapses to MTM (5.7 / M3), annotated.
    assert res.forced_exit_collapsed_to_mtm is True
    assert math.isclose(sc["forced_exit_at_horizon_open"]["realistic"],
                        sc["mtm_at_horizon"]["realistic"])


@pytest.mark.parametrize("stop,fwd_open,fwd_low", [
    (9.0, 8.5, 8.0),   # gap-down stop -> favorable -1R, realistic < -1R
    (9.0, 9.4, 8.9),   # no-gap stop -> equal arms (both at stop)
])
def test_bracket_bound_favorable_ge_realistic_fixed_denominator(stop, fwd_open, fwd_low):
    # C1: the mechanical stop is entry_bar.low, so set the entry bar's low to the
    # parametrized stop level (NOT a candidate input). entry_fill = max(pivot, open) = 10.0.
    entry_bar = Bar("2026-06-01", 10.0, 10.4, stop, 10.2)   # entry_bar.low == stop
    fwd = [Bar("2026-06-02", fwd_open, fwd_open + 0.3, fwd_low, fwd_open + 0.1)]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=1))
    assert res.initial_stop == stop
    assert res.realized_r["favorable_reprice"] >= res.realized_r["realistic"]
    # identical denominator across arms: risk_per_share is single-entry-fill derived.
    assert res.risk_per_share == 10.0 - stop  # entry_fill == max(pivot, open) == 10.0


# --- 19-D risk-unit floor (T1/T2/T3). Fixtures lifted verbatim from the live DB 2026-07-04.
# Reuse the existing _params(**kw) helper (do NOT redefine it): pass risk_floor_adr_ratio=. ---

# Real VSTS 06-25 A+ geometry: pivot 13.56; adr_pct 4.16785698; entry O/H/L/C below.
# entry_fill = max(pivot, open) = 13.6000004; stop = low = 13.5550003; rps = 0.0450001.
# min_rps @ ratio 0.15 = 0.15 * (4.16785698/100 * 13.6000004) = 0.08502.
# PRE-FIX (ratio 0.0) -> min_rps 0.0 -> rps 0.045 > 0 -> NOT degenerate.
# POST-FIX (ratio 0.15) -> rps 0.045 < 0.08502 -> degenerate_risk.
_VSTS_ENTRY = Bar(session="2026-06-25", open=13.600000381469727, high=14.020000457763672,
                  low=13.555000305175781, close=13.739999771118164)
_VSTS_FWD = [Bar(session="2026-06-26", open=13.71, high=14.42, low=13.68, close=14.42),
             Bar(session="2026-06-29", open=14.39, high=14.85, low=14.16, close=14.83)]
_VSTS_ADR = 4.16785698182119


def test_t1_vsts_collapse_survives_zero_floor_but_caught_by_risk_floor():
    off = simulate(pivot=13.5600004, entry_bar=_VSTS_ENTRY, forward_bars=_VSTS_FWD,
                   params=_params(risk_floor_adr_ratio=0.0), adr_pct=_VSTS_ADR)
    assert off.degenerate is False              # pre-fix: the zero-floor lets it through
    on = simulate(pivot=13.5600004, entry_bar=_VSTS_ENTRY, forward_bars=_VSTS_FWD,
                  params=_params(risk_floor_adr_ratio=0.15), adr_pct=_VSTS_ADR)
    assert on.degenerate is True                # post-fix: caught
    assert on.exit_reason == "degenerate_risk"
    assert on.realized_r is None


# Real TVTX 06-12 geometry: pivot 49.68; adr_pct 4.74395635; entry O/H/L/C below.
# entry_fill = max(pivot, open) = 49.6800003; stop = low = 48.9799995; rps = 0.7000008.
# min_rps @ 0.15 = 0.15 * (4.74395635/100 * 49.6800003) = 0.35352. rps 0.70 > 0.35352 -> SURVIVES.
_TVTX_ENTRY = Bar(session="2026-06-12", open=49.099998474121094, high=52.720001220703125,
                  low=48.97999954223633, close=52.040000915527344)
_TVTX_FWD = [Bar(session="2026-06-15", open=52.44, high=53.88, low=52.06, close=53.8),
             Bar(session="2026-06-16", open=53.88, high=54.38, low=52.72, close=53.38)]
_TVTX_ADR = 4.7439563469121495


def test_t2_tvtx_tight_but_real_survives_with_r_unchanged():
    off = simulate(pivot=49.6800003, entry_bar=_TVTX_ENTRY, forward_bars=_TVTX_FWD,
                   params=_params(risk_floor_adr_ratio=0.0), adr_pct=_TVTX_ADR)
    on = simulate(pivot=49.6800003, entry_bar=_TVTX_ENTRY, forward_bars=_TVTX_FWD,
                  params=_params(risk_floor_adr_ratio=0.15), adr_pct=_TVTX_ADR)
    assert on.degenerate is False                       # NOT over-caught
    assert on.realized_r is not None
    assert on.realized_r == off.realized_r              # R unchanged pre->post
    assert on.risk_per_share == off.risk_per_share


# Real GTX run-89 geometry: an ORDINARY healthy signal (NOT an artifact). pivot 34.34; adr 4.0236;
# entry_fill=max(pivot,open)=34.34; stop=low=33.36; rps=0.98 (rps/ADR=0.709 -- well above floor).
# min_rps @ 0.15 = 0.15 * (4.0236/100 * 34.34) = 0.207; rps 0.98 >> 0.207 -> SURVIVES both paths.
_GTX_ENTRY = Bar(session="2026-06-12", open=33.83000183105469, high=34.41999816894531,
                 low=33.36000061035156, close=33.560001373291016)
_GTX_FWD = [Bar(session="2026-06-15", open=34.32, high=34.5, low=33.61, close=34.13),
            Bar(session="2026-06-16", open=34.45, high=35.055, low=34.12, close=34.61)]
_GTX_ADR = 4.0236


def test_t3_normal_signal_r_identical_pre_post():
    # Real ordinary signal: the floor must not move it. Non-vacuous -- a floor that (wrongly)
    # excluded GTX would flip degenerate to True and realized_r to None, failing these asserts.
    off = simulate(pivot=34.34, entry_bar=_GTX_ENTRY, forward_bars=_GTX_FWD,
                   params=_params(risk_floor_adr_ratio=0.0), adr_pct=_GTX_ADR)
    on = simulate(pivot=34.34, entry_bar=_GTX_ENTRY, forward_bars=_GTX_FWD,
                  params=_params(risk_floor_adr_ratio=0.15), adr_pct=_GTX_ADR)
    assert on.degenerate is False and on.realized_r is not None    # NOT excluded
    assert on.realized_r == off.realized_r                         # R (both arms) unchanged
    assert on.risk_per_share == off.risk_per_share


def test_min_risk_per_share_zero_when_adr_missing_else_ratio_times_adr_price():
    from research.harness.shadow_expectancy.simulator import _min_risk_per_share
    p = _params(risk_floor_adr_ratio=0.15)
    # adr null/<=0 -> floor DISABLED -> 0.0 (graceful degrade; no %-of-price fallback).
    assert _min_risk_per_share(100.0, None, p) == 0.0
    assert _min_risk_per_share(100.0, 0.0, p) == 0.0
    # adr present -> ratio * adr_price. adr 4.0% of 100 = 4.0; * 0.15 = 0.6.
    assert abs(_min_risk_per_share(100.0, 4.0, p) - 0.6) < 1e-9
