"""CLI: swing db-backup [--force]."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from swing.data.backup import compute_backup_destination
from swing.data.db import ensure_schema


def _setup(tmp_path: Path) -> tuple[Path, "object"]:
    """Build a project + ensured-schema DB and return (cfg_path, cfg)."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    from swing.config import load
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg_path, cfg


def test_db_backup_creates_weekly_snapshot_when_needed(tmp_path: Path):
    """Default invocation: no backup exists for current week → backup is made."""
    cfg_path, cfg = _setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-backup"])
    assert result.exit_code == 0, result.output

    expected = compute_backup_destination(datetime.now(), cfg.paths.backups_dir)
    assert expected.exists(), f"missing backup at {expected}\noutput: {result.output}"
    assert str(expected) in result.output or expected.name in result.output


def test_db_backup_skips_when_current_week_present(tmp_path: Path):
    """Default invocation when this week's backup exists → 'no backup needed'."""
    cfg_path, cfg = _setup(tmp_path)
    cfg.paths.backups_dir.mkdir(parents=True, exist_ok=True)
    placeholder = compute_backup_destination(datetime.now(), cfg.paths.backups_dir)
    placeholder.write_bytes(b"sentinel")

    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-backup"])
    assert result.exit_code == 0, result.output
    assert "no backup needed" in result.output.lower()
    # Bytes unchanged — no copy happened.
    assert placeholder.read_bytes() == b"sentinel"


def test_db_backup_force_overwrites_current_week(tmp_path: Path):
    """--force replaces an existing current-week backup with a fresh copy."""
    cfg_path, cfg = _setup(tmp_path)
    cfg.paths.backups_dir.mkdir(parents=True, exist_ok=True)
    placeholder = compute_backup_destination(datetime.now(), cfg.paths.backups_dir)
    placeholder.write_bytes(b"sentinel")

    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-backup", "--force"])
    assert result.exit_code == 0, result.output
    # The placeholder was replaced — verify the result is a real SQLite DB now.
    conn = sqlite3.connect(placeholder)
    try:
        # ensure_schema created schema_version; valid SQLite DB will have it.
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        assert row is not None
    finally:
        conn.close()


def test_db_backup_force_creates_when_no_existing_backup(tmp_path: Path):
    """--force still works on a fresh dest dir."""
    cfg_path, cfg = _setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-backup", "--force"])
    assert result.exit_code == 0, result.output
    expected = compute_backup_destination(datetime.now(), cfg.paths.backups_dir)
    assert expected.exists()


def test_db_backup_invokes_prune_after_creating(tmp_path: Path, monkeypatch):
    """After creating the backup, the CLI prunes to keep=12. Verify wired."""
    cfg_path, cfg = _setup(tmp_path)
    cfg.paths.backups_dir.mkdir(parents=True, exist_ok=True)
    # Seed 14 weekly stubs from earlier weeks — pruning should drop the 2 oldest.
    for w in range(1, 15):
        if w == datetime.now().isocalendar().week:
            # Skip current week so the new backup is actually created.
            continue
        (cfg.paths.backups_dir / f"swing-2026{w:02d}.db").write_bytes(b"x")

    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-backup", "--force"])
    assert result.exit_code == 0, result.output

    # After force-backup we have current week + 13 older weeks = 14 total.
    # Pruning keep=12 leaves 12. So 2 deletions occurred.
    weekly = sorted(p.name for p in cfg.paths.backups_dir.glob("swing-*.db"))
    assert len(weekly) == 12, f"unexpected count after prune: {weekly}"


def test_db_backup_missing_db_exits_clean(tmp_path: Path):
    """If the DB does not exist, CLI prints a clear message and exits non-zero
    rather than producing a misleading 'success'."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    # No ensure_schema call → DB file doesn't exist.
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-backup"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "does not exist" in result.output.lower()
