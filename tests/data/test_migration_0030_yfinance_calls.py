from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _current_version,
    _phase18_arc_c_backup_gate,
    run_migrations,
)


def _migrate(tmp_path: Path, version: int, backup_dir: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=version, backup_dir=backup_dir or tmp_path)
    return conn


def _insert_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO pipeline_runs "
        "(started_ts, trigger, data_asof_date, action_session_date, state, lease_token) "
        "VALUES ('2026-06-14T00:00:00','manual','2026-06-13','2026-06-14','running','tok')"
    )
    return int(cur.lastrowid)


def test_expected_schema_version_is_30():
    assert EXPECTED_SCHEMA_VERSION == 30


def test_migrate_to_30_creates_yfinance_calls_table_and_indexes(tmp_path):
    conn = _migrate(tmp_path, 30)
    assert _current_version(conn) == 30
    cols = [r[1] for r in conn.execute("PRAGMA table_info(yfinance_calls)").fetchall()]
    assert cols == [
        "call_id", "ts", "call_type", "ticker", "ticker_count",
        "response_time_ms", "status", "rows_returned", "error_message",
        "pipeline_run_id", "surface",
    ]
    idx = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='yfinance_calls' AND name LIKE 'ix_%'"
        ).fetchall()
    }
    assert idx == {
        "ix_yfinance_calls_ts",
        "ix_yfinance_calls_status_ts",
        "ix_yfinance_calls_pipeline_run_id_ts",
        "ix_yfinance_calls_call_type_ts",
        "ix_yfinance_calls_surface_ts",
        "ix_yfinance_calls_ticker_ts",
    }
    conn.close()


def test_enum_checks(tmp_path):
    conn = _migrate(tmp_path, 30)
    # valid status / call_type / surface
    conn.execute(
        "INSERT INTO yfinance_calls (ts, call_type, ticker, status, surface) "
        "VALUES ('2026-06-14T00:00:00','download_single','AAPL','empty','cli')"
    )
    conn.execute(
        "INSERT INTO yfinance_calls (ts, call_type, ticker, status, surface) "
        "VALUES ('2026-06-14T00:00:00','download_intraday','AAPL','success','web')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls (ts, call_type, ticker, status, surface) "
            "VALUES ('2026-06-14T00:00:00','download_single','AAPL','bogus','cli')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls (ts, call_type, ticker, status, surface) "
            "VALUES ('2026-06-14T00:00:00','frobnicate','AAPL','success','cli')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls (ts, call_type, ticker, status, surface) "
            "VALUES ('2026-06-14T00:00:00','download_single','AAPL','success','mobile')"
        )
    conn.close()


def test_migration_0030_numeric_and_shape_checks(tmp_path):
    conn = _migrate(tmp_path, 30)
    # negative response_time_ms
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls "
            "(ts, call_type, ticker, response_time_ms, status, surface) "
            "VALUES ('2026-06-14T00:00:00','download_single','AAPL',-1,'success','cli')"
        )
    # negative rows_returned
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls "
            "(ts, call_type, ticker, rows_returned, status, surface) "
            "VALUES ('2026-06-14T00:00:00','download_single','AAPL',-1,'success','cli')"
        )
    # ticker_count <= 0
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls "
            "(ts, call_type, ticker_count, status, surface) "
            "VALUES ('2026-06-14T00:00:00','download_batch',0,'success','cli')"
        )
    # shape: download_batch with ticker set
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls "
            "(ts, call_type, ticker, ticker_count, status, surface) "
            "VALUES ('2026-06-14T00:00:00','download_batch','AAPL',3,'success','cli')"
        )
    # shape: download_single with ticker_count set
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls "
            "(ts, call_type, ticker, ticker_count, status, surface) "
            "VALUES ('2026-06-14T00:00:00','download_single','AAPL',3,'success','cli')"
        )
    # valid batch in-flight row: ticker_count set, ticker NULL
    conn.execute(
        "INSERT INTO yfinance_calls (ts, call_type, ticker_count, status, surface) "
        "VALUES ('2026-06-14T00:00:00','download_batch',5,'in_flight','pipeline')"
    )
    conn.close()


