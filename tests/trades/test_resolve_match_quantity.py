"""Tests for `_resolve_match_quantity` helper (T-1.5).

Per plan §A.1.5 + spec §5.3 Codex R1 M#2. 5 discriminating cases covering
the execution-grain quantity-match switch + V1 fall-back semantics.
"""
from __future__ import annotations

from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)
from swing.trades.schwab_reconciliation import _resolve_match_quantity


def _leg(*, leg_id=1, price=10.00, quantity=50,
         mismarked_quantity=0.0, instrument_id=None,
         time="2026-05-15T14:30:00.000Z"):
    return SchwabExecutionLeg(
        leg_id=leg_id, price=price, quantity=quantity,
        mismarked_quantity=mismarked_quantity, instrument_id=instrument_id,
        time=time,
    )


def _order(*, quantity=100.0, executions=None):
    return SchwabOrderResponse(
        order_id="ORD-100",
        status="FILLED",
        enter_time="2026-05-15T14:00:00.000Z",
        instrument_symbol="AAA",
        instruction="BUY",
        quantity=quantity,
        order_type="LIMIT",
        price=10.00,
        executions=executions,
    )


# Test 1 — no executions → returns so.quantity.
def test_no_executions_returns_so_quantity() -> None:
    assert _resolve_match_quantity(_order(quantity=100.0, executions=None)) == 100.0


# Test 2 — empty executions → returns so.quantity.
def test_empty_executions_returns_so_quantity() -> None:
    assert _resolve_match_quantity(_order(quantity=100.0, executions=[])) == 100.0


# Test 3 — single leg → returns leg quantity.
def test_single_leg_returns_leg_quantity() -> None:
    legs = [_leg(quantity=75)]
    assert _resolve_match_quantity(_order(quantity=100.0, executions=legs)) == 75


# Test 4 — multi leg → returns sum.
def test_multi_leg_returns_sum() -> None:
    legs = [_leg(leg_id=1, quantity=30), _leg(leg_id=2, quantity=70)]
    assert _resolve_match_quantity(_order(quantity=100.0, executions=legs)) == 100


# Test 5 — partial fill (Codex R1 M#2): order.quantity=200, executions=[leg@50]
# → returns 50 NOT 200.
def test_partial_fill_returns_legs_sum_not_order_quantity() -> None:
    legs = [_leg(quantity=50)]
    order = _order(quantity=200.0, executions=legs)
    assert _resolve_match_quantity(order) == 50
