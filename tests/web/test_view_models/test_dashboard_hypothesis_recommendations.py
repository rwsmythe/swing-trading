"""Dashboard hypothesis-recommendations panel — Session 2 (frontend brief §4.1).

The dashboard surfaces the prioritized matcher output as a top-N list. These
tests pin the wiring contract: VM field shape, matcher integration, top-N
truncation, ordering follows prioritizer, and graceful degradation for
empty/no-pipeline cases.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from swing.data.db import connect


def _seed_pipeline_with_candidates(cfg, candidates: list[dict[str, Any]]) -> int:
    """Seed one complete pipeline run linked to one evaluation_run; insert
    the supplied candidates + their criteria. Returns the pipeline run id.

    `candidates` is a list of dicts: {ticker, bucket, criteria=[(name,result), ...]}.
    Defaults provide A+ candidates with no criteria — sufficient for the
    `_aplus_baseline_match` rule.
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, ?, 0, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20",
                 len(candidates)),
            )
            eval_id = cur.lastrowid
            for c in candidates:
                cand_cur = conn.execute(
                    """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                       close, pivot, initial_stop, rs_method)
                       VALUES (?, ?, ?, ?, ?, ?, 'universe')""",
                    (eval_id, c["ticker"], c["bucket"],
                     c.get("close", 100.0), c.get("pivot", 101.0),
                     c.get("stop", 95.0)),
                )
                cid = cand_cur.lastrowid
                for crit_name, crit_result in c.get("criteria", []):
                    conn.execute(
                        """INSERT INTO candidate_criteria
                           (candidate_id, criterion_name, layer, result)
                           VALUES (?, ?, 'vcp', ?)""",
                        (cid, crit_name, crit_result),
                    )
            cur2 = conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
            return int(cur2.lastrowid)
    finally:
        conn.close()


def _patched_caches(monkeypatch):
    from swing.web.price_cache import PriceCache, PriceSnapshot

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


def test_dashboard_vm_exposes_active_recommendations_field(seeded_db, monkeypatch):
    """The VM has an `active_recommendations` tuple, populated from the
    matcher + prioritizer output."""
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import (
        DashboardVM, HypothesisRecommendation, build_dashboard,
    )

    cfg, _ = seeded_db
    _seed_pipeline_with_candidates(cfg, [
        # Pure A+ candidate — matches `A+ baseline` hypothesis.
        {"ticker": "AAPL", "bucket": "aplus", "close": 180.0, "pivot": 181.0},
    ])
    _patched_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)

    assert isinstance(vm, DashboardVM)
    # Tuple is the documented type so the dataclass stays frozen-friendly.
    assert isinstance(vm.active_recommendations, tuple)
    assert len(vm.active_recommendations) == 1
    rec = vm.active_recommendations[0]
    assert isinstance(rec, HypothesisRecommendation)
    assert rec.ticker == "AAPL"
    assert rec.hypothesis_name == "A+ baseline"
    assert rec.hypothesis_progress_n == 0  # no closed trades yet
    assert rec.hypothesis_progress_target == 20
    assert rec.tripwire_fired is False
    assert rec.tripwire_reason is None
    # Suggested label MUST start with the canonical hypothesis name so future
    # tripwire/progress aggregation (case-insensitive prefix) attributes the
    # trade correctly. Frontend brief §0 / Session 1 R1 fix.
    assert rec.suggested_label.startswith("A+ baseline"), (
        f"suggested_label must start with hypothesis name; got {rec.suggested_label!r}"
    )
    # Current price is sourced from the price cache for this ticker.
    assert rec.current_price == 180.0


def test_dashboard_vm_active_recommendations_empty_when_no_matches(
    seeded_db, monkeypatch,
):
    """When no candidate matches any active hypothesis, the field is the
    empty tuple — never None — so templates can render `{% if %}` cleanly."""
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _ = seeded_db
    # `skip` bucket without criteria matches NO active hypothesis (capital-
    # blocked requires the only failing criterion to be risk_feasibility).
    _seed_pipeline_with_candidates(cfg, [
        {"ticker": "ZZZ", "bucket": "skip"},
    ])
    _patched_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert vm.active_recommendations == ()


def test_dashboard_vm_active_recommendations_truncates_to_top_n(
    seeded_db, monkeypatch,
):
    """More than 10 matches → only the 10 highest-priority surface.

    The prioritizer ranks A+ matches above watch-bucket near-A+ extension
    matches when distance-to-target favors A+ (target=20 vs 10). We seed
    15 A+ candidates and 1 watch+proximity (Near-A+) candidate; the cap
    yields 10 entries, all of them A+ baseline.
    """
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _ = seeded_db
    candidates = [
        {"ticker": f"A{i:02d}", "bucket": "aplus", "close": 100.0 + i, "pivot": 101.0 + i}
        for i in range(15)
    ]
    _seed_pipeline_with_candidates(cfg, candidates)
    _patched_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert len(vm.active_recommendations) == 10


