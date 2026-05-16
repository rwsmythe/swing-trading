"""Phase 12 Sub-sub-bundle C.C — auto-correction service.

Spec §5 + §7. Outer functions own ``BEGIN IMMEDIATE`` / ``COMMIT`` /
``ROLLBACK`` envelopes and reject caller-held transactions. Inner
functions accept caller-controlled tx and never call ``conn.commit()``.

Public surface:
    - :func:`apply_tier1_correction` — outer (own-tx).
    - :func:`apply_tier2_resolution` — outer (own-tx).
    - :func:`apply_tier3_override` — outer (own-tx).
    - :func:`stamp_pending_ambiguity` — outer (own-tx).
    - :class:`CorrectionResult` — service-layer return shape.
    - :class:`CallerHeldTransactionError` — outer-fn precondition guard.
    - :class:`ValidatorRejectedError` — inner-fn re-raise on validator failure.
    - :class:`AlreadySupersededError` — inner-fn re-raise when target row
      already has a successor in its chain.

Inner / caller-tx helpers (intended for reconciliation-flow pivot
consumers at T-C.5 / T-C.6 / backfill T-D.6):
    - :func:`_apply_tier1_correction_inner`
    - :func:`_apply_tier2_resolution_inner`
    - :func:`_apply_tier3_override_inner`
    - :func:`_stamp_pending_ambiguity_inner`

The inner helpers never own a transaction — they expect the caller to
hold an open tx (or savepoint). The pivot loops at T-C.5/T-C.6 wrap each
per-discrepancy invocation in a SAVEPOINT.

Composability discipline (CLAUDE.md "Service-layer ``with conn:``" gotcha
+ Phase 9 Sub-bundle A precedent): outer fns ALWAYS own + commit; inner
fns NEVER call ``conn.commit()`` / ``conn.rollback()``.
"""
from __future__ import annotations

import contextlib
import functools
import json
import logging
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence

from swing.data.models import ReconciliationCorrection
from swing.data.repos.fills import _recompute_aggregates, insert_fill_with_event
from swing.data.repos.reconciliation_corrections import (
    insert_correction,
    list_corrections_by_discrepancy,
    update_superseded_by,
)
from swing.trades.reconciliation_classifier import ClassificationResult
from swing.trades.reconciliation_validators import default_validator_chain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CallerHeldTransactionError(Exception):
    """Outer (own-tx) service fn called inside an existing transaction.

    Mirrors Phase 9 Sub-bundle A ``supersede_active_policy`` +
    Sub-bundle B reconciliation precedent: caller MUST NOT hold an open
    tx. Compose by calling the corresponding ``_inner`` variant instead.
    """


class ValidatorRejectedError(Exception):
    """Validator chain returned ``(False, reason)`` for a proposed correction.

    Inner functions raise this so the caller (flow pivot at T-C.5/T-C.6
    OR explicit tier-2/tier-3 caller) can disposition the discrepancy as
    ``validator_rejected`` or surface the rejection to the operator.
    """


class AlreadySupersededError(Exception):
    """Tier-3 override target already carries ``superseded_by_correction_id``.

    Per spec §5.7 + OQ-15 — operator MUST override the current chain
    head, not a stale predecessor. Raised by
    :func:`_apply_tier3_override_inner` before any mutation.
    """


# ---------------------------------------------------------------------------
# Return shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorrectionResult:
    """Spec §5.2 service-layer return.

    ``correction_id`` is ``None`` in the sandbox short-circuit path (spec
    §5.9): outer function did not write anything; the discrepancy stays
    ``unresolved``. ``notes`` describes the short-circuit in that case.
    """

    correction_id: int | None
    affected_table: str | None
    affected_row_id: int | None
    field_name: str | None
    applied_value_json: str | None
    correction_action: str | None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Discrepancy resolution states that indicate "already dispositioned" —
# inner fns short-circuit on these and return the most recent existing
# correction id (idempotent).
_TERMINAL_RESOLUTIONS = frozenset(
    {
        "auto_corrected_from_schwab",
        "operator_resolved_ambiguity",
        "operator_overridden",
        "manual_override",
        "journal_corrected",
        "source_treated_canonical",
        "acknowledged_immaterial",
    }
)


# Affected-table → journal-row PK helper. Keyed by the discrepancy's FK
# columns; the C.C service derives ``affected_table`` + ``affected_row_id``
# from the discrepancy row itself (precedence: fill_id → trade_id →
# cash_movement_id → snapshot via trade_id when ``field_name`` indicates
# snapshot scope). See :func:`_resolve_affected_target`.
_AFFECTED_TABLE_FILLS = "fills"
_AFFECTED_TABLE_TRADES = "trades"
_AFFECTED_TABLE_CASH = "cash_movements"
_AFFECTED_TABLE_SNAPSHOTS = "account_equity_snapshots"


def _utc_now_iso_ms() -> str:
    """ISO-8601 with millisecond precision (naive UTC), matching audit cols."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(
        timespec="milliseconds"
    )


# ---------------------------------------------------------------------------
# Outer (own-tx) functions
# ---------------------------------------------------------------------------


def apply_tier1_correction(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    classification: ClassificationResult | None,
    schwab_api_call_id: int | None = None,
    risk_policy_id: int | None = None,
    correction_reason: str | None = None,
    environment: str | None = None,
) -> CorrectionResult:
    """Spec §5.4 — apply a tier-1 classification result.

    Owns ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``. Rejects
    caller-held tx. Inner logic is in
    :func:`_apply_tier1_correction_inner`; the outer wrapper only owns
    the transaction lifecycle.

    Sandbox short-circuit (spec §5.9): when ``environment == 'sandbox'``,
    skip the entire inner logic (no domain writes; discrepancy stays
    unresolved) and emit a WARNING log.
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "apply_tier1_correction must be called with no open transaction; "
            "compose via _apply_tier1_correction_inner inside an existing tx"
        )

    if environment == "sandbox":
        logger.warning(
            "apply_tier1_correction short-circuited under sandbox "
            "environment for discrepancy_id=%d; no domain writes",
            discrepancy_id,
        )
        return CorrectionResult(
            correction_id=None,
            affected_table=None,
            affected_row_id=None,
            field_name=None,
            applied_value_json=None,
            correction_action=None,
            notes="sandbox: domain write short-circuited",
        )

    conn.execute("BEGIN IMMEDIATE")
    try:
        result = _apply_tier1_correction_inner(
            conn,
            discrepancy_id=discrepancy_id,
            classification=classification,
            schwab_api_call_id=schwab_api_call_id,
            risk_policy_id=risk_policy_id,
            correction_reason=correction_reason,
        )
        conn.commit()
        return result
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise


