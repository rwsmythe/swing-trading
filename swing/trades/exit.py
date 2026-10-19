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
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from swing.data.models import Fill, Trade
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
from swing.trades.latched_origin import (
    ENVELOPE_REFUSED,
    canonical_envelope_identity,
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

    Raised by ``check_exit_preconditions`` BEFORE the INSERT (inside
    ``record_exit`` that is under its write lock, after ``BEGIN IMMEDIATE``
    and the trade read -- D79 executing FORK 1), for exactly the column's
    refusal set -- ``<= 0`` (the CHECK) and NaN (the NOT NULL) -- so the
    operator gets a typed refusal instead of an ``IntegrityError`` at the
    INSERT. A ``ValueError`` subclass, so the existing ``except ValueError``
    delivery at the web exit POST and the CLI ``trade exit`` reaches it with
    no new clause. The CHECK stays the backstop.
    """


class ExitOrderAlreadyRecordedError(ValueError):
    """D79 (CHARC K1 (3); RD K2): the submitted broker order id is already
    recorded on a non-entry fill -- on ANY trade (RD K7.1, the id is global
    at the broker).

    Raised by ``record_exit`` UNDER its write lock, so two concurrent
    submissions of one order cannot both pass. A ``ValueError`` subclass, so
    the existing ``except ValueError`` delivery at the web exit POST and the
    CLI ``trade exit`` reaches it with no new clause. There is NO override:
    no confirmation reaches past it (RD K3 precondition 3; orchestrator K5).
    """


class ExitEnvelopeUnreadableError(ValueError):
    """D79 (CHARC FORK 2, F2-(iii)): the SUBMITTED Schwab envelope is one the
    authority (``canonical_envelope_identity``) REFUSES -- undecodable, a
    padded or blank order id, a duplicated key.

    Raised BEFORE ``BEGIN``: the request's own claim cannot be read, so
    nothing is written (the NO branch of the ENTRY-vs-LABEL test). The
    message names the recovery. A ``ValueError`` subclass, like its
    siblings.
    """


#: The refusal texts, ASCII by construction (they reach CLI stdout).
_ALREADY_RECORDED_TEXT = (
    "Order {order} is already recorded as fill(s) {fills} on trade {trades}; "
    "it cannot be recorded again."
)
_ANOMALY_TEXT = (
    " The submitted values differ from that record -- correct fill {fills} "
    "instead of recording again."
)
_ENVELOPE_UNREADABLE_TEXT = (
    "The Schwab auto-fill envelope submitted with this exit cannot be read "
    "(its order id is malformed, padded or duplicated), so it cannot be "
    "recorded; re-open the exit form to get a fresh Schwab auto-fill."
)


@dataclass(frozen=True)
class RecordedExitFill:
    """One recorded non-entry fill, as the identity reader returns it: the
    row's id, its trade, and the STORED values (``date`` is
    ``str(fill_datetime)[:10]``) the anomaly comparison needs, so nothing
    issues a second query.

    ``price`` and ``quantity`` are ``None`` when the stored value does not
    convert to a float (Reviewer A R2, RA-01). The 0014 columns are
    ``REAL NOT NULL CHECK (> 0)``, which a TEXT value satisfies (it compares
    greater than any number), so the reader cannot assume a float. A ``None``
    never derives (``exit_auto_fill.derives_from``), and the row keeps its
    place in the identity result either way."""

    fill_id: int
    trade_id: int
    date: str
    price: float | None
    quantity: float | None


def _stored_number(value: object) -> float | None:
    """A stored ``fills`` price or quantity as a float, or ``None`` when it
    does not convert (RA-01)."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class RecordedExitIdentities:
    """What ``recorded_exit_identities`` read: the linked rows grouped by the
    authority's broker order id, and the rows whose envelope it REFUSED."""

    by_order_id: Mapping[str, tuple[RecordedExitFill, ...]]
    unreadable: tuple[RecordedExitFill, ...]


