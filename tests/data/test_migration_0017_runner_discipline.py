"""Phase 9 T-A.2 — migration 0017 runner discipline regression tests.

Mirrors Phase 8 ``test_migration_0016_runner_discipline.py`` for the
v16 → v17 step. Discriminating tests for:

  - ``_phase9_backup_gate`` fires on v16 → v17
    (creates ``swing-pre-phase9-migration-*.db``).
  - Gate does NOT fire on fresh-DB walk (current_version == 0).
  - Gate does NOT fire when target_version != 17 (mid-walk to v16 only).
  - ``_apply_migration`` rolls back partial executescript failures
    (conn.in_transaction == False; Phase 7 Sub-A R1 M3 lesson; Phase 8
    plan-template T1.1 deviation accept-with-rationale on probe-table
    absence — see Phase 8 test for reasoning, inherited here verbatim).
  - ``_apply_migration`` restores prior PRAGMA foreign_keys value in
    ``finally:`` (Phase 7 hotfix 283d4fa).

Codex R1 Major #2 + R2 Minor #2 fix (inherited from Phase 8): tests invoke
``run_migrations`` through the shipped ``backup_dir`` parameter (the
integration boundary). NO test-only module hook required.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    _apply_migration,
    run_migrations,
)


def test_backup_fires_on_v16_to_v17(tmp_path: Path) -> None:
    """Backup created when current_version == 16 AND target == 17.

    EXACT pre-fix expected (without Phase 9 gate registration): zero files
    matching ``swing-pre-phase9-migration-*.db`` in backup_dir.
    EXACT post-fix expected: exactly 1 file matching the pattern.
    """
    db_path = tmp_path / "v16.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Seed schema at v16 (Phase 8 baseline):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=16, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 16

    # Reopen + walk v16 -> v17 through the production gate:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=17, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 17

    # Backup file should exist with the phase9 prefix:
    backups = list(backup_dir.glob("swing-pre-phase9-migration-*.db"))
    assert len(backups) == 1


def test_backup_does_not_fire_on_fresh_db(tmp_path: Path) -> None:
    """No phase9 backup on fresh DB (current_version == 0).

    EXACT expected: zero files matching ``swing-pre-phase9-*.db`` in
    backup_dir.
    """
    db_path = tmp_path / "fresh.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=17, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 17

    # No phase9 backup (gate condition `current == 16 AND target >= 17` FALSE):
    assert list(backup_dir.glob("swing-pre-phase9-*.db")) == []


def test_backup_does_not_fire_on_v15_to_v16_walk(tmp_path: Path) -> None:
    """No phase9 backup when target_version != 17 (mid-walk to v16 only)."""
    db_path = tmp_path / "v15.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    conn = sqlite3.connect(db_path)
    run_migrations(conn, target_version=15, backup_dir=backup_dir)
    conn.commit()
    run_migrations(conn, target_version=16, backup_dir=backup_dir)
    conn.commit()
    conn.close()

    # No phase9 backup file (target_version was 16, not 17):
    assert list(backup_dir.glob("swing-pre-phase9-*.db")) == []


def test_executescript_rollback_on_partial_failure(tmp_path: Path) -> None:
    """Malformed migration raises + leaves conn.in_transaction == False.

    Inherits Phase 8 deviation accept-with-rationale: ``executescript()``
    issues an implicit COMMIT before running the script and runs each
    statement in autocommit, so a CREATE TABLE that succeeds before a later
    INSERT fails is already durably committed. The Phase 7 hotfix
    (283d4fa) ``_apply_migration`` try/except/rollback discipline still:
    (a) re-raises the underlying error, (b) ensures
    ``conn.in_transaction is False`` so a subsequent caller cannot
    accidentally ``commit()`` partial state. We assert those two invariants
    here; we do NOT assert "probe_table absent" because that assertion is
    incorrect against Python sqlite3's executescript semantics.
    """
    db_path = tmp_path / "v16.db"
    conn = sqlite3.connect(db_path)
    run_migrations(conn, target_version=16)
    conn.commit()

    bad_sql_path = tmp_path / "bad_migration.sql"
    bad_sql_path.write_text(
        "CREATE TABLE probe_table_phase9 (id INTEGER);\n"
        "INSERT INTO nonexistent_table_phase9 VALUES (1);\n"  # FAIL HERE
    )

    with pytest.raises(sqlite3.OperationalError):
        _apply_migration(conn, bad_sql_path)

    assert conn.in_transaction is False
    conn.close()


def test_foreign_keys_pragma_restored_after_apply(tmp_path: Path) -> None:
    """foreign_keys=OFF runner discipline: prior value restored in finally:."""
    db_path = tmp_path / "v16.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    benign_sql_path = tmp_path / "noop.sql"
    benign_sql_path.write_text("-- noop\n")
    _apply_migration(conn, benign_sql_path)
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1
    conn.close()


def _read_version(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT version FROM schema_version").fetchone()[0]
    finally:
        conn.close()
