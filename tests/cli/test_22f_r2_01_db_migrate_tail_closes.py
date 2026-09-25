"""22-F R2-01 (Reviewer A round 2; CHARC-ruled, group 1: census row C2-21
BINDS -- "the close and the echo can each raise ... the two-durability-facts
close handler (B-02) applied runner-wide") -- `swing db-migrate`'s TAIL
closes.

* (i) the FINAL close after a migration that this invocation APPLIED: a
  close failure is contained -> the `WARN: the write IS recorded ...` line,
  the final "DB at" echo, exit 0.  PRE-FIX the bare `conn.close()` raised,
  exit 1, and the final echo never ran -- over a durable version.
* (i') CONTROL / PIN (both trees): already at HEAD, NOTHING was migrated by
  this invocation -> the nothing-durable branch, the pre-arc bare close: the
  close error propagates and NO "IS recorded" text (R1-05's discriminator;
  the reading is reported with the encoding in the exec ledger).
* (ii) the v17-ratification refusal with a failing close: the refusal
  SURVIVES, the close failure is named in it and chained (S-R8).  PRE-FIX
  the bare `conn.close()` inside the handler raised its own error IN PLACE
  of the refusal.

Instrument: `swing.cli.ensure_schema` (the module-level name `db_migrate`
resolves at call time) is wrapped to return a `FailingVerbsConn(real,
fail_close=True)`; every case asserts the proxy's close fired.  The config
fixture keeps every path under `tmp_path` and patches both `USERPROFILE` and
`HOME`.  No assertion reads the clock.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import EXPECTED_SCHEMA_VERSION
from tests._22f_proxies import FailingVerbsConn, raising
from tests.cli.test_db_migrate_single_backup import _build, _config

_WARN = "WARN: the write IS recorded; the connection close failed: "
_ALSO = "the connection close also failed"
_PLANTED = "planted on close"
_RATIFY = "Phase 9 seed ratification failed"


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "project").mkdir()
    (tmp_path / "home").mkdir()
    cfg = _config(tmp_path / "project", tmp_path / "home")
    return {"cfg": cfg, "db": tmp_path / "home" / "swing-data" / "swing.db"}


def _version(db: Path) -> int:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return int(c.execute("SELECT version FROM schema_version").fetchone()[0])
    finally:
        c.close()


def _migrate(world):
    return CliRunner().invoke(main, ["--config", str(world["cfg"]), "db-migrate"])


def _failing_tail_close(monkeypatch) -> list:
    import swing.cli as cli_mod
    real = cli_mod.ensure_schema
    built: list = []

    def _ensure(*args, **kwargs):
        proxy = FailingVerbsConn(real(*args, **kwargs), fail_close=True)
        built.append(proxy)
        return proxy

    monkeypatch.setattr(cli_mod, "ensure_schema", _ensure)
    return built


def test_r2_01_i_final_close_fails_after_applied_migration_warns(
        world, monkeypatch):
    _build(world["db"], EXPECTED_SCHEMA_VERSION - 1)
    built = _failing_tail_close(monkeypatch)
    r = _migrate(world)
    assert len(built) == 1 and built[0].calls["close"] == 1  # did-it-fire
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION
    assert r.exit_code == 0, (r.output, repr(r.exception))
    assert _WARN in r.output
    assert _PLANTED in r.output
    assert (f"DB at {world['db']} - schema version {EXPECTED_SCHEMA_VERSION}"
            in r.output)


def test_r2_01_i_control_at_head_nothing_migrated_close_error_propagates(
        world, monkeypatch):
    """PIN (both trees): nothing migrated by this invocation -> the pre-arc
    bare close; the close error propagates, no "IS recorded" text."""
    _build(world["db"], EXPECTED_SCHEMA_VERSION)
    built = _failing_tail_close(monkeypatch)
    r = _migrate(world)
    assert len(built) == 1 and built[0].calls["close"] == 1  # did-it-fire
    assert "nothing to migrate" in r.output
    assert isinstance(r.exception, sqlite3.OperationalError), (
        r.output, repr(r.exception))
    assert _PLANTED in str(r.exception)
    assert "IS recorded" not in r.output


def test_r2_01_ii_ratification_refusal_survives_a_failing_close(
        world, monkeypatch):
    import swing.trades.risk_policy as rp
    _build(world["db"], 16)
    planted = raising(ValueError("planted ratification failure"))
    monkeypatch.setattr(rp, "ratify_seed_from_cfg_on_v17_landing", planted)
    built = _failing_tail_close(monkeypatch)
    r = _migrate(world)
    assert planted.calls == 1  # did-it-fire (the writer)
    assert len(built) == 1 and built[0].calls["close"] == 1  # did-it-fire
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION
    assert r.exit_code == 1, (r.output, repr(r.exception))
    assert isinstance(r.exception, SystemExit)
    assert _RATIFY in r.output
    assert "planted ratification failure" in r.output
    assert _ALSO in r.output
    assert _PLANTED in r.output


def test_r2_01_ii_control_ratification_refusal_with_working_close(
        world, monkeypatch):
    """CONTROL (both trees): the refusal alone, exit 1, no close text."""
    import swing.trades.risk_policy as rp
    _build(world["db"], 16)
    planted = raising(ValueError("planted ratification failure"))
    monkeypatch.setattr(rp, "ratify_seed_from_cfg_on_v17_landing", planted)
    r = _migrate(world)
    assert planted.calls == 1
    assert r.exit_code == 1, (r.output, repr(r.exception))
    assert _RATIFY in r.output
    assert _ALSO not in r.output
