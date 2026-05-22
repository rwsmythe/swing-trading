import sqlite3
from pathlib import Path

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema


def test_migration_0015_creates_finviz_api_calls_table(tmp_path: Path) -> None:
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    try:
        # PRAGMA preserved — production-equivalent fixture state (Phase 7 Sub-A lesson).
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1, "ensure_schema must enable foreign_keys=ON"

        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 21, f"expected v21 after ensure_schema walks to HEAD, got v{version}"

        cols = {
            r[1]: r[2]
            for r in conn.execute("PRAGMA table_info(finviz_api_calls)").fetchall()
        }
        assert cols == {
            "call_id": "INTEGER",
            "ts": "TEXT",
            "screen_query": "TEXT",
            "status": "TEXT",
            "row_count": "INTEGER",
            "response_time_ms": "INTEGER",
            "rate_limit_remaining": "INTEGER",
            "signature_hash": "TEXT",
            "error_message": "TEXT",
        }, cols

        # CHECK constraint enforces enum.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO finviz_api_calls (ts, screen_query, status) "
                "VALUES (?, ?, ?)",
                ("2026-05-05T12:00:00", "v=152", "INVALID_STATUS"),
            )
            conn.commit()

        # Index exists on ts DESC.
        idx_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='finviz_api_calls'"
        ).fetchall()
        idx_names = {r[0] for r in idx_rows}
        assert "ix_finviz_api_calls_ts_desc" in idx_names, idx_names
    finally:
        conn.close()


def test_expected_schema_version_is_19() -> None:
    """Schema-version pin: this test trips when a new migration lands AND drift
    detection catches accidental skips of the migration version constant."""
    assert EXPECTED_SCHEMA_VERSION == 21
