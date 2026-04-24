"""Metrics aggregator for the earnings-proximity replay.

Emits one :class:`MetricsRow` per variant. Downstream Session 2c
composes a comparison table across variants.

Definitions
-----------
- **signal_count** — number of A+ signals fed in (includes never-triggered).
- **traded_count** — signals that triggered (one trade each).
- **dropped_count** — signals that never triggered within the time-cap window.
- **absent_data_count** — A+ signals flagged as having no earnings data
  available (per method record: flag for review, do NOT exclude).
- **expectancy_r** — mean R-multiple across triggered trades. 0.0 when no trades.
- **gap_through_rate** — fraction of STOPPED (R < 0) trades that gapped through
  the stop (fill at open below stop). 0.0 when no stopped trades. Time-capped
  losers are NOT in the denominator — they were not stopped.
- **gap_magnitude_mean_r** — mean of ``gap_magnitude_r`` across gap-through
  trades. 0.0 if none.
- **gap_magnitude_max_r** — max of ``gap_magnitude_r`` across gap-through
  trades. 0.0 if none.
"""
from __future__ import annotations

from dataclasses import dataclass

from research.harness.earnings_proximity.simulator import TradeOutcome


@dataclass(frozen=True)
class MetricsRow:
    variant_name: str
    blackout_trading_days: int
    signal_count: int
    traded_count: int
    dropped_count: int
    absent_data_count: int
    expectancy_r: float
    gap_through_rate: float
    gap_magnitude_mean_r: float
    gap_magnitude_max_r: float


def aggregate(
    *,
    outcomes: list[TradeOutcome],
    variant_name: str,
    blackout_trading_days: int,
    absent_data_count: int,
) -> MetricsRow:
    """Reduce per-signal outcomes to a single metrics row."""
    signal_count = len(outcomes)
    triggered = [o for o in outcomes if o.triggered and o.r_multiple is not None]
    traded_count = len(triggered)
    dropped_count = signal_count - traded_count

    expectancy = (
        sum(o.r_multiple for o in triggered) / traded_count if triggered else 0.0
    )

    # Gap-through denominator: stopped (R < 0, not time-capped) trades.
    stopped = [o for o in triggered if (o.r_multiple or 0.0) < 0 and not o.time_capped]
    gapped = [o for o in stopped if o.gap_through]
    gap_through_rate = (len(gapped) / len(stopped)) if stopped else 0.0

    gap_mags = [
        o.gap_magnitude_r for o in gapped if o.gap_magnitude_r is not None
    ]
    gap_mag_mean = (sum(gap_mags) / len(gap_mags)) if gap_mags else 0.0
    gap_mag_max = max(gap_mags) if gap_mags else 0.0

    return MetricsRow(
        variant_name=variant_name,
        blackout_trading_days=blackout_trading_days,
        signal_count=signal_count,
        traded_count=traded_count,
        dropped_count=dropped_count,
        absent_data_count=absent_data_count,
        expectancy_r=float(expectancy),
        gap_through_rate=float(gap_through_rate),
        gap_magnitude_mean_r=float(gap_mag_mean),
        gap_magnitude_max_r=float(gap_mag_max),
    )
