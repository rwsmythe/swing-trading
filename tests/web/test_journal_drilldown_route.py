"""Phase 14 SB4 Slice 5 Task 5.5: journal trade drill-down route.

Two DISTINCT missing-trade contracts (Codex Re-R2 M#1):
  full page GET /journal/trades/{id}        -> 200 (exists) / 404 (missing)
  chart frag GET /journal/trades/{id}/chart -> 200+unavailable / 200+not-found
                                               (NOT 404)
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
def app_with_trade(tmp_path: Path):
    db_path = tmp_path / "drilldown.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        tid = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="VIR", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="managing",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-20T09:30:00",
                thesis="breakout", why_now="volume",
                invalidation_condition="loses 9"),
            event_ts="2026-04-20T09:30:00")
        insert_fill_with_event(
            conn,
            Fill(fill_id=None, trade_id=tid,
                 fill_datetime="2026-04-20T09:30:00", action="entry",
                 quantity=10.0, price=10.0),
            event_ts="2026-04-20T09:30:00")
    conn.close()
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    app = create_app(cfg)
    app.state._drilldown_trade_id = tid
    return app


def test_drilldown_page_200(app_with_trade):
    tid = app_with_trade.state._drilldown_trade_id
    with TestClient(app_with_trade) as client:
        r = client.get(f"/journal/trades/{tid}")
    assert r.status_code == 200
    assert "chronology" in r.text.lower()
    assert 'hx-get="/journal/trades/' in r.text and "/chart" in r.text


def test_drilldown_page_404_when_missing(app_with_trade):
    with TestClient(app_with_trade) as client:
        r = client.get("/journal/trades/999999")
    assert r.status_code == 404


def test_drilldown_chart_fragment_200_unavailable_when_missing(app_with_trade):
    with TestClient(app_with_trade) as client:
        r = client.get("/journal/trades/999999/chart",
                       headers={"HX-Request": "true"})
    # The fragment contract is 200 + distinct "not found" copy, NOT 404.
    assert r.status_code == 200 and "not found" in r.text.lower()


def test_drilldown_chart_fragment_200_svg(app_with_trade, monkeypatch):
    monkeypatch.setattr(
        "swing.web.routes.journal.render_trade_window_position_svg",
        lambda **k: b"<svg></svg>")
    tid = app_with_trade.state._drilldown_trade_id
    with TestClient(app_with_trade) as client:
        r = client.get(f"/journal/trades/{tid}/chart",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200 and "<svg" in r.text


def test_drilldown_chart_fragment_200_unavailable_render_none(
        app_with_trade, monkeypatch):
    monkeypatch.setattr(
        "swing.web.routes.journal.render_trade_window_position_svg",
        lambda **k: None)
    tid = app_with_trade.state._drilldown_trade_id
    with TestClient(app_with_trade) as client:
        r = client.get(f"/journal/trades/{tid}/chart")
    assert r.status_code == 200 and "unavailable" in r.text.lower()


def test_drilldown_chart_fragment_render_exception_isolated(
        app_with_trade, monkeypatch, caplog):
    def _boom(**k):
        raise RuntimeError("render blew up")

    monkeypatch.setattr(
        "swing.web.routes.journal.render_trade_window_position_svg", _boom)
    tid = app_with_trade.state._drilldown_trade_id
    with TestClient(app_with_trade) as client, caplog.at_level("WARNING"):
        r = client.get(f"/journal/trades/{tid}/chart")
    assert r.status_code == 200 and "unavailable" in r.text.lower()
