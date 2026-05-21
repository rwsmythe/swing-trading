"""Phase 13 T3.SB2 T-B.2.5 — fast E2E for the exit auto-fill arc.

SELL-side mirror of test_phase13_t3_sb1_entry_auto_fill_e2e.py. Exercises
the full GET -> POST happy-path:

  1. Seed an open trade (AAPL, 100 shares @ $100, entry 2026-04-15).
  2. GET /trades/{id}/exit/form with a mocked production-shape
     SchwabOrderResponse SELL fill -> auto-populated input values + hidden
     anchor + per-candidate hidden inputs.
  3. Operator submits the form unchanged (POST with the same auto-fill
     values + the hidden anchors verbatim) ->
     fills row persists with fill_origin='schwab_auto' +
     schwab_source_value_json (re-stamped with selected_candidate_*) +
     operator_corrected_value_json NULL + auto_fill_audit_at populated.
  4. schwab_api_calls audit row has surface='trade_exit' + success status +
     signature_hash populated.
  5. Trade state transitions to 'closed' (full-quantity exit matches the
     seeded position size).

This is the fast (non-slow) E2E -- runs in pytest -m 'not slow'. Mirrors
T3.SB1 closer test pattern + uses synthetic mocks (NOT cassette replay).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect, ensure_schema
from swing.data.models import Trade
from swing.data.repos import trades as trades_repo
from swing.data.repos.trades import list_open_trades
from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


@pytest.fixture
def seeded_db(tmp_path: Path) -> Any:
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


@pytest.fixture(autouse=True)
def _auto_entry_fill_after_insert_trade(monkeypatch):
    """Mirror tests/web/conftest.py autouse fixture: wrap
    insert_trade_with_event to also write the entry-fill so current_size
    reflects initial_shares (the exit service guards on shares <=
    current_size).
    """
    from swing.data.models import Fill
    from swing.data.repos import fills as fills_repo
    real_insert = trades_repo.insert_trade_with_event

    def wrapped(conn, trade, *, event_ts, rationale=None):
        trade_id = real_insert(
            conn, trade, event_ts=event_ts, rationale=rationale,
        )
        if trade.state in ("entered", "managing", "partial_exited"):
            fills_repo.insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None, trade_id=trade_id,
                    fill_datetime=event_ts, action="entry",
                    quantity=float(trade.initial_shares),
                    price=float(trade.entry_price),
                ),
                event_ts=event_ts,
            )
        return trade_id

    monkeypatch.setattr(trades_repo, "insert_trade_with_event", wrapped)
    try:
        import swing.web.routes.trades as web_trades_routes
        if hasattr(web_trades_routes, "insert_trade_with_event"):
            monkeypatch.setattr(
                web_trades_routes, "insert_trade_with_event", wrapped,
            )
    except ImportError:
        pass


def _patch_price_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=120.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _seed_open_trade(cfg: Any, ticker: str = "AAPL") -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trades_repo.insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=100.0, initial_shares=100, initial_stop=95.0,
                current_stop=95.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
        return int(trade.id)
    finally:
        conn.close()


def _patch_production_cfg_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub apply_overrides so the route handler sees a cfg with
    integrations.schwab.environment='production' + account_hash populated.
    """
    from dataclasses import dataclass
    from types import SimpleNamespace

    @dataclass
    class _SchwabCfgShim:
        environment: str = "production"
        client_id: str | None = "shim-client-id"
        client_secret: str | None = "shim-client-secret"
        account_hash: str | None = "shim-account-hash"

    @dataclass
    class _IntegrationsCfgShim:
        schwab: _SchwabCfgShim
        finviz: Any = None

    def fake_apply_overrides(cfg: Any) -> Any:
        kwargs = {}
        for attr in dir(cfg):
            if attr.startswith("_") or attr in ("integrations",):
                continue
            try:
                kwargs[attr] = getattr(cfg, attr)
            except AttributeError:
                continue
        existing_finviz = getattr(
            getattr(cfg, "integrations", None), "finviz", None,
        )
        kwargs["integrations"] = _IntegrationsCfgShim(
            schwab=_SchwabCfgShim(), finviz=existing_finviz,
        )
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(
        "swing.web.routes.trades.apply_overrides", fake_apply_overrides,
    )


