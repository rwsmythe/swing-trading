"""Phase 13 T2.SB1 T-A.1.6 — ``/patterns/exemplars`` view model.

Per plan §G.1 T-A.1.6 + §A.3 base-layout VM banner pin + §A.18 discrepancies
helper hand-off LOCK + spec §5.9 step 5: operator spot-check surface for
silver-tier exemplars produced by ``swing patterns label-exemplars``.

Operator actions per spec §5.9 step 5 (silver -> gold promotion + flips):
  - promote_to_gold: silver row's label_source flipped to ``curated_gold`` +
    ``gold_validated_at`` server-stamped.
  - reject: silver row's final_decision flipped to ``rejected``.
  - relabel: final_decision='relabeled' + operator-corrected
    ``final_pattern_class``.
  - watch: final_decision='watch'.

Banner field population per forward-binding lesson #12: every base-layout-
mounted VM populates ``unresolved_material_discrepancies_count`` +
``banner_resolve_link`` + ``recent_multi_leg_auto_correction_count`` so
``base.html.j2`` renders without ``UndefinedError``.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from swing.data.models import PatternExemplar
from swing.data.repos import pattern_exemplars as exemplars_repo
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@dataclass(frozen=True)
class PatternExemplarsVM(BaseLayoutVM):
    """VM for ``GET /patterns/exemplars`` operator spot-check surface."""

    silver_rows: tuple[PatternExemplar, ...] = ()
    gold_rows: tuple[PatternExemplar, ...] = ()
    other_rows: tuple[PatternExemplar, ...] = ()
    total_count: int = 0
    # Empty-cohort advisory text per plan §A.16 + spec §5.10 graceful-at-n=0.
    empty_advisory: str | None = None
    # Phase 13 T2.SB1 LOCK: action_form_values dict round-trips hidden anchors
    # through soft-warn confirm fragments per Phase 9 Sub-bundle D Codex R3
    # Critical #1 closure (form-render hidden anchors must round-trip through
    # `form_values` dict so tampered force=true resubmits don't bypass).
    # T2.SB1 ships ZERO soft-warn pathways for the action surface; the dict
    # is empty by default + future T2.SB6 closed-loop review extends.
    action_form_values: dict[str, str] = field(default_factory=dict)


def build_patterns_exemplars_vm(
    conn: sqlite3.Connection,
    *,
    session_date: str,
) -> PatternExemplarsVM:
    """Build the VM for the operator spot-check surface.

    Per §A.3 + forward-binding lesson #12: populates banner fields from the
    Phase 10 discrepancies helper at construction time so the
    ``base.html.j2`` banner block renders without ``UndefinedError``.
    """
    all_rows = exemplars_repo.list_exemplars(conn)
    silver = tuple(
        r for r in all_rows
        if r.label_source in ("claude_silver", "codex_silver")
    )
    gold = tuple(r for r in all_rows if r.label_source == "curated_gold")
    other = tuple(
        r for r in all_rows
        if r.label_source not in (
            "claude_silver", "codex_silver", "curated_gold",
        )
    )

    empty_advisory: str | None = None
    if not all_rows:
        empty_advisory = (
            "No exemplars yet. Run `swing patterns label-exemplars` "
            "(per Phase 13 T-A.1.5) to bootstrap a silver-tier corpus."
        )

    return PatternExemplarsVM(
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
        silver_rows=silver,
        gold_rows=gold,
        other_rows=other,
        total_count=len(all_rows),
        empty_advisory=empty_advisory,
    )
