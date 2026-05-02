"""GET / — the main dashboard route."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.config_overrides import apply_overrides
from swing.web.view_models.dashboard import build_dashboard

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
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
