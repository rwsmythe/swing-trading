"""Chart-scope resolver — Tranche B-ops spec §4 (Bug 4).

Six states derived from: latest completed pipeline_runs row's charts_status,
the A+ set from the pipeline's own evaluation_run (resolved via the
`data_asof_date + run_ts <= finished_ts` heuristic), the LIVE top-N near-
trigger watchlist (reconstructed from active watchlist at render time), and
a filesystem probe for the PNG.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import connect


def _insert_pipeline_run(
    conn, *, started_ts: str, finished_ts: str | None,
    data_asof_date: str, state: str = "complete",
    charts_status: str | None = "ok",
    action_session_date: str | None = None,
    lease_token: str = "done-tok",
) -> int:
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
            state, lease_token, charts_status)
           VALUES (?, ?, 'manual', ?, ?, ?, ?, ?)""",
        (started_ts, finished_ts, data_asof_date,
         action_session_date or data_asof_date, state, lease_token, charts_status),
    )
    return int(cur.lastrowid)


def _insert_eval_run(
    conn, *, run_ts: str, data_asof_date: str,
    action_session_date: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count,
            rs_universe_version, rs_universe_hash)
           VALUES (?, ?, ?, NULL, 2, 1, 1, 0, 0, 0, 'v1', 'deadbeef')""",
        (run_ts, data_asof_date, action_session_date or data_asof_date),
    )
    return int(cur.lastrowid)


def _insert_candidate(conn, *, eval_id: int, ticker: str, bucket: str) -> None:
    conn.execute(
        """INSERT INTO candidates
           (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
            rs_method)
           VALUES (?, ?, ?, 100.0, 101.0, 95.0, 'universe')""",
        (eval_id, ticker, bucket),
    )


def _insert_watchlist_row(
    conn, *, ticker: str, entry_target: float, last_close: float,
) -> None:
    conn.execute(
        """INSERT INTO watchlist
           (ticker, added_date, last_qualified_date, status,
            qualification_count, not_qualified_streak, last_data_asof_date,
            entry_target, initial_stop_target, last_close)
           VALUES (?, '2026-04-15', '2026-04-17', 'watch', 1, 0, '2026-04-17',
                   ?, 95.0, ?)""",
        (ticker, entry_target, last_close),
    )


def _write_chart(charts_dir: Path, *, date: str, ticker: str) -> Path:
    target = charts_dir / date / f"{ticker}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"not-a-real-png-but-exists")
    return target


@pytest.fixture
def db_conn(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    yield cfg, conn
    conn.close()


def test_resolver_no_run_when_no_completed_pipeline(db_conn, tmp_path):
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    reason, msg = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "no-run"
    assert "no pipeline run yet" in msg


def test_resolver_engine_missing_when_charts_status_skipped(db_conn, tmp_path):
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17", charts_status="skipped",
        )
    reason, msg = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "engine-missing"
    assert "mplfinance" in msg


def test_resolver_pipeline_failed_when_charts_status_failed(db_conn, tmp_path):
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17", charts_status="failed",
        )
    reason, msg = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "pipeline-failed"
    assert "chart step failed" in msg.lower()


def test_resolver_available_when_aplus_and_png_exists(db_conn, tmp_path):
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        _insert_candidate(conn, eval_id=eval_id, ticker="AAPL", bucket="aplus")
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17", charts_status="ok",
        )
    _write_chart(tmp_path, date="2026-04-17", ticker="AAPL")

    reason, msg = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason is None
    assert msg is None


def test_resolver_out_of_scope_when_not_aplus_and_not_near_top_n(db_conn, tmp_path):
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        _insert_candidate(conn, eval_id=eval_id, ticker="NVDA", bucket="aplus")
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17", charts_status="ok",
        )
        # ZZZ is not A+ nor on watchlist.
    reason, msg = resolve_chart_scope(
        conn, ticker="ZZZ", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "out-of-scope"
    assert "charting scope" in msg


def test_resolver_insufficient_data_when_in_scope_but_png_missing(db_conn, tmp_path):
    """Ticker is in scope (A+), run was ok, but no PNG on disk."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        _insert_candidate(conn, eval_id=eval_id, ticker="AAPL", bucket="aplus")
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17", charts_status="ok",
        )
    # No PNG written.
    reason, msg = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "insufficient-data"
    assert "data too thin" in msg.lower()


