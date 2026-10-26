"""Position sizing — risk-based + position-cap dual constraint, with feasibility."""
from __future__ import annotations

import pytest

from swing.recommendations.sizing import compute_shares, SizingResult


def test_basic_sizing_constrained_by_risk():
    # entry=100, stop=98 → rps=$2. equity=1200, max_risk=0.5% → $6 risk budget → 3 shares.
    # Position cap raised to 30% so cap allows 3 shares (floor(1200*0.30/100)=3) — makes
    # risk the binding constraint. Tie is resolved to "risk" per impl (shares_by_risk<=cap).
    r = compute_shares(entry=100.0, stop=98.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.30)
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
    # Same configuration as test_basic_sizing_constrained_by_risk — risk binds at 3 shares.
    r = compute_shares(entry=100.0, stop=98.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.30)
    assert r.notional == 300.0
    assert r.notional_pct == pytest.approx(25.0)
    assert r.risk_pct == pytest.approx(0.5)


# ===========================================================================
# D84 T1 -- SizingResult carries the one-share risk and the budget; ONE
# formatter, `zero_share_line`, owns BOTH forms (the stated zero from a
# SizingResult, the criteria-only MARKER from a RiskInputs).
# ===========================================================================

_KOD_LINE = (
    "0 shares at the $37.50 budget; 1 share risks $77.31 (2.1x budget) at "
    "limit 107.12; above budget if you proceed")


def _kod():
    return compute_shares(entry=107.12, stop=29.81, equity=7500.0,
                          max_risk_pct=0.005, position_pct_cap=0.15)


def _cap_bound():
    # The risk leg allows 375 shares; the position cap ($1,125) allows 0.
    return compute_shares(entry=2000.0, stop=1999.9, equity=7500.0,
                          max_risk_pct=0.005, position_pct_cap=0.15)


def test_compute_shares_carries_risk_per_share_and_max_risk_dollars_on_every_return():
    """R-T1.1 -- bit-equal to the expressions that sized the order."""
    cases = [
        dict(entry=100.0, stop=98.0, equity=1200.0, max_risk_pct=0.005,
             position_pct_cap=0.30),           # feasible
        dict(entry=107.12, stop=29.81, equity=7500.0, max_risk_pct=0.005,
             position_pct_cap=0.15),           # infeasible (risk-bound)
        dict(entry=100.0, stop=98.0, equity=0.0, max_risk_pct=0.005,
             position_pct_cap=0.15),           # no_equity
    ]
    constraints = []
    for kw in cases:
        r = compute_shares(**kw)
        constraints.append(r.constraint)
        assert r.risk_per_share == kw["entry"] - kw["stop"]
        assert r.max_risk_dollars == kw["equity"] * kw["max_risk_pct"]
    assert constraints == ["risk", "infeasible", "no_equity"]


def test_zero_share_line_KOD_states_the_ruled_flag():  # noqa: N802
    """R-T1.2 -- CHARC F1-A (1), the verbatim shape, on the real KOD geometry."""
    from swing.recommendations.sizing import zero_share_line

    assert zero_share_line(_kod(), basis_label="limit",
                           basis_price=107.12) == _KOD_LINE


def test_zero_share_line_is_None_when_shares_are_positive():  # noqa: N802
    """R-T1.3."""
    from swing.recommendations.sizing import zero_share_line

    r = compute_shares(entry=100.0, stop=98.0, equity=1200.0,
                       max_risk_pct=0.005, position_pct_cap=0.30)
    assert r.shares == 3
    assert zero_share_line(r, basis_label="limit", basis_price=100.0) is None


def test_a_cap_bound_zero_is_NOT_stated_as_above_budget():  # noqa: N802
    """R-T1.4 -- kills an implementation that keys the flag on `shares == 0`."""
    from swing.recommendations.sizing import zero_share_line

    r = _cap_bound()
    assert r.shares == 0
    line = zero_share_line(r, basis_label="limit", basis_price=2000.0)
    assert line == "0 shares: one share at limit 2000.00 exceeds the position cap"
    assert "above budget" not in line


