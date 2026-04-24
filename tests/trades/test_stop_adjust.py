"""Stop adjust service: trail-up invariant + audit event."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.trades import get_trade, list_events_for_trade
from swing.trades.entry import EntryRequest, record_entry
from swing.trades.stop_adjust import StopAdjustRequest, adjust_stop, StopRegressionError


def _seed(conn) -> int:
    req = EntryRequest(
        ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
        shares=10, initial_stop=170.0, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        rationale="entry", event_ts="2026-04-15T09:30:00",
    )
    return record_entry(conn, req, soft_warn=10, hard_cap=10, force=False).trade_id


def test_trail_up_writes_event(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=tid, new_stop=175.0, rationale="breakeven+",
            event_ts="2026-04-17T15:00:00", force=False,
        ))
        assert get_trade(conn, tid).current_stop == 175.0
        events = list_events_for_trade(conn, tid)
        assert any(e.event_type == "stop_adjust" for e in events)
    finally:
        conn.close()


def test_trail_down_blocked_without_force(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        with pytest.raises(StopRegressionError):
            adjust_stop(conn, StopAdjustRequest(
                trade_id=tid, new_stop=165.0, rationale="loosen",
                event_ts="2026-04-17T15:00:00", force=False,
            ))
    finally:
        conn.close()


def test_trail_down_allowed_with_force(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=tid, new_stop=165.0, rationale="config change override",
            event_ts="2026-04-17T15:00:00", force=True,
        ))
        assert get_trade(conn, tid).current_stop == 165.0
    finally:
        conn.close()


def test_no_op_same_stop(tmp_path: Path):
    """Setting stop to current value is a no-op (no audit row)."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=tid, new_stop=170.0, rationale="no-op",
            event_ts="2026-04-17T15:00:00", force=False,
        ))
        events = list_events_for_trade(conn, tid)
        assert sum(1 for e in events if e.event_type == "stop_adjust") == 0
    finally:
        conn.close()


def test_adjust_stop_carries_notes_through_to_trade_events(tmp_path: Path):
    """Bug 3b: StopAdjustRequest.notes round-trips through the service to
    trade_events.notes. Rationale is independent and preserved."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=tid, new_stop=175.0, rationale="trail-10MA",
            notes="low-volume up-day, tightened per plan",
            event_ts="2026-04-17T15:00:00", force=False,
        ))
        adj = next(
            e for e in list_events_for_trade(conn, tid) if e.event_type == "stop_adjust"
        )
        assert adj.rationale == "trail-10MA"
        assert adj.notes == "low-volume up-day, tightened per plan"
    finally:
        conn.close()


def test_adjust_stop_default_notes_is_none(tmp_path: Path):
    """StopAdjustRequest without notes still works and persists NULL notes."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=tid, new_stop=175.0, rationale="trail",
            event_ts="2026-04-17T15:00:00", force=False,
        ))
        adj = next(
            e for e in list_events_for_trade(conn, tid) if e.event_type == "stop_adjust"
        )
        assert adj.notes is None
    finally:
        conn.close()
