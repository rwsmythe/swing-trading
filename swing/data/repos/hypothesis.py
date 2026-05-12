"""Hypothesis registry repo (migration 0008).

Per `docs/hypothesis-recommendation-backend-brief.md` §4.1, the registry's
seed rows + tripwire thresholds + decision criteria are FROZEN at the
migration. Any change to the seed plan v0.1 must route through a NEW
migration with explicit version bump (anti-rationalization watch item,
brief §5).

Phase 9 Sub-bundle C T-C.4 (per plan §A.1 + §A.1.1 + dispatch brief §0.5
#2): the legacy ``update_hypothesis_status`` function — which mutated
``hypothesis_registry`` directly in the caller's transaction — was
DELETED. Its single CLI call site is rewired to the new service helper
``swing/trades/hypothesis.py:update_hypothesis_status_with_audit`` which
also appends the audit row to ``hypothesis_status_history`` per spec
§3.4.1 single-write-path discipline. The transition rules + status enum
+ the ``HypothesisStatusTransitionError`` exception live at the new
service module.
"""
from __future__ import annotations

import sqlite3

from swing.data.models import HypothesisRegistryEntry


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
