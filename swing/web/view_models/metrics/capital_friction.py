"""View-model for spec §4.4 capital-friction view (Sub-bundle D Task T-D.2).

Wraps :class:`swing.metrics.capital.CapitalFrictionResult` for template
consumption with the shared :class:`BaseLayoutVM` mixin populated per
plan §A.18 + §I.5.

Per plan §A.6 + §I.4: FIRST surface to render the dynamic PROVISIONAL/LIVE
badge. The badge text comes verbatim from the result's
``capital_denominator_badge`` field; the template renders it as a TEXT
badge inline alongside the metric value (NOT color-only) per spec §4.9.

Per plan §A.0.1 Codex R2 Major #4: trend section renders the historical-
reconstruction disclosure footnote verbatim (BINDING):
``"Trend computed from current trade state; historical points approximate
where state has changed since the run."``

Per plan §A.9 + §I.6 LOCK: pure server-rendered HTML. No HTMX OOB-swap,
no HX-Redirect, no embedded forms.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.evaluation.dates import PageKind, last_completed_session, topbar_session_date
from swing.metrics.capital import (
    CapitalFrictionResult,
    compute_capital_friction,
)
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM

# Plan §A.0.1 BINDING verbatim text — Codex R2 Major #4. Rendered in
# CapitalFrictionVM trend section + IdentificationFunnelVM trend section
# (same constant referenced from both VMs for drift-free parity).
HISTORICAL_DISCLOSURE_FOOTNOTE: str = (
    "Trend computed from current trade state; historical points "
    "approximate where state has changed since the run."
)


@dataclass(frozen=True)
class CapitalFrictionVM(BaseLayoutVM):
    """VM for ``GET /metrics/capital-friction`` per plan §G Task D.2.

    Carries the per-metric :class:`CapitalFrictionResult` plus the
    historical-reconstruction disclosure footnote constant rendered by
    the template's trend section.
    """

    result: CapitalFrictionResult | None = None
    historical_disclosure_footnote: str = HISTORICAL_DISCLOSURE_FOOTNOTE

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.result is None:
            raise ValueError(
                "CapitalFrictionVM.result must be supplied (build via "
                "build_capital_friction_vm factory)"
            )
        if not self.historical_disclosure_footnote:
            raise ValueError(
                "CapitalFrictionVM.historical_disclosure_footnote must be "
                "non-empty (plan §A.0.1 BINDING)"
            )


def build_capital_friction_vm(
    *,
    cfg: Config,
    conn: sqlite3.Connection | None = None,
) -> CapitalFrictionVM:
    """Build the capital-friction VM per plan §A.18 + §I.5.

    Plan §A.15 LOCK: asof_date uses backward-looking
    ``last_completed_session(datetime.now())`` to align with the
    ``account_equity_snapshots.snapshot_date`` writer (per Phase 9
    Sub-bundle C). Forward-looking ``action_session_for_run`` MUST NOT be
    used here — would create the session-anchor read/write mismatch
    family per CLAUDE.md gotcha.
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
        now = datetime.now()
        asof = last_completed_session(now)
        result = compute_capital_friction(conn, asof_date=asof)
    finally:
        if own_conn:
            conn.close()
    return CapitalFrictionVM(
        session_date=topbar_session_date(PageKind.HISTORY_ANALYSIS, datetime.now()).isoformat(),
        unresolved_material_discrepancies_count=unresolved,
        recent_multi_leg_auto_correction_count=recent_multi_leg,
        banner_resolve_link=banner_resolve_link,
        result=result,
    )
