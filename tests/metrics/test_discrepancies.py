"""Phase 10 Sub-bundle A T-A.7.1 — discrepancies helper tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.reconciliation import insert_discrepancy, insert_run
from swing.metrics.discrepancies import count_unresolved_material


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase10_discrepancies.db")


def _seed_trade(
    conn: sqlite3.Connection, *, trade_id: int, state: str,
    ticker: str | None = None,
) -> None:
    # `trades.ticker` has a UNIQUE constraint at the partial-index level
    # for open trades; tests use distinct tickers per row.
    ticker = ticker or f"TST{trade_id}"
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label) VALUES (?, ?, '2026-05-12', 10.0, 100, "
        "9.0, 9.0, ?, 'S', 'I', 'manual_off_pipeline', "
        "'2026-05-12T09:00:00.000', 100, 'A+ baseline')",
        (trade_id, ticker, state),
    )
    conn.commit()


def _new_run(conn: sqlite3.Connection) -> int:
    run_id = insert_run(
        conn,
        source="manual",
        started_ts="2026-05-12T09:00:00.000",
        state="completed",
        finished_ts="2026-05-12T09:00:01.000",
    )
    conn.commit()
    return run_id


def _emit(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    trade_id: int | None,
    material: int = 1,
    resolution: str = "unresolved",
    discrepancy_type: str = "stop_mismatch",
) -> int:
    did = insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type=discrepancy_type,
        field_name="current_stop",
        material_to_review=material,
        created_at="2026-05-12T09:00:00.000",
        trade_id=trade_id,
        ticker="TST",
        resolution=resolution,
    )
    conn.commit()
    return did


def test_count_unresolved_material_zero_when_no_discrepancies(
    conn: sqlite3.Connection,
):
    assert count_unresolved_material(conn) == 0


def test_count_unresolved_material_returns_sum_of_active_plus_closed(
    conn: sqlite3.Connection,
):
    """2 unresolved-material on active trades + 1 on closed → 3."""
    _seed_trade(conn, trade_id=1, state="entered")
    _seed_trade(conn, trade_id=2, state="managing")
    _seed_trade(conn, trade_id=3, state="closed")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1)
    _emit(conn, run_id=run_id, trade_id=2)
    _emit(conn, run_id=run_id, trade_id=3)
    assert count_unresolved_material(conn) == 3


def test_count_unresolved_material_excludes_resolved(conn: sqlite3.Connection):
    """`resolution='acknowledged_immaterial'` → NOT counted."""
    _seed_trade(conn, trade_id=1, state="entered")
    _seed_trade(conn, trade_id=2, state="entered")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1, resolution="unresolved")
    _emit(conn, run_id=run_id, trade_id=2, resolution="acknowledged_immaterial")
    assert count_unresolved_material(conn) == 1


def test_count_unresolved_material_excludes_immaterial(conn: sqlite3.Connection):
    """`material_to_review=0` → NOT counted."""
    _seed_trade(conn, trade_id=1, state="entered")
    _seed_trade(conn, trade_id=2, state="entered")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1, material=1)
    _emit(conn, run_id=run_id, trade_id=2, material=0)
    assert count_unresolved_material(conn) == 1


def test_count_unresolved_material_excludes_orphan_emit_no_trade(
    conn: sqlite3.Connection,
):
    """V1 LIMITATION (banked V2 candidate at return report §7): discrepancies
    with NULL trade_id (sector_tamper / equity_delta / cash_movement orphans)
    are EXCLUDED from this count because the underlying repo helpers JOIN
    on trade row.

    Discriminating test: emit an orphan-attributed discrepancy + assert it
    is NOT counted. If the helper is later widened to include orphans, this
    test will need to be updated.
    """
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1)
    _emit(conn, run_id=run_id, trade_id=None,
          discrepancy_type="equity_delta", material=1)
    assert count_unresolved_material(conn) == 1


def test_count_unresolved_material_read_only_no_transaction(
    conn: sqlite3.Connection,
):
    """Helper does NOT open its own transaction (read-only contract per
    plan §A.7.1 watch item)."""
    _seed_trade(conn, trade_id=1, state="entered")
    run_id = _new_run(conn)
    _emit(conn, run_id=run_id, trade_id=1)
    # Caller-side transaction stays untouched.
    assert conn.in_transaction is False
    _ = count_unresolved_material(conn)
    assert conn.in_transaction is False
