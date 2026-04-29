"""DashboardVM + builder."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Candidate, Trade, WatchlistEntry, WeatherRun
from swing.data.repos.cash import list_cash
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.pattern_classifications import (
    list_classifications_for_run,
)
from swing.data.repos.recommendations import list_for_session
from swing.data.repos.trades import list_all_exits, list_open_trades
from swing.data.repos.watchlist import list_active_watchlist
from swing.data.repos.weather import get_latest
from swing.evaluation.dates import action_session_for_run
from swing.journal.stats import HypothesisProgress
from swing.trades.advisory import AdvisoryContext, compute_all_suggestions
from swing.trades.equity import current_equity, total_current_risk
from swing.web.price_cache import PriceCache, PriceSnapshot


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
    pipeline_eval_row = conn.execute(
        """SELECT evaluation_run_id FROM pipeline_runs
           WHERE state = 'complete'
           ORDER BY finished_ts DESC LIMIT 1"""
    ).fetchone()
    pipeline_eval_id = (
        pipeline_eval_row[0] if pipeline_eval_row else None
    )
    if pipeline_eval_id is not None:
        return pipeline_eval_id
    fallback = conn.execute(
        "SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1"
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


# Top-N cap for the dashboard recommendations panel. Pinned as a module
# constant (not config) so the rendering surface remains predictable; if
# the operator wants more, the section is paginated by the prioritizer's
# stable ordering and they can pull the rest from the journal-progress
# section.
_RECOMMENDATIONS_TOP_N = 10


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
        )
        for r in top_recommendations
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

    now = datetime.now()
    action_session = action_session_for_run(now).isoformat()

    conn = connect(cfg.paths.db_path)
    try:
        with conn:  # atomic read snapshot across all queries
            open_trades = list_open_trades(conn)
            # Tranche C T4 (Bug 7): bind today_decisions to the pipeline's
            # OWN eval via pipeline_runs.evaluation_run_id when populated.
            # Eliminates the mixed-anchor inconsistency where today_decisions
            # could show a ticker that the chart-scope resolver reported as
            # out-of-scope (because chart-scope already binds via the FK).
            # Legacy NULL-FK rows fall back to the pre-T4 date-only filter
            # so older runs still render today_decisions.
            pipeline_eval_row = conn.execute(
                """SELECT id, evaluation_run_id FROM pipeline_runs
                   WHERE state = 'complete'
                   ORDER BY finished_ts DESC LIMIT 1"""
            ).fetchone()
            pipeline_run_id = (
                pipeline_eval_row[0] if pipeline_eval_row else None
            )
            pipeline_eval_id = (
                pipeline_eval_row[1] if pipeline_eval_row else None
            )
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
            all_exits = list_all_exits(conn)
            equity = current_equity(
                starting_equity=cfg.account.starting_equity,
                exits=all_exits,
                cash_movements=list_cash(conn),
            )
            # Group exits by trade_id in Python — avoids per-row DB queries.
            exits_by_trade: dict[int, list] = defaultdict(list)
            for e in all_exits:
                exits_by_trade[e.trade_id].append(e)
            # Latest pipeline run — two independent reads so an in-flight run
            # (finished_ts IS NULL) doesn't mask the last-known-good completion.
            # `last_pipeline_ts` = most-recent COMPLETED run's finished_ts
            #                      (when we last had a successful data refresh).
            # `last_pipeline_state` = state of the most-recent-started row
            #                      (so operators see 'running'/'failed' live).
            ts_row = conn.execute(
                """SELECT finished_ts FROM pipeline_runs
                   WHERE state = 'complete'
                   ORDER BY finished_ts DESC LIMIT 1"""
            ).fetchone()
            last_pipeline_ts = ts_row[0] if ts_row else None
            state_row = conn.execute(
                """SELECT state FROM pipeline_runs
                   ORDER BY started_ts DESC LIMIT 1"""
            ).fetchone()
            last_pipeline_state = state_row[0] if state_row else None
            # Stale banner: most recent complete run's action_session < today's action_session.
            row = conn.execute(
                """SELECT action_session_date FROM pipeline_runs
                   WHERE state='complete'
                   ORDER BY finished_ts DESC LIMIT 1"""
            ).fetchone()
            stale_banner = None
            if row is not None and row[0] < action_session:
                stale_banner = (
                    f"Last pipeline session: {row[0]} — decisions below are for session "
                    f"{action_session}. Run pipeline for the current session."
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
            if candidates:
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
                for c in candidates:
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