def apply_tier2_resolution(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    choice_code: str,
    operator_custom_payload: Any = None,
    operator_reason: str,
    risk_policy_id: int | None = None,
    schwab_api_call_id: int | None = None,
) -> CorrectionResult:
    """Spec §5.6 — operator-resolved tier-2 ambiguity.

    Owns ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``. Rejects
    caller-held tx.
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "apply_tier2_resolution must be called with no open transaction; "
            "compose via _apply_tier2_resolution_inner inside an existing tx"
        )

    conn.execute("BEGIN IMMEDIATE")
    try:
        result = _apply_tier2_resolution_inner(
            conn,
            discrepancy_id=discrepancy_id,
            choice_code=choice_code,
            operator_custom_payload=operator_custom_payload,
            operator_reason=operator_reason,
            risk_policy_id=risk_policy_id,
            schwab_api_call_id=schwab_api_call_id,
        )
        conn.commit()
        return result
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise


def apply_tier3_override(
    conn: sqlite3.Connection,
    *,
    correction_id: int,
    operator_truth_value: Mapping[str, Any],
    operator_reason: str,
    risk_policy_id: int | None = None,
) -> CorrectionResult:
    """Spec §5.7 — operator override of a prior correction.

    Owns ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``. Rejects
    caller-held tx.
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "apply_tier3_override must be called with no open transaction; "
            "compose via _apply_tier3_override_inner inside an existing tx"
        )

    conn.execute("BEGIN IMMEDIATE")
    try:
        result = _apply_tier3_override_inner(
            conn,
            correction_id=correction_id,
            operator_truth_value=operator_truth_value,
            operator_reason=operator_reason,
            risk_policy_id=risk_policy_id,
        )
        conn.commit()
        return result
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise


