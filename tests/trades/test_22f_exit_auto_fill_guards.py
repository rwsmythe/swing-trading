"""22-F service-level guards on EXIT auto-fill (`resolve_exit_auto_fill`).

T-A1 (C1-01, RD F-F1 (a), CHARC F-F2 (3)): a `SchwabSchemaParityError` from
the orders fetch lands on the existing ``kind="error"`` / ``operator_typed``
result (A1-b).

The fixtures are the sibling module's (`tests/trades/test_exit_auto_fill.py`);
every drive through ``patch_get_orders`` asserts the recorder saw >= 1 call
(the did-it-fire rule, 22-F plan section 0.4).
"""
from __future__ import annotations

import pytest

from swing.integrations.schwab.client import SchwabSchemaParityError
from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)
from swing.trades.exit_auto_fill import _build_candidate, resolve_exit_auto_fill
from tests._22f_proxies import CountingWrapper
from tests.trades.test_exit_auto_fill import (  # noqa: F401 -- fixtures
    _make_cfg,
    _make_sell_order,
    conn,
    fake_now,
    patch_client_factory,
    patch_credentials,
    patch_get_orders,
    patch_live_state,
)


def test_A1b_parity_on_orders_fetch_degrades_to_error_kind(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """A1-b. PRE-FIX the parity error escapes `exit_auto_fill.py:759`'s
    tuple; POST-FIX it returns ``kind="error"`` / ``operator_typed``."""
    patch_get_orders.state["raises"] = SchwabSchemaParityError(
        "<orders: missing required key 'x'>")
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=_make_cfg(environment="production"), conn=conn, now=fake_now,
    )
    assert len(patch_get_orders) >= 1  # did-it-fire
    assert result.kind == "error"
    assert result.fill_origin == "operator_typed"
    assert result.exit_price is None
    assert "SchwabSchemaParityError" in (result.advisory_text or "")


# ---------------------------------------------------------------------------
# T-A3 -- C1-25, BANK-3: `int(quantity)` at `_build_candidate`'s reason chain
# on a non-finite quantity (RD 2).  inf arrives on validated models ONLY by
# leg-sum overflow (A3-a'); the inf / nan rows A3-a / A3-b are GUARD TESTS
# planted at the resolver's return.
# ---------------------------------------------------------------------------

_T = "2026-05-19T15:30:00.000Z"


def _two_huge_legs_sell(order_id: str = "order-AAPL-huge-sell"):
    """A3-a' MECHANISM: two VALID legs of ``1e308`` (each finite, > 0,
    `models.py:216`); the SUM overflows to inf at `_resolve_match_quantity`.
    The order-level ``quantity`` must be finite (`models.py:336`); the
    resolver never reads it when legs are present."""
    legs = [
        SchwabExecutionLeg(leg_id=i, price=10.0, quantity=1e308,
                           mismarked_quantity=None, instrument_id=12345,
                           time=_T)
        for i in (1, 2)
    ]
    return SchwabOrderResponse(
        order_id=order_id, status="FILLED", enter_time=_T,
        instrument_symbol="AAPL", instruction="SELL", quantity=1e308,
        order_type="LIMIT", price=10.0, executions=legs,
    )


def _plant_exit_resolver(monkeypatch, value: float) -> CountingWrapper:
    """GUARD-TEST plant at the resolver's RETURN (not a claim the broker
    delivers it).  Target: `swing.trades.exit_auto_fill._resolve_match_
    quantity`, bound by the module-level import and resolved per call inside
    `_build_candidate`."""
    wrapper = CountingWrapper(lambda so: value)
    monkeypatch.setattr(
        "swing.trades.exit_auto_fill._resolve_match_quantity", wrapper)
    return wrapper


@pytest.mark.parametrize("planted", [float("inf"), float("nan")],
                         ids=["A3a_inf", "A3b_nan"])
def test_A3a_A3b_guard_non_finite_resolver_return_is_a_refusal_reason(
        planted, monkeypatch):
    """A3-a (inf) / A3-b (nan) GUARD TESTS (unreachable on validated
    models).  PRE-FIX: `int(inf)` -> `OverflowError`, `int(nan)` ->
    `ValueError`, raised out of `_build_candidate`.  POST-FIX: the refusal
    reasons are exactly ``("non_finite_quantity",)`` -- the fixture supplies
    a usable date and price, and A3-f: neither ``no_quantity`` nor
    ``sub_one_share_quantity`` is appended (mutual exclusion kept)."""
    plant = _plant_exit_resolver(monkeypatch, planted)
    cand, _outcome, match_quantity, reasons = _build_candidate(
        _make_sell_order(price=10.0, quantity=3.0, enter_time=_T))
    assert plant.calls >= 1  # did-it-fire
    assert cand is None and match_quantity is None
    assert reasons == ("non_finite_quantity",)


def test_A3a_prime_mechanism_two_huge_legs_is_a_refusal_reason():
    """A3-a' MECHANISM: two valid ``1e308`` legs.  PRE-FIX:
    `OverflowError`.  POST-FIX: ``("non_finite_quantity",)`` (A3-f: the
    other two quantity tokens absent)."""
    cand, _outcome, _mq, reasons = _build_candidate(_two_huge_legs_sell())
    assert cand is None
    assert reasons == ("non_finite_quantity",)


def test_A3a_prime_service_path_refuses_not_raises(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """A3-a' through `resolve_exit_auto_fill`: PRE-FIX the `OverflowError`
    escapes the resolver; POST-FIX every match refused -> ``kind="empty"``
    whose advisory names the new reason text."""
    patch_get_orders.state["orders"] = [_two_huge_legs_sell()]
    result = resolve_exit_auto_fill(
        trade_id=42, ticker="AAPL", entry_date="2026-05-15",
        cfg=_make_cfg(environment="production"), conn=conn, now=fake_now,
    )
    assert len(patch_get_orders) >= 1  # did-it-fire
    assert result.kind == "empty"
    assert "a non-finite execution quantity from the broker" in (
        result.advisory_text or "")


def test_A3c_huge_finite_quantity_is_not_refused_by_this_guard():
    """A3-c: ``1e18`` is FINITE -> a candidate with ``quantity == 10**18``
    on BOTH trees; this guard refuses non-finite values only."""
    cand, _outcome, _mq, reasons = _build_candidate(
        _make_sell_order(price=10.0, quantity=1e18, enter_time=_T))
    assert reasons == ()
    assert cand is not None and cand.quantity == 10**18


def test_A3d_sub_one_share_unchanged():
    """A3-d: ``0.9`` (one fractional leg) -> ``("sub_one_share_quantity",)``
    on BOTH trees."""
    cand, _outcome, _mq, reasons = _build_candidate(
        _make_sell_order(price=10.0, quantity=0.9, enter_time=_T))
    assert cand is None
    assert reasons == ("sub_one_share_quantity",)
