"""Phase 13 T2.SB6c task T-A.6c.2 — Gap A.2 position detail chart wiring.

Per plan §G.2 step 1a (3 tests covering Gap A.2):
  - TradeDetailVM populated from chart_renders cache (surface='position_detail',
    pipeline_run_id=NULL per v20 §3.2 run-agnostic LOCK).
  - Template renders the inline SVG bytes when present.
  - Cache-miss leaves the field None + template omits the chart.

Per L7 LOCK (T2.SB6a substrate API FROZEN): tests reuse
`refresh_chart_render` verbatim; no substrate modification.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.config import Config
from swing.data.db import connect
from swing.data.models import ChartRender, Trade
from swing.data.repos.chart_renders import refresh_chart_render
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


def _seed_open_trade(conn, *, ticker: str = "POS") -> int:
    return insert_trade_with_event(
        conn,
        Trade(
            id=None, ticker=ticker,
            entry_date="2026-05-18", entry_price=100.0,
            initial_shares=10, initial_stop=90.0,
            current_stop=90.0, state="entered",
            watchlist_entry_target=None,
            watchlist_initial_stop=None,
            notes=None,
            trade_origin="manual_off_pipeline",
            pre_trade_locked_at="2026-05-18T09:30:00",
            current_size=10.0,
        ),
        event_ts="2026-05-18T09:30:00",
    )


def test_trade_detail_template_renders_inline_chart_svg_when_cache_hit(
    seeded_db,
):
    """Gap A.2 — operator-facing trade-detail page renders inline SVG bytes
    pulled from chart_renders (surface='position_detail';
    pipeline_run_id IS NULL per v20 §3.2 LOCK)."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = _seed_open_trade(conn, ticker="POS")
            refresh_chart_render(conn, ChartRender(
                id=None, ticker="POS", surface="position_detail",
                chart_svg_bytes=b"<svg>position-cached</svg>",
                source_data_hash="h",
                rendered_at="2026-05-20T09:05:00",
                data_asof_date="2026-05-19",
                pipeline_run_id=None,
                pattern_class=None,
            ))
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade_id}")
    assert r.status_code == 200
    assert "<svg>position-cached</svg>" in r.text


def test_trade_detail_template_omits_chart_when_cache_miss(seeded_db):
    """Gap A.2 — cache-miss leaves field None; template emits no SVG bytes
    (page still renders 200 + summary content)."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = _seed_open_trade(conn, ticker="NOCHART")
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade_id}")
    assert r.status_code == 200
    # Trade summary still rendered.
    assert "Trade #" in r.text
    assert "Entry date" in r.text
    # No spurious cached-row marker.
    assert "<svg>position-cached</svg>" not in r.text


def test_trade_detail_vm_populates_position_chart_svg_bytes_from_cache(
    seeded_db,
):
    """Gap A.2 — `TradeDetailVM` carries the cached bytes via a new
    `position_chart_svg_bytes` field consulted via `get_cached_chart_svg`
    with `pipeline_run_id=None` (run-agnostic key per v20 §3.2 LOCK)."""
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = _seed_open_trade(conn, ticker="POSVM")
            refresh_chart_render(conn, ChartRender(
                id=None, ticker="POSVM", surface="position_detail",
                chart_svg_bytes=b"<svg>position-vm</svg>",
                source_data_hash="h",
                rendered_at="2026-05-20T09:05:00",
                data_asof_date="2026-05-19",
                pipeline_run_id=None,
                pattern_class=None,
            ))
    finally:
        conn.close()
    from swing.config_overrides import apply_overrides
    from swing.web.view_models.trades import build_trade_detail_vm
    vm = build_trade_detail_vm(
        trade_id=trade_id, cfg=apply_overrides(cfg),
    )
    assert vm is not None
    assert getattr(vm, "position_chart_svg_bytes", None) == (
        b"<svg>position-vm</svg>"
    )
