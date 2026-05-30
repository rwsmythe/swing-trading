"""Phase 13 T-T4.SB.5 Sub-task 5C — Item 6: partial-rewire preserves
thumbnail across full-page render + collapse-route render.

Per plan §B.5 Sub-task 5C.1 + spec §B.6 Option 6B: the
``watchlist_row.html.j2`` partial pivots from
``vm.watchlist_chart_svg_bytes.get(w.ticker)`` (fallback chain) to a
single ``chart_svg_bytes_for_row`` template param. The full-page render
sites (`watchlist.html.j2`, `partials/watchlist_top5_section.html.j2`)
pass the bytes via ``{% set chart_svg_bytes_for_row = ... %}`` in the
row loop; the collapse route already passes it explicitly per
T-T4.SB.3 Sub-task 3B.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _patch_price_cache(monkeypatch, ticker: str, price: float) -> None:
    snapshot_map = {
        ticker: PriceSnapshot(
            ticker=ticker, price=price, asof=datetime.now(),
            is_stale=False, source="live",
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


def test_watchlist_full_page_renders_thumbnail_via_param(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """Item 6 Option 6B: full-page /watchlist render passes
    ``chart_svg_bytes_for_row`` via ``{% set %}`` in the row loop; the
    partial reads only that param (no fallback to ``vm`` map).
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
            chart_svg_bytes=b"<svg>full-page-thumb</svg>",
        )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        page = client.get("/watchlist")
    assert page.status_code == 200
    assert b"<svg>full-page-thumb</svg>" in page.content, (
        "Item 6: full-page /watchlist must render planted SVG via "
        "chart_svg_bytes_for_row param"
    )
    assert b"watchlist-thumbnail" in page.content


def test_dashboard_top5_renders_thumbnail_via_param(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """Item 6 Option 6B symmetric coverage on dashboard top-5 watchlist."""
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
            chart_svg_bytes=b"<svg>dashboard-top5-thumb</svg>",
        )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        page = client.get("/")
    assert page.status_code == 200
    assert b"<svg>dashboard-top5-thumb</svg>" in page.content, (
        "Item 6: dashboard top-5 watchlist must render planted SVG via "
        "chart_svg_bytes_for_row param"
    )
    assert b"watchlist-thumbnail" in page.content


def test_watchlist_expand_then_collapse_preserves_thumbnail(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """Item 6: full-page render → expand → collapse sequence preserves
    the thumbnail across all three renders.

    Plants both a watchlist_row surface SVG (for full-page + collapse)
    AND an ticker_detail surface SVG (for expand); asserts each render
    surfaces the expected planted bytes. This guards against the
    pre-fix defect where the collapse path produced a blank thumbnail
    cell because the partial fell back to ``vm.watchlist_chart_svg_bytes``
    which is absent from the single-row route's template context.
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
            chart_svg_bytes=b"<svg>row-thumb</svg>",
        )
        _plant_chart_render_row(
            conn, surface="ticker_detail", ticker="UCTT",
            pipeline_run_id=run_id,
            chart_svg_bytes=b"<svg>expanded</svg>",
        )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # 1. Full-page render shows row thumbnail.
        page = client.get("/watchlist")
        assert page.status_code == 200
        assert b"<svg>row-thumb</svg>" in page.content
        # 2. Expand shows expanded SVG.
        expand = client.get("/watchlist/UCTT/expand")
        assert expand.status_code == 200
        assert b"<svg>expanded</svg>" in expand.content
        # 3. Collapse shows row thumbnail again (THIS was the pre-fix
        #    defect — partial fell back to absent vm map → blank cell).
        collapse = client.get("/watchlist/UCTT/row")
        assert collapse.status_code == 200
        assert b"<svg>row-thumb</svg>" in collapse.content, (
            "Item 6 pre-fix defect: collapse path must surface planted "
            "watchlist_row SVG via chart_svg_bytes_for_row param"
        )
        assert b"watchlist-thumbnail" in collapse.content


def test_watchlist_row_partial_ignores_vm_chart_svg_bytes_fallback(
    seeded_db, seed_watchlist_and_candidate, monkeypatch,
):
    """Item 6 Option 6B: the partial must NOT fall back to
    ``vm.watchlist_chart_svg_bytes`` — only ``chart_svg_bytes_for_row``
    is honored.

    Negative assertion: full-page render with NO chart_render row
    planted — pre-fix the partial would still try the vm-map fallback;
    post-fix the param is None so no thumbnail block emits.
    """
    cfg, cfg_path = seeded_db
    seed_watchlist_and_candidate(
        ticker="UCTT", entry_target=42.00,
        candidate_pivot=44.50, last_close=43.00,
    )
    _patch_price_cache(monkeypatch, "UCTT", 43.00)

    # NO chart_render row planted; vm.watchlist_chart_svg_bytes will be
    # empty too. Confirms partial does not synthesize a spurious
    # thumbnail when both the explicit param and the vm map are empty.
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        page = client.get("/watchlist")
    assert page.status_code == 200
    # No watchlist-thumbnail span emitted when no bytes available.
    assert b"watchlist-thumbnail" not in page.content


def test_watchlist_row_partial_source_drops_vm_fallback():
    """Item 6 Option 6B structural assertion: the partial template MUST
    NOT reference ``vm.watchlist_chart_svg_bytes`` post-fix. The
    explicit ``chart_svg_bytes_for_row`` param is the only supported
    source of thumbnail bytes; the prior fallback chain is removed.

    This is a discriminating source-level test: the prior partial form
    contained ``vm.watchlist_chart_svg_bytes.get(w.ticker)`` in its
    ``{% set _thumb_bytes %}`` chain. Post-rewire the substring is
    absent.
    """
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    partial = repo_root / "swing" / "web" / "templates" / "partials" / (
        "watchlist_row.html.j2"
    )
    text = partial.read_text(encoding="utf-8")
    assert "vm.watchlist_chart_svg_bytes" not in text, (
        "Item 6 Option 6B: partial must not reference "
        "vm.watchlist_chart_svg_bytes; use chart_svg_bytes_for_row only"
    )
    # Positive: partial still consumes the explicit param.
    assert "chart_svg_bytes_for_row" in text


def test_watchlist_html_passes_chart_svg_bytes_for_row():
    """Item 6 Option 6B structural assertion: ``watchlist.html.j2`` must
    pass ``chart_svg_bytes_for_row`` to the included row partial.
    """
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    tpl = repo_root / "swing" / "web" / "templates" / "watchlist.html.j2"
    text = tpl.read_text(encoding="utf-8")
    assert "chart_svg_bytes_for_row" in text, (
        "Item 6: watchlist.html.j2 must {% set chart_svg_bytes_for_row %} "
        "in its row loop"
    )


def test_dashboard_top5_passes_chart_svg_bytes_for_row():
    """Item 6 Option 6B structural assertion: the dashboard top-5
    watchlist include site (``partials/watchlist_top5_section.html.j2``)
    must pass ``chart_svg_bytes_for_row`` to the included row partial.
    """
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    tpl = repo_root / "swing" / "web" / "templates" / "partials" / (
        "watchlist_top5_section.html.j2"
    )
    text = tpl.read_text(encoding="utf-8")
    assert "chart_svg_bytes_for_row" in text, (
        "Item 6: watchlist_top5_section.html.j2 must "
        "{% set chart_svg_bytes_for_row %} in its row loop"
    )
