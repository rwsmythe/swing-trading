"""Trades repo round-trip. Every trades mutation must also write a trade_events row in same txn.

Phase 7 (T6) — `Exit` dataclass removed; `exits` table dropped. Tests that previously
relied on `insert_exit_with_event(conn, Exit(...), ...)` now insert fills directly via
the (Sub-A T4) `fills` table; `list_exits_for_trade` is the fills-backed shim that
preserves caller surface for Sub-B/Sub-C callers until those phases rewrite. Tests for
`status` field round-trip rewritten to assert on `state` field.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema, run_migrations
from swing.data.models import Trade, TradeEvent
from swing.data.repos.trades import (
    find_any_open_trade,
    find_open_trade_by_match,
    get_trade,
    insert_trade_with_event,
    list_closed_trades,
    list_events_for_trade,
    list_exits_for_trade,
    list_open_trades,
    update_stop_with_event,
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
        state="entered", watchlist_entry_target=181.0,
        watchlist_initial_stop=170.0, notes="VCP entry",
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at="2026-04-15T16:00:00",
    )


def _insert_fill(
    conn: sqlite3.Connection, *, trade_id: int, action: str,
    fill_datetime: str, quantity: float, price: float, reason: str | None = None,
) -> int:
    """Test helper — direct INSERT into fills bypassing the (yet-unbuilt) fills repo.

    Sub-A T4 will introduce `swing/data/repos/fills.py:insert_fill_with_event`;
    until then, this helper is the only fills-INSERT path used by T6's tests.
    """
    cur = conn.execute(
        """
        INSERT INTO fills
            (trade_id, fill_datetime, action, quantity, price, reason,
             reconciliation_status)
        VALUES (?, ?, ?, ?, ?, ?, 'unreconciled')
        """,
        (trade_id, fill_datetime, action, quantity, price, reason),
    )
    return int(cur.lastrowid)


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


def test_insert_trade_persists_hypothesis_label(tmp_path: Path):
    """Brief §4.3: hypothesis_label round-trips through insert + get_trade."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        labeled = Trade(
            id=None, ticker="HYPO", entry_date="2026-04-25", entry_price=50.0,
            initial_shares=4, initial_stop=45.0, current_stop=45.0,
            state="entered", watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None,
            hypothesis_label="A+ except risk_feasibility, smaller position",
            trade_origin="manual_off_pipeline",
            pre_trade_locked_at="2026-04-25T16:00:00",
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


def test_update_stop_with_event_rejects_closed_trade():
    """Spec §4.4: closed trade → ValueError, no row mutation, no event insert.

    Phase 7 T6: state-based predicate (state IN ('entered','managing','partial_exited'))
    replaces the legacy status='open' guard. Closing a trade is simulated by
    UPDATE state='closed'.
    """
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
                    "UPDATE trades SET state='closed' WHERE id = ?", (tid,),
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
    fixing the others is the recurring repo-SELECT-coverage bug.

    Phase 7 T6: list_closed_trades since-date branch now queries fills (not
    exits); seed via direct fills INSERT.
    """
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    try:
        with conn:
            trade_id = insert_trade_with_event(conn, Trade(
                id=None, ticker="ZZZE", entry_date="2026-04-28",
                entry_price=100.0, initial_shares=10,
                initial_stop=95.0, current_stop=95.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, hypothesis_label=None,
                sector="Energy", industry="Oil & Gas E&P",
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-28T16:00:00",
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
        # Path 4: list_closed_trades — close the trade first (state='closed').
        with conn:
            conn.execute(
                "UPDATE trades SET state='closed' WHERE id=?", (trade_id,),
            )
        closed_all = list_closed_trades(conn)
        assert any(
            t.ticker == "ZZZE" and t.sector == "Energy" and
            t.industry == "Oil & Gas E&P" for t in closed_all
        )
        # Path 4b: list_closed_trades with since_date branch — now queries fills.
        with conn:
            _insert_fill(
                conn, trade_id=trade_id, action="exit",
                fill_datetime="2026-04-28T16:00:00",
                quantity=10.0, price=100.0, reason="manual",
            )
        closed_since = list_closed_trades(conn, since_date="2026-04-01")
        assert any(
            t.ticker == "ZZZE" and t.sector == "Energy" for t in closed_since
        )
    finally:
        conn.close()


def test_trade_default_sector_industry_empty():
    """Trade constructed without sector/industry uses '' defaults."""
    t = Trade(
        id=None, ticker="DFLT", entry_date="2026-04-28",
        entry_price=100.0, initial_shares=10,
        initial_stop=95.0, current_stop=95.0, state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at="2026-04-28T16:00:00",
    )
    assert t.sector == ""
    assert t.industry == ""


# ---------------------------------------------------------------------------
# Phase 7 T6 — three new discriminating tests for the binding green gate.
# ---------------------------------------------------------------------------


def _seed_v14(tmp_path: Path) -> sqlite3.Connection:
    """Open a fresh DB and migrate to v14 directly via run_migrations."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    return conn


