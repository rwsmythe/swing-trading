"""Walk-forward engine tests for D2 (extends D1 coverage with scale-out path)."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.w_bottom_ruleset_comparison.rulesets import (
    RulesetB,
    RulesetC,
    RulesetE,
    RulesetF,
)
from research.harness.w_bottom_ruleset_comparison.walkforward import (
    FullExit,
    ScaleOut,
    State,
    find_trigger_index,
    sma_at,
    atr_at,
    trigger_search_upper_bound,
    walk_forward,
    _weighted_R,
)


def _bars(closes: list[float], opens: list[float] | None = None,
          highs: list[float] | None = None, lows: list[float] | None = None,
          start: date = date(2026, 1, 2)) -> pd.DataFrame:
    if opens is None:
        opens = closes[:]
    if highs is None:
        highs = [c * 1.005 for c in closes]
    if lows is None:
        lows = [c * 0.995 for c in closes]
    idx = pd.date_range(start, periods=len(closes), freq="B")
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes,
         "Volume": [100_000] * len(closes)},
        index=idx,
    )


def _verdict(asof: date = date(2026, 4, 30), **kw) -> PrimaryVerdict:
    defaults = dict(
        ticker="TEST",
        anchor_asof_date=asof,
        trough_1_date=asof - timedelta(days=60),
        trough_1_price=88.0,
        center_peak_date=asof - timedelta(days=40),
        center_peak_price=100.0,
        trough_2_date=asof - timedelta(days=20),
        trough_2_price=90.0,
        pivot_price=100.0,
        composite_score=0.85,
        geometric_score=0.85,
        template_match_score=0.85,
        max_observed_asof_date=asof,
        observed_asof_dates=(asof,),
    )
    defaults.update(kw)
    return PrimaryVerdict(**defaults)


# ---------------------------------------------------------------------------
# Helper tests (SMA / ATR)
# ---------------------------------------------------------------------------
def test_sma_at_returns_none_if_insufficient_bars():
    bars = _bars([100.0, 101.0])
    assert sma_at(bars, 1, 5) is None  # need 5 bars, only have 2
    assert sma_at(bars, 1, 2) == pytest.approx(100.5)


def test_atr_at_returns_none_if_insufficient_bars():
    bars = _bars([100.0, 101.0])
    assert atr_at(bars, 1, 14) is None
    assert atr_at(bars, 1, 1) is not None  # 1 bar + prior close = ok


# ---------------------------------------------------------------------------
# Trigger search tests
# ---------------------------------------------------------------------------
def test_find_trigger_index_returns_first_close_above_threshold():
    bars = _bars([95.0, 98.0, 99.0, 101.0, 105.0])
    # lower_bound is EXCLUSIVE; uppers INCLUSIVE
    idx = find_trigger_index(
        bars, trigger_threshold=100.0,
        lower_bound_exclusive=date(2026, 1, 1),
        upper_bound_inclusive=date(2026, 12, 31),
    )
    assert idx == 3  # close=101 at idx=3 is first > 100


def test_find_trigger_index_returns_none_if_no_close_above():
    bars = _bars([90.0, 95.0, 99.0])
    idx = find_trigger_index(
        bars, trigger_threshold=100.0,
        lower_bound_exclusive=date(2026, 1, 1),
        upper_bound_inclusive=date(2026, 12, 31),
    )
    assert idx is None


def test_find_trigger_index_respects_lower_bound_exclusive():
    """A close > threshold AT or BEFORE lower_bound is ignored.

    Need 5 bars so that trigger at idx 3 has idx 4 entry-open available
    (find_trigger_index requires i + 1 < n).
    """
    bars = _bars([105.0, 95.0, 99.0, 102.0, 110.0])
    # lower_bound at bars[0] date; bars[0] should be ignored
    idx = find_trigger_index(
        bars, trigger_threshold=100.0,
        lower_bound_exclusive=bars.index[0].date(),
        upper_bound_inclusive=date(2026, 12, 31),
    )
    assert idx == 3  # not 0 (lower_bound skips idx 0)


def test_trigger_search_upper_bound_60_business_days():
    ub = trigger_search_upper_bound(date(2026, 4, 30), max_business_days=60)
    # 60 business days from Thu 2026-04-30 lands in late July 2026
    assert ub > date(2026, 7, 1)
    assert ub < date(2026, 8, 15)


# ---------------------------------------------------------------------------
# walk_forward integration tests (using RulesetC for simple semantics)
# ---------------------------------------------------------------------------
def test_walk_forward_untriggered_when_no_close_above_center_peak():
    # asof=2026-04-30; bars from 2026-01-02 through 2026-04-30 + forward window
    # All closes well below center_peak=100 in forward window
    closes = [85.0] * 120
    bars = _bars(closes, start=date(2026, 1, 2))
    # asof_date in middle so there's forward window
    v = _verdict(asof=date(2026, 3, 6))  # bar around idx 45
    trade = walk_forward(v, bars, RulesetC())
    assert trade.status == "untriggered"
    assert trade.triggered is False
    assert trade.exit_reason == "untriggered"


def test_walk_forward_emits_open_at_data_tail_when_no_exit_fires():
    # Build bars where close > center_peak after asof but no exit ever fires
    # Use RulesetB whose only exits are stop_hit / target_3R
    closes = [85.0] * 50 + [102.0, 103.0, 104.0]  # trigger at bar 50 (close=102>100); entry next bar
    bars = _bars(closes, start=date(2026, 1, 2))
    # asof = date at idx 30 (well before trigger)
    v = _verdict(asof=bars.index[30].date())
    trade = walk_forward(v, bars, RulesetB())
    # Trigger window is asof+1 to asof+60BD; trigger at idx 50
    assert trade.status == "open"
    assert trade.triggered is True
    assert trade.exit_reason == "open_at_data_tail"


def test_walk_forward_entry_gap_below_stop_emits_synthetic_closed():
    """Entry bar's OPEN <= initial_stop -> degenerate; emit closed-at-0R."""
    closes = [85.0] * 50 + [102.0]  # trigger at 50
    opens = [85.0] * 50 + [101.0, 80.0]  # entry next bar opens at 80 < initial_stop 89.1
    closes += [80.0]
    bars = _bars(closes, opens=opens[: len(closes)], start=date(2026, 1, 2))
    v = _verdict(asof=bars.index[30].date(), trough_2_price=90.0)
    trade = walk_forward(v, bars, RulesetB())
    assert trade.status == "closed"
    assert trade.exit_reason == "entry_gap_below_stop"
    assert trade.r_multiple == 0.0


