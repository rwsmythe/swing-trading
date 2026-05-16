"""T-B.7 — ``position_qty_mismatch`` sub-classifier (tier-2-always V1)."""
from __future__ import annotations

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import classify_discrepancy


def _make_position_qty_discrepancy() -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=70,
        run_id=1,
        discrepancy_type="position_qty_mismatch",
        trade_id=1,
        fill_id=None,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="LAR",
        field_name="quantity",
        expected_value_json='{"quantity": 100}',
        actual_value_json='{"quantity": 95}',
        delta_text="-5",
        material_to_review=1,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )


def test_position_qty_mismatch_tier_2_with_one_broker_record_and_few_fills() -> None:
    """Broker has 1 record + journal has small fills count (<=3) →
    multi_match_within_window per fill."""
    discrepancy = _make_position_qty_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"quantity": 95},
        journal_row={
            "ticker": "LAR",
            "fills": [
                {"fill_id": 10, "quantity": 50},
                {"fill_id": 11, "quantity": 50},
            ],
        },
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_match_within_window"


def test_position_qty_mismatch_tier_2_when_broker_has_zero_positions() -> None:
    """Broker has 0 positions + journal has open trade → schwab_returned_no_match."""
    discrepancy = _make_position_qty_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[],
        journal_row={"ticker": "LAR", "fills": [{"fill_id": 10}]},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "schwab_returned_no_match"


def test_position_qty_mismatch_tier_2_default_unsupported() -> None:
    """No specific branch matches → tier-2 unsupported."""
    discrepancy = _make_position_qty_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload="bogus-scalar",
        journal_row={"ticker": "LAR"},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"


def test_position_qty_mismatch_never_emits_tier_1() -> None:
    """V1 LOCK: position_qty_mismatch is tier-2-always."""
    discrepancy = _make_position_qty_discrepancy()
    for source_payload in [
        None,
        [],
        {"quantity": 95},
        [{"quantity": 95}],
        "bogus",
    ]:
        result = classify_discrepancy(
            discrepancy,
            source_payload=source_payload,
            journal_row={"ticker": "LAR", "fills": [{"fill_id": 10}]},
            validator_chain=None,
        )
        assert result.tier == 2, (
            f"V1 LOCK violated: position_qty_mismatch emitted tier-1 for "
            f"source_payload={source_payload!r}"
        )