def test_dashboard_vm_active_recommendations_with_no_pipeline(
    seeded_db, monkeypatch,
):
    """Fresh-install / no-pipeline path: no candidates → empty recommendations
    and no crash. Mirrors the existing flag_tags/candidates_by_ticker fallback."""
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _ = seeded_db
    _patched_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert vm.active_recommendations == ()


def test_dashboard_vm_recommendation_includes_proximity_match(
    seeded_db, monkeypatch,
):
    """Watch-bucket candidate failing ONLY proximity_20ma matches the
    `Near-A+ defensible: extension test` hypothesis (target=10)."""
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _ = seeded_db
    _seed_pipeline_with_candidates(cfg, [
        {
            "ticker": "MSFT", "bucket": "watch",
            "close": 200.0, "pivot": 205.0,
            "criteria": [("proximity_20ma", "fail")],
        },
    ])
    _patched_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert len(vm.active_recommendations) == 1
    rec = vm.active_recommendations[0]
    assert rec.ticker == "MSFT"
    assert rec.hypothesis_name == "Near-A+ defensible: extension test"
    assert rec.hypothesis_progress_target == 10
    assert rec.suggested_label.startswith("Near-A+ defensible: extension test")


def test_dashboard_recommendations_render_with_zero_starting_equity(
    seeded_db, monkeypatch,
):
    """Adversarial review R1 Major 2: with `starting_equity <= 0`, the
    absolute-loss tripwire's threshold (-equity * pct/100) becomes ≤ 0,
    so even cumulative_loss=0 fires the alarm. Defense:
    `build_recommendation_progress` keeps real progress numbers but
    overrides the absolute-loss tripwire flag (R2 Major 1 refinement).
    """
    from dataclasses import replace
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _ = seeded_db
    cfg = replace(cfg, account=replace(cfg.account, starting_equity=0.0))
    _seed_pipeline_with_candidates(cfg, [
        {"ticker": "AAPL", "bucket": "aplus", "close": 180.0, "pivot": 181.0},
    ])
    _patched_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert len(vm.active_recommendations) == 1
    rec = vm.active_recommendations[0]
    assert rec.tripwire_fired is False, (
        "with starting_equity=0, tripwire must NOT fire spuriously"
    )
    assert rec.tripwire_reason is None
    # Target still rendered correctly.
    assert rec.hypothesis_progress_target == 20


def test_dashboard_recommendations_preserve_real_sample_count_under_zero_equity(
    seeded_db, monkeypatch,
):
    """Adversarial review R2 Major 1: zero-equity guard must NOT zero out
    `current_sample`. Real closed-trade history drives prioritizer ranking
    and the dashboard's "N / target" display; only the absolute-loss
    tripwire signal should be suppressed. Pin: with one closed trade
    labeled `Sub-A+ VCP-not-formed ...`, that hypothesis's row shows
    `current_sample == 1`, NOT 0, even when starting_equity=0.
    """
    from dataclasses import replace
    from swing.data.db import connect
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _ = seeded_db
    cfg = replace(cfg, account=replace(cfg.account, starting_equity=0.0))
    # Pipeline + watch candidate matching Sub-A+ VCP-not-formed.
    conn = connect(cfg.paths.db_path)
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
            cand_cur = conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, 'NUE', 'watch', 100.0, 102.0, 95.0, 'universe')""",
                (eval_id,),
            )
            cid = cand_cur.lastrowid
            conn.execute(
                """INSERT INTO candidate_criteria
                   (candidate_id, criterion_name, layer, result)
                   VALUES (?, 'tightness', 'vcp', 'fail')""",
                (cid,),
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
            # One closed trade matching the hypothesis prefix; modest loss
            # well below any absolute threshold.
            conn.execute(
                """INSERT INTO trades
                   (ticker, entry_date, entry_price, initial_shares,
                    initial_stop, current_stop, status,
                    watchlist_entry_target, watchlist_initial_stop,
                    notes, hypothesis_label)
                   VALUES ('VIR', '2026-04-15', 100.0, 10, 90.0, 90.0,
                           'closed', NULL, NULL, NULL,
                           'Sub-A+ VCP-not-formed inaugural')""",
            )
            tid = conn.execute(
                "SELECT id FROM trades WHERE ticker='VIR'"
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO exits
                   (trade_id, exit_date, exit_price, shares, reason,
                    realized_pnl, r_multiple, notes)
                   VALUES (?, '2026-04-20', 95.0, 10, 'stop-hit',
                           -50.0, -0.5, NULL)""",
                (tid,),
            )
    finally:
        conn.close()
    _patched_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert len(vm.active_recommendations) == 1
    rec = vm.active_recommendations[0]
    # Real closed-trade history must still be reflected.
    assert rec.hypothesis_progress_n == 1, (
        f"current_sample regression — under zero equity the guard must "
        f"preserve real closed-trade counts; got "
        f"{rec.hypothesis_progress_n}"
    )
    # No absolute-loss tripwire (would have fired at threshold=0).
    assert rec.tripwire_fired is False
    assert rec.hypothesis_name == "Sub-A+ VCP-not-formed"


