"""Sub-bundle 1.5 Codex R1 M#3+M#4 -- public-path integration coverage.

Existing regression tests at:
  - tests/integrations/test_schwab_mapper_filled_quantity_zero_early_exit.py
  - tests/integrations/test_schwab_mapper_production_shape_regression.py
  - tests/integrations/test_schwab_mapper_anomalous_shape_canary.py

exercise the PRIVATE `_extract_executions_from_order_raw` helper directly,
and plant minimal order envelopes carrying only the keys the helper itself
reads (orderActivityCollection + filledQuantity).

Codex R1 M#3 + M#4 noted the gap: (a) fixtures aren't byte-for-byte
production shapes (they omit orderLegCollection / enteredTime / etc.); (b)
no coverage exercises `map_orders_to_fill_candidates` (the PUBLIC entry
point that pipeline / CLI / reconciliation consume).

This module closes both gaps with two integration tests that:
  1. Construct order envelopes with the FULLER production-shape key set
     (orderId, status, orderType, enteredTime, orderLegCollection with
     instruction/quantity/instrument, price, filledQuantity,
     orderActivityCollection.executionLegs) -- mirroring the shape
     surfaced at T-1.5.1 diagnostic against operator's production account.
  2. Call `map_orders_to_fill_candidates(raw_orders)` (the PUBLIC entry
     point) and assert end-to-end:
     - FILLED LIMIT order -> SchwabOrderResponse.executions populated
       with one SchwabExecutionLeg carrying the actual execution price.
     - CANCELED STOP placeholder order -> SchwabOrderResponse.executions
       is None (early-exit gate fired; mapper still emitted the order
       envelope per existing V1 contract; only executions field collapsed).
     - REPLACED STOP placeholder order -> same as CANCELED case.

Sanitization: account-level identifiers omitted (no accountNumber /
accountHash / hashValue in the envelopes); instrumentId / leg-level
prices retained because they're shape-illustrative.
"""
from __future__ import annotations

from swing.integrations.schwab.mappers import map_orders_to_fill_candidates
from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)


def _filled_limit_order_envelope() -> dict:
    """Production-shape FILLED LIMIT order envelope.

    Mirrors the actual shape returned by Schwab `Client.account_orders(...)`
    in operator's T-1.5.1 diagnostic sample (Order id=1006387238791 CVGI
    BUY @ $12.6999). Includes top-level keys beyond what the helper itself
    reads (orderLegCollection, enteredTime, price, quantity) to validate
    the public-path integration.
    """
    return {
        "session": "NORMAL",
        "duration": "DAY",
        "orderType": "LIMIT",
        "complexOrderStrategyType": "NONE",
        "quantity": 18.0,
        "filledQuantity": 18.0,
        "remainingQuantity": 0.0,
        "requestedDestination": "AUTO",
        "destinationLinkName": "AUTO",
        "price": 12.75,  # ORDER-grain LIMIT price (V1 mapper reads this)
        "orderLegCollection": [
            {
                "orderLegType": "EQUITY",
                "legId": 1,
                "instrument": {
                    "assetType": "EQUITY",
                    "cusip": "000000000",
                    "symbol": "CVGI",
                    "instrumentId": 234814458,
                },
                "instruction": "BUY",
                "positionEffect": "OPENING",
                "quantity": 18.0,
            },
        ],
        "orderStrategyType": "SINGLE",
        "orderId": 1006387238791,
        "cancelable": False,
        "editable": False,
        "status": "FILLED",
        "enteredTime": "2026-05-15T18:55:30+0000",
        "closeTime": "2026-05-15T18:55:46+0000",
        "tag": "API_TOS:SCHWAB",
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionType": "FILL",
                "quantity": 18.0,
                "orderRemainingQuantity": 0.0,
                "executionLegs": [
                    {
                        "instrumentId": 234814458,
                        "legId": 1,
                        "mismarkedQuantity": 0.0,
                        "price": 12.6999,  # EXECUTION-grain price
                        "quantity": 18.0,
                        "time": "2026-05-15T18:55:46+0000",
                    },
                ],
            },
        ],
    }


def _canceled_stop_placeholder_envelope() -> dict:
    """Production-shape CANCELED STOP placeholder order envelope.

    Mirrors operator's T-1.5.1 diagnostic Order id=1006338076032 -- the
    placeholder family that triggered the Sub-bundle 1 validator-drop
    finding (status=CANCELED + orderType=STOP + filledQuantity=0 +
    leg.price=0 sentinel). T-1.5.2 fix early-exits BEFORE iterating legs.
    """
    return {
        "session": "NORMAL",
        "duration": "GOOD_TILL_CANCEL",
        "orderType": "STOP",
        "complexOrderStrategyType": "NONE",
        "quantity": 7.0,
        "filledQuantity": 0.0,
        "remainingQuantity": 7.0,
        "stopPrice": 8.50,
        "requestedDestination": "AUTO",
        "destinationLinkName": "AUTO",
        "orderLegCollection": [
            {
                "orderLegType": "EQUITY",
                "legId": 1,
                "instrument": {
                    "assetType": "EQUITY",
                    "cusip": "000000000",
                    "symbol": "DHC",
                    "instrumentId": 230011483,
                },
                "instruction": "SELL",
                "positionEffect": "CLOSING",
                "quantity": 7.0,
            },
        ],
        "orderStrategyType": "TRIGGER",
        "orderId": 1006338076032,
        "cancelable": True,
        "editable": False,
        "status": "CANCELED",
        "enteredTime": "2026-05-13T16:09:00+0000",
        "closeTime": "2026-05-13T16:09:22+0000",
        "tag": "API_TOS:SCHWAB",
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionType": "CANCEL_REPLACE",
                "quantity": 0.0,
                "orderRemainingQuantity": 7.0,
                "executionLegs": [
                    {
                        "instrumentId": 230011483,
                        "legId": 1,
                        "mismarkedQuantity": 0.0,
                        "price": 0.0,  # placeholder sentinel
                        "quantity": 7.0,
                        "time": "2026-05-13T16:09:22+0000",
                    },
                ],
            },
        ],
    }


