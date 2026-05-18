"""View-model for the ``GET /metrics`` umbrella index page (plan §D Task A.8).

Renders an 8-tile navigator card linking to each Phase 10 metrics surface
per plan §A.3 + spec §4.1-§4.8. The per-surface routes land in
Sub-bundles B/C/D/E; at Sub-bundle A landing the links resolve to 404
until those bundles ship — operator's S3 gate confirms the index renders
+ links are present.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from swing.evaluation.dates import action_session_for_run
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@dataclass(frozen=True)
class MetricsIndexSurface:
    """Single tile in the 8-tile navigator."""

    path: str
    label: str
    description: str


# Per plan §A.3: 8 surfaces + the umbrella `/metrics` index navigator.
# Tile ordering mirrors spec §4.1-§4.8 numbering.
_SURFACES: tuple[MetricsIndexSurface, ...] = (
    MetricsIndexSurface(
        path="/metrics/trade-process",
        label="Trade-process card",
        description="Per-cohort + overall metrics across §3.1 closed-trade scope.",
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
)


@dataclass(frozen=True)
class MetricsIndexVM(BaseLayoutVM):
    """VM for ``GET /metrics``. Extends BaseLayoutVM per §A.8 + §I.5."""

    surfaces: tuple[MetricsIndexSurface, ...] = field(default_factory=tuple)


def build_metrics_index_vm(conn: sqlite3.Connection) -> MetricsIndexVM:
    """Factory per plan §A.18 + §I.5: populate
    ``unresolved_material_discrepancies_count`` via the discrepancies helper
    eagerly so the banner block can render from Sub-bundle A onward.

    ``session_date`` uses forward-looking ``action_session_for_run(now)``
    matching the dashboard surface (the navigator is operator-facing entry
    to all metrics surfaces; session_date matches the dashboard topbar).
    """
    return MetricsIndexVM(
        session_date=action_session_for_run(datetime.now()).isoformat(),
        unresolved_material_discrepancies_count=count_unresolved_material(conn),
        recent_multi_leg_auto_correction_count=(
            count_recent_multi_leg_auto_corrections(conn)
        ),
        surfaces=_SURFACES,
    )