def test_zero_share_line_is_ASCII():  # noqa: N802
    """R-T1.5 -- every stated-zero variant AND the marker (cp1252)."""
    from swing.evaluation.scoring import RiskInputs
    from swing.recommendations.sizing import zero_share_line

    no_eq = compute_shares(entry=100.0, stop=98.0, equity=0.0,
                           max_risk_pct=0.005, position_pct_cap=0.15)
    sentinel = SizingResult(shares=0, risk_dollars=0.0, risk_pct=0.0,
                            notional=0.0, notional_pct=0.0, feasible=False,
                            constraint="infeasible")
    lines = [
        zero_share_line(_kod(), basis_label="limit", basis_price=107.12),
        zero_share_line(_cap_bound(), basis_label="entry", basis_price=2000.0),
        zero_share_line(no_eq, basis_label="cap", basis_price=100.0),
        zero_share_line(sentinel, basis_label="cap", basis_price=None),
        zero_share_line(risk=RiskInputs(1, 1)),
    ]
    assert all(isinstance(s, str) and s for s in lines)
    assert all(s.isascii() for s in lines)
    assert lines[2] == "0 shares: no equity recorded"


def test_the_build_sentinel_without_geometry_states_no_risk():
    """R-T1.6 -- the no-geometry sentinel (build.py's `_sizing_result`) keeps
    the word "infeasible" (it is not a risk fail); `basis_price` may be None
    ONLY on that branch (R2-02)."""
    import pytest

    from swing.recommendations.sizing import zero_share_line

    sentinel = SizingResult(shares=0, risk_dollars=0.0, risk_pct=0.0,
                            notional=0.0, notional_pct=0.0, feasible=False,
                            constraint="infeasible", risk_per_share=None)
    line = zero_share_line(sentinel, basis_label="cap", basis_price=None)
    assert line == "Sizing infeasible: no valid cap basis for this geometry"
    assert "infeasible" in line
    assert "$" not in line
    with pytest.raises(ValueError):
        zero_share_line(_kod(), basis_label="limit", basis_price=None)


def test_the_MARKER_form_renders_only_on_a_flagged_layer():  # noqa: N802
    """R-T1.7 -- P1 (no sizing numbers) and E-d (the formatter consumer)."""
    import pytest

    from swing.evaluation.scoring import RiskInputs
    from swing.recommendations.sizing import RISK_FLAG_MARKER, zero_share_line

    marker = zero_share_line(risk=RiskInputs(1, 1))
    assert marker == "RISK FLAG" == RISK_FLAG_MARKER
    assert not any(ch.isdigit() for ch in marker)
    assert zero_share_line(risk=RiskInputs(1, 0)) is None
    assert zero_share_line(risk=RiskInputs(0, 0)) is None
    with pytest.raises(ValueError):
        zero_share_line(_kod(), risk=RiskInputs(1, 1), basis_label="limit",
                        basis_price=107.12)
    with pytest.raises(ValueError):
        zero_share_line()


def test_risk_bound_zero_names_the_leg_once():
    """R-T1.8 -- the formatter and the card heading choose the leg through ONE
    test: `zero_share_line` returns the flag text exactly when
    `risk_bound_zero` is True."""
    from swing.recommendations.sizing import risk_bound_zero, zero_share_line

    feasible = compute_shares(entry=100.0, stop=98.0, equity=1200.0,
                              max_risk_pct=0.005, position_pct_cap=0.30)
    no_eq = compute_shares(entry=100.0, stop=98.0, equity=0.0,
                           max_risk_pct=0.005, position_pct_cap=0.15)
    assert risk_bound_zero(_kod()) is True
    assert risk_bound_zero(_cap_bound()) is False
    assert risk_bound_zero(feasible) is False
    assert risk_bound_zero(no_eq) is False
    for r, price in ((_kod(), 107.12), (_cap_bound(), 2000.0),
                     (feasible, 100.0), (no_eq, 100.0)):
        line = zero_share_line(r, basis_label="limit", basis_price=price)
        is_flag = line is not None and "above budget if you proceed" in line
        assert is_flag is risk_bound_zero(r)