def test_empty_ticker_rejected(tmp_path):
    conn = _migrate(tmp_path, 30)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls (ts, call_type, ticker, status, surface) "
            "VALUES ('2026-06-14T00:00:00','download_single','','success','cli')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls (ts, call_type, ticker, status, surface) "
            "VALUES ('2026-06-14T00:00:00','download_single','   ','success','cli')"
        )
    conn.close()


def test_no_sql_run_linkage_check_pipeline_null_run_id_allowed(tmp_path):
    # Section-9 LOCK: NO SQL run-linkage CHECK. A pipeline row with NULL run id
    # is ACCEPTED at the SQL layer (post-prune NULLed rows must round-trip).
    conn = _migrate(tmp_path, 30)
    conn.execute(
        "INSERT INTO yfinance_calls (ts, call_type, ticker, status, surface) "
        "VALUES ('2026-06-14T00:00:00','download_single','AAPL','success','pipeline')"
    )
    # and a cli row WITH a non-null run id is also accepted (no SQL CHECK)
    run_id = _insert_run(conn)
    conn.execute(
        "INSERT INTO yfinance_calls "
        "(ts, call_type, ticker, status, surface, pipeline_run_id) "
        "VALUES ('2026-06-14T00:00:00','download_single','AAPL','success','cli',?)",
        (run_id,),
    )
    conn.close()


def test_fk_set_null_on_parent_delete(tmp_path):
    # Section-9 LOCK: ON DELETE SET NULL. Deleting a referenced pipeline_runs row
    # SUCCEEDS; the yfinance row SURVIVES with pipeline_run_id NULL.
    conn = _migrate(tmp_path, 30)
    run_id = _insert_run(conn)
    cur = conn.execute(
        "INSERT INTO yfinance_calls "
        "(ts, call_type, ticker_count, status, surface, pipeline_run_id) "
        "VALUES ('2026-06-14T00:00:00','download_batch',4,'success','pipeline',?)",
        (run_id,),
    )
    call_id = int(cur.lastrowid)
    # invalid fk rejected
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO yfinance_calls "
            "(ts, call_type, ticker_count, status, surface, pipeline_run_id) "
            "VALUES ('2026-06-14T00:00:00','download_batch',4,'success','pipeline',999999)"
        )
    # parent delete succeeds + child survives with NULL run id
    conn.execute("DELETE FROM pipeline_runs WHERE id=?", (run_id,))
    row = conn.execute(
        "SELECT pipeline_run_id FROM yfinance_calls WHERE call_id=?", (call_id,)
    ).fetchone()
    assert row == (None,)
    conn.close()


def test_migrate_twice_is_noop(tmp_path):
    conn = _migrate(tmp_path, 30)
    run_migrations(conn, target_version=30)
    assert _current_version(conn) == 30
    tbls = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='yfinance_calls'"
        ).fetchall()
    ]
    assert tbls == ["yfinance_calls"]
    conn.close()


def test_backup_gate_fires_strict_on_v29(tmp_path):
    conn = sqlite3.connect(":memory:")
    inert = tmp_path / "inert"; fire = tmp_path / "fire"; naive = tmp_path / "naive"
    _phase18_arc_c_backup_gate(conn, current_version=30, target_version=30, backup_dir=inert)
    _phase18_arc_c_backup_gate(conn, current_version=28, target_version=30, backup_dir=naive)
    assert not inert.exists() and not naive.exists()
    with pytest.raises(MigrationBackupRequiredException):
        _phase18_arc_c_backup_gate(conn, current_version=29, target_version=30, backup_dir=fire)


def test_run_migrations_wires_phase18_arc_c_gate(tmp_path):
    backups = tmp_path / "v29_backups"; backups.mkdir()
    conn = _migrate(tmp_path, 29); conn.close()
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=30, backup_dir=backups)
    assert _current_version(conn) == 30
    snaps = list(backups.glob("swing-pre-phase18-arc-c-migration-*.db"))
    assert len(snaps) == 1
    conn.close()


def test_fresh_v0_walk_does_not_fire_phase18_arc_c_gate(tmp_path):
    backups = tmp_path / "fresh_backups"; backups.mkdir()
    conn = _migrate(tmp_path, 30, backup_dir=backups)
    snaps = list(backups.glob("swing-pre-phase18-arc-c-migration-*.db"))
    assert snaps == []
    conn.close()
