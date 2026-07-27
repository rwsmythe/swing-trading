"""latch_view_events repository (migration 0032, Phase 21 Arc A).

Caller-controlled tx discipline -- these functions issue NO BEGIN/COMMIT/
ROLLBACK; the route owns `with conn:`.

SELECT-then-UPDATE-or-INSERT ONLY. NEVER `INSERT OR REPLACE` (that is DELETE +
INSERT: it would issue a new PK and rewrite the immutable first-view facts).
"""
from __future__ import annotations

import sqlite3

from swing.data.models import LatchViewEvent
from swing.latches.identity import LatchIdentity

_COLS = (
    "view_event_id, candidate_id, evaluation_run_id, ticker, detection_date, "
    "pipeline_run_id, view_session_date, first_viewed_ts, last_viewed_ts, "
    "view_count, latch_state_at_first_view, latch_state_at_last_view"
)


def _row_to_model(row: tuple) -> LatchViewEvent:
    return LatchViewEvent(
        view_event_id=row[0], candidate_id=row[1], evaluation_run_id=row[2],
        ticker=row[3], detection_date=row[4], pipeline_run_id=row[5],
        view_session_date=row[6], first_viewed_ts=row[7], last_viewed_ts=row[8],
        view_count=row[9], latch_state_at_first_view=row[10],
        latch_state_at_last_view=row[11],
    )


def get_view(
    conn: sqlite3.Connection, *, evaluation_run_id: int, ticker: str,
    view_session_date: str,
) -> LatchViewEvent | None:
    row = conn.execute(
        f"SELECT {_COLS} FROM latch_view_events "
        "WHERE evaluation_run_id = ? AND ticker = ? AND view_session_date = ?",
        (evaluation_run_id, ticker, view_session_date),
    ).fetchone()
    return None if row is None else _row_to_model(row)


def list_views_for_session(
    conn: sqlite3.Connection, *, view_session_date: str,
) -> list[LatchViewEvent]:
    rows = conn.execute(
        f"SELECT {_COLS} FROM latch_view_events WHERE view_session_date = ? "
        "ORDER BY ticker, evaluation_run_id",
        (view_session_date,),
    ).fetchall()
    return [_row_to_model(r) for r in rows]


def list_views_for_latch(
    conn: sqlite3.Connection, *, evaluation_run_id: int, ticker: str,
) -> list[LatchViewEvent]:
    rows = conn.execute(
        f"SELECT {_COLS} FROM latch_view_events "
        "WHERE evaluation_run_id = ? AND ticker = ? ORDER BY view_session_date",
        (evaluation_run_id, ticker),
    ).fetchall()
    return [_row_to_model(r) for r in rows]


def record_view(
    conn: sqlite3.Connection, *, identity: LatchIdentity, view_session_date: str,
    viewed_ts: str, latch_state: str,
) -> int:
    """Record a view of `identity`'s latch on `view_session_date`.

    First view of the session INSERTs (view_count=1). Subsequent views UPDATE
    IN PLACE: view_count += 1, last_viewed_ts + latch_state_at_last_view
    advance; first_viewed_ts + latch_state_at_first_view are NEVER rewritten.
    Returns the (stable) view_event_id.
    """
    existing = get_view(
        conn, evaluation_run_id=identity.evaluation_run_id,
        ticker=identity.ticker, view_session_date=view_session_date)
    if existing is not None:
        conn.execute(
            "UPDATE latch_view_events SET last_viewed_ts = ?, "
            "latch_state_at_last_view = ?, view_count = view_count + 1 "
            "WHERE view_event_id = ?",
            (viewed_ts, latch_state, existing.view_event_id))
        return int(existing.view_event_id)
    cur = conn.execute(
        "INSERT INTO latch_view_events (candidate_id, evaluation_run_id, ticker, "
        "detection_date, pipeline_run_id, view_session_date, first_viewed_ts, "
        "last_viewed_ts, view_count, latch_state_at_first_view, "
        "latch_state_at_last_view) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (identity.candidate_id, identity.evaluation_run_id, identity.ticker,
         identity.detection_date, identity.pipeline_run_id, view_session_date,
         viewed_ts, viewed_ts, latch_state, latch_state))
    return int(cur.lastrowid)
