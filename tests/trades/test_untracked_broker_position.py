"""Phase 18 Arc 18-H.6 — untracked_broker_position Schwab-driven orphan pass.

A broker holding with NO matching journal open_trade -> a first-class
`untracked_broker_position` discrepancy carrying qty + market value. REPLACES
the old journal-flat-only `orphan_broker_position` cash-warning.

Distinguishing posture (feedback_regression_test_arithmetic): pre-fix the
Schwab reconciliation is journal-driven only (it never loops schwab_positions),
so an orphan produced ZERO discrepancy — silent. Post-fix it produces exactly
one `untracked_broker_position` discrepancy. The orphan-with-open-trades case
was TOTALLY silent pre-fix (the warning fired only when journal_flat).
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
class _SchwabAccount:
    net_liquidating_value: float | None = None
    positions: list[Any] | None = None


def _position(symbol: str, *, long_qty: float = 0.0, short_qty: float = 0.0,
              market_value: float | None = None) -> dict:
    """Real Schwab position dict shape (account-specification.md L158-L184):
    marketValue is a top-level numeric sibling of `instrument`."""
    return {
        "shortQuantity": short_qty,
        "longQuantity": long_qty,
        "instrument": {"symbol": symbol, "type": "EQUITY"},
        "marketValue": market_value,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_open_trade(
    conn: sqlite3.Connection, *, ticker: str, qty: float = 100.0,
    fill_price: float = 5.0,
) -> int:
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
    conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", "entry", qty, fill_price,
         "unreconciled"),
    )
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return trade_id


def _orphans(conn: sqlite3.Connection, run_id: int) -> list[tuple]:
    return conn.execute(
        "SELECT ticker, expected_value_json, actual_value_json, delta_text, "
        "material_to_review, trade_id, field_name FROM "
        "reconciliation_discrepancies WHERE run_id=? AND "
        "discrepancy_type='untracked_broker_position'",
        (run_id,),
    ).fetchall()


def test_orphan_with_no_journal_trade_emits_discrepancy(conn):
    # journal flat; broker holds 2 IPO shares (the live instance).
    acct = _SchwabAccount(
        net_liquidating_value=2000.0,
        positions=[_position("IPOX", long_qty=2.0, market_value=51.40)],
    )
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-06-15",
        period_end="2026-06-15",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=acct,
    )
    rows = _orphans(conn, run.run_id)
    assert len(rows) == 1
    ticker, exp_j, act_j, delta, material, trade_id, field_name = rows[0]
    assert ticker == "IPOX"
    assert trade_id is None
    assert field_name == "broker_position"
    assert json.loads(exp_j) == {"journal_qty": 0}
    assert json.loads(act_j) == {"qty": 2.0, "market_value": 51.40}
    assert material == 1  # C5
    assert "IPOX" in delta and "not in journal" in delta


def test_orphan_alongside_open_journal_trades_still_fires(conn):
    # THE BUG CASE: an open journal trade exists, so the old warning (gated on
    # journal_flat) was TOTALLY silent. The new pass fires regardless.
    _seed_open_trade(conn, ticker="CVGI")
    acct = _SchwabAccount(
        net_liquidating_value=3000.0,
        positions=[
            _position("CVGI", long_qty=100.0, market_value=500.0),  # tracked
            _position("IPOX", long_qty=2.0, market_value=51.40),    # orphan
        ],
    )
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-06-15",
        period_end="2026-06-15",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=acct,
    )
    rows = _orphans(conn, run.run_id)
    assert len(rows) == 1
    assert rows[0][0] == "IPOX"


def test_matched_position_does_not_orphan(conn):
    # A position with a matching journal open_trade is NOT an orphan (only the
    # existing position_qty check applies — here qty matches so no discrepancy).
    _seed_open_trade(conn, ticker="CVGI", qty=100.0)
    acct = _SchwabAccount(
        net_liquidating_value=2000.0,
        positions=[_position("CVGI", long_qty=100.0, market_value=500.0)],
    )
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-06-15",
        period_end="2026-06-15",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=acct,
    )
    assert _orphans(conn, run.run_id) == []


def test_orphan_market_value_unavailable_carries_qty(conn):
    acct = _SchwabAccount(
        net_liquidating_value=2000.0,
        positions=[_position("IPOX", long_qty=2.0, market_value=None)],
    )
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-06-15",
        period_end="2026-06-15",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=acct,
    )
    rows = _orphans(conn, run.run_id)
    assert len(rows) == 1
    assert json.loads(rows[0][2]) == {"qty": 2.0, "market_value": None}
    assert "MV unknown" in rows[0][3]


def test_warning_replaced_no_orphan_broker_position_warning(conn):
    # Refinement 2: the old `orphan_broker_position` cash-warning no longer
    # appends; the discrepancy fires in its place (journal-flat case).
    acct = _SchwabAccount(
        net_liquidating_value=2000.0,
        positions=[_position("IPOX", long_qty=2.0, market_value=51.40)],
    )
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-06-15",
        period_end="2026-06-15",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=acct,
    )
    summary = json.loads(run.summary_json)
    warnings = summary.get("cash_warnings", [])
    reasons = {w.get("reason") for w in warnings if isinstance(w, dict)}
    assert "orphan_broker_position" not in reasons
    # the discrepancy fires instead
    assert len(_orphans(conn, run.run_id)) == 1


def test_no_equity_delta_emitted_when_broker_has_orphan_position(conn):
    # The both-flat equity_delta suppression is preserved structurally: a
    # broker-position case (journal flat, broker NOT flat) must NOT emit a
    # mis-attributable equity_delta even with a large NLV gap.
    acct = _SchwabAccount(
        net_liquidating_value=99999.0,
        positions=[_position("IPOX", long_qty=2.0, market_value=51.40)],
    )
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-06-15",
        period_end="2026-06-15",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=acct,
    )
    eq = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies WHERE run_id=? "
        "AND discrepancy_type='equity_delta'",
        (run.run_id,),
    ).fetchone()[0]
    assert eq == 0


def test_orphan_pass_runs_under_sandbox_emit_unchanged(conn):
    # Mirror every other `_emit`: under environment='sandbox' the discrepancy
    # ROW is still written (audit-shaped output); the production-only gate that
    # protects journal MUTATIONS lives at the caller (_step_schwab_orders) +
    # the tier-1 sandbox short-circuit (see test_step_schwab_orders below /
    # test_run_schwab_reconciliation_pivot). The orphan row classifies tier-2
    # 'unsupported' (no sub-classifier) -> pending_ambiguity_resolution, with
    # NO journal mutation either way.
    acct = _SchwabAccount(
        net_liquidating_value=2000.0,
        positions=[_position("IPOX", long_qty=2.0, market_value=51.40)],
    )
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-06-15",
        period_end="2026-06-15",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=acct,
        environment="sandbox",
    )
    rows = _orphans(conn, run.run_id)
    assert len(rows) == 1
