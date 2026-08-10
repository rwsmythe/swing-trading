"""Item-5 A-4 -- migration 0035 (fills_trades_price_divergence enum widen).

Distinguishing posture (feedback_regression_test_arithmetic): under the pre-fix
v34 schema the discrepancy_type CHECK REJECTS 'fills_trades_price_divergence'
(IntegrityError); post-0035 it is accepted. Both directions are asserted.

Modelled on tests/data/test_migration_0031_untracked_broker_position.py, which
is the verbatim precedent -- 0031 is the last CHECK widening on this table and,
like this one, had to do it by TABLE REBUILD because SQLite cannot ALTER a
CHECK. (0027 is NOT the precedent: it is a cheap ADD COLUMN and would badly
under-state the cost.)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    A4_TAXONOMY_PRE_MIGRATION_EXPECTED_TABLES,
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _a4_taxonomy_backup_gate,
    _current_version,
    run_migrations,
)

NEW_TYPE = "fills_trades_price_divergence"


def _migrate(
    tmp_path: Path, version: int, backup_dir: Path | None = None,
) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=version, backup_dir=backup_dir or tmp_path)
    return conn


def _insert_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES ('schwab_api', '2026-08-09T00:00:00', 'running')",
    )
    return int(cur.lastrowid)


def _insert_discrepancy(
    conn: sqlite3.Connection, run_id: int, dtype: str,
) -> None:
    conn.execute(
        "INSERT INTO reconciliation_discrepancies "
        "(run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at) "
        "VALUES (?, ?, 'internal_consistency', 1, 'unresolved', "
        "'2026-08-09T00:00:00')",
        (run_id, dtype),
    )


def test_expected_schema_version_is_35():
    assert EXPECTED_SCHEMA_VERSION == 35


def test_v34_rejects_the_new_type_then_v35_accepts(tmp_path):
    conn = _migrate(tmp_path, 34)
    assert _current_version(conn) == 34
    run_id = _insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_discrepancy(conn, run_id, NEW_TYPE)
    conn.close()

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=35, backup_dir=tmp_path)
    assert _current_version(conn) == 35
    run_id = _insert_run(conn)
    _insert_discrepancy(conn, run_id, NEW_TYPE)
    assert conn.execute(
        "SELECT discrepancy_type FROM reconciliation_discrepancies "
        "WHERE discrepancy_type = ?", (NEW_TYPE,),
    ).fetchone() == (NEW_TYPE,)
    conn.close()


def test_v35_bogus_type_still_rejected(tmp_path):
    conn = _migrate(tmp_path, 35)
    run_id = _insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_discrepancy(conn, run_id, "frobnicate")
    conn.close()


def test_v35_preserves_every_column_index_and_check(tmp_path):
    conn = _migrate(tmp_path, 35)
    cols = [
        r[1] for r in conn.execute(
            "PRAGMA table_info(reconciliation_discrepancies)",
        ).fetchall()
    ]
    assert cols == [
        "discrepancy_id", "run_id", "discrepancy_type", "trade_id", "fill_id",
        "cash_movement_id", "linked_daily_management_record_id", "ticker",
        "field_name", "expected_value_json", "actual_value_json", "delta_text",
        "material_to_review", "resolution", "ambiguity_kind",
        "resolution_reason", "resolved_at", "resolved_by",
        "mistake_tag_assigned", "created_at",
    ]
    idx = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='reconciliation_discrepancies' AND name LIKE 'ix_%'",
        ).fetchall()
    }
    assert idx == {
        "ix_reconciliation_discrepancies_run",
        "ix_reconciliation_discrepancies_trade",
        "ix_reconciliation_discrepancies_unresolved",
        "ix_reconciliation_discrepancies_material",
        "ix_reconciliation_discrepancies_pending_ambiguity",
    }
    # The pending_ambiguity index is PARTIAL; a rebuild that dropped the WHERE
    # would still satisfy the name check above.
    partial_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = "
        "'ix_reconciliation_discrepancies_pending_ambiguity'",
    ).fetchone()[0]
    assert "WHERE resolution = 'pending_ambiguity_resolution'" in partial_sql

    # The cross-column resolution/ambiguity_kind CHECK still binds.
    run_id = _insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, ambiguity_kind, created_at) "
            "VALUES (?, 'stop_mismatch', 'stop', 1, 'unresolved', "
            "'unsupported', '2026-08-09T00:00:00')",
            (run_id,),
        )
    conn.close()


def test_v35_resolution_and_ambiguity_kind_enums_survive_the_rebuild(tmp_path):
    """The rebuild copies TWO other CHECK enums verbatim; a dropped value in
    either would be invisible to the column/index assertions above."""
    from swing.trades.reconciliation import RESOLUTION_TYPES

    conn = _migrate(tmp_path, 35)
    table_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = "
        "'reconciliation_discrepancies'",
    ).fetchone()[0]
    for value in RESOLUTION_TYPES:
        assert f"'{value}'" in table_sql
    for value in (
        "multi_partial_vs_consolidated", "multi_match_within_window",
        "unknown_schwab_subtype", "field_shape_incompatible",
        "schwab_returned_no_match", "validator_rejected", "unsupported",
    ):
        assert f"'{value}'" in table_sql
    conn.close()


def test_v35_fk_cascade_preserved(tmp_path):
    conn = _migrate(tmp_path, 35)
    run_id = _insert_run(conn)
    _insert_discrepancy(conn, run_id, "position_qty_mismatch")
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies",
    ).fetchone()[0] == 1
    conn.execute("DELETE FROM reconciliation_runs WHERE run_id = ?", (run_id,))
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies",
    ).fetchone()[0] == 0
    conn.close()


def test_v34_to_v35_preserves_existing_rows_and_their_ids(tmp_path):
    conn = _migrate(tmp_path, 34)
    run_id = _insert_run(conn)
    _insert_discrepancy(conn, run_id, "equity_delta")
    _insert_discrepancy(conn, run_id, "entry_price_mismatch")
    conn.commit()
    pre = conn.execute(
        "SELECT discrepancy_id, discrepancy_type FROM "
        "reconciliation_discrepancies ORDER BY discrepancy_id",
    ).fetchall()
    conn.close()

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=35, backup_dir=tmp_path)
    post = conn.execute(
        "SELECT discrepancy_id, discrepancy_type FROM "
        "reconciliation_discrepancies ORDER BY discrepancy_id",
    ).fetchall()
    assert post == pre
    conn.close()


def test_v34_to_v35_preserves_the_correction_child_rows(tmp_path):
    """The runner drops the parent table with foreign_keys=OFF specifically so
    `reconciliation_corrections` is NOT cascade-wiped. That is the highest-cost
    failure this migration could have, and nothing else in this file sees it."""
    conn = _migrate(tmp_path, 34)
    run_id = _insert_run(conn)
    _insert_discrepancy(conn, run_id, "entry_price_mismatch")
    disc_id = conn.execute(
        "SELECT discrepancy_id FROM reconciliation_discrepancies",
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO reconciliation_corrections ("
        "discrepancy_id, correction_action, affected_table, affected_row_id, "
        "field_name, pre_correction_value_json, applied_value_json, "
        "applied_at, applied_by, reconciliation_run_id) "
        "VALUES (?, 'auto_applied', 'fills', 1, 'price', '{}', '{}', "
        "'2026-08-09T00:00:00', 'auto', ?)",
        (disc_id, run_id),
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=35, backup_dir=tmp_path)
    rows = conn.execute(
        "SELECT discrepancy_id FROM reconciliation_corrections",
    ).fetchall()
    assert rows == [(disc_id,)]
    conn.close()


def test_migration_sql_is_atomic_and_stamps_last(tmp_path):
    """gotcha #9 + the Phase-9 R1 Critical #1 precedent: explicit BEGIN/COMMIT,
    and the version stamp is the FINAL statement so a truncated transaction can
    never leave the stamp ahead of the schema."""
    sql = (
        Path(__file__).resolve().parents[2]
        / "swing" / "data" / "migrations"
        / "0035_fills_trades_price_divergence.sql"
    ).read_text()
    lines = [
        ln for ln in sql.splitlines() if not ln.strip().startswith("--")
    ]
    body = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
    assert body[0].upper() == "BEGIN"
    assert body[-1].upper() == "COMMIT"
    assert sum(1 for b in body if b.upper() == "BEGIN") == 1
    assert sum(1 for b in body if b.upper() == "COMMIT") == 1
    assert "UPDATE schema_version SET version = 35" in body[-2]


def test_backup_gate_uses_STRICT_equality_on_pre_version(tmp_path):
    """`pre_version == (target - 1)`, NOT `<=`. A multi-version jump from a
    pre-v34 baseline bypasses this gate BY DESIGN (multi-version jumps are
    separate two-step migrations)."""
    conn = _migrate(tmp_path, 34)
    # Fires at exactly 34 -> >=35 and produces a snapshot.
    _a4_taxonomy_backup_gate(
        conn, current_version=34, target_version=35, backup_dir=tmp_path,
    )
    made = list(tmp_path.glob("swing-pre-a4-taxonomy-migration-*.db"))
    assert len(made) == 1
    for f in made:
        f.unlink()
    # Does NOT fire from 33 (strict equality) or for a target below 35.
    _a4_taxonomy_backup_gate(
        conn, current_version=33, target_version=35, backup_dir=tmp_path,
    )
    _a4_taxonomy_backup_gate(
        conn, current_version=34, target_version=34, backup_dir=tmp_path,
    )
    assert list(tmp_path.glob("swing-pre-a4-taxonomy-migration-*.db")) == []
    conn.close()


def test_backup_gate_refuses_an_in_memory_source(tmp_path):
    conn = sqlite3.connect(":memory:")
    with pytest.raises(MigrationBackupRequiredException):
        _a4_taxonomy_backup_gate(
            conn, current_version=34, target_version=35, backup_dir=tmp_path,
        )
    conn.close()


def test_expected_tables_set_requires_the_table_being_rebuilt():
    """A gate that does not require the one table its migration touches is not
    a fail-closed belt (the H1 gate's own lesson, inherited)."""
    assert "reconciliation_discrepancies" in (
        A4_TAXONOMY_PRE_MIGRATION_EXPECTED_TABLES
    )
    assert "reconciliation_corrections" in (
        A4_TAXONOMY_PRE_MIGRATION_EXPECTED_TABLES
    )


def test_a_real_v34_db_migrates_and_the_snapshot_lands(tmp_path):
    """The gate is registered inside run_migrations, not merely defined."""
    conn = _migrate(tmp_path, 34)
    conn.close()
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=35, backup_dir=tmp_path)
    assert _current_version(conn) == 35
    assert len(list(tmp_path.glob("swing-pre-a4-taxonomy-migration-*.db"))) == 1
    conn.close()


