"""Build the immutable per-session DailyRecommendation snapshot.

Precedence: ticker classified as A+ today wins → today_decision (skip near_trigger to avoid double).
Watchlist tickers near pivot → near_trigger.
Watchlist tickers in watch state → watchlist_watch (informational).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from swing.data.models import Candidate, DailyRecommendation, WatchlistEntry
from swing.recommendations.near_trigger import is_near_trigger
from swing.recommendations.sizing import compute_shares


@dataclass(frozen=True)
class BuildContext:
    evaluation_run_id: int
    data_asof_date: str
    action_session_date: str
    current_equity: float
    max_risk_pct: float
    position_pct_cap: float
    near_trigger_above_pct: float = 0.5
    near_trigger_below_pct: float = 1.0


def _format_action(shares: int, entry: float, risk_dollars: float, infeasible: bool) -> str:
    if infeasible:
        return "Risk infeasible at current sizing — skip or wait for tighter setup"
    return f"Buy-stop ${entry:.2f} \u00b7 {shares} sh \u00b7 ${risk_dollars:.0f} risk"


def build_recommendations(
    *, ctx: BuildContext,
    today_aplus: Iterable[Candidate],
    prior_watchlist: Iterable[WatchlistEntry],
) -> list[DailyRecommendation]:
    aplus_list = list(today_aplus)
    aplus_tickers = {c.ticker for c in aplus_list}

    recs: list[DailyRecommendation] = []

    # 1. A+ names → today_decision (with sizing)
    for c in aplus_list:
        sizing = compute_shares(
            entry=c.pivot, stop=c.initial_stop, equity=ctx.current_equity,
            max_risk_pct=ctx.max_risk_pct, position_pct_cap=ctx.position_pct_cap,
        )
        infeasible = not sizing.feasible
        recs.append(DailyRecommendation(
            id=None, evaluation_run_id=ctx.evaluation_run_id,
            data_asof_date=ctx.data_asof_date,
            action_session_date=ctx.action_session_date,
            ticker=c.ticker, recommendation="today_decision",
            action_text=_format_action(sizing.shares, c.pivot, sizing.risk_dollars, infeasible),
            entry_target=c.pivot, stop_target=c.initial_stop,
            shares=sizing.shares,
            risk_dollars=sizing.risk_dollars, risk_pct=sizing.risk_pct,
            rationale=f"A+ setup, {c.adr_pct:.1f}% ADR, {c.prior_trend_pct:.0f}% prior trend",
        ))

    # 2. Watchlist near-trigger → near_trigger (skip if already in today_decision)
    for w in prior_watchlist:
        if w.ticker in aplus_tickers:
            continue
        if w.last_close is None or w.entry_target is None:
            continue
        if not is_near_trigger(
            price=w.last_close, entry_target=w.entry_target,
            above_pct=ctx.near_trigger_above_pct,
            below_pct=ctx.near_trigger_below_pct,
        ):
            continue
        sizing = compute_shares(
            entry=w.entry_target, stop=w.initial_stop_target or 0.0,
            equity=ctx.current_equity, max_risk_pct=ctx.max_risk_pct,
            position_pct_cap=ctx.position_pct_cap,
        ) if w.initial_stop_target else None
        recs.append(DailyRecommendation(
            id=None, evaluation_run_id=ctx.evaluation_run_id,
            data_asof_date=ctx.data_asof_date,
            action_session_date=ctx.action_session_date,
            ticker=w.ticker, recommendation="near_trigger",
            action_text=(
                _format_action(
                    sizing.shares, w.entry_target,
                    sizing.risk_dollars, not sizing.feasible,
                )
                if sizing else "Pivot reached — review setup"
            ),
            entry_target=w.entry_target, stop_target=w.initial_stop_target,
            shares=sizing.shares if sizing else None,
            risk_dollars=sizing.risk_dollars if sizing else None,
            risk_pct=sizing.risk_pct if sizing else None,
            rationale=f"Watchlist \u00b7 {w.qualification_count} qualifies",
        ))

    return recs
