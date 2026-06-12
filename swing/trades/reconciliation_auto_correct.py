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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from swing.data.models import ReconciliationCorrection
from swing.data.repos.fills import _recompute_aggregates, insert_fill_with_event
from swing.data.repos.reconciliation_corrections import (
    get_correction,
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


class InvalidOverrideComboError(ValueError):
    """Phase 12.5 #1 spec §7.3.1.a + §7.4 — developer-bug signal raised
    when the auto-redirect override kwargs to :func:`apply_tier2_resolution`
    (and its inner) are mismatched.

    NOT a data fall-back — pivot loop MUST NOT catch this + must
    propagate (F21 invariant). Subclass of :class:`ValueError` so existing
    generic ``ValueError`` catches still see it, but exception-specificity
    ordering MUST place ``except InvalidOverrideComboError: raise`` BEFORE
    any generic ``ValueError`` catch.
    """


class SourceResolutionRejected(ValueError):  # noqa: N818 — spec §4.3 name (no Error suffix); subclass of ValueError for the CLI wrap
    """Arc 4b §4.3 — a source-direction (missing_journal_row) resolution was
    rejected: the verifying choice (record_journal_row / matched_existing_row)
    could not confirm the operator's claim against the ledger. Subclass of
    ``ValueError`` so the CLI boundary's generic ValueError→ClickException wrap
    still surfaces it cleanly."""


class _SandboxAutoRedirectShortCircuit(Exception):  # noqa: N818 — spec-locked sentinel name; see docstring
    """Phase 12.5 #1 T-1.6 + spec §7.6.1 — sandbox short-circuit sentinel
    raised by :func:`_apply_tier2_resolution_inner` when the auto-redirect
    override triple is present AND ``environment == 'sandbox'``.

    Intentionally NOT a :class:`ValueError` subclass so the pivot loop's
    ``except (ValidatorRejectedError, ValueError)`` fallback at the
    tier-1 / multi-leg auto-redirect branch does NOT absorb it (the
    pivot loop dispatches its own dedicated catch that rolls back the
    SAVEPOINT + increments the sandbox-skipped counter; the §7.5
    fresh-savepoint pending-ambiguity fallback MUST NOT fire on the
    sandbox path because the stamp was rolled back).
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


# Phase 12.5 #1 spec §7.3.1.a R5 M1 LOCK: the ONLY ``choice_code`` valid
# with the auto-redirect override triple. Multi-leg auto-redirect synthesizes
# a ``split_into_partials`` recipe; any other choice with the auto triple
# is a developer bug (caught by :func:`_validate_override_combo`).
_AUTO_REDIRECT_SANCTIONED_CHOICE_CODE: str = "split_into_partials"


# Phase 12.5 #1 spec §7.3.1.a — the single literal ``resolved_by`` value
# used by the auto-redirect path. Per F7 invariant, ``resolved_by`` remains
# free TEXT (no closed enum) — operator-set values pass through unchecked;
# only this exact literal triggers the hybrid-row invariant checks.
_AUTO_REDIRECT_RESOLVED_BY: str = "auto_tier1_multi_leg"


def _utc_now_iso_ms() -> str:
    """ISO-8601 with millisecond precision (naive UTC), matching audit cols."""
    return datetime.now(UTC).replace(tzinfo=None).isoformat(
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
    the INNER returns a no-op CorrectionResult (no domain writes;
    discrepancy stays unresolved) and emits a WARNING log. Codex R1
    Major #1 LOCK: the OUTER does NOT short-circuit — it ALWAYS opens
    BEGIN IMMEDIATE and commits/rolls back uniformly so transactional
    discipline applies regardless of environment. The inner's
    short-circuit fires inside the transaction envelope; the outer
    then commits the empty transaction and returns.
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "apply_tier1_correction must be called with no open transaction; "
            "compose via _apply_tier1_correction_inner inside an existing tx"
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
            environment=environment,
        )
        conn.commit()
        return result
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise


def _validate_override_combo(
    *,
    choice_code: str,
    applied_by_override: str | None,
    correction_action_override: str | None,
    resolved_by_override: str | None,
) -> None:
    """Phase 12.5 #1 spec §7.3.1.a — validate the auto-redirect override
    triple satisfies the hybrid-row invariant.

    Three invariants enforced:

    1. ``applied_by_override == 'auto'`` OR
       ``correction_action_override == 'auto_applied'`` requires
       ``resolved_by_override == 'auto_tier1_multi_leg'``.
    2. ``resolved_by_override == 'auto_tier1_multi_leg'`` requires
       ``applied_by_override == 'auto'`` AND
       ``correction_action_override == 'auto_applied'``.
    3. ``resolved_by_override == 'auto_tier1_multi_leg'`` requires
       ``choice_code == _AUTO_REDIRECT_SANCTIONED_CHOICE_CODE`` (i.e.,
       ``'split_into_partials'``) per spec §7.3.1.a R5 M1 LOCK.

    Returns ``None`` on all-None (legacy default) — F3 invariant.
    Raises :class:`InvalidOverrideComboError` (subclass of ``ValueError``)
    on any violation. Error messages cite all 4 input values for forensic
    clarity.
    """
    # Fast path: legacy default (all overrides None) — F3 LOCK.
    if (
        applied_by_override is None
        and correction_action_override is None
        and resolved_by_override is None
    ):
        return

    auto_applied_by = applied_by_override == "auto"
    auto_correction_action = correction_action_override == "auto_applied"
    auto_resolved_by = resolved_by_override == _AUTO_REDIRECT_RESOLVED_BY

    # Invariant 1: any "auto applied" signal requires the full auto-redirect
    # resolved_by literal.
    if (auto_applied_by or auto_correction_action) and not auto_resolved_by:
        raise InvalidOverrideComboError(
            f"auto-applied override requires resolved_by_override="
            f"{_AUTO_REDIRECT_RESOLVED_BY!r}; got "
            f"choice_code={choice_code!r}, "
            f"applied_by_override={applied_by_override!r}, "
            f"correction_action_override={correction_action_override!r}, "
            f"resolved_by_override={resolved_by_override!r}"
        )

    # Invariant 2: auto_tier1_multi_leg resolved_by requires the full
    # auto applied_by + correction_action pair.
    if auto_resolved_by and not (auto_applied_by and auto_correction_action):
        raise InvalidOverrideComboError(
            f"resolved_by_override={_AUTO_REDIRECT_RESOLVED_BY!r} requires "
            f"applied_by_override='auto' AND "
            f"correction_action_override='auto_applied'; got "
            f"choice_code={choice_code!r}, "
            f"applied_by_override={applied_by_override!r}, "
            f"correction_action_override={correction_action_override!r}, "
            f"resolved_by_override={resolved_by_override!r}"
        )

    # Invariant 3: auto-redirect triple ONLY valid under split_into_partials.
    if auto_resolved_by and choice_code != _AUTO_REDIRECT_SANCTIONED_CHOICE_CODE:
        raise InvalidOverrideComboError(
            f"auto-redirect triple is only valid under choice_code="
            f"{_AUTO_REDIRECT_SANCTIONED_CHOICE_CODE!r}; got "
            f"choice_code={choice_code!r}, "
            f"applied_by_override={applied_by_override!r}, "
            f"correction_action_override={correction_action_override!r}, "
            f"resolved_by_override={resolved_by_override!r}"
        )


def apply_tier2_resolution(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    choice_code: str,
    operator_custom_payload: Any = None,
    operator_reason: str,
    risk_policy_id: int | None = None,
    schwab_api_call_id: int | None = None,
    applied_by_override: str | None = None,
    correction_action_override: str | None = None,
    resolved_by_override: str | None = None,
    environment: str = "production",
) -> CorrectionResult:
    """Spec §5.6 — operator-resolved tier-2 ambiguity.

    Owns ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``. Rejects
    caller-held tx.

    Phase 12.5 #1 T-1.4 — the three ``*_override`` kwargs (all default
    ``None``) parameterize the audit-row + parent-discrepancy
    ``applied_by`` / ``correction_action`` / ``resolved_by`` columns for
    the multi-leg auto-redirect dispatch path. Pre-existing call sites
    that omit the overrides preserve byte-for-byte legacy shape per F3
    invariant. The hybrid-row invariant is validated up-front in
    :func:`_validate_override_combo` (called from
    :func:`_apply_tier2_resolution_inner` step 0).

    Phase 12.5 #1 T-1.6 — the ``environment`` kwarg (default
    ``'production'``) threads through to the inner. When the auto-redirect
    triple is present (``applied_by_override == 'auto'``) AND
    ``environment == 'sandbox'``, the inner short-circuits with
    :class:`_SandboxAutoRedirectShortCircuit` per spec §7.6.1 LOCK.
    Manual operator paths under sandbox proceed normally — operators may
    test the manual choice menu in sandbox.
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
            applied_by_override=applied_by_override,
            correction_action_override=correction_action_override,
            resolved_by_override=resolved_by_override,
            environment=environment,
        )
        conn.commit()
        return result
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise


