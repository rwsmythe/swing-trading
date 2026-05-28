"""Tests for g2_w_bottom_ruleset_backtest.scorecard (9-metric scorecard).

Per G2 dispatch brief Sec 1.4 + Sec 4.2 + Sec 4.4 (regression test arithmetic).

The scorecard reports nine metrics per (ruleset, substrate) cell:
  1. expectancy_R = sum(R per closed trade) / N_closed
  2. win_rate = N(R > 0 closed) / N_closed
  3. avg_win_R = mean(R) over closed-and-profitable trades
  4. avg_loss_R = abs(mean(R)) over closed-and-unprofitable trades
  5. profit_factor = sum(R from winners) / abs(sum(R from losers))
  6. trigger_conversion_rate = N_triggered / N_patterns
  7. median_time_in_trade_sessions = median(days_held) over closed trades
  8. open_at_tail_count = N(trades still open at data tail) / N_triggered
  9. estimated_dollar_per_period = N_triggered_per_year x expectancy_R x
       R_DOLLAR_SIZE_AT_7500_FLOOR ($75/R per brief Sec 11 Q4)

Edge cases:
  - 0 closed trades -> expectancy_R = None; win_rate = None; profit_factor
    = None; avg_win_R = None; avg_loss_R = None; median_time_in_trade = None
  - 0 triggered -> trigger_conversion_rate = 0.0; estimated_dollar_per_period
    = 0.0; open_at_tail_count = 0
  - 0 losses (all winners) -> profit_factor = None (sentinel)
  - 0 winners (all losers) -> avg_win_R = None

Discriminating arithmetic (per `feedback_verify_regression_test_arithmetic`):
  - expectancy_R test [+1, +1, -1, -1, -1]: canonical -0.2; buggy 'win-rate
    divided by total' would yield 0.4; assertions distinguish.
"""
from __future__ import annotations

from datetime import date

import pytest

from research.harness.g2_w_bottom_ruleset_backtest.scorecard import (
    R_DOLLAR_SIZE_AT_7500_FLOOR,
    ScorecardRow,
    build_scorecard_row,
)
from research.harness.w_bottom_ruleset_comparison.walkforward import Trade


def _make_trade(
    *,
    pattern_id: str = "TST-2025-12-01",
    ticker: str = "TST",
    ruleset_name: str = "G_bulkowski_double_bottom",
    triggered: bool = True,
    status: str = "closed",
    r_multiple: float | None = 1.0,
    days_held: int | None = 10,
    exit_reason: str = "target_measured_move",
) -> Trade:
    return Trade(
        pattern_id=pattern_id, ticker=ticker, ruleset_name=ruleset_name,
        anchor_asof_date=date(2026, 1, 5),
        trough_1_date=date(2025, 11, 1),
        center_peak_price=60.0,
        trough_2_price=52.0,
        composite_score=0.75,
        initial_stop=51.48,
        entry_date=date(2026, 1, 6) if triggered else None,
        entry_price=62.0 if triggered else None,
        exit_date=date(2026, 1, 16) if status == "closed" else None,
        exit_price=72.0 if status == "closed" else None,
        exit_reason=exit_reason,
        r_multiple=r_multiple,
        days_held=days_held,
        status=status,
        triggered=triggered,
        trade_pnl_dollars=37.5 if triggered else None,
        peak_unrealized_R=1.0,
        drawdown_to_exit_R=0.0,
        forward_bars_available=40,
        max_forward_close=72.0,
        max_close_pct_of_peak=120.0,
        days_t2_to_asof=35,
        effective_asof_date=date(2026, 1, 5),
        max_observed_asof_date=date(2026, 1, 5),
    )


def test_expectancy_R_arithmetic_discriminates_canonical_from_winrate_bug():
    """Input [+1, +1, -1, -1, -1] (5 closed; 2 wins; 3 losses).
    Canonical mean = (1+1-1-1-1)/5 = -0.2.
    Buggy 'win_rate / total' = 2/5 = 0.4 (POSITIVE).
    Assertion MUST distinguish.
    """
    trades = [
        _make_trade(pattern_id=f"p{i}", r_multiple=r)
        for i, r in enumerate([1.0, 1.0, -1.0, -1.0, -1.0])
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="r2a_synthetic",
        trades=trades,
        n_patterns=5,
        substrate_window_days=365,
    )
    assert row.expectancy_R == pytest.approx(-0.2)
    assert row.expectancy_R != pytest.approx(0.4)
    assert row.win_rate == pytest.approx(0.4)
    assert row.avg_win_R == pytest.approx(1.0)
    assert row.avg_loss_R == pytest.approx(1.0)  # abs(mean of losses) = abs(-1) = 1
    # profit_factor = sum_wins / abs(sum_losses) = 2 / 3 = 0.6667
    assert row.profit_factor == pytest.approx(2.0 / 3.0)
    assert row.median_time_in_trade_sessions == pytest.approx(10)
    assert row.trigger_conversion_rate == pytest.approx(1.0)


