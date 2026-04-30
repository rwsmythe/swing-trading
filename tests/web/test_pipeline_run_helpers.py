"""Per-helper unit tests for the two pipeline_runs anchor helpers.

Pins:
  1. `latest_completed_pipeline_run` exposes `action_session_date` on the
     returned binding (Task 1 extension).
  2. Both helpers' `id DESC` tiebreaker is exercised on every branch:
       - `latest_completed_pipeline_run`: tied finished_ts → higher id wins.
       - `latest_evaluation_run_id` pipeline branch: tied finished_ts → higher
         id wins.
       - `latest_evaluation_run_id` fallback branch: tied run_ts → higher id wins.
  3. With-fallback semantics: pipeline-bound row wins when present;
     fallback fires only when zero completed pipeline_runs exist.
  4. Pipeline-bound contract: `latest_completed_pipeline_run` returns None
     when zero completed pipeline_runs exist (regardless of standalone-eval
     state).

Each tied-row test inserts the LOWER-id row LAST so that engine-specific
ROWID ordering would naturally pick the lower id without an explicit
`id DESC` tiebreaker; the assertion that the HIGHER id wins is the
discriminator. A future regression that drops the tiebreaker fails
deterministically here.
"""
from __future__ import annotations

from swing.data.db import connect
from swing.web.chart_scope import latest_completed_pipeline_run
from swing.web.view_models.dashboard import latest_evaluation_run_id


def _insert_pipeline_run(
    conn,
    *,
    state: str,
    finished_ts: str | None,
    evaluation_run_id: int | None,
    action_session_date: str = "2026-04-29",
    data_asof_date: str = "2026-04-28",
    charts_status: str | None = "ok",
) -> int:
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, finished_ts, trigger, data_asof_date,
            action_session_date, state, lease_token,
            evaluation_run_id, charts_status)
           VALUES ('2026-04-29T08:00:00', ?, 'manual', ?, ?, ?, ?, ?, ?)""",
        (
            finished_ts, data_asof_date, action_session_date, state,
            f"tok-{conn.execute('SELECT COALESCE(MAX(id), 0)+1 FROM pipeline_runs').fetchone()[0]}",
            evaluation_run_id, charts_status,
        ),
    )
    return int(cur.lastrowid)


def _insert_evaluation_run(
    conn,
    *,
    run_ts: str,
    action_session_date: str = "2026-04-29",
    data_asof_date: str = "2026-04-28",
) -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count)
           VALUES (?, ?, ?, NULL, 0, 0, 0, 0, 0, 0)""",
        (run_ts, data_asof_date, action_session_date),
    )
    return int(cur.lastrowid)


def test_latest_completed_pipeline_run_exposes_action_session_date(seeded_db):
    """The binding must include `action_session_date` so the stale-banner
    consumer (dashboard.py:607) can migrate off its inline query."""
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            eval_id = _insert_evaluation_run(conn, run_ts="2026-04-29T09:00:00")
            _insert_pipeline_run(
                conn, state="complete", finished_ts="2026-04-29T09:00:00",
                evaluation_run_id=eval_id, action_session_date="2026-04-29",
            )
        binding = latest_completed_pipeline_run(conn)
    finally:
        conn.close()
    assert binding is not None
    assert binding.action_session_date == "2026-04-29", (
        "`action_session_date` must be exposed on PipelineRunBinding so "
        "the stale-banner consumer can read it without an inline query"
    )


def test_latest_completed_pipeline_run_returns_none_when_no_completed(seeded_db):
    """Pipeline-bound contract: NO fallback to standalone evals."""
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Standalone eval exists; ZERO completed pipeline_runs.
            _insert_evaluation_run(conn, run_ts="2026-04-29T09:00:00")
        binding = latest_completed_pipeline_run(conn)
    finally:
        conn.close()
    assert binding is None, (
        "Pipeline-bound contract: latest_completed_pipeline_run MUST NOT "
        "fall back to standalone-eval state"
    )


