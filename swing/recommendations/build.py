"""Build the immutable per-session DailyRecommendation snapshot.

Precedence: ticker classified as A+ today wins → today_decision (skip near_trigger to avoid double).
Watchlist tickers near pivot → near_trigger.
Watchlist tickers in watch state → watchlist_watch (informational).

Sizing basis: the LIMIT, never the pivot — see `_sizing_entry`. The pivot stays
the TRIGGER the row reports (`entry_target`, the action text); only the price
the share count is computed against moved.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from swing.data.models import Candidate, DailyRecommendation, WatchlistEntry
from swing.latches.constants import mandate_limit_price, zone_cap_for_pivot
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


def _sizing_entry(pivot: float, stop: float) -> float:
    """THE ENTRY BASIS FOR SIZING: the LIMIT, not the pivot (RD 2026-07-30,
    applied to this path 2026-08-04).

    The pivot is the TRIGGER, not the fill. An order triggered at the pivot can
    fill anywhere up to the buy-zone cap, and in the pullback regime the cap is
    PRECISELY where it fills -- so a count sized off the pivot risks more than
    the policy allows at an ordinary fill, not only in a tail. The latch mandate
    (`swing/latches/order_intent.py:compute_prepared_order`) has sized off the
    limit since 21-B; this is the same rule reaching the nightly briefing, so
    the two surfaces state one share count for one setup.

    NEITHER ARITHMETIC IS RE-IMPLEMENTED HERE. `zone_cap_for_pivot` is the
    latch derivation's own cap expression and `mandate_limit_price` is the
    quantization the prepared order emits; a private copy would agree today and
    drift on the next edit (the item-6 class this project has already paid for).
    The FRAMEWORK cap fraction is used, deliberately and not
    `cfg.web.chase_factor`: that knob is a WEB display pad on the dashboard
    expansion, and the nightly's order is the framework's own.

    THE PIVOT-VS-STOP PRECONDITION IS ENFORCED HERE rather than left to
    `compute_shares`. With entry = the pivot, `compute_shares`'s `stop >= entry`
    refusal doubled as the "the stop must sit below the trigger" sanity gate;
    widening the entry to the limit would silently let a stop ABOVE the pivot
    through and ship a recommendation whose stop is above its own trigger. The
    latch derivation carries the same invariant (`Latch.__post_init__`:
    stop < pivot < zone_cap), so this preserves a guard rather than inventing
    one. Degenerate geometry still fails LOUDLY, exactly as it did before.
    """
    if stop >= pivot:
        raise ValueError(
            f"stop must be < pivot; got pivot={pivot}, stop={stop}")
    return mandate_limit_price(zone_cap_for_pivot(pivot))


def _format_action(shares: int, entry: float, risk_dollars: float,
                   infeasible: bool, basis: float | None = None,
                   stop: float | None = None) -> str:
    """The row's one-line action, SELF-CHECKABLE.

    THE WHOLE RISK EQUATION IS ON THE LINE (Codex R1 MAJOR, completed at R2).
    The row reports the TRIGGER in `entry_target` and the LIMIT-basis risk in
    `risk_dollars`, so from 2026-08-04 a reader recomputing
    `shares x (entry_target - stop_target)` gets a DIFFERENT number from the
    risk the row states -- for AMN, $27.10 against the stated $32.50. Naming
    the basis alone did not close that: NEITHER the markdown briefing nor the
    HTML one renders `stop_target` for a decision, so the operator had no
    route to the figure at all. Both consumers render `action_text`, so
    stating the equation here fixes both at one site.

    THE RISK FIGURE IS TWO DECIMALS for the same reason: at `.0f` the exact
    $32.50 printed as $32 and the equation the line states would not have
    evaluated to the number beside it.

    IT DOES NOT SAY "LIMIT", deliberately: the Tranche-B spec retired
    "Buy-stop limit" because it implied a two-price BROKER ORDER this row
    never produces, and that contract is still pinned by
    `test_aplus_action_text_does_not_say_limit`. "Cap" names the SIZING
    price without describing a second order leg.
    """
    if infeasible:
        return "Risk infeasible at current sizing — skip or wait for tighter setup"
    text = f"Buy-stop ${entry:.2f} \u00b7 {shares} sh \u00b7 ${risk_dollars:.2f} risk"
    if basis is not None and stop is not None:
        text += (f" = {shares} x (${basis:.2f} cap - ${stop:.2f} stop)")
    return text


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
        basis = _sizing_entry(c.pivot, c.initial_stop)
        sizing = compute_shares(
            entry=basis,
            stop=c.initial_stop, equity=ctx.current_equity,
            max_risk_pct=ctx.max_risk_pct, position_pct_cap=ctx.position_pct_cap,
        )
        infeasible = not sizing.feasible
        recs.append(DailyRecommendation(
            id=None, evaluation_run_id=ctx.evaluation_run_id,
            data_asof_date=ctx.data_asof_date,
            action_session_date=ctx.action_session_date,
            ticker=c.ticker, recommendation="today_decision",
            action_text=_format_action(
                sizing.shares, c.pivot, sizing.risk_dollars, infeasible,
                basis=basis, stop=c.initial_stop),
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
        # BOTH sizing call sites move, not just the A+ one: a fix applied to
        # one leaves the other stating a pivot-basis count for the same
        # geometry (the completeness lesson).
        basis = (
            _sizing_entry(w.entry_target, w.initial_stop_target)
            if w.initial_stop_target else None)
        sizing = compute_shares(
            entry=basis, stop=w.initial_stop_target,
            equity=ctx.current_equity, max_risk_pct=ctx.max_risk_pct,
            position_pct_cap=ctx.position_pct_cap,
        ) if basis is not None else None
        recs.append(DailyRecommendation(
            id=None, evaluation_run_id=ctx.evaluation_run_id,
            data_asof_date=ctx.data_asof_date,
            action_session_date=ctx.action_session_date,
            ticker=w.ticker, recommendation="near_trigger",
            action_text=(
                _format_action(
                    sizing.shares, w.entry_target,
                    sizing.risk_dollars, not sizing.feasible,
                    basis=basis, stop=w.initial_stop_target,
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
