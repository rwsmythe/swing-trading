"""build_briefing_view_model: assembles BriefingViewModel from primitive inputs."""
from __future__ import annotations

from datetime import date

from swing.data.models import (
    Candidate, DailyRecommendation, Trade, WatchlistEntry, WeatherRun,
)
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model


def _wr() -> WeatherRun:
    return WeatherRun(id=1, run_ts="2026-04-15T21:49:00", asof_date="2026-04-15",
                      ticker="QQQ", status="Bullish", close=480.0,
                      sma10=475.0, sma20=470.0, sma50=460.0,
                      slope20_5bar=0.5, slope10_5bar=0.7,
                      rationale="20MA rising; 10>20.")


def _rec(ticker: str = "NVDA") -> DailyRecommendation:
    return DailyRecommendation(
        id=1, evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", ticker=ticker,
        recommendation="today_decision",
        action_text="Buy-stop $850 \u00b7 2 sh \u00b7 $60 risk",
        entry_target=850.0, stop_target=820.0, shares=2,
        risk_dollars=60.0, risk_pct=5.0,
        rationale="VCP coil at 12-week base",
    )


def test_minimal_briefing():
    vm = build_briefing_view_model(BriefingInputs(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        weather=_wr(),
        weather_is_stale=False,
        equity=1284.50, open_count=1, soft_warn=4, hard_cap=6,
        last_pipeline_ts="2026-04-15T21:49:00",
        pipeline_is_stale=False, current_session_match=True,
        recommendations=[_rec()],
        open_trades=[], open_trade_advisories={},
        open_trade_last_prices={},
        watchlist=[], watchlist_last_prices={},
        candidates_by_ticker={},
        chart_b64s={},
    ))
    assert vm.action_session_date == "2026-04-16"
    assert vm.status_strip.weather.status == "Bullish"
    assert vm.status_strip.weather.sizing_implication.lower().startswith("full")
    assert len(vm.todays_decisions) == 1
    assert vm.todays_decisions[0].ticker == "NVDA"


def test_caution_weather_changes_sizing_implication():
    wr = _wr()
    cautious_wr = WeatherRun(
        id=wr.id, run_ts=wr.run_ts, asof_date=wr.asof_date, ticker=wr.ticker,
        status="Caution", close=wr.close, sma10=wr.sma10, sma20=wr.sma20,
        sma50=wr.sma50, slope20_5bar=wr.slope20_5bar, slope10_5bar=wr.slope10_5bar,
        rationale="20MA flat",
    )
    vm = build_briefing_view_model(BriefingInputs(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        weather=cautious_wr, weather_is_stale=False,
        equity=1284.50, open_count=1, soft_warn=4, hard_cap=6,
        last_pipeline_ts="2026-04-15T21:49:00",
        pipeline_is_stale=False, current_session_match=True,
        recommendations=[_rec()],
        open_trades=[], open_trade_advisories={},
        open_trade_last_prices={},
        watchlist=[], watchlist_last_prices={},
        candidates_by_ticker={},
        chart_b64s={},
    ))
    assert "half" in vm.status_strip.weather.sizing_implication.lower() \
        or "tighten" in vm.status_strip.weather.sizing_implication.lower()


def test_stale_weather_marker():
    vm = build_briefing_view_model(BriefingInputs(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        weather=None, weather_is_stale=True,
        equity=1200.0, open_count=0, soft_warn=4, hard_cap=6,
        last_pipeline_ts="2026-04-15T21:49:00",
        pipeline_is_stale=False, current_session_match=True,
        recommendations=[], open_trades=[], open_trade_advisories={},
        open_trade_last_prices={},
        watchlist=[], watchlist_last_prices={},
        candidates_by_ticker={},
        chart_b64s={},
    ))
    assert vm.status_strip.weather.status == "STALE" or "stale" in vm.status_strip.weather.rationale.lower()
