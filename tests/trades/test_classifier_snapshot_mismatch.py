"""T-B.11 — ``snapshot_mismatch`` sub-classifier (tier-2-always V1)."""
from __future__ import annotations

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import classify_discrepancy


def _make_snapshot_mismatch_discrepancy() -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=110,
        run_id=1,
        discrepancy_type="snapshot_mismatch",
        trade_id=1,
        fill_id=None,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="DHC",
        field_name="entry_chart_pattern_snapshot",
        expected_value_json='{"snapshot": "vcp"}',
        actual_value_json='{"snapshot": "consolidation"}',
        delta_text=None,
        material_to_review=0,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )


def test_snapshot_mismatch_tier_2_always() -> None:
    discrepancy = _make_snapshot_mismatch_discrepancy()
    for source_payload in [
        None,
        {"snapshot": "vcp"},
        [{"snapshot": "vcp"}],
        [],
    ]:
        result = classify_discrepancy(
            discrepancy,
            source_payload=source_payload,
            journal_row=None,
            validator_chain=None,
        )
        assert result.tier == 2
        assert result.ambiguity_kind == "unknown_schwab_subtype"


def test_snapshot_mismatch_emits_3_choice_unknown_subtype_menu() -> None:
    discrepancy = _make_snapshot_mismatch_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row=None,
        validator_chain=None,
    )
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 3
