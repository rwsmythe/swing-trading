"""Phase 10 Sub-bundle E Task T-E.5 — account snapshot capture form.

Web parallel to the existing ``swing account snapshot record`` CLI (Phase 9
Sub-bundle C). Form-render-and-POST surface for manual
``account_equity_snapshots`` capture.

Per electives amendment §2 + plan §A.18 + CLAUDE.md gotcha family:
- GET /account/snapshot renders the form. ``snapshot_date`` server-stamped
  at handler entry from ``last_completed_session(datetime.now())`` per
  Phase 8 server-stamping discipline (lesson #4 + forward-binding lesson
  #24); display-only ``<span class="muted">``; tampered POST body for
  ``snapshot_date`` IGNORED.
- POST /account/snapshot calls :func:`swing.trades.account_equity_snapshots.record_snapshot`
  (Phase 9 Sub-bundle C service that owns BEGIN IMMEDIATE / COMMIT /
  ROLLBACK + REJECTS caller-held transactions per Phase 9 transactional
  discipline + Phase 8 R3→R4 lesson #2).
- Success returns 204 + ``HX-Redirect: /metrics/capital-friction``
  (Phase 5 R1 M2 lesson — htmx.js follows; NOT a 303 swap-target). The
  HX-Redirect target ``/metrics/capital-friction`` was registered by
  Phase 10 Sub-bundle D (verified by route-table assertion in tests per
  Phase 6 I3 lesson).
- Form template wires ``hx-headers='{"HX-Request": "true"}'`` on the
  form element so embedded HTMX context propagates under OriginGuard
  strict-mode (Phase 5 R1 M1 lesson).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from swing.evaluation.dates import (
    action_session_for_run,
    last_completed_session,
)
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.trades.account_equity_snapshots import record_snapshot
from swing.web.view_models.account import AccountSnapshotFormVM

log = logging.getLogger(__name__)

router = APIRouter()


def _render_form(
    request: Request,
    *,
    snapshot_date_display: str,
    unresolved_count: int,
    recent_multi_leg_count: int = 0,
    banner_resolve_link: str | None = None,
    equity_dollars_value: str = "",
    note_value: str = "",
    error_message: str | None = None,
    status_code: int = 200,
) -> Response:
    """Render the snapshot form with the server-stamped session_date."""
    session_date = action_session_for_run(datetime.now()).isoformat()
    vm = AccountSnapshotFormVM(
        session_date=session_date,
        unresolved_material_discrepancies_count=unresolved_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
        snapshot_date_display=snapshot_date_display,
        equity_dollars_value=equity_dollars_value,
        note_value=note_value,
        error_message=error_message,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "account_snapshot_form.html.j2",
        {"vm": vm},
        status_code=status_code,
    )


@router.get("/account/snapshot", response_class=HTMLResponse)
def account_snapshot_form(request: Request) -> Response:
    """GET — render the snapshot capture form."""
    db_path = request.app.state.cfg.paths.db_path
    conn = sqlite3.connect(db_path)
    try:
        unresolved = count_unresolved_material(conn)
        recent_multi_leg = count_recent_multi_leg_auto_corrections(conn)
        banner_resolve_link = (
            fetch_first_pending_ambiguity_resolve_link_path(conn)
        )
    finally:
        conn.close()
    snapshot_date = last_completed_session(datetime.now()).isoformat()
    return _render_form(
        request,
        snapshot_date_display=snapshot_date,
        unresolved_count=unresolved,
        recent_multi_leg_count=recent_multi_leg,
        banner_resolve_link=banner_resolve_link,
    )


@router.post("/account/snapshot")
async def account_snapshot_post(request: Request) -> Response:
    """POST — server-stamp snapshot_date + persist via Phase 9 service."""
    db_path = request.app.state.cfg.paths.db_path
    form = await request.form()
    # Server-stamp at handler entry. Operator-supplied snapshot_date in
    # the POST body is IGNORED (display-only field; no hidden input).
    # Lesson #24 + Phase 8 R2/R3/R4 server-stamping discipline.
    snapshot_date = last_completed_session(datetime.now()).isoformat()
    note_raw = (form.get("note") or "").strip() or None
    equity_raw = (form.get("equity_dollars") or "").strip()

    conn = sqlite3.connect(db_path)
    try:
        unresolved = count_unresolved_material(conn)
        recent_multi_leg = count_recent_multi_leg_auto_corrections(conn)
        banner_resolve_link = (
            fetch_first_pending_ambiguity_resolve_link_path(conn)
        )
    finally:
        conn.close()

    try:
        equity_dollars = float(equity_raw)
    except (TypeError, ValueError):
        return _render_form(
            request,
            snapshot_date_display=snapshot_date,
            unresolved_count=unresolved,
            recent_multi_leg_count=recent_multi_leg,
            banner_resolve_link=banner_resolve_link,
            equity_dollars_value=equity_raw,
            note_value=note_raw or "",
            error_message="equity_dollars must be a finite number",
            status_code=400,
        )

    # Phase 9 service owns BEGIN IMMEDIATE / COMMIT / ROLLBACK +
    # REJECTS caller-held transactions. We MUST NOT wrap the call in our
    # own ``with conn:`` block (Phase 8 R3→R4 lesson + CLAUDE.md "Service-
    # layer with conn:" gotcha + Phase 9 reject-caller-held-tx contract).
    conn = sqlite3.connect(db_path)
    try:
        record_snapshot(
            conn,
            equity_dollars=equity_dollars,
            snapshot_date=snapshot_date,
            notes=note_raw,
        )
    except ValueError as exc:
        return _render_form(
            request,
            snapshot_date_display=snapshot_date,
            unresolved_count=unresolved,
            recent_multi_leg_count=recent_multi_leg,
            banner_resolve_link=banner_resolve_link,
            equity_dollars_value=equity_raw,
            note_value=note_raw or "",
            error_message=str(exc),
            status_code=400,
        )
    finally:
        conn.close()

    # Success path: 204 + HX-Redirect for htmx.js; standard 303 for plain
    # form submits / curl. Target /metrics/capital-friction was shipped
    # by Sub-bundle D; route-table assertion in test_account_snapshot_form
    # verifies registration per Phase 6 I3 lesson.
    if request.headers.get("HX-Request", "").lower() == "true":
        return Response(
            status_code=204,
            headers={"HX-Redirect": "/metrics/capital-friction"},
        )
    return RedirectResponse(url="/metrics/capital-friction", status_code=303)
