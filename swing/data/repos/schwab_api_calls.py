"""schwab_api_calls repository (migration 0018).

Phase 11 Sub-bundle A T-A.8 + plan §B.1 file map.

Caller-controlled tx discipline — repo functions DO NOT issue BEGIN /
COMMIT / ROLLBACK (Finviz I1 lesson family + Phase 9 Sub-bundle C
account_equity_snapshots precedent). The service layer at T-A.9
(``swing/integrations/schwab/audit.py`` or equivalent) will own
BEGIN IMMEDIATE / COMMIT / ROLLBACK per the project's three-piece
transactional discipline family.

UPDATE-in-place ONLY — NEVER ``INSERT OR REPLACE`` per CLAUDE.md
gotcha. The audit row's PK is the immutable handle the service layer
threads through the request lifecycle (insert_in_flight → update_outcome
→ optional update_linked_*), so a REPLACE-based update would silently
reassign the AUTOINCREMENT PK on each subsequent write. The
``test_update_call_outcome_preserves_pk`` test pins the contract
against accidental REPLACE introduction.
"""
from __future__ import annotations

import sqlite3

from swing.data.models import SchwabApiCall

_SELECT_COLUMNS = (
    "call_id, ts, endpoint, http_status, response_time_ms, "
    "rate_limit_remaining, signature_hash, status, error_message, "
    "linked_snapshot_id, linked_reconciliation_run_id, pipeline_run_id, "
    "surface, environment"
)


def _row_to_model(row: tuple) -> SchwabApiCall:
    return SchwabApiCall(
        call_id=row[0],
        ts=row[1],
        endpoint=row[2],
        http_status=row[3],
        response_time_ms=row[4],
        rate_limit_remaining=row[5],
        signature_hash=row[6],
        status=row[7],
        error_message=row[8],
        linked_snapshot_id=row[9],
        linked_reconciliation_run_id=row[10],
        pipeline_run_id=row[11],
        surface=row[12],
        environment=row[13],
    )


def insert_in_flight(
    conn: sqlite3.Connection,
    *,
    ts: str,
    endpoint: str,
    pipeline_run_id: int | None,
    surface: str,
    environment: str,
) -> int:
    """Insert an in-flight audit row. Returns the assigned call_id.

    Status is hardcoded to ``'in_flight'`` — the request just left the
    service layer; the response has not yet been seen. The caller
    (T-A.9 service wrapper) follows up with ``update_call_outcome`` once
    the response (or terminal failure) is observed.

    Caller controls the transaction. Per Finviz I1 lesson, this function
    MUST NOT call ``conn.commit()``.
    """
    cur = conn.execute(
        "INSERT INTO schwab_api_calls ("
        "ts, endpoint, status, pipeline_run_id, surface, environment"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (ts, endpoint, "in_flight", pipeline_run_id, surface, environment),
    )
    return int(cur.lastrowid)


def update_call_outcome(
    conn: sqlite3.Connection,
    *,
    call_id: int,
    http_status: int | None,
    response_time_ms: int | None,
    rate_limit_remaining: int | None,
    signature_hash: str | None,
    status: str,
    error_message: str | None,
) -> None:
    """Update the existing call_id row in place with terminal outcome fields.

    DISCRIMINATING contract per CLAUDE.md gotcha: this is a plain ``UPDATE``;
    NEVER ``INSERT OR REPLACE``. The ``call_id`` PK MUST be preserved across
    the update so any concurrent reader still holding the original handle
    sees the same row identity (and so any future FK referrer on
    ``schwab_api_calls(call_id)`` does not get cascade-wiped by a REPLACE).
    """
    conn.execute(
        "UPDATE schwab_api_calls SET "
        "http_status = ?, response_time_ms = ?, rate_limit_remaining = ?, "
        "signature_hash = ?, status = ?, error_message = ? "
        "WHERE call_id = ?",
        (http_status, response_time_ms, rate_limit_remaining,
         signature_hash, status, error_message, call_id),
    )


