"""Phase 12.5 #1 T-1.2 — ``ClassificationResult.auto_redirect_recipe`` field +
integration in ``_classify_unmatched_fill_shared``.

Spec §4.3 + §6.1 + §6.5 (n=1 reclassification path) + §10 case fixtures.

New field on ``ClassificationResult`` defaults to ``None``; populated by
``_classify_unmatched_fill_shared`` when the multi-leg auto-redirect
predicate fires AND the input shape is a multi-leg payload.

Two emit paths exercised:
  - n>=2 branch (currently emits ``multi_partial_vs_consolidated``).
  - n=1 branch with multi-leg ``executions`` (per spec §6.5 → RECLASSIFIED
    from ``unknown_schwab_subtype`` to ``multi_partial_vs_consolidated``).
"""
from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import (
    ClassificationResult,
    _classify_unmatched_fill_shared,
)


# ---------------------------------------------------------------------------
# Fixture helpers (mirrors test_reconciliation_classifier_multi_leg_predicate.py)
# ---------------------------------------------------------------------------


def _leg(
    *,
    leg_id: int = 1,
    price: Any = 5.30,
    quantity: Any = 100.0,
    time: str = "2026-05-15T14:30:00+00:00",
) -> dict[str, Any]:
    return {
        "leg_id": leg_id,
        "price": price,
        "quantity": quantity,
        "time": time,
    }


def _candidate(
    *,
    order_id: str = "ORDER-1",
    quantity: float = 100.0,
    price: float = 5.30,
    executions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "order_id": order_id,
        "quantity": quantity,
        "price": price,
    }
    if executions is not None:
        out["executions"] = executions
    return out


def _disc(
    *,
    discrepancy_type: str = "unmatched_open_fill",
    fill_id: int | None = 2,
    ticker: str = "DHC",
) -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=99,
        run_id=1,
        discrepancy_type=discrepancy_type,
        trade_id=1,
        fill_id=fill_id,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker=ticker,
        field_name="fill",
        expected_value_json='{"qty": 0, "price": 0, "action": "entry"}',
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
# Test 1 + 2 — ClassificationResult dataclass extension
# ---------------------------------------------------------------------------


def test_classification_result_auto_redirect_recipe_defaults_to_none() -> None:
    """New field defaults to None when constructed without it."""
    result = ClassificationResult(
        tier=2,
        ambiguity_kind="unsupported",
        correction_target=None,
        correction_reason="x",
    )
    assert result.auto_redirect_recipe is None


def test_classification_result_auto_redirect_recipe_field_is_last_positional_arg() -> None:
    """Field-order pin: ``auto_redirect_recipe`` MUST be the LAST field so
    existing positional construction at all call sites stays valid.

    Pre-existing field order: tier, ambiguity_kind, correction_target,
    correction_reason, candidate_choices (default None).
    """
    field_names = [f.name for f in dataclasses.fields(ClassificationResult)]
    assert field_names[-1] == "auto_redirect_recipe", (
        f"auto_redirect_recipe MUST be the LAST field; got {field_names}"
    )


# ---------------------------------------------------------------------------
# Test 3 — n>=2 branch, predicate fires → recipe emitted
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_n_ge_2_predicate_fires_emits_recipe() -> None:
    """Case B: 2 candidates × 1 leg each summing to journal qty=150 at VWAP
    matching journal price → multi-leg auto-redirect predicate fires →
    recipe synthesized + emitted on the multi_partial_vs_consolidated path.
    """
    discrepancy = _disc()
    source_payload = [
        _candidate(
            order_id="ORDER-B1",
            quantity=75.0,
            price=7.50,
            executions=[_leg(leg_id=1, price=7.50, quantity=75.0)],
        ),
        _candidate(
            order_id="ORDER-B2",
            quantity=75.0,
            price=7.51,
            executions=[_leg(leg_id=2, price=7.51, quantity=75.0)],
        ),
    ]
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_payload,
        journal_row={"quantity": 150, "price": 7.505, "ticker": "DHC"},
        direction="open",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_partial_vs_consolidated"
    assert result.auto_redirect_recipe is not None
    assert result.auto_redirect_recipe["choice_code"] == "split_into_partials"
    assert result.auto_redirect_recipe["resolved_by"] == "auto_tier1_multi_leg"
    assert result.auto_redirect_recipe["applied_by_override"] == "auto"
    assert result.auto_redirect_recipe["correction_action_override"] == "auto_applied"
    payload = result.auto_redirect_recipe["payload"]
    assert len(payload) == 2
    assert payload[0]["qty"] == 75.0
    assert payload[0]["price"] == 7.50
    assert payload[1]["qty"] == 75.0
    assert payload[1]["price"] == 7.51


