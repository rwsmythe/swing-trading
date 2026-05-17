"""Tests for Sub-bundle 1 T-1.9 — Path B execution_unavailable sentinel
recognition at `_classify_unmatched_fill_shared`.

Per plan §A.1.9 + spec §5.2 + §6.1 OQ-A LOCK. V1 Pass-2 STAYS
tier-2-always (Pass-2-tier-1-FORBIDDEN per spec §1.5 + §6.6 OQ-F V2).
5 discriminating cases.
"""
from __future__ import annotations

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import (
    _classify_unmatched_fill_shared,
)


def _disc(*, discrepancy_type: str = "unmatched_open_fill",
          ticker: str = "GHI", fill_id: int = 100):
    return ReconciliationDiscrepancy(
        discrepancy_id=1,
        run_id=1,
        discrepancy_type=discrepancy_type,
        field_name="fill_match",
        trade_id=1,
        fill_id=fill_id,
        cash_movement_id=None,
        ticker=ticker,
        expected_value_json=None,
        actual_value_json=None,
        delta_text=None,
        material_to_review=1,
        created_at="2026-05-16T12:00:00",
        resolution="unresolved",
        resolved_by=None,
        resolved_at=None,
        resolution_reason=None,
        ambiguity_kind=None,
        linked_daily_management_record_id=None,
        mistake_tag_assigned=None,
    )


# Test 1 — Path B sentinel for unmatched_open_fill → tier-2 unsupported
# with reason citing 'execution-grain' / 'execution_unavailable'.
def test_path_b_unmatched_open_fill_tier_2_unsupported_with_clear_reason() -> None:
    payload = {
        "matched": None,
        "execution_unavailable": True,
        "schwab_order_id": "ORD-GHI-1",
        "schwab_order_price": 20.05,
    }
    result = _classify_unmatched_fill_shared(
        discrepancy=_disc(),
        source_payload=payload,
        journal_row={"fill_id": 100, "trade_id": 1,
                     "fill_datetime": "2026-05-15",
                     "action": "entry", "quantity": 100, "price": 20.00},
        direction="open",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert (
        "execution-grain" in result.correction_reason
        or "execution_unavailable" in result.correction_reason
    )


# Test 2 — Path B sentinel for unmatched_close_fill → same shape.
def test_path_b_unmatched_close_fill_tier_2_unsupported() -> None:
    payload = {
        "matched": None,
        "execution_unavailable": True,
        "schwab_order_id": "ORD-MNO-1",
        "schwab_order_price": 5.00,
    }
    result = _classify_unmatched_fill_shared(
        discrepancy=_disc(discrepancy_type="unmatched_close_fill",
                          ticker="MNO"),
        source_payload=payload,
        journal_row={"fill_id": 100, "trade_id": 1,
                     "fill_datetime": "2026-05-15",
                     "action": "exit", "quantity": 100, "price": 4.95},
        direction="close",
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert "unmatched_close_fill" in result.correction_reason


# Test 3 — Path B sentinel reason includes schwab_order_id for
# operator-actionability.
def test_path_b_sentinel_reason_includes_schwab_order_id() -> None:
    payload = {
        "matched": None,
        "execution_unavailable": True,
        "schwab_order_id": "ORD-1234567890",
        "schwab_order_price": 7.50,
    }
    result = _classify_unmatched_fill_shared(
        discrepancy=_disc(),
        source_payload=payload,
        journal_row=None,
        direction="open",
    )
    assert "ORD-1234567890" in result.correction_reason


# Test 4 — Legacy Pass-1 no-payload path → still tier-2 unsupported (V1
# behavior unchanged; preserves the existing pre-T-1.9 branch).
def test_legacy_pass_1_no_payload_still_tier_2() -> None:
    result = _classify_unmatched_fill_shared(
        discrepancy=_disc(),
        source_payload=None,
        journal_row={"fill_id": 100, "trade_id": 1,
                     "fill_datetime": "2026-05-15",
                     "action": "entry", "quantity": 100, "price": 20.00},
        direction="open",
    )
    assert result.tier == 2
    # Distinct from Path B: should NOT contain 'execution_unavailable'.
    assert "execution_unavailable" not in result.correction_reason
    # Should contain the V1 pass-1 reason marker.
    assert "_pass_2_required" in result.correction_reason


# Test 5 — Pass-2 list-shape payload (n>=2) STILL routes through V1 logic
# (tier-2 multi_match_within_window etc.) — Pass-2-tier-1-FORBIDDEN LOCK
# preserved by T-1.9.
def test_pass_2_list_shape_still_tier_2_no_v1_lift_regression() -> None:
    """Pass-2 with N=2 Schwab records. Expected V1 behavior: tier-2 with
    multi-match-related ambiguity_kind. T-1.9 MUST NOT have widened
    Pass-2 LIFT."""
    payload = [
        {"price": 5.30, "ticker": "ABC", "quantity": 50},
        {"price": 5.32, "ticker": "ABC", "quantity": 50},
    ]
    result = _classify_unmatched_fill_shared(
        discrepancy=_disc(ticker="ABC"),
        source_payload=payload,
        journal_row={"fill_id": 100, "trade_id": 1,
                     "fill_datetime": "2026-05-15",
                     "action": "entry", "quantity": 100, "price": 5.23},
        direction="open",
    )
    assert result.tier == 2  # NO V1 LIFT
    assert result.ambiguity_kind in (
        "multi_partial_vs_consolidated",  # qty-sum matches journal
        "multi_match_within_window",
    )
