"""Phase 3b trade-action routes. Starts with sizing-hint; entry/exit/stop
endpoints are added in later tasks. All write endpoints require HX-Request
under strict OriginGuard (spec §3.3)."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from markupsafe import Markup

from swing.data.db import connect
from swing.data.repos.cash import list_cash
from swing.data.repos.trades import get_trade, list_all_exits, list_open_trades
from swing.trades.exit import ExitReason, ExitRequest, record_exit
from swing.trades.stop_adjust import StopAdjustRequest, StopRegressionError, adjust_stop
from swing.recommendations.sizing import compute_shares, SizingResult
from swing.trades.entry import (
    EntryRequest, HardCapException, DuplicateOpenPositionException,
    SoftWarnException, record_entry,
)
from swing.trades.equity import current_equity
from swing.web.routes.dashboard import _templates
from swing.web.view_models.dashboard import build_dashboard
from swing.web.view_models.open_positions_row import build_open_positions_row
from swing.web.view_models.trades import build_entry_form_vm, build_exit_form_vm, build_stop_form_vm

log = logging.getLogger(__name__)
router = APIRouter()


def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


@router.get("/trades/entry/sizing-hint", response_class=HTMLResponse)
def sizing_hint(
    request: Request,
    entry_price: str | None = None,
    initial_stop: str | None = None,
) -> HTMLResponse:
    """Tolerant sizing-hint endpoint (spec §4.6). Always 200.

    Mode contract:
      - Missing / blank / non-numeric / non-positive / stop >= entry
        → 'dim' guidance fragment ("Enter a valid entry price and stop...").
      - Valid inputs + SizingResult(feasible=True) → numbers fragment.
      - SizingResult(feasible=False) → dim fragment with the specific reason.
      - Any unexpected exception → caught, logged WARNING, dim fallback fragment.
    """
    templates = _templates(request)
    cfg = request.app.state.cfg
    entry = _parse_optional_float(entry_price)
    stop = _parse_optional_float(initial_stop)

    if entry is None or stop is None or entry <= 0 or stop <= 0 or stop >= entry:
        return templates.TemplateResponse(
            request, "partials/sizing_hint.html.j2",
            {"guidance": "Enter a valid entry price and stop (stop < entry) to see sizing"},
        )

    try:
        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                exits = list_all_exits(conn)
                cash_movements = list_cash(conn)
        finally:
            conn.close()
        equity = current_equity(
            starting_equity=cfg.account.starting_equity,
            exits=exits, cash_movements=cash_movements,
        )
        sizing: SizingResult = compute_shares(
            entry=entry, stop=stop, equity=equity,
            max_risk_pct=cfg.risk.max_risk_pct,
            position_pct_cap=cfg.sizing.position_pct_cap,
        )
    except Exception as exc:
        log.warning("sizing-hint unexpected exception: %s", exc)
        return templates.TemplateResponse(
            request, "partials/sizing_hint.html.j2",
            {"guidance": "Sizing unavailable — check values"},
        )

    if not sizing.feasible:
        if sizing.constraint == "no_equity":
            reason = "No equity recorded — add a cash_movement or set account.starting_equity"
        else:
            reason = "Risk cap too tight for 1 share at this stop"
        return templates.TemplateResponse(
            request, "partials/sizing_hint.html.j2",
            {"guidance": reason},
        )

    return templates.TemplateResponse(
        request, "partials/sizing_hint.html.j2",
        {"sizing": sizing},
    )


@router.get("/trades/entry/form", response_class=HTMLResponse)
def entry_form(request: Request, ticker: str):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)
    vm = build_entry_form_vm(ticker=ticker, cfg=cfg, cache=cache, executor=executor)
    return templates.TemplateResponse(
        request, "partials/trade_entry_form.html.j2", {"vm": vm},
    )


@router.post("/trades/entry", response_class=HTMLResponse)
def entry_post(
    request: Request,
    ticker: str = Form(...),
    entry_date: str = Form(...),
    entry_price: float = Form(...),
    shares: int = Form(...),
    initial_stop: float = Form(...),
    rationale: str = Form(...),
    notes: str | None = Form(None),
    watchlist_target: float | None = Form(None),
    watchlist_stop: float | None = Form(None),
    force: str | None = Form(None),
):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)

    req = EntryRequest(
        ticker=ticker.upper(),
        entry_date=entry_date,
        entry_price=entry_price,
        shares=shares,
        initial_stop=initial_stop,
        watchlist_entry_target=watchlist_target,
        watchlist_initial_stop=watchlist_stop,
        notes=notes,
        rationale=rationale,
        event_ts=datetime.now().isoformat(timespec="seconds"),
    )

    conn = connect(cfg.paths.db_path)
    try:
        try:
            result = record_entry(
                conn, req,
                soft_warn=cfg.position_limits.soft_warn_open,
                hard_cap=cfg.position_limits.hard_cap_open,
                force=(force == "true"),
            )
        except SoftWarnException:
            # First submit at soft cap — render the 2-step confirm fragment.
            # Re-serialize the submitted form values so the next submit carries
            # them + force=true (spec §4.3 step 4).
            # R2 Minor 1: show the ACTUAL open_count in the banner numerator,
            # not the threshold — "5/4" when 5 are open with soft_warn=4.
            conn_count = connect(cfg.paths.db_path)
            try:
                actual_open = len(list_open_trades(conn_count))
            finally:
                conn_count.close()
            form_values = {
                "ticker": req.ticker,
                "entry_date": req.entry_date,
                "entry_price": req.entry_price,
                "shares": req.shares,
                "initial_stop": req.initial_stop,
                "rationale": req.rationale,
                "notes": req.notes or "",
                "watchlist_target": req.watchlist_entry_target or "",
                "watchlist_stop": req.watchlist_initial_stop or "",
                "open_count": actual_open,
                "soft_warn": cfg.position_limits.soft_warn_open,
                "hard_cap": cfg.position_limits.hard_cap_open,
            }
            return templates.TemplateResponse(
                request, "partials/soft_warn_confirm.html.j2",
                {"form_values": form_values},
            )
        except (HardCapException, DuplicateOpenPositionException) as exc:
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": str(exc), "form_body": None},
                status_code=400,
            )
    finally:
        conn.close()

    # Two-call rebuild (spec §4.3 step 6).
    # a) Primary row.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            open_trades = list_open_trades(conn)
    finally:
        conn.close()
    new_trade = next(t for t in open_trades if t.id == result.trade_id)
    row_vm = build_open_positions_row(
        trade=new_trade, cfg=cfg, cache=cache, executor=executor,
    )

    # b) Dashboard rebuild — source for OOB fragments.
    dashboard_vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)

    # Render response: primary row + #status-strip OOB + #watchlist-top5 OOB.
    # R3 Major 2 + Minor 1 fix: render the watchlist-top5 region via a shared
    # partial (watchlist_top5_section.html.j2) so the POST-success OOB fragment
    # and the dashboard page render identically — heading, table, "Show all"
    # link, all column headers. Single source of truth eliminates the drift
    # risk R3 flagged. Status-strip similarly uses its existing 3a partial.
    row_html = templates.get_template("partials/open_positions_row.html.j2").render(
        request=request, row=row_vm,
    )
    status_strip_html = templates.get_template("partials/status_strip.html.j2").render(
        request=request, vm=dashboard_vm,
    )
    watchlist_section_html = templates.get_template(
        "partials/watchlist_top5_section.html.j2"
    ).render(request=request, vm=dashboard_vm)

    return HTMLResponse(Markup(
        f'{row_html}'
        f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
        f'<section id="watchlist-top5" hx-swap-oob="true">'
        f'{watchlist_section_html}'
        f'</section>'
    ))


@router.get("/trades/{trade_id}/exit/form", response_class=HTMLResponse)
def exit_form(request: Request, trade_id: int):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)
    vm = build_exit_form_vm(trade_id=trade_id, cfg=cfg, cache=cache, executor=executor)
    if vm is None:
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found or not open")
    return templates.TemplateResponse(
        request, "partials/trade_exit_form.html.j2", {"vm": vm},
    )


@router.post("/trades/{trade_id}/exit", response_class=HTMLResponse)
def exit_post(
    request: Request,
    trade_id: int,
    exit_date: str = Form(...),
    exit_price: float = Form(...),
    shares: int = Form(...),
    reason: str = Form(...),
    rationale: str = Form(...),
    notes: str | None = Form(None),
):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)

    # Validate reason.
    try:
        reason_enum = ExitReason(reason)
    except ValueError:
        return templates.TemplateResponse(
            request, "partials/trade_form_error.html.j2",
            {"error_message": f"Invalid reason: {reason}", "form_body": None},
            status_code=400,
        )

    req = ExitRequest(
        trade_id=trade_id, exit_date=exit_date, exit_price=exit_price,
        shares=shares, reason=reason_enum, notes=notes, rationale=rationale,
        event_ts=datetime.now().isoformat(timespec="seconds"),
    )

    conn = connect(cfg.paths.db_path)
    try:
        try:
            result = record_exit(conn, req)
        except Exception as exc:
            # R: spec §5.1 case 2 — re-render form with authoritative remaining shares.
            vm = build_exit_form_vm(trade_id=trade_id, cfg=cfg, cache=cache, executor=executor)
            form_body = None
            if vm is not None:
                form_body = templates.get_template(
                    "partials/trade_exit_form.html.j2"
                ).render(request=request, vm=vm)
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": str(exc), "form_body": form_body},
                status_code=400,
            )
    finally:
        conn.close()

    # Two-call rebuild.
    dashboard_vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)
    status_strip_html = templates.get_template("partials/status_strip.html.j2").render(
        request=request, vm=dashboard_vm,
    )

    if result.fully_closed:
        # Primary target: empty/hidden stub so the row disappears.
        return HTMLResponse(Markup(
            f'<tr id="open-position-{trade_id}" style="display:none"></tr>'
            f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
        ))

    # Partial: re-render the row.
    conn2 = connect(cfg.paths.db_path)
    try:
        updated = get_trade(conn2, trade_id)
    finally:
        conn2.close()
    row_vm = build_open_positions_row(
        trade=updated, cfg=cfg, cache=cache, executor=executor,
    )
    row_html = templates.get_template("partials/open_positions_row.html.j2").render(
        request=request, row=row_vm,
    )
    return HTMLResponse(Markup(
        f'{row_html}'
        f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
    ))


@router.get("/trades/{trade_id}/stop/form", response_class=HTMLResponse)
def stop_form(request: Request, trade_id: int):
    cfg = request.app.state.cfg
    templates = _templates(request)
    vm = build_stop_form_vm(trade_id=trade_id, cfg=cfg)
    if vm is None:
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found or not open")
    return templates.TemplateResponse(
        request, "partials/trade_stop_form.html.j2", {"vm": vm},
    )


@router.get("/trades/{trade_id}/cancel", response_class=HTMLResponse)
def trade_cancel(request: Request, trade_id: int):
    """Return the normal open-position row (no form). Used by Cancel buttons."""
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)

    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
    finally:
        conn.close()
    if trade is None or trade.status != "open":
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found or not open")

    row_vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=executor,
    )
    # Single-contract partial: pass only `row` (R1 Major 3 fix).
    return templates.TemplateResponse(
        request, "partials/open_positions_row.html.j2", {"row": row_vm},
    )


@router.post("/trades/{trade_id}/stop", response_class=HTMLResponse)
def stop_post(
    request: Request, trade_id: int,
    new_stop: float = Form(...), rationale: str = Form(...),
):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)

    req = StopAdjustRequest(
        trade_id=trade_id, new_stop=new_stop, rationale=rationale,
        event_ts=datetime.now().isoformat(timespec="seconds"), force=False,
    )
    conn = connect(cfg.paths.db_path)
    try:
        try:
            adjust_stop(conn, req)
        except StopRegressionError as exc:
            # R: spec §5.1 case 3 — re-render form with updated current_stop.
            vm = build_stop_form_vm(trade_id=trade_id, cfg=cfg)
            form_body = None
            if vm is not None:
                form_body = templates.get_template(
                    "partials/trade_stop_form.html.j2"
                ).render(request=request, vm=vm)
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": (
                    f"{exc}. Use CLI `swing trade stop-adjust --trade-id {trade_id} "
                    f"--new-stop {new_stop} --rationale ... --force` if intentional."
                ), "form_body": form_body},
                status_code=400,
            )
    finally:
        conn.close()

    # Row-only render (no OOB).
    conn = connect(cfg.paths.db_path)
    try:
        updated = get_trade(conn, trade_id)
    finally:
        conn.close()
    row_vm = build_open_positions_row(
        trade=updated, cfg=cfg, cache=cache, executor=executor,
    )
    row_html = templates.get_template("partials/open_positions_row.html.j2").render(
        request=request, row=row_vm,
    )
    return HTMLResponse(Markup(row_html))
