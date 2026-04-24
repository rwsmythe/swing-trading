"""Parity fixture test for the earnings-proximity study.

Satisfies the deterministic half of the parity standard (study design §
Parity standard; V2.1 §VII.B): excluded-vs-eligible classification must
be bit-identical and a pure function of (signal_date, next_earnings_date,
X, trading_calendar). No floating-point, no external state.

The toleranced half (vendor-backed equivalence on live calendar data) was
addressed by Session 2a's 5/5 spot-check in
``research/notes/earnings-calendar-sources.md``.
"""
from __future__ import annotations

from datetime import date

import exchange_calendars as xcals


def _sig(d, next_earn):
    from research.harness.earnings_proximity.replay import AplusSignal

    return AplusSignal(
        ticker="FIXTURE",
        date=d,
        entry_target=100.0,
        initial_stop=95.0,
        next_earnings_date=next_earn,
        absent_earnings_data=False,
    )


def test_earnings_proximity_fixture_identity():
    """Two fixed signals, one excluded at X=5 and one eligible. Classification
    is pure-functional and repeatable across any number of invocations."""
    from research.harness.earnings_proximity.variants import apply_variant

    cal = xcals.get_calendar("XNYS")

    # Signal A: Mon 2025-06-02, earnings Wed 2025-06-04 = 2 sessions out.
    # At X=5: excluded (2 < 5).
    signal_a = _sig(d=date(2025, 6, 2), next_earn=date(2025, 6, 4))

    # Signal B: Mon 2025-06-02, earnings Mon 2025-07-07 = 25 sessions out.
    # At X=5: kept (25 >= 5).
    signal_b = _sig(d=date(2025, 6, 2), next_earn=date(2025, 7, 7))

    filtered = apply_variant([signal_a, signal_b], 5, cal)
    assert filtered == [signal_b]

    # Deterministic across repeat calls.
    for _ in range(5):
        assert apply_variant([signal_a, signal_b], 5, cal) == [signal_b]
        assert apply_variant([signal_a], 5, cal) == []
        assert apply_variant([signal_b], 5, cal) == [signal_b]

    # Sensitivity: changing X reshapes the output deterministically.
    assert apply_variant([signal_a], 2, cal) == [signal_a]  # 2 < 2 False → kept
    assert apply_variant([signal_a], 3, cal) == []           # 2 < 3 → excluded
