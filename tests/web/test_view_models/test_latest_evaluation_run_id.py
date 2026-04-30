"""Determinism guards for `latest_evaluation_run_id`.

Task 1 of the hyp-recs success-path fix plan: both branches of the helper
(pipeline-bound primary and standalone-eval fallback) must resolve ties on
the primary sort key (`finished_ts` / `run_ts`) deterministically by
falling through to `id DESC`. Without a secondary sort, SQLite's tied-key
ordering is unspecified, so downstream consumers (`build_hyp_recs_section`,
`build_dashboard`) inherit a half-deterministic anchor.

Pre-fix discriminating setup: lower-id row is inserted FIRST so its rowid
is lower; without `id DESC`, SQLite's tied-key `ORDER BY finished_ts DESC`
returns the lower-rowid row first, the helper returns the wrong
evaluation_run_id, and the test deterministically FAILs. Post-fix, the
explicit `id DESC` clause picks the higher-id row → test passes.
"""
from __future__ import annotations

import pytest

from swing.data.db import ensure_schema
from swing.web.view_models.dashboard import latest_evaluation_run_id


@pytest.fixture
def conn_with_two_pipeline_runs_same_finished_ts(tmp_path):
    """Two complete pipeline_runs rows with identical finished_ts. The
    higher-id row also points at the higher evaluation_run_id; the helper
    must deterministically resolve to that one (Task 1: id DESC tiebreaker).

    Insert order: id=100 (eval=10) FIRST, id=101 (eval=11) SECOND. Pre-fix,
    SQLite returns rowid=100 first under tied `finished_ts` → helper
    returns 10 → assertion fails. Post-fix with `id DESC`, helper returns
    11.
    """
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    conn.execute(
        "INSERT INTO evaluation_runs "
        "(id, run_ts, data_asof_date, action_session_date, "
        " tickers_evaluated, aplus_count, watch_count, skip_count, "
        " excluded_count, error_count) "
        "VALUES (10, '2026-04-29T09:00:00', '2026-04-28', '2026-04-29', "
        "        0, 0, 0, 0, 0, 0)"
    )
    conn.execute(
        "INSERT INTO evaluation_runs "
        "(id, run_ts, data_asof_date, action_session_date, "
        " tickers_evaluated, aplus_count, watch_count, skip_count, "
        " excluded_count, error_count) "
        "VALUES (11, '2026-04-29T09:01:00', '2026-04-28', '2026-04-29', "
        "        0, 0, 0, 0, 0, 0)"
    )
    conn.execute(
        "INSERT INTO pipeline_runs "
        "(id, started_ts, finished_ts, trigger, data_asof_date, "
        " action_session_date, state, lease_token, evaluation_run_id) "
        "VALUES (100, '2026-04-29T08:55:00', '2026-04-29T09:00:00', "
        "        'manual', '2026-04-28', '2026-04-29', 'complete', "
        "        'tok-100', 10)"
    )
    conn.execute(
        "INSERT INTO pipeline_runs "
        "(id, started_ts, finished_ts, trigger, data_asof_date, "
        " action_session_date, state, lease_token, evaluation_run_id) "
        "VALUES (101, '2026-04-29T08:55:01', '2026-04-29T09:00:00', "
        "        'manual', '2026-04-28', '2026-04-29', 'complete', "
        "        'tok-101', 11)"
    )
    conn.commit()
    yield conn
    conn.close()


def test_latest_evaluation_run_id_id_desc_tiebreaker(
    conn_with_two_pipeline_runs_same_finished_ts,
):
    """Tied finished_ts → deterministic resolution to higher-id row.

    Pre-fix: pipeline-bound query lacks `id DESC`; SQLite ordering on tied
    `finished_ts` is unspecified.
    Post-fix: returns evaluation_run_id=11 (paired with pipeline_run id=101).
    """
    result = latest_evaluation_run_id(
        conn_with_two_pipeline_runs_same_finished_ts,
    )
    assert result == 11


@pytest.fixture
def conn_with_two_evaluation_runs_same_run_ts(tmp_path):
    """Two evaluation_runs rows with identical run_ts and NO pipeline_runs.

    Forces `latest_evaluation_run_id` into the standalone-eval fallback
    branch (Codex R2 Major 1: fallback branch must also be deterministic).
    Insert order: id=50 FIRST, id=51 SECOND. Pre-fix, the fallback query
    lacks `id DESC` and returns rowid=50 → assertion expecting 51 fails.
    """
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    conn.execute(
        "INSERT INTO evaluation_runs "
        "(id, run_ts, data_asof_date, action_session_date, "
        " tickers_evaluated, aplus_count, watch_count, skip_count, "
        " excluded_count, error_count) "
        "VALUES (50, '2026-04-29T09:00:00', '2026-04-28', '2026-04-29', "
        "        0, 0, 0, 0, 0, 0)"
    )
    conn.execute(
        "INSERT INTO evaluation_runs "
        "(id, run_ts, data_asof_date, action_session_date, "
        " tickers_evaluated, aplus_count, watch_count, skip_count, "
        " excluded_count, error_count) "
        "VALUES (51, '2026-04-29T09:00:00', '2026-04-28', '2026-04-29', "
        "        0, 0, 0, 0, 0, 0)"
    )
    conn.commit()
    yield conn
    conn.close()


def test_latest_evaluation_run_id_fallback_id_desc_tiebreaker(
    conn_with_two_evaluation_runs_same_run_ts,
):
    """Codex R2 Major 1: standalone-eval fallback branch also needs id DESC.

    Pre-fix: fallback query orders only by `run_ts DESC`; tied rows resolve
    in unspecified order.
    Post-fix: returns id=51 (highest id under tied run_ts).
    """
    result = latest_evaluation_run_id(
        conn_with_two_evaluation_runs_same_run_ts,
    )
    assert result == 51
