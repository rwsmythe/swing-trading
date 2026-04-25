"""Tranche-C-deferred mixed-anchor fix: build_watchlist's
candidates_by_ticker (and the flag_tags it feeds) must bind to the
pipeline's own eval — same anchor as today_decisions and the dashboard's
candidates_by_ticker.

Without this, the standalone /watchlist page could render flag tags
sourced from a post-pipeline standalone `swing eval` even though the
chart-scope resolver and dashboard already bind via
pipeline_runs.evaluation_run_id. This is the same mixed-anchor bug
class the dashboard fix (commit 1cfc117 Major 2) closed; this test
file is the watchlist-page mirror of
test_dashboard_t4_candidates_eval_scoping.py.
"""
from __future__ import annotations

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry


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


def _seed_watchlist_aapl(conn) -> None:
    upsert_watchlist_entry(conn, WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10",
        last_qualified_date="2026-04-17", status="watch",
        qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-04-17",
        entry_target=181.0, initial_stop_target=170.0,
        last_close=180.0, last_pivot=181.0, last_stop=170.0,
        last_adr_pct=2.5, missing_criteria=None, notes=None,
    ))


def test_watchlist_candidates_bound_to_pipeline_eval(seeded_db, monkeypatch):
    """E1 (pipeline's eval) has AAPL as A+. E2 (later standalone) drops
    AAPL and adds NVDA. The watchlist VM's candidates_by_ticker / flag_tags
    must reflect E1, not E2."""
    from swing.web.view_models.watchlist import build_watchlist
    from swing.web.price_cache import PriceCache

    _patch_caches(monkeypatch)

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_watchlist_aapl(conn)
            # E1: AAPL is A+ (the pipeline's own eval).
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

    cache = PriceCache(cfg)
    vm = build_watchlist(cfg=cfg, cache=cache, executor=_no_op_executor())

    cbt = dict(vm.candidates_by_ticker)
    assert "AAPL" in cbt, (
        f"AAPL must be in candidates_by_ticker (it was the pipeline's eval); "
        f"got {set(cbt.keys())}"
    )
    assert "NVDA" not in cbt, (
        f"NVDA must NOT be in candidates_by_ticker — it only appeared in E2 "
        f"(post-pipeline standalone eval). Got {set(cbt.keys())}"
    )
    # AAPL bucket=aplus → flag_tags includes 'A+'. Pre-fix, AAPL would be
    # missing entirely from candidates_by_ticker (E2 has only NVDA), so
    # flag_tags would not include AAPL at all.
    assert vm.flag_tags.get("AAPL") == ("A+",), (
        f"flag_tags['AAPL'] must reflect E1's bucket=aplus; got "
        f"{vm.flag_tags.get('AAPL')!r}"
    )


def test_watchlist_candidates_falls_back_to_latest_eval_when_no_pipeline(
    seeded_db, monkeypatch,
):
    """No pipeline_runs row → flag_tags / candidates_by_ticker fall back to
    the latest eval. Pre-fix behavior preserved for fresh installs."""
    from swing.web.view_models.watchlist import build_watchlist
    from swing.web.price_cache import PriceCache

    _patch_caches(monkeypatch)

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_watchlist_aapl(conn)
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

    cache = PriceCache(cfg)
    vm = build_watchlist(cfg=cfg, cache=cache, executor=_no_op_executor())
    assert "AAPL" in dict(vm.candidates_by_ticker)
    assert vm.flag_tags.get("AAPL") == ("A+",)


def test_watchlist_candidates_legacy_null_fk_uses_latest_eval(
    seeded_db, monkeypatch,
):
    """Legacy pipeline_runs row (NULL FK) → fall back to latest eval. Keeps
    the watchlist renderable for pre-migration-0006 historical rows."""
    from swing.web.view_models.watchlist import build_watchlist
    from swing.web.price_cache import PriceCache

    _patch_caches(monkeypatch)

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_watchlist_aapl(conn)
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
            # Legacy pipeline run (NULL FK) — pre-migration-0006 historical row.
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

    cache = PriceCache(cfg)
    vm = build_watchlist(cfg=cfg, cache=cache, executor=_no_op_executor())
    assert "AAPL" in dict(vm.candidates_by_ticker)
