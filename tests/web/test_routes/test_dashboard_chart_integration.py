"""Phase 13 T2.SB6b T-A.6.6 — Theme 1 chart surface integration tests.

Per plan G.9 T-A.6.6 Step 1: 8+ tests covering DashboardVM weather chart
+ watchlist/position chart bytes + POST /dashboard/weather-chart/refresh
HTMX 3-surface discipline (L12 LOCK) + dashboard TOP placement (L13 LOCK).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import ChartRender, Trade
from swing.data.repos.chart_renders import refresh_chart_render
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app
from swing.web.view_models.dashboard import build_dashboard


def _seed_complete_run(conn) -> int:
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, finished_ts, trigger, data_asof_date,
             action_session_date, state, lease_token)
        VALUES ('2026-05-20T09:00:00', '2026-05-20T09:05:00',
                'manual', '2026-05-19', '2026-05-20',
                'complete', 't-x')
        """
    )
    return int(cur.lastrowid)


def _seed_market_weather_cache(conn, *, run_id: int,
                                ticker: str = "SPY",
                                svg_text: str = "<svg>weather</svg>") -> None:
    refresh_chart_render(conn, ChartRender(
        id=None,
        ticker=ticker,
        surface="market_weather",
        chart_svg_bytes=svg_text.encode("utf-8"),
        source_data_hash="hash-w",
        rendered_at="2026-05-20T09:05:00",
        data_asof_date="2026-05-19",
        pipeline_run_id=run_id,
        pattern_class=None,
    ))


# ---------------------------------------------------------------------------
# Test 1: DashboardVM populates dashboard_weather_chart_svg_bytes from cache.
# ---------------------------------------------------------------------------


def test_dashboard_vm_populates_weather_chart_svg_bytes_from_cache(
    seeded_db,
):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_complete_run(conn)
            _seed_market_weather_cache(
                conn, run_id=run_id, ticker=cfg.rs.benchmark_ticker,
            )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # Hits the production dashboard route -> build_dashboard hooks the
        # cache read.
        r = client.get("/dashboard")
    assert r.status_code == 200
    assert "<svg>weather</svg>" in r.text


def test_dashboard_vm_weather_chart_none_when_no_cache_row(seeded_db):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_complete_run(conn)
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/dashboard")
    assert r.status_code == 200
    # Placeholder visible (no chart).
    assert "Market weather chart not yet available" in r.text


# ---------------------------------------------------------------------------
# Test 2: Dashboard renders weather chart at TOP (L13 LOCK).
# ---------------------------------------------------------------------------


def test_dashboard_renders_weather_chart_at_top_per_spec_section_4_5(
    seeded_db,
):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_complete_run(conn)
            _seed_market_weather_cache(
                conn, run_id=run_id, ticker=cfg.rs.benchmark_ticker,
            )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/dashboard")
    assert r.status_code == 200
    body = r.text
    # Weather chart section must appear BEFORE the status strip per spec
    # section 4.5 + plan section C.3 LOCK.
    weather_idx = body.find('id="dashboard-market-weather"')
    status_idx = body.find('id="status-strip"')
    assert weather_idx >= 0
    assert status_idx >= 0
    assert weather_idx < status_idx


# ---------------------------------------------------------------------------
# Test 3: watchlist row chart bytes populated per ticker.
# ---------------------------------------------------------------------------


def test_dashboard_vm_watchlist_chart_svg_bytes_populated_per_ticker(
    seeded_db,
):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_complete_run(conn)
            # Plant a watchlist entry + cache row.
            conn.execute(
                "INSERT INTO watchlist "
                "(ticker, added_date, last_qualified_date, status, "
                " qualification_count, not_qualified_streak, "
                " last_data_asof_date, last_close, last_adr_pct) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("WCH", "2026-05-01", "2026-05-19", "watch", 1, 0,
                 "2026-05-19", 100.0, 2.0),
            )
            refresh_chart_render(conn, ChartRender(
                id=None, ticker="WCH", surface="watchlist_row",
                chart_svg_bytes=b"<svg>wch</svg>",
                source_data_hash="h",
                rendered_at="2026-05-20T09:05:00",
                data_asof_date="2026-05-19",
                pipeline_run_id=run_id,
                pattern_class=None,
            ))
    finally:
        conn.close()
    class _StubPriceCache:
        def get_many(self, tickers, deadline_seconds, executor):
            return {}
        def is_degraded(self):
            return False
        def degraded_until(self):
            return None
    vm = build_dashboard(
        cfg=cfg, cache=_StubPriceCache(), executor=None, ohlcv_cache=None,
    )
    assert "WCH" in vm.watchlist_chart_svg_bytes
    assert vm.watchlist_chart_svg_bytes["WCH"] == b"<svg>wch</svg>"


# ---------------------------------------------------------------------------
# Test 4: position chart bytes populated for open trades.
# ---------------------------------------------------------------------------


