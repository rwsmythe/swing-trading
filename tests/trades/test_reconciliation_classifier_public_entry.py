"""T-B.1 — ``classify_discrepancy`` public entry + ``ClassificationResult``.

Tests the SKELETON contract (dispatch dispatch-table; dataclass shape;
graceful-degradation; determinism; validator-respecting downgrade). The
per-discrepancy-type sub-classifiers land in T-B.3..T-B.12 with their own
test files; THIS file pins ONLY the dispatcher.
"""
from __future__ import annotations

from typing import Any, Mapping

import pytest

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import (
    ClassificationResult,
    _SUB_CLASSIFIERS,
    classify_discrepancy,
)


# ---------------------------------------------------------------------------
# Fixture: planted discrepancy rows (in-memory dataclass instances — the
# classifier is pure-logic, no DB needed for these unit tests).
# ---------------------------------------------------------------------------


def _make_discrepancy(
    *,
    discrepancy_type: str,
    discrepancy_id: int = 41,
    field_name: str = "price",
) -> ReconciliationDiscrepancy:
    """Construct a minimal valid discrepancy dataclass instance."""
    return ReconciliationDiscrepancy(
        discrepancy_id=discrepancy_id,
        run_id=1,
        discrepancy_type=discrepancy_type,
        trade_id=1,
        fill_id=9,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="CVGI",
        field_name=field_name,
        expected_value_json='{"price": 5.23}',
        actual_value_json='{"price": 5.30}',
        delta_text="+$0.07 (schwab minus journal)",
        material_to_review=1,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )


@pytest.fixture
def planted_cvgi_discrepancy() -> ReconciliationDiscrepancy:
    return _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        discrepancy_id=41,
    )


# ---------------------------------------------------------------------------
# ClassificationResult dataclass shape
# ---------------------------------------------------------------------------


def test_classification_result_dataclass_shape() -> None:
    """Dataclass exposes the 5 fields per spec §4.2."""
    cr = ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="entry_price_mismatch on CVGI",
        candidate_choices=None,
    )
    assert cr.tier == 1
    assert cr.ambiguity_kind is None
    assert cr.correction_target == {"price": 5.30}
    assert cr.correction_reason == "entry_price_mismatch on CVGI"
    assert cr.candidate_choices is None


def test_classification_result_is_frozen() -> None:
    """Frozen dataclass guarantees deep equality for determinism contract."""
    cr = ClassificationResult(
        tier=2,
        ambiguity_kind="unsupported",
        correction_target=None,
        correction_reason="test",
    )
    # Attempt to mutate; frozen dataclass raises FrozenInstanceError.
    with pytest.raises(Exception):  # noqa: BLE001 — explicit frozen check
        cr.tier = 1  # type: ignore[misc]


def test_classification_result_equality_is_deep() -> None:
    """Two identical-input results compare equal via dataclass __eq__."""
    a = ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="x",
        candidate_choices=None,
    )
    b = ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="x",
        candidate_choices=None,
    )
    assert a == b


# ---------------------------------------------------------------------------
# Public entry signature + dispatch
# ---------------------------------------------------------------------------


def test_classify_discrepancy_returns_classification_result(
    planted_cvgi_discrepancy: ReconciliationDiscrepancy,
) -> None:
    """``classify_discrepancy`` returns a ``ClassificationResult`` instance."""
    result = classify_discrepancy(
        planted_cvgi_discrepancy,
        source_payload={"price": 5.30},
        journal_row={"price": 5.23, "quantity": 100, "trade_id": 1},
        validator_chain=None,
    )
    assert isinstance(result, ClassificationResult)


def test_classify_discrepancy_accepts_kwargs_only_after_discrepancy(
    planted_cvgi_discrepancy: ReconciliationDiscrepancy,
) -> None:
    """``source_payload``, ``journal_row``, ``validator_chain`` are keyword-only."""
    # Positional invocation past the first arg MUST raise TypeError.
    with pytest.raises(TypeError):
        classify_discrepancy(
            planted_cvgi_discrepancy,
            {"price": 5.30},  # type: ignore[misc] — would-be source_payload positional
        )


# ---------------------------------------------------------------------------
# Graceful-degradation contract (spec §4.5)
# ---------------------------------------------------------------------------


