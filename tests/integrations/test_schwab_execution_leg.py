"""Tests for `SchwabExecutionLeg` dataclass (Sub-bundle 1 T-1.1).

Per plan §A.1.1 + spec §4.1. 12 discriminating cases covering all 6
__post_init__ invariants + frozen-dataclass behavior.
"""
from __future__ import annotations

import dataclasses
import math

import pytest

from swing.integrations.schwab.models import SchwabExecutionLeg


def _valid_kwargs(**overrides):
    """Helper: minimum valid kwargs; tests override one field at a time."""
    base = {
        "leg_id": 1,
        "price": 5.2244,
        "quantity": 100.0,
        "mismarked_quantity": 0.0,
        "instrument_id": 12345,
        "time": "2026-05-15T14:30:00.000Z",
    }
    base.update(overrides)
    return base


# Test 1 — valid construction succeeds + all fields preserved.
def test_valid_construction_preserves_all_fields() -> None:
    leg = SchwabExecutionLeg(**_valid_kwargs())
    assert leg.leg_id == 1
    assert leg.price == 5.2244
    assert leg.quantity == 100.0
    assert leg.mismarked_quantity == 0.0
    assert leg.instrument_id == 12345
    assert leg.time == "2026-05-15T14:30:00.000Z"


# Test 2 — zero price rejected.
def test_zero_price_rejected() -> None:
    with pytest.raises(ValueError, match="price"):
        SchwabExecutionLeg(**_valid_kwargs(price=0.0))


# Test 3 — negative price rejected.
def test_negative_price_rejected() -> None:
    with pytest.raises(ValueError, match="price"):
        SchwabExecutionLeg(**_valid_kwargs(price=-1.0))


# Test 4 — non-finite price (NaN / inf) rejected.
def test_non_finite_price_rejected() -> None:
    with pytest.raises(ValueError, match="price"):
        SchwabExecutionLeg(**_valid_kwargs(price=float("nan")))
    with pytest.raises(ValueError, match="price"):
        SchwabExecutionLeg(**_valid_kwargs(price=float("inf")))


# Test 5 — zero quantity rejected.
def test_zero_quantity_rejected() -> None:
    with pytest.raises(ValueError, match="quantity"):
        SchwabExecutionLeg(**_valid_kwargs(quantity=0.0))


# Test 6 — bool-as-price rejected (Python bool is subclass of int).
def test_bool_as_price_rejected() -> None:
    with pytest.raises(ValueError, match="price"):
        SchwabExecutionLeg(**_valid_kwargs(price=True))


# Test 7 — bool-as-quantity rejected.
def test_bool_as_quantity_rejected() -> None:
    with pytest.raises(ValueError, match="quantity"):
        SchwabExecutionLeg(**_valid_kwargs(quantity=True))


# Test 8 — empty time string rejected.
def test_empty_time_rejected() -> None:
    with pytest.raises(ValueError, match="time"):
        SchwabExecutionLeg(**_valid_kwargs(time=""))


# Test 9 — negative leg_id rejected.
def test_negative_leg_id_rejected() -> None:
    with pytest.raises(ValueError, match="leg_id"):
        SchwabExecutionLeg(**_valid_kwargs(leg_id=-1))


# Test 10 — mismarked_quantity None accepted.
def test_mismarked_quantity_none_accepted() -> None:
    leg = SchwabExecutionLeg(**_valid_kwargs(mismarked_quantity=None))
    assert leg.mismarked_quantity is None


# Test 11 — mismarked_quantity negative rejected.
def test_mismarked_quantity_negative_rejected() -> None:
    with pytest.raises(ValueError, match="mismarked_quantity"):
        SchwabExecutionLeg(**_valid_kwargs(mismarked_quantity=-1.0))


# Test 12 — frozen dataclass refuses attribute reassignment.
def test_frozen_dataclass_refuses_reassignment() -> None:
    leg = SchwabExecutionLeg(**_valid_kwargs())
    with pytest.raises(dataclasses.FrozenInstanceError):
        leg.price = 99.99  # type: ignore[misc]


# Bonus — instrument_id None accepted (per spec §4.1 nullability LOCK).
def test_instrument_id_none_accepted() -> None:
    leg = SchwabExecutionLeg(**_valid_kwargs(instrument_id=None))
    assert leg.instrument_id is None


# Bonus — bool-as-leg_id rejected.
def test_bool_as_leg_id_rejected() -> None:
    with pytest.raises(ValueError, match="leg_id"):
        SchwabExecutionLeg(**_valid_kwargs(leg_id=True))


# Bonus — math.isfinite() guards mismarked_quantity too.
def test_mismarked_quantity_non_finite_rejected() -> None:
    with pytest.raises(ValueError, match="mismarked_quantity"):
        SchwabExecutionLeg(
            **_valid_kwargs(mismarked_quantity=float("nan")),
        )
    # Sanity: math.isfinite on the underlying check.
    assert not math.isfinite(float("nan"))
