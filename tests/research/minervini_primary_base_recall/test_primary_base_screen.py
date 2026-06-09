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


def test_fires_on_fresh_cross_first_base():
    # A clean primary base that freshly crosses base_high at asof -> FIRES.
    pad = [40.0] * 40
    rise = [50.0 + (100.0 - 50.0) * i / 9 for i in range(10)]   # peak 100
    base = [92.0, 88.0, 90.0, 89.0, 91.0, 93.0, 90.0, 92.0, 94.0, 91.0,
            93.0, 95.0, 92.0, 94.0, 96.0, 95.0]                 # >=15-bar base, depth ~12% (<0.35)
    cross = [99.0, 101.0]   # close[-2]=99 (<=100), close[-1]=101 (>100): fresh cross
    bars = _frame(pad + rise + base + cross)
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is True
    assert v.first_rejecting_criterion is None
    assert v.emergence_close is not None and v.emergence_close > v.base_high


def test_already_above_base_high_is_no_emergence_not_a_state():
    # asof close is above base_high but so was the PRIOR close (no fresh cross at asof).
    pad = [40.0] * 40
    rise = [50.0 + (100.0 - 50.0) * i / 9 for i in range(10)]   # peak 100
    base = [92.0, 88.0, 90.0, 89.0, 91.0, 93.0, 90.0, 92.0, 94.0, 91.0,
            93.0, 95.0, 92.0, 94.0, 96.0, 95.0]
    above = [101.0, 103.0]  # close[-2]=101 already > 100 -> NOT a fresh cross at asof
    bars = _frame(pad + rise + base + above)
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "no_emergence"


def test_failed_breakout_then_reset_recross_does_not_fire():
    # THE first-cross-not-recross discriminator (R1.M6). base_high is the clean CLOSED pivot 101.
    # An earlier close (102 at asof-2) pokes ABOVE 101 inside the DEVELOPING final up-leg (which
    # never closes -> it is NOT a new pivot, so base_high stays 101), then asof-1 dips to 100.5
    # (a <3% pullback, so the leg stays developing), then asof closes 102.5 (a fresh cross of 101).
    # The second clause max(close[base_start:asof]) <= base_high is THE discriminator: 102 > 101
    # already happened inside the base -> this is a recross, not a first emergence.
    # WRONG-PATH (bare one-bar recross close[asof-1] <= base_high < close[asof]): 100.5 <= 101 <
    #   102.5 -> FIRES wrongly. RIGHT-PATH -> "no_emergence".
    # NOTE: criterion 5 is evaluated BEFORE criterion 6 in screen_at; since 1-5 fail at asof
    # (no_emergence), the first-fire replay is never reached -> the result is no_emergence (not
    # not_primary), even though an earlier session (asof-2) would itself fire 1-5.
    pad = [40.0] * 40
    # closed up-swing, peak 101 @ pos 51:
    rise = [50.0 + (101.0 - 50.0) * i / 11 for i in range(12)]
    drop = [99.0, 97.0, 95.0, 96.0, 95.0, 96.0, 95.0, 96.0]   # -3.96% at 97 closes up-swing; low 95
    # Developing recovery up-leg from the 95 low: monotone up to 102 (asof-2), small dip to 100.5
    # (asof-1, -1.5% -> leg keeps developing), then 102.5 (asof). It never reverses >=3% so it is
    # NOT emitted as a closed swing -> no new pivot above 101 -> base_high stays 101. base_start at
    # pos 51, asof at pos 67 -> base_duration_bars = 16 (>= MIN_BASE_BARS, so duration passes and we
    # reach the emergence check).
    recovery = [97.0, 98.0, 99.0, 100.0, 101.0, 102.0, 100.5, 102.5]
    bars = _frame(pad + rise + drop + recovery)
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "no_emergence"
    assert v.base_high is not None and abs(v.base_high - 101.0) < 0.5  # pivot, NOT the 102 poke


def test_second_base_after_an_earlier_qualifying_base_is_not_primary():
    # Two complete primary-base emergences in one history; screening at the SECOND emergence must
    # return not_primary (criteria 1-5 fired earlier at the first emergence).
    # WRONG-PATH (no first-fire replay) FIRES at the second base; RIGHT-PATH -> "not_primary".
    pad = [40.0] * 40
    # First base + emergence (peak 100, base, fresh cross to 101) ...
    rise1 = [50.0 + (100.0 - 50.0) * i / 9 for i in range(10)]
    base1 = [
        92.0, 88.0, 90.0, 91.0, 93.0, 90.0, 92.0, 94.0, 91.0, 93.0, 95.0, 92.0, 94.0, 96.0, 95.0,
    ]
    cross1 = [99.0, 101.0]
    # ... then a deeper pullback forming a SECOND base (new peak 130) + fresh cross to 131.
    rise2 = [102.0 + (130.0 - 102.0) * i / 9 for i in range(10)]
    base2 = [
        120.0, 116.0, 118.0, 119.0, 121.0, 118.0, 120.0, 122.0, 119.0, 121.0, 123.0, 120.0,
        122.0, 124.0, 123.0,
    ]
    cross2 = [129.0, 131.0]
    bars = _frame(pad + rise1 + base1 + cross1 + rise2 + base2 + cross2)
    # Screen at the FINAL session (the second emergence).
    v = screen_at(bars, bars.index[-1].date())
    assert v.fired is False
    assert v.first_rejecting_criterion == "not_primary"
    # Sanity: screening at the FIRST emergence DOES fire (it is the primary).
    first_emergence_date = bars.index[40 + 10 + 15 + 2 - 1].date()  # last bar of cross1
    v1 = screen_at(bars, first_emergence_date)
    assert v1.fired is True
