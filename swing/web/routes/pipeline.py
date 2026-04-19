"""Pipeline routes. POST handlers land in Tasks 17–19."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.web.routes.dashboard import _templates
from swing.web.view_models.pipeline import build_pipeline

router = APIRouter()


@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_page(request: Request):
    cfg = request.app.state.cfg
    vm = build_pipeline(cfg=cfg)
    return _templates(request).TemplateResponse(
        request, "pipeline.html.j2", {"vm": vm},
    )
