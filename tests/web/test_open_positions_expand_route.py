"""Phase 14 SB4 Slice 1 Tasks 1.2 + 1.3 — open-positions row-expand inlines
the SB3 `position_detail` SVG (rewired off the legacy static PNG).

Task 1.2: the expand fragment shows the inline `position_detail` SVG inside the
existing `<td colspan>` (no legacy `<img src="/charts/...">`); the fragment root
stays `<tr>` (HTMX synthetic-table-wrap rule); a cache miss shows a TERMINAL
fallback, never blank (WP M#3: `chart_reason is None` from the static-PNG scope
can co-occur with `position_chart_svg_bytes is None` from the absent SVG cache).

Task 1.3: a reopened ticker (one closed + one open, same ticker) row-expand
reflects the OPEN trade's chart — the single `position_detail` cache row IS the
open trade's chart (one-open-trade-per-ticker invariant).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app


def _insert_open_trade(conn, *, ticker: str, entry_date: str = "2026-04-20",
                       status: str = "open") -> int:
    """Seed one trade + its entry fill. `status='open'` -> `state='entered'`;
    `status='closed'` -> `state='closed'` (the conftest autouse fixture only
    auto-writes the entry fill for active states, so we write the fill here
    unconditionally to keep current_size consistent)."""
    state_value = "entered" if status == "open" else status
    cur = conn.execute(
        """INSERT INTO trades
           (ticker, entry_date, entry_price, initial_shares,
            initial_stop, current_stop, state,
            trade_origin, pre_trade_locked_at, current_size,
            watchlist_entry_target, watchlist_initial_stop, notes)
           VALUES (?, ?, 100.0, 10, 90.0, 90.0, ?,
                   'manual_off_pipeline', ?, 10.0,
                   NULL, NULL, NULL)""",
        (ticker, entry_date, state_value, f"{entry_date}T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    conn.execute(
        """INSERT INTO fills
           (trade_id, fill_datetime, action, quantity, price, reason,
            rule_based, fees, manual_entry_confidence,
            reconciliation_status, tos_match_id)
           VALUES (?, ?, 'entry', 10.0, 100.0, NULL, NULL, NULL, NULL,
                   'unreconciled', NULL)""",
        (trade_id, f"{entry_date}T16:00:00"),
    )
    return trade_id


def _seed_position_detail_cache(conn, *, ticker: str,
                                svg: bytes = b"<svg>position_detail</svg>") -> None:
    """Insert a `chart_renders` row, surface='position_detail',
    pipeline_run_id IS NULL (TEST seeding, mirrors the production SB3
    write-through)."""
    from swing.data.models import ChartRender
    from swing.data.repos.chart_renders import insert_chart_render

    insert_chart_render(conn, ChartRender(
        id=None, ticker=ticker, surface="position_detail",
        chart_svg_bytes=svg, source_data_hash="hash-pd",
        rendered_at="2026-04-20T16:05:00", data_asof_date="2026-04-20",
        pipeline_run_id=None, pattern_class=None,
    ))


def _patch_price_cache(monkeypatch):
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)


# ---------------------------------------------------------------------------
# Task 1.2 — template swap
# ---------------------------------------------------------------------------

def test_expand_shows_svg_not_legacy_png(seeded_db, monkeypatch):
    """With a position_detail cache row present, the expand fragment inlines
    the SVG (no legacy <img src="/charts/...">) and stays <tr>-rooted."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = _insert_open_trade(conn, ticker="AAPL")
            _seed_position_detail_cache(conn, ticker="AAPL")
    finally:
        conn.close()
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/trades/open/{trade_id}/expand",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200, r.text[:200]
    assert ("<svg" in r.text) or ("position-detail-chart" in r.text)
    assert '<img src="/charts/' not in r.text
    assert r.text.lstrip().startswith("<tr")  # synthetic-table-wrap rule


def test_expand_no_blank_when_svg_cache_missing(seeded_db, monkeypatch):
    """WP M#3 — the chart_reason 'available' (static-PNG scope) can co-occur
    with NO position_detail SVG cache row. The template MUST show a terminal
    fallback, never blank."""
    from tests.web.test_routes.test_open_positions_expand import (
        _seed_in_scope_trade,
    )
    cfg, cfg_path = seeded_db
    # In-scope trade: chart_reason resolves to None ("available") via the
    # static-PNG scope, but NO position_detail SVG cache row is seeded.
    trade_id = _seed_in_scope_trade(cfg, ticker="AAPL")
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/trades/open/{trade_id}/expand",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200, r.text[:200]
    # Never blank: either the SVG, or a chart-unavailable fallback div.
    assert ("<svg" in r.text) or ("chart-unavailable" in r.text)
    # Specifically the terminal cache-miss fallback (chart_reason is None for
    # the in-scope path, so the {% elif chart_reason_message %} branch is NOT
    # taken — only the terminal {% else %} can fire).
    assert 'data-chart-reason="position-detail-cache-miss"' in r.text
    # Legacy PNG path is gone.
    assert '<img src="/charts/' not in r.text


# ---------------------------------------------------------------------------
# Task 1.3 — reopened-ticker safety (one-open-trade-per-ticker invariant)
# ---------------------------------------------------------------------------

def test_reopened_ticker_expand_uses_open_trade_chart(seeded_db, monkeypatch):
    """One closed + one open trade for the SAME ticker. The single
    `position_detail` cache row (run-agnostic, keyed on ticker) IS the open
    trade's chart; the open trade's row-expand inlines that SVG.

    The data model permits at most one concurrently-open trade per ticker
    today (the closed trade is in state 'closed'); if that ever changes,
    ESCALATE (per plan §1.3)."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Closed trade first (same ticker), then the currently-open one.
            _insert_open_trade(conn, ticker="AAPL", status="closed",
                               entry_date="2026-03-01")
            open_trade_id = _insert_open_trade(conn, ticker="AAPL",
                                               entry_date="2026-04-20")
            _seed_position_detail_cache(conn, ticker="AAPL")
    finally:
        conn.close()
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/trades/open/{open_trade_id}/expand",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200 and "<svg" in r.text
