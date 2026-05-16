"""T-B.3 — ``entry_price_mismatch`` sub-classifier (CVGI 41 walkthrough).

Spec §4.3.1 + §10.1 BINDING. Tier-1 auto-correct path is the V1 default
emitter shape; tier-2 branches are defensive (None payload, multi-match
shape, unsupported scalar shape).
"""
from __future__ import annotations

import pytest

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import (
    ClassificationResult,
    classify_discrepancy,
)


def _make_cvgi_41_discrepancy() -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=41,
        run_id=1,
        discrepancy_type="entry_price_mismatch",
        trade_id=1,
        fill_id=9,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="CVGI",
        field_name="price",
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


# ---------------------------------------------------------------------------
# Tier-1 happy path (spec §10.1 BINDING walkthrough)
# ---------------------------------------------------------------------------


def test_cvgi_41_tier_1_emit() -> None:
    """CVGI 41 — journal $5.23 × 100 vs Schwab $5.30 → tier-1 auto-correct."""
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": 5.30},
        journal_row={
            "price": 5.23,
            "quantity": 100,
            "ticker": "CVGI",
            "fill_datetime": "2026-04-27T10:00:00",
        },
        validator_chain=None,
    )
    assert isinstance(result, ClassificationResult)
    assert result.tier == 1
    assert result.ambiguity_kind is None
    assert result.correction_target == {"price": 5.30}
    assert "entry_price_mismatch" in result.correction_reason
    assert "CVGI" in result.correction_reason
    assert "5.23" in result.correction_reason
    assert "5.30" in result.correction_reason
    assert "fill_id=9" in result.correction_reason
    assert result.candidate_choices is None


def test_cvgi_tier_1_with_passing_validator_chain_preserved() -> None:
    """Validator chain returns (True, None) → tier-1 result preserved."""
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": 5.30},
        journal_row={"price": 5.23, "quantity": 100},
        validator_chain=lambda target: (True, None),
    )
    assert result.tier == 1
    assert result.correction_target == {"price": 5.30}


def test_cvgi_tier_1_downgraded_by_rejecting_validator_chain() -> None:
    """Validator chain returns (False, reason) → dispatcher downgrades to
    tier-2 ``validator_rejected``.

    Discriminating test for plan §C.3 acceptance #4: exercises the
    DISPATCHER's validator-respecting downgrade (T-B.1 step 2), not the
    sub-classifier itself.
    """
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": 5.30},
        journal_row={"price": 5.23, "quantity": 100},
        validator_chain=lambda target: (
            False,
            "price would violate aggregate invariant",
        ),
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "validator_rejected"
    assert result.correction_target is None
    assert "price would violate aggregate invariant" in result.correction_reason


# ---------------------------------------------------------------------------
# Tier-2 defensive branches
# ---------------------------------------------------------------------------


def test_entry_price_mismatch_tier_2_when_source_payload_is_none() -> None:
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=None,
        journal_row={"price": 5.23},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "schwab_returned_no_match"
    # candidate_choices spec §6.2.1: 2 choices.
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 2
    codes = {c["code"] for c in result.candidate_choices}
    assert codes == {"mark_unmatched", "operator_truth"}
    # All choices carry the requires_custom_value field per spec §6.2.1.
    for c in result.candidate_choices:
        assert "code" in c
        assert "description" in c
        assert "requires_custom_value" in c
        assert isinstance(c["requires_custom_value"], bool)


def test_entry_price_mismatch_tier_2_when_source_payload_list_multi() -> None:
    """List of 3 candidate Schwab records → tier-2 multi_match_within_window."""
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload=[
            {"price": 5.30, "quantity": 50},
            {"price": 5.32, "quantity": 50},
            {"price": 5.28, "quantity": 100},
        ],
        journal_row={"price": 5.23, "quantity": 100},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_match_within_window"
    # candidate_choices: N+2 (N pick_schwab_record_<i> + mark_unmatched + custom)
    assert result.candidate_choices is not None
    assert len(result.candidate_choices) == 5  # 3 + 2
    codes = [c["code"] for c in result.candidate_choices]
    assert codes[0] == "pick_schwab_record_1"
    assert codes[1] == "pick_schwab_record_2"
    assert codes[2] == "pick_schwab_record_3"
    assert "mark_unmatched" in codes
    assert "custom" in codes


def test_entry_price_mismatch_tier_2_when_source_payload_missing_price_key() -> None:
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"quantity": 100},  # missing 'price'
        journal_row={"price": 5.23},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert "price" in result.correction_reason.lower()


def test_entry_price_mismatch_tier_2_when_source_payload_scalar() -> None:
    """Unexpected scalar payload → tier-2 unsupported (graceful)."""
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload="5.30",  # scalar string; not Mapping; not list
        journal_row={"price": 5.23},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"


