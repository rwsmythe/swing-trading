"""Chart-scope resolver — Tranche C T3 FK-backed lookup path.

When the latest completed pipeline_runs row has a non-NULL evaluation_run_id,
the resolver reads chart scope directly from pipeline_chart_targets instead
of recomputing A+ via the eval-linkage heuristic and near-by-proximity from
the live watchlist. Fallback to the heuristic is preserved for legacy
(NULL FK) rows — existing tests in test_chart_scope.py exercise that path.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import connect


def _insert_pipeline_run(
    conn, *, started_ts, finished_ts, data_asof_date,
    state="complete", charts_status="ok",
    action_session_date=None, lease_token="t-x",
    evaluation_run_id=None,
) -> int:
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, finished_ts, trigger, data_asof_date,
            action_session_date, state, lease_token, charts_status,
            evaluation_run_id)
           VALUES (?, ?, 'manual', ?, ?, ?, ?, ?, ?)""",
        (started_ts, finished_ts, data_asof_date,
         action_session_date or data_asof_date,
         state, lease_token, charts_status, evaluation_run_id),
    )
    return int(cur.lastrowid)


def _insert_eval_run(conn, *, run_ts, data_asof_date) -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES (?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 'v1', 'd')""",
        (run_ts, data_asof_date, data_asof_date),
    )
    return int(cur.lastrowid)


def _insert_chart_target(
    conn, *, pipeline_run_id, ticker, source="aplus", chart_status="ok",
):
    conn.execute(
        """INSERT INTO pipeline_chart_targets
           (pipeline_run_id, ticker, source, chart_status)
           VALUES (?, ?, ?, ?)""",
        (pipeline_run_id, ticker, source, chart_status),
    )


def _write_chart(charts_dir: Path, *, date: str, ticker: str) -> Path:
    target = charts_dir / date / f"{ticker}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"stub")
    return target


@pytest.fixture
def db_conn(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    yield cfg, conn
    conn.close()


def test_resolver_uses_pipeline_chart_targets_when_fk_present(db_conn, tmp_path):
    """When pipeline_runs.evaluation_run_id is set AND a chart_targets row
    exists for the ticker with chart_status='ok' AND the PNG is on disk,
    the resolver returns (None, None) — chart is available."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        run_id = _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17",
            evaluation_run_id=eval_id,
        )
        _insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="AAPL",
            source="aplus", chart_status="ok",
        )
    _write_chart(tmp_path, date="2026-04-17", ticker="AAPL")

    reason, msg = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason is None
    assert msg is None


