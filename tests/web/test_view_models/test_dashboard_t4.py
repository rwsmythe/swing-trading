"""build_dashboard today_decisions binds via evaluation_run_id (Bug 7).

Tranche C T4 — fixes the mixed-anchor inconsistency where today_decisions
read by date-only filter, while chart-scope resolver bound to the pipeline's
own eval. Symptom (Bug 7): SLDB shown in today_decisions while chart-scope
reported it as out-of-scope. After T4 the dashboard passes
pipeline_runs.evaluation_run_id to list_for_session, so today_decisions
reflects the same eval as chart-scope.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from swing.data.db import connect


def _insert_eval(conn, *, run_ts: str, action_session: str = "2026-04-20") -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES (?, '2026-04-17', ?, NULL,
                   1, 1, 0, 0, 0, 0, 'v1', 'd')""",
        (run_ts, action_session),
    )
    return int(cur.lastrowid)


def _insert_aplus_candidate(conn, *, eval_id: int, ticker: str):
    conn.execute(
        """INSERT INTO candidates
           (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
            rs_method)
           VALUES (?, ?, 'aplus', 100.0, 101.0, 95.0, 'universe')""",
        (eval_id, ticker),
    )


def _insert_recommendation(
    conn, *, eval_id: int, ticker: str, action_session: str = "2026-04-20",
):
    conn.execute(
        """INSERT INTO daily_recommendations
           (evaluation_run_id, data_asof_date, action_session_date,
            ticker, recommendation, action_text)
           VALUES (?, '2026-04-17', ?, ?, 'today_decision',
                   'Buy-stop $101 · 5 sh · $25 risk')""",
        (eval_id, action_session, ticker),
    )


def _insert_pipeline_run(
    conn, *, started_ts: str, finished_ts: str, evaluation_run_id: int | None,
    action_session: str = "2026-04-20", state: str = "complete",
    lease_token: str = "t-x", charts_status: str = "ok",
) -> int:
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, finished_ts, trigger, data_asof_date,
            action_session_date, state, lease_token, charts_status,
            evaluation_run_id)
           VALUES (?, ?, 'manual', '2026-04-17', ?, ?, ?, ?, ?)""",
        (started_ts, finished_ts, action_session, state,
         lease_token, charts_status, evaluation_run_id),
    )
    return int(cur.lastrowid)


def _no_op_executor():
    class _Executor:
        def submit(self, fn, *a, **kw):
            class _F:
                def result(self_inner, timeout=None):
                    return fn(*a, **kw)
            return _F()
    return _Executor()


def _patch_caches(monkeypatch):
    """Stub PriceCache/OhlcvCache so build_dashboard doesn't try real I/O.
    Returns the cache mock so the test can supply price snapshots."""
    from swing.web.price_cache import PriceCache

    def fake_get_many(self, tickers, deadline_seconds, *, executor=None):
        return {}

    monkeypatch.setattr(PriceCache, "get_many", fake_get_many)
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_today_decisions_bug7_regression_pipeline_eval_wins(
    seeded_db, monkeypatch,
):
    """Bug 7 regression: pipeline ran with eval E1 (A+ = AAPL); a later
    standalone `swing eval` produced E2 with a DIFFERENT A+ set (NVDA only),
    and `_step_recommendations` writes happen only inside the pipeline so E2
    has no recommendations of its own. Pre-T4 today_decisions filtered by
    session-date alone — both E1 and E2 recs would land. With T4 the
    dashboard binds to pipeline_runs.evaluation_run_id (= E1), so
    today_decisions shows only AAPL even though E2 dropped it."""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache

    _patch_caches(monkeypatch)

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            e1 = _insert_eval(conn, run_ts="2026-04-17T21:00:00")
            _insert_aplus_candidate(conn, eval_id=e1, ticker="AAPL")
            _insert_recommendation(conn, eval_id=e1, ticker="AAPL")

            # Pipeline ran with E1 as its own eval. FK populated by T2.
            _insert_pipeline_run(
                conn, started_ts="2026-04-17T20:55:00",
                finished_ts="2026-04-17T21:05:00",
                evaluation_run_id=e1,
            )

            # Standalone eval E2 ran AFTER pipeline. Different A+ set; also
            # writes its own recommendations (the upsert overwrites by
            # (action_session_date, ticker, recommendation), so AAPL stays
            # but NVDA gets added). This simulates an operator running
            # `swing eval` and (separately) re-running recommendations.
            e2 = _insert_eval(conn, run_ts="2026-04-17T22:00:00")
            _insert_aplus_candidate(conn, eval_id=e2, ticker="NVDA")
            _insert_recommendation(conn, eval_id=e2, ticker="NVDA")
    finally:
        conn.close()

    # Mock action_session_for_run to return 2026-04-20 so the seed dates
    # match. (Real datetime.now() may shift before/after midnight.)
    monkeypatch.setattr(
        "swing.evaluation.dates.action_session_for_run",
        lambda now: __import__("datetime").date(2026, 4, 20),
    )

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=_no_op_executor())

    tickers = {d.ticker for d in vm.today_decisions}
    assert tickers == {"AAPL"}, (
        f"today_decisions must reflect the PIPELINE's eval (E1=AAPL only); "
        f"the post-pipeline standalone eval E2 (NVDA) must not leak in. "
        f"Pre-T4 the result would have been {{'AAPL', 'NVDA'}}; got {tickers}."
    )


def test_today_decisions_legacy_pipeline_run_falls_back_to_date_filter(
    seeded_db, monkeypatch,
):
    """A pipeline_runs row from before migration 0006 has evaluation_run_id
    IS NULL. T4's dashboard wiring must fall back to the pre-T4 date-only
    filter so today_decisions still renders something rather than going empty."""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache

    _patch_caches(monkeypatch)

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            e1 = _insert_eval(conn, run_ts="2026-04-17T21:00:00")
            _insert_aplus_candidate(conn, eval_id=e1, ticker="AAPL")
            _insert_recommendation(conn, eval_id=e1, ticker="AAPL")

            # Legacy pipeline run, NULL FK (pre-migration-0006 backfill).
            _insert_pipeline_run(
                conn, started_ts="2026-04-17T20:55:00",
                finished_ts="2026-04-17T21:05:00",
                evaluation_run_id=None,
            )
    finally:
        conn.close()

    monkeypatch.setattr(
        "swing.evaluation.dates.action_session_for_run",
        lambda now: __import__("datetime").date(2026, 4, 20),
    )

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=_no_op_executor())

    tickers = {d.ticker for d in vm.today_decisions}
    assert tickers == {"AAPL"}, (
        f"legacy NULL-FK pipeline run must fall back to date-only filter; "
        f"got {tickers}"
    )


def test_today_decisions_no_pipeline_run_falls_back_to_date_filter(
    seeded_db, monkeypatch,
):
    """No pipeline_runs row at all (fresh install, eval ran via CLI but
    pipeline never ran). The dashboard should still render the standalone
    eval's recommendations via the date-only fallback."""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache

    _patch_caches(monkeypatch)

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            e1 = _insert_eval(conn, run_ts="2026-04-17T21:00:00")
            _insert_aplus_candidate(conn, eval_id=e1, ticker="AAPL")
            _insert_recommendation(conn, eval_id=e1, ticker="AAPL")
    finally:
        conn.close()

    monkeypatch.setattr(
        "swing.evaluation.dates.action_session_for_run",
        lambda now: __import__("datetime").date(2026, 4, 20),
    )

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=_no_op_executor())

    tickers = {d.ticker for d in vm.today_decisions}
    assert tickers == {"AAPL"}


