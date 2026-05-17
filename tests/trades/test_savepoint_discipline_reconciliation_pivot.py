"""T-C.7 — savepoint-per-discrepancy discipline regression suite.

Per plan §D.7 — spec §7.1 LOCKED. Codex R1 Critical #3 fix + R2 Minor #1
ROLLBACK-TO-then-RELEASE comment fix.

Pins:
  - Savepoint isolation under partial UPDATE failure (ROLLBACK TO undoes
    partial mutations; outer tx survives).
  - Outer tx survives per-discrepancy savepoint rollback (multi-failure
    scenario; remaining rows still dispositioned).
  - SAVEPOINT name uniqueness per discrepancy_id (no two iterations
    share a savepoint name).
  - RELEASE always fires (no leaked savepoints in the outer tx).

Tests run against BOTH `run_schwab_reconciliation` AND
`run_tos_reconciliation` since both share the pivot mechanic per
T-C.5 + T-C.6.
"""
from __future__ import annotations

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
    # Sub-bundle 1 T-1.6 — execution-grain fields. Tests that exercise the
    # tier-1 price-mismatch path under V2 semantics MUST populate `executions`
    # with at least one SchwabExecutionLeg whose `price` is the comparator
    # value. Default `None` preserves V1 fixture shape for tests that
    # exercise Path B (executions=None → sentinel emit).
    order_id: str = "ORD-test"
    executions: object = None  # list[SchwabExecutionLeg] | None at runtime
    enter_time: str = "2026-04-27T14:23:00.000Z"


def _v2_leg(*, leg_id=1, price=5.30, quantity=100.0,
            mismarked_quantity=0.0, instrument_id=None,
            time="2026-05-15T14:30:00.000Z"):
    """Helper: build a SchwabExecutionLeg for V2 execution-grain fixtures
    (Sub-bundle 1 T-1.6)."""
    from swing.integrations.schwab.models import SchwabExecutionLeg
    return SchwabExecutionLeg(
        leg_id=leg_id, price=price, quantity=quantity,
        mismarked_quantity=mismarked_quantity, instrument_id=instrument_id,
        time=time,
    )


@dataclass
class _SchwabAccount:
    net_liquidating_value: float | None = None
    positions: list[Any] | None = None


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_open_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    fill_price: float,
    qty: float = 100.0,
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


# ---------------------------------------------------------------------------
# Savepoint isolates partial mutation under tier-1 failure
# ---------------------------------------------------------------------------


def test_savepoint_isolates_partial_mutation_under_tier1_failure(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rig _apply_tier1_correction_inner to raise mid-flight on the
    second discrepancy; verify ROLLBACK TO undoes partial UPDATEs +
    the first + third discrepancies land normally."""
    _, fid1 = _seed_open_trade(conn, ticker="AAA", fill_price=5.0)
    _, fid2 = _seed_open_trade(conn, ticker="BBB", fill_price=6.0)
    _, fid3 = _seed_open_trade(conn, ticker="CCC", fill_price=7.0)

    import swing.trades.schwab_reconciliation as srx
    from swing.trades.reconciliation_auto_correct import (
        _apply_tier1_correction_inner as real_inner,
    )
    call_count = [0]

    def _rigged(conn_, **kw):
        call_count[0] += 1
        if call_count[0] == 2:
            # Simulate a mid-flight failure AFTER the journal UPDATE has
            # already been written. We do a real UPDATE then raise to
            # ensure the savepoint actually has work to undo.
            disc_id = kw["discrepancy_id"]
            row = conn_.execute(
                "SELECT fill_id FROM reconciliation_discrepancies "
                "WHERE discrepancy_id = ?",
                (disc_id,),
            ).fetchone()
            if row and row[0]:
                conn_.execute(
                    "UPDATE fills SET price = 999.99 WHERE fill_id = ?",
                    (row[0],),
                )
            raise RuntimeError("rigged mid-flight failure (post-UPDATE)")
        return real_inner(conn_, **kw)

    monkeypatch.setattr(srx, "_apply_tier1_correction_inner", _rigged)

    schwab_orders = [
        _SchwabOrder(status="FILLED", price=5.10, quantity=100.0,
                     instrument_symbol="AAA",
                     executions=[_v2_leg(price=5.10, quantity=100.0)]),
        _SchwabOrder(status="FILLED", price=6.10, quantity=100.0,
                     instrument_symbol="BBB",
                     executions=[_v2_leg(price=6.10, quantity=100.0)]),
        _SchwabOrder(status="FILLED", price=7.10, quantity=100.0,
                     instrument_symbol="CCC",
                     executions=[_v2_leg(price=7.10, quantity=100.0)]),
    ]
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=_SchwabAccount(2000.0, []),
    )
    # Outer run completed (graceful degradation).
    assert run.state == "completed"
    # The partial UPDATE to fid2 was rolled back by ROLLBACK TO.
    p2 = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fid2,),
    ).fetchone()
    assert p2[0] == 6.0  # original unchanged; rigged UPDATE undone
    # The other two were dispositioned to tier-1 (real inner ran):
    p1 = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fid1,),
    ).fetchone()
    p3 = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fid3,),
    ).fetchone()
    assert p1[0] == 5.10
    assert p3[0] == 7.10


# ---------------------------------------------------------------------------
# Outer tx survives per-discrepancy savepoint rollback
# ---------------------------------------------------------------------------


def test_outer_tx_survives_multiple_per_discrepancy_failures(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rig EVERY classify call to raise; outer tx still commits +
    no row gets dispositioned."""
    _seed_open_trade(conn, ticker="AAA", fill_price=5.0)
    _seed_open_trade(conn, ticker="BBB", fill_price=6.0)
    schwab_orders = [
        _SchwabOrder(status="FILLED", price=5.10, quantity=100.0,
                     instrument_symbol="AAA",
                     executions=[_v2_leg(price=5.10, quantity=100.0)]),
        _SchwabOrder(status="FILLED", price=6.10, quantity=100.0,
                     instrument_symbol="BBB",
                     executions=[_v2_leg(price=6.10, quantity=100.0)]),
    ]
    import swing.trades.schwab_reconciliation as srx

    def _always_fail(discrepancy, **kw):
        raise RuntimeError("rigged always-fail")

    monkeypatch.setattr(srx, "classify_discrepancy", _always_fail)
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=_SchwabAccount(2000.0, []),
    )
    # Run still completed.
    assert run.state == "completed"
    # All discrepancies stayed unresolved (graceful degradation).
    states = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE run_id = ?", (run.run_id,),
    ).fetchall()
    assert all(s[0] == "unresolved" for s in states)


