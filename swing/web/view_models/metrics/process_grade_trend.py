"""View-model for spec §4.8 process-grade-trend (Sub-bundle E Task T-E.2).

Wraps :class:`swing.metrics.process_grade_trend.ProcessGradeTrendResult`
for template consumption with the shared :class:`BaseLayoutVM` mixin per
plan §A.18 + §I.5.

Per plan §A.10 LOCK: chart renders as inline SVG (NOT matplotlib PNG +
NOT client-side chart library). Avoids the CLAUDE.md matplotlib mathtext
gotcha entirely.

Per spec §5.4 + plan §A.7 amended Decoupling discipline + forward-binding
lesson #23: the 3-tuple decoupling — confidence-floor warning +
window-not-full warning + drawability_text — surface as SEPARATE
template-rendering targets (NOT combined; NOT title= hover-only). The VM
exposes each as a dedicated field on per-metric series.

Per plan §A.9 + §I.6 LOCK: pure server-rendered HTML — NO HTMX OOB-swap,
NO HX-Redirect, NO embedded forms.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.evaluation.dates import action_session_for_run
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.metrics.honesty import (
    BootstrapCI,
    HonestyBadges,
    WilsonCI,
)
from swing.metrics.process_grade_trend import (
    DEFAULT_WINDOW_SIZE,
    PROCESS_GRADE_TREND_METRIC_CLASSES,
    ProcessGradeTrendPoint,
    ProcessGradeTrendResult,
    RollingLinePoint,
    compute_process_grade_trend,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM

# SVG layout constants — plan §A.10 inline SVG.
SVG_WIDTH: int = 800
SVG_HEIGHT: int = 360
SVG_MARGIN_LEFT: int = 56
SVG_MARGIN_RIGHT: int = 16
SVG_MARGIN_TOP: int = 24
SVG_MARGIN_BOTTOM: int = 40

# Grade-axis Y-encoding. Lesson #19 unit-semantic precision: A=4..F=0
# visible as axis label so operator reads grade values, not raw numerics.
GRADE_AXIS_LABELS: tuple[tuple[float, str], ...] = (
    (4.0, "A=4"),
    (3.0, "B=3"),
    (2.0, "C=2"),
    (1.0, "D=1"),
    (0.0, "F=0"),
)


@dataclass(frozen=True)
class RollingSeriesDisplay:
    """Per-metric display fields surfaced to the template.

    Per forward-binding lesson #23: each badge + drawability_text lives in
    its own field so the template renders them as separate text elements,
    NOT combined or `title=` hover-only. Discriminating tests assert
    ``data-{marker}=`` substrings.
    """

    metric_name: str
    underlying_class: str
    is_suppressed: bool
    suppressed_placeholder: str | None
    # When NOT suppressed, the per-window value rendering:
    point_value_text: str | None
    ci_lower_text: str | None
    ci_upper_text: str | None
    # Three distinct cadence/confidence signals per spec §5.4 + lesson #23:
    drawability_text: str | None
    window_not_full_warning_text: str | None
    confidence_floor_warning_text: str | None
    # SVG polyline points strings, one per contiguous non-None run; () when
    # not drawable (a single <polyline> cannot bridge a None gap; F-3).
    svg_polyline_segments: tuple[str, ...]
    # Whether at least one >=2-point rolling-line segment is renderable.
    is_drawable: bool

    def __post_init__(self) -> None:
        if self.is_suppressed and not self.suppressed_placeholder:
            raise ValueError(
                "RollingSeriesDisplay.suppressed_placeholder required when "
                "is_suppressed=True"
            )


@dataclass(frozen=True)
class PerTradeMarkerDisplay:
    """Per-trade marker in SVG coordinates for the line chart.

    ``y_grade_numeric`` is the Y for grade-encoded marker (4..0). NULL
    when the underlying grade letter was None (legacy / in-progress
    review). Templates render only markers with non-NULL Y.
    """

    ordinal: int
    trade_id: int
    ticker: str
    review_date: str
    process_grade_letter: str | None
    process_grade_numeric: float | None
    # SVG-space coordinates for the grade chart:
    svg_x: float
    svg_y: float | None  # None when grade letter is None
    disqualifying: int


@dataclass(frozen=True)
class ProcessGradeTrendVM(BaseLayoutVM):
    """VM for ``GET /metrics/process-grade-trend`` per plan §H T-E.2.

    Carries the §4.8 surface data:
      - per-trade markers (always rendered when trades exist).
      - per-metric rolling series (suppressed-or-drawable per §5.4).
      - SVG layout constants for the template.
    """

    window_size: int = DEFAULT_WINDOW_SIZE
    per_trade_markers: tuple[PerTradeMarkerDisplay, ...] = ()
    rolling_series: tuple[RollingSeriesDisplay, ...] = ()
    svg_width: int = SVG_WIDTH
    svg_height: int = SVG_HEIGHT
    svg_margin_left: int = SVG_MARGIN_LEFT
    svg_margin_right: int = SVG_MARGIN_RIGHT
    svg_margin_top: int = SVG_MARGIN_TOP
    svg_margin_bottom: int = SVG_MARGIN_BOTTOM
    grade_axis_labels: tuple[tuple[float, str], ...] = GRADE_AXIS_LABELS

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.window_size <= 0:
            raise ValueError(
                f"ProcessGradeTrendVM.window_size must be > 0; got {self.window_size!r}"
            )
        expected = set(PROCESS_GRADE_TREND_METRIC_CLASSES)
        got = {s.metric_name for s in self.rolling_series}
        if got != expected:
            missing = expected - got
            extra = got - expected
            raise ValueError(
                "ProcessGradeTrendVM.rolling_series metric names must match "
                f"the §A.21 matrix; missing={sorted(missing)!r}, extra={sorted(extra)!r}"
            )


# ----------------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------------

# Y-axis ranges per metric class:
#  - Grade rollings + "B" cost-per-trade: [0, 4] (grade scale).
#  - Disqualifying-rate (Class A): [0, 1] proportion.
#  - mistake_cost_R_total (point): scaled to data range; suppress chart
#    when no samples.
_GRADE_METRICS: frozenset[str] = frozenset({
    "process_grade_rolling_N",
    "entry_grade_rolling_N",
    "management_grade_rolling_N",
    "exit_grade_rolling_N",
})


def _format_text(value: float | None, *, decimals: int = 2) -> str:
    """Format finite float to fixed-decimal text; '—' for None/NaN."""
    if value is None or not math.isfinite(value):
        return "—"
    return f"{value:.{decimals}f}"


def _format_value_slot(
    value: WilsonCI | BootstrapCI | float | None,
) -> tuple[str | None, str | None, str | None]:
    """Return (point_text, ci_lower_text, ci_upper_text)."""
    if value is None:
        return (None, None, None)
    if isinstance(value, WilsonCI | BootstrapCI):
        return (
            _format_text(value.point),
            _format_text(value.lower),
            _format_text(value.upper),
        )
    # bare float ("point" class)
    return (_format_text(float(value)), None, None)


def _badge_texts(
    badges: HonestyBadges | None,
    *,
    drawability_text: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Compose three distinct badge texts per lesson #23.

    Returns (drawability_text, window_not_full_text, confidence_floor_text).
    All three may be None (no badge to render).
    """
    if badges is None:
        return (None, None, None)
    window_text: str | None = None
    floor_text: str | None = None
    if badges.window_not_full_warning:
        window_text = "rolling window not yet at N"
    if badges.confidence_floor_warning:
        floor_text = "below confidence floor (n<20)"
    return (drawability_text, window_text, floor_text)


