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

import json
import sqlite3
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from swing.data.db import connect
from swing.data.models import DETECTOR_PATTERN_CLASSES, PatternExemplar
from swing.data.repos import pattern_evaluations as evals_repo
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.evaluation.dates import last_completed_session
from swing.web.view_models.patterns.exemplars import (
    build_patterns_exemplars_vm,
)
from swing.web.view_models.patterns.review_form import (
    build_patterns_review_form_vm,
)

router = APIRouter()

ALLOWED_ACTIONS: tuple[str, ...] = (
    "promote_to_gold",
    "reject",
    "relabel",
    "watch",
)

# Per spec section 5.10 6-decision enum (lines 778-783 VERBATIM). Canonical
# allowlist for the closed-loop review form's operator choices. Mirrors are
# duplicated only in tests; production parses Form input against this set.
PATTERN_REVIEW_DECISIONS: tuple[str, ...] = (
    "confirm",
    "watch",
    "reject",
    "relabel",
    "pattern_present_outside_window",
    "multiple_overlapping_patterns",
)

# Mapping from operator decision to pattern_exemplars.final_decision per
# spec section 5.10 lines 778-790 LOCK.
_DECISION_TO_FINAL_DECISION: dict[str, str] = {
    "confirm": "confirmed",
    "watch": "watch",
    "reject": "rejected",
    "relabel": "relabeled",
    "pattern_present_outside_window": "confirmed",
    "multiple_overlapping_patterns": "confirmed",
}


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
    # Read current row state (incl. labeler_evidence_json +
    # final_pattern_class for the promote_to_gold audit-trail branch
    # added at T-A.1.8 Codex R1 Major #2 closure).
    row = conn.execute(
        "SELECT id, label_source, proposed_pattern_class, final_decision, "
        "final_pattern_class, labeler_evidence_json "
        "FROM pattern_exemplars WHERE id = ?",
        (exemplar_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"exemplar {exemplar_id} not found",
        )
    (
        _,
        label_source,
        proposed_pattern_class,
        _,
        current_final_pattern_class,
        current_labeler_evidence_json,
    ) = row

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
        # operator workflow `relabel:<class>` -> `promote_to_gold`.
        #
        # The dispatch brief proposed "preserve final_pattern_class as-is"
        # but Invariant #1 of pattern_exemplars (schema v20 migration
        # 0020_phase13... line 109) precludes (final_decision='confirmed'
        # AND final_pattern_class IS NOT NULL). The semantic-equivalent
        # schema-compatible fix COALESCEs the relabel target into
        # proposed_pattern_class + nulls final_pattern_class (Invariant #1
        # holds, §B.6 escalation rule preserved).
        #
        # T-A.1.8 Codex R1 Major #2 closure: the COALESCE rewrite would
        # otherwise destroy the original proposed_pattern_class history
        # (e.g., for a vcp -> flat_base relabel-then-promote the row no
        # longer records the original proposal was 'vcp'). PRESERVE the
        # transition trail in labeler_evidence_json under
        # `gold_promotion_*` keys BEFORE the UPDATE so downstream confusion
        # analysis + cohort segmentation retain the original-proposal
        # signal. This is performed only when final_pattern_class IS NOT
        # NULL (the relabel-then-promote path); unmodified-silver-promote
        # leaves labeler_evidence_json byte-stable.
        if current_final_pattern_class is not None:
            try:
                evidence_dict = (
                    json.loads(current_labeler_evidence_json)
                    if current_labeler_evidence_json
                    else {}
                )
            except json.JSONDecodeError:
                # Defensive: if labeler_evidence_json is corrupt, do NOT
                # destroy history silently; surface a server-side 500 so
                # the operator can investigate via direct DB inspection.
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"exemplar {exemplar_id} labeler_evidence_json "
                        "is not valid JSON; cannot preserve gold-promotion "
                        "audit trail. Investigate via direct DB inspection."
                    ),
                ) from None
            if not isinstance(evidence_dict, dict):
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"exemplar {exemplar_id} labeler_evidence_json "
                        f"decoded to {type(evidence_dict).__name__}, not "
                        "an object; cannot preserve gold-promotion audit "
                        "trail."
                    ),
                )
            evidence_dict["gold_promotion_original_proposed_pattern_class"] = (
                proposed_pattern_class
            )
            evidence_dict["gold_promotion_corrected_pattern_class"] = (
                current_final_pattern_class
            )
            evidence_dict["gold_promotion_at"] = now_iso
            new_evidence_json = json.dumps(evidence_dict, sort_keys=True)
            conn.execute(
                "UPDATE pattern_exemplars SET label_source = 'curated_gold', "
                "final_decision = 'confirmed', gold_validated_at = ?, "
                "labeler_evidence_json = ?, "
                "proposed_pattern_class = ?, "
                "final_pattern_class = NULL "
                "WHERE id = ?",
                (
                    now_iso,
                    new_evidence_json,
                    current_final_pattern_class,
                    exemplar_id,
                ),
            )
            return
        # Unmodified-silver-promote: byte-stable labeler_evidence_json +
        # proposed_pattern_class UNCHANGED. Single UPDATE keeps the row
        # untouched outside the canonical promotion fields.
        conn.execute(
            "UPDATE pattern_exemplars SET label_source = 'curated_gold', "
            "final_decision = 'confirmed', gold_validated_at = ? "
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


# ---------------------------------------------------------------------------
# Phase 13 T2.SB6b T-A.6.3 — `/patterns/{candidate_id}/review` review form
# ---------------------------------------------------------------------------


@router.get(
    "/patterns/{candidate_id}/review", response_class=HTMLResponse,
)
def patterns_review_page(request: Request, candidate_id: int) -> Response:
    """Render the 8-item closed-loop review form for one pattern_evaluation.

    Per spec section 5.10 + plan G.9 T-A.6.3. Returns 404 if the
    pattern_evaluations row does not exist.
    """
    cfg = request.app.state.cfg
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_review_form_vm(
            conn, candidate_id=candidate_id,
            session_date=_session_date_str(),
        )
    finally:
        conn.close()
    if vm is None:
        raise HTTPException(
            status_code=404,
            detail=f"candidate {candidate_id} not found",
        )
    return request.app.state.templates.TemplateResponse(
        request, "patterns/review.html.j2", {"vm": vm},
    )


@router.post("/patterns/{candidate_id}/review")
def patterns_review_post(
    request: Request,
    candidate_id: int,
    decision: str = Form(...),
    corrected_pattern_class: str | None = Form(default=None),
    corrected_window_start_date: str | None = Form(default=None),
    corrected_window_end_date: str | None = Form(default=None),
    additional_pattern_classes: str | None = Form(default=None),
    notes: str | None = Form(default=None),
) -> Response:
    """Persist the operator's review decision per spec section 5.10.

    L9 LOCK (T3.SB3 R1 M#2): SERVER-RECOMPUTES proposed_pattern_class from
    pattern_evaluations at POST time; any operator-supplied hidden
    proposed_pattern_class form field is IGNORED. The form is rendered
    without that hidden input to begin with, but defense-in-depth: if a
    tampered curl invocation supplies it, the server uses the canonical
    value from the pattern_evaluations row.

    HTMX trinity per L12 LOCK: returns 204 + HX-Redirect: /patterns/queue
    on success.
    """
    if decision not in PATTERN_REVIEW_DECISIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"decision must be one of {PATTERN_REVIEW_DECISIONS}; "
                f"got {decision!r}"
            ),
        )

    cfg = request.app.state.cfg
    conn = connect(cfg.paths.db_path)
    try:
        evaluation = evals_repo.get_evaluation_by_id(conn, candidate_id)
        if evaluation is None:
            raise HTTPException(
                status_code=404,
                detail=f"candidate {candidate_id} not found",
            )

        # L9 LOCK: RECOMPUTE proposed_pattern_class from canonical state.
        canonical_proposed = evaluation.pattern_class

        if decision == "relabel":
            if (
                corrected_pattern_class is None
                or corrected_pattern_class not in DETECTOR_PATTERN_CLASSES
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "relabel requires corrected_pattern_class one of "
                        f"{DETECTOR_PATTERN_CLASSES}; got "
                        f"{corrected_pattern_class!r}"
                    ),
                )
            if corrected_pattern_class == canonical_proposed:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "relabel target must differ from canonical "
                        f"proposed_pattern_class ({canonical_proposed!r})"
                    ),
                )

        now_iso = datetime.now(UTC).isoformat()
        # Trade-opened resolution per spec section 5.10 label_source split.
        # V1 heuristic: if any trade row exists for the ticker, treat as
        # organic_trade_history; else closed_loop_review. (The spec
        # references "candidate-to-trade backlink at trades.candidate_id"
        # but the trades schema does NOT carry candidate_id; ticker-scoped
        # lookup is the V1-pragmatic proxy.)
        trade_opened = bool(conn.execute(
            "SELECT 1 FROM trades WHERE ticker = ? LIMIT 1",
            (evaluation.ticker,),
        ).fetchone())

        if decision == "confirm" and trade_opened:
            base_label_source = "organic_trade_history"
        else:
            base_label_source = "closed_loop_review"

        # gold_validated_at policy per spec section 5.10: every branch
        # except rejected stamps now; rejected stays NULL.
        final_decision = _DECISION_TO_FINAL_DECISION[decision]
        gold_validated_at = (
            now_iso if final_decision != "rejected" else None
        )

        # Window emit shape per decision branch.
        start_date = evaluation.window_start_date
        end_date = evaluation.window_end_date
        if decision == "pattern_present_outside_window":
            # Operator-supplied corrected window overrides detector framing.
            if corrected_window_start_date:
                start_date = corrected_window_start_date
            if corrected_window_end_date:
                end_date = corrected_window_end_date

        # Build primary exemplar row.
        with conn:
            # Invariant #4 + #5 dictate that closed_loop_review +
            # organic_trade_history sources require geometric_score_json
            # non-NULL AND labeler_evidence_json NULL. The evaluation row
            # always carries geometric_score_json; we forward it.
            primary = PatternExemplar(
                id=None,
                ticker=evaluation.ticker,
                timeframe="daily",
                start_date=start_date,
                end_date=end_date,
                proposed_pattern_class=canonical_proposed,
                final_decision=final_decision,
                label_source=base_label_source,
                structural_evidence_json=evaluation.structural_evidence_json,
                created_at=now_iso,
                created_by="operator",
                final_pattern_class=(
                    corrected_pattern_class if decision == "relabel"
                    else None
                ),
                gold_validated_at=gold_validated_at,
                geometric_score_json=evaluation.geometric_score_json,
                labeler_evidence_json=None,
                # Per Phase 6 deviation #3 gotcha: empty `notes` form input
                # MUST persist as NULL, not "" (nullable schema column).
                notes=(notes or None),
            )
            exemplars_repo.insert_exemplar(conn, primary)

            if decision == "multiple_overlapping_patterns":
                # Emit additional rows for operator-noted overlapping
                # patterns. Schema invariants enforced per row by the
                # dataclass.
                additional = _parse_additional_classes(
                    additional_pattern_classes, exclude=canonical_proposed,
                )
                for extra_class in additional:
                    extra = PatternExemplar(
                        id=None,
                        ticker=evaluation.ticker,
                        timeframe="daily",
                        start_date=start_date,
                        end_date=end_date,
                        proposed_pattern_class=extra_class,
                        final_decision="confirmed",
                        label_source="closed_loop_review",
                        structural_evidence_json=(
                            evaluation.structural_evidence_json
                        ),
                        created_at=now_iso,
                        created_by="operator",
                        gold_validated_at=now_iso,
                        geometric_score_json=evaluation.geometric_score_json,
                        labeler_evidence_json=None,
                        notes=(
                            "overlapping pattern noted at review of "
                            f"candidate {candidate_id}"
                        ),
                    )
                    exemplars_repo.insert_exemplar(conn, extra)
    finally:
        conn.close()

    return Response(
        status_code=204, headers={"HX-Redirect": "/patterns/queue"},
    )


