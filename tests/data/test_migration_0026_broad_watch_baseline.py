from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _broad_watch_baseline_backup_gate,
    _current_version,
    run_migrations,
)


def _migrate(tmp_path: Path, version: int, backup_dir: Path | None = None):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=version,
                   backup_dir=backup_dir or tmp_path)
    return conn


def test_expected_schema_version_is_27():
    assert EXPECTED_SCHEMA_VERSION == 30


def test_migrate_to_26_seeds_broad_watch_row(tmp_path):
    conn = _migrate(tmp_path, 26)
    assert _current_version(conn) == 26
    row = conn.execute(
        "SELECT name, target_sample_size, status, consecutive_loss_tripwire, "
        "absolute_loss_tripwire_pct, created_at, statement, decision_criteria, notes "
        "FROM hypothesis_registry WHERE name = 'Broad-watch baseline'"
    ).fetchone()
    assert row is not None
    assert row[1] == 30                      # target_sample_size
    assert row[2] == "active"                # status (default)
    assert row[3] == 5                       # consecutive_loss_tripwire
    assert row[4] == 5.0                     # absolute_loss_tripwire_pct
    assert row[5] == "2026-06-09"            # created_at
    assert row[6].startswith("The widened watch pool")
    assert row[7].startswith("SHADOW-measured (not closed live trades)")
    assert "V2.1 §VII.F" in row[8]
    # exactly 5 rows; the 4 frozen rows untouched.
    assert conn.execute("SELECT COUNT(*) FROM hypothesis_registry").fetchone()[0] == 5
    conn.close()


def test_migrate_to_26_seeds_one_open_history_interval(tmp_path):
    conn = _migrate(tmp_path, 26)
    hid = conn.execute(
        "SELECT id FROM hypothesis_registry WHERE name='Broad-watch baseline'"
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT status, effective_from, effective_to FROM hypothesis_status_history "
        "WHERE hypothesis_id = ?", (hid,)).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "active"
    assert rows[0][1] == "2026-06-09T00:00:00.000"
    assert rows[0][2] is None                # one OPEN interval
    conn.close()


def test_migrate_twice_is_noop(tmp_path):
    conn = _migrate(tmp_path, 26)
    run_migrations(conn, target_version=26)  # current >= target -> early return
    assert _current_version(conn) == 26
    assert conn.execute(
        "SELECT COUNT(*) FROM hypothesis_registry WHERE name='Broad-watch baseline'"
    ).fetchone()[0] == 1
    hid = conn.execute(
        "SELECT id FROM hypothesis_registry WHERE name='Broad-watch baseline'"
    ).fetchone()[0]
    assert conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history WHERE hypothesis_id=?",
        (hid,)).fetchone()[0] == 1           # NO second open interval
    conn.close()


def test_backup_gate_fires_strict_on_v25(tmp_path):
    # In-memory connection -> file-backed source is absent -> raises.
    conn = sqlite3.connect(":memory:")
    inert = tmp_path / "inert"; fire = tmp_path / "fire"; naive = tmp_path / "naive"
    # current==26 -> already past, inert (no raise).
    _broad_watch_baseline_backup_gate(conn, current_version=26, target_version=26,
                                      backup_dir=inert)
    # current==24, target==26 -> multi-version jump bypasses the v25-strict gate.
    _broad_watch_baseline_backup_gate(conn, current_version=24, target_version=26,
                                      backup_dir=naive)
    assert not inert.exists() and not naive.exists()
    # current==25, target>=26 -> fires; in-memory source -> raises.
    with pytest.raises(MigrationBackupRequiredException):
        _broad_watch_baseline_backup_gate(conn, current_version=25, target_version=26,
                                          backup_dir=fire)


def test_run_migrations_wires_broad_watch_gate(tmp_path):
    # v25 DB crossing v26 through the REAL runner writes exactly one backup.
    backups = tmp_path / "v25_backups"; backups.mkdir()
    conn = _migrate(tmp_path, 25)            # build a real file-backed v25 DB
    conn.close()
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=26, backup_dir=backups)
    assert _current_version(conn) == 26
    snaps = list(backups.glob("swing-pre-broad-watch-baseline-migration-*.db"))
    assert len(snaps) == 1
    conn.close()
