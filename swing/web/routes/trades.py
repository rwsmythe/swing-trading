"""Phase 3b trade-action routes. Starts with sizing-hint; entry/exit/stop
endpoints are added in later tasks. All write endpoints require HX-Request
under strict OriginGuard (spec §3.3)."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from markupsafe import Markup

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.data.repos.cash import list_cash
from swing.data.repos.trades import get_trade, list_all_exits, list_open_trades
from swing.trades.exit import ExitReason, ExitRequest, record_exit
from swing.trades.stop_adjust import (
    StopAdjustRationale, StopAdjustRequest, StopRegressionError, adjust_stop,
)
from swing.recommendations.sizing import compute_shares, SizingResult
from swing.trades.entry import (
    EntryRationale, EntryRequest, HardCapException, DuplicateOpenPositionException,
    SoftWarnException, record_entry,
)
from swing.trades.equity import current_equity
from swing.web.view_models.dashboard import build_dashboard
from swing.web.view_models.open_positions_row import (
    build_open_positions_expanded,
    build_open_positions_row,
)
from swing.web.view_models.trades import (
    _coerce_origin, build_entry_form_vm, build_exit_form_vm, build_stop_form_vm,
)

log = logging.getLogger(__name__)
router = APIRouter()


def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _validate_rationale(
    rationale: str, notes: str | None, rationale_enum,
) -> str | None:
    """Tranche B-ops T4/T5: shared rationale validator.

    Returns an error message when invalid, or ``None`` when valid. Used by
    the entry and stop-adjust POST routes to enforce closed-taxonomy
    rationale values and the ``other`` → ``notes`` required coupling.
    """
    try:
        value = rationale_enum(rationale)
    except ValueError:
        valid = ", ".join(r.value for r in rationale_enum)
        return f"Invalid rationale: {rationale!r}. Choose one of: {valid}."
    if value.value == "other" and not (notes and notes.strip()):
        return "Notes are required when rationale = Other."
    return None


def _rerender_stop_form_with_error(
    *, request: Request, templates, cfg, trade_id: int,
    new_stop: float, rationale: str, notes: str | None,
    error_message: str,
) -> HTMLResponse:
    """T7: re-render trade_stop_form with preservation fields + banner at 400.

    Preservation mirrors TradeEntryFormVM's duplicate-re-render pattern:
    typed ``new_stop`` echoes back via ``new_stop_input``; submitted
    ``rationale`` and ``notes`` pre-select/populate their inputs on the
    re-render. ``force`` is deliberately NOT preserved — spec §5 requires
    the operator to tick the Force checkbox each time they want to submit
    a regression-intentional stop, so the rerender path discards the
    submitted force value.
    """
    from dataclasses import replace as dc_replace
    vm = build_stop_form_vm(trade_id=trade_id, cfg=cfg)
    if vm is not None:
        vm = dc_replace(
            vm,
            new_stop_input=new_stop,
            rationale=rationale,
            notes=notes or "",
        )
        return templates.TemplateResponse(
            request, "partials/trade_stop_form.html.j2",
            {"vm": vm, "error_message": error_message},
            status_code=400,
        )
    return templates.TemplateResponse(
        request, "partials/trade_form_error.html.j2",
        {"error_message": error_message},
        status_code=400,
    )


def _rerender_entry_form_with_error(
    *, request: Request, templates, cfg, cache, executor,
    ticker: str, entry_date: str, entry_price: float, shares: int,
    initial_stop: float, rationale: str, notes: str | None,
    error_message: str, origin: str = "watchlist",
) -> HTMLResponse:
    """T4: re-render trade_entry_form with preserved values + banner at 400.

    Mirrors the duplicate-error re-render path but called from rationale
    validation failures before record_entry is invoked.

    Task 8 (R4-Major-1): ``origin`` threads through so the re-rendered
    form's colspan + Cancel target match the originating surface
    (hyp-recs vs watchlist). Defaults to 'watchlist' for backward
    compat with any caller that omits the kwarg.
    """
    from dataclasses import replace as dc_replace
    vm = build_entry_form_vm(
        ticker=ticker.upper(), cfg=cfg, cache=cache, executor=executor,
        origin=origin,
    )
    if vm is not None:
        vm = dc_replace(
            vm,
            entry_date=entry_date,
            entry_price=entry_price,
            initial_stop=initial_stop,
            input_shares=shares,
            rationale=rationale,
            notes=notes or "",
        )
        return templates.TemplateResponse(
            request, "partials/trade_entry_form.html.j2",
            {"vm": vm, "error_message": error_message},
            status_code=400,
        )
    return templates.TemplateResponse(
        request, "partials/trade_form_error.html.j2",
        {"error_message": error_message},
        status_code=400,
    )


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
    templates = request.app.state.templates
    cfg = apply_overrides(request.app.state.cfg)
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
def entry_form(request: Request, ticker: str, origin: str = "watchlist"):
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates
    vm = build_entry_form_vm(
        ticker=ticker, cfg=cfg, cache=cache, executor=executor,
        origin=origin,
    )
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
    # Phase 5 spec §3.6 — chart-pattern snapshot from hidden form
    # fields populated by build_entry_form_vm at form-render time;
    # operator override + free-text companion field. Each is Optional
    # so existing form submitters (CLI tests; bare cURL) keep working.
    chart_pattern_algo: str | None = Form(None),
    chart_pattern_algo_confidence: float | None = Form(None),
    chart_pattern_classification_pipeline_run_id: int | None = Form(None),
    chart_pattern_operator: str | None = Form(None),
    chart_pattern_operator_other: str | None = Form(None),
    # Task 6 — sector/industry snapshot from hidden form fields populated
    # by build_entry_form_vm at form-render time (snapshot-at-entry-surface
    # ToCToU pattern). Default to "" so existing form submitters (CLI tests;
    # bare cURL) keep working.
    sector: str = Form(""),
    industry: str = Form(""),
    # Phase 4.5 — hypothesis_label snapshot from hidden form field
    # populated by build_entry_form_vm at form-render time (snapshot-
    # at-entry-surface ToCToU pattern). Default "" so existing form
    # submitters (CLI tests; bare cURL) keep working. Empty-string is
    # coerced to None at the EntryRequest construction site below;
    # record_entry's canonicalize_hypothesis_label persists NULL.
    hypothesis_label: str = Form(""),
    # Task 8 (R4-Major-1) — origin discriminator survives POST round-trips.
    # The hidden form field emitted by trade_entry_form.html.j2 carries the
    # value resolved at form-render time. Default 'watchlist' preserves
    # behavior for existing callers (CLI tests / bare cURL) that don't post
    # the field. Whitelist-coerced via _coerce_origin to defend against
    # tampered POSTs (XSS / open-redirect into the rendered Cancel target).
    origin: str = Form("watchlist"),
):
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates

    # Task 8 — coerce once at the request boundary; thread the coerced
    # value through every re-render path so the operator sees a stable
    # layout on each round-trip.
    origin_coerced = _coerce_origin(origin)

    # Tranche B-ops T4: enum-validate the rationale *before* constructing
    # EntryRequest. On failure, re-render the form (preserving user inputs)
    # with an error banner and HTTP 400. Service-layer EntryRequest.rationale
    # stays typed as str per spec §6; validation happens here, not in the
    # dataclass, so CLI callers that already enforce click.Choice aren't
    # double-validated.
    rationale_error = _validate_rationale(rationale, notes, EntryRationale)
    if rationale_error is not None:
        return _rerender_entry_form_with_error(
            request=request, templates=templates, cfg=cfg, cache=cache,
            executor=executor, ticker=ticker, entry_date=entry_date,
            entry_price=entry_price, shares=shares, initial_stop=initial_stop,
            rationale=rationale, notes=notes, error_message=rationale_error,
            origin=origin_coerced,
        )

    # Bug 2 (2026-04-25): validate stop < entry at the request boundary so
    # the form re-renders gracefully (400 + row-shaped fragment) instead of
    # bubbling record_entry's internal ValueError to the generic 500 handler,
    # which returns a bare <div> the HTML parser hoists out of <tbody>,
    # vanishing the form-row. Validating here also keeps the catch tightly
    # typed: we don't risk silently swallowing future, unrelated ValueErrors
    # raised by deeper service/persistence layers as if they were operator
    # input errors.
    #
    # The same invariant is also enforced in record_entry
    # (swing/trades/entry.py). This is intentional defense-in-depth: the
    # service-layer check guards CLI / programmatic callers; this UI-layer
    # check guards the form swap-shape contract. Drift risk: if the
    # service-layer check ever tightens (e.g. requires a minimum stop
    # distance), this copy must be updated to match — otherwise
    # record_entry will raise ValueError from a case the route admits as
    # valid, the row-vanish bug returns, and
    # `test_post_entry_stop_ge_entry_unhandled_value_error_still_500` will
    # NOT catch it (that test guards against re-introducing a blanket
    # ValueError catch, not against this specific drift case).
    if initial_stop >= entry_price:
        return _rerender_entry_form_with_error(
            request=request, templates=templates, cfg=cfg, cache=cache,
            executor=executor, ticker=ticker, entry_date=entry_date,
            entry_price=entry_price, shares=shares, initial_stop=initial_stop,
            rationale=rationale, notes=notes,
            error_message=(
                f"stop must be < entry; got entry={entry_price}, "
                f"stop={initial_stop}"
            ),
            origin=origin_coerced,
        )

    # Phase 5 spec §3.6 — resolve the operator override.
    #   "" (Accept algo)  → None
    #   "other"           → use chart_pattern_operator_other (None if empty)
    #   "flag" / "none"   → pass through verbatim (record_entry canonicalizes)
    if chart_pattern_operator == "other":
        cp_operator_value = chart_pattern_operator_other or None
    else:
        cp_operator_value = chart_pattern_operator or None

    # Empty-string Form values from hidden inputs (e.g. when the form
    # rendered the "Not classified" stub but a CLI replay still posts
    # the field) arrive as "" — coerce to None for the dataclass.
    cp_algo_value = chart_pattern_algo or None
    cp_conf_value = chart_pattern_algo_confidence  # already typed float|None
    cp_anchor_value = chart_pattern_classification_pipeline_run_id

    # Cached-only consumption gate (spec §1.1 #5 + §3.7 R1 C1; symmetric
    # with the CLI's refusal gate in Task 5.5). If the operator submitted
    # an override but no cached snapshot rode along, refuse — out-of-scope
    # ticker has no V1 surface for an override. The form's "Not
    # classified" stub gates the dropdown out of the UI; this is the
    # server-side defense for hand-crafted POSTs and Js-bypass cases.
    cache_evaluated = cp_algo_value is not None and cp_anchor_value is not None
    if cp_operator_value is not None and not cache_evaluated:
        return _rerender_entry_form_with_error(
            request=request, templates=templates, cfg=cfg, cache=cache,
            executor=executor, ticker=ticker, entry_date=entry_date,
            entry_price=entry_price, shares=shares, initial_stop=initial_stop,
            rationale=rationale, notes=notes,
            error_message=(
                "Chart-pattern override requires a cached classification for "
                f"{ticker.upper()}; ticker is out-of-scope for the latest "
                "pipeline run. (V1 cached-only; manual fallback deferred to V2.)"
            ),
            origin=origin_coerced,
        )

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
        # Phase 4.5 — empty-string-to-None coercion at the route boundary.
        # record_entry's canonicalize_hypothesis_label also handles
        # empty/whitespace-only → None, but explicit boundary coercion
        # documents the contract.
        hypothesis_label=hypothesis_label or None,
        chart_pattern_operator=cp_operator_value,
        chart_pattern_algo=cp_algo_value,
        chart_pattern_algo_confidence=cp_conf_value,
        chart_pattern_classification_pipeline_run_id=cp_anchor_value,
        sector=sector,
        industry=industry,
    )

    conn = connect(cfg.paths.db_path)
    try:
        try:
            # Bug-fix-AB: result.trade_id is no longer needed — the
            # dashboard rebuild's open_positions partial picks the new row
            # up via list_open_trades. Soft-warn / duplicate / hard-cap /
            # ValueError paths raise to the except blocks below; the
            # success path returns into the OOB-only response below.
            record_entry(
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
            # Codex R1 Major 2 — soft-warn confirm must preserve the
            # chart_pattern snapshot AS-IS (spec §3.6). Without these 5
            # fields, the force=true resubmit drops the snapshot →
            # persists NULL columns or trips the cached-only gate
            # differently than what the operator saw at first submit.
            # Use the raw incoming form values (not the canonicalized
            # ``cp_*_value`` locals) so the second submit re-runs the
            # exact same canonicalization path as the first — single
            # source of truth.
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
                "chart_pattern_algo": chart_pattern_algo or "",
                "chart_pattern_algo_confidence": (
                    chart_pattern_algo_confidence
                    if chart_pattern_algo_confidence is not None else ""
                ),
                "chart_pattern_classification_pipeline_run_id": (
                    chart_pattern_classification_pipeline_run_id
                    if chart_pattern_classification_pipeline_run_id is not None
                    else ""
                ),
                "chart_pattern_operator": chart_pattern_operator or "",
                "chart_pattern_operator_other": chart_pattern_operator_other or "",
                # Task 6 — sector/industry must round-trip through the
                # soft-warn confirm so the force=true resubmit persists
                # the original snapshot AS-IS. soft_warn_confirm.html.j2
                # iterates form_values with an exclusion list; adding
                # these keys auto-emits hidden inputs.
                "sector": sector,
                "industry": industry,
                # Phase 4.5 — hypothesis_label must round-trip through
                # the soft-warn confirm so the force=true resubmit
                # persists the SAME label the operator saw at first
                # submit. Without this entry, soft_warn_confirm.html.j2
                # would emit no hidden input for the field, the second
                # POST's hypothesis_label would default to "", and the
                # persisted Trade.hypothesis_label would be NULL —
                # silently dropping the snapshot. Multi-path-data-
                # ingestion lesson 2026-04-29.
                "hypothesis_label": hypothesis_label,
                # Task 8 (R4-Major-1) — origin must round-trip through the
                # soft-warn confirm so (a) the force=true resubmit's POST
                # carries origin back; (b) the confirm partial's colspan +
                # Cancel target match the originating surface. The
                # form_values.items() loop in soft_warn_confirm.html.j2
                # auto-emits the hidden <input name="origin"> because
                # 'origin' is not in the banner-only exclusion list.
                "origin": origin_coerced,
                "open_count": actual_open,
                "soft_warn": cfg.position_limits.soft_warn_open,
                "hard_cap": cfg.position_limits.hard_cap_open,
            }
            return templates.TemplateResponse(
                request, "partials/soft_warn_confirm.html.j2",
                {"form_values": form_values},
            )
        except DuplicateOpenPositionException as exc:
            # Spec §5.1 case 1: re-render form with submitted values preserved
            # so the user sees the conflict without losing typed inputs.
            # Task 8 (R4-Major-1): pass ``origin=origin_coerced`` so the
            # re-render's colspan + Cancel target match the originating
            # surface (hyp-recs vs watchlist).
            from dataclasses import replace as dc_replace
            vm = build_entry_form_vm(
                ticker=ticker.upper(), cfg=cfg, cache=cache, executor=executor,
                origin=origin_coerced,
            )
            if vm is not None:
                vm = dc_replace(
                    vm,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    initial_stop=initial_stop,
                    input_shares=shares,      # user's submitted value; suggested_shares stays as server computed
                    rationale=rationale,
                    notes=notes or "",
                )
                return templates.TemplateResponse(
                    request, "partials/trade_entry_form.html.j2",
                    {"vm": vm, "error_message": str(exc)},
                    status_code=400,
                )
            # Fallback (watchlist row gone between GET and POST): use banner-only fragment.
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": str(exc)},
                status_code=400,
            )
        except HardCapException as exc:
            # Hard cap: do NOT re-render the form — re-submitting won't succeed
            # until a position is closed (spec §8 "No UI bypass for hard-cap").
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": str(exc)},
                status_code=400,
            )
        except ValueError as exc:
            # Code-review I1 (plan §Task 5.4 lines 3801-3802) —
            # _validate_chart_pattern_invariant in
            # swing/data/repos/trades.py raises ValueError when a tampered
            # POST passes the cached-only gate but violates the
            # cross-column rule (e.g. algo='flag' + confidence=None +
            # valid run_id). Convert to the standard 400 + re-rendered
            # form pattern so a hand-crafted POST cannot produce a generic
            # 500. Only catch chart_pattern-flagged messages — re-raise
            # any other ValueError from deeper service/persistence layers
            # so we don't silently swallow unrelated failures as if they
            # were operator input errors.
            if "chart_pattern" not in str(exc):
                raise
            return _rerender_entry_form_with_error(
                request=request, templates=templates, cfg=cfg, cache=cache,
                executor=executor, ticker=ticker, entry_date=entry_date,
                entry_price=entry_price, shares=shares,
                initial_stop=initial_stop, rationale=rationale, notes=notes,
                error_message=(
                    f"Chart-pattern fields failed validation: {exc}. Please "
                    "contact a developer if the form was not manually altered."
                ),
                origin=origin_coerced,
            )
        except sqlite3.IntegrityError as exc:
            # Codex R1 Major 1 — tampered hidden-form-field POST that slips
            # past the cross-column ValueError invariant can still trip the
            # schema-level guards at INSERT time:
            #   (a) CHECK constraint on chart_pattern_algo (algo not in the
            #       ('none','flag') enum). The error message includes the
            #       column name verbatim, e.g.:
            #         "CHECK constraint failed: chart_pattern_algo IS NULL
            #          OR chart_pattern_algo IN ('none','flag')"
            #   (b) FOREIGN KEY constraint on
            #       chart_pattern_classification_pipeline_run_id (anchor id
            #       does not point to an existing pipeline_runs row). The
            #       FK error message is GENERIC ("FOREIGN KEY constraint
            #       failed") with no column hint — but the trades table has
            #       exactly one FK column (this one), so an FK failure on
            #       this code path is unambiguous when ``cp_anchor_value``
            #       was non-None.
            # Both cases must surface as the standard 400 + re-rendered
            # form pattern, not a generic 500. Re-raise IntegrityErrors
            # not attributable to chart_pattern (e.g., the partial unique
            # index ux_trades_one_open_per_ticker, already mapped to
            # DuplicateOpenPositionException upstream — but defense in
            # depth).
            msg = str(exc)
            # V1: schema-message-coupled — substring-matches CHECK constraint text; forward hardening = pre-insert FK existence check
            chart_pattern_check = any(col in msg for col in (
                "chart_pattern_algo",
                "chart_pattern_algo_confidence",
                "chart_pattern_classification_pipeline_run_id",
            ))
            chart_pattern_fk = (
                "FOREIGN KEY constraint failed" in msg
                and cp_anchor_value is not None
            )
            if not (chart_pattern_check or chart_pattern_fk):
                raise
            return _rerender_entry_form_with_error(
                request=request, templates=templates, cfg=cfg, cache=cache,
                executor=executor, ticker=ticker, entry_date=entry_date,
                entry_price=entry_price, shares=shares,
                initial_stop=initial_stop, rationale=rationale, notes=notes,
                error_message=(
                    f"Chart-pattern fields failed validation: {exc}. Please "
                    "contact a developer if the form was not manually altered."
                ),
                origin=origin_coerced,
            )
    finally:
        conn.close()

    # Bug-fix-AB (2026-04-29): pure-OOB response architecture.
    #
    # Background. The prior architecture emitted the new open-position
    # `<tr>` as PRIMARY content (no `hx-swap-oob`) plus OOB chunks for
    # `#status-strip`, `#watchlist-top5`, and (on hyp-recs origin)
    # `#hypothesis-recommendations`. Two production-confirmed bugs:
    #
    #   Bug A: the form's `hx-target="closest tr" hx-swap="outerHTML"`
    #     directs HTMX to replace the form's `<tr>` (in the SOURCE tbody —
    #     watchlist or hyp-recs). The new open-position row briefly lands
    #     in that source tbody, then OOB rebuilds nuke it. Nothing in the
    #     response targets `#open-positions`, so the open-positions table
    #     never updates without a hard refresh.
    #
    #   Bug B: a leading `<tr>` in the response triggers HTMX's
    #     `makeFragment` to wrap the whole response in a synthetic
    #     `<table><tbody>` for parsing. HTML5 nested-table parse rules
    #     then DROP the `<table>`s inside the OOB `<section>` chunks
    #     during the browser-side fragment parse. Operator's DevTools
    #     capture (2026-04-29) confirmed `htmx:oobAfterSwap` fires for
    #     `#watchlist-top5` but the post-swap DOM contains only the `<h2>`
    #     heading — the `<table>` and rows vanished at parse time.
    #
    # Fix. Make the response purely OOB: NO `<tr>` at fragment root.
    # The new row reaches `#open-positions` via an OOB swap that mirrors
    # `partials/prices_refresh_container.html.j2`'s pattern. Primary swap
    # content is empty; HTMX's `makeFragment` does not wrap-in-`<table>`;
    # foster-parenting/nested-table-stripping does not fire; OOB chunks
    # parse and apply cleanly. The form's `<tr>` (in the source tbody)
    # disappears as a side-effect of the watchlist-top5 / hyp-recs OOB
    # rebuild that replaces its containing section.
    dashboard_vm = build_dashboard(cfg=cfg, cache=cache, executor=executor,
                                   ohlcv_cache=request.app.state.ohlcv_cache)

    status_strip_html = templates.get_template("partials/status_strip.html.j2").render(
        request=request, vm=dashboard_vm,
    )
    open_positions_html = templates.get_template(
        "partials/open_positions.html.j2"
    ).render(request=request, vm=dashboard_vm)
    watchlist_section_html = templates.get_template(
        "partials/watchlist_top5_section.html.j2"
    ).render(request=request, vm=dashboard_vm)

    # Emit the `#hypothesis-recommendations` OOB rebuild on EVERY origin
    # (R1 Codex review of the pure-OOB architecture, 2026-04-29). The
    # prior gating on `origin_coerced == "hyp-recs"` was unsound: the
    # SAME ticker can plausibly appear on the watchlist AND in hyp-recs
    # simultaneously (both surfaces source from candidates + watchlist
    # under the latest eval). A watchlist-origin entry that traded such
    # a ticker would update open-positions + watchlist correctly but
    # leave the hyp-recs panel STALE — the just-traded ticker would
    # remain visible in the recommendations table on the dashboard until
    # the next interaction. Always-rebuild ensures cross-section
    # consistency on every successful entry.
    #
    # Render the OOB chunk from `dashboard_vm` directly (R2 Codex review
    # 2026-04-29 Major 1). `build_dashboard` already ran (line above) AND
    # already applies the Bug-fix-C exclude-open-positions filter to its
    # inline hyp-recs construction, so `dashboard_vm.active_recommendations`
    # is the correct post-write hyp-recs state. Reusing it (instead of a
    # second `build_hyp_recs_section(...)` call) avoids a redundant DB
    # snapshot + matcher run + price fetch AFTER `record_entry` has
    # already committed — narrowing the post-write failure surface so a
    # transient downstream error cannot flip a successful entry into a
    # 500 response. Single source of truth for the hyp-recs panel state
    # within this request.
    #
    # The partial is the SOLE source of the section markup (CLAUDE.md
    # "HTMX OOB-swap partial drift" gotcha) — render it via
    # `.render(..., oob=True)`. The `oob=True` branch ALWAYS emits the
    # `#hypothesis-recommendations` element (with `hx-swap-oob="true"`),
    # even when the rebuild surfaces zero recommendations, so HTMX always
    # has a valid swap target on the dashboard. On pages that don't
    # carry the target id (e.g., standalone /watchlist), HTMX silently
    # skips the OOB swap — emitting the chunk is harmless there.
    #
    # `vm=dashboard_vm` works because the partial reads only
    # `vm.active_recommendations` — the same field name on both
    # `DashboardVM` and `HypRecsSectionVM`. Duck-typed VM contract
    # (CLAUDE.md base-layout VM rule applies only when base.html.j2
    # dereferences the field; here it's the per-section partial that
    # consumes the field, with the same shape on both VM types).
    hyp_recs_section_html = templates.get_template(
        "partials/hypothesis_recommendations.html.j2"
    ).render(request=request, vm=dashboard_vm, oob=True)

    return HTMLResponse(Markup(
        f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
        f'<div id="open-positions" hx-swap-oob="true">'
        f'{open_positions_html}'
        f'</div>'
        f'<section id="watchlist-top5" hx-swap-oob="true">'
        f'{watchlist_section_html}'
        f'</section>'
        f'{hyp_recs_section_html}'
    ))


@router.get("/trades/{trade_id}/exit/form", response_class=HTMLResponse)
def exit_form(request: Request, trade_id: int):
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates
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
    notes: str | None = Form(None),
):
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates

    # Validate reason.
    try:
        reason_enum = ExitReason(reason)
    except ValueError:
        return templates.TemplateResponse(
            request, "partials/trade_form_error.html.j2",
            {"error_message": f"Invalid reason: {reason}"},
            status_code=400,
        )

    # Tranche B-ops T6: rationale is no longer a separate form input.
    # The service still persists trade_events.rationale; derive it from
    # reason_enum.value per spec §3 "Decision — exit rationale: reuse
    # ExitReason." Accepted semantic cost: values like 'partial' and
    # 'manual' appear as rationale rows (spec §3 "Known limitation").
    req = ExitRequest(
        trade_id=trade_id, exit_date=exit_date, exit_price=exit_price,
        shares=shares, reason=reason_enum, notes=notes,
        rationale=reason_enum.value,
        event_ts=datetime.now().isoformat(timespec="seconds"),
    )

    conn = connect(cfg.paths.db_path)
    try:
        try:
            result = record_exit(conn, req)
        except ValueError as exc:
            # R: spec §5.1 case 2 — re-render form with authoritative remaining shares.
            vm = build_exit_form_vm(trade_id=trade_id, cfg=cfg, cache=cache, executor=executor)
            if vm is not None:
                return templates.TemplateResponse(
                    request, "partials/trade_exit_form.html.j2",
                    {"vm": vm, "error_message": str(exc)},
                    status_code=400,
                )
            # Fallback: trade closed/gone — use banner-only fragment.
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": str(exc)},
                status_code=400,
            )
    finally:
        conn.close()

    # Two-call rebuild.
    dashboard_vm = build_dashboard(cfg=cfg, cache=cache, executor=executor,
                                   ohlcv_cache=request.app.state.ohlcv_cache)
    status_strip_html = templates.get_template("partials/status_strip.html.j2").render(
        request=request, vm=dashboard_vm,
    )

    if result.fully_closed:
        # Primary target: empty/hidden stub so the row disappears.
        soft_warn_html = templates.get_template(
            "partials/review_soft_warn_close.html.j2"
        ).render(request=request, trade_id=trade_id)
        return HTMLResponse(Markup(
            f'<tr id="open-position-{trade_id}" style="display:none"></tr>'
            f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
            f'<div id="trade-close-soft-warn" hx-swap-oob="true">{soft_warn_html}</div>'
        ))

    # Partial: re-render the row.
    conn2 = connect(cfg.paths.db_path)
    try:
        updated = get_trade(conn2, trade_id)
    finally:
        conn2.close()
    row_vm = build_open_positions_row(
        trade=updated, cfg=cfg, cache=cache,
        ohlcv_cache=request.app.state.ohlcv_cache, executor=executor,
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
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    vm = build_stop_form_vm(trade_id=trade_id, cfg=cfg)
    if vm is None:
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found or not open")
    return templates.TemplateResponse(
        request, "partials/trade_stop_form.html.j2", {"vm": vm},
    )


@router.get("/trades/{trade_id}/cancel", response_class=HTMLResponse)
def trade_cancel(request: Request, trade_id: int):
    """Return the normal open-position row (no form). Used by Cancel buttons."""
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates

    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
    finally:
        conn.close()
    if trade is None or trade.status != "open":
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found or not open")

    row_vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache,
        ohlcv_cache=request.app.state.ohlcv_cache, executor=executor,
    )
    # Single-contract partial: pass only `row` (R1 Major 3 fix).
    return templates.TemplateResponse(
        request, "partials/open_positions_row.html.j2", {"row": row_vm},
    )


@router.post("/trades/{trade_id}/stop", response_class=HTMLResponse)
def stop_post(
    request: Request, trade_id: int,
    new_stop: float = Form(...), rationale: str = Form(...),
    notes: str | None = Form(None),
    force: str | None = Form(None),
):
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates

    # Collapse blank textarea submissions to NULL (matches entry/exit form
    # convention — `trades.notes`/`exits.notes` store NULL, not "", when the
    # operator leaves the box empty).
    notes_value = notes.strip() if notes and notes.strip() else None
    # Tranche B-ops T7: Force is an opt-in checkbox; the HTML submits
    # "true" only when ticked. Everything else (absent, empty, anything
    # unexpected) is False by construction.
    force_flag = force == "true"

    # Tranche B-ops T5: enum-validate the rationale before constructing the
    # service request. On failure, re-render the stop form with an error
    # banner at HTTP 400. T7 layers field preservation across this re-render.
    rationale_error = _validate_rationale(rationale, notes, StopAdjustRationale)
    if rationale_error is not None:
        return _rerender_stop_form_with_error(
            request=request, templates=templates, cfg=cfg,
            trade_id=trade_id, new_stop=new_stop, rationale=rationale,
            notes=notes,
            error_message=rationale_error,
        )

    req = StopAdjustRequest(
        trade_id=trade_id, new_stop=new_stop, rationale=rationale,
        notes=notes_value,
        event_ts=datetime.now().isoformat(timespec="seconds"),
        force=force_flag,
    )
    conn = connect(cfg.paths.db_path)
    try:
        # Guard: trade must exist and be open before attempting stop adjust.
        # adjust_stop only raises ValueError for not-found, not for closed.
        trade_check = get_trade(conn, trade_id)
        if trade_check is None or trade_check.status != "open":
            raise HTTPException(
                status_code=404,
                detail=f"Trade #{trade_id} not found or not open",
            )
        try:
            adjust_stop(conn, req)
        except ValueError as exc:
            # Trade not found or already closed — surface as 404 so the
            # HTMX-aware handler renders trade_form_error.html.j2 (§5.2).
            raise HTTPException(status_code=404, detail=str(exc))
        except StopRegressionError as exc:
            # R: spec §5.1 case 3 — re-render form with updated current_stop.
            # T7: preservation fields populated from the submitted form
            # (force is intentionally NOT preserved — spec §5).
            error_message = (
                f"{exc}. Tick Force to submit intentionally, or adjust new_stop."
            )
            return _rerender_stop_form_with_error(
                request=request, templates=templates, cfg=cfg,
                trade_id=trade_id, new_stop=new_stop, rationale=rationale,
                notes=notes,
                error_message=error_message,
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
        trade=updated, cfg=cfg, cache=cache,
        ohlcv_cache=request.app.state.ohlcv_cache, executor=executor,
    )
    row_html = templates.get_template("partials/open_positions_row.html.j2").render(
        request=request, row=row_vm,
    )
    return HTMLResponse(Markup(row_html))


# Tier-2 #3 — open-positions row click-to-expand (chart-display fragment).
# trade_id is the route key (more unambiguous than ticker — defends against
# the closed/reopened-position edge case where two trades exist for the
# same ticker).


@router.get("/trades/open/{trade_id}/expand", response_class=HTMLResponse)
def open_position_expand(request: Request, trade_id: int):
    """Render the open-positions expanded fragment for `trade_id`. 404 when
    the trade does not exist OR is not currently open (closed trades must
    not display the open-positions UI)."""
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            expanded = build_open_positions_expanded(
                conn=conn, cfg=cfg, trade_id=trade_id,
            )
    finally:
        conn.close()
    if expanded is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trade #{trade_id} not found or not open",
        )
    return templates.TemplateResponse(
        request, "partials/open_positions_expanded.html.j2",
        {"expanded": expanded},
    )


@router.get("/trades/{trade_id}/review", response_class=HTMLResponse)
def review_form_page(request: Request, trade_id: int):
    """Phase 6: post-trade review form page."""
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    from swing.web.view_models.trades import build_review_vm
    vm = build_review_vm(trade_id=trade_id, cfg=cfg)
    if vm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trade #{trade_id} not found, not closed, or already reviewed",
        )
    return templates.TemplateResponse(
        request, "review.html.j2", {"vm": vm},
    )


@router.post("/trades/{trade_id}/review")
def review_post(
    request: Request, trade_id: int,
    entry_grade: str = Form(...),
    management_grade: str = Form(...),
    exit_grade: str = Form(...),
    lesson_learned: str = Form(...),
    disqualifying_process_violation: str | None = Form(None),
    realized_R_if_plan_followed: float | None = Form(None),
    mistake_cost_confidence: str = Form(""),
    mistake_tags: list[str] = Form(default=[]),
):
    """Phase 6: persist a post-trade review.

    Success: 204 + HX-Redirect: /trades (browser re-navigates via htmx.js;
    NOT a 303 swap — Phase 5 lesson, brief §6.2 watch item 6).
    """
    import json
    from datetime import datetime as _dt
    from fastapi.responses import Response
    from swing.data.db import connect
    from swing.data.repos.trades import (
        get_trade, update_trade_review_fields,
    )
    from swing.trades.review import (
        canonicalize_mistake_tags, compute_process_grade,
        validate_mistake_tags,
    )

    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates

    disq = (disqualifying_process_violation or "").lower() == "true"

    canonical_tags = canonicalize_mistake_tags(list(mistake_tags))
    try:
        validate_mistake_tags(canonical_tags)
    except ValueError as exc:
        from swing.web.view_models.trades import build_review_vm
        vm = build_review_vm(trade_id=trade_id, cfg=cfg)
        if vm is None:
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": str(exc)},
                status_code=400,
            )
        return templates.TemplateResponse(
            request, "partials/review_form.html.j2",
            {"vm": vm, "error_message": str(exc)},
            status_code=400,
        )

    try:
        process_grade = compute_process_grade(
            entry=entry_grade, management=management_grade, exit_=exit_grade,
            disqualifying=disq,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "partials/trade_form_error.html.j2",
            {"error_message": str(exc)},
            status_code=400,
        )

    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
        if trade is None or trade.status != "closed":
            raise HTTPException(status_code=404)
        if trade.reviewed_at is not None:
            raise HTTPException(
                status_code=409,
                detail="Trade already reviewed; V1 supports single-review only",
            )
        with conn:
            update_trade_review_fields(
                conn, trade_id=trade_id,
                reviewed_at=_dt.now().isoformat(timespec="seconds"),
                mistake_tags_json=json.dumps(canonical_tags),
                entry_grade=entry_grade,
                management_grade=management_grade,
                exit_grade=exit_grade,
                process_grade=process_grade,
                disqualifying_process_violation=disq,
                realized_R_if_plan_followed=realized_R_if_plan_followed,
                mistake_cost_confidence=mistake_cost_confidence or None,
                lesson_learned=lesson_learned,
            )
    finally:
        conn.close()
    return Response(status_code=204, headers={"HX-Redirect": "/trades"})


@router.get("/reviews/{review_id}/complete", response_class=HTMLResponse)
def cadence_complete_form(request: Request, review_id: int):
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    from swing.web.view_models.trades import build_cadence_complete_vm
    vm = build_cadence_complete_vm(review_id=review_id, cfg=cfg)
    if vm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Review #{review_id} not found or already completed",
        )
    return templates.TemplateResponse(
        request, "cadence_complete.html.j2", {"vm": vm},
    )


@router.post("/reviews/{review_id}/complete")
def cadence_complete_post(
    request: Request, review_id: int,
    duration_minutes: int = Form(...),
    primary_lesson: str = Form(...),
    next_period_focus: str = Form(...),
):
    from datetime import date as _date
    from fastapi.responses import Response
    from swing.data.repos.review_log import complete_review_atomic, get
    cfg = apply_overrides(request.app.state.cfg)
    conn = connect(cfg.paths.db_path)
    try:
        review = get(conn, review_id)
        if review is None:
            raise HTTPException(status_code=404)
        if review.completed_date is not None:
            raise HTTPException(
                status_code=409,
                detail="Review already completed",
            )
        complete_review_atomic(
            conn, review_id=review_id,
            completed_date=_date.today().isoformat(),
            duration_minutes=duration_minutes,
            primary_lesson=primary_lesson,
            next_period_focus=next_period_focus,
        )
    finally:
        conn.close()
    # 204 + HX-Redirect to dashboard so cadence card flips to "completed":
    return Response(status_code=204, headers={"HX-Redirect": "/"})


@router.get("/trades/open/{trade_id}/row", response_class=HTMLResponse)
def open_position_row(request: Request, trade_id: int):
    """Return the compact open-positions row partial for `trade_id`. Used by
    the close button on an expanded row to swap back to the compact state
    without a full page reload. Mirrors /watchlist/<ticker>/row contract:
    404 on unknown/closed trade, 200 + <tr> body on success."""
    cfg = apply_overrides(request.app.state.cfg)
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates

    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
    finally:
        conn.close()
    if trade is None or trade.status != "open":
        raise HTTPException(
            status_code=404,
            detail=f"Trade #{trade_id} not found or not open",
        )

    row_vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache,
        ohlcv_cache=request.app.state.ohlcv_cache, executor=executor,
    )
    return templates.TemplateResponse(
        request, "partials/open_positions_row.html.j2", {"row": row_vm},
    )
