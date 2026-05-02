"""Journal route."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from swing.config_overrides import apply_overrides
from swing.web.view_models.journal import build_journal

router = APIRouter()


@router.get("/journal", response_class=HTMLResponse)
def journal_page(
    request: Request,
    period: Literal["week", "month", "quarter", "ytd", "all"] = Query("month"),
):
    cfg = apply_overrides(request.app.state.cfg)
    vm = build_journal(cfg=cfg, period=period)
    return request.app.state.templates.TemplateResponse(
        request, "journal.html.j2", {"vm": vm},
    )