# ---------------------------------------------------------------------------
# Codex R1 Critical #1 — (ticker, date, quantity) consistency check +
# NaN/inf/non-numeric guard on source_price.
#
# Spec §4.3.1 LOGIC requires journal (ticker, date, quantity) to match
# source exactly and only `price` to differ before tier-1 emission. The
# pre-Codex-R1 implementation only checked `source_payload['price']` and
# would emit tier-1 even if source ticker/date/quantity contradicted the
# journal or if `journal_row` was missing entirely. These tests pin the
# tightened contract.
# ---------------------------------------------------------------------------


def test_tier_2_unsupported_when_source_ticker_disagrees_with_journal() -> None:
    """Source ticker AAPL vs journal CVGI → tier-2 unsupported (R1 C#1)."""
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"ticker": "AAPL", "price": 5.30},
        journal_row={
            "price": 5.23,
            "quantity": 100,
            "ticker": "CVGI",
            "fill_datetime": "2026-04-27T10:00:00",
        },
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert result.correction_target is None
    assert "ticker" in result.correction_reason.lower()


def test_tier_2_unsupported_when_source_quantity_disagrees() -> None:
    """Source qty=200 vs journal qty=100 → tier-2 unsupported (R1 C#1)."""
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"quantity": 200, "price": 5.30},
        journal_row={
            "price": 5.23,
            "quantity": 100,
            "ticker": "CVGI",
            "fill_datetime": "2026-04-27T10:00:00",
        },
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert "quantity" in result.correction_reason.lower()


def test_tier_2_unsupported_when_source_date_disagrees_against_journal_fill_datetime() -> None:
    """Source date 2026-04-28 vs journal fill_datetime 2026-04-27T... → tier-2."""
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"date": "2026-04-28", "price": 5.30},
        journal_row={
            "price": 5.23,
            "quantity": 100,
            "ticker": "CVGI",
            "fill_datetime": "2026-04-27T14:00:00",
        },
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert "date" in result.correction_reason.lower()


def test_tier_2_unsupported_when_journal_row_is_None() -> None:
    """journal_row=None with non-None source_payload → cannot verify tuple."""
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": 5.30},
        journal_row=None,
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert "journal_row missing" in result.correction_reason


@pytest.mark.parametrize(
    "bad_price",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        "not-a-number",
    ],
)
def test_tier_2_unsupported_when_source_price_is_nan_or_inf(bad_price: object) -> None:
    """NaN/inf/non-numeric source_price → tier-2 unsupported (R1 C#1)."""
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": bad_price},
        journal_row={"price": 5.23, "quantity": 100, "ticker": "CVGI"},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert result.correction_target is None


def test_tier_1_passes_when_source_carries_persisted_json_only_shape() -> None:
    """Discriminating positive case: persisted-JSON-only shape {"price": X}.

    This is the shipped emitter contract per
    swing/trades/schwab_reconciliation.py:469-474 — emitter verifies the
    match pre-emit and persists only {'price': X}. With no contradicting
    keys present in source_payload, tier-1 emits as designed.
    """
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": 5.30},
        journal_row={
            "price": 5.23,
            "quantity": 100,
            "ticker": "CVGI",
            "fill_datetime": "2026-04-27T10:00:00",
        },
        validator_chain=None,
    )
    assert result.tier == 1
    assert result.correction_target == {"price": 5.30}


def test_tier_1_passes_when_source_keys_match_journal_explicitly() -> None:
    """Discriminating positive case: source carries (ticker, qty, price)
    AND they match journal_row → tier-1 emits as designed."""
    discrepancy = _make_cvgi_41_discrepancy()
    result = classify_discrepancy(
        discrepancy,
        source_payload={"ticker": "CVGI", "quantity": 100, "price": 5.30},
        journal_row={
            "price": 5.23,
            "quantity": 100,
            "ticker": "CVGI",
            "fill_datetime": "2026-04-27T10:00:00",
        },
        validator_chain=None,
    )
    assert result.tier == 1
    assert result.correction_target == {"price": 5.30}


# ---------------------------------------------------------------------------
# Determinism over the sub-classifier
# ---------------------------------------------------------------------------


def test_entry_price_mismatch_deterministic() -> None:
    discrepancy = _make_cvgi_41_discrepancy()
    fixture = dict(
        discrepancy=discrepancy,
        source_payload={"price": 5.30},
        journal_row={"price": 5.23, "quantity": 100},
        validator_chain=None,
    )
    first = classify_discrepancy(**fixture)
    for _ in range(99):
        nth = classify_discrepancy(**fixture)
        assert nth == first
