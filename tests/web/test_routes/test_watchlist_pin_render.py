"""Task 7 — Template render tests for the pin form + compact-row badge.

Three tests:
  (a) expanded_pin_form_carries_htmx_attributes — GET /watchlist/{ticker}/expand
      returns the expanded partial that contains the pin form with
      the correct HTMX attributes (hx-post, hx-headers, hx-target, inputs).
  (b) compact_row_shows_pin_badge_when_pinned — GET /watchlist with a pinned
      ticker shows the watchlist-pin-badge element.
  (c) compact_row_no_badge_when_unpinned — GET /watchlist with an unpinned
      ticker does NOT show the badge.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import set_watchlist_pin, upsert_watchlist_entry
from swing.web.app import create_app
from swing.web.price_cache import PriceCache


def _base_entry(ticker: str) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=ticker, added_date="2026-04-10",
        last_qualified_date="2026-04-17", status="watch",
        qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-04-17",
        entry_target=181.0, initial_stop_target=170.0,
        last_close=180.0, last_pivot=181.0, last_stop=170.0,
        last_adr_pct=2.5, missing_criteria=None, notes=None,
    )


def _seed_entry(cfg, ticker: str) -> None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, _base_entry(ticker))
    finally:
        conn.close()


def _seed_pinned_entry(cfg, ticker: str) -> None:
    _seed_entry(cfg, ticker)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            set_watchlist_pin(
                conn, ticker,
                pinned=True,
                pin_note="future breakout",
                pinned_at="2026-04-10T10:00:00",
            )
    finally:
        conn.close()


def _patch_price_cache(monkeypatch) -> None:
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)


def test_expanded_pin_form_carries_htmx_attributes(seeded_db, monkeypatch):
    """GET /watchlist/AAAA/expand returns the expanded partial with a pin
    form that has the correct HTMX wiring (post, target, headers) and
    both named inputs (pinned checkbox + pin_note textarea)."""
    cfg, cfg_path = seeded_db
    _seed_entry(cfg, "AAAA")
    _patch_price_cache(monkeypatch)

    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.get("/watchlist/AAAA/expand", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    html = resp.text

    assert 'hx-post="/watchlist/AAAA/pin"' in html
    # OriginGuard: form must carry HX-Request header (single-quote or double-quote)
    assert "HX-Request" in html
    # hx-target must point at the row id so the POST response swaps the expanded row
    assert 'hx-target="#watchlist-row-AAAA"' in html
    # Both form inputs present
    assert 'name="pinned"' in html
    assert 'name="pin_note"' in html


def test_compact_row_shows_pin_badge_when_pinned(seeded_db, monkeypatch):
    """GET /watchlist with a pinned ticker renders the watchlist-pin-badge
    element in the compact row."""
    cfg, cfg_path = seeded_db
    _seed_pinned_entry(cfg, "AAAA")
    _patch_price_cache(monkeypatch)

    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.get("/watchlist")
    assert resp.status_code == 200
    assert "watchlist-pin-badge" in resp.text


def test_compact_row_no_badge_when_unpinned(seeded_db, monkeypatch):
    """GET /watchlist with an unpinned ticker must NOT show the badge."""
    cfg, cfg_path = seeded_db
    _seed_entry(cfg, "AAAA")   # not pinned (default pinned=False)
    _patch_price_cache(monkeypatch)

    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.get("/watchlist")
    assert resp.status_code == 200
    assert "watchlist-pin-badge" not in resp.text