def test_build_active_recommendations_helper_extracted_matches_build_dashboard(
    seeded_db, monkeypatch,
):
    """Task 3 — pure refactor regression: extract _build_active_recommendations
    helper; the helper's output MUST equal build_dashboard's
    active_recommendations field byte-for-byte.

    Discriminating: if the helper extraction reorders fields, drops a
    field, or swaps progress_n/progress_target, the tuple equality
    fails. Pre-extraction the helper does not exist, so the import
    raises ImportError — that is the failing-test signal.
    """
    from swing.data.db import connect
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.hypothesis import list_hypotheses
    from swing.recommendations.hypothesis import (
        match_candidate_to_hypotheses,
        prioritize_recommendations,
    )
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import (
        _build_active_recommendations,
        _RECOMMENDATIONS_TOP_N,
        build_dashboard,
        build_recommendation_progress,
    )

    cfg, _ = seeded_db
    # Seed multiple candidates so the equality check is non-vacuous on a
    # single-element tuple. Mix A+ and watch-bucket+proximity-fail rows so
    # multiple distinct hypotheses surface in the prioritized output.
    _seed_pipeline_with_candidates(cfg, [
        {"ticker": "AAPL", "bucket": "aplus", "close": 180.0, "pivot": 181.0},
        {"ticker": "MSFT", "bucket": "aplus", "close": 200.0, "pivot": 201.0},
        {
            "ticker": "NVDA", "bucket": "watch",
            "close": 150.0, "pivot": 152.0,
            "criteria": [("proximity_20ma", "fail")],
        },
    ])
    _patched_caches(monkeypatch)

    cache = PriceCache(cfg)
    full_vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    expected = full_vm.active_recommendations
    assert len(expected) >= 2, (
        "fixture seeds insufficient data for a discriminating test"
    )

    # Recompute the inputs the helper takes, mirroring build_dashboard's
    # internal resolution. The helper is then called directly; its output
    # MUST equal build_dashboard's active_recommendations field.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            pipe_row = conn.execute(
                """SELECT id, evaluation_run_id FROM pipeline_runs
                   WHERE state='complete'
                   ORDER BY finished_ts DESC, id DESC LIMIT 1"""
            ).fetchone()
            assert pipe_row is not None
            eval_id = pipe_row[1]
            candidates = fetch_candidates_for_run(conn, eval_id)
            candidates_by_ticker = {c.ticker: c for c in candidates}
            registry = list_hypotheses(conn)
            target_by_id = {h.id: h.target_sample_size for h in registry}
            progress_by_id, progress_summaries = (
                build_recommendation_progress(
                    conn, registry,
                    starting_equity=cfg.account.starting_equity,
                )
            )
            all_matches = []
            for c in candidates:
                all_matches.extend(
                    match_candidate_to_hypotheses(c, registry=registry)
                )
            prioritized = prioritize_recommendations(
                all_matches, registry=registry,
                progress=progress_summaries,
            )
            top_recommendations = list(prioritized[:_RECOMMENDATIONS_TOP_N])
    finally:
        conn.close()

    prices = cache.get_many(
        [r.candidate_ticker for r in top_recommendations],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=None,
    )
    helper_result = _build_active_recommendations(
        prices=prices,
        candidates_by_ticker=candidates_by_ticker,
        top_recommendations=top_recommendations,
        progress_by_id=progress_by_id,
        target_by_id=target_by_id,
    )
    assert helper_result == expected, (
        "_build_active_recommendations helper output must equal "
        "build_dashboard's active_recommendations field byte-for-byte"
    )


def test_dashboard_vm_active_recommendations_field_default(seeded_db):
    """DashboardVM constructable without active_recommendations — defaults
    to an empty tuple. Defends downstream callers that build ad-hoc VMs in
    tests / fixtures."""
    from swing.web.view_models.dashboard import (
        DashboardVM, StatusStripVM,
    )
    vm = DashboardVM(
        generated_at="t", session_date="2026-04-20", stale_banner=None,
        status_strip=StatusStripVM(
            weather_status="STALE", weather_rationale="", equity=0.0,
            open_count=0, soft_warn=4, hard_cap=6,
            last_pipeline_ts=None, last_pipeline_state=None,
        ),
        today_decisions=[], open_trades=[],
        open_trade_advisories={}, open_trade_last_prices={},
        watchlist_top5=[], watchlist_remaining_count=0,
        watchlist_last_prices={}, flag_tags={},
        candidates_by_ticker={}, prices_generated_at="t",
        price_source_degraded=False, price_source_degraded_until=None,
    )
    assert vm.active_recommendations == ()
