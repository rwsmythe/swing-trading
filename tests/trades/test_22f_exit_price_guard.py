"""22-F T-A6 -- C1-24: `record_exit` refuses exactly what `fills.price` refuses,
FIRST (AUTHORIZE-THEN-ABORT; A-1 granted: one typed error in `exit.py`).

`ExitPriceRefusedError(ValueError)` is raised beside the `shares <= 0` check,
before any statement, for `not (price > 0)`: the CHECK's `<= 0` set plus NaN
(the NOT NULL). `inf` is admitted, as the schema admits it (A6-f, a BOUND pin).

A6-d/A6-e run `record_exit` over ONE `FailingVerbsConn` that raises on any
`INSERT` (the proxy IS the `conn` argument -- there is no patch target to
miss).  A6-e is the pass-through control (no failing verb) that proves the
proxy counts INSERTs at all, which is what makes A6-d's zero non-vacuous.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.exit import ExitReason, ExitRequest, record_exit
from tests._22f_proxies import FailingVerbsConn
from tests.trades.test_exit import _seed_active_trade


@pytest.fixture
def world(tmp_path: Path):
    db = tmp_path / "exit_guard.db"
    conn = ensure_schema(db)
    tid = int(_seed_active_trade(conn, ticker="AAPL", current_size=100.0))
    yield conn, db, tid
    conn.close()


def _req(tid: int, price: float) -> ExitRequest:
    return ExitRequest(
        trade_id=tid, exit_date="2026-05-10", exit_price=price, shares=10,
        reason=ExitReason.MANUAL, notes=None, rationale="manual",
        event_ts="2026-05-10T15:00:00",
    )


def _fresh(db: Path, tid: int) -> tuple:
    c = sqlite3.connect(str(db))
    try:
        return (c.execute("SELECT COUNT(*) FROM fills").fetchone()[0],
                c.execute("SELECT current_size FROM trades WHERE id = ?",
                          (tid,)).fetchone()[0])
    finally:
        c.close()


@pytest.mark.parametrize("price", [0, 0.0, -0.0, -1, float("nan")],
                         ids=["0", "0.0", "-0.0", "-1", "nan"])
def test_A6d_record_exit_refuses_the_columns_refusal_set_before_any_insert(
        world, price):
    """A6-d. PRE-FIX: the INSERT is attempted (the proxy's planted INSERT
    failure fires; on a bare connection the CHECK -- or NOT NULL for NaN --
    raises `IntegrityError`).  POST-FIX: `ExitPriceRefusedError`, a
    `ValueError`, with ZERO INSERT attempts."""
    conn, db, tid = world
    before = _fresh(db, tid)
    proxy = FailingVerbsConn(conn, fail_sql_prefix="INSERT")
    with pytest.raises(Exception) as exc:
        record_exit(proxy, _req(tid, price))
    # The type is named rather than imported so the PRE-FIX tree reports the
    # INSERT attempt below, not an ImportError.
    assert type(exc.value).__name__ == "ExitPriceRefusedError", (
        repr(exc.value), proxy.calls["execute:INSERT"])
    assert isinstance(exc.value, ValueError)
    assert "exit price must be > 0" in str(exc.value)
    assert proxy.calls["execute:INSERT"] == 0, proxy.sql_log
    assert _fresh(db, tid) == before  # A6-c at the service


def test_A6e_control_valid_price_through_the_same_proxy_counts_inserts(
        world):
    """A6-e CONTROL: ``price=0.01`` through the SAME proxy class as a
    pass-through: the exit is recorded and the proxy counted >= 1 INSERT --
    what makes A6-d's zero meaningful.  Both trees."""
    conn, db, tid = world
    proxy = FailingVerbsConn(conn)
    before = _fresh(db, tid)[0]
    result = record_exit(proxy, _req(tid, 0.01))
    assert result.exit_id is not None
    assert proxy.calls["execute:INSERT"] >= 1, proxy.sql_log
    assert _fresh(db, tid)[0] == before + 1


def test_A6f_bound_pin_inf_price_is_recorded_as_the_schema_admits(world):
    """A6-f -- a BOUND pin, NOT a contract that an infinite price is
    admissible.  The guard refuses exactly the `fills.price` column's
    refusal set, and the column admits ``inf`` today, so ``inf`` is
    recorded on BOTH trees.  22-G is EXPECTED to invert this pin under
    BANK-4 (the `value="inf"` render); when it does, this test is the one
    that must change, and it says so here."""
    conn, db, tid = world
    result = record_exit(conn, _req(tid, float("inf")))
    assert result.exit_id is not None
    c = sqlite3.connect(str(db))
    try:
        stored = c.execute("SELECT price FROM fills WHERE action != 'entry' "
                           "ORDER BY fill_id DESC LIMIT 1").fetchone()[0]
    finally:
        c.close()
    assert math.isinf(stored)
