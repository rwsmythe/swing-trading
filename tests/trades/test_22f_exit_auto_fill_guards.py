"""22-F service-level guards on EXIT auto-fill (`resolve_exit_auto_fill`).

T-A1 (C1-01, RD F-F1 (a), CHARC F-F2 (3)): a `SchwabSchemaParityError` from
the orders fetch lands on the existing ``kind="error"`` / ``operator_typed``
result (A1-b).

The fixtures are the sibling module's (`tests/trades/test_exit_auto_fill.py`);
every drive through ``patch_get_orders`` asserts the recorder saw >= 1 call
(the did-it-fire rule, 22-F plan section 0.4).
"""
from __future__ import annotations

from swing.integrations.schwab.client import SchwabSchemaParityError
from swing.trades.exit_auto_fill import resolve_exit_auto_fill
from tests.trades.test_exit_auto_fill import (  # noqa: F401 -- fixtures
    _make_cfg,
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
