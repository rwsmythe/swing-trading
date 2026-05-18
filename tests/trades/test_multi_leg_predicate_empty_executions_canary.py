"""Phase 12.5 #1 T-1.11 — empty-executions canary observability hook.

Plan §A T-1.11 + spec §12.3. The multi-leg predicate fires a single
``logger.warning`` at decline time WHEN AND ONLY WHEN at least one
candidate's ``executions`` value is exactly ``[]`` (empty list, NOT
``None`` and NOT a populated list). The decline result text itself
remains UNCHANGED — the canary is observability-only.

The predicate gains a new optional kwarg-only ``ticker: str | None``
(default ``None``) so the canary warning can cite the ticker when
invoked from ``_classify_unmatched_fill_shared``; pre-existing T-1.1
fixtures + the synthesizer call sites that omit ``ticker`` keep
working.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping

from swing.trades.reconciliation_classifier import (
    _multi_leg_auto_redirect_predicate,
)


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
    executions: list[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    return {"order_id": order_id, "executions": executions}


def test_predicate_logs_warning_when_executions_is_empty_list_canary(
    caplog,
) -> None:
    """Empty list executions + sub-condition 1 declines → WARNING fires.

    Canary substring must cite ticker AND "executions list is empty
    (canary)". Decline-reason returned to caller is unaffected by canary
    emission.
    """
    caplog.set_level(
        logging.WARNING, logger="swing.trades.reconciliation_classifier"
    )
    candidates = [
        _candidate(order_id="12345", executions=[]),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=100.0,
        journal_price=5.30,
        ticker="DHC",
    )
    assert ok is False
    assert reason is not None
    # The pre-existing decline reason text is unchanged by the canary hook.
    assert "12345" in reason
    assert "no execution legs" in reason.lower()
    # The canary warning was emitted at WARNING level with ticker + canary
    # substring + order_id.
    canary_records = [
        r for r in caplog.records
        if r.levelno == logging.WARNING
        and "executions list is empty (canary)" in r.getMessage()
    ]
    assert len(canary_records) == 1
    msg = canary_records[0].getMessage()
    assert "DHC" in msg
    assert "12345" in msg


def test_predicate_no_warning_when_executions_is_none(caplog) -> None:
    """``executions=None`` → predicate still declines but NO canary fires.

    The canary is specifically for the empty-list family (Schwab returned
    an executionLegs container that's empty); the None family is the
    typed-missing case already handled by Sub-bundle 1.5 + the
    `execution_unavailable` sentinel path.
    """
    caplog.set_level(
        logging.WARNING, logger="swing.trades.reconciliation_classifier"
    )
    candidates = [
        _candidate(order_id="67890", executions=None),
    ]
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=100.0,
        journal_price=5.30,
        ticker="VSAT",
    )
    assert ok is False
    assert reason is not None
    canary_records = [
        r for r in caplog.records
        if "executions list is empty (canary)" in r.getMessage()
    ]
    assert canary_records == []


def test_predicate_no_warning_when_executions_has_legs(caplog) -> None:
    """Populated executions → predicate may fire or decline on a different
    sub-condition, but no canary warning fires regardless of outcome.

    Uses qty_sum mismatch to force decline at sub-condition 4 (verifies
    the canary is sub-condition-1-specific, not catch-all decline-hook).
    """
    caplog.set_level(
        logging.WARNING, logger="swing.trades.reconciliation_classifier"
    )
    candidates = [
        _candidate(
            order_id="33333",
            executions=[
                _leg(leg_id=1, price=5.30, quantity=50.0),
                _leg(leg_id=2, price=5.30, quantity=50.0),
            ],
        ),
    ]
    # journal_qty=200 vs leg sum 100 → declines at sub-condition 4.
    ok, reason = _multi_leg_auto_redirect_predicate(
        candidates=candidates,
        journal_qty=200.0,
        journal_price=5.30,
        ticker="CVGI",
    )
    assert ok is False
    assert reason is not None
    canary_records = [
        r for r in caplog.records
        if "executions list is empty (canary)" in r.getMessage()
    ]
    assert canary_records == []
