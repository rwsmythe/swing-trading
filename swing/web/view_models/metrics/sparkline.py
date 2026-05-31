"""Inline-SVG sparkline points helper for the /metrics overview (P14.N5).

Pure + suppression-aware. Generalises the process_grade_trend polyline
algorithm (``view_models/metrics/process_grade_trend.py:_format_polyline_points``)
down to a tiny ~100x30 glyph. NO matplotlib, NO render lock, ASCII-only
(OQ-1 / L6 LOCK).

X is positioned over the ORIGINAL sequence index ``i / (len(values) - 1)``
so a ``None`` gap leaves a horizontal gap in spacing and does NOT compress
time. Y is normalised over [min..max] of the DEFINED values, inverted for
SVG's y-down axis. A flat series (max == min) maps to the mid-line. A single
connected polyline draws across ``None`` gaps (omitting their vertices) -
matching the existing process_grade_trend drill-down precedent. Returns
``None`` when fewer than ``min_points`` values are defined (the caller renders
an honest suppressed caption; never a fabricated/flat line - L4).
"""
from __future__ import annotations

from collections.abc import Sequence


def build_sparkline_points(
    values: Sequence[float | None],
    *,
    width: int = 100,
    height: int = 30,
    pad: float = 2.0,
    min_points: int = 2,
) -> str | None:
    """Return an SVG ``<polyline>`` points string ``"x1,y1 x2,y2 ..."`` (2-dp)
    for ``values``, or ``None`` when fewer than ``min_points`` are defined."""
    if width <= 0 or height <= 0:
        raise ValueError(f"width/height must be > 0; got {width!r}x{height!r}")
    n = len(values)
    if n < min_points:
        return None
    defined = [(i, float(v)) for i, v in enumerate(values) if v is not None]
    if len(defined) < min_points:
        return None

    ys = [v for _, v in defined]
    y_min, y_max = min(ys), max(ys)
    plot_w = float(width) - 2.0 * pad
    plot_h = float(height) - 2.0 * pad
    denom = n - 1  # n >= min_points >= 2 -> denom >= 1, no ZeroDivision

    pieces: list[str] = []
    for i, v in defined:
        x = pad + plot_w * (i / denom)
        if y_max == y_min:
            y = pad + plot_h / 2.0
        else:
            norm = (v - y_min) / (y_max - y_min)
            y = pad + plot_h * (1.0 - norm)
        pieces.append(f"{x:.2f},{y:.2f}")
    return " ".join(pieces)


__all__ = ["build_sparkline_points"]