def _polyline_x(
    ordinal: int,
    *,
    total_points: int,
    layout_width: int,
    margin_left: int,
    margin_right: int,
) -> float:
    """Map ordinal to SVG-space X coordinate."""
    plot_width = layout_width - margin_left - margin_right
    if total_points <= 1:
        return float(margin_left)
    step = plot_width / max(1, total_points - 1)
    return float(margin_left) + step * ordinal


def _polyline_y(
    value: float,
    *,
    y_min: float,
    y_max: float,
    layout_height: int,
    margin_top: int,
    margin_bottom: int,
) -> float:
    """Map raw value to SVG-space Y coordinate.

    SVG Y axis grows DOWNWARD — high values map to small Y; low values
    map to large Y.
    """
    plot_height = layout_height - margin_top - margin_bottom
    if y_max == y_min:
        return float(margin_top) + plot_height / 2
    normalized = (value - y_min) / (y_max - y_min)
    return float(margin_top) + plot_height * (1.0 - normalized)


def _format_polyline_segments(
    line_points: tuple[RollingLinePoint, ...],
    *,
    total_points: int,
    y_min: float,
    y_max: float,
    layout_width: int,
    layout_height: int,
    margin_left: int,
    margin_right: int,
    margin_top: int,
    margin_bottom: int,
) -> tuple[str, ...]:
    """SVG polyline ``points`` strings, ONE per contiguous non-None run.

    A single ``<polyline>`` cannot contain a break, so a None gap in the
    rolling-mean series (operational <3 floor) must split into multiple
    polyline elements -- otherwise the line bridges the gap with a straight
    diagonal. Runs of a single defined point are dropped (one point is not a
    line). Returns () when no >=2-point run exists.
    """
    segments: list[str] = []
    current: list[str] = []

    def _flush() -> None:
        if len(current) >= 2:
            segments.append(" ".join(current))
        current.clear()

    for p in line_points:
        if p.value is None:
            _flush()
            continue
        x = _polyline_x(
            p.ordinal,
            total_points=total_points,
            layout_width=layout_width,
            margin_left=margin_left,
            margin_right=margin_right,
        )
        y = _polyline_y(
            p.value,
            y_min=y_min,
            y_max=y_max,
            layout_height=layout_height,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
        )
        current.append(f"{x:.2f},{y:.2f}")
    _flush()
    return tuple(segments)