def _parse_additional_classes(
    raw: str | None, *, exclude: str,
) -> list[str]:
    """Parse the operator-supplied additional pattern classes per the
    multiple_overlapping_patterns branch.

    Accepts a comma-separated string (form input) and filters down to the
    DETECTOR_PATTERN_CLASSES allowlist minus the primary class to avoid
    duplicate-key conflicts on the partial unique index.
    """
    if not raw:
        return []
    out: list[str] = []
    for piece in raw.split(","):
        cls = piece.strip()
        if not cls or cls == exclude or cls not in DETECTOR_PATTERN_CLASSES:
            continue
        if cls in out:
            continue
        out.append(cls)
    return out


# ---------------------------------------------------------------------------
# Phase 13 T2.SB6b T-A.6.4 — `/patterns/queue` active-learning prioritization
# ---------------------------------------------------------------------------


@router.get("/patterns/queue", response_class=HTMLResponse)
def patterns_queue_page(request: Request) -> Response:
    """Render the active-learning prioritized review queue.

    Per spec section 5.10 lines 796-801 + plan G.9 T-A.6.4. Renders the
    top-K candidates by 4-criterion ranking. Composed in
    swing/patterns/active_learning.py.
    """
    from swing.web.view_models.patterns.queue import (
        build_patterns_queue_vm,
    )
    cfg = request.app.state.cfg
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_patterns_queue_vm(
            conn, session_date=_session_date_str(), top_k=20,
        )
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "patterns/queue.html.j2", {"vm": vm},
    )
