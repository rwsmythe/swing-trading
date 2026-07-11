"""20-A Task A-5 — the fills<->trades consistency invariant (the watchdog).

A recon check that the entry-fill VWAP agrees with ``trades.entry_price``
(tolerance = display precision). Divergence emits a MATERIAL diagnostic that
is NEVER auto-corrected (a shared classify-SKIP at BOTH firing sites -- pivot
+ backfill). Covers ALL trades (open + closed/reviewed) -- the corrector's own
six-week divergence lived on CLOSED trades.

Fixtures = the real PTEN geometry (entry_price 13.00 but the entry FILL carries
the corrupt 12.305) pre-B1, and the corrected fill 13.00 post-B1 (quiet).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.schwab_reconciliation import (
    _INTERNAL_CONSISTENCY_FILLS_VS_TRADES,
    _INTERNAL_CONSISTENCY_KEY,
    _is_internal_consistency_diagnostic,
    run_schwab_reconciliation,
)


@dataclass
class _Account:
    net_liquidating_value: float | None = 2000.0
    positions: list | None = None


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_reviewed_trade(
    conn, *, ticker: str, entry_price: float, fill_price: float, qty: float,
) -> tuple[int, int]:
    """A CLOSED/REVIEWED trade whose entry FILL price may diverge from the
    trades.entry_price (the PTEN/DFTX corruption geometry)."""
    cur = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ticker, "2026-05-19", entry_price, int(qty), entry_price - 1.0,
         entry_price - 1.0, "reviewed", "manual_off_pipeline",
         "2026-05-19T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-05-19T14:00:00", "entry", qty, fill_price,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-05-25T14:00:00", "exit", qty, entry_price + 2.0,
         "unreconciled"),
    )
    conn.commit()
    return trade_id, fill_id


def _run(conn):
    return run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-05-19", period_end="2026-05-25",
        schwab_orders=[], schwab_transactions=[], schwab_account=_Account(),
    )


def _a5_rows(conn, run_id):
    rows = conn.execute(
        "SELECT trade_id, actual_value_json, resolution, material_to_review "
        "FROM reconciliation_discrepancies WHERE run_id = ? AND field_name = ?",
        (run_id, _INTERNAL_CONSISTENCY_KEY),
    ).fetchall()
    return rows


def test_a5_fires_on_closed_trade_with_divergent_entry_fill(conn) -> None:
    """PTEN pre-B1: entry_price 13.00 but the entry fill carries 12.305 ->
    a MATERIAL fills<->trades diagnostic on a REVIEWED trade."""
    trade_id, _ = _seed_reviewed_trade(
        conn, ticker="PTEN", entry_price=13.00, fill_price=12.305, qty=15.0,
    )
    run = _run(conn)
    rows = _a5_rows(conn, run.run_id)
    assert len(rows) == 1
    assert rows[0][0] == trade_id
    payload = json.loads(rows[0][1])
    assert payload[_INTERNAL_CONSISTENCY_KEY] == \
        _INTERNAL_CONSISTENCY_FILLS_VS_TRADES
    assert payload["trades_entry_price"] == 13.00
    assert abs(payload["entry_fill_vwap"] - 12.305) < 1e-9
    # Material.
    assert rows[0][3] == 1


def test_a5_quiet_when_fill_matches_entry_price(conn) -> None:
    """Post-B1: entry fill corrected to 13.00 == entry_price -> no emit."""
    _seed_reviewed_trade(
        conn, ticker="PTEN", entry_price=13.00, fill_price=13.00, qty=15.0,
    )
    run = _run(conn)
    assert _a5_rows(conn, run.run_id) == []


def test_a5_row_is_never_auto_corrected(conn) -> None:
    """The diagnostic stays `unresolved` after the pivot (classify-skip) — it
    is NEVER routed into the tier-1 path."""
    _seed_reviewed_trade(
        conn, ticker="DFTX", entry_price=24.53, fill_price=22.16, qty=7.0,
    )
    run = _run(conn)
    rows = _a5_rows(conn, run.run_id)
    assert len(rows) == 1
    assert rows[0][2] == "unresolved"  # not auto_corrected / stamped


def test_a5_backfill_skips_the_diagnostic(conn) -> None:
    """The backfill firing site ALSO skips the diagnostic (shared predicate):
    it stays unresolved after run_backfill."""
    _seed_reviewed_trade(
        conn, ticker="DFTX", entry_price=24.53, fill_price=22.16, qty=7.0,
    )
    run = _run(conn)
    rows = _a5_rows(conn, run.run_id)
    assert len(rows) == 1
    from swing.trades.reconciliation_backfill import run_backfill
    run_backfill(
        conn, dry_run=False, schwab_client=None, environment="production",
        account_hash=None,
    )
    resolution = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE field_name = ?", (_INTERNAL_CONSISTENCY_KEY,),
    ).fetchone()[0]
    assert resolution == "unresolved"


def test_a5_render_consumers_are_sane_on_the_variant(conn) -> None:
    """Consumer audit (D-A4 condition 2): the EXISTING entry_price_mismatch
    render consumers (reconciliation_render + the reconcile pre-resolution VM)
    do NOT crash on the internal-consistency variant and show the divergence."""
    _seed_reviewed_trade(
        conn, ticker="PTEN", entry_price=13.00, fill_price=12.305, qty=15.0,
    )
    run = _run(conn)
    rows = conn.execute(
        "SELECT expected_value_json, actual_value_json FROM "
        "reconciliation_discrepancies WHERE run_id = ? AND field_name = ?",
        (run.run_id, _INTERNAL_CONSISTENCY_KEY),
    ).fetchone()
    expected = json.loads(rows[0])
    actual = json.loads(rows[1])
    from swing.trades.reconciliation_render import _pairs_entry_price_mismatch
    pairs = _pairs_entry_price_mismatch(expected, actual)
    # Renders the divergence (trades 13.00 vs fill VWAP 12.305) — no crash.
    assert ("entry price", 13.00, 12.305) in pairs


def test_skip_predicate_discriminates() -> None:
    """The shared predicate matches the marker and rejects a plain payload."""
    @dataclass
    class _D:
        actual_value_json: str | None

    assert _is_internal_consistency_diagnostic(
        _D(json.dumps({_INTERNAL_CONSISTENCY_KEY:
                       _INTERNAL_CONSISTENCY_FILLS_VS_TRADES}))
    )
    assert not _is_internal_consistency_diagnostic(_D(json.dumps({"price": 5.0})))
    assert not _is_internal_consistency_diagnostic(_D(None))
