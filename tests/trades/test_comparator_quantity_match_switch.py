"""Tests for Sub-bundle 1 T-1.7 — comparator quantity-match switch
to execution-grain via `_resolve_match_quantity`.

Per plan §A.1.7 + spec §5.3 Codex R1 M#2. 4 discriminating tests.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)
from swing.trades.schwab_reconciliation import run_schwab_reconciliation


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _leg(*, leg_id=1, price=10.00, quantity=100.0,
         mismarked_quantity=0.0, instrument_id=None,
         time="2026-05-15T14:30:00.000Z"):
    return SchwabExecutionLeg(
        leg_id=leg_id, price=price, quantity=quantity,
        mismarked_quantity=mismarked_quantity, instrument_id=instrument_id,
        time=time,
    )


def _order(*, order_id="ORD-QM", status="FILLED",
           instrument_symbol="AAA", instruction="BUY",
           quantity=100.0, order_type="LIMIT", price=10.00,
           executions=None,
           enter_time="2026-04-27T14:23:00.000Z"):
    return SchwabOrderResponse(
        order_id=order_id, status=status,
        enter_time=enter_time, instrument_symbol=instrument_symbol,
        instruction=instruction, quantity=quantity,
        order_type=order_type, price=price,
        executions=executions,
    )


class _Account:
    def __init__(self, nlv=2000.0):
        self.net_liquidating_value = nlv
        self.positions: list = []


def _seed_entry_fill(
    conn: sqlite3.Connection, *,
    ticker: str, fill_price: float, qty: float,
) -> tuple[int, int]:
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, "2026-04-27", fill_price, int(qty), 4.0, 4.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", "entry", qty, fill_price,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return trade_id, fill_id


def _count_discrepancies(conn: sqlite3.Connection, run_id: int,
                          discrepancy_type: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND discrepancy_type = ?",
        (run_id, discrepancy_type),
    ).fetchone()[0]


# Test 1 — partial fill matches via legs sum NOT order.quantity.
def test_partial_fill_matches_via_legs_sum_not_order_quantity(conn) -> None:
    """Schwab order.quantity=200 (the OPEN order size) but executions sum=100
    (the FILLED quantity). Journal qty=100 → should MATCH via _resolve_match_quantity,
    NOT emit unmatched_open_fill."""
    _seed_entry_fill(conn, ticker="ABC", fill_price=10.00, qty=100.0)
    order = _order(
        instrument_symbol="ABC",
        quantity=200.0,  # OPEN order size
        price=10.00,
        executions=[_leg(price=10.00, quantity=100.0)],  # FILLED qty
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    # Match succeeded → NO unmatched + NO entry_price_mismatch (prices match).
    assert _count_discrepancies(conn, run.run_id, "unmatched_open_fill") == 0
    assert _count_discrepancies(conn, run.run_id, "entry_price_mismatch") == 0


# Test 2 — full fill match unchanged from V1 (executions sum == order.quantity).
def test_full_fill_match_unchanged_from_v1(conn) -> None:
    _seed_entry_fill(conn, ticker="DEF", fill_price=10.00, qty=100.0)
    order = _order(
        instrument_symbol="DEF",
        quantity=100.0,
        price=10.00,
        executions=[_leg(price=10.00, quantity=100.0)],
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    assert _count_discrepancies(conn, run.run_id, "unmatched_open_fill") == 0
    assert _count_discrepancies(conn, run.run_id, "entry_price_mismatch") == 0


# Test 3 — executions=None falls back to so.quantity (V1 behavior preserved).
def test_executions_none_falls_back_to_so_quantity(conn) -> None:
    """When executions=None, _resolve_match_quantity returns so.quantity (V1
    backward compat). Journal qty=100 + so.quantity=100 → match; Path B
    sentinel fires for missing execution data."""
    _seed_entry_fill(conn, ticker="GHI", fill_price=10.00, qty=100.0)
    order = _order(
        instrument_symbol="GHI",
        quantity=100.0,  # match journal
        price=10.00,
        executions=None,  # Path B
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    # Match succeeded on quantity → Path B sentinel fires (no execution data).
    assert _count_discrepancies(conn, run.run_id, "unmatched_open_fill") == 1
    # Verify the sentinel is Path B's (not V1's "no match" {"matched": null}).
    import json as _json
    row = conn.execute(
        "SELECT actual_value_json FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND discrepancy_type = 'unmatched_open_fill'",
        (run.run_id,),
    ).fetchone()
    actual = _json.loads(row[0])
    assert actual.get("execution_unavailable") is True


# Test 4 — partial fill with no match still emits unmatched_open_fill.
def test_partial_fill_with_no_quantity_match_still_emits_unmatched(conn) -> None:
    """Schwab order.quantity=200, executions sum=50; journal qty=100 → no
    match (legs sum=50 ≠ journal 100); emits unmatched_open_fill (no Path
    B path because never reached a matching iteration)."""
    _seed_entry_fill(conn, ticker="JKL", fill_price=10.00, qty=100.0)
    order = _order(
        instrument_symbol="JKL",
        quantity=200.0,
        price=10.00,
        executions=[_leg(price=10.00, quantity=50.0)],
    )
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-04-27", period_end="2026-04-27",
        schwab_orders=[order], schwab_transactions=[],
        schwab_account=_Account(),
    )
    # No match → unmatched_open_fill emitted via quantity-mismatch branch
    # (V1 no-match path, NOT Path B sentinel).
    assert _count_discrepancies(conn, run.run_id, "unmatched_open_fill") == 1
    import json as _json
    row = conn.execute(
        "SELECT actual_value_json FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND discrepancy_type = 'unmatched_open_fill'",
        (run.run_id,),
    ).fetchone()
    actual = _json.loads(row[0])
    # Quantity-mismatch path emits {"matched": null}; no Path B sentinel.
    assert actual.get("matched") is None
    assert actual.get("execution_unavailable") is None