def recorded_exit_identities(conn: sqlite3.Connection) -> RecordedExitIdentities:
    """THE ONE READER of recorded exit identities (D79; RD K2, K7.1; CHARC
    K1 (2)). The service guard, the exit form's offer list and the route's
    unreadable-envelope flag all import it; nothing re-reads an exit
    envelope's id anywhere else.

    GLOBAL: every non-entry fill on every trade (no ``trade_id`` predicate),
    because a broker order id is global. Each RAW envelope is read through
    ``canonical_envelope_identity`` -- never the stored 22-A reading (13 of 19
    exit fills have none) and never SQL ``json_extract`` (a different reader).
    A ``refused`` reading goes to ``unreadable``; a canonical id groups under
    ``by_order_id`` (a SET per id: the split handler legitimately writes one
    id onto N rows); a canonical document naming no order goes to neither.

    THE NULL CASE (CHARC P1, text correction (a)): a row whose envelope is
    NULL is neither linked nor unreadable, and the ``IS NOT NULL`` filter
    excludes it. ``exit_auto_fill.anonymous_fill_matches`` treats the same
    NULL as ANONYMOUS. The two readers agree: a NULL envelope names no order.

    Linear in non-entry fills with no cache and no index (AL-9, CHARC P1's
    noted cost; revisit when they reach the low thousands).

    Read-only. Inside ``record_exit`` it runs AFTER ``BEGIN IMMEDIATE`` on the
    writer's own connection, which is admissible only because the write lock
    is already held.
    """
    rows = conn.execute(
        "SELECT fill_id, trade_id, fill_datetime, price, quantity, "
        "schwab_source_value_json FROM fills "
        "WHERE action != 'entry' AND schwab_source_value_json IS NOT NULL "
        "ORDER BY fill_id"
    ).fetchall()
    by_order_id: dict[str, list[RecordedExitFill]] = {}
    unreadable: list[RecordedExitFill] = []
    for fill_id, trade_id, fill_datetime, price, quantity, raw in rows:
        # THE IDENTITY FIRST, THEN THE VALUES, AND NO VALUE CAN RAISE
        # (Reviewer A R2, RA-01). This reader is GLOBAL: one row on any trade
        # whose stored price or quantity does not convert would otherwise
        # raise out of every exit-form render, exit POST and confirm, and a
        # linked exit would roll back instead of being refused as already
        # recorded. Such a row still groups under its id (or under
        # ``unreadable``); only its values are ``None``.
        identity = canonical_envelope_identity(raw)
        recorded = RecordedExitFill(
            fill_id=int(fill_id), trade_id=int(trade_id),
            date=str(fill_datetime)[:10], price=_stored_number(price),
            quantity=_stored_number(quantity),
        )
        if identity.state == ENVELOPE_REFUSED:
            unreadable.append(recorded)
        elif identity.broker_order_id is not None:
            by_order_id.setdefault(identity.broker_order_id, []).append(
                recorded)
    return RecordedExitIdentities(
        by_order_id=MappingProxyType(
            {k: tuple(v) for k, v in by_order_id.items()}),
        unreadable=tuple(unreadable),
    )


def _already_recorded_message(order_id: str,
                              hits: tuple[RecordedExitFill, ...], *,
                              exit_date: str, exit_price: float,
                              shares: int) -> str:
    """The (a) refusal, naming ALL N rows and their trade(s), plus RD K2's
    instrument-anomaly sentence when the request's values derive from NONE
    of them (compared at the ONE grain, ``exit_auto_fill.derives_from``)."""
    from swing.trades.exit_auto_fill import derives_from

    fills = ", ".join(f"#{h.fill_id}" for h in hits)
    trades = ", ".join(f"#{t}" for t in sorted({h.trade_id for h in hits}))
    message = _ALREADY_RECORDED_TEXT.format(
        order=order_id, fills=fills, trades=trades)
    if not any(
        derives_from(
            {"date": h.date, "price": h.price, "quantity": h.quantity},
            exit_date=exit_date, exit_price=exit_price, shares=shares,
        )
        for h in hits
    ):
        message += _ANOMALY_TEXT.format(fills=fills)
    return message


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


