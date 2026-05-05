"""Trade exit service tests — fills + state transition (Phase 7 Sub-B B.4)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import run_migrations
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event, list_fills_for_trade
from swing.data.repos.trades import get_trade, insert_trade_with_event
from swing.trades.exit import ExitReason, ExitRequest, record_exit


def _seed_v14(tmp_path: Path) -> sqlite3.Connection:
    """Open a fresh DB and migrate to v14 (Phase 7 schema baseline)."""
    db = tmp_path / "swing.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    return conn


def _seed_active_trade(
    conn: sqlite3.Connection, *,
    ticker: str = "TST",
    state: str = "managing",
    current_size: float = 100.0,
    entry_price: float = 10.0,
    initial_stop: float = 9.0,
    event_ts: str = "2026-05-04T16:00:00",
) -> int:
    """Seed a trade row + entry fill so ``current_size`` denorm is correct.

    ``record_entry`` (Sub-B B.1) now enforces a pre-trade validation gate that
    rejects the legacy minimal request used by these tests; we bypass it by
    going straight through ``insert_trade_with_event`` + entry-fill INSERT,
    then UPDATE state if the test wants a non-entered start state.
    """
    trade = Trade(
        id=None, ticker=ticker, entry_date="2026-05-04",
        entry_price=entry_price, initial_shares=int(current_size),
        initial_stop=initial_stop, current_stop=initial_stop,
        state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
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
                fill_id=None, trade_id=trade_id,
                fill_datetime=event_ts, action="entry",
                quantity=float(current_size), price=entry_price,
            ),
            event_ts=event_ts,
        )
        if state != "entered":
            conn.execute(
                "UPDATE trades SET state=? WHERE id=?", (state, trade_id),
            )
    return trade_id


# ---------------------------------------------------------------------------
# Plan §5 B.4 — six new discriminating tests.
# ---------------------------------------------------------------------------


def test_record_exit_partial_writes_trim_fill_and_transitions_to_partial_exited(
    tmp_path: Path,
):
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="TST", state="managing", current_size=100.0,
        )
        record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-05-05", exit_price=11.0,
            shares=40, reason=ExitReason.TARGET, notes=None, rationale="trim",
            event_ts="2026-05-05T16:00:00",
        ))
        fills = list_fills_for_trade(conn, trade_id)
        actions = [f.action for f in fills]
        assert "trim" in actions
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "partial_exited"
        assert trade.current_size == 60.0
    finally:
        conn.close()


def test_record_exit_full_writes_exit_fill_and_transitions_to_closed(
    tmp_path: Path,
):
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="TST", state="managing", current_size=100.0,
        )
        record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-05-05", exit_price=11.0,
            shares=100, reason=ExitReason.TARGET, notes=None,
            rationale="full exit", event_ts="2026-05-05T16:00:00",
        ))
        fills = list_fills_for_trade(conn, trade_id)
        actions = [f.action for f in fills]
        assert "exit" in actions
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "closed"
        assert trade.current_size == 0.0
    finally:
        conn.close()


def test_record_exit_stop_hit_uses_stop_action(tmp_path: Path):
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="TST", state="managing", current_size=100.0,
        )
        record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-05-05", exit_price=8.5,
            shares=100, reason=ExitReason.STOP_HIT, notes=None,
            rationale="stop", event_ts="2026-05-05T16:00:00",
        ))
        fills = list_fills_for_trade(conn, trade_id)
        stop_fill = next(f for f in fills if f.action == "stop")
        assert stop_fill.quantity == 100.0
    finally:
        conn.close()


def test_record_exit_same_day_stop_out_double_transitions(tmp_path: Path):
    """Spec §3.3: entered → managing → closed must be an atomic double-step.

    Discriminator: a naive single-step entered→closed call would raise
    InvalidStateTransition (not in ALLOWED_TRANSITIONS). Passing requires the
    service to issue both transitions in the same ``with conn:`` block.
    """
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="TST", state="entered", current_size=100.0,
        )
        record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-05-05", exit_price=8.5,
            shares=100, reason=ExitReason.STOP_HIT, notes=None,
            rationale="stop", event_ts="2026-05-05T16:00:00",
        ))
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "closed"
        assert trade.current_size == 0.0
    finally:
        conn.close()


def test_record_exit_rejects_terminal_state(tmp_path: Path):
    """Closed/reviewed are terminal; record_exit must raise."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="TST", state="closed", current_size=100.0,
        )
        with pytest.raises(ValueError, match="not active"):
            record_exit(conn, ExitRequest(
                trade_id=trade_id, exit_date="2026-05-05", exit_price=11.0,
                shares=10, reason=ExitReason.MANUAL, notes=None,
                rationale="x", event_ts="2026-05-05T16:00:00",
            ))
    finally:
        conn.close()