def test_dashboard_vm_position_chart_svg_bytes_populated_for_open_trades(
    seeded_db,
):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_complete_run(conn)
            insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="POS",
                    entry_date="2026-05-18", entry_price=100.0,
                    initial_shares=10, initial_stop=90.0,
                    current_stop=90.0, state="entered",
                    watchlist_entry_target=None,
                    watchlist_initial_stop=None,
                    notes=None,
                    trade_origin="manual_off_pipeline",
                    pre_trade_locked_at="2026-05-18T09:30:00",
                    current_size=10.0,
                ),
                event_ts="2026-05-18T09:30:00",
            )
            # position_detail surface keys on (ticker, surface) with
            # pipeline_run_id=NULL per spec section C.2 cache key shape.
            refresh_chart_render(conn, ChartRender(
                id=None, ticker="POS", surface="position_detail",
                chart_svg_bytes=b"<svg>pos</svg>",
                source_data_hash="h",
                rendered_at="2026-05-20T09:05:00",
                data_asof_date="2026-05-19",
                pipeline_run_id=None,
                pattern_class=None,
            ))
    finally:
        conn.close()
    class _StubPriceCache:
        def get_many(self, tickers, deadline_seconds, executor):
            return {}
        def is_degraded(self):
            return False
        def degraded_until(self):
            return None
    vm = build_dashboard(
        cfg=cfg, cache=_StubPriceCache(), executor=None, ohlcv_cache=None,
    )
    assert "POS" in vm.position_chart_svg_bytes
    assert vm.position_chart_svg_bytes["POS"] == b"<svg>pos</svg>"


# ---------------------------------------------------------------------------
# Test 5: POST /dashboard/weather-chart/refresh 409 when no completed run.
# ---------------------------------------------------------------------------


def test_post_dashboard_weather_chart_refresh_409_when_no_completed_run(
    seeded_db,
):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/dashboard/weather-chart/refresh",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Test 6: HX-Redirect target /dashboard is registered in app.routes
#         (Phase 6 I3 LOCK).
# ---------------------------------------------------------------------------


def test_hx_redirect_target_dashboard_registered_in_app_routes(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    route_paths = {getattr(r, "path", None) for r in app.routes}
    assert "/dashboard" in route_paths


# ---------------------------------------------------------------------------
# Test 7: dashboard form carries hx-headers='{"HX-Request": "true"}'
#         propagation per Phase 5 R1 M1 LOCK.
# ---------------------------------------------------------------------------


def test_dashboard_weather_refresh_form_carries_hx_request_propagation(
    seeded_db,
):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/dashboard")
    assert r.status_code == 200
    body = r.text
    # Identify the form action target + the HX-Request header propagation.
    assert "/dashboard/weather-chart/refresh" in body
    # The hx-headers attribute appears on the form.
    assert 'hx-headers' in body
    assert "HX-Request" in body and "true" in body


# ---------------------------------------------------------------------------
# Test 8: POST refresh route is registered in app.routes (POST verb).
# ---------------------------------------------------------------------------


def test_post_dashboard_weather_chart_refresh_route_registered(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    matching = [
        r for r in app.routes
        if getattr(r, "path", None) == "/dashboard/weather-chart/refresh"
    ]
    assert matching, "POST /dashboard/weather-chart/refresh not registered"
    methods = set()
    for r in matching:
        methods |= getattr(r, "methods", set()) or set()
    assert "POST" in methods


# ---------------------------------------------------------------------------
# Test 9: Cache refresh helper consumes T2.SB6a substrate (production
#         path). Mock OhlcvCache to avoid network.
# ---------------------------------------------------------------------------


def test_post_dashboard_weather_chart_refresh_invalidates_and_regenerates(
    seeded_db, monkeypatch,
):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_complete_run(conn)
            # Seed a STALE cache row first.
            _seed_market_weather_cache(
                conn, run_id=run_id, ticker=cfg.rs.benchmark_ticker,
                svg_text="<svg>STALE</svg>",
            )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)

    # Stub OhlcvCache.get_or_fetch to return a synthetic DataFrame so we
    # avoid network. The renderer accepts a pandas DataFrame; build a
    # minimal one with Close + Volume columns + DatetimeIndex.
    import pandas as pd
    df = pd.DataFrame({
        "Open": [100.0, 101.0, 102.0],
        "High": [101.0, 102.0, 103.0],
        "Low": [99.0, 100.0, 101.0],
        "Close": [100.5, 101.5, 102.5],
        "Volume": [1000, 1100, 1200],
    }, index=pd.date_range("2026-05-15", periods=3, freq="D"))

    class _StubOhlcvCache:
        def get_or_fetch(self, tickers):
            return {t: df for t in tickers}
        def is_degraded(self):
            return False

    app.state.ohlcv_cache = _StubOhlcvCache()
    with TestClient(app) as client:
        r = client.post(
            "/dashboard/weather-chart/refresh",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204, r.text
    assert r.headers.get("HX-Redirect") == "/dashboard"

    # Cache row replaced with fresh content (no longer "STALE").
    conn = connect(cfg.paths.db_path)
    try:
        from swing.data.repos.chart_renders import get_cached_chart_svg
        svg = get_cached_chart_svg(
            conn, ticker=cfg.rs.benchmark_ticker,
            surface="market_weather",
            pipeline_run_id=run_id,
        )
    finally:
        conn.close()
    assert svg is not None
    assert b"STALE" not in svg
    # Real renderer emits SVG markup; just verify it's not empty + plausibly
    # SVG-shaped.
    assert b"<svg" in svg or b"<?xml" in svg
