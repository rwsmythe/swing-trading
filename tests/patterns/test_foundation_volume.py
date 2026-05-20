"""Phase 13 T2.SB2 T-A.2.4 - discriminating tests for volume primitives.

Per plan section G.3 T-A.2.4 Step 1: 3 failing tests covering
``volume_trend_through_swings`` + ``breakout_volume_ratio`` per
spec section 5.1.4 LOCK.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from swing.patterns.foundation import (
    Swing,
    VolumeSegment,
    breakout_volume_ratio,
    volume_trend_through_swings,
)


def _make_bars_with_volume(
    closes: list[float], volumes: list[int], start: date = date(2026, 1, 5)
) -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        [start + timedelta(days=i) for i in range(len(closes))]
    )
    return pd.DataFrame(
        {
            "Close": closes,
            "High": closes,
            "Low": closes,
            "Volume": volumes,
        },
        index=idx,
    )


def test_volume_trend_through_swings_emits_one_segment_per_swing_with_correct_avg() -> None:
    """Given 3 swings with distinct volume profiles, return 3 VolumeSegments
    each carrying the correct ``avg_volume`` for that swing window.
    """
    # Build 3 swings:
    # Days 0-3: closes go up (swing 1, vol avg = 100)
    # Days 4-7: closes go down (swing 2, vol avg = 200)
    # Days 8-11: closes go up (swing 3, vol avg = 300)
    bars = _make_bars_with_volume(
        closes=[100, 105, 110, 115, 110, 105, 100, 95, 100, 105, 110, 115],
        volumes=[100, 100, 100, 100, 200, 200, 200, 200, 300, 300, 300, 300],
    )
    start = date(2026, 1, 5)
    swings = [
        Swing(
            start_date=start + timedelta(days=0),
            end_date=start + timedelta(days=3),
            start_price=100.0,
            end_price=115.0,
            direction="up",
            depth_pct=0.15,
            duration_days=3,
        ),
        Swing(
            start_date=start + timedelta(days=4),
            end_date=start + timedelta(days=7),
            start_price=110.0,
            end_price=95.0,
            direction="down",
            depth_pct=0.1364,
            duration_days=3,
        ),
        Swing(
            start_date=start + timedelta(days=8),
            end_date=start + timedelta(days=11),
            start_price=100.0,
            end_price=115.0,
            direction="up",
            depth_pct=0.15,
            duration_days=3,
        ),
    ]
    out = volume_trend_through_swings(bars, swings)
    assert len(out) == 3
    for v in out:
        assert isinstance(v, VolumeSegment)
    assert out[0].avg_volume == pytest.approx(100.0)
    assert out[1].avg_volume == pytest.approx(200.0)
    assert out[2].avg_volume == pytest.approx(300.0)
    assert out[0].swing_index == 0
    assert out[2].swing_index == 2


def test_breakout_volume_ratio_returns_ratio_against_50d_prior_baseline() -> None:
    """``breakout_volume_ratio`` returns breakout-bar volume divided by the
    mean volume of the 50 bars STRICTLY BEFORE ``breakout_date``.
    """
    # 60 bars: first 60 have volume=1000, the breakout-day at index 55
    # carries volume=2000 -> ratio against 50d baseline at indices [5..54] = 1000.
    closes = [100.0] * 60
    volumes = [1000] * 60
    volumes[55] = 2000
    bars = _make_bars_with_volume(closes, volumes)
    breakout_dt = bars.index[55].date()
    ratio = breakout_volume_ratio(bars, breakout_date=breakout_dt, baseline_days=50)
    assert ratio == pytest.approx(2.0)


def test_breakout_volume_ratio_zero_baseline_returns_zero_no_raise() -> None:
    """Edge case: 50 prior bars all carry volume=0 -> return ``0.0``
    (NOT NaN; NOT raise ZeroDivisionError).
    """
    closes = [100.0] * 60
    volumes = [0] * 60
    volumes[55] = 5000  # non-zero breakout-bar volume
    bars = _make_bars_with_volume(closes, volumes)
    breakout_dt = bars.index[55].date()
    ratio = breakout_volume_ratio(bars, breakout_date=breakout_dt, baseline_days=50)
    assert ratio == 0.0
