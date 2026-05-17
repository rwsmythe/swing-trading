"""Tests for `_compute_execution_price` helper (T-1.4).

Per plan §A.1.4 + spec §5.1. 10 discriminating cases covering single-leg,
multi-leg VWAP, edge cases (None/empty), commutativity, and the §10
worked examples for CVGI + LION.
"""
from __future__ import annotations

from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)
from swing.trades.schwab_reconciliation import _compute_execution_price


def _leg(*, leg_id=1, price=5.2244, quantity=100,
         mismarked_quantity=0.0, instrument_id=None,
         time="2026-05-15T14:30:00.000Z"):
    return SchwabExecutionLeg(
        leg_id=leg_id, price=price, quantity=quantity,
        mismarked_quantity=mismarked_quantity, instrument_id=instrument_id,
        time=time,
    )


def _order(*, executions=None, price=5.30):
    return SchwabOrderResponse(
        order_id="ORD-100",
        status="FILLED",
        enter_time="2026-05-15T14:00:00.000Z",
        instrument_symbol="AAA",
        instruction="BUY",
        quantity=100.0,
        order_type="LIMIT",
        price=price,
        executions=executions,
    )


# Test 1 — None executions → None.
def test_none_executions_returns_none() -> None:
    assert _compute_execution_price(_order(executions=None)) is None


# Test 2 — empty executions → None.
def test_empty_executions_returns_none() -> None:
    assert _compute_execution_price(_order(executions=[])) is None


# Test 3 — single leg → leg price (NOT order.price).
def test_single_leg_returns_leg_price() -> None:
    order = _order(executions=[_leg(price=5.2244)], price=5.30)
    assert _compute_execution_price(order) == 5.2244


# Test 4 — two-leg VWAP equal quantities (50@10.00 + 50@10.20 → 10.10).
def test_two_leg_vwap_equal_quantities() -> None:
    legs = [
        _leg(leg_id=1, price=10.00, quantity=50),
        _leg(leg_id=2, price=10.20, quantity=50),
    ]
    assert _compute_execution_price(_order(executions=legs)) == 10.10


# Test 5 — three-leg VWAP unequal quantities.
def test_three_leg_vwap_unequal_quantities() -> None:
    legs = [
        _leg(leg_id=1, price=10.00, quantity=33),
        _leg(leg_id=2, price=10.10, quantity=33),
        _leg(leg_id=3, price=10.20, quantity=34),
    ]
    # VWAP = (33*10.00 + 33*10.10 + 34*10.20) / 100
    #      = (330.00 + 333.30 + 346.80) / 100 = 1010.10 / 100 = 10.101
    result = _compute_execution_price(_order(executions=legs))
    assert result is not None
    assert abs(result - 10.101) < 1e-9


# Test 6 — VWAP commutative over leg order.
def test_vwap_commutative() -> None:
    legs_a = [
        _leg(leg_id=1, price=10.00, quantity=30),
        _leg(leg_id=2, price=10.20, quantity=70),
    ]
    legs_b = [
        _leg(leg_id=2, price=10.20, quantity=70),
        _leg(leg_id=1, price=10.00, quantity=30),
    ]
    result_a = _compute_execution_price(_order(executions=legs_a))
    result_b = _compute_execution_price(_order(executions=legs_b))
    assert result_a == result_b
    # And matches expected VWAP: (300 + 714) / 100 = 10.14
    assert abs(result_a - 10.14) < 1e-9  # type: ignore[operator]


# Test 7 — pure function — input not mutated by invocation.
def test_pure_function_no_side_effects() -> None:
    legs = [_leg(price=10.00, quantity=50), _leg(price=10.20, quantity=50)]
    order = _order(executions=legs)
    # Invoke multiple times.
    r1 = _compute_execution_price(order)
    r2 = _compute_execution_price(order)
    r3 = _compute_execution_price(order)
    assert r1 == r2 == r3
    # executions preserved byte-for-byte.
    assert order.executions == legs


# Test 8 — high-quantity sub-cent precision.
def test_high_quantity_sub_cent_precision() -> None:
    legs = [_leg(price=5.2244, quantity=1000)]
    result = _compute_execution_price(_order(executions=legs))
    assert result is not None
    assert abs(result - 5.2244) < 1e-12


# Test 9 — spec §10.1 CVGI walkthrough (5.2244 × 100 → 5.2244).
def test_spec_10_1_cvgi_walkthrough() -> None:
    legs = [_leg(price=5.2244, quantity=100)]
    assert _compute_execution_price(_order(executions=legs)) == 5.2244


# Test 10 — spec §10.2 LION walkthrough (12.6999 × 100 → 12.6999).
def test_spec_10_2_lion_walkthrough() -> None:
    legs = [_leg(price=12.6999, quantity=100)]
    assert _compute_execution_price(_order(executions=legs)) == 12.6999
