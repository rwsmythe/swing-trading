"""22-F T-F4 -- D39 (S-D39) on `correct_entry_date`'s BEGIN site (census
C2-07; `journal correct-entry-date` is its operator root).

Same instrument as T-F1: the proxy is the `conn` argument; the body after
BEGIN is planted at `_correct_entry_date_inner` (a module-level name the
outer resolves per call) and issues a REAL `INSERT INTO reconciliation_runs`,
the write the proxy fails.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import FailingVerbsConn

_TARGET = "swing.trades.entry_date_correction._correct_entry_date_inner"
_WRITE = ("INSERT INTO reconciliation_runs (source, started_ts, state) "
          "VALUES ('schwab_api', '2026-09-25T00:00:00', 'running')")


def _plant(monkeypatch, mode: str) -> dict:
    calls = {"n": 0}

    def body(conn, **_k):
        calls["n"] += 1
        conn.execute(_WRITE)
        if mode == "interrupt":
            raise KeyboardInterrupt("planted interrupt")
        return "result"

    monkeypatch.setattr(_TARGET, body)
    return calls


def _call(conn):
    from swing.trades.entry_date_correction import correct_entry_date
    return correct_entry_date(conn, trade_id=1, to_date="2026-04-28",
                              discrepancy_id=1, reason="probe")


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


def _records(caplog):
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


def test_both_verbs_fail_raises_cleanup_chained(db, monkeypatch, caplog):
    """PRE-FIX: the WRITE error (rollback failure suppressed), no record.
    POST-FIX: the CLEANUP error, `__cause__` the write error, one record."""
    calls = _plant(monkeypatch, "return")
    proxy = FailingVerbsConn(sqlite3.connect(str(db)),
                             fail_sql_prefix="INSERT INTO reconciliation_runs",
                             fail_rollback=True)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                _call(proxy)
    finally:
        proxy._real.close()
    assert calls["n"] == 1 and proxy.calls["failed_sql"] == 1
    assert proxy.calls["rollback"] >= 1
    assert "cannot rollback" in str(info.value)
    assert "planted on INSERT" in str(info.value.__cause__)
    assert len(_records(caplog)) == 1


def test_f2_twin_interrupt_rolls_back(db, monkeypatch):
    calls = _plant(monkeypatch, "interrupt")
    proxy = FailingVerbsConn(sqlite3.connect(str(db)))
    try:
        with pytest.raises(KeyboardInterrupt):
            _call(proxy)
        assert calls["n"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _runs(db) == 0


def test_single_failure_write_error_reraised(db, monkeypatch, caplog):
    _plant(monkeypatch, "return")
    proxy = FailingVerbsConn(sqlite3.connect(str(db)),
                             fail_sql_prefix="INSERT INTO reconciliation_runs")
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError, match="planted on"):
                _call(proxy)
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _records(caplog) == []
    assert _runs(db) == 0


def test_control_commits(db, monkeypatch):
    _plant(monkeypatch, "return")
    proxy = FailingVerbsConn(sqlite3.connect(str(db)))
    try:
        assert _call(proxy) == "result"
        assert proxy.calls["commit"] >= 1
    finally:
        proxy._real.close()
    assert _runs(db) == 1