def test_resolver_watchlist_ticker_in_scope_by_proximity(db_conn, tmp_path):
    """A watchlist ticker WITHIN top-N by proximity is in scope (chart renders
    or is insufficient-data, NEVER out-of-scope)."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        # Seed an eval_run so the eval-linkage heuristic succeeds.
        _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17", charts_status="ok",
        )
        # Two watchlist rows; top_n = 1. MSFT is closer (|0| / 100 == 0 vs |5|/100 == 0.05).
        _insert_watchlist_row(conn, ticker="MSFT", entry_target=100.0, last_close=100.0)
        _insert_watchlist_row(conn, ticker="GOOG", entry_target=100.0, last_close=95.0)
    _write_chart(tmp_path, date="2026-04-17", ticker="MSFT")

    # MSFT is in top-1 → chart renders (None).
    reason, _ = resolve_chart_scope(
        conn, ticker="MSFT", charts_dir=tmp_path, chart_top_n_watch=1,
    )
    assert reason is None

    # GOOG is in rank 2 → out-of-scope with top_n=1.
    reason_goog, _ = resolve_chart_scope(
        conn, ticker="GOOG", charts_dir=tmp_path, chart_top_n_watch=1,
    )
    assert reason_goog == "out-of-scope"


def test_resolver_eval_linkage_picks_pipelines_eval_not_later_standalone(
    db_conn, tmp_path,
):
    """Spec §4: eval_run_id heuristic must use
    `data_asof_date = pipeline.data_asof_date AND run_ts <= pipeline.finished_ts
     ORDER BY run_ts DESC LIMIT 1`
    so a standalone `swing eval` run AFTER the pipeline finished doesn't
    poison the resolver's A+ set."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        # Pipeline's own eval E1 (before finish).
        e1 = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        _insert_candidate(conn, eval_id=e1, ticker="AAPL", bucket="aplus")

        # Pipeline run — finished at 21:55.
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17", charts_status="ok",
        )

        # LATER standalone eval E2, same data_asof_date, AFTER pipeline finish.
        # Different A+ set (NVDA, not AAPL).
        e2 = _insert_eval_run(
            conn, run_ts="2026-04-17T22:30:00", data_asof_date="2026-04-17",
        )
        _insert_candidate(conn, eval_id=e2, ticker="NVDA", bucket="aplus")
    _write_chart(tmp_path, date="2026-04-17", ticker="AAPL")

    # Resolver must pick E1's A+ set → AAPL is in-scope → available.
    reason_aapl, _ = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason_aapl is None, (
        "resolver must bind to E1 (pipeline's own eval); AAPL must resolve "
        "to available even though E2 later dropped it from A+"
    )

    # NVDA was only in E2 — not what the pipeline charted → out-of-scope.
    reason_nvda, _ = resolve_chart_scope(
        conn, ticker="NVDA", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason_nvda == "out-of-scope", (
        "resolver must NOT pick E2 (standalone post-pipeline eval)"
    )


def test_resolver_drift_proximity_rank_approximated_from_render_time(
    db_conn, tmp_path,
):
    """Spec §4 drift acknowledgment: the top-N set is recomputed from LIVE
    watchlist state at render time. If the ranking changes between T1 (pipeline
    run) and T2 (expand), the resolver returns the render-time answer.
    Bounded-drift case — the resolver does not try to reconstruct run-time
    rankings (they aren't persisted)."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17", charts_status="ok",
        )
        # Current live watchlist: AAA is closer to pivot than BBB.
        _insert_watchlist_row(conn, ticker="AAA", entry_target=100.0, last_close=99.9)
        _insert_watchlist_row(conn, ticker="BBB", entry_target=100.0, last_close=90.0)

    # AAA ranks 1 at T2 (render time).
    reason_aaa, _ = resolve_chart_scope(
        conn, ticker="AAA", charts_dir=tmp_path, chart_top_n_watch=1,
    )
    # In top-1 but no PNG → insufficient-data.
    assert reason_aaa == "insufficient-data"

    # BBB is outside top-1 at T2.
    reason_bbb, _ = resolve_chart_scope(
        conn, ticker="BBB", charts_dir=tmp_path, chart_top_n_watch=1,
    )
    assert reason_bbb == "out-of-scope"


def test_resolver_falls_back_to_insufficient_data_when_eval_linkage_missing(
    db_conn, tmp_path,
):
    """Spec §4: if the `eval_run_id` heuristic returns no row (migration
    anomaly, or pipeline completed without an eval step), the resolver
    falls back to `insufficient-data` for probed tickers — collapsing toward
    the data-quality bucket rather than misleading the operator."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        # Pipeline completed for data_asof=2026-04-17 but NO eval row exists
        # for that date.
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17", charts_status="ok",
        )
    reason, msg = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "insufficient-data"
    assert "data too thin" in msg.lower()


