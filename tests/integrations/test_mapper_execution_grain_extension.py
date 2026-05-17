"""Tests for `map_orders_to_fill_candidates` execution-grain extension (T-1.3).

Per plan §A.1.3 + spec §4.3 + §5.3 mapper-coherence rule. 14 discriminating
cases covering defensive parsing + tri-valued executions semantics + coherence
check (`sum(legs.quantity) == filledQuantity` → preserve else collapse).
"""
from __future__ import annotations

import logging

from swing.integrations.schwab.mappers import map_orders_to_fill_candidates


def _base_order(**overrides):
    """Minimum valid Schwab order dict for mapper consumption."""
    base = {
        "orderId": "ORD-100",
        "status": "FILLED",
        "enteredTime": "2026-05-15T14:00:00.000Z",
        "orderType": "LIMIT",
        "price": 5.30,
        "filledQuantity": 100,
        "orderLegCollection": [
            {
                "instruction": "BUY",
                "quantity": 100,
                "instrument": {"symbol": "AAA"},
            },
        ],
    }
    base.update(overrides)
    return base


def _exec_activity(legs):
    """Build an orderActivityCollection EXECUTION activity wrapping `legs`.

    Tolerates non-dict legs in the input list (test fixtures inject these
    to exercise defensive parsing) — sum only over dict legs.
    """
    total = sum(
        leg.get("quantity", 0) for leg in legs if isinstance(leg, dict)
    )
    return {
        "activityType": "EXECUTION",
        "executionType": "FILL",
        "quantity": total,
        "executionLegs": legs,
    }


def _leg(*, leg_id=1, price=5.2244, quantity=100,
         mismarked_quantity=0, instrument_id=12345,
         time="2026-05-15T14:30:00.000Z"):
    return {
        "legId": leg_id,
        "price": price,
        "quantity": quantity,
        "mismarkedQuantity": mismarked_quantity,
        "instrumentId": instrument_id,
        "time": time,
    }


# Test 1 — V1 backward compat: no orderActivityCollection → executions=None.
def test_no_order_activity_collection_executions_none() -> None:
    out = map_orders_to_fill_candidates([_base_order()])
    assert len(out) == 1
    assert out[0].executions is None


# Test 2 — empty orderActivityCollection ([]) → executions=None.
def test_empty_order_activity_collection_executions_none() -> None:
    out = map_orders_to_fill_candidates([
        _base_order(orderActivityCollection=[]),
    ])
    assert out[0].executions is None


# Test 3 — non-EXECUTION activityType skipped silently; all filtered → None.
def test_only_non_execution_activities_executions_none(
    caplog,
) -> None:
    out = map_orders_to_fill_candidates([
        _base_order(orderActivityCollection=[
            {"activityType": "ORDER_ACTION", "executionLegs": [_leg()]},
        ]),
    ])
    assert out[0].executions is None


# Test 4 — single EXECUTION + single leg → 1-element list.
def test_single_execution_single_leg() -> None:
    legs = [_leg()]
    out = map_orders_to_fill_candidates([
        _base_order(orderActivityCollection=[_exec_activity(legs)]),
    ])
    assert out[0].executions is not None
    assert len(out[0].executions) == 1
    assert out[0].executions[0].leg_id == 1
    assert out[0].executions[0].price == 5.2244
    assert out[0].executions[0].quantity == 100


# Test 5 — multi-leg preserves leg order.
def test_multi_leg_preserves_order() -> None:
    legs = [
        _leg(leg_id=1, price=10.00, quantity=50),
        _leg(leg_id=2, price=10.20, quantity=50),
    ]
    out = map_orders_to_fill_candidates([
        _base_order(filledQuantity=100,
                    orderActivityCollection=[_exec_activity(legs)]),
    ])
    assert out[0].executions is not None
    assert [leg.leg_id for leg in out[0].executions] == [1, 2]
    assert [leg.price for leg in out[0].executions] == [10.00, 10.20]


