"""GET / — the main dashboard route."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from swing.web.view_models.dashboard import build_dashboard

router = APIRouter()


def _templates(request: Request) -> Jinja2Templates:
    """Lazy-built, per-app templates object (avoids re-scanning the dir)."""
    app = request.app
    tpls = getattr(app.state, "_jinja_templates", None)
    if tpls is None:
        tpls = Jinja2Templates(directory=str(app.state.templates_dir))
        app.state._jinja_templates = tpls
    return tpls


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)
    return _templates(request).TemplateResponse(
        request, "dashboard.html.j2", {"vm": vm},
    )
