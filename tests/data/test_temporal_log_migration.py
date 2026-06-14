import sqlite3
import pytest
from pathlib import Path
from swing.data.db import run_migrations, _current_version, EXPECTED_SCHEMA_VERSION


def _fresh_v21_db(tmp_path: Path) -> sqlite3.Connection:
    """A connection migrated to v21 (one below target)."""
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=21, backup_dir=tmp_path)
    assert _current_version(conn) == 21
    return conn


def test_0022_brings_db_to_v22_with_both_tables(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    assert _current_version(conn) == 22
    tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "pattern_detection_events" in tables
    assert "pattern_forward_observations" in tables


def test_expected_schema_version_is_22():
    assert EXPECTED_SCHEMA_VERSION == 30


from swing.data.db import _phase14_backup_gate, PHASE14_PRE_MIGRATION_EXPECTED_TABLES


def test_phase14_backup_gate_fires_only_at_v21(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    # Fires at current==21, target>=22 -> writes a backup file.
    _phase14_backup_gate(conn, current_version=21, target_version=22, backup_dir=tmp_path)
    backups = list(tmp_path.glob("swing-pre-phase14-migration-*.db"))
    assert len(backups) == 1


def test_phase14_backup_gate_skips_non_v21(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    # current != 21 -> no-op (STRICT equality, not <=).
    _phase14_backup_gate(conn, current_version=20, target_version=22, backup_dir=tmp_path)
    _phase14_backup_gate(conn, current_version=22, target_version=22, backup_dir=tmp_path)
    _phase14_backup_gate(conn, current_version=21, target_version=21, backup_dir=tmp_path)  # target < 22
    assert list(tmp_path.glob("swing-pre-phase14-migration-*.db")) == []


def test_db_migrate_twice_is_noop(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    v_after_first = _current_version(conn)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)  # no-op
    assert _current_version(conn) == v_after_first == 22


def test_run_migrations_wires_gate_and_writes_backup_once(tmp_path):
    # Codex chain #2 Major #7: prove the gate is WIRED into run_migrations
    # (not just callable directly) -- a v21 -> v22 run writes exactly one
    # backup file at the boundary.
    conn = _fresh_v21_db(tmp_path)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    backups = list(tmp_path.glob("swing-pre-phase14-migration-*.db"))
    assert len(backups) == 1
    assert _current_version(conn) == 22


from swing.data.db import _apply_migration


def test_malformed_0022_rolls_back_through_runner(tmp_path, monkeypatch):
    """A 0022 variant that fails mid-script leaves the DB at v21 +
    in_transaction == False (test through the real _apply_migration path,
    NOT bare executescript) -- gotcha #9."""
    conn = _fresh_v21_db(tmp_path)
    bad_sql = tmp_path / "0022_bad.sql"
    bad_sql.write_text(
        "BEGIN;\n"
        "CREATE TABLE pattern_detection_events (detection_id INTEGER PRIMARY KEY);\n"
        "CREATE TABLE pattern_detection_events (x INTEGER);\n"  # duplicate -> error
        "UPDATE schema_version SET version = 22;\n"
        "COMMIT;\n",
        encoding="utf-8",
    )
    with pytest.raises(sqlite3.OperationalError):
        _apply_migration(conn, bad_sql)
    assert conn.in_transaction is False
    assert _current_version(conn) == 21
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "pattern_detection_events" not in tables  # rolled back


def test_check_rejects_bad_pattern_class(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO pattern_detection_events "
            "(ticker, detection_date, data_asof_date, pattern_class, "
            " structural_anchors_json, composite_score, detector_version, "
            " source, per_pattern_metadata_json, created_at) "
            "VALUES ('AAA','2026-05-29','2026-05-28','NOT_A_CLASS','{}',0.5,"
            "'v1','pipeline','{}','2026-05-29T00:00:00Z')"
        )


def test_check_rejects_bad_status(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    conn.execute(
        "INSERT INTO pattern_detection_events "
        "(detection_id, ticker, detection_date, data_asof_date, pattern_class, "
        " structural_anchors_json, composite_score, detector_version, source, "
        " per_pattern_metadata_json, created_at) "
        "VALUES (1,'AAA','2026-05-29','2026-05-28','vcp','{}',0.5,'v1',"
        "'pipeline','{}','2026-05-29T00:00:00Z')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO pattern_forward_observations "
            "(detection_id, observation_date, ohlc_today_json, status, "
            " sessions_since_detection, created_at) "
            "VALUES (1,'2026-05-29','{}','NOT_A_STATUS',1,'2026-05-29T00:00:00Z')"
        )


def test_check_rejects_negative_sessions_since_detection(tmp_path):
    # Codex chain #2 Major #2: the schema CHECK mirrors the dataclass validator.
    conn = _fresh_v21_db(tmp_path)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    conn.execute(
        "INSERT INTO pattern_detection_events "
        "(detection_id, ticker, detection_date, data_asof_date, pattern_class, "
        " structural_anchors_json, composite_score, detector_version, source, "
        " per_pattern_metadata_json, created_at) "
        "VALUES (1,'AAA','2026-05-29','2026-05-28','vcp','{}',0.5,'v1',"
        "'pipeline','{}','2026-05-29T00:00:00Z')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO pattern_forward_observations "
            "(detection_id, observation_date, ohlc_today_json, status, "
            " sessions_since_detection, created_at) "
            "VALUES (1,'2026-05-29','{}','pending',-1,'2026-05-29T00:00:00Z')"
        )