# Test 6 — coherence check legitimate partial fill preserved.
def test_coherence_check_partial_fill_preserved() -> None:
    """`order.quantity=200, filledQuantity=100, legs=[{qty:100}]` →
    executions preserved (legs sum matches filledQuantity)."""
    base = _base_order(filledQuantity=100)
    base["orderLegCollection"][0]["quantity"] = 200  # ordered 200
    legs = [_leg(quantity=100)]
    base["orderActivityCollection"] = [_exec_activity(legs)]
    out = map_orders_to_fill_candidates([base])
    assert out[0].quantity == 200.0
    assert out[0].executions is not None
    assert len(out[0].executions) == 1
    assert out[0].executions[0].quantity == 100


# Test 7 — coherence check malformed legs collapses to None + warning.
def test_coherence_check_malformed_collapses_to_none(caplog) -> None:
    """`order.quantity=100, filledQuantity=100, legs=[{qty:60},{qty:50}]` →
    executions=None + WARNING log (sum 110 ≠ filledQuantity 100)."""
    legs = [_leg(leg_id=1, quantity=60), _leg(leg_id=2, quantity=50)]
    base = _base_order(filledQuantity=100,
                       orderActivityCollection=[_exec_activity(legs)])
    with caplog.at_level(logging.WARNING):
        out = map_orders_to_fill_candidates([base])
    assert out[0].executions is None
    # Coherence warning fired.
    assert any(
        "coherence" in r.getMessage().lower() or "filledquantity" in r.getMessage().lower()
        for r in caplog.records
    )


