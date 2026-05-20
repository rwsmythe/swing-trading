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


# ---------------------------------------------------------------------------
# Fix #1 (code-quality follow-up) — NaN policy at function entry.
# ---------------------------------------------------------------------------


def test_volume_trend_through_swings_raises_valueerror_on_nan_volume() -> None:
    """``volume_trend_through_swings`` raises ValueError when bars['Volume']
    has NaN; silent propagation would yield NaN-poisoned avg_volume.
    """
    closes = [100.0, 105.0, 110.0, 115.0]
    volumes_float: list[float] = [100.0, float("nan"), 100.0, 100.0]
    idx = pd.DatetimeIndex(
        [date(2026, 1, 5) + timedelta(days=i) for i in range(len(closes))]
    )
    bars = pd.DataFrame(
        {"Close": closes, "High": closes, "Low": closes, "Volume": volumes_float},
        index=idx,
    )
    swings = [
        Swing(
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 8),
            start_price=100.0,
            end_price=115.0,
            direction="up",
            depth_pct=0.15,
            duration_days=3,
        )
    ]
    with pytest.raises(ValueError, match=r"volume_trend_through_swings:.*NaN"):
        volume_trend_through_swings(bars, swings)


def test_breakout_volume_ratio_raises_valueerror_on_nan_volume_in_baseline_window() -> None:
    """``breakout_volume_ratio`` raises ValueError when bars['Volume']
    has NaN within the baseline window preceding breakout_date.
    """
    closes = [100.0] * 60
    volumes: list[float] = [1000.0] * 60
    volumes[10] = float("nan")  # inside the baseline window [5..54]
    volumes[55] = 2000.0
    idx = pd.DatetimeIndex(
        [date(2026, 1, 5) + timedelta(days=i) for i in range(len(closes))]
    )
    bars = pd.DataFrame(
        {"Close": closes, "High": closes, "Low": closes, "Volume": volumes},
        index=idx,
    )
    breakout_dt = bars.index[55].date()
    with pytest.raises(ValueError, match=r"breakout_volume_ratio:.*NaN"):
        breakout_volume_ratio(bars, breakout_date=breakout_dt, baseline_days=50)


# ---------------------------------------------------------------------------
# Fix #8(b) (code-quality follow-up) — intraday-timestamp normalization.
# ---------------------------------------------------------------------------


def test_volume_trend_through_swings_handles_intraday_timestamps() -> None:
    """When bars.index carries non-midnight Timestamps (e.g., intraday
    ``2025-01-15 16:00:00``), the inclusive date-range slice must still
    pick up every bar in the swing window; previously the ``.loc[s:e]``
    inclusive slice could miss bars due to time-of-day mismatch.
    """
    # 4 bars with explicit 16:00 timestamps (post-close daily anchors).
    times = [
        pd.Timestamp("2025-01-15 16:00:00"),
        pd.Timestamp("2025-01-16 16:00:00"),
        pd.Timestamp("2025-01-17 16:00:00"),
        pd.Timestamp("2025-01-21 16:00:00"),
    ]
    bars = pd.DataFrame(
        {
            "Close": [100.0, 105.0, 110.0, 115.0],
            "High": [100.0, 105.0, 110.0, 115.0],
            "Low": [100.0, 105.0, 110.0, 115.0],
            "Volume": [100.0, 200.0, 300.0, 400.0],
        },
        index=pd.DatetimeIndex(times),
    )
    # Swing spanning the first 3 bars (date-level boundaries).
    swing = Swing(
        start_date=date(2025, 1, 15),
        end_date=date(2025, 1, 17),
        start_price=100.0,
        end_price=110.0,
        direction="up",
        depth_pct=0.10,
        duration_days=2,
    )
    out = volume_trend_through_swings(bars, [swing])
    assert len(out) == 1
    # Mean of [100, 200, 300] == 200.0 (4th bar excluded by date range).
    assert out[0].avg_volume == pytest.approx(200.0)
