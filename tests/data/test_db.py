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


def test_trades_table_has_hypothesis_label_column(tmp_db: Path):
    """Migration 0007: trades.hypothesis_label TEXT NULL exists post-migration.

    Per trade-hypothesis-label brief — the operator-facing free-text label is
    persisted on the entry-recording table (`trades`) so it round-trips with
    every entry event. Column is nullable; existing rows have NULL.
    """
    conn = ensure_schema(tmp_db)
    try:
        cols = conn.execute("PRAGMA table_info(trades)").fetchall()
        # PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk)
        names = [c[1] for c in cols]
        assert "hypothesis_label" in names
        col = next(c for c in cols if c[1] == "hypothesis_label")
        assert col[2].upper() == "TEXT"
        assert col[3] == 0  # NOT NULL == 0 → nullable
        # NULL insert is allowed (existing-call-site preservation):
        conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
            "initial_stop, current_stop, status) "
            "VALUES ('XYZ', '2026-04-25', 10.0, 1, 9.0, 9.0, 'open')"
        )
        row = conn.execute(
            "SELECT hypothesis_label FROM trades WHERE ticker='XYZ'"
        ).fetchone()
        assert row[0] is None
    finally:
        conn.close()
