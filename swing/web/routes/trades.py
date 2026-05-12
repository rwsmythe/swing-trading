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
from swing.data.repos.trades import get_trade, list_open_trades
from swing.recommendations.sizing import SizingResult, compute_shares
from swing.trades.entry import (
    DuplicateOpenPositionError,
    EntryRationale,
    EntryRequest,
    HardCapError,
    MissingPreTradeFieldsException,
    SoftWarnError,
    record_entry,
)
from swing.trades.equity import current_equity
from swing.trades.exit import ExitReason, ExitRequest, record_exit
from swing.trades.origin import EntryPath
from swing.trades.stop_adjust import (
    StopAdjustRationale,
    StopAdjustRequest,
    StopRegressionError,
    adjust_stop,
)
from swing.web.view_models.dashboard import build_dashboard
from swing.web.view_models.open_positions_row import (
    build_open_positions_expanded,
    build_open_positions_row,
)
from swing.web.view_models.trades import (
    _coerce_origin,
    build_entry_form_vm,
    build_exit_form_vm,
    build_stop_form_vm,
    build_trade_detail_vm,
)

log = logging.getLogger(__name__)
router = APIRouter()

# Phase 7 Sub-C C.7 — active-trade lifecycle states (entered/managing/
# partial_exited). Used by route-level preconditions for write/management
# endpoints (exit_post, stop_post, cancel, open_position_row). Mirrors
# `_ACTIVE_STATES_SQL` in repos/trades.py and the same-named tuples in
# swing/web/view_models/trades.py + open_positions_row.py.
_ACTIVE_STATES = ("entered", "managing", "partial_exited")


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


