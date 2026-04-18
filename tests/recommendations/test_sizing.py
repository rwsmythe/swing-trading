"""Position sizing — risk-based + position-cap dual constraint, with feasibility."""
from __future__ import annotations

import pytest

from swing.recommendations.sizing import compute_shares, SizingResult


def test_basic_sizing_constrained_by_risk():
    r = compute_shares(entry=100.0, stop=98.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)
    assert r.shares == 3
    assert r.risk_dollars == pytest.approx(6.0)
    assert r.feasible is True
    assert r.constraint == "risk"


def test_sizing_constrained_by_position_cap():
    r = compute_shares(entry=100.0, stop=99.5, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)
    assert r.shares == 1
    assert r.constraint == "position_cap"


def test_infeasible_when_rps_exceeds_max_risk():
    r = compute_shares(entry=100.0, stop=50.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)
    assert r.shares == 0
    assert r.feasible is False
    assert r.constraint == "infeasible"


def test_invalid_stop_above_entry_raises():
    with pytest.raises(ValueError, match="stop must be < entry"):
        compute_shares(entry=100.0, stop=105.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)


def test_zero_equity_returns_zero_shares():
    r = compute_shares(entry=100.0, stop=98.0, equity=0.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)
    assert r.shares == 0
    assert r.feasible is False


def test_result_carries_metrics():
    r = compute_shares(entry=100.0, stop=98.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.15)
    assert r.notional == 300.0
    assert r.notional_pct == pytest.approx(25.0)
    assert r.risk_pct == pytest.approx(0.5)
