"""Phase 13 T2.SB6b T-A.6.4 — `/patterns/queue` view model.

Per plan G.9 T-A.6.4 + spec section 5.10 lines 796-801: active-learning
prioritized queue. Composes the pure ranking function in
``swing/patterns/active_learning.py``.

L11 LOCK: extends ``BaseLayoutVM`` + populates banner fields.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.patterns.active_learning import (
    CandidatePriority,
    prioritize_candidates,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@dataclass(frozen=True)
class PatternQueueVM(BaseLayoutVM):
    """VM for ``GET /patterns/queue`` active-learning surface."""

    candidates: tuple[CandidatePriority, ...] = ()
    top_k: int = 20
    empty_advisory: str | None = None


def build_patterns_queue_vm(
    conn: sqlite3.Connection,
    *,
    session_date: str,
    top_k: int = 20,
) -> PatternQueueVM:
    candidates = tuple(prioritize_candidates(conn, top_k=top_k))
    empty: str | None = None
    if not candidates:
        empty = (
            "No prioritized candidates. Run the pipeline + populate "
            "pattern_evaluations to seed the active-learning queue."
        )
    return PatternQueueVM(
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
        candidates=candidates,
        top_k=top_k,
        empty_advisory=empty,
    )
