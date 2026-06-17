"""Phase 18 Arc 18-H.6 — migration 0031 (untracked_broker_position enum widen).

Distinguishing posture (feedback_regression_test_arithmetic): under the pre-fix
v30 schema the discrepancy_type CHECK rejects 'untracked_broker_position'
(IntegrityError); post-0031 it is accepted. Tests assert BOTH directions where
load-bearing.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _current_version,
    _phase18_arc_h6_backup_gate,
    run_migrations,
)


def _migrate(
    tmp_path: Path, version: int, backup_dir: Path | None = None
) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=version, backup_dir=backup_dir or tmp_path)
    return conn


def _insert_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO reconciliation_runs "
        "(source, started_ts, state) "
        "VALUES ('schwab_api', '2026-06-16T00:00:00', 'running')"
    )
    return int(cur.lastrowid)


def _insert_discrepancy(
    conn: sqlite3.Connection, run_id: int, dtype: str
) -> None:
    conn.execute(
        "INSERT INTO reconciliation_discrepancies "
        "(run_id, discrepancy_type, field_name, material_to_review, "
        "resolution, created_at) "
        "VALUES (?, ?, 'broker_position', 1, 'unresolved', "
        "'2026-06-16T00:00:00')",
        (run_id, dtype),
    )


def test_expected_schema_version_is_31():
    assert EXPECTED_SCHEMA_VERSION == 31


def test_v30_rejects_untracked_then_v31_accepts(tmp_path):
    # Pre-fix path: at v30 the CHECK rejects the new value (distinguishing).
    conn = _migrate(tmp_path, 30)
    assert _current_version(conn) == 30
    run_id = _insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_discrepancy(conn, run_id, "untracked_broker_position")
    conn.close()

    # Post-fix path: migrate to v31, the same insert SUCCEEDS.
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=31, backup_dir=tmp_path)
    assert _current_version(conn) == 31
    run_id = _insert_run(conn)
    _insert_discrepancy(conn, run_id, "untracked_broker_position")
    row = conn.execute(
        "SELECT discrepancy_type FROM reconciliation_discrepancies "
        "WHERE discrepancy_type='untracked_broker_position'"
    ).fetchone()
    assert row == ("untracked_broker_position",)
    conn.close()


def test_v31_bogus_type_still_rejected(tmp_path):
    conn = _migrate(tmp_path, 31)
    run_id = _insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_discrepancy(conn, run_id, "frobnicate")
    conn.close()


def test_v31_preserves_existing_columns_indexes_and_checks(tmp_path):
    conn = _migrate(tmp_path, 31)
    cols = [
        r[1]
        for r in conn.execute(
            "PRAGMA table_info(reconciliation_discrepancies)"
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
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='reconciliation_discrepancies' AND name LIKE 'ix_%'"
        ).fetchall()
    }
    assert idx == {
        "ix_reconciliation_discrepancies_run",
        "ix_reconciliation_discrepancies_trade",
        "ix_reconciliation_discrepancies_unresolved",
        "ix_reconciliation_discrepancies_material",
        "ix_reconciliation_discrepancies_pending_ambiguity",
    }
    # Cross-column CHECK still enforced: ambiguity_kind set with an
    # incompatible resolution must fail.
    run_id = _insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(run_id, discrepancy_type, field_name, material_to_review, "
            "resolution, ambiguity_kind, created_at) "
            "VALUES (?, 'stop_mismatch', 'stop', 1, 'unresolved', "
            "'unsupported', '2026-06-16T00:00:00')",
            (run_id,),
        )
    conn.close()


def test_v31_fk_cascade_preserved(tmp_path):
    # The reconciliation_runs -> discrepancies ON DELETE CASCADE survives the
    # rebuild: deleting the run wipes its discrepancies.
    conn = _migrate(tmp_path, 31)
    run_id = _insert_run(conn)
    _insert_discrepancy(conn, run_id, "position_qty_mismatch")
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies"
    ).fetchone()[0] == 1
    conn.execute("DELETE FROM reconciliation_runs WHERE run_id=?", (run_id,))
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies"
    ).fetchone()[0] == 0
    conn.close()


def test_v30_to_v31_preserves_existing_rows(tmp_path):
    conn = _migrate(tmp_path, 30)
    run_id = _insert_run(conn)
    _insert_discrepancy(conn, run_id, "equity_delta")
    _insert_discrepancy(conn, run_id, "stop_mismatch")
    pre = conn.execute(
        "SELECT discrepancy_id, discrepancy_type FROM "
        "reconciliation_discrepancies ORDER BY discrepancy_id"
    ).fetchall()
    conn.commit()  # persist before reopening for the migration walk
    conn.close()

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=31, backup_dir=tmp_path)
    post = conn.execute(
        "SELECT discrepancy_id, discrepancy_type FROM "
        "reconciliation_discrepancies ORDER BY discrepancy_id"
    ).fetchall()
    assert post == pre  # ids + types preserved verbatim
    conn.close()


def test_migrate_twice_is_noop(tmp_path):
    conn = _migrate(tmp_path, 31)
    run_migrations(conn, target_version=31)
    assert _current_version(conn) == 31
    # exactly one reconciliation_discrepancies table (no leftover _new)
    tbls = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'reconciliation_discrepancies%'"
        ).fetchall()
    ]
    assert tbls == ["reconciliation_discrepancies"]
    conn.close()


def test_backup_gate_fires_strict_on_v30(tmp_path):
    conn = sqlite3.connect(":memory:")
    inert = tmp_path / "inert"
    fire = tmp_path / "fire"
    naive = tmp_path / "naive"
    # Already at target -> no-op.
    _phase18_arc_h6_backup_gate(
        conn, current_version=31, target_version=31, backup_dir=inert
    )
    # Multi-version jump from pre-v30 -> bypass by design (STRICT equality).
    _phase18_arc_h6_backup_gate(
        conn, current_version=29, target_version=31, backup_dir=naive
    )
    assert not inert.exists() and not naive.exists()
    # Exactly pre==30 -> gate fires; in-memory source -> required exception.
    with pytest.raises(MigrationBackupRequiredException):
        _phase18_arc_h6_backup_gate(
            conn, current_version=30, target_version=31, backup_dir=fire
        )


def test_run_migrations_wires_phase18_arc_h6_gate(tmp_path):
    backups = tmp_path / "v30_backups"
    backups.mkdir()
    conn = _migrate(tmp_path, 30)
    conn.close()
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=31, backup_dir=backups)
    assert _current_version(conn) == 31
    snaps = list(backups.glob("swing-pre-phase18-arc-h6-migration-*.db"))
    assert len(snaps) == 1
    conn.close()


def test_fresh_v0_walk_does_not_fire_phase18_arc_h6_gate(tmp_path):
    backups = tmp_path / "fresh_backups"
    backups.mkdir()
    conn = _migrate(tmp_path, 31, backup_dir=backups)
    snaps = list(backups.glob("swing-pre-phase18-arc-h6-migration-*.db"))
    assert snaps == []
    conn.close()
