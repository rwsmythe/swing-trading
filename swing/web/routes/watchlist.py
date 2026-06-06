"""Watchlist routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from swing.config_overrides import apply_overrides
from swing.data.db import open_connection
from swing.web.chart_jit import get_or_render_surface
from swing.web.chart_scope import latest_completed_pipeline_run
from swing.web.view_models.watchlist import (
    build_watchlist,
    build_watchlist_expanded,
    build_watchlist_row,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_jit_chart_bytes(
    request: Request, *, ticker: str, surface: str,
    pipeline_run_id: int | None = None,
    data_asof_date: str | None = None,
    resolve_latest_if_missing: bool = True,
    **renderer_kwargs,
) -> bytes | None:
    """Helper: acquire a per-request DB connection + pin Option A anchor +
    consult the JIT cache-miss hook.

    DB connection acquisition mirrors swing/web/routes/account.py +
    swing/web/charts.py: open a fresh sqlite3.connect(...) per-request from
    cfg.paths.db_path (NOT a non-existent ``request.app.state.db_conn``).

    Codex R1 Major #1 — Option A "one pipeline_run anchor" discipline
    (§1.5.3 LOCK): callers that already resolved a pipeline_run binding
    upstream (e.g., ``build_watchlist_expanded`` / ``build_watchlist_row``
    which thread their run binding into the VM) MUST pass
    ``pipeline_run_id`` + ``data_asof_date`` explicitly to keep chart URL /
    candidate criteria / chart-scope reason / JIT bytes pinned to the SAME
    pipeline_run.

    Codex R2 MAJOR #1 + #2 + MINOR #1 — anchor-fallback discipline:

    - ``resolve_latest_if_missing`` (default True): when False AND both
      anchor args are None, the helper RETURNS None (skips JIT entirely)
      instead of falling back to ``latest_completed_pipeline_run``. Route
      callers that already resolved a VM anchor pass ``False`` so a
      pipeline_run landing between VM-build and JIT-call CANNOT attach
      bytes to a response whose VM bound to a no-run state. (Default True
      preserves backward compat for any non-route consumer.)

    - Partial anchor (exactly one of ``pipeline_run_id`` / ``data_asof_date``
      supplied) is a programming error — both come from the SAME upstream
      binding. The helper logs a WARNING + returns None (refuses silent
      fallback to latest) so the call-site bug surfaces in logs instead of
      manifesting as a subtle mixed-anchor response.

    Returns None when no completed pipeline_run exists OR when OHLCV cache
    is unavailable OR when the renderer fails / returns empty.
    """
    cfg = apply_overrides(request.app.state.cfg)
    ohlcv_cache = getattr(request.app.state, "ohlcv_cache", None)
    if ohlcv_cache is None:
        return None

    # R2 MINOR #1: partial anchor → log + degrade (NOT silent fallback).
    if (pipeline_run_id is None) != (data_asof_date is None):
        logger.warning(
            "chart_jit: partial anchor (pipeline_run_id=%s, "
            "data_asof_date=%s) — refusing fallback to avoid mixed-anchor "
            "response (surface=%s, ticker=%s)",
            pipeline_run_id, data_asof_date, surface, ticker,
        )
        return None

    conn = open_connection(str(cfg.paths.db_path), busy_timeout_ms=cfg.web.db_busy_timeout_ms)
    try:
        if pipeline_run_id is not None and data_asof_date is not None:
            resolved_run_id = pipeline_run_id
            resolved_data_asof = data_asof_date
        else:
            # Both are None here (partial case rejected above).
            # R2 MAJOR #1 + #2: callers that already resolved a VM anchor
            # set resolve_latest_if_missing=False — skip JIT entirely so
            # a mid-request pipeline_run completion can't poison the
            # response with bytes from a newer anchor than the VM bound to.
            if not resolve_latest_if_missing:
                return None
            anchor = latest_completed_pipeline_run(conn)
            if anchor is None:
                return None
            resolved_run_id = anchor.run_id
            resolved_data_asof = anchor.data_asof_date
        return get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface=surface, ticker=ticker,
            pipeline_run_id=resolved_run_id,
            data_asof_date=resolved_data_asof,
            **renderer_kwargs,
        )
    finally:
        conn.close()


@router.get("/watchlist", response_class=HTMLResponse)
def watchlist_page(request: Request):
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    vm = build_watchlist(cfg=cfg, cache=cache, executor=executor)
    return request.app.state.templates.TemplateResponse(
        request, "watchlist.html.j2", {"vm": vm},
    )


@router.get("/watchlist/{ticker}/row", response_class=HTMLResponse)
def watchlist_row(request: Request, ticker: str):
    """Render the compact watchlist row for `ticker`.

    Used by the close button on an expanded row to swap back to the
    compact state without a full page reload (3e.4). Symmetric naming
    with /expand. Returns 404 when the ticker is not on the active
    watchlist — same contract as /expand.

    Phase 13 T-T4.SB.3 (Item 5 + Item 6): wires the JIT cache-miss hook
    (``swing/web/chart_jit.py:get_or_render_surface``) so the collapse
    path repopulates the thumbnail from cache (or live-renders) — closing
    the Item 6 "thumbnail blank after expand" defect. Renderer-kwargs
    uniformity LOCK: ma_lines=[20, 50] matches pipeline pre-gen kwargs
    (per Codex R4 M#3 cache-collision avoidance).
    """
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    row_vm = build_watchlist_row(
        cfg=cfg, cache=cache, ticker=ticker.upper(), executor=executor,
    )
    if row_vm is None:
        raise HTTPException(status_code=404, detail=f"ticker {ticker} not on watchlist")

    # JIT cache lookup + live render on miss (Item 6 fix via Item 5 helper).
    #
    # Codex R2 MAJOR #2: thread the VM-pinned anchor through so row
    # classification tags / current pivot + thumbnail bytes ALL bind to
    # the SAME pipeline_run (Option A LOCK; §1.5.3). When the VM has no
    # anchor (no completed pipeline_run at request time), pass
    # ``resolve_latest_if_missing=False`` so the helper skips JIT entirely
    # — a pipeline_run completing mid-request MUST NOT attach bytes to a
    # response whose VM metadata reflects the no-run state.
    chart_bytes = _resolve_jit_chart_bytes(
        request, ticker=ticker.upper(), surface="watchlist_row",
        pipeline_run_id=row_vm.pipeline_run_id,
        data_asof_date=row_vm.data_asof_date,
        resolve_latest_if_missing=False,
        ma_lines=[20, 50],
    )

    return request.app.state.templates.TemplateResponse(
        request, "partials/watchlist_row.html.j2",
        {
            "w": row_vm.w,
            "price": row_vm.price,
            "tags": row_vm.tags,
            "pattern_tag": row_vm.pattern_tag,
            "current_pivot": row_vm.current_pivot,
            "chart_svg_bytes_for_row": chart_bytes,
        },
    )


@router.get("/watchlist/{ticker}/expand", response_class=HTMLResponse)
def watchlist_expand(request: Request, ticker: str):
    """Render the expanded watchlist row.

    Phase 13 T-T4.SB.3 (Item 5): populates
    ``WatchlistExpandedVM.watchlist_expanded_chart_svg_bytes`` via the JIT
    helper (surface='ticker_detail' per spec §B.5 — both the hyp-recs route
    and the watchlist expanded route share the SAME surface for
    cache-key reuse).

    Renderer-kwargs uniformity LOCK: ``pattern_evaluation=None`` matches
    the hyp-recs route's call (per Codex R4 M#3 cache-collision
    avoidance).
    """
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    expanded = build_watchlist_expanded(
        cfg=cfg, cache=cache, ticker=ticker.upper(), executor=executor,
    )
    if expanded is None:
        raise HTTPException(status_code=404, detail=f"ticker {ticker} not on watchlist")

    # JIT cache lookup + live render on miss — populate
    # watchlist_expanded_chart_svg_bytes via the shared ticker_detail
    # surface (renderer-kwargs uniformity LOCK).
    #
    # Codex R1 Major #1 LOCK: thread the VM's resolved pipeline_run
    # anchor through to the JIT helper so chart URL + candidate
    # criteria + chart-scope reason + JIT bytes ALL bind to the SAME
    # pipeline_run (Option A; §1.5.3). Without the threading, a new
    # pipeline completing between VM-build and JIT-call would mix
    # anchors across one response.
    #
    # Codex R2 MAJOR #1: when the VM has no anchor (no completed
    # pipeline_run at request time), pass
    # ``resolve_latest_if_missing=False`` so the helper skips JIT
    # entirely. Otherwise a pipeline completing mid-request would
    # attach new-run chart bytes to a VM whose ``chart_reason='no-run'``
    # banner is already in flight (mixed anchors across one response).
    chart_bytes = _resolve_jit_chart_bytes(
        request, ticker=ticker.upper(), surface="ticker_detail",
        pipeline_run_id=expanded.pipeline_run_id,
        data_asof_date=expanded.data_asof_date,
        resolve_latest_if_missing=False,
        pattern_evaluation=None,
    )
    # Rebuild VM with chart bytes (dataclass is frozen — emit a new copy).
    from dataclasses import replace
    expanded = replace(
        expanded, watchlist_expanded_chart_svg_bytes=chart_bytes,
    )

    return request.app.state.templates.TemplateResponse(
        request, "partials/watchlist_expanded.html.j2", {"expanded": expanded},
    )
