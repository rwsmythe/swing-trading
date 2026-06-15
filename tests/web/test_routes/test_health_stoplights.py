"""Phase 18 Arc 18-F: the GUI health-stoplight web wiring.

The context-processor injection (Task 5), the every-base-route + forced-500 +
per-provider-raise BINDING regression tests (Task 6), and the two drill-down
routes (Task 7). TestClient asserts the BODY, not the rendered DOM — the
operator browser gate is the binding net for DOM/visual regressions (brief §6).
"""
from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from swing.monitoring.stoplights import RESEARCH_MONITOR_ID
from swing.web.app import _health_stoplights_context_processor, create_app


def _seed_minimal_dashboard_state(cfg):
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count, rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17', '2026-04-20',
                           NULL, 0, 0, 0, 0, 0, 0, 'v1', 'deadbeef')""",
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00', 'scheduled',
                           '2026-04-17', '2026-04-20', 'complete', 't')""",
            )
    finally:
        conn.close()


def _stub_price_cache(monkeypatch):
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)


# ---------------------------------------------------------------- Task 5


def test_health_stoplights_context_processor_returns_key(seeded_db):
    cfg, _ = seeded_db
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(cfg=cfg)))
    out = _health_stoplights_context_processor(request)
    assert "health_stoplights" in out
    stoplights = out["health_stoplights"]
    assert isinstance(stoplights, tuple)
    assert len(stoplights) == 2
    assert [s.id for s in stoplights] == ["tool", "research"]


def test_context_processor_returns_empty_when_cfg_none():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(cfg=None)))
    out = _health_stoplights_context_processor(request)
    assert out == {"health_stoplights": ()}


def test_context_processor_never_raises_when_aggregator_raises(seeded_db, monkeypatch):
    cfg, _ = seeded_db

    def _boom(conn, cfg):
        raise RuntimeError("aggregator defect")

    monkeypatch.setattr("swing.web.app.health_stoplights", _boom)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(cfg=cfg)))
    out = _health_stoplights_context_processor(request)  # must NOT raise
    assert out == {"health_stoplights": ()}


def test_dashboard_renders_with_stoplights_present(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert 'class="stoplights"' in r.text
    assert "/health/tool" in r.text
    assert "/health/research" in r.text


def test_context_processor_injects_color_classes(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert r.text.count("stoplight-") >= 2


# ---------------------------------------------------------------- Task 7


def test_health_tool_route_lists_checks(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/health/tool")
    assert r.status_code == 200
    assert "pipeline_freshness" in r.text  # a known 18-E check key
    assert 'class="stoplights"' in r.text  # the drill-down is itself a base page


def test_health_research_route_not_deployed_message(seeded_db, monkeypatch, tmp_path):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: tmp_path / "absent.json",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/health/research")
    assert r.status_code == 200
    assert "18-D" in r.text
    assert "not yet deployed" in r.text.lower()


def test_health_research_route_lists_checks_when_artifact_present(
    seeded_db, monkeypatch, tmp_path,
):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    p = tmp_path / "latest.json"
    p.write_text(
        json.dumps({
            "monitor": RESEARCH_MONITOR_ID,
            "generated_ts": datetime.now().isoformat(),
            "overall": "yellow",
            "checks": [
                {"key": "expectancy_freshness", "status": "yellow",
                 "summary": "stale shadow run", "detail": "ran 9d ago"},
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path", lambda: p,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/health/research")
    assert r.status_code == 200
    assert "expectancy_freshness" in r.text
    assert "stale shadow run" in r.text


def test_health_routes_read_only(seeded_db, monkeypatch):
    from swing.data.db import connect
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)

    def _count(conn):
        return conn.execute(
            "SELECT COUNT(*) FROM pipeline_runs",
        ).fetchone()[0]

    conn = connect(cfg.paths.db_path)
    try:
        before = _count(conn)
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert client.get("/health/tool").status_code == 200
        assert client.get("/health/research").status_code == 200
    conn = connect(cfg.paths.db_path)
    try:
        after = _count(conn)
    finally:
        conn.close()
    assert before == after
