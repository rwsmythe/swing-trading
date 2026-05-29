import sqlite3
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch
from swing.data.db import run_migrations
from swing.data.models import PatternEvaluation
from swing.pipeline.detection_chart_capture import render_and_capture_detection_chart


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp_path / "t.db")
    c.execute("PRAGMA foreign_keys=ON")
    run_migrations(c, target_version=22, backup_dir=tmp_path)
    # seed a pipeline_runs row so the FK is satisfiable
    c.execute(
        "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) VALUES "
        "(1, '2026-05-29T00:00:00', 'manual', '2026-05-28', '2026-05-29', "
        "'running', 'tok-cap-1')"
    )
    c.commit()
    return c


def _pe() -> PatternEvaluation:
    return PatternEvaluation(
        id=None, pipeline_run_id=1, ticker="AAA", pattern_class="vcp",
        detector_version="vcp_v1", geometric_score=0.7, geometric_score_json="{}",
        composite_score=0.7,
        structural_evidence_json='{"pivot_price":10.0,"base_top_price":9.5}',
        feature_distribution_log_json="{}", window_start_date="2026-01-01",
        window_end_date="2026-05-28", created_at="2026-05-29T00:00:00Z",
    )


def _bars() -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-05-28", periods=120)
    close = np.linspace(8, 10, 120)
    return pd.DataFrame({"Open": close, "High": close*1.02, "Low": close*0.98,
                         "Close": close, "Volume": 1e6}, index=idx)


def test_capture_returns_chart_render_id(conn):
    cid = render_and_capture_detection_chart(
        conn, ticker="AAA", bars=_bars(), pattern_evaluation=_pe(),
        pipeline_run_id=1, data_asof_date="2026-05-28")
    assert isinstance(cid, int)
    row = conn.execute(
        "SELECT surface, pattern_class, pipeline_run_id FROM chart_renders "
        "WHERE id = ?", (cid,)).fetchone()
    assert row == ("theme2_annotated", "vcp", 1)


def test_capture_returns_none_on_render_failure(conn):
    with patch(
        "swing.pipeline.detection_chart_capture.render_theme2_annotated_svg",
        return_value=b"",  # empty bytes -> F6 ChartRender barrier raises ValueError
    ):
        cid = render_and_capture_detection_chart(
            conn, ticker="AAA", bars=_bars(), pattern_evaluation=_pe(),
            pipeline_run_id=1, data_asof_date="2026-05-28")
    assert cid is None  # EXPECTED failure class (ValueError) -> NULL


def test_capture_propagates_unexpected_error(conn):
    # Codex chain #1 R2 Minor #1: an UNEXPECTED exception class (a programming
    # bug, e.g. TypeError) is NOT swallowed by the narrow except -- it
    # propagates so the caller logs it distinctly (not masked as "render
    # failed"). The detect-loop's own try/except then degrades to NULL, but
    # the bug is visible.
    with patch(
        "swing.pipeline.detection_chart_capture.render_theme2_annotated_svg",
        side_effect=TypeError("boom"),
    ):
        with pytest.raises(TypeError):
            render_and_capture_detection_chart(
                conn, ticker="AAA", bars=_bars(), pattern_evaluation=_pe(),
                pipeline_run_id=1, data_asof_date="2026-05-28")


def test_capture_cache_collision_last_writer_wins(conn):
    # Renderer-kwargs-uniformity / cache-collision mapping (Codex chain #1
    # Major #8; spec section 8.2 Expansion #10c): two captures on the same
    # (ticker, run, class) key -> 2nd refresh replaces the row
    # (DELETE-then-INSERT); only one row survives (last-writer-wins
    # coexistence with the exemplar theme2_annotated writer, FB-N3).
    c1 = render_and_capture_detection_chart(
        conn, ticker="AAA", bars=_bars(), pattern_evaluation=_pe(),
        pipeline_run_id=1, data_asof_date="2026-05-28")
    c2 = render_and_capture_detection_chart(
        conn, ticker="AAA", bars=_bars(), pattern_evaluation=_pe(),
        pipeline_run_id=1, data_asof_date="2026-05-28")
    n = conn.execute(
        "SELECT COUNT(*) FROM chart_renders WHERE ticker='AAA' "
        "AND surface='theme2_annotated' AND pipeline_run_id=1 "
        "AND pattern_class='vcp'").fetchone()[0]
    assert n == 1 and c2 != c1  # last-writer-wins
