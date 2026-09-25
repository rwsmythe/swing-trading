"""22-F T-G1 -- F4 close-after-durable on the CLI operator-record roots
(plan section 8; S-B02 via `swing/cli.py::_close_after_writes`).

Per root, three tests over the ROOT TABLE below (each row carries its opener
`target`, the name the root resolves AT CALL TIME, read from its source):

* G1-a -- the root's SUCCESS path with `conn.close()` failing
  (`FailingVerbsConn(fail_close=True)`: the real close runs, then the error).
  PRE-FIX: the close error escapes the `finally` -> exit != 0, a traceback,
  over a DURABLE write.  POST-FIX: exit 0, `WARN: the write IS recorded`,
  and a FRESH read shows the write.
* G1-b -- the root's typed REFUSAL path with the close failing (roots that
  have one).  PRE-FIX: the close error REPLACES the refusal text.
  POST-FIX: the refusal text + `the connection close also failed`, exit 1,
  nothing written.
* G1-c -- CONTROL: nothing durable, no refusal (the root's writer is
  replaced by a counting wrapper raising a planted `RuntimeError`), close
  fails.  BOTH TREES: the close error replaces the in-flight error, exactly
  as it always has (the byte-unchanged bare-close branch).

Did-it-fire (R3-01): every case asserts the proxies recorded >= 1 `close()`;
every G1-c asserts its writer wrapper was called once.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest

from swing.cli import main
from tests._22f_proxies import FailingVerbsConn, patch_conn_opener, raising
from tests.cli.test_cli_trade import _PRE_TRADE_OK_FLAGS, _setup

_WARN = "WARN: the write IS recorded; the connection close failed: "
_ALSO = "the connection close also failed"
_PLANTED = "planted on close"
_DB_CONNECT = "swing.data.db.connect"


def _db(tmp_path: Path) -> Path:
    return tmp_path / "home" / "swing-data" / "swing.db"


def _scalar(db_path: Path, sql: str, *params: Any) -> Any:
    c = sqlite3.connect(str(db_path))
    try:
        return c.execute(sql, params).fetchone()[0]
    finally:
        c.close()


@dataclass
class World:
    runner: Any
    cfg: Path
    db: Path
    extra: dict


@dataclass
class Root:
    id: str
    target: str
    world: Callable[[Path, Any], World]
    argv: Callable[[World], list]
    # a FRESH read that changes when the root's write lands
    probe: Callable[[World], Any]
    # the dotted name the root's writer is resolved by at call time (G1-c)
    writer: str
    refusal_argv: Callable[[World], list] | None = None
    refusal_text: str | None = None


# ---------------------------------------------------------------- worlds ---

def _trade_world(tmp_path: Path, _mp: Any) -> World:
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    assert r.exit_code == 0, r.output
    return World(runner, cfg, _db(tmp_path), {})


def _fills(w: World) -> int:
    return _scalar(w.db, "SELECT COUNT(*) FROM fills")


def _current_stop(w: World) -> float:
    return _scalar(w.db, "SELECT current_stop FROM trades WHERE id = 1")


# ------------------------------------------------------------ root table ---

ROOTS: list[Root] = [
    Root(
        id="trade-exit", target=_DB_CONNECT, world=_trade_world,
        argv=lambda w: ["--config", str(w.cfg), "trade", "exit",
                        "--trade-id", "1", "--exit-date", "2026-04-22",
                        "--exit-price", "200.0", "--shares", "2",
                        "--reason", "partial"],
        probe=_fills, writer="swing.trades.exit.record_exit",
        refusal_argv=lambda w: ["--config", str(w.cfg), "trade", "exit",
                                "--trade-id", "1", "--exit-date",
                                "2026-04-22", "--exit-price", "200.0",
                                "--shares", "50", "--reason", "target"],
        refusal_text="exceeds remaining",
    ),
    Root(
        id="trade-stop-adjust", target=_DB_CONNECT, world=_trade_world,
        argv=lambda w: ["--config", str(w.cfg), "trade", "stop-adjust",
                        "--trade-id", "1", "--new-stop", "175.0",
                        "--rationale", "manual-trail"],
        probe=_current_stop, writer="swing.trades.stop_adjust.adjust_stop",
        refusal_argv=lambda w: ["--config", str(w.cfg), "trade",
                                "stop-adjust", "--trade-id", "1",
                                "--new-stop", "165.0", "--rationale",
                                "manual-trail"],
        refusal_text="force",
    ),
]

_REFUSING = [r for r in ROOTS if r.refusal_argv is not None]


def _failing_close(monkeypatch, target: str) -> list:
    return patch_conn_opener(monkeypatch, target,
                             lambda real: FailingVerbsConn(real,
                                                           fail_close=True))


def _closes(built: list) -> int:
    return sum(p.calls["close"] for p in built)


@pytest.mark.parametrize("root", ROOTS, ids=[r.id for r in ROOTS])
def test_G1a_success_with_close_failure_exits_zero_and_warns(
        root: Root, tmp_path, monkeypatch):
    w = root.world(tmp_path, monkeypatch)
    before = root.probe(w)
    built = _failing_close(monkeypatch, root.target)
    result = w.runner.invoke(main, root.argv(w))
    assert _closes(built) >= 1
    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert _WARN in result.output
    assert _PLANTED in result.output
    assert root.probe(w) != before  # the write is durable (fresh read)


@pytest.mark.parametrize("root", _REFUSING, ids=[r.id for r in _REFUSING])
def test_G1b_refusal_with_close_failure_keeps_the_refusal(
        root: Root, tmp_path, monkeypatch):
    w = root.world(tmp_path, monkeypatch)
    before = root.probe(w)
    built = _failing_close(monkeypatch, root.target)
    result = w.runner.invoke(main, root.refusal_argv(w))
    assert _closes(built) >= 1
    assert result.exit_code == 1, (result.output, repr(result.exception))
    assert isinstance(result.exception, SystemExit)
    assert root.refusal_text in result.output
    assert _ALSO in result.output
    assert _PLANTED in result.output
    assert root.probe(w) == before  # nothing written


@pytest.mark.parametrize("root", ROOTS, ids=[r.id for r in ROOTS])
def test_G1c_control_nothing_durable_close_error_replaces_as_before(
        root: Root, tmp_path, monkeypatch):
    w = root.world(tmp_path, monkeypatch)
    before = root.probe(w)
    module_name, _, attr = root.writer.rpartition(".")
    wrapper = raising(RuntimeError("planted writer failure"))
    monkeypatch.setattr(module_name + "." + attr, wrapper)
    built = _failing_close(monkeypatch, root.target)
    result = w.runner.invoke(main, root.argv(w))
    assert wrapper.calls == 1
    assert _closes(built) >= 1
    assert isinstance(result.exception, sqlite3.OperationalError), (
        result.output, repr(result.exception))
    assert _PLANTED in str(result.exception)
    assert _WARN not in result.output
    assert root.probe(w) == before
