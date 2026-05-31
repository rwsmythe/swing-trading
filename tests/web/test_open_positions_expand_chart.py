"""Phase 14 SB4 Slice 1 Task 1.1 — `position_chart_svg_bytes` on
`OpenPositionsExpandedVM`.

The open-positions row-expand reads the existing `position_detail` SVG cache
(the SAME read-only call `build_trade_detail_vm` uses) so the expanded row can
inline the SB3 candlestick+BULZ-zones chart instead of the legacy static PNG.

ZERO-WRITE: the only DB read is `get_cached_chart_svg(... pipeline_run_id=None)`
(read-only); no JIT, no write-through. The `position_detail` cache row this
test seeds is TEST seeding (allowed), mirroring the pipeline write-through that
the SB3 chart step performs in production.
"""
from __future__ import annotations

from swing.data.db import connect


def _insert_open_trade(conn, *, ticker: str, entry_date: str = "2026-04-20",
                       status: str = "open") -> int:
    """Seed one active open trade + its paired entry fill.

    Mirrors `tests/web/test_routes/test_open_positions_expand.py:_insert_open_trade`
    (Phase 7 Sub-A: `status='open'` → `state='entered'`).
    """
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
    """Insert a `chart_renders` row with surface='position_detail' for the
    ticker (run-agnostic: pipeline_run_id IS NULL per the position_detail cache
    key). This mirrors the production SB3 write-through; it is TEST seeding.
    """
    from swing.data.models import ChartRender
    from swing.data.repos.chart_renders import insert_chart_render

    insert_chart_render(conn, ChartRender(
        id=None, ticker=ticker, surface="position_detail",
        chart_svg_bytes=svg, source_data_hash="hash-pd",
        rendered_at="2026-04-20T16:05:00", data_asof_date="2026-04-20",
        pipeline_run_id=None, pattern_class=None,
    ))


def test_expand_vm_carries_cached_svg(seeded_db):
    """VM carries the cached position_detail SVG when a cache row exists."""
    from swing.web.view_models.open_positions_row import (
        build_open_positions_expanded,
    )
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = _insert_open_trade(conn, ticker="AAPL")
            _seed_position_detail_cache(conn, ticker="AAPL")
        vm = build_open_positions_expanded(conn=conn, cfg=cfg, trade_id=trade_id)
    finally:
        conn.close()
    assert vm is not None
    assert vm.position_chart_svg_bytes is not None
    assert b"<svg" in vm.position_chart_svg_bytes


def test_expand_vm_none_when_no_cache_row(seeded_db):
    """VM carries None when no position_detail cache row exists for the ticker."""
    from swing.web.view_models.open_positions_row import (
        build_open_positions_expanded,
    )
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = _insert_open_trade(conn, ticker="AAPL")
        vm = build_open_positions_expanded(conn=conn, cfg=cfg, trade_id=trade_id)
    finally:
        conn.close()
    assert vm is not None
    assert vm.position_chart_svg_bytes is None
