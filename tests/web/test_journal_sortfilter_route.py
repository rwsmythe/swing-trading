"""Phase 14 SB4 Slice 3 Task 3.2 — HTMX whole-<table> sort/filter swap route.

Discriminating coverage (OQ-9 / WP-R2 M#5 / L4 HTMX trinity):
  - an HX GET returns a fragment whose ROOT is `<table id="journal-table">`
    (NOT a bare `<tr>` -> synthetic-table-wrap cannot fire).
  - sort/filter controls carry hx-get + hx-target="#journal-table" +
    hx-swap="outerHTML" + hx-headers='{"HX-Request": "true"}'.
  - a bad sort returns the in-page table fragment with an "invalid filter"
    notice (NOT a bare 400/422).
  - a sort link built while a filter is active CARRIES that filter in its
    hx-get URL (query-state preservation; the discriminating test).
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


def _seed(cfg) -> None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="CLZ", entry_date="2026-04-15",
                    entry_price=10.0, initial_shares=100, initial_stop=9.0,
                    current_stop=9.0, state="reviewed",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None, chart_pattern_operator="vcp",
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


@pytest.fixture
def client(seeded_db):
    cfg, cfg_path = seeded_db
    _seed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as c:
        yield c


def test_sortfilter_returns_table_rooted_fragment(client):
    r = client.get("/journal?sort=final_r&dir=desc",
                   headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert r.text.lstrip().startswith("<table")
    assert 'id="journal-table"' in r.text
    # The fragment is ONLY the table — no full-page chrome (the <h1>).
    assert "<h1>Journal</h1>" not in r.text


def test_sort_controls_have_htmx_attrs(client):
    r = client.get("/journal?period=all")
    assert 'hx-target="#journal-table"' in r.text
    assert 'hx-swap="outerHTML"' in r.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text


def test_bad_filter_returns_inpage_notice_not_400(client):
    r = client.get("/journal?sort=bogus", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "invalid filter" in r.text.lower()


def test_full_page_also_renders_table(client):
    # The full page and the HX fragment share the SAME include — the full page
    # still has the table id.
    r = client.get("/journal?period=all")
    assert r.status_code == 200
    assert 'id="journal-table"' in r.text
    assert "<h1>Journal</h1>" in r.text


def test_sort_link_preserves_active_filters(client):
    r = client.get("/journal?filter_state=reviewed&filter_aplus=aplus",
                   headers={"HX-Request": "true"})
    # WP-R5 m#1: assert the SPECIFIC Final R sort control's hx-get carries the
    # active filters (not merely that the params appear somewhere on the page).
    m = re.search(r'hx-get="([^"]*sort=final_r[^"]*)"', r.text)
    assert m, "Final R sort control not found"
    sort_url = m.group(1)
    assert "filter_state=reviewed" in sort_url
    assert "filter_aplus=aplus" in sort_url