def test_record_exit_partial_from_entered_steps_through_managing(
    tmp_path: Path,
):
    """Partial exit straight off 'entered' must double-step to 'partial_exited'.

    Discriminator: single-step entered→partial_exited is not allowed; the
    service must issue entered→managing→partial_exited in one transaction.
    """
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="TST", state="entered", current_size=100.0,
        )
        record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-05-05", exit_price=11.0,
            shares=30, reason=ExitReason.TARGET, notes=None,
            rationale="early trim", event_ts="2026-05-05T16:00:00",
        ))
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "partial_exited"
        assert trade.current_size == 70.0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Legacy tests (rewritten for B.4): fill-based ledger + state semantics.
# ---------------------------------------------------------------------------


def test_full_exit_transitions_state_to_closed_and_computes_r(tmp_path: Path):
    """Full exit at 2R closes the trade and returns realized_pnl + r_multiple."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="AAPL", state="managing", current_size=10.0,
            entry_price=180.0, initial_stop=170.0,
        )
        result = record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-04-22", exit_price=200.0,
            shares=10, reason=ExitReason.TARGET, notes=None,
            rationale="target hit", event_ts="2026-04-22T15:30:00",
        ))
        assert result.realized_pnl == pytest.approx(200.0)
        assert result.r_multiple == pytest.approx(2.0)
        assert result.fully_closed is True
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "closed"
    finally:
        conn.close()


def test_partial_exit_keeps_open(tmp_path: Path):
    """Partial trim leaves remaining size and transitions to partial_exited."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="AAPL", state="managing", current_size=10.0,
            entry_price=180.0, initial_stop=170.0,
        )
        result = record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-04-18", exit_price=185.0,
            shares=5, reason=ExitReason.MANUAL, notes=None,
            rationale="trim", event_ts="2026-04-18T15:00:00",
        ))
        assert result.fully_closed is False
        assert result.r_multiple == pytest.approx(0.5)
        assert result.realized_pnl == pytest.approx(25.0)
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "partial_exited"
        assert trade.current_size == 5.0
    finally:
        conn.close()


def test_exit_loss(tmp_path: Path):
    """Stop-out at -1R returns negative pnl + -1.0 R."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="AAPL", state="managing", current_size=10.0,
            entry_price=180.0, initial_stop=170.0,
        )
        result = record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-04-18", exit_price=170.0,
            shares=10, reason=ExitReason.STOP_HIT, notes=None,
            rationale="stopped", event_ts="2026-04-18T15:00:00",
        ))
        assert result.realized_pnl == pytest.approx(-100.0)
        assert result.r_multiple == pytest.approx(-1.0)
    finally:
        conn.close()


def test_overfill_raises(tmp_path: Path):
    """Exit shares > current_size must raise ValueError."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="AAPL", state="managing", current_size=10.0,
            entry_price=180.0, initial_stop=170.0,
        )
        with pytest.raises(ValueError, match="exceeds remaining"):
            record_exit(conn, ExitRequest(
                trade_id=trade_id, exit_date="2026-04-18", exit_price=185.0,
                shares=11, reason=ExitReason.MANUAL, notes=None,
                rationale="overfill", event_ts="2026-04-18T15:00:00",
            ))
    finally:
        conn.close()


