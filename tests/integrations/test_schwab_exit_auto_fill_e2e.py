"""Phase 13 T3.SB2 T-B.2.4 — slow Schwab exit auto-fill E2E (cassette-backed).

SELL-side mirror of ``tests/integrations/test_schwab_entry_auto_fill_e2e.py``
(T3.SB1 T-B.1.5). Consumes the operator-recorded Schwab cassette at
``tests/integrations/cassettes/schwab/test_e2e_limit_sell.yaml`` (recorded
2026-05-16 per post-Phase-12 Sub-bundle 1; sanitized via
``tests/conftest.py:vcr_config``). Extracts a FILLED LIMIT SELL order from
the cassette via the SAME helper precedent established at
``tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py``, maps
it through the production
``swing.integrations.schwab.mappers.map_orders_to_fill_candidates`` to
obtain a production-shape ``SchwabOrderResponse`` (closes the CLAUDE.md
"Synthetic-fixture-vs-production-emitter shape drift" gotcha family —
fixture derives from real Schwab API response shape via the real mapper,
NOT hand-authored), then stubs ``trader.get_account_orders`` to return
that mapped object on the form-render Schwab fetch path.

Per plan §G.5 T-B.2.4 step 1:

  - Replay cassette; invoke ``GET /trades/{id}/exit/form`` against an open
    trade fixture; assert response renders with expected auto_fill values
    derived from the cassette response;
  - Assert audit row written with ``surface='trade_exit'`` +
    ``signature_hash`` populated (Phase 11 Sub-bundle B drift-detection
    contract).

The cassette E2E also exercises the production sanitization filter chain
indirectly: the cassette file ON DISK already carries sanitized
``<REDACTED>`` placeholders for ``accountNumber`` + ``<account>`` URI
segments (verified by reading the cassette at this file's authoring time).
Any future cassette re-recording via ``scripts/record_schwab_cassettes.py``
re-runs ``tests/conftest.py:vcr_config`` filters + the sentinel-leak audit.

Marked slow because the test exercises (a) cassette load + YAML parse,
(b) full TestClient lifespan + (c) full Schwab integration ladder.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

try:
    import yaml as _yaml
except ImportError:
    _yaml = None  # type: ignore[assignment]

from fastapi.testclient import TestClient

from swing.data.db import connect, ensure_schema
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event, list_open_trades
from swing.integrations.schwab.mappers import map_orders_to_fill_candidates
from swing.integrations.schwab.models import SchwabOrderResponse
from swing.web.app import create_app
from swing.web.price_cache import PriceCache

pytestmark = pytest.mark.slow


_CASSETTE_PATH = (
    Path(__file__).resolve().parent
    / "cassettes" / "schwab" / "test_e2e_limit_sell.yaml"
)


# ----------------------------------------------------------------------
# Cassette load + first-matching-SELL extraction helpers (mirror the
# precedent at tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py).
# ----------------------------------------------------------------------


def _load_cassette_orders(cassette_path: Path) -> list[dict[str, Any]]:
    """Load a vcrpy YAML cassette + return the response body's `orders` list."""
    if _yaml is None:
        pytest.skip("PyYAML not installed; cassette load skipped")
    if not cassette_path.exists():
        pytest.skip(f"cassette absent: {cassette_path.name}")
    with cassette_path.open(encoding="utf-8") as f:
        cassette = _yaml.safe_load(f)
    interactions = cassette.get("interactions", [])
    if not interactions:
        pytest.skip(f"cassette {cassette_path.name} has zero interactions")
    body_str = interactions[0]["response"]["body"]["string"]
    return json.loads(body_str)


