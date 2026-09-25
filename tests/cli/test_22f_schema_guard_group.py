"""22-F T-C2 -- F-F7 CLI half (C1-14): `SchemaVersionMismatchError` becomes a
typed `Error: ...` at the root group (S-GROUP: a `click.Group` subclass whose
`invoke` catches ONLY that type), never a traceback.  `db-migrate` itself is
untouched (it reaches `ensure_schema`, not the guarded `connect`).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config
from tests.cli.test_cli_trade import _setup


def _db(tmp_path: Path) -> Path:
    return tmp_path / "home" / "swing-data" / "swing.db"


def _set_version(db_path: Path, version: int) -> None:
    c = sqlite3.connect(str(db_path))
    try:
        c.execute("UPDATE schema_version SET version = ?", (version,))
        c.commit()
    finally:
        c.close()


def _version(db_path: Path) -> int:
    c = sqlite3.connect(str(db_path))
    try:
        return c.execute("SELECT version FROM schema_version").fetchone()[0]
    finally:
        c.close()


def _assert_typed(result, needle: str) -> None:
    assert isinstance(result.exception, SystemExit), (
        repr(result.exception), result.output)
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert result.output.startswith("Error: "), result.output
    assert needle in result.output, result.output


def test_C2a_stale_schema_on_a_connect_command_is_typed(tmp_path):
    """C2-a. `trade list` calls `swing.data.db.connect` (function-local
    import).  PRE-FIX: `result.exception` is `SchemaVersionMismatchError`
    (a traceback).  POST-FIX: exit 1, `Error: ... swing db-migrate`."""
    runner, cfg = _setup(tmp_path)
    _set_version(_db(tmp_path), 40)
    result = runner.invoke(main, ["--config", str(cfg), "trade", "list"])
    _assert_typed(result, "swing db-migrate")


def test_C2b_a_two_level_nested_command_is_typed_too(tmp_path):
    """C2-b. `journal discrepancy override-correction` sits two groups
    below the root; the exception propagates through the root group's
    `invoke` (Click runs nested invocations inside it).  PRE-FIX:
    traceback.  POST-FIX: exit 1 typed."""
    runner, cfg = _setup(tmp_path)
    _set_version(_db(tmp_path), 40)
    result = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "override-correction",
        "1", "--truth-value", "{}", "--reason", "x", "--force"])
    _assert_typed(result, "swing db-migrate")


def test_C2c_db_migrate_still_migrates_a_stale_db(tmp_path):
    """C2-c (R29). A DB genuinely migrated only to 40 is migrated to HEAD by
    `db-migrate`, exit 0, on both trees -- the guard must not intercept the
    one command that repairs the state it reports."""
    from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    db = _db(tmp_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        run_migrations(conn, target_version=40, backup_dir=tmp_path)
    finally:
        conn.close()
    assert _version(db) == 40
    result = CliRunner().invoke(main, ["--config", str(cfg), "db-migrate"])
    assert result.exit_code == 0, (repr(result.exception), result.output)
    assert _version(db) == EXPECTED_SCHEMA_VERSION


def test_C2d_control_other_exceptions_still_escape(tmp_path, monkeypatch):
    """C2-d CONTROL: the group catches NOTHING else -- a `ValueError`
    planted at `swing.data.db.connect` (what `trade list`'s function-local
    import resolves per call) still escapes, both trees."""
    from tests._22f_proxies import raising
    runner, cfg = _setup(tmp_path)
    planted = raising(ValueError("planted other"))
    monkeypatch.setattr("swing.data.db.connect", planted)
    result = runner.invoke(main, ["--config", str(cfg), "trade", "list"])
    assert planted.calls >= 1  # did-it-fire
    assert isinstance(result.exception, ValueError), repr(result.exception)


def test_C2e_missing_db_file_is_typed(tmp_path):
    """C2-e. `connect` raises the same type for a missing DB file
    (`db.py`, "DB not found ... Run: swing db-migrate").  PRE-FIX:
    traceback.  POST-FIX: exit 1, typed."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    assert not _db(tmp_path).exists()
    result = CliRunner().invoke(main, ["--config", str(cfg), "trade", "list"])
    _assert_typed(result, "Run: swing db-migrate")