def test_invalid_reason_raises(tmp_path: Path):
    """Non-ExitReason reason argument must raise ValueError."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="AAPL", state="managing", current_size=10.0,
            entry_price=180.0, initial_stop=170.0,
        )
        with pytest.raises(ValueError):
            record_exit(conn, ExitRequest(
                trade_id=trade_id, exit_date="2026-04-18", exit_price=185.0,
                shares=5, reason="invalid_reason",  # type: ignore[arg-type]
                notes=None, rationale="x", event_ts="2026-04-18T15:00:00",
            ))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Codex R1 Major 1 + 2 regression guards — late-recorded exit + notes preservation.
# ---------------------------------------------------------------------------


def test_record_exit_uses_exit_date_for_fill_datetime_not_event_ts(tmp_path: Path):
    """Codex R1 M1: an exit recorded after-the-fact (operator types it
    days later) must persist fill_datetime keyed to req.exit_date, not the
    command's event_ts. Otherwise tos_import substr-date matching breaks
    and journal close-date aggregation lands the trade on the wrong day.

    Pre-fix: fill_datetime = req.event_ts (today's clock-time).
    Post-fix: fill_datetime = f"{req.exit_date}T16:00:00" (NYSE close).
    """
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="LATE", state="managing", current_size=10.0,
        )
        # Exit was 2 days ago; operator records it now.
        record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-05-02", exit_price=11.0,
            shares=10, reason=ExitReason.TARGET, notes=None,
            rationale="late record", event_ts="2026-05-04T12:34:56",
        ))
        from swing.data.repos.fills import list_fills_for_trade
        fills = list_fills_for_trade(conn, trade_id)
        exit_fill = next(f for f in fills if f.action != "entry")
        assert exit_fill.fill_datetime.startswith("2026-05-02"), (
            f"fill_datetime must reflect exit_date 2026-05-02, "
            f"got {exit_fill.fill_datetime!r}"
        )
        assert exit_fill.fill_datetime == "2026-05-02T16:00:00"
    finally:
        conn.close()


def test_record_exit_passes_exit_datetime_through_when_iso_provided(tmp_path: Path):
    """Codex R1 M1: when caller provides a full ISO datetime as exit_date,
    use it as-is (don't double-append T16:00:00)."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="PRE", state="managing", current_size=10.0,
        )
        record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-05-03T13:45:30",
            exit_price=11.0, shares=10, reason=ExitReason.TARGET, notes=None,
            rationale="iso datetime", event_ts="2026-05-04T12:00:00",
        ))
        from swing.data.repos.fills import list_fills_for_trade
        fills = list_fills_for_trade(conn, trade_id)
        exit_fill = next(f for f in fills if f.action != "entry")
        assert exit_fill.fill_datetime == "2026-05-03T13:45:30"
    finally:
        conn.close()


def test_record_exit_persists_notes_to_trade_events(tmp_path: Path):
    """Codex R1 M2: req.notes must NOT be silently dropped. Persist via
    a 'note' trade_events row parallel to the fill+state writes.

    Pre-fix: notes=req.notes flowed into ExitRequest but record_exit ignored
    it (fills schema has no notes column; insert_fill_with_event has no
    notes parameter).
    Post-fix: a separate add_note_event call lands the operator notes
    inside the same with-conn block.
    """
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="NOTE", state="managing", current_size=10.0,
        )
        record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-05-05", exit_price=11.0,
            shares=10, reason=ExitReason.TARGET,
            notes="Hit overhead supply zone; took the win.",
            rationale="target", event_ts="2026-05-05T16:00:00",
        ))
        rows = conn.execute(
            """SELECT event_type, payload_json FROM trade_events
               WHERE trade_id=? AND event_type='note'
               ORDER BY id""",
            (trade_id,),
        ).fetchall()
        assert len(rows) >= 1, "expected at least one 'note' trade_event"
        notes_row = next(
            r for r in rows
            if "Hit overhead supply zone" in (r[1] or "")
        )
        assert notes_row is not None


    finally:
        conn.close()


