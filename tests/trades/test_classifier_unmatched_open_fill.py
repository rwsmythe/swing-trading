"""T-B.4 — ``unmatched_open_fill`` sub-classifier (DHC 39 + VSAT 40).

Spec §4.3.2 + §8.4 Pass-2-tier-1-FORBIDDEN LOCK + §10.2 DHC 39 + §10.3
VSAT 40 BINDING walkthroughs.

V1 LOCK: sub-classifier NEVER returns tier-1 regardless of Pass-2 input
shape. Discriminating parametrize spans 6 plausible Pass-2 shapes + asserts
``result.tier == 2`` for ALL.
"""
from __future__ import annotations

import pytest

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import (
    ClassificationResult,
    classify_discrepancy,
)


def _make_dhc_39_discrepancy() -> ReconciliationDiscrepancy:
    """DHC 39 fixture: ``unmatched_open_fill`` per spec §10.2."""
    return ReconciliationDiscrepancy(
        discrepancy_id=39,
        run_id=1,
        discrepancy_type="unmatched_open_fill",
        trade_id=1,
        fill_id=2,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="DHC",
        field_name="fill",
        expected_value_json='{"qty": 39.0, "price": 7.58, "action": "entry"}',
        actual_value_json='{"matched": null}',
        delta_text=None,
        material_to_review=1,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )


def _make_vsat_40_discrepancy() -> ReconciliationDiscrepancy:
    """VSAT 40 fixture: ``unmatched_open_fill`` per spec §10.3."""
    return ReconciliationDiscrepancy(
        discrepancy_id=40,
        run_id=1,
        discrepancy_type="unmatched_open_fill",
        trade_id=2,
        fill_id=6,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="VSAT",
        field_name="fill",
        expected_value_json='{"qty": 2.0, "price": 65.69, "action": "entry"}',
        actual_value_json='{"matched": null}',
        delta_text=None,
        material_to_review=1,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-15T00:00:00",
        ambiguity_kind=None,
    )


# ---------------------------------------------------------------------------
# PASS-2-TIER-1-FORBIDDEN LOCK (spec §8.4 + brief §0.5 #4)
#
# DISCRIMINATING TEST: every plausible Pass-2 input shape → tier-2.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source_payload, expected_kind",
    [
        # Pass-1 only: no source data at all.
        (None, "unsupported"),
        # Pass-1 only: shipped emitter shape {"matched": null}.
        ({"matched": None}, "unsupported"),
        # Pass-2 returned 0 orders → schwab_returned_no_match.
        ([], "schwab_returned_no_match"),
        # Pass-2 returned 1 order → unknown_schwab_subtype (V1 mapper limit).
        ([{"quantity": 39, "price": 7.58}], "unknown_schwab_subtype"),
        # Pass-2 returned 2 orders summing to journal qty=39 →
        # multi_partial_vs_consolidated.
        (
            [
                {"quantity": 20, "price": 7.57},
                {"quantity": 19, "price": 7.59},
            ],
            "multi_partial_vs_consolidated",
        ),
        # Pass-2 returned 2 orders NOT summing to journal qty=39 →
        # multi_match_within_window.
        (
            [
                {"quantity": 1, "price": 7.50},
                {"quantity": 3, "price": 7.60},
            ],
            "multi_match_within_window",
        ),
    ],
)
def test_unmatched_open_fill_never_emits_tier_1_dhc_39(
    source_payload: object,
    expected_kind: str,
) -> None:
    """BINDING DISCRIMINATING TEST (brief §0.5 #4).

    For EVERY plausible Pass-2 input shape, ``unmatched_open_fill``
    classifier MUST emit ``tier == 2``. The ``ambiguity_kind`` varies per
    shape but ``tier`` is INVARIANT at 2.
    """
    discrepancy = _make_dhc_39_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=source_payload,
        journal_row={"quantity": 39, "ticker": "DHC", "price": 7.58},
        validator_chain=None,
    )
    assert isinstance(result, ClassificationResult)
    assert result.tier == 2, (
        f"Pass-2-tier-1-FORBIDDEN LOCK violated: source_payload="
        f"{source_payload!r} should yield tier-2, got tier={result.tier}"
    )
    assert result.ambiguity_kind == expected_kind, (
        f"expected ambiguity_kind={expected_kind!r}, "
        f"got {result.ambiguity_kind!r}"
    )


# ---------------------------------------------------------------------------
# DHC 39 walkthrough — Pass 1 input emits _pass_2_required signal
# ---------------------------------------------------------------------------


def test_dhc_39_pass_1_emits_pass_2_required_signal() -> None:
    """Pass 1 input (shipped emitter ``{"matched": null}``) → tier-2 unsupported
    with ``_pass_2_required=True`` signal in correction_reason.

    Spec §10.2: backfill path reads this signal to fire Pass 2.
    """
    discrepancy = _make_dhc_39_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"matched": None},
        journal_row={"quantity": 39, "ticker": "DHC", "price": 7.58},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    # Pass-2-required signal must be in the correction_reason text per
    # plan §C.4 acceptance #2 ("metadata flag _pass_2_required=True in
    # correction_reason").
    assert "_pass_2_required=True" in result.correction_reason
    assert result.candidate_choices is None


def test_dhc_39_pass_1_with_source_payload_none_same_signal() -> None:
    """source_payload=None equivalent to {"matched": null} per shipped shape."""
    discrepancy = _make_dhc_39_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row={"quantity": 39},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert "_pass_2_required=True" in result.correction_reason


