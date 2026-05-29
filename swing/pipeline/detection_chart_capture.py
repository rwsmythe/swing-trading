"""Render + capture a detection's theme2_annotated chart at detect time
(Phase 14 Sub-bundle 2, spec section 8). Caller-tx: uses the passed conn;
does NOT open its own transaction (refresh_chart_render is caller-tx).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime

import pandas as pd

from swing.data.models import ChartRender, PatternEvaluation
from swing.data.repos.chart_renders import refresh_chart_render
from swing.web.charts import render_theme2_annotated_svg

log = logging.getLogger(__name__)


def render_and_capture_detection_chart(
    conn: sqlite3.Connection, *, ticker: str, bars: pd.DataFrame,
    pattern_evaluation: PatternEvaluation, pipeline_run_id: int,
    data_asof_date: str,
) -> int | None:
    """Render the theme2_annotated chart for a detection + cache it via the
    standard refresh_chart_render (last-writer-wins coexistence with the
    exemplar path). Returns the chart_render_id, or None on any render/F6
    failure (the caller still inserts the detection with chart_render_id=NULL
    + emits a gotcha #27 warning).
    """
    try:
        svg = render_theme2_annotated_svg(
            ticker=ticker, bars=bars, pattern_evaluation=pattern_evaluation,
        )
        chart = ChartRender(
            id=None, ticker=ticker, surface="theme2_annotated",
            chart_svg_bytes=svg, source_data_hash="detection_capture_v1",
            rendered_at=datetime.now(UTC).isoformat(),
            data_asof_date=data_asof_date,
            pipeline_run_id=pipeline_run_id,
            pattern_class=pattern_evaluation.pattern_class,
        )
        return refresh_chart_render(conn, chart)
    except (ValueError, RuntimeError, OSError) as exc:
        # NARROW catch (Codex chain #1 Major #7): isolate the EXPECTED failure
        # classes only -- ValueError (the F6 empty-bytes ChartRender barrier +
        # any annotator value error), RuntimeError/OSError (matplotlib render
        # hiccups, font/backend I/O). Programming errors (AttributeError,
        # TypeError, KeyError) propagate to the caller's emit-loop try/except
        # (T-2.4 step 11) where they are logged distinctly -- they must NOT be
        # silently masked as a chart-render failure.
        log.warning(
            "detection chart capture failed for (%s, %s): %s",
            ticker, pattern_evaluation.pattern_class, exc,
        )
        return None
