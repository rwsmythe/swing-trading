from __future__ import annotations

from dataclasses import dataclass, field

from research.harness.shadow_expectancy.bracket import ma_exit_fill, price_stop_fill
from research.harness.shadow_expectancy.constants import BRACKET_ARMS
from research.harness.shadow_expectancy.io import Bar
from swing.trades.derived_metrics import (
    initial_risk_per_share,
    r_multiple,
    realized_pnl,
)


@dataclass(frozen=True)
class SimParams:
    initial_shares: float
    partial_session_n: int
    partial_pct: float
    breakeven_r_trigger: float
    maturity_fast_ma_r: float
    ma_fast_period: int
    ma_slow_period: int
    horizon_sessions: int


@dataclass(frozen=True)
class Leg:
    action: str        # 'entry' | 'partial' | 'exit' | 'mtm'
    qty: float
    price: float       # per ARM; stored as a dict at the SimResult level
    session: str


@dataclass
class SimResult:
    entry_fill: float
    initial_stop: float          # C1: mechanical stop = entry_bar.low (NOT candidate-supplied)
    risk_per_share: float
    entry_bar_ambiguous: bool
    degenerate: bool
    exit_reason: str
    open_at_horizon: bool
    # per-arm: {"realistic": R, "favorable_reprice": R}; None when degenerate.
    realized_r: dict | None
    legs: list = field(default_factory=list)
    holding_sessions: int = 0
    # m3 (defined HERE at the dataclass's definition site so Task 8's price-stop return
    # can set it independently of Task 9): the per-arm terminal exit fill
    # {"realistic": x, "favorable_reprice": y} for a CLOSED trade's terminal leg; None for
    # open/MTM/degenerate where both arms coincide. Task 8's stop-exit return and Task 9's
    # MA-exit return populate it; the horizon/degenerate returns leave it None.
    terminal_fill: dict | None = None
    # Censoring/horizon annotations (Task 9 sets these on the open-at-horizon return; the
    # closed/degenerate returns leave them defaulted).
    censoring_scenarios: dict | None = None
    forced_exit_collapsed_to_mtm: bool = False


def _entry_fill(pivot: float, entry_bar: Bar) -> float:
    return max(pivot, entry_bar.open)


def _r_for_legs(entry_fill, rps, initial_shares, legs_priced) -> float:
    """Multi-leg R on ONE FIXED denominator (spec 5.8 / Codex C2).

    legs_priced: list of (qty, price). Sum the per-leg realized P&L, then divide
    ONCE by (rps * initial_shares) via a single r_multiple call. Summing
    r_multiple(...quantity=leg_qty) per leg would divide each leg by its OWN
    denominator (rps*leg_qty) and double-count (50%@+1.2R + 50%@+2.0R would total
    3.2R instead of the correct 1.6R).
    """
    total_pnl = sum(
        realized_pnl(entry_price=entry_fill, exit_price=price, quantity=qty)
        for qty, price in legs_priced
    )
    return r_multiple(realized_pnl=total_pnl, initial_risk_per_share=rps,
                      quantity=initial_shares)


def _running_r(entry_fill, rps, price) -> float:
    return (price - entry_fill) / rps  # mirrors equity.r_so_far formula


def _sma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _trail_ma_period(running_r: float, params: SimParams) -> int:
    """Maturity-staged 10/20 proxy (D12): >=+2R -> 10MA else 20MA."""
    return params.ma_fast_period if running_r >= params.maturity_fast_ma_r \
        else params.ma_slow_period


