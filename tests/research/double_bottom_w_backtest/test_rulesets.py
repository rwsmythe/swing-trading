"""Tests for the 3 exit rulesets via walk_forward.

Synthetic bar fixtures exercise each ruleset's stop-update + exit logic. All
exits are CLOSE-based (no intraday Low/High triggers) per dispatch brief Section 3.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.double_bottom_w_backtest.rulesets import (
    RulesetA,
    RulesetB,
    RulesetC,
    _atr_at,
    _sma_at,
    all_rulesets,
)
from research.harness.double_bottom_w_backtest.walkforward import walk_forward


def _verdict(
    *,
    asof: str = "2026-05-01",
    trough_2_price: float = 95.0,
    center_peak_price: float = 100.0,
) -> PrimaryVerdict:
    return PrimaryVerdict(
        ticker="ABC",
        anchor_asof_date=date.fromisoformat(asof),
        trough_1_date=date(2026, 4, 1),
        trough_1_price=trough_2_price + 1.0,
        center_peak_date=date(2026, 4, 6),
        center_peak_price=center_peak_price,
        trough_2_date=date(2026, 4, 20),
        trough_2_price=trough_2_price,
        pivot_price=99.0,
        composite_score=0.85,
        geometric_score=0.85,
        template_match_score=None,
    )


def _bars(closes: list[float], *, start_date: str = "2026-04-25") -> pd.DataFrame:
    """Synthetic OHLCV with Open=Close-0.1; High=Close+0.5; Low=Close-0.5."""
    idx = pd.bdate_range(start=start_date, periods=len(closes))
    return pd.DataFrame(
        {
            "Open": [c - 0.1 for c in closes],
            "High": [c + 0.5 for c in closes],
            "Low": [c - 0.5 for c in closes],
            "Close": closes,
            "Volume": [1000.0] * len(closes),
        },
        index=idx,
    )


# ---- SMA + ATR helpers --------------------------------------------------


def test_sma_at_returns_none_when_insufficient_bars() -> None:
    bars = _bars([100.0, 101.0])
    assert _sma_at(bars, bar_idx=1, window=50) is None


def test_sma_at_computes_mean_over_window() -> None:
    bars = _bars([100.0, 102.0, 104.0])  # 3 bars; SMA3 at idx 2 = mean(100,102,104)=102
    assert _sma_at(bars, bar_idx=2, window=3) == pytest.approx(102.0)


def test_atr_at_returns_none_when_insufficient_bars() -> None:
    bars = _bars([100.0])
    assert _atr_at(bars, bar_idx=0, window=14) is None


def test_atr_at_returns_finite_with_enough_bars() -> None:
    bars = _bars([100.0 + i for i in range(20)])
    atr = _atr_at(bars, bar_idx=19, window=14)
    assert atr is not None
    assert atr > 0


# ---- Ruleset A ----------------------------------------------------------


def test_ruleset_a_close_below_50d_terminal_exit_pre_trigger() -> None:
    """TERMINAL hard exit fires even pre-trail-arm: first close <= SMA50."""
    # asof=2026-05-01; trigger at idx 50 (close=101 > peak=100); entry idx 51 open.
    # Build 60+ bars: 50 bars rising to peak, then trigger + 1 entry, then drop
    # below SMA50 immediately. Need to be careful that SMA50 is computed properly.
    closes = [98.0 + i * 0.02 for i in range(50)]  # 98.0 .. 98.98 (rising)
    closes += [101.0, 102.0]  # trigger at idx 50 (close=101 > 100); entry at idx 51
    # Drop sharply below SMA50 (which is ~98.5 at that point)
    closes += [70.0]  # crash; close=70 << SMA50 (~98) -> terminal exit fires
    bars = _bars(closes, start_date="2026-01-01")
    # Verdict's lower_bound = max(2026-04-01, 2026-04-20, asof) = asof
    # Set asof to be just before the trigger date for valid window
    asof_date = bars.index[49].date()
    v = PrimaryVerdict(
        ticker="ABC",
        anchor_asof_date=asof_date,
        trough_1_date=date(2025, 12, 1),
        trough_1_price=96.0, center_peak_date=date(2025, 12, 5), center_peak_price=100.0,
        trough_2_date=date(2025, 12, 15), trough_2_price=95.0,
        pivot_price=99.0, composite_score=0.85, geometric_score=0.85, template_match_score=None,
    )
    trade = walk_forward(v, bars, RulesetA())
    assert trade.status == "closed"
    assert trade.exit_reason == "close_below_50d"


def test_ruleset_a_stop_hit_close_based() -> None:
    """Pre-arm: first close < initial_stop fires stop_hit at the close (not the stop)."""
    # Plant pre-history so SMA50 is well below entry price (avoid early terminal exit).
    pre = [50.0] * 60  # 60 bars at close=50 to establish low SMA50
    # Trigger at idx 60 (close=101 > peak=100), entry at idx 61 open
    # Then crash to 90 (below stop=92*0.99=91.08)
    closes = pre + [101.0, 102.0, 90.0]  # idx 62 closes at 90 < 91.08
    bars = _bars(closes, start_date="2026-01-01")
    asof_date = bars.index[59].date()
    v = PrimaryVerdict(
        ticker="ABC",
        anchor_asof_date=asof_date,
        trough_1_date=date(2025, 12, 1),
        trough_1_price=92.5, center_peak_date=date(2025, 12, 5), center_peak_price=100.0,
        trough_2_date=date(2025, 12, 15), trough_2_price=92.0,
        pivot_price=99.0, composite_score=0.85, geometric_score=0.85, template_match_score=None,
    )
    trade = walk_forward(v, bars, RulesetA())
    assert trade.status == "closed"
    assert trade.exit_reason == "stop_hit"
    assert trade.exit_price == pytest.approx(90.0)
    assert trade.r_multiple < 0


# ---- Ruleset B ----------------------------------------------------------


def test_ruleset_b_target_3R_fires_close_based() -> None:
    """Close >= entry + 3R fires; exit at TARGET price (not close)."""
    # asof at idx 0. Trigger at idx 1 close=101; entry at idx 2 open=101.9.
    # Stop = 92*0.99 = 91.08. R = 101.9 - 91.08 = 10.82.
    # Target = 101.9 + 3*10.82 = 134.36. Plant a bar with close >= 134.36.
    closes = [95.0, 101.0, 102.0, 110.0, 125.0, 140.0]
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetB())
    assert trade.status == "closed"
    assert trade.exit_reason == "target_3R"
    # Exit at TARGET price (not 140.0 close)
    assert trade.exit_price == pytest.approx(101.9 + 3 * (101.9 - 92 * 0.99), rel=1e-3)
    assert trade.r_multiple == pytest.approx(3.0, abs=0.01)


def test_ruleset_b_stop_hit_close_based() -> None:
    """Close < initial_stop fires stop_hit at the close."""
    closes = [95.0, 101.0, 102.0, 95.0, 88.0]
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetB())
    assert trade.status == "closed"
    assert trade.exit_reason == "stop_hit"
    assert trade.exit_price == pytest.approx(88.0)
    assert trade.r_multiple < 0


# ---- Ruleset C ----------------------------------------------------------


def test_ruleset_c_stop_hit_close_based() -> None:
    """Close < initial_stop fires stop_hit; no SMA50 if insufficient bars."""
    closes = [95.0, 101.0, 102.0, 95.0, 88.0]
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetC())
    assert trade.status == "closed"
    assert trade.exit_reason == "stop_hit"
    assert trade.exit_price == pytest.approx(88.0)


def test_ruleset_c_close_below_50d_fires_with_sufficient_history() -> None:
    """Close < SMA50 fires (no trail-arm logic)."""
    # Build 60 bars of pre-history at close=100, then trigger + entry + crash.
    pre = [100.0] * 60  # SMA50 will be ~100
    closes = pre + [101.0, 102.0, 95.0]  # entry at idx 61 open=101.9; idx 62 close=95 < SMA50
    bars = _bars(closes, start_date="2026-01-01")
    asof_date = bars.index[59].date()
    v = PrimaryVerdict(
        ticker="ABC",
        anchor_asof_date=asof_date,
        trough_1_date=date(2025, 12, 1),
        trough_1_price=92.5, center_peak_date=date(2025, 12, 5), center_peak_price=100.0,
        trough_2_date=date(2025, 12, 15), trough_2_price=92.0,
        pivot_price=99.0, composite_score=0.85, geometric_score=0.85, template_match_score=None,
    )
    trade = walk_forward(v, bars, RulesetC())
    assert trade.status == "closed"
    assert trade.exit_reason == "close_below_50d"
    assert trade.exit_price == pytest.approx(95.0)


# ---- all_rulesets ------------------------------------------------------


def test_all_rulesets_returns_3_distinct_instances() -> None:
    rs = all_rulesets()
    assert len(rs) == 3
    names = {r.name for r in rs}
    assert names == {"A_minervini_trail_ma", "B_fixed_R_multiple", "C_close_below_50d"}
