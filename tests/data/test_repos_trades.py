"""Trades repo round-trip. Every trades mutation must also write a trade_events row in same txn."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Trade, Exit, TradeEvent
from swing.data.repos.trades import (
    insert_trade_with_event, insert_exit_with_event, update_stop_with_event,
    list_open_trades, list_exits_for_trade, list_events_for_trade,
    get_trade,
)


class _FailingConnection(sqlite3.Connection):
    """Subclass that raises on SQL matching a per-instance trigger substring.

    Used to simulate mid-transaction DB failure without monkeypatching
    sqlite3.Connection.execute (which is read-only on CPython 3.14+).
    Set `conn.fail_on_sql_substring` to a string; any execute() whose SQL
    contains that substring raises sqlite3.OperationalError.
    """
    fail_on_sql_substring: str = ""

    def execute(self, sql, *args, **kwargs):
        if self.fail_on_sql_substring and self.fail_on_sql_substring in sql:
            raise sqlite3.OperationalError(
                f"simulated failure on: {self.fail_on_sql_substring}"
            )
        return super().execute(sql, *args, **kwargs)


def _trade(ticker: str = "AAPL") -> Trade:
    return Trade(
        id=None, ticker=ticker, entry_date="2026-04-15", entry_price=180.0,
        initial_shares=10, initial_stop=170.0, current_stop=170.0,
        status="open", state="entered", watchlist_entry_target=181.0,
        watchlist_initial_stop=170.0, notes="VCP entry",
    )


def test_insert_trade_writes_entry_event(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(
                conn, _trade(),
                event_ts="2026-04-15T09:30:00",
                rationale="VCP breakout"
            )
        got = get_trade(conn, tid)
        assert got is not None and got.ticker == "AAPL"

        events = list_events_for_trade(conn, tid)
        assert len(events) == 1
        assert events[0].event_type == "entry"
        payload = json.loads(events[0].payload_json)
        assert payload["initial_shares"] == 10
        assert payload["entry_price"] == 180.0
    finally:
        conn.close()


def test_insert_exit_writes_event_and_flips_status_when_full(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")
        # Partial first
        with conn:
            insert_exit_with_event(
                conn, Exit(id=None, trade_id=tid, exit_date="2026-04-18",
                           exit_price=185.0, shares=5, reason="partial",
                           realized_pnl=25.0, r_multiple=0.5, notes=None),
                event_ts="2026-04-18T15:00:00", rationale="trim half",
            )
        assert get_trade(conn, tid).status == "open"  # still open

        # Remainder closes
        with conn:
            insert_exit_with_event(
                conn, Exit(id=None, trade_id=tid, exit_date="2026-04-22",
                           exit_price=190.0, shares=5, reason="target",
                           realized_pnl=50.0, r_multiple=1.0, notes=None),
                event_ts="2026-04-22T15:30:00", rationale="hit pivot+10%",
            )
        assert get_trade(conn, tid).status == "closed"

        events = list_events_for_trade(conn, tid)
        assert [e.event_type for e in events] == ["entry", "exit", "exit"]
    finally:
        conn.close()


def test_insert_trade_persists_hypothesis_label(tmp_path: Path):
    """Brief §4.3: hypothesis_label round-trips through insert + get_trade."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        labeled = Trade(
            id=None, ticker="HYPO", entry_date="2026-04-25", entry_price=50.0,
            initial_shares=4, initial_stop=45.0, current_stop=45.0,
            status="open", state="entered", watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None,
            hypothesis_label="A+ except risk_feasibility, smaller position",
        )
        with conn:
            tid = insert_trade_with_event(conn, labeled, event_ts="2026-04-25T09:30:00")
        got = get_trade(conn, tid)
        assert got is not None
        assert got.hypothesis_label == "A+ except risk_feasibility, smaller position"
    finally:
        conn.close()


def test_insert_trade_without_hypothesis_label_persists_null(tmp_path: Path):
    """Existing-call-site preservation: legacy Trade(...) without hypothesis_label
    constructs with default None and persists NULL."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")
        got = get_trade(conn, tid)
        assert got is not None
        assert got.hypothesis_label is None
    finally:
        conn.close()


def test_update_stop_writes_event_with_old_and_new(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")
        with conn:
            update_stop_with_event(
                conn, trade_id=tid, new_stop=175.0,
                event_ts="2026-04-17T15:00:00", rationale="trail to breakeven+",
            )
        assert get_trade(conn, tid).current_stop == 175.0

        events = list_events_for_trade(conn, tid)
        adj = next(e for e in events if e.event_type == "stop_adjust")
        payload = json.loads(adj.payload_json)
        assert payload == {"old_stop": 170.0, "new_stop": 175.0}
    finally:
        conn.close()


def test_update_stop_persists_notes_alongside_rationale(tmp_path: Path):
    """Bug 3b: trade_events.notes round-trips through update_stop_with_event."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")
        with conn:
            update_stop_with_event(
                conn, trade_id=tid, new_stop=175.0,
                event_ts="2026-04-17T15:00:00",
                rationale="trail to breakeven+",
                notes="acted on trail-10MA advisory; low-volume up-day",
            )
        adj = next(
            e for e in list_events_for_trade(conn, tid) if e.event_type == "stop_adjust"
        )
        assert adj.rationale == "trail to breakeven+"
        assert adj.notes == "acted on trail-10MA advisory; low-volume up-day"
    finally:
        conn.close()


