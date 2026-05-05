"""Stop adjust service — enforces trail-up invariant unless force=True."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum

from swing.data.repos.trades import (
    get_trade,
)
from swing.data.repos.trades import (
    update_stop_with_event as repo_update_stop_with_event,
)
from swing.trades.state import state_transition


class StopAdjustRationale(str, Enum):  # noqa: UP042  (match ExitReason's (str, Enum) pattern)
    """Closed taxonomy for stop-adjust rationale (Tranche B-ops Bug 3a, spec §3).

    Values are persisted as plain strings in ``trade_events.rationale``;
    ``StopAdjustRequest.rationale`` stays typed as ``str`` and route/CLI
    layers convert via ``StopAdjustRationale(value)`` before constructing
    the request.

    Provenance (spec §3 table):

    * ``breakeven`` — repo: ``AdvisorySuggestion.rule == 'breakeven'``
      (``suggest_breakeven`` in ``swing.trades.advisory``).
    * ``trail-10ma`` — repo: ``AdvisorySuggestion.rule == 'trail_10ma'``
      (``suggest_trail_ma`` with the 10MA horizon).
    * ``trail-20ma`` — repo: ``AdvisorySuggestion.rule == 'trail_20ma'``.
    * ``weather-tighten`` — repo: ``AdvisorySuggestion.rule == 'weather'``
      combined with a tighten verb from ``suggest_weather_action``.
    * ``manual-trail`` — DELIBERATE EXPANSION. Operator-led tighten when no
      system advisory fired; covers 50MA-proximity tightens that do not
      warrant a full exit.
    * ``news`` — DELIBERATE EXPANSION. Company/sector news prompted the
      tighten; not a repo-derived string.
    * ``other`` — standard escape hatch; route/CLI require ``notes`` when selected.
    """

    BREAKEVEN = "breakeven"
    TRAIL_10MA = "trail-10ma"
    TRAIL_20MA = "trail-20ma"
    WEATHER_TIGHTEN = "weather-tighten"
    MANUAL_TRAIL = "manual-trail"
    NEWS = "news"
    OTHER = "other"


_STOP_ADJUST_RATIONALE_LABELS: dict[StopAdjustRationale, str] = {
    StopAdjustRationale.BREAKEVEN: "Move to breakeven (system advisory)",
    StopAdjustRationale.TRAIL_10MA: "Trail to 10MA (system advisory)",
    StopAdjustRationale.TRAIL_20MA: "Trail to 20MA (system advisory)",
    StopAdjustRationale.WEATHER_TIGHTEN: "Tighten on weather",
    StopAdjustRationale.MANUAL_TRAIL: "Manual trail (operator judgment)",
    StopAdjustRationale.NEWS: "News-driven tighten",
    StopAdjustRationale.OTHER: "Other (see notes)",
}


def stop_adjust_rationale_options() -> tuple[tuple[str, str], ...]:
    """Return ``(value, display_label)`` pairs in spec-declared order.

    Template layer consumes this to render the ``<select>`` options.
    """
    return tuple(
        (r.value, _STOP_ADJUST_RATIONALE_LABELS[r]) for r in StopAdjustRationale
    )


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


def update_stop_with_event(
    conn: sqlite3.Connection, *,
    trade_id: int,
    new_stop: float,
    event_ts: str,
    rationale: str | None = None,
    notes: str | None = None,
) -> None:
    """State-aware stop update.

    Rejects terminal/review states and auto-transitions entered trades to
    managing on the first stop adjustment.
    """
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")
    if trade.state not in ("entered", "managing", "partial_exited"):
        raise ValueError(f"trade {trade_id} is not active (state={trade.state!r})")

    with conn:
        repo_update_stop_with_event(
            conn,
            trade_id=trade_id,
            new_stop=new_stop,
            event_ts=event_ts,
            rationale=rationale,
            notes=notes,
        )
        if trade.state == "entered":
            state_transition(
                conn,
                trade_id=trade_id,
                new_state="managing",
                event_ts=event_ts,
                rationale=rationale,
            )


def adjust_stop(conn: sqlite3.Connection, req: StopAdjustRequest) -> None:
    trade = get_trade(conn, req.trade_id)
    if trade is None:
        raise ValueError(f"trade {req.trade_id} not found")
    # B.5: active-state guard fires BEFORE the trail-up regression check.
    # Rationale: trade-state validity is more fundamental than the domain-level
    # trail-up rule. A closed trade being "lowered" is two errors at once;
    # surfacing the state error first gives the operator the actionable signal
    # ("this trade is closed") rather than a misleading regression message.
    if trade.state not in ("entered", "managing", "partial_exited"):
        raise ValueError(
            f"trade {req.trade_id} is not active (state={trade.state!r})"
        )
    if req.new_stop < trade.current_stop and not req.force:
        raise StopRegressionError(
            f"new stop ${req.new_stop:.2f} < current ${trade.current_stop:.2f}; use force=True"
        )
    if req.new_stop == trade.current_stop:
        return
    # Delegate to the state-aware service: opens its own ``with conn:`` block
    # for atomic stop-write + entered→managing transition.
    update_stop_with_event(
        conn,
        trade_id=req.trade_id,
        new_stop=req.new_stop,
        event_ts=req.event_ts,
        rationale=req.rationale,
        notes=req.notes,
    )
