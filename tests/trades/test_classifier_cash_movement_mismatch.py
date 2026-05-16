"""T-B.9 — ``cash_movement_mismatch`` sub-classifier.

Tier-1 single-match path; tier-2 otherwise. Tier-1 ``correction_target``
carries multi-field atomically per spec §4.4 + §3.1.1.
"""
from __future__ import annotations

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import classify_discrepancy


def _make_cash_movement_discrepancy() -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=90,
        run_id=1,
        discrepancy_type="cash_movement_mismatch",
        trade_id=None,
        fill_id=None,
        cash_movement_id=5,
        linked_daily_management_record_id=None,
        ticker=None,
        field_name="amount",
        expected_value_json='{"amount": 1000.00}',
        actual_value_json='{"amount": 1001.50}',
        delta_text="+$1.50",
        material_to_review=0,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )


def test_cash_movement_mismatch_tier_1_single_match_field_diff() -> None:
    """Single broker match with one differing field → tier-1 correction."""
    discrepancy = _make_cash_movement_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={
            "date": "2026-04-27",
            "kind": "deposit",
            "amount": 1001.50,
            "ref": "BROKER-123",
        },
        journal_row={
            "date": "2026-04-27",
            "kind": "deposit",
            "amount": 1000.00,
            "ref": "BROKER-123",
        },
        validator_chain=None,
    )
    assert result.tier == 1
    assert result.correction_target == {"amount": 1001.50}


def test_cash_movement_mismatch_tier_1_multifield_correction() -> None:
    """Single broker match with two differing fields → multi-field
    correction_target."""
    discrepancy = _make_cash_movement_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={
            "date": "2026-04-27",
            "kind": "deposit",
            "amount": 1001.50,
            "ref": "BROKER-NEW",
        },
        journal_row={
            "date": "2026-04-27",
            "kind": "deposit",
            "amount": 1000.00,
            "ref": "BROKER-OLD",
        },
        validator_chain=None,
    )
    assert result.tier == 1
    assert result.correction_target == {
        "amount": 1001.50,
        "ref": "BROKER-NEW",
    }


def test_cash_movement_mismatch_tier_2_when_no_match() -> None:
    discrepancy = _make_cash_movement_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row={"amount": 1000.00},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "schwab_returned_no_match"


def test_cash_movement_mismatch_tier_2_when_multi_match() -> None:
    discrepancy = _make_cash_movement_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[
            {"date": "2026-04-27", "amount": 1001.50},
            {"date": "2026-04-27", "amount": 1002.00},
        ],
        journal_row={"date": "2026-04-27", "amount": 1000.00},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_match_within_window"


def test_cash_movement_mismatch_tier_2_when_source_matches_journal() -> None:
    """Stale discrepancy: source matches journal → unsupported (operator
    acknowledges)."""
    discrepancy = _make_cash_movement_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"amount": 1000.00, "ref": "BROKER-123"},
        journal_row={"amount": 1000.00, "ref": "BROKER-123"},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"


def test_cash_movement_mismatch_tier_2_when_source_payload_empty_list() -> None:
    discrepancy = _make_cash_movement_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[],
        journal_row={"amount": 1000.00},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "schwab_returned_no_match"
