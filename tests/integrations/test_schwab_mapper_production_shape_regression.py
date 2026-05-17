"""Sub-bundle 1.5 T-1.5.3 production-shape regression coverage.

Plants BYTE-FOR-BYTE order payloads from operator's production responses
(sanitized of any account identifiers) -- captured at T-1.5.1 diagnostic.
Validates the T-1.5.2 fix at `_extract_executions_from_order_raw` against
the actual shape Schwab emits, not synthetic test fixtures (closes the
"synthetic-fixture-vs-production-emitter shape drift" failure family per
CLAUDE.md Gotchas).

Production shapes documented from 30-day diagnostic sample (22 orders;
17 with executionLegs):

  Case A -- FILLED LIMIT order (5 of 17 legs in sample):
      status=FILLED, orderType=LIMIT, filledQuantity > 0,
      executionLegs[0].price > 0 -- extracts successfully.

  Case B -- CANCELED STOP placeholder (production shape from T-1.5.1
  diagnostic Order id=1006338076032):
      status=CANCELED, orderType=STOP, filledQuantity=0.0,
      executionLegs[0].price=0.0 sentinel -- T-1.5.2 fix early-exits
      cleanly without firing drop+warn.

  Case C -- REPLACED STOP placeholder (production shape from T-1.5.1
  diagnostic Order id=1006319961824, status=REPLACED):
      Same defective shape as Case B -- different status, same gate.

  Case D -- DISCRIMINATING pre-fix vs post-fix proof (defensive):
      Asserts the existing coherence-check log signature is NOT in
      caplog when extracting Case B with the fix in place. Per
      memory/feedback_regression_test_arithmetic.md durable lesson,
      computes the assertion under BOTH pre-fix (would have fired
      "failed validator" drop+warn) and post-fix (early-exit, ZERO
      such warnings) paths.

  Case E -- filledQuantity ABSENT preservation (NEGATIVE control):
      Permissive-when-absent stance per `_extract_executions_from_order_raw`
      docstring line 275-276 MUST be preserved -- existing behavior
      (drop+warn on price=0 leg via validator, return None via
      empty-collected path) is the EXPECTED EXISTING behavior; the
      T-1.5.2 fix MUST NOT change it.

Sanitization: values redacted of account-level identifiers per
operator's diagnostic output; instrumentIds + prices retained because
they're shape-illustrative, not identifying.
"""
from __future__ import annotations

import logging

import pytest

from swing.integrations.schwab.mappers import _extract_executions_from_order_raw
from swing.integrations.schwab.models import SchwabExecutionLeg