def test_record_exit_empty_notes_omits_note_event(tmp_path: Path):
    """Codex R1 M2: empty/whitespace notes should NOT trigger a phantom
    'note' event row (avoids cluttering trade_events with empty payloads)."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="EMPT", state="managing", current_size=10.0,
        )
        record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-05-05", exit_price=11.0,
            shares=10, reason=ExitReason.TARGET, notes="   ",
            rationale="target", event_ts="2026-05-05T16:00:00",
        ))
        # State-transition 'note' rows have payload_json containing 'from_state'.
        # An operator-supplied empty-notes row would have a payload that does
        # NOT contain 'from_state' (it'd be the bare {"note": "..."} shape from
        # add_note_event). Discriminating: zero such rows post-fix.
        operator_note_rows = conn.execute(
            """SELECT payload_json FROM trade_events WHERE trade_id=?
               AND event_type='note' AND payload_json NOT LIKE '%from_state%'""",
            (trade_id,),
        ).fetchall()
        assert len(operator_note_rows) == 0, (
            f"empty/whitespace notes should NOT add an operator-notes row; "
            f"got {operator_note_rows!r}"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Codex R2 Major 1 regression guard — exit_date format validation.
# ---------------------------------------------------------------------------


def test_record_exit_rejects_malformed_exit_date_with_t(tmp_path: Path):
    """Codex R2 M1: exit_date containing 'T' but not a parseable ISO
    datetime must raise ValueError BEFORE any fill is INSERTed.

    Pre-fix: any string with 'T' was passed through verbatim, so
    'YYYY-MM-DDTNOT_A_TIME' silently stored as garbage and broke
    substr-date matching downstream.
    Post-fix: datetime.fromisoformat raises; record_exit re-raises with
    a clear message; no fill row, no audit row written.
    """
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="BAD", state="managing", current_size=10.0,
        )
        with pytest.raises(ValueError, match="not a valid ISO datetime"):
            record_exit(conn, ExitRequest(
                trade_id=trade_id, exit_date="2026-05-02TNOT_A_TIME",
                exit_price=11.0, shares=10, reason=ExitReason.TARGET,
                notes=None, rationale="malformed", event_ts="2026-05-04T12:00:00",
            ))
        # Discriminating: no fill or note row should exist for this trade
        # beyond the seed entry-fill (which the helper inserted).
        n_non_entry_fills = conn.execute(
            "SELECT COUNT(*) FROM fills WHERE trade_id=? AND action != 'entry'",
            (trade_id,),
        ).fetchone()[0]
        assert n_non_entry_fills == 0
    finally:
        conn.close()


def test_record_exit_rejects_malformed_date_only_input(tmp_path: Path):
    """Codex R2 M1: exit_date without 'T' must parse as YYYY-MM-DD
    (date.fromisoformat); '2026-13-99' must raise."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="BAD2", state="managing", current_size=10.0,
        )
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            record_exit(conn, ExitRequest(
                trade_id=trade_id, exit_date="2026-13-99",
                exit_price=11.0, shares=10, reason=ExitReason.TARGET,
                notes=None, rationale="bad month", event_ts="2026-05-04T12:00:00",
            ))
    finally:
        conn.close()


def test_record_exit_accepts_valid_iso_datetime_with_seconds(tmp_path: Path):
    """Codex R2 M1: a properly-formed ISO datetime with seconds AND
    microseconds round-trips unchanged."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="ISO", state="managing", current_size=10.0,
        )
        record_exit(conn, ExitRequest(
            trade_id=trade_id, exit_date="2026-05-03T13:45:30.123456",
            exit_price=11.0, shares=10, reason=ExitReason.TARGET,
            notes=None, rationale="iso usec", event_ts="2026-05-04T12:00:00",
        ))
        from swing.data.repos.fills import list_fills_for_trade
        fills = list_fills_for_trade(conn, trade_id)
        exit_fill = next(f for f in fills if f.action != "entry")
        assert exit_fill.fill_datetime == "2026-05-03T13:45:30.123456"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Codex R3 Major 1 regression guard — tz-aware datetimes break ordering.
# ---------------------------------------------------------------------------


def test_record_exit_rejects_timezone_aware_iso_datetime(tmp_path: Path):
    """Codex R3 M1: tz-aware ISO datetimes break the lexicographic-ordering
    invariant that fills.py ORDER BY fill_datetime relies on (an offset-
    bearing string like '2026-05-03T13:45:30+05:00' sorts AFTER naive
    '2026-05-03T09:00:00' despite being earlier in absolute time).
    Reject the input before persisting.

    Discriminator: pre-fix this string round-tripped silently and broke
    chronological ordering. Post-fix raises ValueError; no fill written.
    """
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_active_trade(
            conn, ticker="TZ", state="managing", current_size=10.0,
        )
        with pytest.raises(ValueError, match="timezone-aware"):
            record_exit(conn, ExitRequest(
                trade_id=trade_id, exit_date="2026-05-03T13:45:30+05:00",
                exit_price=11.0, shares=10, reason=ExitReason.TARGET,
                notes=None, rationale="tz", event_ts="2026-05-04T12:00:00",
            ))
        n_non_entry_fills = conn.execute(
            "SELECT COUNT(*) FROM fills WHERE trade_id=? AND action != 'entry'",
            (trade_id,),
        ).fetchone()[0]
        assert n_non_entry_fills == 0
    finally:
        conn.close()
