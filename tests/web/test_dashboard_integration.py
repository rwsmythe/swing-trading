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


def _seed_open_trade_direct(cfg, *, ticker: str, entry_price: float, shares: int) -> int:
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=entry_price, initial_shares=shares,
                initial_stop=entry_price * 0.95, current_stop=entry_price * 0.95,
                status="open", state="entered", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
            )
            return insert_trade_with_event(conn, trade, event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()


def test_get_dashboard_renders_sma_advisories_from_full_bundle(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §5.4: when OhlcvCache returns a full bundle, SMA50 EXIT rule
    fires and the advisory message appears in the rendered page."""
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = test_cfg
    _seed_open_trade_direct(cfg, ticker="AAPL", entry_price=180.0, shares=10)

    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: OhlcvBundle(sma10=198.0, sma20=196.0, sma50=195.0,
                            previous_close=190.0, fetched_at=0.0)
            for t in tickers
        },
    )
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "50MA" in r.text
    assert "$190.00" in r.text


def test_get_dashboard_absent_advisories_on_all_none_bundle(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §5.4: all-None bundle (deadline miss) → SMA advisories absent,
    but page still renders."""
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = test_cfg
    _seed_open_trade_direct(cfg, ticker="AAPL", entry_price=180.0, shares=10)

    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: OhlcvBundle.empty(fetched_at=0.0) for t in tickers
        },
    )
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "50MA" not in r.text


def test_get_dashboard_partial_bundle_sma10_only_renders_only_10ma_rules(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §5.4: a partial bundle (SMA10 only, rest None) → only 10MA rules
    fire. SMA20 and SMA50 rules silently no-op."""
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = test_cfg
    _seed_open_trade_direct(cfg, ticker="AAPL", entry_price=180.0, shares=10)

    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: OhlcvBundle(sma10=198.0, sma20=None, sma50=None,
                            previous_close=190.0, fetched_at=0.0)
            for t in tickers
        },
    )
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "10MA" in r.text
    assert "50MA" not in r.text
