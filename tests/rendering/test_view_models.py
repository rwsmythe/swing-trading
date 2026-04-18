"""View model dataclasses — instantiation + sub-component shape."""
from __future__ import annotations

from swing.rendering.view_models import (
    BriefingViewModel, StatusStripVM, WeatherTileVM, AccountTileVM,
    PipelineTileVM, TodaysDecisionVM, OpenPositionVM, AdvisorySuggestionVM,
    WatchlistRowVM, TickerExpansionVM, CriterionVM,
)


def test_briefing_viewmodel_instantiates():
    vm = BriefingViewModel(
        action_session_date="2026-04-16",
        data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status="Bullish", rationale="20MA rising; 10>20.",
                                   sizing_implication="Full sizing OK"),
            account=AccountTileVM(equity=1284.50, open_count=1, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="2026-04-15T21:49:00",
                                    is_stale=False, current_session_match=True),
        ),
        todays_decisions=[
            TodaysDecisionVM(ticker="NVDA", action_text="Buy-stop $850 \u00b7 2 sh",
                             entry_target=850.0, stop_target=820.0,
                             shares=2, risk_dollars=60.0, risk_pct=4.7,
                             rationale="VCP coil at 12-week base",
                             tt_score="7/8", vcp_score="10/10",
                             chart_b64=None),
        ],
        open_positions=[],
        watchlist=[],
        expansions=[],
    )
    assert vm.action_session_date == "2026-04-16"
    assert vm.status_strip.weather.status == "Bullish"
    assert vm.todays_decisions[0].shares == 2


def test_open_position_with_advisory():
    op = OpenPositionVM(
        ticker="AAPL", entry_price=180.0, current_stop=185.0, last_close=192.0,
        shares=10, unrealized_pnl=120.0, dist_to_stop_pct=3.6, r_so_far=1.2,
        days_open=8,
        advisory=[
            AdvisorySuggestionVM(rule="breakeven", message="Move stop to breakeven ($180)"),
            AdvisorySuggestionVM(rule="trail_10ma", message="Trail to $189.50 (-0.3% below 10MA)"),
        ],
    )
    assert len(op.advisory) == 2
    assert op.r_so_far == 1.2


def test_watchlist_row_with_near_trigger_flag():
    row = WatchlistRowVM(
        ticker="MSFT", entry_target=420.0, current_close=419.0,
        pct_to_pivot=-0.24, adr_pct=2.5, current_stop=410.0,
        is_near_trigger=True, status="watch",
        flag_tags=["TT\u2713", "VCP\u2713"], qualification_count=3,
    )
    assert row.is_near_trigger is True
    assert "TT\u2713" in row.flag_tags


def test_ticker_expansion():
    exp = TickerExpansionVM(
        ticker="NVDA", narrative="VCP coil; 12-week base; 65% prior trend.",
        trend_template_grid=[CriterionVM(name="TT1", result="pass", value="close>150MA AND close>200MA", rule="...")],
        vcp_grid=[CriterionVM(name="prior_trend", result="pass", value="65%", rule=">=25%")],
        chart_b64="data:image/png;base64,iVBOR...",
    )
    assert exp.ticker == "NVDA"
