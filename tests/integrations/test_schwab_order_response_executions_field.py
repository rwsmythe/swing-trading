"""Tests for `SchwabOrderResponse.executions` field extension (T-1.2).

Per plan §A.1.2 + spec §4.2 + §4.4. 8 discriminating cases covering
tri-valued semantics (`None` vs `[]` vs `[leg, ...]`) + 8-positional
backward compat + `__post_init__` extension validators.
"""
from __future__ import annotations

import dataclasses

import pytest

from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)


def _valid_leg(**overrides):
    base = {
        "leg_id": 1,
        "price": 5.2244,
        "quantity": 100.0,
        "mismarked_quantity": 0.0,
        "instrument_id": 12345,
        "time": "2026-05-15T14:30:00.000Z",
    }
    base.update(overrides)
    return SchwabExecutionLeg(**base)


def _valid_order_kwargs(**overrides):
    base = {
        "order_id": "ORD-100",
        "status": "FILLED",
        "enter_time": "2026-05-15T14:00:00.000Z",
        "instrument_symbol": "AAA",
        "instruction": "BUY",
        "quantity": 100.0,
        "order_type": "LIMIT",
        "price": 5.30,
    }
    base.update(overrides)
    return base


# Test 1 — default executions is None (tri-valued: data not available).
def test_default_executions_is_none() -> None:
    order = SchwabOrderResponse(**_valid_order_kwargs())
    assert order.executions is None


# Test 2 — empty list accepted (tri-valued: Schwab confirmed no executions).
def test_empty_executions_list_accepted() -> None:
    order = SchwabOrderResponse(**_valid_order_kwargs(), executions=[])
    assert order.executions == []


# Test 3 — non-empty list accepted (tri-valued: legs present).
def test_non_empty_executions_list_accepted() -> None:
    leg = _valid_leg()
    order = SchwabOrderResponse(**_valid_order_kwargs(), executions=[leg])
    assert order.executions == [leg]
    assert len(order.executions) == 1


# Test 4 — non-list executions rejected.
def test_non_list_executions_rejected() -> None:
    with pytest.raises(ValueError, match="executions"):
        SchwabOrderResponse(
            **_valid_order_kwargs(),
            executions="not-a-list",  # type: ignore[arg-type]
        )


# Test 5 — non-leg element rejected.
def test_non_leg_element_rejected() -> None:
    with pytest.raises(ValueError, match="executions"):
        SchwabOrderResponse(
            **_valid_order_kwargs(),
            executions=[{"leg_id": 1, "price": 5.0}],  # type: ignore[list-item]
        )


# Test 6 — 8-positional backward compat (no executions= kwarg).
def test_eight_positional_backward_compat() -> None:
    """Constructing with the legacy 8 positional args MUST succeed; this
    pins the field-tail placement of `executions` so Phase 11 callsites
    that pass positionals don't break."""
    order = SchwabOrderResponse(
        "ORD-200",            # order_id
        "FILLED",             # status
        "2026-05-15T14:00:00.000Z",  # enter_time
        "AAA",                # instrument_symbol
        "BUY",                # instruction
        100.0,                # quantity
        "LIMIT",              # order_type
        5.30,                 # price
    )
    assert order.executions is None


# Test 7 — frozen dataclass refuses executions reassignment.
def test_frozen_reassignment_rejected() -> None:
    order = SchwabOrderResponse(**_valid_order_kwargs())
    with pytest.raises(dataclasses.FrozenInstanceError):
        order.executions = [_valid_leg()]  # type: ignore[misc]


# Test 8 — pre-existing validator (unknown status) STILL rejects (regression).
def test_preexisting_status_validator_still_rejects() -> None:
    """Sub-bundle 1 T-1.2 field addition MUST NOT regress the V1 status
    enum validator."""
    with pytest.raises(ValueError, match="status"):
        SchwabOrderResponse(
            **_valid_order_kwargs(status="UNKNOWN_STATUS"),
            executions=None,
        )


# Bonus — multi-leg list preserved in order.
def test_multi_leg_executions_preserves_order() -> None:
    leg1 = _valid_leg(leg_id=1, price=10.00, quantity=50)
    leg2 = _valid_leg(leg_id=2, price=10.20, quantity=50)
    order = SchwabOrderResponse(
        **_valid_order_kwargs(),
        executions=[leg1, leg2],
    )
    assert order.executions == [leg1, leg2]
    assert order.executions[0].leg_id == 1
    assert order.executions[1].leg_id == 2