# ---------------------------------------------------------------------------
# Test 4 — n>=2 branch, per-leg outlier → recipe None + reason cites outlier
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_n_ge_2_per_leg_outlier_recipe_none_reason_cites_outlier() -> None:
    """Case C: predicate declines on per-leg outlier (sub-condition 6).

    Recipe MUST be None; correction_reason MUST cite the failing leg
    (substring 'leg #3' since the outlier is leg #3).
    """
    discrepancy = _disc()
    source_payload = [
        _candidate(
            order_id="ORDER-C1",
            quantity=200.0,
            price=5.30,
            executions=[
                _leg(leg_id=1, price=5.30, quantity=100.0),
                _leg(leg_id=2, price=5.30, quantity=50.0),
                _leg(leg_id=3, price=5.50, quantity=50.0),  # outlier
            ],
        ),
    ]
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_payload,
        # sum=200, VWAP = (5.30*100 + 5.30*50 + 5.50*50)/200 = 5.35; journal
        # picked so VWAP-vs-journal passes (≤$0.01) yet per-leg outlier fires.
        journal_row={"quantity": 200, "price": 5.35, "ticker": "DHC"},
        direction="open",
    )
    # n=1 candidate with 3 legs is treated by n=1 branch (len(source_payload)==1).
    # But here we have n=1 candidate, so the n=1 branch is exercised.
    # For test 4, we want n>=2 branch with outlier; use 2 candidates with mixed legs.
    # Adjust: 2 candidates, second has the outlier.
    source_payload_2 = [
        _candidate(
            order_id="ORDER-C1",
            quantity=150.0,
            price=5.30,
            executions=[
                _leg(leg_id=1, price=5.30, quantity=100.0),
                _leg(leg_id=2, price=5.30, quantity=50.0),
            ],
        ),
        _candidate(
            order_id="ORDER-C2",
            quantity=50.0,
            price=5.50,
            executions=[_leg(leg_id=3, price=5.50, quantity=50.0)],  # outlier leg
        ),
    ]
    result2 = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_payload_2,
        # total qty=200, VWAP=(5.30*150 + 5.50*50)/200 = 5.35
        journal_row={"quantity": 200, "price": 5.35, "ticker": "DHC"},
        direction="open",
    )
    assert result2.tier == 2
    assert result2.ambiguity_kind == "multi_partial_vs_consolidated"
    assert result2.auto_redirect_recipe is None
    assert "leg #3" in result2.correction_reason


# ---------------------------------------------------------------------------
# Test 5 — n=1 branch with multi-leg executions → RECLASSIFY (spec §6.5)
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_n_eq_1_with_multi_leg_reclassifies_ambiguity_kind() -> None:
    """Spec §6.5 LOCK: n=1 with multi-leg executions where predicate fires →
    ambiguity_kind RECLASSIFIED from 'unknown_schwab_subtype' to
    'multi_partial_vs_consolidated' so the schema cross-column CHECK pair
    (operator_resolved_ambiguity ↔ multi_partial_vs_consolidated) holds AND
    the existing _TIER2_HANDLERS registry entry routes the auto-redirect.
    """
    discrepancy = _disc()
    source_payload = [
        _candidate(
            order_id="ORDER-A1",
            quantity=200.0,
            price=5.3025,
            executions=[
                _leg(leg_id=1, price=5.30, quantity=100.0),
                _leg(leg_id=2, price=5.31, quantity=50.0),
                _leg(leg_id=3, price=5.30, quantity=50.0),
            ],
        ),
    ]
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_payload,
        journal_row={"quantity": 200, "price": 5.3025, "ticker": "DHC"},
        direction="open",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_partial_vs_consolidated", (
        "n=1 with multi-leg + predicate-fires MUST reclassify to "
        "multi_partial_vs_consolidated per spec §6.5"
    )
    assert result.auto_redirect_recipe is not None
    assert result.auto_redirect_recipe["choice_code"] == "split_into_partials"