def test_zero_closed_trades_emits_none_sentinels():
    """When all triggered trades are 'open' (no closed), expectancy_R /
    win_rate / avg_win_R / avg_loss_R / profit_factor / median_time_in_trade
    are None."""
    trades = [
        _make_trade(pattern_id=f"p{i}", status="open", r_multiple=None,
                   days_held=None, exit_reason="open_at_data_tail")
        for i in range(3)
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="empty_closed",
        trades=trades,
        n_patterns=3,
        substrate_window_days=365,
    )
    assert row.expectancy_R is None
    assert row.win_rate is None
    assert row.avg_win_R is None
    assert row.avg_loss_R is None
    assert row.profit_factor is None
    assert row.median_time_in_trade_sessions is None
    assert row.trigger_conversion_rate == pytest.approx(1.0)
    assert row.open_at_tail_count == 3


def test_zero_triggered_emits_zero_conversion_and_zero_dollar():
    """When no trades triggered (all untriggered): trigger_conversion_rate
    = 0.0; estimated_dollar_per_period = 0.0; open_at_tail_count = 0."""
    trades = [
        _make_trade(pattern_id=f"p{i}", triggered=False, status="untriggered",
                   r_multiple=None, days_held=None, exit_reason="untriggered")
        for i in range(5)
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="all_untriggered",
        trades=trades,
        n_patterns=5,
        substrate_window_days=365,
    )
    assert row.trigger_conversion_rate == pytest.approx(0.0)
    assert row.estimated_dollar_per_period == pytest.approx(0.0)
    assert row.open_at_tail_count == 0
    # No closed trades either
    assert row.expectancy_R is None
    assert row.win_rate is None


def test_zero_losses_profit_factor_is_none_sentinel():
    """When all closed trades are winners (no losses), profit_factor is
    None (cannot divide by zero loss-magnitude)."""
    trades = [
        _make_trade(pattern_id=f"p{i}", r_multiple=r)
        for i, r in enumerate([1.0, 2.0, 0.5])
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="all_winners",
        trades=trades,
        n_patterns=3,
        substrate_window_days=365,
    )
    assert row.profit_factor is None
    assert row.avg_loss_R is None  # no losses; mean undefined
    assert row.avg_win_R == pytest.approx((1.0 + 2.0 + 0.5) / 3.0)
    assert row.win_rate == pytest.approx(1.0)


def test_zero_winners_avg_win_R_is_none():
    """When all closed trades are losers, avg_win_R is None."""
    trades = [
        _make_trade(pattern_id=f"p{i}", r_multiple=r)
        for i, r in enumerate([-0.5, -1.0, -1.5])
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="all_losers",
        trades=trades,
        n_patterns=3,
        substrate_window_days=365,
    )
    assert row.avg_win_R is None
    assert row.avg_loss_R == pytest.approx(1.0)  # abs(-1.0)
    assert row.profit_factor == pytest.approx(0.0)  # sum_wins / abs(sum_losses) = 0/3 = 0
    assert row.win_rate == pytest.approx(0.0)


def test_open_at_tail_count_excludes_closed_and_untriggered():
    """open_at_tail_count counts ONLY trades with status='open'."""
    trades = [
        _make_trade(pattern_id="p1", status="closed", r_multiple=1.0),
        _make_trade(pattern_id="p2", status="open", r_multiple=None,
                   days_held=None, exit_reason="open_at_data_tail"),
        _make_trade(pattern_id="p3", status="open", r_multiple=None,
                   days_held=None, exit_reason="open_at_data_tail"),
        _make_trade(pattern_id="p4", triggered=False, status="untriggered",
                   r_multiple=None, days_held=None, exit_reason="untriggered"),
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="mixed",
        trades=trades,
        n_patterns=4,
        substrate_window_days=365,
    )
    assert row.open_at_tail_count == 2


