"""Pure derived-metric formula tests.

Discriminating fixture uses VIR's actual production numbers to verify the
formulas reproduce the legacy stored exits.realized_pnl + exits.r_multiple.
"""
from __future__ import annotations

import math

import pytest

from swing.trades.derived_metrics import (
    initial_risk_per_share,
    r_multiple,
    realized_pnl,
)


def test_realized_pnl_long_winner():
    assert realized_pnl(entry_price=10.0, exit_price=12.0, quantity=100.0) == 200.0


def test_realized_pnl_long_loser():
    assert realized_pnl(entry_price=10.0, exit_price=9.0, quantity=100.0) == -100.0


def test_initial_risk_per_share():
    assert initial_risk_per_share(entry_price=10.0, initial_stop=9.0) == 1.0


def test_r_multiple_minus_one_R():
    """+1R win -> r_multiple = +1.0; -1R loss -> -1.0; etc."""
    pnl = realized_pnl(entry_price=10.0, exit_price=9.0, quantity=100.0)
    risk = initial_risk_per_share(entry_price=10.0, initial_stop=9.0)
    r = r_multiple(realized_pnl=pnl, initial_risk_per_share=risk, quantity=100.0)
    assert r == -1.0


def test_r_multiple_vir_actual_production_numbers():
    """VIR's documented production numbers — discriminating fixture.

    Production DB at HEAD eba1625:
      VIR: entry=11.30, initial_stop=8.26, exit=10.30, qty=2.
      exits.realized_pnl = -2.0; exits.r_multiple = -0.32894736842105254.
    """
    entry_price = 11.30
    initial_stop = 8.26
    exit_price = 10.30
    quantity = 2.0

    pnl = realized_pnl(entry_price=entry_price, exit_price=exit_price, quantity=quantity)
    assert math.isclose(pnl, -2.0, abs_tol=1e-9)

    risk = initial_risk_per_share(entry_price=entry_price, initial_stop=initial_stop)
    assert math.isclose(risk, 3.04, abs_tol=1e-9)

    r = r_multiple(realized_pnl=pnl, initial_risk_per_share=risk, quantity=quantity)
    # Legacy stored value: -0.32894736842105254
    assert math.isclose(r, -0.32894736842105254, abs_tol=1e-12)


def test_r_multiple_raises_on_zero_risk():
    """Edge case: zero risk_per_share or zero quantity -> ValueError."""
    with pytest.raises(ValueError, match="zero"):
        r_multiple(realized_pnl=0.0, initial_risk_per_share=0.0, quantity=100.0)
    with pytest.raises(ValueError, match="zero"):
        r_multiple(realized_pnl=0.0, initial_risk_per_share=1.0, quantity=0.0)