def _emit_sector_tamper_audit(
    *,
    cfg,
    ticker: str,
    cached_sector: str,
    cached_industry: str,
    form_sector: str,
    form_industry: str,
    cand_session_iso: str,
    run_session_iso: str,
    field_name: str,
) -> int:
    """Phase 9 Sub-bundle D Task D.2 — emit ad-hoc system_audit
    reconciliation_run + sector_tamper discrepancy on tamper rejection.

    Owns its own connection + ``with conn:`` deferred transaction
    (plan §A.4.1: SEPARATE TRANSACTION from any entry-POST tx — entry
    POST is rejected and never commits its own tx). Uses Bundle B's repo
    entry points (``insert_run`` + ``insert_discrepancy`` +
    ``update_run_completed``) directly per plan §A.4 + Sub-bundle B
    return report §10 #1 — does NOT route through Bundle B's
    ``run_tos_reconciliation`` service (which is ``source='tos_csv'``
    only).

    Returns the inserted ``discrepancy_id`` for test plumbing.

    Spec §3.3.1 ``sector_tamper`` JSON shapes:
      expected = {"sector": cached_sector, "industry": cached_industry,
                  "session": cand_session_iso}     # cached candidate anchor
      actual   = {"sector": form_sector, "industry": form_industry}

    Plan §A.4.1: reconciliation_run row's ``period_{start,end}`` =
    ``run_session_iso`` (today's ``action_session_for_run(now())``) —
    describes WHEN the audit happened. Distinct from
    ``cand_session_iso`` which is the cached candidate's
    ``eval_run.action_session_date`` (i.e., the session anchor for the
    data the operator saw at form-render time). The two MAY differ when
    the form was rendered before today's pipeline run completed (Codex
    R1 Major #1 anchor-alignment fix).

    ``MATERIAL_BY_TYPE['sector_tamper'] = 0`` per spec §3.3.2 V1
    advisory; V2 elevates when sector-concentration becomes a hard
    gate. The lookup is authoritative per Bundle B Codex R1 M#2 —
    DO NOT hand-set inline.
    """
    import json as _json

    from swing.data.datetime_helpers import now_ms
    from swing.data.repos.reconciliation import (
        insert_discrepancy,
        insert_run,
        update_run_completed,
    )
    from swing.trades.reconciliation import MATERIAL_BY_TYPE

    expected_value_json = _json.dumps(
        {
            "sector": cached_sector,
            "industry": cached_industry,
            "session": cand_session_iso,
        },
        separators=(",", ":"),
    )
    actual_value_json = _json.dumps(
        {"sector": form_sector, "industry": form_industry},
        separators=(",", ":"),
    )
    started_ts = now_ms()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id = insert_run(
                conn,
                source="system_audit",
                started_ts=started_ts,
                state="running",
                period_start=run_session_iso,
                period_end=run_session_iso,
            )
            disc_id = insert_discrepancy(
                conn,
                run_id=run_id,
                discrepancy_type="sector_tamper",
                field_name=field_name,
                material_to_review=MATERIAL_BY_TYPE["sector_tamper"],
                created_at=started_ts,
                ticker=ticker,
                expected_value_json=expected_value_json,
                actual_value_json=actual_value_json,
            )
            update_run_completed(
                conn,
                run_id=run_id,
                finished_ts=now_ms(),
                discrepancies_count=1,
                unresolved_discrepancies_count=1,
            )
    finally:
        conn.close()
    return disc_id


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
        # C.10: routed through the view-model adapter so equity computation
        # consumes non-entry fills via the shared _ExitShape pattern.
        from swing.web.view_models.trades import (
            _list_all_exitshape_via_fills,
        )

        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                exits = _list_all_exitshape_via_fills(conn)
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
    # Phase 7 Sub-C C.3 — 18 pre-trade required fields (spec §1, §3.5.1).
    # All `Form(None)` so legacy callers (existing tests, bare cURL) keep
    # working until C.4 wires the operator-facing fieldset; the
    # MissingPreTradeFieldsException catch path below re-renders a
    # banner-only error fragment when any required field is missing.
    # Nullable+CHECK columns persist via `... or None` (per CLAUDE.md
    # gotcha 2026-05-04 — empty string would fail the CHECK enum).
    thesis: str | None = Form(None),
    why_now: str | None = Form(None),
    invalidation_condition: str | None = Form(None),
    expected_scenario: str | None = Form(None),
    premortem_technical: str | None = Form(None),
    premortem_market_sector: str | None = Form(None),
    premortem_execution: str | None = Form(None),
    premortem_additional: str | None = Form(None),
    event_risk_present: int | None = Form(None),
    event_handling: str | None = Form(None),
    event_type: str | None = Form(None),
    event_date: str | None = Form(None),
    gap_risk_present: int | None = Form(None),
    gap_risk_handling: str | None = Form(None),
    # Multi-select: HTML `<select multiple name="emotional_state_pre_trade">`
    # posts repeated keys; FastAPI binds these to a list. JSON-encoded at
    # the EntryRequest construction site (matches CLI's
    # `_json.dumps(list(emotional_state))` pattern in swing/cli.py).
    emotional_state_pre_trade: list[str] | None = Form(None),  # noqa: B008
    market_regime: str | None = Form(None),
    catalyst: str | None = Form(None),
    catalyst_other_description: str | None = Form(None),
    manual_entry_confidence: str | None = Form(None),
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

    # Codex R1 Major 1 (Phase 7 Sub-C) — schema-layer guards that used to
    # fire at INSERT time were lost when migration 0014 rebuilt the trades
    # table without the chart_pattern_algo CHECK enum and without enforcing
    # the FK on chart_pattern_classification_pipeline_run_id. Restore them
    # at the route boundary so a tampered hidden-form POST renders the
    # standard 400 + banner instead of either silently persisting a bogus
    # value or bubbling a generic 500. (Repo-layer
    # _validate_chart_pattern_invariant only checks NULL/cross-column
    # shape; it doesn't enforce enum values or FK existence — and Sub-A
    # owns that file, so app-layer guards live here.)
    if cp_algo_value is not None and cp_algo_value not in ("flag", "none"):
        return _rerender_entry_form_with_error(
            request=request, templates=templates, cfg=cfg, cache=cache,
            executor=executor, ticker=ticker, entry_date=entry_date,
            entry_price=entry_price, shares=shares, initial_stop=initial_stop,
            rationale=rationale, notes=notes,
            error_message=(
                f"chart_pattern_algo must be one of 'flag' or 'none'; "
                f"got {cp_algo_value!r}."
            ),
            origin=origin_coerced,
        )
    if cp_anchor_value is not None:
        from swing.data.repos.pattern_classifications import get_classification
        _conn = connect(cfg.paths.db_path)
        try:
            _row = _conn.execute(
                "SELECT 1 FROM pipeline_runs WHERE id = ?",
                (cp_anchor_value,),
            ).fetchone()
            # Codex R2 Major 1 — restore the cached-only contract for
            # tampered POSTs. The FK + enum checks reject obvious tampering
            # (bogus run_id, algo not in enum). This adds the missing
            # snapshot-vs-cache match check: the submitted (run_id, ticker)
            # tuple MUST correspond to a cached classification, otherwise
            # the snapshot is forged. We deliberately do NOT also assert
            # cls.pattern == cp_algo_value or cls.confidence == cp_conf_value
            # — spec §3.6 R2 M3 requires snapshot values flow AS-IS, and a
            # legit "cache changed during form fill" path would false-reject
            # under stricter equality checks.
            _cls_row = (
                get_classification(
                    _conn,
                    pipeline_run_id=cp_anchor_value,
                    ticker=ticker.upper(),
                )
                if _row is not None
                else None
            )
        finally:
            _conn.close()
        if _row is None:
            return _rerender_entry_form_with_error(
                request=request, templates=templates, cfg=cfg, cache=cache,
                executor=executor, ticker=ticker, entry_date=entry_date,
                entry_price=entry_price, shares=shares,
                initial_stop=initial_stop,
                rationale=rationale, notes=notes,
                error_message=(
                    "chart_pattern_classification_pipeline_run_id "
                    f"{cp_anchor_value} does not reference an existing "
                    "pipeline_runs row."
                ),
                origin=origin_coerced,
            )
        if _cls_row is None:
            return _rerender_entry_form_with_error(
                request=request, templates=templates, cfg=cfg, cache=cache,
                executor=executor, ticker=ticker, entry_date=entry_date,
                entry_price=entry_price, shares=shares,
                initial_stop=initial_stop,
                rationale=rationale, notes=notes,
                error_message=(
                    f"chart_pattern snapshot rejected: no cached "
                    f"classification exists for {ticker.upper()} under "
                    f"pipeline_runs.id={cp_anchor_value}"
                ),
                origin=origin_coerced,
            )

    # Phase 9 Sub-bundle D Task D.1 + D.2 — sector/industry tamper
    # hardening (mirrors chart_pattern hardening pattern; recon at
    # docs/phase9-bundle-D-task-D0-recon.md).
    #
    # Codex R1 fix (Critical #1 + Major #1):
    # - Critical: predicate previously required BOTH cached AND form value
    #   truthy to flag a mismatch; a tampered POST with blank sector
    #   (e.g., sector="" + industry=correct, or sector="" alone) silently
    #   bypassed the check. Tightened to strict ``cached != form`` for
    #   each field — empty form value when cached has a value IS a tamper.
    # - Major: form-render anchors hidden sector/industry to
    #   ``latest_evaluation_run_id`` (watchlist) or
    #   ``latest_completed_pipeline_run.evaluation_run_id`` (hyp-recs)
    #   per swing/web/view_models/trades.py:379-396 — NOT today's
    #   action_session. Drift between the two anchors (stale pipeline,
    #   pre-session pipeline run, mid-walk DB) lets a tamper attempt
    #   slip past the today-anchored POST-time lookup. Re-anchor POST
    #   lookup to mirror the SAME anchor the form-render used so form +
    #   POST agree on the cached row being compared against.
    #
    # Backward-compat: empty form sector AND industry (CLI / bare cURL
    # callers that don't emit the hidden inputs) → skip the check entirely.
    # Off-pipeline ticker (no cached row under the form-render anchor) →
    # skip the check (mirrors chart_pattern's ``cp_anchor_value is None``
    # early-out).
    if sector or industry:
        from swing.evaluation.dates import action_session_for_run
        from swing.web.view_models.dashboard import (
            latest_completed_pipeline_run,
            latest_evaluation_run_id,
        )
        # Today's action session — used for the reconciliation_run's
        # period_{start,end} (audit-run timeframe, per plan §A.4.1).
        today_session_iso = (
            action_session_for_run(datetime.now()).isoformat()
        )
        _conn = connect(cfg.paths.db_path)
        try:
            # Mirror form-render anchor selection at
            # swing/web/view_models/trades.py:379-385. Form + POST MUST
            # use the same anchor — Codex R1 Major #1.
            if origin_coerced == "hyp-recs":
                _binding = latest_completed_pipeline_run(_conn)
                _eval_id = (
                    _binding.evaluation_run_id if _binding else None
                )
            else:
                _eval_id = latest_evaluation_run_id(_conn)
            if _eval_id is not None:
                _cand_row = _conn.execute(
                    "SELECT c.sector, c.industry, "
                    "e.action_session_date "
                    "FROM candidates c "
                    "JOIN evaluation_runs e "
                    "ON c.evaluation_run_id = e.id "
                    "WHERE c.evaluation_run_id = ? AND c.ticker = ? "
                    "LIMIT 1",
                    (_eval_id, ticker.upper()),
                ).fetchone()
            else:
                _cand_row = None
        finally:
            _conn.close()
        if _cand_row is not None:
            cached_sector = _cand_row[0] or ""
            cached_industry = _cand_row[1] or ""
            # Spec §3.3.1 ``session`` is the cached candidate's anchor —
            # carry the eval_run's action_session_date verbatim (matches
            # form-render's anchor and the data the operator saw).
            cand_session_iso = _cand_row[2] or today_session_iso
            mismatch_field: str | None = None
            # Codex R1 Critical #1: strict ``!=`` comparison — empty
            # form value against non-empty cached IS a tamper (blank-
            # field bypass closed).
            if cached_sector != sector:
                mismatch_field = "sector"
            elif cached_industry != industry:
                mismatch_field = "industry"
            if mismatch_field is not None:
                # T-D.2 — emit ad-hoc system_audit reconciliation_run +
                # sector_tamper discrepancy in a SEPARATE TRANSACTION
                # (plan §A.4.1). The audit must persist regardless of
                # what happens to the rejected entry POST — record_entry
                # is never invoked on this path, so no entry-tx is open
                # to interleave with the audit-tx.
                #
                # cand_session_iso: spec §3.3.1 ``expected.session`` —
                # the cached candidate's anchor (eval_run's
                # action_session_date), matching the data the operator
                # saw at form-render time.
                # today_session_iso: plan §A.4.1 — the
                # reconciliation_run row's ``period_{start,end}``
                # describing WHEN the audit happened (today).
                _emit_sector_tamper_audit(
                    cfg=cfg,
                    ticker=ticker.upper(),
                    cached_sector=cached_sector,
                    cached_industry=cached_industry,
                    form_sector=sector,
                    form_industry=industry,
                    cand_session_iso=cand_session_iso,
                    run_session_iso=today_session_iso,
                    field_name=mismatch_field,
                )
                return _rerender_entry_form_with_error(
                    request=request, templates=templates, cfg=cfg,
                    cache=cache, executor=executor,
                    ticker=ticker, entry_date=entry_date,
                    entry_price=entry_price, shares=shares,
                    initial_stop=initial_stop,
                    rationale=rationale, notes=notes,
                    error_message=(
                        f"Trade entry rejected: {mismatch_field} "
                        f"mismatch for {ticker.upper()}. Cached "
                        f"sector={cached_sector!r} industry="
                        f"{cached_industry!r}; form submitted "
                        f"sector={sector!r} industry={industry!r}. "
                        f"Re-render the form or update the pipeline "
                        f"candidate; audit row recorded for review."
                    ),
                    origin=origin_coerced,
                )

    # Phase 7 Sub-C C.3 — emotional_state_pre_trade JSON-encoding.
    # Matches CLI's `_json.dumps(list(emotional_state))` (swing/cli.py).
    # Empty list / None → None so the validator's required-field check
    # fires (NULL is treated as missing). Drops empty strings so a
    # bare-cURL POST submitting "emotional_state_pre_trade=" doesn't
    # encode `[""]` and dodge the gate.
    import json as _json
    emo_clean = [
        s for s in (emotional_state_pre_trade or []) if s and s.strip()
    ]
    emo_json: str | None = _json.dumps(emo_clean) if emo_clean else None

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
        # Phase 7 Sub-C C.3 — 18 pre-trade required fields.
        # ``or None`` coerces empty form strings to NULL so nullable+CHECK
        # columns don't trip CHECK constraint failures at INSERT time
        # (CLAUDE.md gotcha 2026-05-04 — Phase 6 mistake_cost_confidence).
        # Web entries always come from the manual entry form.
        entry_path=EntryPath.MANUAL_WEB_FORM,
        thesis=thesis or None,
        why_now=why_now or None,
        invalidation_condition=invalidation_condition or None,
        expected_scenario=expected_scenario or None,
        premortem_technical=premortem_technical or None,
        premortem_market_sector=premortem_market_sector or None,
        premortem_execution=premortem_execution or None,
        premortem_additional=premortem_additional or None,
        event_risk_present=event_risk_present,
        event_handling=event_handling or None,
        event_type=event_type or None,
        event_date=event_date or None,
        gap_risk_present=gap_risk_present,
        gap_risk_handling=gap_risk_handling or None,
        emotional_state_pre_trade=emo_json,
        market_regime=market_regime or None,
        catalyst=catalyst or None,
        catalyst_other_description=catalyst_other_description or None,
        manual_entry_confidence=manual_entry_confidence or None,
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
        except MissingPreTradeFieldsException as exc:
            # Phase 7 Sub-C C.4 — non-bypassable pre-trade required-field
            # gate (spec §9.3). Re-render the FULL entry form fragment
            # so the operator sees:
            #   1. an inline banner naming the missing fields,
            #   2. per-field error class markers on the missing inputs
            #      (template gates on `{% if name in vm.missing_fields %}`),
            #   3. their typed values round-tripped via the `draft_*`
            #      preservation fields (rationale/notes pattern extended
            #      to the 18 new pre-trade fields).
            # On `vm is None` (watchlist row vanished between GET and POST),
            # fall through to the banner-only error fragment — there's no
            # form context to re-render against.
            from dataclasses import replace as dc_replace
            vm = build_entry_form_vm(
                ticker=ticker.upper(), cfg=cfg, cache=cache,
                executor=executor, origin=origin_coerced,
            )
            error_message = (
                "Missing required pre-trade fields: "
                + ", ".join(exc.missing_fields)
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
                    # 18 pre-trade field draft preservation:
                    draft_thesis=thesis or "",
                    draft_why_now=why_now or "",
                    draft_invalidation_condition=invalidation_condition or "",
                    draft_expected_scenario=expected_scenario or "",
                    draft_premortem_technical=premortem_technical or "",
                    draft_premortem_market_sector=premortem_market_sector or "",
                    draft_premortem_execution=premortem_execution or "",
                    draft_premortem_additional=premortem_additional or "",
                    draft_event_risk_present=event_risk_present,
                    draft_event_handling=event_handling or "",
                    draft_event_type=event_type or "",
                    draft_event_date=event_date or "",
                    draft_gap_risk_present=gap_risk_present,
                    draft_gap_risk_handling=gap_risk_handling or "",
                    draft_emotional_state_pre_trade=tuple(emo_clean),
                    draft_manual_entry_confidence=manual_entry_confidence or "",
                    draft_market_regime=market_regime or "",
                    draft_catalyst=catalyst or "",
                    draft_catalyst_other_description=(
                        catalyst_other_description or ""
                    ),
                    missing_fields=frozenset(exc.missing_fields),
                )
                return templates.TemplateResponse(
                    request, "partials/trade_entry_form.html.j2",
                    {"vm": vm, "error_message": error_message},
                    status_code=400,
                )
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {
                    "error_message": error_message,
                    "missing_fields": list(exc.missing_fields),
                },
                status_code=400,
            )
        except SoftWarnError:
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
                # Phase 7 Sub-C C.4 follow-up — the 18 pre-trade fields
                # must round-trip through the soft-warn confirm fragment
                # so the force=true resubmit carries them back through.
                # Without this, the second POST loses the operator's
                # typed values → MissingPreTradeFieldsException → 400 +
                # data loss. ``or ""`` is correct here (these are HTML
                # form values; the route's downstream ``or None`` coerces
                # empty strings to NULL where columns allow it). The
                # int-typed event/gap_risk_present fields render as "0"
                # / "1" / "" so the second POST's ``int | None = Form()``
                # binding succeeds.
                "thesis": thesis or "",
                "why_now": why_now or "",
                "invalidation_condition": invalidation_condition or "",
                "expected_scenario": expected_scenario or "",
                "premortem_technical": premortem_technical or "",
                "premortem_market_sector": premortem_market_sector or "",
                "premortem_execution": premortem_execution or "",
                "premortem_additional": premortem_additional or "",
                "event_risk_present": (
                    str(event_risk_present)
                    if event_risk_present is not None else ""
                ),
                "event_handling": event_handling or "",
                "event_type": event_type or "",
                "event_date": event_date or "",
                "gap_risk_present": (
                    str(gap_risk_present)
                    if gap_risk_present is not None else ""
                ),
                "gap_risk_handling": gap_risk_handling or "",
                # Multi-select: store as list so the template emits ONE
                # hidden input per vocabulary value selected. The
                # soft_warn_confirm.html.j2 special-cases list values to
                # avoid the str(["calm","focused"]) → "['calm', 'focused']"
                # round-trip-lossy degenerate case.
                "emotional_state_pre_trade": list(emo_clean),
                "manual_entry_confidence": manual_entry_confidence or "",
                "market_regime": market_regime or "",
                "catalyst": catalyst or "",
                "catalyst_other_description": (
                    catalyst_other_description or ""
                ),
                "open_count": actual_open,
                "soft_warn": cfg.position_limits.soft_warn_open,
                "hard_cap": cfg.position_limits.hard_cap_open,
            }
            return templates.TemplateResponse(
                request, "partials/soft_warn_confirm.html.j2",
                {"form_values": form_values},
            )
        except DuplicateOpenPositionError as exc:
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
        except HardCapError as exc:
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
            # DuplicateOpenPositionError upstream — but defense in
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
        ).render(
            request=request,
            trade_id=trade_id,
            window_days=cfg.review.review_window_days,
        )
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
    if trade is None or trade.state not in _ACTIVE_STATES:
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
        if trade_check is None or trade_check.state not in _ACTIVE_STATES:
            raise HTTPException(
                status_code=404,
                detail=f"Trade #{trade_id} not found or not open",
            )
        try:
            adjust_stop(conn, req)
        except ValueError as exc:
            # Trade not found or already closed — surface as 404 so the
            # HTMX-aware handler renders trade_form_error.html.j2 (§5.2).
            raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    not display the open-positions UI).

    3e.8 Bundle 1 (§4.F B.AC.5) — threads the same caches as the dashboard
    route so the expanded row can compose advisories that mirror the
    dashboard list view's content via the shared partial.
    """
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            expanded = build_open_positions_expanded(
                conn=conn, cfg=cfg, trade_id=trade_id,
                cache=request.app.state.price_cache,
                executor=request.app.state.price_fetch_executor,
                ohlcv_cache=request.app.state.ohlcv_cache,
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
    realized_R_if_plan_followed: float | None = Form(None),  # noqa: N803
    mistake_cost_confidence: str = Form(""),
    mistake_tags: list[str] = Form(default=[]),  # noqa: B008
):
    """Phase 6: persist a post-trade review.

    Success: 204 + HX-Redirect: /reviews/pending (browser re-navigates via htmx.js;
    NOT a 303 swap — Phase 5 lesson, brief §6.2 watch item 6).
    """
    import json
    from datetime import datetime as _dt

    from fastapi.responses import Response

    from swing.data.db import connect
    from swing.data.repos.trades import get_trade
    from swing.trades.review import (
        canonicalize_mistake_tags,
        complete_trade_review,
        compute_process_grade,
        validate_mistake_tags,
    )

    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates

    disq = (disqualifying_process_violation or "").lower() == "true"

    canonical_tags = canonicalize_mistake_tags(list(mistake_tags))
    if not canonical_tags:
        from swing.web.view_models.trades import build_review_vm
        vm = build_review_vm(trade_id=trade_id, cfg=cfg)
        empty_tags_msg = (
            "At least one mistake tag is required "
            "(select 'none_observed' if no mistakes observed)"
        )
        if vm is None:
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": empty_tags_msg},
                status_code=400,
            )
        return templates.TemplateResponse(
            request, "partials/review_form.html.j2",
            {"vm": vm, "error_message": empty_tags_msg},
            status_code=400,
        )
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
        # Phase 7 Sub-C C.7: closed-but-not-reviewed precondition. Use the
        # explicit single-state check rather than `state not in
        # ("closed","reviewed")` — the latter would re-allow already-reviewed
        # trades through this guard. Already-reviewed gets caught a few lines
        # below by the `reviewed_at is not None` 409 branch.
        if trade is None or trade.state != "closed":
            raise HTTPException(status_code=404)
        if trade.reviewed_at is not None:
            raise HTTPException(
                status_code=409,
                detail="Trade already reviewed; V1 supports single-review only",
            )
        # Hotfix 2026-05-05 (operator-witnessed gate finding S6): the prior
        # implementation called update_trade_review_fields directly inside
        # `with conn:`, persisting Phase 6 review fields BUT never firing the
        # `closed → reviewed` state transition that Phase 7 Sub-B B.6 wired
        # into the complete_trade_review service wrapper. Result: review-
        # completed trades stayed in `state='closed'` (with reviewed_at
        # populated), violating spec §3 terminal-state semantics. Sub-B
        # return report explicitly flagged this Sub-C T1 territory item;
        # implementation didn't switch. Fix now: route through the service.
        review_ts = _dt.now().isoformat(timespec="seconds")
        complete_trade_review(
            conn, trade_id=trade_id,
            reviewed_at=review_ts,
            mistake_tags_json=json.dumps(canonical_tags),
            entry_grade=entry_grade,
            management_grade=management_grade,
            exit_grade=exit_grade,
            process_grade=process_grade,
            disqualifying_process_violation=disq,
            realized_R_if_plan_followed=realized_R_if_plan_followed,
            mistake_cost_confidence=mistake_cost_confidence or None,
            lesson_learned=lesson_learned,
            event_ts=review_ts,
            rationale=None,
        )
    finally:
        conn.close()
    # code-review I3 (operator-witnessed S5): /trades is unrouted — htmx.js
    # honors the HX-Redirect header but the browser then 404s. Land on
    # /reviews/pending instead: workflow-natural ("after reviewing, see
    # what's still pending") and the route exists.
    return Response(status_code=204, headers={"HX-Redirect": "/reviews/pending"})


@router.get("/reviews/pending", response_class=HTMLResponse)
def reviews_pending(request: Request):
    """Phase 6: list ALL closed-and-unreviewed trades.

    Linked from the dashboard 'Needs review (N)' badge. The badge itself
    counts only trades closed >= cfg.review.review_window_days ago, but
    this list view shows every closed-unreviewed trade so the operator
    can review fresh trades early. (Codex R1 Major 1 + R2 Minor 1.)
    """
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    from swing.web.view_models.trades import build_reviews_pending_vm
    vm = build_reviews_pending_vm(cfg=cfg)
    return templates.TemplateResponse(
        request, "reviews_pending.html.j2", {"vm": vm},
    )


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
    if trade is None or trade.state not in _ACTIVE_STATES:
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


# Phase 8 Task 5.0 — daily-management event-log POST. Registered BEFORE the
# bare `/trades/{trade_id}` wildcard so the more-specific path is matched
# first by FastAPI/Starlette's registration-order routing. The route
# delegates to ``record_event_log`` (T3.2's single-transaction service)
# and emits 204 + ``HX-Redirect: /`` on success per Phase 5 R1 M2 lesson
# (htmx.js swallows 303 → swap-target transparently; real-browser
# navigation requires the 204 + HX-Redirect pair).
# Polish-bundle-2026-05-09 Task B.1: redirect target was changed from
# ``/trades/{trade_id}`` to ``/`` so the operator returns to the dashboard
# after submitting a daily-management event.
@router.post("/trades/{trade_id}/daily-management/event")
async def daily_management_event_post(request: Request, trade_id: int):
    """POST handler for the daily-management event-log form.

    Constructs an :class:`EventLogRequest` dataclass from the form payload
    and calls ``record_event_log`` (T3.2 single-transaction service). On
    ``ValidationException`` re-renders the form partial with a 422 + error
    banner; on success returns ``204 No Content`` + ``HX-Redirect: /`` so
    htmx.js navigates the real browser back to the dashboard
    (polish-bundle-2026-05-09 Task B.1).

    HTMX failure-surface mitigations (CLAUDE.md HTMX form gotcha; Phase 5
    R1 M1/M2 + Phase 6 R5 I3 lessons):

    * (a) The form partial includes ``hx-headers='{"HX-Request": "true"}'``
      so OriginGuard strict-mode admits nested submits — verified by a
      template literal-string assertion (real-browser only failure).
    * (b) Success-path response = 204 + HX-Redirect, NOT 303 → swap-target.
    * (c) HX-Redirect target ``/`` IS a registered GET route (the
      dashboard) — verified by route-table + GET-resolves assertion in
      the regression test (Phase 6 I3 lesson).
    """
    from fastapi.responses import Response

    from swing.trades.daily_management import (
        EventLogRequest,
        ValidationException,
        record_event_log,
    )

    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    form = await request.form()

    def _opt(name: str) -> str | None:
        # Form-input fallback: prefer None to "" so nullable text columns
        # with CHECK enums (CLAUDE.md `or "" vs or None` gotcha) accept the
        # absent input cleanly. Empty-string survives only as the explicit
        # JSON-list emotional_state default ("[]") set in the form template.
        raw = form.get(name)
        if raw is None:
            return None
        s = str(raw).strip()
        return s or None

    def _int_flag(name: str) -> int:
        raw = form.get(name)
        return 1 if str(raw or "").strip() == "1" else 0

    def _opt_float(name: str) -> float | None:
        raw = form.get(name)
        if raw is None or str(raw).strip() == "":
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def _emotional_state_from_form(form_data) -> str:
        # code-review I1 fix — multi-checkbox: form.getlist returns the list
        # of values for each checked box. Filter empties + dedupe (preserve
        # first-seen order). Returns JSON-encoded string for record_event_log
        # service-layer contract (emotional_state TEXT JSON-list per spec §1.2).
        import json as _json
        raw_values = form_data.getlist("emotional_state")
        seen: set[str] = set()
        clean: list[str] = []
        for v in raw_values:
            s = str(v).strip()
            if s and s not in seen:
                seen.add(s)
                clean.append(s)
        return _json.dumps(clean)

    # Codex R2 Major #2 fix: SERVER-STAMP ``created_at`` at handler entry.
    # The hidden form input is removed from the rendered partial — a stale
    # form (page open across sessions) or a tampered POST would otherwise
    # persist the wrong audit timestamp. Format matches spec §8.4 + the
    # service-layer convention used by ``compute_daily_approximate_snapshot``
    # (naive UTC ISO, microseconds stripped for stable comparison).
    from datetime import UTC as _UTC
    from datetime import datetime as _dt_now
    server_created_at = (
        _dt_now.now(_UTC).replace(tzinfo=None, microsecond=0).isoformat()
    )

    # Codex R3 Major #2 fix: SERVER-STAMP session anchors at handler entry.
    # ``review_date`` and ``data_asof_session`` default to
    # ``last_completed_session(now)`` per spec §4.5 — never trust hidden
    # form values (a stale form across sessions, weekend/holiday submission,
    # or tampered POST would otherwise anchor the row to a non-session
    # date and break same-session snapshot context). The form template no
    # longer renders hidden inputs for these fields; values arrive (if at
    # all) from the previous render's display + are IGNORED here.
    from swing.evaluation.dates import last_completed_session
    server_session_anchor = last_completed_session(_dt_now.now()).isoformat()

    # Codex R4 Major #2 fix: SERVER-STAMP ``mfe_mae_precision_level``. V1
    # only emits ``daily_approximate`` (spec §10.7); the form template no
    # longer renders a hidden input for this field. A tampered POST
    # (``mfe_mae_precision_level=intraday_exact``) would otherwise persist
    # misleading audit metadata that doesn't match the actual data source.
    # Future V2 (Schwab API intraday ingestion) will route through
    # ``tier_upgrade_to_intraday`` rather than the operator-driven event_log
    # form, so this constant is correct for the lifetime of the form route.
    server_mfe_mae_precision_level = "daily_approximate"

    # Build EventLogRequest from the form payload. Required NOT-NULL
    # metadata fields fall back to safe defaults so the dataclass
    # constructor never raises on missing keys (the service-layer
    # validator surfaces missing-required-field errors via
    # ValidationException → 422 below).
    try:
        req = EventLogRequest(
            trade_id=trade_id,
            # NOTE: review_date / data_asof_session are server-stamped above
            # (Codex R3 Major #2); the route does NOT read them from form data.
            review_date=server_session_anchor,
            data_asof_session=server_session_anchor,
            # NOTE: ``created_at`` is server-stamped above; the route does
            # NOT read it from form data (Codex R2 Major #2).
            created_at=server_created_at,
            # NOTE: ``mfe_mae_precision_level`` is server-stamped above; the
            # route does NOT read it from form data (Codex R4 Major #2).
            mfe_mae_precision_level=server_mfe_mae_precision_level,
            stop_changed=_int_flag("stop_changed"),
            action_taken=_opt("action_taken"),
            rule_violation_suspected=_int_flag("rule_violation_suspected"),
            # code-review I1 fix — emotional_state is multi-checkbox; collect
            # via form.getlist + JSON-encode (mirrors Phase 7 entry-form's
            # `_json.dumps(list(emotional_state))` pattern in the route +
            # CLI). Filter empties + dedupe (preserve first-seen order) so
            # bare-cURL POST submitting "emotional_state=" doesn't survive
            # as the literal empty-string member; an explicitly empty list
            # serializes to "[]" — matching the previous default value.
            emotional_state=_emotional_state_from_form(form),
            prior_stop=_opt_float("prior_stop"),
            new_stop=_opt_float("new_stop"),
            stop_change_reason=_opt("stop_change_reason"),
            action_reason=_opt("action_reason"),
            management_notes=_opt("management_notes"),
        )
    except (TypeError, ValueError) as exc:
        return templates.TemplateResponse(
            request, "partials/trade_form_error.html.j2",
            {"error_message": str(exc)},
            status_code=422,
        )

    conn = connect(cfg.paths.db_path)
    try:
        try:
            record_event_log(conn, trade_id=trade_id, req=req)
        except ValidationException as exc:
            from swing.web.view_models.trades import build_event_log_form_vm
            vm = build_event_log_form_vm(trade_id=trade_id, cfg=cfg)
            if vm is None:
                # Trade not found / not active — bubble up as 422 with the
                # service-layer error message rather than re-render an
                # absent form. (Active-state precondition is the operator's
                # discriminating signal.)
                return templates.TemplateResponse(
                    request, "partials/trade_form_error.html.j2",
                    {"error_message": str(exc)},
                    status_code=422,
                )
            return templates.TemplateResponse(
                request, "partials/daily_management_event_form.html.j2",
                {"vm": vm, "error_message": str(exc)},
                status_code=422,
            )
        except ValueError as exc:
            # Trade not found / Phase 7 service rejection (terminal state).
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        conn.close()

    # Success: 204 + HX-Redirect. Target route ``/`` (dashboard) IS
    # registered (Phase 6 R5 I3 lesson — verified by route-table + GET-
    # resolves assertion in the regression test). Redirect target was
    # changed from ``/trades/{trade_id}`` to ``/`` in
    # polish-bundle-2026-05-09 Task B.1 so the operator returns to the
    # dashboard after submitting a daily-management event.
    return Response(
        status_code=204,
        headers={"HX-Redirect": "/"},
    )


# Phase 7 Sub-C C.5 — canonical trade-detail page. REGISTERED LAST so the
# bare `/trades/{trade_id}` path-template wildcard does NOT shadow the more
# specific `/trades/entry/form`, `/trades/{trade_id}/exit`, etc. routes
# above. FastAPI/Starlette matches in registration order; the literal
# `entry` segment in /trades/entry/form is matched before this route's
# `{trade_id}` parameter sees the request.
@router.get("/trades/{trade_id}", response_class=HTMLResponse)
def trade_detail(request: Request, trade_id: int):
    """Phase 7 — canonical trade-detail page.

    Renders the Pre-Trade Decision section (gated on
    ``vm.has_pre_trade_data``), the audit log of pre-trade edits, and a
    read-only summary of the trade. Position-management actions remain on
    the dashboard's open-positions row in V1.
    """
    from swing.web.view_models.trades import (
        build_daily_management_timeline_vm,
        build_event_log_form_vm,
    )
    cfg = apply_overrides(request.app.state.cfg)
    templates = request.app.state.templates
    # 3e.8 Bundle 1 (§4.F B.AC.6) — thread the price + OHLCV caches so the
    # detail-page VM can compose per-trade advisories. Mirrors the dashboard
    # route's pattern; closed/reviewed trades short-circuit to advisories=()
    # inside the builder.
    vm = build_trade_detail_vm(
        trade_id=trade_id, cfg=cfg,
        cache=request.app.state.price_cache,
        executor=request.app.state.price_fetch_executor,
        ohlcv_cache=request.app.state.ohlcv_cache,
    )
    if vm is None:
        raise HTTPException(
            status_code=404, detail=f"Trade #{trade_id} not found",
        )
    # Phase 8 Task 5.1 — per-trade timeline section. Always rendered (state-
    # agnostic per spec §7.2; closed trades surface their history). Returns
    # None only when the trade does not exist; the trade_detail VM build
    # above already returned 404 in that case, so the timeline VM is
    # guaranteed non-None here unless a race deletes the trade between the
    # two reads (acceptable: the section will simply render its empty
    # state via the partial's `{% if not timeline_vm.rows %}` branch when
    # rows is empty; the None branch is defensive for the race window).
    timeline_vm = build_daily_management_timeline_vm(
        trade_id=trade_id, cfg=cfg,
    )
    # Codex R1 Major 2 fix — surface the event-log form for active trades.
    # ``build_event_log_form_vm`` returns None for non-active states (closed,
    # reviewed), so the template's ``{% if event_form_vm is not none %}``
    # gate naturally hides the form on those trades. Without this, the POST
    # endpoint exists but the operator has no UI surface to reach it.
    event_form_vm = build_event_log_form_vm(trade_id=trade_id, cfg=cfg)
    return templates.TemplateResponse(
        request, "trades/detail.html.j2",
        {
            "vm": vm,
            "timeline_vm": timeline_vm,
            "event_form_vm": event_form_vm,
        },
    )
