"""Phase 13 T3.SB1 T-B.1.5 — slow Schwab entry auto-fill E2E.

V1 uses mock-based Schwab integration (per CLAUDE.md gotcha "Schwab
cassette runbook is V2 PLANNED — V1 ships mock-based tests only"). When
V2 introduces cassette-recorded Schwab tests (operator-paired session
required for live API access), this file extends to include cassette
replay; the mock-based test below remains the V1 backstop for
schwab_api_calls audit-row emit + surface='trade_entry' + production-
shape SchwabOrderResponse → fills row plumbing.

Per plan §G.2 T-B.1.5 step 1 + dispatch brief §5 watch items 11, 12, 17:

  - GET /trades/entry/form?ticker=AAPL renders with auto-populated
    inputs derived from a mock Schwab Trader API response.
  - Audit row written with surface='trade_entry' + endpoint=
    'accounts.orders.list' + status='success'.
  - signature_hash present + non-empty (per Phase 11 Sub-bundle B
    drift-detection contract).

Marked slow because the test exercises the full TestClient lifespan +
ladder of Schwab integration wrappers; runs in pytest -m slow.
"""
from __future__ import annotations

import sqlite3
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
from swing.web.price_cache import PriceCache

pytestmark = pytest.mark.slow


@pytest.fixture
def seeded_db(tmp_path: Path) -> Any:
    """Local seeded_db fixture — mirrors tests/web/conftest.py:seeded_db
    so this test file can live under tests/integrations/ without
    cross-package fixture imports.
    """
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
        lambda self, tickers, *, deadline_seconds, executor: {},
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


def _make_production_buy_order(
    *, ticker: str = "AAPL",
    enter_time: str = "2026-05-19T14:30:00.000Z",
    price: float = 150.25, quantity: float = 100,
) -> SchwabOrderResponse:
    """Production-emitter-shape SchwabOrderResponse with a single execution
    leg. Per CLAUDE.md "Synthetic-fixture-vs-production-emitter shape
    drift" gotcha — uses the real dataclass to ensure shape parity with
    what trader.get_account_orders returns in production.
    """
    leg = SchwabExecutionLeg(
        leg_id=1, price=price, quantity=quantity,
        mismarked_quantity=None, instrument_id=12345, time=enter_time,
    )
    return SchwabOrderResponse(
        order_id="order-AAPL-e2e", status="FILLED",
        enter_time=enter_time, instrument_symbol=ticker,
        instruction="BUY", quantity=quantity,
        order_type="LIMIT", price=price, executions=[leg],
    )


def _patch_full_schwab_stack(
    monkeypatch: pytest.MonkeyPatch,
    *,
    orders: list[SchwabOrderResponse] | None = None,
) -> None:
    """Stub the entire Schwab integration ladder so the entry_auto_fill
    resolver reaches trader.get_account_orders via the real call chain
    (apply_overrides → resolve_credentials_env_or_prompt → DEGRADED
    predicate → construct_authenticated_client → trader.get_account_orders).
    """
    if orders is None:
        orders = [_make_production_buy_order()]
    # LIVE state from the DEGRADED predicate so we proceed.
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill._compute_degraded_state",
        lambda conn, *, env, tokens_path, now: ("LIVE", None),
    )
    # Stub the credential resolver.
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill.resolve_credentials_env_or_prompt",
        lambda cfg, env, *, allow_prompt=True, prompter=None: (
            "sentinel-client-id", "sentinel-client-secret"
        ),
    )
    # Stub the client factory.
    monkeypatch.setattr(
        "swing.trades.entry_auto_fill.construct_authenticated_client",
        lambda cfg, env, cid, csec: MagicMock(),
    )

    # Stub trader.get_account_orders + ALSO write an audit row to mirror
    # the production behavior (the real implementation goes through
    # audit_service.record_call_start + record_call_finish). For the V1
    # mock-based test, we exercise the route plumbing + the audit-row
    # write contract; cassette V2 will exercise the real schwabdev wrapper.
    from swing.integrations.schwab import audit_service

    def fake_get_account_orders(
        client, conn, account_hash, from_dt, to_dt,
        *, surface, environment, pipeline_run_id=None,
        status=None, max_results=None,
    ):
        # Mirror the audit-row lifecycle the real trader.get_account_orders
        # performs via _call_endpoint → audit_service.record_call_start /
        # record_call_finish.
        ts = datetime.now().isoformat(timespec="microseconds")
        call_id = audit_service.record_call_start(
            conn, ts=ts, endpoint="accounts.orders.list",
            pipeline_run_id=pipeline_run_id,
            surface=surface, environment=environment,
        )
        audit_service.record_call_finish(
            conn, call_id=call_id, http_status=200,
            response_time_ms=42, rate_limit_remaining=99,
            signature_hash="sha256:e2e-test-signature-hash",
            status="success", error_message=None,
        )
        return list(orders)

    monkeypatch.setattr(
        "swing.trades.entry_auto_fill.trader.get_account_orders",
        fake_get_account_orders,
    )


