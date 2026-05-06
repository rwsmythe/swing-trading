"""Repo for finviz_api_calls audit table (migration 0015)."""
from __future__ import annotations

import sqlite3

from swing.data.models import FinvizApiCall


def insert_call(conn: sqlite3.Connection, call: FinvizApiCall) -> int:
    cur = conn.execute(
        "INSERT INTO finviz_api_calls "
        "(ts, screen_query, status, row_count, response_time_ms, "
        " rate_limit_remaining, signature_hash, error_message) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (call.ts, call.screen_query, call.status, call.row_count,
         call.response_time_ms, call.rate_limit_remaining,
         call.signature_hash, call.error_message),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_recent_calls(
    conn: sqlite3.Connection, *, limit: int = 50,
) -> list[FinvizApiCall]:
    rows = conn.execute(
        "SELECT call_id, ts, screen_query, status, row_count, response_time_ms, "
        "       rate_limit_remaining, signature_hash, error_message "
        "FROM finviz_api_calls ORDER BY ts DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        FinvizApiCall(
            call_id=r[0], ts=r[1], screen_query=r[2], status=r[3], row_count=r[4],
            response_time_ms=r[5], rate_limit_remaining=r[6],
            signature_hash=r[7], error_message=r[8],
        )
        for r in rows
    ]


def get_latest_signature_hash(
    conn: sqlite3.Connection, *, screen_query: str,
) -> str | None:
    """Return the most recent non-NULL signature_hash for the given screen_query.

    Drift-detection consumer: it only matters that the LAST KNOWN GOOD signature
    is compared against the new fetch — error/skipped rows have no signature
    and would be a vacuous comparison if returned.
    """
    row = conn.execute(
        "SELECT signature_hash FROM finviz_api_calls "
        "WHERE screen_query = ? AND signature_hash IS NOT NULL "
        "ORDER BY ts DESC LIMIT 1",
        (screen_query,),
    ).fetchone()
    return row[0] if row else None
