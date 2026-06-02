"""Journal route."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.data.repos.fills import list_fills_for_trade
from swing.data.repos.trades import get_trade

# Phase 14 close-out (P14.N1): the render cap moved to swing/web/thumbnail_render
# so the dashboard thumbnail routes share ONE process-wide matplotlib cap.
# (Slice 4 / Codex R1 M#6 / spec §5.3(c): caps CONCURRENT thumbnail renders so a
# burst returns a transient 200+busy fragment that self-retries instead of
# piling workers behind the render lock.)
from swing.web.thumbnail_render import (
    _THUMBNAIL_CACHE_CONTROL,
    _THUMBNAIL_RENDER_SEMAPHORE,
    _THUMBNAIL_RENDER_TIMEOUT_S,
)
from swing.web.trade_charts import (
    render_trade_window_position_svg,
    render_trade_window_thumbnail_svg,
)
from swing.web.view_models.journal import (
    DEFAULT_PAGE_SIZE,
    build_journal,
    build_trade_drilldown_vm,
)

log = logging.getLogger(__name__)

router = APIRouter()


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


@router.get("/journal/trades/{trade_id}", response_class=HTMLResponse)
def journal_trade_detail_page(request: Request, trade_id: int):
    """Phase 14 SB4 Slice 5 Task 5.5: the journal per-trade drill-down page.

    Full-page navigation (the listing links here via a plain <a href>, NOT
    HTMX — no 204/HX-Redirect surface). Missing trade -> 404 (the full-page
    contract; mirror routes/trades.py review_form_page). Read-only.
    """
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            vm = build_trade_drilldown_vm(conn, cfg, trade_id)
    finally:
        conn.close()
    if vm is None:
        raise HTTPException(
            status_code=404, detail=f"Trade #{trade_id} not found",
        )
    return templates.TemplateResponse(
        request, "journal_trade_detail.html.j2", {"vm": vm},
    )


@router.get("/journal/trades/{trade_id}/chart", response_class=HTMLResponse)
def journal_trade_chart_fragment(request: Request, trade_id: int):
    """Phase 14 SB4 Slice 5 Task 5.5: lazy annotated trade-window chart.

    Three contracts (the fragment contract is DISTINCT from the page's 404):
      200 + SVG          (render produced bytes)
      200 + unavailable  (render returned None -- no coverage)
      200 + not-found    (distinct trade-not-found copy + WARNING log; NOT 404)
    Render exceptions are isolated (logged, never raised) -- identical
    failure-isolation to the Slice 0 review-chart route. Read-only: zero
    domain writes (only ``read_or_fetch_archive`` inside the renderer).
    """
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None:
                log.warning(
                    "journal trade chart: trade not found trade_id=%s",
                    trade_id,
                )
                resp = templates.TemplateResponse(
                    request, "partials/journal_trade_chart.html.j2",
                    {"chart_svg_bytes": None, "not_found": True},
                )
                resp.headers["Cache-Control"] = "private, max-age=60"
                return resp
            fills = list_fills_for_trade(conn, trade_id)
    finally:
        conn.close()
    try:
        # Deliberately NOT bounded by _THUMBNAIL_RENDER_SEMAPHORE: this
        # annotated drill-down chart is ONE render per full-page navigation
        # (hx-trigger="load", one per drill-down view), not the per-row scroll
        # burst that motivated the thumbnail route's concurrency bound. It
        # relies on the process-wide matplotlib render lock alone, which still
        # serializes it against every other render. The backpressure bound
        # stays where the burst risk actually is (the thumbnail route).
        svg = render_trade_window_position_svg(
            trade=trade, fills=fills, cfg=cfg,
        )
    except Exception:
        log.warning(
            "journal trade chart render failed trade_id=%s ticker=%s",
            trade_id, trade.ticker, exc_info=True,
        )
        svg = None
    if svg is None:
        log.warning(
            "journal trade chart unavailable trade_id=%s ticker=%s",
            trade_id, trade.ticker,
        )
    resp = templates.TemplateResponse(
        request, "partials/journal_trade_chart.html.j2",
        {"chart_svg_bytes": svg, "not_found": False},
    )
    # A None render can be a TRANSIENT no-coverage read (yfinance-empty / F6),
    # not only the permanent "predates archive" case -- caching it would block
    # a quick reload from retrying. Successful SVG is safe to cache 60s.
    if svg is None:
        resp.headers["Cache-Control"] = "private, max-age=0"
    else:
        resp.headers["Cache-Control"] = "private, max-age=60"
    return resp
