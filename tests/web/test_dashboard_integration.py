"""Full dashboard integration smoke + 3 stale-banner scenarios."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app


def _seed_evaluation(cfg, *, data_asof: str, action_session: str) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count, rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 'v1', 'hash')""",
                ("2026-04-17T21:49:00", data_asof, action_session),
            )
            return cur.lastrowid
    finally:
        conn.close()


def _seed_pipeline_run(cfg, *, state: str, action_session: str) -> None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token)
                   VALUES (?, ?, 'scheduled', ?, ?, ?, ?)""",
                ("2026-04-17T21:49:00", "2026-04-17T21:55:00",
                 "2026-04-17", action_session, state, "tok"),
            )
    finally:
        conn.close()


def test_dashboard_no_stale_banner_when_run_is_current(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    from datetime import datetime

    from swing.evaluation.dates import action_session_for_run
    current_session = action_session_for_run(datetime.now()).isoformat()

    _seed_evaluation(cfg, data_asof="2026-04-17", action_session=current_session)
    _seed_pipeline_run(cfg, state="complete", action_session=current_session)

    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "banner-stale" not in r.text


def test_dashboard_shows_stale_banner_when_run_is_old(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_pipeline_run(cfg, state="complete", action_session="1999-01-01")

    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "banner-stale" in r.text


def test_dashboard_renders_degraded_banner_when_cache_degraded(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db

    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: True)
    from datetime import datetime, timedelta
    fake_until = datetime.now() + timedelta(seconds=30)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: fake_until)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "banner-degraded" in r.text
