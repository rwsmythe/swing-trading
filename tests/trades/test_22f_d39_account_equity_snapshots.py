"""22-F T-F7 (C2-11) -- D39 (S-D39) on `account_equity_snapshots.py`'s one
BEGIN site: `record_snapshot` (`:133/:148`).

The proxy is the `conn` argument.  The site's first write after BEGIN is read
from `swing/data/repos/account_equity_snapshots.py:upsert_snapshot`: it is an
`INSERT INTO account_equity_snapshots` for a new `(snapshot_date, source,
basis)` key and an `UPDATE account_equity_snapshots` for an existing one, so
the one site is driven down BOTH write paths.  Every case asserts the proxy
recorded the verb (did-it-fire).  The row is F1 (BEGIN outside the try) and
UNGUARDED pre-fix (a failing `conn.rollback()` replaces the write error).
No clock is read by any assertion: every call passes `snapshot_date`.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import FailingVerbsConn

_SEED_DATE = "2026-09-21"
_NEW_DATE = "2026-09-22"


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.db"
    conn = ensure_schema(path)
    try:
        from swing.trades.account_equity_snapshots import record_snapshot
        record_snapshot(conn, equity_dollars=1000.0, snapshot_date=_SEED_DATE)
    finally:
        conn.close()
    return path


def _record(date_str: str):
    def _call(conn):
        from swing.trades.account_equity_snapshots import record_snapshot
        return record_snapshot(conn, equity_dollars=1234.5,
                               snapshot_date=date_str)
    return _call


_PROBE = ("SELECT COUNT(*) FROM account_equity_snapshots "
          "WHERE snapshot_date = '{d}' AND equity_dollars = 1234.5")

_PATHS = {
    "insert_new_key": (_record(_NEW_DATE),
                       "INSERT INTO account_equity_snapshots",
                       _PROBE.format(d=_NEW_DATE)),
    "update_existing_key": (_record(_SEED_DATE),
                            "UPDATE account_equity_snapshots",
                            _PROBE.format(d=_SEED_DATE)),
}


def _probe(db: Path, sql: str) -> int:
    c = sqlite3.connect(str(db))
    try:
        return c.execute(sql).fetchone()[0]
    finally:
        c.close()


def _records(caplog):
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_both_verbs_fail_raises_cleanup_chained(path, db, caplog):
    """PRE-FIX: the CLEANUP error with `__cause__` None, no record.
    POST-FIX: the CLEANUP error, `__cause__` the write error, one record."""
    call, prefix, _ = _PATHS[path]
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


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_f2_twin_interrupt_rolls_back(path, db):
    call, prefix, probe = _PATHS[path]
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


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_single_failure_write_error_reraised_pin(path, db, caplog):
    """PIN (both trees): the write fails, the rollback works."""
    call, prefix, probe = _PATHS[path]
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


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_control_commits(path, db):
    call, prefix, probe = _PATHS[path]
    proxy = FailingVerbsConn(sqlite3.connect(str(db)))
    try:
        call(proxy)
        assert proxy.calls["commit"] >= 1
        assert proxy.calls["execute:" + prefix.split()[0].upper()] >= 1
    finally:
        proxy._real.close()
    assert _probe(db, probe) == 1