def _patch_schwab_stack_with_sell_fill(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ticker: str = "AAPL",
    enter_time: str = "2026-05-19T14:30:00.000Z",
    price: float = 120.50,
    quantity: float = 100,
) -> None:
    """Stub the exit_auto_fill Schwab integration stack to return a single
    production-shape SELL fill matching the seeded trade.
    """
    leg = SchwabExecutionLeg(
        leg_id=1, price=price, quantity=quantity,
        mismarked_quantity=None, instrument_id=12345, time=enter_time,
    )
    order = SchwabOrderResponse(
        order_id="order-AAPL-exit-e2e", status="FILLED",
        enter_time=enter_time, instrument_symbol=ticker,
        instruction="SELL", quantity=quantity,
        order_type="LIMIT", price=price, executions=[leg],
    )

    monkeypatch.setattr(
        "swing.trades.exit_auto_fill._compute_degraded_state",
        lambda conn, *, env, tokens_path, now: ("LIVE", None),
    )
    monkeypatch.setattr(
        "swing.trades.exit_auto_fill.resolve_credentials_env_or_prompt",
        lambda cfg, env, *, allow_prompt=True, prompter=None: (
            "sentinel-client-id", "sentinel-client-secret"
        ),
    )
    monkeypatch.setattr(
        "swing.trades.exit_auto_fill.construct_authenticated_client",
        lambda cfg, env, cid, csec: MagicMock(),
    )

    from swing.integrations.schwab import audit_service

    def fake_get_account_orders(
        client, conn, account_hash, from_dt, to_dt,
        *, surface, environment, pipeline_run_id=None,
        status=None, max_results=None,
    ):
        ts = datetime.now().isoformat(timespec="microseconds")
        call_id = audit_service.record_call_start(
            conn, ts=ts, endpoint="accounts.orders.list",
            pipeline_run_id=pipeline_run_id,
            surface=surface, environment=environment,
        )
        audit_service.record_call_finish(
            conn, call_id=call_id, http_status=200,
            response_time_ms=42, rate_limit_remaining=99,
            signature_hash="sha256:e2e-fast-exit-test-sig",
            status="success", error_message=None,
        )
        return [order]

    monkeypatch.setattr(
        "swing.trades.exit_auto_fill.trader.get_account_orders",
        fake_get_account_orders,
    )


def _extract_hidden_input_value(body: str, name: str) -> str:
    """Pull the value="..." attribute off a hidden input by ``name``."""
    patterns = [
        re.compile(
            rf'<input[^>]*\bname="{re.escape(name)}"[^>]*\bvalue="([^"]*)"',
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            rf'<input[^>]*\bvalue="([^"]*)"[^>]*\bname="{re.escape(name)}"',
            re.IGNORECASE | re.DOTALL,
        ),
    ]
    for pat in patterns:
        m = pat.search(body)
        if m:
            import html
            return html.unescape(m.group(1))
    raise AssertionError(f"hidden input name={name!r} not in body")


