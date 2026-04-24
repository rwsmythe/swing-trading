"""Metrics aggregator tests.

Expectancy is the mean R across TRIGGERED trades (dropped/never-triggered
signals are excluded — they are not trades). Gap-through rate is the
fraction of LOSING (stopped) trades that gapped through the stop.
"""
from __future__ import annotations

from datetime import date

import pytest


def _outcome(
    *,
    triggered: bool = True,
    r_multiple: float | None = -1.0,
    gap_through: bool = False,
    gap_magnitude_r: float | None = None,
    time_capped: bool = False,
):
    from research.harness.earnings_proximity.simulator import TradeOutcome

    return TradeOutcome(
        ticker="AAPL",
        signal_date=date(2025, 6, 2),
        triggered=triggered,
        trigger_date=date(2025, 6, 3) if triggered else None,
        entry_price=100.0 if triggered else None,
        exit_date=date(2025, 6, 10) if triggered else None,
        exit_price=95.0 if triggered else None,
        r_multiple=r_multiple,
        gap_through=gap_through,
        gap_magnitude_r=gap_magnitude_r,
        time_capped=time_capped,
    )


# ----------------------------------------------------------------------------


def test_aggregate_empty_outcomes_returns_zero_row():
    from research.harness.earnings_proximity.metrics import aggregate

    row = aggregate(outcomes=[], variant_name="baseline", blackout_trading_days=0,
                    absent_data_count=0)
    assert row.signal_count == 0
    assert row.traded_count == 0
    assert row.dropped_count == 0
    assert row.expectancy_r == pytest.approx(0.0)
    assert row.gap_through_rate == pytest.approx(0.0)
    assert row.gap_magnitude_mean_r == pytest.approx(0.0)
    assert row.gap_magnitude_max_r == pytest.approx(0.0)
    assert row.absent_data_count == 0


def test_aggregate_expectancy_mean_over_triggered_only():
    """Expectancy = mean R over triggered trades. Dropped signals don't count."""
    from research.harness.earnings_proximity.metrics import aggregate

    outcomes = [
        _outcome(triggered=True, r_multiple=2.0),
        _outcome(triggered=True, r_multiple=-1.0),
        _outcome(triggered=True, r_multiple=0.5),
        _outcome(triggered=False, r_multiple=None),  # dropped
    ]
    row = aggregate(outcomes=outcomes, variant_name="X=0", blackout_trading_days=0,
                    absent_data_count=0)
    # (2.0 + -1.0 + 0.5) / 3 = 0.5
    assert row.signal_count == 4
    assert row.traded_count == 3
    assert row.dropped_count == 1
    assert row.expectancy_r == pytest.approx(0.5)


def test_aggregate_gap_through_rate_over_losers_only():
    """Gap-through rate = frac of losing (R<0) trades that gapped. Winners
    and time-cap exits are not in the denominator."""
    from research.harness.earnings_proximity.metrics import aggregate

    outcomes = [
        _outcome(r_multiple=-1.0, gap_through=False),                     # clean stop
        _outcome(r_multiple=-1.5, gap_through=True, gap_magnitude_r=0.5), # gap
        _outcome(r_multiple=-2.0, gap_through=True, gap_magnitude_r=1.0), # gap
        _outcome(r_multiple=2.0),                                          # winner
    ]
    row = aggregate(outcomes=outcomes, variant_name="X=3", blackout_trading_days=3,
                    absent_data_count=0)
    # 2 gap-throughs out of 3 losers → 2/3 ≈ 0.667
    assert row.gap_through_rate == pytest.approx(2 / 3)
    # Gap magnitudes: mean of [0.5, 1.0] = 0.75, max = 1.0
    assert row.gap_magnitude_mean_r == pytest.approx(0.75)
    assert row.gap_magnitude_max_r == pytest.approx(1.0)


def test_aggregate_gap_through_rate_zero_when_no_losers():
    from research.harness.earnings_proximity.metrics import aggregate

    outcomes = [_outcome(r_multiple=1.5), _outcome(r_multiple=0.3)]
    row = aggregate(outcomes=outcomes, variant_name="X=5", blackout_trading_days=5,
                    absent_data_count=0)
    assert row.gap_through_rate == pytest.approx(0.0)
    assert row.gap_magnitude_mean_r == pytest.approx(0.0)


def test_aggregate_records_absent_data_count_passthrough():
    """The variant applicator decides which signals were absent-flagged and
    passes the count into the aggregator — metrics.aggregate doesn't recount."""
    from research.harness.earnings_proximity.metrics import aggregate

    row = aggregate(
        outcomes=[_outcome(r_multiple=0.5)],
        variant_name="X=7",
        blackout_trading_days=7,
        absent_data_count=3,
    )
    assert row.absent_data_count == 3


def test_aggregate_time_capped_exit_does_not_count_as_loser_for_gap_rate():
    """A time-capped exit with r=-0.2 (below 0, but not a stop-out) is a
    loser but was NOT stopped, so it is NOT in the gap-through denominator
    (which is stopped trades only)."""
    from research.harness.earnings_proximity.metrics import aggregate

    outcomes = [
        _outcome(r_multiple=-1.0, gap_through=False),  # stopped, clean
        _outcome(r_multiple=-0.2, time_capped=True),   # time-capped loser
    ]
    row = aggregate(outcomes=outcomes, variant_name="X=3", blackout_trading_days=3,
                    absent_data_count=0)
    # Stopped count = 1 (only the first); 0 gapped → 0/1 = 0.0
    assert row.gap_through_rate == pytest.approx(0.0)
