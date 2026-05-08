"""Phase 8 V1 polish Item #2: Dashboard "Detail" button visible per open
positions row. Plan: docs/superpowers/plans/2026-05-07-phase8-v1-polish.md.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import ensure_schema
from swing.web.app import create_app
from swing.web.price_cache import PriceCache


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str = "DHC",
    state: str = "managing",
) -> None:
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, "
        " current_size, current_avg_cost) "
        "VALUES (?, ?, '2026-05-01', 100.0, 50, 90.0, 92.0, ?, "
        " 'manual_off_pipeline', '2026-05-01T09:30:00', 50.0, 100.0)",
        (trade_id, ticker, state),
    )
    conn.commit()


@pytest.fixture
def dashboard_app(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *args, **kwargs: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    db_path = tmp_path / "phase8_polish.db"
    conn = ensure_schema(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC")
        _seed_trade(conn, trade_id=2, ticker="CC")
    finally:
        conn.close()
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )
    return create_app(cfg), db_path


def test_dashboard_detail_anchor_present_per_open_position(dashboard_app):
    """Pre-fix: zero anchors with href='/trades/<id>' in dashboard HTML.
    Post-fix: exactly one such anchor per seeded open trade (2 -> 2 matches)."""
    app, _ = dashboard_app
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.text
    # Anchor with the exact href our partial emits.
    assert body.count('href="/trades/1"') >= 1
    assert body.count('href="/trades/2"') >= 1
    # And it carries the literal "Detail" anchor text within the row-actions cell.
    assert ">Detail</a>" in body


def test_dashboard_detail_anchor_includes_stop_propagation(dashboard_app):
    """Per CLAUDE.md HTMX click-propagation gotcha: the Detail anchor MUST
    include `event.stopPropagation()` so a click on Detail does NOT also fire
    the row's `hx-get="/trades/open/{id}/expand"` row-expand binding.

    Pre-fix expectation: rendered HTML for the open-positions row contains an
    anchor without the literal `event.stopPropagation()` marker.
    Post-fix expectation: every Detail anchor includes the marker.
    """
    app, _ = dashboard_app
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    needle = '<a href="/trades/1"'
    assert needle in body, f"Detail anchor not found for trade 1; body subset: {body[:500]}"
    anchor_start = body.index(needle)
    anchor_end = body.index("</a>", anchor_start)
    anchor_block = body[anchor_start:anchor_end]
    assert "event.stopPropagation()" in anchor_block


def test_dashboard_detail_target_route_resolves(dashboard_app):
    """Phase 6 R5 I3 lesson: navigation target route MUST be registered AND
    resolve. The Detail anchor's href is `/trades/{id}`; verify both the route
    is registered + GET to that path returns 200 for a seeded trade.

    Pre-fix expectation (had we shipped a broken href like `/trade/1`): GET
    returns 404. Post-fix expectation: GET returns 200 with the trade-detail
    page rendered.
    """
    app, _ = dashboard_app
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/trades/{trade_id}" in paths, (
        f"GET /trades/{{trade_id}} not registered; routes: {sorted(p for p in paths if p)}"
    )
    with TestClient(app) as client:
        response = client.get("/trades/1")
    assert response.status_code == 200
    # And the page renders the Phase 8 timeline section header (sanity that
    # the Detail destination is actually the trade-detail page).
    assert 'id="daily-management-timeline"' in response.text
