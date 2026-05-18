"""T-1.3 — Pass-2 candidate-dict emit-shape extension.

Tests that ``_orders_to_classifier_payload`` emits the ``executions`` key
with the 3-branch semantics (None / [] / [legs...]) per plan §A T-1.3 +
F24 dict-branch normalization (Codex R1 Major #4 LOCK).

The classifier (T-1.1 predicate) reads
``so.get('executions')`` from each candidate-dict in source_payload; this
seam is what makes execution-grain data flow from the backfill-fetched
``SchwabOrderResponse`` instances into the classifier's multi-leg
auto-redirect path.
"""

from __future__ import annotations

import pytest

from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)
from swing.trades.reconciliation_backfill import _orders_to_classifier_payload


def _make_order(
    *,
    executions: list[SchwabExecutionLeg] | None = None,
    order_id: str = "ORDER-1",
    instrument_symbol: str = "CVGI",
    instruction: str = "BUY",
    quantity: float = 100.0,
    order_type: str = "LIMIT",
    price: float | None = 5.30,
) -> SchwabOrderResponse:
    """Construct a minimal valid SchwabOrderResponse for testing."""
    return SchwabOrderResponse(
        order_id=order_id,
        status="FILLED",
        enter_time="2026-04-15T13:00:00",
        instrument_symbol=instrument_symbol,
        instruction=instruction,
        quantity=quantity,
        order_type=order_type,
        price=price,
        executions=executions,
    )


def _make_leg(
    *,
    leg_id: int = 1,
    price: float = 5.2244,
    quantity: float = 50.0,
    time: str = "2026-04-15T13:00:01",
) -> SchwabExecutionLeg:
    """Construct a minimal valid SchwabExecutionLeg for testing."""
    return SchwabExecutionLeg(
        leg_id=leg_id,
        price=price,
        quantity=quantity,
        mismarked_quantity=None,
        instrument_id=None,
        time=time,
    )


def test_orders_to_classifier_payload_includes_executions_key_when_present() -> None:
    """Non-dict branch + executions present: emit list-of-plain-dicts with
    leg_id/price/quantity/time keys per plan §A T-1.3."""
    leg1 = _make_leg(leg_id=1, price=5.2244, quantity=50.0, time="2026-04-15T13:00:01")
    leg2 = _make_leg(leg_id=2, price=5.2300, quantity=50.0, time="2026-04-15T13:00:02")
    order = _make_order(executions=[leg1, leg2])

    out = _orders_to_classifier_payload([order])

    assert len(out) == 1
    assert "executions" in out[0]
    assert isinstance(out[0]["executions"], list)
    assert len(out[0]["executions"]) == 2
    # Each leg converted to plain dict with the 4 plan-prescribed keys.
    for leg_dict in out[0]["executions"]:
        assert isinstance(leg_dict, dict)
        assert set(leg_dict.keys()) == {"leg_id", "price", "quantity", "time"}
    assert out[0]["executions"][0]["leg_id"] == 1
    assert out[0]["executions"][0]["price"] == 5.2244
    assert out[0]["executions"][0]["quantity"] == 50.0
    assert out[0]["executions"][0]["time"] == "2026-04-15T13:00:01"
    assert out[0]["executions"][1]["leg_id"] == 2


def test_orders_to_classifier_payload_executions_key_is_none_when_absent() -> None:
    """Non-dict branch + executions=None: emit ``'executions': None``
    (legacy V1 mapper path / sandbox responses)."""
    order = _make_order(executions=None)

    out = _orders_to_classifier_payload([order])

    assert len(out) == 1
    assert "executions" in out[0]
    assert out[0]["executions"] is None


def test_orders_to_classifier_payload_executions_key_is_empty_list_when_explicitly_empty() -> None:
    """Non-dict branch + executions=[] (explicit empty): emit
    ``'executions': []`` — canary observability path per T-1.11 (broker
    confirmed no executions despite populated activityType row).

    Separate from the None path which signals data-unavailable rather
    than data-confirmed-empty.
    """
    order = _make_order(executions=[])

    out = _orders_to_classifier_payload([order])

    assert len(out) == 1
    assert "executions" in out[0]
    assert out[0]["executions"] == []
    # Distinguishable from None branch (this test would fail if the
    # function collapsed [] → None or [] → missing-key).
    assert out[0]["executions"] is not None


def test_orders_to_classifier_payload_dict_input_with_executions_key_passes_through_unchanged() -> None:
    """Dict branch + executions key already present: pass through verbatim
    (cassette/replay path that already carries execution-grain data)."""
    pre_converted = {
        "order_id": "ORDER-X",
        "status": "FILLED",
        "enter_time": "2026-04-15T13:00:00",
        "instrument_symbol": "LION",
        "instruction": "BUY",
        "quantity": 100.0,
        "order_type": "LIMIT",
        "price": 12.75,
        "executions": [
            {"leg_id": 1, "price": 12.6999, "quantity": 100.0, "time": "T1"},
        ],
    }

    out = _orders_to_classifier_payload([pre_converted])

    assert len(out) == 1
    # Passthrough — same object identity or equal contents (current impl
    # appends ``o`` directly when key is present).
    assert out[0] == pre_converted
    assert out[0]["executions"] == [
        {"leg_id": 1, "price": 12.6999, "quantity": 100.0, "time": "T1"},
    ]


