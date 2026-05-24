"""Tests for the 3 exit rulesets + walk-forward entry logic.

Synthetic bar fixtures exercise each ruleset's stop-update + exit logic.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from research.harness.backtest_v2_tightness.patterns import Pattern
from research.harness.backtest_v2_tightness.rulesets import RulesetA, RulesetB, RulesetC
from research.harness.backtest_v2_tightness.walkforward import find_entry_index, walk_forward


def _make_bars(closes: list[float], *, start_date: str = "2026-05-01") -> pd.DataFrame:
    """Bars with Close=closes; Open=Close-0.1; High=Close+0.5; Low=Close-0.5; Volume=1000.

    Index = consecutive business days starting at start_date.
    """
    n = len(closes)
    dates = pd.bdate_range(start=start_date, periods=n)
    df = pd.DataFrame({
        "Open": [c - 0.1 for c in closes],
        "High": [c + 0.5 for c in closes],
        "Low": [c - 0.5 for c in closes],
        "Close": closes,
        "Volume": [1000.0] * n,
    }, index=dates)
    return df


def _pattern(pivot: float, stop: float, ticker: str = "TEST", asof: str = "2026-04-30") -> Pattern:
    return Pattern(
        pattern_id=f"{ticker}-r1",
        ticker=ticker,
        first_eval_run_id=1,
        first_data_asof_date=date.fromisoformat(asof),
        pivot=pivot,
        initial_stop=stop,
        eval_run_ids=(1,),
        asof_dates=(date.fromisoformat(asof),),
    )


# --------------------------------------------------------------------------
# Entry trigger
# --------------------------------------------------------------------------
def test_find_entry_index_returns_first_close_above_pivot() -> None:
    closes = [99.0, 100.5, 101.0, 102.0]
    bars = _make_bars(closes)
    # pivot=100; first close > 100 is index 1 (close=100.5)
    assert find_entry_index(bars, pivot=100.0) == 1


def test_find_entry_index_returns_none_when_no_next_session_after_trigger() -> None:
    closes = [99.0, 99.5, 100.5]
    bars = _make_bars(closes)
    # trigger at index 2 (close=100.5) but no next session for entry -> None
    assert find_entry_index(bars, pivot=100.0) is None


def test_walk_forward_untriggered_when_no_session_crosses_pivot() -> None:
    closes = [99.0, 99.0, 99.0, 99.0]
    bars = _make_bars(closes)
    p = _pattern(pivot=100.0, stop=95.0)
    trade = walk_forward(p, bars, RulesetA())
    assert trade.status == "untriggered"
    assert trade.exit_reason == "untriggered"
    assert trade.r_multiple is None


# --------------------------------------------------------------------------
# Ruleset A — Minervini trail-MA
# --------------------------------------------------------------------------
def test_ruleset_a_stop_hit_at_initial_stop() -> None:
    # pivot=100, entry at index 1 open (~100.4), stop=95
    # trade then drops; Low <= 95 should fire stop_hit at 95.
    closes = [99.5, 100.5, 99.0, 95.0]  # entry @ index 1 open
    bars = _make_bars(closes)
    p = _pattern(pivot=100.0, stop=95.0)
    trade = walk_forward(p, bars, RulesetA())
    assert trade.status == "closed"
    assert trade.exit_reason == "stop_hit"
    assert trade.exit_price == 95.0
    assert trade.r_multiple is not None
    # entry_price ~ 100.4 (close 100.5 - 0.1); R ~ 5.4
    assert trade.r_multiple < 0  # losing trade


def test_ruleset_a_trail_arms_at_2R_extension_then_close_below_50d_exits() -> None:
    # Build 60 bars rising linearly to >+2R then crossing 50d on close.
    # Initial stop=95, pivot=100, entry @ index 1.
    closes = [99.5, 100.5]  # entry trigger + entry
    # Push high enough for +2R extension: entry ~100.4, R~5.4, +2R = ~111.2
    closes += [100.0 + i * 0.5 for i in range(1, 60)]  # rises smoothly
    # Then a sudden drop to trigger close-below-50d.
    closes += [80.0] * 10  # crash below 50d SMA
    bars = _make_bars(closes)
    p = _pattern(pivot=100.0, stop=95.0)
    trade = walk_forward(p, bars, RulesetA())
    assert trade.status == "closed"
    # Should exit either via trail_stop (intraday hit on rising stop) or close_below_50d
    assert trade.exit_reason in ("trail_stop", "close_below_50d")


# --------------------------------------------------------------------------
# Ruleset B — Fixed R-multiple
# --------------------------------------------------------------------------
def test_ruleset_b_target_3R_fires() -> None:
    # Trigger at idx 1 (close=100.5 > pivot=100). Entry at idx 2 open.
    # Make entry_idx = 2, entry close = 100.5 -> entry_open = 100.4.
    # Stop = 95, R = 5.4, +3R target ~116.6.
    closes = [99.0, 100.2, 100.5, 105.0, 110.0, 120.0, 121.0]
    bars = _make_bars(closes)
    p = _pattern(pivot=100.0, stop=95.0)
    trade = walk_forward(p, bars, RulesetB())
    assert trade.status == "closed"
    assert trade.exit_reason == "target_3R"
    # entry was bar 2 open = 100.5 - 0.1 = 100.4; R = 5.4; target = 116.6
    assert abs(trade.exit_price - 116.6) < 0.1
    assert trade.r_multiple is not None
    assert abs(trade.r_multiple - 3.0) < 0.01


def test_ruleset_b_stop_hit_before_BE() -> None:
    closes = [99.0, 100.5, 98.0, 94.0]
    bars = _make_bars(closes)
    p = _pattern(pivot=100.0, stop=95.0)
    trade = walk_forward(p, bars, RulesetB())
    assert trade.exit_reason == "stop_hit"
    assert trade.r_multiple < 0


def test_ruleset_b_breakeven_arms_at_1R_protects_against_loss() -> None:
    # Trigger at idx 1, entry at idx 2 open. Entry close=100.5 -> entry_open=100.4.
    # Stop=95, R=5.4, +1R = 105.8. After bar 3 (high 107.0 >= 105.8) BE arms.
    # Bar 4: Low=99.5 <= 100.4 -> trail_stop fires at 100.4.
    closes = [99.0, 100.2, 100.5, 106.5, 100.0, 99.5]
    bars = _make_bars(closes)
    p = _pattern(pivot=100.0, stop=95.0)
    trade = walk_forward(p, bars, RulesetB())
    assert trade.status == "closed"
    assert trade.exit_reason == "trail_stop"
    assert abs(trade.r_multiple) < 0.01


# --------------------------------------------------------------------------
# Ruleset C — Close-below-50d-SMA
# --------------------------------------------------------------------------
def test_ruleset_c_stop_hit_before_50d_arm() -> None:
    closes = [99.0, 100.5, 98.0, 94.0]
    bars = _make_bars(closes)
    p = _pattern(pivot=100.0, stop=95.0)
    trade = walk_forward(p, bars, RulesetC())
    assert trade.exit_reason == "stop_hit"


def test_ruleset_c_close_below_50d_after_arm() -> None:
    # 60+ bars: rising for first 55 (so 50d SMA is rising AND close > 50d), then crash.
    closes = [99.0, 100.5]  # trigger + entry
    closes += [100.0 + i * 0.2 for i in range(1, 60)]  # rising
    closes += [80.0] * 10  # crash
    bars = _make_bars(closes)
    p = _pattern(pivot=100.0, stop=95.0)
    trade = walk_forward(p, bars, RulesetC())
    assert trade.status == "closed"
    # Either trail_stop (intraday low <= 50d trail) or close_below_50d.
    assert trade.exit_reason in ("close_below_50d", "trail_stop")


# --------------------------------------------------------------------------
# Open-position handling
# --------------------------------------------------------------------------
def test_walk_forward_open_position_at_data_tail() -> None:
    # Enter and rise gently; never trigger any exit before data tail.
    closes = [99.0, 100.5, 101.0, 101.5, 102.0]
    bars = _make_bars(closes)
    p = _pattern(pivot=100.0, stop=95.0)
    trade = walk_forward(p, bars, RulesetA())
    assert trade.status == "open"
    assert trade.exit_reason == "open_at_data_tail"
    assert trade.r_multiple is not None
    assert trade.r_multiple > 0  # winning open
