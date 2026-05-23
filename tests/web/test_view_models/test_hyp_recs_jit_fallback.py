"""Phase 13 T-T4.SB.3 (Item 5) — build_hyp_recs_expanded JIT fallback tests.

Discriminating coverage per plan §B.3 Sub-task 3C:
- JIT fallback fires on cache miss when all 4 gates pass (ohlcv_cache
  provided + pipeline_run_id non-NULL + data_asof_date non-NULL).
- JIT fallback SKIPS when ohlcv_cache is None.
- JIT fallback writes through with the correct data_asof_date.
"""
from __future__ import annotations

import importlib
from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd

from swing.data.db import connect

# Reuse the seeding helper from the canonical hyp-recs VM tests.
from tests.web.test_view_models.test_hyp_recs_expansion_vm import (
    _seed_complete_pipeline,
)


def _planted_bars_df() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=60, freq="B")
    return pd.DataFrame(
        {
            "Open": [10.0 + i * 0.1 for i in range(60)],
            "High": [10.5 + i * 0.1 for i in range(60)],
            "Low": [9.5 + i * 0.1 for i in range(60)],
            "Close": [10.2 + i * 0.1 for i in range(60)],
            "Volume": [1000000 + i * 1000 for i in range(60)],
        },
        index=dates,
    )


def test_build_hyp_recs_expanded_jit_fallback_on_cache_miss(seeded_db):
    """JIT fires when cache is empty + ohlcv_cache + run_id + asof_date OK."""
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    _seed_complete_pipeline(
        cfg,
        candidates=[{"ticker": "UCTT", "pivot": 200.0, "initial_stop": 190.0}],
    )
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    import swing.web.chart_jit as mod

    mod._RENDERERS["hyprec_detail"] = MagicMock(
        return_value=b"<svg>jit-hyprec</svg>",
    )
    try:
        conn = connect(cfg.paths.db_path)
        try:
            vm = build_hyp_recs_expanded(
                conn, cfg, ticker="UCTT", current_balance=10_000.0,
                ohlcv_cache=ohlcv_cache,
            )
        finally:
            conn.close()
    finally:
        importlib.reload(mod)
    assert vm is not None
    assert vm.hyprec_detail_chart_svg_bytes == b"<svg>jit-hyprec</svg>"
    # Verify data_asof_date was threaded through to the write-through path.
    conn = connect(cfg.paths.db_path)
    try:
        cached_row = conn.execute(
            "SELECT data_asof_date FROM chart_renders "
            "WHERE surface='hyprec_detail' AND ticker='UCTT'"
        ).fetchone()
    finally:
        conn.close()
    assert cached_row is not None
    assert cached_row[0] == "2026-04-28"


def test_build_hyp_recs_expanded_skips_jit_when_ohlcv_cache_missing(
    seeded_db,
):
    """Per R3 LOCK + plan §B.3 Sub-task 3C.1: JIT helper requires
    ohlcv_cache. VM builder gates the fallback; with ohlcv_cache=None
    the builder leaves bytes None + renderer must not fire."""
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    _seed_complete_pipeline(
        cfg,
        candidates=[{"ticker": "UCTT", "pivot": 200.0, "initial_stop": 190.0}],
    )
    import swing.web.chart_jit as mod

    renderer = MagicMock(return_value=b"<svg>jit-hyprec</svg>")
    mod._RENDERERS["hyprec_detail"] = renderer
    try:
        conn = connect(cfg.paths.db_path)
        try:
            vm = build_hyp_recs_expanded(
                conn, cfg, ticker="UCTT", current_balance=10_000.0,
                ohlcv_cache=None,
            )
        finally:
            conn.close()
    finally:
        importlib.reload(mod)
    # No JIT fallback fires; bytes remain None.
    assert vm is not None
    assert vm.hyprec_detail_chart_svg_bytes is None
    renderer.assert_not_called()


def test_build_hyp_recs_expanded_cache_hit_does_not_invoke_jit(seeded_db):
    """When the cache row already exists, the builder must NOT live-render."""
    from swing.web.view_models.dashboard import build_hyp_recs_expanded

    cfg, _ = seeded_db
    pipeline_run_id = _seed_complete_pipeline(
        cfg,
        candidates=[{"ticker": "UCTT", "pivot": 200.0, "initial_stop": 190.0}],
    )
    # Plant a cache row matching the canonical reader's key shape.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO chart_renders "
                "(ticker, surface, pipeline_run_id, pattern_class, "
                "chart_svg_bytes, source_data_hash, rendered_at, data_asof_date) "
                "VALUES ('UCTT', 'hyprec_detail', ?, NULL, ?, 'planted', "
                "'2026-04-29T09:00:00Z', '2026-04-28')",
                (pipeline_run_id, b"<svg>planted</svg>"),
            )
    finally:
        conn.close()
    ohlcv_cache = MagicMock()
    import swing.web.chart_jit as mod

    renderer = MagicMock(return_value=b"<svg>jit-hyprec</svg>")
    mod._RENDERERS["hyprec_detail"] = renderer
    try:
        conn = connect(cfg.paths.db_path)
        try:
            vm = build_hyp_recs_expanded(
                conn, cfg, ticker="UCTT", current_balance=10_000.0,
                ohlcv_cache=ohlcv_cache,
            )
        finally:
            conn.close()
    finally:
        importlib.reload(mod)
    assert vm is not None
    # Returned the PLANTED cached bytes — JIT did NOT fire.
    assert vm.hyprec_detail_chart_svg_bytes == b"<svg>planted</svg>"
    renderer.assert_not_called()
    # OHLCV cache should NOT have been consulted on cache hit.
    ohlcv_cache.get_or_fetch.assert_not_called()
