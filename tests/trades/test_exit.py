"""Trade exit service — computes pnl + R then writes via repo."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.trades import (
    get_trade, list_exits_for_trade, list_events_for_trade,
)
from swing.trades.entry import EntryRequest, record_entry
from swing.trades.exit import ExitRequest, record_exit, ExitReason


def _seed(conn, ticker: str = "AAPL") -> int:
    req = EntryRequest(
        ticker=ticker, entry_date="2026-04-15", entry_price=180.0,
        shares=10, initial_stop=170.0, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None, rationale="entry",
        event_ts="2026-04-15T09:30:00",
    )
    return record_entry(conn, req, soft_warn=10, hard_cap=10, force=False).trade_id


def test_full_exit_flips_status_and_computes_r(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        result = record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-22", exit_price=200.0,
            shares=10, reason=ExitReason.TARGET, notes=None,
            rationale="target hit", event_ts="2026-04-22T15:30:00",
        ))
        assert result.realized_pnl == pytest.approx(200.0)
        assert result.r_multiple == pytest.approx(2.0)
        assert result.fully_closed is True
        assert get_trade(conn, tid).status == "closed"
    finally:
        conn.close()


def test_partial_exit_keeps_open(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        result = record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-18", exit_price=185.0,
            shares=5, reason=ExitReason.MANUAL, notes=None,
            rationale="trim", event_ts="2026-04-18T15:00:00",
        ))
        assert result.fully_closed is False
        assert get_trade(conn, tid).status == "open"
        assert result.r_multiple == pytest.approx(0.5)
        assert result.realized_pnl == pytest.approx(25.0)
    finally:
        conn.close()


def test_exit_loss(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        result = record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-18", exit_price=170.0,
            shares=10, reason=ExitReason.STOP_HIT, notes=None,
            rationale="stopped", event_ts="2026-04-18T15:00:00",
        ))
        assert result.realized_pnl == pytest.approx(-100.0)
        assert result.r_multiple == pytest.approx(-1.0)
    finally:
        conn.close()


def test_overfill_raises(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        with pytest.raises(ValueError, match="exceeds remaining"):
            record_exit(conn, ExitRequest(
                trade_id=tid, exit_date="2026-04-18", exit_price=185.0,
                shares=11, reason=ExitReason.MANUAL, notes=None,
                rationale="overfill", event_ts="2026-04-18T15:00:00",
            ))
    finally:
        conn.close()


def test_invalid_reason_raises(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        tid = _seed(conn)
        with pytest.raises(ValueError):
            record_exit(conn, ExitRequest(
                trade_id=tid, exit_date="2026-04-18", exit_price=185.0,
                shares=5, reason="invalid_reason",  # type: ignore[arg-type]
                notes=None, rationale="x", event_ts="2026-04-18T15:00:00",
            ))
    finally:
        conn.close()
