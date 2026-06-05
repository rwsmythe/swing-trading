"""View-model for spec §4.7 deviation-outcome view (Sub-bundle C T-C.3).

Wraps :class:`swing.metrics.tier.DeviationOutcomeResult` for template
consumption with the shared :class:`BaseLayoutVM` mixin populated per
plan §A.18 + §I.5.

Per spec §4.7 + dispatch brief §2 S3 acceptance:
- 4-cohort rows (taxonomy-locked; orphan rows EXCLUDED).
- Each row shows: ``doctrine_deviation_class`` enum text +
  ``expectancy_relative_to_aplus_pct`` rendered as PERCENT delta with
  sign (e.g., "-75.0%") when both that cohort AND A+ have n>=5;
  ``decision_criterion_evaluation_text`` rendered verbatim from
  migration 0008 (manual-only in V1 per spec §3.7 R1 M4 LOCK; NO
  automated evaluation).
- Per spec §4.7 surface LOCK: cohort row stays VISIBLE at n<5 with
  doctrine-deviation-class + decision-criterion text always rendered;
  ``row_suppressed=True`` flags the relative-pct cell suppression at
  the template layer.
- Base layout: nav + session date + dark-theme toggle + discrepancy
  banner.

Per plan §A.9 + §I.6 LOCK: pure server-rendered HTML.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.evaluation.dates import PageKind, topbar_session_date
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.metrics.tier import (
    DeviationOutcomeResult,
    compute_deviation_outcome,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@dataclass(frozen=True)
class DeviationOutcomeVM(BaseLayoutVM):
    """VM for ``GET /metrics/deviation-outcome`` per plan §F Task C.3.

    Per-cohort data carried in :class:`swing.metrics.tier.DeviationOutcomeRow`
    (via ``result.rows``); template iterates the 4-cohort tuple and
    renders per-cohort rows inline.

    Per dispatch brief §0.5 #4 BINDING + spec §4.7: taxonomy-locked to
    the 4 registered cohorts. Orphan-labeled trades NOT rendered as
    additional rows.
    """

    result: DeviationOutcomeResult | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.result is None:
            raise ValueError(
                "DeviationOutcomeVM.result must be supplied (build via "
                "build_deviation_outcome_vm factory)"
            )


def build_deviation_outcome_vm(
    *,
    cfg: Config,
    conn: sqlite3.Connection | None = None,
    exclude_unresolved_discrepancies: bool = False,
) -> DeviationOutcomeVM:
    """Build the deviation-outcome VM eagerly populating discrepancies field
    per plan §A.18 + §I.5.

    Per T-C.5 elective (electives amendment §2): when
    ``exclude_unresolved_discrepancies=True``, trades with unresolved
    material reconciliation discrepancies are filtered out of the cohort
    aggregates (delegated to :func:`compute_deviation_outcome`).
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
        result = compute_deviation_outcome(
            conn,
            exclude_unresolved_discrepancies=exclude_unresolved_discrepancies,
        )
    finally:
        if own_conn:
            conn.close()
    return DeviationOutcomeVM(
        session_date=topbar_session_date(PageKind.HISTORY_ANALYSIS, datetime.now()).isoformat(),
        unresolved_material_discrepancies_count=unresolved,
        recent_multi_leg_auto_correction_count=recent_multi_leg,
        banner_resolve_link=banner_resolve_link,
        result=result,
    )
