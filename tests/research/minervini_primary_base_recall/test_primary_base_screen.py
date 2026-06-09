from __future__ import annotations

from datetime import date

import pandas as pd

from research.harness.minervini_primary_base_recall.primary_base_screen import screen_at


def _frame(closes: list[float], start: date = date(2010, 1, 4)) -> pd.DataFrame:
    """Build a clean business-day OHLCV frame from a Close list (the shape read_full emits)."""
    idx = pd.bdate_range(start=start, periods=len(closes))
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame(
        {"Open": c, "High": c * 1.001, "Low": c * 0.999, "Close": c, "Volume": 1_000_000.0},
        index=idx,
    )


def test_history_gate_rejects_short_slice():
    # 30 bars < MIN_HISTORY_BARS (40). WRONG-PATH (no history gate) would attempt base-id and
    # likely return no_base; RIGHT-PATH returns first_rejecting_criterion == "history".
    bars = _frame([10.0 + i * 0.01 for i in range(30)])
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "history"


def test_no_base_when_pure_uptrend_no_downswing():
    # Monotone rise: extract_zigzag_swings emits at most one developing up-swing (never closed by a
    # down-swing). WRONG-PATH (treat any high as base_high) fires; RIGHT-PATH -> "no_base".
    bars = _frame([10.0 + i * 0.05 for i in range(60)])
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "no_base"


def test_depth_gate_rejects_too_deep_correction():
    # A 50-bar history: rise to a peak (~100), then a >25% drop and a long sideways base (so
    # duration passes, depth fails for a <=25-bar... use a SHORT base so cap=0.25 and depth ~0.40).
    # Construct: 18 bars rising 80->100 (peak at pos 17), then 20 bars dropping to 60 and flat at
    # ~62 (depth = (100-60)/100 = 0.40 > 0.25 cap for the >=15-bar but <=25-bar duration).
    rise = [80.0 + (100.0 - 80.0) * i / 17 for i in range(18)]          # peak 100 at idx 17
    drop = [100.0 - (100.0 - 60.0) * (i + 1) / 4 for i in range(4)]     # quick drop to 60
    flat = [61.0, 60.5, 62.0, 61.5, 60.0, 61.0, 60.5, 62.0, 61.5, 60.0, 61.0, 60.5, 62.0, 61.5]
    bars = _frame(rise + drop + flat)  # 18 + 4 + 14 = 36 bars... pad history below
    # Pad 10 quiet leading bars so len >= 40 (history passes) and the peak stays the global high.
    pad = _frame([55.0] * 10, start=date(2009, 11, 2))
    bars = pd.concat([pad, bars])
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "depth"
    assert v.correction_depth_pct is not None and v.correction_depth_pct > 0.25


def test_duration_gate_rejects_too_short_base():
    # A clean peak then only a 10-bar correction-to-asof (< MIN_BASE_BARS=15) -> "duration".
    pad = [50.0] * 40
    rise = [60.0 + (90.0 - 60.0) * i / 9 for i in range(10)]   # peak 90 at end of rise
    short = [88.0, 86.0, 84.0, 85.0, 86.0, 87.0, 88.0, 89.0, 88.5, 87.0]  # 10-bar base
    bars = _frame(pad + rise + short)
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "duration"


def test_calendar_to_bar_mapping_uses_bars_not_calendar_days():
    # Plant a base whose CALENDAR span (Swing.duration_days) >= 21 but whose BAR count is < 15,
    # by inserting weekend/holiday gaps. bdate_range already excludes weekends, so 14 business days
    # span ~20 calendar days. We assert the duration gate uses the 14-bar count (-> "duration"),
    # NOT the ~20 calendar days (which a WRONG-PATH duration_days check would pass).
    pad = [50.0] * 40
    rise = [60.0 + (90.0 - 60.0) * i / 9 for i in range(10)]   # peak 90
    base14 = [88.0, 86.0, 84.0, 85.0, 86.0, 87.0, 88.0, 89.0, 88.5, 87.0, 86.5, 88.0, 89.0, 88.0]
    bars = _frame(pad + rise + base14)   # base = 14 BARS after the peak
    asof = bars.index[-1].date()
    v = screen_at(bars, asof)
    # base_duration_bars == 14 (bars), so it fails MIN_BASE_BARS=15 with "duration".
    # WRONG-PATH (Swing.duration_days, ~20 calendar days) would PASS duration and move on.
    assert v.first_rejecting_criterion == "duration"
    assert v.base_duration_bars == 14
