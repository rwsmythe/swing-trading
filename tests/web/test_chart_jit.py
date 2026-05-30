"""Phase 13 T4.SB T-T4.SB.3 — JIT cache-miss chart-render helper tests.

Discriminating test coverage per plan §B.3 Sub-task 3A:
- cache hit returns cached bytes; OHLCV cache NOT consulted
- cache miss renders via OHLCV + writes through to cache
- OHLCV empty returns None; NO cache row written (F6 defense)
- cache collision: 2nd caller reads from cache (renderer fires once)
- Option A re-run collision invariant (Sub-task 3F per §1.5.3 amendment)
"""
from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.web.chart_jit import get_or_render_surface


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "chart_jit.db"
    return ensure_schema(db_path)


@pytest.fixture
def pipeline_run_id(conn: sqlite3.Connection) -> int:
    with conn:
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) "
            "VALUES ('2026-05-22T00:00:00.000', 'manual', '2026-05-22', "
            "'2026-05-22', 'complete', 'tok-jit')"
        )
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _planted_bars_df() -> pd.DataFrame:
    """Minimal OHLCV DataFrame to satisfy renderer signatures."""
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


def _plant_chart_render_row(
    conn: sqlite3.Connection,
    *,
    surface: str,
    ticker: str,
    pipeline_run_id: int | None,
    chart_svg_bytes: bytes,
    pattern_class: str | None = None,
) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO chart_renders "
            "(ticker, surface, pipeline_run_id, pattern_class, "
            "chart_svg_bytes, source_data_hash, rendered_at, data_asof_date) "
            "VALUES (?, ?, ?, ?, ?, 'planted', "
            "'2026-05-22T00:00:00Z', '2026-05-22')",
            (ticker, surface, pipeline_run_id, pattern_class, chart_svg_bytes),
        )
        return int(cur.lastrowid)


