"""JIT cache-miss chart-render hook (Phase 13 T4.SB Item 5; T-T4.SB.3).

Architecture LOCK per spec §B.5:
  - ``swing/web/chart_scope.py`` LOCKED read-only (does NOT invoke JIT).
  - JIT invocation lives at route handlers / VM builders that carry the
    necessary dependency context (``conn``, ``ohlcv_cache``, surface-
    specific render kwargs).
  - Cache key shape preserved: run-bound surfaces (``watchlist_row``,
    ``ticker_detail``, ``market_weather``) write pipeline_run_id non-NULL;
    ``position_detail`` writes NULL.
  - F6 construction-barrier defense: ``ChartRender(...)`` construction
    raises on empty bytes; helper catches + returns None + WARN-logs.
  - Renderer-kwargs uniformity LOCK across callsites for cache-collision
    avoidance (per Codex R4 M#3): both ticker_detail callers (hyp-recs
    route + watchlist expanded) pass identical kwargs.

Cumulative gotchas applied:
- Expansion #10 sub-discipline (a) architecture-location: NEW module with
  explicit dependency-injection signature; chart_scope.py LOCKED read-only.
- Expansion #10 sub-discipline (c) renderer-kwargs uniformity for cache
  collision avoidance — both ticker_detail callsites pass
  ``pattern_evaluation=None``; both watchlist_row callsites pass identical
  ma_lines.
- F6 transient-empty defense at construction barrier — ``ChartRender(...)``
  raises ValueError on empty bytes; we catch and return None so the cache
  row stays preserved.
- T2.SB6a Codex R1 CRITICAL #1 semantic contract: run-bound surfaces
  require pipeline_run_id non-NULL; position_detail requires NULL. The
  ``ChartRender.__post_init__`` validator enforces this.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from swing.data.models import ChartRender
from swing.data.repos.chart_renders import (
    get_cached_chart_svg,
    refresh_chart_render,
)
from swing.web.charts import (
    compute_chart_source_hash,
    render_market_weather_svg,
    render_position_detail_svg,
    render_ticker_detail_svg,
    render_watchlist_thumbnail_svg,
)
from swing.web.ohlcv_cache import MIN_CALENDAR_DAYS_FOR_MA200

logger = logging.getLogger(__name__)


# Renderer registry — module-level so tests can mock individual surface
# renderers via ``mod._RENDERERS["ticker_detail"] = MagicMock(...)`` +
# restore via ``importlib.reload(mod)`` in finally block.
_RENDERERS: dict[str, Callable] = {
    "ticker_detail": render_ticker_detail_svg,
    "market_weather": render_market_weather_svg,
    "position_detail": render_position_detail_svg,
    "watchlist_row": render_watchlist_thumbnail_svg,
}


# Conservative default for watchlist thumbnail MA overlays (mirrors current
# ``_step_charts`` invocation pattern + spec §C.5 line 449 thumbnail design).
# Renderer-kwargs uniformity LOCK across both callsites (pipeline pre-gen +
# route JIT) per Codex R4 M#3.
_WATCHLIST_THUMBNAIL_MA_LINES: list[int] = [20, 50]


def get_or_render_surface(
    *,
    conn: sqlite3.Connection,
    ohlcv_cache,
    surface: str,
    ticker: str,
    pipeline_run_id: int | None,
    pattern_class: str | None = None,
    data_asof_date: str,
    source_data_hash: str = "chart_jit_v1",
    **renderer_kwargs,
) -> bytes | None:
    """Return cached SVG bytes if present; otherwise live-render via the
    surface's matplotlib helper, write-through cache, and return bytes.

    Returns None on render-failure / OHLCV-missing / construction-barrier
    rejection. Caller emits chart-unavailable banner per spec §B.5 OQ-5.5.
    """
    # Step 1: cache read.
    #
    # Codex R1 MAJOR #2 — F6 transient-empty defense extended to the
    # cache-HIT path. A bad legacy / future-writer-bypass row whose
    # ``chart_svg_bytes`` is zero-length BLOB (schema only enforces
    # NOT NULL, not non-empty) MUST be treated as a cache miss so the
    # helper falls through to JIT render + write-through replaces the
    # empty row. Without this guard, ``cached is not None`` succeeded
    # at the construction-barrier was bypassed — operator stays blank.
    cached = get_cached_chart_svg(
        conn,
        surface=surface,
        ticker=ticker,
        pipeline_run_id=pipeline_run_id,
        pattern_class=pattern_class,
    )
    if cached is not None and len(cached) > 0:
        return cached
    if cached is not None:
        # cached == b"" → log + fall through to render path.
        logger.warning(
            "chart_jit: cache row for %s/%s/%s has empty bytes; "
            "re-rendering",
            surface, ticker, pipeline_run_id,
        )

    # Step 2: fetch OHLCV via cache (per ``_step_charts._bars_or_none`` precedent).
    try:
        bars = ohlcv_cache.get_or_fetch(
            ticker=ticker, window_days=MIN_CALENDAR_DAYS_FOR_MA200,
        )
    except Exception as exc:  # noqa: BLE001 — log + degrade
        logger.warning(
            "chart_jit ohlcv_cache failure for %s: %s", ticker, exc,
        )
        return None
    if bars is None or len(bars) == 0:
        return None

    renderer = _RENDERERS.get(surface)
    if renderer is None:
        logger.warning("chart_jit: no renderer for surface=%s", surface)
        return None

    # Step 3: render. Renderer-kwargs match the actual signatures at
    # ``swing/web/charts.py:render_*``:
    #   - render_watchlist_thumbnail_svg(*, ticker, bars, ma_lines)
    #   - render_ticker_detail_svg(*, ticker, bars, pattern_evaluation)
    #   - render_market_weather_svg(*, bars, trend_template_state)
    #   - render_position_detail_svg(*, ticker, bars, trade, fills,
    #                                  current_stop)
    # Uniformity LOCK: for ticker_detail, both callsites pass
    # pattern_evaluation=None (V1). For watchlist_row, both callsites
    # pass the SAME ma_lines (cache-collision avoidance).
    try:
        if surface == "ticker_detail":
            svg_bytes = renderer(
                ticker=ticker, bars=bars,
                pattern_evaluation=renderer_kwargs.get("pattern_evaluation"),
            )
        elif surface == "watchlist_row":
            svg_bytes = renderer(
                ticker=ticker, bars=bars,
                ma_lines=renderer_kwargs.get(
                    "ma_lines", _WATCHLIST_THUMBNAIL_MA_LINES,
                ),
            )
        elif surface == "market_weather":
            # Phase 14 SB3 T-3.4 (§C.4a): honest dead/defensive default. No
            # production caller routes market_weather through the JIT today
            # (the two live sites -- pipeline _step_charts + the weather
            # refresh handler -- compute the real state via current_stage and
            # pass it explicitly). A future SB4 caller MUST compute + pass the
            # real trend_template_state; the default below is deliberately a
            # non-committal placeholder, not a fabricated stage label.
            svg_bytes = renderer(
                bars=bars,
                trend_template_state=renderer_kwargs.get(
                    "trend_template_state", "undefined",
                ),
            )
        elif surface == "position_detail":
            svg_bytes = renderer(
                ticker=ticker, bars=bars,
                trade=renderer_kwargs["trade"],
                fills=renderer_kwargs["fills"],
                current_stop=renderer_kwargs.get("current_stop"),
            )
        else:
            return None
    except Exception as exc:  # noqa: BLE001 — log + degrade
        logger.warning(
            "chart_jit render failure for %s/%s: %s",
            surface, ticker, exc,
        )
        return None

    # Step 4: F6 construction-barrier defense — ChartRender(...) raises
    # on empty bytes per CLAUDE.md F6 lesson; catch + WARN + return None
    # (existing cache row not blanked). Also catches semantic contract
    # violations (cache key shape per T2.SB6a Codex R1 CRITICAL #1).
    if not svg_bytes:
        logger.warning(
            "chart_jit renderer returned empty bytes for %s/%s; "
            "preserving existing cache row",
            surface, ticker,
        )
        return None

    # Phase 16 Arc 3 (3c): stamp a content-derived hash (bar count + first/last
    # asof_date) instead of the static ``source_data_hash`` default so the cache
    # row's provenance changes on data growth. Falls back to the passed literal
    # only if hashing fails (defensive — never block the write-through).
    try:
        computed_hash = compute_chart_source_hash(bars)
    except Exception as exc:  # noqa: BLE001 — provenance is best-effort
        logger.warning(
            "chart_jit: compute_chart_source_hash failed for %s/%s: %s; "
            "falling back to %r", surface, ticker, exc, source_data_hash,
        )
        computed_hash = source_data_hash

    try:
        chart_render = ChartRender(
            id=None,
            ticker=ticker,
            surface=surface,
            chart_svg_bytes=svg_bytes,
            source_data_hash=computed_hash,
            rendered_at=datetime.now(UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ",
            ),
            data_asof_date=data_asof_date,
            pipeline_run_id=pipeline_run_id,
            pattern_class=pattern_class,
        )
    except ValueError as exc:
        logger.warning(
            "chart_jit construction-barrier rejected %s/%s: %s",
            surface, ticker, exc,
        )
        return None

    # Step 5: write-through cache. Repo function uses caller-tx contract
    # (no conn.commit() in repo); we wrap in a transaction so the
    # DELETE-then-INSERT atomic refresh commits.
    try:
        with conn:
            refresh_chart_render(conn, chart_render)
    except Exception as exc:  # noqa: BLE001 — degrade + still return bytes
        logger.warning(
            "chart_jit write-through failure for %s/%s: %s",
            surface, ticker, exc,
        )
    return svg_bytes