def _first_filled_sell_with_legs(
    orders: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find the first FILLED LIMIT SELL order carrying executionLegs[].

    Mirrors the predicate at
    ``tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py``
    but restricted to the SELL family (the exit auto-fill surface).
    """
    for order in orders:
        if not isinstance(order, dict):
            continue
        if order.get("status") != "FILLED":
            continue
        if order.get("orderType") not in ("LIMIT",):
            continue
        legs = order.get("orderLegCollection", [])
        if not isinstance(legs, list) or not legs:
            continue
        leg0 = legs[0] if isinstance(legs[0], dict) else {}
        if leg0.get("instruction") not in ("SELL", "SELL_TO_CLOSE"):
            continue
        activities = order.get("orderActivityCollection", [])
        if not isinstance(activities, list):
            continue
        for act in activities:
            if not isinstance(act, dict):
                continue
            if act.get("activityType") != "EXECUTION":
                continue
            exec_legs = act.get("executionLegs", [])
            if isinstance(exec_legs, list) and len(exec_legs) >= 1:
                return order
    return None


# ----------------------------------------------------------------------
# Fixture: seeded_db (mirror tests/web/conftest.py shape without
# cross-package import dependency, per T3.SB1 E2E precedent).
# ----------------------------------------------------------------------


@pytest.fixture
def seeded_db(tmp_path: Path) -> Any:
    """Local seeded_db fixture — mirrors the T3.SB1 E2E pattern at
    tests/integrations/test_schwab_entry_auto_fill_e2e.py."""
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


# ----------------------------------------------------------------------
# Patch helpers — mirror T3.SB1 _patch_price_cache + _patch_cfg_for_production_schwab
# + _patch_full_schwab_stack patterns.
# ----------------------------------------------------------------------


def _patch_price_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _patch_cfg_for_production_schwab(
    monkeypatch: pytest.MonkeyPatch,
    *,
    environment: str = "production",
    account_hash: str | None = "shim-account-hash",
) -> None:
    """Shim apply_overrides so the exit_form route handler sees a cfg with
    integrations.schwab.environment + account_hash populated. Mirrors the
    T3.SB1 E2E precedent verbatim.

    Note: parameters captured into a plain types.SimpleNamespace (NOT a
    dataclass with defaults) to avoid the class-body-closure NameError
    that fires when a dataclass field default references an outer
    function parameter.
    """
    from types import SimpleNamespace

    def fake_apply_overrides(cfg):
        existing_finviz = getattr(
            getattr(cfg, "integrations", None), "finviz", None,
        )
        schwab_shim = SimpleNamespace(
            environment=environment,
            client_id="shim-client-id",
            client_secret="shim-client-secret",
            account_hash=account_hash,
        )
        new_integrations = SimpleNamespace(
            schwab=schwab_shim, finviz=existing_finviz,
        )
        kwargs: dict[str, Any] = {}
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


def _patch_full_schwab_stack(
    monkeypatch: pytest.MonkeyPatch,
    *,
    orders: list[SchwabOrderResponse],
) -> None:
    """Stub the entire Schwab integration ladder so resolve_exit_auto_fill
    reaches trader.get_account_orders via the real call chain. Mirrors the
    T3.SB1 E2E _patch_full_schwab_stack precedent, but BINDS to the
    exit_auto_fill module's import names.
    """
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
            signature_hash="sha256:exit-e2e-cassette-signature-hash",
            status="success", error_message=None,
        )
        return list(orders)

    monkeypatch.setattr(
        "swing.trades.exit_auto_fill.trader.get_account_orders",
        fake_get_account_orders,
    )


def _seed_open_trade_for_ticker(
    cfg: Any, *, ticker: str, entry_date: str, entry_price: float,
    initial_shares: int,
) -> int:
    """Seed a single open trade for ``ticker`` whose ``entry_date``
    bounds the Schwab lookback window such that the cassette's SELL fill
    will be inside the window."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker=ticker, entry_date=entry_date,
                    entry_price=entry_price,
                    initial_shares=initial_shares,
                    initial_stop=entry_price * 0.9,
                    current_stop=entry_price * 0.9,
                    state="entered",
                    watchlist_entry_target=None,
                    watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts=f"{entry_date}T09:30:00",
            )
        trade = list_open_trades(conn)[0]
        return int(trade.id)
    finally:
        conn.close()


# ----------------------------------------------------------------------
# E2E test — cassette-derived production-shape SELL fill flows through
# the exit_form route + audit row lands with surface='trade_exit'.
# ----------------------------------------------------------------------