def _patch_cfg_for_production_schwab(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stub ``apply_overrides`` so the entry_form route handler sees a
    cfg with ``integrations.schwab.environment='production'`` +
    ``account_hash`` populated. The base cfg (from _minimal_config) is a
    frozen dataclass; monkeypatching the field directly raises
    FrozenInstanceError. apply_overrides is the per-request boundary
    where overrides are applied (Phase 12 Sub-bundle B discipline), so
    swapping it here is the canonical seam.
    """
    from dataclasses import dataclass

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

    def fake_apply_overrides(cfg):
        # Construct a SimpleNamespace mirror of the relevant cfg surfaces
        # the route handler + entry_auto_fill resolver consult. We carry
        # through the original cfg's other attributes via getattr so
        # downstream callsites (sizing, position_limits, account, etc.)
        # don't break.
        from types import SimpleNamespace
        existing_finviz = getattr(
            getattr(cfg, "integrations", None), "finviz", None,
        )
        new_integrations = _IntegrationsCfgShim(
            schwab=_SchwabCfgShim(), finviz=existing_finviz,
        )
        # Build a SimpleNamespace that delegates to original cfg for all
        # other attributes while overriding `integrations`. The route
        # handler's downstream code reads cfg.position_limits / cfg.web /
        # cfg.risk / cfg.account / cfg.sizing / cfg.paths — preserve them.
        kwargs = {}
        for attr in (
            "paths", "account", "risk", "sizing", "position_limits",
            "web", "archive", "advisory",
        ):
            if hasattr(cfg, attr):
                kwargs[attr] = getattr(cfg, attr)
        kwargs["integrations"] = new_integrations
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(
        "swing.web.routes.trades.apply_overrides", fake_apply_overrides,
    )
    monkeypatch.setattr(
        "swing.web.view_models.trades.apply_overrides",
        fake_apply_overrides,
        raising=False,
    )


def test_entry_form_e2e_emits_schwab_audit_row_with_surface_trade_entry(
    seeded_db, monkeypatch,
):
    """E2E: GET /trades/entry/form fires a (mocked) Schwab Trader call;
    a schwab_api_calls row lands with surface='trade_entry' +
    signature_hash populated; the form renders with auto-populated
    values.
    """
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    _patch_cfg_for_production_schwab(monkeypatch)
    _patch_full_schwab_stack(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=AAPL")
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Form rendered with auto-populated entry_price + hidden anchor.
    assert 'value="150.25"' in body
    assert 'name="schwab_source_value_json"' in body

    # Audit row written.
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT surface, endpoint, status, environment, signature_hash, "
            "pipeline_run_id FROM schwab_api_calls "
            "ORDER BY call_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, (
        "schwab_api_calls audit row should be emitted by "
        "trader.get_account_orders for the entry auto-fill path"
    )
    surface, endpoint, status, env, sig_hash, pipeline_run_id = row
    assert surface == "trade_entry", (
        f"BINDING: surface MUST be 'trade_entry' at entry auto-fill path; "
        f"got {surface!r}"
    )
    assert endpoint == "accounts.orders.list"
    assert status == "success"
    assert env == "production"
    assert sig_hash is not None and sig_hash.strip(), (
        "signature_hash MUST be populated for drift detection"
    )
    assert pipeline_run_id is None, (
        "form-render fetch is NOT pipeline-bound"
    )


def test_entry_form_e2e_sandbox_does_not_emit_audit_row(seeded_db, monkeypatch):
    """E2E negative: under sandbox environment, NO Schwab call fires; NO
    audit row written; form still renders (with empty auto-fill +
    advisory banner)."""
    cfg, cfg_path = seeded_db
    _seed_watchlist_row(cfg, "AAPL")
    _patch_price_cache(monkeypatch)

    # Force sandbox via apply_overrides seam (cfg is frozen).
    from dataclasses import dataclass
    from types import SimpleNamespace

    @dataclass
    class _SchwabCfgShim:
        environment: str = "sandbox"
        client_id: str | None = None
        client_secret: str | None = None
        account_hash: str | None = None

    @dataclass
    class _IntegrationsCfgShim:
        schwab: _SchwabCfgShim
        finviz: Any = None

    def fake_apply_overrides(cfg):
        kwargs = {}
        for attr in (
            "paths", "account", "risk", "sizing", "position_limits",
            "web", "archive", "advisory",
        ):
            if hasattr(cfg, attr):
                kwargs[attr] = getattr(cfg, attr)
        kwargs["integrations"] = _IntegrationsCfgShim(schwab=_SchwabCfgShim())
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(
        "swing.web.routes.trades.apply_overrides", fake_apply_overrides,
    )

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/trades/entry/form?ticker=AAPL")
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Advisory banner present.
    assert "Schwab auto-fill:" in body
    assert "sandbox" in body.lower()

    # NO audit row.
    conn = connect(cfg.paths.db_path)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 0, (
        "sandbox short-circuit must NOT emit schwab_api_calls audit row"
    )


# ----------------------------------------------------------------------
# Path / sqlite3 import guards (silence ruff F401 if subsequent edits
# remove explicit usage).
# ----------------------------------------------------------------------
_ = Path
_ = sqlite3
