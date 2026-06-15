"""Phase 18 Arc 18-F: the two read-only health drill-down routes.

`GET /health/tool` + `GET /health/research` — full-page navigations (the topbar
stoplights link here via plain <a href>, NOT HTMX). Read-only (SELECTs only);
the `journal_trade_detail_page` pattern.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.web.view_models.health import (
    build_research_health_vm,
    build_tool_health_vm,
)

router = APIRouter()


@router.get("/health/tool", response_class=HTMLResponse)
def health_tool_page(request: Request):
    """The tool-health drill-down: list the 18-E checks (key/status/summary/
    detail). Read-only."""
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            vm = build_tool_health_vm(conn, cfg)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "health_tool.html.j2", {"vm": vm})


@router.get("/health/research", response_class=HTMLResponse)
def health_research_page(request: Request):
    """The research-measurement drill-down: list the 18-D checks, OR the
    not-yet-deployed message when the artifact is absent. Read-only."""
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            vm = build_research_health_vm(conn, cfg)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "health_research.html.j2", {"vm": vm},
    )
