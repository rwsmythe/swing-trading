"""Backup-runner discipline tests for Phase 7 migration 0014 gating.

Spec §12.1 binding: SQLite-native Connection.backup() only; shutil.copy2 NOT
acceptable; 4 integrity checks (file exists; non-empty; PRAGMA integrity_check
returns 'ok'; expected-table-set present).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    MigrationBackupRequiredException,
    _create_pre_migration_backup,
    _verify_backup_integrity,
    run_migrations,
)


def _seed_v13_db(path: Path) -> None:
    """Build a schema-version-13 DB with the expected table set populated.

    Uses run_migrations with target_version=13 directly. The original A.1
    helper used ensure_schema, but that path defaults to EXPECTED_SCHEMA_VERSION
    which is 14 post-T2 — invoking the backup gate on a fresh empty file. The
    explicit-target form bypasses the gate (gate only fires for target>=14)."""
    conn = sqlite3.connect(path)
    try:
        run_migrations(conn, target_version=13)
    finally:
        conn.close()


def test_backup_creates_file_via_sqlite_native(tmp_path):
    """The backup helper writes a non-empty file via Connection.backup()."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    backup_path = _create_pre_migration_backup(src, dest_dir=tmp_path)
    assert backup_path.exists()
    assert backup_path.stat().st_size > 0


def test_backup_integrity_check_passes_on_healthy_db(tmp_path):
    """PRAGMA integrity_check on the backup returns 'ok' for a healthy DB."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    backup_path = _create_pre_migration_backup(src, dest_dir=tmp_path)
    # Should not raise.
    _verify_backup_integrity(
        backup_path,
        expected_tables={"trades", "exits", "trade_events", "schema_version"},
    )


def test_backup_missing_expected_table_raises(tmp_path):
    """If the backup is missing an expected table, integrity check raises."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    backup_path = _create_pre_migration_backup(src, dest_dir=tmp_path)
    backup_conn = sqlite3.connect(backup_path)
    backup_conn.execute("DROP TABLE IF EXISTS trades")
    backup_conn.commit()
    backup_conn.close()
    with pytest.raises(MigrationBackupRequiredException, match="expected table"):
        _verify_backup_integrity(
            backup_path,
            expected_tables={"trades", "exits", "trade_events", "schema_version"},
        )


def test_backup_zero_size_file_raises(tmp_path):
    """A zero-byte backup file (e.g., truncated mid-write) is rejected even if
    the file exists."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    backup_path = tmp_path / "swing-pre-phase7-migration-empty.db"
    backup_path.write_bytes(b"")  # zero bytes
    with pytest.raises(MigrationBackupRequiredException, match="empty"):
        _verify_backup_integrity(
            backup_path,
            expected_tables={"trades", "exits", "trade_events", "schema_version"},
        )


def test_backup_integrity_check_returns_non_ok_raises(tmp_path):
    """An SQLite file that opens cleanly but reports corruption on PRAGMA
    integrity_check is rejected (page-level corruption / broken indices /
    FK issues)."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    backup_path = _create_pre_migration_backup(src, dest_dir=tmp_path)
    # Corrupt page 2 of the backup (page 1 is the SQLite header; page 2 is
    # the schema page — corrupting it makes integrity_check fail without
    # making sqlite3.connect itself raise).
    with open(backup_path, "r+b") as f:
        f.seek(4096)  # default page size
        f.write(b"\xff" * 64)
    with pytest.raises(MigrationBackupRequiredException, match="integrity_check"):
        _verify_backup_integrity(
            backup_path,
            expected_tables={"trades", "exits", "trade_events", "schema_version"},
        )


def test_run_migrations_refuses_when_backup_path_unwritable(tmp_path):
    """If the backup destination is unwritable, run_migrations refuses to migrate.
    Source DB schema_version remains unchanged (13)."""
    src = tmp_path / "src.db"
    _seed_v13_db(src)
    # Point the backup dir at a path with a regular file blocking the parent;
    # mkdir(parents=True) on a subdir of that file raises OSError on both
    # Windows and Linux.
    blocker_file = tmp_path / "blocker_file"
    blocker_file.write_text("not a dir")
    backup_dir = blocker_file / "subdir"
    conn = sqlite3.connect(src)
    try:
        with pytest.raises(MigrationBackupRequiredException):
            run_migrations(conn, target_version=14, backup_dir=backup_dir)
        cur = conn.execute("SELECT version FROM schema_version")
        assert cur.fetchone()[0] == 13  # unchanged
    finally:
        conn.close()


def test_ensure_schema_fresh_db_succeeds_at_v14(tmp_path):
    """A brand-new install (fresh empty DB file) walks 0001->0014 without
    firing the backup gate. The gate is for upgrading existing v13 data;
    a fresh DB has no data to lose.

    Regression: A.2 EXPECTED_SCHEMA_VERSION bump initially fired the gate
    on fresh installs, raising MigrationBackupRequiredException. Code-review
    I1 tightened the gate to current_version == 13 only.
    """
    from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema
    db = tmp_path / "fresh.db"
    conn = ensure_schema(db)
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == EXPECTED_SCHEMA_VERSION  # 14
    # Sanity: no spurious backup file in the same directory.
    backup_files = list(tmp_path.glob("swing-pre-phase7-migration-*.db"))
    assert backup_files == [], f"unexpected backup file(s): {backup_files}"
    conn.close()


def test_run_migrations_skips_gate_when_current_below_13(tmp_path):
    """Mid-walk states (current_version < 13) skip the gate; the walk passes
    through v13->v14 cleanly without backing up the transient v3/v5/etc state.

    Discriminating: would FAIL pre-fix because current=0 < 13 < target=14
    triggered the gate.
    """
    db = tmp_path / "midwalk.db"
    conn = sqlite3.connect(db)
    try:
        # current_version = 0 (no schema_version table); target = 14.
        run_migrations(conn, target_version=14, backup_dir=tmp_path)
        cur = conn.execute("SELECT version FROM schema_version")
        assert cur.fetchone()[0] == 14
        backup_files = list(tmp_path.glob("swing-pre-phase7-migration-*.db"))
        assert backup_files == [], (
            f"gate fired but should have skipped: {backup_files}"
        )
    finally:
        conn.close()


def test_run_migrations_fires_gate_when_current_eq_13(tmp_path):
    """v13 -> v14 upgrade DOES fire the gate (existing data; backup before
    table-rebuild). The successfully-created backup file is left in
    backup_dir; the upgrade succeeds.

    Discriminating: would FAIL post-fix if condition was over-tightened to
    current >= 14, never firing the gate.
    """
    db = tmp_path / "upgrade.db"
    conn = sqlite3.connect(db)
    try:
        run_migrations(conn, target_version=13)
        # Now current = 13.
        backup_dir = tmp_path / "backups"
        run_migrations(conn, target_version=14, backup_dir=backup_dir)
        cur = conn.execute("SELECT version FROM schema_version")
        assert cur.fetchone()[0] == 14
        backup_files = list(backup_dir.glob("swing-pre-phase7-migration-*.db"))
        assert len(backup_files) == 1, (
            f"expected 1 backup file; got {backup_files}"
        )
    finally:
        conn.close()
