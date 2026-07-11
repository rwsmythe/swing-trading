"""20-A Task B-3 — post-correction verification (CODE tests; the live
re-derivation + badge death are the RD/operator witness gate per plan §13).

The forensic doc's arithmetic is the fixture:
  - AMN (entry 6@33.66; trim 3@X; stop 3@32.06): recorded realized (trim
    32.06) = -$9.60; TRUE (trim 35.65) = +$1.17.
  - SATL trade-11 phantom (+$0.01 realized) is VOIDED -> excluded from
    current_equity + the tuition cohort count.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.cash import list_cash
from swing.trades.equity import current_equity, list_all_exitshape_via_fills
from swing.trades.voided_trades import voided_trade_ids


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_amn(conn, *, trim_price: float) -> int:
    """AMN standard-cohort trade: entry 6@33.66; trim 3@trim_price; stop 3@32.06."""
    cur = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
        "entry_intent) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("AMN", "2026-07-01", 33.66, 6, 32.0, 32.0, "reviewed",
         "manual_off_pipeline", "2026-07-01T16:00:00", "standard"),
    )
    trade_id = int(cur.lastrowid)
    for dt, action, qty, price in (
        ("2026-07-01T14:00:00", "entry", 6, 33.66),
        ("2026-07-07T14:00:00", "trim", 3, trim_price),
        ("2026-07-09T14:00:00", "exit", 3, 32.06),
    ):
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
            (trade_id, dt, action, qty, price, "unreconciled"),
        )
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return trade_id


def _amn_realized(conn, trade_id: int) -> float:
    return round(sum(
        e.realized_pnl for e in list_all_exitshape_via_fills(conn)
        if e.trade_id == trade_id and e.realized_pnl is not None
    ), 2)


def test_amn_recorded_realized_is_negative(conn) -> None:
    """Pre-correction (corrupt trim 32.06): realized == -$9.60."""
    tid = _seed_amn(conn, trim_price=32.06)
    assert _amn_realized(conn, tid) == -9.60


def test_amn_true_realized_flips_positive(conn) -> None:
    """Post-correction (trim 35.65): realized flips to +$1.17."""
    tid = _seed_amn(conn, trim_price=35.65)
    assert _amn_realized(conn, tid) == 1.17


def test_current_equity_reflects_corrected_amn_and_excludes_voided_satl(
    conn,
) -> None:
    """current_equity = starting + corrected AMN realized (+1.17) + net cash;
    the voided SATL +$0.01 is excluded."""
    _seed_amn(conn, trim_price=35.65)
    # SATL phantom: 1-share round trip 10.31/10.32 (+$0.01 realized), voided.
    scur = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
        "entry_intent) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("SATL", "2026-05-22", 10.31, 1, 9.0, 9.0, "reviewed",
         "manual_off_pipeline", "2026-05-22T16:00:00",
         "hypothesis_test_by_design"),
    )
    satl_id = int(scur.lastrowid)
    for action, price in (("entry", 10.31), ("exit", 10.32)):
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
            (satl_id, "2026-05-22T14:00:00", action, 1, price, "unreconciled"),
        )
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, satl_id)
    conn.execute(
        "INSERT INTO trade_events (trade_id, ts, event_type, payload_json, "
        "rationale) VALUES (?, ?, 'note', ?, ?)",
        (satl_id, "2026-07-11T00:00:00",
         json.dumps({"voided": True, "reason": "SATL phantom"}), "void"),
    )
    conn.commit()

    starting = 1000.0
    equity = current_equity(
        starting_equity=starting,
        exits=list_all_exitshape_via_fills(conn),
        cash_movements=list_cash(conn),
    )
    # AMN +1.17; SATL's +0.01 EXCLUDED (voided). No cash movements seeded.
    assert round(equity, 2) == round(starting + 1.17, 2)
    # And the raw SATL realized would have been +0.01 had it not been voided.
    assert satl_id in voided_trade_ids(conn)


def test_voided_satl_absent_from_exitshape_and_tuition_count(conn) -> None:
    """voided_trade_ids excludes SATL from list_all_exitshape_via_fills + the
    tuition cohort count (the 16->15 restatement mechanism, scaled here)."""
    # One tuition trade kept + SATL voided (both hypothesis_test_by_design).
    def _mk(ticker, price):
        c = conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, trade_origin, "
            "pre_trade_locked_at, entry_intent) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticker, "2026-05-22", price, 1, price - 1, price - 1, "reviewed",
             "manual_off_pipeline", "2026-05-22T16:00:00",
             "hypothesis_test_by_design"),
        ).lastrowid
        for action, p in (("entry", price), ("exit", price + 0.01)):
            conn.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
                (c, "2026-05-22T14:00:00", action, 1, p, "unreconciled"),
            )
        from swing.data.repos.fills import _recompute_aggregates
        _recompute_aggregates(conn, c)
        return int(c)

    kept = _mk("KEPT", 5.00)
    satl = _mk("SATL", 10.31)
    conn.execute(
        "INSERT INTO trade_events (trade_id, ts, event_type, payload_json, "
        "rationale) VALUES (?, ?, 'note', ?, ?)",
        (satl, "2026-07-11T00:00:00", json.dumps({"voided": True}), "void"),
    )
    conn.commit()

    exit_ids = {e.trade_id for e in list_all_exitshape_via_fills(conn)}
    assert satl not in exit_ids
    assert kept in exit_ids

    from swing.metrics.cohort import list_trades_for_cohort
    tuition = list_trades_for_cohort(
        conn, hypothesis_label=None, state_filter=("closed", "reviewed"),
        entry_intent="hypothesis_test_by_design",
    )
    tuition_ids = {t.id for t in tuition}
    assert satl not in tuition_ids  # the restatement drops the phantom
    assert kept in tuition_ids
