"""22-F T-F1 -- D39 (S-D39) on the five BEGIN sites of
`swing/trades/reconciliation_auto_correct.py` (census C2-01..C2-04; C2-04's
two functions have no production caller and are fixed for uniformity, tested
by direct call).

The both-verbs-fail proxy (`tests/_22f_proxies.py::FailingVerbsConn`) is the
`conn` argument.  The body after BEGIN is planted at the function the public
entry point calls first (the `_inner` for four sites; the function-local
`get_discrepancy` import for `apply_source_direction_resolution`), and the
plant issues a REAL write through the connection -- the statement the proxy
fails.  Pre-fix the rollback failure is SUPPRESSED (`suppress(sqlite3.Error)`),
so the WRITE error escapes and the transaction's fate is silent; post-fix the
CLEANUP error is raised, chained from the write error, with ONE ERROR record
saying the connection MUST BE DISCARDED.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import FailingVerbsConn

_MOD = "swing.trades.reconciliation_auto_correct"
_WRITE = ("INSERT INTO reconciliation_runs (source, started_ts, state) "
          "VALUES ('schwab_api', '2026-09-25T00:00:00', 'running')")


def _planted(mode: str):
    """The body after BEGIN: a real write, then return / interrupt."""
    calls = {"n": 0}

    def body(conn, *a, **k):
        calls["n"] += 1
        conn.execute(_WRITE)
        if mode == "interrupt":
            raise KeyboardInterrupt("planted interrupt")
        return None

    body.calls = calls
    return body


def _call(name: str, conn):
    import swing.trades.reconciliation_auto_correct as m
    if name == "apply_tier1_correction":
        return m.apply_tier1_correction(conn, discrepancy_id=1,
                                        classification=None)
    if name == "apply_tier2_resolution":
        return m.apply_tier2_resolution(conn, discrepancy_id=1,
                                        choice_code="keep_journal_as_is",
                                        operator_reason="probe")
    if name == "apply_source_direction_resolution":
        return m.apply_source_direction_resolution(
            conn, discrepancy_id=1, choice_code="x", operator_reason="probe")
    if name == "apply_tier3_override":
        return m.apply_tier3_override(conn, correction_id=1,
                                      operator_truth_value={"price": 5.25},
                                      operator_reason="probe")
    if name == "stamp_pending_ambiguity":
        return m.stamp_pending_ambiguity(conn, discrepancy_id=1,
                                         ambiguity_kind="unsupported",
                                         resolution_reason="probe")
    raise AssertionError(name)


# (public entry point, the name its try body calls first after BEGIN)
SITES = [
    ("apply_tier1_correction", f"{_MOD}._apply_tier1_correction_inner"),
    ("apply_tier2_resolution", f"{_MOD}._apply_tier2_resolution_inner"),
    ("apply_source_direction_resolution",
     "swing.data.repos.reconciliation.get_discrepancy"),
    ("apply_tier3_override", f"{_MOD}._apply_tier3_override_inner"),
    ("stamp_pending_ambiguity", f"{_MOD}._stamp_pending_ambiguity_inner"),
]
_IDS = [s[0] for s in SITES]


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.db"
    ensure_schema(path).close()
    return path


def _runs(db: Path) -> int:
    c = sqlite3.connect(str(db))
    try:
        return c.execute("SELECT COUNT(*) FROM reconciliation_runs").fetchone()[0]
    finally:
        c.close()


def _discard_records(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records
            if r.levelno >= logging.ERROR and "MUST BE DISCARDED" in r.getMessage()]


@pytest.mark.parametrize(("name", "target"), SITES, ids=_IDS)
def test_both_verbs_fail_raises_cleanup_chained_with_one_record(
        db, name, target, monkeypatch, caplog):
    """PRE-FIX: the WRITE error escapes (the rollback failure suppressed), no
    record.  POST-FIX: the CLEANUP error, `__cause__` the write error, one
    `MUST BE DISCARDED` ERROR record."""
    body = _planted("return")
    monkeypatch.setattr(target, body)
    proxy = FailingVerbsConn(sqlite3.connect(str(db)),
                             fail_sql_prefix="INSERT INTO reconciliation_runs",
                             fail_rollback=True)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                _call(name, proxy)
    finally:
        proxy._real.close()
    assert body.calls["n"] == 1 and proxy.calls["failed_sql"] == 1
    assert proxy.calls["rollback"] >= 1  # did-it-fire
    assert "cannot rollback" in str(info.value)
    assert isinstance(info.value.__cause__, sqlite3.OperationalError)
    assert "planted on INSERT" in str(info.value.__cause__)
    assert len(_discard_records(caplog)) == 1


@pytest.mark.parametrize(("name", "target"), SITES, ids=_IDS)
def test_f2_twin_interrupt_rolls_back(db, name, target, monkeypatch):
    """PRE-FIX: `except Exception` does not run on `KeyboardInterrupt`, the
    transaction stays OPEN.  POST-FIX: rolled back, the interrupt re-raised,
    nothing written (fresh read).  Covers the F1 twin (BEGIN inside the try)
    by reaching the rollback."""
    body = _planted("interrupt")
    monkeypatch.setattr(target, body)
    proxy = FailingVerbsConn(sqlite3.connect(str(db)))
    try:
        with pytest.raises(KeyboardInterrupt):
            _call(name, proxy)
        assert body.calls["n"] == 1
        assert proxy.in_transaction is False
        assert proxy.calls["rollback"] >= 1  # did-it-fire
    finally:
        proxy._real.close()
    assert _runs(db) == 0


@pytest.mark.parametrize(("name", "target"), SITES, ids=_IDS)
def test_single_failure_write_error_reraised_rollback_works(
        db, name, target, monkeypatch, caplog):
    """PIN (both trees): the write fails, the rollback works -> the write
    error re-raised, no record, nothing written."""
    body = _planted("return")
    monkeypatch.setattr(target, body)
    proxy = FailingVerbsConn(sqlite3.connect(str(db)),
                             fail_sql_prefix="INSERT INTO reconciliation_runs")
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError,
                               match="planted on INSERT"):
                _call(name, proxy)
        assert proxy.calls["rollback"] >= 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _discard_records(caplog) == []
    assert _runs(db) == 0


@pytest.mark.parametrize(("name", "target"),
                         [s for s in SITES
                          if s[0] != "apply_source_direction_resolution"],
                         ids=[i for i in _IDS
                              if i != "apply_source_direction_resolution"])
def test_control_write_succeeds_commits(db, name, target, monkeypatch):
    """CONTROL: the write succeeds -> commit, the row on a fresh read.  (The
    source-direction entry point refuses a `None` discrepancy after its read,
    so it has no commit path under this plant; the single-failure PIN covers
    its rollback path.)"""
    body = _planted("return")
    monkeypatch.setattr(target, body)
    proxy = FailingVerbsConn(sqlite3.connect(str(db)))
    try:
        _call(name, proxy)
        assert proxy.calls["commit"] >= 1
    finally:
        proxy._real.close()
    assert _runs(db) == 1