def test_estimated_dollar_per_period_derivation_at_75_per_R():
    """estimated_dollar_per_period = N_triggered_per_year * expectancy_R *
    R_DOLLAR_SIZE_AT_7500_FLOOR.

    Setup: 10 patterns; 5 triggered + 5 untriggered; 5 closed; expectancy
    = +0.5R; substrate_window_days = 730 (2 years).
    N_triggered_per_year = (5 / 730) * 365 = 2.5
    estimated_dollar = 2.5 * 0.5 * 75 = $93.75
    """
    trades = (
        [_make_trade(pattern_id=f"win{i}", r_multiple=1.0) for i in range(3)]
        + [_make_trade(pattern_id=f"loss{i}", r_multiple=-0.25) for i in range(2)]
        + [_make_trade(pattern_id=f"ut{i}", triggered=False, status="untriggered",
                       r_multiple=None, days_held=None, exit_reason="untriggered")
           for i in range(5)]
    )
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="dollar_calc",
        trades=trades,
        n_patterns=10,
        substrate_window_days=730,
    )
    assert R_DOLLAR_SIZE_AT_7500_FLOOR == pytest.approx(75.0)
    # expectancy = (1+1+1-0.25-0.25)/5 = 2.5/5 = 0.5
    assert row.expectancy_R == pytest.approx(0.5)
    # N_triggered_per_year = (5 / 730) * 365 = 2.5
    expected_n_per_year = (5 / 730) * 365
    assert expected_n_per_year == pytest.approx(2.5)
    # estimated = 2.5 * 0.5 * 75 = 93.75
    assert row.estimated_dollar_per_period == pytest.approx(93.75)


def test_estimated_dollar_per_period_handles_none_expectancy():
    """When expectancy_R is None (no closed trades), estimated_dollar_per_period
    is None (cannot compute)."""
    trades = [
        _make_trade(pattern_id=f"p{i}", status="open", r_multiple=None,
                   days_held=None, exit_reason="open_at_data_tail")
        for i in range(3)
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="all_open",
        trades=trades,
        n_patterns=3,
        substrate_window_days=365,
    )
    assert row.expectancy_R is None
    assert row.estimated_dollar_per_period is None


def test_trigger_conversion_rate_n_triggered_over_n_patterns():
    """trigger_conversion_rate counts UNIQUE PATTERN entries (one ruleset's
    trades; not multiplied by N_rulesets)."""
    trades = [
        _make_trade(pattern_id=f"t{i}") for i in range(3)
    ] + [
        _make_trade(pattern_id=f"u{i}", triggered=False, status="untriggered",
                   r_multiple=None, days_held=None, exit_reason="untriggered")
        for i in range(2)
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="mixed_5",
        trades=trades,
        n_patterns=5,
        substrate_window_days=365,
    )
    assert row.trigger_conversion_rate == pytest.approx(3.0 / 5.0)


def test_median_time_in_trade_uses_only_closed_trades():
    """median_time_in_trade computed over CLOSED trades only (days_held);
    open + untriggered trades excluded."""
    trades = [
        _make_trade(pattern_id="c1", status="closed", days_held=5, r_multiple=1.0),
        _make_trade(pattern_id="c2", status="closed", days_held=10, r_multiple=-0.5),
        _make_trade(pattern_id="c3", status="closed", days_held=15, r_multiple=0.5),
        _make_trade(pattern_id="o1", status="open", days_held=None,
                   r_multiple=None, exit_reason="open_at_data_tail"),
        _make_trade(pattern_id="u1", triggered=False, status="untriggered",
                   days_held=None, r_multiple=None, exit_reason="untriggered"),
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="median_test",
        trades=trades,
        n_patterns=5,
        substrate_window_days=365,
    )
    # Median of [5, 10, 15] = 10
    assert row.median_time_in_trade_sessions == pytest.approx(10)


def test_substrate_window_days_zero_emits_none_dollar():
    """substrate_window_days=0 cannot extrapolate; estimated_dollar=None
    (when trades exist + are triggered)."""
    trades = [_make_trade(pattern_id="p1", r_multiple=1.0)]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="zero_window",
        trades=trades,
        n_patterns=1,
        substrate_window_days=0,
    )
    assert row.n_triggered == 1
    assert row.estimated_dollar_per_period is None


