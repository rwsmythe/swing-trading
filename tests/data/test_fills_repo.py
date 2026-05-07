"""Fills repo CRUD + aggregate-recompute tests.

Spec §4.3.1: get_authoritative_entry_fill picks first by (fill_datetime ASC,
fill_id ASC). Aggregate-recompute invariant: current_size = sum(entry qty)
- sum(trim/exit/stop qty); current_avg_cost = first-entry price; last_fill_at
= max fill_datetime.
"""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.db import run_migrations
from swing.data.models import Fill, Trade
from swing.data.repos.fills import (
    get_authoritative_entry_fill,
    insert_fill_with_event,
    list_fills_for_trade,
)
from swing.data.repos.trades import get_trade, insert_trade_with_event


def _seed_v14(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    run_migrations(conn, target_version=16, backup_dir=tmp_path)
    return conn


def _seed_trade(conn, ticker="AAA", state="entered") -> int:
    """Insert a fresh trade with the minimal valid Phase 7 NOT NULL fields."""
    trade = Trade(
        id=None, ticker=ticker, entry_date="2026-05-01",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
        current_stop=9.0, state=state,
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at="2026-05-01T16:00:00",
    )
    return insert_trade_with_event(conn, trade, event_ts="2026-05-01T16:00:00")


def test_insert_entry_fill_recomputes_aggregates(tmp_path):
    """Entry fill of 100 @ $10 sets current_size=100, current_avg_cost=10."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    fill = Fill(
        fill_id=None, trade_id=trade_id,
        fill_datetime="2026-05-01T16:00:00", action="entry",
        quantity=100.0, price=10.0,
    )
    with conn:
        insert_fill_with_event(conn, fill, event_ts="2026-05-01T16:00:00")
    trade = get_trade(conn, trade_id)
    assert trade.current_size == 100.0
    assert trade.current_avg_cost == 10.0
    assert trade.last_fill_at == "2026-05-01T16:00:00"


def test_insert_trim_fill_decrements_current_size(tmp_path):
    """Entry of 100 + trim of 40 → current_size = 60."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    with conn:
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-01T16:00:00", action="entry",
            quantity=100.0, price=10.0,
        ), event_ts="2026-05-01T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-02T16:00:00", action="trim",
            quantity=40.0, price=11.0, reason="resistance",
        ), event_ts="2026-05-02T16:00:00")
    trade = get_trade(conn, trade_id)
    assert trade.current_size == 60.0
    assert trade.last_fill_at == "2026-05-02T16:00:00"


def test_get_authoritative_entry_fill_picks_first_by_datetime(tmp_path):
    """Multi-entry-fill scenario: returns the one with min (fill_datetime, fill_id).

    V1 service-layer constraint enforces single entry-fill per trade; this test
    covers the Phase 9 forward-compat path. The selector contract is locked at
    spec §4.3.1.
    """
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    with conn:
        # Insert second-day entry-fill FIRST in time (later by fill_datetime).
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-02T16:00:00", action="entry",
            quantity=50.0, price=11.0,
        ), event_ts="2026-05-02T16:00:00")
        # Then insert first-day entry-fill (earlier by fill_datetime).
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-01T16:00:00", action="entry",
            quantity=50.0, price=10.0,
        ), event_ts="2026-05-01T16:00:00")
    auth = get_authoritative_entry_fill(conn, trade_id)
    assert auth is not None
    assert auth.price == 10.0
    assert auth.fill_datetime == "2026-05-01T16:00:00"


def test_list_fills_for_trade_orders_by_datetime(tmp_path):
    """list_fills returns fills in (fill_datetime ASC, fill_id ASC) order."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    with conn:
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-01T16:00:00", action="entry",
            quantity=100.0, price=10.0,
        ), event_ts="2026-05-01T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-03T16:00:00", action="exit",
            quantity=60.0, price=12.0, reason="target",
        ), event_ts="2026-05-03T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-02T16:00:00", action="trim",
            quantity=40.0, price=11.0, reason="resistance",
        ), event_ts="2026-05-02T16:00:00")
    fills = list_fills_for_trade(conn, trade_id)
    assert [f.action for f in fills] == ["entry", "trim", "exit"]


def test_aggregate_consistency_invariant(tmp_path):
    """current_size = sum(entry qty) - sum(trim/exit/stop qty); 100 - 30 - 70 = 0."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    with conn:
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-01T16:00:00", action="entry",
            quantity=100.0, price=10.0,
        ), event_ts="2026-05-01T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-02T16:00:00", action="trim",
            quantity=30.0, price=11.0, reason="r1",
        ), event_ts="2026-05-02T16:00:00")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-03T16:00:00", action="stop",
            quantity=70.0, price=9.0, reason="stop-hit",
        ), event_ts="2026-05-03T16:00:00")
    trade = get_trade(conn, trade_id)
    assert trade.current_size == 0.0


def test_check_constraint_rejects_invalid_action(tmp_path):
    """fills.action CHECK enum rejects 'bogus'."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    fill = Fill(
        fill_id=None, trade_id=trade_id,
        fill_datetime="2026-05-01T16:00:00", action="bogus",
        quantity=100.0, price=10.0,
    )
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            insert_fill_with_event(conn, fill, event_ts="2026-05-01T16:00:00")


def test_insert_writes_trade_events_audit_row(tmp_path):
    """insert_fill_with_event writes a trade_events row with action mapped to event_type."""
    conn = _seed_v14(tmp_path)
    trade_id = _seed_trade(conn)
    with conn:
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-01T16:00:00", action="entry",
            quantity=100.0, price=10.0,
        ), event_ts="2026-05-01T16:00:00", rationale="vcp-breakout")
        insert_fill_with_event(conn, Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime="2026-05-02T16:00:00", action="trim",
            quantity=30.0, price=11.0,
        ), event_ts="2026-05-02T16:00:00")
    rows = conn.execute(
        "SELECT event_type, rationale, payload_json FROM trade_events "
        "WHERE trade_id = ? ORDER BY id ASC", (trade_id,),
    ).fetchall()
    # One pre-existing trade_events row from insert_trade_with_event ('entry').
    # Plus 2 from insert_fill_with_event: 'entry' (rationale='vcp-breakout'),
    # 'exit' (trim mapped to exit). Discriminate fill-audit rows by payload
    # containing 'fill_datetime'.
    fill_rows = [
        r for r in rows
        if r[2] is not None and "fill_datetime" in r[2]
    ]
    assert len(fill_rows) == 2
    assert any(r[0] == "entry" and r[1] == "vcp-breakout" for r in fill_rows)
    assert any(r[0] == "exit" for r in fill_rows)  # trim mapped to exit
