"""Phase 13 T2.SB2 T-A.2.3 - discriminating tests for candidate-window generator.

Per plan section G.3 T-A.2.3 Step 1: 4 failing tests covering
``generate_candidate_windows`` per spec section 5.1.3 LOCK.
"""
from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import pandas as pd
import pytest

from swing.patterns.foundation import (
    CandidateWindow,
    generate_candidate_windows,
)


def _make_bars(closes: list[float], highs: list[float] | None = None,
               start: date = date(2026, 1, 5)) -> pd.DataFrame:
    if highs is None:
        highs = closes
    idx = pd.DatetimeIndex(
        [start + timedelta(days=i) for i in range(len(closes))]
    )
    return pd.DataFrame(
        {
            "Close": closes,
            "High": highs,
            "Low": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=idx,
    )


def test_zigzag_pivot_anchor_emits_windows_from_down_swing_endpoints() -> None:
    """``zigzag_pivot`` anchor mode produces windows starting from each
    down-swing's endpoint.
    """
    # Alternating swings: up to 115, down to 100, up to 115 again.
    closes = [
        100.0, 105.0, 110.0, 115.0,    # up
        110.0, 105.0, 100.0,           # down
        105.0, 110.0, 115.0, 120.0,    # up again
        115.0, 110.0, 105.0,           # down
    ]
    bars = _make_bars(closes)
    out = generate_candidate_windows(
        bars,
        anchor_search_method="zigzag_pivot",
        ticker="TEST",
        timeframe="daily",
    )
    # Should emit at least 1 window (down-swing endpoint anchor).
    assert len(out) >= 1
    for w in out:
        assert isinstance(w, CandidateWindow)
        assert w.anchor_reason.startswith("zigzag_pivot:swing_")
        assert "down" in w.anchor_reason
        assert w.ticker == "TEST"
        assert w.timeframe == "daily"


def test_ma_crossover_anchor_emits_window_at_50_above_150_crossover() -> None:
    """``ma_crossover`` anchor mode detects MA50 crossing above MA150 and
    emits exactly one window anchored at the crossover date.
    """
    # Build a long synthetic series where MA50 crosses MA150 exactly once.
    # Start low for 150 bars then ramp to push MA50 above MA150.
    pre = [100.0] * 150
    ramp = [100.0 + i * 2.0 for i in range(1, 81)]
    closes = pre + ramp
    bars = _make_bars(closes)
    out = generate_candidate_windows(
        bars,
        anchor_search_method="ma_crossover",
        ticker="TEST",
        timeframe="daily",
    )
    assert len(out) >= 1
    for w in out:
        assert w.anchor_reason.startswith("ma_crossover:")
        assert w.ticker == "TEST"


def test_high_low_breakout_anchor_emits_window_at_50d_high_breach() -> None:
    """``high_low_breakout`` anchor mode detects close > prior 50d high
    and emits a window anchored at the breach date.
    """
    # 50 bars at 100, then a breakout at index 51 with close=120.
    closes = [100.0] * 60 + [120.0] + [115.0] * 9
    highs = closes.copy()
    bars = _make_bars(closes, highs=highs)
    out = generate_candidate_windows(
        bars,
        anchor_search_method="high_low_breakout",
        ticker="TEST",
        timeframe="daily",
    )
    assert len(out) >= 1
    for w in out:
        assert w.anchor_reason.startswith("high_low_breakout:")
        assert w.ticker == "TEST"


def test_candidate_window_dataclass_shape_frozen_with_six_fields() -> None:
    """``CandidateWindow`` is frozen with exactly 6 fields; ``timeframe``
    validates against frozenset {'daily','weekly'} at __post_init__.
    """
    cw = CandidateWindow(
        ticker="AAPL",
        timeframe="daily",
        start_date=date(2026, 1, 5),
        end_date=date(2026, 3, 5),
        anchor_date=date(2026, 1, 5),
        anchor_reason="zigzag_pivot:swing_3_down",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        cw.ticker = "MSFT"  # type: ignore[misc]
    field_names = {f.name for f in dataclasses.fields(CandidateWindow)}
    assert field_names == {
        "ticker",
        "timeframe",
        "start_date",
        "end_date",
        "anchor_date",
        "anchor_reason",
    }
    # Bad timeframe raises (LOCK L4)
    with pytest.raises(ValueError):
        CandidateWindow(
            ticker="AAPL",
            timeframe="intraday",  # type: ignore[arg-type]
            start_date=date(2026, 1, 5),
            end_date=date(2026, 3, 5),
            anchor_date=date(2026, 1, 5),
            anchor_reason="zigzag_pivot:swing_3_down",
        )


# ---------------------------------------------------------------------------
# Fix #6 (code-quality follow-up) — _ts_to_date raises on bad input.
# ---------------------------------------------------------------------------


def test_generate_candidate_windows_raises_typeerror_on_non_timestamp_index() -> None:
    """``generate_candidate_windows`` raises TypeError via ``_ts_to_date``
    when bars carries an integer index (no ``.date()`` method, not a
    ``datetime.date`` instance).
    """
    closes = [100.0] * 60
    bars = pd.DataFrame(
        {
            "Close": closes,
            "High": closes,
            "Low": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=pd.RangeIndex(len(closes)),  # integer index, NOT timestamps
    )
    with pytest.raises(TypeError, match=r"_ts_to_date:.*expected"):
        generate_candidate_windows(
            bars,
            anchor_search_method="high_low_breakout",
            ticker="TEST",
            timeframe="daily",
        )
