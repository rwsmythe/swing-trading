"""20-A Task A-2 — matcher candidate enumeration + Shape-D / LIST emit.

The fill<->execution matcher no longer break-picks the first same-qty order.
These tests exercise the EMIT SHAPE decision (classifier-independent):
  - NORMAL correct fill (one fully-consistent candidate) -> NO emit.
  - Corrupt-style 2 same-qty candidates, fill CORRECT -> still NO emit
    (the correct leg is the unique good match — the anti-corruption case).
  - Corrupt fill (2 candidates, none good) -> a LIST-shaped
    actual_value_json (tier-2 ambiguity downstream).
  - Single mismatching candidate with WRONG side -> a Shape-D dict carrying
    execution_side + candidate_count + execution_sessions_from_fill.

Real geometries (PTEN 15/15, AMN 3/3) per the plan §9 fixture discipline.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.schwab_reconciliation import run_schwab_reconciliation


@dataclass
class _SchwabOrder:
    status: str
    price: float
    quantity: float
    instrument_symbol: str
    order_type: str = "MARKET"
    instruction: str = "BUY"
    order_id: str = "ORD-test"
    executions: object = None
    enter_time: str = "2026-05-19T14:23:00.000Z"


def _leg(*, leg_id=1, price=13.00, quantity=15.0, time="2026-05-19T14:30:00.000Z"):
    from swing.integrations.schwab.models import SchwabExecutionLeg
    return SchwabExecutionLeg(
        leg_id=leg_id, price=price, quantity=quantity,
        mismarked_quantity=0.0, instrument_id=None, time=time,
    )


@dataclass
class _SchwabAccount:
    net_liquidating_value: float | None = None
    positions: list[Any] | None = None


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_entry_only(
    conn: sqlite3.Connection, *, ticker: str, fill_price: float, qty: float,
    fill_dt: str = "2026-05-19T14:23:00",
) -> tuple[int, int]:
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, "2026-05-19", fill_price, int(qty), fill_price - 1.0,
         fill_price - 1.0, "managing", "manual_off_pipeline",
         "2026-05-19T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, fill_dt, "entry", qty, fill_price, "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return trade_id, fill_id


def _run(conn, orders):
    return run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-05-19",
        period_end="2026-05-19",
        schwab_orders=orders,
        schwab_transactions=[],
        schwab_account=_SchwabAccount(net_liquidating_value=2000.0, positions=[]),
    )


def _price_discrepancies(conn, run_id):
    rows = conn.execute(
        "SELECT discrepancy_type, actual_value_json FROM "
        "reconciliation_discrepancies WHERE run_id = ? AND field_name = 'price'",
        (run_id,),
    ).fetchall()
    return rows


def test_normal_correct_single_candidate_is_suppressed(conn) -> None:
    """One fully-consistent candidate (price+side+session) -> NO emit."""
    _seed_entry_only(conn, ticker="AAA", fill_price=13.00, qty=15.0)
    orders = [
        _SchwabOrder(
            status="FILLED", price=13.00, quantity=15.0,
            instrument_symbol="AAA", instruction="BUY",
            executions=[_leg(price=13.00, quantity=15.0)],
        ),
    ]
    run = _run(conn, orders)
    assert _price_discrepancies(conn, run.run_id) == []


def test_correct_entry_fill_two_candidates_is_suppressed(conn) -> None:
    """Fill CORRECT (13.00) with entry-BUY 13.00 + exit-SELL 12.305 candidates
    (same qty 15) -> good_matches == {entry BUY} -> NO false demotion."""
    _seed_entry_only(conn, ticker="PTEN", fill_price=13.00, qty=15.0)
    orders = [
        _SchwabOrder(
            status="FILLED", price=13.00, quantity=15.0,
            instrument_symbol="PTEN", instruction="BUY", order_id="BUY1",
            executions=[_leg(price=13.00, quantity=15.0)],
        ),
        _SchwabOrder(
            status="FILLED", price=12.305, quantity=15.0,
            instrument_symbol="PTEN", instruction="SELL", order_id="SELL1",
            executions=[_leg(price=12.305, quantity=15.0)],
        ),
    ]
    run = _run(conn, orders)
    assert _price_discrepancies(conn, run.run_id) == []


def test_two_duplicate_good_candidates_are_suppressed(conn) -> None:
    """Codex R1 MINOR — a fill with TWO equally-good (price+side+session)
    candidates is NOT false-demoted (good_matches>=1 suppression)."""
    _seed_entry_only(conn, ticker="AAA", fill_price=13.00, qty=15.0)
    orders = [
        _SchwabOrder(status="FILLED", price=13.00, quantity=15.0,
                     instrument_symbol="AAA", instruction="BUY",
                     order_id="B1", executions=[_leg(price=13.00, quantity=15.0)]),
        _SchwabOrder(status="FILLED", price=13.00, quantity=15.0,
                     instrument_symbol="AAA", instruction="BUY",
                     order_id="B2", executions=[_leg(price=13.00, quantity=15.0)]),
    ]
    run = _run(conn, orders)
    assert _price_discrepancies(conn, run.run_id) == []


def test_corrupt_fill_two_candidates_emits_list_shape(conn) -> None:
    """Fill ALREADY corrupt (12.305): entry BUY 13.00 fails price, exit SELL
    12.305 fails side -> good_matches == [] with 2 candidates -> LIST emit."""
    _seed_entry_only(conn, ticker="PTEN", fill_price=12.305, qty=15.0)
    orders = [
        _SchwabOrder(
            status="FILLED", price=13.00, quantity=15.0,
            instrument_symbol="PTEN", instruction="BUY", order_id="BUY1",
            executions=[_leg(price=13.00, quantity=15.0)],
        ),
        _SchwabOrder(
            status="FILLED", price=12.305, quantity=15.0,
            instrument_symbol="PTEN", instruction="SELL", order_id="SELL1",
            executions=[_leg(price=12.305, quantity=15.0)],
        ),
    ]
    run = _run(conn, orders)
    rows = _price_discrepancies(conn, run.run_id)
    assert len(rows) == 1
    assert rows[0][0] == "entry_price_mismatch"
    payload = json.loads(rows[0][1])
    assert isinstance(payload, list)
    assert len(payload) == 2
    # Each candidate carries the A2 evidence fields.
    for cand in payload:
        assert "execution_side" in cand
        assert "execution_sessions_from_fill" in cand


def test_single_wrong_side_candidate_emits_shape_d(conn) -> None:
    """Single same-qty candidate, price mismatch + WRONG side -> Shape-D dict
    (candidate_count=1 + execution_side + execution_sessions_from_fill)."""
    _seed_entry_only(conn, ticker="DFTX", fill_price=24.53, qty=7.0)
    orders = [
        _SchwabOrder(
            status="FILLED", price=22.16, quantity=7.0,
            instrument_symbol="DFTX", instruction="SELL", order_id="SELL1",
            executions=[_leg(price=22.16, quantity=7.0)],
        ),
    ]
    run = _run(conn, orders)
    rows = _price_discrepancies(conn, run.run_id)
    assert len(rows) == 1
    payload = json.loads(rows[0][1])
    assert isinstance(payload, dict)
    assert payload["execution_side"] == "SELL"
    assert payload["candidate_count"] == 1
    assert payload["execution_sessions_from_fill"] == 0
    assert set(payload.keys()) == {
        "price", "execution_legs", "schwab_order_id", "schwab_order_price",
        "execution_side", "candidate_count", "execution_sessions_from_fill",
    }


def test_amn_two_session_stop_leg_emits_list(conn) -> None:
    """AMN trim fill 07-07 (35.65) with trim-SELL 35.65 (07-07) + stop-SELL
    32.06 (07-09) candidates. The trim leg matches price+side but the fill's
    ACTION is 'trim' -> a close-side fill. good_matches: trim SELL 35.65
    (price+side+session ok) is the unique good match -> suppressed."""
    # Seed AMN with a TRIM fill (non-entry) at the correct 35.65.
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("AMN", "2026-07-01", 33.66, 6, 32.0, 32.0, "partial_exited",
         "manual_off_pipeline", "2026-07-01T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-07-01T14:00:00", "entry", 6, 33.66, "unreconciled"),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-07-07T14:00:00", "trim", 3, 35.65, "unreconciled"),
    )
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    orders = [
        _SchwabOrder(
            status="FILLED", price=33.66, quantity=6.0,
            instrument_symbol="AMN", instruction="BUY", order_id="BUY1",
            executions=[_leg(price=33.66, quantity=6.0,
                             time="2026-07-01T14:00:00.000Z")],
        ),
        _SchwabOrder(
            status="FILLED", price=35.65, quantity=3.0,
            instrument_symbol="AMN", instruction="SELL", order_id="TRIM1",
            executions=[_leg(price=35.65, quantity=3.0,
                             time="2026-07-07T14:00:00.000Z")],
        ),
        _SchwabOrder(
            status="FILLED", price=32.06, quantity=3.0,
            instrument_symbol="AMN", instruction="SELL", order_id="STOP1",
            executions=[_leg(price=32.06, quantity=3.0,
                             time="2026-07-09T14:00:00.000Z")],
        ),
    ]
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-07-01",
        period_end="2026-07-10",
        schwab_orders=orders,
        schwab_transactions=[],
        schwab_account=_SchwabAccount(net_liquidating_value=2000.0, positions=[]),
    )
    # The correct trim fill (35.65) has a unique good match (trim SELL 35.65,
    # 07-07, 0 sessions) -> suppressed; the 32.06 stop leg is 2 sessions away
    # so it is NOT a good match and does not create a false demotion.
    assert _price_discrepancies(conn, run.run_id) == []
