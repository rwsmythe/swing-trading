"""Journal route."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from swing.config_overrides import apply_overrides
from swing.web.view_models.journal import DEFAULT_PAGE_SIZE, build_journal

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
):
    cfg = apply_overrides(request.app.state.cfg)
    vm = build_journal(cfg=cfg, period=period, page=page, page_size=page_size)
    return request.app.state.templates.TemplateResponse(
        request, "journal.html.j2", {"vm": vm},
    )
