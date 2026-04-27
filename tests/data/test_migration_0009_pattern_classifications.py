import sqlite3
from pathlib import Path
import pytest
from swing.data.db import ensure_schema


def test_migration_0009_creates_pattern_classifications_table(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='pipeline_pattern_classifications'"
        )
        assert cur.fetchone() is not None
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_pattern_classifications_run'"
        )
        assert cur.fetchone() is not None
        cur = conn.execute("SELECT version FROM schema_version")
        assert cur.fetchone()[0] >= 9
    finally:
        conn.close()


def test_migration_0009_pattern_state_consistency_check_rejects_mixed_state(tmp_path: Path):
    """Row-level CHECK rejects pattern='flag' with NULL confidence/pivot."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) "
            "VALUES ('2026-04-26T00:00:00', 'manual', '2026-04-25', "
            "'2026-04-26', 'complete', 'tok')"
        )
        run_id = conn.execute("SELECT id FROM pipeline_runs").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError) as exc_info:
            conn.execute(
                "INSERT INTO pipeline_pattern_classifications "
                "(pipeline_run_id, ticker, pattern, confidence, components_json, computed_at) "
                "VALUES (?, ?, 'flag', NULL, '{}', '2026-04-26T00:00:00')",
                (run_id, "TEST"),
            )
        assert "pattern_state_consistency" in str(exc_info.value) or "CHECK" in str(exc_info.value)
    finally:
        conn.close()


def test_migration_0009_idempotent_on_v9_or_later(tmp_path: Path):
    """A second ensure_schema on an already-migrated DB is a no-op."""
    db = tmp_path / "swing.db"
    conn1 = ensure_schema(db)
    conn1.close()
    conn2 = ensure_schema(db)
    try:
        cur = conn2.execute("SELECT version FROM schema_version")
        assert cur.fetchone()[0] >= 9
    finally:
        conn2.close()
