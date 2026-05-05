"""Origin service tests — bucket × entry_path → trade_origin per spec §10.1."""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.db import run_migrations
from swing.trades.origin import EntryPath, derive_trade_origin


def _seed_v14(tmp_path) -> sqlite3.Connection:
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    return conn


def _insert_evaluation_run(
    conn: sqlite3.Connection,
    *,
    eval_id: int,
    run_ts: str = "2026-05-04T08:15:00",
    data_asof: str = "2026-05-01",
    action_session: str = "2026-05-04",
) -> None:
    """Insert an evaluation_runs row with NOT NULL count fields zero-filled."""
    conn.execute(
        "INSERT INTO evaluation_runs "
        "(id, run_ts, data_asof_date, action_session_date, "
        " tickers_evaluated, aplus_count, watch_count, skip_count, "
        " excluded_count, error_count) "
        "VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0)",
        (eval_id, run_ts, data_asof, action_session),
    )


def _insert_pipeline_run(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    eval_run_id: int | None,
    finished: bool = True,
    started_ts: str = "2026-05-04T08:00:00",
    finished_ts: str | None = "2026-05-04T08:30:00",
    data_asof: str = "2026-05-01",
    action_session: str = "2026-05-04",
) -> None:
    """Insert a pipeline_runs row.

    pipeline_runs.state CHECK enum is ('running','complete','failed',
    'blocked','force_cleared'); 'complete' is the success terminal.
    NOT NULL fields: started_ts, trigger, data_asof_date,
    action_session_date, state, lease_token.
    """
    conn.execute(
        "INSERT INTO pipeline_runs "
        "(id, started_ts, finished_ts, trigger, data_asof_date, "
        " action_session_date, state, lease_token, evaluation_run_id) "
        "VALUES (?, ?, ?, 'manual', ?, ?, ?, ?, ?)",
        (
            run_id,
            started_ts,
            finished_ts if finished else None,
            data_asof,
            action_session,
            "complete" if finished else "running",
            f"lease-{run_id}",
            eval_run_id,
        ),
    )


def _insert_candidate(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    bucket: str,
    eval_run_id: int,
) -> None:
    """Insert a candidates row.

    NOT NULL fields: evaluation_run_id, ticker, bucket, rs_method,
    sector, industry. Other columns default NULL.
    """
    conn.execute(
        "INSERT INTO candidates "
        "(evaluation_run_id, ticker, bucket, close, pivot, initial_stop, "
        " adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, "
        " rs_return_12w_vs_spy, rs_method, pattern_tag, notes, sector, "
        " industry) "
        "VALUES (?, ?, ?, 10.0, NULL, 9.0, 5.0, 3, 5.0, 30.0, 50, 0.1, "
        "'universe', 'vcp', NULL, '', '')",
        (eval_run_id, ticker, bucket),
    )


@pytest.mark.parametrize(
    "bucket,entry_path,expected",
    [
        ("aplus", EntryPath.APLUS_TODAY_DECISION, "pipeline_aplus"),
        ("aplus", EntryPath.HYP_RECS_BUTTON, "pipeline_aplus"),
        ("aplus", EntryPath.MANUAL_WEB_FORM, "pipeline_aplus"),
        ("aplus", EntryPath.CLI_MANUAL, "pipeline_aplus"),
        ("watch", EntryPath.HYP_RECS_BUTTON, "pipeline_watch_hyp_recs"),
        ("watch", EntryPath.MANUAL_WEB_FORM, "pipeline_watch_manual"),
        ("watch", EntryPath.CLI_MANUAL, "pipeline_watch_manual"),
        ("watch", EntryPath.APLUS_TODAY_DECISION, "pipeline_watch_manual"),
        ("skip", EntryPath.HYP_RECS_BUTTON, "manual_off_pipeline"),
        ("error", EntryPath.MANUAL_WEB_FORM, "manual_off_pipeline"),
        ("excluded", EntryPath.CLI_MANUAL, "manual_off_pipeline"),
    ],
)
def test_derive_trade_origin_per_cell(tmp_path, bucket, entry_path, expected):
    """11 cells: 4 aplus (entry-path-invariant) + 4 watch (path-sensitive)
    + 3 off-pipeline-bucket (entry-path-invariant)."""
    conn = _seed_v14(tmp_path)
    with conn:
        _insert_evaluation_run(conn, eval_id=10)
        _insert_pipeline_run(conn, run_id=1, eval_run_id=10)
        _insert_candidate(conn, ticker="TST", bucket=bucket, eval_run_id=10)
    assert derive_trade_origin(conn, "TST", entry_path) == expected


def test_derive_trade_origin_ticker_absent_returns_manual_off_pipeline(tmp_path):
    """Ticker not in candidates → manual_off_pipeline regardless of entry_path."""
    conn = _seed_v14(tmp_path)
    with conn:
        _insert_evaluation_run(conn, eval_id=10)
        _insert_pipeline_run(conn, run_id=1, eval_run_id=10)
        # No candidate row for TST.
    assert (
        derive_trade_origin(conn, "TST", EntryPath.MANUAL_WEB_FORM)
        == "manual_off_pipeline"
    )


def test_derive_trade_origin_no_completed_pipeline_returns_manual(tmp_path):
    """Pipeline run exists but unfinished (state='running') →
    manual_off_pipeline even when a candidate row exists for the ticker."""
    conn = _seed_v14(tmp_path)
    with conn:
        _insert_evaluation_run(conn, eval_id=10)
        _insert_pipeline_run(
            conn, run_id=1, eval_run_id=10, finished=False, finished_ts=None,
        )
        _insert_candidate(conn, ticker="TST", bucket="aplus", eval_run_id=10)
    assert (
        derive_trade_origin(conn, "TST", EntryPath.HYP_RECS_BUTTON)
        == "manual_off_pipeline"
    )


def test_derive_trade_origin_falls_back_to_yesterday_run(tmp_path):
    """Yesterday's run COMPLETE; today's still running → uses yesterday's
    evaluation_run candidates (most-recent COMPLETE wins)."""
    conn = _seed_v14(tmp_path)
    with conn:
        # Yesterday's complete run + its evaluation.
        _insert_evaluation_run(
            conn, eval_id=10, run_ts="2026-05-03T08:15:00",
            data_asof="2026-04-30", action_session="2026-05-03",
        )
        _insert_pipeline_run(
            conn, run_id=1, eval_run_id=10,
            started_ts="2026-05-03T08:00:00",
            finished_ts="2026-05-03T08:30:00",
            data_asof="2026-04-30", action_session="2026-05-03",
        )
        _insert_candidate(conn, ticker="TST", bucket="aplus", eval_run_id=10)
        # Today's run still running, no candidates yet.
        _insert_pipeline_run(
            conn, run_id=2, eval_run_id=None, finished=False,
            finished_ts=None, started_ts="2026-05-04T08:00:00",
        )
    assert (
        derive_trade_origin(conn, "TST", EntryPath.HYP_RECS_BUTTON)
        == "pipeline_aplus"
    )
