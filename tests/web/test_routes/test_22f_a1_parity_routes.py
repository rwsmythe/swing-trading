"""22-F T-A1 -- C1-01: `SchwabSchemaParityError` on the entry/exit forms.

RD F-F1 (a) DEGRADE, CHARC F-F2 (3): the widened tuples at
`entry_auto_fill.py:383` / `exit_auto_fill.py:759` land the parity error on the
existing ``kind="error"`` / ``operator_typed`` result.

INSTRUMENT (deviation from the plan's patch target, recorded in the exec
ledger): the plan names `trader.get_account_orders` as the patch target, but
A1-d requires the REAL `schwab_api_calls` audit row that `_call_endpoint`
writes and closes before re-raising.  So these route tests run the REAL
`get_account_orders` / `_call_endpoint` and plant the parity error one level
down, at the MAPPER (`swing.integrations.schwab.trader.map_orders_to_fill_
candidates`, bound by trader's module-level import and resolved per call when
`get_account_orders` builds its `functools.partial`).  The mapper is exactly
where a real parity error originates.  Did-it-fire: a counting wrapper around
the planted mapper, asserted called >= 1 in every test.
"""
from __future__ import annotations

import dataclasses
import html
import json
import sqlite3
from typing import Any

import pytest
from fastapi.testclient import TestClient

from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabSchemaParityError,
)
from swing.web.app import create_app
from swing.web.price_cache import PriceCache
from tests._22f_proxies import CountingWrapper, raising

_AUTO_FILL_MODULES = ("swing.trades.entry_auto_fill",
                      "swing.trades.exit_auto_fill")
_PARITY_TEXT = "<orders: missing required key 'x'>"
_HX = {"HX-Request": "true"}


class _FakeClient:
    """A schwabdev-shaped client whose `account_orders` returns an (ignored)
    raw payload; the planted mapper decides the outcome."""

    def __init__(self) -> None:
        self.calls = 0

    def account_orders(self, *args: Any, **kwargs: Any) -> list:
        self.calls += 1
        return []


def _prod_cfg(base_cfg):
    schwab = dataclasses.replace(
        base_cfg.integrations.schwab, environment="production",
        account_hash="deadbeef-account-hash",
        marketdata_ladder_enabled=False,  # the app constructs NO client
    )
    integ = dataclasses.replace(base_cfg.integrations, schwab=schwab)
    return dataclasses.replace(base_cfg, integrations=integ)