# ---------------------------------------------------------------------------
# Test 6 — n=1 single-leg / executions=None preserves unknown_schwab_subtype
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_n_eq_1_with_single_leg_preserves_unknown_schwab_subtype() -> None:
    """n=1 with executions=None OR a single-leg list → ambiguity_kind stays
    'unknown_schwab_subtype' (predicate sub-condition 2 fails for n<2 legs).
    """
    discrepancy = _disc()
    # Subcase: executions absent.
    source_no_exec = [_candidate(quantity=39.0, price=7.58)]
    result_no_exec = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_no_exec,
        journal_row={"quantity": 39, "price": 7.58, "ticker": "DHC"},
        direction="open",
    )
    assert result_no_exec.tier == 2
    assert result_no_exec.ambiguity_kind == "unknown_schwab_subtype"
    assert result_no_exec.auto_redirect_recipe is None

    # Subcase: executions = single-leg list (len < 2 fails sub-condition 2).
    source_one_leg = [
        _candidate(
            quantity=39.0,
            price=7.58,
            executions=[_leg(leg_id=1, price=7.58, quantity=39.0)],
        )
    ]
    result_one_leg = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_one_leg,
        journal_row={"quantity": 39, "price": 7.58, "ticker": "DHC"},
        direction="open",
    )
    assert result_one_leg.tier == 2
    assert result_one_leg.ambiguity_kind == "unknown_schwab_subtype"
    assert result_one_leg.auto_redirect_recipe is None


# ---------------------------------------------------------------------------
# Test 7 — n=1 with multi-leg but predicate DECLINES → keeps unknown_schwab_subtype
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_n_eq_1_with_multi_leg_predicate_declines_keeps_unknown_schwab_subtype() -> None:
    """n=1 candidate with 3 legs containing a per-leg outlier → predicate
    declines → ambiguity_kind stays 'unknown_schwab_subtype' + recipe None +
    reason cites the outlier leg.
    """
    discrepancy = _disc()
    source_payload = [
        _candidate(
            order_id="ORDER-A1",
            quantity=200.0,
            price=5.35,
            executions=[
                _leg(leg_id=1, price=5.30, quantity=100.0),
                _leg(leg_id=2, price=5.30, quantity=50.0),
                _leg(leg_id=3, price=5.50, quantity=50.0),  # outlier
            ],
        ),
    ]
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_payload,
        # VWAP = (5.30*100 + 5.30*50 + 5.50*50)/200 = 5.35
        journal_row={"quantity": 200, "price": 5.35, "ticker": "DHC"},
        direction="open",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unknown_schwab_subtype"
    assert result.auto_redirect_recipe is None
    assert "leg #3" in result.correction_reason


# ---------------------------------------------------------------------------
# Test 8 — no-payload sentinel
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_no_payload_sentinel_recipe_none() -> None:
    """source_payload=None → 'unsupported' tier-2; recipe is None."""
    discrepancy = _disc()
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=None,
        journal_row={"quantity": 39, "price": 7.58, "ticker": "DHC"},
        direction="open",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert result.auto_redirect_recipe is None


