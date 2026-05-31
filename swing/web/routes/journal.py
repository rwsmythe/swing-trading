"""Journal route."""
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.data.repos.fills import list_fills_for_trade
from swing.data.repos.trades import get_trade
from swing.web.trade_charts import render_trade_window_thumbnail_svg
from swing.web.view_models.journal import DEFAULT_PAGE_SIZE, build_journal

log = logging.getLogger(__name__)

router = APIRouter()

# Slice 4 (Codex R1 M#6 / spec §5.3(c)): the process-wide render LOCK serializes
# matplotlib but does NOT bound how many request workers PILE UP waiting behind
# it on a fast scroll. This BoundedSemaphore caps CONCURRENT thumbnail renders
# (independent of page-size / `revealed`); a burst that exhausts it returns a
# transient 200+busy fragment (which self-retries) rather than blocking a worker
# indefinitely -- preventing the self-inflicted DoS the spec flags.
_THUMBNAIL_RENDER_SEMAPHORE = threading.BoundedSemaphore(2)
# Short acquire timeout (module constant so tests can shrink it).
_THUMBNAIL_RENDER_TIMEOUT_S = 2.0
# Short cache lifetime for the cacheable (svg / unavailable / not-found)
# contracts. Busy is transient backpressure -> Cache-Control: no-store instead.
_THUMBNAIL_CACHE_CONTROL = "private, max-age=60"


@router.get("/journal", response_class=HTMLResponse)
def journal_page(
    request: Request,
    # Slice 2: `period` is now a plain str (was Literal[...]). An unknown
    # value no longer 422s — build_journal clamps it to the default. page /
    # page_size remain typed ints (non-int still 422s, which is correct).
    period: str = Query("month"),
    page: int = Query(1),
    page_size: int = Query(DEFAULT_PAGE_SIZE),
    # Slice 3 (OQ-9): sort/filter are plain `str | None` — allowlist-validated
    # inside build_journal, which falls back to the default + flags
    # invalid_filter (never 422s) on a bad value.
    sort: str | None = Query(None),
    dir: str | None = Query(None),
    filter_state: str | None = Query(None),
    filter_pattern: str | None = Query(None),
    filter_aplus: str | None = Query(None),
):
    cfg = apply_overrides(request.app.state.cfg)
    vm = build_journal(
        cfg=cfg, period=period, page=page, page_size=page_size,
        sort=sort, dir=dir, filter_state=filter_state,
        filter_pattern=filter_pattern, filter_aplus=filter_aplus,
    )
    # Slice 3 (OQ-9): for an HX sort/filter request, render ONLY the shared
    # `<table>` partial (the SAME include the full page uses) so the fragment
    # root is `<table id="journal-table">` — a bare-<tr> root would trip the
    # HTMX synthetic-table-wrap on an outerHTML swap. The HX-Request detection
    # mirrors the established codebase check.
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"
    template = (
        "partials/journal_table.html.j2" if is_htmx else "journal.html.j2"
    )
    return request.app.state.templates.TemplateResponse(
        request, template, {"vm": vm},
    )


@router.get("/journal/trades/{trade_id}/thumbnail", response_class=HTMLResponse)
def journal_thumbnail_fragment(request: Request, trade_id: int):
    """Phase 14 SB4 Slice 4 (OQ-3): lazy on-scroll candlestick thumbnail.

    Four contracts: 200 + SVG / 200 + unavailable / 200 + not-found (with a
    WARNING log) / 200 + busy (render-concurrency bound exhausted). Render
    exceptions are isolated (logged, never raised). Cache-Control is DISTINCT
    by contract: success/unavailable/not-found = ``private, max-age=<short>``;
    busy = ``no-store`` (transient backpressure must not be cached). Read-only:
    zero domain writes (only ``read_or_fetch_archive`` inside the renderer).
    """
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None:
                log.warning(
                    "journal thumbnail: trade not found trade_id=%s", trade_id,
                )
                resp = templates.TemplateResponse(
                    request, "partials/journal_thumbnail.html.j2",
                    {"chart_svg_bytes": None, "not_found": True,
                     "busy": False, "trade_id": trade_id},
                )
                resp.headers["Cache-Control"] = _THUMBNAIL_CACHE_CONTROL
                return resp
            fills = list_fills_for_trade(conn, trade_id)
    finally:
        conn.close()

    # Bound concurrent renders; on timeout return a self-retrying busy fragment
    # rather than blocking a worker behind the render lock.
    if not _THUMBNAIL_RENDER_SEMAPHORE.acquire(
            timeout=_THUMBNAIL_RENDER_TIMEOUT_S):
        log.warning("journal thumbnail render busy trade_id=%s", trade_id)
        resp = templates.TemplateResponse(
            request, "partials/journal_thumbnail.html.j2",
            {"chart_svg_bytes": None, "not_found": False, "busy": True,
             "trade_id": trade_id},
        )
        # Transient backpressure -- must NOT be cached, or the browser would
        # replay "busy" instead of retrying.
        resp.headers["Cache-Control"] = "no-store"
        return resp
    try:
        svg = render_trade_window_thumbnail_svg(
            trade=trade, fills=fills, cfg=cfg,
        )
    except Exception:
        log.warning(
            "journal thumbnail render failed trade_id=%s ticker=%s",
            trade_id, trade.ticker, exc_info=True,
        )
        svg = None
    finally:
        _THUMBNAIL_RENDER_SEMAPHORE.release()
    if svg is None:
        log.warning(
            "journal thumbnail unavailable trade_id=%s ticker=%s",
            trade_id, trade.ticker,
        )
    resp = templates.TemplateResponse(
        request, "partials/journal_thumbnail.html.j2",
        {"chart_svg_bytes": svg, "not_found": False, "busy": False,
         "trade_id": trade_id},
    )
    resp.headers["Cache-Control"] = _THUMBNAIL_CACHE_CONTROL
    return resp
