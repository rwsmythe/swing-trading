"""Phase 14 SB4 Slice 0 Task 0.5: lazy review-chart fragment route.

Three response contracts:
  200 + <svg          (render produced bytes)
  200 + "unavailable" (render returned None -- no coverage)
  200 + "not found"   (distinct trade-not-found, with a WARNING log)
Plus: Cache-Control private; render exception isolated (logged, never raised).
"""
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


@pytest.fixture
def app_with_closed_trade(tmp_path: Path):
    db_path = tmp_path / "review_chart.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        tid = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="VIR", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-20T09:30:00"),
            event_ts="2026-04-20T09:30:00")
        insert_fill_with_event(
            conn,
            Fill(fill_id=None, trade_id=tid,
                 fill_datetime="2026-04-20T09:30:00", action="entry",
                 quantity=10.0, price=10.0),
            event_ts="2026-04-20T09:30:00")
        insert_fill_with_event(
            conn,
            Fill(fill_id=None, trade_id=tid,
                 fill_datetime="2026-04-25T15:00:00", action="exit",
                 quantity=10.0, price=11.5, reason="manual"),
            event_ts="2026-04-25T15:00:00")
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (tid,))
    conn.close()
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    app = create_app(cfg)
    app.state._review_chart_trade_id = tid
    return app


def test_review_chart_200_svg(app_with_closed_trade, monkeypatch):
    monkeypatch.setattr(
        "swing.web.routes.trades.render_trade_window_position_svg",
        lambda **k: b"<svg></svg>")
    tid = app_with_closed_trade.state._review_chart_trade_id
    with TestClient(app_with_closed_trade) as client:
        r = client.get(f"/trades/{tid}/review/chart",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200 and "<svg" in r.text
    assert "private" in r.headers.get("cache-control", "")


def test_review_chart_200_unavailable(app_with_closed_trade, monkeypatch):
    monkeypatch.setattr(
        "swing.web.routes.trades.render_trade_window_position_svg",
        lambda **k: None)
    tid = app_with_closed_trade.state._review_chart_trade_id
    with TestClient(app_with_closed_trade) as client:
        r = client.get(f"/trades/{tid}/review/chart")
    assert r.status_code == 200 and "unavailable" in r.text.lower()


def test_review_chart_200_not_found_distinct(app_with_closed_trade, caplog):
    with TestClient(app_with_closed_trade) as client, \
            caplog.at_level("WARNING"):
        r = client.get("/trades/999999/review/chart")
    assert r.status_code == 200 and "not found" in r.text.lower()
    assert any("999999" in rec.message for rec in caplog.records)


def test_review_chart_render_exception_isolated(app_with_closed_trade,
                                                monkeypatch, caplog):
    def _boom(**k):
        raise RuntimeError("render blew up")

    monkeypatch.setattr(
        "swing.web.routes.trades.render_trade_window_position_svg", _boom)
    tid = app_with_closed_trade.state._review_chart_trade_id
    with TestClient(app_with_closed_trade) as client, \
            caplog.at_level("WARNING"):
        r = client.get(f"/trades/{tid}/review/chart")
    # Exception is caught -> 200 + unavailable, never a 500.
    assert r.status_code == 200 and "unavailable" in r.text.lower()
