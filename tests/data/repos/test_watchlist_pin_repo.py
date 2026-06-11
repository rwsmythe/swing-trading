import sqlite3

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import (
    WatchlistEntryNotFoundError,
    get_watchlist_entry,
    list_active_watchlist,
    set_watchlist_pin,
    upsert_watchlist_entry,
)


def _conn(tmp_path) -> sqlite3.Connection:
    db = tmp_path / "swing.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    return conn


def _entry(ticker: str, **kw) -> WatchlistEntry:
    base = dict(
        ticker=ticker, added_date="2026-06-01", last_qualified_date="2026-06-01",
        status="watch", qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-06-01", entry_target=10.0, initial_stop_target=9.0,
        last_close=10.5, last_pivot=10.0, last_stop=9.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )
    base.update(kw)
    return WatchlistEntry(**base)


def test_row_to_entry_maps_pin_columns(tmp_path):
    conn = _conn(tmp_path)
    try:
        upsert_watchlist_entry(conn, _entry("AAAA"))
        set_watchlist_pin(conn, "AAAA", pinned=True, pin_note="keep me", pinned_at="2026-06-10T12:00:00")
        e = get_watchlist_entry(conn, "AAAA")
        assert e is not None
        assert (e.pinned, e.pin_note, e.pinned_at) == (True, "keep me", "2026-06-10T12:00:00")
        listed = {x.ticker: x for x in list_active_watchlist(conn)}
        assert listed["AAAA"].pinned is True
    finally:
        conn.close()


def test_upsert_do_update_EXCLUDES_pin_columns(tmp_path):
    """DISCRIMINATING: pin a ticker, then upsert a nightly entry whose
    pinned=False/None — the stored pin MUST survive. A naive ON CONFLICT that
    includes pinned=excluded.pinned would zero it -> this FAILS. Intended tripwire."""
    conn = _conn(tmp_path)
    try:
        upsert_watchlist_entry(conn, _entry("BBBB"))
        set_watchlist_pin(conn, "BBBB", pinned=True, pin_note="hold", pinned_at="2026-06-10T00:00:00")
        nightly = _entry("BBBB", not_qualified_streak=1, last_data_asof_date="2026-06-11",
                         pinned=False, pin_note=None, pinned_at=None)
        upsert_watchlist_entry(conn, nightly)
        e = get_watchlist_entry(conn, "BBBB")
        assert e.pinned is True, "pin must survive a nightly upsert (DO UPDATE excludes pin cols)"
        assert e.pin_note == "hold"
        assert e.pinned_at == "2026-06-10T00:00:00"
        assert e.not_qualified_streak == 1
        assert e.last_data_asof_date == "2026-06-11"
    finally:
        conn.close()


def test_set_watchlist_pin_404_on_absent_ticker(tmp_path):
    conn = _conn(tmp_path)
    try:
        with pytest.raises(WatchlistEntryNotFoundError):
            set_watchlist_pin(conn, "ZZZZ", pinned=True, pin_note=None, pinned_at="2026-06-10T00:00:00")
    finally:
        conn.close()


def test_set_watchlist_pin_unpin_clears_note_and_timestamp(tmp_path):
    conn = _conn(tmp_path)
    try:
        upsert_watchlist_entry(conn, _entry("CCCC"))
        set_watchlist_pin(conn, "CCCC", pinned=True, pin_note="x", pinned_at="2026-06-10T00:00:00")
        set_watchlist_pin(conn, "CCCC", pinned=False, pin_note=None, pinned_at=None)
        e = get_watchlist_entry(conn, "CCCC")
        assert (e.pinned, e.pin_note, e.pinned_at) == (False, None, None)
    finally:
        conn.close()