# Case A -- FILLED LIMIT order extracts successfully (positive path; the
# uncommon-in-30-day-sample but architecturally critical hot path).
def test_case_a_filled_limit_order_extracts_successfully(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sub-bundle 1 positive lift fires here -- the 5/17 real FILLED legs
    in T-1.5.1 production sample (e.g., CVGI fill 12.6999 from Order
    id=1006387238791) must continue to extract end-to-end."""
    order_raw = {
        "orderId": 1006387238791,
        "status": "FILLED",
        "orderType": "LIMIT",
        "instruction": "BUY",
        "filledQuantity": 18.0,
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionLegs": [
                    {
                        "instrumentId": 234814458,
                        "legId": 1,
                        "mismarkedQuantity": 0.0,
                        "price": 12.6999,
                        "quantity": 18.0,
                        "time": "2026-05-15T18:55:46+0000",
                    },
                ],
            },
        ],
    }
    with caplog.at_level(
        logging.WARNING, logger="swing.integrations.schwab.mappers"
    ):
        result = _extract_executions_from_order_raw(
            order_raw, order_id="1006387238791",
        )
    assert result is not None
    assert len(result) == 1
    leg = result[0]
    assert isinstance(leg, SchwabExecutionLeg)
    assert leg.leg_id == 1
    assert leg.price == 12.6999
    assert leg.quantity == 18.0
    assert leg.instrument_id == 234814458
    assert leg.time == "2026-05-15T18:55:46+0000"
    # No drop+warn on the positive path.
    assert not any(
        "dropping leg" in record.getMessage() for record in caplog.records
    )


# Case B -- CANCELED STOP placeholder early-exits cleanly (T-1.5.2 fix
# binding criterion; this is the empirical production shape from
# T-1.5.1 diagnostic Order id=1006338076032).
def test_case_b_canceled_stop_placeholder_early_exits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-1.5.2 fix binding criterion -- Schwab production sentinel:
    status=CANCELED + orderType=STOP + filledQuantity=0.0 + leg.price=0.0
    + leg.quantity>0 (reflects intended order size) -> early-exit None
    BEFORE iterating legs."""
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
                        "price": 0.0,
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
    # ZERO drop+warn fired -- the T-1.5.2 regression criterion.
    assert not any(
        "dropping leg" in record.getMessage() for record in caplog.records
    )
    assert not any(
        "failed validator" in record.getMessage() for record in caplog.records
    )


# Case C -- REPLACED STOP placeholder (same shape as Case B but different
# status; production Order id=1006319961824 from T-1.5.1).
def test_case_c_replaced_stop_placeholder_early_exits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Same defective sentinel shape with status=REPLACED -- T-1.5.2
    early-exit is status-agnostic (gates on filledQuantity == 0 regardless
    of order status / type)."""
    order_raw = {
        "orderId": 1006319961824,
        "status": "REPLACED",
        "orderType": "STOP",
        "instruction": "SELL",
        "filledQuantity": 0.0,
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionLegs": [
                    {
                        "instrumentId": 155643,
                        "legId": 1,
                        "mismarkedQuantity": 0.0,
                        "price": 0.0,
                        "quantity": 20.0,
                        "time": "2026-05-13T07:49:13+0000",
                    },
                ],
            },
        ],
    }
    with caplog.at_level(
        logging.WARNING, logger="swing.integrations.schwab.mappers"
    ):
        result = _extract_executions_from_order_raw(
            order_raw, order_id="1006319961824",
        )
    assert result is None
    assert not any(
        "dropping leg" in record.getMessage() for record in caplog.records
    )
    assert not any(
        "failed validator" in record.getMessage() for record in caplog.records
    )


# Case D -- DISCRIMINATING pre-fix vs post-fix proof.
def test_case_d_pre_fix_vs_post_fix_discriminator(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Per memory/feedback_regression_test_arithmetic.md durable lesson,
    document the discrimination explicitly.

    Pre-fix (without the T-1.5.2 early-exit gate at mappers.py):
        - filled_qty computed from filledQuantity=0.0 -> 0.0;
        - activity loop entered; activity is EXECUTION;
        - leg loop entered; leg has price=0.0;
        - bool guard NOT triggered (0.0 is a float, not bool);
        - time guard NOT triggered (non-empty str);
        - SchwabExecutionLeg(...) constructor invoked;
        - __post_init__ validator's price > 0 check RAISES ValueError;
        - except (ValueError, TypeError) catches -> drop+warn log line
          'failed validator (ValueError); dropping leg';
        - collected stays empty -> empty-collected return None;
        - net result: returned None BUT one WARNING fired per leg.

    Post-fix (with the T-1.5.2 early-exit gate):
        - filled_qty computed from filledQuantity=0.0 -> 0.0;
        - early-exit gate fires `filled_qty is not None and filled_qty == 0`
          -> return None BEFORE iterating activities;
        - net result: returned None with ZERO log lines fired.

    Both paths return None; the discriminating signal is the log output.
    This test asserts the post-fix path (no warnings) -- pre-fix it would
    fail with the captured "failed validator" log record.
    """
    order_raw = {
        "orderId": "DISCRIMINATOR-1",
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
                        "price": 0.0,
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
            order_raw, order_id="DISCRIMINATOR-1",
        )
    assert result is None
    # Discriminating assertion: ZERO records on the mapper logger -- the
    # post-fix path doesn't even enter the activity loop.
    mapper_records = [
        record
        for record in caplog.records
        if record.name == "swing.integrations.schwab.mappers"
    ]
    assert len(mapper_records) == 0


# Case E -- NEGATIVE control: filledQuantity absent preserves existing
# behavior (validator drops the price=0 leg via empty-collected path).
def test_case_e_filled_quantity_absent_preserves_existing_behavior(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Permissive-when-`filledQuantity`-absent stance preserved per
    docstring lines 275-276. With the key entirely absent, the gate at
    lines 296-307 does NOT fire (filled_qty is None). The activity loop
    proceeds; the price=0 leg is dropped via validator; empty-collected
    return None.

    Pre-fix and post-fix both return None on this input -- the FIX
    introduces ZERO behavior change here. This test pins that invariant.
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
    with caplog.at_level(
        logging.WARNING, logger="swing.integrations.schwab.mappers"
    ):
        result = _extract_executions_from_order_raw(
            order_raw, order_id="ABSENT-FQ",
        )
    assert result is None
    # Existing behavior preserved: the validator drop+warn DOES fire on this
    # input -- key absent means the gate doesn't trigger; the activity loop
    # proceeds and the price=0 leg is rejected via __post_init__ -> ValueError.
    assert any(
        "failed validator" in record.getMessage() for record in caplog.records
    )
