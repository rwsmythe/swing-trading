"""§3.8 process-grade-trend computations — Phase 10 Sub-bundle E Task T-E.1.

Per spec §3.8 + §4.8 + §5.4 + plan §H + §A.21:

- Iterates closed-and-reviewed trades ordered by ``reviewed_at, id``
  (deterministic tiebreaker per forward-binding lesson #26).
- Per-trade markers always produced (one per closed-reviewed trade).
- Rolling lines for 7 metrics, each rendered via
  :func:`swing.metrics.honesty.render_class_d` with the ``underlying_class``
  argument from the §A.21 BINDING per-metric matrix.
- Numeric grade encoding A=4..F=0 (spec §3.8 line 217).
- Window size ``N=10`` HARDCODED per spec §8.5 + plan §A.4 (caller may
  override for testability).

Lesson #18 (cadence-grain rejection): aggregation is per-trade-grain via
``Trade.process_grade`` etc. + per-trade ``mistake_cost_R`` derived from the
shipped Phase 6 helper :func:`swing.trades.review.compute_mistake_cost_R`.
NOT via cadence-grain ``review_log.total_*`` aggregates.

Lesson #19 (unit-semantic precision): grades render as numeric encoding so
the chart axis can label A=4..F=0 inline (operator readability).

Lesson #25 (bounded-range distinguishing): grade rollings are
mathematically bounded [0, 4]; ``disqualifying_violation_rate_rolling_N`` is
math-bounded [0, 1] by k/n construction. No clamping logic needed.

Lesson #26 (SQL ORDER BY deterministic tiebreaker): trades query orders by
``reviewed_at, id`` so trades reviewed in the same ms-ISO timestamp emit in
deterministic order.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from typing import Literal

from swing.data.models import Fill, Trade
from swing.data.repos.fills import list_fills_for_trade
from swing.data.repos.trades import _row_to_trade  # noqa: PLC2701 — local repo
from swing.metrics.honesty import (
    BootstrapCI,
    HonestyBadges,
    SuppressedMetric,
    WilsonCI,
    render_class_d,
)
from swing.metrics.policy import read_live_policy
from swing.trades.derived_metrics import initial_risk_per_share
from swing.trades.review import compute_mistake_cost_R

# Per spec §8.5 + plan §A.4: ``N=10`` is HARDCODED for V1; operator-
# configurable is deferred to V2 (§8.5 open question).
DEFAULT_WINDOW_SIZE: int = 10

# Spec §3.8 line 217 — numeric grade encoding.
GRADE_TO_NUMERIC: dict[str, int] = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


# Plan §A.21 BINDING per-metric Class assignment matrix (Codex R2 M#1).
# - "B" → BootstrapCI on rolling-window samples (per-trade values).
# - "A" → WilsonCI on rolling-window k/n (events_in_window = count of
#   disqualifying=1 trades in the window).
# - "point" → bare float (sum-only metric; spec-conformance deviation
#   banked at writing-plans as V2.1 §VII.F amendment candidate per plan
#   §A.21).
PROCESS_GRADE_TREND_METRIC_CLASSES: dict[str, Literal["A", "B", "point"]] = {
    "process_grade_rolling_N":               "B",
    "entry_grade_rolling_N":                 "B",
    "management_grade_rolling_N":            "B",
    "exit_grade_rolling_N":                  "B",
    "mistake_cost_R_rolling_N_per_trade":    "B",
    "disqualifying_violation_rate_rolling_N": "A",
    "mistake_cost_R_rolling_N_total":        "point",
}


@dataclass(frozen=True)
class ProcessGradeTrendPoint:
    """One per-trade marker on the §4.8 chart.

    Per spec §4.8 + §5.4: per-trade markers always render regardless of
    rolling-line state (line is suppressed at effective_n<5; markers are
    not).
    """

    ordinal: int                # 0-indexed position in review-date order
    trade_id: int
    ticker: str
    review_date: str            # YYYY-MM-DD (or YYYY-MM-DDT... full ts substr 0:10)
    process_grade_letter: str | None
    # NULL when grade letter is None (legacy/in-progress review).
    process_grade_numeric: float | None
    entry_grade_numeric: float | None
    management_grade_numeric: float | None
    exit_grade_numeric: float | None
    disqualifying: int          # 0 or 1
    mistake_cost_R: float       # noqa: N815 — Phase 6 v1.2 §8.8 convention

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError(
                f"ProcessGradeTrendPoint.ordinal must be >= 0; got {self.ordinal!r}"
            )
        if self.trade_id <= 0:
            raise ValueError(
                f"ProcessGradeTrendPoint.trade_id must be > 0; got {self.trade_id!r}"
            )
        if self.disqualifying not in (0, 1):
            raise ValueError(
                f"ProcessGradeTrendPoint.disqualifying must be 0 or 1; got "
                f"{self.disqualifying!r}"
            )
        for fname, fval in (
            ("process_grade_numeric", self.process_grade_numeric),
            ("entry_grade_numeric", self.entry_grade_numeric),
            ("management_grade_numeric", self.management_grade_numeric),
            ("exit_grade_numeric", self.exit_grade_numeric),
        ):
            if fval is not None and not math.isfinite(fval):
                raise ValueError(
                    f"ProcessGradeTrendPoint.{fname} must be finite or None; "
                    f"got {fval!r}"
                )
        if not math.isfinite(self.mistake_cost_R):
            raise ValueError(
                "ProcessGradeTrendPoint.mistake_cost_R must be finite; got "
                f"{self.mistake_cost_R!r}"
            )


@dataclass(frozen=True)
class RollingLinePoint:
    """One (x, y) point on a rolling-mean line."""

    ordinal: int
    value: float | None  # None when rolling-mean helper suppresses (n<3)

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError(
                f"RollingLinePoint.ordinal must be >= 0; got {self.ordinal!r}"
            )
        if self.value is not None and not math.isfinite(self.value):
            raise ValueError(
                f"RollingLinePoint.value must be finite or None; got {self.value!r}"
            )


@dataclass(frozen=True)
class RollingMetricSeries:
    """Per-metric rolling-window series + render disposition.

    ``rendered_value``/``badges``/``drawability_text`` capture the
    most-recent window's render result via :func:`render_class_d`:

    - SUPPRESSED (effective_n<5) → ``suppressed`` populated + the other
      three are None.
    - DRAWABLE (effective_n>=5) → 3-tuple components populated +
      ``suppressed`` is None.

    ``line_points`` is the rolling-mean trajectory across all ordinals
    (one (ordinal, value-or-None) per closed-reviewed trade). Spec §4.8:
    the line is rendered only when the most-recent window is drawable
    (per ``drawability_text == "rolling line drawable"``); per-trade
    markers always render.
    """

    metric_name: str
    underlying_class: Literal["A", "B", "point"]
    line_points: tuple[RollingLinePoint, ...]
    # Most-recent-window render result fields:
    rendered_value: WilsonCI | BootstrapCI | float | None
    badges: HonestyBadges | None
    drawability_text: str | None
    suppressed: SuppressedMetric | None

    def __post_init__(self) -> None:
        if self.metric_name not in PROCESS_GRADE_TREND_METRIC_CLASSES:
            raise ValueError(
                "RollingMetricSeries.metric_name must be one of "
                f"{sorted(PROCESS_GRADE_TREND_METRIC_CLASSES)}; got "
                f"{self.metric_name!r}"
            )
        if self.underlying_class != PROCESS_GRADE_TREND_METRIC_CLASSES[self.metric_name]:
            raise ValueError(
                "RollingMetricSeries.underlying_class must match the §A.21 "
                f"matrix for {self.metric_name!r}: expected "
                f"{PROCESS_GRADE_TREND_METRIC_CLASSES[self.metric_name]!r}, "
                f"got {self.underlying_class!r}"
            )
        # Exactly one of {suppressed, drawable-trio} must be populated.
        is_suppressed = self.suppressed is not None
        has_trio = (
            self.badges is not None
            and self.drawability_text is not None
        )
        # Note: rendered_value may be float OR None for "point"/"C" so we
        # check the badges + drawability_text presence as the trio gate.
        if is_suppressed and has_trio:
            raise ValueError(
                "RollingMetricSeries cannot be both suppressed and drawable; got "
                f"suppressed={self.suppressed!r}, badges={self.badges!r}"
            )
        if not is_suppressed and not has_trio:
            raise ValueError(
                "RollingMetricSeries must be either suppressed or drawable "
                "(badges + drawability_text required); got neither"
            )


@dataclass(frozen=True)
class ProcessGradeTrendResult:
    """Top-level §4.8 surface data — per-trade markers + per-metric rolling series."""

    window_size: int
    per_trade_markers: tuple[ProcessGradeTrendPoint, ...]
    rolling_series: dict[str, RollingMetricSeries] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.window_size <= 0:
            raise ValueError(
                f"ProcessGradeTrendResult.window_size must be > 0; got {self.window_size!r}"
            )
        expected = set(PROCESS_GRADE_TREND_METRIC_CLASSES)
        got = set(self.rolling_series)
        if got != expected:
            missing = expected - got
            extra = got - expected
            raise ValueError(
                "ProcessGradeTrendResult.rolling_series keys must match the §A.21 "
                f"matrix; missing={sorted(missing)!r}, extra={sorted(extra)!r}"
            )


# ----------------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------------

# Match swing.data.repos.trades._TRADE_SELECT_COLS — we read via the same
# repo helper but pre-compute the SQL inline so the ORDER BY tiebreaker is
# explicit.
def _list_closed_reviewed_trades_ordered(
    conn: sqlite3.Connection,
) -> list[Trade]:
    """Return closed-and-reviewed trades ordered by ``reviewed_at, id``.

    Spec §3.8 + plan §H T-E.1: per-trade-grain aggregation (lesson #18).
    Lesson #26: deterministic tiebreaker on ``id`` so same-ms ``reviewed_at``
    rows emit in stable order. Trades with ``reviewed_at IS NULL`` are
    excluded — only fully-reviewed trades carry process_grade letters.
    """
    from swing.data.repos.trades import _TRADE_SELECT_COLS  # noqa: PLC2701

    rows = conn.execute(
        f"SELECT {_TRADE_SELECT_COLS} FROM trades "  # noqa: S608
        "WHERE state = 'reviewed' AND reviewed_at IS NOT NULL "
        "ORDER BY reviewed_at, id"
    ).fetchall()
    return [_row_to_trade(r) for r in rows]


def _per_trade_actual_realized_R(  # noqa: N802
    trade: Trade, fills: tuple[Fill, ...],
) -> float:
    """Per-trade share-weighted realized R (v1.2 §8.4 convention).

    Mirrors ``swing.trades.review.compute_actual_realized_R_effective``
    semantics without the ExitLike adapter layer: sums ``r_multiple ×
    quantity / initial_shares`` over exit-action fills.

    Returns 0.0 when:
      - No exit fills (open trade — caller filters by state='reviewed',
        so this is defense-in-depth).
      - ``initial_shares`` is 0 (degenerate / legacy row).
      - ``risk_per_share`` is 0 (entry==stop or inverted — undefined R).
    """
    if trade.initial_shares <= 0:
        return 0.0
    rps = initial_risk_per_share(
        entry_price=trade.entry_price, initial_stop=trade.initial_stop,
    )
    if rps <= 0:
        return 0.0
    total = 0.0
    for f in fills:
        if f.action == "entry":
            continue
        # r_multiple per fill = (exit_price - entry_price) / risk_per_share
        # share-weighted via quantity / initial_shares.
        per_fill_r = (f.price - trade.entry_price) / rps
        total += per_fill_r * (f.quantity / trade.initial_shares)
    return total


def _build_per_trade_point(
    trade: Trade, ordinal: int, mistake_cost_R: float,  # noqa: N803
) -> ProcessGradeTrendPoint:
    """Construct a per-trade marker from a Trade row + derived cost.

    Grade fields may be None on legacy rows / in-progress reviews; the
    template renders such markers without a Y-coordinate via the
    ``process_grade_numeric is None`` guard.
    """
    review_date = (trade.reviewed_at or "")[:10]

    def _gnum(letter: str | None) -> float | None:
        if letter is None:
            return None
        return float(GRADE_TO_NUMERIC[letter])

    return ProcessGradeTrendPoint(
        ordinal=ordinal,
        trade_id=trade.id or 0,
        ticker=trade.ticker,
        review_date=review_date,
        process_grade_letter=trade.process_grade,
        process_grade_numeric=_gnum(trade.process_grade),
        entry_grade_numeric=_gnum(trade.entry_grade),
        management_grade_numeric=_gnum(trade.management_grade),
        exit_grade_numeric=_gnum(trade.exit_grade),
        disqualifying=int(bool(trade.disqualifying_process_violation)),
        mistake_cost_R=mistake_cost_R,
    )


def _rolling_window_at_position(
    samples: list[float | None], i: int, window_size: int,
) -> list[float]:
    """Most-recent ``window_size`` finite samples up to and including ``i``."""
    start = max(0, i - window_size + 1)
    return [float(x) for x in samples[start : i + 1] if x is not None]


def _build_rolling_line_points(
    samples: list[float | None], window_size: int,
) -> tuple[RollingLinePoint, ...]:
    """Per-position rolling mean (None when fewer than 3 finite samples).

    Used for Class B + "point" metric line trajectories. Class A rate
    metrics use :func:`_build_rolling_rate_line_points` instead so the
    line value is k/n per window (NOT the mean of the 1.0 sentinel).
    """
    out: list[RollingLinePoint] = []
    for i in range(len(samples)):
        window = _rolling_window_at_position(samples, i, window_size)
        # Operational floor (matching rolling.py's _MIN_N_FOR_MEAN): 3
        # samples needed for a rendered mean point.
        if len(window) < 3:
            out.append(RollingLinePoint(ordinal=i, value=None))
        else:
            out.append(
                RollingLinePoint(ordinal=i, value=sum(window) / len(window))
            )
    return tuple(out)


def _build_rolling_rate_line_points(
    events: list[int], window_size: int,
) -> tuple[RollingLinePoint, ...]:
    """Per-position rolling RATE (k/n) for Class A metrics.

    Each per-position value is ``count(events==1) / window_size_actual``
    over the most-recent ``window_size`` positions up to and including
    ``i``. Operational floor (matching the mean-line path): rate is
    suppressed (None) until the window has at least 3 positions.
    """
    out: list[RollingLinePoint] = []
    for i in range(len(events)):
        start = max(0, i - window_size + 1)
        window = events[start : i + 1]
        if len(window) < 3:
            out.append(RollingLinePoint(ordinal=i, value=None))
        else:
            out.append(
                RollingLinePoint(ordinal=i, value=sum(window) / len(window))
            )
    return tuple(out)


def _build_rolling_sum_line_points(
    samples: list[float | None], window_size: int,
) -> tuple[RollingLinePoint, ...]:
    """Per-position rolling SUM for "point" (sum-only) metrics.

    Codex R1 Major #1 fix: ``mistake_cost_R_rolling_N_total`` is a
    SUM-class metric per §A.21 — the rendered value-slot via
    ``render_class_d`` returns the window SUM (not mean), but the LINE
    points were previously built via :func:`_build_rolling_line_points`
    (mean). Plotting the mean line while reporting the sum value-slot
    is misleading. Sum-class metrics get a dedicated rolling-sum line.

    Per-position value is ``sum(finite_window_samples)`` over the most-
    recent ``window_size`` positions up to and including ``i``.
    Operational floor (matching the mean-line + rate-line paths): line is
    suppressed (None) until the window has at least 3 non-None samples.
    """
    out: list[RollingLinePoint] = []
    for i in range(len(samples)):
        window = _rolling_window_at_position(samples, i, window_size)
        if len(window) < 3:
            out.append(RollingLinePoint(ordinal=i, value=None))
        else:
            out.append(RollingLinePoint(ordinal=i, value=float(sum(window))))
    return tuple(out)


def _render_metric_series(
    *,
    metric_name: str,
    underlying_class: Literal["A", "B", "point"],
    samples_per_position: list[float | None],
    window_size: int,
    policy,  # RiskPolicy
    events_per_position: list[int] | None = None,
) -> RollingMetricSeries:
    """Render one metric series end-to-end.

    For Class B / "point": the rolling line is mean(window-samples);
    samples_per_position carries the per-trade scalars (None for legacy
    rows without grades).

    For Class A: ``samples_per_position`` is the per-trade denominator
    contribution (typically all 1.0 sentinels — one position per closed-
    reviewed trade) and ``events_per_position`` is the per-trade event
    flag (1=disqualifying, 0=qualifying). The rolling LINE is then k/n
    per window (NOT the mean of the 1.0 sentinel — Codex pre-emption for
    rate-metric line semantics).

    Workflow:
      1. Build per-position rolling line points (mean for Class B/"point",
         rate for Class A).
      2. Compose the most-recent window's samples + (for class 'A') the
         events_in_window count.
      3. Call ``render_class_d`` with the §A.21 ``underlying_class``.
      4. Decompose into RollingMetricSeries (suppressed-or-drawable).
    """
    if underlying_class == "A":
        if events_per_position is None:
            raise ValueError(
                "_render_metric_series underlying_class='A' requires "
                "events_per_position; got None"
            )
        line_points = _build_rolling_rate_line_points(
            events_per_position, window_size,
        )
    elif underlying_class == "point":
        # Codex R1 Major #1 fix: sum-class metrics (e.g.,
        # mistake_cost_R_rolling_N_total) plot rolling SUM, NOT rolling
        # mean, so the line matches the rendered value slot.
        line_points = _build_rolling_sum_line_points(
            samples_per_position, window_size,
        )
    else:
        # underlying_class in {"B", "C"} → rolling mean line.
        line_points = _build_rolling_line_points(
            samples_per_position, window_size,
        )

    # Most-recent window: drop None entries (legacy rows without grades).
    last_idx = len(samples_per_position) - 1
    if last_idx < 0:
        window_samples: list[float] = []
        events_in_window: int = 0
    else:
        start = max(0, last_idx - window_size + 1)
        slice_pairs = list(
            zip(
                samples_per_position[start : last_idx + 1],
                events_per_position[start : last_idx + 1]
                if events_per_position is not None
                else [None] * (last_idx + 1 - start),
                strict=False,
            )
        )
        window_samples = [float(x) for x, _ in slice_pairs if x is not None]
        if events_per_position is not None:
            events_in_window = sum(
                int(e or 0) for x, e in slice_pairs if x is not None
            )
        else:
            events_in_window = 0

    kwargs = {
        "samples_in_window": window_samples,
        "window_n": window_size,
        "policy": policy,
        "metric_name": metric_name,
        "underlying_class": underlying_class,
    }
    if underlying_class == "A":
        kwargs["events_in_window"] = events_in_window

    result = render_class_d(**kwargs)

    if isinstance(result, SuppressedMetric):
        return RollingMetricSeries(
            metric_name=metric_name,
            underlying_class=underlying_class,
            line_points=line_points,
            rendered_value=None,
            badges=None,
            drawability_text=None,
            suppressed=result,
        )
    value, badges, drawability_text = result
    return RollingMetricSeries(
        metric_name=metric_name,
        underlying_class=underlying_class,
        line_points=line_points,
        rendered_value=value,
        badges=badges,
        drawability_text=drawability_text,
        suppressed=None,
    )


# ----------------------------------------------------------------------------
# Public surface
# ----------------------------------------------------------------------------

def compute_process_grade_trend(
    conn: sqlite3.Connection,
    *,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> ProcessGradeTrendResult:
    """Compute the §4.8 process-grade-trend surface data.

    Per plan §H T-E.1 + spec §3.8 + §4.8 + §5.4.

    Args:
      conn: open SQLite connection (read-only; no transaction).
      window_size: rolling-window size N. Production callsite passes 10
        per spec §8.5 LOCK; tests parametrize for the §5.4 four-band
        coverage.

    Returns:
      ProcessGradeTrendResult with per-trade markers + 7 rolling series
      keyed on ``PROCESS_GRADE_TREND_METRIC_CLASSES``.

    Lesson #18 — read-side aggregation is PER-TRADE via Phase 6 helpers,
    NOT via cadence-grain ``review_log.total_*``. Caller MUST NOT short-
    circuit through review_log.
    """
    if window_size <= 0:
        raise ValueError(
            f"compute_process_grade_trend window_size must be > 0; got {window_size!r}"
        )

    policy = read_live_policy(conn)
    trades = _list_closed_reviewed_trades_ordered(conn)

    # Build per-trade markers + per-position sample arrays.
    markers: list[ProcessGradeTrendPoint] = []
    process_samples: list[float | None] = []
    entry_samples: list[float | None] = []
    management_samples: list[float | None] = []
    exit_samples: list[float | None] = []
    cost_samples: list[float | None] = []
    disqualifying_flags: list[int] = []

    for i, trade in enumerate(trades):
        assert trade.id is not None  # state='reviewed' implies persisted row
        fills = tuple(list_fills_for_trade(conn, trade.id))
        actual_R = _per_trade_actual_realized_R(trade, fills)  # noqa: N806
        cost = compute_mistake_cost_R(
            realized_R_if_plan_followed=trade.realized_R_if_plan_followed,
            actual_realized_R_effective=actual_R,
        )
        marker = _build_per_trade_point(trade, ordinal=i, mistake_cost_R=cost)
        markers.append(marker)

        process_samples.append(marker.process_grade_numeric)
        entry_samples.append(marker.entry_grade_numeric)
        management_samples.append(marker.management_grade_numeric)
        exit_samples.append(marker.exit_grade_numeric)
        cost_samples.append(cost)
        disqualifying_flags.append(marker.disqualifying)

    # Render 7 rolling series per §A.21 matrix.
    rolling: dict[str, RollingMetricSeries] = {}
    rolling["process_grade_rolling_N"] = _render_metric_series(
        metric_name="process_grade_rolling_N",
        underlying_class="B",
        samples_per_position=process_samples,
        window_size=window_size,
        policy=policy,
    )
    rolling["entry_grade_rolling_N"] = _render_metric_series(
        metric_name="entry_grade_rolling_N",
        underlying_class="B",
        samples_per_position=entry_samples,
        window_size=window_size,
        policy=policy,
    )
    rolling["management_grade_rolling_N"] = _render_metric_series(
        metric_name="management_grade_rolling_N",
        underlying_class="B",
        samples_per_position=management_samples,
        window_size=window_size,
        policy=policy,
    )
    rolling["exit_grade_rolling_N"] = _render_metric_series(
        metric_name="exit_grade_rolling_N",
        underlying_class="B",
        samples_per_position=exit_samples,
        window_size=window_size,
        policy=policy,
    )
    rolling["mistake_cost_R_rolling_N_per_trade"] = _render_metric_series(
        metric_name="mistake_cost_R_rolling_N_per_trade",
        underlying_class="B",
        samples_per_position=cost_samples,
        window_size=window_size,
        policy=policy,
    )
    rolling["disqualifying_violation_rate_rolling_N"] = _render_metric_series(
        metric_name="disqualifying_violation_rate_rolling_N",
        underlying_class="A",
        # For Class A we still need per-position samples to build the
        # rolling LINE (k/n per window); use 1.0 sentinel so the sample
        # count is the trade count (denominator) and pass
        # disqualifying_flags as events.
        samples_per_position=[1.0 for _ in disqualifying_flags],
        window_size=window_size,
        policy=policy,
        events_per_position=disqualifying_flags,
    )
    rolling["mistake_cost_R_rolling_N_total"] = _render_metric_series(
        metric_name="mistake_cost_R_rolling_N_total",
        underlying_class="point",
        samples_per_position=cost_samples,
        window_size=window_size,
        policy=policy,
    )

    return ProcessGradeTrendResult(
        window_size=window_size,
        per_trade_markers=tuple(markers),
        rolling_series=rolling,
    )


__all__ = [
    "DEFAULT_WINDOW_SIZE",
    "GRADE_TO_NUMERIC",
    "PROCESS_GRADE_TREND_METRIC_CLASSES",
    "ProcessGradeTrendPoint",
    "ProcessGradeTrendResult",
    "RollingLinePoint",
    "RollingMetricSeries",
    "compute_process_grade_trend",
]