def test_walk_forward_ohlcv_empty_returns_untriggered():
    bars = _bars([], start=date(2026, 1, 2))  # would fail; build empty
    bars = pd.DataFrame({"Open": [], "High": [], "Low": [], "Close": [], "Volume": []})
    v = _verdict()
    trade = walk_forward(v, bars, RulesetC())
    assert trade.exit_reason == "ohlcv_empty"
    assert trade.status == "untriggered"


# ---------------------------------------------------------------------------
# Scale-out weighted R tests (NEW for D2)
# ---------------------------------------------------------------------------
def test_weighted_R_without_scale_out_returns_remainder_R_verbatim():
    state = State(current_stop=90.0)
    assert _weighted_R(state, 1.5) == pytest.approx(1.5)


def test_weighted_R_with_scale_out_blends_R_per_fraction():
    """scale_R=+2.0R at fraction=1/3; remainder ends at +0.5R.
    weighted = (1/3)*2 + (2/3)*0.5 = 0.6667 + 0.3333 = 1.0R."""
    state = State(current_stop=100.0, scale_out_fired=True,
                  scale_out_R=2.0, scale_out_fraction=1.0 / 3.0)
    weighted = _weighted_R(state, 0.5)
    expected = (1.0 / 3.0) * 2.0 + (2.0 / 3.0) * 0.5
    assert weighted == pytest.approx(expected)


