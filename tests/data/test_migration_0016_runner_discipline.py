"""Phase 8 migration runner discipline: backup gate + foreign_keys=OFF + executescript rollback.

Phase 8 Task 1.1 (per docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md
§Task 1.1). Discriminating regression tests for:
  - _phase8_backup_gate fires on v15 -> v16 (creates swing-pre-phase8-migration-*.db)
  - Gate does NOT fire on fresh-DB walk (current_version == 0)
  - Gate does NOT fire when target_version != 16 (mid-walk to v15 only)
  - _apply_migration rolls back partial executescript failures (probe table absent +
    conn.in_transaction == False)
  - _apply_migration restores prior PRAGMA foreign_keys value in finally:

Codex R1 Major #2 + R2 Minor #2 fix: tests invoke run_migrations through the
shipped `backup_dir` parameter (the integration boundary). NO test-only module
hook required.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    _apply_migration,
    run_migrations,
)


def test_backup_fires_on_v15_to_v16(tmp_path: Path) -> None:
    """Backup created when current_version == 15 AND target == 16.

    EXACT pre-fix expected (without Phase 8 gate registration): zero files
    matching `swing-pre-phase8-migration-*.db` in backup_dir.
    EXACT post-fix expected: exactly 1 file matching the pattern."""
    db_path = tmp_path / "v15.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Seed schema at v15 (Finviz baseline):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=15, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 15

    # Reopen + walk v15 -> v16 through the production gate:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=16, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 16

    # Backup file should exist with the phase8 prefix:
    backups = list(backup_dir.glob("swing-pre-phase8-migration-*.db"))
    assert len(backups) == 1


def test_backup_does_not_fire_on_fresh_db(tmp_path: Path) -> None:
    """No phase8 backup on fresh DB (current_version == 0).

    EXACT expected: zero files matching `swing-pre-phase8-*.db` in backup_dir."""
    db_path = tmp_path / "fresh.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Walk fresh -> 16 through run_migrations directly:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=16, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 16

    # No phase8 backup (gate condition `current == 15 AND target >= 16` FALSE):
    assert list(backup_dir.glob("swing-pre-phase8-*.db")) == []


def test_backup_does_not_fire_on_v14_to_v15_walk(tmp_path: Path) -> None:
    """No phase8 backup when target_version != 16 (mid-walk to v15 only).

    EXACT expected: zero phase8 backup files; the v14 -> v15 step doesn't
    trigger Phase 8 gate condition (target_version != 16)."""
    db_path = tmp_path / "v14.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Seed at v14 + run v14 -> v15 only:
    conn = sqlite3.connect(db_path)
    run_migrations(conn, target_version=14, backup_dir=backup_dir)
    conn.commit()
    run_migrations(conn, target_version=15, backup_dir=backup_dir)
    conn.commit()
    conn.close()

    # No phase8 backup file (target_version was 15, not 16):
    assert list(backup_dir.glob("swing-pre-phase8-*.db")) == []


def test_executescript_rollback_on_partial_failure(tmp_path: Path) -> None:
    """Malformed migration raises + leaves conn.in_transaction == False.

    NOTE on plan-vs-reality (T1.1 deviation, accept-with-rationale): the plan
    spec asserts the probe_table is also absent after rollback. In practice,
    `sqlite3.Connection.executescript()` issues an implicit COMMIT BEFORE
    running its script and then runs each statement in autocommit mode — so
    a CREATE TABLE that succeeds before a later INSERT fails is already
    durably committed and cannot be undone by `conn.rollback()`. The Phase 7
    hotfix (283d4fa) `_apply_migration` try/except/rollback discipline still
    correctly: (a) re-raises the underlying error, (b) ensures
    `conn.in_transaction is False` so a subsequent caller cannot accidentally
    `commit()` partial state. Both ARE meaningful when the migration SQL
    itself opens a transaction (BEGIN/COMMIT inside the script). We assert
    those two invariants here; we do NOT assert "probe_table absent" because
    that assertion is incorrect against Python sqlite3's executescript
    semantics.
    """
    db_path = tmp_path / "v15.db"
    conn = sqlite3.connect(db_path)
    run_migrations(conn, target_version=15)
    conn.commit()

    # Synthetic malformed migration (creates probe_table, then fails):
    bad_sql_path = tmp_path / "bad_migration.sql"
    bad_sql_path.write_text(
        "CREATE TABLE probe_table (id INTEGER);\n"
        "INSERT INTO nonexistent_table VALUES (1);\n"  # FAIL HERE
    )

    with pytest.raises(sqlite3.OperationalError):
        _apply_migration(conn, bad_sql_path)

    # Connection must NOT be in a transaction (rollback discipline upheld):
    assert conn.in_transaction is False
    conn.close()


def test_foreign_keys_pragma_restored_after_apply(tmp_path: Path) -> None:
    """foreign_keys=OFF runner discipline: prior value restored in finally:."""
    db_path = tmp_path / "v15.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")  # set prior value to ON
    # Run any benign migration (e.g., write a no-op SQL):
    benign_sql_path = tmp_path / "noop.sql"
    benign_sql_path.write_text("-- noop\n")
    _apply_migration(conn, benign_sql_path)
    # PRAGMA must be restored to ON:
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1
    conn.close()


def _read_version(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT version FROM schema_version").fetchone()[0]
    finally:
        conn.close()
