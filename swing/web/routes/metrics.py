"""Phase 10 metrics dashboard routes (plan §A.3).

Single router with 8 surface GETs + 1 umbrella index GET. Sub-bundle A
lands only the index + the router skeleton; Sub-bundles B/C/D/E land
their respective surface endpoints.

Per plan §A.9 + §I.6 LOCK: all Phase 10 surfaces are pure server-rendered
HTML — NO HTMX OOB-swap, NO HX-Redirect, NO embedded forms.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from swing.web.view_models.metrics.hypothesis_progress_card import (
    build_hypothesis_progress_card_vm,
)
from swing.web.view_models.metrics.index import build_metrics_index_vm
from swing.web.view_models.metrics.trade_process_card import (
    build_trade_process_card_vm,
)

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


@router.get("/metrics/trade-process", response_class=HTMLResponse)
def metrics_trade_process(
    request: Request,
    cohort: str | None = Query(default=None),
):
    """Spec §4.1 trade-process card — Sub-bundle B Task T-B.3.

    Renders 5 cohort tabs (4 registry cohorts + "All closed trades").
    The active tab is operator-selected via ``?cohort=<name>``;
    default-active is the FIRST cohort per spec §4.1 binding.
    """
    cfg = request.app.state.cfg
    vm = build_trade_process_card_vm(cfg=cfg, active_cohort_key=cohort)
    return request.app.state.templates.TemplateResponse(
        request, "metrics/trade_process_card.html.j2", {"vm": vm},
    )


@router.get("/metrics/hypothesis-progress", response_class=HTMLResponse)
def metrics_hypothesis_progress(request: Request):
    """Spec §4.2 hypothesis-progress card — Sub-bundle B Task T-B.5.

    Renders the 4 hypothesis_registry cohorts in a row layout with
    progress bars, tripwire indicators, decision_criteria text, and the
    last 5 transition-history entries newest-first (per plan §A.11
    supersession of spec §3.2 V1-limitation).
    """
    cfg = request.app.state.cfg
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    return request.app.state.templates.TemplateResponse(
        request, "metrics/hypothesis_progress_card.html.j2", {"vm": vm},
    )
