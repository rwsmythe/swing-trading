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


# ---------------------------------------------------------------------------
# Bug-fix-C: build_dashboard's hyp-recs construction must EXCLUDE tickers
# that already have an open position. The just-shipped Task 3 added
# `exclude_tickers` to `build_hyp_recs_section`, consumed by entry_post's
# OOB rebuild path. But `build_dashboard` inlines its own hyp-recs
# construction (independent of `build_hyp_recs_section`) which had no
# exclusion. Net effect operator caught in production (2026-04-29): hard-
# navigating to / after a hyp-recs trade re-rendered the dashboard with
# the just-traded ticker still in the recommendations panel. Codex R1
# Major 1 of the prior dispatch flagged this as ACCEPTED-with-rationale;
# operator-witnessed verification confirmed it as a live production bug.
# ---------------------------------------------------------------------------


def test_dashboard_vm_excludes_open_trade_tickers_from_active_recommendations(
    seeded_db, monkeypatch,
):
    """Bug-fix-C: candidate tickers that already have an OPEN trade must
    NOT appear in `vm.active_recommendations`. The exclusion must apply on
    the FULL dashboard render path (GET /), not just the entry_post OOB
    rebuild path.

    Discriminator: pre-fix, `vm.active_recommendations` contains BOTH
    AAA (open position) and BBB (no open position). Post-fix, only BBB
    is present.

    BBB is the witness candidate — its presence verifies the matcher is
    still firing, so an empty result wouldn't trivially satisfy the
    assertion.
    """
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _ = seeded_db
    _seed_pipeline_with_candidates(cfg, [
        {"ticker": "AAA", "bucket": "aplus", "close": 99.0, "pivot": 100.0,
         "stop": 95.0},
        {"ticker": "BBB", "bucket": "aplus", "close": 99.0, "pivot": 100.0,
         "stop": 95.0},
    ])
    # Open position for AAA — record_entry isn't used here because the
    # service-layer also archives a watchlist row if present, and we don't
    # need that side effect. insert_trade_with_event is the lower-level
    # write that records the trade row + event without touching watchlist.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAA", entry_date="2026-04-15",
                entry_price=98.0, initial_shares=5, initial_stop=93.0,
                current_stop=93.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()
    _patched_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    rec_tickers = {r.ticker for r in vm.active_recommendations}
    assert "BBB" in rec_tickers, (
        "BBB (witness candidate, no open position) must be present — "
        "without it, the exclusion assertion is vacuous (an empty result "
        f"would trivially satisfy it). Got tickers={rec_tickers!r}"
    )
    assert "AAA" not in rec_tickers, (
        "AAA has an open position; build_dashboard's hyp-recs construction "
        "must structurally exclude open-position tickers so the operator "
        "doesn't see the same ticker in BOTH the open-positions table AND "
        f"the recommendations panel. Got tickers={rec_tickers!r}"
    )


def test_hyp_recs_refresh_route_excludes_open_trade_tickers(
    seeded_db, monkeypatch,
):
    """Bug-fix-C: GET /hyp-recs/refresh must also exclude open-position
    tickers from the rendered hyp-recs section. Pre-fix the route called
    `build_hyp_recs_section` without `exclude_tickers`, so the close-
    button refresh re-introduced a just-traded ticker into the panel.

    Discriminator: pre-fix, response body contains `>AAA<` (the ticker
    cell text). Post-fix it does not. BBB (witness) confirms the matcher
    is still firing.
    """
    from fastapi.testclient import TestClient

    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.app import create_app

    cfg, cfg_path = seeded_db
    _seed_pipeline_with_candidates(cfg, [
        {"ticker": "AAA", "bucket": "aplus", "close": 99.0, "pivot": 100.0,
         "stop": 95.0},
        {"ticker": "BBB", "bucket": "aplus", "close": 99.0, "pivot": 100.0,
         "stop": 95.0},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAA", entry_date="2026-04-15",
                entry_price=98.0, initial_shares=5, initial_stop=93.0,
                current_stop=93.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()
    _patched_caches(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/hyp-recs/refresh", headers={"HX-Request": "true"})
    assert r.status_code == 200, f"Got {r.status_code}; body[:500]={r.text[:500]!r}"
    assert ">BBB<" in r.text, (
        "BBB (witness candidate) must appear in the refresh-route render — "
        "otherwise the test is vacuous (empty hyp-recs would trivially "
        f"satisfy the AAA-absence assertion). Body[:1000]={r.text[:1000]!r}"
    )
    assert ">AAA<" not in r.text, (
        "AAA has an open position; /hyp-recs/refresh must thread "
        "`exclude_tickers={t.ticker for t in list_open_trades(conn)}` to "
        "build_hyp_recs_section. Without it, the close-button refresh "
        "re-introduces just-traded tickers into the panel. "
        f"Body[:1000]={r.text[:1000]!r}"
    )


def test_dashboard_recommendation_exposes_in_flight_count(seeded_db, monkeypatch):
    """Per-hypothesis in-flight count surfaces on each HypothesisRecommendation
    so the dashboard can render '1/5 closed (+2 in flight)' style decoration.

    Discriminator: candidate FOO matches Sub-A+ VCP-not-formed (watch +
    tightness fail). Two OPEN trades with prefix-matching labels exist for
    DHC + CC (DIFFERENT tickers from FOO so they aren't structurally
    excluded by Bug-fix-C). The recommendation row for FOO must report
    hypothesis_in_flight_n=2. With the new field unwired, the value would
    be 0 (default).
    """
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _ = seeded_db
    _seed_pipeline_with_candidates(cfg, [
        {"ticker": "FOO", "bucket": "watch", "close": 99.0, "pivot": 100.0,
         "stop": 95.0,
         "criteria": [("tightness", "fail")]},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="DHC", entry_date="2026-04-27",
                entry_price=7.58, initial_shares=39, initial_stop=7.00,
                current_stop=7.00, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                hypothesis_label=(
                    "sub-A+ VCP-not-formed test (proximity_20ma + tightness fails)"
                ),
            ), event_ts="2026-04-27T09:30:00")
            insert_trade_with_event(conn, Trade(
                id=None, ticker="CC", entry_date="2026-04-30",
                entry_price=26.97, initial_shares=5, initial_stop=24.00,
                current_stop=24.00, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                hypothesis_label=(
                    "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness"
                ),
            ), event_ts="2026-04-30T09:30:00")
    finally:
        conn.close()
    _patched_caches(monkeypatch)

    cache = PriceCache(cfg)
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    foo = next(
        (r for r in vm.active_recommendations if r.ticker == "FOO"), None,
    )
    assert foo is not None, (
        "FOO (witness candidate, no open position) must surface in "
        "active_recommendations — without it, the in-flight assertion is "
        f"vacuous. Got tickers={[r.ticker for r in vm.active_recommendations]!r}"
    )
    assert foo.hypothesis_name == "Sub-A+ VCP-not-formed", (
        f"FOO should match Sub-A+ VCP-not-formed; got {foo.hypothesis_name!r}"
    )
    assert foo.hypothesis_progress_n == 0, (
        f"closed-trade count is 0 (no closed trades seeded); "
        f"got {foo.hypothesis_progress_n}"
    )
    assert foo.hypothesis_in_flight_n == 2, (
        "DHC + CC are both open with prefix-matching labels; in-flight "
        f"must report 2. Got {foo.hypothesis_in_flight_n}. If this is 0, "
        "_build_active_recommendations did not plumb in_flight_sample from "
        "progress_by_id; if this is the wrong count, the journal-stats "
        "compute fn is not counting open-prefix-matchers correctly."
    )