def test_get_or_render_surface_cache_hit_returns_cached_bytes(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    _plant_chart_render_row(
        conn, surface="ticker_detail", ticker="UCTT",
        pipeline_run_id=pipeline_run_id,
        chart_svg_bytes=b"<svg>cached</svg>",
    )
    ohlcv_cache = MagicMock()
    result = get_or_render_surface(
        conn=conn, ohlcv_cache=ohlcv_cache,
        surface="ticker_detail", ticker="UCTT",
        pipeline_run_id=pipeline_run_id,
        data_asof_date="2026-05-22",
    )
    assert result == b"<svg>cached</svg>"
    # On cache hit, OHLCV cache is NOT consulted.
    ohlcv_cache.get_or_fetch.assert_not_called()


def test_get_or_render_surface_cache_miss_renders_via_ohlcv_and_writes_through(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    # Inject a renderer mock to avoid matplotlib in the unit test.
    import swing.web.chart_jit as mod

    mod._RENDERERS["ticker_detail"] = MagicMock(
        return_value=b"<svg>rendered</svg>",
    )
    try:
        result = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="ticker_detail", ticker="UCTT",
            pipeline_run_id=pipeline_run_id,
            data_asof_date="2026-05-22",
        )
    finally:
        importlib.reload(mod)
    assert result == b"<svg>rendered</svg>"
    # Write-through populated cache.
    cached = conn.execute(
        "SELECT chart_svg_bytes FROM chart_renders "
        "WHERE surface = 'ticker_detail' AND ticker = 'UCTT' "
        "  AND pipeline_run_id = ?",
        (pipeline_run_id,),
    ).fetchone()
    assert cached is not None
    assert bytes(cached[0]) == b"<svg>rendered</svg>"


def test_get_or_render_surface_returns_none_on_empty_ohlcv(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = None
    result = get_or_render_surface(
        conn=conn, ohlcv_cache=ohlcv_cache,
        surface="ticker_detail", ticker="UCTT",
        pipeline_run_id=pipeline_run_id,
        data_asof_date="2026-05-22",
    )
    assert result is None
    # No cache row written (F6 construction-barrier defense — bytes never
    # produced because OHLCV missing).
    cached = conn.execute(
        "SELECT 1 FROM chart_renders WHERE ticker = 'UCTT'"
    ).fetchone()
    assert cached is None


def test_get_or_render_surface_returns_none_on_empty_dataframe_ohlcv(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Empty DataFrame from OHLCV cache should also return None + no cache write."""
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = pd.DataFrame()
    result = get_or_render_surface(
        conn=conn, ohlcv_cache=ohlcv_cache,
        surface="ticker_detail", ticker="UCTT",
        pipeline_run_id=pipeline_run_id,
        data_asof_date="2026-05-22",
    )
    assert result is None
    cached = conn.execute(
        "SELECT 1 FROM chart_renders WHERE ticker = 'UCTT'"
    ).fetchone()
    assert cached is None


def test_get_or_render_surface_returns_none_on_ohlcv_exception(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """OHLCV cache exception should degrade gracefully + return None."""
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.side_effect = RuntimeError("fetch boom")
    result = get_or_render_surface(
        conn=conn, ohlcv_cache=ohlcv_cache,
        surface="ticker_detail", ticker="UCTT",
        pipeline_run_id=pipeline_run_id,
        data_asof_date="2026-05-22",
    )
    assert result is None


def test_get_or_render_surface_returns_none_on_empty_render_bytes(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """F6 lesson: renderer returning empty bytes MUST NOT blank existing cache.

    Plant a known-good cache row; flip the renderer to return b""; assert
    the existing cache row is preserved verbatim (the helper short-circuits
    before any DELETE/INSERT). This is the construction-barrier defense
    from the CLAUDE.md F6 cumulative gotcha.
    """
    _plant_chart_render_row(
        conn, surface="market_weather", ticker="SPY",
        pipeline_run_id=pipeline_run_id,
        chart_svg_bytes=b"<svg>good</svg>",
    )
    # Force cache miss for a DIFFERENT ticker so we exercise the render path.
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    import swing.web.chart_jit as mod

    mod._RENDERERS["market_weather"] = MagicMock(return_value=b"")
    try:
        result = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="market_weather", ticker="QQQ",
            pipeline_run_id=pipeline_run_id,
            data_asof_date="2026-05-22",
        )
    finally:
        importlib.reload(mod)
    assert result is None
    # Existing SPY cache row preserved verbatim.
    rows = conn.execute(
        "SELECT ticker, chart_svg_bytes FROM chart_renders "
        "WHERE surface='market_weather'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "SPY"
    assert bytes(rows[0][1]) == b"<svg>good</svg>"


def test_get_or_render_surface_cache_collision_renderer_called_once(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Per Codex R4 M#3: two callers requesting the SAME (surface, ticker,
    pipeline_run_id) — renderer fires ONCE; second caller reads from cache.

    Renderer-kwargs uniformity LOCK: both callsites pass
    ``pattern_evaluation=None`` (V1 ticker_detail callsites).
    """
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    import swing.web.chart_jit as mod

    renderer = MagicMock(return_value=b"<svg>once</svg>")
    mod._RENDERERS["ticker_detail"] = renderer
    try:
        r1 = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="ticker_detail", ticker="UCTT",
            pipeline_run_id=pipeline_run_id,
            data_asof_date="2026-05-22",
            pattern_evaluation=None,  # Uniformity LOCK
        )
        r2 = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="ticker_detail", ticker="UCTT",
            pipeline_run_id=pipeline_run_id,
            data_asof_date="2026-05-22",
            pattern_evaluation=None,  # Uniformity LOCK
        )
    finally:
        importlib.reload(mod)
    assert r1 == r2 == b"<svg>once</svg>"
    assert renderer.call_count == 1
    cached_count = conn.execute(
        "SELECT COUNT(*) FROM chart_renders "
        "WHERE surface = 'ticker_detail' AND ticker = 'UCTT' "
        "  AND pipeline_run_id = ?",
        (pipeline_run_id,),
    ).fetchone()[0]
    assert cached_count == 1


def test_jit_writes_pipeline_run_id_matching_dashboard_anchor(
    conn: sqlite3.Connection,
) -> None:
    """Sub-task 3F: per spec §1.5.3 Option A LOCK — dashboard reader binds
    to ONE pipeline_run anchor; JIT writes match anchor even if a fresher
    run lands mid-session. Cache holds one row PER run_id; older anchor
    NOT clobbered.
    """
    with conn:
        cur = conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) "
            "VALUES ('2026-05-22T08:00:00', 'manual', '2026-05-22', "
            "'2026-05-22', 'complete', 'tok-r100')"
        )
        run_id_100 = int(cur.lastrowid)
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    import swing.web.chart_jit as mod

    mod._RENDERERS["ticker_detail"] = MagicMock(
        return_value=b"<svg>v100</svg>",
    )
    try:
        bytes_v100 = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="ticker_detail", ticker="UCTT",
            pipeline_run_id=run_id_100,
            data_asof_date="2026-05-22",
        )
        assert bytes_v100 == b"<svg>v100</svg>"
        # New pipeline_run lands; dashboard re-renders against run_id_101.
        with conn:
            cur = conn.execute(
                "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
                "action_session_date, state, lease_token) "
                "VALUES ('2026-05-22T18:00:00', 'manual', '2026-05-22', "
                "'2026-05-22', 'complete', 'tok-r101')"
            )
            run_id_101 = int(cur.lastrowid)
        mod._RENDERERS["ticker_detail"] = MagicMock(
            return_value=b"<svg>v101</svg>",
        )
        bytes_v101 = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="ticker_detail", ticker="UCTT",
            pipeline_run_id=run_id_101,
            data_asof_date="2026-05-22",
        )
        assert bytes_v101 == b"<svg>v101</svg>"
    finally:
        importlib.reload(mod)
    # Cache holds TWO rows — one per run_id. Old run_id NOT clobbered.
    rows = list(conn.execute(
        "SELECT pipeline_run_id, chart_svg_bytes FROM chart_renders "
        "WHERE surface='ticker_detail' AND ticker='UCTT' "
        "ORDER BY pipeline_run_id"
    ))
    assert len(rows) == 2
    assert rows[0][0] == run_id_100
    assert bytes(rows[0][1]) == b"<svg>v100</svg>"
    assert rows[1][0] == run_id_101
    assert bytes(rows[1][1]) == b"<svg>v101</svg>"


