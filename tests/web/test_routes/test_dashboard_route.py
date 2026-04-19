"""GET / returns 200 with expected snippets."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def _seed_minimal_dashboard_state(cfg):
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count, rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17', '2026-04-20',
                           NULL, 0, 0, 0, 0, 0, 0, 'v1', 'deadbeef')""",
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00', 'scheduled',
                           '2026-04-17', '2026-04-20', 'complete', 't')""",
            )
    finally:
        conn.close()


def test_get_root_renders(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)

    # Avoid hitting real yfinance.
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "Today's decisions" in r.text
    assert "Watchlist" in r.text
