"""Stop adjust service — enforces trail-up invariant unless force=True."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from swing.data.repos.trades import get_trade, update_stop_with_event


class StopRegressionError(Exception):
    """Attempted to lower the stop without force=True."""


@dataclass(frozen=True)
class StopAdjustRequest:
    trade_id: int
    new_stop: float
    rationale: str
    event_ts: str
    force: bool = False
    notes: str | None = None


def adjust_stop(conn: sqlite3.Connection, req: StopAdjustRequest) -> None:
    trade = get_trade(conn, req.trade_id)
    if trade is None:
        raise ValueError(f"trade {req.trade_id} not found")
    if req.new_stop < trade.current_stop and not req.force:
        raise StopRegressionError(
            f"new stop ${req.new_stop:.2f} < current ${trade.current_stop:.2f}; use force=True"
        )
    if req.new_stop == trade.current_stop:
        return
    with conn:
        update_stop_with_event(
            conn, trade_id=req.trade_id, new_stop=req.new_stop,
            event_ts=req.event_ts, rationale=req.rationale,
            notes=req.notes,
        )
