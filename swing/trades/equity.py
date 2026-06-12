"""Pure functions: equity, R-multiple, position sizing helpers (legacy parity)."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from swing.data.models import CashMovement, Trade

# C.14: ``Exit`` is deleted. Function signatures here use ``Iterable[Any]``
# for the exits parameter — consumers pass duck-typed ExitLike-shape objects
# (the per-module ``_ExitShape`` adapter pattern from C.1/C.9/C.10/C.14)
# which expose ``.realized_pnl``, ``.shares``, ``.trade_id`` — all that
# ``current_equity`` / ``shares_remaining`` / ``total_current_risk`` require.
ExitLike = Any  # Structural duck-type alias for Exit-shape adapter rows.


# Migration 0029 widened cash_movements.kind to 5 values. interest/dividend ADD
# to net cash (income); withdraw/fee SUBTRACT. An unknown kind now RAISES (the
# pre-0029 silent-ignore was the drift hazard).
_CASH_ADD_KINDS = frozenset({"deposit", "interest", "dividend"})
_CASH_SUB_KINDS = frozenset({"withdraw", "fee"})


def net_cash_movements(cash_movements: Iterable[CashMovement]) -> float:
    total = 0.0
    for c in cash_movements:
        if c.kind in _CASH_ADD_KINDS:
            total += c.amount
        elif c.kind in _CASH_SUB_KINDS:
            total -= c.amount
        else:
            raise ValueError(
                f"unknown cash kind {c.kind!r} in net_cash_movements"
            )
    return total


def current_equity(
    *, starting_equity: float, exits: Iterable[ExitLike],
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


def shares_remaining(trade: Trade, exits: Iterable[ExitLike]) -> int:
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
    trades: Iterable[Trade], exits: Iterable[ExitLike],
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


# ---------------------------------------------------------------------------
# Exits adapter (lifted from swing/web/view_models/dashboard.py, Arc 4b Task 4).
# Single home for the fills-derived ExitLike collection that current_equity /
# total_current_risk consume. dashboard.py + the schwab equity-coherence check
# (Task 8) both import the SHARED ``list_all_exitshape_via_fills`` rather than
# duplicating it (the Arc-6 shared-predicate lesson: two impls WILL diverge).
# Internal repo imports stay LAZY (inside the function body) so equity.py keeps
# its current import surface and never cycles with swing.data.repos / swing.web.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ExitShape:
    """Local adapter mirroring legacy Exit shape for ExitLike-consuming APIs
    (current_equity, total_current_risk, dashboard remaining-shares grouping).
    Single source of math truth: swing.trades.derived_metrics."""
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None


def list_all_exitshape_via_fills(conn) -> list[_ExitShape]:
    """Produce the ExitLike collection sourced from ``fills`` filtered to
    non-entry actions. Per-fill realized_pnl + r derive on the fly from the
    parent trade's entry_price/initial_stop via ``swing.trades.derived_metrics``
    — single source of math truth. Sort matches the legacy shim:
    (fill_datetime ASC, fill_id ASC) by way of ``list_all_fills``'s ORDER BY.
    """
    from swing.data.repos.fills import list_all_fills
    from swing.data.repos.trades import list_closed_trades, list_open_trades
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
