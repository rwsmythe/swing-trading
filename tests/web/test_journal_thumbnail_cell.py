"""Phase 14 SB4 Slice 4 Task 4.3: on-scroll thumbnail cell wiring.

Each journal-listing row's `journal-thumb` <td> lazy-loads its thumbnail with
the HTMX trinity: hx-get to the per-trade thumbnail route, hx-trigger=revealed
(window-scroll viewport -- base.html.j2 has no overflow:auto/scroll container),
hx-swap=innerHTML, and the HX-Request header so OriginGuard strict-mode does not
403 the fragment fetch.
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
            tid = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="CLZ", entry_date="2026-04-15",
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


def test_thumbnail_cell_lazy_attrs(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_mixed(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=all")
    assert r.status_code == 200
    assert 'hx-trigger="revealed"' in r.text
    assert 'hx-get="/journal/trades/' in r.text and "/thumbnail" in r.text
    assert 'hx-swap="innerHTML"' in r.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text
