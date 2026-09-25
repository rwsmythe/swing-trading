"""22-F T-F11 (C2-22) -- `trade entry`'s close handler, the PRE-boundary
branch (`result is None`), gets S-R8 (RULING R8, 22-B).

Pre-fix, a typed refusal in flight (here `DuplicateOpenPositionError` -> its
`ClickException`, `cli.py`) with `conn.close()` ALSO failing: the close error
REPLACES the refusal, so the operator never hears why the entry was refused.
Post-fix (S-R8): `ClickException(f"{refusal}; the connection close also
failed: {safe_text(close_exc)}") from close_exc` -- the refusal text
survives, the close failure is named and chained, exit 1, nothing written.

Delivery: `patch_conn_opener` at `swing.data.db.connect` (`trade entry`
imports `connect` function-locally, plan section 0.4), with
`FailingVerbsConn(real, fail_close=True)` (the real close runs, then the
error); every case asserts >= 1 `close()` recorded (did-it-fire).  The world
is the 22-A3 CLI fixture (`test_cli_trade_entry_post_commit_warnings`); the
entry date is a literal, and no assertion reads the clock.
"""
from __future__ import annotations

import sqlite3

from swing.cli import main
from tests._22f_proxies import FailingVerbsConn, patch_conn_opener
from tests.cli.test_cli_trade_entry_post_commit_warnings import (
    _entry_argv,
    _setup,
    _trade_rows,
)

_REFUSAL = "Already an open position in AAPL"
_CLOSE = "the connection close also failed"


def _duplicate_world(tmp_path):
    runner, cfg = _setup(tmp_path)
    first = runner.invoke(main, _entry_argv(cfg))
    assert first.exit_code == 0, first.output
    return runner, cfg


def test_refusal_with_close_failure_keeps_the_refusal_text(tmp_path,
                                                           monkeypatch):
    """PRE-FIX: the close error replaces the refusal (no refusal text).
    POST-FIX: exit 1, the refusal text AND the close failure named."""
    runner, cfg = _duplicate_world(tmp_path)
    built = patch_conn_opener(monkeypatch, "swing.data.db.connect",
                              lambda real: FailingVerbsConn(real,
                                                            fail_close=True))
    r = runner.invoke(main, _entry_argv(cfg))
    assert sum(p.calls["close"] for p in built) >= 1
    assert r.exit_code == 1, (r.output, r.exception)
    assert _REFUSAL in r.output
    assert _CLOSE in r.output
    assert "planted on close" in r.output
    assert len(_trade_rows(cfg)) == 1


def test_refusal_with_close_failure_chains_the_close_error(tmp_path,
                                                           monkeypatch):
    """The raised `ClickException`'s `__cause__` is the close error
    (`standalone_mode=False` hands the exception back un-rendered)."""
    import click
    runner, cfg = _duplicate_world(tmp_path)
    built = patch_conn_opener(monkeypatch, "swing.data.db.connect",
                              lambda real: FailingVerbsConn(real,
                                                            fail_close=True))
    r = runner.invoke(main, _entry_argv(cfg), standalone_mode=False)
    assert sum(p.calls["close"] for p in built) >= 1
    assert isinstance(r.exception, click.ClickException), repr(r.exception)
    assert _REFUSAL in r.exception.format_message()
    assert isinstance(r.exception.__cause__, sqlite3.OperationalError)
    assert "planted on close" in str(r.exception.__cause__)
    assert len(_trade_rows(cfg)) == 1


def test_refusal_with_working_close_control(tmp_path, monkeypatch):
    """CONTROL (both trees): the close works -> the refusal alone, exit 1."""
    runner, cfg = _duplicate_world(tmp_path)
    built = patch_conn_opener(monkeypatch, "swing.data.db.connect",
                              lambda real: FailingVerbsConn(real))
    r = runner.invoke(main, _entry_argv(cfg))
    assert sum(p.calls["close"] for p in built) >= 1
    assert r.exit_code == 1, (r.output, r.exception)
    assert _REFUSAL in r.output
    assert _CLOSE not in r.output
    assert len(_trade_rows(cfg)) == 1
