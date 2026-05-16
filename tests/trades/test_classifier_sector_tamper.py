"""T-B.10 — ``sector_tamper`` sub-classifier (tier-2-always V1).

Spec §4.3.8 LOCK: Schwab doesn't supply sector data; operator-action-only.
"""
from __future__ import annotations

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import classify_discrepancy


def _make_sector_tamper_discrepancy() -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=100,
        run_id=1,
        discrepancy_type="sector_tamper",
        trade_id=1,
        fill_id=None,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="CVGI",
        field_name="sector",
        expected_value_json=(
            '{"sector": "Energy", "industry": "Oil & Gas Midstream"}'
        ),
        actual_value_json='{"sector": "Technology"}',
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


def test_sector_tamper_tier_2_always() -> None:
    """V1 LOCK: sector_tamper tier-2-always."""
    discrepancy = _make_sector_tamper_discrepancy()
    for source_payload in [
        None,
        {"sector": "Energy"},
        [],
        "bogus",
    ]:
        result = classify_discrepancy(
            discrepancy,
            source_payload=source_payload,
            journal_row=None,
            validator_chain=None,
        )
        assert result.tier == 2
        assert result.ambiguity_kind == "unknown_schwab_subtype"


def test_sector_tamper_reason_mentions_schwab_does_not_supply() -> None:
    discrepancy = _make_sector_tamper_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row=None,
        validator_chain=None,
    )
    assert "sector" in result.correction_reason.lower()
    assert (
        "schwab does not supply" in result.correction_reason.lower()
        or "schwab doesn't supply" in result.correction_reason.lower()
    )


def test_sector_tamper_emits_3_choice_unknown_subtype_menu() -> None:
    discrepancy = _make_sector_tamper_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row=None,
        validator_chain=None,
    )
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 3
