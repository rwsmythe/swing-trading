"""Pure functions: equity, R-multiple, position sizing helpers (legacy parity)."""
from __future__ import annotations

from typing import Iterable

from swing.data.models import CashMovement, Exit, Trade


def net_cash_movements(cash_movements: Iterable[CashMovement]) -> float:
    total = 0.0
    for c in cash_movements:
        if c.kind == "deposit":
            total += c.amount
        elif c.kind == "withdraw":
            total -= c.amount
    return total


def current_equity(
    *, starting_equity: float, exits: Iterable[Exit],
    cash_movements: Iterable[CashMovement],
) -> float:
    """starting + realized P&L + net cash. Excludes unrealized P&L."""
    realized = sum(e.realized_pnl for e in exits)
    return starting_equity + realized + net_cash_movements(cash_movements)


def sizing_equity(*, real_equity: float, floor: float) -> float:
    """Sizing uses max(real, floor) so a $1.2k account sizes against a wider
    risk aperture; broker cash still caps actual fills."""
    if floor > 0 and real_equity < floor:
        return floor
    return real_equity


def shares_remaining(trade: Trade, exits: Iterable[Exit]) -> int:
    sold = sum(e.shares for e in exits if e.trade_id == trade.id)
    return trade.initial_shares - sold


def risk_per_share(trade: Trade) -> float:
    rps = trade.entry_price - trade.initial_stop
    return rps if rps > 0 else 0.0


def r_so_far(trade: Trade, current_price: float) -> float:
    rps = risk_per_share(trade)
    if rps <= 0:
        return 0.0
    return (current_price - trade.entry_price) / rps


def total_current_risk(
    trades: Iterable[Trade], exits: Iterable[Exit],
) -> tuple[float, int, bool]:
    """Σ max(0, shares_remaining × (entry_price − current_stop)) across trades.

    Returns (dollars_at_risk, contributing_count, all_above_breakeven).
    Positions whose stop ≥ entry contribute $0 (locked-in non-loss). Partial
    exits reduce `shares_remaining`. See Tranche B-ops session-1 spec §2.
    """
    trade_list = list(trades)
    exit_list = list(exits)
    dollars = 0.0
    contributing = 0
    for t in trade_list:
        remaining = shares_remaining(t, exit_list)
        risk_per_share_left = t.entry_price - t.current_stop
        if risk_per_share_left <= 0 or remaining <= 0:
            continue
        dollars += remaining * risk_per_share_left
        contributing += 1
    all_above_be = bool(trade_list) and contributing == 0
    return dollars, contributing, all_above_be
