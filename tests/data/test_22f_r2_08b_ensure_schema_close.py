"""22-F R2-08(b) (Reviewer A round 2; CHARC-ruled, group 1: census row C2-21
"the close ... can raise") -- `ensure_schema`'s migration-error handler
closes its connection before re-raising.  PRE-FIX that close was bare
(`except Exception: conn.close(); raise`), so a failing close REPLACED the
migration's error.  POST-FIX the close is guarded: a close failure is logged
against the migration's error (one ERROR record; the S-D39 cleanup shape) and the
MIGRATION's error propagates; an INTERRUPT from the close is noted and
re-raised CHAINED from the migration's error (the R2 class ruling -- never
swallowed, never retyped).

Instrument: `open_connection_returning` (the module global `ensure_schema`
resolves at call time).  Only the FIRST connection opened -- `ensure_schema`'s
own; a firing backup gate opens later ones through the same name -- fails
its close; the script fails through `fail_executescript` (a BEGIN is left
open and the rollback works).  Every case asserts the failing close fired.
No clock is read by any assertion.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, open_connection, run_migrations
from tests._22f_proxies import FailingVerbsConn, open_connection_returning

_V_BEFORE = EXPECTED_SCHEMA_VERSION - 1


class _InterruptOnClose(FailingVerbsConn):
    def close(self) -> None:
        self.calls["close"] += 1
        self._real.close()
        raise KeyboardInterrupt("planted interrupt on close")


@pytest.fixture
def prior(tmp_path: Path) -> Path:
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


def _first_fails(monkeypatch, cls=FailingVerbsConn, **kw) -> list:
    count = {"n": 0}

    def _factory(real):
        count["n"] += 1
        if count["n"] == 1:
            return cls(real, fail_executescript=sqlite3.OperationalError, **kw)
        return FailingVerbsConn(real)
    return open_connection_returning(monkeypatch, _factory)


def _ensure(path: Path, tmp_path: Path):
    from swing.data.db import ensure_schema
    return ensure_schema(path, backup_dir=tmp_path / "bak2")


def test_r2_08b_close_failure_keeps_the_migration_error(prior, tmp_path,
                                                         monkeypatch, caplog):
    built = _first_fails(monkeypatch, fail_close=True)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(sqlite3.OperationalError) as info:
            _ensure(prior, tmp_path)
    assert built[0].calls["executescript"] >= 1  # did-it-fire (the script)
    assert built[0].calls["close"] == 1  # did-it-fire (the close)
    assert "planted on executescript" in str(info.value)
    assert [r for r in caplog.records
            if r.levelno == logging.ERROR
            and "planted on close" in r.getMessage()
            and "planted on executescript" in r.getMessage()]
    assert _version(prior) == _V_BEFORE


def test_r2_08b_interrupt_on_close_is_chained_from_the_migration_error(
        prior, tmp_path, monkeypatch):
    built = _first_fails(monkeypatch, cls=_InterruptOnClose)
    with pytest.raises(KeyboardInterrupt) as info:
        _ensure(prior, tmp_path)
    assert built[0].calls["close"] == 1  # did-it-fire
    assert isinstance(info.value.__cause__, sqlite3.OperationalError)
    assert "planted on executescript" in str(info.value.__cause__)
    assert _version(prior) == _V_BEFORE


class _TxAtClose(FailingVerbsConn):
    """Counts, in ``calls["open_tx_at_close"]``, a close of the REAL
    connection while it still held an open transaction."""

    def close(self) -> None:
        self.calls["open_tx_at_close"] += int(self._real.in_transaction)
        return super().close()


class _InterruptOnRollback(_TxAtClose):
    """``rollback()`` is INTERRUPTED: it raises ``KeyboardInterrupt`` WITHOUT
    rolling back, so the migration's transaction stays OPEN (R3-06)."""

    def rollback(self) -> None:
        self.calls["rollback"] += 1
        raise KeyboardInterrupt("planted interrupt on rollback")


def _first_script_fails(monkeypatch, cls, exc) -> list:
    """As ``_first_fails``, with the script's exception chosen by the test."""
    count = {"n": 0}

    def _factory(real):
        count["n"] += 1
        if count["n"] == 1:
            return cls(real, fail_executescript=exc)
        return FailingVerbsConn(real)
    return open_connection_returning(monkeypatch, _factory)


def _assert_real_closed(proxy) -> None:
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        proxy._real.execute("SELECT 1")


def test_r3_06_interrupt_in_the_migration_closes_the_connection(
        prior, tmp_path, monkeypatch):
    """22-F R3-06 (CHARC-ruled (a)): an interrupt ORIGINATING in the
    migration -- ``executescript`` opens a transaction and raises
    ``KeyboardInterrupt``; the rollback works -- still reaches the close, and
    the interrupt propagates unchanged.  PRE (``except Exception as
    migration_error``): the handler does not run for an interrupt, so the
    close count is 0 and the connection is left open."""
    built = _first_script_fails(monkeypatch, _TxAtClose, KeyboardInterrupt)
    try:
        with pytest.raises(KeyboardInterrupt,
                           match="planted on executescript") as info:
            _ensure(prior, tmp_path)
        assert built[0].calls["executescript"] == 1  # did-it-fire (script)
        assert built[0].calls["rollback"] == 1  # did-it-fire (rollback)
        assert built[0].calls["close"] == 1  # did-it-fire (the close)
        assert built[0].calls["open_tx_at_close"] == 0  # rolled back first
        _assert_real_closed(built[0])
        assert info.value.__cause__ is None
    finally:
        for p in built:
            p._real.close()
    assert _version(prior) == _V_BEFORE


def test_r3_06_interrupted_rollback_closes_the_connection(
        prior, tmp_path, monkeypatch, caplog):
    """22-F R3-06, the INTERRUPTED-ROLLBACK posture the reviewer named:
    ``executescript`` opens a transaction and fails; ``rollback()`` raises
    ``KeyboardInterrupt``, so the migration's transaction is still OPEN.  The
    interrupt escapes with its cause (the script's error, set by
    ``_apply_migration``'s ``raise cleanup_error from exc``) AND the close
    count is 1: the open transaction dies with the closed connection.  PRE:
    close count 0 -- the connection, transaction open, is reachable only
    through the traceback."""
    built = _first_script_fails(monkeypatch, _InterruptOnRollback,
                                sqlite3.OperationalError)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(KeyboardInterrupt,
                               match="planted interrupt on rollback") as info:
                _ensure(prior, tmp_path)
        assert built[0].calls["executescript"] == 1  # did-it-fire (script)
        assert built[0].calls["rollback"] == 1  # did-it-fire (interrupt)
        assert isinstance(info.value.__cause__, sqlite3.OperationalError)
        assert "planted on executescript" in str(info.value.__cause__)
        assert built[0].calls["close"] == 1  # did-it-fire (the close)
        assert built[0].calls["open_tx_at_close"] == 1  # the posture held
        _assert_real_closed(built[0])
        assert [r for r in caplog.records
                if "MUST BE DISCARDED" in r.getMessage()]
    finally:
        for p in built:
            p._real.close()
    assert _version(prior) == _V_BEFORE


def test_r2_08b_control_working_close_reraises_the_migration_error(
        prior, tmp_path, monkeypatch):
    """CONTROL (both trees): the close works -> the migration's error, no
    note."""
    built = _first_fails(monkeypatch)
    with pytest.raises(sqlite3.OperationalError,
                       match="planted on executescript") as info:
        _ensure(prior, tmp_path)
    assert built[0].calls["close"] == 1
    assert not getattr(info.value, "__notes__", [])
    assert _version(prior) == _V_BEFORE
