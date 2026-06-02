"""Phase 13 T2.SB6b T-A.6.6 -- Theme 1 chart surface integration tests.

Per plan G.9 T-A.6.6 Step 1: 8+ tests covering DashboardVM weather chart
+ watchlist/position chart bytes + POST /dashboard/weather-chart/refresh
HTMX 3-surface discipline (L12 LOCK) + dashboard TOP placement (L13 LOCK).

Phase 14 Sub-bundle 1 T-2.1 additions (V2.G4 weather-chart refresh signature
fix): ~8 regression tests for OhlcvCache.get_or_fetch(ticker=) call
discipline + narrow ValueError-only exception handling + programming-error
propagation to 500 (NOT 409).
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
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
        # Phase 14 Sub-bundle 1 T-2.1 V2.G4 fix: production signature is
        # `get_or_fetch(*, ticker: str)` returning a DataFrame (NOT a bundle
        # dict). Stub updated to match the production contract; pre-fix
        # stub returned a {ticker: df} dict via positional list which only
        # worked because the route's bare-except masked the TypeError.
        def get_or_fetch(self, *, ticker, window_days=180):
            return df
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


# ---------------------------------------------------------------------------
# Phase 14 Sub-bundle 1 T-2.1 V2.G4 weather-chart refresh signature regression
# tests. Per plan section G.T-2.1 + spec section 5.2 (R2.M2 narrow
# ValueError-only catch LOCK) + spec section 5.6 discriminating examples.
# ---------------------------------------------------------------------------


def _build_spy_bars_fixture() -> pd.DataFrame:
    """Production-shape DataFrame matching read_or_fetch_archive output:
    DatetimeIndex + capitalized Open/High/Low/Close/Volume columns."""
    idx = pd.DatetimeIndex(
        pd.date_range(end="2026-05-27", periods=60, freq="B"),
    )
    return pd.DataFrame({
        "Open": [400.0] * 60, "High": [405.0] * 60, "Low": [395.0] * 60,
        "Close": [402.0] * 60, "Volume": [1_000_000] * 60,
    }, index=idx)


def _make_app_with_pipeline_run(seeded_db):
    """Plant a completed pipeline_run row + return (app, cfg, cfg_path)."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_complete_run(conn)
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    return app, cfg, cfg_path


@pytest.fixture
def mocked_ohlcv_cache():
    """A MagicMock standing in for OhlcvCache; tests override return_value
    or side_effect to control the get_or_fetch call's outcome."""
    mock = MagicMock()
    mock.is_degraded = MagicMock(return_value=False)
    return mock


@pytest.fixture
def test_client_with_pipeline_run(seeded_db, mocked_ohlcv_cache):
    """TestClient with completed pipeline_run + monkeypatched OhlcvCache.
    Default raise_server_exceptions=True for happy-path + ValueError-degraded
    paths (which return clean HTTP responses).
    """
    app, _cfg, _cfg_path = _make_app_with_pipeline_run(seeded_db)
    app.state.ohlcv_cache = mocked_ohlcv_cache
    with TestClient(app) as client:
        # Re-install after lifespan (lifespan may reset app.state).
        app.state.ohlcv_cache = mocked_ohlcv_cache
        yield client


@pytest.fixture
def test_client_with_pipeline_run_no_raise(seeded_db, mocked_ohlcv_cache):
    """TestClient with raise_server_exceptions=False per Codex R1.M#3 LOCK.
    Required for TypeError/AttributeError/KeyError/RuntimeError propagation
    tests; the default TestClient re-raises uncaught exceptions into the
    test runner instead of yielding a 500 response.
    """
    app, _cfg, _cfg_path = _make_app_with_pipeline_run(seeded_db)
    app.state.ohlcv_cache = mocked_ohlcv_cache
    with TestClient(app, raise_server_exceptions=False) as client:
        app.state.ohlcv_cache = mocked_ohlcv_cache
        yield client


