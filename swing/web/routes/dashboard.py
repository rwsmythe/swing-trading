"""GET / — the main dashboard route + POST /dashboard/weather-chart/refresh."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.data.models import ChartRender
from swing.data.repos.chart_renders import refresh_chart_render
from swing.evaluation.dates import last_completed_session
from swing.web.chart_scope import latest_completed_pipeline_run
from swing.web.view_models.dashboard import build_dashboard

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def index(request: Request):
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    ohlcv_cache = request.app.state.ohlcv_cache
    executor = request.app.state.price_fetch_executor
    vm = build_dashboard(cfg=cfg, cache=cache, executor=executor,
                         ohlcv_cache=ohlcv_cache)
    return request.app.state.templates.TemplateResponse(
        request, "dashboard.html.j2", {"vm": vm},
    )


# ---------------------------------------------------------------------------
# Phase 13 T2.SB6b T-A.6.6 — POST /dashboard/weather-chart/refresh
# ---------------------------------------------------------------------------


@router.post("/dashboard/weather-chart/refresh")
def dashboard_weather_chart_refresh(request: Request) -> Response:
    """Invalidate the chart_renders cache row for the benchmark ticker's
    market_weather surface + re-render against the most recent OHLCV bars
    per spec section 4.5 + plan section C.3 LOCK.

    HTMX 3-surface discipline per L12 LOCK + Phase 5 R1 M1+M2 + Phase 6 I3:
      (a) Embedded form carries hx-headers='{"HX-Request": "true"}' under
          OriginGuard strict-mode (rendered in dashboard.html.j2).
      (b) Success-path response: 204 + HX-Redirect: /dashboard (NOT 303
          swap-target).
      (c) /dashboard route is registered above.

    Cache invalidation uses the T2.SB6a substrate `refresh_chart_render`
    helper (DELETE-then-INSERT atomic per plan A.15 + BEGIN IMMEDIATE per
    A.12). Caller-tx contract preserved: wrap in `with conn:`.
    """
    cfg = apply_overrides(request.app.state.cfg)
    conn = connect(cfg.paths.db_path)
    try:
        binding = latest_completed_pipeline_run(conn)
        if binding is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "no completed pipeline_run; run the pipeline before "
                    "refreshing the dashboard weather chart"
                ),
            )
        ohlcv_cache = request.app.state.ohlcv_cache
        if ohlcv_cache is None:
            raise HTTPException(
                status_code=409,
                detail="OHLCV cache not initialized",
            )
        benchmark = cfg.rs.benchmark_ticker
        try:
            bars_bundle = ohlcv_cache.get_or_fetch([benchmark])
            bars = bars_bundle.get(benchmark) if bars_bundle else None
        except Exception:  # noqa: BLE001 - degraded fallback
            bars = None
        if bars is None or bars.empty:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"no OHLCV bars available for benchmark {benchmark!r}; "
                    "run the pipeline first"
                ),
            )
        from swing.web.charts import render_market_weather_svg
        svg_bytes = render_market_weather_svg(
            bars=bars, trend_template_state="n/a",
        )
        now_iso = datetime.now().isoformat()
        chart_render = ChartRender(
            id=None,
            ticker=benchmark,
            surface="market_weather",
            chart_svg_bytes=svg_bytes,
            source_data_hash="manual_refresh",
            rendered_at=now_iso,
            data_asof_date=last_completed_session(
                datetime.now(),
            ).isoformat(),
            pipeline_run_id=binding.run_id,
            pattern_class=None,
        )
        with conn:
            refresh_chart_render(conn, chart_render)
    finally:
        conn.close()

    return Response(
        status_code=204, headers={"HX-Redirect": "/dashboard"},
    )
