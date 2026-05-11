"""Pipeline runs repo with lease-token fencing.

Every mutation function takes lease_token and raises LeaseRevokedError if it doesn't
match the row's current value (or if the row's state is no longer 'running').
This is the only enforcement layer — the application can't bypass it.
"""
from __future__ import annotations

import sqlite3
import uuid

from swing.data.models import PipelineChartTarget, PipelineRun


class LeaseRevokedError(Exception):
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


def _raise_revoked_if_no_row(conn: sqlite3.Connection, run_id: int) -> None:
    """If a lease-fenced UPDATE matched 0 rows, diagnose which condition failed
    (run missing, lease_token mismatch, or state change) and raise LeaseRevokedError
    with a useful message. Called AFTER a rowcount==0 UPDATE so the read happens
    inside the same transaction as the failed update."""
    row = conn.execute(
        "SELECT lease_token, state FROM pipeline_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        raise LeaseRevokedError(f"run {run_id} not found")
    raise LeaseRevokedError(
        f"run {run_id} lease revoked or state changed (state={row[1]})"
    )


def update_heartbeat(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str, heartbeat_ts: str
) -> None:
    # Lease fencing done in the UPDATE's WHERE clause (atomic — no TOCTOU race).
    cur = conn.execute(
        """
        UPDATE pipeline_runs SET lease_heartbeat_ts = ?
        WHERE id = ? AND lease_token = ? AND state = 'running'
        """,
        (heartbeat_ts, run_id, lease_token),
    )
    if cur.rowcount == 0:
        _raise_revoked_if_no_row(conn, run_id)


def update_step(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str,
    step: str, progress_ts: str,
) -> None:
    cur = conn.execute(
        """
        UPDATE pipeline_runs SET current_step = ?, last_step_progress_ts = ?
        WHERE id = ? AND lease_token = ? AND state = 'running'
        """,
        (step, progress_ts, run_id, lease_token),
    )
    if cur.rowcount == 0:
        _raise_revoked_if_no_row(conn, run_id)


def update_status_columns(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str, **status_cols: str
) -> None:
    """Update one or more *_status columns. Allowed keys: weather_status,
    evaluation_status, watchlist_status, recommendations_status,
    charts_status, export_status. Lease-fenced atomically in the WHERE clause."""
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
    cur = conn.execute(
        f"""UPDATE pipeline_runs SET {set_clause}
            WHERE id = ? AND lease_token = ? AND state = 'running'""",
        (*status_cols.values(), run_id, lease_token),
    )
    if cur.rowcount == 0:
        _raise_revoked_if_no_row(conn, run_id)


def finalize_run(
    conn: sqlite3.Connection, *, run_id: int, lease_token: str,
    state: str, finished_ts: str, error_message: str | None = None,
    warnings_json: str | None = None,
) -> None:
    """Move state to complete/failed and stamp finished_ts.
    Lease-fenced atomically in the WHERE clause."""
    if state not in ("complete", "failed"):
        raise ValueError(f"invalid finalize state: {state}")
    cur = conn.execute(
        """
        UPDATE pipeline_runs SET state = ?, finished_ts = ?,
               error_message = COALESCE(?, error_message),
               warnings_json = COALESCE(?, warnings_json)
        WHERE id = ? AND lease_token = ? AND state = 'running'
        """,
        (state, finished_ts, error_message, warnings_json, run_id, lease_token),
    )
    if cur.rowcount == 0:
        _raise_revoked_if_no_row(conn, run_id)


def force_clear(
    conn: sqlite3.Connection, *, run_id: int, error_message: str
) -> None:
    """Admin recovery — does NOT take lease_token because lease is being revoked.
    Subsequent writes by the original holder will raise LeaseRevokedError."""
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
              error_message, warnings_json, evaluation_run_id"""


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
        evaluation_run_id=row[22],
    )


# ---------------------------------------------------------------------------
# Tranche C T2: pipeline_runs.evaluation_run_id + pipeline_chart_targets repo.
#
# These mutations do NOT take lease_token — they are designed to be called
# from inside a `lease.fenced_write()` transaction whose lease was already
# verified atomically by the surrounding context manager. Callers outside a
# fenced_write must establish their own atomic fence; otherwise the lease
# guarantee for the larger pipeline mutation does not extend to these writes.
# ---------------------------------------------------------------------------


def set_evaluation_run_id(
    conn: sqlite3.Connection, *, pipeline_run_id: int, evaluation_run_id: int,
) -> None:
    """Bind a pipeline_runs row to the evaluation_runs row produced by its own
    `_step_evaluate`. Called from inside `lease.fenced_write()` so the FK
    write lands atomically with the eval-row insert."""
    conn.execute(
        "UPDATE pipeline_runs SET evaluation_run_id = ? WHERE id = ?",
        (evaluation_run_id, pipeline_run_id),
    )


def insert_chart_target(
    conn: sqlite3.Connection, *, pipeline_run_id: int, ticker: str,
    source: str, chart_status: str = "pending",
) -> int:
    """Persist one row in pipeline_chart_targets. Initial status defaults to
    'pending' so the chart step can update per-ticker as outcomes are known
    (`pending` → `ok` | `fetcher_failed` | `too_few_bars`).

    The (pipeline_run_id, ticker) UNIQUE constraint surfaces as
    sqlite3.IntegrityError on duplicate insert — caller must dedupe.
    """
    cur = conn.execute(
        """INSERT INTO pipeline_chart_targets
           (pipeline_run_id, ticker, source, chart_status)
           VALUES (?, ?, ?, ?)""",
        (pipeline_run_id, ticker, source, chart_status),
    )
    return int(cur.lastrowid)


def update_chart_target_status(
    conn: sqlite3.Connection, *, pipeline_run_id: int, ticker: str,
    chart_status: str,
) -> None:
    """Transition a target's chart_status. Silent no-op when no row matches —
    the chart step inserts before update, but a defensive call after a
    filter-out should not fail the surrounding fenced_write."""
    conn.execute(
        """UPDATE pipeline_chart_targets SET chart_status = ?
           WHERE pipeline_run_id = ? AND ticker = ?""",
        (chart_status, pipeline_run_id, ticker),
    )


def list_chart_targets(
    conn: sqlite3.Connection, *, pipeline_run_id: int,
) -> list[PipelineChartTarget]:
    """All chart targets for one pipeline run, ordered by id (insertion order)."""
    rows = conn.execute(
        """SELECT id, pipeline_run_id, ticker, source, chart_status
           FROM pipeline_chart_targets
           WHERE pipeline_run_id = ? ORDER BY id""",
        (pipeline_run_id,),
    ).fetchall()
    return [
        PipelineChartTarget(
            id=r[0], pipeline_run_id=r[1], ticker=r[2],
            source=r[3], chart_status=r[4],
        )
        for r in rows
    ]
