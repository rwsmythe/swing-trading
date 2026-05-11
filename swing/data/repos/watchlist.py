"""Watchlist + watchlist_archive repo. Caller wraps writes in `with conn:`."""
from __future__ import annotations

import sqlite3

from swing.data.models import WatchlistArchiveEntry, WatchlistEntry


def upsert_watchlist_entry(conn: sqlite3.Connection, e: WatchlistEntry) -> None:
    conn.execute(
        """
        INSERT INTO watchlist
            (ticker, added_date, last_qualified_date, status, qualification_count,
             not_qualified_streak, last_data_asof_date, entry_target,
             initial_stop_target, last_close, last_pivot, last_stop, last_adr_pct,
             missing_criteria, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            last_qualified_date = excluded.last_qualified_date,
            status = excluded.status,
            qualification_count = excluded.qualification_count,
            not_qualified_streak = excluded.not_qualified_streak,
            last_data_asof_date = excluded.last_data_asof_date,
            last_close = excluded.last_close,
            last_pivot = excluded.last_pivot,
            last_stop = excluded.last_stop,
            last_adr_pct = excluded.last_adr_pct,
            missing_criteria = excluded.missing_criteria,
            notes = excluded.notes
            -- entry_target / initial_stop_target are FROZEN — never overwritten
        """,
        (e.ticker, e.added_date, e.last_qualified_date, e.status,
         e.qualification_count, e.not_qualified_streak, e.last_data_asof_date,
         e.entry_target, e.initial_stop_target, e.last_close, e.last_pivot,
         e.last_stop, e.last_adr_pct, e.missing_criteria, e.notes),
    )


def get_watchlist_entry(conn: sqlite3.Connection, ticker: str) -> WatchlistEntry | None:
    row = conn.execute(
        """
        SELECT ticker, added_date, last_qualified_date, status, qualification_count,
               not_qualified_streak, last_data_asof_date, entry_target,
               initial_stop_target, last_close, last_pivot, last_stop, last_adr_pct,
               missing_criteria, notes
        FROM watchlist WHERE ticker = ?
        """,
        (ticker,),
    ).fetchone()
    return _row_to_entry(row) if row else None


def list_active_watchlist(conn: sqlite3.Connection) -> list[WatchlistEntry]:
    rows = conn.execute(
        """
        SELECT ticker, added_date, last_qualified_date, status, qualification_count,
               not_qualified_streak, last_data_asof_date, entry_target,
               initial_stop_target, last_close, last_pivot, last_stop, last_adr_pct,
               missing_criteria, notes
        FROM watchlist
        ORDER BY ticker
        """,
    ).fetchall()
    return [_row_to_entry(r) for r in rows]


class WatchlistEntryNotFoundError(Exception):
    """Raised when archive is called on a ticker not present in the active watchlist."""


def archive_watchlist_entry(conn: sqlite3.Connection, a: WatchlistArchiveEntry) -> int:
    """Delete from `watchlist` and insert into `watchlist_archive` atomically.
    Caller's `with conn:` wraps both statements in one transaction.

    Raises WatchlistEntryNotFoundError if no active row for the ticker exists — the
    archive is an audit trail, so we refuse to record removals that didn't happen.
    Delete runs FIRST so the not-found case doesn't leak a phantom archive row.
    """
    cur = conn.execute("DELETE FROM watchlist WHERE ticker = ?", (a.ticker,))
    if cur.rowcount == 0:
        raise WatchlistEntryNotFoundError(
            f"cannot archive {a.ticker}: not on active watchlist"
        )
    insert_cur = conn.execute(
        """
        INSERT INTO watchlist_archive
            (ticker, added_date, removed_date, reason, qualification_count,
             last_data_asof_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (a.ticker, a.added_date, a.removed_date, a.reason,
         a.qualification_count, a.last_data_asof_date, a.notes),
    )
    return int(insert_cur.lastrowid)


def list_archive(
    conn: sqlite3.Connection, *, ticker: str | None = None, limit: int = 100
) -> list[WatchlistArchiveEntry]:
    if ticker:
        rows = conn.execute(
            """
            SELECT id, ticker, added_date, removed_date, reason,
                   qualification_count, last_data_asof_date, notes
            FROM watchlist_archive WHERE ticker = ?
            ORDER BY removed_date DESC LIMIT ?
            """,
            (ticker, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, ticker, added_date, removed_date, reason,
                   qualification_count, last_data_asof_date, notes
            FROM watchlist_archive ORDER BY removed_date DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        WatchlistArchiveEntry(
            id=r[0], ticker=r[1], added_date=r[2], removed_date=r[3],
            reason=r[4], qualification_count=r[5],
            last_data_asof_date=r[6], notes=r[7],
        )
        for r in rows
    ]


def _row_to_entry(row: tuple) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=row[0], added_date=row[1], last_qualified_date=row[2],
        status=row[3], qualification_count=row[4], not_qualified_streak=row[5],
        last_data_asof_date=row[6], entry_target=row[7],
        initial_stop_target=row[8], last_close=row[9], last_pivot=row[10],
        last_stop=row[11], last_adr_pct=row[12], missing_criteria=row[13],
        notes=row[14],
    )
