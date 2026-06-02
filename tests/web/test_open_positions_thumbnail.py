"""Phase 14 close-out (P14.N1) — lazy candlestick thumbnail column on the
open-positions table. Open-positions reuses the existing journal thumbnail
route; this asserts the column shape stays aligned (header == compact-row ==
expanded colspan) and the lazy cell is wired.
"""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


def _seed_open_trade(cfg, ticker: str = "AAPL") -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = insert_trade_with_event(conn, Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10, initial_stop=170.0,
                current_stop=170.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()
    return tid


def _patch_price_cache(monkeypatch):
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _open_positions_section(body: str) -> str:
    m = re.search(
        r'<section class="open-positions">.*?</section>', body, flags=re.DOTALL,
    )
    assert m is not None, "open-positions section not found in dashboard body"
    return m.group(0)


def _count_header_th(section: str) -> int:
    thead = re.search(r"<thead>.*?</thead>", section, flags=re.DOTALL)
    assert thead is not None
    return len(re.findall(r"<th\b[^>]*>", thead.group(0)))


def _count_first_row_td(section: str) -> int:
    row = re.search(
        r'<tr\b[^>]*id="open-position-\d+"[^>]*>.*?</tr>',
        section, flags=re.DOTALL,
    )
    assert row is not None, "no open-position compact row found"
    return len(re.findall(r"<td\b[^>]*>", row.group(0)))


def test_open_positions_column_counts_align(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_open_trade(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        body = client.get("/").text
        section = _open_positions_section(body)
        assert _count_header_th(section) == 11
        assert _count_first_row_td(section) == 11
        # expanded fragment colspan
        trade_id = re.search(r'id="open-position-(\d+)"', section).group(1)
        expanded = client.get(
            f"/trades/open/{trade_id}/expand",
            headers={"HX-Request": "true"},
        ).text
    assert 'colspan="11"' in expanded


def test_open_positions_row_has_lazy_thumbnail_cell(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_open_trade(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        body = client.get("/").text
    section = _open_positions_section(body)
    assert 'hx-get="/journal/trades/' in section and "/thumbnail" in section
    assert 'hx-trigger="revealed"' in section
    assert 'HX-Request' in section


def test_open_positions_thumbnail_cell_targets_self(seeded_db, monkeypatch):
    """Gate-fix regression: the lazy thumbnail <td> MUST set hx-target="this".

    The open-positions <tr> carries hx-target="closest tr" (click-to-expand);
    without an explicit hx-target on the thumbnail <td>, HTMX attribute
    inheritance makes the revealed thumbnail swap replace the WHOLE row's
    innerHTML, wiping every other cell. Browser-only failure (the initial
    render looks fine); locked here against the exact rendered attribute order.
    """
    cfg, cfg_path = seeded_db
    _seed_open_trade(cfg, "AAPL")
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        body = client.get("/").text
    section = _open_positions_section(body)
    assert (
        'hx-trigger="revealed" hx-target="this" hx-swap="innerHTML"' in section
    )
