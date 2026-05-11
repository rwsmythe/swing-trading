"""Stop-advisory rules — 7 functions + aggregator."""
from __future__ import annotations

import pandas as pd

from swing.config import StopAdvisoryConfig
from swing.data.models import Trade
from swing.trades.advisory import (
    AdvisoryContext, AdvisorySuggestion, compute_all_suggestions,
    suggest_breakeven, suggest_trail_ma, suggest_exit_close_below_ma,
    suggest_weather_action, suggest_time_stop,
)


def test_advisory_context_accepts_adr_pct_field():
    """3e.8 Bundle 2 — AdvisoryContext gains adr_pct field for §4.D parabolic."""
    ctx = AdvisoryContext(
        as_of_date="2026-04-15", current_price=100.0,
        sma10=None, sma20=None, sma50=None, previous_close=None,
        weather_status="Bullish", config=StopAdvisoryConfig(),
        adr_pct=5.0,
    )
    assert ctx.adr_pct == 5.0


def test_advisory_context_adr_pct_defaults_to_none():
    ctx = AdvisoryContext(
        as_of_date="2026-04-15", current_price=100.0,
        sma10=None, sma20=None, sma50=None, previous_close=None,
        weather_status="Bullish", config=StopAdvisoryConfig(),
    )
    assert ctx.adr_pct is None


def test_advisory_context_accepts_has_been_trimmed_field():
    ctx = AdvisoryContext(
        as_of_date="2026-04-15", current_price=100.0,
        sma10=None, sma20=None, sma50=None, previous_close=None,
        weather_status="Bullish", config=StopAdvisoryConfig(),
        has_been_trimmed=True,
    )
    assert ctx.has_been_trimmed is True


def test_advisory_context_has_been_trimmed_defaults_to_false():
    ctx = AdvisoryContext(
        as_of_date="2026-04-15", current_price=100.0,
        sma10=None, sma20=None, sma50=None, previous_close=None,
        weather_status="Bullish", config=StopAdvisoryConfig(),
    )
    assert ctx.has_been_trimmed is False


def _trade(*, current_stop: float = 170.0, entry: float = 180.0, days: int = 0) -> Trade:
    from datetime import date, timedelta
    entry_date = (date.fromisoformat("2026-04-15") - timedelta(days=days)).isoformat()
    return Trade(
        id=1, ticker="AAPL", entry_date=entry_date, entry_price=entry,
        initial_shares=10, initial_stop=170.0, current_stop=current_stop,
        state="entered", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )


def _ctx(close: float = 195.0, ma10: float = 190.0, ma20: float = 185.0,
         ma50: float | None = None, prev_close: float | None = None,
         weather: str = "Bullish") -> AdvisoryContext:
    return AdvisoryContext(
        as_of_date="2026-04-15", current_price=close,
        sma10=ma10, sma20=ma20, sma50=ma50,
        previous_close=prev_close,
        weather_status=weather,
        config=StopAdvisoryConfig(),
    )


def test_breakeven_suggested_at_1r():
    s = suggest_breakeven(_trade(), _ctx(close=190.0))
    assert s is not None
    assert "breakeven" in s.message.lower()
    assert "180" in s.message


def test_breakeven_not_suggested_when_already_at_or_above_entry():
    s = suggest_breakeven(_trade(current_stop=180.0), _ctx(close=200.0))
    assert s is None


def test_breakeven_not_suggested_below_1r():
    s = suggest_breakeven(_trade(), _ctx(close=185.0))
    assert s is None


def test_trail_10ma_suggested():
    s = suggest_trail_ma(_trade(), _ctx(close=195.0, ma10=190.0),
                         ma_value=190.0, ma_label="10MA",
                         buffer_pct=0.3)
    assert s is not None
    assert "10MA" in s.message
    assert "189.43" in s.message or "189.4" in s.message


def test_trail_ma_no_op_when_below_ma():
    s = suggest_trail_ma(_trade(), _ctx(close=185.0, ma10=190.0),
                         ma_value=190.0, ma_label="10MA",
                         buffer_pct=0.3)
    assert s is None


def test_exit_close_below_ma():
    s = suggest_exit_close_below_ma(
        _trade(),
        _ctx(close=185.0, ma10=190.0, prev_close=187.0),   # was: no prev_close arg
        ma_value=190.0, ma_label="10MA",
    )
    assert s is not None
    assert "EXIT" in s.message
    assert "10MA" in s.message
    assert "187.00" in s.message  # previous_close echoed


def test_weather_caution_action():
    s = suggest_weather_action(_trade(), _ctx(weather="Caution"))
    assert s is not None
    assert "caution" in s.message.lower() or "tighten" in s.message.lower()


def test_weather_bearish_action():
    s = suggest_weather_action(_trade(), _ctx(weather="Bearish"))
    assert s is not None
    assert "bearish" in s.message.lower() or "exit" in s.message.lower()


def test_weather_bullish_no_action():
    assert suggest_weather_action(_trade(), _ctx(weather="Bullish")) is None


