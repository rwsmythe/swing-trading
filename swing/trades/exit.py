"""Trade exit service — writes a fill, drives the state machine.

Phase 7 Sub-B Task B.4 rewrite. The legacy ``Exit`` dataclass and the
``insert_exit_with_event`` repo helper are no longer consumed; both are
stubbed at the import surface and only retained for the remaining
out-of-carve-out callers (review_log, recommendations, pipeline, journal,
CLI, web). Exit-flow execution now goes through:

* ``swing.data.repos.fills.insert_fill_with_event`` — atomic fill INSERT
  + aggregate recompute (current_size denorm) + audit row.
* ``swing.trades.state.state_transition`` — atomic state UPDATE + audit row.

Both are wrapped in the SAME ``with conn:`` so a fill never lands without
its accompanying state movement (and vice versa).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum

from swing.data.models import Fill
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import add_note_event, get_trade
from swing.trades.derived_metrics import (
    initial_risk_per_share as compute_initial_risk_per_share,
)
from swing.trades.derived_metrics import (
    r_multiple as compute_r_multiple,
)
from swing.trades.derived_metrics import (
    realized_pnl as compute_realized_pnl,
)
from swing.trades.state import state_transition


class ExitReason(str, Enum):
    STOP_HIT = "stop-hit"
    TARGET = "target"
    MANUAL = "manual"
    TIME_STOP = "time-stop"
    WEATHER = "weather"
    PARTIAL = "partial"
    OTHER = "other"


# States in which an exit fill is permitted. Closed/reviewed are terminal.
_ACTIVE_STATES: frozenset[str] = frozenset({"entered", "managing", "partial_exited"})


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
    """Return shape of ``record_exit``.

    ``exit_id`` is the new ``fills.fill_id`` (callers comparing against the
    legacy ``exits.id`` int continue to work — both are sqlite ROWIDs).
    """
    exit_id: int
    realized_pnl: float
    r_multiple: float
    fully_closed: bool


def _normalize_exit_date_to_iso(raw: str) -> str:
    """Validate + canonicalize ``req.exit_date`` to ISO-8601 datetime form.

    Codex R2 Major 1 — accepts ``YYYY-MM-DD`` (synthesizes NYSE close
    ``T16:00:00``) or full ISO datetime ``YYYY-MM-DDTHH:MM[:SS][.ffffff]``.
    Anything else raises ``ValueError`` BEFORE the fill is INSERTed,
    keeping ``fills.fill_datetime`` invariant: every stored value is a
    parseable ISO datetime so ``substr(f.fill_datetime, 1, 10)`` (used by
    ``tos_import._find_unclaimed_recorded_exit``) always yields a real
    YYYY-MM-DD prefix and lexicographic ordering matches chronology.
    """
    from datetime import date, datetime
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"exit_date must be a non-empty string; got {raw!r}")
    if "T" in raw:
        try:
            datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(
                f"exit_date {raw!r} contains 'T' but is not a valid ISO datetime"
            ) from exc
        return raw
    try:
        date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            f"exit_date {raw!r} is not a valid YYYY-MM-DD or ISO datetime"
        ) from exc
    return f"{raw}T16:00:00"


def record_exit(conn: sqlite3.Connection, req: ExitRequest) -> ExitResult:
    """Write an exit/trim/stop fill and drive the state machine.

    Action selection:
      * reason == STOP_HIT  → ``'stop'``
      * remaining shares > 0 → ``'trim'``
      * else                  → ``'exit'``

    State movement (driven by ``(current_state, new_size)``):
      * entered + new_size == 0  → managing → closed (double-step; spec §3.3)
      * entered + new_size > 0   → managing → partial_exited
      * managing + new_size == 0 → closed
      * managing + new_size > 0  → partial_exited
      * partial_exited + new_size == 0 → closed
      * partial_exited + new_size > 0  → (no transition; stays partial_exited)
    """
    if not isinstance(req.reason, ExitReason):
        raise ValueError(f"invalid exit reason: {req.reason}")
    if req.shares <= 0:
        raise ValueError(f"shares must be > 0; got {req.shares}")

    trade = get_trade(conn, req.trade_id)
    if trade is None:
        raise ValueError(f"trade {req.trade_id} not found")
    if trade.state not in _ACTIVE_STATES:
        raise ValueError(
            f"trade {req.trade_id} not active (state={trade.state!r}); "
            f"exits only permitted from {sorted(_ACTIVE_STATES)}"
        )

    new_size = float(trade.current_size) - float(req.shares)
    if new_size < 0:
        raise ValueError(
            f"exit shares {req.shares} exceeds remaining current_size "
            f"{trade.current_size}"
        )

    # Action computation. STOP_HIT always wins; otherwise size-driven.
    if req.reason == ExitReason.STOP_HIT:
        action = "stop"
    elif new_size > 0:
        action = "trim"
    else:
        action = "exit"

    # Codex R1 Major 1: fill_datetime must reflect when the EXIT happened
    # (req.exit_date), not when the operator typed the command (req.event_ts).
    # CLI sends event_ts=now, so an exit recorded for a past session would
    # otherwise land at today's clock-time and break tos_import reconciliation
    # (substr(f.fill_datetime, 1, 10) match) + journal close-date aggregation.
    # Codex R2 Major 1: validate the exit_date format before persisting.
    # Pre-R2 the helper trusted any string containing "T" as ISO datetime,
    # so "2026-05-02TNOT_A_TIME" silently stored as garbage and broke
    # downstream substr-date matching. Now: parse strictly via fromisoformat
    # for both YYYY-MM-DD and YYYY-MM-DDTHH:MM[:SS] forms; reject otherwise.
    fill_datetime = _normalize_exit_date_to_iso(req.exit_date)
    fill = Fill(
        fill_id=None,
        trade_id=req.trade_id,
        fill_datetime=fill_datetime,
        action=action,
        quantity=float(req.shares),
        price=float(req.exit_price),
        reason=req.reason.value,
    )

    with conn:
        fill_id = insert_fill_with_event(
            conn, fill, event_ts=req.event_ts, rationale=req.rationale,
        )
        # Codex R1 Major 2: req.notes was silently dropped post-Phase-7. The
        # legacy Exit dataclass had a notes column; fills schema does not.
        # Persist operator notes via a parallel 'note' trade_event so the
        # information survives the data-model migration.
        if req.notes is not None and req.notes.strip():
            add_note_event(
                conn, trade_id=req.trade_id, event_ts=req.event_ts,
                note=req.notes.strip(), rationale=req.rationale,
            )
        # Drive state transition by (current_state, new_size). Spec §3.3:
        # same-day stop-out from 'entered' MUST step through 'managing' —
        # entered→closed is not in ALLOWED_TRANSITIONS. The double-step is
        # intentional and audit-visible (two trade_events rows).
        current_state = trade.state
        if current_state == "entered" and new_size == 0:
            state_transition(
                conn, trade_id=req.trade_id, new_state="managing",
                event_ts=req.event_ts, rationale=req.rationale,
            )
            state_transition(
                conn, trade_id=req.trade_id, new_state="closed",
                event_ts=req.event_ts, rationale=req.rationale,
            )
        elif current_state == "entered" and new_size > 0:
            state_transition(
                conn, trade_id=req.trade_id, new_state="managing",
                event_ts=req.event_ts, rationale=req.rationale,
            )
            state_transition(
                conn, trade_id=req.trade_id, new_state="partial_exited",
                event_ts=req.event_ts, rationale=req.rationale,
            )
        elif current_state == "managing" and new_size == 0:
            state_transition(
                conn, trade_id=req.trade_id, new_state="closed",
                event_ts=req.event_ts, rationale=req.rationale,
            )
        elif current_state == "managing" and new_size > 0:
            state_transition(
                conn, trade_id=req.trade_id, new_state="partial_exited",
                event_ts=req.event_ts, rationale=req.rationale,
            )
        elif current_state == "partial_exited" and new_size == 0:
            state_transition(
                conn, trade_id=req.trade_id, new_state="closed",
                event_ts=req.event_ts, rationale=req.rationale,
            )
        # partial_exited + new_size > 0: stays partial_exited (no transition).

    # Compute derived metrics for the return value (post-commit; pure math).
    pnl = compute_realized_pnl(
        entry_price=trade.entry_price,
        exit_price=req.exit_price,
        quantity=req.shares,
    )
    rps = compute_initial_risk_per_share(
        entry_price=trade.entry_price,
        initial_stop=trade.initial_stop,
    )
    if rps > 0:
        rmult = compute_r_multiple(
            realized_pnl=pnl,
            initial_risk_per_share=rps,
            quantity=req.shares,
        )
    else:
        rmult = 0.0
    fully_closed = (new_size == 0)

    return ExitResult(
        exit_id=fill_id,
        realized_pnl=pnl,
        r_multiple=rmult,
        fully_closed=fully_closed,
    )