def test_resolver_ignores_running_pipeline_uses_last_complete(db_conn, tmp_path):
    """A new pipeline run mid-flight (state='running', finished_ts IS NULL)
    must NOT mask the last-completed run — the resolver looks only at
    state='complete' rows when picking the reference run."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        # Completed run (data_asof = 04-17, charts_status=ok).
        eval_id = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        _insert_candidate(conn, eval_id=eval_id, ticker="AAPL", bucket="aplus")
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17", charts_status="ok",
        )
        # New in-flight run (no finished_ts).
        conn.execute(
            """INSERT INTO pipeline_runs
               (started_ts, finished_ts, trigger, data_asof_date,
                action_session_date, state, lease_token, charts_status)
               VALUES ('2026-04-17T22:00:00', NULL, 'manual', '2026-04-17',
                       '2026-04-20', 'running', 'in-flight', NULL)""",
        )
    _write_chart(tmp_path, date="2026-04-17", ticker="AAPL")

    reason, _ = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason is None, "in-flight run must not mask the last-completed run"


from swing.web.chart_scope import (
    PipelineRunBinding,
    latest_completed_pipeline_run,
)


def test_latest_completed_pipeline_run_returns_none_on_empty_db(db_conn):
    """No completed runs → helper returns None.

    Discriminating verification: pre-fix code (no helper exists) raises
    ImportError. Post-fix the helper returns None. Asserting on None
    distinguishes from "raised some error" failure mode.

    Fixture: `db_conn` (already in tests/web/test_chart_scope.py) yields
    `(cfg, conn)` where conn is an open sqlite3.Connection over a fully-
    migrated empty DB. NOT `seeded_db` — that fixture returns
    `(cfg, cfg_path)`, not a connection.
    """
    cfg, conn = db_conn
    # db_conn yields a fresh DB; pipeline_runs is empty by default.
    assert latest_completed_pipeline_run(conn) is None


def test_latest_completed_pipeline_run_returns_binding_with_all_fields(db_conn):
    """Helper populates all 5 fields from the latest completed run.

    Discriminating verification: each field's value is checked against the
    seeded data; if the helper SELECTed the wrong column or omitted a field,
    the assertion fails on the specific mismatch.
    """
    cfg, conn = db_conn
    # Seed the evaluation_run first so the FK constraint on pipeline_runs
    # (evaluation_run_id REFERENCES evaluation_runs(id)) is satisfied.
    conn.execute(
        """INSERT INTO evaluation_runs
               (id, run_ts, data_asof_date, action_session_date, finviz_csv_path,
                tickers_evaluated, aplus_count, watch_count, skip_count,
                excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES (7, '2026-04-01T09:00:00', '2026-04-01', '2026-04-02', NULL,
                   1, 1, 0, 0, 0, 0, 'v1', 'deadbeef')""",
    )
    conn.execute(
        """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                       data_asof_date, action_session_date,
                                       charts_status, evaluation_run_id,
                                       trigger, lease_token)
           VALUES (10, '2026-04-01T09:00:00', '2026-04-01T09:30:00',
                   'complete', '2026-04-01', '2026-04-02', 'ok', 7,
                   'manual', 'tok-10')""",
    )
    conn.commit()
    binding = latest_completed_pipeline_run(conn)
    assert binding is not None
    assert binding.run_id == 10
    assert binding.finished_ts == "2026-04-01T09:30:00"
    assert binding.data_asof_date == "2026-04-01"
    assert binding.charts_status == "ok"
    assert binding.evaluation_run_id == 7


def test_latest_completed_pipeline_run_id_desc_tiebreaker(db_conn):
    """When two completed runs share `finished_ts`, helper picks the higher id.

    Discriminating verification: pre-fix `ORDER BY finished_ts DESC LIMIT 1`
    relies on SQLite's natural-row-ordering for ties — non-deterministic.
    Post-fix `ORDER BY finished_ts DESC, id DESC LIMIT 1` deterministically
    picks the higher id. Codex R1 Minor 1.

    Compounding-confound discipline: ids are seeded in non-monotonic order
    (5 then 12 then 3) so a "natural row order" lookup would NOT pick id=12;
    the test would fail with id=3 or id=5 if the tiebreaker is missing.
    """
    cfg, conn = db_conn
    # Insert in non-monotonic order to defeat natural-row-order coincidence.
    for run_id in (5, 12, 3):
        conn.execute(
            """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                           data_asof_date, action_session_date,
                                           charts_status, evaluation_run_id,
                                           trigger, lease_token)
               VALUES (?, '2026-04-01T09:00:00', '2026-04-01T09:30:00',
                       'complete', '2026-04-01', '2026-04-02', 'ok', NULL,
                       'manual', ?)""",
            (run_id, f"tok-{run_id}"),
        )
    conn.commit()
    binding = latest_completed_pipeline_run(conn)
    assert binding is not None
    assert binding.run_id == 12, (
        f"expected id-DESC tiebreaker to pick 12, got {binding.run_id}; "
        "regression: missing `id DESC` in ORDER BY"
    )


def test_latest_completed_pipeline_run_skips_in_progress_runs(db_conn):
    """Runs with state != 'complete' are excluded.

    Discriminating verification: a run with finished_ts='2026-04-02T09:30:00'
    state='running' would WIN the ORDER BY if the WHERE clause were dropped.
    The test asserts the older 'complete' run is selected, which fails if
    the state filter is missing.
    """
    cfg, conn = db_conn
    conn.execute(
        """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                       data_asof_date, action_session_date,
                                       charts_status, evaluation_run_id,
                                       trigger, lease_token)
           VALUES (1, '2026-04-01T09:00:00', '2026-04-01T09:30:00',
                   'complete', '2026-04-01', '2026-04-02', 'ok', NULL,
                   'manual', 'tok-1')""",
    )
    conn.execute(
        """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                       data_asof_date, action_session_date,
                                       charts_status, evaluation_run_id,
                                       trigger, lease_token)
           VALUES (2, '2026-04-02T09:00:00', '2026-04-02T09:30:00',
                   'running', '2026-04-02', '2026-04-03', NULL, NULL,
                   'manual', 'tok-2')""",
    )
    conn.commit()
    binding = latest_completed_pipeline_run(conn)
    assert binding is not None
    assert binding.run_id == 1, (
        f"expected the only 'complete' run (id=1) to win; got id={binding.run_id}; "
        "regression: WHERE state='complete' filter dropped"
    )


def test_pipeline_run_binding_is_frozen():
    """Dataclass is frozen (immutable). A snapshot pinned at request entry
    must not be mutable mid-handler.

    Discriminating verification: assigning to a field on a frozen dataclass
    raises FrozenInstanceError; on a non-frozen dataclass the assignment
    silently succeeds. Catches a regression that drops `frozen=True`.
    """
    import dataclasses
    binding = PipelineRunBinding(
        run_id=1, finished_ts="t", data_asof_date="d",
        charts_status="ok", evaluation_run_id=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        binding.run_id = 999  # type: ignore[misc]
