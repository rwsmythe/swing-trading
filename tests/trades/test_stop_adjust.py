"""Stop adjust service: trail-up invariant + audit event."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import run_migrations
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import get_trade, insert_trade_with_event, list_events_for_trade
from swing.trades.stop_adjust import (
    StopAdjustRationale,
    StopAdjustRequest,
    StopRegressionError,
    adjust_stop,
    stop_adjust_rationale_options,
    update_stop_with_event,
)


def test_stop_adjust_rationale_enum_values_match_spec_order():
    """Tranche B-ops T5: StopAdjustRationale enum is the closed taxonomy per
    spec §3 table, in the spec-declared order."""
    assert [r.value for r in StopAdjustRationale] == [
        "breakeven",
        "trail-10ma",
        "trail-20ma",
        "weather-tighten",
        "manual-trail",
        "news",
        "other",
    ]


def test_stop_adjust_rationale_options_pair_value_with_display_label():
    """stop_adjust_rationale_options() returns (value, label) pairs in enum
    order. Template consumes this to render the <select>."""
    opts = stop_adjust_rationale_options()
    assert len(opts) == 7
    assert opts[0] == ("breakeven", "Move to breakeven (system advisory)")
    assert opts[-1] == ("other", "Other (see notes)")
    assert {v for v, _ in opts} == {r.value for r in StopAdjustRationale}


def _seed_v14(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "swing.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    return conn


def _seed_active_trade(
    conn: sqlite3.Connection, *,
    ticker: str = "AAPL",
    state: str = "managing",
    current_size: float = 10.0,
    entry_price: float = 180.0,
    initial_stop: float = 170.0,
    event_ts: str = "2026-04-15T09:30:00",
) -> int:
    trade = Trade(
        id=None,
        ticker=ticker,
        entry_date="2026-04-15",
        entry_price=entry_price,
        initial_shares=int(current_size),
        initial_stop=initial_stop,
        current_stop=initial_stop,
        state="entered",
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at=event_ts,
    )
    with conn:
        trade_id = insert_trade_with_event(
            conn, trade, event_ts=event_ts, rationale="seed",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None,
                trade_id=trade_id,
                fill_datetime=event_ts,
                action="entry",
                quantity=float(current_size),
                price=entry_price,
            ),
            event_ts=event_ts,
        )
        if state != "entered":
            conn.execute("UPDATE trades SET state=? WHERE id=?", (state, trade_id))
    return trade_id


def test_trail_up_writes_event(tmp_path: Path):
    conn = _seed_v14(tmp_path)
    try:
        tid = _seed_active_trade(conn)
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
    conn = _seed_v14(tmp_path)
    try:
        tid = _seed_active_trade(conn)
        with pytest.raises(StopRegressionError):
            adjust_stop(conn, StopAdjustRequest(
                trade_id=tid, new_stop=165.0, rationale="loosen",
                event_ts="2026-04-17T15:00:00", force=False,
            ))
    finally:
        conn.close()


def test_trail_down_allowed_with_force(tmp_path: Path):
    conn = _seed_v14(tmp_path)
    try:
        tid = _seed_active_trade(conn)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=tid, new_stop=165.0, rationale="config change override",
            event_ts="2026-04-17T15:00:00", force=True,
        ))
        assert get_trade(conn, tid).current_stop == 165.0
    finally:
        conn.close()


def test_no_op_same_stop(tmp_path: Path):
    """Setting stop to current value is a no-op (no audit row)."""
    conn = _seed_v14(tmp_path)
    try:
        tid = _seed_active_trade(conn)
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
    conn = _seed_v14(tmp_path)
    try:
        tid = _seed_active_trade(conn)
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
    conn = _seed_v14(tmp_path)
    try:
        tid = _seed_active_trade(conn)
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


def test_stop_adjust_rejected_on_closed_state(tmp_path: Path):
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(conn, state="closed")
        with pytest.raises(ValueError, match="not active"):
            update_stop_with_event(
                conn,
                trade_id=trade_id,
                new_stop=169.5,
                event_ts="2026-05-05T16:00:00",
            )
    finally:
        conn.close()


def test_first_stop_adjust_on_entered_transitions_to_managing(tmp_path: Path):
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(conn, state="entered")
        update_stop_with_event(
            conn,
            trade_id=trade_id,
            new_stop=169.5,
            event_ts="2026-05-05T16:00:00",
        )
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "managing"
        assert trade.current_stop == 169.5
    finally:
        conn.close()


def test_subsequent_stop_adjust_on_managing_no_state_change(tmp_path: Path):
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(conn, state="managing")
        update_stop_with_event(
            conn,
            trade_id=trade_id,
            new_stop=169.5,
            event_ts="2026-05-05T16:00:00",
        )
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "managing"
        assert trade.current_stop == 169.5
    finally:
        conn.close()


def test_adjust_stop_rejects_terminal_state(tmp_path: Path):
    """B.5: adjust_stop rejects state='closed'/'reviewed' BEFORE writing anything."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(conn, state="closed")
        with pytest.raises(ValueError, match="not active"):
            adjust_stop(conn, StopAdjustRequest(
                trade_id=trade_id, new_stop=11.0,
                rationale="trail-10ma", event_ts="2026-05-05T16:00:00",
            ))
        # Discriminating: no stop_adjust event written.
        events = conn.execute(
            "SELECT * FROM trade_events WHERE trade_id=? AND event_type='stop_adjust'",
            (trade_id,),
        ).fetchall()
        assert len(events) == 0
    finally:
        conn.close()


def test_adjust_stop_first_on_entered_transitions_to_managing(tmp_path: Path):
    """B.5: adjust_stop on state='entered' atomically transitions to 'managing'
    per spec §3.3."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(conn, state="entered", initial_stop=9.0)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=trade_id, new_stop=9.5,
            rationale="trail-10ma", event_ts="2026-05-05T16:00:00",
        ))
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "managing"
        assert trade.current_stop == 9.5
    finally:
        conn.close()


def test_adjust_stop_subsequent_on_managing_no_state_change(tmp_path: Path):
    """B.5: adjust_stop on state='managing' does NOT change state
    (no managing→managing transition)."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(conn, state="managing", initial_stop=9.0)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=trade_id, new_stop=9.5,
            rationale="trail-10ma", event_ts="2026-05-05T16:00:00",
        ))
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "managing"
        assert trade.current_stop == 9.5
    finally:
        conn.close()


def test_adjust_stop_force_lower_on_entered_still_transitions_to_managing(tmp_path: Path):
    """B.5: force=True bypasses trail-up guard but does NOT bypass state transition.
    Discriminating: pre-fix would land the lower stop without entering 'managing';
    post-fix lands the stop AND moves the trade into managing."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(conn, state="entered", initial_stop=9.0)
        adjust_stop(conn, StopAdjustRequest(
            trade_id=trade_id, new_stop=8.5,  # LOWER than current_stop=9.0
            rationale="manual-trail", event_ts="2026-05-05T16:00:00", force=True,
        ))
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "managing"
        assert trade.current_stop == 8.5
    finally:
        conn.close()