def test_update_stop_notes_default_none_preserves_backcompat(tmp_path: Path):
    """Callers that don't pass notes still succeed and persist NULL notes."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")
        with conn:
            update_stop_with_event(
                conn, trade_id=tid, new_stop=175.0,
                event_ts="2026-04-17T15:00:00",
                rationale="trail",
            )
        adj = next(
            e for e in list_events_for_trade(conn, tid) if e.event_type == "stop_adjust"
        )
        assert adj.notes is None
    finally:
        conn.close()


def test_overfill_exit_raises(tmp_path: Path):
    """Trying to exit more shares than remain raises before any write."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")
        with pytest.raises(ValueError, match="exceeds remaining"):
            with conn:
                insert_exit_with_event(
                    conn, Exit(id=None, trade_id=tid, exit_date="2026-04-18",
                               exit_price=185.0, shares=100, reason="manual",
                               realized_pnl=500.0, r_multiple=5.0, notes=None),
                    event_ts="2026-04-18T15:00:00",
                )
    finally:
        conn.close()


def test_list_open_trades(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            insert_trade_with_event(conn, _trade("AAPL"), event_ts="2026-04-15T09:30:00")
            insert_trade_with_event(conn, _trade("MSFT"), event_ts="2026-04-15T09:31:00")
        opens = list_open_trades(conn)
        assert {t.ticker for t in opens} == {"AAPL", "MSFT"}
    finally:
        conn.close()


def test_trade_event_atomicity_rolls_back_on_failure(tmp_path: Path):
    """If the trade_events INSERT fails mid-transaction, the trades INSERT must
    also roll back — no orphaned trades row without its paired 'entry' event.

    Uses a Connection subclass rather than monkeypatching conn.execute because
    on CPython 3.14+, sqlite3.Connection.execute is read-only.
    """
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(str(db), factory=_FailingConnection)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.fail_on_sql_substring = "INSERT INTO trade_events"

        with pytest.raises(sqlite3.OperationalError):
            with conn:
                insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")

        conn.fail_on_sql_substring = ""
        count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        assert count == 0, "trades row leaked past a failed trade_events INSERT"
        event_count = conn.execute("SELECT COUNT(*) FROM trade_events").fetchone()[0]
        assert event_count == 0
    finally:
        conn.close()


def test_exit_atomicity_rolls_back_on_failure(tmp_path: Path):
    """Same invariant for exits: failure in the 'exit' event insert must roll
    back the exits INSERT + the trades status update.
    """
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(str(db), factory=_FailingConnection)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        # Seed a trade first (no failure trigger set)
        with conn:
            tid = insert_trade_with_event(conn, _trade(), event_ts="2026-04-15T09:30:00")

        # Now arm the failure trigger to match ONLY the exit event INSERT.
        # The repo's exit-event SQL has the literal `'exit'` (with quotes) in it.
        conn.fail_on_sql_substring = "'exit'"

        with pytest.raises(sqlite3.OperationalError):
            with conn:
                insert_exit_with_event(
                    conn, Exit(id=None, trade_id=tid, exit_date="2026-04-18",
                               exit_price=185.0, shares=5, reason="partial",
                               realized_pnl=25.0, r_multiple=0.5, notes=None),
                    event_ts="2026-04-18T15:00:00",
                )

        conn.fail_on_sql_substring = ""
        assert get_trade(conn, tid).status == "open"
        assert list_exits_for_trade(conn, tid) == []
        events = list_events_for_trade(conn, tid)
        # Only the original 'entry' event, no 'exit' event
        assert [e.event_type for e in events] == ["entry"]
    finally:
        conn.close()


def test_update_stop_with_event_rejects_closed_trade():
    """Spec §4.4: closed trade → ValueError, no row mutation, no event insert."""
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.trades import (
        insert_trade_with_event, update_stop_with_event,
    )
    import pytest as _pt
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test.db"
        ensure_schema(db_path).close()
        conn = connect(db_path)
        try:
            with conn:
                tid = insert_trade_with_event(
                    conn, _trade(), event_ts="2026-04-15T09:30:00",
                )
                # Mark the trade closed (simulates post-exit state transition).
                conn.execute(
                    "UPDATE trades SET status='closed' WHERE id = ?", (tid,),
                )

            # Attempt stop-adjust on the closed trade.
            with _pt.raises(ValueError) as excinfo:
                with conn:
                    update_stop_with_event(
                        conn, trade_id=tid, new_stop=175.0,
                        event_ts="2026-04-16T10:00:00",
                        rationale="attempt after close",
                    )
            # Accept either wording — the closed-trade path raises with one;
            # missing-trade path raises with another.
            msg = str(excinfo.value).lower()
            assert "not open" in msg or "does not exist" in msg

            # Confirm no stop_adjust event was inserted.
            rows = conn.execute(
                "SELECT COUNT(*) FROM trade_events "
                "WHERE event_type='stop_adjust' AND trade_id = ?",
                (tid,),
            ).fetchone()
            assert rows[0] == 0

            # current_stop must not have mutated.
            row = conn.execute(
                "SELECT current_stop FROM trades WHERE id = ?", (tid,),
            ).fetchone()
            assert row[0] == _trade().initial_stop  # whatever initial_stop _trade() sets
        finally:
            conn.close()


def test_update_stop_with_event_rejects_missing_trade():
    """Spec §4.4: nonexistent trade_id → ValueError, no event insert."""
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.trades import update_stop_with_event
    import pytest as _pt
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test.db"
        ensure_schema(db_path).close()
        conn = connect(db_path)
        try:
            with _pt.raises(ValueError) as excinfo:
                with conn:
                    update_stop_with_event(
                        conn, trade_id=99999, new_stop=175.0,
                        event_ts="2026-04-16T10:00:00",
                        rationale="missing",
                    )
            msg = str(excinfo.value).lower()
            assert "not found" in msg or "does not exist" in msg

            rows = conn.execute(
                "SELECT COUNT(*) FROM trade_events WHERE trade_id=99999"
            ).fetchone()
            assert rows[0] == 0
        finally:
            conn.close()


def test_trade_sector_industry_roundtrip_all_select_paths(tmp_path):
    """Trade with sector + industry roundtrips through ALL FIVE repo SELECT
    paths. Each path hand-rolls its column list — missing one path while
    fixing the others is the recurring repo-SELECT-coverage bug."""
    from swing.data.db import ensure_schema
    from swing.data.models import Trade
    from swing.data.repos.trades import (
        find_any_open_trade,
        find_open_trade_by_match,
        get_trade,
        insert_trade_with_event,
        list_closed_trades,
        list_open_trades,
    )
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    try:
        with conn:
            trade_id = insert_trade_with_event(conn, Trade(
                id=None, ticker="ZZZE", entry_date="2026-04-28",
                entry_price=100.0, initial_shares=10,
                initial_stop=95.0, current_stop=95.0, status="open", state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, hypothesis_label=None,
                sector="Energy", industry="Oil & Gas E&P",
            ), event_ts="2026-04-28T00:00:00")
        # Path 1: get_trade
        t1 = get_trade(conn, trade_id)
        assert t1 is not None and t1.sector == "Energy"
        assert t1.industry == "Oil & Gas E&P"
        # Path 2: list_open_trades
        opens = list_open_trades(conn)
        assert any(t.ticker == "ZZZE" and t.sector == "Energy" for t in opens)
        # Path 3a: find_any_open_trade
        t3 = find_any_open_trade(conn, ticker="ZZZE")
        assert t3 is not None and t3.sector == "Energy"
        assert t3.industry == "Oil & Gas E&P"
        # Path 3b: find_open_trade_by_match (with shares)
        t4 = find_open_trade_by_match(
            conn, ticker="ZZZE", entry_date="2026-04-28", initial_shares=10,
        )
        assert t4 is not None and t4.sector == "Energy"
        # Path 3c: find_open_trade_by_match (without shares)
        t5 = find_open_trade_by_match(
            conn, ticker="ZZZE", entry_date="2026-04-28", initial_shares=None,
        )
        assert t5 is not None and t5.industry == "Oil & Gas E&P"
        # Path 4: list_closed_trades — close the trade first.
        with conn:
            conn.execute(
                "UPDATE trades SET status='closed' WHERE id=?", (trade_id,),
            )
        closed_all = list_closed_trades(conn)
        assert any(
            t.ticker == "ZZZE" and t.sector == "Energy" and
            t.industry == "Oil & Gas E&P" for t in closed_all
        )
        # Path 4b: list_closed_trades with since_date branch (requires an
        # exits row to satisfy the EXISTS subquery; insert directly).
        with conn:
            conn.execute(
                """INSERT INTO exits
                   (trade_id, exit_date, exit_price, shares, reason,
                    realized_pnl, r_multiple, notes)
                   VALUES (?, '2026-04-28', 100.0, 10, 'manual', 0.0, 0.0, NULL)""",
                (trade_id,),
            )
        closed_since = list_closed_trades(conn, since_date="2026-04-01")
        assert any(
            t.ticker == "ZZZE" and t.sector == "Energy" for t in closed_since
        )
    finally:
        conn.close()


def test_trade_default_sector_industry_empty():
    """Trade constructed without sector/industry uses '' defaults."""
    from swing.data.models import Trade
    t = Trade(
        id=None, ticker="DFLT", entry_date="2026-04-28",
        entry_price=100.0, initial_shares=10,
        initial_stop=95.0, current_stop=95.0, status="open", state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )
    assert t.sector == ""
    assert t.industry == ""
