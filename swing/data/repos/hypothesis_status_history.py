"""hypothesis_status_history repository (migration 0017).

Phase 9 Sub-bundle C T-C.3 + spec §3.4 + plan §B file map.

Pure CRUD inside the caller's transaction scope — repo functions DO NOT
call ``conn.commit()`` (Finviz I1 lesson + caller-controlled transaction
discipline; the service layer
``swing/trades/hypothesis.py:update_hypothesis_status_with_audit`` owns
BEGIN IMMEDIATE / COMMIT / ROLLBACK per plan §A.1 8-step transactional
sequence).

The supersession sequence on this table is REVERSED from risk_policy
(spec §3.4.0): predecessor's open interval is CLOSED first
(``UPDATE prior SET effective_to = ?``), THEN successor is INSERTed.
There is no intermediate state where two rows share ``effective_to IS
NULL`` for the same hypothesis_id, so the partial-unique index
``ux_hypothesis_status_history_current`` (one row WHERE effective_to IS
NULL per hypothesis) is never momentarily violated mid-transaction.
"""
from __future__ import annotations

import sqlite3

from swing.data.models import HypothesisStatusHistory

_SELECT_COLUMNS = (
    "history_id, hypothesis_id, status, effective_from, "
    "effective_to, change_reason, recorded_at"
)


def _row_to_model(row: tuple) -> HypothesisStatusHistory:
    return HypothesisStatusHistory(
        history_id=row[0],
        hypothesis_id=row[1],
        status=row[2],
        effective_from=row[3],
        effective_to=row[4],
        change_reason=row[5],
        recorded_at=row[6],
    )


def insert_history(
    conn: sqlite3.Connection,
    *,
    hypothesis_id: int,
    status: str,
    effective_from: str,
    effective_to: str | None,
    change_reason: str | None,
    recorded_at: str,
) -> int:
    """Pure INSERT inside caller's transaction. Returns assigned history_id."""
    cur = conn.execute(
        "INSERT INTO hypothesis_status_history ("
        "hypothesis_id, status, effective_from, effective_to, "
        "change_reason, recorded_at"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (hypothesis_id, status, effective_from, effective_to,
         change_reason, recorded_at),
    )
    return int(cur.lastrowid)


def update_close_open_interval(
    conn: sqlite3.Connection,
    *,
    hypothesis_id: int,
    effective_to: str,
) -> int:
    """Close the (single) open-interval row for hypothesis_id.

    Returns: number of rows affected (0 if no open interval; 1 otherwise).
    The partial-unique index `ux_hypothesis_status_history_current`
    guarantees that at most one row matches WHERE effective_to IS NULL per
    hypothesis_id.
    """
    cur = conn.execute(
        "UPDATE hypothesis_status_history "
        "SET effective_to = ? "
        "WHERE hypothesis_id = ? AND effective_to IS NULL",
        (effective_to, hypothesis_id),
    )
    return cur.rowcount


def get_current_status(
    conn: sqlite3.Connection,
    hypothesis_id: int,
) -> HypothesisStatusHistory | None:
    """Return the open-interval row for hypothesis_id, or None."""
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM hypothesis_status_history "
        "WHERE hypothesis_id = ? AND effective_to IS NULL",
        (hypothesis_id,),
    ).fetchone()
    return _row_to_model(row) if row else None


def list_history_for_hypothesis(
    conn: sqlite3.Connection,
    hypothesis_id: int,
) -> list[HypothesisStatusHistory]:
    """Return all history rows for hypothesis_id, oldest-first.

    Ordering: effective_from ASC, history_id ASC (tiebreaker for rows
    with identical ms-precision effective_from — same-instant rows are
    a defensive concern but the ladder is stable under retry).
    """
    rows = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM hypothesis_status_history "
        "WHERE hypothesis_id = ? "
        "ORDER BY effective_from ASC, history_id ASC",
        (hypothesis_id,),
    ).fetchall()
    return [_row_to_model(r) for r in rows]


def list_all_history(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> list[HypothesisStatusHistory]:
    """Return all history rows, newest effective_from first."""
    sql = (
        f"SELECT {_SELECT_COLUMNS} FROM hypothesis_status_history "
        "ORDER BY effective_from DESC, history_id DESC"
    )
    if limit is not None:
        rows = conn.execute(sql + " LIMIT ?", (limit,)).fetchall()
    else:
        rows = conn.execute(sql).fetchall()
    return [_row_to_model(r) for r in rows]
