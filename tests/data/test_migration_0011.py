# tests/data/test_migration_0011.py
"""Migration 0011 + source-taxonomy expansion tests.

Spec §B. Verifies:
- schema_version advances 10 → 11.
- New CHECK constraint accepts all 4 source values.
- New CHECK constraint rejects an unknown source value.
- Existing rows preserved bit-identically (count, ticker, source, chart_status,
  pipeline_run_id all intact post-migration; this includes legacy 'near_proximity').
- Index `idx_pipeline_chart_targets_run` re-created on the new table.
- Pre-migration vs post-migration index/trigger/view inventory matches
  (no objects silently dropped on DROP TABLE).
"""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.db import ensure_schema


def _migrate_to_v10(conn: sqlite3.Connection) -> None:
    """Apply migrations 0001-0010 to bring an empty conn to schema_version=10.

    Applies migrations sequentially from disk so the test exercises the
    v10 → v11 transition specifically. Migration 0001 owns schema_version
    creation; we do not pre-create it here.
    """
    # Apply migrations 0001-0010 in order from disk.
    from swing.data import migrations  # package; loader path resolution
    from pathlib import Path
    migs_dir = Path(migrations.__file__).parent
    for n in range(1, 11):
        sql_files = sorted(migs_dir.glob(f"{n:04d}_*.sql"))
        assert len(sql_files) == 1, f"expected exactly one migration {n:04d}, got {sql_files}"
        conn.executescript(sql_files[0].read_text())
    conn.commit()


def _seed_pipeline_run(conn: sqlite3.Connection, *, run_id: int) -> None:
    """Seed pipeline_runs row with the FK target for chart_target inserts.

    Per Phase 2 lesson (FK-references): tests that insert into
    pipeline_chart_targets MUST seed pipeline_runs first, otherwise the
    schema-layer FK fires before any plan-asserted behavior.
    """
    conn.execute(
        """INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, state,
                                       lease_token, data_asof_date, action_session_date)
           VALUES (?, '2026-04-01T09:00:00', '2026-04-01T09:30:00', 'manual', 'complete',
                   'test-lease-token', '2026-04-01', '2026-04-02')""",
        (run_id,),
    )


def test_migration_0011_advances_schema_version(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _migrate_to_v10(conn)
        # Pre-condition: schema is at v10.
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 10
        # Apply 0011.
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        # Post-condition: schema is at v11.
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 11
    finally:
        conn.close()


def test_migration_0011_accepts_all_four_source_values(tmp_path):
    """Post-migration, INSERT with each of the 4 valid source values succeeds.

    Discriminating verification: pre-migration the CHECK is
    `source IN ('aplus', 'near_proximity')`; an INSERT with 'open_position'
    raises `sqlite3.IntegrityError: CHECK constraint failed`. Post-migration
    all 4 inserts succeed. The test would fail with IntegrityError on the
    pre-migration schema.
    """
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _migrate_to_v10(conn)
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        _seed_pipeline_run(conn, run_id=1)
        for source in ("aplus", "near_proximity", "open_position", "tag_aware_top_n"):
            conn.execute(
                """INSERT INTO pipeline_chart_targets
                   (pipeline_run_id, ticker, source, chart_status)
                   VALUES (?, ?, ?, 'pending')""",
                (1, f"T{source[:4].upper()}", source),
            )
        conn.commit()
        rows = conn.execute(
            "SELECT source FROM pipeline_chart_targets ORDER BY id"
        ).fetchall()
        assert {r[0] for r in rows} == {
            "aplus", "near_proximity", "open_position", "tag_aware_top_n",
        }
    finally:
        conn.close()


def test_migration_0011_rejects_unknown_source_value(tmp_path):
    """Post-migration, an unknown source value raises IntegrityError.

    Discriminating verification: catches a regression where the CHECK is
    accidentally widened (e.g., dropped or replaced with a permissive list).
    """
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _migrate_to_v10(conn)
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        _seed_pipeline_run(conn, run_id=1)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO pipeline_chart_targets
                   (pipeline_run_id, ticker, source, chart_status)
                   VALUES (1, 'TEST', 'random_source', 'pending')""",
            )
    finally:
        conn.close()


def test_migration_0011_preserves_existing_rows_bit_identically(tmp_path):
    """Pre-existing rows under each legacy source value survive the migration
    with all columns intact.

    Discriminating verification: pre-fix path (DROP TABLE without an
    INSERT-from-old) would zero the row count; this test fails with
    `assert 2 == 0` if the migration accidentally truncates.
    """
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _migrate_to_v10(conn)
        _seed_pipeline_run(conn, run_id=42)
        # Insert a legacy 'aplus' and a legacy 'near_proximity' row.
        conn.execute(
            """INSERT INTO pipeline_chart_targets
               (pipeline_run_id, ticker, source, chart_status)
               VALUES (42, 'AAPL', 'aplus', 'ok')""",
        )
        conn.execute(
            """INSERT INTO pipeline_chart_targets
               (pipeline_run_id, ticker, source, chart_status)
               VALUES (42, 'NVDA', 'near_proximity', 'ok')""",
        )
        conn.commit()
        # Apply 0011.
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        rows = conn.execute(
            """SELECT pipeline_run_id, ticker, source, chart_status
               FROM pipeline_chart_targets ORDER BY ticker"""
        ).fetchall()
        assert rows == [(42, "AAPL", "aplus", "ok"), (42, "NVDA", "near_proximity", "ok")]
    finally:
        conn.close()


def test_migration_0011_recreates_index(tmp_path):
    """The `idx_pipeline_chart_targets_run` index exists post-migration.

    Discriminating verification: pre-migration the index exists on the OLD
    table; SQLite drops indexes when the underlying table is dropped.
    A migration that forgets `CREATE INDEX` after `RENAME` leaves the index
    missing. The test fails with `assert 0 == 1` if the migration omits the
    re-creation step.
    """
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _migrate_to_v10(conn)
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        idx_count = conn.execute(
            """SELECT COUNT(*) FROM sqlite_master
               WHERE type = 'index' AND name = 'idx_pipeline_chart_targets_run'""",
        ).fetchone()[0]
        assert idx_count == 1
    finally:
        conn.close()


def test_migration_0011_inventory_objects_match(tmp_path):
    """Pre- and post-migration, the same set of NON-TABLE objects exists on
    `pipeline_chart_targets`. Spec §B "schema-objects inventory verification."

    Discriminating verification: this test catches a regression where a
    side-migration in 0007-0010 added a trigger or extra index that the
    0011 migration silently drops. If the inventory test passes pre-migration
    with a single index AND post-migration with a single index (same name),
    no objects were lost.
    """
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _migrate_to_v10(conn)
        pre_objects = sorted(conn.execute(
            """SELECT name, type FROM sqlite_master
               WHERE tbl_name = 'pipeline_chart_targets' AND type IN ('index', 'trigger', 'view')""",
        ).fetchall())
        from swing.data import migrations
        from pathlib import Path
        migration_sql = (Path(migrations.__file__).parent
                         / "0011_pipeline_chart_targets_source_taxonomy.sql").read_text()
        conn.executescript(migration_sql)
        conn.commit()
        post_objects = sorted(conn.execute(
            """SELECT name, type FROM sqlite_master
               WHERE tbl_name = 'pipeline_chart_targets' AND type IN ('index', 'trigger', 'view')""",
        ).fetchall())
        assert pre_objects == post_objects, (
            f"inventory drift: pre={pre_objects} post={post_objects}; "
            "migration must recreate ALL non-table objects after RENAME"
        )
    finally:
        conn.close()
