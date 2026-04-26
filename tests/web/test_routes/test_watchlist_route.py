"""GET /watchlist and GET /watchlist/{ticker}/expand routes."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app


def _seed_one_watchlist(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()


def test_get_watchlist_renders(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_one_watchlist(cfg)
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist")
    assert r.status_code == 200
    assert "AAPL" in r.text


def test_watchlist_expand_htmx(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_one_watchlist(cfg)
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist/AAPL/expand", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "Trend Template" in r.text or "AAPL" in r.text


def test_watchlist_expand_unknown_ticker_404(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist/NOPE/expand", headers={"HX-Request": "true"})
    assert r.status_code == 404


def test_watchlist_row_has_ticker_id_for_hx_target(seeded_db, monkeypatch):
    """Spec §3.1: watchlist row `<tr>` gains id='watchlist-row-<ticker>' so HTMX
    populates HX-Target when the Enter button fires, letting the row-prefix
    whitelist engage for error responses."""
    cfg, cfg_path = seeded_db
    _seed_one_watchlist(cfg)
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist")
    assert r.status_code == 200
    assert 'id="watchlist-row-AAPL"' in r.text


def test_watchlist_row_enter_button_stops_click_propagation(seeded_db, monkeypatch):
    """Bug 1 (2026-04-25): the row `<tr>` has hx-get='/watchlist/<t>/expand'
    (HTMX default click trigger). The Enter button has its own hx-get; without
    a propagation stop, the button click bubbles to the parent row, triggering
    BOTH HTMX requests simultaneously and racing on which response wins the
    outerHTML swap. The expanded partial has no actionable inputs, so when it
    won the race the operator was blocked from entering the trade.

    The Enter button must include an event-propagation stop. We accept either
    `onclick="event.stopPropagation()"` (Option A) or
    `hx-on:click="event.stopPropagation()"` (Option B); the literal token
    `stopPropagation` distinguishes pre-fix from post-fix templates."""
    cfg, cfg_path = seeded_db
    _seed_one_watchlist(cfg)
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist")
    assert r.status_code == 200
    enter_idx = r.text.find(">Enter</button>")
    assert enter_idx != -1, "Enter button not found in rendered watchlist"
    button_open = r.text.rfind("<button", 0, enter_idx)
    assert button_open != -1, "Could not locate <button> opening tag for Enter"
    button_html = r.text[button_open:enter_idx]
    assert "stopPropagation" in button_html, (
        "Enter button must stop click propagation so it does not also trigger "
        "the parent <tr>'s hx-get='/watchlist/<ticker>/expand'. Expected "
        "onclick=\"event.stopPropagation()\" or hx-on:click=\"event.stopPropagation()\". "
        f"Got: {button_html!r}"
    )
