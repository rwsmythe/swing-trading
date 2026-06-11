"""Task 7 — POST /watchlist/{ticker}/pin route tests.

Four tests:
  (a) pin_route_persists_and_server_stamps_pinned_at — POST with pinned=on
      persists pinned=True, note, and a non-None server-stamped pinned_at.
  (b) unpin_clears_note_and_timestamp — POST without pinned checkbox
      clears all three fields.
  (c) empty_pin_note_persists_null_not_empty_string — empty textarea → None
      (not "").
  (d) pin_route_404_for_absent_ticker — unknown ticker → 404.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import get_watchlist_entry, set_watchlist_pin, upsert_watchlist_entry
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
                pin_note="existing note",
                pinned_at="2026-04-10T10:00:00",
            )
    finally:
        conn.close()


def _patch_price_cache(monkeypatch) -> None:
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)


def test_pin_route_persists_and_server_stamps_pinned_at(seeded_db, monkeypatch):
    """POST pinned=on + note → pinned=True, note persisted, pinned_at server-stamped."""
    cfg, cfg_path = seeded_db
    _seed_entry(cfg, "AAAA")
    _patch_price_cache(monkeypatch)

    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.post(
            "/watchlist/AAAA/pin",
            data={"pinned": "on", "pin_note": "future breakout"},
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200

    conn = connect(cfg.paths.db_path)
    try:
        e = get_watchlist_entry(conn, "AAAA")
    finally:
        conn.close()
    assert e is not None
    assert e.pinned is True
    assert e.pin_note == "future breakout"
    assert e.pinned_at is not None


def test_unpin_clears_note_and_timestamp(seeded_db, monkeypatch):
    """POST without pinned checkbox clears pinned, pin_note, and pinned_at."""
    cfg, cfg_path = seeded_db
    _seed_pinned_entry(cfg, "AAAA")
    _patch_price_cache(monkeypatch)

    with TestClient(create_app(cfg, cfg_path)) as client:
        # checkbox absent → unpinned
        resp = client.post(
            "/watchlist/AAAA/pin",
            data={"pin_note": ""},
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200

    conn = connect(cfg.paths.db_path)
    try:
        e = get_watchlist_entry(conn, "AAAA")
    finally:
        conn.close()
    assert e is not None
    assert (e.pinned, e.pin_note, e.pinned_at) == (False, None, None)


def test_empty_pin_note_persists_null_not_empty_string(seeded_db, monkeypatch):
    """Empty textarea with pinned=on → pin_note=None (not '')."""
    cfg, cfg_path = seeded_db
    _seed_entry(cfg, "AAAA")
    _patch_price_cache(monkeypatch)

    with TestClient(create_app(cfg, cfg_path)) as client:
        client.post(
            "/watchlist/AAAA/pin",
            data={"pinned": "on", "pin_note": ""},
            headers={"HX-Request": "true"},
        )

    conn = connect(cfg.paths.db_path)
    try:
        e = get_watchlist_entry(conn, "AAAA")
    finally:
        conn.close()
    assert e is not None
    assert e.pin_note is None


def test_pin_route_404_for_absent_ticker(seeded_db, monkeypatch):
    """Unknown ticker returns 404."""
    cfg, cfg_path = seeded_db
    _patch_price_cache(monkeypatch)

    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.post(
            "/watchlist/ZZZZ/pin",
            data={"pinned": "on"},
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 404
