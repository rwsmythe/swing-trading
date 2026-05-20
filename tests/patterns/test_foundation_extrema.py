"""Phase 13 T2.SB2 T-A.2.2 - discriminating tests for zigzag extrema.

Per plan section G.3 T-A.2.2 Step 1: 5 failing tests covering
``extract_zigzag_swings`` with adaptive threshold per spec section 5.1.2 LOCK.
"""
from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

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
    """Clean alternating swing decomposition with deterministic close path
    (Fix #5: STRENGTHENED — assert exact swing count, directions, depth_pct).

    Synthesized path with sharp ~10% reversals at 3% static threshold yields
    a deterministic 2-swing zigzag: up 100->110 then down 110->99.

    The intervening 102/105/103 micro-fluctuations between bars 0..4 do NOT
    open a new swing because they never violate the 3% counter-move from
    the running extremum. The detector only opens an up-swing once price
    moves >= 3% above the initial pivot — that first happens at bar 2
    (close=105, +5% from 100). The extremum then climbs to 110 at bar 5;
    the move to 99 at bar 8 is a 10% counter-move closing the up-swing
    100->110 and opening a down-swing. The down-swing closes when the
    counter-move from 99 reaches 3% — at bar 11 (close=110, +11% from 99).
    The final up-swing 99->110 is currently-developing past bar 11 (110
    is the running extremum; no counter-move emitted) so per the
    "do-not-emit-developing-swing" contract it is NOT returned.
    """
    import pytest

    closes = [
        100.0,  # bar 0: pivot
        102.0,  # bar 1: +2% from pivot (below 3% — still anchoring)
        105.0,  # bar 2: +5% from pivot — opens up-swing; extremum=105
        103.0,  # bar 3: counter -1.9% from extremum (below 3%; no close)
        104.0,  # bar 4: still within tolerance
        110.0,  # bar 5: new extremum=110
        108.0,  # bar 6: counter -1.8% (below 3%)
        103.0,  # bar 7: counter -6.4% (>= 3%; CLOSES up-swing 100->110;
                #                       opens down-swing; extremum=103)
        99.0,   # bar 8: new low extremum=99
        102.0,  # bar 9: counter +3.0% (>= 3%; CLOSES down-swing 110->99;
                #                       opens up-swing; extremum=102)
        106.0,  # bar 10: new up extremum=106 (developing)
        110.0,  # bar 11: new up extremum=110 (developing)
    ]
    bars = _make_bars(closes)
    out = extract_zigzag_swings(
        bars, initial_threshold_pct=3.0, monotonic_narrow=False
    )
    # Exact count: 2 closed swings (the final developing up-swing is NOT
    # emitted per the historical-only contract).
    assert len(out) == 2
    # Exact direction sequence.
    assert [s.direction for s in out] == ["up", "down"]
    # Exact endpoint prices.
    assert out[0].start_price == pytest.approx(100.0)
    assert out[0].end_price == pytest.approx(110.0)
    assert out[1].start_price == pytest.approx(110.0)
    assert out[1].end_price == pytest.approx(99.0)
    # Approximate depth_pct values (unsigned per spec).
    assert out[0].depth_pct == pytest.approx(0.10, abs=1e-6)
    assert out[1].depth_pct == pytest.approx(0.10, abs=1e-3)
    # Field shape invariants preserved.
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


# ---------------------------------------------------------------------------
# Fix #1 (code-quality follow-up) — NaN policy at function entry.
# ---------------------------------------------------------------------------


def test_extract_zigzag_swings_raises_valueerror_on_nan_close() -> None:
    """``extract_zigzag_swings`` raises ValueError when bars['Close'] has
    NaN; holiday-adjacent rows from real archives must be dropped/imputed
    before invocation rather than silently producing degraded swings.
    """
    import pytest

    closes_with_nan = [100.0, 102.0, float("nan"), 104.0, 110.0, 100.0, 103.0]
    bars = _make_bars(closes_with_nan)
    with pytest.raises(ValueError, match=r"extract_zigzag_swings:.*NaN"):
        extract_zigzag_swings(bars, initial_threshold_pct=3.0)


# ---------------------------------------------------------------------------
# Fix #4 (code-quality follow-up) — monotonic_narrow threshold floor.
# ---------------------------------------------------------------------------


def test_zigzag_monotonic_narrow_threshold_floor_prevents_zero_threshold() -> None:
    """Under ``monotonic_narrow=True`` on a long alternating ~+/-1% sequence,
    without a floor on threshold-decay the effective threshold would
    approach zero and the zigzag would emit a swing for every bar's noise.
    With the floor (0.5% per the module constant) the threshold cannot
    decay below the floor and the swing count stays bounded.
    """
    # Build 60 bars alternating exactly +1% / -1% — well below the 3.0%
    # initial threshold so the FIRST swing never even opens at static-3.0.
    # Under monotonic_narrow the floor at 0.5% means a +/-1% move can be
    # caught only after the decay sequence stalls at the floor — but the
    # algorithm needs an OPENING swing first, which never crosses 3%, so
    # the threshold never decays past 3.0%.
    # To exercise the floor we need the threshold to actually decay; we
    # synthesize a path that opens a 3%+ swing then a series of <=1% moves.
    closes = [100.0, 100.5, 101.0, 101.5, 103.5]  # bar 4 opens up-swing
    # Then long alternation of +/-1% from 102 base.
    for i in range(60):
        if i % 2 == 0:
            closes.append(101.0)
        else:
            closes.append(103.0)
    bars = _make_bars(closes)
    out = extract_zigzag_swings(
        bars, initial_threshold_pct=3.0, monotonic_narrow=True
    )
    # Without a floor on threshold-decay the zigzag could emit dozens of
    # swings. With the 0.5% floor, the threshold caps the swing count.
    # Reasonable upper bound: well under 20 (each swing requires a 0.5%+
    # counter-move from the running extremum).
    assert len(out) <= 20
    # Result is finite (no infinite loop / unbounded output).
    assert isinstance(out, list)


# ---------------------------------------------------------------------------
# Codex R1 Minor #3 - adaptive_initial_threshold_pct NaN-rejection policy.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nan_column", ["Close", "High", "Low"])
def test_adaptive_initial_threshold_pct_raises_on_nan_in_required_column(
    nan_column: str,
) -> None:
    """Codex R1 Minor #3 + R2 Minor #3: ``adaptive_initial_threshold_pct``
    must reject NaN in any of Close/High/Low (the 3 columns it reads)
    consistently with the rest of the primitives' NaN policy.

    The function reads only the last 5 bars (the ATR-5d tail) so the NaN
    must land within indices [-5:] to exercise the check.
    """
    idx = pd.date_range("2025-01-02", periods=10, freq="B")
    base_close = np.full(10, 100.0)
    base_high = np.full(10, 101.0)
    base_low = np.full(10, 99.0)
    columns = {
        "Open": base_close,
        "High": base_high,
        "Low": base_low,
        "Close": base_close,
        "Volume": np.full(10, 1_000_000),
    }
    # Inject NaN in the tail (last 5 bars - the window
    # adaptive_initial_threshold_pct reads).
    columns[nan_column] = columns[nan_column].copy()
    columns[nan_column][7] = np.nan  # tail bar
    bars = pd.DataFrame(columns, index=idx)
    with pytest.raises(
        ValueError,
        match=rf"adaptive_initial_threshold_pct.*{nan_column}",
    ):
        adaptive_initial_threshold_pct(bars)
