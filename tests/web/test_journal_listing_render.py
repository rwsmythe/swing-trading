"""Phase 14 SB4 Slice 2 Task 2.3 — redesigned journal listing render.

  - the listing renders a `<table id="journal-table">` with rich columns
    (Total risk, Final R) + a per-row drill-down `<a href="/journal/trades/{id}">`.
  - the thumbnail cell placeholder (Slice 4) is present.
  - None fields render n/a / open fallbacks (not the literal word "None").
  - operator/derived text is auto-escaped (no `| safe`): a hypothesis_label
    carrying HTML metacharacters is escaped.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


def _seed_mixed(cfg) -> None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Closed trade with an exit fill (closing_price + final_r populated).
            tid = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="CLZ", entry_date="2026-04-15",
                    entry_price=10.0, initial_shares=100, initial_stop=9.0,
                    current_stop=9.0, state="closed",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None, hypothesis_label="<b>bold</b>",
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
            # Open trade (closing_price + final_r -> 'open' fallback).
            insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="OPN", entry_date="2026-04-16",
                    entry_price=20.0, initial_shares=50, initial_stop=18.0,
                    current_stop=18.0, state="managing",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-16T09:30:00",
            )
    finally:
        conn.close()


def test_journal_listing_rich_columns(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_mixed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=all")
    assert r.status_code == 200
    assert 'id="journal-table"' in r.text
    assert "Total risk" in r.text and "Final R" in r.text
    assert 'href="/journal/trades/' in r.text  # drill-down link


def test_journal_listing_thumb_placeholder(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_mixed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=all")
    assert 'class="journal-thumb"' in r.text


def test_journal_listing_open_fallback(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_mixed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=all")
    # The open trade renders 'open' for closing_price/final_r, never 'None'.
    assert ">open<" in r.text
    assert ">None<" not in r.text


def test_journal_listing_escapes_operator_text(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_mixed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=all")
    # hypothesis_label '<b>bold</b>' must be auto-escaped (no raw <b>).
    assert "<b>bold</b>" not in r.text
    assert "&lt;b&gt;bold&lt;/b&gt;" in r.text
