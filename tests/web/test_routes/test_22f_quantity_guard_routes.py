"""22-F T-A2 / T-A3 -- the quantity guards at the entry and exit form routes.

T-A2 (C1-27): an overflowing leg sum reaching `int(quantity)` at the ENTRY
auto-fill site escapes as `OverflowError` -> the app-wide 500 page.  After the
guard, the form renders with the non-finite advisory (A2-e).

The world is T-A1's (`test_22f_a1_parity_routes.py`): the REAL
`get_account_orders` / `_call_endpoint`, with the MAPPER planted (a counting
wrapper, did-it-fire asserted) to return real `SchwabOrderResponse`s.
"""
from __future__ import annotations

import html

from fastapi.testclient import TestClient

from swing.web.app import create_app
from tests._22f_proxies import CountingWrapper
from tests.trades.test_22f_entry_auto_fill_guards import _two_huge_legs_order
from tests.web.test_routes.test_22f_a1_parity_routes import (  # noqa: F401
    _seed_watchlist,
    prod_world,
)


def _plant_mapper_orders(monkeypatch, orders: list) -> CountingWrapper:
    wrapper = CountingWrapper(lambda payload, **kw: list(orders))
    monkeypatch.setattr(
        "swing.integrations.schwab.trader.map_orders_to_fill_candidates",
        wrapper)
    return wrapper


def test_A2e_entry_form_overflowing_leg_sum_renders_advisory_not_500(
        prod_world, monkeypatch):
    """A2-e: `GET /trades/entry/form` under A2-a' (two valid legs of
    ``1e308``).  PRE-FIX: 500 (`int(inf)` raises `OverflowError` out of the
    resolver).  POST-FIX: 200 with the non-finite advisory rendered."""
    cfg, cfg_path, client = prod_world
    _seed_watchlist(cfg)
    mapper = _plant_mapper_orders(monkeypatch, [_two_huge_legs_order()])
    with TestClient(create_app(cfg, cfg_path)) as tc:
        resp = tc.get("/trades/entry/form?ticker=AAPL")
    assert mapper.calls >= 1 and client.calls >= 1  # did-it-fire
    assert resp.status_code == 200, resp.text[:500]
    body = html.unescape(resp.text)
    assert "carries a non-finite quantity" in body
    assert "below one whole share" not in body