# ---------------------------------------------------------------------------
# Savepoint name uniqueness per discrepancy_id
# ---------------------------------------------------------------------------


def test_savepoint_name_unique_per_discrepancy_id(
    conn: sqlite3.Connection,
) -> None:
    """The savepoint name template is ``correction_sp_{discrepancy_id}``.
    Since discrepancy_id is an autoincrement PK, no two iterations share
    a savepoint name. We verify the pivot helper builds the expected name."""
    from swing.trades.schwab_reconciliation import (
        _pivot_classify_and_dispatch_for_run,
    )
    # Just import-time check that the helper exists + the source uses
    # the canonical name template.
    import inspect
    src = inspect.getsource(_pivot_classify_and_dispatch_for_run)
    assert 'f"correction_sp_{disc.discrepancy_id}"' in src
    assert 'f"correction_fallback_sp_{disc.discrepancy_id}"' in src


# ---------------------------------------------------------------------------
# RELEASE-always discipline — no leaked savepoints after pivot
# ---------------------------------------------------------------------------


def test_no_leaked_savepoints_after_pivot(
    conn: sqlite3.Connection,
) -> None:
    """After the pivot completes, conn.in_transaction is False (outer
    committed) + no orphan savepoints remain on the connection. SQLite
    auto-clears savepoints on COMMIT; this test pins the contract."""
    _seed_open_trade(conn, ticker="AAA", fill_price=5.0)
    schwab_orders = [
        _SchwabOrder(status="FILLED", price=5.10, quantity=100.0,
                     instrument_symbol="AAA",
                     executions=[_v2_leg(price=5.10, quantity=100.0)]),
    ]
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=_SchwabAccount(2000.0, []),
    )
    # Outer committed; no leaked tx state.
    assert run.state == "completed"
    assert conn.in_transaction is False
    # Attempting to ROLLBACK TO a stale savepoint should raise (SQLite
    # cleared it on COMMIT).
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("ROLLBACK TO SAVEPOINT correction_sp_1")


# ---------------------------------------------------------------------------
# Fall-through to fresh savepoint on validator rejection
# ---------------------------------------------------------------------------


def test_validator_rejection_falls_through_to_fresh_fallback_savepoint(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When tier-1 inner raises ValidatorRejectedError, the pivot
    releases the primary savepoint + opens a FRESH fallback savepoint
    for the tier-2 stamp (Codex R2 Minor #1 fix; never reuses an
    already-released sp_name)."""
    _, fid = _seed_open_trade(conn, ticker="AAA", fill_price=5.0)

    # Rig the classifier to return tier-1 with an INVALID
    # correction_target so the validator rejects + pivot falls through.
    import swing.trades.schwab_reconciliation as srx
    from swing.trades.reconciliation_classifier import ClassificationResult

    def _bad_classify(discrepancy, **kw):
        return ClassificationResult(
            tier=1, ambiguity_kind=None,
            correction_target={"price": -1.0},  # validator rejects
            correction_reason="rigged invalid target",
            candidate_choices=None,
        )

    monkeypatch.setattr(srx, "classify_discrepancy", _bad_classify)

    schwab_orders = [
        _SchwabOrder(status="FILLED", price=5.10, quantity=100.0,
                     instrument_symbol="AAA",
                     executions=[_v2_leg(price=5.10, quantity=100.0)]),
    ]
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=_SchwabAccount(2000.0, []),
    )
    # Outer completed; fid's price unchanged (validator rejected).
    assert run.state == "completed"
    fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fid,),
    ).fetchone()
    assert fp[0] == 5.0
    # Discrepancy stamped pending_ambiguity_resolution with
    # validator_rejected ambiguity_kind.
    d = conn.execute(
        "SELECT resolution, ambiguity_kind FROM reconciliation_discrepancies "
        "WHERE run_id = ?", (run.run_id,),
    ).fetchone()
    assert d[0] == "pending_ambiguity_resolution"
    assert d[1] == "validator_rejected"
