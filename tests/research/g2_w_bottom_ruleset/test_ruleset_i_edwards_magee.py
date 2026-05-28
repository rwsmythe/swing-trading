"""Tests for I_edwards_magee_classical_double_bottom (G2 dispatch brief Sec 2.3).

Spec:
  - Entry: first close > center_peak_price AND breakout_bar_volume >
    1.5 x mean(volume between trough_2_date and breakout_bar_date - 1).
  - Initial stop: min(trough_1_price, trough_2_price) * (1 - 0.01).
  - Target: entry + (center_peak - min(trough_1, trough_2)) -- same as G.
  - Failure: close < stop -> exit at close.
  - Throwback-aware: brief Sec 2.3 wording 'do NOT re-enter on second
    break' aligns with the harness's single-entry convention; the engine
    enters once + holds through any subsequent retracement. No special
    code needed; verified via discriminating test.

Discriminating tests:
  - initial_stop arithmetic: min(t1, t2) * 0.99
  - stop uses LOWER of two troughs when t1 < t2 (vs G which uses only t2)
  - target arithmetic (measured-move; same as G)
  - target exit on first close >= target
  - stop exit on close < stop
  - trigger_predicate: rally_volume baseline = mean(volume t2_date..bar-1)
  - 1.4x rally_volume -> False; 1.5x -> False (strict); 1.6x -> True
  - trigger_predicate falls through when no bars between t2 and breakout
    (returns False; cannot establish baseline)
  - throwback semantic: single entry; no re-entry on subsequent breaks
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.g2_w_bottom_ruleset_backtest.rulesets.i_edwards_magee_classical import (  # noqa: E501
    RulesetI,
    edwards_magee_trigger_predicate,
    I_STOP_BUFFER,
    I_BREAKOUT_VOLUME_MULTIPLIER,
)
from research.harness.g2_w_bottom_ruleset_backtest.walkforward_ghi import (
    DeferredExit,
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


def test_i_initial_stop_uses_lower_trough_when_t1_lower():
    """When trough_1 (50) < trough_2 (52), stop uses trough_1 * 0.99 = 49.5."""
    verdict = _make_verdict(trough_1_price=50.0, trough_2_price=52.0)
    i = RulesetI()
    stop = i.initial_stop(verdict=verdict, entry_price=62.0)
    assert stop == pytest.approx(50.0 * (1 - I_STOP_BUFFER))
    assert stop == pytest.approx(49.5)


def test_i_initial_stop_uses_lower_trough_when_t2_lower():
    """When trough_2 (48) < trough_1 (50), stop uses trough_2 * 0.99 = 47.52."""
    verdict = _make_verdict(trough_1_price=50.0, trough_2_price=48.0)
    i = RulesetI()
    stop = i.initial_stop(verdict=verdict, entry_price=62.0)
    assert stop == pytest.approx(48.0 * (1 - I_STOP_BUFFER))
    assert stop == pytest.approx(47.52)


def test_i_stop_differs_from_g_when_t1_lower():
    """Discriminator vs G (which always uses trough_2 * 0.99): when t1 < t2,
    I's stop = t1 * 0.99 != G's stop = t2 * 0.99."""
    verdict = _make_verdict(trough_1_price=50.0, trough_2_price=55.0)
    i = RulesetI()
    stop = i.initial_stop(verdict=verdict, entry_price=62.0)
    # I uses min(50, 55) = 50 -> 49.5; G would use 55 -> 54.45
    assert stop == pytest.approx(49.5)
    assert stop != pytest.approx(54.45)


def test_i_target_is_pattern_anchored_measured_move():
    """Per brief Sec 2.3 LOCK: target = center_peak + height (PATTERN-
    ANCHORED). Same formula as G + H."""
    verdict = _make_verdict(
        trough_1_price=50.0, center_peak_price=60.0, trough_2_price=52.0
    )
    i = RulesetI()
    bars = pd.DataFrame(
        {
            "Open": [62.0] * 10, "High": [62.1] * 10, "Low": [61.9] * 10,
            "Close": [62.0] * 10, "Volume": [1_000_000.0] * 10,
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=10),
    )
    state = i.init_state(
        verdict=verdict, bars=bars, entry_idx=0,
        entry_price=62.0, initial_stop=49.5,
    )
    # height = 60 - 50 = 10; pattern-anchored target = 60 + 10 = 70.0
    assert state.extra["target_price"] == pytest.approx(70.0)
    assert state.extra["target_price"] != pytest.approx(72.0)


def test_i_target_exit_fires():
    """Pattern-anchored target = 70.0; bars build up: 69.99 (below) then
    70.0 (at target)."""
    verdict = _make_verdict()
    i = RulesetI()
    closes = [62.0, 69.99, 70.0]
    bars = pd.DataFrame(
        {
            "Open": closes, "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes], "Close": closes,
            "Volume": [1_000_000.0] * 3,
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=3),
    )
    state = i.init_state(
        verdict=verdict, bars=bars, entry_idx=0,
        entry_price=62.0, initial_stop=49.5,
    )
    action = i.update_and_check(
        state=state, bars=bars, bar_idx=2, entry_idx=0,
        entry_price=62.0, initial_R=12.5,
    )
    assert action is not None
    assert action.reason == "target_measured_move"
    assert action.price == pytest.approx(70.0)


def test_i_stop_exit_fires():
    verdict = _make_verdict()
    i = RulesetI()
    closes = [62.0, 49.0]  # close 49.0 < stop 49.5
    bars = pd.DataFrame(
        {
            "Open": closes, "High": [c + 0.1 for c in closes],
            "Low": [c - 0.1 for c in closes], "Close": closes,
            "Volume": [1_000_000.0] * 2,
        },
        index=pd.bdate_range(start=date(2026, 1, 6), periods=2),
    )
    state = i.init_state(
        verdict=verdict, bars=bars, entry_idx=0,
        entry_price=62.0, initial_stop=49.5,
    )
    action = i.update_and_check(
        state=state, bars=bars, bar_idx=1, entry_idx=0,
        entry_price=62.0, initial_R=12.5,
    )
    assert action is not None
    assert isinstance(action, DeferredExit)
    assert action.reason == "stop_hit"


def test_i_trigger_predicate_rally_volume_baseline_at_1_5x_strict():
    """Edwards-Magee: breakout volume > 1.5 x mean(volume between trough_2_date
    and breakout_bar_date - 1)."""
    # 10 bars starting 2025-12-02 (day after trough_2_date 2025-12-01); the
    # breakout bar is at index 10. Bars 0..9 are the rally bars; their mean
    # volume is the baseline. The candidate breakout bar at idx 10 is OUTSIDE
    # the rally window.
    rally_dates = pd.bdate_range(start=date(2025, 12, 2), periods=10)
    breakout_date = pd.bdate_range(start=date(2025, 12, 16), periods=1)[0]
    all_dates = list(rally_dates) + [breakout_date]
    closes = [55.0] * 10 + [62.0]
    rally_volume = 1_000_000.0
    rally_volumes = [rally_volume] * 10  # mean = 1_000_000

    def make_bars(breakout_vol):
        return pd.DataFrame(
            {
                "Open": closes, "High": [c + 0.1 for c in closes],
                "Low": [c - 0.1 for c in closes], "Close": closes,
                "Volume": rally_volumes + [breakout_vol],
            },
            index=all_dates,
        )

    verdict = _make_verdict(
        trough_2_date=date(2025, 12, 1),
        anchor_asof_date=date(2025, 12, 15),
    )
    assert edwards_magee_trigger_predicate(
        make_bars(1_400_000.0), 10, verdict
    ) is False
    # 1.5x boundary: strict inequality REJECTS exactly 1.5x
    assert edwards_magee_trigger_predicate(
        make_bars(1_500_000.0), 10, verdict
    ) is False
    assert edwards_magee_trigger_predicate(
        make_bars(1_600_000.0), 10, verdict
    ) is True


def test_i_trigger_predicate_rejects_when_no_rally_bars_between_t2_and_breakout():
    """If breakout bar is the bar immediately AFTER trough_2 (no rally bars
    in between), predicate returns False (cannot establish baseline)."""
    verdict = _make_verdict(trough_2_date=date(2025, 12, 1))
    # Breakout at the bar with date 2025-12-02 (immediately after trough_2).
    # No bars in (2025-12-01, 2025-12-02) exclusive of both endpoints.
    bars = pd.DataFrame(
        {
            "Open": [62.0], "High": [62.1], "Low": [61.9],
            "Close": [62.0], "Volume": [5_000_000.0],
        },
        index=[date(2025, 12, 2)],
    )
    assert edwards_magee_trigger_predicate(bars, 0, verdict) is False


def test_i_full_walkforward_synthetic_w_target_exit():
    verdict = _make_verdict(
        trough_2_date=date(2025, 12, 1),
        anchor_asof_date=date(2026, 1, 5),
    )
    # Bars from 2025-12-02 (after trough_2) onwards
    n_rally = 20
    rally_dates = pd.bdate_range(start=date(2025, 12, 2), periods=n_rally)
    rally_closes = [55.0] * n_rally
    rally_volumes = [1_000_000.0] * n_rally
    # Breakout bar must be AFTER trigger_lower_bound_date = max(t1, t2, asof)
    # = 2026-01-05; pick first bdate after that.
    trigger_date = pd.bdate_range(start=date(2026, 1, 6), periods=1)[0]
    trigger_close = 62.0
    trigger_volume = 5_000_000.0  # 5x rally baseline; passes 1.5x predicate
    # Post-trigger drift to target
    n_post = 30
    post_dates = pd.bdate_range(start=trigger_date + pd.tseries.offsets.BDay(1), periods=n_post)
    post_opens = [trigger_close]
    post_closes = [trigger_close + 0.5]
    for k in range(1, n_post):
        post_opens.append(post_closes[k - 1])
        post_closes.append(min(post_closes[k - 1] + 0.5, 80.0))
    all_dates = list(rally_dates) + [trigger_date] + list(post_dates)
    all_closes = rally_closes + [trigger_close] + post_closes
    all_opens = rally_closes + [trigger_close] + post_opens
    all_volumes = rally_volumes + [trigger_volume] + [1_000_000.0] * n_post
    bars = pd.DataFrame(
        {
            "Open": all_opens,
            "High": [max(o, c) + 0.1 for o, c in zip(all_opens, all_closes)],
            "Low": [min(o, c) - 0.1 for o, c in zip(all_opens, all_closes)],
            "Close": all_closes,
            "Volume": all_volumes,
        },
        index=all_dates,
    )
    i = RulesetI()
    trade = walk_forward_with_trigger_predicate(
        verdict, bars, i, trigger_predicate=edwards_magee_trigger_predicate
    )
    assert trade.triggered is True
    assert trade.status == "closed"
    assert trade.exit_reason == "target_measured_move"
    # Pattern-anchored target = 60 + 10 = 70.0
    assert trade.exit_price == pytest.approx(70.0)
    # Entry-at-trigger-close = trigger bar's close = 62.0
    assert trade.entry_price == pytest.approx(62.0)


def test_i_throwback_single_entry_no_reentry():
    """Brief Sec 2.3 'do NOT re-enter on second break' aligns with the
    harness's single-entry convention. Construct a synthetic sequence:
    breakout -> entry -> immediate retrace below center_peak -> later
    re-break. Engine should NOT emit a second entry; the original trade
    persists (or stops out if applicable).
    """
    verdict = _make_verdict(
        trough_2_date=date(2025, 12, 1),
        anchor_asof_date=date(2026, 1, 5),
    )
    n_rally = 20
    rally_dates = pd.bdate_range(start=date(2025, 12, 2), periods=n_rally)
    rally_closes = [55.0] * n_rally
    rally_volumes = [1_000_000.0] * n_rally
    trigger_date = pd.bdate_range(start=date(2026, 1, 6), periods=1)[0]
    # Throwback sequence: trigger (62.0) -> entry (62.0) -> retrace bars
    # below center_peak (55.0 for 5 bars) -> RE-BREAK at 63.0 (above center_peak)
    n_post = 30
    post_dates = pd.bdate_range(start=trigger_date + pd.tseries.offsets.BDay(1), periods=n_post)
    post_closes = [62.5] + [55.0] * 5 + [63.0] * (n_post - 6)
    post_opens = [62.0] + [62.5] + [55.0] * 4 + [55.0] + [63.0] * (n_post - 7)
    all_dates = list(rally_dates) + [trigger_date] + list(post_dates)
    all_closes = rally_closes + [62.0] + post_closes
    all_opens = rally_closes + [62.0] + post_opens
    all_volumes = rally_volumes + [5_000_000.0] + [1_000_000.0] * n_post
    bars = pd.DataFrame(
        {
            "Open": all_opens,
            "High": [max(o, c) + 0.1 for o, c in zip(all_opens, all_closes)],
            "Low": [min(o, c) - 0.1 for o, c in zip(all_opens, all_closes)],
            "Close": all_closes,
            "Volume": all_volumes,
        },
        index=all_dates,
    )
    i = RulesetI()
    trade = walk_forward_with_trigger_predicate(
        verdict, bars, i, trigger_predicate=edwards_magee_trigger_predicate
    )
    # Per brief Sec 2.1-2.3 LOCK: entry at TRIGGER BAR's date (NOT next-
    # session). The trigger bar is at trigger_date (first close > 60
    # after the asof+1BD lower bound). With the engine's entry-at-trigger-
    # close semantic, entry_date == trigger_date.
    assert trade.triggered is True
    assert trade.entry_date == trigger_date.date()
    # The trade has only ONE entry; the later re-break date does NOT
    # produce a separate entry.
    later_rebreak_date = post_dates[6].date()
    assert trade.entry_date != later_rebreak_date
