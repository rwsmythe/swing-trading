"""Trade exit service — writes a fill, drives the state machine.

Phase 7 Sub-B Task B.4 rewrite. The legacy ``Exit`` dataclass and the
``insert_exit_with_event`` repo helper are no longer consumed; both are
stubbed at the import surface and only retained for the remaining
out-of-carve-out callers (review_log, recommendations, pipeline, journal,
CLI, web). Exit-flow execution now goes through:

* ``swing.data.repos.fills.insert_fill_with_event`` — atomic fill INSERT
  + aggregate recompute (current_size denorm) + audit row.
* ``swing.trades.state.state_transition`` — atomic state UPDATE + audit row.

D79 (CHARC K1 (1)): ``record_exit`` OWNS its transaction. It REJECTS a
caller-held transaction (``CallerHeldTransactionError``; never auto-detects
and joins one), then opens ONE ``BEGIN IMMEDIATE`` inside which the trade is
read, the state and size are checked, and the fill, the note and the state
movement are written before a single ``COMMIT`` -- so a fill never lands
without its accompanying state movement (and vice versa), and every read the
write depends on is taken under the write lock. Any failure rolls back
through ``_rollback_or_raise`` (the S-D39 template in the D73 shape).
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from enum import StrEnum

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

log = logging.getLogger(__name__)


class ExitReason(StrEnum):
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
    # Phase 13 T3.SB2 T-B.2.3 — exit auto-fill audit columns persisted on
    # the fills row (per spec §6.2 + §6.4 + plan §G.5 T-B.2.3). Defaults
    # preserve legacy / CLI / bare-cURL callers that don't supply auto-
    # fill provenance.
    fill_origin: str = "operator_typed"
    schwab_source_value_json: str | None = None
    operator_corrected_value_json: str | None = None
    auto_fill_audit_at: str | None = None


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


def _normalize_trade_event_date_to_iso(raw: str, *, field_name: str = "date") -> str:
    """Validate + canonicalize a trade-event date string to ISO-8601 datetime.

    Codex R2 M1 + R3 M1 + R4 M1 + R5 m1 — accepts ``YYYY-MM-DD`` (synthesizes
    NYSE close ``T16:00:00``) or naive full ISO datetime
    ``YYYY-MM-DDTHH:MM[:SS][.ffffff]``. Rejects timezone-aware datetimes
    (would break lexicographic-ordering invariant) and malformed strings.
    Anything else raises ``ValueError`` BEFORE the fill is INSERTed,
    keeping ``fills.fill_datetime`` and ``trades.pre_trade_locked_at``
    invariant: every stored value is a parseable naive ISO datetime so
    ``substr(f.fill_datetime, 1, 10)`` (used by
    ``tos_import._find_unclaimed_recorded_exit``) always yields a real
    YYYY-MM-DD prefix and lexicographic ordering matches chronology.

    ``field_name`` is woven into error messages so operator-facing
    validation errors point at the actual offending CLI flag (Codex R5 m1).

    Used by ``swing.trades.exit.record_exit`` (with field_name='exit_date')
    and ``swing.trades.entry.record_entry`` (with field_name='entry_date',
    which additionally enforces date-only via a separate guard because
    trades.entry_date column is date-only and downstream consumers call
    date.fromisoformat on it).
    """
    from datetime import date, datetime
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{field_name} must be a non-empty string; got {raw!r}")
    if "T" in raw:
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} {raw!r} contains 'T' but is not a valid ISO datetime"
            ) from exc
        # Codex R3 Major 1: reject tz-aware datetimes. Storing offset-bearing
        # values would break the lexicographic-ordering invariant that
        # fills.py:list_fills_for_trade ORDER BY relies on, and tos_import's
        # substr(fill_datetime, 1, 10) date prefix becomes ambiguous.
        if parsed.tzinfo is not None:
            raise ValueError(
                f"{field_name} {raw!r} is timezone-aware; Phase 7 stores naive "
                f"ISO datetimes — strip the offset before persisting"
            )
        return raw
    try:
        date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} {raw!r} is not a valid YYYY-MM-DD or ISO datetime"
        ) from exc
    return f"{raw}T16:00:00"


class ExitPriceRefusedError(ValueError):
    """22-F C1-24: an exit price the ``fills.price`` column would refuse.

    Raised by ``record_exit`` BEFORE any statement, for exactly the column's
    refusal set -- ``<= 0`` (the CHECK) and NaN (the NOT NULL) -- so the
    operator gets a typed refusal instead of an ``IntegrityError`` at the
    INSERT. A ``ValueError`` subclass, so the existing ``except ValueError``
    delivery at the web exit POST and the CLI ``trade exit`` reaches it with
    no new clause. The CHECK stays the backstop.
    """


class CallerHeldTransactionError(RuntimeError):
    """D79 (CHARC K1 (1)): ``record_exit`` was called while the caller holds
    an open transaction.

    The single-transaction contract REJECTS a caller-held transaction rather
    than auto-detecting and joining it (CLAUDE.md: the auto-detect guard
    re-introduces the race the explicit lock closed). A ``RuntimeError``, NOT
    a ``ValueError``: it is a programming error, not an operator refusal, so
    neither caller's ``except ValueError`` re-render reaches it. Both
    production callers enter with no open transaction, which a test pins.
    """


def _rollback_or_raise(conn: sqlite3.Connection, op: str,
                       original: BaseException) -> None:
    """Roll back only an open transaction; a rollback that ALSO fails is
    raised CHAINED, with ONE ERROR record naming both errors and the discard.

    The S-D39 template (``account_equity_snapshots._rollback_or_raise``, the
    22-A template) in **the D73 shape (2026-10-18)**: with an INTERRUPT in
    flight (``original`` is not an ``Exception``) THE INTERRUPT PROPAGATES and
    the cleanup failure rides as its explicit cause, so an outer ``except
    Exception`` can never contain the operator's stop signal wearing an
    ``OperationalError``. With an ordinary error in flight the cleanup error
    propagates, chained from the original, as before. Neither is ever
    swallowed; the ERROR record is what makes the double failure loud.
    """
    if not conn.in_transaction:
        return
    try:
        conn.rollback()
    except BaseException as cleanup_error:  # noqa: BLE001 -- the CLASS
        from swing.trades.entry import log_contained_note
        interrupted = not isinstance(original, Exception)
        still = conn.in_transaction
        log_contained_note(
            log, original if interrupted else cleanup_error,
            "D79: %s failed (%s) AND the rollback of its transaction failed "
            "(%s); in_transaction reads %s after the failed rollback; this "
            "connection MUST BE DISCARDED either way.",
            op, original, cleanup_error, still)
        if interrupted:
            raise original from cleanup_error
        raise cleanup_error from original


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

    Transaction (D79, CHARC K1 (1)): a caller-held transaction is REJECTED
    as the first statement, before any read. The pure argument checks run
    next and read nothing. Then ONE ``BEGIN IMMEDIATE`` is taken, and the
    trade read, the state and size checks, the writes and the ``COMMIT`` all
    run under it; a refusal raised there (not found / not active / exceeds)
    still propagates as the same ``ValueError`` after a clean rollback.
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "record_exit owns its transaction; it was called while the "
            "caller holds an open transaction (commit or roll it back first)"
        )
    if not isinstance(req.reason, ExitReason):
        raise ValueError(f"invalid exit reason: {req.reason}")
    if req.shares <= 0:
        raise ValueError(f"shares must be > 0; got {req.shares}")
    if not (req.exit_price > 0):
        raise ExitPriceRefusedError(
            f"exit price must be > 0; got {req.exit_price!r}"
        )

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
    fill_datetime = _normalize_trade_event_date_to_iso(
        req.exit_date, field_name="exit_date",
    )
    # D79 (CHARC K1 (1)): ONE owned transaction. BEGIN is INSIDE the try so a
    # BEGIN that fails (busy) is handled like any other failure; every read
    # the write depends on -- the trade's state and size -- is taken AFTER the
    # write lock is held, so no concurrent writer can commit between the read
    # and the INSERT (the VISIBILITY precondition of CHARC's K1 packet).
    try:
        conn.execute("BEGIN IMMEDIATE")
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

        fill = Fill(
            fill_id=None,
            trade_id=req.trade_id,
            fill_datetime=fill_datetime,
            action=action,
            quantity=float(req.shares),
            price=float(req.exit_price),
            reason=req.reason.value,
            # Phase 13 T3.SB2 T-B.2.3 — exit auto-fill provenance audit columns.
            # ExitRequest defaults preserve legacy operator_typed / NULL behavior
            # for CLI / bare-cURL callers; web POST handler populates these from
            # the form-render hidden anchor + operator-selection round-trip.
            fill_origin=req.fill_origin,
            schwab_source_value_json=req.schwab_source_value_json,
            operator_corrected_value_json=req.operator_corrected_value_json,
            auto_fill_audit_at=req.auto_fill_audit_at,
        )

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
        conn.commit()
    except BaseException as exc:  # noqa: BLE001 -- the CLASS (S-D39 / D73)
        _rollback_or_raise(conn, "record_exit", exc)
        raise

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
