"""Watchlist repo round-trip — upsert / get / list_active / archive_entry."""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import WatchlistEntry, WatchlistArchiveEntry
from swing.data.repos.watchlist import (
    upsert_watchlist_entry, get_watchlist_entry, list_active_watchlist,
    archive_watchlist_entry, list_archive,
)


def _wl(t: str, asof: str = "2026-04-15", count: int = 1) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=t, added_date=asof, last_qualified_date=asof, status="watch",
        qualification_count=count, not_qualified_streak=0,
        last_data_asof_date=asof, entry_target=420.0, initial_stop_target=410.0,
        last_close=418.0, last_pivot=420.0, last_stop=410.0, last_adr_pct=2.5,
        missing_criteria=None, notes=None,
    )


def test_upsert_and_get(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            upsert_watchlist_entry(conn, _wl("MSFT"))
        got = get_watchlist_entry(conn, "MSFT")
        assert got is not None and got.qualification_count == 1

        # Update via upsert
        with conn:
            upsert_watchlist_entry(conn, _wl("MSFT", asof="2026-04-16", count=2))
        got2 = get_watchlist_entry(conn, "MSFT")
        assert got2.qualification_count == 2
        assert got2.last_qualified_date == "2026-04-16"
    finally:
        conn.close()


def test_list_active(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            upsert_watchlist_entry(conn, _wl("AAPL"))
            upsert_watchlist_entry(conn, _wl("MSFT"))
            upsert_watchlist_entry(conn, _wl("NVDA"))
        rows = list_active_watchlist(conn)
        tickers = {r.ticker for r in rows}
        assert tickers == {"AAPL", "MSFT", "NVDA"}
    finally:
        conn.close()


def test_archive_removes_from_active(tmp_path: Path):
    """archive_watchlist_entry must delete from watchlist + insert into archive in one transaction."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            upsert_watchlist_entry(conn, _wl("AAPL"))
        wa = WatchlistArchiveEntry(
            id=None, ticker="AAPL", added_date="2026-04-15",
            removed_date="2026-04-20", reason="entered",
            qualification_count=1, last_data_asof_date="2026-04-19", notes=None,
        )
        with conn:
            archive_watchlist_entry(conn, wa)

        assert get_watchlist_entry(conn, "AAPL") is None
        archived = list_archive(conn, ticker="AAPL")
        assert len(archived) == 1
        assert archived[0].reason == "entered"
    finally:
        conn.close()
