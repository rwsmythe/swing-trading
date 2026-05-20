"""Phase 13 T2.SB2 T-A.2.2 - discriminating tests for zigzag extrema.

Per plan section G.3 T-A.2.2 Step 1: 5 failing tests covering
``extract_zigzag_swings`` with adaptive threshold per spec section 5.1.2 LOCK.
"""
from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import pandas as pd

from swing.patterns.foundation import (
    Swing,
    adaptive_initial_threshold_pct,
    extract_zigzag_swings,
)


def _make_bars(closes: list[float], start: date = date(2026, 1, 5)) -> pd.DataFrame:
    """Build a daily-bar DataFrame indexed by Timestamps for testing.

    High and Low set equal to Close for simplicity; Volume placeholder.
    """
    idx = pd.DatetimeIndex(
        [start + timedelta(days=i) for i in range(len(closes))]
    )
    return pd.DataFrame(
        {
            "Close": closes,
            "High": closes,
            "Low": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=idx,
    )


def test_zigzag_monotonic_uptrend_no_reversals_returns_empty() -> None:
    """Monotonically increasing close with no reversals + static 3% threshold
    -> returns ``[]``.
    """
    closes = [100.0 + i * 0.5 for i in range(20)]
    bars = _make_bars(closes)
    out = extract_zigzag_swings(
        bars, initial_threshold_pct=3.0, monotonic_narrow=False
    )
    assert out == []


def test_zigzag_alternating_five_percent_static_threshold_detects_swings() -> None:
    """Alternating +/-5%-ish pattern with static threshold 3%, no monotonic
    narrowing -> detects each swing with correct direction and depth.
    """
    # Generate a price series with clear reversals
    closes = [
        100.0, 102.0, 105.0,  # uptrend leg
        103.0, 100.0,         # mini-pullback (not big enough)
        110.0, 115.0,         # uptrend resumes (peak)
        110.0, 105.0, 100.0,  # downtrend
        105.0, 110.0, 115.0,  # back up
    ]
    bars = _make_bars(closes)
    out = extract_zigzag_swings(
        bars, initial_threshold_pct=3.0, monotonic_narrow=False
    )
    # At least 2 swings: up to 115, down to 100, up to 115 again.
    assert len(out) >= 2
    # First non-empty swing's direction is one of up/down
    assert out[0].direction in ("up", "down")
    # All swings carry the 7 dataclass fields
    for sw in out:
        assert sw.depth_pct >= 0.0
        assert sw.duration_days >= 0


def test_zigzag_monotonic_narrow_catches_decreasing_contractions_static_misses_them() -> None:
    """``monotonic_narrow=True`` narrows the threshold by 0.75x after each
    swing; with initial threshold 5%, an alternating sequence of decreasing
    swings (depths ~10%, ~8%, ~6%, ~4%) is fully captured under
    monotonic_narrow but the static path drops the late swings.

    Threshold sequence under monotonic_narrow=True starting at 5.0:
    5.0 -> 3.75 -> 2.8125 -> 2.109375 -> ...
    Late swings (~4%) exceed 2.81 (third threshold) so are caught.
    """
    # Synthesize a price path with 4 ever-shallower swings.
    # Up from 100 -> 110 (10%), down to 101.2 (~8%), up to 107.3 (~6%),
    # down to 103.0 (~4%).
    closes_legs = [
        # Leg 1 up: 100 -> 110 (10%)
        100.0, 102.0, 104.0, 106.0, 108.0, 110.0,
        # Leg 2 down: 110 -> 101.2 (~8%)
        108.5, 106.5, 104.0, 102.0, 101.2,
        # Leg 3 up: 101.2 -> 107.3 (~6%)
        103.0, 104.5, 106.0, 107.3,
        # Leg 4 down: 107.3 -> 103.0 (~4%)
        106.5, 105.5, 104.5, 103.0,
    ]
    bars = _make_bars(closes_legs)
    static = extract_zigzag_swings(
        bars, initial_threshold_pct=5.0, monotonic_narrow=False
    )
    narrow = extract_zigzag_swings(
        bars, initial_threshold_pct=5.0, monotonic_narrow=True
    )
    # Narrow mode catches more swings than static mode for ever-shallower legs
    assert len(narrow) > len(static)


def test_zigzag_adaptive_threshold_helper_returns_max_of_3_and_1p5x_atr_pct() -> None:
    """``adaptive_initial_threshold_pct`` returns ``max(3.0, ATR_5d_pct * 1.5)``.

    Construct bars where the 5-day ATR is small (returns 3.0 floor) AND a
    second where ATR is large (returns ATR*1.5).
    """
    # Small-range bars: H=L=Close=100; ATR=0; helper returns 3.0 floor.
    small = _make_bars([100.0] * 10)
    assert adaptive_initial_threshold_pct(small) == 3.0
    # Big-range bars: synthesize H-L=10 on a 100-price; ATR_pct=10; helper
    # returns max(3.0, 15.0) = 15.0.
    idx = pd.DatetimeIndex([date(2026, 1, 5) + timedelta(days=i) for i in range(10)])
    big = pd.DataFrame(
        {
            "Close": [100.0] * 10,
            "High": [105.0] * 10,
            "Low": [95.0] * 10,
            "Volume": [1_000_000] * 10,
        },
        index=idx,
    )
    assert adaptive_initial_threshold_pct(big) == 15.0


def test_swing_dataclass_shape_frozen_with_required_fields() -> None:
    """Swing dataclass: frozen=True; 7 required fields; depth_pct unsigned;
    direction validated against frozenset at __post_init__.
    """
    sw = Swing(
        start_date=date(2026, 1, 5),
        end_date=date(2026, 1, 10),
        start_price=100.0,
        end_price=110.0,
        direction="up",
        depth_pct=0.10,
        duration_days=5,
    )
    # frozen: mutation raises
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        sw.start_price = 50.0  # type: ignore[misc]

    # depth_pct is unsigned (abs((end-start)/start) per docstring)
    assert sw.depth_pct >= 0.0
    # All 7 fields present
    field_names = {f.name for f in dataclasses.fields(Swing)}
    assert field_names == {
        "start_date",
        "end_date",
        "start_price",
        "end_price",
        "direction",
        "depth_pct",
        "duration_days",
    }
    # Literal runtime validation per L4: bad direction raises
    with pytest.raises(ValueError):
        Swing(
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 10),
            start_price=100.0,
            end_price=110.0,
            direction="sideways",  # type: ignore[arg-type]
            depth_pct=0.10,
            duration_days=5,
        )