def test_resolver_fk_path_out_of_scope_when_no_target_row(db_conn, tmp_path):
    """When FK is set but the ticker has no chart_targets row, the resolver
    returns out-of-scope (the pipeline did not chart this ticker)."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        run_id = _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17",
            evaluation_run_id=eval_id,
        )
        _insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="MSFT",
            source="aplus", chart_status="ok",
        )

    reason, msg = resolve_chart_scope(
        conn, ticker="ZZZ", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "out-of-scope"
    assert "charting scope" in msg


def test_resolver_fk_path_eliminates_drift_mode_a(db_conn, tmp_path):
    """Spec §4 drift mode A regression: pipeline charted AAPL; AFTER
    pipeline.finished_ts a standalone `swing eval` runs that drops AAPL from
    its A+ set and adds NVDA. The resolver MUST NOT consult that later eval
    — it must read pipeline_chart_targets directly. AAPL stays in scope;
    NVDA is out-of-scope. Pre-T3 heuristic resolver (post-T2 with FK) would
    still pick the right A+ set via the FK; pre-T2 heuristic would pick
    whichever of E1 or E2 satisfied `run_ts <= finished_ts` (E1 in this
    case because E2's run_ts is after finished_ts), so this case is
    hardened more strongly by T3 than by T2 alone."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        e1 = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        run_id = _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17",
            evaluation_run_id=e1,
        )
        _insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="AAPL",
            source="aplus", chart_status="ok",
        )
        # Standalone eval E2 ran AFTER pipeline.finished_ts and has a
        # different A+ set. The FK on pipeline_runs still points to E1,
        # so the resolver ignores E2.
        _insert_eval_run(
            conn, run_ts="2026-04-17T22:30:00", data_asof_date="2026-04-17",
        )
    _write_chart(tmp_path, date="2026-04-17", ticker="AAPL")

    reason_aapl, _ = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason_aapl is None, (
        "AAPL must remain in-scope via the FK-backed chart_targets read; "
        "E2 must not poison the resolver"
    )

    reason_nvda, _ = resolve_chart_scope(
        conn, ticker="NVDA", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason_nvda == "out-of-scope", (
        "NVDA was only ever in E2's A+ set, never charted — must be "
        "out-of-scope"
    )


def test_resolver_fk_path_eliminates_drift_mode_b(db_conn, tmp_path):
    """Spec §4 drift mode B regression: pipeline ran top-N with watchlist
    state at T1; AFTER the pipeline ran, the watchlist's near-by-proximity
    rank changed because a row's last_close moved. The resolver MUST NOT
    recompute proximity at render time — it reads what was actually persisted
    in pipeline_chart_targets. AAA was the top-1 at T1 (charted); BBB became
    top-1 at T2 but was never charted, so BBB is out-of-scope."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        run_id = _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17",
            evaluation_run_id=eval_id,
        )
        # At T1 the pipeline picked AAA as the top-1 near-by-proximity.
        _insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="AAA",
            source="near_proximity", chart_status="ok",
        )
        # Live watchlist at render time: BBB has moved closer than AAA.
        # The pre-T3 heuristic would have re-ranked and picked BBB.
        conn.execute(
            """INSERT INTO watchlist
               (ticker, added_date, last_qualified_date, status,
                qualification_count, not_qualified_streak, last_data_asof_date,
                entry_target, initial_stop_target, last_close)
               VALUES ('AAA', '2026-04-15', '2026-04-17', 'watch', 1, 0,
                       '2026-04-17', 100.0, 95.0, 90.0)""",
        )
        conn.execute(
            """INSERT INTO watchlist
               (ticker, added_date, last_qualified_date, status,
                qualification_count, not_qualified_streak, last_data_asof_date,
                entry_target, initial_stop_target, last_close)
               VALUES ('BBB', '2026-04-15', '2026-04-17', 'watch', 1, 0,
                       '2026-04-17', 100.0, 95.0, 100.0)""",
        )
    _write_chart(tmp_path, date="2026-04-17", ticker="AAA")

    reason_aaa, _ = resolve_chart_scope(
        conn, ticker="AAA", charts_dir=tmp_path, chart_top_n_watch=1,
    )
    assert reason_aaa is None, (
        "AAA was charted at T1 — FK-backed read keeps it in scope even "
        "though render-time proximity has flipped"
    )

    reason_bbb, _ = resolve_chart_scope(
        conn, ticker="BBB", charts_dir=tmp_path, chart_top_n_watch=1,
    )
    assert reason_bbb == "out-of-scope", (
        "BBB became top-1 only at render time; FK-backed read never picks "
        "it because it has no chart_targets row"
    )


def test_resolver_fk_path_chart_status_too_few_bars_yields_insufficient_data(
    db_conn, tmp_path,
):
    """Until T5 ships, persisted chart_status='too_few_bars' or 'fetcher_failed'
    on a chart_targets row must collapse to the existing 'insufficient-data'
    state for backward compatibility. T5 splits this into two new states."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        run_id = _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17",
            evaluation_run_id=eval_id,
        )
        _insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="AAPL",
            source="aplus", chart_status="too_few_bars",
        )
        _insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="MSFT",
            source="aplus", chart_status="fetcher_failed",
        )
    # No PNG written for either.

    for ticker in ("AAPL", "MSFT"):
        reason, msg = resolve_chart_scope(
            conn, ticker=ticker, charts_dir=tmp_path, chart_top_n_watch=5,
        )
        assert reason == "insufficient-data", (
            f"{ticker}: pre-T5 collapse, expected insufficient-data, got {reason}"
        )
        assert "data too thin" in msg.lower()


def test_resolver_fk_path_pending_yields_insufficient_data(db_conn, tmp_path):
    """A 'pending' chart_status means the chart step never finalized this
    ticker (e.g., crashed mid-step). Resolver collapses to insufficient-data
    rather than claiming success without a PNG."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        run_id = _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17",
            evaluation_run_id=eval_id,
        )
        _insert_chart_target(
            conn, pipeline_run_id=run_id, ticker="AAPL",
            source="aplus", chart_status="pending",
        )

    reason, _ = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason == "insufficient-data"


def test_resolver_legacy_null_fk_falls_back_to_heuristic(db_conn, tmp_path):
    """Pre-migration-0006 rows have evaluation_run_id IS NULL. The resolver
    must NOT return out-of-scope (nor crash) — it must use the heuristic
    eval-linkage + live-watchlist code path that existing tests cover."""
    from swing.web.chart_scope import resolve_chart_scope

    cfg, conn = db_conn
    with conn:
        eval_id = _insert_eval_run(
            conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
        )
        # Heuristic-target candidate (A+).
        conn.execute(
            """INSERT INTO candidates
               (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                rs_method)
               VALUES (?, 'AAPL', 'aplus', 100.0, 101.0, 95.0, 'universe')""",
            (eval_id,),
        )
        # Pipeline run with NULL FK (legacy).
        _insert_pipeline_run(
            conn, started_ts="2026-04-17T21:00:00",
            finished_ts="2026-04-17T21:55:00",
            data_asof_date="2026-04-17",
            evaluation_run_id=None,
        )
    _write_chart(tmp_path, date="2026-04-17", ticker="AAPL")

    reason, msg = resolve_chart_scope(
        conn, ticker="AAPL", charts_dir=tmp_path, chart_top_n_watch=5,
    )
    assert reason is None, (
        "legacy NULL-FK row must fall back to the heuristic and find AAPL "
        f"in scope; got reason={reason!r} msg={msg!r}"
    )
