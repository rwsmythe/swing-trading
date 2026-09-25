"""22-F T-F7 (C2-14) -- D39 (S-D39) on `risk_policy.py`'s
`supersede_active_policy` BEGIN site (census `:132/:212`; `:144/:227` on this
branch after T-D5).  `seed_initial_policy` (census `:407`) is DECLARED, not
fixed: it has no production caller (census C2-14).

The proxy is the `conn` argument.  BEGIN is ALREADY inside the try (not an
F1 row); the handler's `conn.rollback()` is UNGUARDED (a failing rollback
replaces the original).  Failing verbs, read from
`swing/data/repos/risk_policy.py`: the body's FIRST write,
`UPDATE risk_policy` (`update_policy_active_flag`, step 2), and
`INSERT INTO risk_policy` (`insert_policy`, step 4, after step 2 has already
deactivated the predecessor in-tx).  Every case asserts the proxy recorded
the verb (did-it-fire) and, on a failure, that a fresh read still shows the
seeded policy 1 as the one active row.  SS-4, by reading: the try body has
no in-try ROLLBACK; its refusals (`NoActivePolicyError`, the validator's
`ValueError`) raise into the same handler.  The clock the service reads
(`swing.trades.risk_policy.now_ms`, a module global resolved at call time)
is FROZEN after any wall-clock seed stamp the migrations write.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import FailingVerbsConn

_FROZEN_NOW = "2099-01-01T00:00:00.000"


@pytest.fixture(autouse=True)
def _frozen_clock(monkeypatch):
    import swing.trades.risk_policy as mod
    monkeypatch.setattr(mod, "now_ms", lambda: _FROZEN_NOW)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "t.db"
    ensure_schema(path).close()
    return path


def _supersede(conn):
    from swing.trades.risk_policy import supersede_active_policy
    return supersede_active_policy(
        conn, field_updates={"max_account_risk_per_trade_pct": 0.75},
        notes="22-F probe")


def _active(db: Path) -> list[tuple[int, float]]:
    c = sqlite3.connect(str(db))
    try:
        return c.execute(
            "SELECT policy_id, max_account_risk_per_trade_pct "
            "FROM risk_policy WHERE is_active = 1").fetchall()
    finally:
        c.close()


_VERBS = ("UPDATE risk_policy", "INSERT INTO risk_policy")


def _records(caplog):
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


@pytest.fixture
def seeded(db) -> list[tuple[int, float]]:
    rows = _active(db)
    assert len(rows) == 1 and rows[0][0] == 1, rows
    return rows


@pytest.mark.parametrize("verb", _VERBS)
def test_both_verbs_fail_raises_cleanup_chained(verb, db, seeded, caplog):
    """PRE-FIX: the CLEANUP error with `__cause__` None, no record.
    POST-FIX: the CLEANUP error, `__cause__` the write error, one record."""
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=verb,
                             fail_rollback=True)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                _supersede(proxy)
    finally:
        proxy._real.close()
    assert proxy.calls["failed_sql"] == 1
    assert proxy.calls["rollback"] >= 1
    assert "cannot rollback" in str(info.value)
    assert "planted on" in str(info.value.__cause__)
    assert len(_records(caplog)) == 1
    assert _active(db) == seeded


@pytest.mark.parametrize("verb", _VERBS)
def test_f2_twin_interrupt_rolls_back(verb, db, seeded):
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=verb,
                             raise_on_sql=KeyboardInterrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            _supersede(proxy)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _active(db) == seeded


@pytest.mark.parametrize("verb", _VERBS)
def test_single_failure_write_error_reraised_pin(verb, db, seeded, caplog):
    """PIN (both trees): the write fails, the rollback works."""
    proxy = FailingVerbsConn(sqlite3.connect(str(db)), fail_sql_prefix=verb)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError, match="planted on"):
                _supersede(proxy)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _records(caplog) == []
    assert _active(db) == seeded


@pytest.mark.parametrize("verb", _VERBS)
def test_control_commits(verb, db, seeded):
    proxy = FailingVerbsConn(sqlite3.connect(str(db)))
    try:
        new_id = _supersede(proxy)
        assert proxy.calls["commit"] >= 1
        assert proxy.calls["execute:" + verb.split()[0].upper()] >= 1
    finally:
        proxy._real.close()
    assert new_id == 2
    assert _active(db) == [(2, 0.75)]