def test_walk_forward_with_ruleset_f_scale_out_then_continues():
    """Plant +2R move (scale-out fires) + then close-below-50d_gated trigger
    later -> exit_reason gets `_after_scaleout` suffix; r_multiple is weighted."""
    # Build bars: pre-history for ATR, entry+trigger, +2R move, then decline below SMA50_gated
    pre_closes = [100.0] * 50
    # trigger at idx 50 (close=102 > center_peak=100)
    # entry at idx 51 (open=102, close=105)
    # +2R = entry + 2*R; entry=102, R=102 - 90*0.99 = 102 - 89.1 = 12.9; +2R = 127.8
    # session 1 (idx 51): close=105
    # session 2 (idx 52): close=130 -> +2R hit -> ScaleOut + BE arm
    # subsequent: SMA50 climbs above entry * 1.05 = 107.1; eventually close drops below SMA50
    # build sufficient bars for SMA50 to climb above 107.1 then close drops below
    post = [
        102.0,  # idx 50 trigger close
        105.0,  # idx 51 entry close (session 1)
        130.0,  # idx 52 +2R scale-out (session 2)
        135.0, 140.0, 145.0,  # sustained higher closes -> SMA50 climbs
        # subsequent sustained higher closes lift SMA50 above 107.1
    ]
    # Add many high closes to lift SMA50, then a drop below SMA50
    post += [140.0] * 100  # SMA50 climbs to ~140
    post += [100.0]  # final close drops below SMA50 (~140) and < entry*1.05 - but
                      # gated 50d requires sma50 > entry*1.05 (=107.1) AND close <= sma50.
                      # SMA50 ~ 140 > 107.1 -> gate armed; close=100 < 140 -> exit fires.
    closes = pre_closes + post
    # Opens match closes (no gaps); highs/lows tight band
    bars = _bars(closes, start=date(2026, 1, 2))
    asof = bars.index[40].date()  # before trigger; lower_bound=max(trough dates, asof)+1
    v = _verdict(asof=asof, center_peak_price=100.0, trough_2_price=90.0, trough_1_price=88.0)
    trade = walk_forward(v, bars, RulesetF())
    assert trade.status == "closed"
    # Either close_below_50d_gated_after_scaleout OR open_at_data_tail_after_scaleout
    # (depending on whether the late drop fires the gate or runs to data tail)
    assert "after_scaleout" in trade.exit_reason
    # r_multiple should be the weighted blend (positive due to +2R scale-out)
    assert trade.r_multiple is not None
    # Scale-out contribution: (1/3) * 2R = +0.667R; remainder R can be much
    # smaller or negative; weighted should still be positive overall in this setup.
    assert trade.r_multiple > 0


# ---------------------------------------------------------------------------
# walk_forward Ruleset E measured-move target test
# ---------------------------------------------------------------------------
def test_walk_forward_ruleset_e_exits_at_target_when_close_above_target():
    pre = [85.0] * 50
    # trigger at idx 50 (close 102 > center_peak 100)
    # entry at idx 51 (open 102)
    # target = entry + (center_peak - min(trough_1, trough_2)) = 102 + (100 - 88) = 114
    # plant close 115 at idx 53 (well above target)
    post = [102.0, 102.0, 110.0, 115.0]
    closes = pre + post
    bars = _bars(closes, start=date(2026, 1, 2))
    asof = bars.index[40].date()
    v = _verdict(asof=asof, center_peak_price=100.0, trough_1_price=88.0, trough_2_price=90.0)
    trade = walk_forward(v, bars, RulesetE())
    assert trade.status == "closed"
    assert trade.exit_reason == "target_measured_move"
    # Target = 102 + (100 - 88) = 114; exit_price should equal target
    assert trade.exit_price == pytest.approx(114.0)
