"""Hyp-recs trade-prep expansion routes.

Spec §3.5.4: GET /hyp-recs/refresh (close-button target / hyp-recs-origin
entry-form Cancel target).
Spec §3.5.4: GET /hyp-recs/{ticker}/expand (Task 5; defined here as a
placeholder docstring at Task 4 stage).

Both routes are HTMX-driven; under strict OriginGuard the GET routes
do NOT require HX-Request (only writes do), but the templates expect
the request to come from the dashboard so they include HTMX-specific
markup unconditionally.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.web.view_models.dashboard import build_hyp_recs_section

router = APIRouter()


@router.get("/hyp-recs/refresh", response_class=HTMLResponse)
def hyp_recs_refresh(request: Request):
    """Close-button target. Returns ONLY the freshly-rendered hyp-recs section
    so the closing operator sees current hyp-recs values without rebuilding
    open-trades, watchlist top-5, prices for non-recommended tickers, or
    OHLCV (R2-Major-2 — scoped builder, NOT a full build_dashboard call).

    Cross-panel snapshot consistency caveat: the swap target is
    #hypothesis-recommendations only — other dashboard sections retain
    their full-page-render snapshot. Inherent to the partial-swap UX
    and the intentional V1 trade.
    """
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates
    section_vm = build_hyp_recs_section(cfg=cfg, cache=cache, executor=executor)
    return templates.TemplateResponse(
        request,
        "partials/hypothesis_recommendations.html.j2",
        {"vm": section_vm},
    )
