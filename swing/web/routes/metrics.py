"""Phase 10 metrics dashboard routes (plan §A.3).

Single router with 8 surface GETs + 1 umbrella index GET. Sub-bundle A
lands only the index + the router skeleton; Sub-bundles B/C/D/E land
their respective surface endpoints.

Per plan §A.9 + §I.6 LOCK: all Phase 10 surfaces are pure server-rendered
HTML — NO HTMX OOB-swap, NO HX-Redirect, NO embedded forms.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.web.view_models.metrics.index import build_metrics_index_vm

router = APIRouter()


@router.get("/metrics", response_class=HTMLResponse)
def metrics_index(request: Request):
    """8-tile navigator for Phase 10 metrics surfaces."""
    db_path = request.app.state.cfg.paths.db_path
    conn = sqlite3.connect(db_path)
    try:
        vm = build_metrics_index_vm(conn)
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "metrics/index.html.j2", {"vm": vm},
    )
