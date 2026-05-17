"""T-C.5 — `run_schwab_reconciliation` flow-pivot tests.

Per plan §D.5 — spec §7.1 LOCKED savepoint-per-discrepancy discipline.

Mock-driven (no live Schwab API). We construct synthetic
`SchwabOrderResponse`-like objects + a journal trade with an entry fill
+ exercise the pivot end-to-end. The pivot loop classifies emitted
discrepancies + dispatches tier-1 or tier-2 stamp per the
ClassificationResult.
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


# ---------------------------------------------------------------------------
# Synthetic Schwab response fixtures — minimal duck-typed shape that
# satisfies the schwab_reconciliation.py consumer (which reads
# `.status`, `.price`, `.quantity`, `.instrument_symbol`).
# ---------------------------------------------------------------------------


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
    # value (V1 tests used `price` field; V2 reads leg price via
    # `_compute_execution_price`). The default-`None` preserves V1 fixture
    # shape for tests that exercise Path B (executions=None → sentinel emit).
    order_id: str = "ORD-test"
    executions: object = None  # list[SchwabExecutionLeg] | None at runtime
    enter_time: str = "2026-04-27T14:23:00.000Z"


def _v2_leg(*, leg_id=1, price=5.30, quantity=100.0,
            mismarked_quantity=0.0, instrument_id=None,
            time="2026-05-15T14:30:00.000Z"):
    """Helper: build a SchwabExecutionLeg for V2 execution-grain fixtures.

    Sub-bundle 1 T-1.6 architectural shift — comparator reads leg.price
    not order.price. Existing V1 tests that asserted tier-1 entry_price_mismatch
    behavior with `_SchwabOrder(price=5.30)` MUST also supply
    `executions=[_v2_leg(price=5.30)]` to exercise the same tier-1 path
    under V2 Shape C semantics.
    """
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
# Tier-1 auto-correct inside the same run
# ---------------------------------------------------------------------------


def test_run_schwab_reconciliation_applies_tier1_inline(
    conn: sqlite3.Connection,
) -> None:
    """CVGI-shape entry_price_mismatch → tier-1 auto-correct under the same
    reconciliation run."""
    trade_id, fill_id = _seed_open_trade(
        conn, ticker="CVGI", fill_price=5.23,
    )
    schwab_orders = [
        _SchwabOrder(
            status="FILLED", price=5.30, quantity=100.0,
            instrument_symbol="CVGI",
            executions=[_v2_leg(price=5.30, quantity=100.0)],
        ),
    ]
    schwab_account = _SchwabAccount(net_liquidating_value=2000.0, positions=[])
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    # Discrepancy emitted AND auto-corrected in the same run.
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND discrepancy_type = 'entry_price_mismatch'",
        (run.run_id,),
    ).fetchone()
    assert d is not None
    assert d[0] == "auto_corrected_from_schwab"
    # fills.price updated.
    fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fill_id,),
    ).fetchone()
    assert fp[0] == 5.30
    # summary_json carries tier1_applied_count.
    summary = json.loads(run.summary_json)
    assert summary.get("tier1_applied_count", 0) == 1
    # Outer run state: completed.
    assert run.state == "completed"


# ---------------------------------------------------------------------------
# Sandbox short-circuit
# ---------------------------------------------------------------------------


def test_run_schwab_reconciliation_sandbox_short_circuits(
    conn: sqlite3.Connection,
) -> None:
    trade_id, fill_id = _seed_open_trade(
        conn, ticker="CVGI", fill_price=5.23,
    )
    schwab_orders = [
        _SchwabOrder(
            status="FILLED", price=5.30, quantity=100.0,
            instrument_symbol="CVGI",
            executions=[_v2_leg(price=5.30, quantity=100.0)],
        ),
    ]
    schwab_account = _SchwabAccount(net_liquidating_value=2000.0, positions=[])
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=schwab_account,
        environment="sandbox",
    )
    # Discrepancy emitted but NOT auto-corrected.
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND discrepancy_type = 'entry_price_mismatch'",
        (run.run_id,),
    ).fetchone()
    assert d[0] == "unresolved"
    fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fill_id,),
    ).fetchone()
    assert fp[0] == 5.23  # unchanged
    summary = json.loads(run.summary_json)
    assert summary.get("tier1_applied_count", 0) == 0


# ---------------------------------------------------------------------------
# Tier-2 path — no Schwab match → schwab_returned_no_match → tier-2 stamp
# ---------------------------------------------------------------------------


def test_run_schwab_reconciliation_tier2_stamps_for_unmatched_open_fill(
    conn: sqlite3.Connection,
) -> None:
    """When Schwab returns NO matching record, the journal fill emits
    unmatched_open_fill; classifier emits tier-2 with
    `schwab_returned_no_match` (Pass-2-tier-1-FORBIDDEN LOCK from C.B).
    """
    trade_id, fill_id = _seed_open_trade(
        conn, ticker="ABC", fill_price=10.0,
    )
    # No Schwab orders → all journal fills unmatched.
    schwab_account = _SchwabAccount(net_liquidating_value=2000.0, positions=[])
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    d = conn.execute(
        "SELECT resolution, ambiguity_kind FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND discrepancy_type = 'unmatched_open_fill'",
        (run.run_id,),
    ).fetchone()
    assert d is not None
    assert d[0] == "pending_ambiguity_resolution"
    # ambiguity_kind set per classifier (LOCK: unmatched_open_fill never
    # tier-1; the kind enum depends on classifier output — schwab_returned_no_match
    # is the spec §8.4 default).
    assert d[1] is not None
    summary = json.loads(run.summary_json)
    assert summary.get("tier2_pending_count", 0) >= 1
    assert summary.get("tier1_applied_count", 0) == 0


# ---------------------------------------------------------------------------
# Savepoint isolates per-discrepancy failure
# ---------------------------------------------------------------------------


def test_run_schwab_reconciliation_savepoint_isolates_failure(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rig the 2nd classify call to raise; verify the OTHER discrepancies
    are still dispositioned + the outer run lands as 'completed'."""
    _seed_open_trade(conn, ticker="AAA", fill_price=5.0)
    _seed_open_trade(conn, ticker="BBB", fill_price=6.0)
    _seed_open_trade(conn, ticker="CCC", fill_price=7.0)
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
    schwab_account = _SchwabAccount(net_liquidating_value=2000.0, positions=[])

    # Patch classify_discrepancy to fail on the 2nd call only.
    import swing.trades.schwab_reconciliation as srx
    from swing.trades.reconciliation_classifier import (
        classify_discrepancy as real_classify,
    )
    call_count = [0]

    def _rigged(discrepancy, **kw):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("rigged 2nd-discrepancy failure")
        return real_classify(discrepancy, **kw)

    monkeypatch.setattr(srx, "classify_discrepancy", _rigged)

    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    # Outer run completed (graceful degradation).
    assert run.state == "completed"
    # 3 entry_price_mismatch discrepancies emitted; 2 dispositioned to
    # tier-1, 1 (the rigged failure) stayed unresolved.
    states = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND discrepancy_type = 'entry_price_mismatch' "
        "ORDER BY discrepancy_id ASC",
        (run.run_id,),
    ).fetchall()
    assert len(states) == 3
    n_unresolved = sum(1 for s in states if s[0] == "unresolved")
    n_disp = sum(1 for s in states if s[0] != "unresolved")
    assert n_unresolved == 1
    assert n_disp == 2


