"""Discriminating tests for `build_hyp_recs_section` anchor selection.

Task 2 of the hyp-recs success-path fix plan: the section builder must
consume the shared `latest_evaluation_run_id(conn)` helper (rather than
its own inline pipeline_runs query), so:

1. Standalone-eval-only state (an `evaluation_runs` row but NO
   `pipeline_runs` row) renders a non-empty section. Pre-refactor, the
   inline query returned None and the section was empty. Post-refactor,
   the helper falls back to the latest standalone eval and the matcher
   surfaces its candidates.

2. Under tied `finished_ts` between two completed pipeline_runs, BOTH
   `build_dashboard` and `build_hyp_recs_section` resolve to the SAME
   `evaluation_run_id` and therefore surface the same recommended
   tickers. This is the cross-consumer anchor-sharing invariant
   Codex R1 Major 2 requires.

Sentinel ticker `TESTAPLUS` is reserved for Tasks 2-5 of this plan to
keep test fixtures unambiguous against the CC-pivot sentinel pair
(FOO/BAR @ $24.13/$26.98) used by an earlier dispatch.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.web.price_cache import PriceCache, PriceSnapshot


def _patch_price_cache(monkeypatch):
    """Stub PriceCache.get_many so the builder doesn't fetch live prices."""

    def get_many(self, tickers, *, deadline_seconds, executor):
        return {
            t: PriceSnapshot(
                ticker=t, price=99.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        }
    monkeypatch.setattr(PriceCache, "get_many", get_many)
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _seed_standalone_eval_with_aplus_candidate(
    cfg: Config, *, ticker: str = "TESTAPLUS"
) -> int:
    """Seed an `evaluation_runs` row with NO `pipeline_runs` row, plus a
    single A+ candidate matching the migration-seeded `A+ baseline`
    hypothesis. Returns the new evaluation_run id.

    The candidate's pivot/close ratio (close = pivot * 0.99) keeps the
    matcher's priority_hint stable; values are arbitrary.
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date,
                    finviz_csv_path, tickers_evaluated, aplus_count,
                    watch_count, skip_count, excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-29T09:00:00", "2026-04-28", "2026-04-29"),
            )
            eval_id = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 99.0, 100.0, 95.0, 'universe')""",
                (eval_id, ticker),
            )
        return eval_id
    finally:
        conn.close()


