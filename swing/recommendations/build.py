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
from swing.recommendations.sizing import SizingResult, compute_shares


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


def _sizing_entry(pivot: float) -> float:
    """THE ENTRY BASIS FOR SIZING: the LIMIT, not the pivot (RD
    2026-07-30, applied to this path 2026-08-04).

    The pivot is the TRIGGER, not the fill. An order triggered at the pivot
    can fill anywhere up to the buy-zone cap, and in the pullback regime the
    cap is PRECISELY where it fills -- so a count sized off the pivot risks
    more than the policy allows at an ordinary fill, not only in a tail. The
    latch mandate (`swing/latches/order_intent.py:compute_prepared_order`)
    has sized off the limit since 21-B; this is the same rule reaching the
    nightly briefing, so the two surfaces state one share count for one
    setup.

    NEITHER ARITHMETIC IS RE-IMPLEMENTED HERE. `zone_cap_for_pivot` is the
    latch derivation's own cap expression and `mandate_limit_price` is the
    quantization the prepared order emits; a private copy would agree today
    and drift on the next edit (the item-6 class this project has already
    paid for). The FRAMEWORK cap fraction is used, deliberately and not
    `cfg.web.chase_factor`: that knob is a WEB display pad on the dashboard
    expansion, and the nightly's order is the framework's own.

    IT RAISES `ValueError` ON A NON-FINITE OR OVERFLOWING PIVOT, which is
    `zone_cap_for_pivot`'s own contract. `_sizing_result` catches that --
    see the reason there.
    """
    return mandate_limit_price(zone_cap_for_pivot(pivot))


def _equation(shares: int, basis: float, stop: float,
              risk_dollars: float) -> str:
    """The risk equation, at whatever precision makes it TRUE.

    CODEX R3 MAJOR, GENERALISED AT R4. `candidates.initial_stop` is a bare
    REAL with NO precision constraint, and 1105 of the 11753 live candidate
    rows already carry a sub-cent stop (ADPT, 2026-08-04: 19.771). A FIXED
    display precision cannot serve every one of them, because the residual
    is MULTIPLIED BY THE SHARE COUNT: at pivot 0.5001 / stop 0.500049 the
    position cap binds at 2205 shares and a 4-decimal stop states an
    equation worth $22.05 beside a risk of $21.94. A self-checkable line
    that fails its own check is worse than one that never invited the
    check, so THE PRECISION IS DERIVED FROM THE CHECK rather than guessed.

    Two decimals are tried first because that is what every ordinary
    geometry needs and extra digits are noise; the search widens only when
    the printed equation would not round to the printed risk.

    THE FALLBACK IS EXACT, NOT A LAST GUESS. `repr` of a float is the
    shortest decimal that ROUND-TRIPS it, so the operands parse back to the
    very floats `compute_shares` subtracted and the equation reproduces
    `risk_dollars` bit for bit. The loop above it is a readability
    preference, never a correctness dependency.
    """
    target = round(risk_dollars, 2)
    for places in (2, 4, 6, 8):
        cap_text = f'{basis:.{places}f}'
        stop_text = f'{stop:.{places}f}'
        if round(shares * (float(cap_text) - float(stop_text)), 2) == target:
            break
    else:
        cap_text, stop_text = repr(float(basis)), repr(float(stop))
    return f' = {shares} x (${cap_text} cap - ${stop_text} stop)'


