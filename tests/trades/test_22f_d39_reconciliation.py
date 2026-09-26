"""22-F T-F3 -- D39 (S-D39) on `swing/trades/reconciliation.py`'s two BEGIN
sites (census C2-06): `run_tos_reconciliation` (its OUTER handler -- the
"outer INSERT run row itself fails" branch) and `resolve_discrepancy`.

Both already open the transaction inside the `try` (F1 holds); the defects
are F2 (`except Exception`) and F3 (`suppress(sqlite3.Error)` on the
rollback).  The proxy is the `conn` argument and fails each site's FIRST
write after BEGIN: `INSERT INTO reconciliation_runs` (`repo.insert_run`) and
`UPDATE reconciliation_discrepancies` (`update_discrepancy_resolution`).
`resolve_discrepancy`'s not-found refusal (raised inside the try) is driven
too -- its error is the original the cleanup error must chain from.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import FailingVerbsConn
from tests.trades.test_22a4_corrector_refusal import _seed_trade_anchored_world
from tests.trades.test_reconciliation_service import _SIMPLE_TOS_CSV

_RUN_INSERT = "INSERT INTO reconciliation_runs"
_DISC_UPDATE = "UPDATE reconciliation_discrepancies"


@pytest.fixture
def world(tmp_path: Path):
    db = tmp_path / "t.db"
    conn = ensure_schema(db)
    try:
        w = _seed_trade_anchored_world(conn, tier2=False)
    finally:
        conn.close()
    csv = tmp_path / "tos.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")
    return db, w, csv


def _drive(case: str, conn, w, csv):
    from swing.trades.reconciliation import (
        resolve_discrepancy,
        run_tos_reconciliation,
    )
    if case == "run_tos":
        return run_tos_reconciliation(conn, csv_path=csv)
    if case == "resolve":
        return resolve_discrepancy(conn, discrepancy_id=w["discrepancy_id"],
                                   resolution="journal_corrected",
                                   resolution_reason="probe")
    if case == "resolve_not_found":
        return resolve_discrepancy(conn, discrepancy_id=99999,
                                   resolution="journal_corrected",
                                   resolution_reason="probe")
    raise AssertionError(case)


def _state(db: Path) -> tuple:
    c = sqlite3.connect(str(db))
    try:
        return (c.execute("SELECT COUNT(*) FROM reconciliation_runs").fetchone()[0],
                c.execute("SELECT resolution FROM reconciliation_discrepancies "
                          "ORDER BY discrepancy_id").fetchall())
    finally:
        c.close()


def _records(caplog) -> list:
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


# (case, the proxy's write-failure prefix or None for a refusal original)
BOTH = [("run_tos", _RUN_INSERT), ("resolve", _DISC_UPDATE),
        ("resolve_not_found", None)]


@pytest.mark.parametrize(("case", "prefix"), BOTH, ids=[b[0] for b in BOTH])
def test_both_fail_raises_cleanup_chained_with_one_record(world, case, prefix,
                                                          caplog):
    """PRE-FIX: the original escapes (the rollback failure suppressed), no
    record.  POST-FIX: the CLEANUP error chained from the original, one
    `MUST BE DISCARDED` ERROR record."""
    db, w, csv = world
    before = _state(db)
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=prefix,
                             fail_rollback=True)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                _drive(case, proxy, w, csv)
    finally:
        proxy._real.close()
    assert proxy.calls["rollback"] >= 1  # did-it-fire
    if prefix is not None:
        assert proxy.calls["failed_sql"] == 1
    assert "cannot rollback" in str(info.value)
    cause = info.value.__cause__
    if case == "resolve_not_found":
        assert isinstance(cause, ValueError) and "not found" in str(cause)
    else:
        assert isinstance(cause, sqlite3.OperationalError)
        assert "planted on" in str(cause)
    assert len(_records(caplog)) == 1
    assert _state(db) == before


@pytest.mark.parametrize(("case", "prefix"), BOTH[:2], ids=[b[0] for b in BOTH[:2]])
def test_f2_twin_interrupt_rolls_back(world, case, prefix):
    """PRE-FIX: `except Exception` does not run -> the transaction stays
    OPEN.  POST-FIX: rolled back, the interrupt re-raised, nothing written."""
    db, w, csv = world
    before = _state(db)
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=prefix,
                             raise_on_sql=KeyboardInterrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            _drive(case, proxy, w, csv)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _state(db) == before


@pytest.mark.parametrize(("case", "prefix"), BOTH, ids=[b[0] for b in BOTH])
def test_single_failure_original_reraised(world, case, prefix, caplog):
    """PIN (both trees): the rollback works -> the original re-raised, no
    record, nothing written."""
    db, w, csv = world
    before = _state(db)
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=prefix)
    expected = ValueError if prefix is None else sqlite3.OperationalError
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(expected):
                _drive(case, proxy, w, csv)
        assert proxy.calls["rollback"] >= 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _records(caplog) == []
    assert _state(db) == before


@pytest.mark.parametrize("case", ["run_tos", "resolve"])
def test_control_commits(world, case):
    db, w, csv = world
    runs0, res0 = _state(db)
    proxy = FailingVerbsConn(sqlite3.connect(str(db)))
    try:
        _drive(case, proxy, w, csv)
        assert proxy.calls["commit"] >= 1
    finally:
        proxy._real.close()
    runs1, res1 = _state(db)
    if case == "run_tos":
        assert runs1 == runs0 + 1
    else:
        assert res1 != res0 and ("journal_corrected",) in res1
