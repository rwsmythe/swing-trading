"""Sub-bundle 1.5 Codex R1 M#1+M#6 -- observability canary for the
filledQuantity == 0 early-exit gate.

Failure mode addressed: Codex R1 noted that the T-1.5.2 broad gate at
`_extract_executions_from_order_raw` (`if filled_qty == 0: return None`)
silently swallows ANY future order shape with `filledQuantity=0` regardless
of leg content. The diagnosed STOP/REPLACED/CANCELED placeholder family has
`leg.price == 0` (sentinel); but a hypothetical future Schwab regression could
emit `filledQuantity=0` AND non-zero-price legs (internally-inconsistent shape).
Without observability, that future regression would be silently dropped.

The fix preserves the gate semantics (still returns None -- no behavior change
to skipping) but emits a WARN log line BEFORE returning None when any leg in
the activities has a non-zero price. The WARN substring "anomalous shape" is
the discriminating signal.

The helper `_has_non_placeholder_leg` is defensively-parsed: any malformed
shape returns False (no false-positive warnings).
"""
from __future__ import annotations

import logging

import pytest

from swing.integrations.schwab.mappers import (
    _extract_executions_from_order_raw,
    _has_non_placeholder_leg,
)


# Test 1 (Major 1+6 BINDING) -- anomalous shape: filledQuantity=0 + leg
# with price>0 -> early-exit None + WARN with "anomalous shape" substring.
def test_anomalous_shape_emits_warn_inside_early_exit_gate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Discriminating regression for Codex R1 M#1+M#6 -- the canary fires
    when a future Schwab response carries filledQuantity=0 + non-zero-price
    legs (would-be-silent under broad gate; now observable via WARN).
    """
    order_raw = {
        "orderId": "ANOMALOUS-1",
        "status": "CANCELED",
        "orderType": "STOP",
        "instruction": "SELL",
        "filledQuantity": 0.0,
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionLegs": [
                    {
                        "instrumentId": 999,
                        "legId": 1,
                        "mismarkedQuantity": 0.0,
                        "price": 10.50,  # non-zero -- canary signal
                        "quantity": 5.0,
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
            order_raw, order_id="ANOMALOUS-1",
        )
    # Gate behavior preserved: returns None.
    assert result is None
    # Observability hook fires: at least one WARNING carries "anomalous shape".
    assert any(
        "anomalous shape" in record.getMessage() for record in caplog.records
    ), (
        f"Expected 'anomalous shape' WARN; got: "
        f"{[r.getMessage() for r in caplog.records]}"
    )


# Test 2 (Major 1+6 BINDING NEGATIVE control) -- placeholder shape:
# filledQuantity=0 + leg with price=0 -> early-exit None + NO WARN.
def test_placeholder_shape_silent_no_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The diagnosed STOP/REPLACED/CANCELED placeholder family (leg.price=0)
    must remain silent under the early-exit gate -- the canary discrimates
    ONLY anomalous shapes from the known-benign placeholder population.
    """
    order_raw = {
        "orderId": "PLACEHOLDER-1",
        "status": "CANCELED",
        "orderType": "STOP",
        "instruction": "SELL",
        "filledQuantity": 0.0,
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionLegs": [
                    {
                        "instrumentId": 999,
                        "legId": 1,
                        "mismarkedQuantity": 0.0,
                        "price": 0.0,  # placeholder sentinel
                        "quantity": 5.0,
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
            order_raw, order_id="PLACEHOLDER-1",
        )
    assert result is None
    # NO "anomalous shape" warning fires on the benign placeholder population.
    assert not any(
        "anomalous shape" in record.getMessage() for record in caplog.records
    )


# Test 3 -- multi-leg anomalous: one zero-price leg + one non-zero -> canary fires.
def test_anomalous_multi_leg_one_non_zero_fires(
    caplog: pytest.LogCaptureFixture,
) -> None:
    order_raw = {
        "orderId": "MIXED-1",
        "status": "CANCELED",
        "orderType": "STOP",
        "filledQuantity": 0.0,
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionLegs": [
                    {
                        "legId": 1, "price": 0.0, "quantity": 5.0,
                        "time": "2026-05-13T16:09:22+0000",
                    },
                    {
                        "legId": 2, "price": 7.25, "quantity": 3.0,
                        "time": "2026-05-13T16:09:23+0000",
                    },
                ],
            },
        ],
    }
    with caplog.at_level(
        logging.WARNING, logger="swing.integrations.schwab.mappers"
    ):
        result = _extract_executions_from_order_raw(
            order_raw, order_id="MIXED-1",
        )
    assert result is None
    assert any(
        "anomalous shape" in record.getMessage() for record in caplog.records
    )


# ---------------------------------------------------------------------------
# Helper-level coverage -- `_has_non_placeholder_leg` is defensively parsed.
# ---------------------------------------------------------------------------

def test_has_non_placeholder_leg_returns_true_on_positive_price() -> None:
    activities = [
        {
            "activityType": "EXECUTION",
            "executionLegs": [{"price": 5.30, "quantity": 1.0}],
        },
    ]
    assert _has_non_placeholder_leg(activities) is True


def test_has_non_placeholder_leg_returns_false_on_all_zero() -> None:
    activities = [
        {
            "activityType": "EXECUTION",
            "executionLegs": [
                {"price": 0.0, "quantity": 1.0},
                {"price": 0.0, "quantity": 2.0},
            ],
        },
    ]
    assert _has_non_placeholder_leg(activities) is False