def test_scorecard_row_dataclass_shape_includes_all_9_metrics():
    """Verify all 9 metrics are fields on ScorecardRow.

    Per Codex R1 MAJOR #6 closure: open_at_tail surfaced as BOTH count
    (integer) and rate (fraction of n_triggered) to disambiguate brief
    Sec 1.4 line 100 (formula says rate; field name says count).
    """
    expected_fields = {
        "ruleset_name", "substrate_name", "n_patterns", "n_triggered",
        "n_closed", "expectancy_R", "win_rate", "avg_win_R", "avg_loss_R",
        "profit_factor", "trigger_conversion_rate",
        "median_time_in_trade_sessions", "open_at_tail_count",
        "open_at_tail_rate",
        "estimated_dollar_per_period", "substrate_window_days",
    }
    actual_fields = set(ScorecardRow.__dataclass_fields__.keys())
    missing = expected_fields - actual_fields
    assert not missing, f"missing fields: {missing}"


def test_open_at_tail_rate_derivation():
    """open_at_tail_rate = open_at_tail_count / n_triggered;
    None when n_triggered == 0."""
    trades = [
        _make_trade(pattern_id="c1", status="closed", r_multiple=1.0),
        _make_trade(pattern_id="o1", status="open", r_multiple=None,
                   days_held=None, exit_reason="open_at_data_tail"),
        _make_trade(pattern_id="o2", status="open", r_multiple=None,
                   days_held=None, exit_reason="open_at_data_tail"),
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="rate_test",
        trades=trades,
        n_patterns=3,
        substrate_window_days=365,
    )
    assert row.open_at_tail_count == 2
    assert row.n_triggered == 3
    assert row.open_at_tail_rate == pytest.approx(2.0 / 3.0)


def test_open_at_tail_rate_none_when_zero_triggered():
    """When no triggered trades, rate is None (cannot divide by zero)."""
    trades = [
        _make_trade(pattern_id="u1", triggered=False, status="untriggered",
                   r_multiple=None, days_held=None, exit_reason="untriggered"),
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="all_untrig",
        trades=trades,
        n_patterns=1,
        substrate_window_days=365,
    )
    assert row.open_at_tail_count == 0
    assert row.n_triggered == 0
    assert row.open_at_tail_rate is None


def test_filter_to_one_ruleset_when_multiple_rulesets_passed():
    """build_scorecard_row consumes ONLY trades whose ruleset_name matches
    the requested ruleset_name; other rulesets' trades are filtered out."""
    trades = [
        _make_trade(pattern_id="g1", ruleset_name="G_bulkowski_double_bottom",
                   r_multiple=2.0),
        _make_trade(pattern_id="g2", ruleset_name="G_bulkowski_double_bottom",
                   r_multiple=-1.0),
        # Other ruleset's trades should be ignored
        _make_trade(pattern_id="e1", ruleset_name="E_oneil_cup_with_handle",
                   r_multiple=10.0),
        _make_trade(pattern_id="e2", ruleset_name="E_oneil_cup_with_handle",
                   r_multiple=10.0),
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="mixed_rulesets",
        trades=trades,
        n_patterns=2,
        substrate_window_days=365,
    )
    # Only G's trades counted: expectancy = (2 + -1) / 2 = 0.5
    assert row.expectancy_R == pytest.approx(0.5)
    assert row.n_closed == 2
    assert row.n_triggered == 2


def test_scorecard_filters_out_error_and_ohlcv_empty_exit_reasons():
    """Trades with exit_reason in {ohlcv_missing, ohlcv_empty,
    second_scaleout_invalid} are administrative sentinels; they should
    NOT count toward closed/triggered metrics that reflect strategy
    performance. They still count as a pattern (in n_patterns)."""
    trades = [
        _make_trade(pattern_id="ok1", r_multiple=1.0),
        _make_trade(pattern_id="m1", triggered=False, status="untriggered",
                   r_multiple=None, days_held=None, exit_reason="ohlcv_missing"),
        _make_trade(pattern_id="e1", triggered=False, status="untriggered",
                   r_multiple=None, days_held=None, exit_reason="ohlcv_empty"),
    ]
    row = build_scorecard_row(
        ruleset_name="G_bulkowski_double_bottom",
        substrate_name="with_sentinels",
        trades=trades,
        n_patterns=3,
        substrate_window_days=365,
    )
    # n_triggered ignores the ohlcv_missing + ohlcv_empty sentinels
    assert row.n_triggered == 1
    assert row.n_closed == 1
    assert row.expectancy_R == pytest.approx(1.0)
