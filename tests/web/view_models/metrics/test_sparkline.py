"""T-5.1 — pure inline-SVG sparkline points helper (P14.N5)."""
from __future__ import annotations

import pytest

from swing.web.view_models.metrics.sparkline import build_sparkline_points


def _coords(points: str) -> list[tuple[float, float]]:
    return [tuple(float(c) for c in pair.split(",")) for pair in points.split(" ")]


def test_two_points_emits_two_vertices_spanning_width():
    out = build_sparkline_points([0.0, 10.0], width=100, height=30, pad=2.0)
    assert out is not None
    coords = _coords(out)
    assert len(coords) == 2
    assert coords[0][0] == pytest.approx(2.0)
    assert coords[1][0] == pytest.approx(98.0)
    assert coords[0][1] > coords[1][1]  # 0.0 lower on screen than 10.0 (y-down)


def test_empty_returns_none():
    assert build_sparkline_points([]) is None


def test_all_none_returns_none():
    assert build_sparkline_points([None, None, None]) is None


def test_single_defined_returns_none():
    assert build_sparkline_points([5.0]) is None
    assert build_sparkline_points([None, 5.0, None]) is None


def test_flat_series_is_mid_line():
    out = build_sparkline_points([5.0, 5.0, 5.0], width=100, height=30, pad=2.0)
    assert out is not None
    ys = [y for _, y in _coords(out)]
    assert all(y == pytest.approx(15.0) for y in ys)  # height/2 mid-line


def test_none_gap_does_not_compress_x_axis():
    out = build_sparkline_points([5.0, None, 7.0], width=100, height=30, pad=2.0)
    assert out is not None
    coords = _coords(out)
    assert len(coords) == 2  # None vertex omitted (single connected line)
    assert coords[0][0] == pytest.approx(2.0)   # index 0
    assert coords[1][0] == pytest.approx(98.0)  # index 2, NOT compressed to index 1


def test_two_dp_formatting():
    out = build_sparkline_points([1.0, 2.0, 3.0])
    assert out is not None
    for pair in out.split(" "):
        x, y = pair.split(",")
        assert len(x.split(".")[1]) == 2
        assert len(y.split(".")[1]) == 2


def test_non_positive_dimensions_raise():
    with pytest.raises(ValueError):
        build_sparkline_points([1.0, 2.0], width=0)
    with pytest.raises(ValueError):
        build_sparkline_points([1.0, 2.0], height=-1)


def test_ascii_only_output():
    out = build_sparkline_points([1.0, 2.0, 3.0])
    assert out is not None and out.isascii()
