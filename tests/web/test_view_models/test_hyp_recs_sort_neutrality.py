"""Sort-neutrality regression guard for the hyp-recs section.

Task 5.7 (plan §Task 5 sub-task 5.7). Two binding test shapes per the
plan's R3-Major-1 + R4-Major-2 contracts:

1. Cross-builder neutrality: `build_dashboard.active_recommendations`
   ticker order MUST equal `build_hyp_recs_section.active_recommendations`
   ticker order, given the same DB state. Discriminates a regression in
   the Task 3 `_build_active_recommendations` extraction (e.g. a swapped
   sort key, dropped field) that diverges the two builders' rendered
   tuples.

2. Pinned-baseline neutrality: ticker order MUST equal a tuple captured
   against the PRE-CHANGE baseline (HEAD `a492b84`). The pinned tuple
   was captured via the 6-step worktree protocol the plan specifies
   (lines 1715-1843), NOT against the first-green-after-edit run, so
   the pin survives any later refactor that introduces an internally
   self-consistent regression.

No production-code change in this sub-task.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.price_cache import PriceCache, PriceSnapshot


# Captured against HEAD `a492b84` (pre-Task-3 baseline) via the 6-step
# worktree protocol in the plan (lines 1715-1843). Re-capture is required
# whenever the seed body below changes — the pin is rooted in real
# pre-change behavior, not in post-Task-3 self-consistency.
BASELINE_TUPLE: tuple[str, ...] = ("AMD", "NVDA", "TSLA")


def _patch_price_cache(monkeypatch):
    """Stub PriceCache.get_many so the builders don't fetch live prices."""

    def get_many(self, tickers, *, deadline_seconds, executor):
        return {
            t: PriceSnapshot(
                ticker=t, price=180.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        }
    monkeypatch.setattr(PriceCache, "get_many", get_many)
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _make_watchlist_entry(
    *, ticker: str, entry_target: float, initial_stop_target: float,
    last_close: float,
) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=ticker, added_date="2026-04-29",
        last_qualified_date="2026-04-29", status="watch",
        qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-04-28",
        entry_target=entry_target, initial_stop_target=initial_stop_target,
        last_close=last_close, last_pivot=None, last_stop=None,
        last_adr_pct=2.0, missing_criteria=None, notes=None,
    )


