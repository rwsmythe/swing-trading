"""Phase 13 Theme 2 web routes (T-A.1.6 + later sub-bundles).

T-A.1.6 (this task) ships:
  - ``GET /patterns/exemplars`` — operator spot-check surface.
  - ``POST /patterns/exemplars/{exemplar_id}/action`` — silver -> gold
    promotion, reject, relabel, watch flips.

Later sub-bundles (T2.SB6) extend with ``/patterns/{candidate_id}/review``
+ ``/patterns/queue`` per plan §A.4.

HTMX form-driven trinity per CLAUDE.md gotcha family + plan §A.4 LOCK:
  (a) HX-Request propagation: embedded form carries
      ``hx-headers='{"HX-Request": "true"}'`` per Phase 5 R1 M1.
  (b) Success-path response: 204 No Content + HX-Redirect: /patterns/exemplars
      per Phase 5 R1 M2 (NOT 303 swap-target).
  (c) HX-Redirect target ``/patterns/exemplars`` MUST be a registered route;
      Phase 6 I3 + T-A.1.6 test asserts via app.routes membership.

Session-anchor discipline per §A.13 + CLAUDE.md gotcha: ``session_date``
populated from ``last_completed_session(now())`` (backward-looking; matches
the writers for ``pattern_exemplars.created_at`` which is server-stamped).
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from swing.data.db import connect
from swing.data.models import DETECTOR_PATTERN_CLASSES
from swing.evaluation.dates import last_completed_session
from swing.web.view_models.patterns.exemplars import (
    build_patterns_exemplars_vm,
)

router = APIRouter()

ALLOWED_ACTIONS: tuple[str, ...] = (
    "promote_to_gold",
    "reject",
    "relabel",
    "watch",
)


def _session_date_str() -> str:
    """Backward-looking session anchor per §A.13 LOCK.

    Uses naive ``datetime.now()`` because ``last_completed_session`` does
    ``.replace(tzinfo=ZoneInfo('Pacific/Honolulu'))`` internally — passing
    a UTC-aware datetime would double-localize.
    """
    return last_completed_session(datetime.now()).isoformat()


@router.get("/patterns/exemplars", response_class=HTMLResponse)
def patterns_exemplars_page(request: Request) -> Response:
    """List silver + gold pattern_exemplars for operator spot-check."""
    cfg = request.app.state.cfg
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_exemplars_vm(
            conn, session_date=_session_date_str(),
        )
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "patterns/exemplars.html.j2", {"vm": vm},
    )


@router.post("/patterns/exemplars/{exemplar_id}/action")
def patterns_exemplars_action(
    request: Request,
    exemplar_id: int,
    action: str = Form(...),
    corrected_pattern_class: str | None = Form(default=None),
) -> Response:
    """Apply operator action to one silver exemplar.

    Returns ``204 No Content`` + ``HX-Redirect: /patterns/exemplars`` per
    Phase 5 R1 M2 LOCK (NOT 303 swap-target — htmx.js swallows the 303
    transparently in real browsers).
    """
    if action not in ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"action must be one of {ALLOWED_ACTIONS}; got {action!r}"
            ),
        )

    if action == "relabel" and (
        corrected_pattern_class is None
        or corrected_pattern_class not in DETECTOR_PATTERN_CLASSES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "relabel action requires corrected_pattern_class to be "
                f"one of {DETECTOR_PATTERN_CLASSES}; got "
                f"{corrected_pattern_class!r}"
            ),
        )

    cfg = request.app.state.cfg
    conn = connect(cfg.paths.db_path)
    try:
        now_iso = datetime.now(UTC).isoformat()
        with conn:
            _apply_action(
                conn,
                exemplar_id=exemplar_id,
                action=action,  # type: ignore[arg-type]
                corrected_pattern_class=corrected_pattern_class,
                now_iso=now_iso,
            )
    finally:
        conn.close()

    return Response(
        status_code=204,
        headers={"HX-Redirect": "/patterns/exemplars"},
    )


def _apply_action(
    conn: sqlite3.Connection,
    *,
    exemplar_id: int,
    action: Literal["promote_to_gold", "reject", "relabel", "watch"],
    corrected_pattern_class: str | None,
    now_iso: str,
) -> None:
    """Apply the operator action with raw SQL UPDATE in caller's transaction.

    NO ``INSERT OR REPLACE`` per plan §A.15 LOCK. The audit-trail intent of
    ``pattern_exemplars`` is preserved via UPDATE-in-place; the prior
    ``final_decision`` value is lost on this UPDATE (V1 LOCK — closed-loop
    review surface at T2.SB6 introduces append-only revision history).
    """
    # Read current row state.
    row = conn.execute(
        "SELECT id, label_source, proposed_pattern_class, final_decision "
        "FROM pattern_exemplars WHERE id = ?",
        (exemplar_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"exemplar {exemplar_id} not found",
        )
    _, label_source, proposed_pattern_class, _ = row

    if action == "promote_to_gold":
        # Silver -> Gold promotion: flip label_source + stamp validated_at.
        # Per spec §3.1 invariant #5: curated_gold requires labeler_evidence_json
        # non-NULL; silver rows already have it set (per `fire_claude_silver_label`
        # which always populates), so the UPDATE preserves the constraint.
        #
        # T-A.1.8 Deficiency 2 closure: PRESERVE the operator's relabel
        # intent through gold promotion by ABSORBING final_pattern_class
        # into proposed_pattern_class atomically. Pre-fix the UPDATE
        # unconditionally stamped final_pattern_class=NULL, blocking the
        # operator workflow `relabel:<class>` -> `promote_to_gold` (the
        # relabel target was clobbered + the row landed in gold under
        # the original proposed_pattern_class instead of the corrected
        # class).
        #
        # The dispatch brief proposed "preserve final_pattern_class as-is"
        # but Invariant #1 of pattern_exemplars (schema v20 migration
        # 0020_phase13... line 109) precludes (final_decision='confirmed'
        # AND final_pattern_class IS NOT NULL). The semantic-equivalent
        # schema-compatible fix is to COALESCE the relabel target into
        # proposed_pattern_class + null out final_pattern_class: the
        # operator's class choice survives + Invariant #1 holds (no schema
        # migration required, §B.6 escalation rule preserved). The
        # operator's audit trail of the relabel transition is preserved
        # at T2.SB6's append-only revision-history surface (V1 LOCK in
        # this function's docstring).
        conn.execute(
            "UPDATE pattern_exemplars SET label_source = 'curated_gold', "
            "final_decision = 'confirmed', gold_validated_at = ?, "
            "proposed_pattern_class = "
            "  COALESCE(final_pattern_class, proposed_pattern_class), "
            "final_pattern_class = NULL "
            "WHERE id = ?",
            (now_iso, exemplar_id),
        )
        return

    # T-A.1.8 cross-audit (Deficiency 2 follow-on): the `reject` + `watch`
    # handlers ALSO stamp final_pattern_class=NULL. This is INTENTIONALLY
    # NOT analogous to the promote_to_gold bug: the operator's semantic
    # intent on reject/watch IS to revert the row to an unclassified state
    # (rejected means "this isn't a pattern of any known type"; watch means
    # "no decision yet; keep observing"). The pre-existing tests
    # (test_post_action_reject_flips_final_decision +
    # test_post_action_watch_flips_final_decision) lock this contract.
    # T2.SB6's append-only revision history surface (per V1 LOCK in this
    # function's docstring) preserves audit trail across action transitions
    # without requiring final_pattern_class to carry that history forward.

    if action == "reject":
        conn.execute(
            "UPDATE pattern_exemplars SET final_decision = 'rejected', "
            "final_pattern_class = NULL WHERE id = ?",
            (exemplar_id,),
        )
        return

    if action == "watch":
        conn.execute(
            "UPDATE pattern_exemplars SET final_decision = 'watch', "
            "final_pattern_class = NULL WHERE id = ?",
            (exemplar_id,),
        )
        return

    if action == "relabel":
        # corrected_pattern_class validated non-NULL + distinct from proposed
        # at route entry; double-check the distinct invariant per spec §3.1
        # invariant #1.
        if corrected_pattern_class == proposed_pattern_class:
            raise HTTPException(
                status_code=400,
                detail=(
                    "relabel target must differ from proposed_pattern_class "
                    f"({proposed_pattern_class!r}); got "
                    f"{corrected_pattern_class!r}"
                ),
            )
        conn.execute(
            "UPDATE pattern_exemplars SET final_decision = 'relabeled', "
            "final_pattern_class = ? WHERE id = ?",
            (corrected_pattern_class, exemplar_id),
        )
        return

    raise HTTPException(
        status_code=400, detail=f"unsupported action {action!r}",
    )
