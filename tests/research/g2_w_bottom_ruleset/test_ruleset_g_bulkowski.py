"""Tests for G_bulkowski_double_bottom (G2 dispatch brief Sec 2.1).

Spec:
  - Entry: first close > center_peak_price within search window AND
    breakout_bar_volume > 1.3 x trailing_20_bar_mean_volume.
  - Initial stop: trough_2_price * (1 - 0.01) = trough_2_price * 0.99
    (TIGHTER than E; no entry-relative arm).
  - Target: entry_price + (center_peak_price - min(trough_1_price,
    trough_2_price)); exit on first close >= target.
  - Failure: close < stop -> exit at the bar's close (consistent with E's
    close <= stop convention; per harness convention exit at bar's close).
  - No time-stop in V1.

Discriminating tests:
  - initial_stop arithmetic (trough_2 * 0.99); NO entry-relative arm
  - target arithmetic (measured-move = entry + (center_peak - min(trough_1, trough_2)))
  - target exit fires on first close >= target
  - stop exit fires on close < stop
  - trigger_predicate: breakout volume = 1.2x mean -> False; 1.3x -> False
    (strict inequality); 1.31x -> True
  - trigger_predicate at bar with < 20 trailing bars: returns False (insufficient history)
  - composition: full walk-forward with ruleset G and synthetic W produces
    expected target_measured_move exit
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.g2_w_bottom_ruleset_backtest.rulesets.g_bulkowski_double_bottom import (  # noqa: E501
    RulesetG,
    bulkowski_trigger_predicate,
    G_BREAKOUT_VOLUME_MULTIPLIER,
    G_VOLUME_LOOKBACK_BARS,
    G_STOP_BUFFER,
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


def test_g_initial_stop_is_trough2_minus_1pct():
    """G uses trough_2 * 0.99 (tight; no entry-relative arm per brief Sec 2.1)."""
    verdict = _make_verdict(trough_2_price=52.0)
    g = RulesetG()
    stop = g.initial_stop(verdict=verdict, entry_price=62.0)
    assert stop == pytest.approx(52.0 * (1 - G_STOP_BUFFER))
    assert stop == pytest.approx(51.48)


def test_g_initial_stop_does_not_apply_entry_relative_arm():
    """Unlike RulesetE (which uses max(trough_2*0.99, entry*0.92)), G has NO
    entry-relative floor: stop is always trough_2 * 0.99 regardless of entry.

    Discriminator: with entry far above trough_2 (e.g., 100 vs trough_2 52),
    E's entry * 0.92 = 92.0 would dominate; G's stop remains 51.48.
    """
    verdict = _make_verdict(trough_2_price=52.0)
    g = RulesetG()
    stop = g.initial_stop(verdict=verdict, entry_price=100.0)
    assert stop == pytest.approx(51.48)
    # Buggy alternative would yield max(51.48, 92.0) = 92.0; assert NOT equal
    assert stop != pytest.approx(92.0)


def test_g_target_is_measured_move():
    """target = entry + (center_peak - min(trough_1, trough_2)); discriminating
    arithmetic vs alternative formulae.

    With center_peak=60, trough_1=50, trough_2=52, entry=62:
      pattern_height = 60 - min(50, 52) = 60 - 50 = 10
      target = 62 + 10 = 72.0
    """
    verdict = _make_verdict(
        trough_1_price=50.0, center_peak_price=60.0, trough_2_price=52.0
    )
    g = RulesetG()
    # Stub bars: 100 flat bars at 62 (enough for any SMA window)
    bars = pd.DataFrame(
        {
            "Open": [62.0] * 100,
            "High": [62.1] * 100,
            "Low": [61.9] * 100,
            "Close": [62.0] * 100,
            "Volume": [1_000_000.0] * 100,
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=100),
    )
    state = g.init_state(
        verdict=verdict, bars=bars, entry_idx=0,
        entry_price=62.0, initial_stop=51.48,
    )
    assert state.extra["target_price"] == pytest.approx(72.0)


def test_g_target_uses_min_of_two_troughs_when_t1_lower():
    """If trough_1 (left shoulder) < trough_2 (right shoulder), use t1 for height."""
    verdict = _make_verdict(
        trough_1_price=48.0, center_peak_price=60.0, trough_2_price=52.0
    )
    g = RulesetG()
    bars = pd.DataFrame(
        {
            "Open": [62.0] * 100, "High": [62.1] * 100, "Low": [61.9] * 100,
            "Close": [62.0] * 100, "Volume": [1_000_000.0] * 100,
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=100),
    )
    state = g.init_state(
        verdict=verdict, bars=bars, entry_idx=0,
        entry_price=62.0, initial_stop=47.52,
    )
    # height = 60 - 48 = 12; target = 62 + 12 = 74.0
    assert state.extra["target_price"] == pytest.approx(74.0)


def test_g_exits_at_target_on_first_close_at_or_above():
    verdict = _make_verdict()
    g = RulesetG()
    # Target = 72.0; build bars where bar 1 = 71.99 (below), bar 2 = 72.0 (at)
    closes = [62.0, 71.99, 72.0, 75.0]
    bars = pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 0.10 for c in closes],
            "Low": [c - 0.10 for c in closes],
            "Close": closes,
            "Volume": [1_000_000.0] * 4,
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=4),
    )
    state = g.init_state(
        verdict=verdict, bars=bars, entry_idx=0,
        entry_price=62.0, initial_stop=51.48,
    )
    # Bar 0 (entry): close=62.0 < target 72.0 -> None
    action = g.update_and_check(
        state=state, bars=bars, bar_idx=0, entry_idx=0,
        entry_price=62.0, initial_R=10.52,
    )
    assert action is None
    # Bar 1: close=71.99 < target -> None
    action = g.update_and_check(
        state=state, bars=bars, bar_idx=1, entry_idx=0,
        entry_price=62.0, initial_R=10.52,
    )
    assert action is None
    # Bar 2: close=72.0 >= target -> FullExit at target
    action = g.update_and_check(
        state=state, bars=bars, bar_idx=2, entry_idx=0,
        entry_price=62.0, initial_R=10.52,
    )
    assert action is not None
    assert action.reason == "target_measured_move"
    assert action.price == pytest.approx(72.0)


def test_g_exits_at_close_on_stop_break():
    verdict = _make_verdict()
    g = RulesetG()
    # Stop = 51.48; bar 1 close = 51.0 (below stop)
    closes = [62.0, 51.0]
    bars = pd.DataFrame(
        {
            "Open": closes, "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes], "Close": closes,
            "Volume": [1_000_000.0] * 2,
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=2),
    )
    state = g.init_state(
        verdict=verdict, bars=bars, entry_idx=0,
        entry_price=62.0, initial_stop=51.48,
    )
    action = g.update_and_check(
        state=state, bars=bars, bar_idx=1, entry_idx=0,
        entry_price=62.0, initial_R=10.52,
    )
    assert action is not None
    assert action.reason == "stop_hit"
    assert action.price == pytest.approx(51.0)


def test_g_trigger_predicate_rejects_at_or_below_1_3x_volume():
    """Brief Sec 2.1: breakout_bar_volume > 1.3 x trailing 20-bar mean.
    Strict inequality; 1.3x exactly should be REJECTED.
    """
    verdict = _make_verdict()
    # 20 bars of mean=1_000_000, then breakout bar with various volumes
    closes_pre = [55.0] * 20
    volumes_pre = [1_000_000.0] * 20
    # Breakout bar at index 20 with close=62.0 (above center_peak 60)
    closes = closes_pre + [62.0]
    volumes_below = volumes_pre + [1_200_000.0]  # 1.2x
    volumes_at = volumes_pre + [1_300_000.0]  # 1.3x (boundary)
    volumes_above = volumes_pre + [1_310_000.0]  # 1.31x

    def make_bars(vols):
        return pd.DataFrame(
            {
                "Open": closes, "High": [c + 0.1 for c in closes],
                "Low": [c - 0.1 for c in closes], "Close": closes,
                "Volume": vols,
            },
            index=pd.bdate_range(start=date(2026, 1, 6), periods=21),
        )

    bars_below = make_bars(volumes_below)
    bars_at = make_bars(volumes_at)
    bars_above = make_bars(volumes_above)
    assert bulkowski_trigger_predicate(bars_below, 20, verdict) is False
    # Strict inequality: 1.3x exactly is NOT > 1.3x
    assert bulkowski_trigger_predicate(bars_at, 20, verdict) is False
    assert bulkowski_trigger_predicate(bars_above, 20, verdict) is True


def test_g_trigger_predicate_rejects_when_insufficient_history():
    """With fewer than G_VOLUME_LOOKBACK_BARS prior bars, predicate returns
    False (cannot establish baseline volume).
    """
    verdict = _make_verdict()
    # Only 10 prior bars (< 20 lookback)
    closes = [55.0] * 10 + [62.0]
    volumes = [1_000_000.0] * 10 + [5_000_000.0]
    bars = pd.DataFrame(
        {
            "Open": closes, "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes], "Close": closes, "Volume": volumes,
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=11),
    )
    assert bulkowski_trigger_predicate(bars, 10, verdict) is False


def test_g_full_walkforward_target_exit_on_synthetic_w():
    """End-to-end: synthetic W with clean volume-confirmed breakout and
    forward drift hits the measured-move target."""
    verdict = _make_verdict(
        trough_2_date=date(2025, 12, 29),
        anchor_asof_date=date(2026, 1, 5),
    )
    # 20 pre-window bars (volume baseline), then trigger bar inside search
    # window with 2x volume + drift to target
    n_pre = 25
    pre_dates = pd.bdate_range(start=date(2026, 1, 6), periods=n_pre)
    pre_closes = [55.0] * n_pre
    pre_opens = [55.0] * n_pre
    pre_volumes = [1_000_000.0] * n_pre
    # Trigger bar at index n_pre (e.g., bar 25)
    trigger_close = 62.0
    trigger_volume = 2_000_000.0  # 2x baseline -> passes 1.3x predicate
    # Entry bar (n_pre + 1) opens at trigger_close; drift up
    n_post = 30
    post_opens = [trigger_close] + [None] * (n_post - 1)
    post_closes = [trigger_close + 0.5] + [None] * (n_post - 1)
    for k in range(1, n_post):
        post_opens[k] = post_closes[k - 1]
        post_closes[k] = min(post_closes[k - 1] + 0.5, 80.0)  # well past target
    all_dates = pd.bdate_range(start=date(2026, 1, 6), periods=n_pre + 1 + n_post)
    all_closes = pre_closes + [trigger_close] + post_closes
    all_opens = pre_opens + [trigger_close] + post_opens
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
    g = RulesetG()
    trade = walk_forward_with_trigger_predicate(
        verdict, bars, g, trigger_predicate=bulkowski_trigger_predicate
    )
    assert trade.triggered is True
    assert trade.status == "closed"
    assert trade.exit_reason == "target_measured_move"
    # Target = 62 + (60 - 50) = 72.0; exit_price at target
    assert trade.exit_price == pytest.approx(72.0)