def _y_axis_bounds_for_metric(
    metric_name: str,
    line_points: tuple[RollingLinePoint, ...],
) -> tuple[float, float]:
    """Return (y_min, y_max) for the metric's SVG line."""
    if metric_name in _GRADE_METRICS:
        return (0.0, 4.0)
    if metric_name == "disqualifying_violation_rate_rolling_N":
        return (0.0, 1.0)
    # mistake_cost_R_rolling_N_per_trade (B) and _total (point):
    finite_values = [
        float(p.value) for p in line_points
        if p.value is not None and math.isfinite(p.value)
    ]
    if not finite_values:
        return (0.0, 1.0)
    raw_min = min(finite_values)
    raw_max = max(finite_values)
    if raw_min == raw_max:
        return (raw_min - 0.5, raw_max + 0.5)
    return (raw_min, raw_max)


def _build_rolling_display(
    metric_name: str,
    series,
    *,
    total_points: int,
    layout_width: int,
    layout_height: int,
    margin_left: int,
    margin_right: int,
    margin_top: int,
    margin_bottom: int,
) -> RollingSeriesDisplay:
    """Map one RollingMetricSeries to its display VM."""
    if series.suppressed is not None:
        return RollingSeriesDisplay(
            metric_name=metric_name,
            underlying_class=series.underlying_class,
            is_suppressed=True,
            suppressed_placeholder=series.suppressed.placeholder_text,
            point_value_text=None,
            ci_lower_text=None,
            ci_upper_text=None,
            drawability_text=None,
            window_not_full_warning_text=None,
            confidence_floor_warning_text=None,
            svg_polyline_segments=(),
            is_drawable=False,
        )

    point_text, lo_text, hi_text = _format_value_slot(series.rendered_value)
    drawability, window_text, floor_text = _badge_texts(
        series.badges, drawability_text=series.drawability_text,
    )
    y_min, y_max = _y_axis_bounds_for_metric(metric_name, series.line_points)
    segments = _format_polyline_segments(
        series.line_points,
        total_points=total_points,
        y_min=y_min,
        y_max=y_max,
        layout_width=layout_width,
        layout_height=layout_height,
        margin_left=margin_left,
        margin_right=margin_right,
        margin_top=margin_top,
        margin_bottom=margin_bottom,
    )
    # Drawability gate: ``drawability_text='rolling line drawable'`` means the
    # §5.4 line band has fired AND at least one >=2-point segment must survive
    # (else the template would emit an empty <polyline> set; F-3).
    is_drawable = (
        drawability == "rolling line drawable"
        and bool(segments)
    )
    return RollingSeriesDisplay(
        metric_name=metric_name,
        underlying_class=series.underlying_class,
        is_suppressed=False,
        suppressed_placeholder=None,
        point_value_text=point_text,
        ci_lower_text=lo_text,
        ci_upper_text=hi_text,
        drawability_text=drawability,
        window_not_full_warning_text=window_text,
        confidence_floor_warning_text=floor_text,
        svg_polyline_segments=segments,
        is_drawable=is_drawable,
    )


