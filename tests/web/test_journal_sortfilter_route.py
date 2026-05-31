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


# --- GAP #1: filter <select> UI controls ------------------------------------


def test_filter_selects_present(client):
    # The filter BACKEND existed but there was no browser control to INITIATE a
    # filter. A <select name="filter_state"> (+ pattern + aplus) must render so
    # the operator can pick a filter (plan lines 71, 1069, 1158; S4 gate).
    r = client.get("/journal?period=all")
    assert r.status_code == 200
    assert 'name="filter_state"' in r.text
    assert 'name="filter_pattern"' in r.text
    assert 'name="filter_aplus"' in r.text


def test_filter_state_options_cover_allowlist(client):
    # Every backend-accepted filter_state (incl. virtual groups) must be a
    # selectable option, plus a blank "All".
    r = client.get("/journal?period=all")
    for value in (
        "open", "closed_any", "entered", "managing", "partial_exited",
        "closed", "reviewed",
    ):
        assert f'value="{value}"' in r.text, f"missing filter_state option {value}"


def test_active_filter_option_marked_selected(client):
    # The currently-applied filter option carries `selected` so it persists in
    # the re-rendered fragment after a swap.
    r = client.get("/journal?filter_state=reviewed",
                   headers={"HX-Request": "true"})
    m = re.search(r'<option[^>]*value="reviewed"[^>]*>', r.text)
    assert m, "reviewed option not found"
    assert "selected" in m.group(0)


def test_filter_selects_carry_htmx_attrs(client):
    # The selects fire an HX request on change, targeting the same table with
    # an outerHTML swap + the HX-Request header (OriginGuard strict-mode).
    r = client.get("/journal?period=all", headers={"HX-Request": "true"})
    # the filter form/selects must carry the HTMX trinity
    assert 'hx-get="/journal"' in r.text
    assert 'hx-target="#journal-table"' in r.text
    assert 'hx-swap="outerHTML"' in r.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text
    assert 'hx-trigger="change"' in r.text


def test_filter_change_preserves_active_sort(client):
    # Changing a filter must NOT drop the active sort. The form carries the
    # active sort/dir as hidden inputs so an hx-include sweeps them into the
    # filter-change request (the specific mechanism, mirroring the sort-link
    # discrimination — not merely "sort appears somewhere").
    r = client.get("/journal?sort=final_r&dir=asc",
                   headers={"HX-Request": "true"})
    assert re.search(
        r'<input[^>]*type="hidden"[^>]*name="sort"[^>]*value="final_r"', r.text
    ) or re.search(
        r'<input[^>]*name="sort"[^>]*value="final_r"[^>]*type="hidden"', r.text
    ), "hidden sort input carrying active sort not found in filter form"
    assert re.search(
        r'<input[^>]*name="dir"[^>]*value="asc"', r.text
    ), "hidden dir input carrying active dir not found in filter form"


def test_aplus_filter_options(client):
    r = client.get("/journal?period=all")
    assert 'value="aplus"' in r.text
    assert 'value="non_aplus"' in r.text


def test_pattern_filter_options(client):
    r = client.get("/journal?period=all")
    for value in (
        "vcp", "flat_base", "cup_with_handle", "high_tight_flag",
        "double_bottom_w",
    ):
        assert f'value="{value}"' in r.text, f"missing filter_pattern option {value}"


def test_thead_rows_are_well_formed(client):
    # Codex R1 MAJOR: when the filter control row was added, the column-header
    # row lost its opening <tr>, leaving the <thead> with one <tr> open but two
    # </tr> close -> malformed table served on BOTH the full page and the
    # whole-<table> outerHTML fragment. Browsers auto-correct so TestClient
    # content assertions miss it; assert <tr>/</tr> balance inside <thead>.
    r = client.get("/journal?period=all", headers={"HX-Request": "true"})
    assert r.status_code == 200
    m = re.search(r"<thead>(.*?)</thead>", r.text, re.DOTALL)
    assert m, "journal table has no <thead>"
    thead = m.group(1)
    opens = len(re.findall(r"<tr\b", thead))
    closes = len(re.findall(r"</tr>", thead))
    assert opens == closes, (
        f"<thead> has unbalanced rows: {opens} <tr> vs {closes} </tr> "
        "(column-header row missing its opening <tr>)"
    )
    # The column-header cells must live inside a <tr> (not orphaned after the
    # filter row closes): the filter row and the heading row are TWO rows.
    assert opens == 2, f"expected filter-row + heading-row (2 <tr>), got {opens}"
