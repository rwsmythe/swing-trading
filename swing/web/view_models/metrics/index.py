"""View-model for the ``GET /metrics`` umbrella index page.

Renders a 9-card overview navigator linking to each Phase 10 metrics surface
(P14.N5). Each card carries a headline stat read read-only from the existing
per-surface output, and the 3 trend-bearing surfaces also carry an inline
``<polyline>`` sparkline. Every card stays the drill-down link to its
per-surface route.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import datetime

from swing.config import Config
from swing.evaluation.dates import action_session_for_run
from swing.metrics.capital import TREND_MIN_RUNS as _CAPITAL_TREND_MIN_RUNS
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.metrics.funnel import TREND_MIN_RUNS as _FUNNEL_TREND_MIN_RUNS
from swing.metrics.honesty import BootstrapCI, SuppressedMetric
from swing.metrics.process_grade_trend import compute_process_grade_trend
from swing.metrics.tier import APLUS_COHORT
from swing.web.view_models.metrics.capital_friction import build_capital_friction_vm
from swing.web.view_models.metrics.deviation_outcome import build_deviation_outcome_vm
from swing.web.view_models.metrics.hypothesis_progress_card import (
    build_hypothesis_progress_card_vm,
)
from swing.web.view_models.metrics.identification_funnel import (
    build_identification_funnel_vm,
)
from swing.web.view_models.metrics.maturity_stage import build_maturity_stage_vm
from swing.web.view_models.metrics.shared import BaseLayoutVM
from swing.web.view_models.metrics.sparkline import build_sparkline_points
from swing.web.view_models.metrics.tier_comparison import build_tier_comparison_vm
from swing.web.view_models.metrics.trade_process_card import (
    ALL_COHORTS_KEY,
    build_trade_process_card_vm,
)
from swing.web.view_models.patterns.outcomes_card import build_pattern_outcomes_vm

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetricsIndexSurface:
    """One overview card. Static {path,label,description} from the registry;
    the rest are populated per-request from existing per-surface outputs."""

    path: str
    label: str
    description: str
    headline_stat_text: str | None = None       # display-ready, e.g. "42.0%"
    headline_caption: str | None = None          # unit caption, e.g. "utilization"
    headline_suppressed_text: str | None = None  # honest placeholder when unavailable
    sparkline_points: str | None = None          # inline-SVG points; None => no line
    sparkline_suppressed_text: str | None = None  # trend-bearing but below threshold
    sparkline_kind: str = "none"                 # "none" | "inline_svg"


@dataclass(frozen=True)
class _OverviewCard:
    """The 6 per-request overview fields an extractor returns."""

    headline_stat_text: str | None = None
    headline_caption: str | None = None
    headline_suppressed_text: str | None = None
    sparkline_points: str | None = None
    sparkline_suppressed_text: str | None = None
    sparkline_kind: str = "none"


# Reused metric strings (placeholder_text/suppressed_text/triggered_pct_text)
# may embed NON-ASCII - e.g. honesty.py builds "need: >=N" with a real
# U+2265 glyph. Coerce to ASCII at the overview boundary (#16/#32 cp1252).
# The map keys are written as \uXXXX escapes so THIS source file stays pure
# ASCII (the T-5.4 file-wide non-ASCII gate would otherwise flag the keys).
_ASCII_SUBSTITUTIONS = {
    chr(0x2265): ">=",     # U+2265 GREATER-THAN OR EQUAL TO
    chr(0x2264): "<=",     # U+2264 LESS-THAN OR EQUAL TO
    chr(0x2013): "-",      # U+2013 EN DASH
    chr(0x2014): "-",      # U+2014 EM DASH
    chr(0x2192): "->",     # U+2192 RIGHTWARDS ARROW
    chr(0x00B1): "+/-",    # U+00B1 PLUS-MINUS SIGN
    chr(0x0394): "delta",  # U+0394 GREEK CAPITAL LETTER DELTA
    chr(0x00A7): "sec ",   # U+00A7 SECTION SIGN
}


def _ascii(text: str | None) -> str | None:
    if text is None:
        return None
    for src, dst in _ASCII_SUBSTITUTIONS.items():
        text = text.replace(src, dst)
    # encode("ascii","replace") is the last-resort net; the substitution map
    # above MUST cover every glyph the reused metric strings actually use
    # (today only U+2265 in honesty.py). A "?" appearing in overview text is a
    # BUG (an unmapped glyph) - the no-"?" test guards it.
    return text.encode("ascii", "replace").decode("ascii")


def _format_metric_value(value: object) -> tuple[str | None, str | None]:
    """Map a metric value to (headline_text, suppressed_text), reusing the
    metric's OWN suppression placeholder (never fabricates a number - L2/L4).
    The suppressed text is ASCII-coerced (it may carry a non-ASCII glyph)."""
    if isinstance(value, SuppressedMetric):
        return (None, _ascii(value.placeholder_text))
    if isinstance(value, BootstrapCI):
        return (f"{value.point:.2f}", None)
    if value is None:
        return (None, "unavailable")
    return (f"{float(value):.2f}", None)


_PROCESS_GRADE_HEADLINE_METRIC = "process_grade_rolling_N"


# --------------------------------------------------------------------------
# Per-surface extractors (read-only; reuse the existing per-surface output).
# The 3 trend-bearing surfaces each gate their sparkline on their OWN
# threshold constant (capital=5, funnel=10, process-grade line-band) - L4.
# --------------------------------------------------------------------------
def _extract_capital_friction(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_capital_friction_vm(cfg=cfg, conn=conn)
    result = vm.result
    if result is None:
        return _OverviewCard(
            headline_suppressed_text="unavailable",
            sparkline_kind="inline_svg",
            sparkline_suppressed_text="trend unavailable",
        )
    util = result.current_capital_utilization_pct
    headline = None if util is None else f"{util:.1f}%"
    headline_supp = "utilization unavailable" if util is None else None
    runs = result.trend_runs
    points: str | None = None
    if len(runs) >= _CAPITAL_TREND_MIN_RUNS:
        points = build_sparkline_points(
            [p.current_capital_utilization_pct for p in runs]
        )
    if points is None:
        supp = (
            f"trend needs >={_CAPITAL_TREND_MIN_RUNS} runs (have {len(runs)})"
            if len(runs) < _CAPITAL_TREND_MIN_RUNS
            else "trend not drawable (insufficient defined points)"
        )
    else:
        supp = None
    return _OverviewCard(
        headline_stat_text=headline,
        headline_caption="utilization",
        headline_suppressed_text=headline_supp,
        sparkline_points=points,
        sparkline_suppressed_text=supp,
        sparkline_kind="inline_svg",
    )


def _extract_identification_funnel(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_identification_funnel_vm(cfg=cfg, conn=conn)
    result = vm.result
    if result is None:
        return _OverviewCard(
            headline_suppressed_text="unavailable",
            sparkline_kind="inline_svg",
            sparkline_suppressed_text="trend unavailable",
        )
    runs = result.trend_runs
    if runs:
        headline = str(runs[-1].aplus_identifications_per_run)
        headline_supp = None
    else:
        headline = None
        headline_supp = "no pipeline runs yet"
    points: str | None = None
    if len(runs) >= _FUNNEL_TREND_MIN_RUNS:
        points = build_sparkline_points(
            [float(p.aplus_identifications_per_run) for p in runs]
        )
    if points is None:
        supp = (
            f"trend needs >={_FUNNEL_TREND_MIN_RUNS} runs (have {len(runs)})"
            if len(runs) < _FUNNEL_TREND_MIN_RUNS
            else "trend not drawable (insufficient defined points)"
        )
    else:
        supp = None
    return _OverviewCard(
        headline_stat_text=headline,
        headline_caption="A+ ident. (latest run)",
        headline_suppressed_text=headline_supp,
        sparkline_points=points,
        sparkline_suppressed_text=supp,
        sparkline_kind="inline_svg",
    )


def _extract_process_grade_trend(cfg: Config, conn, session_date: str) -> _OverviewCard:
    result = compute_process_grade_trend(conn)
    series = result.rolling_series[_PROCESS_GRADE_HEADLINE_METRIC]
    if series.suppressed is not None:
        headline = None
        headline_supp = series.suppressed.placeholder_text
    else:
        rv = series.rendered_value  # BootstrapCI for the class-"B" headline metric
        point = getattr(rv, "point", rv)
        headline = None if point is None else f"{float(point):.2f}"
        headline_supp = None if headline is not None else "unavailable"
    points: str | None = None
    drawable = (
        series.suppressed is None
        and series.drawability_text == "rolling line drawable"
    )
    if drawable:
        points = build_sparkline_points([p.value for p in series.line_points])
    supp = None if points is not None else "rolling grade line not yet drawable"
    return _OverviewCard(
        headline_stat_text=headline,
        headline_caption="rolling grade",
        headline_suppressed_text=_ascii(headline_supp),
        sparkline_points=points,
        sparkline_suppressed_text=supp,
        sparkline_kind="inline_svg",
    )


# OQ-4 fixed selectors (operator-confirmable at executing-plans; plan sec C.4).
DEVIATION_HEADLINE_COHORT: str = "Near-A+ defensible: extension test"
_DEVIATION_HEADLINE_SHORT: str = "Near-A+"
PATTERN_HEADLINE_CLASS: str = "vcp"


def _extract_trade_process(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_trade_process_card_vm(cfg=cfg, conn=conn)
    tab = next((t for t in vm.cohort_tabs if t.cohort_key == ALL_COHORTS_KEY), None)
    if tab is None:
        return _OverviewCard(headline_suppressed_text="unavailable")
    stat, supp = _format_metric_value(tab.metrics.expectancy_R.value)
    return _OverviewCard(
        headline_stat_text=stat,
        headline_caption="expectancy R (all)",
        headline_suppressed_text=supp,
    )


def _extract_hypothesis_progress(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_hypothesis_progress_card_vm(cfg=cfg, conn=conn)
    n = len(vm.cohorts)
    if n == 0:
        return _OverviewCard(headline_suppressed_text="no registered cohorts")
    return _OverviewCard(headline_stat_text=str(n), headline_caption="registered cohorts")


def _extract_tier_comparison(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_tier_comparison_vm(cfg=cfg, conn=conn)
    if vm.result is None:
        return _OverviewCard(headline_suppressed_text="unavailable")
    cohort = next((c for c in vm.result.cohorts if c.cohort_name == APLUS_COHORT), None)
    if cohort is None:
        return _OverviewCard(headline_suppressed_text="A+ cohort unavailable")
    stat, supp = _format_metric_value(cohort.expectancy)
    return _OverviewCard(
        headline_stat_text=stat,
        headline_caption="A+ expectancy R",
        headline_suppressed_text=supp,
    )


def _extract_maturity_stage(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_maturity_stage_vm(cfg=cfg, conn=conn)
    if vm.result is None:
        return _OverviewCard(headline_suppressed_text="unavailable")
    return _OverviewCard(
        headline_stat_text=str(len(vm.result.rows)),
        headline_caption="open positions",
    )


def _extract_deviation_outcome(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_deviation_outcome_vm(cfg=cfg, conn=conn)
    caption = f"delta vs A+ ({_DEVIATION_HEADLINE_SHORT})"
    if vm.result is None:
        return _OverviewCard(headline_suppressed_text="unavailable", headline_caption=caption)
    row = next(
        (r for r in vm.result.rows if r.cohort_name == DEVIATION_HEADLINE_COHORT), None
    )
    if row is None:
        return _OverviewCard(
            headline_suppressed_text="cohort unavailable", headline_caption=caption
        )
    if row.row_suppressed or row.expectancy_relative_to_aplus_pct is None:
        return _OverviewCard(headline_suppressed_text="n too low", headline_caption=caption)
    return _OverviewCard(
        headline_stat_text=f"{row.expectancy_relative_to_aplus_pct:+.1f}%",
        headline_caption=caption,
    )


def _extract_pattern_outcomes(cfg: Config, conn, session_date: str) -> _OverviewCard:
    vm = build_pattern_outcomes_vm(conn, session_date=session_date)
    caption = f"trigger rate ({PATTERN_HEADLINE_CLASS})"
    row = next(
        (r for r in vm.pattern_outcome_rows if r.pattern_class == PATTERN_HEADLINE_CLASS),
        None,
    )
    if row is None:
        return _OverviewCard(
            headline_suppressed_text="pattern unavailable", headline_caption=caption
        )
    if row.triggered_ci is not None:
        return _OverviewCard(headline_stat_text=row.triggered_pct_text, headline_caption=caption)
    return _OverviewCard(headline_suppressed_text=row.suppressed_text, headline_caption=caption)


# 9 surfaces in the umbrella `/metrics` index navigator (registry order).
# Card ordering mirrors the Phase 10 spec surface numbering.
_SURFACES: tuple[MetricsIndexSurface, ...] = (
    MetricsIndexSurface(
        path="/metrics/trade-process",
        label="Trade-process card",
        description="Per-cohort + overall metrics across the closed-trade scope.",
    ),
    MetricsIndexSurface(
        path="/metrics/hypothesis-progress",
        label="Hypothesis-progress card",
        description="Per-cohort governance: progress bars, tripwires, transition history.",
    ),
    MetricsIndexSurface(
        path="/metrics/tier-comparison",
        label="Tier-comparison",
        description="A+ vs Sub-A+ vs Capital-blocked side-by-side with CIs.",
    ),
    MetricsIndexSurface(
        path="/metrics/capital-friction",
        label="Capital-friction",
        description="Risk_feasibility, utilization, heat, cycle-time gauges.",
    ),
    MetricsIndexSurface(
        path="/metrics/maturity-stage",
        label="Maturity-stage",
        description="Per-open-position stage + trail-MA eligibility + MFE/MAE.",
    ),
    MetricsIndexSurface(
        path="/metrics/identification-funnel",
        label="Identification-funnel",
        description="A+ + watch identifications vs trades per pipeline run.",
    ),
    MetricsIndexSurface(
        path="/metrics/deviation-outcome",
        label="Deviation-outcome",
        description="Per-cohort doctrine-deviation class vs expectancy relative to A+.",
    ),
    MetricsIndexSurface(
        path="/metrics/process-grade-trend",
        label="Process-grade-trend",
        description="Rolling-N grade line + per-stage + violation rate + mistake-cost.",
    ),
    # Phase 13 T2.SB6b T-A.6.5 - 9th metric tile per OQ-10 LOCK. ADDITIVE
    # on top of the 8 Phase 10 tiles + 1 umbrella `/metrics` navigator.
    MetricsIndexSurface(
        path="/metrics/pattern-outcomes",
        label="Pattern-outcomes",
        description=(
            "Per-pattern-class triggered + reached 1R + hit stop with "
            "Wilson CI; suppressed at n < 5 (Phase 10 honesty)."
        ),
    ),
)


@dataclass(frozen=True)
class MetricsIndexVM(BaseLayoutVM):
    """VM for ``GET /metrics``. Extends BaseLayoutVM (leaf overview fields
    live on MetricsIndexSurface, not here - L7)."""

    surfaces: tuple[MetricsIndexSurface, ...] = field(default_factory=tuple)


_EXTRACTORS = {
    "/metrics/trade-process": _extract_trade_process,
    "/metrics/hypothesis-progress": _extract_hypothesis_progress,
    "/metrics/tier-comparison": _extract_tier_comparison,
    "/metrics/capital-friction": _extract_capital_friction,
    "/metrics/maturity-stage": _extract_maturity_stage,
    "/metrics/identification-funnel": _extract_identification_funnel,
    "/metrics/deviation-outcome": _extract_deviation_outcome,
    "/metrics/process-grade-trend": _extract_process_grade_trend,
    "/metrics/pattern-outcomes": _extract_pattern_outcomes,
}

_OVERVIEW_FIELD_NAMES = (
    "headline_stat_text", "headline_caption", "headline_suppressed_text",
    "sparkline_points", "sparkline_suppressed_text", "sparkline_kind",
)

_TEXT_FIELDS = (
    "headline_stat_text", "headline_caption",
    "headline_suppressed_text", "sparkline_suppressed_text",
)


def _enrich_surface(
    base: MetricsIndexSurface, cfg: Config, conn: sqlite3.Connection, session_date: str,
) -> MetricsIndexSurface:
    extractor = _EXTRACTORS.get(base.path)
    if extractor is None:  # defensive - every registry path has an extractor
        return base
    try:
        card = extractor(cfg, conn, session_date)
    except Exception:  # noqa: BLE001 - per-card isolation: one fail != whole-page 500
        _LOG.warning(
            "metrics overview extractor failed for %s", base.path, exc_info=True
        )
        card = _OverviewCard(headline_suppressed_text="unavailable")
    values = {name: getattr(card, name) for name in _OVERVIEW_FIELD_NAMES}
    # CENTRAL ASCII chokepoint: every reused text field is coerced to ASCII
    # here, so no extractor can leak honesty.py's U+2265 etc. Also sanitise the
    # static label/description (defense-in-depth even though the registry is
    # ASCII at source) so the rendered body.isascii().
    for name in _TEXT_FIELDS:
        values[name] = _ascii(values[name])
    values["label"] = _ascii(base.label)
    values["description"] = _ascii(base.description)
    return replace(base, **values)


def build_metrics_index_vm(cfg: Config, conn: sqlite3.Connection) -> MetricsIndexVM:
    """Build the enhanced overview VM. ``session_date`` stays forward-looking
    ``action_session_for_run(now)`` (the navigator topbar date, as before).
    Each surface card is enriched read-only from the existing per-surface
    output; a single surface's failure degrades only that card."""
    session_date = action_session_for_run(datetime.now()).isoformat()
    enriched = tuple(
        _enrich_surface(base, cfg, conn, session_date) for base in _SURFACES
    )
    from swing.web.view_models.schwab_checker_badge import build_schwab_checker_badge
    return MetricsIndexVM(
        session_date=session_date,
        unresolved_material_discrepancies_count=count_unresolved_material(conn),
        recent_multi_leg_auto_correction_count=(
            count_recent_multi_leg_auto_corrections(conn)
        ),
        banner_resolve_link=fetch_first_pending_ambiguity_resolve_link_path(conn),
        surfaces=enriched,
        schwab_checker_badge=build_schwab_checker_badge(cfg),
    )
