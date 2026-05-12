"""hypothesis status audit service (Phase 9 Sub-bundle C T-C.4).

Spec §3.4.1 + plan §A.1 + §A.1.1 + plan §F + dispatch brief §0.5 #2 + #3 + #4.

Single-write-path discipline: every code path that UPDATEs
``hypothesis_registry.status`` MUST flow through
``update_hypothesis_status_with_audit`` (this module's public entry). The
legacy ``swing/data/repos/hypothesis.py:update_hypothesis_status`` repo
function is DELETED in T-C.4 (per plan §A.1.1 + brief §0.5 #2).

Transactional discipline mirrors Sub-bundle A's ``supersede_active_policy``
+ Sub-bundle B's ``run_tos_reconciliation``:

  - REJECT caller-held transactions at entry (do NOT auto-detect; Phase 8
    R3→R4 lesson + CLAUDE.md gotcha).
  - Own ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``.
  - 8-step sequence per spec §3.4.1 + plan §A.1:

      1. Reject caller-held transaction at entry.
      2. BEGIN IMMEDIATE TRANSACTION (acquires write lock first).
      3. SELECT current status from hypothesis_registry WHERE id=? (now
         reads under the lock — R2 Major #2 fix; closes the
         two-CLI-process race).
      4. If current_status == new_status: ROLLBACK + return
         ``"noop_identity"`` sentinel (NOT raised; CLI / web render as
         INFO "already <status>"; R3 Minor #1 fix).
      5. UPDATE hypothesis_status_history SET effective_to=now WHERE
         hypothesis_id=? AND effective_to IS NULL (closes prior open
         interval).
      6. INSERT INTO hypothesis_status_history (..., effective_to=NULL,
         change_reason, recorded_at=now_ms).
      7. UPDATE hypothesis_registry SET status=new_status,
         status_changed_at=now_ms, status_change_reason=reason.
      8. COMMIT.

Allowed transitions (preserved from the legacy repo function — operator
discipline contract from `docs/hypothesis-recommendation-backend-brief.md`
§4.6):

  - active → paused | closed-escaped | closed-target-met
  - paused → active | closed-escaped
  - closed-escaped → active
  - closed-target-met → (terminal)

Identity transitions (e.g., active → active) are treated as
NoOpIdentityTransition per spec §3.4.1 R3 Minor #1; the legacy repo
function REJECTED them as transition errors. This is the one V1 behavior
CHANGE in T-C.4 — the operator-facing CLI message also changes from ERROR
to INFO.
"""
from __future__ import annotations

import sqlite3
from typing import Literal

from swing.data.datetime_helpers import now_ms
from swing.data.repos.hypothesis_status_history import (
    insert_history,
    update_close_open_interval,
)

# Mirrors hypothesis_registry CHECK enum (migration 0008) + the
# HypothesisStatusHistory dataclass validator.
HYPOTHESIS_STATUSES: tuple[str, ...] = (
    "active",
    "paused",
    "closed-escaped",
    "closed-target-met",
)

# Allowed status transitions per brief §4.6 (preserved from the legacy
# repo function). closed-target-met is TERMINAL (no outgoing edges) per
# anti-rationalization discipline.
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"paused", "closed-escaped", "closed-target-met"}),
    "paused": frozenset({"active", "closed-escaped"}),
    "closed-escaped": frozenset({"active"}),
    "closed-target-met": frozenset(),
}


class CallerHeldTransactionError(RuntimeError):
    """Raised when ``update_hypothesis_status_with_audit`` is called while
    the connection holds an open transaction.

    Phase 8 R3→R4 lesson + CLAUDE.md gotcha "in_transaction auto-detect
    re-introduces the very race the explicit lock was meant to close":
    single-transaction services own BEGIN IMMEDIATE / COMMIT / ROLLBACK;
    they REJECT caller-held transactions rather than silently
    auto-detecting (auto-detect is the failure mode).
    """


class HypothesisStatusTransitionError(ValueError):
    """Raised when the requested transition is not in ``_ALLOWED_TRANSITIONS``.

    Preserved from the legacy repo so existing CLI tests (and the CLI
    handler) keep their pointed error message. Subclass of ValueError so
    callers catching ValueError still see it.
    """


def _normalize_to_ms_day_start(value: str) -> str:
    """Coerce a hypothesis_registry.created_at value to ms-precision
    day-start anchor (mirrors the migration 0017 seed pattern).

    Migration 0008 stores created_at as a date-only ``YYYY-MM-DD``
    string; the migration 0017 seed normalizes that to
    ``YYYY-MM-DDT00:00:00.000``. Post-migration hypotheses may have an
    arbitrary value here, including a full datetime; this helper keeps
    the seed effective_from format uniform so the partial-unique +
    chronology invariants hold.
    """
    s = (value or "").strip()
    if not s:
        # Defensive fallback: empty created_at → epoch ms-precision day.
        return "1970-01-01T00:00:00.000"
    # Take the date portion (first 10 chars: YYYY-MM-DD) and append the
    # day-start anchor. If the input is malformed, the dataclass
    # __post_init__ cross-field check still catches downstream errors.
    date_part = s[:10]
    return f"{date_part}T00:00:00.000"