def test_orders_to_classifier_payload_dict_input_without_executions_key_normalized_to_none() -> None:
    """F24 LOCK (Codex R1 Major #4): pre-converted dict lacking
    ``executions`` key → output dict has ``'executions': None`` injected.

    Cassette/replay fixtures pre-Phase-12.5 #1 do NOT include
    ``executions`` keys. Without normalization, dict-branch +
    non-dict-branch outputs diverge on shape contract. F24 invariant:
    every output dict MUST carry an ``executions`` key.
    """
    pre_converted = {
        "order_id": "ORDER-LEGACY",
        "status": "FILLED",
        "enter_time": "2026-04-15T13:00:00",
        "instrument_symbol": "DHC",
        "instruction": "BUY",
        "quantity": 100.0,
        "order_type": "LIMIT",
        "price": 7.62,
    }

    out = _orders_to_classifier_payload([pre_converted])

    assert len(out) == 1
    assert "executions" in out[0]
    assert out[0]["executions"] is None
    # All other keys preserved.
    for k, v in pre_converted.items():
        assert out[0][k] == v


def test_orders_to_classifier_payload_other_keys_preserved() -> None:
    """All 8 pre-existing emitted keys (order_id, status, enter_time,
    instrument_symbol, instruction, quantity, order_type, price) still
    emitted alongside the new ``executions`` key in the non-dict branch.
    """
    order = _make_order(
        order_id="ORDER-PRES",
        instrument_symbol="VSAT",
        instruction="SELL",
        quantity=42.0,
        order_type="LIMIT",
        price=63.23,
        executions=[_make_leg()],
    )

    out = _orders_to_classifier_payload([order])

    assert len(out) == 1
    expected_pre_existing_keys = {
        "order_id",
        "status",
        "enter_time",
        "instrument_symbol",
        "instruction",
        "quantity",
        "order_type",
        "price",
    }
    actual_keys = set(out[0].keys())
    # All pre-existing keys present.
    assert expected_pre_existing_keys.issubset(actual_keys)
    # Plus the new executions key (T-1.3 addition).
    assert "executions" in actual_keys
    # Pre-existing values preserved verbatim.
    assert out[0]["order_id"] == "ORDER-PRES"
    assert out[0]["status"] == "FILLED"
    assert out[0]["enter_time"] == "2026-04-15T13:00:00"
    assert out[0]["instrument_symbol"] == "VSAT"
    assert out[0]["instruction"] == "SELL"
    assert out[0]["quantity"] == 42.0
    assert out[0]["order_type"] == "LIMIT"
    assert out[0]["price"] == 63.23


def test_orders_to_classifier_payload_multi_order_mix_dict_and_dataclass() -> None:
    """Mixed input list (dict + dataclass + dict-without-executions) →
    all three normalized to dict-shape with executions key present.

    Defense-in-depth regression check that F24 holds across a
    heterogeneous list (not just a single-element list as the prior tests
    exercise individually).
    """
    leg = _make_leg()
    order = _make_order(order_id="ORDER-DC", executions=[leg])
    dict_with_exec = {
        "order_id": "ORDER-D1",
        "status": "FILLED",
        "enter_time": "2026-04-15T13:00:00",
        "instrument_symbol": "YOU",
        "instruction": "BUY",
        "quantity": 10.0,
        "order_type": "LIMIT",
        "price": 54.06,
        "executions": [{"leg_id": 1, "price": 54.0, "quantity": 10.0, "time": "T"}],
    }
    dict_without_exec = {
        "order_id": "ORDER-D2",
        "status": "FILLED",
        "enter_time": "2026-04-15T13:00:00",
        "instrument_symbol": "LAR",
        "instruction": "BUY",
        "quantity": 5.0,
        "order_type": "LIMIT",
        "price": 7.00,
    }

    out = _orders_to_classifier_payload([order, dict_with_exec, dict_without_exec])

    assert len(out) == 3
    # F24: every output dict has executions key.
    for entry in out:
        assert "executions" in entry
    # Dataclass branch: list-of-plain-dict.
    assert isinstance(out[0]["executions"], list)
    assert out[0]["executions"][0]["leg_id"] == 1
    # Dict branch with executions: passthrough.
    assert out[1]["executions"] == dict_with_exec["executions"]
    # Dict branch without executions: normalized to None.
    assert out[2]["executions"] is None
