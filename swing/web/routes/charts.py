"""Date-less chart-image redirect route — Tier-2 #2.

Operator-friendly URL `/charts/{ticker}.png` that resolves to the latest
completed pipeline run's `data_asof_date` and either redirects to the
existing date-prefixed StaticFiles URL or returns an informative 404 with
the chart-unavailable reason from `chart_scope.resolve_chart_scope`.

The router MUST be registered BEFORE `app.mount("/charts", StaticFiles(...))`
in `swing/web/app.py` so the dynamic handler fires for single-segment paths
like `/charts/AAPL.png`. Two-segment paths like `/charts/2026-04-17/AAPL.png`
do not match `{ticker}.png` (Starlette path params don't span `/`) and
correctly fall through to the StaticFiles mount.
"""
from __future__ import annotations

import html

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from swing.data.db import connect
from swing.web.chart_scope import (
    CHART_REASON_MESSAGES,
    latest_completed_pipeline_run,
    resolve_chart_scope,
)

router = APIRouter()


def _unavailable_html(*, ticker: str, message: str) -> str:
    safe_ticker = html.escape(ticker)
    safe_message = html.escape(message)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>Chart unavailable — {safe_ticker}</title></head>"
        f"<body><h1>Chart unavailable for {safe_ticker}</h1>"
        f"<p>{safe_message}</p></body></html>"
    )


@router.get("/charts/{ticker}.png")
def charts_redirect(request: Request, ticker: str):
    """Resolve `ticker` against the latest completed pipeline run and redirect
    to the date-prefixed StaticFiles URL, or return 404 with the operator-
    facing reason message when the chart is unavailable.
    """
    ticker_upper = ticker.upper()
    cfg = request.app.state.cfg

    redirect_date: str | None = None
    reason: str | None = None
    message: str | None = None
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            binding = latest_completed_pipeline_run(conn)
            if binding is None:
                return HTMLResponse(
                    _unavailable_html(
                        ticker=ticker_upper,
                        message=CHART_REASON_MESSAGES["no-run"],
                    ),
                    status_code=404,
                )
            reason, message = resolve_chart_scope(
                conn, binding=binding, ticker=ticker_upper,
                charts_dir=cfg.paths.charts_dir,
                chart_top_n_watch=cfg.pipeline.chart_top_n_watch,
            )
            if reason is None:
                # binding.data_asof_date is paired with binding.run_id —
                # SAME run that produced `reason=None`. No drift race.
                redirect_date = binding.data_asof_date
    finally:
        conn.close()

    if reason is None:
        return RedirectResponse(
            url=f"/charts/{redirect_date}/{ticker_upper}.png",
            status_code=303,
        )
    return HTMLResponse(
        _unavailable_html(
            ticker=ticker_upper,
            message=message or CHART_REASON_MESSAGES.get(reason, "Chart unavailable."),
        ),
        status_code=404,
    )
