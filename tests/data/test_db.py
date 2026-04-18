"""Tests for swing.data.db."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, SchemaVersionMismatch, connect, ensure_schema


def test_ensure_schema_applies_migrations_on_fresh_db(tmp_db: Path):
    conn = ensure_schema(tmp_db)
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == EXPECTED_SCHEMA_VERSION
    # evaluation_runs exists
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evaluation_runs'"
    )
    assert cur.fetchone() is not None
    conn.close()


def test_connect_refuses_old_schema(tmp_db: Path):
    # Create a DB with schema_version = 0 (pre-migration)
    conn = sqlite3.connect(tmp_db)
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_version VALUES (0)")
    conn.commit()
    conn.close()

    with pytest.raises(SchemaVersionMismatch) as exc:
        connect(tmp_db)
    assert "db-migrate" in str(exc.value)


def test_connect_works_after_ensure_schema(tmp_db: Path):
    ensure_schema(tmp_db).close()
    conn = connect(tmp_db)
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == EXPECTED_SCHEMA_VERSION
    conn.close()


def test_connect_raises_when_db_missing(tmp_path: Path):
    missing = tmp_path / "nope.db"
    with pytest.raises(SchemaVersionMismatch) as exc:
        connect(missing)
    assert "db-migrate" in str(exc.value)
