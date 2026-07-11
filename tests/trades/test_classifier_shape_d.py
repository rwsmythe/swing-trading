"""20-A Task A-3 — classifier Shape-D branch (entry + close) + A1/A2 guards.

Shape D = Shape-C keys PLUS ``execution_side`` + ``candidate_count`` +
``execution_sessions_from_fill`` (matcher-enriched, plan §5.3). The branch
fail-closes to tier-2 on any missing/malformed enrichment (a matcher bug can
never leak a corruption back to tier-1). On a valid Shape-D it applies A1
(candidate_count>=2), A2-side, A2-date (session int), A2-magnitude; only when
ALL pass does it emit tier-1.
"""
from __future__ import annotations

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import (
    _SHAPE_D_EXPECTED_KEYS,
    ClassificationResult,
    classify_discrepancy,
)


def _disc(dtype: str, *, ticker: str, fill_id: int | None, trade_id: int):
    return ReconciliationDiscrepancy(
        discrepancy_id=1, run_id=1, discrepancy_type=dtype, trade_id=trade_id,
        fill_id=fill_id, cash_movement_id=None,
        linked_daily_management_record_id=None, ticker=ticker,
        field_name="price", expected_value_json=None, actual_value_json=None,
        delta_text="d", material_to_review=1, resolution="unresolved",
        resolution_reason=None, resolved_at=None, resolved_by=None,
        mistake_tag_assigned=None, created_at="2026-07-11T00:00:00",
        ambiguity_kind=None,
    )


def _shape_d(price, *, side, count, sessions, qty=15.0):
    return {
        "price": price,
        "execution_legs": [
            {"leg_id": 1, "price": price, "quantity": qty,
             "time": "2026-05-19T10:00:00"},
        ],
        "schwab_order_id": "ORD1",
        "schwab_order_price": price,
        "execution_side": side,
        "candidate_count": count,
        "execution_sessions_from_fill": sessions,
    }


def test_shape_d_expected_keys_superset_of_shape_c() -> None:
    assert {"execution_side", "candidate_count",
            "execution_sessions_from_fill"} <= _SHAPE_D_EXPECTED_KEYS


def test_shape_d_all_pass_entry_tier1() -> None:
    """side BUY, session 0, count 1, magnitude 1.34% -> tier-1."""
    result = classify_discrepancy(
        _disc("entry_price_mismatch", ticker="CVGI", fill_id=9, trade_id=1),
        source_payload=_shape_d(5.30, side="BUY", count=1, sessions=0,
                                qty=100.0),
        journal_row={"price": 5.23, "quantity": 100, "action": "entry"},
    )
    assert result.tier == 1
    assert result.correction_target == {"price": 5.30}


