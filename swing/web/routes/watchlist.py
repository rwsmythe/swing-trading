"""Watchlist routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from swing.web.view_models.watchlist import (
    build_watchlist,
    build_watchlist_expanded,
    build_watchlist_row,
)

router = APIRouter()


@router.get("/watchlist", response_class=HTMLResponse)
def watchlist_page(request: Request):
    cfg = request.app.state.cfg
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
    """
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    row_vm = build_watchlist_row(
        cfg=cfg, cache=cache, ticker=ticker.upper(), executor=executor,
    )
    if row_vm is None:
        raise HTTPException(status_code=404, detail=f"ticker {ticker} not on watchlist")
    return request.app.state.templates.TemplateResponse(
        request, "partials/watchlist_row.html.j2",
        {
            "w": row_vm.w,
            "price": row_vm.price,
            "tags": row_vm.tags,
            "pattern_tag": row_vm.pattern_tag,
            "current_pivot": row_vm.current_pivot,
        },
    )


@router.get("/watchlist/{ticker}/expand", response_class=HTMLResponse)
def watchlist_expand(request: Request, ticker: str):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    expanded = build_watchlist_expanded(
        cfg=cfg, cache=cache, ticker=ticker.upper(), executor=executor,
    )
    if expanded is None:
        raise HTTPException(status_code=404, detail=f"ticker {ticker} not on watchlist")
    return request.app.state.templates.TemplateResponse(
        request, "partials/watchlist_expanded.html.j2", {"expanded": expanded},
    )
