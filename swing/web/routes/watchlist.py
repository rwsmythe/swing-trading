"""Watchlist routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from swing.web.routes.dashboard import _templates
from swing.web.view_models.watchlist import build_watchlist, build_watchlist_expanded

router = APIRouter()


@router.get("/watchlist", response_class=HTMLResponse)
def watchlist_page(request: Request):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    vm = build_watchlist(cfg=cfg, cache=cache, executor=executor)
    return _templates(request).TemplateResponse(
        request, "watchlist.html.j2", {"vm": vm},
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
    return _templates(request).TemplateResponse(
        request, "partials/watchlist_expanded.html.j2", {"expanded": expanded},
    )
