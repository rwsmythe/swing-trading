"""T-B.6 — ``stop_mismatch`` sub-classifier.

Spec §4.3.4 — tier-1 ALLOWED (unlike unmatched_*_fill).

Key BINDING criterion (plan §C.6 acceptance #2 + spec §1.6 advisory-not-
validator family): tier-1 emissions DO NOT consult Phase 9 risk_policy
advisory thresholds. Advisories surface at Phase 10 dashboard time.
"""
from __future__ import annotations

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import classify_discrepancy


def _make_stop_mismatch_discrepancy(
    *,
    discrepancy_id: int = 60,
    trade_id: int = 1,
    ticker: str = "DHC",
) -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=discrepancy_id,
        run_id=1,
        discrepancy_type="stop_mismatch",
        trade_id=trade_id,
        fill_id=None,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker=ticker,
        field_name="current_stop",
        expected_value_json='{"current_stop": 7.62}',
        actual_value_json='{"stop_price": 7.49}',
        delta_text="-$0.13",
        material_to_review=0,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )


# ---------------------------------------------------------------------------
# Tier-1: single active stop with different price → auto-correct
# ---------------------------------------------------------------------------


def test_stop_mismatch_tier_1_single_active_stop() -> None:
    discrepancy = _make_stop_mismatch_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"stop_price": 7.49},
        journal_row={"current_stop": 7.62, "ticker": "DHC"},
        validator_chain=None,
    )
    assert result.tier == 1
    assert result.ambiguity_kind is None
    assert result.correction_target == {"current_stop": 7.49}
    assert "stop_mismatch" in result.correction_reason
    assert "DHC" in result.correction_reason
    assert "7.62" in result.correction_reason
    assert "7.49" in result.correction_reason
    assert result.candidate_choices is None


def test_stop_mismatch_tier_1_single_active_stop_list_wrapped() -> None:
    """source_payload may arrive as ``[{...single dict...}]`` (list of 1)."""
    discrepancy = _make_stop_mismatch_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[{"stop_price": 7.49}],
        journal_row={"current_stop": 7.62},
        validator_chain=None,
    )
    assert result.tier == 1
    assert result.correction_target == {"current_stop": 7.49}


# ---------------------------------------------------------------------------
# Tier-2: source has multiple active stops
# ---------------------------------------------------------------------------


def test_stop_mismatch_tier_2_when_multiple_active_stops() -> None:
    discrepancy = _make_stop_mismatch_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[
            {"stop_price": 7.49},
            {"stop_price": 7.30},
        ],
        journal_row={"current_stop": 7.62},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_match_within_window"
    # 2 + 2 = 4 choices.
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 4


# ---------------------------------------------------------------------------
# Tier-2: source_payload is None OR has 0 stops
# ---------------------------------------------------------------------------


def test_stop_mismatch_tier_2_when_source_payload_is_none() -> None:
    discrepancy = _make_stop_mismatch_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row={"current_stop": 7.62},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "schwab_returned_no_match"


def test_stop_mismatch_tier_2_when_source_payload_empty_list() -> None:
    discrepancy = _make_stop_mismatch_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[],
        journal_row={"current_stop": 7.62},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "schwab_returned_no_match"


# ---------------------------------------------------------------------------
# Tier-1 unaffected by missing 'stop_price' key → tier-2 unsupported
# ---------------------------------------------------------------------------


def test_stop_mismatch_tier_2_when_source_payload_missing_stop_price() -> None:
    discrepancy = _make_stop_mismatch_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": 7.49},  # wrong key name
        journal_row={"current_stop": 7.62},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert "stop_price" in result.correction_reason.lower()


# ---------------------------------------------------------------------------
# ADVISORY-NOT-VALIDATOR BINDING (plan §C.6 acceptance #2 + spec §1.6)
#
# Tier-1 emissions DO NOT consult risk_policy thresholds. Even if the
# proposed stop would TRIP an advisory (e.g., scratch_epsilon_R), the
# classifier STILL emits tier-1. Advisory surface is the Phase 10
# dashboard, not the classifier.
# ---------------------------------------------------------------------------


def test_stop_mismatch_tier_1_even_when_risk_policy_advisory_would_trip() -> None:
    """Plant a trade with risk_policy_id_at_lock + a proposed stop that
    trips a scratch_epsilon_R advisory. Classifier STILL emits tier-1.

    The journal_row carries risk_policy_id_at_lock as METADATA; the
    classifier deliberately ignores it. Advisory firing is a downstream
    concern (Phase 10 dashboard).
    """
    discrepancy = _make_stop_mismatch_discrepancy()
    journal_with_policy_stamp = {
        "current_stop": 7.62,
        "ticker": "DHC",
        # Phase 9 Sub-bundle A risk_policy field — classifier MUST ignore.
        "risk_policy_id_at_lock": 5,
        # Hypothetical advisory-tripping field; classifier MUST NOT branch
        # on it.
        "scratch_epsilon_R": 0.05,
    }
    # Proposed stop $7.49 is below the journal stop $7.62; in a typical
    # risk policy this might trip an "outside scratch epsilon" advisory.
    # The classifier ignores all of that.
    result = classify_discrepancy(
        discrepancy,
        source_payload={"stop_price": 7.49},
        journal_row=journal_with_policy_stamp,
        validator_chain=None,
    )
    assert result.tier == 1, (
        "advisory-not-validator family violated: classifier consulted "
        "risk_policy metadata and downgraded to tier-2; spec §1.6 + §4.3.4 "
        "require classifier to ignore advisory thresholds at classification "
        "time"
    )
    assert result.correction_target == {"current_stop": 7.49}


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_stop_mismatch_deterministic() -> None:
    discrepancy = _make_stop_mismatch_discrepancy()
    fixture = dict(
        discrepancy=discrepancy,
        source_payload={"stop_price": 7.49},
        journal_row={"current_stop": 7.62},
        validator_chain=None,
    )
    first = classify_discrepancy(**fixture)
    for _ in range(99):
        nth = classify_discrepancy(**fixture)
        assert nth == first