def _seed_two_pipeline_runs_tied_finished_ts(
    cfg: Config,
    *,
    higher_id_eval_candidate_ticker: str,
    lower_id_eval_candidate_ticker: str,
) -> None:
    """Seed two completed `pipeline_runs` with identical `finished_ts`.

    Lower-id row inserts FIRST so SQLite's default tied-key ordering
    would pick its evaluation_run_id without an explicit `id DESC`
    tiebreaker. The helper's `id DESC` (Task 1) deterministically picks
    the higher-id row's eval. Each eval gets exactly one A+ candidate,
    so the section's recommended-ticker set is a 1:1 witness for which
    eval the helper resolved.
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Lower-id eval + pipeline run (inserted first → lower rowid).
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date,
                    finviz_csv_path, tickers_evaluated, aplus_count,
                    watch_count, skip_count, excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-29T08:55:00", "2026-04-28", "2026-04-29"),
            )
            lower_eval_id = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 99.0, 100.0, 95.0, 'universe')""",
                (lower_eval_id, lower_id_eval_candidate_ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id, charts_status)
                   VALUES ('2026-04-29T08:00:00', '2026-04-29T09:00:00',
                           'scheduled', '2026-04-28', '2026-04-29',
                           'complete', 'tok-lo', ?, 'ok')""",
                (lower_eval_id,),
            )
            # Higher-id eval + pipeline run (inserted second → higher rowid).
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date,
                    finviz_csv_path, tickers_evaluated, aplus_count,
                    watch_count, skip_count, excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-29T08:56:00", "2026-04-28", "2026-04-29"),
            )
            higher_eval_id = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 99.0, 100.0, 95.0, 'universe')""",
                (higher_eval_id, higher_id_eval_candidate_ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id, charts_status)
                   VALUES ('2026-04-29T08:00:01', '2026-04-29T09:00:00',
                           'scheduled', '2026-04-28', '2026-04-29',
                           'complete', 'tok-hi', ?, 'ok')""",
                (higher_eval_id,),
            )
    finally:
        conn.close()


def test_build_hyp_recs_section_falls_back_to_standalone_eval(
    seeded_db, monkeypatch,
):
    """Standalone-eval-only state (no completed pipeline_runs) — section
    must render via the `latest_evaluation_run_id` 2-step fallback.

    Discriminating: pre-refactor, the inline pipeline_runs query in
    `build_hyp_recs_section` returns None under this state, so the
    section is empty. Post-refactor, the helper falls back to the
    standalone eval and the matcher runs against its candidates.
    """
    from swing.web.view_models.dashboard import build_hyp_recs_section

    cfg, _ = seeded_db
    _seed_standalone_eval_with_aplus_candidate(cfg, ticker="TESTAPLUS")
    _patch_price_cache(monkeypatch)

    cache = PriceCache(cfg)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        section_vm = build_hyp_recs_section(
            cfg=cfg, cache=cache, executor=executor,
        )
    finally:
        executor.shutdown(wait=False)

    tickers = [r.ticker for r in section_vm.active_recommendations]
    assert "TESTAPLUS" in tickers, (
        "Standalone-eval-only state should fall back to the latest "
        "evaluation_runs row and surface its candidates as recommendations. "
        f"Got tickers={tickers!r}"
    )


def test_build_hyp_recs_section_and_build_dashboard_share_anchor_under_tied_finished_ts(
    seeded_db, monkeypatch,
):
    """Codex R1 Major 2: under tied `finished_ts` between two completed
    pipeline_runs, both consumers must resolve to the SAME
    `evaluation_run_id` and surface the same recommended-ticker set.

    Discriminating: pre-Task-2, `build_hyp_recs_section`'s inline query
    could return one row's eval while `build_dashboard` (already routed
    through `latest_evaluation_run_id` for `candidates_eval_id`) returns
    the other. Post-refactor, both consumers share the helper, and
    Task 1's `id DESC` tiebreaker pins both to the higher-id row's eval.
    """
    from swing.web.view_models.dashboard import (
        build_dashboard, build_hyp_recs_section,
    )

    cfg, _ = seeded_db
    _seed_two_pipeline_runs_tied_finished_ts(
        cfg,
        higher_id_eval_candidate_ticker="TESTAPLUS",
        lower_id_eval_candidate_ticker="TESTOTHER",
    )
    _patch_price_cache(monkeypatch)

    cache = PriceCache(cfg)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        section_vm = build_hyp_recs_section(
            cfg=cfg, cache=cache, executor=executor,
        )
        dashboard_vm = build_dashboard(
            cfg=cfg, cache=cache, executor=executor, ohlcv_cache=None,
        )
    finally:
        executor.shutdown(wait=False)

    section_tickers = {r.ticker for r in section_vm.active_recommendations}
    dashboard_tickers = {
        r.ticker for r in dashboard_vm.active_recommendations
    }

    assert section_tickers == dashboard_tickers, (
        f"Anchor divergence: build_hyp_recs_section saw {section_tickers}, "
        f"build_dashboard saw {dashboard_tickers}. Both must resolve to "
        f"the same evaluation_run_id under tied finished_ts."
    )
    # And specifically: the higher-id row wins (Task 1's `id DESC`).
    assert "TESTAPLUS" in section_tickers
    assert "TESTOTHER" not in section_tickers


def test_build_hyp_recs_section_excludes_specified_tickers(
    seeded_db, monkeypatch,
):
    """Task 3: `exclude_tickers` kwarg structurally suppresses listed
    tickers from the recommendations output, even when their candidate
    row is still in the latest evaluation run.

    Discriminating: pre-Task-3, the kwarg doesn't exist (TypeError on
    call); a pure signature-only addition without filter wiring would
    accept the call but still surface TESTAPLUS in the recommendations.
    Both halves are required:
      - sanity baseline: without the kwarg, TESTAPLUS DOES appear;
      - filtered: with `exclude_tickers=("TESTAPLUS",)`, it does NOT.
    """
    from swing.web.view_models.dashboard import build_hyp_recs_section

    cfg, _ = seeded_db
    _seed_standalone_eval_with_aplus_candidate(cfg, ticker="TESTAPLUS")
    _patch_price_cache(monkeypatch)

    cache = PriceCache(cfg)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        # Sanity baseline: without exclude_tickers, TESTAPLUS appears.
        baseline_vm = build_hyp_recs_section(
            cfg=cfg, cache=cache, executor=executor,
        )
        baseline_tickers = [
            r.ticker for r in baseline_vm.active_recommendations
        ]
        assert "TESTAPLUS" in baseline_tickers, (
            "Sanity baseline failed: TESTAPLUS should appear in the "
            "section without exclude_tickers. The discriminating value "
            "of the filtered assertion below depends on this. "
            f"Got tickers={baseline_tickers!r}"
        )

        # Filtered: with exclude_tickers, TESTAPLUS is suppressed.
        filtered_vm = build_hyp_recs_section(
            cfg=cfg, cache=cache, executor=executor,
            exclude_tickers=("TESTAPLUS",),
        )
    finally:
        executor.shutdown(wait=False)

    filtered_tickers = [
        r.ticker for r in filtered_vm.active_recommendations
    ]
    assert "TESTAPLUS" not in filtered_tickers, (
        "exclude_tickers kwarg should structurally suppress TESTAPLUS "
        f"from the recommendations. Got tickers={filtered_tickers!r}"
    )