def _sizing_result(pivot: float | None, stop: float | None,
                   ctx: BuildContext):
    """`(basis, SizingResult)` for one row -- INFEASIBLE, never an
    abort, when the geometry is not orderable.

    CODEX R3 MAJOR -- THE UNORDERABLE LIMIT. The whole-cent floor can put
    the limit AT OR BELOW the stop for a sub-cent pivot: at pivot 0.009 /
    stop 0.001 the cap 0.0093 floors to 0.00, and `compute_shares` then
    raises `stop >= entry`. That exception is uncaught in this builder, so
    ONE such candidate would abort the whole nightly step and NO
    recommendation would be written -- a geometry the pivot basis accepted.

    CODEX R5 MAJOR -- THE NON-FINITE PIVOT, the same class one step
    earlier. `zone_cap_for_pivot` refuses a non-finite pivot and an
    overflowing one (1.79e308 x 1.03 is `inf`), and `candidates.pivot` is a
    bare REAL: no CHECK excludes either, and SQLite stores infinity
    happily. The PIVOT basis absorbed both silently -- `floor(budget / inf)`
    is 0 -- so the change turned a quiet infeasible row into a lost batch.
    The derivation is therefore caught and reported as infeasible with NO
    basis, so the line states no price it could not compute.

    An unorderable geometry is exactly what `infeasible` means, and the
    today_decision snapshot is specified to LIST infeasible names rather
    than drop them (`test_infeasible_sizing_still_produces_today_decision`),
    so the row is emitted with zero shares and no price.

    A STOP AT OR ABOVE THE PIVOT STILL RAISES. That is degenerate DATA, not
    an unreachable price: it aborted the step before this change too, and
    while the entry was the pivot it doubled as the "stop below the trigger"
    gate that the wider basis would otherwise have loosened. The latch
    derivation carries the same invariant (`Latch.__post_init__`:
    stop < pivot < zone_cap). A NON-FINITE STOP is likewise unchanged in
    kind -- it reached `compute_shares` and raised before this change and
    still does.

    A LIMIT BELOW THE TRIGGER IS REFUSED, AND THAT IS THE STRONGEST OF THE
    REFUSALS (Codex R8). The whole-cent FLOOR can put the limit UNDER the
    pivot whenever `pivot x 0.03` is worth less than a cent -- at pivot
    0.019 the cap 0.0196 floors to $0.01. Such a row is non-null, finite,
    positive and above the stop, so it slipped every other guard, and the
    consequence is the WORST kind: sizing off $0.01 against a $0.001 stop
    recommends 4166 shares and reports $37.49 of risk, while the order
    TRIGGERS at $0.019 and therefore risks $74.99 -- twice the policy cap,
    which is the exact defect this whole change exists to remove, running
    in the opposite direction. An order cannot fill below its own trigger,
    so a limit under the pivot is not an order at all.

    A SEPARATE `basis <= stop` CHECK IS NOW REDUNDANT and was removed
    rather than kept as reassurance: `stop >= pivot` is refused above, so
    `basis >= pivot > stop` follows. Both of the earlier geometries still
    land here -- pivot 0.009 floors to $0.00 and pivot 1e-305 to $0.00,
    each below its own pivot -- and their tests still pin them.

    OUT OF SCOPE, FLAGGED: `compute_prepared_order` has the SAME hole. Its
    breakout branch emits `stop = latched_pivot` with
    `limit = mandate_limit_price(zone_cap)`, so on this geometry it would
    offer a stop-limit whose limit sits below its own trigger.
    `Latch.__post_init__` guarantees `pivot < zone_cap` on the RAW cap and
    says nothing about the quantized one. That is 21-B's emitter, not this
    arc's scope.

    A NON-POSITIVE BASIS IS REFUSED TOO, AND `<= stop` DOES NOT COVER IT
    (Codex R7). At pivot 1e-305 the cap rounds to 0.0 and the limit
    quantizes to $0.00; against a NEGATIVE stop, `0.0 <= -1e-307` is False,
    so the row fell through to `compute_shares(entry=0.0, ...)` whose risk
    leg evaluates `floor(37.5 / 1e-307)` and raises **OverflowError** --
    which is NOT the `ValueError` either surface guards, so the nightly
    lost the batch and the dashboard 500'd. The pivot basis produced finite
    quotients for the same geometry, so this too is a regression.
    Refusing a non-positive basis closes the overflow at its source rather
    than widening a shared `except`: a POSITIVE basis is a whole-cent price,
    hence at least $0.01, so `equity x cap / basis` is bounded and the risk
    leg cannot overflow either (float spacing near $0.01 is ~1.7e-18, so no
    representable stop puts `basis - stop` inside the ~2e-307 needed).

    A NULL PIVOT OR STOP IS THE SAME CLASS AND IS REFUSED THE SAME WAY
    (Codex R6). `Candidate.pivot` and `Candidate.initial_stop` are both
    `float | None` and the schema declares both REAL without NOT NULL, and
    `_step_recommendations` passes every A+ candidate through unfiltered.
    A `None` reaching the ordering comparison raises `TypeError` OUTSIDE
    any guard, so one degenerate evaluator row lost the whole batch. That
    is PRE-EXISTING -- `compute_shares(entry=None, ...)` raised the same
    way before this change -- but it is the same batch-loss class as the
    two above, in the same function, and the dashboard's own builder has
    guarded the null pair since Phase 2.

    THE ORDERING TEST IS `stop >= pivot`, NOT `not stop < pivot`, AND THE
    DIFFERENCE IS `nan`. Every comparison against `nan` is False, so a
    `nan` PIVOT falls through this gate and is caught one line below as a
    derivation failure -- a per-row infeasible instead of a lost batch.
    That is strictly better than the pivot basis, which reached
    `math.floor(nan)` and aborted; the strict form would have re-created
    the abort while reading like a tightening.
    """
    infeasible = SizingResult(
        shares=0, risk_dollars=0.0, risk_pct=0.0, notional=0.0,
        notional_pct=0.0, feasible=False, constraint='infeasible')
    if pivot is None or stop is None:
        return None, infeasible
    if stop >= pivot:
        raise ValueError(
            f'stop must be < pivot; got pivot={pivot}, stop={stop}')
    try:
        basis = _sizing_entry(pivot)
    except ValueError:
        return None, infeasible
    if basis <= 0 or basis < pivot:
        return None, infeasible
    return basis, compute_shares(
        entry=basis, stop=stop, equity=ctx.current_equity,
        max_risk_pct=ctx.max_risk_pct,
        position_pct_cap=ctx.position_pct_cap)


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
        text += _equation(shares, basis, stop, risk_dollars)
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
        basis, sizing = _sizing_result(c.pivot, c.initial_stop, ctx)
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
        basis, sizing = (
            _sizing_result(w.entry_target, w.initial_stop_target, ctx)
            if w.initial_stop_target else (None, None))
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
