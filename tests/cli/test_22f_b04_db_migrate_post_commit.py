"""22-F T-F10 B-04 (R1-02, R51; plan 1.2 row 13) -- `swing db-migrate` when a
POST-COMMIT step of the migration runner fails.

`_apply_migration`'s `finally` restores two connection PRAGMAs AFTER the
script's COMMIT (`db.py`).  If that restore raises, the migration is DURABLE
but the exception escapes `ensure_schema`, and pre-fix `db_migrate` dies with
a traceback, skipping its tail (the gate-image check, the single-fire v17
ratification, the final echo).  The fix (boundary: `cli.py db_migrate`)
re-reads `schema_version` on a FRESH plain-`sqlite3` read-only connection:
at target -> a WARN line naming the version and the failure, a fresh
connection, and the existing tail; below target (or the re-read fails) ->
re-raise.

Instrument: `open_connection_returning` (the name `ensure_schema` resolves)
with `FailingVerbsConn(real, fail_after_executescript=("PRAGMA foreign_keys=",
n))`: the FIRST `PRAGMA foreign_keys=` after the proxy's n-th script has
RETURNED fails -- the restore of migration n.  Every case asserts the proxy
recorded the failing statement (did-it-fire); B-04-c asserts the failing
script.  `db_migrate`'s own `open_connection` is a module-level import in
`swing/cli.py`, so its probe and the fix's fresh connection are NOT proxied.
The config fixture keeps every path under `tmp_path` and patches both
`USERPROFILE` and `HOME`.  No assertion reads the clock.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import EXPECTED_SCHEMA_VERSION
from tests._22f_proxies import FailingVerbsConn, open_connection_returning
from tests.cli.test_db_migrate_single_backup import _build, _config

_WARN = "WARN: the migration IS applied (schema version"


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


def _fail_restore_after(monkeypatch, n: int) -> list:
    return open_connection_returning(monkeypatch, lambda real: FailingVerbsConn(
        real, fail_after_executescript=("PRAGMA foreign_keys=", n)))


def _fired(built: list, key: str) -> int:
    return sum(p.calls[key] for p in built)


def test_b04_a_restore_fails_at_target_warns_and_completes(world, monkeypatch):
    _build(world["db"], EXPECTED_SCHEMA_VERSION - 1)
    built = _fail_restore_after(monkeypatch, 1)
    r = _migrate(world)
    assert _fired(built, "failed_after_executescript") == 1
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION
    assert r.exit_code == 0, (r.output, r.exception)
    assert f"{_WARN} {EXPECTED_SCHEMA_VERSION})" in r.output
    assert "planted on PRAGMA foreign_keys=" in r.output
    assert f"schema version {EXPECTED_SCHEMA_VERSION}" in r.output.split(_WARN)[1]
    assert f"DB at {world['db']} - schema version {EXPECTED_SCHEMA_VERSION}" in (
        r.output)


def test_b04_b_restore_fails_below_target_reraises(world, monkeypatch):
    """PIN (both trees): the chain stops below target -> re-raised, exit != 0,
    no WARN."""
    _build(world["db"], EXPECTED_SCHEMA_VERSION - 2)
    built = _fail_restore_after(monkeypatch, 1)
    r = _migrate(world)
    assert _fired(built, "failed_after_executescript") == 1
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION - 1
    assert r.exit_code != 0
    assert isinstance(r.exception, sqlite3.OperationalError)
    assert "planted on PRAGMA foreign_keys=" in str(r.exception)
    assert _WARN not in r.output


def test_b04_c_control_failure_before_commit_no_warn(world, monkeypatch):
    """CONTROL (both trees): the SCRIPT fails before any COMMIT -> exit != 0,
    version unchanged, no WARN."""
    _build(world["db"], EXPECTED_SCHEMA_VERSION - 1)
    built = open_connection_returning(monkeypatch, lambda real: FailingVerbsConn(
        real, fail_executescript=sqlite3.OperationalError))
    r = _migrate(world)
    assert _fired(built, "executescript") >= 1
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION - 1
    assert r.exit_code != 0
    assert _WARN not in r.output


def test_b04_d_tail_continues_the_v17_ratification_runs_once(world, monkeypatch):
    """From v16, the LAST restore (migration 41's) fails.  Pre: the raise
    escapes before the tail, so the single-fire v17 ratification never runs.
    Post: it runs exactly once, and the WARN line precedes the final echo."""
    import swing.trades.risk_policy as rp
    _build(world["db"], 16)
    n = EXPECTED_SCHEMA_VERSION - 16
    calls: list[int] = []
    real_ratify = rp.ratify_seed_from_cfg_on_v17_landing

    def spy(conn, cfg):
        calls.append(1)
        return real_ratify(conn, cfg)

    monkeypatch.setattr(rp, "ratify_seed_from_cfg_on_v17_landing", spy)
    built = _fail_restore_after(monkeypatch, n)
    r = _migrate(world)
    assert _fired(built, "failed_after_executescript") == 1
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION
    assert calls == [1]
    assert r.exit_code == 0, (r.output, r.exception)
    final = f"DB at {world['db']} - schema version {EXPECTED_SCHEMA_VERSION}"
    assert r.output.index(_WARN) < r.output.index(final)


# -- R1-03 (Reviewer A round 1): the read-only witness's CLOSE fails ---------
# PRE-FIX `applied` was bound inside the try whose `finally` closed the
# witness, so a failing `_ro.close()` reset `applied` to None and the command
# RE-RAISED over a migration that the witness had just read as applied (the
# tail skipped, exit != 0).  POST-FIX `applied` comes from the query alone; a
# failing witness close is contained (an ERROR record + a WARN line).


def _fail_witness_close(monkeypatch) -> list:
    """Wrap the name `db_migrate` resolves at call time
    (`swing.cli.open_connection`); only the `mode=ro` URI open is proxied."""
    import swing.cli as cli_mod
    real_open = cli_mod.open_connection
    built: list = []

    def _open(target, *args, **kwargs):
        conn = real_open(target, *args, **kwargs)
        if kwargs.get("uri") and "mode=ro" in str(target):
            proxy = FailingVerbsConn(conn, fail_close=True)
            built.append(proxy)
            return proxy
        return conn

    monkeypatch.setattr(cli_mod, "open_connection", _open)
    return built


def test_r1_03_witness_close_fails_at_target_still_completes(world,
                                                             monkeypatch,
                                                             caplog):
    import logging
    _build(world["db"], EXPECTED_SCHEMA_VERSION - 1)
    built = _fail_restore_after(monkeypatch, 1)
    witnesses = _fail_witness_close(monkeypatch)
    with caplog.at_level(logging.ERROR):
        r = _migrate(world)
    assert _fired(built, "failed_after_executescript") == 1
    assert len(witnesses) == 1 and witnesses[0].calls["close"] == 1
    assert witnesses[0].calls["execute:SELECT"] == 1
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION
    assert r.exit_code == 0, (r.output, r.exception)
    assert f"{_WARN} {EXPECTED_SCHEMA_VERSION})" in r.output
    assert "planted on close" in r.output
    assert f"DB at {world['db']} - schema version {EXPECTED_SCHEMA_VERSION}" in (
        r.output)
    assert any("planted on close" in rec.getMessage()
               for rec in caplog.records)


def test_r1_03_witness_close_fails_below_target_still_reraises(world,
                                                               monkeypatch):
    """PIN (both trees): below target the original error is re-raised."""
    _build(world["db"], EXPECTED_SCHEMA_VERSION - 2)
    built = _fail_restore_after(monkeypatch, 1)
    witnesses = _fail_witness_close(monkeypatch)
    r = _migrate(world)
    assert _fired(built, "failed_after_executescript") == 1
    assert len(witnesses) == 1 and witnesses[0].calls["close"] == 1
    assert r.exit_code != 0
    assert isinstance(r.exception, sqlite3.OperationalError)
    assert "planted on PRAGMA foreign_keys=" in str(r.exception)
    assert _WARN not in r.output


# -- R2-02 (Reviewer A round 2; CHARC's class ruling): an INTERRUPT from the
# witness's close.  PRE-FIX (R1-03 caught `Exception`) the interrupt escaped
# from the close IN PLACE of the post-commit error, unchained and unrecorded.
# POST-FIX it is recorded and re-raised CHAINED from the post-commit error.
# That the interrupt still SKIPS the tail is pre-arc for any interrupt
# between the COMMIT and the ratification (plan AL-11).  click's standalone
# mode would turn the interrupt into "Aborted!"; `standalone_mode=False`
# surfaces it as `Abort` whose `__cause__` is the interrupt.
class _InterruptOnClose(FailingVerbsConn):
    def close(self) -> None:
        self.calls["close"] += 1
        self._real.close()
        raise KeyboardInterrupt("planted interrupt on close")


def test_r2_02_witness_close_interrupt_is_chained_from_the_post_commit_error(
        world, monkeypatch, caplog):
    import logging

    import click

    import swing.cli as cli_mod
    _build(world["db"], EXPECTED_SCHEMA_VERSION - 1)
    built = _fail_restore_after(monkeypatch, 1)
    real_open = cli_mod.open_connection
    witnesses: list = []

    def _open(target, *args, **kwargs):
        conn = real_open(target, *args, **kwargs)
        if kwargs.get("uri") and "mode=ro" in str(target):
            proxy = _InterruptOnClose(conn)
            witnesses.append(proxy)
            return proxy
        return conn

    monkeypatch.setattr(cli_mod, "open_connection", _open)
    with caplog.at_level(logging.ERROR):
        r = CliRunner().invoke(main, ["--config", str(world["cfg"]),
                                      "db-migrate"], standalone_mode=False)
    assert _fired(built, "failed_after_executescript") == 1
    assert len(witnesses) == 1 and witnesses[0].calls["close"] == 1
    assert isinstance(r.exception, click.exceptions.Abort), repr(r.exception)
    interrupt = r.exception.__cause__
    assert isinstance(interrupt, KeyboardInterrupt), repr(interrupt)
    assert isinstance(interrupt.__cause__, sqlite3.OperationalError)
    assert "planted on PRAGMA foreign_keys=" in str(interrupt.__cause__)
    assert any("interrupted" in rec.getMessage().lower()
               and "planted on PRAGMA foreign_keys=" in rec.getMessage()
               for rec in caplog.records)
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION


# -- R3-02 (CHARC's Round 3 ruling, item 2, option (a)): an INTERRUPT from a
# post-COMMIT restore at target.  R2-03 re-raises it out of
# `_apply_migration`; PRE-FIX the B-04 `except BaseException` then turned it
# into the WARN path, ran the tail (the single-fire v17 ratification
# included) and exited 0 -- the Ctrl-C swallowed one frame outward.
# POST-FIX the witness still runs and the durable WARN still prints (the
# operator who interrupted learns the version is durable), then the
# interrupt is re-raised BARE and the tail is skipped (plan AL-11).
def test_r3_02_restore_interrupt_at_target_warns_then_aborts_skipping_tail(
        world, monkeypatch):
    import swing.trades.risk_policy as rp
    _build(world["db"], 16)
    n = EXPECTED_SCHEMA_VERSION - 16
    calls: list[int] = []
    real_ratify = rp.ratify_seed_from_cfg_on_v17_landing

    def spy(conn, cfg):
        calls.append(1)
        return real_ratify(conn, cfg)

    monkeypatch.setattr(rp, "ratify_seed_from_cfg_on_v17_landing", spy)
    built = open_connection_returning(monkeypatch, lambda real: FailingVerbsConn(
        real, fail_after_executescript=("PRAGMA foreign_keys=", n),
        raise_on_sql=KeyboardInterrupt))
    r = _migrate(world)
    assert _fired(built, "failed_after_executescript") == 1  # did-it-fire
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION
    assert r.exit_code != 0, (r.output, r.exception)
    assert "Aborted!" in r.output
    assert f"{_WARN} {EXPECTED_SCHEMA_VERSION})" in r.output
    assert "KeyboardInterrupt" in r.output.split(_WARN)[1]
    assert calls == []  # the tail (the v17 ratification) was skipped
    assert f"DB at {world['db']} - schema version" not in r.output
