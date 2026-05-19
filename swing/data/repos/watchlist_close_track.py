"""``watchlist_close_track_flags`` + ``watchlist_close_track_flag_events``
repos — Phase 13 T2.SB1 task T-A.1.1b.

Minimum CRUD (insert / get_by_id / list) per plan §G.1 T-A.1.1b acceptance.
Caller-tx contract (NO ``conn.commit()`` in repo) + NO ``INSERT OR REPLACE``
per plan §A.15 LOCK (audit-trail tables; UPDATE-cleared_at-in-place pattern
preserves history per §A.12 transactional discipline).

Active-flag uniqueness is enforced via partial unique index
``idx_wclf_active_ticker`` per Codex R1 M#9 closure — re-flagging a
previously-cleared ticker INSERTs a NEW lifecycle row, NOT UPSERTs.

T4.SB will introduce the service layer (``swing/trades/watchlist_close_track.py``)
with reject-caller-held-tx + auto-clear-on-position-open. This repo is the
consumer-side foundation those services build on.
"""
from __future__ import annotations

import sqlite3

from swing.data.models import (
    WatchlistCloseTrackFlag,
    WatchlistCloseTrackFlagEvent,
)

_FLAG_COLUMNS: tuple[str, ...] = (
    "id",
    "ticker",
    "flagged_at",
    "flagged_by_surface",
    "reason_text",
    "cleared_at",
    "cleared_reason",
)
_FLAG_SELECT_SQL: str = ", ".join(_FLAG_COLUMNS)

_EVENT_COLUMNS: tuple[str, ...] = (
    "id",
    "flag_id",
    "event_type",
    "event_at",
    "surface",
    "reason_text",
)
_EVENT_SELECT_SQL: str = ", ".join(_EVENT_COLUMNS)


def _row_to_flag(row: tuple) -> WatchlistCloseTrackFlag:
    return WatchlistCloseTrackFlag(
        id=row[0],
        ticker=row[1],
        flagged_at=row[2],
        flagged_by_surface=row[3],
        reason_text=row[4],
        cleared_at=row[5],
        cleared_reason=row[6],
    )


def _row_to_event(row: tuple) -> WatchlistCloseTrackFlagEvent:
    return WatchlistCloseTrackFlagEvent(
        id=row[0],
        flag_id=row[1],
        event_type=row[2],
        event_at=row[3],
        surface=row[4],
        reason_text=row[5],
    )


# ============================================================================
# watchlist_close_track_flags CRUD
# ============================================================================


def insert_flag(
    conn: sqlite3.Connection, flag: WatchlistCloseTrackFlag,
) -> int:
    """Insert one ``watchlist_close_track_flags`` row; return new id.

    Caller-tx contract: NO ``conn.commit()``. Partial unique index
    ``idx_wclf_active_ticker`` raises ``sqlite3.IntegrityError`` if another
    ACTIVE flag (cleared_at IS NULL) already exists for the same ticker;
    caller decides idempotent SELECT-then-INSERT semantics.
    """
    cur = conn.execute(
        """
        INSERT INTO watchlist_close_track_flags
            (ticker, flagged_at, flagged_by_surface, reason_text,
             cleared_at, cleared_reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            flag.ticker,
            flag.flagged_at,
            flag.flagged_by_surface,
            flag.reason_text,
            flag.cleared_at,
            flag.cleared_reason,
        ),
    )
    return int(cur.lastrowid)


def get_flag_by_id(
    conn: sqlite3.Connection, flag_id: int,
) -> WatchlistCloseTrackFlag | None:
    row = conn.execute(
        f"SELECT {_FLAG_SELECT_SQL} FROM watchlist_close_track_flags WHERE id = ?",
        (flag_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_flag(row)


def list_flags(
    conn: sqlite3.Connection,
    *,
    ticker: str | None = None,
    active_only: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> list[WatchlistCloseTrackFlag]:
    """List flags optionally filtered by ticker / active-state.

    ``active_only=True`` filters to ``cleared_at IS NULL`` (current
    operator-flagged tickers). Ordered by (id ASC) for deterministic
    pagination.
    """
    where_clauses: list[str] = []
    params: list[object] = []
    if ticker is not None:
        where_clauses.append("ticker = ?")
        params.append(ticker)
    if active_only:
        where_clauses.append("cleared_at IS NULL")

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    limit_sql = ""
    if limit is not None:
        limit_sql = " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    rows = conn.execute(
        f"SELECT {_FLAG_SELECT_SQL} FROM watchlist_close_track_flags"
        f"{where_sql} ORDER BY id ASC{limit_sql}",
        tuple(params),
    ).fetchall()
    return [_row_to_flag(r) for r in rows]


# ============================================================================
# watchlist_close_track_flag_events CRUD (append-only audit per D-Q4.7)
# ============================================================================


def insert_flag_event(
    conn: sqlite3.Connection, event: WatchlistCloseTrackFlagEvent,
) -> int:
    """Insert one ``watchlist_close_track_flag_events`` row; return new id.

    Append-only audit per Phase 12 C.A ``reconciliation_corrections``
    precedent + spec §7.2 D-Q4.7. Caller-tx contract.
    """
    cur = conn.execute(
        """
        INSERT INTO watchlist_close_track_flag_events
            (flag_id, event_type, event_at, surface, reason_text)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            event.flag_id,
            event.event_type,
            event.event_at,
            event.surface,
            event.reason_text,
        ),
    )
    return int(cur.lastrowid)


def get_flag_event_by_id(
    conn: sqlite3.Connection, event_id: int,
) -> WatchlistCloseTrackFlagEvent | None:
    row = conn.execute(
        f"SELECT {_EVENT_SELECT_SQL} FROM watchlist_close_track_flag_events "
        f"WHERE id = ?",
        (event_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_event(row)


def list_flag_events(
    conn: sqlite3.Connection,
    *,
    flag_id: int | None = None,
    event_type: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[WatchlistCloseTrackFlagEvent]:
    """List flag events filtered by optional flag_id / event_type. Ordered
    by (event_at ASC, id ASC) for chronological audit replay.
    """
    where_clauses: list[str] = []
    params: list[object] = []
    if flag_id is not None:
        where_clauses.append("flag_id = ?")
        params.append(flag_id)
    if event_type is not None:
        where_clauses.append("event_type = ?")
        params.append(event_type)

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    limit_sql = ""
    if limit is not None:
        limit_sql = " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    rows = conn.execute(
        f"SELECT {_EVENT_SELECT_SQL} FROM watchlist_close_track_flag_events"
        f"{where_sql} ORDER BY event_at ASC, id ASC{limit_sql}",
        tuple(params),
    ).fetchall()
    return [_row_to_event(r) for r in rows]
