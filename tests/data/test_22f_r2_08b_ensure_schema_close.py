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