def test_time_stop_triggers_after_n_days_with_low_r():
    t = _trade(days=11)
    s = suggest_time_stop(t, _ctx(close=183.0))
    assert s is not None
    assert "time" in s.message.lower()


def test_time_stop_not_triggered_when_r_high_enough():
    t = _trade(days=11)
    assert suggest_time_stop(t, _ctx(close=195.0)) is None


def test_compute_all_suggestions_aggregates_non_none():
    sugs = compute_all_suggestions(_trade(), _ctx(close=190.0, ma10=185.0, ma20=180.0))
    rules = {s.rule for s in sugs}
    assert "breakeven" in rules


def test_exit_close_below_ma_uses_previous_close_not_current():
    """Spec §3.3: exit rule now fires on yesterday's DAILY close vs MA,
    not on intraday current_price. If previous_close is above MA but
    current_price is below, the rule must NOT fire."""
    # current_price 185 (below 190 MA) but previous_close 195 (above) → no exit.
    s = suggest_exit_close_below_ma(
        _trade(),
        _ctx(close=185.0, ma10=190.0, prev_close=195.0),
        ma_value=190.0, ma_label="10MA",
    )
    assert s is None


def test_exit_close_below_ma_noops_when_previous_close_is_none():
    """Graceful degradation: missing previous_close → rule no-ops."""
    s = suggest_exit_close_below_ma(
        _trade(),
        _ctx(close=185.0, ma10=190.0, prev_close=None),
        ma_value=190.0, ma_label="10MA",
    )
    assert s is None


def test_exit_below_50ma_fires_on_previous_close_below():
    """SMA50 exit rule (Minervini) fires when yesterday's close < SMA50."""
    s = suggest_exit_close_below_ma(
        _trade(),
        _ctx(close=200.0, ma50=195.0, prev_close=190.0),
        ma_value=195.0, ma_label="50MA",
    )
    assert s is not None
    assert "EXIT" in s.message
    assert "50MA" in s.message
    assert "190.00" in s.message  # previous_close echoed in message


def test_exit_below_50ma_noops_when_sma50_is_none():
    """Missing SMA50 → rule no-ops."""
    s = suggest_exit_close_below_ma(
        _trade(),
        _ctx(close=200.0, ma50=None, prev_close=190.0),
        ma_value=None, ma_label="50MA",
    )
    assert s is None


def test_compute_all_suggestions_includes_50ma_exit():
    """compute_all_suggestions now calls suggest_exit_close_below_ma for 50MA."""
    ctx = _ctx(close=200.0, ma10=198.0, ma20=196.0, ma50=195.0, prev_close=190.0)
    sugs = compute_all_suggestions(_trade(), ctx)
    rules = {s.rule for s in sugs}
    assert "exit_below_50ma" in rules


def test_trail_ma_extinguishes_when_stop_meets_displayed_target():
    """Bug 2 regression: displayed target must equal actual extinction threshold.

    Round-trip: fire the advisory, parse the displayed "Trail stop up to $X.YZ"
    value from the message, set current_stop to exactly that value, re-fire, and
    assert the advisory clears. Pre-fix, raw proposed = 10.334 * 0.997 = 10.302998
    displays as "$10.30" but the extinction threshold is 10.302998, so a stop set
    to the displayed value does NOT extinguish — this test fails. Post-fix, the
    ceiling rounds proposed to 10.31 so the display matches the threshold and the
    round trip extinguishes.
    """
    import re
    ctx = _ctx(close=11.00, ma10=10.334)
    first = suggest_trail_ma(
        _trade(current_stop=9.00, entry=9.50),
        ctx, ma_value=ctx.sma10, ma_label="10MA", buffer_pct=0.3,
    )
    assert first is not None, "precondition: advisory fires for a low stop"
    match = re.search(r"Trail stop up to \$(\d+\.\d{2})", first.message)
    assert match, f"could not parse displayed target from {first.message!r}"
    displayed_target = float(match.group(1))

    # User acts on the advisory by setting current_stop to the displayed value.
    second = suggest_trail_ma(
        _trade(current_stop=displayed_target, entry=9.50),
        ctx, ma_value=ctx.sma10, ma_label="10MA", buffer_pct=0.3,
    )
    assert second is None, (
        f"advisory should extinguish when stop is set to the displayed target "
        f"${displayed_target:.2f}, but it persists"
    )


def test_trail_ma_fires_when_stop_one_cent_below_ceiling_target():
    """Companion to the extinction test: confirms the new ceiling threshold
    correctly still fires when the stop is one cent below the displayed target.
    Also documents that the displayed target is the ceiling ($10.31), not the
    truncation ($10.30) — this is the user-visible behavior change.
    """
    trade = _trade(current_stop=10.30, entry=9.50)
    ctx = _ctx(close=11.00, ma10=10.334)
    result = suggest_trail_ma(
        trade, ctx, ma_value=ctx.sma10, ma_label="10MA", buffer_pct=0.3,
    )
    assert result is not None
    assert "10.31" in result.message, (
        "displayed target must be the ceiling-rounded cent, not the truncation"
    )
