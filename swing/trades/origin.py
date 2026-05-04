"""Trade-origin derivation service (Phase 7 §10).

Maps (candidates.bucket × entry_path) → 4-value trade_origin enum.
Lookup uses the most-recent-COMPLETE pipeline_runs row's evaluation_run_id
to find the candidates row for the ticker; if none completed (or the
ticker is not in that run's candidates), falls back to manual_off_pipeline.

The pipeline_runs.state CHECK enum is ('running','complete','failed',
'blocked','force_cleared') — we filter on 'complete' (not 'completed').
candidates.evaluation_run_id (NOT pipeline_run_id) is the join key into
evaluation_runs.id, which pipeline_runs.evaluation_run_id references once
the evaluate step finishes.
"""
from __future__ import annotations

import sqlite3
from enum import StrEnum


class EntryPath(StrEnum):
    APLUS_TODAY_DECISION = "aplus_today_decision"
    HYP_RECS_BUTTON = "hyp_recs_button"
    MANUAL_WEB_FORM = "manual_web_form"
    CLI_MANUAL = "cli_manual"


def _latest_complete_evaluation_run_id(conn: sqlite3.Connection) -> int | None:
    """Return the evaluation_run_id of the most-recent COMPLETE pipeline run.

    Returns None when no pipeline run has reached state='complete' with a
    non-NULL evaluation_run_id (legacy pre-0006 rows, or a fresh DB).
    """
    row = conn.execute(
        "SELECT evaluation_run_id FROM pipeline_runs "
        "WHERE state = 'complete' AND evaluation_run_id IS NOT NULL "
        "ORDER BY finished_ts DESC, id DESC LIMIT 1"
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def _bucket_for_ticker(
    conn: sqlite3.Connection, ticker: str, evaluation_run_id: int,
) -> str | None:
    row = conn.execute(
        "SELECT bucket FROM candidates "
        "WHERE evaluation_run_id = ? AND ticker = ?",
        (evaluation_run_id, ticker),
    ).fetchone()
    return row[0] if row else None


def derive_trade_origin(
    conn: sqlite3.Connection, ticker: str, entry_path: EntryPath,
) -> str:
    """Map (candidates.bucket × entry_path) → trade_origin enum.

    Per spec §10.1 / §10.4. Returns one of:
      pipeline_aplus, pipeline_watch_hyp_recs, pipeline_watch_manual,
      manual_off_pipeline.
    """
    eval_run_id = _latest_complete_evaluation_run_id(conn)
    if eval_run_id is None:
        return "manual_off_pipeline"
    bucket = _bucket_for_ticker(conn, ticker, eval_run_id)
    if bucket is None:
        return "manual_off_pipeline"
    if bucket == "aplus":
        return "pipeline_aplus"
    if bucket == "watch":
        if entry_path == EntryPath.HYP_RECS_BUTTON:
            return "pipeline_watch_hyp_recs"
        return "pipeline_watch_manual"
    # skip / error / excluded → off-pipeline.
    return "manual_off_pipeline"
