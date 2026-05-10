"""Hypothesis registry repo (migration 0008).

Per `docs/hypothesis-recommendation-backend-brief.md` §4.1, the registry's
seed rows + tripwire thresholds + decision criteria are FROZEN at the
migration. The repo intentionally exposes NO API to mutate frozen fields:
`update_hypothesis_status` only writes `status`, `status_changed_at`, and
`status_change_reason`. Any change to the seed plan v0.1 must route through
a NEW migration with explicit version bump (anti-rationalization watch
item, brief §5).
"""
from __future__ import annotations

import sqlite3

from swing.data.models import HypothesisRegistryEntry

_VALID_STATUSES = ("active", "paused", "closed-escaped", "closed-target-met")

# Allowed status transitions per brief §4.6.
# closed-target-met is terminal (no outgoing edges) — once a hypothesis hits
# its target sample with the predicted outcome, reopening it post-data is
# the textbook anti-rationalization move the pre-registration discipline
# exists to prevent.
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"paused", "closed-escaped", "closed-target-met"}),
    "paused": frozenset({"active", "closed-escaped"}),
    "closed-escaped": frozenset({"active"}),
    "closed-target-met": frozenset(),
}


class HypothesisStatusTransitionError(ValueError):
    """Raised when an `update_hypothesis_status` call requests a transition
    not in `_ALLOWED_TRANSITIONS`. Subclass of ValueError so callers
    catching ValueError still see it; the dedicated type lets the CLI emit
    a more pointed message."""


def _row_to_entry(row: tuple) -> HypothesisRegistryEntry:
    return HypothesisRegistryEntry(
        id=row[0],
        name=row[1],
        statement=row[2],
        target_sample_size=row[3],
        decision_criteria=row[4],
        status=row[5],
        consecutive_loss_tripwire=row[6],
        absolute_loss_tripwire_pct=row[7],
        created_at=row[8],
        status_changed_at=row[9],
        status_change_reason=row[10],
        notes=row[11],
    )


_SELECT_COLUMNS = (
    "id, name, statement, target_sample_size, decision_criteria, status, "
    "consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at, "
    "status_changed_at, status_change_reason, notes"
)


def list_hypotheses(
    conn: sqlite3.Connection, *, status_filter: str | None = None,
) -> list[HypothesisRegistryEntry]:
    """Return registry rows ordered by id. Optionally filter by status."""
    if status_filter is not None:
        rows = conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM hypothesis_registry "
            "WHERE status = ? ORDER BY id",
            (status_filter,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM hypothesis_registry ORDER BY id"
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def get_hypothesis(
    conn: sqlite3.Connection, hypothesis_id: int,
) -> HypothesisRegistryEntry | None:
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM hypothesis_registry WHERE id = ?",
        (hypothesis_id,),
    ).fetchone()
    return _row_to_entry(row) if row else None


def update_hypothesis_status(
    conn: sqlite3.Connection,
    hypothesis_id: int,
    *,
    new_status: str,
    reason: str,
    now_iso: str,
) -> None:
    """Mutate `status` (and only status). Records `status_changed_at` +
    `status_change_reason` in the same statement.

    Raises:
      ValueError if `reason` is empty/whitespace, `new_status` is not one
        of the four allowed values, or the hypothesis id is unknown.
      HypothesisStatusTransitionError if the from→to transition is not
        allowed (including same-state "no-op" updates, which are rejected
        so the audit log doesn't fill with redundant rows).
    """
    if new_status not in _VALID_STATUSES:
        raise ValueError(
            f"invalid status {new_status!r}; must be one of {_VALID_STATUSES}"
        )
    if not reason or not reason.strip():
        raise ValueError("reason is required and must be non-empty")

    current = get_hypothesis(conn, hypothesis_id)
    if current is None:
        raise ValueError(f"hypothesis {hypothesis_id} not found")
    allowed_to = _ALLOWED_TRANSITIONS.get(current.status, frozenset())
    if new_status not in allowed_to:
        raise HypothesisStatusTransitionError(
            f"transition {current.status!r} -> {new_status!r} is not allowed; "
            f"allowed from {current.status!r}: {sorted(allowed_to) or '(none — terminal)'}"
        )

    conn.execute(
        "UPDATE hypothesis_registry "
        "SET status = ?, status_changed_at = ?, status_change_reason = ? "
        "WHERE id = ?",
        (new_status, now_iso, reason, hypothesis_id),
    )
