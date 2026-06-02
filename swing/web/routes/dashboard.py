"""GET / -- the main dashboard route + POST /dashboard/weather-chart/refresh."""
from __future__ import annotations

# Phase 14 Sub-bundle 1 T-2.1 V2.G4 R3.M2 LOCK: module-level logger required
# for the narrow ValueError-only log.warning path below. The `import logging`
# + `log = logging.getLogger(__name__)` + `log.warning(...)` triplet MUST
# land in the same commit (split would NameError on the first
# ValueError-degraded invocation; forward-binding lesson #4).
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.data.models import ChartRender
from swing.data.repos.chart_renders import refresh_chart_render

# Phase 14 close-out follow-on (F-2): module-top import so the call-site test
# may monkeypatch ``swing.web.routes.dashboard.structural_stage``. Pure compute
# over fetched closes (no DB; the persisted-criteria read via current_stage is
# replaced by a LIVE structural compute -- see the refresh handler below).
from swing.evaluation.criteria.trend_template import structural_stage
from swing.evaluation.dates import last_completed_session
from swing.web.chart_scope import latest_completed_pipeline_run

# Phase 14 SB3 T-3.4: module-top import (was a function-local import) so the
# discriminating test may monkeypatch
# ``swing.web.routes.dashboard.render_market_weather_svg``.
from swing.web.charts import render_market_weather_svg
from swing.web.ohlcv_cache import (
    MIN_CALENDAR_DAYS_FOR_MA200,
    MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE,
    slice_recent_calendar_days,
)
from swing.web.view_models.dashboard import build_dashboard

router = APIRouter()
log = logging.getLogger(__name__)  # Phase 14 Sub-bundle 1 T-2.1 V2.G4 R3.M2
                                    # LOCK: see import logging note above.


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
# Phase 13 T2.SB6b T-A.6.6 -- POST /dashboard/weather-chart/refresh
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
        # F-2: fetch a WIDE compute window so structural_stage has TT3's 200MA
        # rising history (>= MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE); display the
        # narrower MIN_CALENDAR_DAYS_FOR_MA200 slice (legibility unchanged).
        try:
            compute_bars = ohlcv_cache.get_or_fetch(
                ticker=benchmark, window_days=MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE,
            )
        except ValueError as exc:
            # OhlcvCache.get_or_fetch raises ValueError("No data for {ticker}")
            # on empty-archive / cache-miss-fallthrough per its docstring at
            # swing/web/ohlcv_cache.py:131. This is the canonical empty-result
            # signal (NOT a programming error). Emit a warning so the
            # operator-visible 409 message can be diagnosed via logs per
            # CLAUDE.md gotcha #27 (silent-skip-without-audit) + Phase 14
            # Sub-bundle 1 V2.G4 R2.M2 LOCK.
            log.warning(
                "weather-chart refresh: get_or_fetch returned empty for %s: %s",
                benchmark, exc,
            )
            compute_bars = None
        # NOTE: Do NOT catch broad `Exception` here. The pre-fix handler caught
        # arbitrary exceptions (including the TypeError that hid this bug for
        # weeks via the positional-list call signature drift) and silently
        # returned a 409 "no bars" message -- exactly the masking pattern the
        # operator-witnessed gate surfaced. Let TypeError, AttributeError,
        # KeyError, RuntimeError, and other programming errors propagate to
        # FastAPI's default 500 handler so they surface as 500s (not as
        # misleading "run the pipeline first" 409s). Per R2.M2 anti-pattern
        # lock + forward-binding lesson #8.
        if compute_bars is None or compute_bars.empty:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"no OHLCV bars available for benchmark {benchmark!r}; "
                    "run the pipeline first"
                ),
            )
        # F-2: compute the trend state LIVE from the wide compute window via
        # structural_stage (current_stage read PERSISTED criteria for a
        # benchmark not in the evaluated set -> always 'undefined'). Fail-soft
        # to "undefined" on any error so the refresh never crashes.
        try:
            closes = compute_bars["Close"]
            if getattr(closes, "ndim", 1) == 2:
                closes = closes.iloc[:, 0]
            weather_state = structural_stage(
                closes, rising_period=cfg.trend_template.rising_ma_period_days,
            )
        except Exception as exc:  # noqa: BLE001 - fail-soft, never crash refresh
            log.warning(
                "weather refresh structural_stage failed for %s: %s",
                benchmark, exc,
            )
            weather_state = "undefined"
        bars = slice_recent_calendar_days(
            compute_bars, window_days=MIN_CALENDAR_DAYS_FOR_MA200,
        )
        svg_bytes = render_market_weather_svg(
            bars=bars, trend_template_state=weather_state,
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
