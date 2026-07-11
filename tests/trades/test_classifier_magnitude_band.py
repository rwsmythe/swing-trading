"""20-A Task A-1 — classifier tier-1 overwrite magnitude band (A2-magnitude).

The tier-1 corrector overwrote CORRECT fill prices with the OTHER leg's
execution price (D25 forensic). A magnitude band demotes any Shape-C /
Shape-D tier-1 fill-price auto-correct whose overwrite exceeds
``_MAX_TIER1_OVERWRITE_RATIO`` (2.0%, RD-LOCKED) to tier-2.

Fixtures are the REAL live geometries (PTEN/DFTX/AMN + broker-true prices)
per the plan §9 discipline. Pre/post arithmetic:
  - PTEN entry 12.305 vs journal 13.00 -> 5.35% > 2% -> tier-2 (pre-fix: tier-1)
  - DFTX entry 22.16  vs journal 24.53 -> 9.66% > 2% -> tier-2 (pre-fix: tier-1)
  - AMN close 32.06   vs journal 35.65 -> 10.07% > 2% -> tier-2 (pre-fix: tier-1)
  - CVGI entry 5.30   vs journal 5.23  -> 1.34% <= 2% -> tier-1 (unchanged)
"""
from __future__ import annotations

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import (
    _MAX_TIER1_OVERWRITE_RATIO,
    ClassificationResult,
    classify_discrepancy,
)


def _make_discrepancy(
    dtype: str, *, ticker: str, fill_id: int, trade_id: int,
) -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=1,
        run_id=1,
        discrepancy_type=dtype,
        trade_id=trade_id,
        fill_id=fill_id,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker=ticker,
        field_name="price",
        expected_value_json=None,
        actual_value_json=None,
        delta_text="delta",
        material_to_review=1,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-07-11T00:00:00",
        ambiguity_kind=None,
    )


def _shape_c(price: float, *, qty: float = 15.0) -> dict:
    """A Shape-C ``actual_value_json`` payload (exact key-set)."""
    return {
        "price": price,
        "execution_legs": [
            {"leg_id": 1, "price": price, "quantity": qty,
             "time": "2026-05-19T10:00:00"},
        ],
        "schwab_order_id": "ORD1",
        "schwab_order_price": price,
    }


def test_band_constant_is_locked_two_percent() -> None:
    assert _MAX_TIER1_OVERWRITE_RATIO == 0.02


def test_pten_entry_shape_c_over_band_demotes_to_tier2() -> None:
    """PTEN entry 12.305 vs journal 13.00 = 5.35% > 2% -> tier-2."""
    disc = _make_discrepancy(
        "entry_price_mismatch", ticker="PTEN", fill_id=17, trade_id=10,
    )
    result = classify_discrepancy(
        disc,
        source_payload=_shape_c(12.305),
        journal_row={"price": 13.00, "quantity": 15, "action": "entry"},
    )
    assert isinstance(result, ClassificationResult)
    assert result.tier == 2
    assert result.correction_target is None
    assert "magnitude" in result.correction_reason


def test_amn_close_shape_c_over_band_demotes_to_tier2() -> None:
    """AMN trim/close 32.06 vs journal 35.65 = 10.07% > 2% -> tier-2."""
    disc = _make_discrepancy(
        "close_price_mismatch", ticker="AMN", fill_id=37, trade_id=18,
    )
    result = classify_discrepancy(
        disc,
        source_payload=_shape_c(32.06, qty=3.0),
        journal_row={"price": 35.65, "quantity": 3, "action": "trim"},
    )
    assert result.tier == 2
    assert result.correction_target is None
    assert "magnitude" in result.correction_reason


def test_dftx_entry_shape_c_over_band_demotes_to_tier2() -> None:
    """DFTX entry 22.16 vs journal 24.53 = 9.66% > 2% -> tier-2."""
    disc = _make_discrepancy(
        "entry_price_mismatch", ticker="DFTX", fill_id=28, trade_id=16,
    )
    result = classify_discrepancy(
        disc,
        source_payload=_shape_c(22.16, qty=7.0),
        journal_row={"price": 24.53, "quantity": 7, "action": "entry"},
    )
    assert result.tier == 2


def test_cvgi_entry_shape_c_within_band_stays_tier1() -> None:
    """Legitimate CVGI fix 5.23 -> 5.30 = 1.34% <= 2% -> tier-1 preserved."""
    disc = _make_discrepancy(
        "entry_price_mismatch", ticker="CVGI", fill_id=9, trade_id=1,
    )
    result = classify_discrepancy(
        disc,
        source_payload=_shape_c(5.30, qty=100.0),
        journal_row={"price": 5.23, "quantity": 100, "action": "entry"},
    )
    assert result.tier == 1
    assert result.correction_target == {"price": 5.30}


def test_close_shape_c_within_band_stays_tier1() -> None:
    """A within-band close-price fix stays tier-1 (guard does not over-fire)."""
    disc = _make_discrepancy(
        "close_price_mismatch", ticker="DHC", fill_id=50, trade_id=20,
    )
    result = classify_discrepancy(
        disc,
        source_payload=_shape_c(5.30, qty=100.0),
        journal_row={"price": 5.23, "quantity": 100, "action": "exit"},
    )
    assert result.tier == 1
    assert result.correction_target == {"price": 5.30}


def test_shape_c_missing_journal_price_keeps_tier1() -> None:
    """journal_price falsy/None -> nothing to gate against -> tier-1 kept."""
    disc = _make_discrepancy(
        "entry_price_mismatch", ticker="PTEN", fill_id=17, trade_id=10,
    )
    result = classify_discrepancy(
        disc,
        source_payload=_shape_c(12.305),
        journal_row=None,
    )
    assert result.tier == 1
