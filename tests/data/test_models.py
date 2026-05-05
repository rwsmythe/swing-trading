"""Phase 2 model dataclass smoke test — instantiation + equality."""
from __future__ import annotations

from swing.data.models import (
    Trade, Fill, CashMovement, TradeEvent, WatchlistEntry,
    WatchlistArchiveEntry, WeatherRun, DailyRecommendation,
    PipelineRun, ConfigRevision,
)


def test_models_instantiate():
    t = Trade(id=None, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
              initial_shares=10, initial_stop=170.0, current_stop=170.0,
              state="entered", watchlist_entry_target=181.0,
              watchlist_initial_stop=170.0, notes=None)
    # Phase 7 Sub-A T3: `status` removed from Trade dataclass; replaced with
    # `state` machine. Smoke test now asserts the new field.
    assert t.ticker == "AAPL" and t.state == "entered"

    f = Fill(fill_id=None, trade_id=1, fill_datetime="2026-04-20T16:00:00",
             action="exit", quantity=10.0, price=190.0, reason="target",
             rule_based=None, fees=None, manual_entry_confidence=None)
    assert f.action == "exit" and f.quantity == 10.0

    cm = CashMovement(id=None, date="2026-04-01", kind="deposit",
                      amount=500.0, ref="DEP-001", note="initial funding")
    assert cm.kind == "deposit"

    te = TradeEvent(id=None, trade_id=1, ts="2026-04-15T09:30:00",
                    event_type="entry", payload_json='{"shares":10}',
                    rationale="VCP breakout")
    assert te.event_type == "entry"

    we = WatchlistEntry(ticker="MSFT", added_date="2026-04-10",
                        last_qualified_date="2026-04-15", status="watch",
                        qualification_count=3, not_qualified_streak=0,
                        last_data_asof_date="2026-04-15",
                        entry_target=420.0, initial_stop_target=410.0,
                        last_close=418.0, last_pivot=420.0, last_stop=410.0,
                        last_adr_pct=2.5, missing_criteria=None, notes=None)
    assert we.qualification_count == 3

    wa = WatchlistArchiveEntry(id=None, ticker="MSFT", added_date="2026-04-10",
                               removed_date="2026-04-20", reason="entered",
                               qualification_count=4, last_data_asof_date="2026-04-19",
                               notes=None)
    assert wa.reason == "entered"

    wr = WeatherRun(id=None, run_ts="2026-04-15T21:49:00",
                    asof_date="2026-04-15", ticker="QQQ", status="Bullish",
                    close=480.0, sma10=475.0, sma20=470.0, sma50=460.0,
                    slope20_5bar=0.5, slope10_5bar=0.7, rationale="all bullish")
    assert wr.status == "Bullish"

    dr = DailyRecommendation(id=None, evaluation_run_id=1,
                             data_asof_date="2026-04-15",
                             action_session_date="2026-04-16",
                             ticker="NVDA", recommendation="today_decision",
                             action_text="Buy-stop $850", entry_target=850.0,
                             stop_target=820.0, shares=2, risk_dollars=60.0,
                             risk_pct=0.5, rationale="VCP coil at 12-week base")
    assert dr.recommendation == "today_decision"

    pr = PipelineRun(id=None, started_ts="2026-04-15T21:49:00", finished_ts=None,
                     trigger="scheduled", data_asof_date="2026-04-15",
                     action_session_date="2026-04-16", state="running",
                     lease_token="abc-123", lease_heartbeat_ts="2026-04-15T21:49:30",
                     last_step_progress_ts="2026-04-15T21:50:00",
                     current_step="evaluate",
                     weather_status="ok", evaluation_status=None,
                     watchlist_status=None, recommendations_status=None,
                     charts_status=None, export_status=None,
                     rs_universe_version="2026-04-17-1",
                     rs_universe_hash="abcd",
                     finviz_csv_path="data/finviz-inbox/finviz15Apr2026.csv",
                     error_message=None, warnings_json=None)
    assert pr.state == "running"

    cr = ConfigRevision(id=None, ts="2026-04-15T22:00:00",
                        payload_json='{"vcp":{"adr_min_pct":4.5}}', source="cli")
    assert cr.source == "cli"
