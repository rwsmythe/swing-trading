"""Tranche C T5: chart-reason split — fetcher_failed vs too_few_bars.

Closes spec §8 deferred item. The pre-T5 'insufficient-data' state collapsed
two distinct conditions:
  - the per-ticker yfinance fetch raised in `_step_charts`
  - the per-ticker OHLCV had fewer than MIN_BARS rows

T2 persists the distinction in pipeline_chart_targets.chart_status. T5
surfaces it through the chart-scope resolver so the operator sees a
specific message. Legacy NULL-FK runs (which can't distinguish) still
return the catch-all 'insufficient-data'.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import connect


def _insert_eval(conn, *, run_ts="2026-04-17T21:30:00") -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES (?, '2026-04-17', '2026-04-17', NULL,
                   0, 0, 0, 0, 0, 0, 'v1', 'd')""",
        (run_ts,),
    )
    return int(cur.lastrowid)


def _insert_pipeline_run(conn, *, evaluation_run_id, lease_token="t-1") -> int:
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, finished_ts, trigger, data_asof_date,
            action_session_date, state, lease_token, charts_status,
            evaluation_run_id)
           VALUES ('2026-04-17T21:00:00', '2026-04-17T21:55:00',
                   'manual', '2026-04-17', '2026-04-17',
                   'complete', ?, 'ok', ?)""",
        (lease_token, evaluation_run_id),
    )
    return int(cur.lastrowid)


def _insert_chart_target(conn, *, run_id, ticker, chart_status):
    conn.execute(
        """INSERT INTO pipeline_chart_targets
           (pipeline_run_id, ticker, source, chart_status)
           VALUES (?, ?, 'aplus', ?)""",
        (run_id, ticker, chart_status),
    )


@pytest.fixture
def db_conn(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    yield cfg, conn
    conn.close()


def test_resolver_emits_fetcher_failed_state(db_conn, tmp_path: Path):
    from swing.web.chart_scope import (
        latest_completed_pipeline_run,
        resolve_chart_scope,
    )

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval(conn)
        run_id = _insert_pipeline_run(conn, evaluation_run_id=eval_id)
        _insert_chart_target(
            conn, run_id=run_id, ticker="AAPL", chart_status="fetcher_failed",
        )

    binding = latest_completed_pipeline_run(conn)
    assert binding is not None
    reason, msg = resolve_chart_scope(
        conn, binding=binding, ticker="AAPL",
        charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "fetcher_failed"
    assert "fetch failed" in msg.lower()
    assert "yfinance" in msg.lower() or "fetch" in msg.lower()


def test_resolver_emits_too_few_bars_state(db_conn, tmp_path: Path):
    from swing.web.chart_scope import (
        latest_completed_pipeline_run,
        resolve_chart_scope,
    )

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval(conn)
        run_id = _insert_pipeline_run(conn, evaluation_run_id=eval_id)
        _insert_chart_target(
            conn, run_id=run_id, ticker="AAPL", chart_status="too_few_bars",
        )

    binding = latest_completed_pipeline_run(conn)
    assert binding is not None
    reason, msg = resolve_chart_scope(
        conn, binding=binding, ticker="AAPL",
        charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "too_few_bars"
    assert "bars" in msg.lower() or "historical" in msg.lower()


def test_resolver_pending_still_collapses_to_insufficient_data(
    db_conn, tmp_path: Path,
):
    """'pending' represents an in-flight or crashed-mid-step state — neither
    a fetcher failure nor a thin-bars skip. Operator sees the catch-all
    'insufficient-data' message rather than a misleading specific cause."""
    from swing.web.chart_scope import (
        latest_completed_pipeline_run,
        resolve_chart_scope,
    )

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval(conn)
        run_id = _insert_pipeline_run(conn, evaluation_run_id=eval_id)
        _insert_chart_target(
            conn, run_id=run_id, ticker="AAPL", chart_status="pending",
        )

    binding = latest_completed_pipeline_run(conn)
    assert binding is not None
    reason, _ = resolve_chart_scope(
        conn, binding=binding, ticker="AAPL",
        charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "insufficient-data"


def test_resolver_legacy_null_fk_still_uses_insufficient_data(
    db_conn, tmp_path: Path,
):
    """Heuristic-fallback path (legacy NULL FK) cannot distinguish fetcher
    failures from short-bar skips — it sees only the absence of a PNG.
    The catch-all 'insufficient-data' state remains for these rows."""
    from swing.web.chart_scope import (
        latest_completed_pipeline_run,
        resolve_chart_scope,
    )

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval(conn)
        # A+ candidate so the heuristic puts AAPL in scope.
        conn.execute(
            """INSERT INTO candidates
               (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                rs_method)
               VALUES (?, 'AAPL', 'aplus', 100.0, 101.0, 95.0, 'universe')""",
            (eval_id,),
        )
        # Pipeline run with NULL FK (legacy).
        conn.execute(
            """INSERT INTO pipeline_runs
               (started_ts, finished_ts, trigger, data_asof_date,
                action_session_date, state, lease_token, charts_status,
                evaluation_run_id)
               VALUES ('2026-04-17T21:00:00', '2026-04-17T21:55:00',
                       'manual', '2026-04-17', '2026-04-17',
                       'complete', 't-x', 'ok', NULL)""",
        )
    binding = latest_completed_pipeline_run(conn)
    assert binding is not None
    # No PNG written.
    reason, msg = resolve_chart_scope(
        conn, binding=binding, ticker="AAPL",
        charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "insufficient-data"
    assert "data too thin" in msg.lower()


def test_resolver_ok_status_with_png_still_returns_none(db_conn, tmp_path: Path):
    """Sanity check: T5 must not have regressed the success path."""
    from swing.web.chart_scope import (
        latest_completed_pipeline_run,
        resolve_chart_scope,
    )

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval(conn)
        run_id = _insert_pipeline_run(conn, evaluation_run_id=eval_id)
        _insert_chart_target(
            conn, run_id=run_id, ticker="AAPL", chart_status="ok",
        )
    target = tmp_path / "2026-04-17" / "AAPL.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"stub")

    binding = latest_completed_pipeline_run(conn)
    assert binding is not None
    reason, msg = resolve_chart_scope(
        conn, binding=binding, ticker="AAPL",
        charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason is None
    assert msg is None


def test_chart_reason_messages_dict_includes_new_states():
    """Both new keys must be in CHART_REASON_MESSAGES so any caller that
    looks the message up by reason value gets a non-None result."""
    from swing.web.chart_scope import CHART_REASON_MESSAGES

    assert "fetcher_failed" in CHART_REASON_MESSAGES
    assert "too_few_bars" in CHART_REASON_MESSAGES
    # Legacy collapsed state must still be present for the heuristic path.
    assert "insufficient-data" in CHART_REASON_MESSAGES
