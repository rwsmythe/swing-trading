"""Phase 12.5 #1 T-1.2 — regression pin: ALL pre-existing classifier emit
paths produce ``ClassificationResult.auto_redirect_recipe = None``.

T-1.2 only populates the recipe on the multi-leg auto-redirect path inside
``_classify_unmatched_fill_shared``. Every OTHER classifier sub-function
(entry_price_mismatch / close_price_mismatch / stop_mismatch /
position_qty_mismatch / cash_movement_mismatch / sector_tamper /
snapshot_mismatch / equity_delta) MUST emit ``auto_redirect_recipe=None``
via the dataclass default.
"""
from __future__ import annotations

from typing import Any

import pytest

from swing.data.models import ReconciliationDiscrepancy
from swing.trades.reconciliation_classifier import (
    ClassificationResult,
    classify_discrepancy,
)


def _make_discrepancy(
    *,
    discrepancy_type: str,
    field_name: str = "price",
    ticker: str = "TST",
    fill_id: int | None = 1,
    cash_movement_id: int | None = None,
    trade_id: int | None = 1,
    expected_value_json: str = '{"price": 5.00}',
    actual_value_json: str = '{"price": 5.10}',
) -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=1,
        run_id=1,
        discrepancy_type=discrepancy_type,
        trade_id=trade_id,
        fill_id=fill_id,
        cash_movement_id=cash_movement_id,
        linked_daily_management_record_id=None,
        ticker=ticker,
        field_name=field_name,
        expected_value_json=expected_value_json,
        actual_value_json=actual_value_json,
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


# Each tuple: (discrepancy_type, source_payload, journal_row, extra kwargs).
# Selected to exercise EACH classifier sub-function (tier-1 OR tier-2) and
# confirm the auto_redirect_recipe default flows through.
_CASES: list[tuple[str, Any, Any, dict[str, Any]]] = [
    # entry_price_mismatch — tier-1 path (only price differs).
    (
        "entry_price_mismatch",
        {"price": 5.30},
        {"price": 5.23, "quantity": 100, "ticker": "TST"},
        {},
    ),
    # entry_price_mismatch — tier-2 schwab_returned_no_match.
    (
        "entry_price_mismatch",
        None,
        {"price": 5.23, "quantity": 100, "ticker": "TST"},
        {},
    ),
    # close_price_mismatch — tier-1 path.
    (
        "close_price_mismatch",
        {"price": 5.30},
        {"price": 5.23, "quantity": 100, "ticker": "TST"},
        {},
    ),
    # close_price_mismatch — tier-2 schwab_returned_no_match.
    (
        "close_price_mismatch",
        None,
        {"price": 5.23, "quantity": 100, "ticker": "TST"},
        {},
    ),
    # stop_mismatch.
    (
        "stop_mismatch",
        {"stop_price": 7.50},
        {"current_stop": 7.62, "ticker": "TST"},
        {"field_name": "current_stop"},
    ),
    # position_qty_mismatch.
    (
        "position_qty_mismatch",
        {"quantity": 100},
        {"quantity": 99, "ticker": "TST"},
        {"field_name": "quantity"},
    ),
    # cash_movement_mismatch.
    (
        "cash_movement_mismatch",
        {"amount_dollars": 100.00},
        {"amount_dollars": 99.00},
        {"field_name": "amount_dollars", "fill_id": None, "cash_movement_id": 1, "trade_id": None},
    ),
    # equity_delta.
    (
        "equity_delta",
        {"net_liquidating_value_dollars": 2000.00},
        {"equity_dollars": 2015.00},
        {"field_name": "equity_delta", "fill_id": None, "trade_id": None},
    ),
]


@pytest.mark.parametrize("discrepancy_type, source_payload, journal_row, extra", _CASES)
def test_pre_existing_classifier_emit_paths_recipe_is_none(
    discrepancy_type: str,
    source_payload: Any,
    journal_row: Any,
    extra: dict[str, Any],
) -> None:
    """All pre-existing classifier emit paths MUST flow `auto_redirect_recipe`
    through as the dataclass default ``None``.

    T-1.2 ONLY populates the recipe on the multi-leg auto-redirect path
    inside ``_classify_unmatched_fill_shared``; every other emit path is
    pinned by this regression test to stay at None.
    """
    discrepancy = _make_discrepancy(discrepancy_type=discrepancy_type, **extra)
    result = classify_discrepancy(
        discrepancy,
        source_payload=source_payload,
        journal_row=journal_row,
        validator_chain=None,
    )
    assert isinstance(result, ClassificationResult)
    assert result.auto_redirect_recipe is None, (
        f"discrepancy_type={discrepancy_type!r} with source_payload="
        f"{source_payload!r} unexpectedly emitted "
        f"auto_redirect_recipe={result.auto_redirect_recipe!r}; ONLY the "
        f"unmatched_*_fill multi-leg auto-redirect path may populate the "
        f"recipe per T-1.2."
    )


def test_validator_rejected_downgrade_path_recipe_is_none() -> None:
    """When the validator_chain rejects a tier-1 result, the dispatcher
    downgrades to ``(tier=2, ambiguity_kind='validator_rejected', ...)`` —
    that downgrade path also MUST emit recipe=None.
    """
    discrepancy = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
    )

    def _always_reject(_target: Any) -> tuple[bool, str | None]:
        return (False, "bogus reason")

    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": 5.30},
        journal_row={"price": 5.23, "quantity": 100, "ticker": "TST"},
        validator_chain=_always_reject,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "validator_rejected"
    assert result.auto_redirect_recipe is None


def test_classifier_exception_path_recipe_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a sub-classifier raises an exception, the dispatcher catches and
    emits ``(tier=2, ambiguity_kind='unsupported', ...)`` per spec §4.5
    graceful-degradation contract — the exception path also MUST emit
    recipe=None.
    """
    from swing.trades import reconciliation_classifier as rc

    def _explodes(**_kwargs: Any) -> ClassificationResult:
        raise RuntimeError("synthetic test failure")

    monkeypatch.setitem(rc._SUB_CLASSIFIERS, "entry_price_mismatch", _explodes)

    discrepancy = _make_discrepancy(discrepancy_type="entry_price_mismatch")
    result = classify_discrepancy(
        discrepancy,
        source_payload={"price": 5.30},
        journal_row={"price": 5.23, "quantity": 100, "ticker": "TST"},
        validator_chain=None,
    )
    assert result.tier == 2
    assert result.ambiguity_kind == "unsupported"
    assert result.auto_redirect_recipe is None