def test_run_migrations_twice_is_a_no_op(tmp_path):
    conn = _migrate(tmp_path, 35)
    run_id = _insert_run(conn)
    _insert_discrepancy(conn, run_id, NEW_TYPE)
    conn.commit()
    before = conn.execute(
        "SELECT discrepancy_id, discrepancy_type FROM "
        "reconciliation_discrepancies ORDER BY discrepancy_id",
    ).fetchall()
    run_migrations(conn, target_version=35, backup_dir=tmp_path)
    assert _current_version(conn) == 35
    assert conn.execute(
        "SELECT discrepancy_id, discrepancy_type FROM "
        "reconciliation_discrepancies ORDER BY discrepancy_id",
    ).fetchall() == before
    conn.close()


def test_r1_M3_the_rebuild_PRESERVES_the_autoincrement_high_water_mark(tmp_path):
    """`discrepancy_id` is INTEGER PRIMARY KEY **AUTOINCREMENT**, whose whole
    point is that a retired id is never reissued. A naive table rebuild defeats
    it: DROP removes the old `sqlite_sequence` row and the new sequence becomes
    the maximum SURVIVING id.

    Seed 1-3, delete 3, migrate. Pre-fix the next insert is 3 -- a REUSED audit
    identifier, in a ledger whose whole purpose is that its statements are
    true. Post-fix it is 4.
    """
    conn = _migrate(tmp_path, 34)
    run_id = _insert_run(conn)
    for _ in range(3):
        _insert_discrepancy(conn, run_id, "stop_mismatch")
    conn.execute(
        "DELETE FROM reconciliation_discrepancies WHERE discrepancy_id = 3",
    )
    conn.commit()
    assert conn.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = "
        "'reconciliation_discrepancies'",
    ).fetchone()[0] == 3
    conn.close()

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=35, backup_dir=tmp_path)
    assert conn.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = "
        "'reconciliation_discrepancies'",
    ).fetchone()[0] == 3
    new_id = conn.execute(
        "INSERT INTO reconciliation_discrepancies "
        "(run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at) VALUES (?, 'stop_mismatch', 'x', 1, "
        "'unresolved', '2026-08-09T00:00:00')", (run_id,),
    ).lastrowid
    assert new_id == 4
    conn.close()


