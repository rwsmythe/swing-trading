"""View-model for spec §4.3 tier-comparison view (Sub-bundle C T-C.2).

Wraps :class:`swing.metrics.tier.TierComparisonResult` for template
consumption with the shared :class:`BaseLayoutVM` mixin populated per
plan §A.18 + §I.5 (eager ``unresolved_material_discrepancies_count``).

Per spec §4.3 + dispatch brief §2 S2 acceptance:
- 4-cohort side-by-side table (taxonomy-locked; orphan rows EXCLUDED).
- Per-cohort cells render Wilson win-rate CI + Bootstrap expectancy CI
  when n>=5; "n too low" italic placeholder when n<5 (spec §5.6 format).
- ``cohort_relative_to_aplus_pct`` rendered as PERCENT raw-ratio
  (e.g., "25.0%") for non-A+ cohorts when both that cohort AND A+ have
  n>=5; otherwise "—" placeholder.
- ``cohort_ci_overlap_descriptor`` rendered as a single TEXT block
  separate from per-cohort cells; suppression placeholder when either
  A+ or Sub-A+ has n<5.
- Base layout: nav + session date + dark-theme toggle + discrepancy
  banner.

Per plan §A.9 + §I.6 LOCK: pure server-rendered HTML. No HTMX OOB-swap,
no HX-Redirect, no embedded forms.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.evaluation.dates import action_session_for_run
from swing.metrics.discrepancies import count_unresolved_material
from swing.metrics.tier import (
    TierComparisonResult,
    compute_tier_comparison,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@dataclass(frozen=True)
class TierComparisonVM(BaseLayoutVM):
    """VM for ``GET /metrics/tier-comparison`` per plan §F Task C.2.

    The cohort-level data lives in :class:`swing.metrics.tier.CohortStatistics`
    (carried via ``result.cohorts``); template iterates the 4-cohort tuple
    and renders per-cohort cells inline.

    Per dispatch brief §0.5 #4 BINDING + spec §4.3: taxonomy-locked to the
    4 registered cohorts. Orphan-labeled trades NOT rendered as additional
    columns (the compute layer enforces this; the VM merely surfaces the
    result).
    """

    result: TierComparisonResult | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.result is None:
            raise ValueError(
                "TierComparisonVM.result must be supplied (build via "
                "build_tier_comparison_vm factory)"
            )


def build_tier_comparison_vm(
    *,
    cfg: Config,
    conn: sqlite3.Connection | None = None,
) -> TierComparisonVM:
    """Build the tier-comparison VM eagerly populating discrepancies field
    per plan §A.18 + §I.5."""
    own_conn = conn is None
    if own_conn:
        conn = connect(cfg.paths.db_path)
    assert conn is not None
    try:
        unresolved = count_unresolved_material(conn)
        result = compute_tier_comparison(conn)
    finally:
        if own_conn:
            conn.close()
    return TierComparisonVM(
        session_date=action_session_for_run(datetime.now()).isoformat(),
        unresolved_material_discrepancies_count=unresolved,
        result=result,
    )