def _seed_trade_at_state(
    conn: sqlite3.Connection, *, ticker: str, state: str,
) -> int:
    """Insert a trade row through the repo, then UPDATE state directly.

    The repo's INSERT writes whatever `Trade.state` says, but the CHECK
    constraint enforces the 5-element enum. To exercise tests that need
    arbitrary post-creation states (e.g. 'managing','partial_exited',
    'closed','reviewed') we seed at 'entered' (Phase-7 entry-state) and then
    UPDATE state directly.
    """
    trade = Trade(
        id=None, ticker=ticker, entry_date="2026-05-01",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
        current_stop=9.0, state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at="2026-05-01T16:00:00",
    )
    with conn:
        trade_id = insert_trade_with_event(
            conn, trade, event_ts="2026-05-01T16:00:00",
        )
        if state != "entered":
            conn.execute("UPDATE trades SET state=? WHERE id=?", (state, trade_id))
    return trade_id


def test_get_trade_returns_state_not_status(tmp_path: Path):
    """T6 discriminating: get_trade returns Trade with .state attr.

    Pre-fix (status-only schema): get_trade SELECT'd `status`; trade.status
    would be "open" and accessing trade.state would raise AttributeError.
    Post-fix (state schema, T6): trade.state is the enum field; status no
    longer a Trade attribute.
    """
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_trade_at_state(conn, ticker="TST", state="entered")
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "entered"
        # Discriminating against the wrong rewrite: Trade dataclass must not
        # carry a `status` attribute post-T3.
        assert not hasattr(trade, "status")
    finally:
        conn.close()


def test_list_open_trades_filters_by_state_set(tmp_path: Path):
    """T6 discriminating: list_open_trades returns the 3 active states only.

    Seeds 5 trades at distinct states (entered, managing, partial_exited,
    closed, reviewed). Pre-fix predicate (status='open') would select 0 rows
    or raise OperationalError. Post-fix predicate
    (state IN ('entered','managing','partial_exited')) selects exactly
    {AAA, BBB, CCC}.
    """
    conn = _seed_v14(tmp_path)
    try:
        _seed_trade_at_state(conn, ticker="AAA", state="entered")
        _seed_trade_at_state(conn, ticker="BBB", state="managing")
        _seed_trade_at_state(conn, ticker="CCC", state="partial_exited")
        _seed_trade_at_state(conn, ticker="DDD", state="closed")
        _seed_trade_at_state(conn, ticker="EEE", state="reviewed")
        open_trades = list_open_trades(conn)
        tickers = {t.ticker for t in open_trades}
        assert tickers == {"AAA", "BBB", "CCC"}
    finally:
        conn.close()


