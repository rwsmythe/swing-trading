"""Tranche C adversarial-review Round 1 Major 2: build_dashboard's
candidates_by_ticker (and the flag_tags it feeds) must bind to the
pipeline's own eval — same anchor as today_decisions.

Without this, the dashboard could show today_decisions sourced from E1
(the pipeline's eval) alongside watchlist flag-tags sourced from E2 (a
later standalone eval). That is the same mixed-anchor inconsistency Bug 7
reported for chart-scope vs today_decisions, just on a different field.
"""
from __future__ import annotations

from swing.data.db import connect


def _no_op_executor():
    class _Executor:
        def submit(self, fn, *a, **kw):
            class _F:
                def result(self_inner, timeout=None):
                    return fn(*a, **kw)
            return _F()
    return _Executor()


def _patch_caches(monkeypatch):
    from swing.web.price_cache import PriceCache

    def fake_get_many(self, tickers, deadline_seconds, *, executor=None):
        return {}

    monkeypatch.setattr(PriceCache, "get_many", fake_get_many)
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_dashboard_candidates_bound_to_pipeline_eval(seeded_db, monkeypatch):
    """E1 (pipeline's eval) has AAPL with a passing trend-template count.
    E2 (later standalone) drops AAPL but adds NVDA. The dashboard's
    candidates_by_ticker must reflect E1, not E2."""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache

    _patch_caches(monkeypatch)

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # E1: AAPL is A+
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T21:00:00', '2026-04-17', '2026-04-20',
                           NULL, 1, 1, 0, 0, 0, 0, 'v1', 'd')""",
            )
            e1 = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'AAPL', 'aplus', 100.0, 101.0, 95.0, 'universe')""",
                (e1,),
            )
            # Pipeline run bound to E1 via FK.
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token, charts_status,
                    evaluation_run_id)
                   VALUES ('2026-04-17T20:55:00', '2026-04-17T21:05:00',
                           'manual', '2026-04-17', '2026-04-20',
                           'complete', 't-x', 'ok', ?)""",
                (e1,),
            )
            # E2: standalone, post-pipeline. Drops AAPL, adds NVDA.
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T22:00:00', '2026-04-17', '2026-04-20',
                           NULL, 1, 1, 0, 0, 0, 0, 'v1', 'd')""",
            )
            e2 = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'NVDA', 'aplus', 200.0, 201.0, 190.0, 'universe')""",
                (e2,),
            )
    finally:
        conn.close()

    monkeypatch.setattr(
        "swing.web.view_models.dashboard.action_session_for_run",
        lambda now: __import__("datetime").date(2026, 4, 20),
    )

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=_no_op_executor())

    # candidates_by_ticker must reflect E1's set (AAPL only), not E2 (NVDA only).
    cbt = dict(vm.candidates_by_ticker)
    assert "AAPL" in cbt, (
        f"AAPL must be in candidates_by_ticker (it was the pipeline's eval); "
        f"got {set(cbt.keys())}"
    )
    assert "NVDA" not in cbt, (
        f"NVDA must NOT be in candidates_by_ticker — it only appeared in E2 "
        f"(post-pipeline standalone eval). Got {set(cbt.keys())}"
    )


def test_dashboard_candidates_falls_back_to_latest_eval_when_no_pipeline(
    seeded_db, monkeypatch,
):
    """No pipeline_runs row → flag_tags / candidates_by_ticker fall back to
    the latest eval. (Pre-fix behavior preserved for fresh installs.)"""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache

    _patch_caches(monkeypatch)

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T22:00:00', '2026-04-17', '2026-04-20',
                           NULL, 1, 1, 0, 0, 0, 0, 'v1', 'd')""",
            )
            e1 = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'AAPL', 'aplus', 100.0, 101.0, 95.0, 'universe')""",
                (e1,),
            )
    finally:
        conn.close()

    monkeypatch.setattr(
        "swing.web.view_models.dashboard.action_session_for_run",
        lambda now: __import__("datetime").date(2026, 4, 20),
    )

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=_no_op_executor())
    assert "AAPL" in dict(vm.candidates_by_ticker)


def test_dashboard_candidates_legacy_null_fk_uses_latest_eval(
    seeded_db, monkeypatch,
):
    """Legacy pipeline_runs row (NULL FK) → fall back to latest eval (pre-T4
    behavior). This keeps the dashboard renderable for pre-migration-0006
    historical rows."""
    from swing.web.view_models.dashboard import build_dashboard
    from swing.web.price_cache import PriceCache

    _patch_caches(monkeypatch)

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T22:00:00', '2026-04-17', '2026-04-20',
                           NULL, 1, 1, 0, 0, 0, 0, 'v1', 'd')""",
            )
            e1 = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'AAPL', 'aplus', 100.0, 101.0, 95.0, 'universe')""",
                (e1,),
            )
            # Legacy pipeline run (NULL FK).
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token, charts_status,
                    evaluation_run_id)
                   VALUES ('2026-04-17T20:55:00', '2026-04-17T21:05:00',
                           'manual', '2026-04-17', '2026-04-20',
                           'complete', 't-x', 'ok', NULL)""",
            )
    finally:
        conn.close()

    monkeypatch.setattr(
        "swing.web.view_models.dashboard.action_session_for_run",
        lambda now: __import__("datetime").date(2026, 4, 20),
    )

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=_no_op_executor())
    assert "AAPL" in dict(vm.candidates_by_ticker)
