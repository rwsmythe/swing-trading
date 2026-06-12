from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _current_version,
    _watchlist_pin_backup_gate,
    run_migrations,
)


def _migrate(tmp_path: Path, version: int, backup_dir: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=version, backup_dir=backup_dir or tmp_path)
    return conn


def test_expected_schema_version_is_28():
    assert EXPECTED_SCHEMA_VERSION == 29


def test_migrate_to_28_adds_three_pin_columns(tmp_path):
    conn = _migrate(tmp_path, 28)
    assert _current_version(conn) == 28
    cols = {r[1] for r in conn.execute("PRAGMA table_info(watchlist)").fetchall()}
    assert {"pinned", "pin_note", "pinned_at"} <= cols
    conn.execute(
        "INSERT INTO watchlist (ticker, added_date, last_qualified_date, status, "
        "qualification_count, not_qualified_streak, last_data_asof_date) VALUES "
        "('AAAA','2026-06-10','2026-06-10','watch',1,0,'2026-06-10')")
    row = conn.execute("SELECT pinned, pin_note, pinned_at FROM watchlist WHERE ticker='AAAA'").fetchone()
    assert row == (0, None, None)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE watchlist SET pinned = 2 WHERE ticker='AAAA'")
    conn.close()


def test_backup_gate_fires_strict_on_v27(tmp_path):
    conn = sqlite3.connect(":memory:")
    inert = tmp_path / "inert"; fire = tmp_path / "fire"; naive = tmp_path / "naive"
    _watchlist_pin_backup_gate(conn, current_version=28, target_version=28, backup_dir=inert)
    _watchlist_pin_backup_gate(conn, current_version=26, target_version=28, backup_dir=naive)
    assert not inert.exists() and not naive.exists()
    with pytest.raises(MigrationBackupRequiredException):
        _watchlist_pin_backup_gate(conn, current_version=27, target_version=28, backup_dir=fire)


def test_run_migrations_wires_watchlist_pin_gate(tmp_path):
    backups = tmp_path / "v27_backups"; backups.mkdir()
    conn = _migrate(tmp_path, 27); conn.close()
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=28, backup_dir=backups)
    assert _current_version(conn) == 28
    snaps = list(backups.glob("swing-pre-watchlist-pin-migration-*.db"))
    assert len(snaps) == 1
    conn.close()


def test_migrate_twice_is_noop(tmp_path):
    conn = _migrate(tmp_path, 28)
    run_migrations(conn, target_version=28)
    assert _current_version(conn) == 28
    cols = [r[1] for r in conn.execute("PRAGMA table_info(watchlist)").fetchall()]
    assert cols.count("pinned") == 1
    conn.close()