@pytest.fixture
def test_client_no_pipeline_run(seeded_db, mocked_ohlcv_cache):
    """TestClient WITHOUT a pipeline_run row (regression check that the
    no-completed-pipeline 409 message is unchanged post-fix)."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    app.state.ohlcv_cache = mocked_ohlcv_cache
    with TestClient(app) as client:
        app.state.ohlcv_cache = mocked_ohlcv_cache
        yield client


def test_weather_refresh_calls_get_or_fetch_with_ticker_kwarg(
    test_client_with_pipeline_run, mocked_ohlcv_cache,
):
    """V2.G4 root cause: get_or_fetch is keyword-only; pre-fix handler
    passed a positional list which raised TypeError silently swallowed
    by bare except Exception. Post-fix: kwarg-style call only."""
    mocked_ohlcv_cache.get_or_fetch.return_value = _build_spy_bars_fixture()
    test_client_with_pipeline_run.post(
        "/dashboard/weather-chart/refresh",
        headers={"HX-Request": "true"},
    )
    mocked_ohlcv_cache.get_or_fetch.assert_called_once()
    call_args = mocked_ohlcv_cache.get_or_fetch.call_args.args
    call_kwargs = mocked_ohlcv_cache.get_or_fetch.call_args.kwargs
    assert call_args == (), (
        "get_or_fetch must be invoked with KEYWORD ticker= argument, "
        "not positional list (V2.G4 root cause)"
    )
    # Phase 14 close-out (A-1): the refresh now also passes the widened
    # window_days so the market-weather 200-MA has enough bars.
    from swing.web.ohlcv_cache import MIN_CALENDAR_DAYS_FOR_MA200
    assert call_kwargs == {
        "ticker": "SPY", "window_days": MIN_CALENDAR_DAYS_FOR_MA200,
    }


def test_value_error_degraded_path_logs_warning_and_returns_409(
    test_client_with_pipeline_run, mocked_ohlcv_cache, caplog,
):
    """ValueError from get_or_fetch is the canonical empty-archive signal;
    handler logs warning + returns 409 with operator-friendly message
    (spec section 5.2 R2.M2 ValueError-only narrow catch LOCK)."""
    mocked_ohlcv_cache.get_or_fetch.side_effect = ValueError(
        "No data for SPY",
    )
    with caplog.at_level(
        logging.WARNING, logger="swing.web.routes.dashboard",
    ):
        response = test_client_with_pipeline_run.post(
            "/dashboard/weather-chart/refresh",
        headers={"HX-Request": "true"},
        )
    assert response.status_code == 409
    # 409 banner HTML escapes the apostrophe in the benchmark ticker name.
    assert "no OHLCV bars available for benchmark" in response.text
    assert "SPY" in response.text
    # log.warning emitted with the benchmark ticker name for operator
    # grep-reachability.
    assert any(
        "weather-chart refresh" in rec.message and "SPY" in rec.message
        for rec in caplog.records
    )


def test_type_error_propagates_to_500_not_409(
    test_client_with_pipeline_run_no_raise, mocked_ohlcv_cache,
):
    """Programming errors (TypeError) propagate to FastAPI default 500
    handler -- they MUST NOT be silently masked as a misleading 409
    (R2.M2 LOCK; this is the V2.G4 root-cause-class regression check).

    Per Codex R1.M#3 LOCK: TestClient is constructed with
    raise_server_exceptions=False so the server-side 500 response is
    observable. Default TestClient would re-raise the TypeError into the
    test runner rather than yield a 500.
    """
    mocked_ohlcv_cache.get_or_fetch.side_effect = TypeError(
        "Simulated programming error -- e.g., positional vs keyword "
        "signature drift.",
    )
    response = test_client_with_pipeline_run_no_raise.post(
        "/dashboard/weather-chart/refresh",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 500
    assert "no OHLCV bars" not in response.text


@pytest.mark.parametrize(
    "exc_type, exc_args",
    [
        (AttributeError, ("simulated attr error",)),
        (KeyError, ("simulated key error",)),
        (RuntimeError, ("simulated runtime error",)),
    ],
)
def test_other_programming_errors_propagate_to_500(
    test_client_with_pipeline_run_no_raise, mocked_ohlcv_cache,
    exc_type, exc_args,
):
    """AttributeError, KeyError, RuntimeError all propagate as 500
    (forward-binding lesson #8 -- narrow ValueError-only catch ensures
    programming errors are NOT silently masked).

    Per Codex R1.M#3 LOCK: TestClient(raise_server_exceptions=False)
    fixture so the 500 server-side response is observable.
    """
    mocked_ohlcv_cache.get_or_fetch.side_effect = exc_type(*exc_args)
    response = test_client_with_pipeline_run_no_raise.post(
        "/dashboard/weather-chart/refresh",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 500


def test_happy_path_returns_204_with_hx_redirect_and_writes_chart_render(
    test_client_with_pipeline_run, mocked_ohlcv_cache, seeded_db,
):
    """Happy path: SPY bars in cache -> 204 + HX-Redirect: /dashboard +
    chart_renders row written (spec section 5.6 example #1)."""
    cfg, _ = seeded_db
    mocked_ohlcv_cache.get_or_fetch.return_value = _build_spy_bars_fixture()
    response = test_client_with_pipeline_run.post(
        "/dashboard/weather-chart/refresh",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 204, response.text
    assert response.headers.get("HX-Redirect") == "/dashboard"
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM chart_renders "
            "WHERE ticker='SPY' AND surface='market_weather'",
        ).fetchone()
        assert row[0] >= 1
    finally:
        conn.close()


def test_htmx_trinity_preserved_for_weather_chart_refresh(
    test_client_with_pipeline_run, mocked_ohlcv_cache, seeded_db,
):
    """Forward-binding lesson #7: weather-chart/refresh HTMX trinity
    PRESERVED post-V2.G4 fix:
      (a) /dashboard target route registered;
      (b) success response 204 + HX-Redirect (NOT 303 swap-target);
      (c) embedded form HX-Request header propagation (verified by
          checking dashboard.html.j2 still emits hx-headers).
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    # (a) Target route registered.
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/dashboard" in paths
    # (b) Success response shape.
    mocked_ohlcv_cache.get_or_fetch.return_value = _build_spy_bars_fixture()
    response = test_client_with_pipeline_run.post(
        "/dashboard/weather-chart/refresh",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 204
    assert "HX-Redirect" in response.headers
    # (c) Embedded form HX-Request propagation -- inspect template source.
    # swing.web.templates is a namespace package (no __init__.py); use
    # __path__ rather than __file__.
    import swing.web.templates as tpl_mod
    tpl_root = Path(list(tpl_mod.__path__)[0])
    tpl_path = tpl_root / "dashboard.html.j2"
    src = tpl_path.read_text(encoding="utf-8")
    assert "hx-headers" in src
    assert '"HX-Request"' in src


def test_no_pipeline_run_returns_existing_409_unchanged(
    test_client_no_pipeline_run, mocked_ohlcv_cache,
):
    """Empty pipeline_runs table -> existing 409 'no completed pipeline_run'
    message (UNCHANGED from pre-fix behavior; regression check)."""
    response = test_client_no_pipeline_run.post(
        "/dashboard/weather-chart/refresh",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 409
    assert "no completed pipeline_run" in response.text


def test_dashboard_route_module_ascii_only():
    """Per gotcha #32 + spec section 15.2 -- route module ASCII-only."""
    import swing.web.routes.dashboard as mod
    Path(mod.__file__).read_text(encoding="utf-8").encode("ascii")
