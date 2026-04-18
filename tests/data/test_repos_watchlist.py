"""Watchlist repo round-trip — upsert / get / list_active / archive_entry."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import WatchlistEntry, WatchlistArchiveEntry
from swing.data.repos.watchlist import (
    upsert_watchlist_entry, get_watchlist_entry, list_active_watchlist,
    archive_watchlist_entry, list_archive, WatchlistEntryNotFound,
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


def test_archive_unknown_ticker_raises_without_phantom_row(tmp_path: Path):
    """Archiving a ticker not on the active list must raise and NOT leak a
    phantom archive row (audit integrity)."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        wa = WatchlistArchiveEntry(
            id=None, ticker="NONEXIST", added_date="2026-04-15",
            removed_date="2026-04-20", reason="typo",
            qualification_count=None, last_data_asof_date=None, notes=None,
        )
        with pytest.raises(WatchlistEntryNotFound):
            with conn:
                archive_watchlist_entry(conn, wa)
        # No archive row should have been written
        assert list_archive(conn, ticker="NONEXIST") == []
    finally:
        conn.close()


def test_archive_twice_second_call_raises(tmp_path: Path):
    """Second archive on the same ticker (already removed by first) must raise
    rather than silently writing another archive row."""
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
        # Second call on already-archived ticker must raise
        with pytest.raises(WatchlistEntryNotFound):
            with conn:
                archive_watchlist_entry(conn, wa)
        # Exactly one archive row, not two
        assert len(list_archive(conn, ticker="AAPL")) == 1
    finally:
        conn.close()
