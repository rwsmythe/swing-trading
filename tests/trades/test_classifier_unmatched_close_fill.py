"""T-B.5 — ``unmatched_close_fill`` sub-classifier.

Spec §4.3.3 — mirrors T-B.4 symmetrically. Same V1 LOCK
(Pass-2-tier-1-FORBIDDEN); same ambiguity_kind enum; same candidate
choices per spec §6.2.1. Sub-classifier shares a core helper with
``unmatched_open_fill`` (the ``action`` field — ``exit`` vs ``trim`` —
is metadata for downstream service; classifier is action-agnostic for
unmatched close).
"""
from __future__ import annotations

import pytest

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import classify_discrepancy


def _make_close_fill_discrepancy(
    *,
    action_label: str,
    discrepancy_id: int = 50,
) -> ReconciliationDiscrepancy:
    """Build an unmatched_close_fill discrepancy with the journal fill's
    action labeled via ``expected_value_json``."""
    return ReconciliationDiscrepancy(
        discrepancy_id=discrepancy_id,
        run_id=1,
        discrepancy_type="unmatched_close_fill",
        trade_id=3,
        fill_id=12,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="TEST",
        field_name="fill",
        expected_value_json=(
            '{"qty": 50.0, "price": 12.34, "action": '
            f'"{action_label}"' "}"
        ),
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
# PASS-2-TIER-1-FORBIDDEN LOCK (mirrors T-B.4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source_payload, expected_kind",
    [
        (None, "unsupported"),
        ({"matched": None}, "unsupported"),
        ([], "schwab_returned_no_match"),
        ([{"quantity": 50, "price": 12.34}], "unknown_schwab_subtype"),
        (
            [
                {"quantity": 25, "price": 12.33},
                {"quantity": 25, "price": 12.35},
            ],
            "multi_partial_vs_consolidated",
        ),
        (
            [
                {"quantity": 10, "price": 12.30},
                {"quantity": 15, "price": 12.40},
            ],
            "multi_match_within_window",
        ),
    ],
)
def test_unmatched_close_fill_never_emits_tier_1(
    source_payload: object,
    expected_kind: str,
) -> None:
    """Mirrors T-B.4 — close-side sub-classifier NEVER emits tier-1."""
    discrepancy = _make_close_fill_discrepancy(action_label="exit")
    result = classify_discrepancy(
        discrepancy,
        source_payload=source_payload,
        journal_row={"quantity": 50, "ticker": "TEST", "price": 12.34},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == expected_kind


# ---------------------------------------------------------------------------
# Action-agnostic emission: exit vs trim → identical classifier output
# (plan §C.5 acceptance: "the action field is metadata for downstream
# service; classifier is action-agnostic for unmatched close").
# ---------------------------------------------------------------------------


def test_unmatched_close_fill_action_exit_vs_trim_symmetric() -> None:
    """``action='exit'`` and ``action='trim'`` produce identical classifier
    output (same tier + ambiguity_kind + candidate_choices structure).

    The action label rides through ``expected_value_json`` metadata; the
    classifier does NOT inspect it for path selection.
    """
    payload = [
        {"quantity": 25, "price": 12.33},
        {"quantity": 25, "price": 12.35},
    ]
    journal = {"quantity": 50, "ticker": "TEST", "price": 12.34}

    exit_disc = _make_close_fill_discrepancy(
        action_label="exit", discrepancy_id=50,
    )
    trim_disc = _make_close_fill_discrepancy(
        action_label="trim", discrepancy_id=51,
    )

    exit_result = classify_discrepancy(
        exit_disc, source_payload=payload, journal_row=journal,
    )
    trim_result = classify_discrepancy(
        trim_disc, source_payload=payload, journal_row=journal,
    )

    # Same tier + ambiguity_kind + candidate_choices.
    assert exit_result.tier == trim_result.tier == 2
    assert exit_result.ambiguity_kind == trim_result.ambiguity_kind
    assert exit_result.candidate_choices == trim_result.candidate_choices


# ---------------------------------------------------------------------------
# Pass-1-only signal (parallel with T-B.4)
# ---------------------------------------------------------------------------


def test_unmatched_close_fill_pass_1_emits_pass_2_required_signal() -> None:
    discrepancy = _make_close_fill_discrepancy(action_label="exit")
    result = classify_discrepancy(
        discrepancy,
        source_payload={"matched": None},
        journal_row={"quantity": 50},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert "_pass_2_required=True" in result.correction_reason


# ---------------------------------------------------------------------------
# multi_partial_vs_consolidated candidate menu (4; keep_journal_as_is FIRST)
# ---------------------------------------------------------------------------


def test_unmatched_close_fill_multi_partial_choices_first_is_keep() -> None:
    discrepancy = _make_close_fill_discrepancy(action_label="exit")
    result = classify_discrepancy(
        discrepancy,
        source_payload=[
            {"quantity": 25, "price": 12.33},
            {"quantity": 25, "price": 12.35},
        ],
        journal_row={"quantity": 50},
        validator_chain=None,
    )
    assert result.ambiguity_kind == "multi_partial_vs_consolidated"
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 4
    assert result.candidate_choices[0]["code"] == "keep_journal_as_is"


# ---------------------------------------------------------------------------
# Reason text is direction-specific
# ---------------------------------------------------------------------------


def test_unmatched_close_fill_reason_text_says_close() -> None:
    """Discriminating: ensure the reason names this as a CLOSE-side path."""
    discrepancy = _make_close_fill_discrepancy(action_label="exit")
    result = classify_discrepancy(
        discrepancy,
        source_payload=[],
        journal_row={"quantity": 50},
        validator_chain=None,
    )
    assert "unmatched_close_fill" in result.correction_reason
    assert "unmatched_open_fill" not in result.correction_reason