def _build_marker_display(
    marker: ProcessGradeTrendPoint,
    *,
    total_points: int,
    layout_width: int,
    layout_height: int,
    margin_left: int,
    margin_right: int,
    margin_top: int,
    margin_bottom: int,
) -> PerTradeMarkerDisplay:
    """Map ProcessGradeTrendPoint → SVG marker display."""
    x = _polyline_x(
        marker.ordinal,
        total_points=total_points,
        layout_width=layout_width,
        margin_left=margin_left,
        margin_right=margin_right,
    )
    if marker.process_grade_numeric is None:
        y: float | None = None
    else:
        y = _polyline_y(
            marker.process_grade_numeric,
            y_min=0.0,
            y_max=4.0,
            layout_height=layout_height,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
        )
    return PerTradeMarkerDisplay(
        ordinal=marker.ordinal,
        trade_id=marker.trade_id,
        ticker=marker.ticker,
        review_date=marker.review_date,
        process_grade_letter=marker.process_grade_letter,
        process_grade_numeric=marker.process_grade_numeric,
        svg_x=x,
        svg_y=y,
        disqualifying=marker.disqualifying,
    )


# ----------------------------------------------------------------------------
# Public factory
# ----------------------------------------------------------------------------

def build_process_grade_trend_vm(
    *,
    cfg: Config,
    conn: sqlite3.Connection | None = None,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> ProcessGradeTrendVM:
    """Build the process-grade-trend page VM.

    Eagerly populates ``unresolved_material_discrepancies_count`` per
    plan §A.18 + §I.5 mixin contract.
    """
    own_conn = conn is None
    if own_conn:
        conn = connect(cfg.paths.db_path)
    assert conn is not None
    try:
        unresolved = count_unresolved_material(conn)
        recent_multi_leg = count_recent_multi_leg_auto_corrections(conn)
        banner_resolve_link = (
            fetch_first_pending_ambiguity_resolve_link_path(conn)
        )
        result: ProcessGradeTrendResult = compute_process_grade_trend(
            conn, window_size=window_size,
        )
    finally:
        if own_conn:
            conn.close()

    total_points = len(result.per_trade_markers)
    markers = tuple(
        _build_marker_display(
            m,
            total_points=total_points,
            layout_width=SVG_WIDTH,
            layout_height=SVG_HEIGHT,
            margin_left=SVG_MARGIN_LEFT,
            margin_right=SVG_MARGIN_RIGHT,
            margin_top=SVG_MARGIN_TOP,
            margin_bottom=SVG_MARGIN_BOTTOM,
        )
        for m in result.per_trade_markers
    )
    rolling_displays = tuple(
        _build_rolling_display(
            metric_name,
            result.rolling_series[metric_name],
            total_points=total_points,
            layout_width=SVG_WIDTH,
            layout_height=SVG_HEIGHT,
            margin_left=SVG_MARGIN_LEFT,
            margin_right=SVG_MARGIN_RIGHT,
            margin_top=SVG_MARGIN_TOP,
            margin_bottom=SVG_MARGIN_BOTTOM,
        )
        for metric_name in PROCESS_GRADE_TREND_METRIC_CLASSES
    )

    return ProcessGradeTrendVM(
        session_date=action_session_for_run(datetime.now()).isoformat(),
        unresolved_material_discrepancies_count=unresolved,
        recent_multi_leg_auto_correction_count=recent_multi_leg,
        banner_resolve_link=banner_resolve_link,
        window_size=result.window_size,
        per_trade_markers=markers,
        rolling_series=rolling_displays,
    )


__all__ = [
    "GRADE_AXIS_LABELS",
    "PerTradeMarkerDisplay",
    "ProcessGradeTrendVM",
    "RollingSeriesDisplay",
    "build_process_grade_trend_vm",
]