@pytest.fixture
def prod_world(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    cfg = _prod_cfg(cfg)
    monkeypatch.setattr(PriceCache, "get_many",
                        lambda self, tickers, *, deadline_seconds, executor: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    client = _FakeClient()
    for mod in _AUTO_FILL_MODULES:
        monkeypatch.setattr(f"{mod}._compute_degraded_state",
                            lambda conn, *, env, tokens_path, now: ("LIVE", None))
        monkeypatch.setattr(f"{mod}.resolve_credentials_env_or_prompt",
                            lambda cfg, env, **kw: ("id-x", "secret-x"))
        monkeypatch.setattr(f"{mod}.construct_authenticated_client",
                            lambda cfg, env, cid, csec: client)
    return cfg, cfg_path, client


def _plant_mapper(monkeypatch, exc: BaseException | None) -> CountingWrapper:
    if exc is None:
        wrapper = CountingWrapper(lambda payload, **kw: [])
    else:
        wrapper = raising(exc)
    monkeypatch.setattr(
        "swing.integrations.schwab.trader.map_orders_to_fill_candidates",
        wrapper)
    return wrapper


def _seed_watchlist(cfg, ticker: str = "AAPL") -> None:
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, last_qualified_date, "
            "status, qualification_count, not_qualified_streak, "
            "last_data_asof_date, entry_target, last_close) "
            f"VALUES ('{ticker}', '2026-04-01','2026-05-15','watch',1,0,"
            "'2026-05-15',105.0,100.0)")
        conn.commit()
    finally:
        conn.close()


def _seed_open_trade(cfg, ticker: str = "AAPL") -> int:
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos import trades as trades_repo
    trade = Trade(
        id=None, ticker=ticker, entry_date="2026-05-04", entry_price=120.50,
        initial_shares=100, initial_stop=115.00, current_stop=118.00,
        state="managing", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = trades_repo.insert_trade_with_event(
                conn, trade, event_ts="2026-05-04T09:30:00")
    finally:
        conn.close()
    return int(tid)


def _fresh_counts(db_path) -> dict:
    c = sqlite3.connect(str(db_path))
    try:
        return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("trades", "fills", "schwab_api_calls")}
    finally:
        c.close()


def test_A1c_A1d_A1f_entry_form_parity_degrades_and_audit_row_closed(
        prod_world, monkeypatch):
    """A1-c (200 + the advisory names the class), A1-d (fresh read: one
    CLOSED audit row, nothing else written), A1-f (degraded form carries no
    auto-fill provenance).  PRE-FIX: 500 (the parity error escapes the
    resolver to the app-wide handler)."""
    cfg, cfg_path, client = prod_world
    _seed_watchlist(cfg)
    mapper = _plant_mapper(monkeypatch, SchwabSchemaParityError(_PARITY_TEXT))
    before = _fresh_counts(cfg.paths.db_path)
    with TestClient(create_app(cfg, cfg_path)) as tc:
        resp = tc.get("/trades/entry/form?ticker=AAPL")
    assert mapper.calls >= 1 and client.calls >= 1  # did-it-fire
    assert resp.status_code == 200, resp.text[:500]
    assert "SchwabSchemaParityError" in resp.text
    assert "auto-fill unavailable" in resp.text
    # A1-d -- a FRESH connection.
    after = _fresh_counts(cfg.paths.db_path)
    assert after["schwab_api_calls"] == before["schwab_api_calls"] + 1
    assert after["trades"] == before["trades"]
    assert after["fills"] == before["fills"]
    c = sqlite3.connect(str(cfg.paths.db_path))
    try:
        # `schwab_api_calls` has no finished-timestamp column; the close is
        # `record_call_finish`, which sets `status` and `response_time_ms`.
        status, finished = c.execute(
            "SELECT status, response_time_ms FROM schwab_api_calls "
            "ORDER BY call_id DESC LIMIT 1").fetchone()
    finally:
        c.close()
    assert status == "error"
    assert status != "in_flight"  # closed BEFORE raising
    assert finished is not None
    # A1-f -- no provenance claim on the degraded form: the three hidden
    # auto-fill anchors are ABSENT, so the POST infers `operator_typed` and
    # persists NULL audit columns (R11, exactly as today's degraded rows).
    assert _hidden_value(resp.text, "schwab_source_value_json") is None
    assert _hidden_value(resp.text, "fill_origin_at_form_render") is None


def _hidden_value(body: str, name: str) -> str | None:
    import re
    m = re.search(r'<input[^>]*name="' + re.escape(name) + r'"[^>]*>', body)
    if m is None:
        return None
    v = re.search(r'value="([^"]*)"', m.group(0))
    return html.unescape(v.group(1)) if v else ""


def test_A1c_prime_exit_form_parity_degrades(prod_world, monkeypatch):
    """A1-c'. PRE-FIX: 500.  POST-FIX: 200, the advisory names the class."""
    cfg, cfg_path, client = prod_world
    tid = _seed_open_trade(cfg)
    mapper = _plant_mapper(monkeypatch, SchwabSchemaParityError(_PARITY_TEXT))
    with TestClient(create_app(cfg, cfg_path)) as tc:
        resp = tc.get(f"/trades/{tid}/exit/form")
    assert mapper.calls >= 1 and client.calls >= 1  # did-it-fire
    assert resp.status_code == 200, resp.text[:500]
    assert "SchwabSchemaParityError" in resp.text
    assert "auto-fill unavailable" in resp.text


def test_A1e_prime_exit_post_rerender_parity_is_400_not_500(
        prod_world, monkeypatch):
    """A1-e'. `exit_shares` > remaining makes `record_exit` raise
    `ValueError`; the `except ValueError` branch re-renders through
    `build_exit_form_vm`, whose fetch raises parity.  PRE-FIX: 500.
    POST-FIX: 400 re-render naming the class AND the refusal.  Nothing about
    the anchor (RD 1(iii), AL-6)."""
    cfg, cfg_path, client = prod_world
    tid = _seed_open_trade(cfg)
    mapper = _plant_mapper(monkeypatch, SchwabSchemaParityError(_PARITY_TEXT))
    before = _fresh_counts(cfg.paths.db_path)
    with TestClient(create_app(cfg, cfg_path)) as tc:
        resp = tc.post(f"/trades/{tid}/exit", headers=_HX, data={
            "exit_date": "2026-05-10", "exit_price": "130.0",
            "shares": "500", "reason": "manual", "notes": "",
        })
    assert mapper.calls >= 1  # did-it-fire
    assert resp.status_code == 400, resp.text[:500]
    assert "SchwabSchemaParityError" in resp.text
    assert "exceeds" in resp.text
    assert _fresh_counts(cfg.paths.db_path)["fills"] == before["fills"]


def _entry_post_data(**over: str) -> dict:
    data = {
        "ticker": "AAPL", "entry_date": "2026-05-19", "entry_price": "150.25",
        "shares": "10", "initial_stop": "140.0", "rationale": "not-a-rationale",
        "notes": "",
    }
    data.update(over)
    return data


_ENVELOPE = json.dumps({"entry_date": "2026-05-19", "entry_price": 150.25,
                        "shares": 100, "schwab_order_id": "order-abc"})


def test_A1e_entry_post_rerender_restores_submitted_anchor_under_parity(
        prod_world, monkeypatch):
    """A1-e (RD 1(ii) PIN): a validation-failed POST carrying a populated
    anchor, the re-render's fetch raising parity.  PRE-FIX: 500 (the fetch
    raises inside `build_entry_form_vm`).  POST-FIX: 400; the hidden anchor
    equals the SUBMITTED string byte-for-byte; kind `populated`; no parity
    advisory (the restore clears it, `routes/trades.py:487-505`)."""
    cfg, cfg_path, client = prod_world
    _seed_watchlist(cfg)
    mapper = _plant_mapper(monkeypatch, SchwabSchemaParityError(_PARITY_TEXT))
    with TestClient(create_app(cfg, cfg_path)) as tc:
        resp = tc.post("/trades/entry", headers=_HX, data=_entry_post_data(
            schwab_source_value_json=_ENVELOPE,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        ))
    assert mapper.calls >= 1  # did-it-fire
    assert resp.status_code == 400, resp.text[:500]
    assert _hidden_value(resp.text, "schwab_source_value_json") == _ENVELOPE
    assert _hidden_value(resp.text, "fill_origin_at_form_render") == "schwab_auto"
    assert "Auto-fill source:" in resp.text  # the populated-kind block
    assert "SchwabSchemaParityError" not in resp.text


def test_A1g_control_schwab_api_error_still_degrades(prod_world, monkeypatch):
    """A1-g CONTROL: a plain `SchwabApiError` from the mapper path takes the
    sibling branch on BOTH trees (200 + kind error)."""
    cfg, cfg_path, client = prod_world
    _seed_watchlist(cfg)
    mapper = _plant_mapper(monkeypatch, SchwabApiError(500, "x"))
    with TestClient(create_app(cfg, cfg_path)) as tc:
        resp = tc.get("/trades/entry/form?ticker=AAPL")
    assert mapper.calls >= 1  # did-it-fire
    assert resp.status_code == 200
    assert "SchwabApiError" in resp.text
    assert "auto-fill unavailable" in resp.text


def test_A1h_control_rerender_with_normal_fetch_restores_anchor(
        prod_world, monkeypatch):
    """A1-h CONTROL: orders return normally -> 400 + anchor restored, both
    trees."""
    cfg, cfg_path, client = prod_world
    _seed_watchlist(cfg)
    mapper = _plant_mapper(monkeypatch, None)
    with TestClient(create_app(cfg, cfg_path)) as tc:
        resp = tc.post("/trades/entry", headers=_HX, data=_entry_post_data(
            schwab_source_value_json=_ENVELOPE,
            auto_fill_audit_at="2026-05-19T14:30:00.000000+00:00",
            fill_origin_at_form_render="schwab_auto",
        ))
    assert mapper.calls >= 1  # did-it-fire
    assert resp.status_code == 400
    assert _hidden_value(resp.text, "schwab_source_value_json") == _ENVELOPE
