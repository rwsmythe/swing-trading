"""DashboardVM + builder."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Candidate, Trade, WatchlistEntry, WeatherRun
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.cash import list_cash
from swing.data.repos.fills import list_all_fills
from swing.data.repos.pattern_classifications import (
    list_classifications_for_run,
)
from swing.data.repos.recommendations import list_for_session
from swing.data.repos.trades import list_closed_trades, list_open_trades
from swing.data.repos.watchlist import list_active_watchlist
from swing.data.repos.weather import get_latest
from swing.evaluation.dates import action_session_for_run
from swing.journal.stats import HypothesisProgress
from swing.recommendations.sizing import SizingResult, compute_shares
from swing.trades.advisory import AdvisoryContext, compute_all_suggestions
from swing.trades.equity import current_equity, sizing_equity, total_current_risk
from swing.web.chart_scope import (
    latest_completed_pipeline_run,
    resolve_chart_scope,
)
from swing.web.price_cache import PriceCache, PriceSnapshot


@dataclass(frozen=True)
class _ExitShape:
    """Local adapter mirroring legacy Exit shape for ExitLike-consuming
    APIs (current_equity, total_current_risk, dashboard remaining-shares
    grouping). Mirrors swing/web/view_models/trades.py's _ExitShape — both
    die in C.10 when equity.py refactors to consume fills directly. Single
    source of math truth: swing.trades.derived_metrics.
    """
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None


def _list_all_exitshape_via_fills(conn) -> list[_ExitShape]:
    """C.9 migration helper: produces the ExitLike collection that
    ``list_all_exits(conn)`` previously returned, but sourced from
    ``fills`` filtered to non-entry actions. Per-fill realized_pnl + r
    derive on the fly from the parent trade's entry_price/initial_stop
    via ``swing.trades.derived_metrics`` — single source of math truth.
    Sort matches the legacy shim: (fill_datetime ASC, fill_id ASC) by
    way of ``list_all_fills``'s ORDER BY.
    """
    from swing.trades.derived_metrics import (
        initial_risk_per_share,
        r_multiple,
        realized_pnl,
    )

    trades_by_id: dict[int, Trade] = {}
    for t in list_open_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t
    for t in list_closed_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t

    out: list[_ExitShape] = []
    for f in list_all_fills(conn):
        if f.action == "entry":
            continue
        trade = trades_by_id.get(f.trade_id)
        if trade is None:
            continue  # orphan fill — skip (parent trade missing)
        rps = initial_risk_per_share(
            entry_price=trade.entry_price, initial_stop=trade.initial_stop,
        )
        pnl = realized_pnl(
            entry_price=trade.entry_price, exit_price=f.price,
            quantity=f.quantity,
        )
        rmult: float | None
        if rps == 0 or f.quantity == 0:
            rmult = None
        else:
            rmult = r_multiple(
                realized_pnl=pnl, initial_risk_per_share=rps,
                quantity=f.quantity,
            )
        exit_date = (
            f.fill_datetime.split("T")[0]
            if "T" in f.fill_datetime else f.fill_datetime
        )
        out.append(_ExitShape(
            trade_id=f.trade_id,
            exit_date=exit_date,
            exit_price=float(f.price),
            shares=int(f.quantity),
            reason=f.reason,
            realized_pnl=pnl,
            r_multiple=rmult,
        ))
    return out


@dataclass(frozen=True)
class StatusStripVM:
    weather_status: str       # "Bullish" | "Caution" | "Bearish" | "STALE"
    weather_rationale: str
    equity: float
    open_count: int
    soft_warn: int
    hard_cap: int
    last_pipeline_ts: str | None
    last_pipeline_state: str | None
    # Open-risk tile (Tranche B-ops spec §2). Denominator is realized equity
    # (matches entry-form sizing-hint convention); None when equity ≤ 0.
    open_risk_dollars: float = 0.0
    open_risk_pct: float | None = 0.0
    open_risk_position_count: int = 0
    open_risk_all_above_breakeven: bool = False
    # Mark-to-market unrealized P&L (3e.1). None when no priced positions
    # exist (template hides the line entirely). `unrealized_priced_count`
    # tracks how many open trades had a price snapshot at compute time;
    # template renders "(N of M priced)" suffix when this is < open_count.
    unrealized_pnl: float | None = None
    unrealized_priced_count: int = 0


@dataclass(frozen=True)
class DecisionVM:
    ticker: str
    action_text: str
    narrative: str | None


@dataclass(frozen=True)
class AdvisorySuggestionVM:
    rule: str
    message: str   # matches Phase 2 AdvisorySuggestion.message — do not rename


def latest_evaluation_run_id(conn) -> int | None:
    """Return the evaluation_run id the dashboard binds candidates to.

    Two-step selection:
      1. Most recent COMPLETE pipeline_run's `evaluation_run_id` when
         non-NULL — the canonical "this is what the operator's UI is
         showing right now" anchor.
      2. Fallback: most recent `evaluation_runs` row by `run_ts` — legacy
         pipeline rows with NULL FK + fresh installs that have run
         standalone `swing eval` but no pipeline yet.

    Pinned in one helper so the dashboard recommendations panel and the
    CLI `swing trade entry --hypothesis` pre-fill agree on which run they
    consult. Cross-surface drift is the trap adversarial review R1 caught:
    if the dashboard surfaces a recommendation from a standalone eval
    while the CLI only looks at pipeline-bound evals, the operator's
    pre-fill silently disagrees with what they were just shown.
    """
    # `id DESC` is the deterministic tiebreaker on both branches: tied
    # `finished_ts` (pipeline) or tied `run_ts` (fallback) would otherwise
    # leave SQLite's ordering unspecified, and downstream surfaces inherit
    # the non-determinism (Codex R1 M2 + R2 Major 1).
    pipeline_eval_row = conn.execute(
        """SELECT evaluation_run_id FROM pipeline_runs
           WHERE state = 'complete'
           ORDER BY finished_ts DESC, id DESC LIMIT 1"""
    ).fetchone()
    pipeline_eval_id = (
        pipeline_eval_row[0] if pipeline_eval_row else None
    )
    if pipeline_eval_id is not None:
        return pipeline_eval_id
    fallback = conn.execute(
        "SELECT id FROM evaluation_runs ORDER BY run_ts DESC, id DESC LIMIT 1"
    ).fetchone()
    return fallback[0] if fallback else None


def build_recommendation_progress(
    conn, registry, *, starting_equity: float,
):
    """Return `(progress_by_id, progress_summaries)` for the recommendation
    surfaces. Used by both the dashboard panel build path and the CLI
    pre-fill helper so they apply the same equity-guard discipline.

    Adversarial review R1 Major 2 + R2 Major 1: `compute_tripwire_status`
    derives the absolute-loss threshold as `-starting_equity * pct / 100`.
    With `starting_equity <= 0` the threshold is ≤ 0 and even a
    cumulative_loss of 0 trips the absolute-loss alarm — making every
    hypothesis appear FIRED with no closed trades.

    Defense (R2 fix): always compute progress against a POSITIVE sentinel
    so `current_sample`, mean R, win rate, and the consecutive-loss
    streak (which don't depend on equity) remain real and drive
    prioritization correctly. Then in the degenerate branch, override
    `absolute_tripwire_fired = False` (the only field whose value depends
    on the absent equity baseline) and recompute `tripwire_fired` as
    `consecutive_tripwire_fired` alone. The prior R1 fix zeroed
    `current_sample` and changed the prioritizer's ranking; the R2 fix
    suppresses ONLY the absolute-loss signal, leaving every other
    behavior intact.
    """
    from dataclasses import replace

    from swing.journal.stats import compute_hypothesis_progress_breakdown
    from swing.recommendations.hypothesis import HypothesisProgressSummary

    # Sentinel keeps the absolute-loss threshold computation finite under
    # degenerate config; we override the resulting field below regardless.
    threshold_equity = starting_equity if starting_equity > 0 else 1.0
    progress_rows = compute_hypothesis_progress_breakdown(
        conn, starting_equity=threshold_equity,
    )
    if starting_equity <= 0:
        progress_rows = [
            replace(
                p,
                absolute_tripwire_fired=False,
                tripwire_fired=p.consecutive_tripwire_fired,
            )
            for p in progress_rows
        ]
    progress_by_id = {p.hypothesis_id: p for p in progress_rows}
    progress_summaries = [
        HypothesisProgressSummary(
            hypothesis_id=p.hypothesis_id,
            hypothesis_name=p.name,
            current_sample=p.current_sample,
            target_sample=p.target_sample,
            any_tripwire_fired=p.tripwire_fired,
        ) for p in progress_rows
    ]
    return progress_by_id, progress_summaries


@dataclass(frozen=True)
class HypothesisRecommendation:
    """One row of the dashboard's "Hypothesis-driven recommendations" panel.

    Display VM derived from `CandidateRecommendation` plus per-hypothesis
    progress + the live/cached price snapshot for the candidate ticker.
    `suggested_label` is passed through unchanged from the matcher so the
    canonical hypothesis-name prefix (case-insensitive — Session 1 R1 fix)
    is preserved when this string is used to pre-fill `swing trade entry
    --hypothesis`. If the prefix were stripped or rewritten, downstream
    tripwire/progress aggregation would silently fail to attribute the
    trade to its hypothesis.

    `tripwire_reason` is None when no tripwire is fired; otherwise it
    describes the firing condition(s) (consecutive -1R streak, absolute
    cumulative loss) so the operator sees why the alarm raised.
    """
    ticker: str
    current_price: float | None
    hypothesis_id: int
    hypothesis_name: str
    hypothesis_progress_n: int
    hypothesis_progress_target: int
    tripwire_fired: bool
    tripwire_reason: str | None
    suggested_label: str
    # `pivot_price` is APPENDED with a default rather than inserted between
    # current_price and hypothesis_id so positional callers (current or
    # future) cannot silently shift later fields. Template renders fields
    # by name so on-screen column order is independent of dataclass order.
    # (Adversarial review R1 Major 1.)
    pivot_price: float | None = None
    # Display-only count of OPEN trades whose hypothesis_label prefix-matches
    # this hypothesis. Sourced from `HypothesisProgress.in_flight_sample`
    # (closed-vs-open distinction lives in journal-stats compute fn). Default
    # 0 preserves any hand-constructed test sites that omit the kwarg.
    hypothesis_in_flight_n: int = 0


# Top-N cap for the dashboard recommendations panel. Pinned as a module
# constant (not config) so the rendering surface remains predictable; if
# the operator wants more, the section is paginated by the prioritizer's
# stable ordering and they can pull the rest from the journal-progress
# section.
_RECOMMENDATIONS_TOP_N = 10


@dataclass(frozen=True)
class CadenceCardVM:
    """Display VM for one cadence-type review card (daily/weekly/monthly).

    Phase 6 Task 13: consumed by partials/cadence_cards.html.j2.
    `is_pending` is True when completed_date is None (pre-created but not
    yet completed). `scheduled_date` is always populated (set at
    insert_pre_create time); `completed_date` is None until the operator
    runs `swing review complete`.
    """
    cadence_type: str        # 'daily' | 'weekly' | 'monthly'
    scheduled_date: str
    completed_date: str | None
    period_start: str
    period_end: str
    is_pending: bool
    review_id: int           # Task E.3: target for inline /reviews/{id}/complete link


@dataclass(frozen=True)
class DashboardVM:
    generated_at: str
    session_date: str
    stale_banner: str | None
    status_strip: StatusStripVM
    today_decisions: list[DecisionVM]
    open_trades: list[Trade]
    open_trade_advisories: Mapping[int, list[AdvisorySuggestionVM]]
    open_trade_last_prices: Mapping[str, PriceSnapshot]
    watchlist_top5: list[WatchlistEntry]
    watchlist_remaining_count: int
    watchlist_last_prices: Mapping[str, PriceSnapshot]
    flag_tags: Mapping[str, tuple[str, ...]]
    candidates_by_ticker: Mapping[str, Candidate]
    prices_generated_at: str
    price_source_degraded: bool
    price_source_degraded_until: str | None
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)
    # Additive field — populated by Task 6 refactor. Default preserves backward
    # compat for any caller that constructs DashboardVM without this argument.
    open_trade_rows: Mapping[int, object] = field(default_factory=dict)
    # Frontend brief §4.1 — top-N hypothesis-driven recommendations sourced
    # from the Session 1 matcher + prioritizer. Default empty tuple so any
    # ad-hoc VM construction (tests, fixtures) doesn't trip the template's
    # `{% if vm.active_recommendations %}` guard.
    active_recommendations: tuple[HypothesisRecommendation, ...] = ()
    # Spec §3.5 (Phase 4 Task 4.2): SIBLING to flag_tags. {ticker: 'flag (0.78)'}
    # for chart-scope tickers with detected flag patterns. Default empty dict so
    # the dashboard renders gracefully when no classifications are loaded.
    # base.html.j2 was empirically verified at Phase 4 to NOT reference
    # `pattern_tags` (zero matches), so the field stays scoped to the two
    # consuming VMs (DashboardVM + WatchlistVM) — other base-layout VMs
    # (PipelineVM, JournalVM, PageErrorVM) need not propagate.
    pattern_tags: Mapping[str, str] = field(default_factory=dict)
    # Phase 6 Task 13: needs-review badge + cadence cards.
    # Default 0 / None so any ad-hoc VM construction (tests, fixtures outside
    # the phase-6 test files) remains valid without supplying these fields.
    needs_review_count: int = 0
    daily_card: CadenceCardVM | None = None
    weekly_card: CadenceCardVM | None = None
    monthly_card: CadenceCardVM | None = None
    # Phase 8 Task 5.1 — per-open-position daily-management tiles. Built from
    # ``list_open_position_active_snapshots(conn) + JOIN trades-row`` per
    # spec §7.1 + §5.6 read-precedence ladder. Empty tuple when no open
    # trade has an active snapshot yet (legacy rows / first session before
    # any pipeline run has emitted snapshots). Default empty tuple so
    # ad-hoc VM construction in tests outside the Phase 8 surface remains
    # valid without supplying the field.
    daily_management_tiles: tuple = field(default_factory=tuple)


def _build_active_recommendations(
    *,
    prices: Mapping[str, PriceSnapshot],
    candidates_by_ticker: Mapping[str, Candidate],
    top_recommendations: list,
    progress_by_id: Mapping[int, HypothesisProgress],
    target_by_id: Mapping[int, int],
) -> tuple[HypothesisRecommendation, ...]:
    """Construct the hyp-recs `active_recommendations` tuple from
    prerequisites. Single source of truth — consumed by:
      - `build_dashboard` (full-page render path);
      - `build_hyp_recs_section` (Task 4: /hyp-recs/refresh route).

    Code motion only — no semantic change vs the inlined tuple
    construction at swing/web/view_models/dashboard.py:552-581 prior
    to this refactor.
    """
    return tuple(
        HypothesisRecommendation(
            ticker=r.candidate_ticker,
            current_price=(
                prices[r.candidate_ticker].price
                if r.candidate_ticker in prices else None
            ),
            pivot_price=(
                candidates_by_ticker[r.candidate_ticker].pivot
                if r.candidate_ticker in candidates_by_ticker else None
            ),
            hypothesis_id=r.hypothesis_id,
            hypothesis_name=r.hypothesis_name,
            hypothesis_progress_n=(
                progress_by_id[r.hypothesis_id].current_sample
                if r.hypothesis_id in progress_by_id else 0
            ),
            hypothesis_progress_target=(
                progress_by_id[r.hypothesis_id].target_sample
                if r.hypothesis_id in progress_by_id
                else target_by_id.get(r.hypothesis_id, 0)
            ),
            tripwire_fired=r.tripwire_fired,
            tripwire_reason=_tripwire_reason_text(
                progress_by_id.get(r.hypothesis_id),
            ),
            suggested_label=r.suggested_label_descriptive,
            hypothesis_in_flight_n=(
                progress_by_id[r.hypothesis_id].in_flight_sample
                if r.hypothesis_id in progress_by_id else 0
            ),
        )
        for r in top_recommendations
    )


@dataclass(frozen=True)
class HypRecsSectionVM:
    """Sub-VM shaped exactly as the hypothesis_recommendations.html.j2
    partial expects (`vm.active_recommendations`). Returned by
    GET /hyp-recs/refresh; renders the same flat-table chevron + Enter
    column markup the full-page render produces.

    Spec §3.5.4 (R2-Major-2 resolution).
    """
    active_recommendations: tuple[HypothesisRecommendation, ...] = ()


def build_hyp_recs_section(
    *, cfg: Config, cache: PriceCache, executor,
    exclude_tickers: Iterable[str] = (),
) -> HypRecsSectionVM:
    """Refresh-route VM builder. Resolves ONLY the data needed for the
    hyp-recs section: candidates_by_ticker (for pivot_price), prices for
    the recommended tickers (subset, NOT the full watchlist), and the
    progress/registry data the prioritizer needs. Does NOT touch
    open-trade OHLCV, watchlist top-5, advisories, status strip.

    R2-Major-2 motivation: a hyp-recs close-button refresh MUST NOT
    depend on subsystems unrelated to hyp-recs — open-trade OHLCV
    breaker tripping or watchlist sort-anchor mis-alignment must not
    break the close action.

    Spec §3.5.4.
    """
    from swing.data.repos.hypothesis import list_hypotheses
    from swing.recommendations.hypothesis import (
        match_candidate_to_hypotheses,
        prioritize_recommendations,
    )

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Task 2 (R1 M2): consume the shared `latest_evaluation_run_id`
            # helper so the hyp-recs section anchors on the same eval that
            # `build_dashboard` binds candidates_by_ticker to. Closes the
            # divergence between `/` and `/hyp-recs/refresh` under tied
            # `finished_ts` (helper has `id DESC` tiebreaker per Task 1)
            # and under standalone-eval-only state (helper falls back to
            # the most-recent `evaluation_runs` row when no completed
            # pipeline_runs exist).
            eval_id = latest_evaluation_run_id(conn)
            if eval_id is None:
                # No eval at all (fresh install, no pipeline + no
                # standalone eval) — empty section.
                return HypRecsSectionVM(active_recommendations=())
            candidates = fetch_candidates_for_run(conn, eval_id)
            # Task 3 (R1 M1 prereq): structurally exclude tickers (open
            # positions, including the just-traded one when called from
            # entry_post). Filter the candidate set before matching so the
            # prices/matchers/prioritizer never see them; the post-filter
            # below the matcher loop is defense-in-depth. .upper() on both
            # sides keeps the kwarg lenient (caller can pass mixed-case)
            # while tolerating any candidate-side casing drift.
            exclude_set = {t.upper() for t in exclude_tickers}
            if exclude_set:
                candidates = [
                    c for c in candidates if c.ticker.upper() not in exclude_set
                ]
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
                all_matches, registry=registry, progress=progress_summaries,
            )
            top_recommendations = list(prioritized[:_RECOMMENDATIONS_TOP_N])
            # Defense-in-depth: filter again after prioritization in case
            # the matcher chain ever surfaces a ticker not present in the
            # pre-filtered candidate set (e.g., future synthesis paths).
            if exclude_set:
                top_recommendations = [
                    r for r in top_recommendations
                    if r.candidate_ticker.upper() not in exclude_set
                ]
    finally:
        conn.close()
    recommended_tickers = sorted(
        {r.candidate_ticker for r in top_recommendations}
    )
    prices = cache.get_many(
        recommended_tickers,
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    active_recommendations = _build_active_recommendations(
        prices=prices,
        candidates_by_ticker=candidates_by_ticker,
        top_recommendations=top_recommendations,
        progress_by_id=progress_by_id,
        target_by_id=target_by_id,
    )
    return HypRecsSectionVM(active_recommendations=active_recommendations)


@dataclass(frozen=True)
class HypRecsExpandedVM:
    """Per-ticker hyp-recs expansion VM (spec §3.5.2).

    Carries the order parameters (buy_stop = pivot, buy_limit = pivot ×
    (1 + chase_factor), sell_stop = initial_stop), the dual sizing
    regimes (`sizing_risk` uses `sizing_equity(real, floor)`; `sizing_cash`
    uses real balance directly), context (sector/industry), the chart-
    scope reason for the same pipeline-run binding, and the freshness
    timestamp from the COMPLETED pipeline run the helper resolved.

    Returned by `build_hyp_recs_expanded`; the route handler renders it
    via the `hypothesis_recommendations_expanded.html.j2` partial (Task 5.3).
    """
    ticker: str
    # Order params.
    buy_stop: float                       # = candidate.pivot
    buy_limit: float                      # = pivot × (1 + chase_factor)
    sell_stop: float | None               # = candidate.initial_stop
    chase_factor: float                   # echo for footer / tooltip
    # Sizing (two regimes).
    current_balance: float
    risk_equity: float
    sizing_risk: SizingResult
    sizing_cash: SizingResult
    # Context.
    sector: str
    industry: str
    # Chart.
    data_asof_date: str | None            # for /charts/{date}/{TICKER}.png URL
    chart_reason: str | None              # None → in scope
    chart_reason_message: str | None
    # Freshness.
    pipeline_finished_at: str | None      # ISO timestamp of binding pipeline run


def build_hyp_recs_expanded(
    conn, cfg: Config, *, ticker: str, current_balance: float,
) -> HypRecsExpandedVM | None:
    """Resolve a hyp-recs expansion VM at request time. Returns None when:

    - No completed pipeline_run exists yet.
    - The ticker has no candidate row in the latest completed pipeline
      run's evaluation (operator's expansion request races a candidate
      rotation).
    - `candidate.pivot` is None (degenerate evaluator output).
    - `compute_shares` raises ValueError (degenerate sizing — `stop >=
      entry`; spec §3.5.3 last paragraph).

    Spec §3.5.3. Phase 2 carve-out: candidate lookup uses
    `fetch_candidates_for_run` + Python-side ticker filter rather than a
    new `get_for_evaluation` accessor — keeps `swing/data/repos/` change-
    free for this dispatch.
    """
    binding = latest_completed_pipeline_run(conn)
    if binding is None:
        return None
    if binding.evaluation_run_id is None:
        # Legacy NULL-FK pipeline_run rows pre-date migration 0006; we
        # cannot bind candidates to such a run. Treat as "no run" for the
        # hyp-recs expansion surface.
        return None
    candidates = fetch_candidates_for_run(conn, binding.evaluation_run_id)
    candidate = next((c for c in candidates if c.ticker == ticker), None)
    # Codex R2 Major-1: `Candidate.initial_stop` is `float | None` per
    # the dataclass; the schema (migration 0001) declares the column as
    # nullable REAL. A NULL stop reaches `compute_shares` as `stop=None`,
    # whose `if stop >= entry:` precondition raises TypeError — NOT the
    # ValueError the surrounding try/except catches — and the route
    # 500s instead of returning the intended unavailable partial. Guard
    # at the same upfront barrier as `pivot is None`.
    if (
        candidate is None
        or candidate.pivot is None
        or candidate.initial_stop is None
    ):
        return None

    chart_reason, chart_message = resolve_chart_scope(
        conn, binding=binding, ticker=ticker,
        charts_dir=cfg.paths.charts_dir,
        chart_top_n_watch=cfg.pipeline.chart_top_n_watch,
    )

    risk_equity = sizing_equity(
        real_equity=current_balance, floor=cfg.account.risk_equity_floor,
    )
    try:
        sizing_risk = compute_shares(
            entry=candidate.pivot, stop=candidate.initial_stop,
            equity=risk_equity,
            max_risk_pct=cfg.risk.max_risk_pct,
            position_pct_cap=cfg.sizing.position_pct_cap,
        )
        sizing_cash = compute_shares(
            entry=candidate.pivot, stop=candidate.initial_stop,
            equity=current_balance,
            max_risk_pct=cfg.risk.max_risk_pct,
            position_pct_cap=cfg.sizing.position_pct_cap,
        )
    except ValueError:
        # Degenerate sizing parameters (stop >= entry). Defensive-at-
        # boundary acceptance — the route handler renders 404 with the
        # operator-facing message; spec §3.5.3 last paragraph.
        return None

    return HypRecsExpandedVM(
        ticker=ticker,
        buy_stop=candidate.pivot,
        buy_limit=candidate.pivot * (1.0 + cfg.web.chase_factor),
        sell_stop=candidate.initial_stop,
        chase_factor=cfg.web.chase_factor,
        current_balance=current_balance,
        risk_equity=risk_equity,
        sizing_risk=sizing_risk,
        sizing_cash=sizing_cash,
        sector=candidate.sector or "",
        industry=candidate.industry or "",
        data_asof_date=binding.data_asof_date,
        chart_reason=chart_reason,
        chart_reason_message=chart_message,
        pipeline_finished_at=binding.finished_ts,
    )


def build_dashboard(
    *, cfg: Config, cache: PriceCache, executor, ohlcv_cache=None,
) -> DashboardVM:
    """Read state + prices + OHLCV bundles, return a frozen VM.

    When `ohlcv_cache=None` (transitional — wired in T14/15), the OHLCV fetch
    is skipped and all SMA fields fall through to None, so the dashboard
    renders without SMA advisories. `executor` may be None in tests.
    """
    from swing.web.view_models.open_positions_row import (
        OpenPositionsRowVM,
        _open_positions_row_vm,
    )
    from swing.web.view_models.trades import STATE_BADGE_LABELS

    now = datetime.now()
    action_session = action_session_for_run(now).isoformat()

    conn = connect(cfg.paths.db_path)
    try:
        with conn:  # atomic read snapshot across all queries
            open_trades = list_open_trades(conn)
            # Phase 4 (Task 2): consume the shared latest_completed_pipeline_run
            # helper for today_decisions / last_pipeline_ts / stale_banner.
            # Pipeline-bound contract: when no completed pipeline_runs exist,
            # all three sites correctly degrade (recs empty; last_pipeline_ts
            # None; banner None). Bug-7 family closure: id DESC tiebreaker
            # is now centralized in the helper.
            binding = latest_completed_pipeline_run(conn)
            if binding is not None:
                pipeline_run_id = binding.run_id
                pipeline_eval_id = binding.evaluation_run_id
            else:
                pipeline_run_id = None
                pipeline_eval_id = None
            recs = list_for_session(
                conn, action_session, evaluation_run_id=pipeline_eval_id,
            )
            watchlist = list_active_watchlist(conn)
            # Weather is keyed by data_asof_date (last completed session);
            # action_session is forward-looking (next session). Query by
            # ticker only — the latest classification for that ticker is the
            # right answer, regardless of its asof date. Prevents weekend/
            # holiday gaps from silently rendering STALE.
            weather = get_latest(conn, ticker=cfg.rs.benchmark_ticker)
            # Equity for status strip — fetch all exits once; also used for
            # per-trade remaining-shares grouping below (no N+1 queries).
            # C.9: now sourced from fills (non-entry) via local adapter;
            # C.10 will refactor equity.py to consume Fill directly.
            all_exits = _list_all_exitshape_via_fills(conn)
            equity = current_equity(
                starting_equity=cfg.account.starting_equity,
                exits=all_exits,
                cash_movements=list_cash(conn),
            )
            # Group exits by trade_id in Python — avoids per-row DB queries.
            exits_by_trade: dict[int, list] = defaultdict(list)
            for e in all_exits:
                exits_by_trade[e.trade_id].append(e)
            # Polish-bundle 2026-05-09 Family A — "updated today?" badge per
            # open position. Computed ONCE under this read snapshot and
            # consumed in the per-trade loop below; mirrors the
            # ``exits_by_trade`` precompute pattern.
            from swing.data.repos.daily_management import (
                has_update_today_for_trades,
            )
            update_today_set = has_update_today_for_trades(
                conn,
                [t.id for t in open_trades if t.id is not None],
                action_session=action_session,
            )
            # Latest pipeline run — two independent reads so an in-flight run
            # (finished_ts IS NULL) doesn't mask the last-known-good completion.
            # `last_pipeline_ts` = most-recent COMPLETED run's finished_ts
            #                      (now sourced from the binding above).
            # `last_pipeline_state` = state of the most-recent-started row
            #                      (so operators see 'running'/'failed' live).
            #                      DELIBERATELY a separate inline query —
            #                      `started_ts DESC` (no state filter) is
            #                      the in-flight-state surface; the
            #                      structural-guard test (Task 6) recognizes
            #                      this exception by ORDER BY shape.
            last_pipeline_ts = binding.finished_ts if binding else None
            state_row = conn.execute(
                """SELECT state FROM pipeline_runs
                   ORDER BY started_ts DESC LIMIT 1"""
            ).fetchone()
            last_pipeline_state = state_row[0] if state_row else None
            # Stale banner: most recent complete run's action_session < today's action_session.
            stale_banner = None
            if (
                binding is not None
                and binding.action_session_date < action_session
            ):
                stale_banner = (
                    f"Last pipeline session: {binding.action_session_date} —"
                    f" decisions below are for session {action_session}."
                    f" Run pipeline for the current session."
                )
            # Tranche C T4 follow-up (adversarial review Major 2): bind
            # candidates_by_ticker (and the flag_tags it feeds) to the SAME
            # eval as today_decisions. Otherwise the dashboard could show
            # pipeline-scoped decisions next to flag tags from a later
            # standalone eval — the same mixed-anchor inconsistency Bug 7
            # surfaced for chart-scope. Falls back to latest eval only when
            # there is no pipeline FK to bind to (legacy NULL or no run yet).
            # Selection logic factored into `latest_evaluation_run_id` so the
            # CLI `swing trade entry` pre-fill consults the SAME eval — see
            # adversarial review R1 Major 1 (Session 2 frontend).
            candidates: list[Candidate] = []
            candidates_eval_id = latest_evaluation_run_id(conn)
            if candidates_eval_id is not None:
                candidates = fetch_candidates_for_run(
                    conn, candidates_eval_id,
                )

            # Hypothesis-driven recommendations (frontend brief §4.1) — sourced
            # from Session 1's matcher + prioritizer + tripwire compute. Run
            # under the same read snapshot so the registry / progress numbers
            # are consistent with the candidates we just loaded. Registry +
            # target lookup are also retained so VM construction has stable
            # `target_sample` even on the degenerate-equity branch (where
            # progress_by_id is empty by design).
            top_recommendations: list = []
            progress_by_id: dict = {}
            target_by_id: dict[int, int] = {}
            # Bug-fix-C (2026-04-29): structurally exclude open-position
            # tickers from the candidate set BEFORE matching. Mirrors the
            # filter `build_hyp_recs_section` already does (Task 3
            # `exclude_tickers` kwarg) so the operator never sees the same
            # ticker in BOTH the open-positions table AND the hyp-recs
            # panel — on EITHER the entry_post OOB rebuild path OR the
            # full-page render path. Without this filter, hard-navigating
            # to / after a hyp-recs trade re-rendered the just-traded
            # ticker in the recommendations panel (operator-witnessed
            # 2026-04-29; Codex R1 Major 1 of the prior dispatch had
            # flagged this as ACCEPTED-with-rationale).
            #
            # Filter at the candidate-set level (not at top_recommendations
            # post-prioritization) so the matcher / prioritizer never see
            # excluded tickers — defense in depth against future synthesis
            # paths that might surface a ticker not present in the
            # pre-filtered candidate set.
            open_trade_tickers = {t.ticker.upper() for t in open_trades}
            hyp_recs_candidates = [
                c for c in candidates
                if c.ticker.upper() not in open_trade_tickers
            ]
            if hyp_recs_candidates:
                from swing.data.repos.hypothesis import list_hypotheses
                from swing.recommendations.hypothesis import (
                    match_candidate_to_hypotheses,
                    prioritize_recommendations,
                )

                registry = list_hypotheses(conn)
                target_by_id = {h.id: h.target_sample_size for h in registry}
                progress_by_id, progress_summaries = (
                    build_recommendation_progress(
                        conn, registry,
                        starting_equity=cfg.account.starting_equity,
                    )
                )
                all_matches = []
                for c in hyp_recs_candidates:
                    all_matches.extend(
                        match_candidate_to_hypotheses(c, registry=registry)
                    )
                prioritized = prioritize_recommendations(
                    all_matches, registry=registry,
                    progress=progress_summaries,
                )
                top_recommendations = list(
                    prioritized[:_RECOMMENDATIONS_TOP_N]
                )

            # Bug-7-family anchor discipline (Phase 4 Task 4.3):
            # classifications bind to pipeline_run_id resolved above.
            # NO MAX(run_ts) fallback — when there is no completed
            # pipeline run, classifications stay empty (legacy NULL-FK
            # eval rows have no chart-pattern data anyway).
            if pipeline_run_id is not None:
                classifications = list_classifications_for_run(
                    conn, pipeline_run_id=pipeline_run_id,
                )
            else:
                classifications = {}
    finally:
        conn.close()

    candidates_by_ticker = {c.ticker: c for c in candidates}
    # flag_tags must be computed BEFORE the watchlist sort because the new
    # `_sort_watchlist` uses tag count and precedence as primary keys. The
    # subsequent rebuild of flag_tags later in this function was removed
    # alongside this move; the same mapping is reused.
    flag_tags = _flag_tags(candidates_by_ticker)
    pattern_tags = _pattern_tags(
        classifications,
        display_threshold=cfg.web.flag_pattern_display_threshold,
    )

    # Prices — batch fetch all tickers we need. Recommended-ticker prices
    # are added so the panel can render each row's current price live; the
    # cache's last-close fallback covers tickers that the breaker is
    # currently rejecting.
    active_tickers = {t.ticker for t in open_trades}
    watch_sorted = _sort_watchlist(watchlist, flag_tags)
    top5 = watch_sorted[:5]
    active_tickers.update(w.ticker for w in top5)
    active_tickers.update(r.candidate_ticker for r in top_recommendations)
    prices = cache.get_many(
        sorted(active_tickers),
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )

    # OHLCV fetch scope: OPEN TRADES ONLY. Advisories (trail-MA, exit-below-MA)
    # only fire for open positions; watchlist rows never consume SMA data.
    # Fetching OHLCV for watchlist tickers burns yfinance quota and trips the
    # breaker on first load (0 open trades → 0 fetches). Spec §3.4 Major 3.
    bundles: dict = {}
    ohlcv_tickers = sorted({t.ticker for t in open_trades})
    if ohlcv_cache is not None and ohlcv_tickers:
        bundles = ohlcv_cache.get_many_bundles(
            ohlcv_tickers,
            deadline_seconds=cfg.web.price_fetch_deadline_seconds,
            executor=executor,
        )

    watchlist_last_prices = {w.ticker: prices[w.ticker] for w in top5 if w.ticker in prices}

    # Build per-row VMs via the pure assembler. No I/O here — all I/O already
    # happened under the `with conn:` snapshot above. Matches spec §3.4.
    weather_status_str = weather.status if weather else "STALE"

    open_trade_last_prices: dict[str, PriceSnapshot] = {}
    open_trade_advisories: dict[int, list[AdvisorySuggestionVM]] = {}
    open_trade_rows: dict[int, OpenPositionsRowVM] = {}
    for t in open_trades:
        assert t.id is not None, (
            f"open trade {t.ticker} has id=None — data-integrity bug in "
            f"list_open_trades; dashboard cannot render advisories reliably"
        )
        snap = prices.get(t.ticker)
        remaining = t.initial_shares - sum(e.shares for e in exits_by_trade.get(t.id, []))
        bundle = bundles.get(t.ticker)        # may be None or all-None
        ctx_adv = AdvisoryContext(
            as_of_date=action_session,
            current_price=snap.price if snap else 0.0,
            sma10=bundle.sma10 if bundle else None,
            sma20=bundle.sma20 if bundle else None,
            sma50=bundle.sma50 if bundle else None,
            previous_close=bundle.previous_close if bundle else None,
            weather_status=weather_status_str,
            config=cfg.stop_advisory,
        )
        raw = compute_all_suggestions(t, ctx_adv) if snap else []
        advisories_tuple = tuple(
            AdvisorySuggestionVM(rule=s.rule, message=s.message) for s in raw
        )
        row_vm = _open_positions_row_vm(
            trade=t,
            price_snapshot=snap,
            remaining_shares=remaining,
            advisories=advisories_tuple,
            state_badge_label=STATE_BADGE_LABELS.get(t.state, t.state),
            has_update_today=(t.id in update_today_set),
        )
        open_trade_rows[t.id] = row_vm
        # Legacy mappings — kept for backward compat with any external consumer.
        if snap is not None:
            open_trade_last_prices[t.ticker] = snap
        open_trade_advisories[t.id] = list(advisories_tuple)

    # Open-risk (spec §2). Helper returns dollars + contributing-count +
    # all-above-breakeven; pct computed here because the helper has no
    # equity in scope. Pct is None ONLY when equity ≤ 0 (template renders
    # "—"). The tile's displayed position count is len(open_trades) — the
    # TOTAL open positions — not the helper's contributing-count; the spec's
    # "N positions (all above breakeven)" edge case requires N to be the
    # full count so the rationale doesn't collapse to "0 positions" when
    # every stop has trailed past entry.
    open_risk_dollars, _contributing_count, open_risk_all_above_be = total_current_risk(
        open_trades, all_exits,
    )
    open_risk_pct: float | None = (
        open_risk_dollars / equity if equity > 0 else None
    )

    # Mark-to-market unrealized P&L (3e.1). Sum (price - entry) * remaining
    # over priced positions only; None when nothing is priced so the
    # template hides the line entirely (no "$0.00 (0 of N priced)" noise).
    unrealized = 0.0
    priced_count = 0
    for t in open_trades:
        snap = open_trade_last_prices.get(t.ticker)
        if snap is None:
            continue
        remaining_raw = t.initial_shares - sum(
            e.shares for e in exits_by_trade.get(t.id, [])
        )
        # Clamp negative remainders to 0 (R3 Minor 1). A negative value means
        # exits overshoot entry shares — a data-integrity bug, not a real
        # short position. Log loudly and use 0 so a bad row does not push the
        # dashboard's unrealized P&L into a phantom short PnL.
        if remaining_raw < 0:
            import logging
            logging.getLogger(__name__).warning(
                "trade %s (%s): exits overshoot entry shares "
                "(initial=%d, remaining_raw=%d) — clamping to 0",
                t.id, t.ticker, t.initial_shares, remaining_raw,
            )
            remaining = 0
        else:
            remaining = remaining_raw
        unrealized += (snap.price - t.entry_price) * remaining
        priced_count += 1
    unrealized_pnl = unrealized if priced_count > 0 else None

    # Status strip.
    status_strip = StatusStripVM(
        weather_status=(weather.status if weather else "STALE"),
        weather_rationale=(weather.rationale if weather and weather.rationale else ""),
        equity=equity,
        open_count=len(open_trades),
        soft_warn=cfg.position_limits.soft_warn_open,
        hard_cap=cfg.position_limits.hard_cap_open,
        last_pipeline_ts=last_pipeline_ts,
        last_pipeline_state=last_pipeline_state,
        open_risk_dollars=open_risk_dollars,
        open_risk_pct=open_risk_pct,
        open_risk_position_count=len(open_trades),
        open_risk_all_above_breakeven=open_risk_all_above_be,
        unrealized_pnl=unrealized_pnl,
        unrealized_priced_count=priced_count,
    )


    today_decisions = [
        DecisionVM(
            ticker=r.ticker, action_text=r.action_text or "",
            narrative=r.rationale,
        ) for r in recs if r.recommendation == "today_decision"
    ]

    # Map prioritized recommendations to display VMs. Tripwire reason text
    # mirrors `swing.journal.stats.render_hypothesis_progress` so the
    # dashboard and `swing journal review` agree on phrasing — the operator
    # is reading the same alarm in two places. `target_by_id` (registry-
    # sourced) is the fallback for the degenerate-equity branch where
    # `progress_by_id` is empty by design (see
    # `build_recommendation_progress`).
    active_recommendations = _build_active_recommendations(
        prices=prices,
        candidates_by_ticker=candidates_by_ticker,
        top_recommendations=top_recommendations,
        progress_by_id=progress_by_id,
        target_by_id=target_by_id,
    )

    # Phase 6 Task 13: needs-review badge + cadence cards.
    # Separate connection (outside the main read snapshot) so this
    # additive query block does not lengthen the critical-path transaction.
    from datetime import date as _date

    from swing.data.repos.review_log import count_needs_review, list_recent

    conn2 = connect(cfg.paths.db_path)
    try:
        with conn2:
            needs_review = count_needs_review(
                conn2,
                window_days=cfg.review.review_window_days,
                today_iso=_date.today().isoformat(),
            )
            cadence_cards: dict[str, CadenceCardVM | None] = {}
            for cadence in ("daily", "weekly", "monthly"):
                recent = list_recent(conn2, review_type=cadence, limit=1)
                if recent:
                    row = recent[0]
                    # row.review_id is non-None for any row returned by
                    # list_recent (it SELECTs from review_log where rows
                    # already carry an auto-increment PK). The `or 0`
                    # fallback is defensive only — never hit at runtime.
                    cadence_cards[cadence] = CadenceCardVM(
                        cadence_type=cadence,
                        scheduled_date=row.scheduled_date,
                        completed_date=row.completed_date,
                        period_start=row.period_start,
                        period_end=row.period_end,
                        is_pending=row.completed_date is None,
                        review_id=row.review_id or 0,
                    )
                else:
                    cadence_cards[cadence] = None
    finally:
        conn2.close()

    # Phase 8 Task 5.1 — daily-management tile list. Open the DB once more to
    # query the active-snapshot feed; JOIN with the open-trades collection
    # already in scope so each tile resolves §5.6 live values from the
    # trades-row authoritative source (current_stop, state,
    # planned_target_R) and time-series values from the snapshot row.
    from swing.data.repos.daily_management import (
        list_open_position_active_snapshots,
    )
    from swing.web.view_models.trades import DailyManagementTileVM

    daily_management_tiles: tuple[DailyManagementTileVM, ...] = ()
    open_trades_by_id = {t.id: t for t in open_trades if t.id is not None}
    if open_trades_by_id:
        conn3 = connect(cfg.paths.db_path)
        try:
            with conn3:
                snapshots = list_open_position_active_snapshots(conn3)
        finally:
            conn3.close()
        tiles: list[DailyManagementTileVM] = []
        for snap in snapshots:
            trade = open_trades_by_id.get(snap.trade_id)
            if trade is None:
                # Defensive: snapshot's open-trade JOIN diverges from the
                # in-memory open_trades list. Skip rather than render a
                # ghost tile.
                continue
            # Codex R1 Major 3 fix — open_R_effective recomputed LIVE.
            # Spec §7.1 line 547: tile shows the LIVE risk-effective value
            # using the trades-row's current_size (post-partial-exit) and
            # the live PriceCache snapshot. Snapshot's open_R_effective is
            # the close-of-session anchor and remains in the timeline; the
            # tile is the operator's "right now" view, which must reflect
            # mid-session partial exits and live price moves.
            #
            # Formula matches compute_open_R_effective in
            # swing/trades/daily_management.py:
            #   (live_price - live_avg_cost) * live_size / planned_risk
            # planned_risk_budget = (entry_price - initial_stop) * initial_shares
            # (Phase 7 pre-trade-locked derivation).
            live_snap = open_trade_last_prices.get(trade.ticker)
            live_avg_cost = (
                trade.current_avg_cost
                if trade.current_avg_cost is not None
                else trade.entry_price
            )
            planned_risk_budget = (
                (trade.entry_price - trade.initial_stop)
                * trade.initial_shares
            )
            if (
                live_snap is not None
                and trade.current_size is not None
                and trade.current_size > 0
                and planned_risk_budget != 0
            ):
                live_open_R = (  # noqa: N806
                    (live_snap.price - live_avg_cost)
                    * trade.current_size
                    / planned_risk_budget
                )
            else:
                # Fall back to the snapshot's value if live price missing
                # (PriceCache degraded path) or the trade has zero size.
                # The fallback is the closing-session anchor, not "right
                # now"; the operator sees the same value as the timeline.
                live_open_R = snap.open_R_effective  # noqa: N806

            tiles.append(DailyManagementTileVM(
                trade_id=snap.trade_id,
                ticker=trade.ticker,
                # §5.6 LIVE values from trades-row:
                state=trade.state,
                current_stop=trade.current_stop,
                planned_target_R=trade.planned_target_R,
                # §5.6 time-series + end-of-session anchored values from
                # the active snapshot row:
                current_price=snap.current_price,
                open_R_effective=live_open_R,
                open_MFE_R_to_date=snap.open_MFE_R_to_date,
                open_MAE_R_to_date=snap.open_MAE_R_to_date,
                maturity_stage=snap.maturity_stage,
                trail_MA_eligibility_flag=snap.trail_MA_eligibility_flag,
                trail_MA_candidate_price=snap.trail_MA_candidate_price,
                position_capital_utilization_pct=(
                    snap.position_capital_utilization_pct
                ),
                position_capital_denominator_dollars=(
                    snap.position_capital_denominator_dollars
                ),
                position_portfolio_heat_contribution_dollars=(
                    snap.position_portfolio_heat_contribution_dollars
                ),
                data_asof_session=snap.data_asof_session,
            ))
        daily_management_tiles = tuple(tiles)

    degraded_until = cache.degraded_until()
    return DashboardVM(
        generated_at=now.isoformat(timespec="seconds"),
        session_date=action_session,
        stale_banner=stale_banner,
        status_strip=status_strip,
        today_decisions=today_decisions,
        open_trades=list(open_trades),
        open_trade_advisories=open_trade_advisories,
        open_trade_last_prices=open_trade_last_prices,
        watchlist_top5=list(top5),
        watchlist_remaining_count=max(0, len(watchlist) - 5),
        watchlist_last_prices=watchlist_last_prices,
        flag_tags=flag_tags,
        candidates_by_ticker=candidates_by_ticker,
        prices_generated_at=now.isoformat(timespec="seconds"),
        price_source_degraded=cache.is_degraded(),
        price_source_degraded_until=(
            degraded_until.isoformat(timespec="seconds") if degraded_until else None
        ),
        ohlcv_source_degraded=(
            ohlcv_cache.is_degraded() if ohlcv_cache is not None else False
        ),
        open_trade_rows=open_trade_rows,
        active_recommendations=active_recommendations,
        pattern_tags=pattern_tags,
        needs_review_count=needs_review,
        daily_card=cadence_cards["daily"],
        weekly_card=cadence_cards["weekly"],
        monthly_card=cadence_cards["monthly"],
        daily_management_tiles=daily_management_tiles,
    )


def _tripwire_reason_text(progress) -> str | None:
    """Render the per-hypothesis tripwire alarm as a single string, or None
    when no tripwire is fired. Mirrors `render_hypothesis_progress` in
    `swing.journal.stats` so the operator sees the same phrasing on the
    dashboard and in `swing journal review`.

    Wording pinned to match the journal review formatter (adversarial
    review R1 Minor 1): consecutive bit reads "{N} consecutive -1R
    (threshold {T})", absolute bit reads "absolute loss ${magnitude}",
    and the trailing recommendation suffix is "recommend escape
    evaluation". If you change one formatter, change both.
    """
    if progress is None or not progress.tripwire_fired:
        return None
    bits: list[str] = []
    if progress.consecutive_tripwire_fired:
        bits.append(
            f"{progress.consecutive_max_loss_streak} consecutive -1R "
            f"(threshold {progress.consecutive_loss_tripwire_threshold})"
        )
    if progress.absolute_tripwire_fired:
        bits.append(
            f"absolute loss ${-progress.cumulative_loss:.2f}"
        )
    if not bits:
        return None
    return "; ".join(bits) + "; recommend escape evaluation"


# Tag precedence encoding for the secondary sort key. Operator-confirmed
# order: A+ > VCP✓ > TT✓. Sum-of-position-values (rather than strict
# lexicographic) so the natural tag combinations on real candidates
# ((A+, VCP✓, TT✓), (VCP✓, TT✓), (TT✓,), ()) order correctly AND a future
# tag addition only requires assigning a precedence value — the sort
# survives. Keys MUST exactly match the strings emitted by `_flag_tags`
# below (note Unicode checkmark `✓`, not ASCII `v`); a mismatch would
# silently score every tag at 0 via the `.get(t, 0)` fallback.
_TAG_PRECEDENCE = {"A+": 4, "VCP✓": 2, "TT✓": 1}


def _tag_precedence_score(tags: tuple[str, ...]) -> int:
    """Sum-of-precedence-values across a row's flag tags. Higher score
    sorts first as the secondary key in `_sort_watchlist`. Unknown tags
    score 0."""
    return sum(_TAG_PRECEDENCE.get(t, 0) for t in tags)


def _abs_proximity(w: WatchlistEntry) -> float:
    """abs(% to pivot) — tertiary sort key. Returns +inf when pivot or
    last_close is missing so those rows sort last on the proximity axis."""
    if w.entry_target is None or w.last_close is None:
        return float("inf")
    return abs(w.last_close - w.entry_target) / max(w.entry_target, 1e-6)


def _tag_aware_sort_key(
    entry: WatchlistEntry,
    flag_tags: Mapping[str, tuple[str, ...]],
) -> tuple[int, int, float, str]:
    """4-key composite sort key. Spec §A.

    Returns (-tag_count, -tag_precedence_score, abs_proximity, ticker).

    Shared between _sort_watchlist (web view-model) and _step_charts
    (pipeline) — by-construction byte identity for the chart-scope
    tag-aware tier per spec §A "Tag-aware composite definition."
    """
    tags = flag_tags.get(entry.ticker, ())
    return (
        -len(tags),
        -_tag_precedence_score(tags),
        _abs_proximity(entry),
        entry.ticker,
    )


def _sort_watchlist(
    watchlist: list[WatchlistEntry],
    flag_tags: Mapping[str, tuple[str, ...]],
) -> list[WatchlistEntry]:
    """4-key composite via _tag_aware_sort_key. The trailing ticker key is
    part of the contract — without it, Python's stable sort preserves
    whatever order list_active_watchlist happens to return on full-equality
    ties, which is non-deterministic.
    """
    return sorted(watchlist, key=lambda w: _tag_aware_sort_key(w, flag_tags))


def _flag_tags(candidates_by_ticker: Mapping[str, Candidate]) -> Mapping[str, tuple[str, ...]]:
    tags: dict[str, tuple[str, ...]] = {}
    for ticker, c in candidates_by_ticker.items():
        row_tags: list[str] = []
        tt_pass = sum(1 for cr in c.criteria if cr.layer == "trend_template" and cr.result == "pass")
        if tt_pass >= 7:
            row_tags.append("TT\u2713")
        vcp_pass = sum(1 for cr in c.criteria if cr.layer == "vcp" and cr.result == "pass")
        vcp_total = sum(1 for cr in c.criteria if cr.layer == "vcp")
        if vcp_total and vcp_pass == vcp_total:
            row_tags.append("VCP\u2713")
        if c.bucket == "aplus":
            row_tags.append("A+")
        if row_tags:
            tags[ticker] = tuple(row_tags)
    return tags


def _pattern_tags(
    classifications_by_ticker, display_threshold: float,
) -> Mapping[str, str]:
    """Return {ticker: 'flag (0.78)'} for tickers whose classification's
    pattern == 'flag' and confidence >= threshold. Spec \u00a73.5 (R1 M2).

    SIBLING to `_flag_tags` \u2014 by construction the pattern tag NEVER enters
    the `tags` tuple consumed by `_sort_watchlist`. Sort-neutrality is
    structurally guaranteed: callers populate the parallel `pattern_tags`
    VM field with this helper's output and consume both fields at render
    time without merging.

    `classifications_by_ticker` is a mapping of ticker \u2192
    PipelinePatternClassification (the shape produced by
    `list_classifications_for_run`). None or empty mapping returns {}.
    Format pinned to two decimals to give stable visual width across
    confidence bands.
    """
    if not classifications_by_ticker:
        return {}
    out: dict[str, str] = {}
    for ticker, cls in classifications_by_ticker.items():
        if (
            cls.pattern == "flag"
            and cls.confidence is not None
            and cls.confidence >= display_threshold
        ):
            out[ticker] = f"flag ({cls.confidence:.2f})"
    return out