def test_today_decisions_subset_of_chart_targets_when_pipeline_present(
    seeded_db, monkeypatch,
):
    """Cross-consistency invariant (brief §4 T4): every ticker in
    today_decisions is also in pipeline_chart_targets (because A+ tickers
    are always charted by `_step_charts`). Bug 7's reported symptom
    becomes structurally impossible."""
    from swing.data.repos.pipeline import (
        insert_chart_target, list_chart_targets,
    )
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache

    _patch_caches(monkeypatch)

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            e1 = _insert_eval(conn, run_ts="2026-04-17T21:00:00")
            _insert_aplus_candidate(conn, eval_id=e1, ticker="AAPL")
            _insert_aplus_candidate(conn, eval_id=e1, ticker="NVDA")
            _insert_recommendation(conn, eval_id=e1, ticker="AAPL")
            _insert_recommendation(conn, eval_id=e1, ticker="NVDA")
            run_id = _insert_pipeline_run(
                conn, started_ts="2026-04-17T20:55:00",
                finished_ts="2026-04-17T21:05:00",
                evaluation_run_id=e1,
            )
            insert_chart_target(
                conn, pipeline_run_id=run_id, ticker="AAPL",
                source="aplus", chart_status="ok",
            )
            insert_chart_target(
                conn, pipeline_run_id=run_id, ticker="NVDA",
                source="aplus", chart_status="ok",
            )
    finally:
        conn.close()

    monkeypatch.setattr(
        "swing.evaluation.dates.action_session_for_run",
        lambda now: __import__("datetime").date(2026, 4, 20),
    )

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=_no_op_executor())

    today_tickers = {d.ticker for d in vm.today_decisions}

    conn = connect(cfg.paths.db_path)
    try:
        # The latest completed pipeline_run id is what build_dashboard binds to.
        run_id_row = conn.execute(
            "SELECT id FROM pipeline_runs WHERE state='complete' "
            "ORDER BY finished_ts DESC LIMIT 1"
        ).fetchone()
        target_tickers = {
            t.ticker
            for t in list_chart_targets(conn, pipeline_run_id=run_id_row[0])
        }
    finally:
        conn.close()

    assert today_tickers <= target_tickers, (
        f"invariant violated: today_decisions {today_tickers} is not a subset "
        f"of chart_targets {target_tickers}"
    )
