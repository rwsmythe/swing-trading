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


# ----------------------------------------------------------------------
# 3e.8 Bundle 2 — §4.B suggest_trim_into_strength
# Entry 180, initial_stop 170 → 1R = $10. +1R fires at price ≥ 190.
# ----------------------------------------------------------------------

def test_suggest_trim_into_strength_returns_none_below_trigger_r():
    from swing.trades.advisory import suggest_trim_into_strength
    # Price 189.99 → 0.999R; below trigger 1.0R.
    s = suggest_trim_into_strength(_trade(), _ctx(close=189.99))
    assert s is None


def test_suggest_trim_into_strength_returns_none_when_already_trimmed():
    from swing.trades.advisory import suggest_trim_into_strength
    ctx = AdvisoryContext(
        as_of_date="2026-04-15", current_price=200.0,  # +2R; above trigger
        sma10=None, sma20=None, sma50=None, previous_close=None,
        weather_status="Bullish", config=StopAdvisoryConfig(),
        has_been_trimmed=True,
    )
    assert suggest_trim_into_strength(_trade(), ctx) is None


def test_suggest_trim_into_strength_fires_at_trigger_r_no_prior_trim():
    from swing.trades.advisory import suggest_trim_into_strength
    s = suggest_trim_into_strength(_trade(), _ctx(close=190.0))  # exactly +1R
    assert s is not None
    assert s.rule == "trim_into_strength"
    assert "1.00R" in s.message
    assert "25" in s.message  # trim_first_pct_default 0.25 → 25%


def test_suggest_trim_into_strength_fires_above_trigger_when_not_trimmed():
    from swing.trades.advisory import suggest_trim_into_strength
    s = suggest_trim_into_strength(_trade(), _ctx(close=200.0))  # +2R
    assert s is not None
    assert s.rule == "trim_into_strength"
    assert "2.00R" in s.message


def test_suggest_trim_into_strength_message_format():
    from swing.trades.advisory import suggest_trim_into_strength
    s = suggest_trim_into_strength(_trade(), _ctx(close=190.0))
    assert s is not None
    msg = s.message
    # Hard-anchored phrasing per §0.3 #1 message template.
    assert "trim" in msg.lower()
    assert "25%" in msg
    assert "sell-into-strength" in msg.lower()


# ----------------------------------------------------------------------
# 3e.8 Bundle 2 — §4.K suggest_planned_target_r_hit
# Entry 180, initial_stop 170 → 1R = $10. +2R fires at price ≥ 200.
# ----------------------------------------------------------------------

def _trade_with_target(planned_target_R: float | None) -> Trade:
    from datetime import date, timedelta
    entry_date = (date.fromisoformat("2026-04-15") - timedelta(days=0)).isoformat()
    return Trade(
        id=1, ticker="AAPL", entry_date=entry_date, entry_price=180.0,
        initial_shares=10, initial_stop=170.0, current_stop=170.0,
        state="entered", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        planned_target_R=planned_target_R,
    )


def test_suggest_planned_target_r_hit_returns_none_when_target_is_null():
    from swing.trades.advisory import suggest_planned_target_r_hit
    # Even at +5R, NULL planned_target_R suppresses the rule. Must NOT raise.
    s = suggest_planned_target_r_hit(_trade_with_target(None), _ctx(close=230.0))
    assert s is None


def test_suggest_planned_target_r_hit_returns_none_below_target():
    from swing.trades.advisory import suggest_planned_target_r_hit
    # Target 2.0R; price 199 → 1.9R; below target.
    s = suggest_planned_target_r_hit(_trade_with_target(2.0), _ctx(close=199.0))
    assert s is None


def test_suggest_planned_target_r_hit_fires_at_target_r():
    from swing.trades.advisory import suggest_planned_target_r_hit
    # Target 2.0R; price 200 → exactly +2R.
    s = suggest_planned_target_r_hit(_trade_with_target(2.0), _ctx(close=200.0))
    assert s is not None
    assert s.rule == "planned_target_r_hit"
    assert "2.0R" in s.message or "+2.0R" in s.message


def test_suggest_planned_target_r_hit_fires_above_target():
    from swing.trades.advisory import suggest_planned_target_r_hit
    s = suggest_planned_target_r_hit(_trade_with_target(2.0), _ctx(close=220.0))
    assert s is not None


def test_suggest_planned_target_r_hit_message_format():
    from swing.trades.advisory import suggest_planned_target_r_hit
    s = suggest_planned_target_r_hit(_trade_with_target(2.5), _ctx(close=210.0))
    assert s is not None
    msg = s.message
    assert "+2.5R" in msg
    assert "target" in msg.lower()


# ----------------------------------------------------------------------
# 3e.8 Bundle 2 — §4.D suggest_parabolic_trim
# Trigger: (price - sma50) / sma50 * 100 >= multiple * adr_pct.
# With multiple=7.0 and adr_pct=5%, the threshold extension is 35% above sma50.
# ----------------------------------------------------------------------

