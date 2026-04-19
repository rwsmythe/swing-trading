"""GET /pipeline route."""
from __future__ import annotations

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
