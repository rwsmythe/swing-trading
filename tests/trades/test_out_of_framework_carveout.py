"""SPCX out-of-framework carve-out — Task 2 orphan-pass carve-out tests.

A declared out-of-framework ticker held at the broker produces ZERO
`untracked_broker_position` orphans; an UNDECLARED untracked position STILL
banners (the L3 / C2 discriminator); the carve-out is surfaced in cash_warnings
+ a summary counter (never silent).

Fixtures use the REAL Schwab position dict shape
(``{"instrument": {"symbol": ...}, "longQuantity": ..., "marketValue": ...}``).
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
    return {
        "shortQuantity": short_qty,
        "longQuantity": long_qty,
        "instrument": {"symbol": symbol, "type": "EQUITY"},
        "marketValue": market_value,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _orphans(conn: sqlite3.Connection, run_id: int) -> list[tuple]:
    return conn.execute(
        "SELECT ticker, resolution FROM reconciliation_discrepancies "
        "WHERE run_id=? AND discrepancy_type='untracked_broker_position'",
        (run_id,),
    ).fetchall()


def _run(conn, positions, *, out_of_framework=()):
    acct = _SchwabAccount(net_liquidating_value=2000.0, positions=positions)
    return run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-06-15",
        period_end="2026-06-15",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=acct,
        out_of_framework_tickers=out_of_framework,
    )


def test_declared_ticker_emits_no_untracked_orphan(conn):
    """A declared held ticker produces ZERO untracked_broker_position rows.

    Pre-fix (param absent / not threaded): one orphan for SPCX.
    Post-fix: zero.
    """
    run = _run(
        conn,
        [_position("SPCX", long_qty=2.0, market_value=412.0)],
        out_of_framework=("SPCX",),
    )
    rows = _orphans(conn, run.run_id)
    assert [r for r in rows if r[0] == "SPCX"] == []


def test_undeclared_untracked_position_still_banners(conn):
    """L3 / C2 discriminator: declared SPCX skipped; UNDECLARED FOO still
    banners unresolved. Proves the carve-out is scoped, NOT a blanket.

    Pre-fix: two orphans (FOO + SPCX). Post-fix: one (FOO only).
    """
    run = _run(
        conn,
        [
            _position("SPCX", long_qty=2.0, market_value=412.0),  # declared
            _position("FOO", long_qty=10.0, market_value=500.0),  # undeclared
        ],
        out_of_framework=("SPCX",),
    )
    rows = _orphans(conn, run.run_id)
    assert [r[0] for r in rows] == ["FOO"]
    assert rows[0][1] == "unresolved"


def test_carveout_surfaces_in_summary_warnings(conn):
    """C2 / #27 visibility: a cash_warnings entry with
    reason=out_of_framework_excluded mentioning SPCX + qty + MV, AND the
    summary counter == 1. Proves the skip is NOT silent.

    Pre-fix: no such warning (KeyError / empty). Post-fix: present.
    """
    run = _run(
        conn,
        [_position("SPCX", long_qty=2.0, market_value=412.0)],
        out_of_framework=("SPCX",),
    )
    summary = json.loads(run.summary_json)
    warnings = summary.get("cash_warnings", [])
    excl = [
        w for w in warnings
        if isinstance(w, dict) and w.get("reason") == "out_of_framework_excluded"
    ]
    assert len(excl) == 1
    detail = excl[0]["detail"]
    assert "SPCX" in detail
    assert "2.00" in detail  # qty
    assert "412" in detail   # market value
    assert summary["out_of_framework_excluded_count"] == 1


def test_default_empty_out_of_framework_preserves_orphan(conn):
    """No-regression guard (NOT distinguishing): with the empty-set default an
    untracked SPCX position STILL emits an orphan (byte-identical to 18-H.6).
    Guards against an over-eager empty-set carve-out.
    """
    run = _run(
        conn,
        [_position("SPCX", long_qty=2.0, market_value=412.0)],
        out_of_framework=(),
    )
    rows = _orphans(conn, run.run_id)
    assert [r[0] for r in rows] == ["SPCX"]


def test_declared_holding_never_in_trades_or_stats(conn):
    """L1 structural LOCK (NOT distinguishing): path B never creates a
    trades/fills row for a declared holding, so SPCX is structurally absent
    from compute_stats / every strategy surface. Passes before AND after; its
    value is guarding that no future task journals a declared holding.
    """
    from swing.data.repos.trades import list_open_trades
    from swing.journal.stats import compute_stats

    run = _run(
        conn,
        [_position("SPCX", long_qty=2.0, market_value=412.0)],
        out_of_framework=("SPCX",),
    )
    assert run.state == "completed"
    # No trades row for SPCX (by construction).
    n_spcx = conn.execute(
        "SELECT COUNT(*) FROM trades WHERE ticker='SPCX'"
    ).fetchone()[0]
    assert n_spcx == 0
    open_trades = list_open_trades(conn)
    stats = compute_stats(trades=open_trades, exits=[])
    assert stats.n_trades == 0
