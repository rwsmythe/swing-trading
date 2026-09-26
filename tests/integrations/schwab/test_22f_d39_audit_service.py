"""22-F T-F6 -- D39 (S-D39) on the four `audit_service.py` BEGIN sites
(census C2-09; reached from 10 operator roots through the Schwab wrappers):
`record_call_start` (`:164/:184,:187`), `record_call_finish`
(`:237/:259,:262`), `link_snapshot_and_stamp_account_hash` (`:307/:319`),
`link_reconciliation_run` (`:367/:376`).

The proxy is the `conn` argument; its failing verb is each site's FIRST
write after BEGIN (read from the repo): `INSERT INTO schwab_api_calls` for
start, `UPDATE schwab_api_calls` for the other three.  Every case asserts
the proxy recorded the failing verb (did-it-fire).  All four rows are
UNGUARDED pre-fix: a failing `conn.rollback()` inside the handler replaces
the write error (implicit `__context__` only).
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
        from swing.integrations.schwab.audit_service import record_call_start
        record_call_start(conn, ts="2026-09-25T00:00:00",
                          endpoint="accounts.linked",
                          pipeline_run_id=None, surface="cli",
                          environment="production")
    finally:
        conn.close()
    return path


def _start(conn):
    from swing.integrations.schwab.audit_service import record_call_start
    return record_call_start(conn, ts="2026-09-25T00:00:01",
                             endpoint="accounts.details",
                             pipeline_run_id=None, surface="cli",
                             environment="production")


def _finish(conn):
    from swing.integrations.schwab.audit_service import record_call_finish
    return record_call_finish(conn, call_id=1, http_status=200,
                              response_time_ms=5, rate_limit_remaining=None,
                              signature_hash=None, status="success",
                              error_message=None)


def _link_snapshot(conn):
    from swing.integrations.schwab.audit_service import (
        link_snapshot_and_stamp_account_hash,
    )
    return link_snapshot_and_stamp_account_hash(
        conn, call_id=1, snapshot_id=7, account_hash="<acct>")


def _link_run(conn):
    from swing.integrations.schwab.audit_service import link_reconciliation_run
    return link_reconciliation_run(conn, call_id=1, reconciliation_run_id=9)


# site id -> (call, the first write's prefix, a fresh-read probe of its effect)
_SITES = {
    "record_call_start": (
        _start, "INSERT INTO schwab_api_calls",
        "SELECT COUNT(*) FROM schwab_api_calls "
        "WHERE endpoint = 'accounts.details'"),
    "record_call_finish": (
        _finish, "UPDATE schwab_api_calls",
        "SELECT COUNT(*) FROM schwab_api_calls "
        "WHERE call_id = 1 AND status = 'success'"),
    "link_snapshot_and_stamp_account_hash": (
        _link_snapshot, "UPDATE schwab_api_calls",
        "SELECT COUNT(*) FROM schwab_api_calls "
        "WHERE call_id = 1 AND linked_snapshot_id = 7"),
    "link_reconciliation_run": (
        _link_run, "UPDATE schwab_api_calls",
        "SELECT COUNT(*) FROM schwab_api_calls "
        "WHERE call_id = 1 AND linked_reconciliation_run_id = 9"),
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
