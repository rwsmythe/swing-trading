"""Phase 13 T-T4.SB.3 Sub-task 3F (§1.5.3 amendment LOCK) — Option A
re-run collision invariant assertion at the dashboard-anchor binding level.

Per spec §1.5.3 LOCK: the dashboard reader binds to ONE pipeline_run anchor
via ``swing/web/chart_scope.py:latest_completed_pipeline_run(conn)``. The
JIT helper takes that anchor's ``run_id`` verbatim and writes through to
``chart_renders`` keyed on the SAME ``pipeline_run_id``. When a fresher
pipeline_run lands mid-session, the dashboard's NEXT request rebinds to
the new anchor — and the JIT writes to the NEW anchor's key. The OLD
anchor's row is preserved untouched (NOT clobbered).

This invariant test exercises both the helper-level guarantee (in
``test_chart_jit.py`` already) AND the binding-discipline LOCK at the
``latest_completed_pipeline_run`` chart-scope helper level: walks the
anchor flip explicitly via the chart_scope helper and asserts the JIT
helper's writes track the anchor's ``run_id`` field exactly.
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
from swing.web.chart_scope import latest_completed_pipeline_run


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "option_a.db")


def _planted_bars_df() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=60, freq="B")
    return pd.DataFrame(
        {
            "Open": [10.0] * 60,
            "High": [10.5] * 60,
            "Low": [9.5] * 60,
            "Close": [10.2] * 60,
            "Volume": [1_000_000] * 60,
        },
        index=dates,
    )


def _seed_completed_pipeline_run(
    conn: sqlite3.Connection, *,
    finished_ts: str, data_asof: str, token: str,
) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO pipeline_runs (started_ts, finished_ts, trigger, "
            "data_asof_date, action_session_date, state, lease_token) "
            "VALUES (?, ?, 'manual', ?, ?, 'complete', ?)",
            (finished_ts, finished_ts, data_asof, data_asof, token),
        )
        return int(cur.lastrowid)


def test_option_a_dashboard_anchor_flip_does_not_clobber_old_run_id(
    conn: sqlite3.Connection,
):
    """Per §1.5.3 Option A LOCK: anchor flip mid-session yields TWO
    chart_renders rows (one per run_id); the OLD run_id's row is
    preserved verbatim.

    Discriminating against the alternative "Option B" semantic where
    the cache would be keyed agnostic of run_id and the second JIT write
    would clobber the first.
    """
    run_id_100 = _seed_completed_pipeline_run(
        conn, finished_ts="2026-05-22T08:00:00",
        data_asof="2026-05-22", token="tok-100",
    )
    # Dashboard request 1: binding pins run_id_100.
    binding_v1 = latest_completed_pipeline_run(conn)
    assert binding_v1 is not None
    assert binding_v1.run_id == run_id_100

    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = _planted_bars_df()
    import swing.web.chart_jit as mod

    mod._RENDERERS["hyprec_detail"] = MagicMock(
        return_value=b"<svg>v100-bytes</svg>",
    )
    try:
        bytes_v100 = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="hyprec_detail", ticker="UCTT",
            pipeline_run_id=binding_v1.run_id,
            data_asof_date=binding_v1.data_asof_date,
        )
        assert bytes_v100 == b"<svg>v100-bytes</svg>"

        # New pipeline run completes mid-session.
        run_id_101 = _seed_completed_pipeline_run(
            conn, finished_ts="2026-05-22T18:00:00",
            data_asof="2026-05-22", token="tok-101",
        )
        # Dashboard request 2: binding pins the FRESHER run.
        binding_v2 = latest_completed_pipeline_run(conn)
        assert binding_v2 is not None
        assert binding_v2.run_id == run_id_101

        mod._RENDERERS["hyprec_detail"] = MagicMock(
            return_value=b"<svg>v101-bytes</svg>",
        )
        bytes_v101 = get_or_render_surface(
            conn=conn, ohlcv_cache=ohlcv_cache,
            surface="hyprec_detail", ticker="UCTT",
            pipeline_run_id=binding_v2.run_id,
            data_asof_date=binding_v2.data_asof_date,
        )
        assert bytes_v101 == b"<svg>v101-bytes</svg>"
    finally:
        importlib.reload(mod)

    # Anchor-flip invariant: TWO rows persisted (one per run_id);
    # the OLD anchor's bytes preserved verbatim (not clobbered).
    rows = list(conn.execute(
        "SELECT pipeline_run_id, chart_svg_bytes FROM chart_renders "
        "WHERE surface='hyprec_detail' AND ticker='UCTT' "
        "ORDER BY pipeline_run_id"
    ))
    assert len(rows) == 2
    assert rows[0][0] == run_id_100
    assert bytes(rows[0][1]) == b"<svg>v100-bytes</svg>"
    assert rows[1][0] == run_id_101
    assert bytes(rows[1][1]) == b"<svg>v101-bytes</svg>"