def _replaced_stop_placeholder_envelope() -> dict:
    """Production-shape REPLACED STOP placeholder order envelope.

    Mirrors operator's T-1.5.1 diagnostic Order id=1006319961824 -- same
    sentinel family as CANCELED, different terminal status.
    """
    return {
        "session": "NORMAL",
        "duration": "GOOD_TILL_CANCEL",
        "orderType": "STOP",
        "complexOrderStrategyType": "NONE",
        "quantity": 20.0,
        "filledQuantity": 0.0,
        "remainingQuantity": 20.0,
        "stopPrice": 5.10,
        "orderLegCollection": [
            {
                "orderLegType": "EQUITY",
                "legId": 1,
                "instrument": {
                    "assetType": "EQUITY",
                    "cusip": "000000000",
                    "symbol": "LION",
                    "instrumentId": 155643,
                },
                "instruction": "SELL",
                "positionEffect": "CLOSING",
                "quantity": 20.0,
            },
        ],
        "orderStrategyType": "TRIGGER",
        "orderId": 1006319961824,
        "cancelable": False,
        "editable": False,
        "status": "REPLACED",
        "enteredTime": "2026-05-13T07:48:00+0000",
        "closeTime": "2026-05-13T07:49:13+0000",
        "tag": "API_TOS:SCHWAB",
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionType": "CANCEL_REPLACE",
                "quantity": 0.0,
                "orderRemainingQuantity": 20.0,
                "executionLegs": [
                    {
                        "instrumentId": 155643,
                        "legId": 1,
                        "mismarkedQuantity": 0.0,
                        "price": 0.0,
                        "quantity": 20.0,
                        "time": "2026-05-13T07:49:13+0000",
                    },
                ],
            },
        ],
    }


# Test 1 (Major 3+4 BINDING) -- multi-order public-path round-trip.
def test_map_orders_public_path_mixed_production_shapes() -> None:
    """Public-path integration: feed the fuller production envelopes
    (FILLED LIMIT + CANCELED STOP placeholder + REPLACED STOP placeholder)
    through `map_orders_to_fill_candidates` and assert each emerges with
    the expected `SchwabOrderResponse.executions` shape.
    """
    raw_orders = [
        _filled_limit_order_envelope(),
        _canceled_stop_placeholder_envelope(),
        _replaced_stop_placeholder_envelope(),
    ]
    mapped = map_orders_to_fill_candidates(raw_orders)
    # All 3 orders mapped (no order envelopes dropped at the order level).
    assert len(mapped) == 3
    # Each is a SchwabOrderResponse.
    for so in mapped:
        assert isinstance(so, SchwabOrderResponse)

    # FILLED LIMIT case: executions populated with execution-grain price.
    filled = mapped[0]
    assert filled.order_id == "1006387238791"
    assert filled.status == "FILLED"
    assert filled.order_type == "LIMIT"
    assert filled.instruction == "BUY"
    assert filled.instrument_symbol == "CVGI"
    assert filled.quantity == 18.0
    assert filled.price == 12.75  # order-grain LIMIT
    assert filled.executions is not None
    assert len(filled.executions) == 1
    leg = filled.executions[0]
    assert isinstance(leg, SchwabExecutionLeg)
    assert leg.leg_id == 1
    assert leg.price == 12.6999  # execution-grain (the lift)
    assert leg.quantity == 18.0
    assert leg.instrument_id == 234814458
    assert leg.time == "2026-05-15T18:55:46+0000"

    # CANCELED STOP placeholder case: executions is None (early-exit gate
    # fired at the helper). The order envelope itself is still emitted
    # because mapper-level extraction happens after order-shape parsing.
    canceled = mapped[1]
    assert canceled.order_id == "1006338076032"
    assert canceled.status == "CANCELED"
    assert canceled.order_type == "STOP"
    assert canceled.instruction == "SELL"
    assert canceled.instrument_symbol == "DHC"
    assert canceled.quantity == 7.0
    # STOP order: price falls back to stopPrice in mapper.
    assert canceled.price == 8.50
    assert canceled.executions is None

    # REPLACED STOP placeholder case: same shape as CANCELED.
    replaced = mapped[2]
    assert replaced.order_id == "1006319961824"
    assert replaced.status == "REPLACED"
    assert replaced.order_type == "STOP"
    assert replaced.instrument_symbol == "LION"
    assert replaced.quantity == 20.0
    assert replaced.price == 5.10
    assert replaced.executions is None


# Test 2 (Major 3+4 supporting) -- single FILLED LIMIT order isolates the
# positive lift through the public API for downstream consumer pinning.
def test_map_orders_public_path_filled_limit_extracts_execution_grain() -> None:
    """Single-order positive lift through the PUBLIC API. Pins the
    contract that downstream consumers (comparator at
    `swing/trades/schwab_reconciliation.py`) rely on for execution-grain
    price availability.
    """
    raw_orders = [_filled_limit_order_envelope()]
    mapped = map_orders_to_fill_candidates(raw_orders)
    assert len(mapped) == 1
    so = mapped[0]
    assert so.executions is not None
    assert len(so.executions) == 1
    assert so.executions[0].price == 12.6999
    assert so.executions[0].quantity == 18.0
