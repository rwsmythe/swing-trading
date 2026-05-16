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


def _apply_tier2_resolution_inner(  # pragma: no cover — populated in T-C.3
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    choice_code: str,
    operator_custom_payload: Any = None,
    operator_reason: str,
    risk_policy_id: int | None = None,
    schwab_api_call_id: int | None = None,
) -> CorrectionResult:
    """T-C.3 — spec §5.6 per-(kind, choice_code) handler dispatch. Caller owns tx."""
    raise NotImplementedError(
        "_apply_tier2_resolution_inner body lands in T-C.3 per plan §D.3"
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


def _stamp_pending_ambiguity_inner(  # pragma: no cover — populated in T-C.3.1
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    ambiguity_kind: str,
    resolution_reason: str,
    allow_pending_update: bool = False,
) -> None:
    """T-C.3.1 — UPDATE discrepancy to pending_ambiguity_resolution. Caller owns tx."""
    raise NotImplementedError(
        "_stamp_pending_ambiguity_inner body lands in T-C.3.1 per plan §D.3.1"
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