# ---------------------------------------------------------------------------
# DHC 39 Pass-2: 2 orders summing to 39 → multi_partial_vs_consolidated
# (candidate_choices length = 4; keep_journal_as_is is FIRST)
# ---------------------------------------------------------------------------


def test_dhc_39_pass_2_multi_partial_vs_consolidated() -> None:
    """Spec §10.2 + §6.2.1 LOCKED menu: 4 choices; keep_journal_as_is FIRST.

    Brief §0.5 #4: candidate_choices length matches spec §6.2.1 menu;
    ``keep_journal_as_is`` MUST be ``candidate_choices[0]``.
    """
    discrepancy = _make_dhc_39_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[
            {"quantity": 20, "price": 7.57},
            {"quantity": 19, "price": 7.59},
        ],
        journal_row={"quantity": 39, "ticker": "DHC", "price": 7.58},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_partial_vs_consolidated"
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 4, (
        f"multi_partial_vs_consolidated MUST emit 4 choices per spec "
        f"§6.2.1; got {len(result.candidate_choices)}"
    )
    # keep_journal_as_is is HIGHLIGHTED FIRST per §0.4 OQ-4 + brief §0.5 #7.
    assert result.candidate_choices[0]["code"] == "keep_journal_as_is"
    expected_codes = {
        "keep_journal_as_is",
        "consolidate_using_operator_vwap",
        "split_into_partials",
        "custom",
    }
    actual_codes = {c["code"] for c in result.candidate_choices}
    assert actual_codes == expected_codes
    # All choice dicts include the spec §6.2.1 LOCKED 3-key shape.
    for c in result.candidate_choices:
        assert "code" in c
        assert "description" in c
        assert "requires_custom_value" in c
        assert isinstance(c["requires_custom_value"], bool)
    # keep_journal_as_is is the no-mutation choice — does NOT require custom.
    keep = result.candidate_choices[0]
    assert keep["requires_custom_value"] is False


# ---------------------------------------------------------------------------
# VSAT 40 Pass-2 branches (spec §10.3 Case A/B/C)
# ---------------------------------------------------------------------------


def test_vsat_40_pass_2_case_a_single_order_returns_unknown_schwab_subtype() -> None:
    """Spec §10.3 Case A — Schwab returns 1 single order. Tier-2 always."""
    discrepancy = _make_vsat_40_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[{"quantity": 2, "price": 65.69}],
        journal_row={"quantity": 2, "ticker": "VSAT", "price": 65.69},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unknown_schwab_subtype"
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 3
    codes = {c["code"] for c in result.candidate_choices}
    assert codes == {"acknowledge", "operator_truth", "custom"}


def test_vsat_40_pass_2_case_b_two_orders_summing_to_journal_qty() -> None:
    """Spec §10.3 Case B — multi_partial_vs_consolidated (4 choices)."""
    discrepancy = _make_vsat_40_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[
            {"quantity": 1, "price": 65.68},
            {"quantity": 1, "price": 65.70},
        ],
        journal_row={"quantity": 2, "ticker": "VSAT", "price": 65.69},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_partial_vs_consolidated"
    assert len(result.candidate_choices or []) == 4


def test_vsat_40_pass_2_case_c_zero_orders_returns_schwab_no_match() -> None:
    """Spec §10.3 Case C — schwab_returned_no_match (2 choices)."""
    discrepancy = _make_vsat_40_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[],
        journal_row={"quantity": 2, "ticker": "VSAT", "price": 65.69},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "schwab_returned_no_match"
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 2
    codes = {c["code"] for c in result.candidate_choices}
    assert codes == {"mark_unmatched", "operator_truth"}


# ---------------------------------------------------------------------------
# multi_match_within_window candidate_choices = N+2
# ---------------------------------------------------------------------------


def test_vsat_multi_match_within_window_candidate_count_n_plus_2() -> None:
    """N=2 orders not summing → 2+2=4 choices (pick_1, pick_2, mark, custom)."""
    discrepancy = _make_vsat_40_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[
            {"quantity": 1, "price": 65.68},
            {"quantity": 3, "price": 65.70},
        ],
        journal_row={"quantity": 2, "ticker": "VSAT"},  # 1+3 != 2
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_match_within_window"
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 4  # 2 + 2
    codes = [c["code"] for c in result.candidate_choices]
    assert codes[0] == "pick_schwab_record_1"
    assert codes[1] == "pick_schwab_record_2"
    assert "mark_unmatched" in codes
    assert "custom" in codes


def test_unmatched_open_fill_with_n3_match_window_emits_n_plus_2_choices() -> None:
    """N=3 orders, qty sum != journal → 3+2=5 choices."""
    discrepancy = _make_dhc_39_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[
            {"quantity": 10},
            {"quantity": 10},
            {"quantity": 10},  # sum=30 != 39
        ],
        journal_row={"quantity": 39},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_match_within_window"
    assert len(result.candidate_choices or []) == 5


# ---------------------------------------------------------------------------
# Determinism over the sub-classifier
# ---------------------------------------------------------------------------


def test_unmatched_open_fill_deterministic() -> None:
    discrepancy = _make_dhc_39_discrepancy()
    fixture = dict(
        discrepancy=discrepancy,
        source_payload=[
            {"quantity": 20, "price": 7.57},
            {"quantity": 19, "price": 7.59},
        ],
        journal_row={"quantity": 39},
        validator_chain=None,
    )
    first = classify_discrepancy(**fixture)
    for _ in range(99):
        nth = classify_discrepancy(**fixture)
        assert nth == first
