"""Tests for H_oneil_double_bottom_base (G2 dispatch brief Sec 2.2).

Spec:
  - Entry: first close > pivot_price (= center_peak_price) AND breakout_bar
    volume > 1.4 x trailing 50-bar mean volume.
  - Initial stop: entry_price * 0.92 (8% below entry; same as RulesetE's
    entry * 0.92 arm but WITHOUT the trough_2 * 0.99 max() comparison).
  - Target: entry + (center_peak - min(trough_1, trough_2)) -- same
    measured-move as G.
  - Failure: close < stop OR close < 50-bar SMA -> exit at close
    (first to fire; O'Neil's 'stage 2 break' invalidation).

Discriminating tests:
  - initial_stop arithmetic (entry * 0.92); independent of trough_2
  - target arithmetic (measured-move)
  - target exit fires before stop / SMA-break when target reached
  - close < stop exits with reason 'stop_hit'
  - close < SMA50 exits with reason 'close_below_50d'
  - close < stop AND close < SMA50 same bar: stop_hit fires first (closer to
    discipline order documented in module)
  - trigger_predicate: 1.3x mean volume -> False; 1.4x -> False (strict);
    1.41x -> True
  - trigger_predicate: insufficient history (< 50 bars) -> False
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.g2_w_bottom_ruleset_backtest.rulesets.h_oneil_double_bottom_base import (  # noqa: E501
    RulesetH,
    oneil_trigger_predicate,
    H_STOP_PCT,
    H_BREAKOUT_VOLUME_MULTIPLIER,
    H_VOLUME_LOOKBACK_BARS,
    H_HARD_EXIT_SMA_WINDOW,
)
from research.harness.g2_w_bottom_ruleset_backtest.walkforward_ghi import (
    walk_forward_with_trigger_predicate,
)


def _make_verdict(
    *,
    ticker: str = "TST",
    trough_1_price: float = 50.0,
    center_peak_price: float = 60.0,
    trough_2_price: float = 52.0,
    anchor_asof_date: date = date(2026, 1, 5),
    trough_1_date: date = date(2025, 11, 1),
    center_peak_date: date = date(2025, 11, 15),
    trough_2_date: date = date(2025, 12, 1),
) -> PrimaryVerdict:
    return PrimaryVerdict(
        ticker=ticker,
        anchor_asof_date=anchor_asof_date,
        trough_1_date=trough_1_date,
        trough_1_price=trough_1_price,
        center_peak_date=center_peak_date,
        center_peak_price=center_peak_price,
        trough_2_date=trough_2_date,
        trough_2_price=trough_2_price,
        pivot_price=center_peak_price,
        composite_score=0.75,
        geometric_score=0.75,
        template_match_score=None,
        cohort_entry_ids=(1,),
        aux_window_indices=(0,),
        max_observed_asof_date=anchor_asof_date,
        observed_asof_dates=(anchor_asof_date,),
        window_count=1,
    )


def test_h_initial_stop_is_entry_times_0_92():
    """H uses entry * 0.92 (8% below entry); independent of trough_2."""
    verdict = _make_verdict()
    h = RulesetH()
    stop = h.initial_stop(verdict=verdict, entry_price=62.0)
    assert stop == pytest.approx(62.0 * H_STOP_PCT)
    assert stop == pytest.approx(57.04)


def test_h_initial_stop_independent_of_trough_2():
    """Discriminator vs G (which uses trough_2 * 0.99): with trough_2=100
    (above entry), G's stop would be 99.0; H's stop stays at entry * 0.92."""
    verdict = _make_verdict(trough_2_price=100.0)
    h = RulesetH()
    stop = h.initial_stop(verdict=verdict, entry_price=62.0)
    assert stop == pytest.approx(57.04)
    assert stop != pytest.approx(99.0)


def test_h_target_is_measured_move_same_as_g():
    verdict = _make_verdict(
        trough_1_price=50.0, center_peak_price=60.0, trough_2_price=52.0
    )
    h = RulesetH()
    bars = pd.DataFrame(
        {
            "Open": [62.0] * 60, "High": [62.1] * 60, "Low": [61.9] * 60,
            "Close": [62.0] * 60, "Volume": [1_000_000.0] * 60,
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=60),
    )
    state = h.init_state(
        verdict=verdict, bars=bars, entry_idx=0,
        entry_price=62.0, initial_stop=57.04,
    )
    # height = 60 - 50 = 10; target = 62 + 10 = 72.0
    assert state.extra["target_price"] == pytest.approx(72.0)


def test_h_target_exit_fires_when_reached():
    verdict = _make_verdict()
    h = RulesetH()
    closes = [62.0] * 60 + [71.99, 72.0]  # 60 flat bars + 2 trigger candidates
    bars = pd.DataFrame(
        {
            "Open": closes, "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes], "Close": closes,
            "Volume": [1_000_000.0] * len(closes),
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=len(closes)),
    )
    state = h.init_state(
        verdict=verdict, bars=bars, entry_idx=0,
        entry_price=62.0, initial_stop=57.04,
    )
    # Bar 61: close=72.0 >= target 72.0 -> FullExit at target
    action = h.update_and_check(
        state=state, bars=bars, bar_idx=61, entry_idx=0,
        entry_price=62.0, initial_R=4.96,
    )
    assert action is not None
    assert action.reason == "target_measured_move"
    assert action.price == pytest.approx(72.0)


def test_h_stop_exit_fires_on_close_below_stop():
    verdict = _make_verdict()
    h = RulesetH()
    # 60 flat bars to populate SMA50 history; then a stop-break bar
    closes = [62.0] * 60 + [57.0]  # 57.0 < stop 57.04
    bars = pd.DataFrame(
        {
            "Open": closes, "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes], "Close": closes,
            "Volume": [1_000_000.0] * len(closes),
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=len(closes)),
    )
    state = h.init_state(
        verdict=verdict, bars=bars, entry_idx=0,
        entry_price=62.0, initial_stop=57.04,
    )
    action = h.update_and_check(
        state=state, bars=bars, bar_idx=60, entry_idx=0,
        entry_price=62.0, initial_R=4.96,
    )
    assert action is not None
    assert action.reason == "stop_hit"
    assert action.price == pytest.approx(57.0)


def test_h_sma50_break_exits_when_close_below_sma_but_above_stop():
    """Construct: 50 bars at 70.0 (so SMA50 just below 70), entry at bar 50 at
    62.0; bar 51 close = 65.0 (above stop 57.04, but below SMA50 ~ 69.86)."""
    verdict = _make_verdict()
    h = RulesetH()
    closes = [70.0] * 50 + [62.0, 65.0]
    bars = pd.DataFrame(
        {
            "Open": closes, "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes], "Close": closes,
            "Volume": [1_000_000.0] * len(closes),
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=len(closes)),
    )
    state = h.init_state(
        verdict=verdict, bars=bars, entry_idx=50,
        entry_price=62.0, initial_stop=57.04,
    )
    # Bar 51: close=65.0 > stop 57.04; SMA50 over (idx 2..51) is roughly mix
    # of 70.0 * 48 + 62.0 + 65.0 = 3487 / 50 = 69.74; close 65 < 69.74 -> exit
    action = h.update_and_check(
        state=state, bars=bars, bar_idx=51, entry_idx=50,
        entry_price=62.0, initial_R=4.96,
    )
    assert action is not None
    assert action.reason == "close_below_50d"
    assert action.price == pytest.approx(65.0)


def test_h_stop_hit_takes_precedence_when_both_break_same_bar():
    """When close < stop AND close < SMA50 on the same bar, stop_hit fires
    first (deterministic order: stop check before SMA-break check)."""
    verdict = _make_verdict()
    h = RulesetH()
    # 50 bars at 70.0; entry bar at 62.0; bar 51 crashes to 55.0
    closes = [70.0] * 50 + [62.0, 55.0]
    bars = pd.DataFrame(
        {
            "Open": closes, "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes], "Close": closes,
            "Volume": [1_000_000.0] * len(closes),
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=len(closes)),
    )
    state = h.init_state(
        verdict=verdict, bars=bars, entry_idx=50,
        entry_price=62.0, initial_stop=57.04,
    )
    action = h.update_and_check(
        state=state, bars=bars, bar_idx=51, entry_idx=50,
        entry_price=62.0, initial_R=4.96,
    )
    assert action is not None
    assert action.reason == "stop_hit"  # NOT close_below_50d
    assert action.price == pytest.approx(55.0)


def test_h_trigger_predicate_strict_inequality_at_1_4x():
    verdict = _make_verdict()
    closes_pre = [55.0] * 50
    volumes_pre = [1_000_000.0] * 50
    closes = closes_pre + [62.0]

    def make_bars(vol_at_breakout):
        return pd.DataFrame(
            {
                "Open": closes, "High": [c + 0.1 for c in closes],
                "Low": [c - 0.1 for c in closes], "Close": closes,
                "Volume": volumes_pre + [vol_at_breakout],
            },
            index=pd.bdate_range(start=date(2026, 1, 6), periods=51),
        )

    assert oneil_trigger_predicate(make_bars(1_300_000.0), 50, verdict) is False
    # 1.4x boundary: strict inequality, so 1.4x exactly is REJECTED
    assert oneil_trigger_predicate(make_bars(1_400_000.0), 50, verdict) is False
    assert oneil_trigger_predicate(make_bars(1_410_000.0), 50, verdict) is True


def test_h_trigger_predicate_rejects_insufficient_history():
    """With fewer than 50 prior bars, predicate returns False."""
    verdict = _make_verdict()
    closes = [55.0] * 30 + [62.0]
    volumes = [1_000_000.0] * 30 + [5_000_000.0]
    bars = pd.DataFrame(
        {
            "Open": closes, "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes], "Close": closes, "Volume": volumes,
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=31),
    )
    assert oneil_trigger_predicate(bars, 30, verdict) is False


def test_h_full_walkforward_synthetic_w_target_exit():
    verdict = _make_verdict(
        trough_2_date=date(2025, 12, 29),
        anchor_asof_date=date(2026, 1, 5),
    )
    # 55 pre-window bars (50-volume baseline), then trigger + drift to target
    n_pre = 55
    pre_closes = [55.0] * n_pre
    pre_volumes = [1_000_000.0] * n_pre
    trigger_close = 62.0
    trigger_volume = 2_000_000.0
    n_post = 30
    post_opens = [trigger_close]
    post_closes = [trigger_close + 0.5]
    for k in range(1, n_post):
        post_opens.append(post_closes[k - 1])
        post_closes.append(min(post_closes[k - 1] + 0.5, 80.0))
    all_dates = pd.bdate_range(start=date(2026, 1, 6), periods=n_pre + 1 + n_post)
    all_closes = pre_closes + [trigger_close] + post_closes
    all_opens = pre_closes + [trigger_close] + post_opens
    all_volumes = pre_volumes + [trigger_volume] + [1_000_000.0] * n_post
    bars = pd.DataFrame(
        {
            "Open": all_opens,
            "High": [max(o, c) + 0.10 for o, c in zip(all_opens, all_closes)],
            "Low": [min(o, c) - 0.10 for o, c in zip(all_opens, all_closes)],
            "Close": all_closes,
            "Volume": all_volumes,
        },
        index=all_dates,
    )
    h = RulesetH()
    trade = walk_forward_with_trigger_predicate(
        verdict, bars, h, trigger_predicate=oneil_trigger_predicate
    )
    assert trade.triggered is True
    assert trade.status == "closed"
    assert trade.exit_reason == "target_measured_move"
    assert trade.exit_price == pytest.approx(72.0)