def test_full_arc_get_then_post_persists_schwab_auto_exit_fill(
    seeded_db, monkeypatch,
):
    """T3.SB2 happy-path E2E:

    1. Seed open AAPL trade (100sh @ $100, entered 2026-04-15).
    2. GET /trades/{id}/exit/form -> mock Schwab returns matching SELL fill
       at $120.50 x 100sh on 2026-05-19.
    3. Form renders pre-populated with those values + hidden anchor +
       per-candidate hidden inputs.
    4. POST /trades/{id}/exit submits unchanged values (operator accepts
       auto-fill).
    5. fills row carries fill_origin='schwab_auto' +
       schwab_source_value_json (re-stamped with selected_candidate_*) +
       operator_corrected_value_json NULL + auto_fill_audit_at present.
    6. Audit row in schwab_api_calls with surface='trade_exit'.
    7. Trade state transitions to 'closed' (full-quantity exit).
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    _patch_production_cfg_seam(monkeypatch)
    _patch_schwab_stack_with_sell_fill(
        monkeypatch, ticker="AAPL",
        enter_time="2026-05-19T14:30:00.000Z",
        price=120.50, quantity=100,
    )

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # Step 2+3 -- GET the exit form.
        resp_get = client.get(f"/trades/{trade_id}/exit/form")
        assert resp_get.status_code == 200, resp_get.text
        body = resp_get.text
        anchor_json = _extract_hidden_input_value(
            body, "schwab_source_value_json",
        )
        audit_at = _extract_hidden_input_value(body, "auto_fill_audit_at")
        fill_origin_at_form_render = _extract_hidden_input_value(
            body, "fill_origin_at_form_render",
        )
        assert fill_origin_at_form_render == "schwab_auto"
        # Sanity: anchor envelope parses + matches expected fields.
        anchor_dict = json.loads(anchor_json)
        assert anchor_dict["exit_price"] == 120.50
        assert anchor_dict["closed_shares"] == 100
        assert anchor_dict["exit_date"] == "2026-05-19"
        assert anchor_dict["schwab_instrument_symbol"] == "AAPL"
        assert anchor_dict["candidate_count"] == 1
        # Defense-in-depth: single-fill case (length-1 candidates list)
        # MUST NOT emit per-candidate hidden inputs or the radio fieldset
        # per the template gate `{% if vm.auto_fill_candidates|length > 1 %}`.
        # Mirrors test_exit_form_auto_fill.py::test_a negative-assertion.
        assert 'candidate_signature_hash_' not in body, (
            "single-fill case must not emit per-candidate hidden inputs"
        )
        assert 'type="radio"' not in body, (
            "single-fill case must not render radio fieldset"
        )

        # Step 4 -- POST form unchanged. Single-fill case: no per-candidate
        # hidden inputs, no candidate_index. POST handler's selected_index
        # falls through to None (per route line ~1891), so the persisted
        # envelope carries no selected_candidate_* provenance fields.
        payload = {
            "exit_date": "2026-05-19",
            "exit_price": "120.50",
            "shares": "100",
            "reason": "manual",
            "notes": "",
            "schwab_source_value_json": anchor_json,
            "auto_fill_audit_at": audit_at,
            "fill_origin_at_form_render": "schwab_auto",
        }
        resp_post = client.post(
            f"/trades/{trade_id}/exit", data=payload,
            headers={"HX-Request": "true"},
        )
        assert resp_post.status_code == 200, resp_post.text

    # Step 5 -- verify fills row persistence.
    conn = connect(cfg.paths.db_path)
    try:
        fill_row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, auto_fill_audit_at, "
            "quantity, price "
            "FROM fills WHERE trade_id = ? AND action != 'entry' "
            "ORDER BY fill_id DESC LIMIT 1",
            (trade_id,),
        ).fetchone()
        # Step 6 -- verify schwab_api_calls audit row.
        audit_row = conn.execute(
            "SELECT surface, endpoint, status, environment, signature_hash "
            "FROM schwab_api_calls "
            "WHERE surface = 'trade_exit' "
            "ORDER BY call_id DESC LIMIT 1"
        ).fetchone()
        # Step 7 -- verify trade state transitioned to 'closed'.
        trade_state_row = conn.execute(
            "SELECT state FROM trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
    finally:
        conn.close()

    assert fill_row is not None, "exit fill should be persisted"
    assert fill_row[0] == "schwab_auto"
    # Original envelope keys round-trip verbatim through the POST handler's
    # provenance-stamping branch. Single-fill case: no per-candidate hidden
    # inputs were emitted (template gate at length > 1), so the POST
    # handler's selected_index stays None and the persisted envelope does
    # NOT carry selected_candidate_* provenance fields (per route logic at
    # ~lines 1886-1962). T-B.2.3 test_a synthesizes the multi-partial-shaped
    # hidden inputs to exercise the provenance-stamping branch; this E2E
    # exercises the genuine GET -> POST round-trip flow.
    persisted = json.loads(fill_row[1])
    original = json.loads(anchor_json)
    for k, v in original.items():
        assert persisted[k] == v, (
            f"original envelope key {k!r} must round-trip verbatim"
        )
    assert "selected_candidate_signature_hash" not in persisted, (
        "single-fill GET emits no per-candidate hidden inputs, so POST "
        "handler should not stamp selected_candidate_signature_hash"
    )
    assert fill_row[2] is None, (
        "operator_corrected_value_json must be NULL on unchanged submit"
    )
    assert fill_row[3] == audit_at
    assert float(fill_row[4]) == 100.0
    assert float(fill_row[5]) == 120.50

    assert audit_row is not None
    assert audit_row[0] == "trade_exit"
    assert audit_row[1] == "accounts.orders.list"
    assert audit_row[2] == "success"
    assert audit_row[3] == "production"
    assert audit_row[4] == "sha256:e2e-fast-exit-test-sig"

    assert trade_state_row is not None
    assert trade_state_row[0] == "closed", (
        f"full-quantity exit (100/100) should close the trade; "
        f"got state={trade_state_row[0]!r}"
    )