def simulate(*, pivot, entry_bar: Bar, forward_bars, params: SimParams):
    # C1 / spec 5.2 / D6: mechanical stop = entry_bar.low (derived, not candidate-supplied).
    entry_fill = _entry_fill(pivot, entry_bar)
    initial_stop = entry_bar.low
    rps = initial_risk_per_share(entry_price=entry_fill, initial_stop=initial_stop)
    ambiguous = entry_bar.low < entry_fill
    if entry_fill <= initial_stop:
        return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                         risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                         degenerate=True, exit_reason="degenerate_risk",
                         open_at_horizon=False, realized_r=None)

    current_stop = initial_stop
    shares = params.initial_shares
    shares_remaining = shares
    horizon = min(params.horizon_sessions, len(forward_bars))
    # legs carry an ARM-INDEPENDENT price for partials (a close, identical across arms)
    # and an ARM-DEPENDENT price only for the terminal stop/MA exit (computed at exit).
    closed_legs: list[tuple[str, float, float, str]] = []  # (action, qty, price, session)

    for i in range(horizon):
        bar = forward_bars[i]
        session_index = i + 1  # 1-based sessions after entry

        # 5.0 step 1: intrabar price-level stop on the PRIOR session's close stop.
        if bar.low <= current_stop:
            exit_reason = "breakeven_stop" if current_stop >= entry_fill else "initial_stop"
            realized = {}
            terminal_legs_by_arm = {}
            for arm in BRACKET_ARMS:
                fill = price_stop_fill(arm, stop=current_stop, bar_open=bar.open)
                priced = [(q, p) for (_a, q, p, _s) in closed_legs] + \
                         [(shares_remaining, fill)]
                # FIXED denominator: rps * initial_shares (C2), NOT per-leg.
                realized[arm] = _r_for_legs(entry_fill, rps, shares, priced)
                terminal_legs_by_arm[arm] = fill
            legs = [Leg(a, q, p, s) for (a, q, p, s) in closed_legs]
            legs.append(Leg("exit", shares_remaining,
                            terminal_legs_by_arm["realistic"], bar.session))
            return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                             risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                             degenerate=False, exit_reason=exit_reason,
                             open_at_horizon=False, realized_r=realized,
                             holding_sessions=session_index, legs=legs,
                             terminal_fill=dict(terminal_legs_by_arm))  # m3: both arms

        # 5.0 step 2a: MA-trail close-below (evaluated BEFORE the partial; terminates EOD).
        closes_so_far = [b.close for b in forward_bars[: i + 1]]
        running_r = _running_r(entry_fill, rps, bar.close)
        period = _trail_ma_period(running_r, params)
        sma = _sma(closes_so_far, period)
        if sma is not None and bar.close < sma:
            # schedule a full exit at NEXT session open (5.6); Codex M2: if NO next session
            # exists (i+1 >= horizon), exit at the SIGNAL close instead -- this is a genuine
            # MA exit, NOT a censored open trade.
            if i + 1 < horizon:
                nxt = forward_bars[i + 1]
                next_open = nxt.open
                exit_session = nxt.session
                holding = i + 2
            else:
                next_open = bar.close          # M2 edge: no next open -> fill at signal close
                exit_session = bar.session
                holding = i + 1
            realized = {}
            terminal_by_arm = {}
            for arm in BRACKET_ARMS:
                fill = ma_exit_fill(arm, signal_close=bar.close, next_open=next_open)
                terminal_by_arm[arm] = fill
                priced = [(q, p) for (_a, q, p, _s) in closed_legs] + \
                         [(shares_remaining, fill)]
                realized[arm] = _r_for_legs(entry_fill, rps, shares, priced)
            legs = [Leg(a, q, p, s) for (a, q, p, s) in closed_legs]
            legs.append(Leg("exit", shares_remaining,
                            terminal_by_arm["realistic"], exit_session))
            return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                             risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                             degenerate=False, exit_reason="ma_close_below",
                             open_at_horizon=False, realized_r=realized,
                             holding_sessions=holding, legs=legs,
                             terminal_fill=dict(terminal_by_arm))  # m3: both arms

        # 5.0 step 2: EOD signals on bar.close, fixed order.
        # (b) Day-N partial; (c) breakeven.
        if (session_index == params.partial_session_n
                and bar.close > entry_fill and shares_remaining == params.initial_shares):
            qty = params.initial_shares * params.partial_pct
            closed_legs.append(("partial", qty, bar.close, bar.session))
            shares_remaining -= qty
        # (c) breakeven raise for NEXT session (5.4): once r_so_far >= trigger and stop<entry.
        if (_running_r(entry_fill, rps, bar.close) >= params.breakeven_r_trigger
                and current_stop < entry_fill):
            current_stop = entry_fill

    # horizon reached: open-at-horizon. Compute four censoring scenarios over the OPEN
    # remainder (D10 / Codex M3).
    last_close = forward_bars[horizon - 1].close if horizon else entry_fill
    realized = {}
    for arm in BRACKET_ARMS:
        priced = [(q, p) for (_a, q, p, _s) in closed_legs] + [(shares_remaining, last_close)]
        realized[arm] = _r_for_legs(entry_fill, rps, shares, priced)
    legs = [Leg(a, q, p, s) for (a, q, p, s) in closed_legs]
    legs.append(Leg("mtm", shares_remaining, last_close,
                    forward_bars[horizon - 1].session if horizon else entry_bar.session))

    def _scenarios():
        closed_priced = [(q, p) for (_a, q, p, _s) in closed_legs]
        # closed_only (PER-TRADE grain; m3): the realized R from THIS trade's already-closed
        # legs only (e.g. a Day-3 partial), dropping the still-open remainder. NOTE this is a
        # DIFFERENT grain from the scorecard's aggregate `closed_only` SCENARIO (Task 10),
        # which EXCLUDES a still-open trade entirely from the closed-only mean. Here we report
        # what this one open trade has realized so far; the scorecard chooses NOT to fold that
        # partial realization into its headline closed-only population. Same label, two grains
        # -- documented in both tasks (m3).
        closed_only = (_r_for_legs(entry_fill, rps, shares, closed_priced)
                       if closed_priced else 0.0)
        mtm = _r_for_legs(entry_fill, rps, shares,
                          closed_priced + [(shares_remaining, last_close)])
        # forced-exit at the next available open AFTER the horizon (5.7 / M3). If the log has
        # no post-horizon bar, collapse to MTM (last close) and annotate.
        if len(forward_bars) > horizon:
            forced_price = forward_bars[horizon].open
            collapsed = False
        else:
            forced_price = last_close
            collapsed = True
        forced = _r_for_legs(entry_fill, rps, shares,
                             closed_priced + [(shares_remaining, forced_price)])
        stop_adv = _r_for_legs(entry_fill, rps, shares,
                               closed_priced + [(shares_remaining, current_stop)])

        def arms(v):  # realistic == favorable for an open trade (5.8)
            return {"realistic": v, "favorable_reprice": v}
        return {
            "closed_only": arms(closed_only),
            "mtm_at_horizon": arms(mtm),
            "forced_exit_at_horizon_open": arms(forced),
            "stop_level_adverse": arms(stop_adv),
        }, collapsed
    scenarios, forced_collapsed = _scenarios()

    return SimResult(entry_fill=entry_fill, initial_stop=initial_stop, risk_per_share=rps,
                     entry_bar_ambiguous=ambiguous, degenerate=False,
                     exit_reason="horizon_mtm", open_at_horizon=True,
                     realized_r=realized, holding_sessions=horizon, legs=legs,
                     censoring_scenarios=scenarios,
                     forced_exit_collapsed_to_mtm=forced_collapsed)