# ---------------------------------------------------------------------------
# Codex R1 Major #3 — unresolved_discrepancies_count stays in sync after pivot
# ---------------------------------------------------------------------------


def test_run_schwab_reconciliation_unresolved_counter_decrements_post_pivot(
    conn: sqlite3.Connection,
) -> None:
    """The unresolved_discrepancies_count column on the parent
    reconciliation_run row MUST reflect the post-pivot state — _emit
    increments at INSERT time, but the pivot loop flips rows OFF
    'unresolved' (tier-1 → auto_corrected_from_schwab; tier-2 →
    pending_ambiguity_resolution). Without a post-pivot recompute the
    counter stays stale.

    Plant 1 CVGI tier-1 + 2 unmatched-open-fill tier-2 → expect
    unresolved_discrepancies_count == 0 (all rows moved off
    'unresolved') and discrepancies_count == 3.
    """
    # 1 CVGI tier-1 candidate (entry_price_mismatch with Schwab match)
    _seed_open_trade(conn, ticker="CVGI", fill_price=5.23)
    # 2 unmatched journal fills (tier-2 — no Schwab side match)
    _seed_open_trade(conn, ticker="AAA", fill_price=10.0)
    _seed_open_trade(conn, ticker="BBB", fill_price=20.0)

    schwab_orders = [
        _SchwabOrder(
            status="FILLED", price=5.30, quantity=100.0,
            instrument_symbol="CVGI",
            executions=[_v2_leg(price=5.30, quantity=100.0)],
        ),
    ]
    schwab_account = _SchwabAccount(net_liquidating_value=2000.0, positions=[])

    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=schwab_account,
    )

    # Sanity check: all 3 dispositioned off 'unresolved' state.
    rows = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE run_id = ?",
        (run.run_id,),
    ).fetchall()
    resolutions = sorted(r[0] for r in rows)
    n_unresolved = sum(1 for r in resolutions if r == "unresolved")
    assert n_unresolved == 0, (
        f"all discrepancies should be off 'unresolved' post-pivot; "
        f"got resolutions={resolutions}"
    )
    # Discriminating signal: parent run's unresolved counter recomputed.
    assert run.unresolved_discrepancies_count == 0, (
        f"unresolved_discrepancies_count must be recomputed post-pivot; "
        f"got {run.unresolved_discrepancies_count}, "
        f"resolutions={resolutions}"
    )
    # discrepancies_count remains 3 (emit count, not lifecycle).
    assert run.discrepancies_count == 3
