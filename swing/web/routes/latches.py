"""Phase 21 Arc A: the read-only latch panel.

A4 -- THE WRITE SEAM IS DELIBERATE AND IT IS NOT THIS GET. `GET /latches`
writes NOTHING AT ALL: not the view record (that is `POST /latches/view`) and
not a Schwab audit row (the broker join is the lazy `POST /latches/orders`).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.web.view_models.latches import build_latch_orders_vm, build_latch_panel_vm

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/latches", response_class=HTMLResponse)
def latches_panel(request: Request):
    """The read-only latch panel. Writes NOTHING (A4)."""
    cfg = apply_overrides(request.app.state.cfg)
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_panel_vm(
            conn, cfg,
            getattr(request.app.state, "price_cache", None),
            getattr(request.app.state, "price_fetch_executor", None),
        )
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "latches.html.j2", {"vm": vm},
    )


@router.post("/latches/orders", response_class=HTMLResponse)
def latches_orders_fragment(request: Request):
    """The lazy broker-order-awareness fragment.

    THIS ENDPOINT IS NOT A SAFE METHOD. It performs an AUDITED external Schwab
    call that inserts a `schwab_api_calls` row -- that is a write. It writes NO
    domain row (no `latch_view_events`, no `trades`, no `fills`). It is a POST
    for exactly that reason: calling it GET would be a lie about the method's
    safety, would contradict A4 inside the arc that asserts A4, and would
    expose a real broker call to browser prefetch / preconnect / refresh.
    """
    cfg = apply_overrides(request.app.state.cfg)
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_orders_vm(conn, cfg, request.app.state)
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "partials/latch_orders.html.j2", {"vm": vm},
    )
