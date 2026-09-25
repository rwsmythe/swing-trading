"""22-F T-F7 (C2-12) -- D39 (S-D39) on `daily_management.py`'s one BEGIN
site: `record_event_log` (`:823/:935`).

The proxy is the `conn` argument.  The failing verb is
`INSERT INTO daily_management_records` (read from
`swing/data/repos/daily_management.py:insert_event_log`), driven down two
paths: `stop_changed=0` (the insert is the body's FIRST write) and
`stop_changed=1` (the insert fails AFTER `update_stop_with_event` has already
moved `trades.current_stop` inside the transaction -- a partial mutation the
rollback must discard).  Every case asserts the proxy recorded the verb
(did-it-fire).  The row is F1 (BEGIN outside the try) and UNGUARDED pre-fix
(a failing `conn.rollback()` replaces the write error).  SS-4, by reading:
the try body issues no in-try ROLLBACK; its refusals (`ValueError`,
`ValidationException`) raise into the same handler.  No clock is read: every
timestamp is a literal.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import FailingVerbsConn

_VERB = "INSERT INTO daily_management_records"


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.db"
    conn = ensure_schema(path)
    try:
        conn.execute(
            "INSERT INTO trades "
            "(id, ticker, entry_date, entry_price, initial_shares, "
            " initial_stop, current_stop, state, trade_origin, "
            " pre_trade_locked_at, current_size, current_avg_cost) "
            "VALUES (1, 'DHC', '2026-05-01', 100.0, 50, 90.0, 92.0, "
            "'managing', 'manual_off_pipeline', '2026-05-01T09:30:00', "
            "50.0, 100.0)")
        conn.commit()
    finally:
        conn.close()
    return path


def _request(stop_changed: int):
    from swing.trades.daily_management import EventLogRequest
    return EventLogRequest(
        trade_id=1, review_date="2026-05-07",
        data_asof_session="2026-05-07", created_at="2026-05-07T18:00:00",
        mfe_mae_precision_level="daily_approximate",
        stop_changed=stop_changed,
        prior_stop=92.0 if stop_changed else None,
        new_stop=95.0 if stop_changed else None,
        stop_change_reason="raise to breakeven-ish" if stop_changed else None,
        action_taken="hold", action_reason=None, rule_violation_suspected=0,
        emotional_state='["calm"]', thesis_status=None,
        management_notes=None)


def _call(stop_changed: int):
    def _run(conn):
        from swing.trades.daily_management import record_event_log
        return record_event_log(conn, trade_id=1,
                                req=_request(stop_changed))
    return _run


# path -> (call, state after a CONTROL commit: (records, current_stop))
_PATHS = {
    "no_stop_change": (_call(0), (1, 92.0)),
    "stop_change_partial_write": (_call(1), (1, 95.0)),
}
_UNTOUCHED = (0, 92.0)


def _state(db: Path) -> tuple[int, float]:
    c = sqlite3.connect(str(db))
    try:
        n = c.execute("SELECT COUNT(*) FROM daily_management_records "
                      "WHERE trade_id = 1").fetchone()[0]
        stop = c.execute("SELECT current_stop FROM trades WHERE id = 1"
                         ).fetchone()[0]
        return n, stop
    finally:
        c.close()


def _records(caplog):
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_both_verbs_fail_raises_cleanup_chained(path, db, caplog):
    """PRE-FIX: the CLEANUP error with `__cause__` None, no record.
    POST-FIX: the CLEANUP error, `__cause__` the write error, one record."""
    call, _ = _PATHS[path]
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=_VERB,
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
    assert _state(db) == _UNTOUCHED


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_f2_twin_interrupt_rolls_back(path, db):
    call, _ = _PATHS[path]
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=_VERB,
                             raise_on_sql=KeyboardInterrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            call(proxy)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _state(db) == _UNTOUCHED


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_single_failure_write_error_reraised_pin(path, db, caplog):
    """PIN (both trees): the write fails, the rollback works."""
    call, _ = _PATHS[path]
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=_VERB)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError, match="planted on"):
                call(proxy)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _records(caplog) == []
    assert _state(db) == _UNTOUCHED


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_control_commits(path, db):
    call, committed = _PATHS[path]
    proxy = FailingVerbsConn(sqlite3.connect(str(db)))
    try:
        call(proxy)
        assert proxy.calls["commit"] >= 1
        assert proxy.calls["execute:INSERT"] >= 1
    finally:
        proxy._real.close()
    assert _state(db) == committed


# -- R1-02 (Reviewer A round 1; C2-12's COMMIT in the `else:` clause) --------
# The COMMIT is a write verb of the transaction this function owns: a failing
# COMMIT leaves the transaction OPEN.  PRE-FIX the COMMIT sat in `else:`,
# outside the guarded try, so its failure escaped with no rollback (the
# connection left in_transaction) and a second, failing rollback was never
# attempted.  POST-FIX the COMMIT is inside the guarded try.


class _FailingCommitConn(FailingVerbsConn):
    """`commit()` raises WITHOUT committing (the transaction stays open)."""

    def commit(self) -> None:
        self.calls["commit"] += 1
        raise sqlite3.OperationalError("cannot commit (planted on commit)")


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_r1_02_commit_failure_rolls_back_and_reraises(path, db, caplog):
    """PRE-FIX: the commit error escapes, rollback NOT called, the
    transaction left open.  POST-FIX: rolled back, commit error re-raised,
    no MUST-BE-DISCARDED record."""
    call, _ = _PATHS[path]
    proxy = _FailingCommitConn(sqlite3.connect(str(db)))
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError,
                               match="planted on commit"):
                call(proxy)
        assert proxy.calls["commit"] == 1
        assert proxy.calls["rollback"] >= 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _records(caplog) == []
    assert _state(db) == _UNTOUCHED


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_r1_02_commit_and_rollback_fail_raises_cleanup_chained(path, db,
                                                                caplog):
    """PRE-FIX: the COMMIT error, no rollback attempted, no record.
    POST-FIX: the CLEANUP error chained from the commit error, one
    MUST-BE-DISCARDED record."""
    call, _ = _PATHS[path]
    proxy = _FailingCommitConn(sqlite3.connect(str(db)), fail_rollback=True)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                call(proxy)
        assert proxy.calls["commit"] == 1
        assert proxy.calls["rollback"] >= 1
    finally:
        proxy._real.close()
    assert "cannot rollback" in str(info.value)
    assert "planted on commit" in str(info.value.__cause__)
    assert len(_records(caplog)) == 1
    assert _state(db) == _UNTOUCHED
