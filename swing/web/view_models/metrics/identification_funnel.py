"""View-model for spec §4.6 identification-vs-trade-funnel (T-D.6).

Wraps :class:`swing.metrics.funnel.IdentificationFunnelResult` for
template consumption with the shared :class:`BaseLayoutVM` mixin per
plan §A.18 + §I.5.

Per plan §A.0.1 Codex R2 Major #4 + dispatch brief §0.10 BINDING: the
template's trend section renders the EXACT verbatim disclosure footnote
``"Trend computed from current trade state; historical points approximate
where state has changed since the run."`` — SAME constant as
CapitalFrictionVM (drift-free parity via the
:data:`HISTORICAL_DISCLOSURE_FOOTNOTE` import below).

Per plan §A.9 + §I.6 LOCK: pure server-rendered HTML.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.evaluation.dates import action_session_for_run, last_completed_session
from swing.metrics.discrepancies import count_unresolved_material
from swing.metrics.funnel import (
    IdentificationFunnelResult,
    compute_identification_funnel,
)
from swing.web.view_models.metrics.capital_friction import (
    HISTORICAL_DISCLOSURE_FOOTNOTE,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@dataclass(frozen=True)
class IdentificationFunnelVM(BaseLayoutVM):
    """VM for ``GET /metrics/identification-funnel`` per plan §G T-D.6."""

    result: IdentificationFunnelResult | None = None
    historical_disclosure_footnote: str = HISTORICAL_DISCLOSURE_FOOTNOTE

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.result is None:
            raise ValueError(
                "IdentificationFunnelVM.result must be supplied (build via "
                "build_identification_funnel_vm factory)"
            )
        if not self.historical_disclosure_footnote:
            raise ValueError(
                "IdentificationFunnelVM.historical_disclosure_footnote must "
                "be non-empty (plan §A.0.1 BINDING)"
            )


def build_identification_funnel_vm(
    *,
    cfg: Config,
    conn: sqlite3.Connection | None = None,
) -> IdentificationFunnelVM:
    """Build the identification-funnel VM per plan §A.18 + §I.5."""
    own_conn = conn is None
    if own_conn:
        conn = connect(cfg.paths.db_path)
    assert conn is not None
    try:
        unresolved = count_unresolved_material(conn)
        result = compute_identification_funnel(
            conn, asof_date=last_completed_session(datetime.now()),
        )
    finally:
        if own_conn:
            conn.close()
    return IdentificationFunnelVM(
        session_date=action_session_for_run(datetime.now()).isoformat(),
        unresolved_material_discrepancies_count=unresolved,
        result=result,
    )
