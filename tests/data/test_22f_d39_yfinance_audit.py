"""22-F T-F7 (C2-10) -- D39 (S-D39) on `yfinance_audit.py`'s two BEGIN sites:
`record_call_start` (`:118/:127`) and `record_call_finish` (`:158/:167`).

The proxy is the `conn` argument; its failing verb is each site's first write
after BEGIN (read from `swing/data/repos/yfinance_calls.py`): `INSERT INTO
yfinance_calls` and `UPDATE yfinance_calls`.  Every case asserts the proxy
recorded the verb (did-it-fire).  Both rows are F1 (BEGIN outside the try)
and UNGUARDED pre-fix (a failing `conn.rollback()` replaces the write error).
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import FailingVerbsConn


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.db"
    conn = ensure_schema(path)
    try:
        from swing.data.yfinance_audit import record_call_start
        record_call_start(conn, ts="2026-09-25T00:00:00",
                          call_type="download_single", ticker="SEED",
                          ticker_count=None, pipeline_run_id=None,
                          surface="cli")
    finally:
        conn.close()
    return path


def _start(conn):
    from swing.data.yfinance_audit import record_call_start
    return record_call_start(conn, ts="2026-09-25T00:00:01",
                             call_type="download_single", ticker="PROBE",
                             ticker_count=None, pipeline_run_id=None,
                             surface="cli")


def _finish(conn):
    from swing.data.yfinance_audit import record_call_finish
    return record_call_finish(conn, call_id=1, response_time_ms=5,
                              status="success", rows_returned=3,
                              error_message=None)


_SITES = {
    "record_call_start": (
        _start, "INSERT INTO yfinance_calls",
        "SELECT COUNT(*) FROM yfinance_calls WHERE ticker = 'PROBE'"),
    "record_call_finish": (
        _finish, "UPDATE yfinance_calls",
        "SELECT COUNT(*) FROM yfinance_calls "
        "WHERE call_id = 1 AND status = 'success'"),
}


def _probe(db: Path, sql: str) -> int:
    c = sqlite3.connect(str(db))
    try:
        return c.execute(sql).fetchone()[0]
    finally:
        c.close()


def _records(caplog):
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


@pytest.mark.parametrize("site", sorted(_SITES))
def test_both_verbs_fail_raises_cleanup_chained(site, db, caplog):
    """PRE-FIX: the CLEANUP error with `__cause__` None, no record.
    POST-FIX: the CLEANUP error, `__cause__` the write error, one record."""
    call, prefix, _ = _SITES[site]
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=prefix,
                             fail_rollback=True)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                call(proxy)
    finally:
        proxy._real.close()
    assert proxy.calls["failed_sql"] == 1
    assert proxy.calls["rollback"] >= 1
    assert "cannot rollback" in str(info.value)
    assert "planted on" in str(info.value.__cause__)
    assert len(_records(caplog)) == 1


@pytest.mark.parametrize("site", sorted(_SITES))
def test_f2_twin_interrupt_rolls_back(site, db):
    call, prefix, probe = _SITES[site]
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=prefix,
                             raise_on_sql=KeyboardInterrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            call(proxy)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _probe(db, probe) == 0


@pytest.mark.parametrize("site", sorted(_SITES))
def test_single_failure_write_error_reraised_pin(site, db, caplog):
    """PIN (both trees): the write fails, the rollback works."""
    call, prefix, probe = _SITES[site]
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=prefix)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError, match="planted on"):
                call(proxy)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _records(caplog) == []
    assert _probe(db, probe) == 0


@pytest.mark.parametrize("site", sorted(_SITES))
def test_control_commits(site, db):
    call, prefix, probe = _SITES[site]
    proxy = FailingVerbsConn(sqlite3.connect(str(db)))
    try:
        call(proxy)
        assert proxy.calls["commit"] >= 1
        assert proxy.calls["execute:" + prefix.split()[0].upper()] >= 1
    finally:
        proxy._real.close()
    assert _probe(db, probe) == 1
