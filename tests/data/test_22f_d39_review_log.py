"""22-F T-F8 (C2-15) -- D39 (S-D39) on `repos/review_log.py`'s one BEGIN
site: `complete_review_atomic` (`:248/:359`).

The proxy is the `conn` argument.  The site's first write after BEGIN is the
body's one `UPDATE review_log` (everything before it is a SELECT), read from
the body.  The cleanup is `conn.execute("ROLLBACK")` (plan section 1.2 row 3:
the census's `.rollback()` count missed it); the proxy fails that verb too.
Every case asserts the proxy recorded its verb (did-it-fire).  The row is
F1 (BEGIN outside the try), F2 (`except Exception`) and F3 (the cleanup
UNGUARDED: a failing ROLLBACK replaces the write error).  SS-4, by reading:
the try body has no in-try ROLLBACK; its refusals (`ValueError` not-found,
`ReviewAlreadyCompletedError`) raise into the same handler.  No clock is
read: every date is a literal.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import FailingVerbsConn

_VERB = "UPDATE review_log"


@pytest.fixture
def db(tmp_path: Path) -> tuple[Path, int]:
    from swing.data.repos.review_log import insert_pre_create
    path = tmp_path / "t.db"
    conn = ensure_schema(path)
    try:
        with conn:
            rid = insert_pre_create(
                conn, review_type="daily", period_start="2026-04-30",
                period_end="2026-04-30", scheduled_date="2026-05-01")
    finally:
        conn.close()
    assert rid is not None
    return path, rid


def _complete(conn, rid: int) -> None:
    from swing.data.repos.review_log import complete_review_atomic
    complete_review_atomic(
        conn, review_id=rid, completed_date="2026-05-02",
        duration_minutes=15, primary_lesson="Wait for the breakout.",
        next_period_focus="Tighten entries.")


def _completed(path: Path, rid: int):
    c = sqlite3.connect(str(path))
    try:
        return c.execute("SELECT completed_date FROM review_log "
                         "WHERE review_id = ?", (rid,)).fetchone()[0]
    finally:
        c.close()


def _records(caplog):
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


def test_both_verbs_fail_raises_cleanup_chained(db, caplog):
    """PRE-FIX: the CLEANUP error with `__cause__` None, no record.
    POST-FIX: the CLEANUP error, `__cause__` the write error, one record."""
    path, rid = db
    proxy = FailingVerbsConn(sqlite3.connect(str(path)), fail_sql_prefix=_VERB,
                             fail_rollback=True)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                _complete(proxy, rid)
    finally:
        proxy._real.close()
    assert proxy.calls["failed_sql"] == 1
    assert proxy.calls["rollback"] >= 1
    assert "cannot rollback" in str(info.value)
    assert "planted on" in str(info.value.__cause__)
    assert len(_records(caplog)) == 1
    assert _completed(path, rid) is None


def test_f2_twin_interrupt_rolls_back(db):
    path, rid = db
    proxy = FailingVerbsConn(sqlite3.connect(str(path)), fail_sql_prefix=_VERB,
                             raise_on_sql=KeyboardInterrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            _complete(proxy, rid)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _completed(path, rid) is None


def test_single_failure_write_error_reraised_pin(db, caplog):
    """PIN (both trees): the write fails, the ROLLBACK works."""
    path, rid = db
    proxy = FailingVerbsConn(sqlite3.connect(str(path)), fail_sql_prefix=_VERB)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError, match="planted on"):
                _complete(proxy, rid)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.calls["rollback"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _records(caplog) == []
    assert _completed(path, rid) is None


def test_control_commits(db):
    path, rid = db
    proxy = FailingVerbsConn(sqlite3.connect(str(path)))
    try:
        _complete(proxy, rid)
        assert proxy.calls["execute:UPDATE"] == 1
        assert proxy.calls["execute:COMMIT"] == 1
    finally:
        proxy._real.close()
    assert _completed(path, rid) == "2026-05-02"


def test_refusal_single_failure_pin(db, caplog):
    """PIN (both trees): the not-found refusal raises into the handler; the
    ROLLBACK works -> the refusal's `ValueError` re-raised, no record."""
    path, _ = db
    proxy = FailingVerbsConn(sqlite3.connect(str(path)))
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError, match="not found"):
                _complete(proxy, 999_999)
        assert proxy.calls["rollback"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _records(caplog) == []
