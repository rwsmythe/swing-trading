"""Trade exit service — computes pnl + R, delegates to repo for atomic write."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum

from swing.data.models import Exit
from swing.data.repos.trades import (
    get_trade, insert_exit_with_event, list_exits_for_trade,
)


class ExitReason(str, Enum):
    STOP_HIT = "stop-hit"
    TARGET = "target"
    MANUAL = "manual"
    TIME_STOP = "time-stop"
    WEATHER = "weather"
    PARTIAL = "partial"
    OTHER = "other"


@dataclass(frozen=True)
class ExitRequest:
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: ExitReason
    notes: str | None
    rationale: str
    event_ts: str


@dataclass(frozen=True)
class ExitResult:
    exit_id: int
    realized_pnl: float
    r_multiple: float
    fully_closed: bool


def record_exit(conn: sqlite3.Connection, req: ExitRequest) -> ExitResult:
    if not isinstance(req.reason, ExitReason):
        raise ValueError(f"invalid exit reason: {req.reason}")
    if req.shares <= 0:
        raise ValueError(f"shares must be > 0; got {req.shares}")

    trade = get_trade(conn, req.trade_id)
    if trade is None:
        raise ValueError(f"trade {req.trade_id} not found")

    pnl_per_share = req.exit_price - trade.entry_price
    realized_pnl = pnl_per_share * req.shares
    rps = trade.entry_price - trade.initial_stop
    r_multiple = pnl_per_share / rps if rps > 0 else 0.0

    exit_row = Exit(
        id=None, trade_id=req.trade_id, exit_date=req.exit_date,
        exit_price=req.exit_price, shares=req.shares,
        reason=req.reason.value, realized_pnl=realized_pnl,
        r_multiple=r_multiple, notes=req.notes,
    )

    sold_before = sum(e.shares for e in list_exits_for_trade(conn, req.trade_id))
    fully_closed = (sold_before + req.shares) == trade.initial_shares

    with conn:
        exit_id = insert_exit_with_event(
            conn, exit_row, event_ts=req.event_ts, rationale=req.rationale,
        )

    return ExitResult(
        exit_id=exit_id, realized_pnl=realized_pnl,
        r_multiple=r_multiple, fully_closed=fully_closed,
    )
