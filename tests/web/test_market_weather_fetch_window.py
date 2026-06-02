"""Phase 14 close-out (A-1) — the dashboard weather-chart refresh handler
fetches >=200 trading bars (~300 calendar days) so the market-weather 200-MA
renders as a full line. Production-path: drives the REAL POST handler + REAL
render_market_weather_svg; only the OHLCV-fetch boundary is faked.
"""
from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

import swing.web.routes.dashboard as dash
from swing.data.db import connect
from swing.web.app import create_app
from swing.web.ohlcv_cache import MIN_CALENDAR_DAYS_FOR_MA200
from tests.web.test_routes.test_dashboard_chart_integration import (
    _seed_complete_run,
)


def _bars(rows: int = 260) -> pd.DataFrame:
    idx = pd.date_range(end="2026-05-27", periods=rows, freq="B")
    closes = [400.0 + i * 0.1 for i in range(rows)]
    return pd.DataFrame({
        "Open": closes, "High": [c + 1 for c in closes],
        "Low": [c - 1 for c in closes], "Close": closes,
        "Volume": [1_000_000] * rows,
    }, index=idx)


def test_weather_refresh_fetches_min_calendar_days_and_bars_reach_renderer(
    seeded_db, monkeypatch,
):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_complete_run(conn)
    finally:
        conn.close()

    captured: dict[str, int] = {}

    class _RecordingCache:
        def get_or_fetch(self, *, ticker, window_days=180):
            captured["window_days"] = window_days
            return _bars(260)
        def is_degraded(self):
            return False

    seen: dict[str, int] = {}
    real = dash.render_market_weather_svg

    def spy(*, bars, **kw):
        seen["bars_len"] = len(bars)
        return real(bars=bars, **kw)

    monkeypatch.setattr(dash, "render_market_weather_svg", spy)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        app.state.ohlcv_cache = _RecordingCache()
        resp = client.post(
            "/dashboard/weather-chart/refresh",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 204, resp.text
    assert captured["window_days"] == MIN_CALENDAR_DAYS_FOR_MA200
    # Binding (Codex M#5): >=200 bars REACH the renderer.
    assert seen["bars_len"] >= 200
