"""yfinance_calls repository (migration 0030, Phase 18 Arc 18-C).

Mirrors ``swing/data/repos/schwab_api_calls.py``:

- Caller-controlled tx discipline — repo functions DO NOT issue BEGIN /
  COMMIT / ROLLBACK. The service layer (``swing/data/yfinance_audit.py``)
  owns BEGIN IMMEDIATE / COMMIT / ROLLBACK.
- UPDATE-in-place ONLY — NEVER ``INSERT OR REPLACE`` per CLAUDE.md cascade-wipe
  gotcha; the AUTOINCREMENT call_id PK is the immutable handle the service
  threads through the fetch lifecycle (insert_in_flight -> update_call_outcome).
  ``test_update_call_outcome_preserves_pk`` pins it.

Stale ``in_flight`` rows: a rare best-effort finish-contention drop can leave a
row ``in_flight`` permanently (no terminal status). Read helpers/monitors
(18-D/18-E) MUST treat a stale ``in_flight`` row as INCOMPLETE/unknown, NOT a
hung call. NO new status is added (the enum lock holds).
"""
from __future__ import annotations

import sqlite3

from swing.data.models import YfinanceCall

_SELECT_COLUMNS = (
    "call_id, ts, call_type, ticker, ticker_count, response_time_ms, "
    "status, rows_returned, error_message, pipeline_run_id, surface"
)


def _row_to_model(row: tuple) -> YfinanceCall:
    return YfinanceCall(
        call_id=row[0],
        ts=row[1],
        call_type=row[2],
        ticker=row[3],
        ticker_count=row[4],
        response_time_ms=row[5],
        status=row[6],
        rows_returned=row[7],
        error_message=row[8],
        pipeline_run_id=row[9],
        surface=row[10],
    )


def insert_in_flight(
    conn: sqlite3.Connection,
    *,
    ts: str,
    call_type: str,
    ticker: str | None,
    ticker_count: int | None,
    pipeline_run_id: int | None,
    surface: str,
) -> int:
    """Insert an in-flight audit row. Returns the assigned call_id.

    Status is hardcoded to ``'in_flight'`` — the fetch just started. Both shape
    fields (ticker / ticker_count) are known at call start, so the in-flight row
    already satisfies the SQL shape CHECK. Caller controls the transaction; this
    function MUST NOT call ``conn.commit()``.
    """
    cur = conn.execute(
        "INSERT INTO yfinance_calls ("
        "ts, call_type, ticker, ticker_count, status, pipeline_run_id, surface"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, call_type, ticker, ticker_count, "in_flight", pipeline_run_id, surface),
    )
    return int(cur.lastrowid)


def update_call_outcome(
    conn: sqlite3.Connection,
    *,
    call_id: int,
    response_time_ms: int | None,
    status: str,
    rows_returned: int | None,
    error_message: str | None,
) -> None:
    """Update the existing call_id row in place with terminal outcome fields.

    DISCRIMINATING contract per CLAUDE.md gotcha: plain ``UPDATE``; NEVER
    ``INSERT OR REPLACE``. The ``call_id`` PK is preserved across the update.
    """
    conn.execute(
        "UPDATE yfinance_calls SET "
        "response_time_ms = ?, status = ?, rows_returned = ?, error_message = ? "
        "WHERE call_id = ?",
        (response_time_ms, status, rows_returned, error_message, call_id),
    )


def get_call(
    conn: sqlite3.Connection,
    *,
    call_id: int,
) -> YfinanceCall | None:
    """Return the call with the given call_id; None if not found."""
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM yfinance_calls WHERE call_id = ?",
        (call_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_model(row)