# ---------------------------------------------------------------------------
# Test 9 — matched-null sentinel
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_matched_null_sentinel_recipe_none() -> None:
    """source_payload={'matched': None} → 'unsupported' tier-2; recipe is None."""
    discrepancy = _disc()
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload={"matched": None},
        journal_row={"quantity": 39, "price": 7.58, "ticker": "DHC"},
        direction="open",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert result.auto_redirect_recipe is None


# ---------------------------------------------------------------------------
# Test 10 — n=0 schwab_returned_no_match
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_n_eq_0_schwab_returned_no_match_recipe_none() -> None:
    """source_payload=[] → 'schwab_returned_no_match'; recipe is None."""
    discrepancy = _disc()
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=[],
        journal_row={"quantity": 39, "price": 7.58, "ticker": "DHC"},
        direction="open",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "schwab_returned_no_match"
    assert result.auto_redirect_recipe is None


# ---------------------------------------------------------------------------
# Test 11 — n>=2 qty-mismatch multi_match_within_window
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_n_ge_2_qty_mismatch_multi_match_within_window_recipe_none() -> None:
    """n=2 with sum-qty != journal qty → 'multi_match_within_window' (not
    multi_partial_vs_consolidated); recipe is None.
    """
    discrepancy = _disc()
    source_payload = [
        _candidate(quantity=1.0, price=7.50, executions=[_leg(price=7.50, quantity=1.0)]),
        _candidate(quantity=3.0, price=7.60, executions=[_leg(price=7.60, quantity=3.0)]),
    ]
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_payload,
        journal_row={"quantity": 39, "price": 7.58, "ticker": "DHC"},
        direction="open",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_match_within_window"
    assert result.auto_redirect_recipe is None


# ---------------------------------------------------------------------------
# Test 12 — defensive scalar shape
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_defensive_scalar_shape_recipe_none() -> None:
    """source_payload=42 (non-list, non-Mapping) → 'unsupported'; recipe is None."""
    discrepancy = _disc()
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=42,
        journal_row={"quantity": 39, "price": 7.58, "ticker": "DHC"},
        direction="open",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert result.auto_redirect_recipe is None


# ---------------------------------------------------------------------------
# Test 13 — predicate-eligible payload but journal_row=None
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_n_ge_2_journal_row_none_no_synthesis() -> None:
    """predicate-eligible payload but journal_row=None → no synthesis."""
    discrepancy = _disc()
    source_payload = [
        _candidate(quantity=75.0, price=7.50, executions=[_leg(price=7.50, quantity=75.0)]),
        _candidate(quantity=75.0, price=7.51, executions=[_leg(price=7.51, quantity=75.0)]),
    ]
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_payload,
        journal_row=None,
        direction="open",
    )
    # Path lands on multi_match_within_window (journal_qty=None → sum-vs-journal
    # comparison branch falls through). Recipe MUST be None either way.
    assert result.tier == 2
    assert result.auto_redirect_recipe is None


# ---------------------------------------------------------------------------
# Test 14 — journal_row missing 'price' key
# ---------------------------------------------------------------------------


def test_unmatched_fill_shared_n_ge_2_journal_row_missing_price_no_synthesis() -> None:
    """predicate-eligible payload but journal_row missing 'price' → no synthesis.

    Sub-condition 5 requires journal_price to be a real number; absent key
    means predicate cannot be evaluated.
    """
    discrepancy = _disc()
    source_payload = [
        _candidate(quantity=75.0, price=7.50, executions=[_leg(price=7.50, quantity=75.0)]),
        _candidate(quantity=75.0, price=7.51, executions=[_leg(price=7.51, quantity=75.0)]),
    ]
    result = _classify_unmatched_fill_shared(
        discrepancy=discrepancy,
        source_payload=source_payload,
        # quantity matches sum (150), so reaches multi_partial_vs_consolidated branch,
        # but no 'price' → predicate cannot be evaluated → recipe stays None.
        journal_row={"quantity": 150, "ticker": "DHC"},
        direction="open",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_partial_vs_consolidated"
    assert result.auto_redirect_recipe is None
