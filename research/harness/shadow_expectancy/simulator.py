from __future__ import annotations

from dataclasses import dataclass, field

from research.harness.shadow_expectancy.bracket import price_stop_fill
from research.harness.shadow_expectancy.constants import BRACKET_ARMS
from research.harness.shadow_expectancy.io import Bar
from swing.trades.derived_metrics import (
    initial_risk_per_share, r_multiple, realized_pnl,
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


def simulate(*, pivot, entry_bar: Bar, forward_bars, params: SimParams):
    # C1 / spec 5.2 / D6: the MECHANICAL initial stop is the entry bar's low-of-day,
    # derived internally -- NOT passed from the candidate. risk_per_share = entry_fill
    # - entry_bar.low; degenerate gate = entry_fill <= entry_bar.low.
    entry_fill = _entry_fill(pivot, entry_bar)
    initial_stop = entry_bar.low
    rps = initial_risk_per_share(entry_price=entry_fill, initial_stop=initial_stop)
    ambiguous = entry_bar.low < entry_fill
    if entry_fill <= initial_stop:  # spec 5.2 / D6 -> non-positive denominator
        return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                         risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                         degenerate=True, exit_reason="degenerate_risk",
                         open_at_horizon=False, realized_r=None)
    current_stop = initial_stop
    shares = params.initial_shares
    horizon = min(params.horizon_sessions, len(forward_bars))
    # Core (Task 7): stop test only. Partial/breakeven/MA land in Tasks 8-9.
    for i in range(horizon):
        bar = forward_bars[i]
        # 5.0 precedence step 1: intrabar price-level stop test on prior close stop.
        if bar.low <= current_stop:
            realized = {}
            terminal_by_arm = {}
            for arm in BRACKET_ARMS:
                fill = price_stop_fill(arm, stop=current_stop, bar_open=bar.open)
                terminal_by_arm[arm] = fill
                realized[arm] = _r_for_legs(entry_fill, rps, shares, [(shares, fill)])
            return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                             risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                             degenerate=False, exit_reason="initial_stop",
                             open_at_horizon=False, realized_r=realized,
                             holding_sessions=i + 1,
                             legs=[Leg("exit", shares, terminal_by_arm["realistic"],
                                       bar.session)],
                             terminal_fill=dict(terminal_by_arm))
    # Reached horizon with no exit -> open-at-horizon (scenarios computed in scorecard;
    # Task 9 fills the four censoring numbers). Placeholder MTM for the core task.
    last_close = forward_bars[horizon - 1].close if horizon else entry_fill
    realized = {arm: _r_for_legs(entry_fill, rps, shares, [(shares, last_close)])
                for arm in BRACKET_ARMS}
    return SimResult(entry_fill=entry_fill, initial_stop=initial_stop, risk_per_share=rps,
                     entry_bar_ambiguous=ambiguous, degenerate=False,
                     exit_reason="horizon_mtm", open_at_horizon=True,
                     realized_r=realized, holding_sessions=horizon)
