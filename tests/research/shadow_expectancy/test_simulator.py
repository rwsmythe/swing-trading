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
