"""T-B.8 — ``close_price_mismatch`` sub-classifier (tier-2-always V1)."""
from __future__ import annotations

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import classify_discrepancy


def _make_close_price_discrepancy() -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=80,
        run_id=1,
        discrepancy_type="close_price_mismatch",
        trade_id=1,
        fill_id=None,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="DHC",
        field_name="close_price",
        expected_value_json='{"close": 7.50}',
        actual_value_json='{"close": 7.55}',
        delta_text="+$0.05",
        material_to_review=0,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )


def test_close_price_mismatch_tier_2_always() -> None:
    """V1 LOCK: close_price_mismatch tier-2-always; V2 OHLCV re-import banked."""
    discrepancy = _make_close_price_discrepancy()
    for source_payload in [
        None,
        {"close": 7.55},
        [{"close": 7.55}],
        [],
        "bogus",
    ]:
        result = classify_discrepancy(
            discrepancy,
            source_payload=source_payload,
            journal_row={"close": 7.50},
            validator_chain=None,
        )
        assert result.tier == 2
        assert result.ambiguity_kind == "unknown_schwab_subtype"


def test_close_price_mismatch_emits_3_choice_unknown_subtype_menu() -> None:
    """spec §6.2.1 — unknown_schwab_subtype emits 3 choices."""
    discrepancy = _make_close_price_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row=None,
        validator_chain=None,
    )
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 3
    codes = {c["code"] for c in result.candidate_choices}
    assert codes == {"acknowledge", "operator_truth", "custom"}


def test_close_price_mismatch_reason_mentions_v2() -> None:
    discrepancy = _make_close_price_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row=None,
        validator_chain=None,
    )
    # Plan §C.8 acceptance #1 — V2 candidate banked in reason.
    assert "V2" in result.correction_reason
