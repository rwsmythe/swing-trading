"""T-B.12 — ``equity_delta`` sub-classifier (tier-2-always V1).

Spec §4.3.10 LOCK: cash-basis-vs-MTM semantics divergence is a Phase 10
operator-locked V2 candidate.
"""
from __future__ import annotations

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import classify_discrepancy


def _make_equity_delta_discrepancy() -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=120,
        run_id=1,
        discrepancy_type="equity_delta",
        trade_id=None,
        fill_id=None,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker=None,
        field_name="equity_delta_dollars",
        expected_value_json='{"journal_equity": 2000.00}',
        actual_value_json='{"source_equity": 2034.78}',
        delta_text="+$34.78",
        material_to_review=0,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )


def test_equity_delta_tier_2_field_shape_incompatible() -> None:
    """V1 LOCK: equity_delta always tier-2 ``field_shape_incompatible``."""
    discrepancy = _make_equity_delta_discrepancy()
    for source_payload in [None, {"source_equity": 2034.78}, []]:
        result = classify_discrepancy(
            discrepancy,
            source_payload=source_payload,
            journal_row={"journal_equity": 2000.00},
            validator_chain=None,
        )
        assert result.tier == 2
        assert result.ambiguity_kind == "field_shape_incompatible"


def test_equity_delta_reason_mentions_cash_basis_vs_mtm_v2() -> None:
    """Plan §C.12 acceptance #2: rationale cites Phase 10 V2 candidate."""
    discrepancy = _make_equity_delta_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row=None,
        validator_chain=None,
    )
    assert (
        "cash-basis" in result.correction_reason.lower()
        or "cash_basis" in result.correction_reason.lower()
    )
    assert "mtm" in result.correction_reason.lower()
    assert "v2" in result.correction_reason.lower()


def test_equity_delta_emits_acknowledge_or_operator_truth_menu() -> None:
    discrepancy = _make_equity_delta_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row=None,
        validator_chain=None,
    )
    assert result.candidate_choices is not None
    codes = {c["code"] for c in result.candidate_choices}
    assert "acknowledge" in codes
    assert "operator_truth" in codes
