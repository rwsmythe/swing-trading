"""Phase 12 Sub-sub-bundle C.B — pure-logic discrepancy classifier.

Spec §4 ``classify_discrepancy`` + per-discrepancy-type sub-classifiers.

Public entry: :func:`classify_discrepancy` (pure function; no DB writes; no
external API calls; no transaction management). Caller supplies pre-fetched
``source_payload`` + ``journal_row`` data. Per-type sub-classifiers register
into ``_SUB_CLASSIFIERS`` at module-load time; ``classify_discrepancy``
dispatches on ``discrepancy.discrepancy_type``.

Determinism contract (spec §4.4): same inputs → same ``ClassificationResult``
byte-for-byte. Frozen dataclass equality is deep.

Failure-mode contract (spec §4.5): unknown ``discrepancy_type`` or
sub-classifier exception → ``(tier=2, ambiguity_kind='unsupported',
correction_target=None, correction_reason="classifier exception: ...")``.
Pipeline / CLI never crashes from a classifier defect.

Validator-respecting downgrade (spec §4.6): when ``validator_chain`` is
supplied AND the sub-classifier returned tier-1, the dispatcher invokes
``validator_chain(correction_target)``. On ``(False, reason)``, the
dispatcher downgrades to ``(tier=2, ambiguity_kind='validator_rejected',
correction_target=None, correction_reason="validator rejected proposed
correction: <reason or 'unknown'>")``.

Pass-2-tier-1-FORBIDDEN LOCK (spec §8.4): ``_classify_unmatched_open_fill``
+ ``_classify_unmatched_close_fill`` NEVER emit tier-1 in V1 regardless of
Pass-2 input shape. Order-level Schwab data is limit/order price, not
execution price; cannot drive tier-1 auto-correct without operator-side
broker-statement consultation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from swing.data.models import ReconciliationDiscrepancy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClassificationResult:
    """Classifier output — pure data shape; tier ∈ {1, 2}.

    Tier-3 is operator-initiated post-tier-1; the classifier NEVER emits
    ``tier=3``. ``ambiguity_kind`` MUST be ``None`` when ``tier == 1`` and
    MUST be one of the 7-value enum from migration 0019 line 125-129 when
    ``tier == 2`` (cross-column CHECK precedence per C.A lesson #2 +
    migration 0019 cross-column CHECK at lines 135-147).

    ``candidate_choices`` is ``None`` for tier-1; for tier-2 it is a list of
    per-choice dicts with keys ``code`` / ``description`` / ``requires_custom_value:
    bool`` per spec §6.2.1 LOCKED contract (Codex R5 Major #2 fix).
    """

    tier: int
    ambiguity_kind: str | None
    correction_target: dict[str, Any] | None
    correction_reason: str
    candidate_choices: list[dict[str, Any]] | None = None


# Callable contract: ``(correction_target) -> (passes, rejection_reason_or_None)``.
# The dispatcher calls this with a single positional arg; callers compose
# ``default_validator_chain`` via ``functools.partial`` at C.C construction
# time to bind ``affected_table`` + ``affected_row_id`` (spec §5.5).
ValidatorChainCallable = Callable[[Mapping[str, Any]], tuple[bool, str | None]]


# Dispatch table populated as sub-classifiers land (T-B.3..T-B.12 register
# into this dict at module-load time via direct assignment below their
# function definitions). Unknown discrepancy_type values miss this lookup
# and trigger the graceful-degradation path at the dispatcher.
_SUB_CLASSIFIERS: dict[str, Callable[..., ClassificationResult]] = {}


def classify_discrepancy(
    discrepancy: ReconciliationDiscrepancy,
    *,
    source_payload: Any | None,
    journal_row: Mapping[str, Any] | None,
    validator_chain: ValidatorChainCallable | None = None,
) -> ClassificationResult:
    """Pure classifier; dispatches on ``discrepancy.discrepancy_type``.

    Args:
        discrepancy: The ``ReconciliationDiscrepancy`` to classify.
        source_payload: Pre-fetched broker-side payload (shape varies per
            discrepancy_type; ``None`` means no broker data available).
        journal_row: Pre-fetched journal-side row (e.g., the ``fills`` row
            for fill-shaped discrepancies; ``None`` when unavailable).
        validator_chain: Optional callable that dry-runs the proposed
            ``correction_target`` against schema-CHECK-mirror predicates.
            When provided AND classifier emits tier-1, the dispatcher
            invokes the chain; a ``(False, reason)`` return downgrades to
            tier-2 ``validator_rejected``.

    Returns:
        ``ClassificationResult`` per spec §4.2. ALWAYS returns a result;
        never raises (spec §4.5 graceful-degradation contract).
    """
    sub = _SUB_CLASSIFIERS.get(discrepancy.discrepancy_type)
    if sub is None:
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"no sub-classifier registered for discrepancy_type="
                f"{discrepancy.discrepancy_type!r}"
            ),
        )
    try:
        result = sub(
            discrepancy=discrepancy,
            source_payload=source_payload,
            journal_row=journal_row,
        )
    except Exception as e:  # noqa: BLE001 — graceful degradation per spec §4.5
        logger.warning(
            "classifier exception for discrepancy %s (%s): %s: %s",
            discrepancy.discrepancy_id,
            discrepancy.discrepancy_type,
            type(e).__name__,
            e,
        )
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"classifier exception: {type(e).__name__}: {e}"
            ),
        )

    if result.tier == 1 and validator_chain is not None:
        try:
            passes, reason = validator_chain(result.correction_target or {})
        except Exception as e:  # noqa: BLE001 — validator-side defect must not crash
            logger.warning(
                "validator_chain exception for discrepancy %s: %s: %s",
                discrepancy.discrepancy_id,
                type(e).__name__,
                e,
            )
            return ClassificationResult(
                tier=2,
                ambiguity_kind="validator_rejected",
                correction_target=None,
                correction_reason=(
                    f"validator chain raised: {type(e).__name__}: {e}"
                ),
            )
        if not passes:
            return ClassificationResult(
                tier=2,
                ambiguity_kind="validator_rejected",
                correction_target=None,
                correction_reason=(
                    f"validator rejected proposed correction: "
                    f"{reason or 'unknown'}"
                ),
            )
    return result
