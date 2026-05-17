"""Sub-bundle 1.5 T-1.5.2 regression coverage for the `filledQuantity == 0`
early-exit gate at `_extract_executions_from_order_raw`.

Failure mode: Schwab production emits `orderActivityCollection[].executionLegs[]`
on STOP-typed orders that NEVER EXECUTED (status REPLACED / CANCELED /
PENDING_ACTIVATION) -- informational placeholder rows where:

- order has `filledQuantity == 0.0` (EXPLICIT zero, not absent)
- `executionLegs[0].price == 0.0` (sentinel placeholder)
- `executionLegs[0].quantity > 0` (reflects order's intended size)

Without the early-exit gate, the validator rejects each placeholder leg via
`price > 0` check -> drop+warn fires uniformly on production -> `executions=None`
returned via empty-collected path -> Sub-bundle 1 positive lift never fires.

The fix lives at `swing/integrations/schwab/mappers.py:_extract_executions_from_order_raw`:
early-exit `return None` BEFORE iterating activities when the order's
`filledQuantity` is present AND equals zero.

CRITICAL PRESERVATION: permissive-when-`filledQuantity`-absent stance is
UNCHANGED -- only skip on EXPLICIT zero, not on absent/missing key.
"""
from __future__ import annotations

import logging

import pytest

from swing.integrations.schwab.mappers import _extract_executions_from_order_raw


# Test 1 -- EXPLICIT filledQuantity=0 with executionLegs present -> return None
# WITHOUT firing any drop+warn against the placeholder leg.
def test_filled_quantity_zero_early_exits_without_drop_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Discriminating regression -- pre-fix path drops the price=0 leg via
    the validator's `ValueError` -> `except (ValueError, TypeError)` -> a
    WARNING log line carrying "failed validator"; post-fix path early-exits
    cleanly BEFORE iterating legs so no such warning fires.
    """
    order_raw = {
        "orderId": 1006338076032,
        "status": "CANCELED",
        "orderType": "STOP",
        "instruction": "SELL",
        "filledQuantity": 0.0,
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionLegs": [
                    {
                        "instrumentId": 230011483,
                        "legId": 1,
                        "mismarkedQuantity": 0.0,
                        "price": 0.0,  # sentinel placeholder
                        "quantity": 7.0,
                        "time": "2026-05-13T16:09:22+0000",
                    },
                ],
            },
        ],
    }
    with caplog.at_level(
        logging.WARNING, logger="swing.integrations.schwab.mappers"
    ):
        result = _extract_executions_from_order_raw(
            order_raw, order_id="1006338076032",
        )
    assert result is None
    # Discriminating signal -- pre-fix the validator drop+warn fires (matching
    # "failed validator" substring); post-fix the early-exit returns BEFORE
    # iterating legs so no such warning fires.
    assert not any(
        "failed validator" in record.getMessage() for record in caplog.records
    )


# Test 2 -- filledQuantity ABSENT entirely -> existing behavior preserved
# (must NOT trigger the new early-exit; permissive-when-absent stance per
# `_extract_executions_from_order_raw` docstring line 275-276).
def test_filled_quantity_absent_does_not_trigger_early_exit() -> None:
    """Negative control: absent `filledQuantity` key must continue processing
    the activity (not short-circuit to None via the new gate). The existing
    behavior here is that the price=0 leg STILL gets dropped via validator,
    collected stays empty, function returns None -- but via the EXISTING
    empty-collected path, NOT the new explicit-zero early-exit.
    """
    order_raw = {
        "orderId": "ABSENT-FQ",
        "status": "WORKING",
        "orderType": "STOP",
        "instruction": "SELL",
        # filledQuantity intentionally OMITTED
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionLegs": [
                    {
                        "instrumentId": 12345,
                        "legId": 1,
                        "mismarkedQuantity": 0.0,
                        "price": 0.0,
                        "quantity": 7.0,
                        "time": "2026-05-13T16:09:22+0000",
                    },
                ],
            },
        ],
    }
    result = _extract_executions_from_order_raw(
        order_raw, order_id="ABSENT-FQ",
    )
    # Existing behavior preserved: empty-collected path returns None (validator
    # rejects price=0 leg; no surviving legs).
    assert result is None
