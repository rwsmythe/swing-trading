"""Phase 10 Sub-bundle A T-A.8 — /metrics index page smoke tests.

Per-surface routes (Sub-bundles B/C/D/E) get their own test files when
they land. This file covers the umbrella `GET /metrics` only.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_metrics_index_returns_200(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    assert "Metrics dashboard" in r.text


def test_metrics_index_renders_all_8_surface_links(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    # Every plan §A.3 surface link must appear in the index.
    for href in (
        "/metrics/trade-process",
        "/metrics/hypothesis-progress",
        "/metrics/tier-comparison",
        "/metrics/capital-friction",
        "/metrics/maturity-stage",
        "/metrics/identification-funnel",
        "/metrics/deviation-outcome",
        "/metrics/process-grade-trend",
    ):
        assert href in r.text, f"missing surface link: {href}"


def test_metrics_index_extends_base_layout(seeded_db):
    """Response body contains the base-layout topbar (dashboard link + date)
    confirming the index template extends base.html.j2."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    # Topbar nav markers from base.html.j2.
    assert 'class="topbar"' in r.text
    assert "Dashboard" in r.text
    assert "Pipeline" in r.text


def test_metrics_index_registered_in_app_routes(seeded_db):
    """Confirm /metrics is registered in the app's route table (per CLAUDE.md
    'HX-Redirect target route must be verified to exist' gotcha family —
    apply pre-emptively to any new route landing). Sub-bundle A
    deliberately ships the navigator + the 8 surface tile links; tile
    targets 404 until B/C/D/E land per dispatch brief §2 S3."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    route_paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/metrics" in route_paths


def test_metrics_index_unresolved_material_field_populated(seeded_db):
    """VM constructor populates ``unresolved_material_discrepancies_count``
    eagerly from the discrepancies helper (plan §A.18 + §I.5 LOCK)."""
    import sqlite3

    from swing.web.view_models.metrics.index import build_metrics_index_vm

    cfg, _ = seeded_db
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        vm = build_metrics_index_vm(conn)
    finally:
        conn.close()
    # Empty DB has 0 unresolved-material discrepancies → field is 0.
    assert vm.unresolved_material_discrepancies_count == 0


def test_metrics_index_top_nav_link_in_base_layout(seeded_db):
    """`Metrics` link appears in topbar nav on any base-layout page (e.g., /)."""
    cfg, cfg_path = seeded_db
    # Seed minimal pipeline_runs row so / renders.
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count, rs_universe_version, rs_universe_hash)
                   VALUES ('2026-05-12T21:49:00', '2026-05-12', '2026-05-13',
                           NULL, 0, 0, 0, 0, 0, 0, 'v1', 'deadbeef')""",
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token)
                   VALUES ('2026-05-12T21:49:00', '2026-05-12T21:55:00', 'scheduled',
                           '2026-05-12', '2026-05-13', 'complete', 't')""",
            )
    finally:
        conn.close()

    from swing.web.price_cache import PriceCache

    import pytest as _pytest
    monkeypatch = _pytest.MonkeyPatch()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    monkeypatch.undo()
    assert r.status_code == 200
    assert 'href="/metrics"' in r.text
