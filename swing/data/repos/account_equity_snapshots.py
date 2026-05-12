"""account_equity_snapshots repository (migration 0017).

Phase 9 Sub-bundle C T-C.2 + spec §3.5 + plan §B file map.

Pure CRUD inside the caller's transaction scope — repo functions DO NOT
commit (Finviz I1 lesson + caller-controlled transaction discipline; the
service layer ``swing/trades/account_equity_snapshots.py`` owns BEGIN
IMMEDIATE / COMMIT / ROLLBACK per plan §0.5 #6).

UPSERT is SELECT-then-UPDATE-or-INSERT (NOT the SQLite ``REPLACE``
shorthand per CLAUDE.md SQLite gotcha + plan §A.8 baseline) so the
snapshot_id PK is preserved across re-record for the same
``(snapshot_date, source)`` — defensive forward compatibility for any
future FK referrer.

Source-ladder precedence per spec §3.5 + §11.4 (Phase 10 hand-off):
``schwab_api`` > ``tos_csv`` > ``manual`` at the same snapshot_date. The
``with_provenance=True`` mode returns ``(winner, suppressed)`` per spec
§3.5 R4 Minor #3 so the UI can render "TOS CSV from <ts> superseded my
manual <ts> entry".
"""
from __future__ import annotations

import sqlite3

from swing.data.models import AccountEquitySnapshot

_SELECT_COLUMNS = (
    "snapshot_id, snapshot_date, equity_dollars, source, "
    "source_artifact_path, recorded_at, recorded_by, notes"
)

# Source-ladder precedence: lower integer wins under MIN(precedence).
# Mirrors spec §3.5 "schwab_api > tos_csv > manual" semantics. Used for
# in-Python sort tie-breaking in get_latest_snapshot_on_or_before; the SQL
# layer cannot express this ordering without a CASE expression, so we
# fetch the same-date candidates and apply the ladder in Python.
_SOURCE_PRECEDENCE: dict[str, int] = {
    "schwab_api": 0,
    "tos_csv": 1,
    "manual": 2,
}


def _row_to_model(row: tuple) -> AccountEquitySnapshot:
    return AccountEquitySnapshot(
        snapshot_id=row[0],
        snapshot_date=row[1],
        equity_dollars=row[2],
        source=row[3],
        source_artifact_path=row[4],
        recorded_at=row[5],
        recorded_by=row[6],
        notes=row[7],
    )


def insert_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_date: str,
    equity_dollars: float,
    source: str,
    source_artifact_path: str | None,
    recorded_at: str,
    recorded_by: str,
    notes: str | None,
) -> int:
    """Pure INSERT inside caller's transaction. Returns assigned snapshot_id."""
    cur = conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (snapshot_date, equity_dollars, source, source_artifact_path,
         recorded_at, recorded_by, notes),
    )
    return int(cur.lastrowid)


def upsert_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_date: str,
    equity_dollars: float,
    source: str,
    source_artifact_path: str | None,
    recorded_at: str,
    recorded_by: str,
    notes: str | None,
) -> int:
    """SELECT-then-UPDATE-or-INSERT keyed on (snapshot_date, source).

    PK preservation is the binding contract — re-record for the same
    ``(snapshot_date, source)`` UPDATEs the existing row's mutable columns
    in place; never DELETE+INSERT. Per CLAUDE.md SQLite gotcha, the
    ``REPLACE`` shorthand would CASCADE-WIPE any child FK referrers +
    reissue a new PK. The UPSERT path here defends against both.

    Returns: snapshot_id of the row (existing if updated, new if inserted).
    """
    row = conn.execute(
        "SELECT snapshot_id FROM account_equity_snapshots "
        "WHERE snapshot_date = ? AND source = ?",
        (snapshot_date, source),
    ).fetchone()
    if row is not None:
        existing_id = int(row[0])
        conn.execute(
            "UPDATE account_equity_snapshots SET "
            "equity_dollars = ?, source_artifact_path = ?, "
            "recorded_at = ?, recorded_by = ?, notes = ? "
            "WHERE snapshot_id = ?",
            (equity_dollars, source_artifact_path, recorded_at,
             recorded_by, notes, existing_id),
        )
        return existing_id
    return insert_snapshot(
        conn,
        snapshot_date=snapshot_date,
        equity_dollars=equity_dollars,
        source=source,
        source_artifact_path=source_artifact_path,
        recorded_at=recorded_at,
        recorded_by=recorded_by,
        notes=notes,
    )


def get_latest_snapshot_on_or_before(
    conn: sqlite3.Connection,
    *,
    asof_date: str,
    with_provenance: bool = False,
) -> (
    AccountEquitySnapshot
    | tuple[AccountEquitySnapshot, list[AccountEquitySnapshot]]
    | None
):
    """Return the most-recent snapshot whose snapshot_date <= asof_date.

    Source-ladder tiebreaker (spec §3.5 + §11.4): when multiple sources
    coexist at the SAME snapshot_date, schwab_api > tos_csv > manual.

    With ``with_provenance=True`` (per spec §3.5 R4 Minor #3): returns
    a tuple ``(winner, suppressed)`` where ``suppressed`` is the list of
    rows at the winning snapshot_date that LOST the precedence contest
    (for operator-meaningful UI rendering).
    """
    # Step 1: find the most-recent snapshot_date <= asof_date.
    max_date = conn.execute(
        "SELECT MAX(snapshot_date) FROM account_equity_snapshots "
        "WHERE snapshot_date <= ?",
        (asof_date,),
    ).fetchone()[0]
    if max_date is None:
        return None
    # Step 2: fetch ALL rows at that date.
    rows = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM account_equity_snapshots "
        "WHERE snapshot_date = ?",
        (max_date,),
    ).fetchall()
    if not rows:
        # Defensive: should not happen given step 1's MAX existed.
        return None
    candidates = [_row_to_model(r) for r in rows]
    # Step 3: pick winner by source ladder; tie-break by snapshot_id DESC
    # (most-recently-inserted row wins among same-source duplicates — a
    # defensive last-write-wins; the unique index normally prevents this).
    candidates.sort(
        key=lambda s: (
            _SOURCE_PRECEDENCE.get(s.source, 99),
            -1 * (s.snapshot_id or 0),
        )
    )
    winner = candidates[0]
    if not with_provenance:
        return winner
    suppressed = [c for c in candidates if c is not winner]
    return (winner, suppressed)


def list_snapshots(
    conn: sqlite3.Connection,
    *,
    limit: int = 20,
) -> list[AccountEquitySnapshot]:
    """Return rows ordered newest-first (snapshot_date DESC, snapshot_id DESC)."""
    rows = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM account_equity_snapshots "
        "ORDER BY snapshot_date DESC, snapshot_id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_model(r) for r in rows]
