"""Task 6 — dashboard broad-watch containment regression.

BEHAVIORAL: with an active "Broad-watch baseline" registry row AND a
pure-watch candidate (matches no narrow hypothesis), the dashboard
recommendation panel must NOT surface a Broad-watch baseline row
(`include_baseline=False` at the matcher calls), while the per-row
cohort-hint preview path IS live (`vm.cohort_hints["WCH"] == "broad-watch"`).

AST companion: both `match_candidate_to_hypotheses` calls in
dashboard.py stay `include_baseline=False` (R6 containment).
"""
from __future__ import annotations

import ast
from pathlib import Path

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.price_cache import PriceCache
from swing.web.view_models.dashboard import build_dashboard

BROAD_PREFIX = "Broad-watch baseline"


def _seed_watch_pipeline(db_path: Path, ticker: str) -> None:
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 0, 1, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'watch', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id, ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def _seed_watchlist_row(db_path: Path, ticker: str) -> None:
    conn = connect(db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker=ticker,
                added_date="2026-04-17",
                last_qualified_date="2026-04-17",
                status="watch",
                qualification_count=1,
                not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0,
                initial_stop_target=170.0,
                last_close=180.0,
                last_pivot=181.0,
                last_stop=170.0,
                last_adr_pct=2.0,
                missing_criteria=None,
                notes=None,
            ))
    finally:
        conn.close()


def test_dashboard_recommendations_exclude_broad_watch_but_hint_is_live(
    seeded_db, monkeypatch,
):
    cfg, _ = seeded_db
    _seed_watch_pipeline(cfg.paths.db_path, "WCH")
    _seed_watchlist_row(cfg.paths.db_path, "WCH")

    # Stub the live price fetch (no network / executor) — the cohort-hint +
    # containment logic is price-independent.
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *args, **kwargs: {},
    )
    cache = PriceCache(cfg.web)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)

    # Containment: no recommendation row attributes to the broad-watch baseline.
    for rec in vm.active_recommendations:
        assert not rec.suggested_label.startswith(BROAD_PREFIX), (
            f"recommendation panel leaked a broad-watch row: {rec!r}"
        )

    # The hint path IS live for the same watch candidate.
    assert vm.cohort_hints.get("WCH") == "broad-watch"


def test_dashboard_matcher_calls_do_not_pass_include_baseline():
    src = Path("swing/web/view_models/dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", getattr(getattr(n, "func", None), "attr", None)) == "match_candidate_to_hypotheses"]
    assert len(calls) == 2
    for c in calls:
        assert not any(k.arg == "include_baseline" for k in c.keywords), \
            "dashboard matcher call must stay include_baseline=False (R6 containment)"
