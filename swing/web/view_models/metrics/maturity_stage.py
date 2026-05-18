"""View-model for spec §4.5 maturity-stage view (Sub-bundle D Task T-D.4).

Wraps :class:`swing.metrics.maturity.MaturityStageResult` for template
consumption with the shared :class:`BaseLayoutVM` mixin per plan §A.18 +
§I.5.

Per spec §4.5 + plan §G T-D.4 acceptance: per-row cells with NULL Phase-8-
capture-need columns (``trail_MA_candidate_price``, ``planned_target_R``)
render ``"—"`` placeholder. Phase 8 IS shipped; NULL is a data-state
(legacy / non-target trade) NOT a capture-state.

Empty-state placeholder: ``"No open positions to manage."``

Per plan §A.9 + §I.6 LOCK: pure server-rendered HTML.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.evaluation.dates import action_session_for_run, last_completed_session
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
)
from swing.metrics.maturity import (
    MaturityStageResult,
    compute_maturity_stage,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@dataclass(frozen=True)
class MaturityStageVM(BaseLayoutVM):
    """VM for ``GET /metrics/maturity-stage`` per plan §G T-D.4."""

    result: MaturityStageResult | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.result is None:
            raise ValueError(
                "MaturityStageVM.result must be supplied (build via "
                "build_maturity_stage_vm factory)"
            )


def build_maturity_stage_vm(
    *,
    cfg: Config,
    conn: sqlite3.Connection | None = None,
) -> MaturityStageVM:
    """Build the maturity-stage VM eagerly populating discrepancies field
    per plan §A.18 + §I.5.

    Plan §A.15 LOCK: ``asof_date`` uses backward-looking
    ``last_completed_session(datetime.now())``.
    """
    own_conn = conn is None
    if own_conn:
        conn = connect(cfg.paths.db_path)
    assert conn is not None
    try:
        unresolved = count_unresolved_material(conn)
        recent_multi_leg = count_recent_multi_leg_auto_corrections(conn)
        result = compute_maturity_stage(
            conn, asof_date=last_completed_session(datetime.now()),
        )
    finally:
        if own_conn:
            conn.close()
    return MaturityStageVM(
        session_date=action_session_for_run(datetime.now()).isoformat(),
        unresolved_material_discrepancies_count=unresolved,
        recent_multi_leg_auto_correction_count=recent_multi_leg,
        result=result,
    )
