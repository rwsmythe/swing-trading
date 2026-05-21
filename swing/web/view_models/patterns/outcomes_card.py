"""Phase 13 T2.SB6b T-A.6.5 — `/metrics/pattern-outcomes` view model.

Per plan G.9 T-A.6.5 + spec section 5.10 item 8 + OQ-10 LOCK: 9th metric
tile per-pattern-class outcome distribution. ADDITIVE on top of the
shipped 8 Phase 10 metric tiles + 1 umbrella `/metrics` navigator (L10
LOCK).

Reuses Phase 10 `swing/metrics/cohort.py` + `honesty.py` confidence-floor
+ Wilson-CI badge helpers (per spec section 5.10 "composes with Phase 10
metrics cohort architecture").
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from swing.data.repos.risk_policy import get_active_policy
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.metrics.pattern_outcomes import (
    PatternOutcomeRow,
    build_pattern_outcome_rows,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@dataclass(frozen=True)
class PatternOutcomesVM(BaseLayoutVM):
    """VM for ``GET /metrics/pattern-outcomes``."""

    pattern_outcome_rows: tuple[PatternOutcomeRow, ...] = field(
        default_factory=tuple,
    )


def build_pattern_outcomes_vm(
    conn: sqlite3.Connection, *, session_date: str,
) -> PatternOutcomesVM:
    policy = get_active_policy(conn)
    rows = tuple(build_pattern_outcome_rows(conn, policy=policy))
    return PatternOutcomesVM(
        session_date=session_date,
        unresolved_material_discrepancies_count=(
            count_unresolved_material(conn)
        ),
        recent_multi_leg_auto_correction_count=(
            count_recent_multi_leg_auto_corrections(conn)
        ),
        banner_resolve_link=(
            fetch_first_pending_ambiguity_resolve_link_path(conn)
        ),
        pattern_outcome_rows=rows,
    )
