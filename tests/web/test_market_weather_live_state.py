"""F-2 production-path regression: the market-weather trend state is computed
LIVE from fetched bars (structural_stage), so a healthy uptrend benchmark
classifies as DEFINED (stage_2) -- NOT 'undefined'. Exercises the real
fetch -> closes -> structural_stage wiring at BOTH live sites (web refresh +
pipeline _step_charts), not a stubbed current_stage (Codex R1 Major #5)."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import swing.pipeline.runner as runner_mod
import swing.web.routes.dashboard as dash_mod
from swing.data.db import connect
from swing.evaluation.criteria.trend_template import structural_stage
from swing.web.app import create_app
from swing.web.ohlcv_cache import (
    MIN_CALENDAR_DAYS_FOR_MA200,
    MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE,
    slice_recent_calendar_days,
)
from tests.web.test_routes.test_dashboard_chart_integration import (
    _seed_complete_run,
)


def _uptrend_frame(n: int) -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-05-27", periods=n)
    close = np.linspace(100.0, 300.0, n)
    return pd.DataFrame(
        {"Open": close, "High": close * 1.01, "Low": close * 0.99,
         "Close": close, "Volume": np.full(n, 1_000_000.0)},
        index=idx,
    )


# ---------------------------------------------------------------------------
# Live-compute unit assertions.
# ---------------------------------------------------------------------------


def test_uptrend_classifies_stage_2():
    bars = _uptrend_frame(260)
    assert structural_stage(bars["Close"], rising_period=21) == "stage_2"


def test_short_history_classifies_undefined():
    bars = _uptrend_frame(150)
    assert structural_stage(bars["Close"], rising_period=21) == "undefined"


def test_compute_window_wider_than_display_window():
    assert MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE > MIN_CALENDAR_DAYS_FOR_MA200


def test_display_slice_narrows_compute_frame_anchored_on_last_bar():
    bars = _uptrend_frame(300)  # ~300 business days spans > 300 calendar days
    display = slice_recent_calendar_days(bars, window_days=MIN_CALENDAR_DAYS_FOR_MA200)
    assert len(display) <= len(bars)
    assert not display.empty
    # The display tail anchors at the SAME last bar as the compute frame.
    assert display.index[-1] == bars.index[-1]


def test_display_slice_safe_on_stale_lagging_frame():
    # A frame whose last bar is several days in the past (cache lag): the slice
    # must still be non-empty and end on the same last bar (Codex R1 Major #4).
    bars = _uptrend_frame(260)
    display = slice_recent_calendar_days(bars, window_days=MIN_CALENDAR_DAYS_FOR_MA200)
    assert not display.empty
    assert display.index[-1] == bars.index[-1]


# ---------------------------------------------------------------------------
# Web-route call-site: REAL fetch -> REAL structural_stage -> renderer (no
# sentinel). 204 + HX-Redirect; spy the renderer (the route persists, does NOT
# return the SVG).
# ---------------------------------------------------------------------------


def _make_refresh_app(seeded_db):
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_complete_run(conn)
    finally:
        conn.close()
    return create_app(cfg, cfg_path), cfg


class _UptrendCache:
    def get_or_fetch(self, *, ticker, window_days):
        return _uptrend_frame(260)

    def is_degraded(self):
        return False


def test_dashboard_refresh_route_computes_defined_trend(seeded_db, monkeypatch):
    app, _cfg = _make_refresh_app(seeded_db)
    captured: dict = {}

    def _spy_render(*, bars, trend_template_state):
        captured["state"] = trend_template_state
        return b"<svg/>"

    monkeypatch.setattr(dash_mod, "render_market_weather_svg", _spy_render)
    with TestClient(app) as client:
        app.state.ohlcv_cache = _UptrendCache()
        resp = client.post(
            "/dashboard/weather-chart/refresh",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 204, resp.text  # 204 + HX-Redirect, NOT 200 + body
    assert captured["state"] == "stage_2"  # the DEFINED live trend (F-2)


# ---------------------------------------------------------------------------
# Pipeline call-site: spy swing.pipeline.runner.structural_stage (imported at
# module load) to confirm the LIVE compute is reached + a DEFINED state reaches
# the renderer (Codex R2 Major #2).
# ---------------------------------------------------------------------------


def test_pipeline_step_charts_market_weather_uses_structural_stage(
    tmp_path, monkeypatch,
):
    from tests.pipeline.test_step_charts_ohlcv_cache_wiring import (
        _make_cfg,
        _seed_eval_with_aplus_candidates,
        _stub_render,
    )
    from swing.pipeline.lease import acquire_lease
    from swing.pipeline.runner import _step_charts

    cfg = _make_cfg(tmp_path)
    cfg = replace(cfg, pipeline=replace(cfg.pipeline, chart_top_n_watch=5))
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    eval_run_id, data_asof = _seed_eval_with_aplus_candidates(
        cfg, lease, [("APLA", 110.0)],
    )

    real = runner_mod.structural_stage
    seen: dict = {}

    def _spy_stage(closes, *, rising_period):
        seen["called"] = True
        return real(closes, rising_period=rising_period)

    monkeypatch.setattr(runner_mod, "structural_stage", _spy_stage)

    captured: dict = {}
    real_render = runner_mod.render_market_weather_svg

    def _spy_render(*, bars, trend_template_state):
        captured["state"] = trend_template_state
        return b"<svg/>"

    monkeypatch.setattr(runner_mod, "render_market_weather_svg", _spy_render)
    _stub_render(monkeypatch)

    class _UptrendCacheKw:
        def get_or_fetch(self, *, ticker, window_days):
            return _uptrend_frame(260)

    _step_charts(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id, data_asof=data_asof,
        ohlcv_cache=_UptrendCacheKw(),
    )

    assert seen.get("called") is True  # the LIVE structural_stage was invoked
    assert captured.get("state") == "stage_2"  # DEFINED trend reached the renderer
