"""Task 6 — per-row cohort-hint preview chip (opt-in site #2).

`cohort_hint_for(candidate, registry)` is the render-time attribution
PREVIEW: the narrow hypothesis name (abbreviated) a candidate WOULD
attribute as, or 'broad-watch', or None. The lone `include_baseline=True`
hint call site lives in `swing/web/view_models/watchlist.py`.

Coverage:
  - unit: broad-watch (bucket='watch'), narrow (bucket='aplus' -> 'A+'),
    None candidate.
  - THREE-SITE render (the load-bearing one): the standalone watchlist
    page, the dashboard top-5 section, and the /watchlist/WCH/row collapse
    route ALL render a `tag-cohort` 'broad-watch' chip for a seeded watch
    candidate that matches no narrow hypothesis.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from swing.data.db import connect, ensure_schema
from swing.data.models import Candidate, WatchlistEntry
from swing.data.repos.hypothesis import list_hypotheses
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app
from swing.web.view_models.watchlist import cohort_hint_for


def _registry(db_path: Path):
    conn = ensure_schema(db_path)
    try:
        return list_hypotheses(conn)
    finally:
        conn.close()


def _watch_candidate(ticker: str = "WCH") -> Candidate:
    return Candidate(
        ticker=ticker, bucket="watch", close=180.0, pivot=181.0,
        initial_stop=170.0, adr_pct=2.0, tight_streak=None,
        pullback_pct=None, prior_trend_pct=None, rs_rank=None,
        rs_return_12w_vs_spy=None, rs_method="universe",
        pattern_tag=None, notes=None, criteria=(),
    )


def _aplus_candidate(ticker: str = "APL") -> Candidate:
    return Candidate(
        ticker=ticker, bucket="aplus", close=180.0, pivot=181.0,
        initial_stop=170.0, adr_pct=2.0, tight_streak=None,
        pullback_pct=None, prior_trend_pct=None, rs_rank=None,
        rs_return_12w_vs_spy=None, rs_method="universe",
        pattern_tag=None, notes=None, criteria=(),
    )


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


def test_cohort_hint_for_watch_candidate_is_broad_watch(seeded_db):
    cfg, _ = seeded_db
    registry = _registry(cfg.paths.db_path)
    assert cohort_hint_for(_watch_candidate(), registry) == "broad-watch"


def test_cohort_hint_for_narrow_candidate_is_truthy_not_broad_watch(seeded_db):
    cfg, _ = seeded_db
    registry = _registry(cfg.paths.db_path)
    hint = cohort_hint_for(_aplus_candidate(), registry)
    assert hint and hint != "broad-watch"
    assert hint == "A+"


def test_cohort_hint_for_none_candidate_is_none(seeded_db):
    cfg, _ = seeded_db
    registry = _registry(cfg.paths.db_path)
    assert cohort_hint_for(None, registry) is None


# ---------------------------------------------------------------------------
# Seed helpers for the three-site render test
# ---------------------------------------------------------------------------


def _seed_watch_pipeline(db_path: Path, ticker: str) -> None:
    """Completed pipeline_run + one watch-bucket candidate (no criteria)."""
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
    """Active watchlist row so `ticker` renders on /watchlist + dashboard top-5."""
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


# ---------------------------------------------------------------------------
# Three-site render (load-bearing, Codex R2-Major)
# ---------------------------------------------------------------------------


def test_cohort_chip_renders_on_all_three_surfaces(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_watch_pipeline(cfg.paths.db_path, "WCH")
    _seed_watchlist_row(cfg.paths.db_path, "WCH")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        watchlist_html = client.get("/watchlist").text
        dashboard_html = client.get("/").text
        row_html = client.get("/watchlist/WCH/row").text

    for label, html in (
        ("/watchlist", watchlist_html),
        ("/", dashboard_html),
        ("/watchlist/WCH/row", row_html),
    ):
        assert "tag-cohort" in html, (
            f"{label} must render the cohort chip class; got: {html[:600]!r}"
        )
        assert "broad-watch" in html, (
            f"{label} must render the broad-watch hint; got: {html[:600]!r}"
        )
