"""reconciliation_corrections repository (migration 0019).

Phase 12 Sub-bundle C Sub-sub-bundle C.A spec §3.1 + plan §B.3. Pure
CRUD inside the caller's transaction scope — repo functions DO NOT call
``conn.commit()`` (Finviz I1 lesson + Phase 9 Sub-bundle A + B repo
precedent; caller-controlled transaction discipline). The auto-correct
service layer at T-C.* owns BEGIN IMMEDIATE / COMMIT / ROLLBACK.

NO ``INSERT OR REPLACE`` anywhere — UPDATE-only semantics for the
supersede-pointer-set helper (per CLAUDE.md ``INSERT OR REPLACE``
cascade-wipe gotcha). All SQL parameterized.

The 7 public functions are:
    - insert_correction
    - get_correction
    - list_corrections_by_discrepancy (applied_at ASC, correction_id ASC tiebreak)
    - list_corrections_by_run
    - list_corrections_by_affected_row
    - update_superseded_by (UPDATE only; supports tier-3 override apply +
      multi-row correction-set anchor pattern per spec §3.1.1 two-step
      INSERT-then-UPDATE-self-reference)
    - count_corrections_by_action (returns dict with all 3 keys initialised
      to 0 so callers never face KeyError)
"""
from __future__ import annotations

import sqlite3

from swing.data.models import ReconciliationCorrection

# Column list mirrors the migration 0019 CREATE TABLE column order which
# matches the ReconciliationCorrection dataclass field order — explicit
# SELECT per project convention.
_CORRECTION_COLUMNS = (
    "correction_id, discrepancy_id, correction_action, correction_choice, "
    "affected_table, affected_row_id, field_name, "
    "pre_correction_value_json, source_canonical_value_json, "
    "applied_value_json, operator_truth_value_json, "
    "applied_at, applied_by, correction_set_id, "
    "superseded_by_correction_id, risk_policy_id_at_correction, "
    "schwab_api_call_id, reconciliation_run_id, "
    "correction_reason, notes"
)


def _row_to_correction(row: tuple) -> ReconciliationCorrection:
    return ReconciliationCorrection(
        correction_id=row[0],
        discrepancy_id=row[1],
        correction_action=row[2],
        correction_choice=row[3],
        affected_table=row[4],
        affected_row_id=row[5],
        field_name=row[6],
        pre_correction_value_json=row[7],
        source_canonical_value_json=row[8],
        applied_value_json=row[9],
        operator_truth_value_json=row[10],
        applied_at=row[11],
        applied_by=row[12],
        correction_set_id=row[13],
        superseded_by_correction_id=row[14],
        risk_policy_id_at_correction=row[15],
        schwab_api_call_id=row[16],
        reconciliation_run_id=row[17],
        correction_reason=row[18],
        notes=row[19],
    )


def insert_correction(
    conn: sqlite3.Connection,
    correction: ReconciliationCorrection,
) -> int:
    """Pure INSERT inside the caller's transaction scope.

    The ``correction_id`` field on the input is ignored (AUTOINCREMENT
    assigns it at INSERT time). Returns the newly-assigned ``correction_id``.

    Caller controls transaction (auto-correct service owns BEGIN
    IMMEDIATE / COMMIT per spec §3.8 + plan §C.4 — repo does NOT commit).
    """
    cur = conn.execute(
        "INSERT INTO reconciliation_corrections ("
        "discrepancy_id, correction_action, correction_choice, "
        "affected_table, affected_row_id, field_name, "
        "pre_correction_value_json, source_canonical_value_json, "
        "applied_value_json, operator_truth_value_json, "
        "applied_at, applied_by, correction_set_id, "
        "superseded_by_correction_id, risk_policy_id_at_correction, "
        "schwab_api_call_id, reconciliation_run_id, "
        "correction_reason, notes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            correction.discrepancy_id,
            correction.correction_action,
            correction.correction_choice,
            correction.affected_table,
            correction.affected_row_id,
            correction.field_name,
            correction.pre_correction_value_json,
            correction.source_canonical_value_json,
            correction.applied_value_json,
            correction.operator_truth_value_json,
            correction.applied_at,
            correction.applied_by,
            correction.correction_set_id,
            correction.superseded_by_correction_id,
            correction.risk_policy_id_at_correction,
            correction.schwab_api_call_id,
            correction.reconciliation_run_id,
            correction.correction_reason,
            correction.notes,
        ),
    )
    return cur.lastrowid


