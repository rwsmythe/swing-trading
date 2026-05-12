"""Phase 9 Sub-bundle B — tos_import reconciliation extension tests.

T-B.3: close_price_mismatch + entry_price_mismatch detection per spec §6.1.
Future tasks (T-B.4 stop_mismatch, T-B.5 position_qty_mismatch, T-B.6
cash_movement_mismatch) append additional discrepancy-type sections to
this file as they land.

Strict-greater-than tolerance convention preserved at
``swing/journal/tos_import.py:365``: exact (delta=0) → NO emit; within
(delta=0.005) → NO emit; at boundary (delta=0.01) → NO emit; outside
(delta=0.02) → EMIT. This is the discriminating boundary pattern per
plan T-B.3 acceptance criteria.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.journal.tos_import import reconcile_tos


# ---------------------------------------------------------------------------
# Seeding helpers (mirror tests/journal/test_tos_import.py:_seed_entry).
# ---------------------------------------------------------------------------


def _seed_entry(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    entry_date: str,
    entry_price: float,
    shares: int,
    initial_stop: float,
) -> int:
    event_ts = f"{entry_date}T09:30:00"
    trade = Trade(
        id=None,
        ticker=ticker,
        entry_date=entry_date,
        entry_price=entry_price,
        initial_shares=shares,
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
        tid = insert_trade_with_event(
            conn, trade, event_ts=event_ts, rationale="seed",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None,
                trade_id=tid,
                fill_datetime=event_ts,
                action="entry",
                quantity=float(shares),
                price=entry_price,
            ),
            event_ts=event_ts,
        )
    return tid


def _seed_exit(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    exit_date: str,
    exit_price: float,
    shares: int,
) -> int:
    event_ts = f"{exit_date}T15:30:00"
    with conn:
        fid = insert_fill_with_event(
            conn,
            Fill(
                fill_id=None,
                trade_id=trade_id,
                fill_datetime=event_ts,
                action="exit",
                quantity=float(shares),
                price=exit_price,
                reason="target",
            ),
            event_ts=event_ts,
        )
    return fid


# ---------------------------------------------------------------------------
# Inline TOS CSV builders — single OPEN or CLOSE fill for each scenario.
# ---------------------------------------------------------------------------


_TOS_OPEN_TEMPLATE = """\
Account Trade History
Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
{exec_time},STOCK,BUY,+{qty},OPENING,{ticker},,,,{price:.4f},{price:.4f},MKT
"""

_TOS_CLOSE_TEMPLATE = """\
Account Trade History
Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
{exec_time},STOCK,SELL,-{qty},CLOSING,{ticker},,,,{price:.4f},{price:.4f},MKT
"""


def _tos_open(*, ticker: str, date: str, qty: int, price: float) -> str:
    return _TOS_OPEN_TEMPLATE.format(
        exec_time=f"{date} 10:00:00",
        qty=qty,
        ticker=ticker,
        price=price,
    )


def _tos_close(*, ticker: str, date: str, qty: int, price: float) -> str:
    return _TOS_CLOSE_TEMPLATE.format(
        exec_time=f"{date} 15:30:00",
        qty=qty,
        ticker=ticker,
        price=price,
    )


# ---------------------------------------------------------------------------
# Capture-emitter test fixture.
# ---------------------------------------------------------------------------


def _make_capture_emitter() -> tuple[list[dict], "callable"]:
    captured: list[dict] = []

    def _emit(**kw):
        captured.append(kw)
        return len(captured)

    return captured, _emit


@pytest.fixture
def db_with_schema(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


# ===========================================================================
# §1 — entry_price_mismatch detection (spec §6.1 + §3.3.1)
# ===========================================================================


def test_entry_price_mismatch_exact_match_no_emit(
    db_with_schema: Path,
) -> None:
    conn = sqlite3.connect(db_with_schema)
    try:
        _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-12",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        text = _tos_open(ticker="ABC", date="2026-05-12", qty=10, price=10.00)
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        assert captured == []
    finally:
        conn.close()


def test_entry_price_mismatch_within_tolerance_no_emit(
    db_with_schema: Path,
) -> None:
    conn = sqlite3.connect(db_with_schema)
    try:
        _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-12",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        text = _tos_open(ticker="ABC", date="2026-05-12", qty=10, price=10.005)
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        assert captured == []
    finally:
        conn.close()


def test_entry_price_mismatch_at_boundary_no_emit(
    db_with_schema: Path,
) -> None:
    """Strict > tolerance: delta = 0.01 (== tolerance) MUST NOT emit."""
    conn = sqlite3.connect(db_with_schema)
    try:
        _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-12",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        text = _tos_open(ticker="ABC", date="2026-05-12", qty=10, price=10.01)
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        assert captured == []
    finally:
        conn.close()


def test_entry_price_mismatch_outside_tolerance_emits(
    db_with_schema: Path,
) -> None:
    conn = sqlite3.connect(db_with_schema)
    try:
        tid = _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-12",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        text = _tos_open(ticker="ABC", date="2026-05-12", qty=10, price=10.02)
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        assert len(captured) == 1
        e = captured[0]
        assert e["discrepancy_type"] == "entry_price_mismatch"
        assert e["run_id"] == 1
        assert e["trade_id"] == tid
        assert e["ticker"] == "ABC"
        assert e["field_name"] == "price"
        assert e["material_to_review"] == 1
        # JSON shape per spec §3.3.1.
        expected = json.loads(e["expected_value_json"])
        actual = json.loads(e["actual_value_json"])
        assert expected == {"price": 10.00, "entry_date": "2026-05-12"}
        assert actual == {"price": 10.02, "fill_date": "2026-05-12"}
        # delta_text signed dollar formatting.
        assert e["delta_text"] == "$+0.02 price difference"
        # fill_id populated (entry fill exists).
        assert e["fill_id"] is not None
    finally:
        conn.close()


def test_entry_price_mismatch_negative_delta_emits_negative_sign(
    db_with_schema: Path,
) -> None:
    conn = sqlite3.connect(db_with_schema)
    try:
        _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-12",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        text = _tos_open(ticker="ABC", date="2026-05-12", qty=10, price=9.95)
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        assert len(captured) == 1
        assert captured[0]["delta_text"] == "$-0.05 price difference"
    finally:
        conn.close()


# ===========================================================================
# §2 — close_price_mismatch detection (spec §6.1 + §3.3.1)
# ===========================================================================


def test_close_price_mismatch_exact_match_no_emit(
    db_with_schema: Path,
) -> None:
    conn = sqlite3.connect(db_with_schema)
    try:
        tid = _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-10",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        # Journal exit fill at 11.00 (partial exit; trade still open).
        _seed_exit(
            conn,
            trade_id=tid,
            exit_date="2026-05-12",
            exit_price=11.00,
            shares=5,
        )
        # TOS close fill matches journal exit price exactly.
        text = _tos_close(ticker="ABC", date="2026-05-12", qty=5, price=11.00)
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        # No close_price_mismatch emit.
        assert all(c["discrepancy_type"] != "close_price_mismatch" for c in captured)
    finally:
        conn.close()


def test_close_price_mismatch_at_boundary_no_emit(
    db_with_schema: Path,
) -> None:
    """delta = tolerance (0.01) MUST NOT emit (strict >)."""
    conn = sqlite3.connect(db_with_schema)
    try:
        tid = _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-10",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        _seed_exit(
            conn,
            trade_id=tid,
            exit_date="2026-05-12",
            exit_price=11.00,
            shares=5,
        )
        text = _tos_close(ticker="ABC", date="2026-05-12", qty=5, price=11.01)
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        assert all(c["discrepancy_type"] != "close_price_mismatch" for c in captured)
    finally:
        conn.close()


def test_close_price_mismatch_outside_tolerance_emits(
    db_with_schema: Path,
) -> None:
    conn = sqlite3.connect(db_with_schema)
    try:
        tid = _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-10",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        je_fid = _seed_exit(
            conn,
            trade_id=tid,
            exit_date="2026-05-12",
            exit_price=11.00,
            shares=5,
        )
        text = _tos_close(ticker="ABC", date="2026-05-12", qty=5, price=11.20)
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        # Find the close_price_mismatch emit.
        cpms = [c for c in captured if c["discrepancy_type"] == "close_price_mismatch"]
        assert len(cpms) == 1
        e = cpms[0]
        assert e["trade_id"] == tid
        assert e["fill_id"] == je_fid
        assert e["ticker"] == "ABC"
        assert e["field_name"] == "price"
        assert e["material_to_review"] == 1
        # JSON shape per spec §3.3.1.
        expected = json.loads(e["expected_value_json"])
        actual = json.loads(e["actual_value_json"])
        assert expected == {"price": 11.00, "exit_date": "2026-05-12"}
        assert actual == {"price": 11.20, "fill_date": "2026-05-12"}
        assert e["delta_text"] == "$+0.20 price difference"
    finally:
        conn.close()


def test_close_price_mismatch_no_journal_exit_no_emit(
    db_with_schema: Path,
) -> None:
    """When journal has no recorded exit yet, close_price_mismatch cannot
    fire (nothing to compare against). The TOS fill still routes as
    'matched' against the open-size cap.
    """
    conn = sqlite3.connect(db_with_schema)
    try:
        _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-10",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        # NO journal exit; the trade is still fully open.
        text = _tos_close(ticker="ABC", date="2026-05-12", qty=5, price=11.20)
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        assert all(c["discrepancy_type"] != "close_price_mismatch" for c in captured)
    finally:
        conn.close()


# ===========================================================================
# §3 — emitter unused when run_id+emitter not provided (T-B.2 boundary).
# ===========================================================================


def test_no_emit_when_emitter_none(db_with_schema: Path) -> None:
    """When the emitter is None, the legacy bucket-list behavior is the
    sole reporting channel — no side-channel emits occur.
    """
    conn = sqlite3.connect(db_with_schema)
    try:
        _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-12",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        text = _tos_open(ticker="ABC", date="2026-05-12", qty=10, price=10.02)
        report = reconcile_tos(conn=conn, tos_text=text)
        # Existing bucket-list behavior: price_mismatch_fills populated.
        assert len(report.price_mismatch_fills) == 1
    finally:
        conn.close()


# ===========================================================================
# §4 — within-run dedup (spec §5.1 R3 Major #4) — pinned via duplicate
# rows in the same CSV.
# ===========================================================================


def test_within_run_dedup_on_identical_tuple(db_with_schema: Path) -> None:
    """Two identical OPEN rows in one TOS CSV produce a single
    entry_price_mismatch emit (deduplication on
    (trade_id, type, field_name, ticker, fill_id, cash_movement_id)).
    Cross-run dedup is explicitly NOT done; subsequent runs against the
    same CSV emit again (legitimate audit workflow).
    """
    conn = sqlite3.connect(db_with_schema)
    try:
        _seed_entry(
            conn,
            ticker="ABC",
            entry_date="2026-05-12",
            entry_price=10.00,
            shares=10,
            initial_stop=9.00,
        )
        # Two identical TOS rows would both attempt to emit; dedup skips
        # the second. (The match-loop fall-through: 2nd OPEN cannot
        # double-match the same trade given the cumulative cap — but the
        # dedup contract is the binding regardless of how the matcher
        # routes the duplicate.)
        first = _tos_open(ticker="ABC", date="2026-05-12", qty=10, price=10.05)
        # Append a second header-less row by concatenating the data line.
        text = first + (
            "2026-05-12 10:00:01,STOCK,BUY,+10,OPENING,ABC,,,,10.0500,10.0500,MKT\n"
        )
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        epms = [c for c in captured if c["discrepancy_type"] == "entry_price_mismatch"]
        assert len(epms) == 1
    finally:
        conn.close()
