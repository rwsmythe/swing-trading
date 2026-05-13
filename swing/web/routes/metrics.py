"""Phase 10 metrics dashboard routes (plan §A.3).

Single router with 8 surface GETs + 1 umbrella index GET. Sub-bundle A
lands only the index + the router skeleton; Sub-bundles B/C/D/E land
their respective surface endpoints.

Per plan §A.9 + §I.6 LOCK: all Phase 10 surfaces are pure server-rendered
HTML — NO HTMX OOB-swap, NO HX-Redirect, NO embedded forms.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from swing.web.view_models.metrics.capital_friction import (
    build_capital_friction_vm,
)
from swing.web.view_models.metrics.deviation_outcome import (
    build_deviation_outcome_vm,
)
from swing.web.view_models.metrics.hypothesis_progress_card import (
    build_hypothesis_progress_card_vm,
)
from swing.web.view_models.metrics.index import build_metrics_index_vm
from swing.web.view_models.metrics.maturity_stage import (
    build_maturity_stage_vm,
)
from swing.web.view_models.metrics.tier_comparison import (
    build_tier_comparison_vm,
)
from swing.web.view_models.metrics.trade_process_card import (
    build_trade_process_card_vm,
)

router = APIRouter()


@router.get("/metrics", response_class=HTMLResponse)
def metrics_index(request: Request):
    """8-tile navigator for Phase 10 metrics surfaces."""
    db_path = request.app.state.cfg.paths.db_path
    conn = sqlite3.connect(db_path)
    try:
        vm = build_metrics_index_vm(conn)
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "metrics/index.html.j2", {"vm": vm},
    )


@router.get("/metrics/trade-process", response_class=HTMLResponse)
def metrics_trade_process(
    request: Request,
    cohort: str | None = Query(default=None),
):
    """Spec §4.1 trade-process card — Sub-bundle B Task T-B.3.

    Renders 5 cohort tabs (4 registry cohorts + "All closed trades").
    The active tab is operator-selected via ``?cohort=<name>``;
    default-active is the FIRST cohort per spec §4.1 binding.
    """
    cfg = request.app.state.cfg
    vm = build_trade_process_card_vm(cfg=cfg, active_cohort_key=cohort)
    return request.app.state.templates.TemplateResponse(
        request, "metrics/trade_process_card.html.j2", {"vm": vm},
    )


@router.get("/metrics/tier-comparison", response_class=HTMLResponse)
def metrics_tier_comparison(
    request: Request,
    exclude_discrepancies: int = Query(default=0),
):
    """Spec §4.3 tier-comparison view — Sub-bundle C Task T-C.2.

    Renders the 4 registered hypothesis_registry cohorts side-by-side
    with Wilson win-rate CI + Bootstrap expectancy CI + per-non-A+
    ``cohort_relative_to_aplus_pct`` + single ``cohort_ci_overlap_descriptor``
    TEXT block. Per spec §3.3 R1 M3 LOCK: descriptor is TEXT (NOT
    boolean). Per spec §4.3 surface LOCK: cohort cells suppress at n<5.

    Per T-C.5 elective (electives amendment §2): ``?exclude_discrepancies=1``
    filters trades with unresolved material reconciliation discrepancies
    out of the cohort aggregates before classification. Any truthy
    integer activates the filter; missing parameter or ``0`` keeps it
    inactive. Per plan §A.9 + §I.6 LOCK: static-render link, NOT
    HTMX OOB-swap.
    """
    cfg = request.app.state.cfg
    vm = build_tier_comparison_vm(
        cfg=cfg,
        exclude_unresolved_discrepancies=bool(exclude_discrepancies),
    )
    return request.app.state.templates.TemplateResponse(
        request, "metrics/tier_comparison.html.j2", {"vm": vm},
    )


@router.get("/metrics/deviation-outcome", response_class=HTMLResponse)
def metrics_deviation_outcome(
    request: Request,
    exclude_discrepancies: int = Query(default=0),
):
    """Spec §4.7 deviation-outcome view — Sub-bundle C Task T-C.3.

    Renders the 4 registered hypothesis_registry cohorts as rows with
    each cohort's ``doctrine_deviation_class`` enum +
    ``expectancy_relative_to_aplus_pct`` (PERCENT delta with sign) +
    ``decision_criterion_evaluation_text`` rendered verbatim from the
    migration 0008 seed.

    Per spec §3.7 R1 M4 LOCK: NO automated decision-criterion evaluation
    in V1 — operator reads + judges. Per spec §4.7 surface LOCK: cohort
    row stays VISIBLE at n<5 (showing deviation-class + criterion text);
    the relative-pct cell shows "n too low" placeholder.

    Per T-C.5 elective (electives amendment §2): ``?exclude_discrepancies=1``
    filters trades with unresolved material reconciliation discrepancies
    out of the cohort aggregates before classification.
    """
    cfg = request.app.state.cfg
    vm = build_deviation_outcome_vm(
        cfg=cfg,
        exclude_unresolved_discrepancies=bool(exclude_discrepancies),
    )
    return request.app.state.templates.TemplateResponse(
        request, "metrics/deviation_outcome.html.j2", {"vm": vm},
    )


@router.get("/metrics/capital-friction", response_class=HTMLResponse)
def metrics_capital_friction(request: Request):
    """Spec §4.4 capital-friction view — Sub-bundle D Task T-D.2.

    Renders point-in-time gauges (current_capital_utilization_pct +
    current_portfolio_heat_pct + concurrent_open_positions +
    capital_cycle_time_days + risk_feasibility_blocked_rate +
    capital_feasibility_pressure_index) with PROVISIONAL/LIVE dynamic
    badge per plan §A.6 + spec §4.9 TEXT-only LOCK.

    Multi-run trend (30-trading-session window ending at backward-looking
    ``last_completed_session(now)``) suppressed at <5 runs per spec §4.4;
    when rendered, the §A.0.1 historical-reconstruction disclosure
    footnote appears verbatim below the trend table.

    Per plan §A.9 + §I.6 LOCK: pure server-rendered HTML; NO HTMX
    OOB-swap, NO HX-Redirect, NO embedded forms.
    """
    cfg = request.app.state.cfg
    vm = build_capital_friction_vm(cfg=cfg)
    return request.app.state.templates.TemplateResponse(
        request, "metrics/capital_friction.html.j2", {"vm": vm},
    )


@router.get("/metrics/maturity-stage", response_class=HTMLResponse)
def metrics_maturity_stage(request: Request):
    """Spec §4.5 maturity-stage view — Sub-bundle D Task T-D.4.

    Renders per-open-position table sorted by maturity_stage with stage
    enum + open_MFE_R/MAE_R + current_stop + planned_target_R + trail-MA
    eligibility + position_capital_utilization_pct (with PROVISIONAL/LIVE
    per-row badge) + position_portfolio_heat_contribution_dollars.

    Per spec §4.5 + plan §G T-D.4 acceptance: NULL Phase-8-capture-need
    cells (``trail_MA_candidate_price``, ``planned_target_R``) render
    ``"—"`` placeholder (NOT "[Phase 8 capture pending]" — Phase 8 IS
    shipped; NULL is a data-state, not a capture-state).

    Empty-state placeholder: ``"No open positions to manage."``

    Per plan §A.9 + §I.6 LOCK: pure server-rendered HTML.
    """
    cfg = request.app.state.cfg
    vm = build_maturity_stage_vm(cfg=cfg)
    return request.app.state.templates.TemplateResponse(
        request, "metrics/maturity_stage.html.j2", {"vm": vm},
    )


@router.get("/metrics/hypothesis-progress", response_class=HTMLResponse)
def metrics_hypothesis_progress(request: Request):
    """Spec §4.2 hypothesis-progress card — Sub-bundle B Task T-B.5.

    Renders the 4 hypothesis_registry cohorts in a row layout with
    progress bars, tripwire indicators, decision_criteria text, and the
    last 5 transition-history entries newest-first (per plan §A.11
    supersession of spec §3.2 V1-limitation).
    """
    cfg = request.app.state.cfg
    vm = build_hypothesis_progress_card_vm(cfg=cfg)
    return request.app.state.templates.TemplateResponse(
        request, "metrics/hypothesis_progress_card.html.j2", {"vm": vm},
    )