def test_classify_discrepancy_unknown_type_returns_tier_2_unsupported() -> None:
    """Unknown discrepancy_type → tier-2 unsupported (no exception escapes)."""
    # Build a discrepancy with a discrepancy_type NOT in _SUB_CLASSIFIERS.
    # We must bypass the dataclass CHECK by using a synthetic value that
    # passes the dataclass enum check; instead we plant via dict-subclass
    # since the dataclass __post_init__ validates discrepancy_type against
    # the shipped enum. To get "unrecognized" through, we use a real type
    # ('cash_movement_mismatch') and temporarily un-register it.
    discrepancy = _make_discrepancy(
        discrepancy_type="cash_movement_mismatch",
        discrepancy_id=999,
    )
    # Save then clear the dispatch table entry (if any) for the duration
    # of this test. The dispatch table is the module-level dict.
    saved = _SUB_CLASSIFIERS.pop("cash_movement_mismatch", None)
    try:
        result = classify_discrepancy(
            discrepancy,
            source_payload=None,
            journal_row=None,
            validator_chain=None,
        )
        assert result.tier == 2
        assert result.ambiguity_kind == "unsupported"
        assert result.correction_target is None
        assert "cash_movement_mismatch" in result.correction_reason
    finally:
        if saved is not None:
            _SUB_CLASSIFIERS["cash_movement_mismatch"] = saved


def test_classify_discrepancy_sub_classifier_exception_returns_tier_2(
    planted_cvgi_discrepancy: ReconciliationDiscrepancy,
) -> None:
    """Sub-classifier raises → dispatcher catches → tier-2 unsupported."""
    def _raising_sub(**kwargs: Any) -> ClassificationResult:
        raise RuntimeError("synthetic sub-classifier defect")

    saved = _SUB_CLASSIFIERS.pop("entry_price_mismatch", None)
    _SUB_CLASSIFIERS["entry_price_mismatch"] = _raising_sub
    try:
        result = classify_discrepancy(
            planted_cvgi_discrepancy,
            source_payload={"price": 5.30},
            journal_row=None,
            validator_chain=None,
        )
        assert result.tier == 2
        assert result.ambiguity_kind == "unsupported"
        assert "classifier exception" in result.correction_reason
        assert "RuntimeError" in result.correction_reason
        assert "synthetic sub-classifier defect" in result.correction_reason
    finally:
        # Restore original registration (or remove if there was none).
        if saved is not None:
            _SUB_CLASSIFIERS["entry_price_mismatch"] = saved
        else:
            _SUB_CLASSIFIERS.pop("entry_price_mismatch", None)


# ---------------------------------------------------------------------------
# Determinism contract (spec §4.4)
# ---------------------------------------------------------------------------


def test_classifier_is_deterministic_on_unknown_type() -> None:
    """100x invocation with same inputs → byte-for-byte identical result.

    Uses the unknown-discrepancy_type path because that dispatch branch is
    available at T-B.1 ship time without any sub-classifier registered.
    Frozen-dataclass deep equality verifies byte-for-byte stability.
    """
    discrepancy = _make_discrepancy(
        discrepancy_type="cash_movement_mismatch",
        discrepancy_id=999,
    )
    saved = _SUB_CLASSIFIERS.pop("cash_movement_mismatch", None)
    try:
        first = classify_discrepancy(
            discrepancy,
            source_payload=None,
            journal_row=None,
            validator_chain=None,
        )
        for _ in range(99):
            nth = classify_discrepancy(
                discrepancy,
                source_payload=None,
                journal_row=None,
                validator_chain=None,
            )
            assert nth == first  # frozen dataclass equality is deep
    finally:
        if saved is not None:
            _SUB_CLASSIFIERS["cash_movement_mismatch"] = saved


# ---------------------------------------------------------------------------
# Validator-respecting downgrade (spec §4.6)
# ---------------------------------------------------------------------------


def test_validator_chain_invoked_on_tier_1_and_rejection_downgrades(
    planted_cvgi_discrepancy: ReconciliationDiscrepancy,
) -> None:
    """Validator returns ``(False, reason)`` → dispatcher downgrades to tier-2."""

    def _tier_1_sub(**kwargs: Any) -> ClassificationResult:
        return ClassificationResult(
            tier=1,
            ambiguity_kind=None,
            correction_target={"price": 5.30},
            correction_reason="planted tier-1 for validator-downgrade test",
            candidate_choices=None,
        )

    def _rejecting_validator(target: Mapping[str, Any]) -> tuple[bool, str | None]:
        return (False, "test rejection")

    saved = _SUB_CLASSIFIERS.pop("entry_price_mismatch", None)
    _SUB_CLASSIFIERS["entry_price_mismatch"] = _tier_1_sub
    try:
        result = classify_discrepancy(
            planted_cvgi_discrepancy,
            source_payload={"price": 5.30},
            journal_row=None,
            validator_chain=_rejecting_validator,
        )
        assert result.tier == 2
        assert result.ambiguity_kind == "validator_rejected"
        assert result.correction_target is None
        assert "test rejection" in result.correction_reason
    finally:
        if saved is not None:
            _SUB_CLASSIFIERS["entry_price_mismatch"] = saved
        else:
            _SUB_CLASSIFIERS.pop("entry_price_mismatch", None)


