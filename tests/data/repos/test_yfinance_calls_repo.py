from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import run_migrations
from swing.data.models import YfinanceCall
from swing.data.repos import yfinance_calls as repo


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp_path / "t.db")
    c.execute("PRAGMA foreign_keys=ON")
    run_migrations(c, target_version=30, backup_dir=tmp_path)
    return c


def test_insert_in_flight_returns_id_and_status(conn):
    call_id = repo.insert_in_flight(
        conn, ts="2026-06-14T00:00:00", call_type="download_single",
        ticker="AAPL", ticker_count=None, pipeline_run_id=None, surface="cli",
    )
    assert isinstance(call_id, int)
    row = repo.get_call(conn, call_id=call_id)
    assert row.status == "in_flight"
    assert row.call_type == "download_single"
    assert row.ticker == "AAPL"


def test_insert_in_flight_does_not_commit(conn):
    # caller controls tx: insert under an explicit BEGIN, rollback, expect gone.
    conn.execute("BEGIN")
    call_id = repo.insert_in_flight(
        conn, ts="2026-06-14T00:00:00", call_type="download_batch",
        ticker=None, ticker_count=3, pipeline_run_id=None, surface="cli",
    )
    conn.rollback()
    assert repo.get_call(conn, call_id=call_id) is None


def test_update_call_outcome_preserves_pk(conn):
    call_id = repo.insert_in_flight(
        conn, ts="2026-06-14T00:00:00", call_type="download_single",
        ticker="AAPL", ticker_count=None, pipeline_run_id=None, surface="cli",
    )
    repo.update_call_outcome(
        conn, call_id=call_id, response_time_ms=42, status="success",
        rows_returned=10, error_message=None,
    )
    row = repo.get_call(conn, call_id=call_id)
    assert row.call_id == call_id
    assert row.status == "success"
    assert row.response_time_ms == 42
    assert row.rows_returned == 10
    # exactly one row
    n = conn.execute("SELECT COUNT(*) FROM yfinance_calls").fetchone()[0]
    assert n == 1


def test_get_call_round_trips_through_model(conn):
    call_id = repo.insert_in_flight(
        conn, ts="2026-06-14T00:00:00", call_type="download_intraday",
        ticker="MSFT", ticker_count=None, pipeline_run_id=None, surface="web",
    )
    repo.update_call_outcome(
        conn, call_id=call_id, response_time_ms=7, status="empty",
        rows_returned=0, error_message=None,
    )
    row = repo.get_call(conn, call_id=call_id)
    assert isinstance(row, YfinanceCall)
    assert row.surface == "web"
    assert row.status == "empty"
    assert row.rows_returned == 0


def test_get_call_missing_returns_none(conn):
    assert repo.get_call(conn, call_id=999999) is None


def test_row_to_model_column_order(conn):
    # A column-order regression: insert directly with known values per column
    # and confirm _row_to_model maps each to the right field.
    run_id = conn.execute(
        "INSERT INTO pipeline_runs "
        "(started_ts, trigger, data_asof_date, action_session_date, state, lease_token) "
        "VALUES ('2026-06-14T00:00:00','manual','2026-06-13','2026-06-14','running','tok')"
    ).lastrowid
    conn.execute(
        "INSERT INTO yfinance_calls (call_id, ts, call_type, ticker, ticker_count, "
        "response_time_ms, status, rows_returned, error_message, pipeline_run_id, "
        "surface) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (500, "2026-06-14T01:02:03", "download_batch", None, 6, 99, "error", 0,
         "boom", run_id, "pipeline"),
    )
    row = repo.get_call(conn, call_id=500)
    assert row.call_id == 500
    assert row.ts == "2026-06-14T01:02:03"
    assert row.call_type == "download_batch"
    assert row.ticker is None
    assert row.ticker_count == 6
    assert row.response_time_ms == 99
    assert row.status == "error"
    assert row.rows_returned == 0
    assert row.error_message == "boom"
    assert row.pipeline_run_id == run_id
    assert row.surface == "pipeline"