def update_call_linked_snapshot(
    conn: sqlite3.Connection,
    *,
    call_id: int,
    snapshot_id: int,
) -> None:
    """Set linked_snapshot_id on the existing call row; preserve all else."""
    conn.execute(
        "UPDATE schwab_api_calls SET linked_snapshot_id = ? "
        "WHERE call_id = ?",
        (snapshot_id, call_id),
    )


def update_call_linked_reconciliation_run(
    conn: sqlite3.Connection,
    *,
    call_id: int,
    reconciliation_run_id: int,
) -> None:
    """Set linked_reconciliation_run_id; preserve all else."""
    conn.execute(
        "UPDATE schwab_api_calls SET linked_reconciliation_run_id = ? "
        "WHERE call_id = ?",
        (reconciliation_run_id, call_id),
    )


def list_recent_calls(
    conn: sqlite3.Connection,
    *,
    since_ts: str,
    surface_filter: str | None,
    environment_filter: str | None,
    limit: int,
) -> list[SchwabApiCall]:
    """Return calls with ts >= since_ts, optionally filtered, newest-first.

    Ordering: ``ts DESC, call_id DESC`` (Finviz R3 Major-1 tiebreaker
    precedent — second-precision ``ts`` ties are realistic when multiple
    requests fire in the same second; AUTOINCREMENT call_id strictly
    increases, so newest-insert wins among ties).

    Filter semantics: ``surface_filter`` and ``environment_filter`` are
    optional; ``None`` means "do not filter on this axis". The
    intersection of all active filters applies.
    """
    sql_parts = [
        f"SELECT {_SELECT_COLUMNS} FROM schwab_api_calls WHERE ts >= ?",
    ]
    params: list = [since_ts]
    if surface_filter is not None:
        sql_parts.append("AND surface = ?")
        params.append(surface_filter)
    if environment_filter is not None:
        sql_parts.append("AND environment = ?")
        params.append(environment_filter)
    sql_parts.append("ORDER BY ts DESC, call_id DESC LIMIT ?")
    params.append(limit)
    rows = conn.execute(" ".join(sql_parts), tuple(params)).fetchall()
    return [_row_to_model(r) for r in rows]


def get_call(
    conn: sqlite3.Connection,
    *,
    call_id: int,
) -> SchwabApiCall | None:
    """Return the call with the given call_id; None if not found."""
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM schwab_api_calls WHERE call_id = ?",
        (call_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_model(row)


def count_calls_by_status(
    conn: sqlite3.Connection,
    *,
    status_filter: str,
    since_ts: str,
) -> int:
    """Count calls with status == status_filter AND ts >= since_ts."""
    row = conn.execute(
        "SELECT COUNT(*) FROM schwab_api_calls "
        "WHERE status = ? AND ts >= ?",
        (status_filter, since_ts),
    ).fetchone()
    return int(row[0])


def is_schwab_degraded(
    conn: sqlite3.Connection,
) -> tuple[bool, str | None]:
    """Schwab API arc-closer Sub-bundle D Task T-D.5 — degraded predicate.

    Plan §Tasks-D T-D.5 + dispatch brief §0.9 + spec §3.4.4 + §7.2.

    Returns ``(True, endpoint_name)`` when the most-recent ``schwab_api_calls``
    row's ``status != 'success'``. Returns ``(False, None)`` otherwise.

    CRITICAL: ZERO-rows-yet state is NOT degraded (false-positive guard per
    dispatch brief §5.2 T-D.5 pre-emption — predicate MUST NOT fire on
    fresh DB state where no Schwab API calls have been made yet).

    Read-only; caller-controlled tx; mirrors ordering of ``list_recent_calls``
    (``ts DESC, call_id DESC``).
    """
    row = conn.execute(
        "SELECT status, endpoint FROM schwab_api_calls "
        "ORDER BY ts DESC, call_id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return (False, None)
    status, endpoint = row[0], row[1]
    if status == "success":
        return (False, None)
    return (True, endpoint)