def check_exit_preconditions(trade: Trade | None, req: ExitRequest) -> None:
    """The six refusals of an exit request, PURE (D79 executing FORK 1,
    CHARC: A1, the helper pure).

    Raises, in this order and with these texts: an invalid reason; shares
    ``<= 0``; ``ExitPriceRefusedError`` (``<= 0`` or NaN -- the ``fills.price``
    column's refusal set); the trade not found; the trade not active; the
    shares exceeding its remaining ``current_size``. Each is a ``ValueError``,
    so both callers' existing ``except ValueError`` delivery reaches it.

    It takes the trade ROW and the request and performs NO read: it cannot
    be the barrier and cannot drift from it. ``record_exit`` calls it on the
    row it reads UNDER its write lock -- that call is the barrier. The web
    exit POST calls it earlier, on a row read outside any lock, only to ORDER
    a refusal that does not depend on the operator's answer BEFORE the F1
    question (a refusal precedes the question it would make moot).
    """
    if not isinstance(req.reason, ExitReason):
        raise ValueError(f"invalid exit reason: {req.reason}")
    if req.shares <= 0:
        raise ValueError(f"shares must be > 0; got {req.shares}")
    if not (req.exit_price > 0):
        raise ExitPriceRefusedError(
            f"exit price must be > 0; got {req.exit_price!r}"
        )
    if trade is None:
        raise ValueError(f"trade {req.trade_id} not found")
    if trade.state not in _ACTIVE_STATES:
        raise ValueError(
            f"trade {req.trade_id} not active (state={trade.state!r}); "
            f"exits only permitted from {sorted(_ACTIVE_STATES)}"
        )
    if float(trade.current_size) - float(req.shares) < 0:
        raise ValueError(
            f"exit shares {req.shares} exceeds remaining current_size "
            f"{trade.current_size}"
        )


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

    Transaction (D79, CHARC K1 (1); executing FORK 1): a caller-held
    transaction is REJECTED as the first statement, before any read. The
    exit date is normalised and the SUBMITTED envelope is read through the
    authority before ``BEGIN`` (an unreadable one is refused there, CHARC
    FORK 2 F2-(iii)). Then ONE ``BEGIN IMMEDIATE`` is taken, and the trade
    read, ``check_exit_preconditions`` (all six refusals, one spelling), the
    identity guard, the writes and the ``COMMIT`` all run under it; a refusal
    raised there propagates as the same ``ValueError`` after a clean
    rollback. ACCEPTED COST (CHARC's ruling): a request refused on its
    arguments alone now takes one ``BEGIN IMMEDIATE`` / ``ROLLBACK`` first --
    nothing on a single-operator DB, where a second spelling of the checks
    is not. A consequence of the same order: a request with BOTH a bad
    argument and an unreadable envelope is refused for the envelope.
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "record_exit owns its transaction; it was called while the "
            "caller holds an open transaction (commit or roll it back first)"
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
    # D79 (CHARC FORK 2, F2-(iii)): the SUBMITTED envelope is read through the
    # ONE authority BEFORE BEGIN. A reading it REFUSES is the request's own
    # claim being unreadable, so nothing is written. A canonical reading
    # yields the broker order id (the authority's TOP-LEVEL id only -- RD
    # FORK 1) that the identity guard below keys on.
    submitted_order_id: str | None = None
    if req.schwab_source_value_json is not None:
        submitted = canonical_envelope_identity(req.schwab_source_value_json)
        if submitted.state == ENVELOPE_REFUSED:
            raise ExitEnvelopeUnreadableError(_ENVELOPE_UNREADABLE_TEXT)
        submitted_order_id = submitted.broker_order_id
    # D79 (CHARC K1 (1)): ONE owned transaction. BEGIN is INSIDE the try so a
    # BEGIN that fails (busy) is handled like any other failure; every read
    # the write depends on -- the trade's state and size -- is taken AFTER the
    # write lock is held, so no concurrent writer can commit between the read
    # and the INSERT (the VISIBILITY precondition of CHARC's K1 packet).
    try:
        conn.execute("BEGIN IMMEDIATE")
        trade = get_trade(conn, req.trade_id)
        # THE BARRIER: the six refusals on the row read UNDER the lock.
        check_exit_preconditions(trade, req)
        new_size = float(trade.current_size) - float(req.shares)

        # D79 (CHARC K1 (2); RD K2, K7.1): the identity guard, AFTER the
        # write lock is held and BEFORE the insert, so no concurrent writer
        # can commit the same order between this read and the write. GLOBAL
        # and multiplicity-aware: ANY recorded row carrying the id refuses
        # (the split handler writes N rows with one id; it never enters this
        # function, so the guard cannot fire inside that correction path).
        if submitted_order_id is not None:
            hits = recorded_exit_identities(conn).by_order_id.get(
                submitted_order_id, ())
            if hits:
                raise ExitOrderAlreadyRecordedError(_already_recorded_message(
                    submitted_order_id, hits,
                    exit_date=fill_datetime[:10], exit_price=req.exit_price,
                    shares=req.shares,
                ))

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