def test_shape_d_a1_candidate_count_two_demotes(monkeypatch=None) -> None:
    result = classify_discrepancy(
        _disc("entry_price_mismatch", ticker="PTEN", fill_id=17, trade_id=10),
        source_payload=_shape_d(12.305, side="BUY", count=2, sessions=0),
        journal_row={"price": 13.00, "quantity": 15, "action": "entry"},
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_match_within_window"


def test_shape_d_a2_side_mismatch_demotes() -> None:
    """execution_side SELL vs action entry -> tier-2."""
    result = classify_discrepancy(
        _disc("entry_price_mismatch", ticker="PTEN", fill_id=17, trade_id=10),
        # magnitude within band so ONLY the side guard can demote.
        source_payload=_shape_d(13.05, side="SELL", count=1, sessions=0),
        journal_row={"price": 13.00, "quantity": 15, "action": "entry"},
    )
    assert result.tier == 2
    assert "side" in result.correction_reason.lower()


def test_shape_d_a2_date_two_sessions_demotes() -> None:
    """execution_sessions_from_fill 2 > 1 -> tier-2 (AMN 07-07 vs 07-09)."""
    result = classify_discrepancy(
        _disc("close_price_mismatch", ticker="AMN", fill_id=37, trade_id=18),
        # side + magnitude within band; ONLY the session guard demotes.
        source_payload=_shape_d(35.70, side="SELL", count=1, sessions=2,
                                qty=3.0),
        journal_row={"price": 35.65, "quantity": 3, "action": "trim"},
    )
    assert result.tier == 2


def test_shape_d_a2_magnitude_over_band_demotes() -> None:
    """AMN 32.06 vs 35.65 = 10.07% > 2% -> tier-2 (close side)."""
    result = classify_discrepancy(
        _disc("close_price_mismatch", ticker="AMN", fill_id=37, trade_id=18),
        source_payload=_shape_d(32.06, side="SELL", count=1, sessions=0,
                                qty=3.0),
        journal_row={"price": 35.65, "quantity": 3, "action": "trim"},
    )
    assert result.tier == 2
    assert "magnitude" in result.correction_reason


def test_shape_d_null_session_sentinel_forces_tier2() -> None:
    """execution_sessions_from_fill == null (resolution failure) -> tier-2."""
    result = classify_discrepancy(
        _disc("entry_price_mismatch", ticker="CVGI", fill_id=9, trade_id=1),
        source_payload=_shape_d(5.30, side="BUY", count=1, sessions=None,
                                qty=100.0),
        journal_row={"price": 5.23, "quantity": 100, "action": "entry"},
    )
    assert result.tier == 2


def test_shape_d_missing_field_fails_closed_to_tier2() -> None:
    """A malformed Shape-D (missing execution_side) fails closed to tier-2 —
    never silently re-enters the unguarded tier-1 path."""
    payload = _shape_d(12.305, side="BUY", count=1, sessions=0)
    del payload["execution_side"]  # now has candidate_count etc but not exact
    result = classify_discrepancy(
        _disc("entry_price_mismatch", ticker="PTEN", fill_id=17, trade_id=10),
        source_payload=payload,
        journal_row={"price": 13.00, "quantity": 15, "action": "entry"},
    )
    assert result.tier == 2
    assert "contract" in result.correction_reason.lower()


def test_shape_d_candidate_count_zero_fails_closed() -> None:
    """Codex R5 MAJOR — candidate_count=0 is an IMPOSSIBLE Shape-D enrichment
    (single-candidate by definition) -> fail closed to tier-2, never tier-1."""
    result = classify_discrepancy(
        _disc("entry_price_mismatch", ticker="CVGI", fill_id=9, trade_id=1),
        # side + session + magnitude all pass; ONLY the 0 count must demote.
        source_payload=_shape_d(5.30, side="BUY", count=0, sessions=0,
                                qty=100.0),
        journal_row={"price": 5.23, "quantity": 100, "action": "entry"},
    )
    assert result.tier == 2
    assert "contract" in result.correction_reason.lower()


def test_shape_d_malformed_candidate_count_fails_closed() -> None:
    """candidate_count is a string -> contract violation -> tier-2."""
    result = classify_discrepancy(
        _disc("entry_price_mismatch", ticker="PTEN", fill_id=17, trade_id=10),
        source_payload=_shape_d(13.05, side="BUY", count="1", sessions=0),
        journal_row={"price": 13.00, "quantity": 15, "action": "entry"},
    )
    assert result.tier == 2
    assert "contract" in result.correction_reason.lower()


def test_close_list_shape_demotes_multi_match() -> None:
    """The close-side LIST emit (A1) -> multi_match_within_window tier-2."""
    result = classify_discrepancy(
        _disc("close_price_mismatch", ticker="AMN", fill_id=37, trade_id=18),
        source_payload=[
            _shape_d(35.65, side="SELL", count=2, sessions=0, qty=3.0),
            _shape_d(32.06, side="SELL", count=2, sessions=2, qty=3.0),
        ],
        journal_row={"price": 35.65, "quantity": 3, "action": "trim"},
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "multi_match_within_window"
