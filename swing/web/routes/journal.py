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