def test_get_or_render_surface_treats_empty_cached_bytes_as_miss(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Codex R1 Major #2 — F6 transient-empty defense MUST cover the
    cache-HIT path, not only the construction-barrier on writes.

    Plant a chart_renders row directly via raw SQL with
    ``chart_svg_bytes = b""`` (bypassing the ChartRender dataclass
    construction barrier — simulates legacy data OR a future writer
    that skips the dataclass). Call ``get_or_render_surface``. Assert
    the helper FALLS THROUGH to JIT render (does NOT return ``b""``)
    + write-through REPLACES the empty row with non-empty bytes.

    Pre-fix: ``get_or_render_surface`` returned the empty bytes
    verbatim because ``cached is not None`` short-circuited before any
    length check. Operator never recovered (zero-length blob stuck in
    cache; chart cell rendered as blank).
    """
    # Plant empty-bytes row via raw SQL (bypass ChartRender barrier).
    with conn:
        conn.execute(
            "INSERT INTO chart_renders "
            "(ticker, surface, pipeline_run_id, pattern_class, "
            "chart_svg_bytes, source_data_hash, rendered_at, data_asof_date) "
            "VALUES (?, ?, ?, NULL, ?, 'legacy-empty', "
            "'2026-05-22T00:00:00Z', '2026-05-22')",
            ("UCTT", "ticker_detail", pipeline_run_id, b""),
        )
    # Sanity: legacy empty row exists.
    legacy = conn.execute(
        "SELECT length(chart_svg_bytes) FROM chart_renders "
        "WHERE ticker='UCTT' AND surface='ticker_detail' "
        "  AND pipeline_run_id=?",
        (pipeline_run_id,),
    ).fetchone()
    assert legacy[0] == 0

    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()

    import swing.web.chart_jit as mod

    renderer = MagicMock(return_value=b"<svg>recovered</svg>")
    mod._RENDERERS["ticker_detail"] = renderer
    try:
        result = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="ticker_detail", ticker="UCTT",
            pipeline_run_id=pipeline_run_id,
            data_asof_date="2026-05-22",
        )
    finally:
        importlib.reload(mod)
    # Post-fix: helper falls through to render; returns non-empty bytes.
    assert result == b"<svg>recovered</svg>"
    # Renderer WAS invoked (pre-fix would have short-circuited at cache hit).
    assert renderer.call_count == 1
    # Write-through replaced the empty row with the rendered bytes.
    rows = list(conn.execute(
        "SELECT chart_svg_bytes FROM chart_renders "
        "WHERE ticker='UCTT' AND surface='ticker_detail' "
        "  AND pipeline_run_id=?",
        (pipeline_run_id,),
    ))
    assert len(rows) == 1
    assert bytes(rows[0][0]) == b"<svg>recovered</svg>"


def test_chart_jit_market_weather_default_is_undefined(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """Phase 14 SB3 T-3.4 (§C.4a): the dead/defensive JIT market_weather
    branch defaults trend_template_state to an honest "undefined" (NOT the
    old "stage_2"). BEHAVIORAL: spy the renderer + assert the kwarg value.
    """
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    import swing.web.chart_jit as mod

    captured: dict = {}

    def spy(*, bars, trend_template_state):
        captured["trend_template_state"] = trend_template_state
        return b"<svg>jit</svg>"

    mod._RENDERERS["market_weather"] = spy
    try:
        get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="market_weather", ticker="SPY",
            pipeline_run_id=pipeline_run_id,
            data_asof_date="2026-05-22",
        )
    finally:
        importlib.reload(mod)
    assert captured.get("trend_template_state") == "undefined"


# ---------------------------------------------------------------------------
# Phase 14 SB3 T-3.5 (plan §C.6, OQ-4) — P14.N1 thumbnail substrate proof.
#
# Substrate-only: prove ``render_watchlist_thumbnail_svg`` (the line-chart
# 200x100 thumbnail) is REUSABLE as the substrate for open-position / hyp-rec
# table thumbnails via the existing ``watchlist_row`` JIT surface — with NO
# new renderer, NO new surface enum, and NO consuming-surface row TEMPLATE
# wiring (deferred to SB4). The thumbnail STAYS a line chart.
# ---------------------------------------------------------------------------


def test_jit_renders_watchlist_thumbnail_for_non_watchlist_ticker(
    conn: sqlite3.Connection, pipeline_run_id: int,
) -> None:
    """A non-watchlist ticker (e.g. an open-position ticker that rotated out
    of finviz) renders + caches a ``watchlist_row`` thumbnail through the JIT
    via the SAME run-bound (ticker, pipeline_run_id) cache key. Uses the REAL
    ``render_watchlist_thumbnail_svg`` substrate (no renderer mock) so the
    proof exercises the actual line-chart renderer. The second call returns
    the cached row byte-identical (write-through reuse).
    """
    from swing.web.chart_jit import _WATCHLIST_THUMBNAIL_MA_LINES

    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()

    r1 = get_or_render_surface(
        conn=conn, ohlcv_cache=ohlcv_cache,
        surface="watchlist_row", ticker="ZZZZ",
        pipeline_run_id=pipeline_run_id,
        data_asof_date="2026-05-22",
        ma_lines=_WATCHLIST_THUMBNAIL_MA_LINES,
    )
    assert r1 is not None
    assert b"</svg>" in r1
    # Write-through populated a run-bound watchlist_row cache row.
    rows = list(conn.execute(
        "SELECT chart_svg_bytes, pipeline_run_id FROM chart_renders "
        "WHERE surface='watchlist_row' AND ticker='ZZZZ'"
    ))
    assert len(rows) == 1
    assert rows[0][1] == pipeline_run_id

    # Second call reads from cache — byte-identical (substrate reuse). The
    # OHLCV cache is consulted exactly once (first render only).
    r2 = get_or_render_surface(
        conn=conn, ohlcv_cache=ohlcv_cache,
        surface="watchlist_row", ticker="ZZZZ",
        pipeline_run_id=pipeline_run_id,
        data_asof_date="2026-05-22",
        ma_lines=_WATCHLIST_THUMBNAIL_MA_LINES,
    )
    assert r2 == r1
    assert ohlcv_cache.get_or_fetch.call_count == 1


def test_open_position_and_hyprec_row_vms_expose_thumbnail_binding(
    conn: sqlite3.Connection,
) -> None:
    """Substrate-binding contract proof (NO production change expected): the
    open-position + hyp-rec row VMs already expose the ``ticker`` the
    thumbnail substrate needs, and the run binding ``(pipeline_run_id,
    data_asof_date)`` is resolvable from VM context via
    ``latest_completed_pipeline_run(conn)`` (the same anchor the dashboard
    binds to). This unblocks SB4's row-template wiring without any template
    change here.
    """
    from swing.web.chart_scope import latest_completed_pipeline_run
    from swing.web.view_models.dashboard import HypothesisRecommendation
    from swing.web.view_models.open_positions_row import OpenPositionsRowVM

    # The hyp-rec row VM exposes `ticker` directly (the substrate's first
    # identity coordinate).
    assert "ticker" in HypothesisRecommendation.__dataclass_fields__

    # OpenPositionsRowVM carries the `trade` (which holds `.ticker`); confirm
    # the substrate's ticker is resolvable from the VM.
    op_fields = OpenPositionsRowVM.__dataclass_fields__
    assert "trade" in op_fields

    # The run binding is resolvable from VM context: build a completed run +
    # confirm latest_completed_pipeline_run returns the (run_id, data_asof)
    # pair the substrate cache key needs.
    with conn:
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, finished_ts, trigger, "
            "data_asof_date, action_session_date, state, lease_token) "
            "VALUES ('2026-05-22T08:00:00', '2026-05-22T08:05:00', 'manual', "
            "'2026-05-22', '2026-05-22', 'complete', 'tok-bind')"
        )
    binding = latest_completed_pipeline_run(conn)
    assert binding is not None
    assert isinstance(binding.run_id, int)
    assert binding.data_asof_date == "2026-05-22"
