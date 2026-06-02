"""F-3: the rolling-line polyline is segmented at None gaps (one segment per
contiguous non-None run; 1-point segments dropped) so gaps render as gaps."""
from __future__ import annotations

from swing.web.view_models.metrics.process_grade_trend import (
    RollingLinePoint,
    _format_polyline_segments,
)


def _pts(values):
    return tuple(
        RollingLinePoint(ordinal=i, value=v) for i, v in enumerate(values)
    )


_GEOM = dict(
    total_points=6, y_min=0.0, y_max=4.0,
    layout_width=400, layout_height=120,
    margin_left=10, margin_right=10, margin_top=5, margin_bottom=5,
)


def test_contiguous_series_one_segment():
    segs = _format_polyline_segments(_pts([1.0, 2.0, 3.0, 2.0]), **_GEOM)
    assert len(segs) == 1
    assert segs[0].count(",") == 4  # 4 points


def test_gap_splits_into_two_segments():
    segs = _format_polyline_segments(_pts([1.0, 2.0, None, 3.0, 4.0]), **_GEOM)
    assert len(segs) == 2


def test_one_point_segments_dropped():
    # A lone defined point between gaps is not a line -> dropped.
    segs = _format_polyline_segments(_pts([1.0, None, 9.0, None, 2.0, 3.0]), **_GEOM)
    assert len(segs) == 1  # only the trailing 2-point run survives


def test_all_none_is_empty():
    segs = _format_polyline_segments(_pts([None, None]), **_GEOM)
    assert segs == ()


def test_leading_and_trailing_gaps_trimmed():
    segs = _format_polyline_segments(_pts([None, 1.0, 2.0, None]), **_GEOM)
    assert len(segs) == 1
    assert segs[0].count(",") == 2  # 2 points
