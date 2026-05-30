"""Phase 13 T-T4.SB.3 (Item 5 + Item 6) — route-level JIT wiring tests.

Discriminating coverage per plan §B.3 Sub-task 3B:
- watchlist_row collapse path serves cached watchlist_row SVG via JIT
- watchlist_expand path populates watchlist_expanded_chart_svg_bytes via
  JIT (shared ticker_detail surface per spec §B.5)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _patch_price_cache(monkeypatch, ticker: str, price: float | None) -> None:
    if price is None:
        snapshot_map: dict[str, PriceSnapshot] = {}
    else:
        snapshot_map = {
            ticker: PriceSnapshot(
                ticker=ticker,
                price=price,
                asof=datetime.now(),
                is_stale=False,
                source="live",
            )
        }
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: snapshot_map[t] for t in tickers if t in snapshot_map
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _plant_chart_render_row(
    conn: sqlite3.Connection,
    *,
    surface: str,
    ticker: str,
    pipeline_run_id: int | None,
    chart_svg_bytes: bytes,
) -> None:
    with conn:
        conn.execute(
            "INSERT INTO chart_renders "
            "(ticker, surface, pipeline_run_id, pattern_class, "
            "chart_svg_bytes, source_data_hash, rendered_at, data_asof_date) "
            "VALUES (?, ?, ?, NULL, ?, 'planted', "
            "'2026-04-29T09:00:00Z', '2026-04-28')",
            (ticker, surface, pipeline_run_id, chart_svg_bytes),
        )


def _latest_pipeline_run_id(cfg) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT id FROM pipeline_runs WHERE state='complete' "
            "ORDER BY finished_ts DESC, id DESC LIMIT 1"
        ).fetchone()
        return int(row[0])
    finally:
        conn.close()


def test_watchlist_row_collapse_uses_jit_to_repopulate_thumbnail(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """Per spec §B.6 Item 6 + §B.5 Item 5: collapse-route renders the
    thumbnail via JIT helper (cache hit branch). Thumbnail must NEVER
    silently absent post-expand.
    """
    cfg, cfg_path = seeded_db
    seed_watchlist_and_candidate(
        ticker="UCTT", entry_target=42.00,
        candidate_pivot=44.50, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "UCTT", 43.00)

    run_id = _latest_pipeline_run_id(cfg)
    conn = connect(cfg.paths.db_path)
    try:
        _plant_chart_render_row(
            conn, surface="watchlist_row", ticker="UCTT",
            pipeline_run_id=run_id,
            chart_svg_bytes=b"<svg>jit-watchlist</svg>",
        )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/watchlist/UCTT/row")
    assert resp.status_code == 200
    body = resp.content
    assert b"watchlist-thumbnail" in body
    assert b"<svg>jit-watchlist</svg>" in body


def test_watchlist_expand_uses_jit_to_populate_expanded_chart_bytes(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """Per spec §B.5 Item 5: watchlist_expand wires JIT via shared
    surface='ticker_detail' (cache-key reuse with hyp-recs route)."""
    cfg, cfg_path = seeded_db
    seed_watchlist_and_candidate(
        ticker="UCTT", entry_target=42.00,
        candidate_pivot=44.50, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "UCTT", 43.00)

    run_id = _latest_pipeline_run_id(cfg)
    conn = connect(cfg.paths.db_path)
    try:
        _plant_chart_render_row(
            conn, surface="ticker_detail", ticker="UCTT",
            pipeline_run_id=run_id,
            chart_svg_bytes=b"<svg>jit-expanded</svg>",
        )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/watchlist/UCTT/expand")
    assert resp.status_code == 200
    body = resp.content
    # Inline SVG present in expanded view (Sub-task 3D template cascade
    # uses watchlist_expanded_chart_svg_bytes).
    assert b"<svg>jit-expanded</svg>" in body