def test_exit_form_e2e_via_limit_sell_cassette_emits_schwab_audit_row(
    seeded_db, monkeypatch,
):
    """E2E: load the operator-recorded LIMIT SELL cassette; extract the
    first FILLED SELL via the production mapper; stub
    trader.get_account_orders to return it; invoke GET /trades/{id}/exit/form;
    assert the form renders with auto-populated exit_price from the
    cassette's execution-grain price + audit row lands with
    surface='trade_exit' + signature_hash populated.
    """
    # ------------------------------------------------------------------
    # Cassette extraction — production-shape via real mapper (closes the
    # synthetic-fixture-vs-production-emitter shape drift gotcha).
    # ------------------------------------------------------------------
    raw_orders = _load_cassette_orders(_CASSETTE_PATH)
    raw_sell = _first_filled_sell_with_legs(raw_orders)
    if raw_sell is None:
        pytest.skip(
            "cassette contains no FILLED LIMIT SELL with executionLegs[]; "
            "re-record via scripts/record_schwab_cassettes.py"
        )
    mapped = map_orders_to_fill_candidates([raw_sell])
    assert len(mapped) == 1, (
        f"mapper produced {len(mapped)} fills from 1 raw order; expected 1"
    )
    so = mapped[0]
    assert so.executions is not None and len(so.executions) >= 1, (
        "mapped SchwabOrderResponse must carry executions[] for the "
        "E2E to exercise the execution-grain price path"
    )
    cassette_ticker = so.instrument_symbol
    cassette_exec_price = float(so.executions[0].price)
    cassette_exec_qty = int(so.executions[0].quantity)
    assert cassette_exec_price > 0
    assert cassette_exec_qty > 0

    # ------------------------------------------------------------------
    # Trade seeding — entry well before the cassette fill so the lookback
    # window (entry_date → now) admits it. The cassette's most-recent
    # SELL fills occurred ~2026-05-14; seed entry at 2026-04-01.
    # ------------------------------------------------------------------
    cfg, cfg_path = seeded_db
    trade_id = _seed_open_trade_for_ticker(
        cfg,
        ticker=cassette_ticker,
        entry_date="2026-04-01",
        entry_price=100.0,
        initial_shares=cassette_exec_qty,
    )

    _patch_price_cache(monkeypatch)
    _patch_cfg_for_production_schwab(monkeypatch)
    _patch_full_schwab_stack(monkeypatch, orders=[so])

    # ------------------------------------------------------------------
    # Drive the exit_form route.
    # ------------------------------------------------------------------
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(f"/trades/{trade_id}/exit/form")
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Form rendered with auto-populated exit_price (formatted to 2 dp by
    # the template's '%.2f' filter; assert the formatted value present).
    expected_price_str = f"{cassette_exec_price:.2f}"
    assert f'value="{expected_price_str}"' in body, (
        f"expected formatted price {expected_price_str!r} in form body; "
        f"got body excerpt: {body[:500]!r}..."
    )
    # Hidden anchor present (the form-render path stamped it).
    assert 'name="schwab_source_value_json"' in body
    assert 'name="auto_fill_audit_at"' in body
    assert 'name="fill_origin_at_form_render"' in body

    # ------------------------------------------------------------------
    # Audit row contract — surface='trade_exit' + signature_hash populated
    # + environment=production + pipeline_run_id NULL (form-render fetch
    # is not pipeline-bound).
    # ------------------------------------------------------------------
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
        "trader.get_account_orders for the exit auto-fill path"
    )
    surface, endpoint, status, env, sig_hash, pipeline_run_id = row
    assert surface == "trade_exit", (
        f"BINDING: surface MUST be 'trade_exit' at exit auto-fill path; "
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


# ----------------------------------------------------------------------
# E2E negative — sandbox short-circuit emits NO Schwab call + NO audit row.
# (Symmetric counterpart of T3.SB1 entry sandbox negative test.)
# ----------------------------------------------------------------------


def test_exit_form_e2e_sandbox_does_not_emit_audit_row(
    seeded_db, monkeypatch,
):
    """E2E negative: under sandbox environment, NO Schwab call fires; NO
    audit row written; form still renders (with advisory banner)."""
    cfg, cfg_path = seeded_db
    # Any ticker works for the sandbox short-circuit path.
    trade_id = _seed_open_trade_for_ticker(
        cfg,
        ticker="AAPL",
        entry_date="2026-04-01",
        entry_price=150.0,
        initial_shares=10,
    )
    _patch_price_cache(monkeypatch)
    _patch_cfg_for_production_schwab(
        monkeypatch, environment="sandbox", account_hash=None,
    )

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(f"/trades/{trade_id}/exit/form")
    assert resp.status_code == 200, resp.text
    body = resp.text

    # Advisory text mentions sandbox.
    assert "sandbox" in body.lower(), (
        "sandbox short-circuit advisory text must surface in form body"
    )

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