def test_insert_trade_no_longer_writes_status_column(tmp_path: Path):
    """T6 discriminating: schema lacks `status` column; INSERT succeeds.

    Pre-fix INSERT col list contained `status` → would raise
    sqlite3.OperationalError ("table trades has no column named status").
    Post-fix INSERT col list omits `status` → INSERT succeeds.
    """
    conn = _seed_v14(tmp_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(trades)")}
        assert "status" not in cols
        # And the new state column IS present (sanity).
        assert "state" in cols
        trade_id = _seed_trade_at_state(conn, ticker="TST", state="entered")
        assert trade_id > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Phase 7 T6 — list_exits_for_trade fills-backed shim coverage.
# ---------------------------------------------------------------------------


def test_list_exits_for_trade_shim_returns_fills_as_exitlike_rows(tmp_path: Path):
    """T6 shim: list_exits_for_trade returns fills-backed Exit-shape rows.

    The shim preserves caller surface (`.exit_date`, `.exit_price`, `.shares`,
    `.reason`, `.realized_pnl`, `.r_multiple`, `.notes`) so Sub-B/Sub-C
    callers continue to work until they migrate to fills repo helpers.
    """
    conn = _seed_v14(tmp_path)
    try:
        tid = _seed_trade_at_state(conn, ticker="EXT", state="managing")
        # Insert a 'trim' fill (50 shares at 12.0) and an 'exit' fill (50 at 14.0).
        with conn:
            _insert_fill(
                conn, trade_id=tid, action="trim",
                fill_datetime="2026-05-02T16:00:00",
                quantity=50.0, price=12.0, reason="partial",
            )
            _insert_fill(
                conn, trade_id=tid, action="exit",
                fill_datetime="2026-05-03T16:00:00",
                quantity=50.0, price=14.0, reason="target",
            )
        rows = list_exits_for_trade(conn, tid)
        assert len(rows) == 2
        # Sorted by fill_datetime ASC.
        assert rows[0].exit_date == "2026-05-02"
        assert rows[0].exit_price == 12.0
        assert rows[0].shares == 50
        assert rows[0].reason == "partial"
        # realized_pnl = (12.0 - 10.0) * 50 = 100.0
        assert rows[0].realized_pnl == 100.0
        # risk_per_share = 10 - 9 = 1.0; r_multiple = 100 / (1.0 * 50) = 2.0
        assert rows[0].r_multiple == 2.0
        # Second row.
        assert rows[1].exit_date == "2026-05-03"
        assert rows[1].exit_price == 14.0
        assert rows[1].shares == 50
        assert rows[1].reason == "target"
        # realized_pnl = (14.0 - 10.0) * 50 = 200.0; r_multiple = 200 / 50 = 4.0
        assert rows[1].realized_pnl == 200.0
        assert rows[1].r_multiple == 4.0
    finally:
        conn.close()


def test_list_exits_for_trade_excludes_entry_fills(tmp_path: Path):
    """T6 shim: entry fills (action='entry', backfilled by migration 0014) are NOT
    returned as 'exits'."""
    conn = _seed_v14(tmp_path)
    try:
        tid = _seed_trade_at_state(conn, ticker="ENT", state="entered")
        # _seed_trade_at_state goes via repo INSERT — that does NOT write a fills
        # row by itself (Sub-A T4's fills repo will). Add an explicit entry fill
        # to verify the shim filters action='entry'.
        with conn:
            _insert_fill(
                conn, trade_id=tid, action="entry",
                fill_datetime="2026-05-01T16:00:00",
                quantity=100.0, price=10.0, reason=None,
            )
            _insert_fill(
                conn, trade_id=tid, action="exit",
                fill_datetime="2026-05-04T16:00:00",
                quantity=100.0, price=11.0, reason="target",
            )
        rows = list_exits_for_trade(conn, tid)
        assert len(rows) == 1, f"shim must filter action='entry'; got {rows}"
        assert rows[0].exit_price == 11.0
    finally:
        conn.close()
