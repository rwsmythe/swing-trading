"""Pipeline runs repo with lease-token fencing.

Every mutation function takes lease_token and raises LeaseRevoked if it doesn't
match the row's current value (or if the row's state is no longer 'running').
This is the only enforcement layer — the application can't bypass it.
"""
from __future__ import annotations

import sqlite3
import uuid

from swing.data.models import PipelineRun


class LeaseRevoked(Exception):
    """Raised when a write is attempted with a stale or wrong lease_token."""


def insert_pipeline_run(
    conn: sqlite3.Connection, *, started_ts: str, trigger: str,
    data_asof_date: str, action_session_date: str,
    lease_heartbeat_ts: str, finviz_csv_path: str | None = None,
    rs_universe_version: str | None = None, rs_universe_hash: str | None = None,
) -> tuple[int, str]:
    """Insert a fresh 'running' run row. Returns (run_id, lease_token).
    Caller should hold the new lease for all subsequent writes."""
    token = str(uuid.uuid4())
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, trigger, data_asof_date, action_session_date, state,
             lease_token, lease_heartbeat_ts, last_step_progress_ts,
             current_step, finviz_csv_path,
             rs_universe_version, rs_universe_hash)
        VALUES (?, ?, ?, ?, 'running', ?, ?, ?, 'lock', ?, ?, ?)
        """,
        (started_ts, trigger, data_asof_date, action_session_date, token,
         lease_heartbeat_ts, lease_heartbeat_ts, finviz_csv_path,
         rs_universe_version, rs_universe_hash),
    )
    return int(cur.lastrowid), token


def _check_lease(conn: sqlite3.Connection, run_id: int, lease_token: str) -> None:
    row = conn.execute(
        "SELECT lease_token, state FROM pipeline_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        raise LeaseRevoked(f"run {run_id} not found")
    if row[0] != lease_token or row[1] != "running":
        raise LeaseRevoked(
            f"run {run_id} lease revoked or state changed (state={row[1]})"
        )


def update_heartbeat(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str, heartbeat_ts: str
) -> None:
    _check_lease(conn, run_id, lease_token)
    conn.execute(
        "UPDATE pipeline_runs SET lease_heartbeat_ts = ? WHERE id = ?",
        (heartbeat_ts, run_id),
    )


def update_step(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str,
    step: str, progress_ts: str,
) -> None:
    _check_lease(conn, run_id, lease_token)
    conn.execute(
        "UPDATE pipeline_runs SET current_step = ?, last_step_progress_ts = ? WHERE id = ?",
        (step, progress_ts, run_id),
    )


def update_status_columns(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str, **status_cols: str
) -> None:
    """Update one or more *_status columns. Allowed keys: weather_status,
    evaluation_status, watchlist_status, recommendations_status,
    charts_status, export_status."""
    _check_lease(conn, run_id, lease_token)
    allowed = {
        "weather_status", "evaluation_status", "watchlist_status",
        "recommendations_status", "charts_status", "export_status",
    }
    bad = set(status_cols) - allowed
    if bad:
        raise ValueError(f"unknown status columns: {bad}")
    if not status_cols:
        return
    set_clause = ", ".join(f"{k} = ?" for k in status_cols)
    conn.execute(
        f"UPDATE pipeline_runs SET {set_clause} WHERE id = ?",
        (*status_cols.values(), run_id),
    )


def finalize_run(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str,
    state: str, finished_ts: str, error_message: str | None = None,
    warnings_json: str | None = None,
) -> None:
    """Move state to complete/failed and stamp finished_ts. Lease still required."""
    if state not in ("complete", "failed"):
        raise ValueError(f"invalid finalize state: {state}")
    _check_lease(conn, run_id, lease_token)
    conn.execute(
        """
        UPDATE pipeline_runs SET state = ?, finished_ts = ?,
               error_message = COALESCE(?, error_message),
               warnings_json = COALESCE(?, warnings_json)
        WHERE id = ?
        """,
        (state, finished_ts, error_message, warnings_json, run_id),
    )


def force_clear(
    conn: sqlite3.Connection, *, run_id: int, error_message: str
) -> None:
    """Admin recovery — does NOT take lease_token because lease is being revoked.
    Subsequent writes by the original holder will raise LeaseRevoked."""
    conn.execute(
        """
        UPDATE pipeline_runs SET state = 'force_cleared',
               error_message = ?
        WHERE id = ? AND state = 'running'
        """,
        (error_message, run_id),
    )


def find_active_run(conn: sqlite3.Connection) -> PipelineRun | None:
    """Returns any row with state='running'. Spec assumes one at a time."""
    row = conn.execute(
        f"SELECT {_PR_COLS} FROM pipeline_runs WHERE state='running' LIMIT 1"
    ).fetchone()
    return _row_to_run(row) if row else None


def find_run(conn: sqlite3.Connection, run_id: int) -> PipelineRun | None:
    row = conn.execute(
        f"SELECT {_PR_COLS} FROM pipeline_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    return _row_to_run(row) if row else None


def list_recent_runs(conn: sqlite3.Connection, *, limit: int = 20) -> list[PipelineRun]:
    rows = conn.execute(
        f"SELECT {_PR_COLS} FROM pipeline_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_run(r) for r in rows]


_PR_COLS = """id, started_ts, finished_ts, trigger, data_asof_date, action_session_date,
              state, lease_token, lease_heartbeat_ts, last_step_progress_ts,
              current_step, weather_status, evaluation_status, watchlist_status,
              recommendations_status, charts_status, export_status,
              rs_universe_version, rs_universe_hash, finviz_csv_path,
              error_message, warnings_json"""


def _row_to_run(row: tuple) -> PipelineRun:
    return PipelineRun(
        id=row[0], started_ts=row[1], finished_ts=row[2], trigger=row[3],
        data_asof_date=row[4], action_session_date=row[5], state=row[6],
        lease_token=row[7], lease_heartbeat_ts=row[8],
        last_step_progress_ts=row[9], current_step=row[10],
        weather_status=row[11], evaluation_status=row[12],
        watchlist_status=row[13], recommendations_status=row[14],
        charts_status=row[15], export_status=row[16],
        rs_universe_version=row[17], rs_universe_hash=row[18],
        finviz_csv_path=row[19], error_message=row[20], warnings_json=row[21],
    )