def _ctx_parabolic(
    *, close: float, sma50: float | None, adr_pct: float | None,
) -> AdvisoryContext:
    return AdvisoryContext(
        as_of_date="2026-04-15", current_price=close,
        sma10=None, sma20=None, sma50=sma50, previous_close=None,
        weather_status="Bullish", config=StopAdvisoryConfig(),
        adr_pct=adr_pct,
    )


def test_suggest_parabolic_trim_returns_none_when_adr_pct_none():
    from swing.trades.advisory import suggest_parabolic_trim
    s = suggest_parabolic_trim(
        _trade(), _ctx_parabolic(close=150.0, sma50=100.0, adr_pct=None),
    )
    assert s is None


def test_suggest_parabolic_trim_returns_none_when_sma50_none():
    from swing.trades.advisory import suggest_parabolic_trim
    s = suggest_parabolic_trim(
        _trade(), _ctx_parabolic(close=150.0, sma50=None, adr_pct=5.0),
    )
    assert s is None


def test_suggest_parabolic_trim_returns_none_when_price_below_sma50():
    from swing.trades.advisory import suggest_parabolic_trim
    s = suggest_parabolic_trim(
        _trade(), _ctx_parabolic(close=95.0, sma50=100.0, adr_pct=5.0),
    )
    assert s is None


def test_suggest_parabolic_trim_returns_none_when_extension_below_multiple():
    """6.9× ADR above sma50 → does NOT fire (just below 7.0× threshold)."""
    from swing.trades.advisory import suggest_parabolic_trim
    # sma50=100, adr_pct=5 → 1 ADR = $5 extension (5% of sma50).
    # Threshold extension = 7.0 × 5 = 35%. Below: 34.5% → close=134.5.
    s = suggest_parabolic_trim(
        _trade(), _ctx_parabolic(close=134.5, sma50=100.0, adr_pct=5.0),
    )
    assert s is None


def test_suggest_parabolic_trim_fires_at_7x_adr_above_50sma():
    """7.0× ADR exactly → fires (≥ comparison)."""
    from swing.trades.advisory import suggest_parabolic_trim
    # Threshold extension = 35% above sma50=100 → close=135.0.
    s = suggest_parabolic_trim(
        _trade(), _ctx_parabolic(close=135.0, sma50=100.0, adr_pct=5.0),
    )
    assert s is not None
    assert s.rule == "parabolic_trim"


def test_suggest_parabolic_trim_fires_above_7x_adr():
    from swing.trades.advisory import suggest_parabolic_trim
    # 7.1× ADR → 35.5% above; clearly above.
    s = suggest_parabolic_trim(
        _trade(), _ctx_parabolic(close=135.5, sma50=100.0, adr_pct=5.0),
    )
    assert s is not None


def test_suggest_parabolic_trim_message_format():
    from swing.trades.advisory import suggest_parabolic_trim
    s = suggest_parabolic_trim(
        _trade(), _ctx_parabolic(close=140.0, sma50=100.0, adr_pct=5.0),
    )
    assert s is not None
    msg = s.message
    assert "parabolic" in msg.lower()
    assert "ADR" in msg
    assert "50SMA" in msg or "50 SMA" in msg
    assert "DST" in msg or "D.7" in msg or "Realsimpleariel" in msg.lower()


def test_suggest_parabolic_trim_returns_none_when_adr_pct_is_nan():
    """ADR may be NaN when fewer than `lookback` bars available."""
    import math
    from swing.trades.advisory import suggest_parabolic_trim
    s = suggest_parabolic_trim(
        _trade(), _ctx_parabolic(close=200.0, sma50=100.0, adr_pct=math.nan),
    )
    assert s is None


# ----------------------------------------------------------------------
# 3e.8 Bundle 2 — compute_all_suggestions aggregator wiring
# ----------------------------------------------------------------------

def test_compute_all_suggestions_includes_trim_into_strength():
    """Aggregator picks up the new rule alongside existing ones."""
    sugs = compute_all_suggestions(_trade(), _ctx(close=190.0))
    rules = [s.rule for s in sugs]
    assert "trim_into_strength" in rules


def test_compute_all_suggestions_includes_planned_target_r_hit():
    trade = _trade_with_target(2.0)
    sugs = compute_all_suggestions(trade, _ctx(close=200.0))
    rules = [s.rule for s in sugs]
    assert "planned_target_r_hit" in rules


def test_compute_all_suggestions_includes_parabolic_trim():
    sugs = compute_all_suggestions(
        _trade(),
        _ctx_parabolic(close=140.0, sma50=100.0, adr_pct=5.0),
    )
    rules = [s.rule for s in sugs]
    assert "parabolic_trim" in rules


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