def test_latest_completed_pipeline_run_id_desc_tiebreaker(seeded_db):
    """Tied finished_ts → higher id wins. See module docstring for the
    rationale on insert order: the helper's `id DESC` tiebreaker MUST
    pick the higher id deterministically.
    """
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            eval_a = _insert_evaluation_run(conn, run_ts="2026-04-29T09:00:00")
            eval_b = _insert_evaluation_run(conn, run_ts="2026-04-29T09:00:01")
            run_a_id = _insert_pipeline_run(
                conn, state="complete", finished_ts="2026-04-29T09:00:00",
                evaluation_run_id=eval_a,
            )
            run_b_id = _insert_pipeline_run(
                conn, state="complete", finished_ts="2026-04-29T09:00:00",
                evaluation_run_id=eval_b,
            )
            # SANITY: both runs have identical finished_ts; b has higher id.
            assert run_b_id > run_a_id
        binding = latest_completed_pipeline_run(conn)
    finally:
        conn.close()
    assert binding is not None
    assert binding.run_id == run_b_id, (
        f"Tied finished_ts tiebreaker: helper must pick higher id "
        f"({run_b_id}) deterministically; got run_id={binding.run_id}. "
        "Regression: dropped or weakened `id DESC` tiebreaker."
    )


def test_latest_evaluation_run_id_pipeline_branch_id_desc_tiebreaker(seeded_db):
    """`latest_evaluation_run_id` pipeline branch tied finished_ts."""
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            eval_a = _insert_evaluation_run(conn, run_ts="2026-04-29T09:00:00")
            eval_b = _insert_evaluation_run(conn, run_ts="2026-04-29T09:00:01")
            _insert_pipeline_run(
                conn, state="complete", finished_ts="2026-04-29T09:00:00",
                evaluation_run_id=eval_a,
            )
            _insert_pipeline_run(
                conn, state="complete", finished_ts="2026-04-29T09:00:00",
                evaluation_run_id=eval_b,
            )
        result = latest_evaluation_run_id(conn)
    finally:
        conn.close()
    # Higher pipeline_run id has eval_b — so eval_b wins.
    assert result == eval_b, (
        f"Pipeline branch tied finished_ts: helper must return the eval "
        f"id ({eval_b}) bound to the higher pipeline_run id; got {result}"
    )


def test_latest_evaluation_run_id_fallback_branch_id_desc_tiebreaker(seeded_db):
    """`latest_evaluation_run_id` fallback branch (no completed pipeline)."""
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            eval_a = _insert_evaluation_run(conn, run_ts="2026-04-29T09:00:00")
            eval_b = _insert_evaluation_run(conn, run_ts="2026-04-29T09:00:00")
            assert eval_b > eval_a
            # No completed pipeline_runs → fallback fires.
        result = latest_evaluation_run_id(conn)
    finally:
        conn.close()
    assert result == eval_b, (
        f"Fallback branch tied run_ts: helper must pick higher eval id "
        f"({eval_b}); got {result}"
    )


def test_latest_evaluation_run_id_pipeline_wins_over_fallback(seeded_db):
    """With-fallback contract: pipeline-bound row wins when present, even
    if a NEWER standalone eval exists."""
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Pipeline eval (older).
            pipeline_eval = _insert_evaluation_run(
                conn, run_ts="2026-04-29T08:00:00",
            )
            _insert_pipeline_run(
                conn, state="complete", finished_ts="2026-04-29T08:30:00",
                evaluation_run_id=pipeline_eval,
            )
            # Standalone eval (NEWER) — would win MAX(run_ts) FROM
            # evaluation_runs, but pipeline-bound branch wins first.
            _insert_evaluation_run(conn, run_ts="2026-04-29T10:00:00")
        result = latest_evaluation_run_id(conn)
    finally:
        conn.close()
    assert result == pipeline_eval, (
        "Pipeline-bound branch must win over a newer standalone eval "
        "(this is the Bug-7 family's foundational contract)"
    )


def test_latest_evaluation_run_id_falls_back_when_pipeline_eval_id_null(seeded_db):
    """Legacy pipeline_runs with NULL evaluation_run_id → fallback fires."""
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _insert_pipeline_run(
                conn, state="complete", finished_ts="2026-04-29T08:30:00",
                evaluation_run_id=None,
            )
            standalone_eval = _insert_evaluation_run(
                conn, run_ts="2026-04-29T10:00:00",
            )
        result = latest_evaluation_run_id(conn)
    finally:
        conn.close()
    assert result == standalone_eval, (
        "Legacy NULL-FK pipeline_run forces fallback to most-recent "
        "standalone eval"
    )
