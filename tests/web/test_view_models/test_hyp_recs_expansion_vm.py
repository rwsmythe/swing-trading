"""Task 5.2 — `HypRecsExpandedVM` + `build_hyp_recs_expanded` helper.
Plus Task 2.1 — apply_overrides chase_factor reaches buy_limit (override path).

Spec §3.5.2 + §3.5.3. The helper resolves a per-ticker hyp-recs expansion VM:
candidate (pivot, stop, sector/industry) from the latest COMPLETED pipeline
run's evaluation, the chase-factor-based buy_limit, sizing twins (risk-floor
vs cash), and chart-scope reason. Returns None on (no completed pipeline
run) ∪ (ticker not in latest run's candidates) ∪ (candidate.pivot None) ∪
(degenerate sizing — `compute_shares` raises ValueError).

The 9 tests below pin the contract per the writing-plans Task 5.2 critical
sub-task contract — happy path, buy_limit arithmetic, chase_factor
threading, ticker-not-in-run None, no-completed-pipeline-run None, anchor
consistency (in-flight run with NULL finished_ts MUST NOT win), degenerate
stop None, sector/industry threading + empty-string coercion, and sizing
twins discriminating when balance < floor.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from swing.data.db import connect


def _seed_complete_pipeline(
    cfg, *, candidates: list[dict[str, Any]],
    finished_ts: str = "2026-04-29T16:00:00",
    data_asof_date: str = "2026-04-28",
    action_session_date: str = "2026-04-29",
    started_ts: str = "2026-04-29T15:50:00",
    charts_status: str = "ok",
) -> int:
    """Seed one COMPLETED pipeline_run + linked evaluation_run + candidates.

    Returns the pipeline run id. Each candidate dict supports keys: ticker,
    bucket (default 'aplus'), pivot (default 100.0), initial_stop (default
    95.0), close, sector, industry.
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
                   VALUES (?, ?, ?, NULL, ?, ?, 0, 0, 0, 0, 'v1', 'h1')""",
                (started_ts, data_asof_date, action_session_date,
                 len(candidates), len(candidates)),
            )
            eval_id = cur.lastrowid
            for c in candidates:
                conn.execute(
                    """INSERT INTO candidates
                       (evaluation_run_id, ticker, bucket, close, pivot,
                        initial_stop, rs_method, sector, industry)
                       VALUES (?, ?, ?, ?, ?, ?, 'universe', ?, ?)""",
                    (eval_id, c["ticker"], c.get("bucket", "aplus"),
                     c.get("close", 99.0), c.get("pivot", 100.0),
                     c.get("initial_stop", 95.0),
                     c.get("sector", "Technology"),
                     c.get("industry", "Semiconductors")),
                )
            cur2 = conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id, charts_status)
                   VALUES (?, ?, 'scheduled', ?, ?, 'complete', 'tok', ?, ?)""",
                (started_ts, finished_ts, data_asof_date,
                 action_session_date, eval_id, charts_status),
            )
            return int(cur2.lastrowid)
    finally:
        conn.close()


