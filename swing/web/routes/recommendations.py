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

from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.cash import list_cash
from swing.data.repos.fills import list_all_fills
from swing.data.repos.trades import list_closed_trades, list_open_trades
from swing.trades.equity import current_equity
from swing.web.view_models.dashboard import (
    build_hyp_recs_expanded,
    build_hyp_recs_section,
)

router = APIRouter()


@dataclass(frozen=True)
class _ExitShape:
    """Local adapter mirroring legacy Exit shape for ExitLike-consuming
    APIs (current_equity). Mirrors view_models/dashboard.py's _ExitShape
    — both die in C.10 when equity.py refactors to consume fills directly.
    Single source of math truth: swing.trades.derived_metrics.
    """
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None


def _list_all_exitshape_via_fills(conn) -> list[_ExitShape]:
    """C.9 migration helper: produces the ExitLike collection that
    ``list_all_exits(conn)`` previously returned, but sourced from
    ``fills`` filtered to non-entry actions.
    """
    from swing.trades.derived_metrics import (
        initial_risk_per_share,
        r_multiple,
        realized_pnl,
    )

    trades_by_id: dict[int, Trade] = {}
    for t in list_open_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t
    for t in list_closed_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t

    out: list[_ExitShape] = []
    for f in list_all_fills(conn):
        if f.action == "entry":
            continue
        trade = trades_by_id.get(f.trade_id)
        if trade is None:
            continue
        rps = initial_risk_per_share(
            entry_price=trade.entry_price, initial_stop=trade.initial_stop,
        )
        pnl = realized_pnl(
            entry_price=trade.entry_price, exit_price=f.price,
            quantity=f.quantity,
        )
        rmult: float | None
        if rps == 0 or f.quantity == 0:
            rmult = None
        else:
            rmult = r_multiple(
                realized_pnl=pnl, initial_risk_per_share=rps,
                quantity=f.quantity,
            )
        exit_date = (
            f.fill_datetime.split("T")[0]
            if "T" in f.fill_datetime else f.fill_datetime
        )
        out.append(_ExitShape(
            trade_id=f.trade_id,
            exit_date=exit_date,
            exit_price=float(f.price),
            shares=int(f.quantity),
            reason=f.reason,
            realized_pnl=pnl,
            r_multiple=rmult,
        ))
    return out


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
    cfg = apply_overrides(request.app.state.cfg)
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
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    ticker_upper = ticker.upper()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            current_balance = current_equity(
                starting_equity=cfg.account.starting_equity,
                exits=_list_all_exitshape_via_fills(conn),
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
