"""22-F T-F10 (C2-21, R3-02) -- D39 (S-D39) on `_apply_migration`'s rollback
(`db.py:572-577`, the `except Exception: conn.rollback(); raise`).

Instrument (plan T-F10): `open_connection_returning` patches
`swing.data.db.open_connection`, the MODULE GLOBAL `ensure_schema` resolves at
call time, with a `FailingVerbsConn` whose `executescript` first runs the real
`executescript("BEGIN;")` (the migration scripts open their own transaction;
this leaves one OPEN, as a mid-script failure does) and then raises.  Each
case drives `ensure_schema` on a v40 fixture (one migration, 0041, to apply)
and asserts the proxy recorded >= 1 `executescript` (and, where the table says
one runs, >= 1 `rollback()`): the did-it-fire rule.

* C2-21-a both fail (E1 from `executescript`, E2 from `rollback()`) -> pre: E2
  escapes from inside the `except` with `__cause__` None, no record; post: E2,
  `__cause__ is E1`, exactly one `MUST BE DISCARDED` record.
* C2-21-b F2 twin: `executescript` raises `KeyboardInterrupt` after the
  BEGIN, rollback works -> pre: `except Exception` does not run, so the
  proxy's `in_transaction` is True after the raise; post: False, and the
  `KeyboardInterrupt` re-raised.
* C2-21-c single failure (E1, rollback works) -> E1 re-raised, fresh read
  `schema_version` 40, on both trees (a PIN).
* C2-21-d CONTROL: pass-through proxy -> migrated to 41, on both trees.

These stop before the post-COMMIT `finally` PRAGMAs, which are B-04's.  No
clock is read by any assertion.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, open_connection, run_migrations
from tests._22f_proxies import FailingVerbsConn, open_connection_returning

_V_BEFORE = 40


@pytest.fixture
def v40(tmp_path: Path) -> Path:
    assert EXPECTED_SCHEMA_VERSION == _V_BEFORE + 1
    path = tmp_path / "swing.db"
    c = open_connection(path)
    try:
        run_migrations(c, target_version=_V_BEFORE, backup_dir=tmp_path / "bak")
    finally:
        c.close()
    return path


def _version(path: Path) -> int:
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return c.execute("SELECT version FROM schema_version").fetchone()[0]
    finally:
        c.close()


def _records(caplog):
    return [r for r in caplog.records if "MUST BE DISCARDED" in r.getMessage()]


def _mig(built: list) -> FailingVerbsConn:
    """The ONE proxy the migration ran on (a firing backup gate may open
    others through the same opener; they never run a script)."""
    ran = [p for p in built if p.calls["executescript"] >= 1]
    assert len(ran) == 1, [dict(p.calls) for p in built]
    return ran[0]


def _ensure(path: Path, tmp_path: Path):
    from swing.data.db import ensure_schema
    return ensure_schema(path, backup_dir=tmp_path / "bak")


def test_c2_21_a_both_fail_raises_cleanup_chained(v40, tmp_path, monkeypatch,
                                                  caplog):
    built = open_connection_returning(monkeypatch, lambda real: FailingVerbsConn(
        real, fail_executescript=sqlite3.OperationalError, fail_rollback=True))
    with caplog.at_level(logging.ERROR):
        with pytest.raises(sqlite3.OperationalError) as info:
            _ensure(v40, tmp_path)
    assert _mig(built).calls["rollback"] >= 1
    assert "cannot rollback" in str(info.value)
    assert isinstance(info.value.__cause__, sqlite3.OperationalError)
    assert "planted on executescript" in str(info.value.__cause__)
    assert len(_records(caplog)) == 1
    assert _version(v40) == _V_BEFORE


def test_c2_21_b_f2_twin_interrupt_rolls_back(v40, tmp_path, monkeypatch):
    built = open_connection_returning(monkeypatch, lambda real: FailingVerbsConn(
        real, fail_executescript=KeyboardInterrupt))
    try:
        with pytest.raises(KeyboardInterrupt):
            _ensure(v40, tmp_path)
        assert _mig(built).in_transaction is False
    finally:
        for p in built:
            p._real.close()
    assert _version(v40) == _V_BEFORE


def test_c2_21_c_single_failure_reraised_pin(v40, tmp_path, monkeypatch,
                                             caplog):
    built = open_connection_returning(monkeypatch, lambda real: FailingVerbsConn(
        real, fail_executescript=sqlite3.OperationalError))
    with caplog.at_level(logging.ERROR):
        with pytest.raises(sqlite3.OperationalError,
                           match="planted on executescript"):
            _ensure(v40, tmp_path)
    assert _mig(built).calls["rollback"] >= 1
    assert _records(caplog) == []
    assert _version(v40) == _V_BEFORE


def test_c2_21_d_control_migrates(v40, tmp_path, monkeypatch):
    built = open_connection_returning(monkeypatch,
                                      lambda real: FailingVerbsConn(real))
    conn = _ensure(v40, tmp_path)
    conn.close()
    assert _mig(built).calls["rollback"] == 0
    assert _version(v40) == EXPECTED_SCHEMA_VERSION