def _seed_inflight_pipeline(
    cfg, *, candidates: list[dict[str, Any]],
    started_ts: str,
    data_asof_date: str,
    action_session_date: str,
) -> int:
    """Seed an IN-FLIGHT pipeline_run (state='running', finished_ts NULL)
    with its OWN evaluation_run + candidate set. Used by the anchor-
    consistency test to verify the helper picks the COMPLETED run, not
    the newer in-flight one (its finished_ts IS NULL).
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
                   VALUES (?, ?, ?, NULL, ?, ?, 0, 0, 0, 0, 'v1', 'h1')""",
                (started_ts, data_asof_date, action_session_date,
                 len(candidates), len(candidates)),
            )
            eval_id = cur.lastrowid
            for c in candidates:
                conn.execute(
                    """INSERT INTO candidates
                       (evaluation_run_id, ticker, bucket, close, pivot,
                        initial_stop, rs_method, sector, industry)
                       VALUES (?, ?, ?, ?, ?, ?, 'universe', ?, ?)""",
                    (eval_id, c["ticker"], c.get("bucket", "aplus"),
                     c.get("close", 99.0), c.get("pivot", 100.0),
                     c.get("initial_stop", 95.0),
                     c.get("sector", "Technology"),
                     c.get("industry", "Semiconductors")),
                )
            cur2 = conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id, charts_status)
                   VALUES (?, NULL, 'manual', ?, ?, 'running', 'tok-2', ?, NULL)""",
                (started_ts, data_asof_date, action_session_date, eval_id),
            )
            return int(cur2.lastrowid)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 1 — happy path: fully populated candidate produces a complete VM.
# ---------------------------------------------------------------------------
def test_happy_path_full_vm(seeded_db):
    from swing.recommendations.sizing import SizingResult
    from swing.web.view_models.dashboard import (
        HypRecsExpandedVM, build_hyp_recs_expanded,
    )

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 200.0, "initial_stop": 190.0,
         "sector": "Technology", "industry": "Consumer Electronics"},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert isinstance(vm, HypRecsExpandedVM)
    assert vm.ticker == "AAPL"
    assert vm.buy_stop == 200.0
    assert vm.sell_stop == 190.0
    assert vm.chase_factor == cfg.web.chase_factor
    assert vm.current_balance == 10_000.0
    assert isinstance(vm.sizing_risk, SizingResult)
    assert isinstance(vm.sizing_cash, SizingResult)
    assert vm.sector == "Technology"
    assert vm.industry == "Consumer Electronics"
    assert vm.data_asof_date == "2026-04-28"
    assert vm.pipeline_finished_at == "2026-04-29T16:00:00"
    # chart_reason is None (in-scope) ONLY if the helper threads
    # resolve_chart_scope through. With charts_status='ok' and no
    # pipeline_chart_targets row, FK-backed path returns 'out-of-scope'.
    # The point is the field is wired (string or None) — message follows.
    if vm.chart_reason is None:
        assert vm.chart_reason_message is None
    else:
        assert vm.chart_reason_message is not None


# ---------------------------------------------------------------------------
# Test 2 — buy_limit arithmetic: pivot × (1 + chase_factor).
# ---------------------------------------------------------------------------
def test_buy_limit_arithmetic(seeded_db):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    # Default chase_factor is 0.01. pivot=100.0 → buy_limit=101.0.
    assert cfg.web.chase_factor == 0.01
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 95.0},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert vm is not None
    assert vm.buy_stop == 100.0
    # buy_limit = 100.0 × (1 + 0.01) = 101.0 (exact float arithmetic).
    assert vm.buy_limit == 101.0


# ---------------------------------------------------------------------------
# Test 3 — chase_factor threading from config.
# ---------------------------------------------------------------------------
def test_chase_factor_threading_from_config(seeded_db):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    cfg = replace(cfg, web=replace(cfg.web, chase_factor=0.02))
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 95.0},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert vm is not None
    assert vm.chase_factor == 0.02
    # buy_limit = 100.0 × 1.02 = 102.0; this discriminates against a
    # hardcoded 0.01 (which would yield 101.0).
    assert vm.buy_limit == 102.0


# ---------------------------------------------------------------------------
# Test 4 — ticker not in latest run's candidates: helper returns None.
# ---------------------------------------------------------------------------
def test_ticker_not_in_latest_run_returns_none(seeded_db):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 95.0},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        # Ask for ticker B (MSFT) — only A (AAPL) was seeded.
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="MSFT", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert vm is None


# ---------------------------------------------------------------------------
# Test 5 — no completed pipeline run at all: helper returns None.
# ---------------------------------------------------------------------------
def test_no_completed_pipeline_run_returns_none(seeded_db):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    # Don't seed anything — fresh schema only.
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert vm is None


# ---------------------------------------------------------------------------
# Test 6 — anchor consistency: completed run with DIFFERENT pivot for the
# same ticker MUST win over a newer in-flight run (finished_ts IS NULL).
# Discriminating: assert vm.buy_stop matches the COMPLETED run's pivot.
# ---------------------------------------------------------------------------
def test_anchor_consistency_completed_run_wins_over_inflight(seeded_db):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    # Older COMPLETED run — pivot=100.0.
    _seed_complete_pipeline(
        cfg,
        candidates=[
            {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 95.0},
        ],
        finished_ts="2026-04-28T16:00:00",
        started_ts="2026-04-28T15:50:00",
        data_asof_date="2026-04-27",
        action_session_date="2026-04-28",
    )
    # Newer IN-FLIGHT run (finished_ts IS NULL, state='running') — pivot=999.0.
    _seed_inflight_pipeline(
        cfg,
        candidates=[
            {"ticker": "AAPL", "pivot": 999.0, "initial_stop": 950.0},
        ],
        started_ts="2026-04-29T09:00:00",
        data_asof_date="2026-04-28",
        action_session_date="2026-04-29",
    )

    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert vm is not None
    # Discriminating: COMPLETED-run pivot (100.0), NOT in-flight pivot (999.0).
    assert vm.buy_stop == 100.0, (
        f"helper must bind to COMPLETED run; got buy_stop={vm.buy_stop} "
        f"(in-flight pivot was 999.0, completed pivot was 100.0)"
    )
    assert vm.sell_stop == 95.0
    assert vm.pipeline_finished_at == "2026-04-28T16:00:00"


# ---------------------------------------------------------------------------
# Test 7 — degenerate stop (stop >= pivot) → compute_shares raises
# ValueError → helper catches and returns None.
# ---------------------------------------------------------------------------
def test_degenerate_stop_returns_none(seeded_db):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    # initial_stop >= pivot triggers compute_shares' precondition guard.
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 100.0},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert vm is None


# ---------------------------------------------------------------------------
# Test 8 — sector/industry threading + empty-string coercion path.
#
# Two candidates: one with populated values (must pass through verbatim);
# one with empty strings (must surface as "" — the `candidate.sector or ""`
# branch fires identically for None and ""; the schema enforces NOT NULL on
# both columns post-migration-0012 so empty-string IS the realistic NULL-
# equivalent path on disk).
# ---------------------------------------------------------------------------
def test_sector_industry_threading_with_empty_coercion(seeded_db):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 95.0,
         "sector": "Technology", "industry": "Semiconductors"},
        {"ticker": "EMPTYCO", "pivot": 100.0, "initial_stop": 95.0,
         "sector": "", "industry": ""},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        vm_pop = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
        )
        vm_empty = build_hyp_recs_expanded(
            conn, cfg, ticker="EMPTYCO", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert vm_pop is not None
    assert vm_pop.sector == "Technology"
    assert vm_pop.industry == "Semiconductors"
    assert vm_empty is not None
    # Empty-string sector/industry — per spec §3.5.3, helper coerces via
    # `candidate.sector or ""` so the field stays "" (not None).
    assert vm_empty.sector == ""
    assert vm_empty.industry == ""


# ---------------------------------------------------------------------------
# Test 9 — sizing twins discriminate: current_balance < floor →
# vm.sizing_risk.shares > vm.sizing_cash.shares strictly.
# ---------------------------------------------------------------------------
def test_sizing_twins_discriminate_below_floor(seeded_db):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    # cfg.account.risk_equity_floor = 7500.0 from _minimal_config.
    # Use the same inputs as the Task 5.1 sizing-twin pair: pivot=$25,
    # stop=$24.50 → discriminating shares 45 (risk@floor) vs 7 (cash).
    cfg = replace(cfg, risk=replace(cfg.risk, max_risk_pct=0.005))
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 25.0, "initial_stop": 24.50},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=1200.0,
        )
    finally:
        conn.close()

    assert vm is not None
    assert vm.current_balance == 1200.0
    assert vm.risk_equity == 7500.0  # floor wins (1200 < 7500).
    # Sizing twins must DIVERGE strictly — the core hyp-recs contract.
    assert vm.sizing_risk.shares > vm.sizing_cash.shares
    # Pin the actual numerics (matches Task 5.1 hand-derivation).
    assert vm.sizing_risk.shares == 45
    assert vm.sizing_cash.shares == 7


# ---------------------------------------------------------------------------
# Test 10 — Codex R2 Major-1: candidate.initial_stop IS NULL must return
# None, NOT raise TypeError.
#
# Discriminating: pre-fix path threads `stop=None` into compute_shares,
# whose `if stop >= entry:` precondition raises TypeError comparing
# NoneType to float (the surrounding `try/except ValueError` does NOT
# catch TypeError). Post-fix: helper returns None on the upfront guard.
# ---------------------------------------------------------------------------
def test_initial_stop_none_returns_none(seeded_db):
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    # Schema (migration 0001) declares candidates.initial_stop as REAL
    # without NOT NULL — NULL is a realistic value on disk for a
    # degenerate evaluator output that produced a pivot but no stop.
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": None},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        # Must return None cleanly — no TypeError leak from compute_shares.
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert vm is None


# ---------------------------------------------------------------------------
# Task 2.1 — apply_overrides chase_factor override threads through to
# build_hyp_recs_expanded.buy_limit.
#
# This is the unit-level safety harness for the route-level wiring change:
# every web route now reads `cfg = apply_overrides(request.app.state.cfg)`.
# We prove the discriminator (chase_factor 0.01 → 0.025 yields buy_limit
# 101.0 → 102.5 for pivot=100) at the VM layer that the routes call into.
# Pre-fix path: route reads raw state.cfg → buy_limit = 100*(1+0.01) = 101.0.
# Post-fix path: route reads apply_overrides(state.cfg) → 100*(1+0.025) = 102.5.
# This test exercises the post-fix code path directly via apply_overrides().
# ---------------------------------------------------------------------------
def test_apply_overrides_chase_factor_propagates_to_buy_limit(
    seeded_db, tmp_path, monkeypatch,
):
    import pytest
    from swing.config_overrides import apply_overrides
    from swing.config_user import write_user_overrides
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    # Isolate USERPROFILE/HOME to the test's tmp_path/home — the seeded_db
    # fixture already created this directory via _minimal_config().
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    # Sanity: base cfg defaults to chase_factor=0.01 (101.0 buy_limit).
    assert cfg.web.chase_factor == 0.01

    # Write a user-config override for chase_factor=0.025.
    write_user_overrides({"web": {"chase_factor": 0.025}})

    # Apply overrides (mirroring the route-level wiring change).
    effective_cfg = apply_overrides(cfg)
    assert effective_cfg.web.chase_factor == 0.025

    _seed_complete_pipeline(effective_cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 95.0},
    ])
    conn = connect(effective_cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, effective_cfg, ticker="AAPL", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert vm is not None
    # Discriminating: pre-wiring (raw cfg) yields buy_limit=101.0;
    # post-wiring (apply_overrides) yields buy_limit=102.5.
    # pytest.approx absorbs IEEE-754 float-rep noise (1.025 isn't exact).
    assert vm.chase_factor == 0.025
    assert vm.buy_limit == pytest.approx(102.5)
    # Also explicitly distinguish from the no-override default (101.0).
    assert vm.buy_limit != pytest.approx(101.0)


# ---------------------------------------------------------------------------
# 3e.4 Task A.1 — `HypRecsExpandedVM.current_price` field + builder
# cache+executor parameters. The field defaults to None for backward-compat
# with callers that don't pass a cache; the builder accepts optional
# `cache=` and `executor=` kwargs; when BOTH are provided, the builder
# fetches via `cache.get_many([ticker], deadline_seconds=..., executor=...)`
# (Codex R1 Major #1+#2: deadline-bounded batch path, NOT the unbounded
# single-ticker `get`) and populates the field. Acceptance criteria
# A.AC.1 + A.AC.2.
# ---------------------------------------------------------------------------
def test_hyp_recs_expanded_vm_has_current_price_field_default_none(seeded_db):
    """A.AC.1 — `HypRecsExpandedVM.current_price` exists and defaults to
    None when constructed without an explicit value. Discriminating: the
    field is accessible and defaults to None even though every existing
    constructor call site omits it."""
    from swing.recommendations.sizing import SizingResult
    from swing.web.view_models.dashboard import HypRecsExpandedVM

    vm = HypRecsExpandedVM(
        ticker="AAPL",
        buy_stop=100.0,
        buy_limit=101.0,
        sell_stop=95.0,
        chase_factor=0.01,
        current_balance=10_000.0,
        risk_equity=10_000.0,
        sizing_risk=SizingResult(
            shares=0, risk_dollars=0.0, risk_pct=0.0,
            notional=0.0, notional_pct=0.0,
            feasible=False, constraint="x"),
        sizing_cash=SizingResult(
            shares=0, risk_dollars=0.0, risk_pct=0.0,
            notional=0.0, notional_pct=0.0,
            feasible=False, constraint="x"),
        sector="S", industry="I",
        data_asof_date=None, chart_reason=None, chart_reason_message=None,
        pipeline_finished_at=None,
    )
    # Field exists and is None by default.
    assert vm.current_price is None


def test_build_hyp_recs_expanded_populates_current_price_when_cache_provided(
    seeded_db,
):
    """A.AC.2 — when builder is called with `cache=<PriceCache-like>` AND
    `executor=<Executor-like>`, the returned VM has `current_price` populated
    with the snapshot the cache returned for the ticker via the batch
    `get_many([ticker], deadline_seconds=, executor=)` path. Brief §0.3 #4
    PriceCache+executor pattern. Discriminating: a stub cache returning
    PriceSnapshot(price=123.45) propagates verbatim to VM.current_price.price.
    """
    from datetime import datetime

    from swing.web.price_cache import PriceSnapshot
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 95.0},
    ])

    class _StubCache:
        def __init__(self):
            self.calls: list = []

        def get_many(self, tickers, *, deadline_seconds, executor):
            self.calls.append(
                (list(tickers), deadline_seconds, executor),
            )
            return {
                t: PriceSnapshot(
                    ticker=t, price=123.45, asof=datetime.now(),
                    is_stale=False, source="live",
                ) for t in tickers
            }

    stub = _StubCache()
    sentinel_executor = object()
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
            cache=stub, executor=sentinel_executor,
        )
    finally:
        conn.close()

    assert vm is not None
    assert len(stub.calls) == 1, (
        f"builder must invoke get_many exactly once; got {stub.calls}"
    )
    tickers_called, deadline_called, executor_called = stub.calls[0]
    assert tickers_called == ["AAPL"], (
        f"builder must call get_many with a 1-element list; got {tickers_called}"
    )
    # Deadline-bounded contract: builder must pass the configured deadline
    # (mirrors the open-positions dashboard path).
    assert deadline_called == cfg.web.price_fetch_deadline_seconds, (
        f"builder must thread cfg.web.price_fetch_deadline_seconds; "
        f"got {deadline_called}"
    )
    # Executor passthrough (locked in brief §0.3 #4 + A.AC.2).
    assert executor_called is sentinel_executor, (
        "builder must forward the executor kwarg into get_many verbatim"
    )
    assert vm.current_price is not None
    assert vm.current_price.price == 123.45
    assert vm.current_price.is_stale is False
    assert vm.current_price.source == "live"


def test_build_hyp_recs_expanded_leaves_current_price_none_without_cache(
    seeded_db,
):
    """A.AC.1 + A.AC.2 — when builder is called WITHOUT the cache kwarg
    (cache defaults to None), the returned VM has `current_price = None`.
    Discriminating: existing call sites pass nothing and must remain
    backward-compat — no AttributeError, no network call, no live fetch."""
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 95.0},
    ])
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
        )
    finally:
        conn.close()

    assert vm is not None
    assert vm.current_price is None


def test_build_hyp_recs_expanded_current_price_none_when_cache_returns_empty(
    seeded_db,
):
    """A.AC.6 (VM-level) — when get_many returns an empty dict (e.g., the
    deadline elapsed or the breaker is degraded with no last_close row),
    the VM has `current_price = None`. Discriminating: a stub cache
    returning `{}` propagates as None, NOT as an exception, NOT as a sentinel.
    """
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 95.0},
    ])

    class _EmptyCache:
        def get_many(self, tickers, *, deadline_seconds, executor):
            return {}

    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
            cache=_EmptyCache(), executor=object(),
        )
    finally:
        conn.close()

    assert vm is not None
    assert vm.current_price is None


def test_build_hyp_recs_expanded_skips_fetch_when_executor_missing(
    seeded_db,
):
    """A.AC.2 (caller contract) — when cache is provided but executor is
    missing (e.g., unit tests exercising other code paths), the builder
    skips the live fetch and returns VM with `current_price = None`.
    Discriminating: a stub cache whose `get_many` would explode is NEVER
    invoked — the builder's guard short-circuits before calling it."""
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    _seed_complete_pipeline(cfg, candidates=[
        {"ticker": "AAPL", "pivot": 100.0, "initial_stop": 95.0},
    ])

    class _ExplodingCache:
        def get_many(self, *args, **kwargs):
            raise AssertionError(
                "get_many must NOT be called when executor is missing"
            )

    conn = connect(cfg.paths.db_path)
    try:
        vm = build_hyp_recs_expanded(
            conn, cfg, ticker="AAPL", current_balance=10_000.0,
            cache=_ExplodingCache(),  # executor=None (default)
        )
    finally:
        conn.close()

    assert vm is not None
    assert vm.current_price is None