# Test 8 — defensive parsing: non-dict activity entry skipped + warn.
def test_non_dict_activity_skipped(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        out = map_orders_to_fill_candidates([
            _base_order(orderActivityCollection=[
                "not-a-dict",  # type: ignore[list-item]
                _exec_activity([_leg()]),
            ]),
        ])
    # The valid activity still surfaces legs (the non-dict one skipped).
    assert out[0].executions is not None
    assert len(out[0].executions) == 1


# Test 9 — defensive parsing: non-dict leg skipped + warn.
def test_non_dict_leg_skipped(caplog) -> None:
    legs_with_garbage = [
        "not-a-dict",  # type: ignore[list-item]
        _leg(),
    ]
    with caplog.at_level(logging.WARNING):
        out = map_orders_to_fill_candidates([
            _base_order(
                filledQuantity=100,
                orderActivityCollection=[_exec_activity(legs_with_garbage)],
            ),
        ])
    # The valid leg surfaces.
    assert out[0].executions is not None
    assert len(out[0].executions) == 1


# Test 10 — leg fails dataclass validator → drop leg + warn + preserve rest.
def test_leg_validator_failure_drops_leg(caplog) -> None:
    legs = [
        _leg(leg_id=1, price=-1.0, quantity=50),  # validator rejects
        _leg(leg_id=2, price=10.20, quantity=50),  # valid
    ]
    # filledQuantity reflects only the surviving leg (50) post-drop:
    base = _base_order(
        filledQuantity=50,
        orderActivityCollection=[_exec_activity(legs)],
    )
    with caplog.at_level(logging.WARNING):
        out = map_orders_to_fill_candidates([base])
    # Surviving leg present; coherence check passes (50 == 50).
    assert out[0].executions is not None
    assert len(out[0].executions) == 1
    assert out[0].executions[0].leg_id == 2


# Test 11 — multiple EXECUTION activities aggregate legs.
def test_multiple_execution_activities_aggregate() -> None:
    legs1 = [_leg(leg_id=1, price=10.00, quantity=30)]
    legs2 = [_leg(leg_id=2, price=10.10, quantity=70)]
    base = _base_order(
        filledQuantity=100,
        orderActivityCollection=[
            _exec_activity(legs1),
            _exec_activity(legs2),
        ],
    )
    out = map_orders_to_fill_candidates([base])
    assert out[0].executions is not None
    assert len(out[0].executions) == 2
    assert [leg.leg_id for leg in out[0].executions] == [1, 2]


# Test 12 — orderActivityCollection is non-list (e.g., string) → None.
def test_non_list_order_activity_collection_executions_none(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        out = map_orders_to_fill_candidates([
            _base_order(orderActivityCollection="not-a-list"),
        ])
    assert out[0].executions is None


# Test 13 — SchwabOrderResponse.price field preserved unchanged from V1.
def test_price_field_preserved_unchanged() -> None:
    """Load-bearing for backward compat — comparator's Path B sentinel +
    stop_mismatch path consume `so.price`."""
    out = map_orders_to_fill_candidates([_base_order(price=5.30)])
    assert out[0].price == 5.30
    # Stop trigger fall-back.
    out2 = map_orders_to_fill_candidates([
        _base_order(price=None, orderType="STOP", stopPrice=5.00),
    ])
    assert out2[0].price == 5.00


# Test 14 — NO filledQuantity field → permissive (treat legs as authoritative).
def test_no_filled_quantity_permissive() -> None:
    legs = [_leg(leg_id=1, quantity=50), _leg(leg_id=2, quantity=50)]
    base = _base_order(orderActivityCollection=[_exec_activity(legs)])
    del base["filledQuantity"]
    out = map_orders_to_fill_candidates([base])
    # No coherence check fires → legs preserved.
    assert out[0].executions is not None
    assert len(out[0].executions) == 2


# Test 15 — Codex R1 Major #2: bool-as-number raw field rejected at mapper
# layer (pre-coercion) so the dataclass validator contract stays honest.
def test_bool_as_number_leg_field_rejected_pre_coercion(caplog) -> None:
    """Raw JSON `{"price": true}` would coerce to `float(True)=1.0` which
    would slip past `SchwabExecutionLeg.__post_init__`'s `isinstance(x, bool)`
    rejection. T-1.3 mapper rejects bool BEFORE coercion (defense-in-depth
    mirroring the dataclass contract end-to-end)."""
    legs_with_bool_price = [
        {"legId": 1, "price": True, "quantity": 100,
         "mismarkedQuantity": 0, "instrumentId": None,
         "time": "2026-05-15T14:30:00.000Z"},
    ]
    base = _base_order(
        filledQuantity=100,
        orderActivityCollection=[_exec_activity(legs_with_bool_price)],
    )
    with caplog.at_level(logging.WARNING):
        out = map_orders_to_fill_candidates([base])
    # Bool-leg dropped → executions=None (coherence-check on filledQuantity=100
    # with empty collected legs → return None per `if not collected`).
    assert out[0].executions is None
    assert any(
        "bool-as-number" in r.getMessage().lower()
        for r in caplog.records
    )


# Test 16 — bool-as-quantity also rejected.
def test_bool_as_quantity_leg_field_rejected_pre_coercion() -> None:
    legs = [
        {"legId": 1, "price": 5.0, "quantity": True,  # noqa
         "mismarkedQuantity": 0, "instrumentId": None,
         "time": "2026-05-15T14:30:00.000Z"},
    ]
    base = _base_order(
        filledQuantity=100,
        orderActivityCollection=[_exec_activity(legs)],
    )
    out = map_orders_to_fill_candidates([base])
    assert out[0].executions is None  # leg dropped → empty collected → None


# Test 17 — Codex R2 Major #3: non-str / empty time rejected pre-coercion.
def test_non_str_time_leg_field_rejected_pre_coercion(caplog) -> None:
    """`str(None) == "None"` and `str(123) == "123"` would slip past the
    dataclass validator's `isinstance(self.time, str) and self.time` check.
    Mapper rejects non-str time BEFORE coercion (defense-in-depth)."""
    legs = [
        {"legId": 1, "price": 5.0, "quantity": 100,
         "mismarkedQuantity": 0, "instrumentId": None,
         "time": None},  # would coerce to "None" via str()
    ]
    base = _base_order(
        filledQuantity=100,
        orderActivityCollection=[_exec_activity(legs)],
    )
    with caplog.at_level(logging.WARNING):
        out = map_orders_to_fill_candidates([base])
    assert out[0].executions is None
    assert any(
        "non-str" in r.getMessage().lower() or "time" in r.getMessage().lower()
        for r in caplog.records
    )


# Test 18 — empty-str time also rejected.
def test_empty_str_time_leg_field_rejected_pre_coercion() -> None:
    legs = [
        {"legId": 1, "price": 5.0, "quantity": 100,
         "mismarkedQuantity": 0, "instrumentId": None,
         "time": ""},
    ]
    base = _base_order(
        filledQuantity=100,
        orderActivityCollection=[_exec_activity(legs)],
    )
    out = map_orders_to_fill_candidates([base])
    assert out[0].executions is None
