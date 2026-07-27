"""stop_price is ADDITIVE: `price` semantics are unchanged."""
from __future__ import annotations

from swing.integrations.schwab.mappers import map_orders_to_fill_candidates


def _order(**over):
    base = {
        "orderId": 1, "status": "WORKING", "enteredTime": "2026-07-20T13:30:00Z",
        "orderType": "STOP_LIMIT", "price": 18.89, "stopPrice": 18.34,
        "orderLegCollection": [{
            "instruction": "BUY", "quantity": 3,
            "instrument": {"symbol": "FTRE"}}],
    }
    base.update(over)
    return base


def test_stop_limit_carries_both_prices():
    (o,) = map_orders_to_fill_candidates([_order()])
    assert o.price == 18.89       # the LIMIT -- unchanged behavior
    assert o.stop_price == 18.34  # NEW


def test_plain_stop_order_price_still_falls_back_to_stop_price():
    """REGRESSION: reconciliation depends on `price` falling back to stopPrice
    when `price` is absent. That must not change."""
    (o,) = map_orders_to_fill_candidates(
        [_order(orderType="STOP", price=None)])
    assert o.price == 18.34
    assert o.stop_price == 18.34


def test_limit_order_has_no_stop_price():
    (o,) = map_orders_to_fill_candidates(
        [_order(orderType="LIMIT", stopPrice=None)])
    assert o.price == 18.89
    assert o.stop_price is None


def test_default_is_none_for_positional_construction():
    """Tail placement preserves the 8-positional backward compat the
    `executions` field established."""
    from swing.integrations.schwab.models import SchwabOrderResponse
    o = SchwabOrderResponse("1", "WORKING", "", "FTRE", "BUY", 3.0, "STOP", 18.34)
    assert o.stop_price is None
    assert o.executions is None


def test_a_non_finite_stop_price_is_rejected_at_the_construction_barrier():
    """`Literal`/type hints are not runtime-enforced; the validator is. Mirrors
    the existing `price` validator exactly."""
    import pytest

    from swing.integrations.schwab.models import SchwabOrderResponse
    for bad in (float("nan"), float("inf"), -1.0):
        with pytest.raises(ValueError, match="stop_price"):
            SchwabOrderResponse(
                "1", "WORKING", "", "FTRE", "BUY", 3.0, "STOP", 18.34,
                stop_price=bad)
