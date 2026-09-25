"""22-F service-level guards on ENTRY auto-fill (`resolve_entry_auto_fill`).

T-A1 (C1-01, RD F-F1 (a), CHARC F-F2 (3)): a `SchwabSchemaParityError` from
the orders fetch lands on the existing ``kind="error"`` / ``operator_typed``
result, exactly like every `SchwabApiError` sibling (A1-a).

The fixtures are the sibling module's (`tests/trades/test_entry_auto_fill.py`);
every drive through ``patch_get_orders`` asserts the recorder saw >= 1 call
(the did-it-fire rule, 22-F plan section 0.4).
"""
from __future__ import annotations

from swing.integrations.schwab.client import SchwabSchemaParityError
from swing.trades.entry_auto_fill import resolve_entry_auto_fill
from tests.trades.test_entry_auto_fill import (  # noqa: F401 -- fixtures
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
