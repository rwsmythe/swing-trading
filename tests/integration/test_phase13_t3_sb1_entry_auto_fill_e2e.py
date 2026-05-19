"""Phase 13 T3.SB1 T-B.1.6 — fast E2E for the entry auto-fill arc.

Exercises the full GET → POST happy-path:
  1. GET /trades/entry/form?ticker=AAPL with a mocked production-shape
     SchwabOrderResponse → auto-populated input values + hidden anchor
     + advisory text omitted (populated kind).
  2. Operator submits the form unchanged (POST with the same
     entry_date / entry_price / shares as the auto-fill values) →
     fills row persists with fill_origin='schwab_auto' +
     schwab_source_value_json present + operator_corrected_value_json
     NULL + auto_fill_audit_at populated.
  3. schwab_api_calls audit row has surface='trade_entry' + success
     status + signature_hash populated.

This is the fast (non-slow) E2E — runs in pytest -m 'not slow'.
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


def _patch_price_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds=None, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _seed_watchlist_row(cfg: Any, ticker: str = "AAPL") -> None:
    conn = ensure_schema(cfg.paths.db_path)
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, added_date, last_qualified_date, "
            "status, qualification_count, not_qualified_streak, "
            "last_data_asof_date, entry_target, last_close) "
            f"VALUES ('{ticker}', '2026-04-01','2026-05-15','watch',1,0,"
            "'2026-05-15',105.0,100.0)"
        )
        conn.commit()
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
        # Carry through ALL public cfg attributes — downstream callsites
        # (build_dashboard, sizing, etc.) consult fields like cfg.rs,
        # cfg.briefing, cfg.evaluation that we don't enumerate explicitly.
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


def _patch_schwab_stack_with_buy_fill(
    monkeypatch: pytest.MonkeyPatch,
    *,
    entry_date: str = "2026-05-19",
    enter_time: str = "2026-05-19T14:30:00.000Z",
    price: float = 150.25,
    quantity: float = 100,
) -> None:
    """Stub the entry_auto_fill Schwab integration stack to return a
    single production-shape BUY fill matching AAPL.
    """
    leg = SchwabExecutionLeg(
        leg_id=1, price=price, quantity=quantity,
        mismarked_quantity=None, instrument_id=12345, time=enter_time,
    )
    order = SchwabOrderResponse(
        order_id="order-AAPL-e2e", status="FILLED",
        enter_time=enter_time, instrument_symbol="AAPL",
        instruction="BUY", quantity=quantity,
        order_type="LIMIT", price=price, executions=[leg],
    )

    monkeypatch.setattr(
        "swing.trades.entry_auto_fill._compute_degraded_state",
        lambda conn, *, env, tokens_path, now: ("LIVE", None),
    )
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill.resolve_credentials_env_or_prompt",
        lambda cfg, env, *, allow_prompt=True, prompter=None: (
            "sentinel-client-id", "sentinel-client-secret"
        ),
    )
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill.construct_authenticated_client",
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
            signature_hash="sha256:e2e-fast-test-sig",
            status="success", error_message=None,
        )
        return [order]

    monkeypatch.setattr(
        "swing.trades.entry_auto_fill.trader.get_account_orders",
        fake_get_account_orders,
    )
    _ = entry_date  # unused but kept for signature symmetry


def _extract_hidden_input_value(body: str, name: str) -> str:
    """Pull the value="..." attribute off a hidden input by `name`.

    Tolerant of attribute-order variation + HTML-entity escaping (Jinja
    autoescape converts " inside the JSON value to &#34;).
    """
    # Match either `name="X" ... value="..."` OR `value="..." ... name="X"`.
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
            # Decode HTML entities (Jinja autoescape converts " → &#34;).
            import html
            return html.unescape(m.group(1))
    raise AssertionError(f"hidden input name={name!r} not in body")


def test_full_arc_get_then_post_persists_schwab_auto_fill(
    seeded_db, monkeypatch,
):
    """T3.SB1 happy-path E2E:

    1. GET form → mock Schwab returns matching BUY fill at $150.25 ×
       100sh on 2026-05-19.
    2. Form renders pre-populated with those values + hidden anchor.
    3. POST submits unchanged values (operator accepts auto-fill).
    4. trades row created; fills row carries fill_origin='schwab_auto'
       + schwab_source_value_json (verbatim anchor) +
       operator_corrected_value_json NULL + auto_fill_audit_at present.
    5. Audit row in schwab_api_calls with surface='trade_entry'.
    """
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    _patch_production_cfg_seam(monkeypatch)
    _patch_schwab_stack_with_buy_fill(
        monkeypatch, entry_date="2026-05-19",
        enter_time="2026-05-19T14:30:00.000Z",
        price=150.25, quantity=100,
    )

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # Step 1+2 — GET the form.
        resp_get = client.get("/trades/entry/form?ticker=AAPL")
        assert resp_get.status_code == 200, resp_get.text
        body = resp_get.text
        # Pull anchors out of hidden inputs.
        anchor_json = _extract_hidden_input_value(
            body, "schwab_source_value_json",
        )
        audit_at = _extract_hidden_input_value(body, "auto_fill_audit_at")
        # Sanity: anchor envelope parses + matches expected.
        anchor_dict = json.loads(anchor_json)
        assert anchor_dict["entry_price"] == 150.25
        assert anchor_dict["shares"] == 100
        assert anchor_dict["entry_date"] == "2026-05-19"
        # Hidden anchor for fill_origin_at_form_render.
        fill_origin_at_form_render = _extract_hidden_input_value(
            body, "fill_origin_at_form_render",
        )
        assert fill_origin_at_form_render == "schwab_auto"

        # Step 3 — POST form unchanged. Use full_phase7_entry_payload
        # helper to satisfy the 18 pre-trade required-field gate, then
        # override with the auto-populated values + hidden anchors.
        from tests.web.conftest import full_phase7_entry_payload
        payload = full_phase7_entry_payload(
            ticker="AAPL",
            entry_date="2026-05-19",
            entry_price="150.25",
            shares="100",
            initial_stop="140.00",
            rationale="aplus-setup",
            notes="",
        )
        payload.update({
            "schwab_source_value_json": anchor_json,
            "auto_fill_audit_at": audit_at,
            "fill_origin_at_form_render": "schwab_auto",
        })
        resp_post = client.post(
            "/trades/entry", data=payload, headers={"HX-Request": "true"},
        )
        assert resp_post.status_code == 200, resp_post.text

    # Step 4 — verify fills row persistence.
    conn = connect(cfg.paths.db_path)
    try:
        # ORDER BY fill_id DESC LIMIT 1 picks record_entry's authoritative
        # entry fill (the conftest auto-fixture also writes an entry fill
        # with default fill_origin='operator_typed' — see
        # tests/web/conftest.py:90+).
        fill_row = conn.execute(
            "SELECT fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, auto_fill_audit_at "
            "FROM fills WHERE action='entry' "
            "ORDER BY fill_id DESC LIMIT 1"
        ).fetchone()
        # Step 5 — verify schwab_api_calls audit row.
        audit_row = conn.execute(
            "SELECT surface, endpoint, status, environment, signature_hash "
            "FROM schwab_api_calls ORDER BY call_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    assert fill_row is not None
    assert fill_row[0] == "schwab_auto"
    assert fill_row[1] == anchor_json
    assert fill_row[2] is None, (
        "operator_corrected_value_json must be NULL on unchanged submit"
    )
    assert fill_row[3] == audit_at

    assert audit_row is not None
    assert audit_row[0] == "trade_entry"
    assert audit_row[1] == "accounts.orders.list"
    assert audit_row[2] == "success"
    assert audit_row[3] == "production"
    assert audit_row[4] == "sha256:e2e-fast-test-sig"
