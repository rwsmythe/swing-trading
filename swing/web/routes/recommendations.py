"""Hyp-recs trade-prep expansion routes.

Spec §3.5.4:
- `GET /hyp-recs/refresh` — close-button target / hyp-recs-origin entry-form
  Cancel target. Returns ONLY the freshly-rendered hyp-recs section partial
  via the scoped `build_hyp_recs_section` builder (R2-Major-2).
- `GET /hyp-recs/{ticker}/expand` — chevron-button target. Returns the
  `hypothesis_recommendations_expanded.html.j2` partial when the ticker is
  in the latest completed pipeline run's candidate set with non-degenerate
  sizing parameters, OR returns 404 + the
  `hyp_recs_expand_unavailable.html.j2` partial otherwise.

Both routes are HTMX-driven; under strict OriginGuard the GET routes
do NOT require HX-Request (only writes do), but the templates expect
the request to come from the dashboard so they include HTMX-specific
markup unconditionally.

Row-target swap awareness: an HTMX request whose `HX-Target` matches a
`hyp-rec-row-*` element MUST receive a `<tr>` fragment on error/404 paths
(see `swing/web/app.py:_ROW_TARGET_PREFIXES`). The 404 path here returns
`hyp_recs_expand_unavailable.html.j2` (a `<tr>`); 500s flow through the
global exception handler which detects the prefix and renders the
trade_form_error.html.j2 fragment.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.data.db import connect
from swing.data.repos.cash import list_cash
from swing.data.repos.trades import list_all_exits, list_open_trades
from swing.trades.equity import current_equity
from swing.web.view_models.dashboard import (
    build_hyp_recs_expanded,
    build_hyp_recs_section,
)

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
    # Bug-fix-C: thread `exclude_tickers={t.ticker for t in open_trades}`
    # so the close-button refresh consistently excludes open-position
    # tickers — same invariant entry_post enforces, same invariant
    # build_dashboard now enforces. Without this, the close-button refresh
    # would re-introduce a just-traded ticker into the panel even though
    # both the entry_post OOB rebuild AND the full /  render correctly
    # exclude it.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            open_trade_tickers = {t.ticker for t in list_open_trades(conn)}
    finally:
        conn.close()
    section_vm = build_hyp_recs_section(
        cfg=cfg, cache=cache, executor=executor,
        exclude_tickers=open_trade_tickers,
    )
    return templates.TemplateResponse(
        request,
        "partials/hypothesis_recommendations.html.j2",
        {"vm": section_vm},
    )


@router.get("/hyp-recs/{ticker}/expand", response_class=HTMLResponse)
def hyp_recs_expand(request: Request, ticker: str):
    """Chevron-target. Renders the per-ticker expansion partial when the
    ticker has a candidate row + non-degenerate sizing under the latest
    completed pipeline run; otherwise returns 404 + the unavailable
    partial.

    Anchor consistency: `build_hyp_recs_expanded` resolves the binding
    via `latest_completed_pipeline_run` — in-flight rows with
    `finished_ts IS NULL` cannot win.
    """
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    ticker_upper = ticker.upper()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            current_balance = current_equity(
                starting_equity=cfg.account.starting_equity,
                exits=list_all_exits(conn),
                cash_movements=list_cash(conn),
            )
            vm = build_hyp_recs_expanded(
                conn, cfg,
                ticker=ticker_upper, current_balance=current_balance,
            )
            if vm is None:
                return templates.TemplateResponse(
                    request,
                    "partials/hyp_recs_expand_unavailable.html.j2",
                    {
                        "ticker": ticker_upper,
                        "message": (
                            "Not a current candidate or pivot data missing."
                        ),
                    },
                    status_code=404,
                )
            return templates.TemplateResponse(
                request,
                "partials/hypothesis_recommendations_expanded.html.j2",
                {"expanded": vm},
                status_code=200,
            )
    finally:
        conn.close()


__all__ = ["router", "hyp_recs_refresh", "hyp_recs_expand"]
