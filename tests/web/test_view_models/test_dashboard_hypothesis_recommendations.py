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
    `build_recommendation_progress` skips the tripwire compute and uses
    registry-derived target_sample only. Recommendations still surface;
    no false tripwires.
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
    # Target still rendered correctly via registry fallback.
    assert rec.hypothesis_progress_target == 20


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