def _seed_sort_neutrality_fixture(cfg: Config) -> None:
    """Seed 3 A+ candidates exercising the prioritizer's tie-breaking.

    Each candidate has the same close-to-pivot ratio (0.99), so all three
    receive the same `priority_hint` from `_priority_hint_for`. Same A+
    baseline hypothesis, same progress (zero closed trades). Result: the
    prioritizer's deterministic alpha tie-break on `candidate_ticker`
    drives the final order.

    Relies on the migration-seeded `A+ baseline` hypothesis (id=1) per
    the canonical pattern in `_seed_hyp_recs_fixture`; no manual
    `hypothesis_registry` INSERT.

    NOTE: this body MUST stay in lockstep with the inlined `_seed`
    function in the (uncommitted) `_capture_baseline.py` capture helper
    used to capture `BASELINE_TUPLE`. If you change one, re-capture.
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count)
                   VALUES ('2026-04-29T09:00:00','2026-04-28','2026-04-29',
                           NULL, 3, 3, 0, 0, 0, 0)"""
            )
            eval_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO pipeline_runs
                   (state, started_ts, finished_ts, trigger, lease_token,
                    action_session_date, data_asof_date, evaluation_run_id,
                    charts_status)
                   VALUES ('complete','2026-04-29T08:00:00',
                           '2026-04-29T09:00:00','scheduled','tok-5p7',
                           '2026-04-29','2026-04-28',?,'ok')""",
                (eval_id,),
            )
            for tk, pivot, stop in [
                ("NVDA", 100.0, 95.0),
                ("AMD", 200.0, 190.0),
                ("TSLA", 300.0, 285.0),
            ]:
                upsert_watchlist_entry(
                    conn,
                    _make_watchlist_entry(
                        ticker=tk, entry_target=pivot,
                        initial_stop_target=stop, last_close=pivot * 0.99,
                    ),
                )
                conn.execute(
                    """INSERT INTO candidates
                       (evaluation_run_id, ticker, bucket, close, pivot,
                        initial_stop, adr_pct, tight_streak, pullback_pct,
                        prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                        rs_method, pattern_tag, notes, sector, industry)
                       VALUES (?, ?, 'aplus', ?, ?, ?, 2.0, 5,
                               NULL, NULL, NULL, NULL, 'fallback_spy',
                               NULL, NULL, 'Technology', 'Semiconductors')""",
                    (eval_id, tk, pivot * 0.99, pivot, stop),
                )
    finally:
        conn.close()


def test_cross_builder_sort_neutrality(seeded_db, monkeypatch):
    """`build_dashboard.active_recommendations` ticker order MUST equal
    `build_hyp_recs_section.active_recommendations` ticker order against
    identical DB state. Discriminates a Task 3 regression that diverges
    the two render paths.
    """
    from swing.web.view_models.dashboard import (
        build_dashboard, build_hyp_recs_section,
    )

    cfg, _ = seeded_db
    _seed_sort_neutrality_fixture(cfg)
    _patch_price_cache(monkeypatch)

    cache = PriceCache(cfg)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        dash_vm = build_dashboard(
            cfg=cfg, cache=cache, executor=executor, ohlcv_cache=None,
        )
        section_vm = build_hyp_recs_section(
            cfg=cfg, cache=cache, executor=executor,
        )
    finally:
        executor.shutdown(wait=False)

    dash_tickers = tuple(r.ticker for r in dash_vm.active_recommendations)
    section_tickers = tuple(
        r.ticker for r in section_vm.active_recommendations
    )
    assert dash_tickers == section_tickers, (
        "build_dashboard and build_hyp_recs_section must produce the same"
        f" ticker order; got dash={dash_tickers!r}"
        f" section={section_tickers!r}"
    )


def test_pinned_baseline_neutrality(seeded_db, monkeypatch):
    """`build_dashboard.active_recommendations` ticker order MUST equal
    the tuple captured against the pre-Task-3 baseline (HEAD `a492b84`)
    via the 6-step worktree capture protocol. Discriminates ANY future
    perturbation of prioritizer logic, hypothesis registry scoring, or
    default sort tiebreakers — the pin is rooted in real pre-change
    behavior, not in post-Task-3 self-consistency.
    """
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _ = seeded_db
    _seed_sort_neutrality_fixture(cfg)
    _patch_price_cache(monkeypatch)

    cache = PriceCache(cfg)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        dash_vm = build_dashboard(
            cfg=cfg, cache=cache, executor=executor, ohlcv_cache=None,
        )
    finally:
        executor.shutdown(wait=False)

    tickers = tuple(r.ticker for r in dash_vm.active_recommendations)
    assert tickers == BASELINE_TUPLE, (
        f"hyp-recs ticker order drifted from pre-Task-3 baseline."
        f" got={tickers!r} expected={BASELINE_TUPLE!r}"
    )


# Phase 4 (Task 10) — non-equal-priority discriminator. Closes Phase 2
# R1 Minor 2 advisory + the sort-coupling-test-vacuousness lesson.
NON_EQUAL_PRIORITY_TUPLE: tuple[str, ...] = ("ZZZ", "MMM", "AAA")


def _seed_non_equal_priority_fixture(cfg: Config) -> None:
    """Seed 3 A+ candidates with DIFFERENT priority_hint values so the
    prioritizer's priority_hint comparison drives the order, NOT
    alphabetical tiebreak.

    Priority-hint-correct order: ZZZ (0.01) < MMM (0.05) < AAA (0.10).
    Alphabetical order: AAA, MMM, ZZZ — REVERSED. A regression that
    bypasses priority_hint and falls to alphabetical produces the
    reversed tuple, which the discriminating assertion catches.
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count)
                   VALUES ('2026-04-29T09:00:00','2026-04-28','2026-04-29',
                           NULL, 3, 3, 0, 0, 0, 0)"""
            )
            eval_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO pipeline_runs
                   (state, started_ts, finished_ts, trigger, lease_token,
                    action_session_date, data_asof_date, evaluation_run_id,
                    charts_status)
                   VALUES ('complete','2026-04-29T08:00:00',
                           '2026-04-29T09:00:00','scheduled','tok-nep',
                           '2026-04-29','2026-04-28',?,'ok')""",
                (eval_id,),
            )
            for tk, pivot, close in [
                ("ZZZ", 100.0, 99.0),
                ("MMM", 200.0, 190.0),
                ("AAA", 300.0, 270.0),
            ]:
                upsert_watchlist_entry(
                    conn,
                    _make_watchlist_entry(
                        ticker=tk, entry_target=pivot,
                        initial_stop_target=pivot * 0.95, last_close=close,
                    ),
                )
                conn.execute(
                    """INSERT INTO candidates
                       (evaluation_run_id, ticker, bucket, close, pivot,
                        initial_stop, adr_pct, tight_streak, pullback_pct,
                        prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                        rs_method, pattern_tag, notes, sector, industry)
                       VALUES (?, ?, 'aplus', ?, ?, ?, 2.0, 5,
                               NULL, NULL, NULL, NULL, 'fallback_spy',
                               NULL, NULL, 'Technology', 'Semiconductors')""",
                    (eval_id, tk, close, pivot, pivot * 0.95),
                )
    finally:
        conn.close()


def test_non_equal_priority_sort_order(seeded_db, monkeypatch):
    """Discriminating: fixture produces DIFFERENT priority_hint values
    so the prioritizer's priority_hint comparison drives the order,
    NOT the alphabetical tiebreak. A regression that drops priority_hint
    from the sort key (or inverts the comparison) would produce
    alphabetical order ('AAA', 'MMM', 'ZZZ'), which fails the
    discriminating assertion ('ZZZ', 'MMM', 'AAA')."""
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _ = seeded_db
    _seed_non_equal_priority_fixture(cfg)
    _patch_price_cache(monkeypatch)

    cache = PriceCache(cfg)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        dash_vm = build_dashboard(
            cfg=cfg, cache=cache, executor=executor, ohlcv_cache=None,
        )
    finally:
        executor.shutdown(wait=False)

    tickers = tuple(r.ticker for r in dash_vm.active_recommendations)
    assert tickers == NON_EQUAL_PRIORITY_TUPLE, (
        f"hyp-recs ticker order must reflect priority_hint ASC "
        f"(closer-to-pivot first): expected={NON_EQUAL_PRIORITY_TUPLE!r} "
        f"got={tickers!r}. A regression that falls to alphabetical "
        f"tiebreak instead of priority_hint produces "
        f"('AAA', 'MMM', 'ZZZ')."
    )
