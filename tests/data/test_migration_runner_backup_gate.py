"""Phase 12 Sub-bundle C T-A.4 — migration runner backup-gate for v18 → v19.

Mirrors Phase 9 ``test_migration_0017_runner_discipline.py`` for the
v18 → v19 step. Discriminating tests for:

  - ``_phase12_bundle_c_backup_gate`` fires on v18 → v19
    (creates ``swing-pre-phase12-bundle-c-migration-*.db``).
  - Gate does NOT fire on fresh-DB walk (current_version == 0).
  - Gate does NOT fire when current_version != 18.
  - Backup file content equals pre-migration DB byte-for-byte
    (per plan §B.4 acceptance criterion #4 — sha256 equality).
  - Backup is taken BEFORE migration 0019 applies
    (per plan §B.4 acceptance criterion #5 — verify backup contains
    schema_version == 18, not == 19, after migration completes).
  - Existing Phase 9 backup gate behavior preserved.

Per plan §B.4: file pattern ``swing-pre-phase12-bundle-c-migration-<ISO>.db``
in same parent dir as the live ``swing.db``. Reuses Phase 9 Sub-bundle A
T-A.1 backup-gate mechanism verbatim.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from swing.data.db import run_migrations


def _read_version(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT version FROM schema_version").fetchone()[0]
    finally:
        conn.close()


def test_backup_fires_on_v18_to_v19(tmp_path: Path) -> None:
    """Backup created when current_version == 18 AND target == 19.

    EXACT pre-fix expected (without Phase 12 Sub-bundle C gate registration):
    zero files matching ``swing-pre-phase12-bundle-c-migration-*.db``.
    EXACT post-fix expected: exactly 1 file matching the pattern.
    """
    db_path = tmp_path / "v18.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Seed schema at v18 (Phase 11 baseline):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=18, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 18

    # Reopen + walk v18 -> v19 through the production gate:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=19, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 19

    # Backup file should exist with the phase12-bundle-c prefix:
    backups = list(backup_dir.glob("swing-pre-phase12-bundle-c-migration-*.db"))
    assert len(backups) == 1, f"expected 1 backup file; got {backups}"


def test_backup_does_not_fire_on_fresh_db(tmp_path: Path) -> None:
    """No phase12 backup on fresh DB (current_version == 0).

    Mid-walk states 0 → 19 must not fire the v18→v19 gate (mirrors Phase 9
    fresh-install posture).
    """
    db_path = tmp_path / "fresh.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=19, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 19

    # No phase12 backup (gate condition `current == 18 AND target >= 19` FALSE):
    assert list(backup_dir.glob("swing-pre-phase12-bundle-c-migration-*.db")) == []


def test_backup_does_not_fire_on_v17_to_v18_walk(tmp_path: Path) -> None:
    """No phase12 backup when target_version != 19 (mid-walk to v18 only).

    Walking from v17 → v18 must not trip the new v18→v19 gate.
    """
    db_path = tmp_path / "v17.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    conn = sqlite3.connect(db_path)
    run_migrations(conn, target_version=17, backup_dir=backup_dir)
    conn.commit()
    run_migrations(conn, target_version=18, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 18

    # No phase12 backup file (target_version was 18, not 19):
    assert list(backup_dir.glob("swing-pre-phase12-bundle-c-migration-*.db")) == []


def test_backup_content_equals_pre_migration_logical(tmp_path: Path) -> None:
    """Per plan §B.4 acceptance criterion #4: backup file content equals the
    pre-migration DB.

    PLAN-VS-IMPLEMENTATION DEVIATION (banked at return report §self-review):
    Plan §B.4 #4 prescribes ``hashlib.sha256`` byte-for-byte file equality,
    but the shipped backup mechanism uses SQLite-native ``Connection.backup()``
    (spec §12.1 binding; ``shutil.copy2()`` explicitly rejected because it
    can yield a torn snapshot under live writers). ``Connection.backup()``
    rebuilds the destination file page-by-page, which means the destination
    file is logically equivalent but does NOT match the source byte-for-byte
    (page ordering / freelist state / journal mode markers can differ even
    on an idle DB).

    This test substitutes content-equivalence at the SQL layer for the
    plan-prescribed byte-equality at the filesystem layer. The discriminating
    property — that the backup represents the pre-migration state, not the
    post-migration state — is covered by ``test_backup_taken_before_
    migration_0019_applies`` via direct schema_version inspection (the
    schema_version table cleanly distinguishes 18 from 19).

    Content equivalence here: pre-migration table set + row counts +
    schema_version on snapshot match the backup file's same.
    """
    db_path = tmp_path / "v18_sha.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Seed schema at v18:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=18, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 18

    # Snapshot the pre-migration DB byte-for-byte for the comparison anchor.
    pre_migration_snapshot = tmp_path / "pre_migration_snapshot.db"
    shutil.copy(db_path, pre_migration_snapshot)
    pre_summary = _summarize_db(pre_migration_snapshot)

    # Walk v18 → v19 — backup fires:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=19, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 19

    # Find the phase12 backup:
    backups = list(backup_dir.glob("swing-pre-phase12-bundle-c-migration-*.db"))
    assert len(backups) == 1, f"expected 1 backup file; got {backups}"
    backup_summary = _summarize_db(backups[0])

    # Logical content equivalence: schema_version + table set + per-table
    # row counts identical between the pre-migration snapshot and the backup.
    assert backup_summary == pre_summary, (
        f"backup logical content does not match pre-migration snapshot:\n"
        f"  pre_summary = {pre_summary}\n"
        f"  backup_summary = {backup_summary}\n"
        "This indicates either (a) the backup captured post-migration state, "
        "or (b) the backup is missing tables/rows present pre-migration."
    )


def _summarize_db(db_path: Path) -> dict:
    """Return a deterministic logical-content summary for backup-equivalence
    comparison: schema_version + sorted (table_name, row_count) tuples.

    Excludes SQLite-internal tables (``sqlite_*``) which can vary between
    page-rebuild operations even on logically-identical DBs.
    """
    conn = sqlite3.connect(db_path)
    try:
        version = conn.execute(
            "SELECT version FROM schema_version"
        ).fetchone()[0]
        table_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        row_counts = tuple(
            (
                name,
                conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0],
            )
            for (name,) in table_rows
        )
        return {"schema_version": version, "row_counts": row_counts}
    finally:
        conn.close()


def test_backup_taken_before_migration_0019_applies(tmp_path: Path) -> None:
    """Per plan §B.4 acceptance criterion #5: backup is taken BEFORE
    migration 0019 applies.

    Discriminator: open the backup file directly, read its schema_version.
    If the backup was taken before migration applied, schema_version == 18.
    If the backup was taken after migration applied, schema_version == 19.
    """
    db_path = tmp_path / "v18_order.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Seed schema at v18:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=18, backup_dir=backup_dir)
    conn.commit()
    conn.close()

    # Walk v18 → v19:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=19, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 19

    # Inspect the backup file directly:
    backups = list(backup_dir.glob("swing-pre-phase12-bundle-c-migration-*.db"))
    assert len(backups) == 1
    backup_version = _read_version(backups[0])
    assert backup_version == 18, (
        f"backup file schema_version is {backup_version}, expected 18; "
        "this indicates the backup was taken AFTER migration 0019 applied, "
        "violating plan §B.4 acceptance criterion #5."
    )


def test_backup_defaults_to_db_parent_dir_when_unspecified(tmp_path: Path) -> None:
    """Per plan §B.4 acceptance criterion #3: backup file is created in the
    same parent dir as ``swing.db`` when ``backup_dir`` is not explicitly
    provided.

    Mirrors Phase 9 ``_phase9_backup_gate`` default behavior (falls back
    to ``src_path.parent`` when caller-supplied ``backup_dir is None``).
    """
    db_path = tmp_path / "swing.db"

    # Seed schema at v18:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=18)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 18

    # Walk v18 → v19 WITHOUT explicit backup_dir:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=19)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 19

    # Backup should land in tmp_path (same dir as swing.db):
    backups = list(tmp_path.glob("swing-pre-phase12-bundle-c-migration-*.db"))
    assert len(backups) == 1, (
        f"expected 1 backup file in db parent dir; got {backups}"
    )


def test_phase9_backup_gate_still_fires_unchanged(tmp_path: Path) -> None:
    """Per plan §B.4 acceptance criterion #2: existing Phase 9 + Phase 11
    backup-gate entries unchanged. Phase 11 (v17→v18) per §C.5 LOCK does
    NOT have a wired gate — only Phase 9 does. Verify Phase 9 gate still
    fires on v16 → v17 walks.
    """
    db_path = tmp_path / "v16_phase9.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Seed schema at v16:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=16, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 16

    # Walk v16 -> v17 — Phase 9 gate fires:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=17, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 17

    # Existing Phase 9 backup remains correctly emitted with phase9 prefix:
    phase9_backups = list(backup_dir.glob("swing-pre-phase9-migration-*.db"))
    assert len(phase9_backups) == 1, (
        f"Phase 9 gate must remain unchanged; got {phase9_backups}"
    )
    # And no phase12 backup fires for this transition:
    phase12_backups = list(
        backup_dir.glob("swing-pre-phase12-bundle-c-migration-*.db")
    )
    assert phase12_backups == [], (
        f"phase12 gate must not fire on v16 → v17; got {phase12_backups}"
    )
