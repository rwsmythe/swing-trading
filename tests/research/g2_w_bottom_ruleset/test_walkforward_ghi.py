"""Tests for g2_w_bottom_ruleset_backtest.walkforward_ghi.

The g2 variant of walk_forward accepts a per-ruleset `trigger_predicate(bars,
candidate_idx, verdict) -> bool` that gates whether a candidate trigger-bar
(close > center_peak) is admitted as the entry trigger. If the predicate
rejects, the engine continues searching forward through the trigger window.

Discriminating tests:
  - predicate that always-True reproduces the existing walk_forward behavior
    on a synthetic W with a clean breakout
  - predicate that rejects the FIRST candidate but admits the SECOND triggers
    on the second candidate
  - predicate that rejects ALL candidates emits exit_reason='untriggered'
  - non-callable predicate raises TypeError at the entrypoint
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.g2_w_bottom_ruleset_backtest.walkforward_ghi import (
    walk_forward_with_trigger_predicate,
)
from research.harness.w_bottom_ruleset_comparison.rulesets import RulesetE
from research.harness.w_bottom_ruleset_comparison.walkforward import (
    walk_forward as walk_forward_legacy,
)


def _make_verdict(
    *,
    ticker: str = "TST",
    anchor_asof_date: date = date(2026, 1, 5),
    trough_1_date: date = date(2025, 12, 1),
    trough_1_price: float = 50.0,
    center_peak_date: date = date(2025, 12, 15),
    center_peak_price: float = 60.0,
    trough_2_date: date = date(2025, 12, 29),
    trough_2_price: float = 52.0,
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


def _make_bars_w_breakout(
    *,
    start: date = date(2026, 1, 6),
    n_bars: int = 90,
    breakout_at: int = 5,
    breakout_close: float = 62.0,
    breakout_volume: float = 2_000_000.0,
    baseline_volume: float = 1_000_000.0,
    target_close: float = 70.0,
) -> pd.DataFrame:
    """Synthetic bar sequence beginning AFTER trigger_lower_bound_date.

    Bars 0..breakout_at-1 hold flat below center_peak; bar `breakout_at`
    closes above center_peak (60.0) at `breakout_close`; subsequent bars
    drift up to target_close. Volume = baseline_volume EXCEPT the breakout
    bar at `breakout_volume`. Open == Close for simplicity; entry is at the
    NEXT bar's Open per the harness convention.
    """
    dates = pd.bdate_range(start=start, periods=n_bars)
    closes = [55.0] * n_bars  # below center_peak (60)
    opens = [55.0] * n_bars
    volumes = [baseline_volume] * n_bars
    closes[breakout_at] = breakout_close
    opens[breakout_at] = breakout_close
    volumes[breakout_at] = breakout_volume
    # Entry bar (breakout_at + 1) opens at breakout_close; drift to target
    if breakout_at + 1 < n_bars:
        opens[breakout_at + 1] = breakout_close
        closes[breakout_at + 1] = breakout_close + 0.5
    for i in range(breakout_at + 2, n_bars):
        opens[i] = closes[i - 1]
        closes[i] = min(closes[i - 1] + 0.5, target_close)
    highs = [max(o, c) + 0.10 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 0.10 for o, c in zip(opens, closes)]
    df = pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )
    return df


def test_always_true_predicate_g2_enters_at_trigger_close_legacy_at_next_open():
    """Per brief Sec 2.1-2.3 LOCK: g2's walk_forward_with_trigger_predicate
    enters at the TRIGGER BAR's close (one bar earlier than legacy's
    next-session-open convention). This test asserts the divergence
    intentionally.

    With breakout at bar idx 5: legacy enters at bar 6 open; g2 enters at
    bar 5 close. The entry dates differ by 1 trading day.
    """
    verdict = _make_verdict()
    bars = _make_bars_w_breakout()
    ruleset = RulesetE()
    trade_legacy = walk_forward_legacy(verdict, bars, ruleset)
    trade_ghi = walk_forward_with_trigger_predicate(
        verdict, bars, ruleset, trigger_predicate=lambda b, i, v: True
    )
    # Per brief LOCK: g2 entry date is one bar EARLIER than legacy
    # (legacy uses next-session open; g2 uses trigger-bar close).
    # Both trigger on the same breakout bar; entry dates differ by 1 bar.
    assert trade_ghi.entry_date != trade_legacy.entry_date
    # g2 entry_price = trigger bar's close; legacy entry_price = next bar's open
    # In our synthetic, trigger bar close = breakout_close = 62.0
    # and next bar open also = breakout_close = 62.0 (synthetic). So
    # entry_price IS THE SAME here but for a different reason.
    assert trade_ghi.entry_price == pytest.approx(62.0)
    assert trade_ghi.triggered is True
    assert trade_legacy.triggered is True


def test_g2_engine_entry_date_matches_trigger_bar_not_next():
    """Per brief LOCK: g2 enters at TRIGGER BAR (NOT trigger+1). Verifies
    the entry semantic with a synthetic W."""
    verdict = _make_verdict()
    bars = _make_bars_w_breakout(breakout_at=5)
    ruleset = RulesetE()
    trade = walk_forward_with_trigger_predicate(
        verdict, bars, ruleset, trigger_predicate=lambda b, i, v: True
    )
    # Trigger bar is at idx 5; entry_date should be bars.index[5].date()
    expected_entry_date = bars.index[5].date()
    assert trade.entry_date == expected_entry_date
    # entry_price = close at idx 5 = breakout_close (default 62.0)
    assert trade.entry_price == pytest.approx(62.0)


def test_predicate_rejects_first_admits_second_triggers_on_second():
    """Reject the FIRST candidate-trigger bar; engine continues forward to
    the next eligible bar that passes BOTH close>threshold AND predicate."""
    verdict = _make_verdict()
    # Two breakouts: bar 5 (first) and bar 10 (second). Inject by keeping
    # close > center_peak on bars 5 and 10 only; bars between dip back below.
    bars = _make_bars_w_breakout(breakout_at=5)
    # Set bar 6..9 closes back below center_peak (60) so they don't trigger
    bars.iloc[6:10, bars.columns.get_loc("Close")] = 55.0
    bars.iloc[6:10, bars.columns.get_loc("Open")] = 55.0
    # Second breakout at bar 10
    bars.iloc[10, bars.columns.get_loc("Close")] = 63.0
    bars.iloc[10, bars.columns.get_loc("Open")] = 63.0
    bars.iloc[10, bars.columns.get_loc("Volume")] = 1_800_000.0
    # Predicate rejects bar 5 but accepts bar 10
    rejected_indices = []

    def predicate(bars_df, idx, v):
        rejected_indices.append(idx)
        return idx >= 10

    ruleset = RulesetE()
    trade = walk_forward_with_trigger_predicate(
        verdict, bars, ruleset, trigger_predicate=predicate
    )
    assert 5 in rejected_indices
    assert 10 in rejected_indices
    # Per brief LOCK: entry at TRIGGER BAR (idx 10), not idx 11
    expected_entry_date = bars.index[10].date()
    assert trade.entry_date == expected_entry_date
    assert trade.triggered is True


def test_predicate_rejects_all_emits_untriggered():
    verdict = _make_verdict()
    bars = _make_bars_w_breakout(breakout_at=5)
    ruleset = RulesetE()
    trade = walk_forward_with_trigger_predicate(
        verdict, bars, ruleset, trigger_predicate=lambda b, i, v: False
    )
    assert trade.triggered is False
    assert trade.status == "untriggered"
    assert trade.entry_date is None


def test_non_callable_predicate_raises_type_error():
    verdict = _make_verdict()
    bars = _make_bars_w_breakout()
    ruleset = RulesetE()
    with pytest.raises(TypeError):
        walk_forward_with_trigger_predicate(
            verdict, bars, ruleset, trigger_predicate=None  # type: ignore[arg-type]
        )


def test_predicate_receives_correct_arguments():
    """Predicate signature: (bars_df, candidate_idx, verdict)."""
    verdict = _make_verdict()
    bars = _make_bars_w_breakout(breakout_at=5)
    ruleset = RulesetE()
    captured_args = []

    def predicate(bars_arg, idx_arg, verdict_arg):
        captured_args.append((bars_arg is bars, isinstance(idx_arg, int), verdict_arg is verdict))
        return True

    walk_forward_with_trigger_predicate(
        verdict, bars, ruleset, trigger_predicate=predicate
    )
    assert captured_args, "predicate should have been called at least once"
    # First admission call: verify shapes
    assert captured_args[0] == (True, True, True)