def _admitted_kinds_for_source_flag(*, net_amount: float, flag_reason: str) -> set[str]:
    """Arc 4b §4.3(b) — the journal kinds a record_journal_row resolution may
    link, given the flagged transaction's sign + flag_reason."""
    if flag_reason == "unrecognized_income_description" and net_amount > 0:
        return {"interest", "dividend"}
    if flag_reason == "negative_income_amount" or net_amount < 0:
        return {"fee", "withdraw"}
    if net_amount > 0:
        return {"deposit", "interest", "dividend"}
    return {"withdraw", "fee"}


_KIND_TO_CLI_FLAG = {
    "deposit": "--deposit", "withdraw": "--withdraw", "interest": "--interest",
    "dividend": "--dividend", "fee": "--fee",
}


def apply_source_direction_resolution(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    choice_code: str,
    operator_reason: str,
    operator_custom_payload: Any = None,
) -> None:
    """Arc 4b §4.3 — resolve a source-direction (missing_journal_row) pending.

    A no-FK-safe terminal resolver: it NEVER calls ``_resolve_affected_target``
    (which raises on all-NULL FK). Owns BEGIN IMMEDIATE / COMMIT / ROLLBACK;
    rejects caller-held tx. Three choices (spec §4.3):

      - acknowledge_not_journal_event -> acknowledged_immaterial (ambiguity_kind
        nulled to satisfy the resolution<->ambiguity_kind CHECK).
      - record_journal_row -> VERIFYING: requires find_by_ref(transactionId) to
        return a row whose kind is direction-compatible, amount within $0.01, and
        date within ±4d of the envelope; else SourceResolutionRejected.
      - matched_existing_row -> requires {"cash_movement_id": N} where N is in
        the envelope's candidate list AND the row still exists with matching
        kind/amount; else SourceResolutionRejected.
    """
    from datetime import date as _date

    from swing.data.datetime_helpers import now_ms
    from swing.data.repos.cash import find_by_ref
    from swing.data.repos.reconciliation import get_discrepancy

    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "apply_source_direction_resolution owns its own transaction; "
            "caller MUST NOT hold an open transaction."
        )

    conn.execute("BEGIN IMMEDIATE")
    try:
        disc = get_discrepancy(conn, discrepancy_id=discrepancy_id)
        if disc is None:
            raise SourceResolutionRejected(
                f"discrepancy {discrepancy_id} not found")
        if disc.field_name != "missing_journal_row":
            raise SourceResolutionRejected(
                f"discrepancy {discrepancy_id} is not a source-direction "
                f"(missing_journal_row) row")
        # Pending-state precondition (Codex R2 MAJOR; the SELECT-first terminal-
        # state discipline): the service is self-protecting — a terminal source
        # row (already operator_resolved_ambiguity / acknowledged_immaterial)
        # must NOT be re-resolved, which would rewrite the terminal audit state
        # without a correction row. The web/CLI surfaces also gate on this, but
        # the service enforces it independently.
        if disc.resolution != "pending_ambiguity_resolution":
            raise SourceResolutionRejected(
                f"discrepancy {discrepancy_id} is not pending "
                f"(resolution={disc.resolution!r}); cannot re-resolve a "
                f"terminal source-direction row")
        envelope = json.loads(disc.expected_value_json or "{}")
        tx_id = str(envelope.get("transactionId"))
        net_amount = float(envelope.get("net_amount", 0.0))
        iso_date = envelope.get("date")
        flag_reason = envelope.get("flag_reason", "")
        now = now_ms()

        def _terminal(resolution: str, reason: str, *, null_kind: bool) -> None:
            if null_kind:
                conn.execute(
                    "UPDATE reconciliation_discrepancies SET resolution=?, "
                    "ambiguity_kind=NULL, resolution_reason=?, resolved_at=?, "
                    "resolved_by='operator' WHERE discrepancy_id=?",
                    (resolution, reason, now, discrepancy_id))
            else:
                conn.execute(
                    "UPDATE reconciliation_discrepancies SET resolution=?, "
                    "resolution_reason=?, resolved_at=?, resolved_by='operator' "
                    "WHERE discrepancy_id=?",
                    (resolution, reason, now, discrepancy_id))

        if choice_code == "acknowledge_not_journal_event":
            _terminal("acknowledged_immaterial", operator_reason, null_kind=True)

        elif choice_code == "record_journal_row":
            row = find_by_ref(conn, ref=tx_id)
            admitted = _admitted_kinds_for_source_flag(
                net_amount=net_amount, flag_reason=flag_reason)
            if row is None:
                kind_hint = sorted(admitted)[0]
                flag = _KIND_TO_CLI_FLAG.get(kind_hint, "--deposit")
                raise SourceResolutionRejected(
                    "no journal row carries this transactionId yet; record it "
                    f"first: swing journal cash {flag} {abs(net_amount):.2f} "
                    f"--date {iso_date} --ref {tx_id}")
            if row.kind not in admitted:
                raise SourceResolutionRejected(
                    f"journal row kind {row.kind!r} is not direction-compatible "
                    f"with the transaction (admitted: {sorted(admitted)})")
            if abs(abs(float(row.amount)) - abs(net_amount)) > 0.01:
                raise SourceResolutionRejected(
                    f"journal row amount {row.amount} does not match the "
                    f"transaction net_amount {net_amount}")
            if iso_date and abs(
                (_date.fromisoformat(row.date) - _date.fromisoformat(iso_date)).days
            ) > 4:
                raise SourceResolutionRejected(
                    f"journal row date {row.date} is outside ±4d of {iso_date}")
            _terminal(
                "operator_resolved_ambiguity",
                f"verified journal row id={row.id} ref={tx_id}: {operator_reason}",
                null_kind=False)

        elif choice_code == "matched_existing_row":
            payload = operator_custom_payload or {}
            cm_id = payload.get("cash_movement_id")
            candidates = envelope.get("candidate_cash_movement_ids") or []
            if cm_id is None or int(cm_id) not in [int(c) for c in candidates]:
                raise SourceResolutionRejected(
                    f"cash_movement_id {cm_id} is not in the envelope's "
                    f"candidate list {sorted(candidates)}")
            r = conn.execute(
                "SELECT id, kind, amount FROM cash_movements WHERE id=?",
                (int(cm_id),)).fetchone()
            if r is None:
                raise SourceResolutionRejected(
                    f"candidate cash_movement {cm_id} no longer exists")
            # Re-validate the candidate row's EXACT classified KIND at resolve
            # time (spec §4.3(c) "matching kind/amount"; Codex R1+R3 MAJOR).
            # matched_existing_row resolves ONLY fallback_multi_match rows, whose
            # candidates were ingested via `WHERE ref IS NULL AND kind = <disp>`
            # — and the fallback never handles income/fee, so the determinate
            # kind is deposit (net>0) or withdraw (net<0). Requiring the EXACT
            # kind (not just sign-compatibility) stops a stale same-amount
            # interest/dividend row from suppressing an ACH deposit. The
            # envelope's persisted expected_kind is preferred when present.
            expected_kind = envelope.get("expected_kind") or (
                "deposit" if net_amount > 0 else "withdraw")
            if r[1] != expected_kind:
                raise SourceResolutionRejected(
                    f"candidate cash_movement {cm_id} kind {r[1]!r} does not "
                    f"match the transaction's classified kind {expected_kind!r}")
            if abs(abs(float(r[2])) - abs(net_amount)) > 0.01:
                raise SourceResolutionRejected(
                    f"candidate cash_movement {cm_id} amount {r[2]} does not "
                    f"match the transaction net_amount {net_amount}")
            _terminal(
                "operator_resolved_ambiguity",
                f"matched_existing_cash_movement_id={cm_id}: {operator_reason}",
                null_kind=False)
        else:
            raise SourceResolutionRejected(
                f"unknown source-direction choice {choice_code!r}")

        conn.commit()
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
    environment: str | None = None,
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

    Sandbox short-circuit (plan §D.5 step 3 LOCK + spec §5.9): when
    ``environment == 'sandbox'``, skip steps 3-11 (no journal mutation,
    no correction INSERT, no discrepancy resolution update, no
    review_log supersede, no trade_events emit) and return a no-op
    ``CorrectionResult(correction_id=None, notes="sandbox: ...")``.
    Callers (the pivot dispatcher) MUST treat ``correction_id is None``
    as the no-op signal (do NOT increment ``tier1_applied_count``).
    """
    # Sandbox short-circuit (plan §D.5 step 3 + spec §5.9) FIRST — before
    # any validation of classification fields. Mirrors the outer wrapper's
    # pre-validation short-circuit so callers that pass the kwarg through
    # (the pivot dispatcher) get the same no-op contract without the
    # outer's tx-management. The pre-validation order matters: under
    # sandbox the outer never inspected classification, so a None-
    # classification call would have returned the no-op too.
    if environment == "sandbox":
        logger.warning(
            "_apply_tier1_correction_inner short-circuited under sandbox "
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

    # Codex R1 Major #2 — SELECT-first idempotency. A terminal
    # discrepancy returns its existing correction_id WITHOUT requiring a
    # valid classification payload (stale-caller-safe). The SELECT +
    # terminal-state check happens BEFORE any classification validation
    # so callers replaying a completed apply can pass `None` / stale /
    # malformed classification without getting a spurious ValueError.
    #
    # Step 1: SELECT discrepancy.
    disc = _select_discrepancy(conn, discrepancy_id)

    # Idempotency: terminal resolution → return existing (BEFORE
    # classification-payload validation per Codex R1 M#2 LOCK).
    if disc.resolution in _TERMINAL_RESOLUTIONS:
        return _idempotent_result_for(conn, discrepancy_id)

    # Classification-payload validation (post-SELECT, post-idempotency).
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
    applied_by_override: str | None = None,
    correction_action_override: str | None = None,
    resolved_by_override: str | None = None,
    environment: str = "production",
) -> CorrectionResult:
    """T-C.3 — spec §5.6 per-(kind, choice_code) dispatch. Caller owns tx.

    Phase 12.5 #1 T-1.4 introduces three ``*_override`` kwargs (all
    default ``None``) for the multi-leg auto-redirect dispatch path. The
    inner-fn step layout reserves room for T-1.6's sandbox short-circuit
    (between step 2.5 and step 3 below); T-1.4 ONLY adds steps 0 / 1.5 /
    2.5 — pure validation that fires before any handler dispatch.

    Step 0 (NEW T-1.4): :func:`_validate_override_combo` — fires BEFORE
            any DB I/O. Pure validation of the override-kwarg shape.
    Step 1 (existing): SELECT discrepancy. Unknown → raise.
    Step 1.5 (NEW T-1.4): post-SELECT secondary invariant —
            ``resolved_by_override == 'auto_tier1_multi_leg'`` requires
            ``disc.ambiguity_kind == 'multi_partial_vs_consolidated'``
            (spec §7.3.1.a R5 M1 LOCK; no other ambiguity_kind supports
            the auto-redirect path V1).
    Step 2 (existing): terminal-state idempotent return.
    Step 2.5 (NEW T-1.4): shape-aware terminal-state guard per spec
            §7.3.1.a R6 M1 LOCK — auto-redirect overrides against a
            terminal-state discrepancy whose chain head was NOT
            auto-resolved (``disc.resolved_by != 'auto_tier1_multi_leg'``)
            raise to prevent overwriting an operator decision.
    Step 2.6 (NEW T-1.6): sandbox short-circuit per spec §7.6.1 LOCK —
            when ``applied_by_override == 'auto'`` AND
            ``environment == 'sandbox'``, log a warning + raise
            :class:`_SandboxAutoRedirectShortCircuit`. Manual operator
            paths under sandbox proceed normally. Fires AFTER step 0
            (developer-bug guard still fires) AND AFTER step 1
            (SELECT-first idempotency contract honored per C.C lesson
            #3) but BEFORE handler dispatch.
    Step 3 (existing): verify resolution == 'pending_ambiguity_resolution'.
    Step 4 (existing): look up + dispatch handler by
            (ambiguity_kind, choice_code).
    """
    # Step 0 — fire override-shape validation BEFORE any DB I/O.
    _validate_override_combo(
        choice_code=choice_code,
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
    )

    # Step 1 — SELECT discrepancy.
    disc = _select_discrepancy(conn, discrepancy_id)

    # Step 1.5 — post-SELECT secondary invariant: the auto-redirect path is
    # only valid against multi_partial_vs_consolidated discrepancies.
    if (
        resolved_by_override == _AUTO_REDIRECT_RESOLVED_BY
        and disc.ambiguity_kind != "multi_partial_vs_consolidated"
    ):
        raise InvalidOverrideComboError(
            f"auto-redirect triple requires ambiguity_kind="
            f"'multi_partial_vs_consolidated'; discrepancy_id="
            f"{discrepancy_id} has ambiguity_kind={disc.ambiguity_kind!r}"
        )

    # Step 2 — terminal-state idempotent return.
    if disc.resolution in _TERMINAL_RESOLUTIONS:
        # Step 2.5 — shape-aware idempotency: prevent auto-redirect from
        # silently no-op'ing against a manually-resolved chain head.
        if resolved_by_override == _AUTO_REDIRECT_RESOLVED_BY:
            existing_resolved_by = _read_discrepancy_resolved_by(
                conn, discrepancy_id,
            )
            if existing_resolved_by != _AUTO_REDIRECT_RESOLVED_BY:
                raise InvalidOverrideComboError(
                    f"discrepancy_id={discrepancy_id} is already in "
                    f"terminal state {disc.resolution!r} with "
                    f"resolved_by={existing_resolved_by!r} (manual "
                    f"operator decision); cannot re-resolve via "
                    f"auto-redirect override"
                )
        return _idempotent_result_for(conn, discrepancy_id)

    # Step 2.6 (NEW T-1.6) — sandbox short-circuit per spec §7.6.1 LOCK.
    # Gated on the auto-redirect path (``applied_by_override == 'auto'``):
    # manual operator paths under sandbox proceed to the handler so
    # operators can test the menu choices in a sandbox environment.
    # Fires BEFORE the resolution precondition check + handler dispatch
    # (the sandbox is read-only for auto-redirect; the pivot loop catches
    # the sentinel + rolls back the immediately-preceding
    # ``_stamp_pending_ambiguity_inner`` stamp within its SAVEPOINT).
    if applied_by_override == "auto" and environment == "sandbox":
        logger.warning(
            "_apply_tier2_resolution_inner auto-redirect short-circuited "
            "under sandbox environment for discrepancy_id=%d; no domain "
            "writes",
            discrepancy_id,
        )
        raise _SandboxAutoRedirectShortCircuit(discrepancy_id)

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
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
    )


def _apply_tier3_override_inner(
    conn: sqlite3.Connection,
    *,
    correction_id: int,
    operator_truth_value: Mapping[str, Any],
    operator_reason: str,
    risk_policy_id: int | None = None,
) -> CorrectionResult:
    """T-C.4 — spec §5.7 + Codex R1 Minor #1 reorder (validator BEFORE mutation).

    Step 1: SELECT target correction row by correction_id.
    Step 2: Reject if superseded_by_correction_id IS NOT NULL.
    Step 3: Validator chain re-run on operator_truth_value BEFORE any
            mutation (defense-in-depth — operator-truth may violate
            invariants).
    Step 4: INSERT new correction row with correction_action=
            'operator_overridden' + operator_truth_value_json populated.
    Step 5: UPDATE prior row's superseded_by_correction_id = new id.
    Step 6: UPDATE journal column to operator-truth value.
    Step 7: _recompute_aggregates when affected_table == 'fills'.
    Step 8: UPDATE discrepancy resolution to 'operator_overridden'.
    Step 9: UPDATE review_log.superseded_by_correction_id (closed-trade).
    Step 10: INSERT trade_events row.
    """
    target = _select_correction_row(conn, correction_id)

    if target.superseded_by_correction_id is not None:
        raise AlreadySupersededError(
            f"correction_id={correction_id} is already superseded by "
            f"{target.superseded_by_correction_id}; override the current "
            f"chain head"
        )

    # Step 3: validator chain re-run on operator-truth (BEFORE mutation).
    chain = functools.partial(
        default_validator_chain(conn),
        affected_table=target.affected_table,
        affected_row_id=target.affected_row_id,
    )
    passes, rejection_reason = chain(operator_truth_value)
    if not passes:
        raise ValidatorRejectedError(
            f"validator rejected tier-3 operator_truth for "
            f"correction_id={correction_id} affected_table="
            f"{target.affected_table} affected_row_id="
            f"{target.affected_row_id}: {rejection_reason}"
        )

    # Determine the canonical field anchor.
    field_name = (
        "price" if "price" in operator_truth_value
        else next(iter(operator_truth_value.keys()))
    )

    # Step 4: INSERT new correction row.
    effective_policy_id = risk_policy_id
    if effective_policy_id is None:
        effective_policy_id = _maybe_get_active_risk_policy_id(conn)

    operator_truth_json = json.dumps(
        dict(operator_truth_value), sort_keys=True, default=str,
    )
    new_correction = ReconciliationCorrection(
        correction_id=0,
        discrepancy_id=target.discrepancy_id,
        correction_action="operator_overridden",
        correction_choice=None,
        affected_table=target.affected_table,
        affected_row_id=target.affected_row_id,
        field_name=field_name,
        pre_correction_value_json=target.applied_value_json,
        source_canonical_value_json=target.source_canonical_value_json,
        applied_value_json=operator_truth_json,
        operator_truth_value_json=operator_truth_json,
        applied_at=_utc_now_iso_ms(),
        applied_by="operator",
        correction_set_id=None,
        superseded_by_correction_id=None,
        risk_policy_id_at_correction=effective_policy_id,
        schwab_api_call_id=None,
        reconciliation_run_id=target.reconciliation_run_id,
        correction_reason=operator_reason,
        notes=None,
    )
    new_correction_id = insert_correction(conn, new_correction)

    # Step 5: chain pointer.
    update_superseded_by(
        conn,
        correction_id=correction_id,
        superseded_by_correction_id=new_correction_id,
    )

    # Step 6: UPDATE journal column to operator-truth value(s).
    pre_values_for_event: dict[str, Any] = {}
    for fname, fvalue in operator_truth_value.items():
        pre_values_for_event[fname] = _read_journal_value(
            conn, target.affected_table, target.affected_row_id, fname,
        )
        _update_journal_field(
            conn, target.affected_table, target.affected_row_id, fname, fvalue,
        )

    # Step 7: recompute aggregates for fills.
    if target.affected_table == _AFFECTED_TABLE_FILLS:
        trade_id = _get_fill_trade_id(conn, target.affected_row_id)
        _recompute_aggregates(conn, trade_id)

    # Step 8: UPDATE discrepancy resolution.
    conn.execute(
        "UPDATE reconciliation_discrepancies SET "
        "resolution = ?, resolution_reason = ?, "
        "resolved_at = ?, resolved_by = ? "
        "WHERE discrepancy_id = ?",
        (
            "operator_overridden", operator_reason,
            _utc_now_iso_ms(), "operator", target.discrepancy_id,
        ),
    )

    # Step 9: review_log supersede pointer for the new correction id.
    if target.affected_table == _AFFECTED_TABLE_FILLS:
        trade_id = _get_fill_trade_id(conn, target.affected_row_id)
        _supersede_review_log_for_trade_close(
            conn, trade_id=trade_id, new_correction_id=new_correction_id,
        )

    # Step 10: trade_events emit when affected_table is fills.
    if target.affected_table == _AFFECTED_TABLE_FILLS:
        trade_id = _get_fill_trade_id(conn, target.affected_row_id)
        _emit_trade_events_correction(
            conn,
            trade_id=trade_id,
            correction_id=new_correction_id,
            affected_table=target.affected_table,
            affected_row_id=target.affected_row_id,
            field_name=field_name,
            pre_value=pre_values_for_event.get(field_name),
            applied_value=operator_truth_value.get(field_name),
        )

    return CorrectionResult(
        correction_id=new_correction_id,
        affected_table=target.affected_table,
        affected_row_id=target.affected_row_id,
        field_name=field_name,
        applied_value_json=operator_truth_json,
        correction_action="operator_overridden",
        notes=None,
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
    expected_value_json: str | None


def _select_correction_row(
    conn: sqlite3.Connection, correction_id: int,
) -> ReconciliationCorrection:
    """Wrapper around ``get_correction`` that raises on unknown id."""
    row = get_correction(conn, correction_id)
    if row is None:
        raise ValueError(
            f"correction_id={correction_id} not found in "
            f"reconciliation_corrections"
        )
    return row


def _select_discrepancy(
    conn: sqlite3.Connection, discrepancy_id: int,
) -> _DiscrepancyInfo:
    row = conn.execute(
        "SELECT discrepancy_id, run_id, discrepancy_type, trade_id, "
        "fill_id, cash_movement_id, field_name, resolution, ambiguity_kind, "
        "expected_value_json "
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
        expected_value_json=row[9],
    )


def _read_discrepancy_resolved_by(
    conn: sqlite3.Connection, discrepancy_id: int,
) -> str | None:
    """Phase 12.5 #1 T-1.4 — narrow helper for the shape-aware terminal-
    state idempotency guard. Returns the discrepancy row's current
    ``resolved_by`` value (free TEXT; may be ``NULL`` for legacy rows).

    Kept separate from :func:`_select_discrepancy` to avoid widening the
    :class:`_DiscrepancyInfo` dataclass — ``resolved_by`` is consulted
    only by the auto-redirect override path.
    """
    row = conn.execute(
        "SELECT resolved_by FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (discrepancy_id,),
    ).fetchone()
    if row is None:
        return None
    return row[0]


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
    applied_by: str = "operator",
) -> ReconciliationCorrection:
    """Construct a ReconciliationCorrection row for the tier-2 audit emit.

    Phase 12.5 #1 T-1.4 — ``correction_action`` and ``applied_by`` are
    parameterized so multi-leg auto-redirect handlers can write the
    hybrid (auto_applied / auto) shape per F15 invariant. The legacy
    default for ``applied_by`` is ``'operator'`` (matches pre-T-1.4
    behavior byte-for-byte); ``correction_action`` was already a required
    parameter so no default change applies there.
    """
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
        applied_by=applied_by,
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
    resolved_by: str = "operator",
) -> None:
    """Phase 12.5 #1 T-1.4 — ``resolved_by`` parameterized for the
    multi-leg auto-redirect path (callers pass
    ``'auto_tier1_multi_leg'``). Legacy default ``'operator'`` preserves
    byte-for-byte pre-T-1.4 behavior.
    """
    conn.execute(
        "UPDATE reconciliation_discrepancies SET "
        "resolution = ?, resolution_reason = ?, "
        "resolved_at = ?, resolved_by = ? "
        "WHERE discrepancy_id = ?",
        (
            "operator_resolved_ambiguity", resolution_reason,
            _utc_now_iso_ms(), resolved_by, discrepancy_id,
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
    applied_by_override: str | None = None,
    correction_action_override: str | None = None,
    resolved_by_override: str | None = None,
) -> CorrectionResult:
    """Shared implementation for the no-journal-mutation choices.

    Used by keep_journal_as_is / mark_unmatched / acknowledge / custom
    (the V1 audit-only family per spec §6.2.1 + Codex R1 Critical #1).
    The audit row carries applied_value_json == pre_correction_value_json
    bytewise — the canonical no-mutation marker.

    Phase 12.5 #1 T-1.4 — accepts override kwargs for hybrid-row shape
    parity with the auto-redirect path (though no-mutation handlers are
    not the auto-redirect-sanctioned choice, the threading keeps the
    handler signature uniform across the family per F22).
    """
    affected_table, affected_row_id = _resolve_affected_target(disc)
    field_name = disc.field_name
    # Unmatched-fill discrepancies use a synthetic field_name='fill_match'
    # (set by swing/trades/schwab_reconciliation.py:672 for unmatched_open_fill
    # / unmatched_close_fill) which is NOT a real column on the fills table.
    # For these, skip the column read and use the discrepancy's
    # expected_value_json (the journal-recorded state at emit time) as the
    # no-mutation audit shape per spec §6.2.1 Codex R1 Critical #1 LOCK.
    if disc.discrepancy_type in ("unmatched_open_fill", "unmatched_close_fill"):
        pre_json = disc.expected_value_json or json.dumps(
            {field_name: None}, sort_keys=True,
        )
    else:
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
        correction_action=(
            correction_action_override
            if correction_action_override is not None
            else "operator_resolved_ambiguity"
        ),
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
        applied_by=(
            applied_by_override
            if applied_by_override is not None
            else "operator"
        ),
    )
    correction_id = insert_correction(conn, correction)
    _flip_discrepancy_to_resolved_ambiguity(
        conn,
        discrepancy_id=disc.discrepancy_id,
        resolution_reason=full_reason,
        resolved_by=(
            resolved_by_override
            if resolved_by_override is not None
            else "operator"
        ),
    )
    return CorrectionResult(
        correction_id=correction_id,
        affected_table=affected_table,
        affected_row_id=affected_row_id,
        field_name=field_name,
        applied_value_json=pre_json,
        correction_action=(
            correction_action_override
            if correction_action_override is not None
            else "operator_resolved_ambiguity"
        ),
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
    applied_by_override: str | None = None,
    correction_action_override: str | None = None,
    resolved_by_override: str | None = None,
) -> CorrectionResult:
    """Shared implementation for single-field UPDATE handlers.

    Used by consolidate_using_operator_vwap (price-only) +
    operator_alternative (validator-rejected re-run).

    Updates the journal column for the discrepancy's field_name with
    ``correction_target[field_name]``. Validates via the chain when
    ``revalidate=True``; raises ValueError("validator rejected ...")
    on rejection.

    Phase 12.5 #1 T-1.4 — accepts override kwargs for hybrid-row shape
    parity (F22).
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
    effective_correction_action = (
        correction_action_override
        if correction_action_override is not None
        else "operator_resolved_ambiguity"
    )
    effective_applied_by = (
        applied_by_override if applied_by_override is not None else "operator"
    )
    effective_resolved_by = (
        resolved_by_override if resolved_by_override is not None else "operator"
    )
    correction = _build_tier2_correction(
        disc=disc,
        correction_action=effective_correction_action,
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
        applied_by=effective_applied_by,
    )
    correction_id = insert_correction(conn, correction)

    _flip_discrepancy_to_resolved_ambiguity(
        conn,
        discrepancy_id=disc.discrepancy_id,
        resolution_reason=operator_reason,
        resolved_by=effective_resolved_by,
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
        correction_action=effective_correction_action,
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
    applied_by_override: str | None = None,
    correction_action_override: str | None = None,
    resolved_by_override: str | None = None,
) -> CorrectionResult:
    """Multi-column UPDATE handler — used by operator_truth /
    pick_schwab_record_<N> when the operator's payload carries multiple
    field-value pairs.

    Validator runs ONCE against the merged proposed-updates dict.
    INSERTs ONE correction row whose ``applied_value_json`` carries the
    full merged dict + ``field_name`` is the canonical 'price' anchor
    when present (else first key) for forward-compat with single-field
    queries.

    Phase 12.5 #1 T-1.4 — accepts override kwargs for hybrid-row shape
    parity (F22).
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
        for fname in correction_target
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

    effective_correction_action = (
        correction_action_override
        if correction_action_override is not None
        else "operator_resolved_ambiguity"
    )
    effective_applied_by = (
        applied_by_override if applied_by_override is not None else "operator"
    )
    effective_resolved_by = (
        resolved_by_override if resolved_by_override is not None else "operator"
    )
    correction = _build_tier2_correction(
        disc=disc,
        correction_action=effective_correction_action,
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
        applied_by=effective_applied_by,
    )
    correction_id = insert_correction(conn, correction)

    _flip_discrepancy_to_resolved_ambiguity(
        conn,
        discrepancy_id=disc.discrepancy_id,
        resolution_reason=operator_reason,
        resolved_by=effective_resolved_by,
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
        correction_action=effective_correction_action,
        notes=None,
    )


# ---------------------------------------------------------------------------
# Per-(kind, choice_code) handlers — small, focused functions.
# ---------------------------------------------------------------------------


def _handle_keep_journal_as_is(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
    applied_by_override=None, correction_action_override=None,
    resolved_by_override=None,
):
    return _handle_no_mutation_audit(
        conn, disc=disc, choice_code=choice_code,
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
    )


def _handle_consolidate_using_operator_vwap(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
    applied_by_override=None, correction_action_override=None,
    resolved_by_override=None,
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
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
    )


def _handle_split_into_partials(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
    applied_by_override=None, correction_action_override=None,
    resolved_by_override=None,
):
    """spec §6.2.1 split_into_partials — DELETE consolidated fill, INSERT
    N partial fills, write N+1 correction rows under one correction_set_id.

    Per spec §3.1.1 anchor-self-reference pattern: anchor (delete) row's
    correction_set_id = its own correction_id; the N insert rows share
    that correction_set_id.

    Phase 12.5 #1 T-1.4 — when the auto-redirect override triple is
    threaded in, ALL N+1 correction rows + the parent discrepancy carry
    the hybrid (auto_applied / auto / auto_tier1_multi_leg) shape per
    F15 invariant. Legacy default (no overrides) preserves byte-for-byte
    operator-shape behavior per F3.
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
    original_action = str(orig_row[3])
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

    # T-1.4 — compute effective override values ONCE; applied uniformly
    # to ALL N+1 correction rows + the parent discrepancy flip per F15.
    effective_correction_action = (
        correction_action_override
        if correction_action_override is not None
        else "operator_resolved_ambiguity"
    )
    effective_applied_by = (
        applied_by_override if applied_by_override is not None else "operator"
    )
    effective_resolved_by = (
        resolved_by_override if resolved_by_override is not None else "operator"
    )

    # Step 1: DELETE the consolidated fill + recompute aggregates ONCE.
    conn.execute("DELETE FROM fills WHERE fill_id = ?", (original_fill_id,))
    _recompute_aggregates(conn, trade_id)

    # Step 2: INSERT anchor (deletion-sentinel) correction row.
    anchor_correction = _build_tier2_correction(
        disc=disc,
        correction_action=effective_correction_action,
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
        applied_by=effective_applied_by,
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
            # Codex R2 Critical #1 fix — PRESERVE the original fill's
            # action (entry / exit / trim / stop) so close-fill
            # discrepancies (parent ``action='exit'``) do NOT silently
            # convert their N partials to ``'entry'`` rows. The
            # classifier's ``_classify_unmatched_fill_shared`` is shared
            # between ``unmatched_open_fill`` AND ``unmatched_close_fill``
            # per Sub-bundle C.B; both branches reach this handler.
            action=original_action,
            quantity=partial["qty"],
            price=partial["price"],
            reason=None,
            rule_based=None,
            fees=None,
            manual_entry_confidence=None,
            reconciliation_status="reconciled_discrepancy_resolved",
            tos_match_id=None,
        )
        # Suppress the per-fill action trade_event — the correction
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
    for new_fid, partial in zip(
        inserted_fill_ids, parsed_partials, strict=True,
    ):
        insert_payload_json = json.dumps(
            {
                "fill_id": new_fid,
                "trade_id": trade_id,
                "fill_datetime": partial["fill_datetime"],
                # Codex R2 Critical #1 fix — mirror the original fill's
                # action in the audit-row payload as well (see fix at
                # the partial-fill construction above).
                "action": original_action,
                "quantity": partial["qty"],
                "price": partial["price"],
            },
            sort_keys=True, default=str,
        )
        sub_correction = _build_tier2_correction(
            disc=disc,
            correction_action=effective_correction_action,
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
            applied_by=effective_applied_by,
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
        resolved_by=effective_resolved_by,
    )

    return CorrectionResult(
        correction_id=anchor_id,
        affected_table=_AFFECTED_TABLE_FILLS,
        affected_row_id=original_fill_id,
        field_name="__delete__",
        applied_value_json=anchor_correction.applied_value_json,
        correction_action=effective_correction_action,
        notes=f"split into {len(inserted_fill_ids)} partial fills",
    )


def _handle_custom_audit_only(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
    applied_by_override=None, correction_action_override=None,
    resolved_by_override=None,
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
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
    )


def _handle_mark_unmatched(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
    applied_by_override=None, correction_action_override=None,
    resolved_by_override=None,
):
    return _handle_no_mutation_audit(
        conn, disc=disc, choice_code=choice_code,
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
    )


def _handle_acknowledge(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
    applied_by_override=None, correction_action_override=None,
    resolved_by_override=None,
):
    return _handle_no_mutation_audit(
        conn, disc=disc, choice_code=choice_code,
        operator_reason=operator_reason,
        risk_policy_id=risk_policy_id,
        schwab_api_call_id=schwab_api_call_id,
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
    )


def _handle_operator_truth(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
    applied_by_override=None, correction_action_override=None,
    resolved_by_override=None,
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
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
    )


def _handle_operator_alternative(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
    applied_by_override=None, correction_action_override=None,
    resolved_by_override=None,
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
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
    )


def _handle_pick_schwab_record_n(
    conn, *, disc, choice_code, operator_custom_payload,
    operator_reason, risk_policy_id, schwab_api_call_id,
    applied_by_override=None, correction_action_override=None,
    resolved_by_override=None,
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
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
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
        _handle_pick_schwab_record_n,
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