def update_hypothesis_status_with_audit(
    conn: sqlite3.Connection,
    *,
    hypothesis_id: int,
    new_status: str,
    change_reason: str | None,
) -> Literal["transition", "noop_identity"]:
    """Update hypothesis status + append audit row in a single transaction.

    Returns:
      - ``"transition"``: a real state change happened; both the audit
        history row INSERT and the registry UPDATE committed.
      - ``"noop_identity"``: ``current_status == new_status`` at the time
        the write lock was acquired. ROLLBACK + return; no audit row, no
        registry UPDATE. CLI / web render as INFO, not ERROR.

    Raises:
      ``CallerHeldTransactionError`` if conn already holds a transaction.
      ``ValueError`` for invalid new_status / empty change_reason /
        unknown hypothesis_id.
      ``HypothesisStatusTransitionError`` for disallowed transitions
        (e.g., closed-target-met → active).
    """
    # Step 1: reject caller-held transaction.
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "update_hypothesis_status_with_audit owns its own transaction; "
            "caller MUST NOT hold an open transaction. See CLAUDE.md gotcha "
            "'in_transaction auto-detect outer transaction guards re-introduce "
            "the very race the explicit lock was meant to close'."
        )

    # Pre-write validation: surface bad inputs without acquiring a lock.
    if new_status not in HYPOTHESIS_STATUSES:
        raise ValueError(
            f"invalid status {new_status!r}; must be one of "
            f"{HYPOTHESIS_STATUSES}"
        )
    if not change_reason or not change_reason.strip():
        raise ValueError("change_reason is required and must be non-empty")

    # Step 2: BEGIN IMMEDIATE (acquires the write lock first).
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Step 3: SELECT current status under the lock. We additionally
        # pull created_at to support the post-migration-seed synthesis
        # path below (Codex R1 Major #3 fix).
        row = conn.execute(
            "SELECT status, created_at FROM hypothesis_registry "
            "WHERE id = ?",
            (hypothesis_id,),
        ).fetchone()
        if row is None:
            # ROLLBACK + raise; we never reached the audit append.
            conn.rollback()
            raise ValueError(f"hypothesis {hypothesis_id} not found")
        current_status, registry_created_at = row[0], row[1]

        # Step 4: identity transition → noop sentinel.
        if current_status == new_status:
            conn.rollback()
            return "noop_identity"

        # Transition validation under the lock (R2 Major #2 fix scope).
        allowed_to = _ALLOWED_TRANSITIONS.get(current_status, frozenset())
        if new_status not in allowed_to:
            conn.rollback()
            raise HypothesisStatusTransitionError(
                f"transition {current_status!r} -> {new_status!r} is not "
                f"allowed; allowed from {current_status!r}: "
                f"{sorted(allowed_to) or '(none — terminal)'}"
            )

        # Step 5: close prior open-interval row. Capture rowcount so we
        # can detect a post-migration hypothesis that lacks the
        # migration seed (Codex R1 Major #3 fix). The migration seeded
        # ONCE per existing hypothesis_registry row; new rows added
        # post-migration via direct SQL or future create-hypothesis web
        # forms have NO history row + would otherwise lose their
        # initial-status audit interval on first transition.
        now = now_ms()
        closed = update_close_open_interval(
            conn,
            hypothesis_id=hypothesis_id,
            effective_to=now,
        )

        if closed == 0:
            # No open interval found — synthesize the missing predecessor
            # so the audit trail captures the initial status interval
            # before this transition. Mirrors the migration seed shape:
            # effective_from = day-start anchor of registry.created_at,
            # effective_to = now, status = current_status (the OLD
            # status), change_reason = explicit self-documenting marker.
            seed_effective_from = _normalize_to_ms_day_start(
                registry_created_at
            )
            # Guard: if registry.created_at is itself after `now` (clock
            # skew / mistaken backfill), clamp to `now` so the dataclass
            # cross-field invariant effective_from <= effective_to holds.
            if seed_effective_from > now:
                seed_effective_from = now
            insert_history(
                conn,
                hypothesis_id=hypothesis_id,
                status=current_status,
                effective_from=seed_effective_from,
                effective_to=now,
                change_reason=(
                    "auto-synthesized predecessor "
                    "(post-migration hypothesis lacked seed history row)"
                ),
                recorded_at=now,
            )

        # Step 6: INSERT new open-interval row.
        insert_history(
            conn,
            hypothesis_id=hypothesis_id,
            status=new_status,
            effective_from=now,
            effective_to=None,
            change_reason=change_reason,
            recorded_at=now,
        )

        # Step 7: UPDATE hypothesis_registry (denormalized current-row view).
        conn.execute(
            "UPDATE hypothesis_registry SET status = ?, "
            "status_changed_at = ?, status_change_reason = ? "
            "WHERE id = ?",
            (new_status, now, change_reason, hypothesis_id),
        )

        # Step 8: COMMIT.
        conn.commit()
        return "transition"
    except Exception:
        # Any non-noop / non-rollback path that raises after BEGIN IMMEDIATE
        # must roll back to release the write lock + leave the DB in the
        # pre-call state. Re-raise so the caller sees the error.
        if conn.in_transaction:
            conn.rollback()
        raise


__all__ = [
    "HYPOTHESIS_STATUSES",
    "CallerHeldTransactionError",
    "HypothesisStatusTransitionError",
    "update_hypothesis_status_with_audit",
]
