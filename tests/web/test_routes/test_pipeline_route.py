"""GET /pipeline route."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app


def _seed_pipeline_history(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.executemany(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token)
                   VALUES (?, ?, 'scheduled', ?, ?, 'complete', ?)""",
                [
                    ("2026-04-17T21:49:00", "2026-04-17T21:55:00", "2026-04-17", "2026-04-20", "tok-1"),
                    ("2026-04-16T21:49:00", "2026-04-16T21:55:00", "2026-04-16", "2026-04-17", "tok-2"),
                ],
            )
    finally:
        conn.close()


def test_get_pipeline_page(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_pipeline_history(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline")
    assert r.status_code == 200
    assert "tok-1" in r.text or "2026-04-17" in r.text
    assert "Run now" in r.text


def test_post_pipeline_run_spawns_subprocess(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    spawned = {}

    class FakeProc:
        pid = 4242
        returncode = None
        def poll(self):
            return None  # still running

    def fake_popen(cmd, **kwargs):
        spawned["cmd"] = cmd
        # Simulate the child acquiring the lease immediately.
        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                conn.execute(
                    """INSERT INTO pipeline_runs
                       (started_ts, trigger, data_asof_date, action_session_date,
                        state, lease_token, lease_heartbeat_ts)
                       VALUES (?, 'manual', '2026-04-17', '2026-04-20',
                               'running', 'subprocess-tok', ?)""",
                    (datetime.now().isoformat(timespec='seconds'),
                     datetime.now().isoformat(timespec='seconds')),
                )
        finally:
            conn.close()
        return FakeProc()

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/pipeline/run", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "cmd" in spawned
    assert "--config" in spawned["cmd"]
    assert str(cfg_path) in spawned["cmd"]
    assert "pipeline" in spawned["cmd"]
    assert "run" in spawned["cmd"]
    assert "--manual" in spawned["cmd"]
    assert "pipeline-progress" in r.text or "state" in r.text.lower()


def test_post_pipeline_run_503_when_cfg_path_missing(seeded_db):
    cfg, _ = seeded_db
    app = create_app(cfg, None)
    with TestClient(app) as client:
        r = client.post("/pipeline/run", headers={"HX-Request": "true"})
    assert r.status_code == 503
    assert "config" in r.text.lower()


def test_post_pipeline_run_detects_stale_heartbeat(seeded_db):
    cfg, cfg_path = seeded_db
    stale_ts = (datetime.now() - timedelta(seconds=900)).isoformat(timespec="seconds")
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token, lease_heartbeat_ts)
                   VALUES (?, 'scheduled', '2026-04-17', '2026-04-20',
                           'running', 'stale-tok', ?)""",
                (stale_ts, stale_ts),
            )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/pipeline/run", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "force-clear" in r.text.lower() or "stuck" in r.text.lower()


def test_post_pipeline_run_detects_early_child_exit(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db

    class FakeProc:
        pid = 5252
        returncode = 1
        def poll(self):
            return 1  # exited immediately with code 1

    monkeypatch.setattr("subprocess.Popen", lambda cmd, **kw: FakeProc())

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/pipeline/run", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "exited early" in r.text.lower() or "code=1" in r.text


def test_pipeline_status_running_keeps_trigger(seeded_db):
    cfg, cfg_path = seeded_db
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (id, started_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token, lease_heartbeat_ts, current_step)
                   VALUES (99, '2026-04-17T21:49:00', 'manual', '2026-04-17',
                           '2026-04-20', 'running', 'tok', '2026-04-17T21:49:00',
                           'evaluate')""",
            )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline/status/99", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "hx-trigger" in r.text.lower()
    assert "evaluate" in r.text


def test_pipeline_status_complete_drops_trigger(seeded_db):
    cfg, cfg_path = seeded_db
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (id, started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token)
                   VALUES (100, '2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'manual', '2026-04-17', '2026-04-20', 'complete', 'tok')""",
            )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline/status/100", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "hx-trigger" not in r.text.lower()
    assert "complete" in r.text.lower()


def test_pipeline_status_missing_returns_error(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline/status/99999", headers={"HX-Request": "true"})
    assert r.status_code == 404


def test_post_prices_refresh_emits_three_oob_regions(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    from swing.web.price_cache import PriceCache
    calls = {"refresh": 0, "reset": 0}
    orig_refresh = PriceCache.refresh_all
    orig_reset = PriceCache.reset_circuit_breaker
    def wrapped_refresh(self, tickers):
        calls["refresh"] += 1
        return orig_refresh(self, tickers)
    def wrapped_reset(self):
        calls["reset"] += 1
        return orig_reset(self)
    monkeypatch.setattr(PriceCache, "refresh_all", wrapped_refresh)
    monkeypatch.setattr(PriceCache, "reset_circuit_breaker", wrapped_reset)
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/prices/refresh", headers={"HX-Request": "true"})
    assert r.status_code == 200
    # Three oob containers with the expected IDs.
    for marker in ("status-strip", "open-positions", "watchlist-top5"):
        assert f'id="{marker}"' in r.text
    assert "hx-swap-oob" in r.text
    assert calls["refresh"] == 1
    # Manual refresh resets the breaker (R2 Major 2).
    assert calls["reset"] == 1


def test_post_prices_refresh_bypasses_degraded_mode(seeded_db, monkeypatch):
    """User-clicked Refresh now must force a live-fetch attempt even when
    the breaker is tripped. This test narrowly asserts that
    `reset_circuit_breaker` WAS called before `refresh_all` rebuilds the
    VM — it does NOT assert the breaker stays un-tripped after the route
    returns, because the rebuild might immediately re-trip on a fresh
    fetch failure (that is correct behavior and independent of the
    bypass-on-refresh contract) — R3 Minor 1."""
    cfg, cfg_path = seeded_db
    from swing.web.price_cache import PriceCache

    call_order: list[str] = []
    orig_reset = PriceCache.reset_circuit_breaker
    orig_refresh = PriceCache.refresh_all

    def wrapped_reset(self):
        call_order.append("reset")
        return orig_reset(self)

    def wrapped_refresh(self, tickers):
        call_order.append("refresh")
        return orig_refresh(self, tickers)

    monkeypatch.setattr(PriceCache, "reset_circuit_breaker", wrapped_reset)
    monkeypatch.setattr(PriceCache, "refresh_all", wrapped_refresh)
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    # Trip the breaker on the app's cache.
    for _ in range(20):
        app.state.price_cache._record_outcome(success=False)
    app.state.price_cache._maybe_trip_breaker()
    assert app.state.price_cache.is_degraded()

    with TestClient(app) as client:
        r = client.post("/prices/refresh", headers={"HX-Request": "true"})
    assert r.status_code == 200
    # Reset was called BEFORE refresh (operator override before re-populate).
    assert call_order[:2] == ["reset", "refresh"], (
        f"expected reset then refresh, got {call_order}"
    )
