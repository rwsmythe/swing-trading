"""22-F service-level guards on ENTRY auto-fill (`resolve_entry_auto_fill`).

T-A1 (C1-01, RD F-F1 (a), CHARC F-F2 (3)): a `SchwabSchemaParityError` from
the orders fetch lands on the existing ``kind="error"`` / ``operator_typed``
result, exactly like every `SchwabApiError` sibling (A1-a).

The fixtures are the sibling module's (`tests/trades/test_entry_auto_fill.py`);
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
from swing.trades.entry_auto_fill import resolve_entry_auto_fill
from tests._22f_proxies import CountingWrapper
from tests.trades.test_entry_auto_fill import (  # noqa: F401 -- fixtures
    _make_buy_order,
    _make_cfg,
    conn,
    fake_now,
    patch_client_factory,
    patch_credentials,
    patch_get_orders,
    patch_live_state,
)


def test_A1a_parity_on_orders_fetch_degrades_to_error_kind(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """A1-a. PRE-FIX: `SchwabSchemaParityError` is not in the tuple at
    `entry_auto_fill.py:383` (it is a `_RedactedMessageError`, NOT a
    `SchwabApiError`), so it escapes the resolver.  POST-FIX: the widened
    tuple returns the sibling ``kind="error"`` result."""
    patch_get_orders.state["raises"] = SchwabSchemaParityError(
        "<orders: missing required key 'x'>")
    result = resolve_entry_auto_fill(
        ticker="AAPL", cfg=_make_cfg(environment="production"), conn=conn,
        now=fake_now,
    )
    assert len(patch_get_orders) >= 1  # did-it-fire
    assert result.kind == "error"
    assert result.fill_origin == "operator_typed"
    assert result.entry_price is None
    assert "SchwabSchemaParityError" in (result.advisory_text or "")
    assert "auto-fill unavailable" in (result.advisory_text or "")


# ---------------------------------------------------------------------------
# T-A2 -- C1-27, the entry twin of BANK-3 (RD 3 as superseded at the R1 gate;
# the A2-b / A2-c drives AS RULED by RD at STOP-1, exec ledger).
# ---------------------------------------------------------------------------

_NON_FINITE = "non-finite quantity"
_SUB_ONE = "below one whole share"
_NO_PRICE = "lacks execution-grain price"


def _two_huge_legs_order() -> SchwabOrderResponse:
    """A2-a' MECHANISM: two VALID legs of ``1e308`` (each finite and > 0,
    `models.py:216`); their SUM overflows to ``inf`` at
    `_resolve_match_quantity`.  The order-level ``quantity`` must be finite
    (`models.py:336`), so it carries one leg's size -- the resolver never
    reads it when legs are present."""
    t = "2026-05-19T14:30:00.000Z"
    legs = [
        SchwabExecutionLeg(leg_id=i, price=10.0, quantity=1e308,
                           mismarked_quantity=None, instrument_id=12345,
                           time=t)
        for i in (1, 2)
    ]
    return SchwabOrderResponse(
        order_id="order-AAPL-huge", status="FILLED", enter_time=t,
        instrument_symbol="AAPL", instruction="BUY", quantity=1e308,
        order_type="LIMIT", price=10.0, executions=legs,
    )


def _no_legs_order(quantity: float) -> SchwabOrderResponse:
    """A FILLED order with ``executions=None`` -- the ``so.quantity``
    fallback in `_resolve_match_quantity`."""
    return SchwabOrderResponse(
        order_id=f"order-AAPL-nolegs-{quantity}", status="FILLED",
        enter_time="2026-05-19T14:30:00.000Z", instrument_symbol="AAPL",
        instruction="BUY", quantity=quantity, order_type="LIMIT",
        price=10.0, executions=None,
    )


def _plant_resolver(monkeypatch, value: float) -> CountingWrapper:
    """GUARD-TEST plant at the resolver's RETURN (the 18-B.1 raw-plant
    technique; NOT a claim the broker delivers the value).  Target: the
    module attribute `swing.trades.entry_auto_fill._resolve_match_quantity`
    -- bound by the module-level import, and resolved per call at the
    quantity site."""
    wrapper = CountingWrapper(lambda so: value)
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill._resolve_match_quantity", wrapper)
    return wrapper


def _resolve(conn, fake_now):
    return resolve_entry_auto_fill(
        ticker="AAPL", cfg=_make_cfg(environment="production"), conn=conn,
        now=fake_now,
    )


@pytest.mark.parametrize("planted", [float("inf"), float("nan")],
                         ids=["A2a_inf", "A2d_nan"])
def test_A2a_A2d_guard_non_finite_resolver_return_refuses(
    planted, monkeypatch, conn, fake_now, patch_live_state,
    patch_credentials, patch_client_factory, patch_get_orders,
):
    """A2-a (inf) / A2-d (nan). GUARD TESTS, planted at the resolver's
    return -- unreachable on validated models (the legs and the order
    quantity are validated finite).  PRE-FIX: `int(inf)` raises
    `OverflowError` / `int(nan)` raises `ValueError`, escaping the
    resolver.  POST-FIX: ``kind="empty"`` with the non-finite advisory, and
    NOT the sub-one-share one (R7's no-fold rule)."""
    patch_get_orders.state["orders"] = [_make_buy_order(price=10.0,
                                                        quantity=3.0)]
    plant = _plant_resolver(monkeypatch, planted)
    result = _resolve(conn, fake_now)
    assert len(patch_get_orders) >= 1  # did-it-fire (the fetch)
    assert plant.calls >= 1  # did-it-fire (the plant)
    assert result.kind == "empty"
    assert result.fill_origin == "operator_typed"
    assert result.shares is None
    assert _NON_FINITE in (result.advisory_text or "")
    assert _SUB_ONE not in (result.advisory_text or "")


def test_A2a_prime_mechanism_two_huge_legs_overflow_refuses(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """A2-a' MECHANISM (the only validated path to inf): two valid legs of
    ``1e308``.  PRE-FIX: the leg sum overflows to inf and `int(inf)` raises
    `OverflowError`.  POST-FIX: the non-finite refusal."""
    patch_get_orders.state["orders"] = [_two_huge_legs_order()]
    result = _resolve(conn, fake_now)
    assert len(patch_get_orders) >= 1  # did-it-fire
    assert result.kind == "empty"
    assert result.fill_origin == "operator_typed"
    assert _NON_FINITE in (result.advisory_text or "")
    assert _SUB_ONE not in (result.advisory_text or "")


def test_A2b_one_fractional_leg_refuses_sub_one_share(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """A2-b AS RULED (RD, STOP-1): ONE execution leg, ``quantity=0.5``,
    ``price=10.0`` -- the real path to ``[0, 1)`` at the entry site.
    PRE-FIX: ``kind="populated"`` with ``shares == 0`` (the C1-27 defect:
    `int(0.5) == 0`).  POST-FIX: ``kind="empty"``, the sub-one-share
    advisory, NOT the non-finite one."""
    patch_get_orders.state["orders"] = [_make_buy_order(price=10.0,
                                                        quantity=0.5)]
    result = _resolve(conn, fake_now)
    assert len(patch_get_orders) >= 1  # did-it-fire
    assert result.kind == "empty", (result.kind, result.shares)
    assert result.fill_origin == "operator_typed"
    assert result.shares is None
    assert _SUB_ONE in (result.advisory_text or "")
    assert _NON_FINITE not in (result.advisory_text or "")


def test_A2c_guard_zero_resolver_return_refuses_sub_one_share(
    monkeypatch, conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """A2-c AS RULED (RD, STOP-1): a GUARD TEST planted at the resolver's
    return, ``0.0`` -- unreachable on validated models (at the entry site a
    leg sum is > 0, `models.py:216`, and the ``so.quantity`` fallback is
    pre-empted by the price branch; see A2-c').  PRE-FIX: ``populated``,
    ``shares == 0``.  POST-FIX: ``empty``, the sub-one-share advisory."""
    patch_get_orders.state["orders"] = [_make_buy_order(price=10.0,
                                                        quantity=3.0)]
    plant = _plant_resolver(monkeypatch, 0.0)
    result = _resolve(conn, fake_now)
    assert len(patch_get_orders) >= 1  # did-it-fire (the fetch)
    assert plant.calls >= 1  # did-it-fire (the plant)
    assert result.kind == "empty", (result.kind, result.shares)
    assert result.fill_origin == "operator_typed"
    assert _SUB_ONE in (result.advisory_text or "")
    assert _NON_FINITE not in (result.advisory_text or "")


@pytest.mark.parametrize("quantity", [0.5, 0.0],
                         ids=["A2b_prime_0.5", "A2c_prime_0.0"])
def test_A2b_prime_A2c_prime_control_price_branch_preempts_quantity(
    quantity, conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """A2-b' / A2-c' -- REQUIRED CONTROLS (RD, STOP-1).  ``executions=None``
    with ``quantity`` in ``[0, 1)``: `_compute_execution_price` returns
    ``None`` on exactly the condition that sends `_resolve_match_quantity`
    to its ``so.quantity`` fallback, so the price branch returns
    ``kind="empty"`` ("lacks execution-grain price") BEFORE the quantity
    guard is reached.  Passes on BOTH trees by design: it pins the
    pre-emption ORDER.  If a later arc moves the price branch below the
    quantity guard, this goes red and says why."""
    patch_get_orders.state["orders"] = [_no_legs_order(quantity)]
    result = _resolve(conn, fake_now)
    assert len(patch_get_orders) >= 1  # did-it-fire
    assert result.kind == "empty"
    assert _NO_PRICE in (result.advisory_text or "")
    assert _SUB_ONE not in (result.advisory_text or "")


def test_A2f_control_three_whole_shares_populates(
    conn, fake_now, patch_live_state, patch_credentials,
    patch_client_factory, patch_get_orders,
):
    """A2-f CONTROL: ``quantity=3.0`` -> populated, 3 shares, both trees."""
    patch_get_orders.state["orders"] = [_make_buy_order(price=10.0,
                                                        quantity=3.0)]
    result = _resolve(conn, fake_now)
    assert len(patch_get_orders) >= 1  # did-it-fire
    assert result.kind == "populated"
    assert result.shares == 3