def test_validator_chain_passes_keeps_tier_1(
    planted_cvgi_discrepancy: ReconciliationDiscrepancy,
) -> None:
    """Validator returns ``(True, None)`` → dispatcher preserves tier-1."""

    def _tier_1_sub(**kwargs: Any) -> ClassificationResult:
        return ClassificationResult(
            tier=1,
            ambiguity_kind=None,
            correction_target={"price": 5.30},
            correction_reason="planted tier-1 for validator-pass test",
            candidate_choices=None,
        )

    def _passing_validator(target: Mapping[str, Any]) -> tuple[bool, str | None]:
        return (True, None)

    saved = _SUB_CLASSIFIERS.pop("entry_price_mismatch", None)
    _SUB_CLASSIFIERS["entry_price_mismatch"] = _tier_1_sub
    try:
        result = classify_discrepancy(
            planted_cvgi_discrepancy,
            source_payload={"price": 5.30},
            journal_row=None,
            validator_chain=_passing_validator,
        )
        assert result.tier == 1
        assert result.correction_target == {"price": 5.30}
    finally:
        if saved is not None:
            _SUB_CLASSIFIERS["entry_price_mismatch"] = saved
        else:
            _SUB_CLASSIFIERS.pop("entry_price_mismatch", None)


def test_validator_chain_not_invoked_on_tier_2(
    planted_cvgi_discrepancy: ReconciliationDiscrepancy,
) -> None:
    """Tier-2 sub-classifier output → validator NOT invoked (no downgrade)."""

    invocations = {"count": 0}

    def _tier_2_sub(**kwargs: Any) -> ClassificationResult:
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason="planted tier-2 for no-invoke test",
        )

    def _tracking_validator(target: Mapping[str, Any]) -> tuple[bool, str | None]:
        invocations["count"] += 1
        return (True, None)

    saved = _SUB_CLASSIFIERS.pop("entry_price_mismatch", None)
    _SUB_CLASSIFIERS["entry_price_mismatch"] = _tier_2_sub
    try:
        result = classify_discrepancy(
            planted_cvgi_discrepancy,
            source_payload=None,
            journal_row=None,
            validator_chain=_tracking_validator,
        )
        assert result.tier == 2
        assert invocations["count"] == 0
    finally:
        if saved is not None:
            _SUB_CLASSIFIERS["entry_price_mismatch"] = saved
        else:
            _SUB_CLASSIFIERS.pop("entry_price_mismatch", None)


def test_validator_chain_raises_treated_as_rejection(
    planted_cvgi_discrepancy: ReconciliationDiscrepancy,
) -> None:
    """Validator raises → dispatcher treats as rejection (tier-2 downgrade)."""

    def _tier_1_sub(**kwargs: Any) -> ClassificationResult:
        return ClassificationResult(
            tier=1,
            ambiguity_kind=None,
            correction_target={"price": 5.30},
            correction_reason="planted tier-1 for validator-raise test",
            candidate_choices=None,
        )

    def _raising_validator(target: Mapping[str, Any]) -> tuple[bool, str | None]:
        raise RuntimeError("validator defect")

    saved = _SUB_CLASSIFIERS.pop("entry_price_mismatch", None)
    _SUB_CLASSIFIERS["entry_price_mismatch"] = _tier_1_sub
    try:
        result = classify_discrepancy(
            planted_cvgi_discrepancy,
            source_payload={"price": 5.30},
            journal_row=None,
            validator_chain=_raising_validator,
        )
        assert result.tier == 2
        assert result.ambiguity_kind == "validator_rejected"
        assert "validator chain raised" in result.correction_reason
        assert "RuntimeError" in result.correction_reason
    finally:
        if saved is not None:
            _SUB_CLASSIFIERS["entry_price_mismatch"] = saved
        else:
            _SUB_CLASSIFIERS.pop("entry_price_mismatch", None)