def stamp_pending_ambiguity(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    ambiguity_kind: str,
    resolution_reason: str,
    allow_pending_update: bool = False,
) -> None:
    """Spec §5.6 prelude — flip discrepancy to ``pending_ambiguity_resolution``.

    Owns ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``. Rejects
    caller-held tx. No journal mutation; no audit row write.
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "stamp_pending_ambiguity must be called with no open transaction; "
            "compose via _stamp_pending_ambiguity_inner inside an existing tx"
        )

    conn.execute("BEGIN IMMEDIATE")
    try:
        _stamp_pending_ambiguity_inner(
            conn,
            discrepancy_id=discrepancy_id,
            ambiguity_kind=ambiguity_kind,
            resolution_reason=resolution_reason,
            allow_pending_update=allow_pending_update,
        )
        conn.commit()
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise


# ---------------------------------------------------------------------------
# Inner (caller-tx) skeletons — bodies populated in T-C.2 / T-C.3 / T-C.4 / T-C.3.1.
# ---------------------------------------------------------------------------


def _apply_tier1_correction_inner(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    classification: ClassificationResult | None,
    schwab_api_call_id: int | None = None,
    risk_policy_id: int | None = None,
    correction_reason: str | None = None,
) -> CorrectionResult:
    """T-C.2 — spec §5.4 11-step atomic flow. Caller owns tx.

    Step 1: SELECT discrepancy. Unknown → raise ValueError. Terminal
            resolution → idempotent return.
    Step 2: Resolve affected_table + affected_row_id from discrepancy.
    Step 3: Re-run validator chain on classification.correction_target.
            Reject → ValidatorRejectedError.
    Step 4: Read pre-correction journal value.
    Step 5: UPDATE journal table.
    Step 6: _recompute_aggregates when affected_table == 'fills'.
    Step 7: INSERT reconciliation_corrections audit row + lifecycle
            invariants.
    Step 8: Back-link schwab_api_calls.linked_correction_id when supplied.
    Step 9: UPDATE review_log.superseded_by_correction_id for affected
            cadence rows (closed-trade case only).
    Step 10: UPDATE discrepancy resolution to 'auto_corrected_from_schwab'.
    Step 11: UPDATE fills.reconciliation_status + INSERT trade_events.
    """
    if classification is None:
        raise ValueError(
            "classification is required for tier-1 correction; got None"
        )
    if classification.tier != 1:
        raise ValueError(
            f"_apply_tier1_correction_inner: classification.tier must be 1; "
            f"got {classification.tier}"
        )
    if classification.correction_target is None:
        raise ValueError(
            "tier-1 classification.correction_target must not be None"
        )

    # Step 1: SELECT discrepancy.
    disc = _select_discrepancy(conn, discrepancy_id)

    # Idempotency: terminal resolution → return existing.
    if disc.resolution in _TERMINAL_RESOLUTIONS:
        return _idempotent_result_for(conn, discrepancy_id)

    # Step 2: resolve affected target.
    affected_table, affected_row_id = _resolve_affected_target(disc)
    field_name = next(iter(classification.correction_target.keys()))

    # Step 3: validator chain re-run.
    chain = functools.partial(
        default_validator_chain(conn),
        affected_table=affected_table,
        affected_row_id=affected_row_id,
    )
    passes, rejection_reason = chain(classification.correction_target)
    if not passes:
        raise ValidatorRejectedError(
            f"validator rejected tier-1 correction for discrepancy_id="
            f"{discrepancy_id} affected_table={affected_table} "
            f"affected_row_id={affected_row_id}: {rejection_reason}"
        )

    # Step 4: read pre-correction value.
    pre_value = _read_journal_value(
        conn, affected_table, affected_row_id, field_name,
    )

    # Step 5: UPDATE journal table.
    target_value = classification.correction_target[field_name]
    _update_journal_field(
        conn, affected_table, affected_row_id, field_name, target_value,
    )

    # Step 6: recompute aggregates for fills.
    if affected_table == _AFFECTED_TABLE_FILLS:
        trade_id = _get_fill_trade_id(conn, affected_row_id)
        _recompute_aggregates(conn, trade_id)

    # Step 7: INSERT correction audit row.
    effective_policy_id = risk_policy_id
    if effective_policy_id is None:
        effective_policy_id = _maybe_get_active_risk_policy_id(conn)

    pre_json = json.dumps({field_name: pre_value}, sort_keys=True)
    applied_json = json.dumps({field_name: target_value}, sort_keys=True)
    reason = correction_reason or classification.correction_reason

    # Lifecycle invariants enforcement (spec §5.4 step 7 + models.py
    # forward-binding from C.A): tier-1 = ('auto_applied' + 'auto' +
    # operator_truth_value_json IS NULL + correction_choice IS NULL).
    correction = ReconciliationCorrection(
        correction_id=0,  # ignored by INSERT
        discrepancy_id=discrepancy_id,
        correction_action="auto_applied",
        correction_choice=None,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=field_name,
        pre_correction_value_json=pre_json,
        source_canonical_value_json=applied_json,
        applied_value_json=applied_json,
        operator_truth_value_json=None,
        applied_at=_utc_now_iso_ms(),
        applied_by="auto",
        correction_set_id=None,
        superseded_by_correction_id=None,
        risk_policy_id_at_correction=effective_policy_id,
        schwab_api_call_id=schwab_api_call_id,
        reconciliation_run_id=disc.run_id,
        correction_reason=reason,
        notes=None,
    )
    correction_id = insert_correction(conn, correction)

    # Step 8: back-link schwab_api_calls.linked_correction_id.
    if schwab_api_call_id is not None:
        _back_link_schwab_api_call(conn, schwab_api_call_id, correction_id)

    # Step 9: review_log supersede for closed-trade case.
    if affected_table == _AFFECTED_TABLE_FILLS:
        trade_id = _get_fill_trade_id(conn, affected_row_id)
        _supersede_review_log_for_trade_close(
            conn, trade_id=trade_id, new_correction_id=correction_id,
        )

    # Step 10: UPDATE discrepancy resolution.
    conn.execute(
        "UPDATE reconciliation_discrepancies SET "
        "resolution = ?, resolution_reason = ?, "
        "resolved_at = ?, resolved_by = ? "
        "WHERE discrepancy_id = ?",
        (
            "auto_corrected_from_schwab", reason,
            _utc_now_iso_ms(), "auto", discrepancy_id,
        ),
    )

    # Step 11a: UPDATE fills.reconciliation_status (only for fills affected_table).
    if affected_table == _AFFECTED_TABLE_FILLS:
        conn.execute(
            "UPDATE fills SET reconciliation_status = ? WHERE fill_id = ?",
            ("reconciled_discrepancy_resolved", affected_row_id),
        )

    # Step 11b: INSERT trade_events when fill is attributable to a trade.
    if affected_table == _AFFECTED_TABLE_FILLS:
        trade_id = _get_fill_trade_id(conn, affected_row_id)
        _emit_trade_events_correction(
            conn,
            trade_id=trade_id,
            correction_id=correction_id,
            affected_table=affected_table,
            affected_row_id=affected_row_id,
            field_name=field_name,
            pre_value=pre_value,
            applied_value=target_value,
        )

    return CorrectionResult(
        correction_id=correction_id,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=field_name,
        applied_value_json=applied_json,
        correction_action="auto_applied",
        notes=None,
    )


def _apply_tier2_resolution_inner(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    choice_code: str,
    operator_custom_payload: Any = None,
    operator_reason: str,
    risk_policy_id: int | None = None,
    schwab_api_call_id: int | None = None,
) -> CorrectionResult:
    """T-C.3 — spec §5.6 per-(kind, choice_code) dispatch. Caller owns tx.

    Step 1: SELECT discrepancy. Unknown → raise. Terminal resolution →
            idempotent return.
    Step 2: Verify resolution == 'pending_ambiguity_resolution'; else
            raise ValueError.
    Step 3: Look up handler by (ambiguity_kind, choice_code) — with
            parametric-prefix dispatch for pick_schwab_record_<N>.
    Step 4: Dispatch to handler. Each handler validates its payload +
            executes its mutation (or no-mutation audit) + INSERTs the
            correction row + UPDATEs discrepancy resolution + emits
            trade_events when applicable.
    """
    disc = _select_discrepancy(conn, discrepancy_id)

    if disc.resolution in _TERMINAL_RESOLUTIONS:
        return _idempotent_result_for(conn, discrepancy_id)

    if disc.resolution != "pending_ambiguity_resolution":
        raise ValueError(
            f"apply_tier2_resolution requires discrepancy in "
            f"pending_ambiguity_resolution state; "
            f"discrepancy_id={discrepancy_id} is in {disc.resolution!r}"
        )

    if disc.ambiguity_kind is None:
        raise ValueError(
            f"discrepancy_id={discrepancy_id} has resolution="
            f"pending_ambiguity_resolution but ambiguity_kind IS NULL; "
            f"schema cross-CHECK is violated (data corruption?)"
        )

    handler_key = _resolve_handler_key(disc.ambiguity_kind, choice_code)
    if handler_key is None:
        raise ValueError(
            f"incompatible (ambiguity_kind={disc.ambiguity_kind!r}, "
            f"choice_code={choice_code!r}) — no handler registered; valid "
            f"choices for this ambiguity_kind are per spec §6.2.1 menu"
        )

    handler = _TIER2_HANDLERS[handler_key]
    return handler(
        conn,
        disc=disc,
        choice_code=choice_code,
        operator_custom_payload=operator_custom_payload,
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
    )


def _apply_tier3_override_inner(  # pragma: no cover — populated in T-C.4
    conn: sqlite3.Connection,
    *,
    correction_id: int,
    operator_truth_value: Mapping[str, Any],
    operator_reason: str,
    risk_policy_id: int | None = None,
) -> CorrectionResult:
    """T-C.4 — spec §5.7 10-step flow + validator pre-mutation. Caller owns tx."""
    raise NotImplementedError(
        "_apply_tier3_override_inner body lands in T-C.4 per plan §D.4"
    )


def _stamp_pending_ambiguity_inner(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    ambiguity_kind: str,
    resolution_reason: str,
    allow_pending_update: bool = False,
) -> None:
    """T-C.3.1 — UPDATE discrepancy to pending_ambiguity_resolution.

    Per plan §D.3.1 contract (Codex R4/R5 LOCK):
      - resolution='unresolved' → UPDATE (standard backfill stamp).
      - resolution='pending_ambiguity_resolution' AND
        allow_pending_update=False (default) → no-op (idempotent).
      - resolution='pending_ambiguity_resolution' AND
        allow_pending_update=True → UPDATE (T-D.9 --retry-pass-2-failures).
      - resolution in terminal state → raise ValueError.

    No journal mutation; no audit row write.
    """
    disc = _select_discrepancy(conn, discrepancy_id)

    if disc.resolution == "unresolved":
        pass  # standard backfill stamp; proceed to UPDATE
    elif disc.resolution == "pending_ambiguity_resolution":
        if not allow_pending_update:
            return  # idempotent no-op
        # else: T-D.9 retry — proceed to UPDATE
    else:
        raise ValueError(
            f"cannot stamp pending_ambiguity on discrepancy in terminal "
            f"state {disc.resolution!r} (discrepancy_id={discrepancy_id})"
        )

    conn.execute(
        "UPDATE reconciliation_discrepancies SET "
        "resolution = ?, ambiguity_kind = ?, resolution_reason = ? "
        "WHERE discrepancy_id = ?",
        (
            "pending_ambiguity_resolution", ambiguity_kind,
            resolution_reason, discrepancy_id,
        ),
    )


# ---------------------------------------------------------------------------
# Private helpers (shared by tier-1 / tier-2 / tier-3 flows)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DiscrepancyInfo:
    """Subset of reconciliation_discrepancies columns needed by the service."""

    discrepancy_id: int
    run_id: int
    discrepancy_type: str
    trade_id: int | None
    fill_id: int | None
    cash_movement_id: int | None
    field_name: str
    resolution: str
    ambiguity_kind: str | None


def _select_discrepancy(
    conn: sqlite3.Connection, discrepancy_id: int,
) -> _DiscrepancyInfo:
    row = conn.execute(
        "SELECT discrepancy_id, run_id, discrepancy_type, trade_id, "
        "fill_id, cash_movement_id, field_name, resolution, ambiguity_kind "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (discrepancy_id,),
    ).fetchone()
    if row is None:
        raise ValueError(
            f"discrepancy_id={discrepancy_id} not found in "
            f"reconciliation_discrepancies"
        )
    return _DiscrepancyInfo(
        discrepancy_id=row[0],
        run_id=row[1],
        discrepancy_type=row[2],
        trade_id=row[3],
        fill_id=row[4],
        cash_movement_id=row[5],
        field_name=row[6],
        resolution=row[7],
        ambiguity_kind=row[8],
    )


def _idempotent_result_for(
    conn: sqlite3.Connection, discrepancy_id: int,
) -> CorrectionResult:
    """Spec §5.3 idempotent return — look up the most recent correction
    row for this discrepancy and return its shape without writing."""
    existing = list_corrections_by_discrepancy(conn, discrepancy_id)
    if not existing:
        # Terminal resolution without a corresponding correction row.
        # This is legal for legacy resolutions like 'manual_override' that
        # pre-date the auto-correct service. Return a no-op result.
        return CorrectionResult(
            correction_id=None,
            affected_table=None,
            affected_row_id=None,
            field_name=None,
            applied_value_json=None,
            correction_action=None,
            notes=(
                f"discrepancy_id={discrepancy_id} already in terminal state "
                f"with no correction row; idempotent no-op"
            ),
        )
    # Pick the current chain head (max applied_at, then max correction_id).
    head = existing[-1]
    return CorrectionResult(
        correction_id=head.correction_id,
        affected_table=head.affected_table,
        affected_row_id=head.affected_row_id,
        field_name=head.field_name,
        applied_value_json=head.applied_value_json,
        correction_action=head.correction_action,
        notes="idempotent: discrepancy already in terminal state",
    )


def _resolve_affected_target(
    disc: _DiscrepancyInfo,
) -> tuple[str, int]:
    """Map a discrepancy row to (affected_table, affected_row_id) per
    spec §5.4 step 2.

    Precedence (Codex R1 lock from C.B context):
      - fill_id present → fills
      - cash_movement_id present → cash_movements
      - discrepancy_type == 'equity_delta' or 'snapshot_mismatch' → account_equity_snapshots
        (resolution needs the snapshot id; V1 returns the most recent matching row)
      - trade_id present → trades
    """
    if disc.fill_id is not None:
        return (_AFFECTED_TABLE_FILLS, int(disc.fill_id))
    if disc.cash_movement_id is not None:
        return (_AFFECTED_TABLE_CASH, int(disc.cash_movement_id))
    if disc.trade_id is not None:
        return (_AFFECTED_TABLE_TRADES, int(disc.trade_id))
    raise ValueError(
        f"discrepancy_id={disc.discrepancy_id} has no resolvable "
        f"affected_table FK (fill_id/trade_id/cash_movement_id all NULL); "
        f"discrepancy_type={disc.discrepancy_type}"
    )


def _read_journal_value(
    conn: sqlite3.Connection,
    affected_table: str,
    affected_row_id: int,
    field_name: str,
) -> Any:
    """SELECT the current value of the column being corrected."""
    if affected_table == _AFFECTED_TABLE_FILLS:
        sql = f"SELECT {field_name} FROM fills WHERE fill_id = ?"
    elif affected_table == _AFFECTED_TABLE_TRADES:
        sql = f"SELECT {field_name} FROM trades WHERE id = ?"
    elif affected_table == _AFFECTED_TABLE_CASH:
        sql = f"SELECT {field_name} FROM cash_movements WHERE id = ?"
    elif affected_table == _AFFECTED_TABLE_SNAPSHOTS:
        sql = (
            f"SELECT {field_name} FROM account_equity_snapshots "
            f"WHERE snapshot_id = ?"
        )
    else:
        raise ValueError(f"unsupported affected_table: {affected_table!r}")
    row = conn.execute(sql, (affected_row_id,)).fetchone()
    if row is None:
        raise ValueError(
            f"{affected_table} row id={affected_row_id} not found while "
            f"reading pre-correction value"
        )
    return row[0]


def _update_journal_field(
    conn: sqlite3.Connection,
    affected_table: str,
    affected_row_id: int,
    field_name: str,
    new_value: Any,
) -> None:
    """UPDATE the affected row's single column.

    Note: column name is interpolated from ``field_name`` (NOT parameterized
    — SQLite does not bind identifiers). Callers MUST source ``field_name``
    from a closed enum (the discrepancy emitter or classifier output);
    never accept raw operator input here. Tier-2 handlers that surface
    operator-supplied fields validate the field name against the per-
    (kind, choice_code) menu before invoking this helper.
    """
    if affected_table == _AFFECTED_TABLE_FILLS:
        sql = f"UPDATE fills SET {field_name} = ? WHERE fill_id = ?"
    elif affected_table == _AFFECTED_TABLE_TRADES:
        sql = f"UPDATE trades SET {field_name} = ? WHERE id = ?"
    elif affected_table == _AFFECTED_TABLE_CASH:
        sql = f"UPDATE cash_movements SET {field_name} = ? WHERE id = ?"
    elif affected_table == _AFFECTED_TABLE_SNAPSHOTS:
        sql = (
            f"UPDATE account_equity_snapshots SET {field_name} = ? "
            f"WHERE snapshot_id = ?"
        )
    else:
        raise ValueError(f"unsupported affected_table: {affected_table!r}")
    conn.execute(sql, (new_value, affected_row_id))


def _get_fill_trade_id(
    conn: sqlite3.Connection, fill_id: int,
) -> int:
    row = conn.execute(
        "SELECT trade_id FROM fills WHERE fill_id = ?",
        (fill_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"fill_id={fill_id} not found")
    return int(row[0])


def _maybe_get_active_risk_policy_id(
    conn: sqlite3.Connection,
) -> int | None:
    """Best-effort lookup of the active risk_policy row.

    Returns None when no active policy exists (legal for legacy DBs per
    spec §9.4 backwards-compat). Callers MUST handle a NULL stamp at
    INSERT time — ``reconciliation_corrections.risk_policy_id_at_correction``
    is nullable.
    """
    row = conn.execute(
        "SELECT policy_id FROM risk_policy WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    return int(row[0]) if row else None


def _back_link_schwab_api_call(
    conn: sqlite3.Connection,
    call_id: int,
    correction_id: int,
) -> None:
    """Bidirectional audit chain: schwab_api_calls -> reconciliation_corrections."""
    conn.execute(
        "UPDATE schwab_api_calls SET linked_correction_id = ? "
        "WHERE call_id = ?",
        (correction_id, call_id),
    )


def _supersede_review_log_for_trade_close(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    new_correction_id: int,
) -> None:
    """Spec §5.4 step 9 — UPDATE review_log.superseded_by_correction_id
    for any completed review whose period bracket covers the trade's
    effective close date (MAX non-entry fill_datetime).

    Mirrors ``complete_review_atomic`` derivation pattern. Open trades
    (no non-entry fills) → zero rows touched.
    """
    row = conn.execute(
        """
        SELECT MAX(fill_datetime) FROM fills
        WHERE trade_id = ? AND action IN ('exit', 'trim', 'stop')
        """,
        (trade_id,),
    ).fetchone()
    if row is None or row[0] is None:
        return  # open trade; no close-date to anchor against
    close_dt_text = str(row[0])
    # Pull just the date portion (YYYY-MM-DD); accept both
    # ``YYYY-MM-DDTHH:MM:SS`` and bare date forms.
    close_date = close_dt_text[:10]
    conn.execute(
        """
        UPDATE review_log SET superseded_by_correction_id = ?
        WHERE completed_date IS NOT NULL
          AND period_start <= ?
          AND ? <= period_end
        """,
        (new_correction_id, close_date, close_date),
    )


def _emit_trade_events_correction(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    correction_id: int,
    affected_table: str,
    affected_row_id: int,
    field_name: str,
    pre_value: Any,
    applied_value: Any,
) -> None:
    """INSERT a 'reconciliation_auto_correct' trade_events row.

    Spec §9.3 single-event-per-correction discipline. Payload carries
    the {correction_id, affected_table, affected_row_id, field_name,
    pre, applied} tuple for forensic replay.
    """
    payload = {
        "correction_id": correction_id,
        "affected_table": affected_table,
        "affected_row_id": affected_row_id,
        "field_name": field_name,
        "pre": pre_value,
        "applied": applied_value,
    }
    conn.execute(
        "INSERT INTO trade_events (trade_id, ts, event_type, payload_json) "
        "VALUES (?, ?, ?, ?)",
        (
            trade_id, _utc_now_iso_ms(), "reconciliation_auto_correct",
            json.dumps(payload, sort_keys=True, default=str),
        ),
    )


# ===========================================================================
# Tier-2 handler registry — spec §6.2.1 LOCKED.
# ===========================================================================
#
# 17 exact-key entries + 1 parametric-prefix entry. The
# ``_PICK_SCHWAB_RECORD_PREFIX`` value is registered as a single key in
# the dispatch table; ``_resolve_handler_key`` performs prefix-matching
# at runtime when the operator-supplied ``choice_code`` starts with the
# prefix and the discrepancy's ``ambiguity_kind`` is
# ``multi_match_within_window``.

_PICK_SCHWAB_RECORD_PREFIX = "pick_schwab_record_"


def _resolve_handler_key(
    ambiguity_kind: str, choice_code: str,
) -> tuple[str, str] | None:
    """Map (ambiguity_kind, choice_code) → registry key.

    Direct lookup for the 17 exact-key entries. For
    ``multi_match_within_window`` discrepancies whose ``choice_code``
    starts with ``pick_schwab_record_``, the registry key is
    ``(ambiguity_kind, _PICK_SCHWAB_RECORD_PREFIX)`` — the handler then
    parses the integer suffix at dispatch time.
    """
    direct = (ambiguity_kind, choice_code)
    if direct in _TIER2_HANDLERS:
        return direct
    if (
        ambiguity_kind == "multi_match_within_window"
        and choice_code.startswith(_PICK_SCHWAB_RECORD_PREFIX)
    ):
        return (ambiguity_kind, _PICK_SCHWAB_RECORD_PREFIX)
    return None


# Shared payload helpers


def _require_custom_value(
    payload: Any, choice_code: str,
) -> Any:
    """Raise ValueError("--custom-value required for choice ...") when
    payload is missing-or-empty.

    Accepts:
      - dict / Mapping with at least one key
      - non-empty list (for split_into_partials)
      - non-empty string (defensive; unused V1)

    Rejects: None, empty dict, empty list, empty string.
    """
    if payload is None:
        raise ValueError(
            f"--custom-value required for choice {choice_code!r} "
            f"(operator_custom_payload is None)"
        )
    if isinstance(payload, Mapping):
        if not payload:
            raise ValueError(
                f"--custom-value required for choice {choice_code!r} "
                f"(operator_custom_payload dict is empty)"
            )
        return payload
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        if not payload:
            raise ValueError(
                f"--custom-value required for choice {choice_code!r} "
                f"(operator_custom_payload list is empty)"
            )
        return payload
    if isinstance(payload, str):
        if not payload.strip():
            raise ValueError(
                f"--custom-value required for choice {choice_code!r} "
                f"(operator_custom_payload string is empty)"
            )
        return payload
    raise ValueError(
        f"--custom-value for choice {choice_code!r} has unsupported "
        f"shape {type(payload).__name__!r}; expected dict or list"
    )


def _validate_correction_target(
    conn: sqlite3.Connection,
    *,
    affected_table: str,
    affected_row_id: int,
    correction_target: Mapping[str, Any],
) -> None:
    """Re-run the validator chain on a tier-2 correction target.

    Raises ValueError with a descriptive message when the validator
    rejects. Tier-2 callers translate this to a per-handler-shape error
    (e.g., operator_alternative re-runs after the operator supplies a
    new payload).
    """
    chain = functools.partial(
        default_validator_chain(conn),
        affected_table=affected_table,
        affected_row_id=affected_row_id,
    )
    passes, reason = chain(correction_target)
    if not passes:
        raise ValueError(
            f"validator rejected tier-2 correction_target for "
            f"affected_table={affected_table} affected_row_id="
            f"{affected_row_id}: {reason}"
        )


def _build_tier2_correction(
    *,
    disc: _DiscrepancyInfo,
    correction_action: str,
    correction_choice: str,
    affected_table: str,
    affected_row_id: int,
    field_name: str,
    pre_correction_value_json: str,
    applied_value_json: str,
    correction_reason: str,
    risk_policy_id: int | None,
    schwab_api_call_id: int | None,
    correction_set_id: int | None,
    source_canonical_value_json: str | None = None,
) -> ReconciliationCorrection:
    """Construct a ReconciliationCorrection row for the tier-2 audit emit."""
    return ReconciliationCorrection(
        correction_id=0,  # ignored at INSERT
        discrepancy_id=disc.discrepancy_id,
        correction_action=correction_action,
        correction_choice=correction_choice,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=field_name,
        pre_correction_value_json=pre_correction_value_json,
        source_canonical_value_json=source_canonical_value_json,
        applied_value_json=applied_value_json,
        operator_truth_value_json=None,
        applied_at=_utc_now_iso_ms(),
        applied_by="operator",
        correction_set_id=correction_set_id,
        superseded_by_correction_id=None,
        risk_policy_id_at_correction=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
        reconciliation_run_id=disc.run_id,
        correction_reason=correction_reason,
        notes=None,
    )


def _flip_discrepancy_to_resolved_ambiguity(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    resolution_reason: str,
) -> None:
    conn.execute(
        "UPDATE reconciliation_discrepancies SET "
        "resolution = ?, resolution_reason = ?, "
        "resolved_at = ?, resolved_by = ? "
        "WHERE discrepancy_id = ?",
        (
            "operator_resolved_ambiguity", resolution_reason,
            _utc_now_iso_ms(), "operator", discrepancy_id,
        ),
    )


def _handle_no_mutation_audit(
    conn: sqlite3.Connection,
    *,
    disc: _DiscrepancyInfo,
    choice_code: str,
    operator_reason: str,
    risk_policy_id: int | None,
    schwab_api_call_id: int | None,
    correction_reason_suffix: str | None = None,
) -> CorrectionResult:
    """Shared implementation for the no-journal-mutation choices.

    Used by keep_journal_as_is / mark_unmatched / acknowledge / custom
    (the V1 audit-only family per spec §6.2.1 + Codex R1 Critical #1).
    The audit row carries applied_value_json == pre_correction_value_json
    bytewise — the canonical no-mutation marker.
    """
    affected_table, affected_row_id = _resolve_affected_target(disc)
    field_name = disc.field_name
    pre_value = _read_journal_value(
        conn, affected_table, affected_row_id, field_name,
    )
    pre_json = json.dumps({field_name: pre_value}, sort_keys=True, default=str)

    if risk_policy_id is None:
        risk_policy_id = _maybe_get_active_risk_policy_id(conn)

    full_reason = operator_reason
    if correction_reason_suffix:
        full_reason = f"{operator_reason} | {correction_reason_suffix}"

    correction = _build_tier2_correction(
        disc=disc,
        correction_action="operator_resolved_ambiguity",
        correction_choice=choice_code,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=field_name,
        pre_correction_value_json=pre_json,
        applied_value_json=pre_json,  # bytewise no-mutation marker
        correction_reason=full_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
        correction_set_id=None,
    )
    correction_id = insert_correction(conn, correction)
    _flip_discrepancy_to_resolved_ambiguity(
        conn,
        discrepancy_id=disc.discrepancy_id,
        resolution_reason=full_reason,
    )
    return CorrectionResult(
        correction_id=correction_id,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=field_name,
        applied_value_json=pre_json,
        correction_action="operator_resolved_ambiguity",
        notes="no journal mutation (audit-only)",
    )


def _handle_single_field_correction(
    conn: sqlite3.Connection,
    *,
    disc: _DiscrepancyInfo,
    choice_code: str,
    correction_target: Mapping[str, Any],
    operator_reason: str,
    risk_policy_id: int | None,
    schwab_api_call_id: int | None,
    revalidate: bool = True,
) -> CorrectionResult:
    """Shared implementation for single-field UPDATE handlers.

    Used by consolidate_using_operator_vwap (price-only) +
    operator_alternative (validator-rejected re-run).

    Updates the journal column for the discrepancy's field_name with
    ``correction_target[field_name]``. Validates via the chain when
    ``revalidate=True``; raises ValueError("validator rejected ...")
    on rejection.
    """
    affected_table, affected_row_id = _resolve_affected_target(disc)
    field_name = next(iter(correction_target.keys()))

    if revalidate:
        _validate_correction_target(
            conn,
            affected_table=affected_table,
            affected_row_id=affected_row_id,
            correction_target=correction_target,
        )

    pre_value = _read_journal_value(
        conn, affected_table, affected_row_id, field_name,
    )
    target_value = correction_target[field_name]

    _update_journal_field(
        conn, affected_table, affected_row_id, field_name, target_value,
    )
    if affected_table == _AFFECTED_TABLE_FILLS:
        trade_id = _get_fill_trade_id(conn, affected_row_id)
        _recompute_aggregates(conn, trade_id)

    if risk_policy_id is None:
        risk_policy_id = _maybe_get_active_risk_policy_id(conn)

    pre_json = json.dumps({field_name: pre_value}, sort_keys=True, default=str)
    applied_json = json.dumps(
        {field_name: target_value}, sort_keys=True, default=str,
    )
    correction = _build_tier2_correction(
        disc=disc,
        correction_action="operator_resolved_ambiguity",
        correction_choice=choice_code,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=field_name,
        pre_correction_value_json=pre_json,
        applied_value_json=applied_json,
        source_canonical_value_json=applied_json,
        correction_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
        correction_set_id=None,
    )
    correction_id = insert_correction(conn, correction)

    _flip_discrepancy_to_resolved_ambiguity(
        conn,
        discrepancy_id=disc.discrepancy_id,
        resolution_reason=operator_reason,
    )

    if affected_table == _AFFECTED_TABLE_FILLS:
        conn.execute(
            "UPDATE fills SET reconciliation_status = ? WHERE fill_id = ?",
            ("reconciled_discrepancy_resolved", affected_row_id),
        )
        trade_id = _get_fill_trade_id(conn, affected_row_id)
        _emit_trade_events_correction(
            conn,
            trade_id=trade_id,
            correction_id=correction_id,
            affected_table=affected_table,
            affected_row_id=affected_row_id,
            field_name=field_name,
            pre_value=pre_value,
            applied_value=target_value,
        )

    return CorrectionResult(
        correction_id=correction_id,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=field_name,
        applied_value_json=applied_json,
        correction_action="operator_resolved_ambiguity",
        notes=None,
    )


def _handle_multi_field_correction(
    conn: sqlite3.Connection,
    *,
    disc: _DiscrepancyInfo,
    choice_code: str,
    correction_target: Mapping[str, Any],
    operator_reason: str,
    risk_policy_id: int | None,
    schwab_api_call_id: int | None,
) -> CorrectionResult:
    """Multi-column UPDATE handler — used by operator_truth /
    pick_schwab_record_<N> when the operator's payload carries multiple
    field-value pairs.

    Validator runs ONCE against the merged proposed-updates dict.
    INSERTs ONE correction row whose ``applied_value_json`` carries the
    full merged dict + ``field_name`` is the canonical 'price' anchor
    when present (else first key) for forward-compat with single-field
    queries.
    """
    affected_table, affected_row_id = _resolve_affected_target(disc)

    _validate_correction_target(
        conn,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        correction_target=correction_target,
    )

    # Read pre-values for all touched fields.
    pre_values = {
        fname: _read_journal_value(
            conn, affected_table, affected_row_id, fname,
        )
        for fname in correction_target.keys()
    }
    pre_json = json.dumps(pre_values, sort_keys=True, default=str)
    applied_json = json.dumps(
        dict(correction_target), sort_keys=True, default=str,
    )

    # UPDATE each column.
    for fname, fvalue in correction_target.items():
        _update_journal_field(
            conn, affected_table, affected_row_id, fname, fvalue,
        )
    if affected_table == _AFFECTED_TABLE_FILLS:
        trade_id = _get_fill_trade_id(conn, affected_row_id)
        _recompute_aggregates(conn, trade_id)

    if risk_policy_id is None:
        risk_policy_id = _maybe_get_active_risk_policy_id(conn)

    # Canonical field_name anchor for downstream queries: prefer 'price'.
    canonical_field = (
        "price" if "price" in correction_target
        else next(iter(correction_target.keys()))
    )

    correction = _build_tier2_correction(
        disc=disc,
        correction_action="operator_resolved_ambiguity",
        correction_choice=choice_code,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=canonical_field,
        pre_correction_value_json=pre_json,
        applied_value_json=applied_json,
        source_canonical_value_json=applied_json,
        correction_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
        correction_set_id=None,
    )
    correction_id = insert_correction(conn, correction)

    _flip_discrepancy_to_resolved_ambiguity(
        conn,
        discrepancy_id=disc.discrepancy_id,
        resolution_reason=operator_reason,
    )

    if affected_table == _AFFECTED_TABLE_FILLS:
        conn.execute(
            "UPDATE fills SET reconciliation_status = ? WHERE fill_id = ?",
            ("reconciled_discrepancy_resolved", affected_row_id),
        )
        trade_id = _get_fill_trade_id(conn, affected_row_id)
        _emit_trade_events_correction(
            conn,
            trade_id=trade_id,
            correction_id=correction_id,
            affected_table=affected_table,
            affected_row_id=affected_row_id,
            field_name=canonical_field,
            pre_value=pre_values.get(canonical_field),
            applied_value=correction_target.get(canonical_field),
        )

    return CorrectionResult(
        correction_id=correction_id,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=canonical_field,
        applied_value_json=applied_json,
        correction_action="operator_resolved_ambiguity",
        notes=None,
    )


# ---------------------------------------------------------------------------
# Per-(kind, choice_code) handlers — small, focused functions.
# ---------------------------------------------------------------------------


def _handle_keep_journal_as_is(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
):
    return _handle_no_mutation_audit(
        conn, disc=disc, choice_code=choice_code,
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
    )


def _handle_consolidate_using_operator_vwap(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
):
    payload = _require_custom_value(operator_custom_payload, choice_code)
    if not isinstance(payload, Mapping) or "price" not in payload:
        raise ValueError(
            f"choice {choice_code!r} requires --custom-value with a "
            f"dict containing 'price'; got {payload!r}"
        )
    return _handle_single_field_correction(
        conn, disc=disc, choice_code=choice_code,
        correction_target={"price": payload["price"]},
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
    )


def _handle_split_into_partials(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
):
    """spec §6.2.1 split_into_partials — DELETE consolidated fill, INSERT
    N partial fills, write N+1 correction rows under one correction_set_id.

    Per spec §3.1.1 anchor-self-reference pattern: anchor (delete) row's
    correction_set_id = its own correction_id; the N insert rows share
    that correction_set_id.
    """
    payload = _require_custom_value(operator_custom_payload, choice_code)
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(
            f"choice {choice_code!r} requires --custom-value with a "
            f"list of partial-fill dicts; got {type(payload).__name__}"
        )
    parsed_partials: list[dict[str, Any]] = []
    for i, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(
                f"choice {choice_code!r} partial #{i + 1}: must be a "
                f"dict with keys {{qty, price, fill_datetime}}; got "
                f"{type(item).__name__}"
            )
        for k in ("qty", "price", "fill_datetime"):
            if k not in item:
                raise ValueError(
                    f"choice {choice_code!r} partial #{i + 1}: missing "
                    f"required key {k!r}"
                )
        if not isinstance(item["qty"], (int, float)) or item["qty"] <= 0:
            raise ValueError(
                f"choice {choice_code!r} partial #{i + 1}: qty must be "
                f"positive numeric; got {item['qty']!r}"
            )
        if not isinstance(item["price"], (int, float)) or item["price"] <= 0:
            raise ValueError(
                f"choice {choice_code!r} partial #{i + 1}: price must "
                f"be positive numeric; got {item['price']!r}"
            )
        if not math.isfinite(float(item["qty"])) or not math.isfinite(
            float(item["price"])
        ):
            raise ValueError(
                f"choice {choice_code!r} partial #{i + 1}: qty + price "
                f"must be finite; got qty={item['qty']!r} "
                f"price={item['price']!r}"
            )
        parsed_partials.append(
            {
                "qty": float(item["qty"]),
                "price": float(item["price"]),
                "fill_datetime": str(item["fill_datetime"]),
            }
        )

    if disc.fill_id is None:
        raise ValueError(
            f"split_into_partials requires discrepancy.fill_id to be set; "
            f"discrepancy_id={disc.discrepancy_id} has fill_id IS NULL"
        )
    original_fill_id = int(disc.fill_id)

    # Read the original fill to (a) sanity-check quantity sum + (b)
    # capture the trade_id + (c) preserve the original payload for the
    # deletion-sentinel audit row.
    orig_row = conn.execute(
        "SELECT fill_id, trade_id, fill_datetime, action, quantity, price, "
        "reason, rule_based, fees, manual_entry_confidence, "
        "reconciliation_status, tos_match_id "
        "FROM fills WHERE fill_id = ?",
        (original_fill_id,),
    ).fetchone()
    if orig_row is None:
        raise ValueError(
            f"original fill_id={original_fill_id} not found for "
            f"split_into_partials handler"
        )
    original_payload = {
        "fill_id": orig_row[0],
        "trade_id": orig_row[1],
        "fill_datetime": orig_row[2],
        "action": orig_row[3],
        "quantity": orig_row[4],
        "price": orig_row[5],
    }
    trade_id = int(orig_row[1])
    orig_quantity = float(orig_row[4])

    partials_qty_sum = sum(p["qty"] for p in parsed_partials)
    qty_tolerance = 1e-6
    if abs(partials_qty_sum - orig_quantity) > qty_tolerance:
        raise ValueError(
            f"split_into_partials: partial-fill quantities sum to "
            f"{partials_qty_sum} which does not match original fill "
            f"quantity {orig_quantity} (tolerance {qty_tolerance})"
        )

    if risk_policy_id is None:
        risk_policy_id = _maybe_get_active_risk_policy_id(conn)

    pre_json = json.dumps(original_payload, sort_keys=True, default=str)

    # Step 1: DELETE the consolidated fill + recompute aggregates ONCE.
    conn.execute("DELETE FROM fills WHERE fill_id = ?", (original_fill_id,))
    _recompute_aggregates(conn, trade_id)

    # Step 2: INSERT anchor (deletion-sentinel) correction row.
    anchor_correction = _build_tier2_correction(
        disc=disc,
        correction_action="operator_resolved_ambiguity",
        correction_choice=choice_code,
        affected_table=_AFFECTED_TABLE_FILLS,
        affected_row_id=original_fill_id,
        field_name="__delete__",
        pre_correction_value_json=pre_json,
        applied_value_json=json.dumps(
            {"deleted": True}, sort_keys=True, default=str,
        ),
        source_canonical_value_json=None,
        correction_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
        correction_set_id=None,  # set in step 2.5 (self-reference)
    )
    anchor_id = insert_correction(conn, anchor_correction)
    # Step 2.5: UPDATE anchor's correction_set_id to itself.
    conn.execute(
        "UPDATE reconciliation_corrections SET correction_set_id = ? "
        "WHERE correction_id = ?",
        (anchor_id, anchor_id),
    )

    # Step 3: INSERT N partial fills via the existing shipped helper
    # (which recomputes aggregates internally; cost is N × O(N) on
    # current_size but N is small in V1 + sub-millisecond cost).
    from swing.data.models import Fill

    inserted_fill_ids: list[int] = []
    for partial in parsed_partials:
        new_fill = Fill(
            fill_id=None,
            trade_id=trade_id,
            fill_datetime=partial["fill_datetime"],
            action="entry",
            quantity=partial["qty"],
            price=partial["price"],
            reason=None,
            rule_based=None,
            fees=None,
            manual_entry_confidence=None,
            reconciliation_status="reconciled_discrepancy_resolved",
            tos_match_id=None,
        )
        # Suppress the per-fill 'entry' trade_event — the correction
        # event is emitted separately below as
        # 'reconciliation_auto_correct' (single audit-event-per-
        # corrected-row).
        new_fid = insert_fill_with_event(
            conn, new_fill,
            event_ts=partial["fill_datetime"],
            rationale=None,
            emit_event=False,
        )
        inserted_fill_ids.append(int(new_fid))

    # Step 4: INSERT N insertion-sentinel correction rows under the same
    # correction_set_id.
    for new_fid, partial in zip(inserted_fill_ids, parsed_partials):
        insert_payload_json = json.dumps(
            {
                "fill_id": new_fid,
                "trade_id": trade_id,
                "fill_datetime": partial["fill_datetime"],
                "action": "entry",
                "quantity": partial["qty"],
                "price": partial["price"],
            },
            sort_keys=True, default=str,
        )
        sub_correction = _build_tier2_correction(
            disc=disc,
            correction_action="operator_resolved_ambiguity",
            correction_choice=choice_code,
            affected_table=_AFFECTED_TABLE_FILLS,
            affected_row_id=new_fid,
            field_name="__insert__",
            pre_correction_value_json=json.dumps(
                {"existed_before": False}, sort_keys=True, default=str,
            ),
            applied_value_json=insert_payload_json,
            source_canonical_value_json=insert_payload_json,
            correction_reason=operator_reason,
            risk_policy_id=risk_policy_id,
            schwab_api_call_id=schwab_api_call_id,
            correction_set_id=anchor_id,
        )
        sub_id = insert_correction(conn, sub_correction)

        # spec §9.3: one trade_event per RESULTING fill.
        _emit_trade_events_correction(
            conn,
            trade_id=trade_id,
            correction_id=sub_id,
            affected_table=_AFFECTED_TABLE_FILLS,
            affected_row_id=new_fid,
            field_name="__insert__",
            pre_value=None,
            applied_value=insert_payload_json,
        )

    # Step 5: flip discrepancy to operator_resolved_ambiguity.
    _flip_discrepancy_to_resolved_ambiguity(
        conn,
        discrepancy_id=disc.discrepancy_id,
        resolution_reason=operator_reason,
    )

    return CorrectionResult(
        correction_id=anchor_id,
        affected_table=_AFFECTED_TABLE_FILLS,
        affected_row_id=original_fill_id,
        field_name="__delete__",
        applied_value_json=anchor_correction.applied_value_json,
        correction_action="operator_resolved_ambiguity",
        notes=f"split into {len(inserted_fill_ids)} partial fills",
    )


def _handle_custom_audit_only(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
):
    """V1 LOCK (Codex R2 Major #5): the ``custom`` choice is audit-only;
    no journal mutation regardless of payload shape. Spec §6.2.1
    earmarks V2 widening for operator-defined transformations.
    """
    # Validate the payload is present even though we don't mutate from it.
    payload = _require_custom_value(operator_custom_payload, choice_code)
    operator_intent = ""
    if isinstance(payload, Mapping):
        operator_intent = str(payload.get("operator_intent", ""))
    suffix = (
        f"operator_intent={operator_intent}"
        if operator_intent else
        "operator-supplied payload (V1 audit-only)"
    )
    return _handle_no_mutation_audit(
        conn, disc=disc, choice_code=choice_code,
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
        correction_reason_suffix=suffix,
    )


def _handle_mark_unmatched(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
):
    return _handle_no_mutation_audit(
        conn, disc=disc, choice_code=choice_code,
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
    )


def _handle_acknowledge(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
):
    return _handle_no_mutation_audit(
        conn, disc=disc, choice_code=choice_code,
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
    )


def _handle_operator_truth(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
):
    payload = _require_custom_value(operator_custom_payload, choice_code)
    if not isinstance(payload, Mapping):
        raise ValueError(
            f"choice {choice_code!r} requires --custom-value with a dict; "
            f"got {type(payload).__name__}"
        )
    return _handle_multi_field_correction(
        conn, disc=disc, choice_code=choice_code,
        correction_target=dict(payload),
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
    )


def _handle_operator_alternative(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
):
    payload = _require_custom_value(operator_custom_payload, choice_code)
    if not isinstance(payload, Mapping):
        raise ValueError(
            f"choice {choice_code!r} requires --custom-value with a dict; "
            f"got {type(payload).__name__}"
        )
    return _handle_single_field_correction(
        conn, disc=disc, choice_code=choice_code,
        correction_target=dict(payload),
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
    )


def _handle_pick_schwab_record_N(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
):
    """Parametric handler — dispatched via prefix-match in _resolve_handler_key.

    Parses the N suffix from choice_code; surfaces a clear error when
    the suffix is non-numeric. Validates payload presence + then
    delegates to ``_handle_multi_field_correction`` for the actual
    UPDATE (since operator supplies the execution-level field-values
    per Codex R7 Major #2 lock).
    """
    suffix = choice_code[len(_PICK_SCHWAB_RECORD_PREFIX):]
    try:
        n = int(suffix)
    except (TypeError, ValueError):
        raise ValueError(
            f"choice {choice_code!r}: pick_schwab_record_<N> requires "
            f"an integer N suffix; got {suffix!r}"
        ) from None
    if n < 1:
        raise ValueError(
            f"choice {choice_code!r}: N must be >= 1; got {n}"
        )
    payload = _require_custom_value(operator_custom_payload, choice_code)
    if not isinstance(payload, Mapping):
        raise ValueError(
            f"choice {choice_code!r} requires --custom-value with a dict "
            f"of operator-supplied execution-level field values; got "
            f"{type(payload).__name__}"
        )
    return _handle_multi_field_correction(
        conn, disc=disc, choice_code=choice_code,
        correction_target=dict(payload),
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
    )


# Registry — 17 exact-key entries + 1 parametric-prefix entry.
_TIER2_HANDLERS: dict[tuple[str, str], Callable[..., CorrectionResult]] = {
    ("multi_partial_vs_consolidated", "keep_journal_as_is"):
        _handle_keep_journal_as_is,
    ("multi_partial_vs_consolidated", "consolidate_using_operator_vwap"):
        _handle_consolidate_using_operator_vwap,
    ("multi_partial_vs_consolidated", "split_into_partials"):
        _handle_split_into_partials,
    ("multi_partial_vs_consolidated", "custom"):
        _handle_custom_audit_only,
    ("multi_match_within_window", _PICK_SCHWAB_RECORD_PREFIX):
        _handle_pick_schwab_record_N,
    ("multi_match_within_window", "mark_unmatched"):
        _handle_mark_unmatched,
    ("multi_match_within_window", "custom"):
        _handle_custom_audit_only,
    ("unknown_schwab_subtype", "acknowledge"):
        _handle_acknowledge,
    ("unknown_schwab_subtype", "operator_truth"):
        _handle_operator_truth,
    ("unknown_schwab_subtype", "custom"):
        _handle_custom_audit_only,
    ("field_shape_incompatible", "acknowledge"):
        _handle_acknowledge,
    ("field_shape_incompatible", "custom"):
        _handle_custom_audit_only,
    ("schwab_returned_no_match", "mark_unmatched"):
        _handle_mark_unmatched,
    ("schwab_returned_no_match", "operator_truth"):
        _handle_operator_truth,
    ("validator_rejected", "acknowledge"):
        _handle_acknowledge,
    ("validator_rejected", "operator_alternative"):
        _handle_operator_alternative,
    ("unsupported", "operator_truth"):
        _handle_operator_truth,
    ("unsupported", "acknowledge"):
        _handle_acknowledge,
}
