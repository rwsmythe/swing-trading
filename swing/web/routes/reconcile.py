"""Phase 12.5 #2 Task T-2.5 — web Tier-2 discrepancy-resolution surface.

Read-only GET handler for the dedicated form page at
``/reconcile/discrepancy/{discrepancy_id}/resolve``. The POST companion
handler ships in T-2.6; the error-template's 3 additional branches
(``anchor_mismatch`` / ``service_error`` / ``db_unavailable``) ship at
T-2.6 as well.

Per plan §A T-2.5 acceptance + spec §4.1:

- ``apply_overrides(request.app.state.cfg)`` at route entry (F14 LOCK;
  Phase 12 Sub-bundle B Codex R1 Critical #1 inheritance).
- ``sqlite3.connect(cfg.paths.db_path)`` + ``try/finally: conn.close()``
  (F13 LOCK; Codex R3 M#3 — connection closure guaranteed on ALL paths
  including early-return 404 / 409).
- 404 branch: ``get_discrepancy(conn, discrepancy_id) is None``.
- 409 branch: ``disc.resolution != 'pending_ambiguity_resolution'`` OR
  ``disc.ambiguity_kind is None`` (defensive — schema CHECK in migration
  0019 normally forbids the second case, but covered for hardening).
- Happy path: render ``reconcile_discrepancy_resolve.html.j2`` via the
  T-2.3 builder.
- ZERO Schwab API calls. ZERO DB writes. ZERO transaction openings.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from swing.config_overrides import apply_overrides
from swing.data.repos.reconciliation import get_discrepancy
from swing.evaluation.dates import action_session_for_run
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
)
from swing.web.view_models.reconcile import (
    ReconcileDiscrepancyErrorVM,
    build_reconcile_discrepancy_resolve_vm,
)

log = logging.getLogger(__name__)

router = APIRouter()


def _render_error(
    request: Request,
    *,
    status_code: int,
    error_kind: str,
    error_message: str,
    discrepancy_id: int | None,
    unresolved_count: int,
    recent_multi_leg_count: int,
    disc_resolution: str | None = None,
    disc_resolved_by: str | None = None,
    disc_created_at: str | None = None,
) -> Response:
    """Render ``reconcile_discrepancy_resolve_error.html.j2`` with the
    appropriate ``ReconcileDiscrepancyErrorVM``. Used by 404 + 409 paths
    (and T-2.6 will extend with anchor_mismatch + service_error +
    db_unavailable branches)."""
    try:
        session_date = action_session_for_run(datetime.now()).isoformat()
    except Exception:  # pragma: no cover - defensive
        session_date = "n/a"
    vm = ReconcileDiscrepancyErrorVM(
        session_date=session_date,
        error_kind=error_kind,
        error_message=error_message,
        discrepancy_id=discrepancy_id,
        disc_resolution=disc_resolution,
        disc_resolved_by=disc_resolved_by,
        disc_created_at=disc_created_at,
        unresolved_material_discrepancies_count=unresolved_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "reconcile_discrepancy_resolve_error.html.j2",
        {"vm": vm},
        status_code=status_code,
    )


@router.get(
    "/reconcile/discrepancy/{discrepancy_id}/resolve",
    response_class=HTMLResponse,
)
def reconcile_discrepancy_resolve_form(
    request: Request, discrepancy_id: int,
) -> Response:
    """GET — render the operator Tier-2 resolution form page.

    Flow per spec §4.1 + plan §A T-2.5 acceptance:

    1. ``apply_overrides`` on the raw cfg (F14 LOCK).
    2. Open a short-lived ``sqlite3.Connection``; wrap remaining steps in
       try/finally to guarantee closure (F13 LOCK).
    3. ``get_discrepancy(conn, discrepancy_id)`` -> None: 404 + error
       template with ``error_kind='not_found'``.
    4. Resolution not ``pending_ambiguity_resolution`` OR ambiguity_kind
       is NULL: 409 + error template with ``error_kind='already_resolved'``
       (echoes ``disc.resolution`` + ``disc.resolved_by`` +
       ``disc.created_at``).
    5. Happy path: hand off to ``build_reconcile_discrepancy_resolve_vm``
       (T-2.3 builder; read-only on conn) + render
       ``reconcile_discrepancy_resolve.html.j2``.
    """
    # F14 LOCK — apply_overrides at every web route entry. Phase 12 Sub-
    # bundle B Codex R1 Critical #1 inheritance + Sub-bundle 2 T-2.1
    # SchwabStatus route precedent.
    cfg = apply_overrides(request.app.state.cfg)
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        unresolved_count = count_unresolved_material(conn)
        recent_multi_leg_count = count_recent_multi_leg_auto_corrections(conn)
        disc = get_discrepancy(conn, discrepancy_id)
        if disc is None:
            return _render_error(
                request,
                status_code=404,
                error_kind="not_found",
                error_message=(
                    f"No reconciliation discrepancy exists with id "
                    f"{discrepancy_id}."
                ),
                discrepancy_id=discrepancy_id,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )
        if (
            disc.resolution != "pending_ambiguity_resolution"
            or disc.ambiguity_kind is None
        ):
            return _render_error(
                request,
                status_code=409,
                error_kind="already_resolved",
                error_message=(
                    f"Discrepancy {discrepancy_id} is no longer in "
                    f"pending_ambiguity_resolution state."
                ),
                discrepancy_id=discrepancy_id,
                disc_resolution=disc.resolution,
                disc_resolved_by=disc.resolved_by,
                disc_created_at=disc.created_at,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )
        vm = build_reconcile_discrepancy_resolve_vm(conn, discrepancy_id)
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request,
        "reconcile_discrepancy_resolve.html.j2",
        {"vm": vm},
    )