def test_has_non_placeholder_leg_defensive_non_list() -> None:
    """Non-list activities -> False (no false positives)."""
    assert _has_non_placeholder_leg("not a list") is False
    assert _has_non_placeholder_leg(None) is False
    assert _has_non_placeholder_leg(42) is False
    assert _has_non_placeholder_leg({"key": "value"}) is False


def test_has_non_placeholder_leg_defensive_non_dict_entries() -> None:
    """Non-dict activity entries / non-list legs are skipped."""
    activities: list = [
        "not a dict",
        None,
        {"executionLegs": "not a list"},
        {"executionLegs": None},
    ]
    assert _has_non_placeholder_leg(activities) is False


def test_has_non_placeholder_leg_defensive_non_dict_legs() -> None:
    """Non-dict leg entries are skipped without raising."""
    activities = [
        {
            "activityType": "EXECUTION",
            "executionLegs": ["not a dict", None, 42, []],
        },
    ]
    assert _has_non_placeholder_leg(activities) is False


def test_has_non_placeholder_leg_defensive_non_numeric_price() -> None:
    """Non-numeric price values are skipped (TypeError on float coercion)."""
    activities = [
        {
            "activityType": "EXECUTION",
            "executionLegs": [
                {"price": "abc", "quantity": 1.0},
                {"price": None, "quantity": 1.0},
                {"price": [1, 2], "quantity": 1.0},
            ],
        },
    ]
    assert _has_non_placeholder_leg(activities) is False


def test_has_non_placeholder_leg_rejects_bool_price() -> None:
    """Python bool is subclass of int -- explicit reject to avoid
    `True == 1.0 > 0` false positive."""
    activities = [
        {
            "activityType": "EXECUTION",
            "executionLegs": [{"price": True, "quantity": 1.0}],
        },
    ]
    assert _has_non_placeholder_leg(activities) is False


def test_has_non_placeholder_leg_missing_price_key() -> None:
    """Leg missing 'price' key -> defaults to 0 -> not non-placeholder."""
    activities = [
        {
            "activityType": "EXECUTION",
            "executionLegs": [{"quantity": 1.0}],
        },
    ]
    assert _has_non_placeholder_leg(activities) is False


# Test 11 (Codex R2 Major #2 BINDING) -- scope alignment with mapper
# extraction loop. The canary must skip non-EXECUTION activities just as
# `_extract_executions_from_order_raw` silently skips them at
# mappers.py:373-377. Without this filter the canary would fire on data
# the mapper would otherwise ignore (false-positive "anomalous shape"
# WARN on non-execution payloads like ORDER_ACTION audit rows).
def test_anomalous_shape_skips_non_execution_activity(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Plant an order with filledQuantity=0 + a NON-EXECUTION activity
    (activityType='ORDER_ACTION') carrying a non-zero-price leg. The
    canary MUST NOT fire because the mapper's extraction loop ignores
    non-EXECUTION activities; the canary now mirrors that semantic.
    """
    order_raw = {
        "orderId": "ORDER-ACTION-1",
        "status": "CANCELED",
        "orderType": "STOP",
        "instruction": "SELL",
        "filledQuantity": 0.0,
        "orderActivityCollection": [
            {
                # NOT 'EXECUTION' -- the mapper would silently skip this
                # activity at line 373-377 even if leg.price > 0.
                "activityType": "ORDER_ACTION",
                "executionLegs": [
                    {
                        "instrumentId": 999,
                        "legId": 1,
                        "mismarkedQuantity": 0.0,
                        "price": 10.50,  # non-zero -- would-be canary signal
                        "quantity": 5.0,
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
            order_raw, order_id="ORDER-ACTION-1",
        )
    # Gate behavior preserved: returns None (filledQuantity=0 gate fires).
    assert result is None
    # Canary MUST NOT fire because the non-zero-price leg lives under a
    # non-EXECUTION activity -- mapper extraction loop ignores it anyway.
    assert not any(
        "anomalous shape" in record.getMessage() for record in caplog.records
    ), (
        "Expected NO 'anomalous shape' WARN for non-EXECUTION activity; "
        f"got: {[r.getMessage() for r in caplog.records]}"
    )


# Test 12 (Codex R2 Major #2 supporting) -- helper-level coverage of the
# EXECUTION-only filter.
def test_has_non_placeholder_leg_skips_non_execution_activity() -> None:
    """Non-EXECUTION activity types are skipped regardless of leg prices."""
    activities = [
        {
            "activityType": "ORDER_ACTION",
            "executionLegs": [{"price": 99.0, "quantity": 1.0}],
        },
    ]
    assert _has_non_placeholder_leg(activities) is False


# Test 13 (Codex R2 Major #2 supporting) -- mixed: EXECUTION activity with
# zero-price legs alongside a NON-EXECUTION activity with non-zero-price
# legs. Canary must NOT fire (only EXECUTION-scoped legs participate).
def test_has_non_placeholder_leg_mixed_non_execution_ignored() -> None:
    activities = [
        {
            "activityType": "EXECUTION",
            "executionLegs": [{"price": 0.0, "quantity": 5.0}],
        },
        {
            "activityType": "ORDER_ACTION",
            "executionLegs": [{"price": 99.0, "quantity": 1.0}],
        },
    ]
    assert _has_non_placeholder_leg(activities) is False
