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


def _apply_tier1_correction_inner(  # pragma: no cover — populated in T-C.2
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    classification: ClassificationResult | None,
    schwab_api_call_id: int | None = None,
    risk_policy_id: int | None = None,
    correction_reason: str | None = None,
) -> CorrectionResult:
    """T-C.2 — spec §5.4 11-step atomic flow. Caller owns tx."""
    raise NotImplementedError(
        "_apply_tier1_correction_inner body lands in T-C.2 per plan §D.2"
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