def get_correction(
    conn: sqlite3.Connection,
    correction_id: int,
) -> ReconciliationCorrection | None:
    """Return the correction row by PK, or None when no match."""
    row = conn.execute(
        f"SELECT {_CORRECTION_COLUMNS} FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (correction_id,),
    ).fetchone()
    return _row_to_correction(row) if row else None


def list_corrections_by_discrepancy(
    conn: sqlite3.Connection,
    discrepancy_id: int,
) -> list[ReconciliationCorrection]:
    """List corrections for one discrepancy ordered chronologically.

    Order is ``applied_at ASC, correction_id ASC`` — deterministic
    tiebreak on tied timestamps per Phase 10 Sub-bundle D lesson #26
    (SQL ORDER BY on potentially-tied columns must include a deterministic
    tiebreaker, typically PK monotonicity).
    """
    rows = conn.execute(
        f"SELECT {_CORRECTION_COLUMNS} FROM reconciliation_corrections "
        "WHERE discrepancy_id = ? "
        "ORDER BY applied_at ASC, correction_id ASC",
        (discrepancy_id,),
    ).fetchall()
    return [_row_to_correction(r) for r in rows]


def list_corrections_by_run(
    conn: sqlite3.Connection,
    run_id: int,
) -> list[ReconciliationCorrection]:
    """List corrections emitted under one reconciliation_runs row."""
    rows = conn.execute(
        f"SELECT {_CORRECTION_COLUMNS} FROM reconciliation_corrections "
        "WHERE reconciliation_run_id = ? "
        "ORDER BY applied_at ASC, correction_id ASC",
        (run_id,),
    ).fetchall()
    return [_row_to_correction(r) for r in rows]


def list_corrections_by_affected_row(
    conn: sqlite3.Connection,
    affected_table: str,
    affected_row_id: int,
) -> list[ReconciliationCorrection]:
    """List corrections that touched a specific (affected_table, row_id) pair.

    Supports per-fill + per-trade provenance queries on the trade detail
    UI surface. Order is ``applied_at ASC, correction_id ASC`` for
    deterministic chronological replay.
    """
    rows = conn.execute(
        f"SELECT {_CORRECTION_COLUMNS} FROM reconciliation_corrections "
        "WHERE affected_table = ? AND affected_row_id = ? "
        "ORDER BY applied_at ASC, correction_id ASC",
        (affected_table, affected_row_id),
    ).fetchall()
    return [_row_to_correction(r) for r in rows]


def update_superseded_by(
    conn: sqlite3.Connection,
    correction_id: int,
    superseded_by_correction_id: int,
) -> None:
    """UPDATE ``superseded_by_correction_id`` on an existing correction row.

    Used by:
      - The tier-3 override apply at T-C.4 — when an operator overrides a
        prior tier-1 correction, the operator's new row's PK is stamped
        on the old row's ``superseded_by_correction_id`` so list queries
        can filter for the currently-effective tip of the chain.
      - The multi-row correction-set anchor pattern (spec §3.1.1 two-step:
        INSERT anchor → UPDATE self-reference for ``correction_set_id =
        correction_id``). That second step is a different column (the
        anchor uses ``correction_set_id``), but the same UPDATE-only
        discipline applies.

    UPDATE only — NO ``INSERT OR REPLACE`` per CLAUDE.md cascade-wipe
    gotcha.
    """
    conn.execute(
        "UPDATE reconciliation_corrections "
        "SET superseded_by_correction_id = ? "
        "WHERE correction_id = ?",
        (superseded_by_correction_id, correction_id),
    )


def count_corrections_by_action(
    conn: sqlite3.Connection,
) -> dict[str, int]:
    """Return per-action counts for the briefing.md Reconciliation section.

    Returns a dict with all three CHECK-enum values keyed to zero by
    default so callers never face a ``KeyError`` when no rows exist.
    """
    counts: dict[str, int] = {
        "auto_applied": 0,
        "operator_resolved_ambiguity": 0,
        "operator_overridden": 0,
    }
    rows = conn.execute(
        "SELECT correction_action, COUNT(*) "
        "FROM reconciliation_corrections "
        "GROUP BY correction_action"
    ).fetchall()
    for action, count in rows:
        # Defensive: ignore unknown actions in case of CHECK enum drift.
        if action in counts:
            counts[action] = int(count)
    return counts