def test_r1_M3_the_high_water_mark_survives_an_EMPTY_table(tmp_path):
    """A rebuild that copies ZERO rows leaves NO `sqlite_sequence` row at all
    (AUTOINCREMENT creates it on the first insert), so the sequence would
    restart at 1. The INSERT-if-absent half covers that."""
    conn = _migrate(tmp_path, 34)
    run_id = _insert_run(conn)
    for _ in range(2):
        _insert_discrepancy(conn, run_id, "stop_mismatch")
    conn.execute("DELETE FROM reconciliation_discrepancies")
    conn.commit()
    conn.close()

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=35, backup_dir=tmp_path)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies",
    ).fetchone()[0] == 0
    new_id = conn.execute(
        "INSERT INTO reconciliation_discrepancies "
        "(run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at) VALUES (?, 'stop_mismatch', 'x', 1, "
        "'unresolved', '2026-08-09T00:00:00')", (run_id,),
    ).lastrowid
    assert new_id == 3
    conn.close()


def test_r1_M3_a_virgin_db_migrates_without_a_sequence_row(tmp_path):
    """No discrepancy has ever existed. Read off a real migrated DB rather
    than assumed: 0031's own rebuild already leaves a `sqlite_sequence` row at
    seq=0, so the stash is 0 (not NULL) and BOTH restore statements must be
    no-ops -- the INSERT because the row exists, the UPDATE because `seq < 0`
    is false. What matters is the BEHAVIOUR: the first id is still 1."""
    conn = _migrate(tmp_path, 35)
    assert conn.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = "
        "'reconciliation_discrepancies'",
    ).fetchone() == (0,)
    run_id = _insert_run(conn)
    new_id = conn.execute(
        "INSERT INTO reconciliation_discrepancies "
        "(run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at) VALUES (?, 'stop_mismatch', 'x', 1, "
        "'unresolved', '2026-08-09T00:00:00')", (run_id,),
    ).lastrowid
    assert new_id == 1
    conn.close()


def test_r1_M3_the_migration_leaves_no_temp_table_behind(tmp_path):
    conn = _migrate(tmp_path, 35)
    temp = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_temp_master WHERE type = 'table'",
        ).fetchall()
    }
    assert not {t for t in temp if t.startswith("_a4_seq")}, temp
    conn.close()
