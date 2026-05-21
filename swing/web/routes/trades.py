"""Phase 3b trade-action routes. Starts with sizing-hint; entry/exit/stop
endpoints are added in later tasks. All write endpoints require HX-Request
under strict OriginGuard (spec §3.3)."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta

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
    # Phase 13 T3.SB1 Codex R1 Major #3 fix — preserve the submitted
    # auto-fill anchors across validation error re-renders. Without
    # these, ``build_entry_form_vm`` below fires a FRESH Schwab Trader
    # API call on every validation retry — bleeding the lookback
    # window + drifting the anchor away from the operator's original
    # submission + potentially overwriting a tampered anchor with a
    # genuine one on retry. Defaults None preserve backward compat for
    # callers without auto-fill semantics.
    submitted_schwab_source_value_json: str | None = None,
    submitted_auto_fill_audit_at: str | None = None,
    submitted_fill_origin_at_form_render: str | None = None,
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
        # Phase 13 T3.SB1 Codex R1 Major #3 fix — overwrite the freshly-
        # rebuilt auto-fill anchors with the SUBMITTED values, so the
        # operator's force=true / retry submit replays the same anchor
        # the original validation-failed POST carried. This prevents the
        # build_entry_form_vm-driven fresh Schwab fetch from substituting
        # a different anchor mid-flight.
        if submitted_schwab_source_value_json is not None:
            # Codex R2 Minor #1 fix — when restoring a submitted populated
            # anchor on retry, also restore ``auto_fill_kind='populated'``
            # AND clear ``auto_fill_advisory_text``. Otherwise the freshly-
            # rebuilt VM's stale kind/advisory (from the new Schwab fetch
            # that may have returned 'empty' / 'degraded') leaks into the
            # rendered banner, showing "no match" while the hidden anchor
            # still claims auto-fill — confusing the operator.
            submitted_claim = (
                submitted_fill_origin_at_form_render or "operator_typed"
            )
            preserved_kind = (
                "populated"
                if (
                    submitted_schwab_source_value_json
                    and submitted_claim in (
                        "schwab_auto",
                        "schwab_auto_then_operator_corrected",
                    )
                )
                else vm.auto_fill_kind
            )
            preserved_advisory = (
                None
                if preserved_kind == "populated"
                else vm.auto_fill_advisory_text
            )
            vm = dc_replace(
                vm,
                auto_fill_schwab_source_value_json=(
                    submitted_schwab_source_value_json or None
                ),
                auto_fill_audit_at=(
                    submitted_auto_fill_audit_at or None
                ),
                auto_fill_fill_origin=submitted_claim,
                auto_fill_kind=preserved_kind,
                auto_fill_advisory_text=preserved_advisory,
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
    # Phase 9 Bundle D — sector/industry tamper-hardening anchor (Codex
    # R2 Major #1 fix). Carries the form-render's evaluation_run_id so
    # POST validation reaches the same authoritative candidate row the
    # operator saw. None when the form-render found no cached candidate
    # OR when the form posts no anchor (bare cURL / CLI tests) — both
    # cases route to the backward-compat skip path. Mirrors
    # chart_pattern's pipeline_run_id hidden anchor.
    sector_industry_evaluation_run_id: int | None = Form(None),
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
    # Phase 13 T3.SB1 T-B.1.4 — auto-fill hidden audit anchors emitted by
    # the form-render path (T-B.1.3 template additions). Default ""/None
    # so legacy callers (CLI tests, bare cURL, pre-Phase-13 form submits)
    # keep working — the POST handler infers fill_origin='operator_typed'
    # when these are absent. Per CLAUDE.md gotcha "Form-render hidden
    # anchors driving POST-time validation MUST round-trip through
    # soft-warn confirm form_values dict" + Phase 9 Sub-bundle D R3
    # Critical #1 LOCK: these 3 anchors MUST also be added to the
    # soft-warn confirm form_values dict below (T-B.1.4 +5.5 watch
    # item 9 BINDING).
    schwab_source_value_json: str = Form(""),
    auto_fill_audit_at: str = Form(""),
    fill_origin_at_form_render: str = Form(""),
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
            submitted_schwab_source_value_json=schwab_source_value_json,
            submitted_auto_fill_audit_at=auto_fill_audit_at,
            submitted_fill_origin_at_form_render=fill_origin_at_form_render,
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
            submitted_schwab_source_value_json=schwab_source_value_json,
            submitted_auto_fill_audit_at=auto_fill_audit_at,
            submitted_fill_origin_at_form_render=fill_origin_at_form_render,
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
            submitted_schwab_source_value_json=schwab_source_value_json,
            submitted_auto_fill_audit_at=auto_fill_audit_at,
            submitted_fill_origin_at_form_render=fill_origin_at_form_render,
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
            submitted_schwab_source_value_json=schwab_source_value_json,
            submitted_auto_fill_audit_at=auto_fill_audit_at,
            submitted_fill_origin_at_form_render=fill_origin_at_form_render,
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
                submitted_schwab_source_value_json=schwab_source_value_json,
                submitted_auto_fill_audit_at=auto_fill_audit_at,
                submitted_fill_origin_at_form_render=fill_origin_at_form_render,
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
                submitted_schwab_source_value_json=schwab_source_value_json,
                submitted_auto_fill_audit_at=auto_fill_audit_at,
                submitted_fill_origin_at_form_render=fill_origin_at_form_render,
            )

    # Phase 9 Sub-bundle D Task D.1 + D.2 — sector/industry tamper
    # hardening (mirrors chart_pattern hardening pattern; recon at
    # docs/phase9-bundle-D-task-D0-recon.md).
    #
    # Codex R2 fix (Critical #1 + Major #1 + #2): the form-render emits
    # an explicit ``sector_industry_evaluation_run_id`` hidden anchor
    # (analogous to chart_pattern's ``classification_pipeline_run_id``).
    # POST validates against that exact eval_run's candidate row — NOT
    # a POST-time recomputation of "latest". This closes:
    #
    # - R2 Critical #1: previously the both-blank check was an outer
    #   guard that bypassed the entire tamper check; a tampered HTMX
    #   POST with both sector="" + industry="" silently passed. The
    #   anchor flip changes the backward-compat path: if NO anchor was
    #   posted (bare cURL / CLI not going through the form), skip the
    #   check entirely; otherwise — including both-blank with a valid
    #   posted anchor — strict comparison fires.
    # - R2 Major #1: anchor stability across GET → POST. A pipeline run
    #   landing between form render and submit can no longer (a)
    #   false-reject a legitimate POST against the freshly-landed row
    #   nor (b) false-accept a tampered POST whose values happen to
    #   match the new row.
    # - R2 Major #2: the implementation now matches the chart_pattern-
    #   mirror semantics named in plan §A.4 + spec §7 (extension);
    #   plan §A.4 + the D0 recon note are updated in this commit.
    if sector_industry_evaluation_run_id is not None:
        from swing.evaluation.dates import action_session_for_run
        today_session_iso = (
            action_session_for_run(datetime.now()).isoformat()
        )
        _conn = connect(cfg.paths.db_path)
        try:
            _cand_row = _conn.execute(
                "SELECT c.sector, c.industry, "
                "e.action_session_date "
                "FROM candidates c "
                "JOIN evaluation_runs e "
                "ON c.evaluation_run_id = e.id "
                "WHERE c.evaluation_run_id = ? AND c.ticker = ? "
                "LIMIT 1",
                (sector_industry_evaluation_run_id, ticker.upper()),
            ).fetchone()
        finally:
            _conn.close()
        if _cand_row is None:
            # Posted anchor doesn't reference an existing candidate row
            # for this ticker — tampered or operator-supplied bogus
            # eval_run_id. Reject without emitting an audit row (no
            # cached values to attribute the discrepancy against).
            return _rerender_entry_form_with_error(
                request=request, templates=templates, cfg=cfg,
                cache=cache, executor=executor,
                ticker=ticker, entry_date=entry_date,
                entry_price=entry_price, shares=shares,
                initial_stop=initial_stop,
                rationale=rationale, notes=notes,
                error_message=(
                    "sector/industry anchor rejected: no cached "
                    f"candidate exists for {ticker.upper()} under "
                    f"evaluation_run_id="
                    f"{sector_industry_evaluation_run_id}. Re-render "
                    "the form to bind a current anchor."
                ),
                origin=origin_coerced,
                submitted_schwab_source_value_json=schwab_source_value_json,
                submitted_auto_fill_audit_at=auto_fill_audit_at,
                submitted_fill_origin_at_form_render=fill_origin_at_form_render,
            )
        cached_sector = _cand_row[0] or ""
        cached_industry = _cand_row[1] or ""
        # Spec §3.3.1 ``session`` is the cached candidate's anchor —
        # carry the eval_run's action_session_date verbatim (matches
        # form-render's anchor and the data the operator saw).
        cand_session_iso = _cand_row[2] or today_session_iso
        mismatch_field: str | None = None
        # Strict ``!=`` comparison — empty form value against
        # non-empty cached IS a tamper (R1 Critical #1 close
        # preserved); both-blank-with-cached-non-empty fires here.
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
                submitted_schwab_source_value_json=schwab_source_value_json,
                submitted_auto_fill_audit_at=auto_fill_audit_at,
                submitted_fill_origin_at_form_render=fill_origin_at_form_render,
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

    # Phase 13 T3.SB1 T-B.1.4 — fill_origin transition resolution.
    # Compare submitted entry_date / entry_price / shares against the
    # form-render anchor (``schwab_source_value_json`` JSON envelope).
    # Three outcomes:
    #   - No anchor (empty/missing JSON) → operator_typed; all audit
    #     columns NULL.
    #   - Anchor matches submitted values exactly → schwab_auto.
    #   - Anchor differs from submitted values (operator edited any of
    #     the 3 fields) → schwab_auto_then_operator_corrected;
    #     ``operator_corrected_value_json`` carries the submitted values.
    # Per spec §6.1 + §6.4 + plan §G.2 T-B.1.4 + brief §5 watch item 10.
    resolved_fill_origin = "operator_typed"
    resolved_schwab_source_value_json: str | None = None
    resolved_operator_corrected_value_json: str | None = None
    resolved_auto_fill_audit_at: str | None = None
    # Codex R1 Major #1 + #2 fix — consistency check across the 3 hidden
    # anchors (schwab_source_value_json + auto_fill_audit_at +
    # fill_origin_at_form_render). When the operator claims
    # fill_origin_at_form_render='schwab_auto' (or
    # 'schwab_auto_then_operator_corrected') but the anchor JSON envelope
    # is missing / empty / malformed, the POST is internally inconsistent
    # — either a tampered submit OR a stale form (operator submitted the
    # page after server-side state evicted). Reject with 400 + descriptive
    # error so the operator re-renders. The legacy / bare-cURL backward-
    # compat path (no anchor, no claim) still flows through as
    # operator_typed.
    # Codex R3 Minor #1 fix — normalize ``fill_origin_at_form_render``
    # via ``.strip()`` ONCE here so the same canonical value is consulted
    # by both the consistency-check predicate (``claimed_auto_fill``) and
    # the re-render preservation kwargs (`submitted_*`). Without this,
    # whitespace-padded input could be treated as auto-fill for validation
    # purposes but not restored as populated on retry.
    fill_origin_at_form_render = fill_origin_at_form_render.strip()
    claimed_auto_fill = fill_origin_at_form_render in (
        "schwab_auto", "schwab_auto_then_operator_corrected",
    )
    if schwab_source_value_json.strip():
        try:
            anchor_envelope = _json.loads(schwab_source_value_json)
        except (ValueError, TypeError):
            anchor_envelope = None
        # Codex R2 Major #1 fix — reject non-dict JSON (e.g., ``[]``, ``"x"``)
        # when the claim is auto-fill. Without this guard, a valid-JSON
        # non-dict slips past the ``isinstance(anchor_envelope, dict)``
        # branch below and silently persists as ``operator_typed`` despite
        # the claim, re-opening the "claim present but provenance erased"
        # failure mode the R1 Major #1 fix was meant to close.
        # Codex R3 Major #2 fix — when rejecting due to tampered/invalid
        # anchor, pass empty submitted_* kwargs (instead of the raw
        # rejected anchor) so the recovery form receives a FRESH
        # auto-fill anchor from build_entry_form_vm. Without this, the
        # 400 response re-emits the same invalid anchor + the operator
        # gets trapped in repeated 400s on every retry.
        def _reject_anchor(error_message: str):
            return _rerender_entry_form_with_error(
                request=request, templates=templates, cfg=cfg,
                cache=cache, executor=executor,
                ticker=ticker, entry_date=entry_date,
                entry_price=entry_price, shares=shares,
                initial_stop=initial_stop, rationale=rationale, notes=notes,
                error_message=error_message,
                origin=origin_coerced,
                # Anchor was rejected as invalid — DON'T preserve it.
                # Leaving these None tells _rerender_entry_form_with_error
                # to use the rebuilt VM's fresh auto-fill anchor.
                submitted_schwab_source_value_json=None,
                submitted_auto_fill_audit_at=None,
                submitted_fill_origin_at_form_render=None,
            )

        if (
            (anchor_envelope is None
             or not isinstance(anchor_envelope, dict))
            and claimed_auto_fill
        ):
            return _reject_anchor(
                "Trade entry rejected: fill_origin_at_form_render="
                f"{fill_origin_at_form_render!r} claims auto-fill "
                "provenance but schwab_source_value_json is malformed, "
                "unparseable, or not a JSON object. The form has been "
                "regenerated with a fresh Schwab fetch; please re-submit."
            )
        # Codex R2 Major #2 fix — when the anchor IS a dict but lacks one
        # of the 3 required keys (entry_date, entry_price, shares) AND
        # the operator claims auto-fill, reject. Without this guard, an
        # empty-dict ``{}`` or a partial envelope classifies the row as
        # ``schwab_auto_then_operator_corrected`` (every missing key
        # counts as an edit) and persists the junk source JSON.
        if (
            isinstance(anchor_envelope, dict)
            and claimed_auto_fill
            and not all(
                k in anchor_envelope
                for k in ("entry_date", "entry_price", "shares")
            )
        ):
            return _reject_anchor(
                "Trade entry rejected: fill_origin_at_form_render="
                f"{fill_origin_at_form_render!r} claims auto-fill "
                "provenance but schwab_source_value_json is missing "
                "one or more required keys (entry_date, entry_price, "
                "shares). The form has been regenerated; please re-submit."
            )
        # Codex R3 Major #1 fix — value-validation for the 3 required
        # keys when ``claimed_auto_fill``. Without this guard, an
        # ``entry_price=NaN`` slips past the ``abs(... - ...) > 1e-9``
        # comparison (NaN comparisons all return False), persisting the
        # junk source JSON as ``schwab_auto``; an ``entry_date='foo'``
        # would persist as junk; a non-int ``shares`` would coerce
        # noisily. Validate value shapes here BEFORE the transition
        # logic at L957 onward.
        if isinstance(anchor_envelope, dict) and claimed_auto_fill:
            import math as _math
            v_entry_date = anchor_envelope.get("entry_date")
            v_entry_price = anchor_envelope.get("entry_price")
            v_shares = anchor_envelope.get("shares")
            # Codex R4 Minor #1 fix — tighten date validation to calendar
            # validity (rejects 2026-99-99 etc.). ``date.fromisoformat``
            # raises ValueError on invalid date strings; tolerate by
            # catching to set the flag False.
            from datetime import date as _date_cls
            entry_date_ok = isinstance(v_entry_date, str)
            if entry_date_ok:
                try:
                    _date_cls.fromisoformat(v_entry_date)
                except (TypeError, ValueError):
                    entry_date_ok = False
            entry_price_ok = (
                isinstance(v_entry_price, (int, float))
                and not isinstance(v_entry_price, bool)
                and _math.isfinite(float(v_entry_price))
            )
            shares_ok = (
                isinstance(v_shares, int) and not isinstance(v_shares, bool)
            )
            if not (entry_date_ok and entry_price_ok and shares_ok):
                return _reject_anchor(
                    "Trade entry rejected: fill_origin_at_form_render="
                    f"{fill_origin_at_form_render!r} claims auto-fill "
                    "provenance but schwab_source_value_json contains "
                    "invalid values (entry_date must be ISO YYYY-MM-DD; "
                    "entry_price must be finite numeric; shares must be "
                    "an integer). The form has been regenerated; please "
                    "re-submit."
                )
        # Codex R4 Major #1 fix — require ``claimed_auto_fill`` to be true
        # before any non-operator_typed fill_origin stamping. Without this
        # gate, an attacker can submit a valid-JSON anchor with EMPTY
        # ``fill_origin_at_form_render`` and have it persist as
        # 'schwab_auto' (the JSON envelope present + claim absent is
        # internally inconsistent + the previous code path would have
        # stamped Schwab provenance anyway). With the gate, the
        # provenance-stamping branch only fires when BOTH halves of the
        # consistency check agree.
        if isinstance(anchor_envelope, dict) and claimed_auto_fill:
            # The form-render anchor exists; default to schwab_auto unless
            # operator edited any of the 3 auto-populated fields.
            anchor_entry_date = anchor_envelope.get("entry_date")
            anchor_entry_price = anchor_envelope.get("entry_price")
            anchor_shares = anchor_envelope.get("shares")
            # Compare entry_price as float (tolerant of 150 vs 150.0 vs
            # "150.00" form-text drift); shares as int (form Field(int)
            # already coerced); entry_date as exact str (ISO YYYY-MM-DD).
            try:
                anchor_price_float = (
                    float(anchor_entry_price)
                    if anchor_entry_price is not None else None
                )
            except (TypeError, ValueError):
                anchor_price_float = None
            try:
                anchor_shares_int = (
                    int(anchor_shares) if anchor_shares is not None else None
                )
            except (TypeError, ValueError):
                anchor_shares_int = None
            entry_date_diff = anchor_entry_date != entry_date
            price_diff = (
                anchor_price_float is None
                or abs(anchor_price_float - entry_price) > 1e-9
            )
            shares_diff = (
                anchor_shares_int is None or anchor_shares_int != shares
            )
            if entry_date_diff or price_diff or shares_diff:
                resolved_fill_origin = "schwab_auto_then_operator_corrected"
                # Stamp the submitted values so future reads can compare.
                resolved_operator_corrected_value_json = _json.dumps(
                    {
                        "entry_date": entry_date,
                        "entry_price": entry_price,
                        "shares": shares,
                    },
                    sort_keys=True,
                )
            else:
                resolved_fill_origin = "schwab_auto"
            resolved_schwab_source_value_json = schwab_source_value_json
            # ``auto_fill_audit_at`` is a separate hidden input alongside
            # the JSON envelope (per T-B.1.3 template emission). Use the
            # submitted value verbatim; fall back to None on empty/missing.
            resolved_auto_fill_audit_at = auto_fill_audit_at or None
    elif claimed_auto_fill:
        # Codex R1 Major #1 + #2 fix — claim of schwab_auto with EMPTY
        # anchor (operator stripped the JSON envelope but kept the
        # claim). Reject with 400 (cannot trust the claim without the
        # anchor). Same UX as the malformed-JSON branch above.
        return _rerender_entry_form_with_error(
            request=request, templates=templates, cfg=cfg,
            cache=cache, executor=executor,
            ticker=ticker, entry_date=entry_date,
            entry_price=entry_price, shares=shares,
            initial_stop=initial_stop, rationale=rationale, notes=notes,
            error_message=(
                "Trade entry rejected: fill_origin_at_form_render="
                f"{fill_origin_at_form_render!r} claims auto-fill "
                "provenance but schwab_source_value_json is empty. "
                "Re-render the form to recover."
            ),
            origin=origin_coerced,
            submitted_schwab_source_value_json=schwab_source_value_json,
            submitted_auto_fill_audit_at=auto_fill_audit_at,
            submitted_fill_origin_at_form_render=fill_origin_at_form_render,
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
        # Phase 13 T3.SB1 T-B.1.4 — auto-fill audit columns persisted on
        # the fills row by ``record_entry`` → ``insert_fill_with_event``.
        fill_origin=resolved_fill_origin,
        schwab_source_value_json=resolved_schwab_source_value_json,
        operator_corrected_value_json=(
            resolved_operator_corrected_value_json
        ),
        auto_fill_audit_at=resolved_auto_fill_audit_at,
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
                    # Phase 13 T3.SB1 Codex R1 Major #3 fix — preserve
                    # the submitted auto-fill anchors so the
                    # MissingPreTradeFieldsException re-render carries
                    # them back into the form (force=true retry replays
                    # the same anchor instead of substituting a fresh
                    # Schwab fetch's result).
                    # Codex R2 Minor #1 fix — also restore kind +
                    # clear advisory text when the submitted claim is
                    # populated, so the banner doesn't drift to "no
                    # match" while the hidden anchor still claims
                    # auto-fill.
                    auto_fill_schwab_source_value_json=(
                        schwab_source_value_json or None
                    ),
                    auto_fill_audit_at=auto_fill_audit_at or None,
                    auto_fill_fill_origin=(
                        fill_origin_at_form_render or "operator_typed"
                    ),
                    auto_fill_kind=(
                        "populated"
                        if (
                            schwab_source_value_json
                            and fill_origin_at_form_render in (
                                "schwab_auto",
                                "schwab_auto_then_operator_corrected",
                            )
                        )
                        else vm.auto_fill_kind
                    ),
                    auto_fill_advisory_text=(
                        None
                        if (
                            schwab_source_value_json
                            and fill_origin_at_form_render in (
                                "schwab_auto",
                                "schwab_auto_then_operator_corrected",
                            )
                        )
                        else vm.auto_fill_advisory_text
                    ),
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
                # Phase 9 Sub-bundle D Codex R3 Critical #1 — the
                # sector/industry tamper-hardening anchor must also
                # round-trip through soft-warn confirm. Without it the
                # ``force=true`` resubmit arrives with no anchor and
                # falls into the bare-cURL backward-compat skip path,
                # silently accepting tampered sector/industry on the
                # confirm submit. Re-emit as "" when None so the hidden
                # input is consistent with the form's GET render.
                "sector_industry_evaluation_run_id": (
                    sector_industry_evaluation_run_id
                    if sector_industry_evaluation_run_id is not None
                    else ""
                ),
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
                # Phase 13 T3.SB1 T-B.1.4 — auto-fill hidden anchors MUST
                # round-trip through the soft-warn confirm fragment per
                # CLAUDE.md gotcha "Form-render hidden anchors driving
                # POST-time validation MUST round-trip through soft-warn
                # confirm form_values dict" + Phase 9 Sub-bundle D R3
                # Critical #1 LOCK + dispatch brief §5 watch item 9.
                # Without this, a tampered force=true resubmit would
                # silently drop the anchors → fill_origin defaults to
                # 'operator_typed' on the persisted fill row even when
                # the original submit was 'schwab_auto'.
                "schwab_source_value_json": schwab_source_value_json or "",
                "auto_fill_audit_at": auto_fill_audit_at or "",
                "fill_origin_at_form_render": (
                    fill_origin_at_form_render or ""
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
                    # user's submitted value; suggested_shares stays as server computed
                    input_shares=shares,
                    rationale=rationale,
                    notes=notes or "",
                    # Phase 13 T3.SB1 Codex R1 Major #3 + R2 Minor #1
                    # fix — preserve the submitted auto-fill anchors AND
                    # restore kind/advisory on the duplicate-position
                    # re-render path so the operator's original anchor +
                    # banner state isn't overwritten by a fresh Schwab
                    # fetch's stale advisory.
                    auto_fill_schwab_source_value_json=(
                        schwab_source_value_json or None
                    ),
                    auto_fill_audit_at=auto_fill_audit_at or None,
                    auto_fill_fill_origin=(
                        fill_origin_at_form_render or "operator_typed"
                    ),
                    auto_fill_kind=(
                        "populated"
                        if (
                            schwab_source_value_json
                            and fill_origin_at_form_render in (
                                "schwab_auto",
                                "schwab_auto_then_operator_corrected",
                            )
                        )
                        else vm.auto_fill_kind
                    ),
                    auto_fill_advisory_text=(
                        None
                        if (
                            schwab_source_value_json
                            and fill_origin_at_form_render in (
                                "schwab_auto",
                                "schwab_auto_then_operator_corrected",
                            )
                        )
                        else vm.auto_fill_advisory_text
                    ),
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
                submitted_schwab_source_value_json=schwab_source_value_json,
                submitted_auto_fill_audit_at=auto_fill_audit_at,
                submitted_fill_origin_at_form_render=fill_origin_at_form_render,
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
            # V1: schema-message-coupled — substring-matches CHECK constraint
            # text; forward hardening = pre-insert FK existence check.
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
                submitted_schwab_source_value_json=schwab_source_value_json,
                submitted_auto_fill_audit_at=auto_fill_audit_at,
                submitted_fill_origin_at_form_render=fill_origin_at_form_render,
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
async def exit_post(
    request: Request,
    trade_id: int,
    exit_date: str = Form(...),
    exit_price: float = Form(...),
    shares: int = Form(...),
    reason: str = Form(...),
    notes: str | None = Form(None),
    # Phase 13 T3.SB2 T-B.2.3 — exit auto-fill hidden audit anchors emitted
    # by the form-render path (T-B.2.2 template additions). Defaults ""/None
    # so legacy callers (CLI tests, bare cURL, pre-Phase-13 form submits)
    # keep working — the POST handler infers fill_origin='operator_typed'
    # when these are absent. Per CLAUDE.md gotcha "Form-render hidden
    # anchors driving POST-time validation MUST round-trip" + forward-
    # binding lesson #13 BINDING. Per-candidate hidden inputs
    # (candidate_signature_hash_<i> + candidate_order_id_<i> + radio
    # candidate_index) are read from request.form() below since their
    # names are dynamic.
    schwab_source_value_json: str = Form(""),
    auto_fill_audit_at: str = Form(""),
    fill_origin_at_form_render: str = Form(""),
):
    import json as _json
    import math as _math
    from datetime import date as _date_cls

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

    # ------------------------------------------------------------------
    # Phase 13 T3.SB2 T-B.2.3 — read dynamic per-candidate hidden inputs
    # from the raw form (FastAPI's Form(...) bindings only cover known
    # keys; multi-partial provenance uses dynamic candidate_<n> names).
    # ------------------------------------------------------------------
    form_data = await request.form()
    candidate_index_raw = form_data.get("candidate_index")

    # Collect all candidate_signature_hash_<i> / candidate_order_id_<i>
    # pairs the form sent. Indices are 0-based; gaps OK (template emits
    # contiguous indices but defense-in-depth tolerates sparsity).
    candidate_sigs: dict[int, str] = {}
    candidate_orders: dict[int, str] = {}
    for key in form_data:
        if key.startswith("candidate_signature_hash_"):
            try:
                idx = int(key[len("candidate_signature_hash_"):])
            except ValueError:
                continue
            candidate_sigs[idx] = str(form_data.get(key) or "")
        elif key.startswith("candidate_order_id_"):
            try:
                idx = int(key[len("candidate_order_id_"):])
            except ValueError:
                continue
            candidate_orders[idx] = str(form_data.get(key) or "")

    # ------------------------------------------------------------------
    # Phase 13 T3.SB2 T-B.2.3 — fill_origin transition resolution.
    # Compare submitted exit_date / exit_price / shares against the
    # form-render anchor (``schwab_source_value_json`` JSON envelope).
    # Three outcomes:
    #   - No anchor (empty/missing JSON) → operator_typed; audit cols NULL.
    #   - Anchor matches submitted values → schwab_auto.
    #   - Anchor differs from submitted values → schwab_auto_then_operator_corrected.
    # Per spec §6.2 + §6.4 + dispatch brief BINDING.
    # ------------------------------------------------------------------
    resolved_fill_origin = "operator_typed"
    resolved_schwab_source_value_json: str | None = None
    resolved_operator_corrected_value_json: str | None = None
    resolved_auto_fill_audit_at: str | None = None

    # Normalize claim via strip() once so the consistency-check predicate +
    # any re-render path consult the same canonical value (mirrors entry_post
    # Codex R3 Minor #1 fix).
    fill_origin_at_form_render = fill_origin_at_form_render.strip()
    claimed_auto_fill = fill_origin_at_form_render in (
        "schwab_auto", "schwab_auto_then_operator_corrected",
    )

    # Helper: 400 + recovery-form re-render with anchor CLEARED (T3.SB1 R3
    # M#2 anchor-clear discipline BINDING). Recovery form is rebuilt from
    # build_exit_form_vm which re-runs the Schwab fetch (or fallbacks to
    # operator_typed); the bad submitted anchor is NOT echoed back so the
    # operator's next retry sees a fresh anchor instead of replaying the
    # tampered one.
    def _reject_anchor(error_message: str) -> HTMLResponse:
        vm_local = build_exit_form_vm(
            trade_id=trade_id, cfg=cfg, cache=cache, executor=executor,
        )
        if vm_local is not None:
            return templates.TemplateResponse(
                request, "partials/trade_exit_form.html.j2",
                {"vm": vm_local, "error_message": error_message},
                status_code=400,
            )
        return templates.TemplateResponse(
            request, "partials/trade_form_error.html.j2",
            {"error_message": error_message},
            status_code=400,
        )

    # 4-tier rejection ladder (mirrors entry_post pattern):
    #   (a) malformed JSON → 400 + clear
    #   (b) non-dict JSON → 400 + clear
    #   (c) dict missing required keys → 400 + clear
    #   (d) dict with invalid value shapes → 400 + clear
    #   plus claim-vs-anchor consistency.
    if schwab_source_value_json.strip():
        try:
            anchor_envelope = _json.loads(schwab_source_value_json)
        except (ValueError, TypeError):
            anchor_envelope = None

        # (a) malformed JSON + claim → 400
        if anchor_envelope is None and claimed_auto_fill:
            return _reject_anchor(
                "Trade exit rejected: fill_origin_at_form_render="
                f"{fill_origin_at_form_render!r} claims auto-fill "
                "provenance but schwab_source_value_json is malformed, "
                "unparseable, or not a JSON object. The form has been "
                "regenerated with a fresh Schwab fetch; please re-submit."
            )
        # (b) non-dict JSON + claim → 400
        if (
            anchor_envelope is not None
            and not isinstance(anchor_envelope, dict)
            and claimed_auto_fill
        ):
            return _reject_anchor(
                "Trade exit rejected: fill_origin_at_form_render="
                f"{fill_origin_at_form_render!r} claims auto-fill "
                "provenance but schwab_source_value_json is not a JSON "
                "object. The form has been regenerated; please re-submit."
            )
        # (c) dict missing one or more of the 3 required keys + claim → 400
        if (
            isinstance(anchor_envelope, dict)
            and claimed_auto_fill
            and not all(
                k in anchor_envelope
                for k in ("exit_date", "exit_price", "closed_shares")
            )
        ):
            return _reject_anchor(
                "Trade exit rejected: fill_origin_at_form_render="
                f"{fill_origin_at_form_render!r} claims auto-fill "
                "provenance but schwab_source_value_json is missing one or "
                "more required keys (exit_date, exit_price, closed_shares). "
                "The form has been regenerated; please re-submit."
            )
        # (d) dict with invalid value shapes + claim → 400
        if isinstance(anchor_envelope, dict) and claimed_auto_fill:
            v_exit_date = anchor_envelope.get("exit_date")
            v_exit_price = anchor_envelope.get("exit_price")
            v_closed_shares = anchor_envelope.get("closed_shares")
            exit_date_ok = isinstance(v_exit_date, str)
            if exit_date_ok:
                try:
                    _date_cls.fromisoformat(v_exit_date)
                except (TypeError, ValueError):
                    exit_date_ok = False
            exit_price_ok = (
                isinstance(v_exit_price, (int, float))
                and not isinstance(v_exit_price, bool)
                and _math.isfinite(float(v_exit_price))
            )
            shares_ok = (
                isinstance(v_closed_shares, int)
                and not isinstance(v_closed_shares, bool)
            )
            if not (exit_date_ok and exit_price_ok and shares_ok):
                return _reject_anchor(
                    "Trade exit rejected: fill_origin_at_form_render="
                    f"{fill_origin_at_form_render!r} claims auto-fill "
                    "provenance but schwab_source_value_json contains "
                    "invalid values (exit_date must be ISO YYYY-MM-DD; "
                    "exit_price must be finite numeric; closed_shares must "
                    "be an integer). The form has been regenerated; please "
                    "re-submit."
                )

        # Multi-partial: parse candidate_index + verify it maps to a
        # server-rendered candidate (its candidate_signature_hash_<i> hidden
        # input must be present). Single-fill case: candidate_index omitted
        # → treat as 0 (the template emits no radio at length 1; the form
        # may or may not emit candidate_signature_hash_0; both shapes OK).
        selected_index: int | None = None
        if isinstance(anchor_envelope, dict) and claimed_auto_fill:
            if candidate_index_raw is not None and str(
                candidate_index_raw,
            ).strip() != "":
                try:
                    selected_index = int(str(candidate_index_raw).strip())
                except ValueError:
                    return _reject_anchor(
                        "Trade exit rejected: candidate_index "
                        f"{candidate_index_raw!r} is not an integer. The "
                        "form has been regenerated; please re-submit."
                    )
                # Out-of-range: selected index has no matching
                # candidate_signature_hash_<i> hidden input.
                if selected_index not in candidate_sigs:
                    return _reject_anchor(
                        "Trade exit rejected: candidate_index="
                        f"{selected_index} does not map to a server-"
                        "rendered candidate (no candidate_signature_hash_"
                        f"{selected_index} hidden input). The form has "
                        "been regenerated; please re-submit."
                    )
            elif candidate_sigs:
                # candidate_index omitted but per-candidate hidden inputs
                # ARE present (single-fill case): default to index 0 IF
                # present, otherwise treat as "no selection" (single-fill
                # without per-candidate hidden inputs is also legal).
                selected_index = 0 if 0 in candidate_sigs else None

        # Provenance-stamping branch — fires only when both halves of the
        # consistency check agree (valid dict envelope + claim present).
        # Mirrors entry_post Codex R4 Major #1 gate.
        if isinstance(anchor_envelope, dict) and claimed_auto_fill:
            # Codex R1 Critical #1 + Major #1 fix — server-side
            # authoritative envelope. The ``candidates_map`` (added by
            # ``resolve_exit_auto_fill`` at form render) is keyed by
            # signature_hash and carries the per-candidate authoritative
            # date/price/quantity/order_id. Two failure modes closed:
            #   (a) Major #1 forgery surface — a tampered POST claiming
            #       an arbitrary candidate_signature_hash that does NOT
            #       appear in the server-stamped map is rejected with 400.
            #   (b) Critical #1 broken radio selection — the template's
            #       radio inputs do NOT rebind visible exit_date /
            #       exit_price / shares form fields client-side. When the
            #       operator picks a non-default candidate without editing
            #       visible inputs, the submitted visible values are the
            #       MOST-RECENT default's values (which differ from the
            #       authoritative selected candidate). The comparator
            #       below treats that delta as an operator edit and
            #       persists fill_origin='schwab_auto_then_operator_corrected'
            #       with the visible-input values — semantically honest
            #       given that the form has no client-side rebind. When
            #       the operator DOES manually edit visible inputs to
            #       match the selected candidate (or when the operator
            #       leaves the default candidate radio unchanged), the
            #       comparator records fill_origin='schwab_auto' and the
            #       authoritative selected-candidate values are persisted.
            candidates_map = anchor_envelope.get("candidates_map")
            if not isinstance(candidates_map, dict):
                candidates_map = {}

            # When a multi-partial selection is present, verify the
            # operator's submitted signature_hash maps to a server-stamped
            # candidate in ``candidates_map``. This is the Major #1
            # forgery-rejection gate. ``selected_index`` was already
            # validated to be in ``candidate_sigs`` above; here we go one
            # step further and confirm the hash itself is server-issued.
            submitted_sig_hash: str | None = None
            authoritative_selected: dict | None = None
            if selected_index is not None and selected_index in candidate_sigs:
                submitted_sig_hash = candidate_sigs[selected_index]
                if (
                    candidates_map
                    and submitted_sig_hash not in candidates_map
                ):
                    return _reject_anchor(
                        "Trade exit rejected: candidate_signature_hash_"
                        f"{selected_index}={submitted_sig_hash!r} does not "
                        "map to a server-stamped candidate in the auto-fill "
                        "envelope. The form has been regenerated; please "
                        "re-submit."
                    )
                if candidates_map:
                    authoritative_selected = candidates_map.get(
                        submitted_sig_hash,
                    )

            # Compute the comparison baseline. When the operator made a
            # multi-partial selection with a server-validated authoritative
            # entry, compare visible inputs against THAT candidate (not
            # the envelope's default chosen). Otherwise (single-fill case
            # or selection without candidates_map) fall back to the
            # envelope's top-level exit_date / exit_price / closed_shares.
            if authoritative_selected is not None:
                cmp_date = authoritative_selected.get("date")
                cmp_price = authoritative_selected.get("price")
                cmp_shares = authoritative_selected.get("quantity")
            else:
                cmp_date = anchor_envelope.get("exit_date")
                cmp_price = anchor_envelope.get("exit_price")
                cmp_shares = anchor_envelope.get("closed_shares")
            try:
                cmp_price_float = (
                    float(cmp_price) if cmp_price is not None else None
                )
            except (TypeError, ValueError):
                cmp_price_float = None
            try:
                cmp_shares_int = (
                    int(cmp_shares) if cmp_shares is not None else None
                )
            except (TypeError, ValueError):
                cmp_shares_int = None
            exit_date_diff = cmp_date != exit_date
            # Codex R4 Major #2 fix — price comparison must match the
            # template's rendering precision. The form renders
            # ``exit_price`` via ``{{ '%.2f' | format(vm.exit_price) }}``
            # (``swing/web/templates/partials/trade_exit_form.html.j2``
            # line 102), so authoritative candidate prices with 3+ decimal
            # precision (e.g. VWAP across multi-leg execution-grain fills:
            # 120.505) are TRUNCATED-via-banker's-rounding to 2 decimals
            # before the operator sees them. Submitting the rendered
            # 2-decimal value back used to flip ``fill_origin`` to
            # ``schwab_auto_then_operator_corrected`` against a 1e-9
            # epsilon, even though the operator made NO actual edit
            # (0.005 > 1e-9). Compare at the template's rendering
            # precision (2 decimals) instead — ``round(_, 2) != round(_, 2)``
            # exactly matches what the form can render.
            price_diff = (
                cmp_price_float is None
                or round(cmp_price_float, 2) != round(exit_price, 2)
            )
            shares_diff = (
                cmp_shares_int is None or cmp_shares_int != shares
            )
            if exit_date_diff or price_diff or shares_diff:
                resolved_fill_origin = "schwab_auto_then_operator_corrected"
                resolved_operator_corrected_value_json = _json.dumps(
                    {
                        "exit_date": exit_date,
                        "exit_price": exit_price,
                        "closed_shares": shares,
                    },
                    sort_keys=True,
                )
            else:
                resolved_fill_origin = "schwab_auto"

            # Re-stamp envelope with operator-selection provenance (multi-
            # partial threading per dispatch brief). The persisted envelope
            # extends the form-render envelope with:
            #   - ``selected_candidate_signature_hash`` (chosen candidate)
            #   - ``selected_candidate_order_id`` (chosen candidate's order)
            #   - ``other_candidate_signature_hashes`` (audit history)
            # Architectural decision: keep the original envelope keys
            # verbatim + ADD provenance fields rather than rebuilding so
            # downstream consumers reading e.g. ``schwab_order_id`` from
            # the legacy single-fill shape continue to work.
            extended = dict(anchor_envelope)
            if selected_index is not None and selected_index in candidate_sigs:
                extended["selected_candidate_signature_hash"] = (
                    candidate_sigs[selected_index]
                )
                # Codex R2 Major #2 fix — persist authoritative ``order_id``
                # from the server-stamped ``candidates_map`` envelope, NOT
                # the client-submitted ``candidate_order_id_<i>`` hidden
                # input. A tampered POST could submit a valid
                # signature_hash but a forged candidate_order_id_<i>; the
                # envelope's authoritative entry has already been
                # validated by the M1 hash-membership check above. Falls
                # back to the client-submitted value only when
                # candidates_map is empty (legacy envelopes lacking the
                # map — pre-Critical-#1-fix envelopes; covered by R2 M4
                # legacy-fill fallback territory).
                if authoritative_selected is not None:
                    auth_order_id = authoritative_selected.get("order_id")
                    extended["selected_candidate_order_id"] = (
                        auth_order_id if isinstance(auth_order_id, str)
                        and auth_order_id else None
                    )
                else:
                    extended["selected_candidate_order_id"] = (
                        candidate_orders.get(selected_index, "") or None
                    )
                others = sorted(
                    sig for idx, sig in candidate_sigs.items()
                    if idx != selected_index
                )
                # Always emit the key for audit clarity (empty list when
                # single-fill case). Wrapping audit history is the V1
                # contract per the dispatch brief.
                extended["other_candidate_signature_hashes"] = others
                # Codex R3 Major #1 fix — rewrite top-level
                # ``schwab_order_id`` to reflect the SCHWAB ORDER WHOSE
                # VALUES WERE ACTUALLY PERSISTED.
                #
                # The form-render envelope's top-level ``schwab_order_id``
                # is the DEFAULT (most-recent) candidate's order_id (per
                # ``resolve_exit_auto_fill`` at
                # ``swing/trades/exit_auto_fill.py``). When the operator
                # picks a NON-DEFAULT candidate via radio AND manually
                # edits visible inputs to match the picked candidate's
                # values, ``resolved_fill_origin == 'schwab_auto'`` AND
                # the persisted fill row carries the SELECTED candidate's
                # values — but pre-fix the top-level ``schwab_order_id``
                # still pointed at the form-render default.
                #
                # The future-fetch dedupe path in
                # ``swing/web/view_models/trades.py`` (per Codex R2 M#3
                # fix) reads top-level ``schwab_order_id`` to exclude
                # already-recorded fills. Pre-fix this excluded the WRONG
                # order_id (the default which was never persisted) and
                # FAILED to exclude the SELECTED order_id (which WAS
                # persisted), letting the operator re-record the same
                # Schwab order as a duplicate fill.
                #
                # Fix scope: ONLY rewrite when ``fill_origin ==
                # 'schwab_auto'`` AND ``authoritative_selected is not
                # None``. The ``schwab_auto_then_operator_corrected``
                # branch keeps the existing top-level top-level order_id —
                # the operator either (a) over-rode the default with
                # custom values, or (b) picked a non-default candidate
                # without rebinding visible inputs (so the default's
                # values were persisted). In both sub-cases the persisted
                # values trace back to the default's "source" candidate,
                # which the existing top-level order_id correctly
                # represents.
                if (
                    resolved_fill_origin == "schwab_auto"
                    and authoritative_selected is not None
                ):
                    # Codex R4 Major #1 fix — when the authoritative
                    # selected candidate's ``order_id`` is None (e.g.,
                    # MARKET fills without a broker order_id, or mapper
                    # edge cases), the pre-R4 R3 M#1 rewrite SILENTLY
                    # SKIPPED, leaving top-level ``schwab_order_id`` at the
                    # form-render default (most-recent candidate's
                    # order_id). The future-fetch dedupe path in
                    # ``view_models/trades.py`` then read the wrong
                    # order_id (the default which was never persisted) and
                    # ``order_id_found=True`` (just for the wrong order),
                    # preventing the fallback (date, price, qty) tuple
                    # match from firing — letting the operator re-record
                    # the same fill as a duplicate.
                    #
                    # Fix: pop top-level ``schwab_order_id`` when the
                    # authoritative selected has no usable order_id. The
                    # VM-side dedupe will see no usable order_id for this
                    # fill and correctly fall through to the (date, price,
                    # qty) tuple fallback (R2 M#4 behavior).
                    auth_top_order_id = authoritative_selected.get("order_id")
                    if isinstance(auth_top_order_id, str) and auth_top_order_id:
                        extended["schwab_order_id"] = auth_top_order_id
                    else:
                        extended.pop("schwab_order_id", None)
            resolved_schwab_source_value_json = _json.dumps(
                extended, sort_keys=True,
            )
            # ``... or None`` not ``... or ''`` (Phase 6 gotcha).
            resolved_auto_fill_audit_at = auto_fill_audit_at or None
    elif claimed_auto_fill:
        # Empty anchor with claim → 400 (claim cannot be trusted without
        # anchor). Mirrors entry_post Codex R1 Major #1 fix.
        return _reject_anchor(
            "Trade exit rejected: fill_origin_at_form_render="
            f"{fill_origin_at_form_render!r} claims auto-fill provenance "
            "but schwab_source_value_json is empty. Re-render the form "
            "to recover."
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
        # Phase 13 T3.SB2 T-B.2.3 — auto-fill audit columns persisted on
        # the fills row by ``record_exit`` → ``insert_fill_with_event``.
        fill_origin=resolved_fill_origin,
        schwab_source_value_json=resolved_schwab_source_value_json,
        operator_corrected_value_json=resolved_operator_corrected_value_json,
        auto_fill_audit_at=resolved_auto_fill_audit_at,
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
    vm = build_review_vm(
        trade_id=trade_id, cfg=cfg,
        ohlcv_cache=request.app.state.ohlcv_cache,
    )
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
    """Phase 13 T3.SB3 (T-B.3.4) — persist period review.

    Audit envelope ``auto_populated_field_keys_json`` is SERVER-RECOMPUTED
    at POST time from the review's period (NOT trusted from a hidden form
    input). This honors the Phase 8 R2-R5 server-stamping family + L10
    LOCK + CLAUDE.md hidden-audit-field-as-tampering-surface gotcha:
    accepting the value from the form would let an operator submit a
    fabricated envelope. Recomputing from the canonical period helpers at
    POST time matches what was actually shown at form-render time (the
    GET-side build_cadence_complete_vm uses the same helpers); any
    GET→POST drift surfaces in the audit row faithfully.
    """
    import json as _json
    from datetime import date as _date

    from fastapi.responses import Response

    from swing.data.repos.review_log import complete_review_atomic, get
    from swing.trades.review import (
        get_period_cohort_health_deltas,
        get_period_lessons_summary,
        get_period_mistake_tag_aggregate,
    )
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
        # Server-recompute the audit envelope from the canonical period
        # helpers. Mirrors build_cadence_complete_vm's GET-side logic so
        # the persisted envelope reflects what the operator actually saw.
        ps = _date.fromisoformat(review.period_start)
        pe = _date.fromisoformat(review.period_end)
        period_length_days = (pe - ps).days + 1
        prior_pe = ps - timedelta(days=1)
        prior_ps = prior_pe - timedelta(days=period_length_days - 1)
        period_lessons = get_period_lessons_summary(
            conn, period_start=ps, period_end=pe,
        )
        period_mistake_agg = get_period_mistake_tag_aggregate(
            conn, period_start=ps, period_end=pe,
        )
        period_cohort_deltas = get_period_cohort_health_deltas(
            conn,
            current_period_start=ps,
            current_period_end=pe,
            prior_period_start=prior_ps,
            prior_period_end=prior_pe,
        )
        recomputed_keys: list[str] = []
        if period_lessons:
            recomputed_keys.append("primary_lesson")
        if period_mistake_agg:
            recomputed_keys.append("most_common_mistake_tags")
        if period_cohort_deltas:
            recomputed_keys.append("cohort_health_summary")
        audit_envelope = _json.dumps(recomputed_keys) if recomputed_keys else None
        # ``... or None`` per Phase 6 deviation #3 CLAUDE.md gotcha —
        # nullable JSON column rejects empty string under future
        # validation; persist NULL when no auto-fill keys produced.
        complete_review_atomic(
            conn, review_id=review_id,
            completed_date=_date.today().isoformat(),
            duration_minutes=duration_minutes,
            primary_lesson=primary_lesson,
            next_period_focus=next_period_focus,
            auto_populated_field_keys_json=audit_envelope or None,
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
