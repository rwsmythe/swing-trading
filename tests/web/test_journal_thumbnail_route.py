"""Phase 14 SB4 Slice 4 Task 4.2: GET /journal/trades/{id}/thumbnail.

Four response contracts (fragment is a <svg>/<span>, never a table element):
  200 + <svg          (render produced bytes)        -> private, max-age=<short>
  200 + unavailable   (render returned None)         -> private, max-age=<short>
  200 + not found     (trade missing, WARNING log)   -> private, max-age=<short>
  200 + busy          (render semaphore exhausted)    -> no-store + self-retry

The busy contract self-retries via hx-target=this / hx-swap=outerHTML and
releases its permits (try/finally). Render exceptions are isolated.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


def _seed_closed_trade(cfg) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="THM", entry_date="2026-04-15",
                    entry_price=10.0, initial_shares=100, initial_stop=9.0,
                    current_stop=9.0, state="closed",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-15T09:30:00",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None, trade_id=tid,
                    fill_datetime="2026-04-20T15:30:00",
                    action="exit", quantity=100, price=12.0, reason="target",
                ),
                event_ts="2026-04-20T15:30:00",
            )
    finally:
        conn.close()
    return tid


@pytest.fixture
def client_with_trade(seeded_db):
    cfg, cfg_path = seeded_db
    tid = _seed_closed_trade(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        client._trade_id = tid  # type: ignore[attr-defined]
        yield client


def test_thumbnail_200_svg(client_with_trade, monkeypatch):
    monkeypatch.setattr(
        "swing.web.routes.journal.render_trade_window_thumbnail_svg",
        lambda **k: b"<svg></svg>")
    tid = client_with_trade._trade_id
    r = client_with_trade.get(f"/journal/trades/{tid}/thumbnail",
                              headers={"HX-Request": "true"})
    assert r.status_code == 200 and "<svg" in r.text
    cache_control = r.headers.get("cache-control", "")
    assert "private" in cache_control and "max-age" in cache_control
    assert "no-store" not in cache_control


def test_thumbnail_200_unavailable(client_with_trade, monkeypatch):
    monkeypatch.setattr(
        "swing.web.routes.journal.render_trade_window_thumbnail_svg",
        lambda **k: None)
    tid = client_with_trade._trade_id
    r = client_with_trade.get(f"/journal/trades/{tid}/thumbnail")
    assert r.status_code == 200 and "unavailable" in r.text.lower()
    assert "private" in r.headers.get("cache-control", "")


def test_thumbnail_200_not_found(client_with_trade, caplog):
    with caplog.at_level("WARNING"):
        r = client_with_trade.get("/journal/trades/999999/thumbnail")
    assert r.status_code == 200 and "not found" in r.text.lower()
    assert any("999999" in rec.message for rec in caplog.records)


def test_thumbnail_render_exception_isolated(client_with_trade, monkeypatch,
                                             caplog):
    def _boom(**k):
        raise RuntimeError("render blew up")

    monkeypatch.setattr(
        "swing.web.routes.journal.render_trade_window_thumbnail_svg", _boom)
    tid = client_with_trade._trade_id
    with caplog.at_level("WARNING"):
        r = client_with_trade.get(f"/journal/trades/{tid}/thumbnail")
    assert r.status_code == 200 and "unavailable" in r.text.lower()


def test_thumbnail_busy_when_semaphore_exhausted(client_with_trade, caplog):
    # Force the semaphore to time out by holding all permits, then assert the
    # 200+busy contract: busy body, no-store cache, self-retry trigger,
    # structured WARNING, and that permits are released afterward.
    import swing.web.routes.journal as J
    monkeypatch_timeout = 0.05
    orig_timeout = J._THUMBNAIL_RENDER_TIMEOUT_S
    J._THUMBNAIL_RENDER_TIMEOUT_S = monkeypatch_timeout
    J._THUMBNAIL_RENDER_SEMAPHORE.acquire()
    J._THUMBNAIL_RENDER_SEMAPHORE.acquire()  # both permits held
    tid = client_with_trade._trade_id
    try:
        with caplog.at_level("WARNING"):
            r = client_with_trade.get(f"/journal/trades/{tid}/thumbnail",
                                      headers={"HX-Request": "true"})
    finally:
        J._THUMBNAIL_RENDER_SEMAPHORE.release()
        J._THUMBNAIL_RENDER_SEMAPHORE.release()
        J._THUMBNAIL_RENDER_TIMEOUT_S = orig_timeout
    assert r.status_code == 200
    assert 'data-chart-reason="busy"' in r.text
    assert 'hx-trigger="load delay' in r.text          # self-retry present
    # The retry must REPLACE the busy span (outerHTML on self), not nest it.
    assert 'hx-target="this"' in r.text and 'hx-swap="outerHTML"' in r.text
    assert r.headers.get("cache-control") == "no-store"  # not cacheable
    assert any("busy" in rec.message for rec in caplog.records)
    # Permits fully released after the request (no leak).
    assert J._THUMBNAIL_RENDER_SEMAPHORE.acquire(blocking=False) is True
    J._THUMBNAIL_RENDER_SEMAPHORE.release()
