"""Phase 13 T2.SB6c task T-A.6c.2 — Gap A.3 watchlist template thumbnail wiring.

Per plan §G.2 step 1a (2 tests covering Gap A.3):
  - `partials/watchlist_row.html.j2` renders `vm.watchlist_chart_svg_bytes`
    bytes when present for the row's ticker.
  - Cache-miss (ticker absent from the mapping) emits no chart markup +
    the row still renders all original columns.

The WatchlistVM populates `watchlist_chart_svg_bytes` via T-A.6.6 wiring
(commit `94e4418`); this gap closes the surface by extending the partial.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import ChartRender
from swing.data.repos.chart_renders import refresh_chart_render
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app


def _seed_complete_run(conn) -> int:
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, finished_ts, trigger, data_asof_date,
             action_session_date, state, lease_token)
        VALUES ('2026-05-20T09:00:00', '2026-05-20T09:05:00', 'manual',
                '2026-05-19', '2026-05-20', 'complete', 't-w')
        """
    )
    return int(cur.lastrowid)


def _seed_watchlist_entry(conn, *, ticker: str = "WCH") -> None:
    from swing.data.models import WatchlistEntry
    upsert_watchlist_entry(
        conn,
        WatchlistEntry(
            ticker=ticker, added_date="2026-05-01",
            last_qualified_date="2026-05-19", status="watch",
            qualification_count=1, not_qualified_streak=0,
            last_data_asof_date="2026-05-19",
            entry_target=100.0, initial_stop_target=95.0,
            last_close=100.0, last_pivot=None, last_stop=None,
            last_adr_pct=2.0, missing_criteria=None, notes=None,
        ),
    )


def test_watchlist_row_partial_renders_thumbnail_when_cache_hit(seeded_db):
    """Gap A.3 — `/watchlist` page renders the watchlist_row partial with
    inline SVG thumbnail bytes pulled from chart_renders cache."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = _seed_complete_run(conn)
            _seed_watchlist_entry(conn, ticker="THB")
            refresh_chart_render(conn, ChartRender(
                id=None, ticker="THB", surface="watchlist_row",
                chart_svg_bytes=b"<svg>thumb-cached</svg>",
                source_data_hash="h",
                rendered_at="2026-05-20T09:05:00",
                data_asof_date="2026-05-19",
                pipeline_run_id=run_id,
                pattern_class=None,
            ))
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist")
    assert r.status_code == 200
    assert "<svg>thumb-cached</svg>" in r.text


def test_watchlist_row_partial_omits_thumbnail_when_cache_miss(seeded_db):
    """Gap A.3 — ticker absent from `vm.watchlist_chart_svg_bytes` mapping;
    template omits the chart markup; row still renders the ticker + other
    columns unchanged."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_complete_run(conn)
            _seed_watchlist_entry(conn, ticker="NOSVG")
            # No chart_renders row planted -> cache miss.
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist")
    assert r.status_code == 200
    # Row markup still present (ticker visible).
    assert "NOSVG" in r.text
    # No leaked SVG content from any cache row.
    assert "<svg>thumb-cached</svg>" not in r.text
