"""Trade form view-models + builders for Phase 3b."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Fill, ReviewLog, Trade
from swing.data.repos.cash import list_cash
from swing.data.repos.fills import (
    list_fills_for_trade,
)
from swing.data.repos.trades import (
    TradeActivitySummary,
    get_trade,
    list_open_trades,
    list_trades_with_activity_in_period,
)
from swing.data.repos.watchlist import list_active_watchlist
from swing.recommendations.sizing import compute_shares
from swing.trades.entry import entry_rationale_options
from swing.trades.equity import current_equity
from swing.trades.exit import ExitReason
from swing.trades.review import ReviewPriors
from swing.trades.stop_adjust import stop_adjust_rationale_options
from swing.web.chart_scope import latest_completed_pipeline_run
from swing.web.price_cache import PriceCache

# 3e.16 — re-export TradeActivitySummary under the VM-layer name. The
# helper's dataclass is the canonical shape used by the cadence-completion
# template; no separate VM dataclass is needed (would duplicate the locked
# field set in two places). Template-side imports use TradeSummaryVM.
TradeSummaryVM = TradeActivitySummary

# Phase 7 Sub-C T1: Active-trade lifecycle states (exit-form + stop-form
# preconditions). Mirrors `_ACTIVE_STATES_SQL` in repos/trades.py.
_ACTIVE_STATES = ("entered", "managing", "partial_exited")

# Phase 7 Sub-C T1 — display labels for the trade-detail page state badge.
STATE_BADGE_LABELS: dict[str, str] = {
    "entered": "Entered",
    "managing": "Managing",
    "partial_exited": "Partial",
    "closed": "Closed",
    "reviewed": "Reviewed",
}

_VALID_ORIGINS = ("watchlist", "hyp-recs")


@dataclass(frozen=True)
class _ExitShape:
    """Minimal Exit-attribute surface required by
    ``compute_actual_realized_R_effective`` (``trade_id``, ``shares``,
    ``r_multiple``).

    Phase 7 Sub-C T1: the legacy ``Exit`` dataclass is removed in Sub-A;
    consumers that still need the attribute surface (review math, equity
    math) reconstruct the missing PnL/R fields on-the-fly via
    ``swing/trades/derived_metrics.py``. C.10 will refactor equity.py to
    consume Fill directly; this VM-local adapter survives until then.
    """
    trade_id: int
    exit_date: str
    exit_price: float
    # NOTE: shares is typed `int` here (legacy Exit shape) even though the
    # underlying Fill.quantity is REAL. Current production paths produce only
    # integer-share fills (compute_shares() returns int; CLI/web entry +
    # trim/exit submit shares: int), so the int(fill.quantity) cast in the
    # adapter (_fill_to_exit_like) does not currently truncate any real
    # data. Fractional-share support is forward-compat work (see Phase 7
    # Sub-C Codex R1 Major 3 disposition). When fractional support lands,
    # replace the int truncation here AND in 6 sibling _ExitShape
    # adapters (cli.py, journal/stats.py, recommendations/hypothesis.py,
    # research/parity/fetcher.py, data/repos/review_log.py,
    # pipeline/runner.py) with float passthrough + audit downstream
    # consumers (current_equity, compute_actual_realized_R_effective,
    # journal aggregations).
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None


def _fill_to_exit_like(fill: Fill, trade: Trade) -> _ExitShape:
    """Convert a non-entry Fill into an Exit-shape adapter for review math.

    ``r_multiple`` math mirrors the
    ``swing.data.repos.trades._fill_row_to_exitlike`` shim so that callers
    migrating off the shim see the same numeric output.
    """
    from swing.trades.derived_metrics import (
        initial_risk_per_share,
        r_multiple,
        realized_pnl,
    )

    rps = initial_risk_per_share(
        entry_price=trade.entry_price, initial_stop=trade.initial_stop,
    )
    pnl = realized_pnl(
        entry_price=trade.entry_price, exit_price=fill.price,
        quantity=fill.quantity,
    )
    rmult: float | None
    if rps == 0 or fill.quantity == 0:
        rmult = None
    else:
        rmult = r_multiple(
            realized_pnl=pnl, initial_risk_per_share=rps,
            quantity=fill.quantity,
        )
    exit_date = (
        fill.fill_datetime.split("T")[0]
        if "T" in fill.fill_datetime else fill.fill_datetime
    )
    return _ExitShape(
        trade_id=fill.trade_id,
        exit_date=exit_date,
        exit_price=float(fill.price),
        shares=int(fill.quantity),
        reason=fill.reason,
        realized_pnl=pnl,
        r_multiple=rmult,
    )


def _list_all_exitshape_via_fills(conn) -> list[_ExitShape]:
    """C.10 migration helper: produces the ExitLike collection that
    ``list_all_exits(conn)`` previously returned, but sourced from fills
    filtered to non-entry actions. Mirrors the C.9 helpers in
    ``view_models/dashboard.py`` and ``view_models/journal.py``; the
    adapter dies in a future cleanup phase when ``equity.py`` refactors
    to consume Fill directly.
    """
    from swing.data.repos.fills import list_all_fills
    from swing.data.repos.trades import list_closed_trades

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
            continue  # orphan fill — skip (parent trade missing)
        out.append(_fill_to_exit_like(f, trade))
    return out


@dataclass(frozen=True)
class AuditEntry:
    """One row of the trade-detail audit log (event_type='pre_trade_edit').

    Phase 7 spec §11.4: rendered chronologically on the trade-detail page
    when an operator edits a pre-trade decision field via the (currently
    unimplemented) edit surface. V1 has no UI write path; the read path
    here is forward-compatible with the planned edit endpoint.
    """
    ts: str
    field: str
    old_value: str | None
    new_value: str | None
    reason: str | None


def _decode_emotional_state(raw: str | None) -> tuple[str, ...]:
    """Decode the JSON-list TEXT stored in trades.emotional_state_pre_trade
    (spec §1.2 multi-select; entry route writes via json.dumps in
    swing/web/routes/trades.py + swing/cli.py) to a tuple of strings.

    Returns () for NULL, empty string, or malformed JSON — the template
    renders an empty cell rather than crashing on storage-format anomalies.
    Codex R3 Minor 1.
    """
    if not raw:
        return ()
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return ()
    if not isinstance(decoded, list):
        return ()
    return tuple(str(x) for x in decoded if x)


def _coerce_origin(raw: str | None) -> Literal["watchlist", "hyp-recs"]:
    """Whitelist-coerce ?origin= query-param / form-payload value.

    Unknown / missing → 'watchlist' (preserves existing behavior).

    Spec §3.8b.1 R3-Major-1.
    """
    if raw in _VALID_ORIGINS:
        return raw  # type: ignore[return-value]
    return "watchlist"


@dataclass(frozen=True)
class TradeEntryFormVM:
    ticker: str
    entry_date: str                  # today, ISO
    entry_price: float               # from live price cache
    initial_stop: float              # from watchlist_initial_stop_target if present, else 0.0
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    suggested_shares: int
    risk_dollars: float
    risk_pct: float
    soft_warn_threshold: int
    hard_cap: int
    open_count: int
    force: bool = False
    rationale: str = ""       # preserved from prior submit on duplicate/drift
    notes: str = ""           # preserved from prior submit on duplicate/drift
    input_shares: int = 0     # user's submitted shares on drift-retry; 0 = no override
    # Closed-taxonomy rationale options (value, display_label) pairs — T4.
    rationale_options: tuple[tuple[str, str], ...] = ()
    # Phase 5 spec §3.6 — chart-pattern algo display + override snapshot.
    # ``chart_pattern_algo_evaluated`` is True only when a non-error
    # classification row exists for this ticker under the latest
    # complete pipeline_run; the template gates the override dropdown
    # on this flag (out-of-scope tickers see the "Not classified" stub
    # so the operator cannot submit an override that the CLI parity
    # gate would have refused — spec §1.1 #5 + §3.7 R1 C1).
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_algo_evaluated: bool = False
    chart_pattern_algo_computed_at: str | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
    # Task 6 — sector/industry snapshot resolved at form-render time from
    # the candidate row anchored on ``latest_evaluation_run_id()`` (same
    # helper the dashboard candidates_by_ticker binding uses, so the form
    # sees the same run). Hidden inputs flow these through POST →
    # EntryRequest → record_entry. Empty strings = off-pipeline entry
    # (graceful degradation per brief §5.8).
    sector: str = ""
    industry: str = ""
    # Phase 9 Sub-bundle D Codex R2 Major #1 — explicit evaluation_run_id
    # anchor that carries the form-render's candidate binding through
    # to POST validation. Mirrors chart_pattern's
    # ``chart_pattern_classification_pipeline_run_id`` hidden-anchor
    # pattern (Phase 5 spec §3.6). Form-render binds to the candidate
    # the operator is shown; POST validates ``(eval_run_id, ticker)``
    # against that exact row so a pipeline run landing between GET +
    # POST cannot cause false-reject (form's snapshot drifts from
    # new authoritative) or false-accept (tampered POST matches the
    # new row instead of the one the operator saw). None when the
    # form-render found no cached candidate — POST treats absence as
    # the bare-cURL backward-compat skip path.
    sector_industry_evaluation_run_id: int | None = None
    # Spec §3.8b — origin discriminator. Whitelist-validated at the
    # request boundary by ``_coerce_origin``; unknown values default
    # to 'watchlist' so existing watchlist callers (no ?origin=) keep
    # working. Threading: GET ?origin= → build_entry_form_vm → VM
    # field → template parameterizes colspan + Cancel target. POST
    # round-trip survival ships in Task 8 via a hidden form field.
    origin: Literal["watchlist", "hyp-recs"] = "watchlist"
    # Spec §3.8b.4 R4-Major-2 — when origin=hyp-recs, this is the
    # pipeline_runs.finished_ts of the binding pipeline run; rendered
    # in the freshness footer ("Candidate context as of pipeline
    # finished {ISO}"). Wording is deliberately scoped to "candidate
    # context" — the form's entry_price still comes from live
    # PriceCache / wl_entry.last_close (NOT the pipeline snapshot),
    # so the footer must NOT imply live-price freshness. None for
    # watchlist origin (no footer rendered).
    pipeline_finished_at: str | None = None
    # Phase 4.5 — Hypothesis recommendation label resolved at form-render
    # time via swing.recommendations.hypothesis_prefill. Snapshot-at-
    # entry-surface (ToCToU fix per spec §3.6 / Phase 5 lesson): the
    # value flows through a hidden form field to the POST handler and
    # persists AS-IS via record_entry's canonicalize_hypothesis_label
    # boundary. None when the ticker has no active recommendation in
    # the latest evaluation run — template renders "(none)" display
    # and emits an empty hidden input value.
    hypothesis_label: str | None = None
    # Phase 7 Sub-C C.4 — draft_* preservation fields for the 18 pre-trade
    # required fields (spec §11.1). Mirrors the rationale/notes
    # preservation pattern: when the MissingPreTradeFieldsException catch
    # path re-renders the form, ``dataclasses.replace`` populates these
    # so the operator's typed values round-trip back into the inputs
    # (textarea body / input value attr / select selected / checkbox
    # checked). All default to safe empty values so the GET-form path
    # renders a clean form (no draft preservation needed there).
    draft_thesis: str = ""
    draft_why_now: str = ""
    draft_invalidation_condition: str = ""
    draft_expected_scenario: str = ""
    draft_premortem_technical: str = ""
    draft_premortem_market_sector: str = ""
    draft_premortem_execution: str = ""
    draft_premortem_additional: str = ""
    # event_risk_present / gap_risk_present arrive as int|None from the
    # form ("0"/"1" → 0/1; missing → None). Carry through as None so
    # the template renders neither checkbox checked on a GET.
    draft_event_risk_present: int | None = None
    draft_event_handling: str = ""
    draft_event_type: str = ""
    draft_event_date: str = ""
    draft_gap_risk_present: int | None = None
    draft_gap_risk_handling: str = ""
    # emotional_state_pre_trade is multi-select; carry the submitted set
    # as a tuple of strings so the template can ``in`` -test each
    # checkbox value. Empty tuple = no draft (GET path / first POST).
    draft_emotional_state_pre_trade: tuple[str, ...] = ()
    draft_manual_entry_confidence: str = ""
    draft_market_regime: str = ""
    draft_catalyst: str = ""
    draft_catalyst_other_description: str = ""
    # Phase 7 Sub-C C.4 — per-field error markers. Populated only on the
    # MissingPreTradeFieldsException re-render path (spec §11.1 + §9.3);
    # empty frozenset on GET / non-missing-field error paths so the
    # template never renders an error class on a clean form. The template
    # tests `{% if 'thesis' in vm.missing_fields %}` per input.
    missing_fields: frozenset[str] = frozenset()
    # Phase 13 T3.SB1 — entry auto-fill via Schwab Trader API at form
    # render (spec §6.1 + plan §G.2 T-B.1.3). The 5 auto_fill_* fields
    # carry the resolution result from
    # ``swing.trades.entry_auto_fill.resolve_entry_auto_fill``. When the
    # resolution is short-circuited (sandbox / DEGRADED / no account_hash /
    # credentials missing / Schwab error) OR yields no candidates, all
    # auto_fill_* fields stay None except ``auto_fill_advisory_text`` and
    # ``auto_fill_fill_origin``. The template gates display + hidden-input
    # emission on ``vm.auto_fill_schwab_source_value_json is not none``.
    #
    # ``fill_origin`` here is the form-render-time stamp (always
    # 'schwab_auto' on populated, 'operator_typed' otherwise). The POST
    # handler (T-B.1.4) re-derives the persisted ``fill_origin`` by
    # comparing the submitted entry_date / entry_price / shares against
    # the ``auto_fill_schwab_source_value_json`` anchor.
    auto_fill_kind: str = "operator_typed"
    auto_fill_fill_origin: str = "operator_typed"
    auto_fill_entry_date: str | None = None
    auto_fill_entry_price: float | None = None
    auto_fill_shares: int | None = None
    auto_fill_advisory_text: str | None = None
    auto_fill_schwab_source_value_json: str | None = None
    auto_fill_audit_at: str | None = None
    # Phase 13 T3.SB1 dispatch brief §5 watch item 7 + plan §G.2 T-B.1.3
    # forward-binding lesson #12 — base-layout VM banner pin (defense-in-
    # depth for any future full-page render path that extends
    # ``base.html.j2``; the current /trades/entry/form route returns a
    # row-partial fragment that does NOT extend the base layout, so the
    # banner-pin fields are not currently rendered — but the VM populates
    # them anyway so future plumbing changes don't trip the CLAUDE.md
    # "base.html.j2 is shared — new vm.foo field requires adding to
    # EVERY base-layout VM" gotcha). Defaults match the BaseLayoutVM
    # canonical values.
    unresolved_material_discrepancies_count: int = 0
    recent_multi_leg_auto_correction_count: int = 0
    banner_resolve_link: str | None = None
    # Phase 13 T2.SB6c T-A.6c.4 §C.5 anchor-threading (OQ-12 CLOSURE):
    # 3 hidden form anchors that propagate the pipeline-origin
    # pattern_evaluations row through the form submission to the POST
    # handler's 5-tier rejection ladder + claim-consistency gate.
    #
    # ``pattern_evaluation_id``: id of the pattern_evaluations row that
    #   matches (pipeline_run_id, ticker) at form-render time. None when
    #   the form-render found no matching row (manual_off_pipeline path).
    # ``claimed_pattern_evaluation_anchor``: True when the form-render
    #   resolved an anchor; round-trips through the form so POST can
    #   detect tampering (anchor present without claim OR vice-versa).
    # ``pipeline_run_id_at_form_render``: the pipeline_runs.id under
    #   which the form found the anchor; POST validates this matches
    #   the evaluation row's pipeline_run_id (R5 MAJOR #1 / R6 MAJOR #3
    #   missing-anchor symmetry).
    pattern_evaluation_id: int | None = None
    claimed_pattern_evaluation_anchor: bool = False
    pipeline_run_id_at_form_render: int | None = None


def build_entry_form_vm(
    *, ticker: str, cfg: Config, cache: PriceCache, executor,
    origin: str = "watchlist",
    explicit_pattern_evaluation_id: int | None = None,
    explicit_pipeline_run_id_at_form_render: int | None = None,
) -> TradeEntryFormVM:
    """Build entry-form VM from: watchlist row, live price, open
    positions, equity, and (Phase 5) the chart-pattern classification
    snapshot for this ticker under the latest complete pipeline run.

    Spec §4.2 + §3.6. Cache resolution happens ONCE here at the
    entry-surface — POST handler persists the snapshot AS-IS via
    ``record_entry`` (no re-resolve at submit). Bug-7-family anchor
    discipline: classification reads bind to the most-recent COMPLETE
    pipeline_run via the single-round-trip
    ``SELECT id, evaluation_run_id`` pattern; the ``id`` IS the
    parent ``pipeline_run_id`` by construction.
    """
    coerced_origin = _coerce_origin(origin)
    ticker = ticker.upper()
    cls = None
    pipeline_finished_at: str | None = None
    # Phase 13 T3.SB1 — banner-pin counters (read inside `with conn:` block
    # below; defaults preserved if discrepancies-helper not yet plumbed).
    unresolved_material_count: int = 0
    recent_multi_leg_count: int = 0
    banner_resolve_link: str | None = None
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            wl = list_active_watchlist(conn)
            wl_entry = next((w for w in wl if w.ticker == ticker), None)
            open_trades = list_open_trades(conn)
            # C.10: migrated off ``list_all_exits`` shim. ``current_equity``
            # consumes ExitLike-shape duck-typed input; the local helper
            # adapts non-entry fills via the C.9/C.10 _ExitShape pattern.
            exits = _list_all_exitshape_via_fills(conn)
            cash_movements = list_cash(conn)
            # Phase 4 (Task 4): consume `latest_completed_pipeline_run`.
            # Chart-pattern ALWAYS binds to the binding's run_id (both
            # origins). hyp-recs origin ALSO uses binding.evaluation_run_id
            # as the sector/industry/pivot/initial_stop anchor (Task 9
            # R4-Major-2 — matches build_hyp_recs_expanded so the form
            # does not split anchors across columns). The `id DESC`
            # tiebreaker is centralized in the helper.
            binding = latest_completed_pipeline_run(conn)
            pipeline_run_id = binding.run_id if binding else None
            pipeline_eval_id = binding.evaluation_run_id if binding else None
            pipeline_finished_at = binding.finished_ts if binding else None
            if pipeline_run_id is not None:
                from swing.data.repos.pattern_classifications import (
                    get_classification,
                )
                cls = get_classification(
                    conn, pipeline_run_id=pipeline_run_id, ticker=ticker,
                )
            # Task 6 + Task 9 — sector/industry/pivot/initial_stop snapshot.
            # Anchor selection branches on origin:
            #   - hyp-recs: bind to the pipeline-bound eval (matches the
            #     hyp-recs expansion's anchor so candidate-derived reads
            #     don't split across columns; closes Task 9 R4-Major-2).
            #   - watchlist: preserve the existing canonical
            #     ``latest_evaluation_run_id()`` helper (R1 Codex Major 4)
            #     so the watchlist surface keeps its existing anchor
            #     contract — backward compat.
            # Chart-pattern read above stays bound to ``pipeline_runs`` for
            # BOTH origins (existing behavior; chart-pattern requires a
            # completed pipeline).
            #
            # Codex R3 MAJOR #1 closure (mixed-context trade defense): for
            # the hyp-recs origin, when the caller passes BOTH explicit
            # ``pattern_evaluation_id`` AND
            # ``pipeline_run_id_at_form_render`` query params AND the PE
            # row's pipeline_run_id matches the submitted run anchor,
            # the candidate-snapshot reads MUST anchor on the EXPLICIT
            # run's evaluation_run_id — NOT on
            # ``latest_completed_pipeline_run()``. Otherwise the form
            # binds PE_1 (run-1) but reads sector/industry/pivot from
            # run-2's candidate snapshot for the same ticker, yielding
            # a "mixed-context" persisted trade (old PE backlink + new
            # candidate-derived order defaults). Validation failure
            # (run mismatch, ticker mismatch, PE missing) preserves the
            # legacy permissive fallback to latest-completed-run snapshot
            # so the operator never sees an empty form on tampered URLs.
            cand_sector = ""
            cand_industry = ""
            cand_pivot: float | None = None
            cand_initial_stop: float | None = None
            # Resolve the explicit-anchor's evaluation_run_id up-front so
            # candidate-snapshot reads can anchor on the operator-
            # witnessed run when validation succeeds.
            explicit_anchor_validates = False
            explicit_anchor_eval_run_id: int | None = None
            if (
                coerced_origin == "hyp-recs"
                and explicit_pattern_evaluation_id is not None
                and explicit_pipeline_run_id_at_form_render is not None
            ):
                _anchor_row = conn.execute(
                    "SELECT pipeline_run_id, ticker FROM "
                    "pattern_evaluations WHERE id = ?",
                    (int(explicit_pattern_evaluation_id),),
                ).fetchone()
                if _anchor_row is not None:
                    _pe_run = int(_anchor_row[0])
                    _pe_ticker = (_anchor_row[1] or "").upper()
                    if (
                        _pe_run
                        == int(explicit_pipeline_run_id_at_form_render)
                        and _pe_ticker == ticker.upper()
                    ):
                        explicit_anchor_validates = True
                        _pr_row = conn.execute(
                            "SELECT evaluation_run_id FROM pipeline_runs "
                            "WHERE id = ?",
                            (_pe_run,),
                        ).fetchone()
                        if _pr_row is not None and _pr_row[0] is not None:
                            explicit_anchor_eval_run_id = int(_pr_row[0])
            if coerced_origin == "hyp-recs":
                if (
                    explicit_anchor_validates
                    and explicit_anchor_eval_run_id is not None
                ):
                    sector_eval_id = explicit_anchor_eval_run_id
                else:
                    sector_eval_id = pipeline_eval_id
            else:
                from swing.web.view_models.dashboard import (
                    latest_evaluation_run_id,
                )
                sector_eval_id = latest_evaluation_run_id(conn)
            cand_eval_id_for_si_anchor: int | None = None
            if sector_eval_id is not None:
                cand_row = conn.execute(
                    """SELECT sector, industry, pivot, initial_stop FROM candidates
                       WHERE evaluation_run_id = ? AND ticker = ?""",
                    (sector_eval_id, ticker),
                ).fetchone()
                if cand_row is not None:
                    cand_sector = cand_row[0] or ""
                    cand_industry = cand_row[1] or ""
                    cand_pivot = cand_row[2]
                    cand_initial_stop = cand_row[3]
                    # Phase 9 Bundle D Codex R2 Major #1 — capture the
                    # exact eval anchor the form is rendering with so
                    # POST validation reaches the same authoritative row.
                    cand_eval_id_for_si_anchor = sector_eval_id
            # Phase 4.5 — resolve active hypothesis recommendation label
            # at form-render (snapshot-at-entry-surface). Same matcher
            # chain the CLI uses (swing/cli.py:trade_entry_cmd via the
            # extracted helper) — cross-surface consistency: dashboard
            # recommendation, CLI prefill, and form prefill all converge
            # on the same suggested label. None when the ticker has no
            # active recommendation; template renders "(none)" + empty
            # hidden input value.
            from swing.recommendations.hypothesis_prefill import (
                lookup_active_recommendation_label,
            )
            resolved_hypothesis_label = lookup_active_recommendation_label(
                conn, ticker=ticker,
                starting_equity=cfg.account.starting_equity,
            )
            # Phase 13 T3.SB1 dispatch brief §5 watch item 7 — banner-pin
            # counters mirror DashboardVM. Helper module already exists at
            # swing.metrics.discrepancies (Phase 10 + Phase 12.5 #1 + #2).
            from swing.metrics.discrepancies import (
                count_recent_multi_leg_auto_corrections,
                count_unresolved_material,
                fetch_first_pending_ambiguity_resolve_link_path,
            )
            unresolved_material_count = count_unresolved_material(conn)
            recent_multi_leg_count = count_recent_multi_leg_auto_corrections(
                conn,
            )
            banner_resolve_link = (
                fetch_first_pending_ambiguity_resolve_link_path(conn)
            )
        # `with conn:` block has exited (autocommit released); call the
        # auto-fill resolver on the same conn since
        # ``resolve_entry_auto_fill`` invokes
        # ``audit_service.record_call_start`` which requires
        # ``conn.in_transaction == False`` (per CLAUDE.md
        # "in_transaction auto-detect" + "Service-layer with conn:" gotchas).
        from swing.trades.entry_auto_fill import resolve_entry_auto_fill
        auto_fill = resolve_entry_auto_fill(
            ticker=ticker, cfg=cfg, conn=conn,
        )
    finally:
        conn.close()

    # Live price.
    prices = cache.get_many(
        [ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snap = prices.get(ticker)

    # R3-Major-2 fallback chain — GATED on origin=hyp-recs (R1-Major-2).
    # Watchlist origin (default) preserves existing behavior for backward
    # compat: a watchlist Enter caller hitting an off-watchlist ticker is
    # a degenerate path under existing UX (the watchlist Enter button only
    # fires from watchlist rows by construction); preserving the 0.0
    # fallback there is the conservative choice. Hyp-recs origin gets the
    # candidate-row fallback so off-watchlist hyp-recs Enter sees useful
    # values from the latest evaluation.
    if coerced_origin == "hyp-recs":
        if wl_entry is not None and wl_entry.initial_stop_target:
            initial_stop = wl_entry.initial_stop_target
        elif cand_initial_stop is not None:
            initial_stop = cand_initial_stop
        else:
            initial_stop = 0.0
    else:
        # Watchlist origin: existing behavior.
        initial_stop = (
            wl_entry.initial_stop_target
            if wl_entry and wl_entry.initial_stop_target
            else 0.0
        )

    # entry_price fallback chain. For hyp-recs origin: live snap →
    # wl_entry.last_close → candidate.pivot → 0.0. For watchlist origin:
    # preserve existing behavior (live snap → wl_entry.last_close → 0.0).
    if snap is not None:
        entry_price = snap.price
    elif wl_entry is not None and wl_entry.last_close:
        entry_price = wl_entry.last_close
    elif coerced_origin == "hyp-recs" and cand_pivot is not None:
        entry_price = cand_pivot
    else:
        entry_price = 0.0

    # Hidden inputs stay BOUND TO wl_entry ONLY (spec §3.8b.2): their
    # POST-side semantic is "the value the watchlist had at form-render".
    # When hyp-recs-originated and wl_entry is None, both are absent.
    watchlist_entry_target = wl_entry.entry_target if wl_entry else None
    watchlist_initial_stop = wl_entry.initial_stop_target if wl_entry else None

    # Phase 13 T2.SB6c T-A.6c.4 §C.5 Layer 1 — resolve the
    # pattern_evaluations anchor for pipeline-origin trades.
    #
    # Codex R1 MAJOR #2 closure: when the caller passes an explicit
    # ``explicit_pattern_evaluation_id`` (sourced from the hyp-rec
    # template's ``?pattern_evaluation_id=<id>`` query param), validate
    # it against the form's ``(pipeline_run_id, ticker)`` context. If
    # the explicit id resolves to a row whose ticker + pipeline_run_id
    # match the form's context, USE IT verbatim (operator-chosen PE
    # row; multi-pattern_class disambiguation per spec §C.5). Else
    # fall back to the legacy highest-composite_score row (V1
    # simplification preserved for non-anchored entry-form GETs;
    # banked V2: operator picks which class drives the anchor).
    #
    # Codex R2 MAJOR #1 closure: when an explicit
    # ``explicit_pipeline_run_id_at_form_render`` arrives alongside
    # the explicit PE id, validate against the OPERATOR-SUBMITTED run
    # (the pipeline_run that was active on the expanded card), NOT
    # ``latest_completed_pipeline_run()``. Without this discipline, a
    # new pipeline completing between expanded-card render and form
    # GET would silently rebind to the new run's highest-composite PE
    # — reintroducing operator-intent drift via a fresh race path. The
    # legacy loose-validation path (explicit PE WITHOUT explicit run
    # anchor) is preserved for backwards-compat: any external caller
    # that links to ``/trades/entry/form?pattern_evaluation_id=<id>``
    # without supplying the run anchor still validates against the
    # latest completed run as before.
    resolved_pattern_evaluation_id: int | None = None
    pattern_evaluation_anchor_pipeline_run_id: int | None = None
    if pipeline_run_id is not None:
        _conn2 = connect(cfg.paths.db_path)
        try:
            if explicit_pattern_evaluation_id is not None:
                explicit_row = _conn2.execute(
                    "SELECT id, pipeline_run_id, ticker FROM "
                    "pattern_evaluations WHERE id = ?",
                    (int(explicit_pattern_evaluation_id),),
                ).fetchone()
                if explicit_row is not None:
                    _explicit_run = int(explicit_row[1])
                    _explicit_ticker = (explicit_row[2] or "").upper()
                    # Codex R2 MAJOR #1: when the caller pinned the run
                    # anchor on the expanded card, validate against it
                    # (operator-witnessed run); else fall back to the
                    # latest-completed run (legacy loose-validation
                    # contract for non-anchored callers).
                    if (
                        explicit_pipeline_run_id_at_form_render
                        is not None
                    ):
                        _expected_run = int(
                            explicit_pipeline_run_id_at_form_render,
                        )
                    else:
                        _expected_run = pipeline_run_id
                    if (
                        _explicit_run == _expected_run
                        and _explicit_ticker == ticker.upper()
                    ):
                        resolved_pattern_evaluation_id = int(explicit_row[0])
                        pattern_evaluation_anchor_pipeline_run_id = (
                            _explicit_run
                        )
            if resolved_pattern_evaluation_id is None:
                # Codex R3 MINOR #1 — explicit-anchor mismatch fallback.
                # When explicit-anchor validation fails (PE row missing
                # OR pipeline_run_id mismatch OR ticker mismatch), we
                # fall back to the highest-composite PE on the latest-
                # completed pipeline_run rather than 500'ing or
                # rendering an empty form. This preserves operator UX
                # continuity at the cost of cosmetic anchor drift on
                # tampered URLs — the 5-tier rejection ladder at
                # POST /trades/entry catches every anchor-vs-payload
                # inconsistency at submit time (anchor stamping is
                # server-recomputed at POST per the T3.SB3
                # "server-stamping LOCK" semantic clarification).
                pe_row = _conn2.execute(
                    "SELECT id FROM pattern_evaluations "
                    "WHERE pipeline_run_id = ? AND ticker = ? "
                    "ORDER BY composite_score DESC, id DESC LIMIT 1",
                    (pipeline_run_id, ticker),
                ).fetchone()
                if pe_row is not None:
                    resolved_pattern_evaluation_id = int(pe_row[0])
                    pattern_evaluation_anchor_pipeline_run_id = (
                        pipeline_run_id
                    )
        finally:
            _conn2.close()

    # Phase 13 T3.SB1 — Schwab auto-fill OVERRIDES the live-price /
    # watchlist fallback chain when the resolver returns a populated
    # result (spec §6.1 + plan §G.2 T-B.1.3). The operator sees the
    # auto-populated values in the input fields; manual edits are
    # detected at POST and flip fill_origin to
    # 'schwab_auto_then_operator_corrected' (T-B.1.4).
    auto_fill_entry_date_default = date.today().isoformat()
    if auto_fill.kind == "populated":
        # Defensive: auto_fill.entry_price + shares + entry_date are
        # non-None by EntryAutoFillResult __post_init__ contract.
        entry_price = float(auto_fill.entry_price)  # type: ignore[arg-type]
        auto_fill_entry_date_default = (
            auto_fill.entry_date or auto_fill_entry_date_default
        )

    # Sizing hint at current (entry, stop).
    equity = current_equity(
        starting_equity=cfg.account.starting_equity,
        exits=exits, cash_movements=cash_movements,
    )
    if entry_price > 0 and 0 < initial_stop < entry_price:
        sizing = compute_shares(
            entry=entry_price, stop=initial_stop, equity=equity,
            max_risk_pct=cfg.risk.max_risk_pct,
            position_pct_cap=cfg.sizing.position_pct_cap,
        )
        suggested_shares = sizing.shares
        risk_dollars = sizing.risk_dollars
        risk_pct = sizing.risk_pct
    else:
        suggested_shares = 0
        risk_dollars = 0.0
        risk_pct = 0.0
    # Phase 13 T3.SB1 — Schwab shares overrides sizing-derived
    # suggested_shares so the input pre-population matches the actual
    # fill. Cast safely: auto_fill.shares is int|None.
    if auto_fill.kind == "populated" and auto_fill.shares is not None:
        suggested_shares = int(auto_fill.shares)

    # Spec §3.6: only ``pattern in ('flag', 'none')`` rows count as
    # "evaluated"; classifier-error rows (pattern=NULL) and missing
    # rows render the "Not classified" stub with no override surface.
    cp_algo: str | None = None
    cp_conf: float | None = None
    cp_evaluated = False
    cp_computed_at: str | None = None
    cp_anchor: int | None = None
    if cls is not None and cls.pattern in ("flag", "none"):
        cp_algo = cls.pattern
        cp_conf = cls.confidence
        cp_evaluated = True
        cp_computed_at = cls.computed_at
        cp_anchor = cls.pipeline_run_id

    return TradeEntryFormVM(
        ticker=ticker,
        entry_date=auto_fill_entry_date_default,
        entry_price=entry_price,
        initial_stop=initial_stop,
        watchlist_entry_target=watchlist_entry_target,
        watchlist_initial_stop=watchlist_initial_stop,
        suggested_shares=suggested_shares,
        risk_dollars=risk_dollars,
        risk_pct=risk_pct,
        soft_warn_threshold=cfg.position_limits.soft_warn_open,
        hard_cap=cfg.position_limits.hard_cap_open,
        open_count=len(open_trades),
        rationale_options=entry_rationale_options(),
        chart_pattern_algo=cp_algo,
        chart_pattern_algo_confidence=cp_conf,
        chart_pattern_algo_evaluated=cp_evaluated,
        chart_pattern_algo_computed_at=cp_computed_at,
        chart_pattern_classification_pipeline_run_id=cp_anchor,
        sector=cand_sector,
        industry=cand_industry,
        sector_industry_evaluation_run_id=cand_eval_id_for_si_anchor,
        origin=coerced_origin,
        pipeline_finished_at=(
            pipeline_finished_at if coerced_origin == "hyp-recs" else None
        ),
        hypothesis_label=resolved_hypothesis_label,
        # Phase 13 T3.SB1 — Schwab auto-fill fields (T-B.1.3).
        auto_fill_kind=auto_fill.kind,
        auto_fill_fill_origin=auto_fill.fill_origin,
        auto_fill_entry_date=auto_fill.entry_date,
        auto_fill_entry_price=auto_fill.entry_price,
        auto_fill_shares=auto_fill.shares,
        auto_fill_advisory_text=auto_fill.advisory_text,
        auto_fill_schwab_source_value_json=(
            auto_fill.schwab_source_value_json
        ),
        auto_fill_audit_at=auto_fill.auto_fill_audit_at,
        # Phase 13 T3.SB1 dispatch brief §5 watch item 7 — banner-pin fields.
        unresolved_material_discrepancies_count=unresolved_material_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
        # Phase 13 T2.SB6c T-A.6c.4 §C.5 Layer 1 — pattern_evaluations
        # anchor for OQ-12 CLOSURE. None when no matching row.
        pattern_evaluation_id=resolved_pattern_evaluation_id,
        claimed_pattern_evaluation_anchor=(
            resolved_pattern_evaluation_id is not None
        ),
        pipeline_run_id_at_form_render=(
            pattern_evaluation_anchor_pipeline_run_id
        ),
    )


@dataclass(frozen=True)
class TradeExitFormVM:
    trade: Trade
    exit_date: str
    exit_price: float
    remaining_shares: int
    reasons: tuple[str, ...]
    # Phase 13 T3.SB2 T-B.2.2 — exit auto-fill via Schwab Trader API at
    # form render (spec §6.2 + plan §G.5). SELL-side mirror of
    # TradeEntryFormVM's auto_fill_* fields. The 8 auto_fill_* fields
    # carry the resolution result from
    # ``swing.trades.exit_auto_fill.resolve_exit_auto_fill``. When the
    # resolution is short-circuited (sandbox / DEGRADED / no account_hash /
    # credentials missing / Schwab error) OR yields no candidates, all
    # auto_fill_* fields stay None except ``auto_fill_advisory_text`` +
    # ``auto_fill_fill_origin``. The template gates display + hidden-input
    # emission on ``vm.auto_fill_schwab_source_value_json is not none``.
    #
    # ``fill_origin`` here is the form-render-time stamp (always
    # 'schwab_auto' on populated, 'operator_typed' otherwise). The POST
    # handler (T-B.2.3) re-derives the persisted ``fill_origin`` by
    # comparing the submitted exit_date / exit_price / shares against the
    # ``auto_fill_schwab_source_value_json`` anchor (and, for multi-
    # partial, the operator-selected candidate's per-candidate hidden
    # inputs).
    #
    # Multi-partial-exit handling: ``auto_fill_candidates`` carries the
    # full per-fill list (length >= 1 when populated; None otherwise).
    # The template renders radio buttons for selection when length >= 2;
    # the single-fill case renders pre-populated inputs directly (no
    # radio). Per-candidate ``signature_hash`` + ``order_id`` are emitted
    # as hidden inputs ``candidate_signature_hash_<i>`` +
    # ``candidate_order_id_<i>`` so POST handler can verify operator's
    # selected candidate index maps to a server-rendered candidate
    # (FORWARD-BINDING WATCH ITEM for T-B.2.3).
    auto_fill_kind: str = "operator_typed"
    auto_fill_fill_origin: str = "operator_typed"
    auto_fill_exit_date: str | None = None
    auto_fill_exit_price: float | None = None
    auto_fill_closed_shares: int | None = None
    auto_fill_candidates: tuple[Any, ...] | None = None
    auto_fill_advisory_text: str | None = None
    auto_fill_schwab_source_value_json: str | None = None
    auto_fill_audit_at: str | None = None
    # Phase 13 T3.SB2 dispatch brief §5 watch item — base-layout VM banner
    # pin (defense-in-depth for any future full-page render path that
    # extends ``base.html.j2``; the current /trades/{id}/exit/form route
    # returns a row-partial fragment that does NOT extend the base
    # layout, so the banner-pin fields are not currently rendered — but
    # the VM populates them anyway so future plumbing changes don't trip
    # the CLAUDE.md "base.html.j2 is shared — new vm.foo field requires
    # adding to EVERY base-layout VM" gotcha). Defaults match
    # BaseLayoutVM canonical values + mirror TradeEntryFormVM precedent
    # (forward-binding lesson #12; field-duplication convention per
    # Codex R1 Major #4 ACCEPT on T3.SB1).
    unresolved_material_discrepancies_count: int = 0
    recent_multi_leg_auto_correction_count: int = 0
    banner_resolve_link: str | None = None


def build_exit_form_vm(
    *, trade_id: int, cfg: Config, cache: PriceCache, executor,
) -> TradeExitFormVM | None:
    # Phase 13 T3.SB2 T-B.2.2 — banner-pin counters mirror DashboardVM
    # via swing.metrics.discrepancies helpers (Phase 10 + Phase 12.5).
    unresolved_material_count: int = 0
    recent_multi_leg_count: int = 0
    banner_resolve_link: str | None = None
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None or trade.state not in _ACTIVE_STATES:
                return None
            # Phase 7 Sub-C T1 — fills repo migration. Drop the
            # ``list_exits_for_trade`` shim; ``Fill.quantity`` replaces
            # ``Exit.shares`` (terminology change). Filter ``action='entry'``
            # so the canonical entry-fill (Sub-A T6 backfill) does not count
            # against the remaining-shares math.
            fills = list_fills_for_trade(conn, trade_id)
            # Phase 13 T3.SB2 — banner-pin counters (read inside `with conn:`
            # block; defaults preserved if discrepancies-helper not yet
            # plumbed). Mirrors build_entry_form_vm precedent.
            from swing.metrics.discrepancies import (
                count_recent_multi_leg_auto_corrections,
                count_unresolved_material,
                fetch_first_pending_ambiguity_resolve_link_path,
            )
            unresolved_material_count = count_unresolved_material(conn)
            recent_multi_leg_count = count_recent_multi_leg_auto_corrections(
                conn,
            )
            banner_resolve_link = (
                fetch_first_pending_ambiguity_resolve_link_path(conn)
            )
        # `with conn:` block has exited (autocommit released); call the
        # auto-fill resolver on the same conn since
        # ``resolve_exit_auto_fill`` invokes
        # ``audit_service.record_call_start`` which requires
        # ``conn.in_transaction == False`` (per CLAUDE.md
        # "in_transaction auto-detect" + "Service-layer with conn:"
        # gotchas).
        #
        # Codex R1 Major #4 fix — collect schwab_order_id from any
        # already-recorded non-entry fills on this trade so the resolver
        # excludes already-persisted Schwab fills from the candidate
        # list (prevents operator double-recording the same Schwab
        # fill on a partial_exited trade with multiple sells).
        #
        # ``schwab_order_id`` is NOT a first-class column on fills; it
        # lives inside ``schwab_source_value_json`` (the audit envelope
        # written by exit_post when fill_origin in {'schwab_auto',
        # 'schwab_auto_then_operator_corrected'}). Parse it here.
        #
        # Codex R2 Major #3 fix — dedupe ONLY on ``schwab_order_id``
        # (envelope's pre-existing field that reflects which Schwab
        # order's values were ACTUALLY persisted), NOT on
        # ``selected_candidate_order_id`` (envelope's audit field for
        # "which candidate the operator picked at form-render"). The
        # non-default-radio-no-edit case persists the DEFAULT candidate's
        # values (envelope.schwab_order_id = default), while
        # envelope.selected_candidate_order_id = the picked candidate's
        # order — but only the DEFAULT was actually recorded as a fill.
        # Excluding both would over-dedupe the picked-but-unrecorded
        # candidate from future fetches.
        #
        # Codex R2 Major #4 fix — fallback dedupe by
        # (date, round(price, 2), quantity) tuple for fills lacking a
        # parseable ``schwab_order_id`` (pre-v20 / tos_import /
        # imported_legacy / operator_typed fills with no envelope, OR
        # envelopes missing the key). Tolerance: price compared with
        # round(_, 2); date string-exact; quantity int-exact.
        existing_fill_order_ids: set[str] = set()
        existing_fill_value_tuples: set[tuple[str, float, int]] = set()
        existing_envelopes_cur = conn.execute(
            "SELECT schwab_source_value_json, fill_datetime, price, "
            "quantity FROM fills WHERE trade_id = ? AND action != 'entry'",
            (trade_id,),
        )
        for env_json, fill_dt, fill_price, fill_qty in (
            existing_envelopes_cur.fetchall()
        ):
            try:
                env = json.loads(env_json) if env_json else None
            except (ValueError, TypeError):
                env = None
            order_id_found = False
            if isinstance(env, dict):
                v = env.get("schwab_order_id")
                if isinstance(v, str) and v:
                    existing_fill_order_ids.add(v)
                    order_id_found = True
            # Fallback dedupe tuple — populated for ALL non-entry fills
            # whose envelope did not surface an order_id. This covers
            # pre-v20 fills (no schwab_source_value_json), operator_typed
            # fills (no envelope), tos_import / imported_legacy fills
            # (no envelope), AND envelopes carrying only
            # selected_candidate_order_id (per M3 — the actually-persisted
            # values are the visible-input values, NOT a Schwab order's).
            if not order_id_found:
                try:
                    fill_date = (
                        str(fill_dt).split("T", 1)[0]
                        if fill_dt is not None else None
                    )
                    if fill_date and fill_price is not None and fill_qty is not None:
                        existing_fill_value_tuples.add(
                            (
                                fill_date,
                                round(float(fill_price), 2),
                                int(fill_qty),
                            )
                        )
                except (TypeError, ValueError):
                    # Defensive: skip fills with non-parseable values.
                    continue

        from swing.trades.exit_auto_fill import resolve_exit_auto_fill
        auto_fill = resolve_exit_auto_fill(
            trade_id=trade_id,
            ticker=trade.ticker,
            entry_date=trade.entry_date,
            cfg=cfg,
            conn=conn,
            existing_fill_order_ids=(
                existing_fill_order_ids if existing_fill_order_ids else None
            ),
            existing_fill_value_tuples=(
                existing_fill_value_tuples
                if existing_fill_value_tuples else None
            ),
        )
    finally:
        conn.close()
    non_entry_fills = [f for f in fills if f.action != "entry"]
    remaining = trade.initial_shares - sum(f.quantity for f in non_entry_fills)

    prices = cache.get_many(
        [trade.ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snap = prices.get(trade.ticker)
    exit_price = snap.price if snap else trade.entry_price  # conservative fallback

    # Phase 13 T3.SB2 — Schwab auto-fill OVERRIDES the live-price fallback
    # when the resolver returns a populated result (spec §6.2 + plan
    # §G.5). The operator sees auto-populated values in the input fields;
    # manual edits are detected at POST and flip fill_origin to
    # 'schwab_auto_then_operator_corrected' (T-B.2.3).
    exit_date_default = date.today().isoformat()
    if auto_fill.kind == "populated":
        # Defensive: auto_fill.exit_price + closed_shares + exit_date are
        # non-None by ExitAutoFillResult __post_init__ contract.
        exit_price = float(auto_fill.exit_price)  # type: ignore[arg-type]
        exit_date_default = auto_fill.exit_date or exit_date_default

    candidates_tuple: tuple[Any, ...] | None = (
        tuple(auto_fill.candidates) if auto_fill.candidates else None
    )

    return TradeExitFormVM(
        trade=trade,
        exit_date=exit_date_default,
        exit_price=exit_price,
        remaining_shares=remaining,
        reasons=tuple(r.value for r in ExitReason),
        # Phase 13 T3.SB2 — Schwab auto-fill fields (T-B.2.2).
        auto_fill_kind=auto_fill.kind,
        auto_fill_fill_origin=auto_fill.fill_origin,
        auto_fill_exit_date=auto_fill.exit_date,
        auto_fill_exit_price=auto_fill.exit_price,
        auto_fill_closed_shares=auto_fill.closed_shares,
        auto_fill_candidates=candidates_tuple,
        auto_fill_advisory_text=auto_fill.advisory_text,
        auto_fill_schwab_source_value_json=(
            auto_fill.schwab_source_value_json
        ),
        auto_fill_audit_at=auto_fill.auto_fill_audit_at,
        # Phase 13 T3.SB2 — banner-pin fields.
        unresolved_material_discrepancies_count=unresolved_material_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
    )


@dataclass(frozen=True)
class TradeStopFormVM:
    trade: Trade
    current_stop: float
    suggested_stops: tuple[tuple[str, float], ...]  # empty in 3b; 3c populates
    # Closed-taxonomy rationale options (value, display_label) pairs — T5.
    rationale_options: tuple[tuple[str, str], ...] = ()
    # Tranche B-ops T7: preservation fields — populated from the submitted
    # form on error re-render. Defaults represent the "clean form" case.
    # Mirrors TradeEntryFormVM's preservation pattern at N=2; no shared base
    # class per spec §5 rationale (field sets differ enough that an
    # abstraction would impose more than it saves).
    #
    # NOTE: `force` is intentionally NOT carried on the VM. Spec §5 is
    # explicit that the Force checkbox must never be auto-ticked on error
    # re-render — the operator has to tick it each time. Giving the VM a
    # `force` field would invite a future "preserve it too" change that
    # silently violates the spec. The POST route reads `force` from the
    # submitted form directly and uses it only to build StopAdjustRequest;
    # the rerender path deliberately drops it.
    new_stop_input: float | None = None
    rationale: str = ""
    notes: str = ""


def build_stop_form_vm(*, trade_id: int, cfg: Config) -> TradeStopFormVM | None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None or trade.state not in _ACTIVE_STATES:
                return None
    finally:
        conn.close()
    return TradeStopFormVM(
        trade=trade, current_stop=trade.current_stop, suggested_stops=(),
        rationale_options=stop_adjust_rationale_options(),
    )


@dataclass(frozen=True)
class ExitLegVM:
    """Phase 14 SB4 CR.1: one reducing (non-entry) fill surfaced on the
    review page exit table."""
    action: str
    fill_date: str       # fill_datetime[:10]
    price: float
    quantity: float
    reason: str | None


def _exit_vwap(non_entry_fills) -> float | None:
    """Share-weighted VWAP of the reducing fills, or None when no quantity.

    NOT a naive mean: (60*11 + 40*13)/100 = 11.80, not (11+13)/2 = 12.00.
    """
    num = sum(f.price * f.quantity for f in non_entry_fills if f.quantity)
    den = sum(f.quantity for f in non_entry_fills if f.quantity)
    return round(num / den, 4) if den else None


def _total_risk_dollars(trade) -> float | None:
    """Dollar-risk-at-open = initial_shares * (entry - initial_stop).

    Long-only; None on a missing or inverted (>= entry) stop.
    """
    stop = trade.initial_stop
    if stop is None or not (trade.entry_price > stop):
        return None
    return round(trade.initial_shares * (trade.entry_price - stop), 2)


@dataclass(frozen=True)
class ReviewVM:
    trade: Trade
    actual_realized_R_effective: float  # noqa: N815

    # Mistake_Tags vocabulary surfaced for form rendering:
    mistake_tag_categories: dict[str, tuple[str, ...]]

    # Disqualifying-violations reference list for form helper text:
    disqualifying_violations_reference: tuple[str, ...]

    # Per-grade label list (A..F):
    grade_choices: tuple[str, ...] = ("A", "B", "C", "D", "F")

    # Phase 5 lesson — base.html.j2 dereferences these. New page VMs MUST
    # carry safe defaults (5-VM existing-fields rule; brief §6.2 watch item 8).
    session_date: str = ""
    stale_banner: str = ""
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False

    # Phase 10 Sub-bundle B Task T-B.7 (electives amendment §2): per-trade
    # derived mistake_cost_R + lucky_violation_R values surfaced
    # symmetrically on the review form. Computed at VM build time via the
    # Phase 6 helpers (``swing/trades/review.py``) from
    # ``trade.realized_R_if_plan_followed`` + ``actual_realized_R_effective``.
    # Both render as ``None`` when ``realized_R_if_plan_followed IS NULL``
    # (operator did not record a counterfactual at review-form save time)
    # OR when the value is 0.0 (plan-followed-exactly).
    mistake_cost_R_display: float | None = None  # noqa: N815
    lucky_violation_R_display: float | None = None  # noqa: N815

    # Phase 10 Sub-bundle E T-E.3 — unresolved-material discrepancy banner.
    unresolved_material_discrepancies_count: int = 0
    # Phase 12.5 #1 T-1.8 — multi-leg auto-redirect advisory banner counter.
    recent_multi_leg_auto_correction_count: int = 0
    # Phase 12.5 #2 T-2.7 — banner link to FIRST pending-ambiguity discrepancy
    # resolve form. None when no pending-ambiguity row exists.
    banner_resolve_link: str | None = None

    # Phase 13 T3.SB3 (T-B.3.3) — Review auto-fill priors + MFE/MAE per
    # spec §6.3 + plan §E.4 + §E.3 LOCK. All values are operator-editable
    # DEFAULTS surfaced on the form-render path; the audit array tracks
    # which keys were server-populated so the POST handler can persist
    # ``review_log.auto_populated_field_keys_json`` faithfully.
    priors: ReviewPriors = field(
        default_factory=lambda: ReviewPriors(
            mistake_tag_candidates=(),
            process_grade_baseline=None,
            lesson_learned_candidates=(),
        ),
    )
    mfe_pct: float = 0.0
    mae_pct: float = 0.0
    # Server-stamped at handler entry; operator cannot tamper (Phase 8
    # R2-R5 family forward-binding lesson + L10 LOCK).
    auto_populated_field_keys_json: str | None = None

    # Phase 14 SB4 Slice 0 CR.1 — exit-data + chart snapshot. Safe defaults
    # so base.html.j2's 5-VM existing-fields rule holds and any non-returned
    # construction site stays valid.
    exit_legs: tuple[ExitLegVM, ...] = ()
    exit_price_vwap: float | None = None
    exit_date_last: str | None = None
    total_risk_dollars: float | None = None
    review_chart_url: str | None = None  # Task 0.6

    def __post_init__(self) -> None:
        if self.banner_resolve_link is not None:
            if not isinstance(self.banner_resolve_link, str):
                raise TypeError(
                    "ReviewVM.banner_resolve_link must be str | None; "
                    f"got {type(self.banner_resolve_link).__name__}"
                )
            if (
                not self.banner_resolve_link
                or not self.banner_resolve_link.startswith("/")
            ):
                raise ValueError(
                    "ReviewVM.banner_resolve_link must be None or a "
                    "non-empty path starting with '/'; got "
                    f"{self.banner_resolve_link!r}"
                )


def build_review_vm(
    *, trade_id: int, cfg: Config, ohlcv_cache: Any = None,
) -> ReviewVM | None:
    """Build the review-page VM. Returns None if trade not found, not closed,
    or already reviewed (V1 single-review-per-trade per brief §3.2).

    Phase 13 T3.SB3 (T-B.3.3): plumb priors + MFE/MAE auto-fill per spec
    §6.3. ``ohlcv_cache`` is the optional ``OhlcvCache.get_or_fetch``-
    capable substrate (request.app.state.ohlcv_cache at the web boundary;
    None when called from tests / CLI paths). MFE/MAE source-ladder per
    spec §E.3 LOCK: Phase 8 ``daily_management_records`` FIRST; OhlcvCache
    FALLBACK. Server-stamps ``auto_populated_field_keys_json`` honoring
    Phase 8 R2-R5 server-stamping family + L10 LOCK — operator cannot
    tamper with the audit envelope.
    """
    from datetime import datetime as _dt

    from swing.evaluation.dates import last_completed_session
    from swing.metrics.discrepancies import (
        count_recent_multi_leg_auto_corrections,
        count_unresolved_material,
        fetch_first_pending_ambiguity_resolve_link_path,
    )
    from swing.trades.review import (
        DISQUALIFYING_VIOLATIONS,
        MISTAKE_TAGS,
        compute_actual_realized_R_effective,
        compute_lucky_violation_R,
        compute_mistake_cost_R,
        get_priors_for_ticker,
    )
    from swing.trades.review_auto_fill import compute_mfe_mae_from_ohlcv_cache

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            # Phase 7 Sub-C T1 — Closed-but-not-reviewed predicate. Spec §2.1
            # reserves the bare ``state == 'closed'`` form for the per-trade
            # review precondition (NOT ``state in ('closed', 'reviewed')``,
            # which would re-allow already-reviewed trades through review).
            if trade is None or trade.state != "closed":
                return None
            if trade.reviewed_at is not None:
                return None  # V1: single-review-per-trade (defensive)
            # Fills repo migration: pull non-entry fills + transform to
            # Exit-shape rows so ``compute_actual_realized_R_effective``
            # (which still expects ``e.shares`` / ``e.r_multiple`` /
            # ``e.trade_id``) keeps working without an equity.py refactor.
            non_entry_fills = [
                f for f in list_fills_for_trade(conn, trade_id)
                if f.action != "entry"
            ]
            unresolved_material_count = count_unresolved_material(conn)
            recent_multi_leg_count = count_recent_multi_leg_auto_corrections(
                conn,
            )
            banner_resolve_link = (
                fetch_first_pending_ambiguity_resolve_link_path(conn)
            )
            # T-B.3.3: priors + MFE/MAE source-ladder reads. Stays inside the
            # same outer ``with conn:`` so all reads happen against a single
            # connection / snapshot.
            priors = get_priors_for_ticker(conn, trade.ticker)
            mfe_pct, mae_pct = compute_mfe_mae_from_ohlcv_cache(
                conn, trade, ohlcv_cache,
            )
    finally:
        conn.close()
    exits = tuple(_fill_to_exit_like(f, trade) for f in non_entry_fills)
    actual_r = compute_actual_realized_R_effective(trade, list(exits))

    # Phase 14 SB4 Slice 0 CR.1 — exit-data derivations. non_entry_fills are
    # the reducing fills; surface them sorted ASC by fill_datetime, plus the
    # share-weighted exit VWAP, the last-exit date, and the dollar risk at
    # open. _exit_vwap / _total_risk_dollars are the single math source reused
    # by Slice 2.
    non_entry_sorted = sorted(non_entry_fills, key=lambda f: f.fill_datetime)
    exit_legs = tuple(
        ExitLegVM(
            action=f.action, fill_date=f.fill_datetime[:10], price=f.price,
            quantity=f.quantity, reason=f.reason,
        )
        for f in non_entry_sorted
    )
    exit_price_vwap = _exit_vwap(non_entry_fills)
    exit_date_last = (
        non_entry_sorted[-1].fill_datetime[:10] if non_entry_sorted else None
    )
    total_risk_dollars = _total_risk_dollars(trade)

    # T-B.3.3: server-stamp the audit envelope at handler entry. Each key
    # is included iff its auto-fill source produced a non-empty / non-
    # trivial value. Operator-typed fields stay attributable (omitted from
    # the array → POST handler persists ``operator_typed`` for those keys
    # by exclusion).
    auto_keys: list[str] = []
    if priors.mistake_tag_candidates:
        auto_keys.append("mistake_tags")
    if priors.process_grade_baseline is not None:
        auto_keys.append("process_grade_baseline")
    if priors.lesson_learned_candidates:
        auto_keys.append("lesson_learned")
    if mfe_pct != 0.0:
        auto_keys.append("mfe_pct")
    if mae_pct != 0.0:
        auto_keys.append("mae_pct")
    # Pre-Codex review MAJOR #1: emit None on empty so the ``... or None``
    # gotcha-defense at any downstream POST persistence (or future v21
    # trades-level audit column) doesn't accidentally persist the string
    # "[]" (truthy) instead of NULL. Mirrors the cadence-path discipline
    # in build_cadence_complete_vm.
    auto_populated_field_keys_json: str | None = (
        json.dumps(auto_keys) if auto_keys else None
    )

    # T-B.3.3 step 1 (d): session-anchor alignment via
    # ``last_completed_session(now())`` (CLAUDE.md session-anchor read/
    # write mismatch gotcha family — backward-looking anchor matches the
    # period-helpers' read predicate at T-B.3.4).
    session_date = last_completed_session(_dt.now()).isoformat()

    # Phase 10 T-B.7 elective (per electives amendment §2): derive per-trade
    # mistake_cost_R + lucky_violation_R via Phase 6 helpers. Both surface
    # as None when realized_R_if_plan_followed is NULL OR when the
    # computed value equals 0.0 (plan-followed-exactly). The "—" placeholder
    # rendering at the template layer keys on the None value.
    mistake_cost_raw = compute_mistake_cost_R(
        realized_R_if_plan_followed=trade.realized_R_if_plan_followed,
        actual_realized_R_effective=actual_r,
    )
    lucky_violation_raw = compute_lucky_violation_R(
        realized_R_if_plan_followed=trade.realized_R_if_plan_followed,
        actual_realized_R_effective=actual_r,
    )
    mistake_cost_R_display = (  # noqa: N806
        None
        if trade.realized_R_if_plan_followed is None or mistake_cost_raw == 0.0
        else mistake_cost_raw
    )
    lucky_violation_R_display = (  # noqa: N806
        None
        if trade.realized_R_if_plan_followed is None
        or lucky_violation_raw == 0.0
        else lucky_violation_raw
    )
    return ReviewVM(
        trade=trade,
        actual_realized_R_effective=actual_r,
        mistake_tag_categories=MISTAKE_TAGS,
        disqualifying_violations_reference=DISQUALIFYING_VIOLATIONS,
        mistake_cost_R_display=mistake_cost_R_display,
        lucky_violation_R_display=lucky_violation_R_display,
        unresolved_material_discrepancies_count=unresolved_material_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
        session_date=session_date,
        priors=priors,
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
        auto_populated_field_keys_json=auto_populated_field_keys_json,
        exit_legs=exit_legs,
        exit_price_vwap=exit_price_vwap,
        exit_date_last=exit_date_last,
        total_risk_dollars=total_risk_dollars,
        review_chart_url=f"/trades/{trade_id}/review/chart",
    )


@dataclass(frozen=True)
class CadenceCompleteVM:
    review: ReviewLog
    n_closed_trades_in_period: int
    # 3e.16 — per-trade activity summaries for the review's period
    # (entered / exited / had a trade_event inside the period inclusive).
    # Default-empty tuple keeps backwards compatibility with existing
    # constructor sites that pre-date the field.
    trades_during_period: tuple[TradeSummaryVM, ...] = ()
    # 5-VM existing-fields safe defaults:
    session_date: str = ""
    stale_banner: str = ""
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    # Phase 10 Sub-bundle E T-E.3 — unresolved-material discrepancy banner.
    unresolved_material_discrepancies_count: int = 0
    # Phase 12.5 #1 T-1.8 — multi-leg auto-redirect advisory banner counter.
    recent_multi_leg_auto_correction_count: int = 0
    # Phase 12.5 #2 T-2.7 — banner link to FIRST pending-ambiguity discrepancy
    # resolve form. None when no pending-ambiguity row exists.
    banner_resolve_link: str | None = None

    # Phase 13 T3.SB3 (T-B.3.4) — period review auto-fill per spec §E.5
    # LOCK. All values are operator-editable starter text surfaced on the
    # form-render path; the audit envelope tracks which keys were server-
    # populated so the POST handler can persist
    # ``review_log.auto_populated_field_keys_json`` faithfully.
    period_lessons_summary: str = ""
    period_mistake_tag_aggregate: dict[str, int] = field(default_factory=dict)
    period_cohort_health_deltas: dict[str, float] = field(default_factory=dict)
    # Server-stamped at handler entry; operator cannot tamper (Phase 8
    # R2-R5 family forward-binding lesson + L10 LOCK).
    auto_populated_field_keys_json: str | None = None

    def __post_init__(self) -> None:
        if self.banner_resolve_link is not None:
            if not isinstance(self.banner_resolve_link, str):
                raise TypeError(
                    "CadenceCompleteVM.banner_resolve_link must be str | None; "
                    f"got {type(self.banner_resolve_link).__name__}"
                )
            if (
                not self.banner_resolve_link
                or not self.banner_resolve_link.startswith("/")
            ):
                raise ValueError(
                    "CadenceCompleteVM.banner_resolve_link must be None or a "
                    "non-empty path starting with '/'; got "
                    f"{self.banner_resolve_link!r}"
                )


@dataclass(frozen=True)
class ReviewsPendingVM:
    trades: tuple[Trade, ...]
    window_days: int
    # 5-VM existing-fields safe defaults:
    session_date: str = ""
    stale_banner: str = ""
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    # Phase 10 Sub-bundle E T-E.3 — unresolved-material discrepancy banner.
    unresolved_material_discrepancies_count: int = 0
    # Phase 12.5 #1 T-1.8 — multi-leg auto-redirect advisory banner counter.
    recent_multi_leg_auto_correction_count: int = 0
    # Phase 12.5 #2 T-2.7 — banner link to FIRST pending-ambiguity discrepancy
    # resolve form. None when no pending-ambiguity row exists.
    banner_resolve_link: str | None = None

    def __post_init__(self) -> None:
        if self.banner_resolve_link is not None:
            if not isinstance(self.banner_resolve_link, str):
                raise TypeError(
                    "ReviewsPendingVM.banner_resolve_link must be str | None; "
                    f"got {type(self.banner_resolve_link).__name__}"
                )
            if (
                not self.banner_resolve_link
                or not self.banner_resolve_link.startswith("/")
            ):
                raise ValueError(
                    "ReviewsPendingVM.banner_resolve_link must be None or a "
                    "non-empty path starting with '/'; got "
                    f"{self.banner_resolve_link!r}"
                )


def build_reviews_pending_vm(*, cfg: Config) -> ReviewsPendingVM:
    from swing.data.repos.review_log import list_unreviewed_closed_trades
    from swing.metrics.discrepancies import (
        count_recent_multi_leg_auto_corrections,
        count_unresolved_material,
        fetch_first_pending_ambiguity_resolve_link_path,
    )
    conn = connect(cfg.paths.db_path)
    try:
        # Spec §3.1: list-view shows ALL closed-unreviewed (window_days=None).
        # Spec §2.6: the BADGE uses window_days (count_needs_review); that path
        # is unaffected.
        trades = list_unreviewed_closed_trades(
            conn, window_days=None, today_iso=None,
        )
        unresolved_material_count = count_unresolved_material(conn)
        recent_multi_leg_count = count_recent_multi_leg_auto_corrections(conn)
        banner_resolve_link = (
            fetch_first_pending_ambiguity_resolve_link_path(conn)
        )
    finally:
        conn.close()
    return ReviewsPendingVM(
        trades=tuple(trades),
        window_days=cfg.review.review_window_days,
        unresolved_material_discrepancies_count=unresolved_material_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
    )


def build_cadence_complete_vm(*, review_id: int, cfg: Config) -> CadenceCompleteVM | None:
    """Returns None for unknown review or already-completed review (404 in route)."""
    from swing.data.repos.review_log import get
    from swing.metrics.discrepancies import (
        count_recent_multi_leg_auto_corrections,
        count_unresolved_material,
        fetch_first_pending_ambiguity_resolve_link_path,
    )
    conn = connect(cfg.paths.db_path)
    try:
        review = get(conn, review_id)
        if review is None or review.completed_date is not None:
            return None
        # Pre-render the count of closed trades in the period (helper text):
        from datetime import date as _date

        # C.10: migrated off ``list_all_exits``. The closed-trades-in-period
        # count walks the local _ExitShape adapter list (same exit_date /
        # trade_id surface).
        from swing.data.repos.trades import list_closed_trades
        closed = list_closed_trades(conn)
        all_exits = _list_all_exitshape_via_fills(conn)
        ps = _date.fromisoformat(review.period_start)
        pe = _date.fromisoformat(review.period_end)
        n = 0
        for t in closed:
            relevant = [
                _date.fromisoformat(e.exit_date) for e in all_exits
                if e.trade_id == t.id
            ]
            if relevant and ps <= max(relevant) <= pe:
                n += 1
        # 3e.16 — per-trade activity summaries for the period.
        trades_during_period = tuple(list_trades_with_activity_in_period(
            conn,
            period_start=review.period_start,
            period_end=review.period_end,
        ))
        unresolved_material_count = count_unresolved_material(conn)
        recent_multi_leg_count = count_recent_multi_leg_auto_corrections(conn)
        banner_resolve_link = (
            fetch_first_pending_ambiguity_resolve_link_path(conn)
        )

        # Phase 13 T3.SB3 (T-B.3.4): invoke the §E.5 period helpers to
        # surface starter section text. Prior-period boundaries derived
        # from the review's period span: same-length window immediately
        # preceding the current period.
        from swing.trades.review import (
            get_period_cohort_health_deltas,
            get_period_lessons_summary,
            get_period_mistake_tag_aggregate,
        )

        period_lessons = get_period_lessons_summary(
            conn, period_start=ps, period_end=pe,
        )
        period_mistake_agg = get_period_mistake_tag_aggregate(
            conn, period_start=ps, period_end=pe,
        )
        period_length_days = (pe - ps).days + 1
        prior_pe = ps - timedelta(days=1)
        prior_ps = prior_pe - timedelta(days=period_length_days - 1)
        period_cohort_deltas = get_period_cohort_health_deltas(
            conn,
            current_period_start=ps,
            current_period_end=pe,
            prior_period_start=prior_ps,
            prior_period_end=prior_pe,
        )
    finally:
        conn.close()

    # T-B.3.4: server-stamp the audit envelope based on which period
    # helpers produced non-empty output. Operator-typed sections stay
    # attributable (excluded from the JSON array).
    auto_keys: list[str] = []
    if period_lessons:
        auto_keys.append("primary_lesson")
    if period_mistake_agg:
        auto_keys.append("most_common_mistake_tags")
    if period_cohort_deltas:
        auto_keys.append("cohort_health_summary")
    auto_populated_field_keys_json: str | None = (
        json.dumps(auto_keys) if auto_keys else None
    )

    return CadenceCompleteVM(
        review=review,
        n_closed_trades_in_period=n,
        trades_during_period=trades_during_period,
        unresolved_material_discrepancies_count=unresolved_material_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
        period_lessons_summary=period_lessons,
        period_mistake_tag_aggregate=period_mistake_agg,
        period_cohort_health_deltas=period_cohort_deltas,
        auto_populated_field_keys_json=auto_populated_field_keys_json,
    )


# ---------------------------------------------------------------------------
# Phase 7 Sub-C T1 — Trade-detail page VM. Consumed by the route + template
# wired up by Sub-C T3/T5. Read-only surface; no write path lives here.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TradeDetailVM:
    """View-model for the trade-detail page (Phase 7 spec §11.4).

    Wraps a Trade plus its fills + audit-log read so the template can
    render the new Pre-Trade Decision section, the state badge, and the
    fills history without re-querying the DB.

    ``has_pre_trade_data`` gates the Pre-Trade Decision section render —
    legacy rows (pre-Phase-7, ``premortem_technical IS NULL``) hide the
    section entirely so the operator does not see a sea of empty fields.

    3e.8 Bundle 1 (§4.F) — ``advisories`` carries the same per-trade
    ``AdvisorySuggestionVM`` tuple that ``OpenPositionsRowVM.advisories``
    surfaces on the dashboard list view. Default empty tuple keeps
    existing call sites green (callers that build the VM without
    ``cache``/``executor``/``ohlcv_cache`` see no advisories).
    """
    trade: Trade
    state: str
    state_badge_label: str
    has_pre_trade_data: bool
    # 18 + 1 pre-trade-field accessors (spec §11.4 enumeration plus
    # ``catalyst_other_description`` companion). All passthrough from
    # ``trade.X`` for template ergonomics; legacy rows surface None.
    thesis: str | None
    why_now: str | None
    invalidation_condition: str | None
    expected_scenario: str | None
    premortem_technical: str | None
    premortem_market_sector: str | None
    premortem_execution: str | None
    premortem_additional: str | None
    event_risk_present: int | None
    event_handling: str | None
    event_type: str | None
    event_date: str | None
    gap_risk_present: int | None
    gap_risk_handling: str | None
    # emotional_state_pre_trade is stored as JSON-list TEXT (spec §1.2);
    # the builder decodes to a tuple of strings so the template can render
    # operator-friendly text instead of raw JSON-list storage format
    # (Codex R3 Minor 1). Empty tuple when NULL/empty/malformed-JSON.
    emotional_state_pre_trade: tuple[str, ...]
    # ``manual_entry_confidence`` lives on Fill (spec §4.3.1); pulled from
    # the authoritative entry-fill at build time. None when no entry-fill
    # exists yet (legacy rows; trade migrated without a backfill).
    manual_entry_confidence: str | None
    market_regime: str | None
    catalyst: str | None
    catalyst_other_description: str | None
    pre_trade_locked_at: str
    trade_origin: str
    audit_entries: tuple[AuditEntry, ...]
    fills: tuple[Fill, ...]
    # 3e.8 Bundle 1 (§4.F B.AC.1) — spec-conformant ``field(default_factory=
    # tuple)`` per brief §0.3 #3. Tuples are immutable so a shared default
    # is also safe, but the brief locks the factory form to harmonize with
    # the dashboard surface's existing pattern. Codex R2 Minor #1.
    advisories: tuple = field(default_factory=tuple)  # tuple[AdvisorySuggestionVM, ...]
    # 5-VM existing-fields safe defaults (CLAUDE.md base-layout VM rule):
    session_date: str = ""
    stale_banner: str = ""
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    # Phase 10 Sub-bundle E T-E.3 — global discrepancy banner counter (header).
    unresolved_material_discrepancies_count: int = 0
    # Phase 12.5 #1 T-1.8 — multi-leg auto-redirect advisory banner counter.
    recent_multi_leg_auto_correction_count: int = 0
    # Phase 10 Sub-bundle E T-E.6 — per-trade unresolved-material
    # discrepancies (electives amendment §2 Task E.6). Empty tuple when
    # the trade has zero unresolved material discrepancies; the template
    # hides the indicator entirely in that case.
    unresolved_material_discrepancies: tuple = field(default_factory=tuple)
    # Phase 12.5 #2 T-2.7 — banner link to FIRST pending-ambiguity discrepancy
    # resolve form. None when no pending-ambiguity row exists.
    banner_resolve_link: str | None = None
    # Phase 13 T2.SB6c T-A.6c.2 Gap A.2 — inline SVG bytes for the
    # operator-facing trade-detail page. Cache key:
    # `(ticker, surface='position_detail', pipeline_run_id IS NULL)` per
    # v20 §3.2 run-agnostic LOCK. None when no cache row exists; template
    # guards with `{% if vm.position_chart_svg_bytes %}`.
    position_chart_svg_bytes: bytes | None = None

    def __post_init__(self) -> None:
        if self.banner_resolve_link is not None:
            if not isinstance(self.banner_resolve_link, str):
                raise TypeError(
                    "TradeDetailVM.banner_resolve_link must be str | None; "
                    f"got {type(self.banner_resolve_link).__name__}"
                )
            if (
                not self.banner_resolve_link
                or not self.banner_resolve_link.startswith("/")
            ):
                raise ValueError(
                    "TradeDetailVM.banner_resolve_link must be None or a "
                    "non-empty path starting with '/'; got "
                    f"{self.banner_resolve_link!r}"
                )


@dataclass(frozen=True)
class DiscrepancyDisplay:
    """Per-discrepancy display shape for the T-E.6 indicator.

    Decouples the template from the persisted dataclass shape so the
    indicator surfaces operator-friendly text (type / field / expected /
    actual / period_end) without exposing JSON payload columns directly.
    """

    discrepancy_id: int
    type: str
    field_name: str
    expected: str
    actual: str
    period_end: str

    def __post_init__(self) -> None:
        if self.discrepancy_id <= 0:
            raise ValueError(
                f"DiscrepancyDisplay.discrepancy_id must be > 0; got "
                f"{self.discrepancy_id!r}"
            )
        if not self.type:
            raise ValueError("DiscrepancyDisplay.type must be non-empty")
        if not self.field_name:
            raise ValueError("DiscrepancyDisplay.field_name must be non-empty")


def _load_audit_entries(
    conn, trade_id: int,
) -> tuple[AuditEntry, ...]:
    """Read trade_events rows with event_type='pre_trade_edit', sorted ASC by ts.

    Each row's payload_json carries ``field``/``old_value``/``new_value``
    keys; the rationale column carries the operator-supplied edit reason.
    Malformed payloads (non-JSON / missing keys) surface as best-effort
    AuditEntry rows with None fallbacks rather than raising — V1 has no
    write path, so any rows that exist are operator-injected debug data.
    """
    rows = conn.execute(
        """
        SELECT ts, payload_json, rationale
        FROM trade_events
        WHERE trade_id = ? AND event_type = 'pre_trade_edit'
        ORDER BY ts ASC, id ASC
        """,
        (trade_id,),
    ).fetchall()
    out: list[AuditEntry] = []
    for ts, payload_json, rationale in rows:
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except (TypeError, ValueError):
            payload = {}
        out.append(AuditEntry(
            ts=ts,
            field=str(payload.get("field", "")),
            old_value=payload.get("old_value"),
            new_value=payload.get("new_value"),
            reason=rationale,
        ))
    return tuple(out)


def build_trade_detail_vm(
    *, trade_id: int, cfg: Config,
    cache=None, executor=None, ohlcv_cache=None,
) -> TradeDetailVM | None:
    """Build the trade-detail page VM. Returns None if trade not found.

    Loads trade + fills + pre-trade-edit audit log + (optionally) the
    authoritative entry-fill's ``manual_entry_confidence`` and assembles
    the VM. Pure read; no DB writes.

    3e.8 Bundle 1 (§4.F B.AC.2) — when ``cache`` is provided AND the trade
    is in an active lifecycle state (entered/managing/partial_exited),
    composes per-trade advisories via the same path as
    ``build_open_positions_row`` (live PriceCache + optional OhlcvCache +
    latest weather + ``compute_all_suggestions``). When ``cache is None``
    OR the trade is closed/reviewed, ``vm.advisories`` is an empty tuple
    (closed trades render the "No advisories." empty state per B.AC.4).
    """
    from swing.data.repos.fills import get_authoritative_entry_fill
    from swing.metrics.discrepancies import (
        count_recent_multi_leg_auto_corrections,
        count_unresolved_material,
        fetch_first_pending_ambiguity_resolve_link_path,
        list_unresolved_material_for_trade,
    )

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None:
                return None
            fills = tuple(list_fills_for_trade(conn, trade_id))
            audit_entries = _load_audit_entries(conn, trade_id)
            entry_fill = get_authoritative_entry_fill(conn, trade_id)
            unresolved_material_count = count_unresolved_material(conn)
            recent_multi_leg_count = count_recent_multi_leg_auto_corrections(
                conn,
            )
            banner_resolve_link = (
                fetch_first_pending_ambiguity_resolve_link_path(conn)
            )
            trade_discrepancies = list_unresolved_material_for_trade(
                conn, trade_id,
            )
            # Phase 13 T2.SB6c T-A.6c.2 Gap A.2 — consult chart_renders
            # cache for the position_detail surface. Run-agnostic per v20
            # §3.2 LOCK (pipeline_run_id IS NULL).
            from swing.data.repos.chart_renders import get_cached_chart_svg
            position_chart_svg_bytes = get_cached_chart_svg(
                conn,
                ticker=trade.ticker,
                surface="position_detail",
                pipeline_run_id=None,
            )
            # Latest weather — pipeline writer stamps `data_asof_date` on
            # weather rows, so read-only UIs MUST use get_latest (per CLAUDE.md
            # "Weather lookup in read-only UIs must NOT query by
            # action_session"). Read inside the same snapshot so the advisory
            # composition sees a consistent view.
            weather = None
            # 3e.8 Bundle 3 — per-trade active snapshot for §4.A.bis maturity_stage
            # hint. Loaded inside the same read snapshot as fills + weather so the
            # advisory composition sees a consistent view.
            active_snap = None
            if cache is not None and trade.state in _ACTIVE_STATES:
                from swing.data.repos.weather import get_latest
                weather = get_latest(conn, ticker=cfg.rs.benchmark_ticker)
                from swing.data.repos.daily_management import (
                    select_latest_active_snapshot_for_trade,
                )
                active_snap = select_latest_active_snapshot_for_trade(
                    conn, trade_id=trade_id,
                )
    finally:
        conn.close()

    badge_label = STATE_BADGE_LABELS.get(trade.state, trade.state)
    has_pre_trade_data = trade.premortem_technical is not None
    manual_entry_confidence = (
        entry_fill.manual_entry_confidence if entry_fill is not None else None
    )

    # 3e.8 Bundle 1 (§4.F B.AC.2) advisories: only compose for active trades
    # AND only when the caller threaded the live PriceCache. Mirrors the
    # dashboard composition in `build_dashboard` / `build_open_positions_row`.
    advisories: tuple = ()
    if cache is not None and trade.state in _ACTIVE_STATES:
        from swing.evaluation.dates import action_session_for_run
        from swing.trades.advisory import (
            AdvisoryContext,
            compute_all_suggestions,
        )
        from swing.web.view_models.dashboard import AdvisorySuggestionVM

        action_session = action_session_for_run(datetime.now()).isoformat()
        prices = cache.get_many(
            [trade.ticker],
            deadline_seconds=cfg.web.price_fetch_deadline_seconds,
            executor=executor,
        )
        snap = prices.get(trade.ticker)
        bundle = None
        if ohlcv_cache is not None:
            bundles = ohlcv_cache.get_many_bundles(
                [trade.ticker],
                deadline_seconds=cfg.web.price_fetch_deadline_seconds,
                executor=executor,
            )
            bundle = bundles.get(trade.ticker)
        weather_status = weather.status if weather else "STALE"
        # 3e.8 Bundle 2 — has_been_trimmed from the already-loaded fills
        # tuple (line ~899); adr_pct from OhlcvBundle (no new fetch).
        has_been_trimmed = any(f.action != "entry" for f in fills)
        # 3e.8 Bundle 3 Codex R1 Major #2 — §4.A.bis fires regardless of
        # price availability; build context always, choose composer by snap.
        ctx = AdvisoryContext(
            as_of_date=action_session,
            current_price=snap.price if snap is not None else 0.0,
            sma10=bundle.sma10 if bundle else None,
            sma20=bundle.sma20 if bundle else None,
            sma50=bundle.sma50 if bundle else None,
            previous_close=bundle.previous_close if bundle else None,
            weather_status=weather_status,
            config=cfg.stop_advisory,
            adr_pct=bundle.adr_pct if bundle else None,
            has_been_trimmed=has_been_trimmed,
            maturity_stage=(
                active_snap.maturity_stage if active_snap else None
            ),
        )
        if snap is not None:
            raw = compute_all_suggestions(trade, ctx)
        else:
            from swing.trades.advisory import (
                compute_price_independent_suggestions,
            )
            raw = compute_price_independent_suggestions(trade, ctx)
        advisories = tuple(
            AdvisorySuggestionVM(rule=s.rule, message=s.message)
            for s in raw
        )

    return TradeDetailVM(
        trade=trade,
        state=trade.state,
        state_badge_label=badge_label,
        has_pre_trade_data=has_pre_trade_data,
        thesis=trade.thesis,
        why_now=trade.why_now,
        invalidation_condition=trade.invalidation_condition,
        expected_scenario=trade.expected_scenario,
        premortem_technical=trade.premortem_technical,
        premortem_market_sector=trade.premortem_market_sector,
        premortem_execution=trade.premortem_execution,
        premortem_additional=trade.premortem_additional,
        event_risk_present=trade.event_risk_present,
        event_handling=trade.event_handling,
        event_type=trade.event_type,
        event_date=trade.event_date,
        gap_risk_present=trade.gap_risk_present,
        gap_risk_handling=trade.gap_risk_handling,
        emotional_state_pre_trade=_decode_emotional_state(
            trade.emotional_state_pre_trade,
        ),
        manual_entry_confidence=manual_entry_confidence,
        market_regime=trade.market_regime,
        catalyst=trade.catalyst,
        catalyst_other_description=trade.catalyst_other_description,
        pre_trade_locked_at=trade.pre_trade_locked_at,
        trade_origin=trade.trade_origin,
        audit_entries=audit_entries,
        fills=fills,
        advisories=advisories,
        unresolved_material_discrepancies_count=unresolved_material_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
        unresolved_material_discrepancies=tuple(
            _to_discrepancy_display(d) for d in trade_discrepancies
        ),
        position_chart_svg_bytes=position_chart_svg_bytes,
    )


def _to_discrepancy_display(d) -> DiscrepancyDisplay:
    """Map a :class:`ReconciliationDiscrepancy` to its template display shape.

    Per electives amendment §2 Task E.6: surfaces type / field_name /
    expected / actual / period_end. Expected + actual are parsed out of
    the JSON-text payload columns; on malformed-JSON the raw text is
    surfaced verbatim so the operator can still see what was recorded.
    """
    import json

    def _decode(raw: str | None) -> str:
        if raw is None:
            return "—"
        try:
            return str(json.loads(raw))
        except (TypeError, ValueError):
            return raw

    period_end: str = "—"
    # period_end on the discrepancy is implicit via the parent run; we
    # surface the created_at date-part as a deterministic proxy so the
    # indicator carries SOME date context without re-JOINing on runs.
    if d.created_at:
        period_end = d.created_at[:10]
    return DiscrepancyDisplay(
        discrepancy_id=int(d.discrepancy_id or 0),
        type=d.discrepancy_type,
        field_name=d.field_name,
        expected=_decode(d.expected_value_json),
        actual=_decode(d.actual_value_json),
        period_end=period_end,
    )


# ---------------------------------------------------------------------------
# Phase 8 Task 5.0 — daily-management event-log form VM.
# ---------------------------------------------------------------------------


# Closed-taxonomy action options surfaced in the event-log form. Mirrors
# spec §3.1.1 ``action_taken`` values; ``no_action`` and ``hold`` are inert
# observations exempt from the action_reason requirement (T3.2 contract).
_EVENT_LOG_ACTION_OPTIONS: tuple[str, ...] = (
    "no_action",
    "hold",
    "move_stop",
    "trim",
    "exit",
    "stop",
)


@dataclass(frozen=True)
class EventLogFormVM:
    """View-model for the daily-management event-log form.

    Pre-populates ``current_stop`` from the live ``trades.current_stop`` so
    the hidden ``prior_stop`` form input matches what ``record_event_log``
    re-reads inside its single-transaction stale-form guard. If a
    ``stop_adjust`` races between render + POST, the guard rejects the
    submission with a ``ValidationException`` and the route re-renders the
    form with the error banner.
    """

    trade: Trade
    current_stop: float
    review_date: str
    data_asof_session: str
    created_at: str
    mfe_mae_precision_level: str
    action_taken_options: tuple[str, ...] = _EVENT_LOG_ACTION_OPTIONS
    # code-review I1 fix — emotional_state is multi-checkbox, mirroring Phase 7
    # entry-form pattern. ``emotional_state_options`` is the canonical option
    # list rendered as checkboxes; ``emotional_state_set`` is the preservation
    # tuple for validation-error re-render (which boxes were checked).
    emotional_state_options: tuple[str, ...] = ()
    emotional_state_set: tuple[str, ...] = ()
    # Preservation fields (populated on validation-error re-render):
    stop_changed: int = 0
    new_stop: float | None = None
    stop_change_reason: str | None = None
    action_taken: str | None = None
    action_reason: str | None = None
    rule_violation_suspected: int = 0
    management_notes: str | None = None


def build_event_log_form_vm(
    *, trade_id: int, cfg: Config,
) -> EventLogFormVM | None:
    """Build the event-log form VM. Returns None if the trade is not active.

    Reads ``trades.current_stop`` so the hidden ``prior_stop`` field
    pre-populates with the canonical at-render value (T3.2 stale-form guard
    contract). Session anchors (``review_date``, ``data_asof_session``)
    default to ``last_completed_session(now)`` per spec §4.5 (Codex R3
    Major #2 fix) — weekend / holiday / pre-close renders otherwise stamp
    a non-session date and break same-session snapshot context. The route
    server-stamps these on POST regardless of the rendered values; the VM
    values feed the template's display strings only (no client-trustable
    hidden inputs — same R2 Major #2 carry-forward pattern as
    ``created_at``).
    """
    # Lazy / module-level import keeps the symbol patchable for tests + avoids
    # the circular-import surface load at top-of-module.
    from swing.evaluation.dates import last_completed_session

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None or trade.state not in _ACTIVE_STATES:
                return None
    finally:
        conn.close()
    now = datetime.now()
    session_anchor = last_completed_session(now).isoformat()
    # code-review I1 fix — populate emotional_state_options from canonical
    # vocabulary (mirrors Phase 7 entry-form's hardcoded same-tuple pattern).
    from swing.trades.daily_management import DAILY_MGMT_EMOTIONAL_STATES
    return EventLogFormVM(
        trade=trade,
        current_stop=trade.current_stop,
        review_date=session_anchor,
        data_asof_session=session_anchor,
        created_at=now.isoformat(timespec="seconds"),
        mfe_mae_precision_level="daily_approximate",
        emotional_state_options=DAILY_MGMT_EMOTIONAL_STATES,
    )


# ---------------------------------------------------------------------------
# Phase 8 Task 5.1 — Daily Management read-surface VMs.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyManagementTileVM:
    """Per-open-position dashboard tile row (spec §7.1 + plan T5.1).

    Read-source precedence (§5.6 ladder enforced by the builder):

      * Live values (``current_stop``, ``state``, ``planned_target_R``) ←
        ``trades`` row (Phase 7 single-write-path is authoritative). NOT
        the snapshot's stale copy — operator stop_adjusts mid-session must
        surface as the live tile value.
      * Time-series running extrema (``open_MFE_R_to_date``,
        ``open_MAE_R_to_date``) ← latest active snapshot row.
      * End-of-session anchored values (``current_price``, ``maturity_stage``,
        ``trail_MA_*``, ``position_capital_*``,
        ``position_portfolio_heat_contribution_dollars``) ← latest active
        snapshot row.

    ``data_asof_session`` is included so the template can stamp "as-of-{date}"
    on the tile (the snapshot is end-of-session anchored — the operator must
    see the staleness window explicitly).
    """
    trade_id: int
    ticker: str
    state: str                              # from trades-row (live)
    current_price: float | None             # from snapshot
    current_stop: float                     # from trades-row (LIVE per §5.6)
    open_R_effective: float | None          # noqa: N815  -- spec column name
    open_MFE_R_to_date: float | None        # noqa: N815  -- spec column name
    open_MAE_R_to_date: float | None        # noqa: N815  -- spec column name
    maturity_stage: str | None
    trail_MA_eligibility_flag: int | None   # noqa: N815  -- spec column name
    trail_MA_candidate_price: float | None  # noqa: N815  -- spec column name
    position_capital_utilization_pct: float | None
    position_capital_denominator_dollars: float | None
    position_portfolio_heat_contribution_dollars: float | None
    planned_target_R: float | None          # noqa: N815  -- from trades-row
    data_asof_session: str | None
    # ----- Phase 14 Sub-bundle 1 P14.N3 (spec section 6.2) -----
    # Freshly-resolved denominator at render time (via
    # equity_resolver.resolve_live_capital_denominator_dollars).
    position_capital_denominator_dollars_resolved: float = 0.0
    # True iff freshly-resolved state == "PROVISIONAL". Defaults False (LIVE):
    # the builder sets the real PROVISIONAL state explicitly, so an omitting
    # caller must not be silently marked PROVISIONAL (C-1).
    position_capital_utilization_is_provisional: bool = False
    # The utilization to render: stored when denominators match
    # (math.isclose rel_tol=1e-9); recomputed via
    # swing.trades.daily_management.compute_position_capital_utilization
    # otherwise; None when ill-defined.
    position_capital_utilization_pct_effective: float | None = None
    # True iff no risk_policy row has is_active=1 (NoActivePolicyError
    # caught at the build site). Codex R2.M#1+M#2 LOCK -- template
    # renders PROVISIONAL badge + extra-caveat tooltip OUTSIDE the
    # util-value guard so the operator sees a distinct remediation
    # path (direct DB intervention via SQL) even when
    # util_pct_effective is None.
    position_capital_policy_missing: bool = False


@dataclass(frozen=True)
class DailyManagementTimelineRowVM:
    """One row of the per-trade timeline (spec §7.2).

    ``record_type`` discriminates 'daily_snapshot' vs 'event_log'; the
    template renders different cells per type. Both share the chronological
    ORDER BY contract enforced by the repo (review_date ASC, created_at
    ASC, management_record_id ASC).
    """
    management_record_id: int
    record_type: str                # 'daily_snapshot' | 'event_log'
    review_date: str
    created_at: str
    is_superseded: int              # 0|1 — UI may toggle visibility
    mfe_mae_precision_level: str
    # Snapshot-only fields (None on event_log rows by default):
    current_price: float | None
    current_stop: float | None
    open_R_effective: float | None         # noqa: N815
    open_MFE_R_to_date: float | None       # noqa: N815
    open_MAE_R_to_date: float | None       # noqa: N815
    maturity_stage: str | None
    # Event_log-only fields (None on snapshot rows):
    action_taken: str | None
    action_reason: str | None
    stop_changed: int | None               # 0|1
    prior_stop: float | None
    new_stop: float | None
    thesis_status: str | None
    rule_violation_suspected: int | None   # 0|1
    emotional_state: str | None            # JSON-list TEXT
    management_notes: str | None
    # Phase 8 V1 polish — Item #1: legacy Phase 7 trade_events surfacing.
    # Populated only on `record_type == 'trade_event_legacy'` rows. None
    # everywhere else (defaulted so existing _record_to_timeline_row call
    # sites construct unchanged).
    trade_event_id: int | None = None
    event_type: str | None = None  # raw trade_events.event_type
    legacy_prior_stop: float | None = None  # decoded from payload_json["old_stop"]
    legacy_new_stop: float | None = None    # decoded from payload_json["new_stop"]
    legacy_rationale: str | None = None     # trade_events.rationale
    legacy_notes: str | None = None         # trade_events.notes


@dataclass(frozen=True)
class DailyManagementTimelineVM:
    """Timeline section for the per-trade detail page (spec §7.2).

    Surfaced as a dedicated section on the trade-detail page (Phase 7 Sub-C
    C.5 ``trades/detail.html.j2``) below the Pre-Trade Decision section.
    """
    trade_id: int
    ticker: str
    rows: tuple[DailyManagementTimelineRowVM, ...]


def _record_to_timeline_row(rec) -> DailyManagementTimelineRowVM:
    """Map a ``DailyManagementRecord`` to the timeline-row VM.

    Field selection mirrors spec §7.2 composition list — snapshot rows
    surface position-state cells; event_log rows surface operator-input
    cells. The dataclass carries both column groups so the template can
    branch on ``record_type``.
    """
    return DailyManagementTimelineRowVM(
        management_record_id=rec.management_record_id,
        record_type=rec.record_type,
        review_date=rec.review_date,
        created_at=rec.created_at,
        is_superseded=rec.is_superseded,
        mfe_mae_precision_level=rec.mfe_mae_precision_level,
        current_price=rec.current_price,
        current_stop=rec.current_stop,
        open_R_effective=rec.open_R_effective,
        open_MFE_R_to_date=rec.open_MFE_R_to_date,
        open_MAE_R_to_date=rec.open_MAE_R_to_date,
        maturity_stage=rec.maturity_stage,
        action_taken=rec.action_taken,
        action_reason=rec.action_reason,
        stop_changed=rec.stop_changed,
        prior_stop=rec.prior_stop,
        new_stop=rec.new_stop,
        thesis_status=rec.thesis_status,
        rule_violation_suspected=rec.rule_violation_suspected,
        emotional_state=rec.emotional_state,
        management_notes=rec.management_notes,
    )


def _orphan_stop_adjust_to_timeline_row(event):
    """Map an orphan Phase 7 ``trade_events`` row of event_type='stop_adjust'
    to the timeline-row VM (Phase 8 V1 polish Item #1).

    Field mapping:
        review_date          := event.ts[:10]   (YYYY-MM-DD slice of ISO ts)
        created_at           := event.ts        (full ISO timestamp)
        trade_event_id       := event.id        (positive PK — the sort
                                                 tiebreak uses this; see
                                                 ``_sort_key`` in
                                                 ``build_daily_management_timeline_vm``)
        management_record_id := -event.id       (negative synthetic ID,
                                                 emitted as the template
                                                 ``data-timeline-record-id``
                                                 attribute so legacy rows do
                                                 NOT collide with positive
                                                 ``daily_management_records``
                                                 PKs; informational only,
                                                 NOT used in sort key)

    Payload decode is DEFENSIVE — the helper never raises on malformed
    payload_json or missing keys; missing values render as None (template
    branch handles None gracefully via `is not none` checks).
    """
    import json

    prior_stop: float | None = None
    new_stop: float | None = None
    try:
        payload = json.loads(event.payload_json) if event.payload_json else {}
    except (json.JSONDecodeError, TypeError):
        payload = {}
    if isinstance(payload, dict):
        old = payload.get("old_stop")
        new = payload.get("new_stop")
        if isinstance(old, (int, float)):
            prior_stop = float(old)
        if isinstance(new, (int, float)):
            new_stop = float(new)

    return DailyManagementTimelineRowVM(
        management_record_id=-event.id,
        record_type="trade_event_legacy",
        review_date=event.ts[:10],
        created_at=event.ts,
        is_superseded=0,  # Phase 7 trade_events have no supersedure semantics.
        mfe_mae_precision_level="",  # Not applicable; template branch ignores.
        # All daily_snapshot/event_log column-group fields stay None on legacy rows:
        current_price=None,
        current_stop=None,
        open_R_effective=None,
        open_MFE_R_to_date=None,
        open_MAE_R_to_date=None,
        maturity_stage=None,
        action_taken=None,
        action_reason=None,
        stop_changed=None,
        prior_stop=None,
        new_stop=None,
        thesis_status=None,
        rule_violation_suspected=None,
        emotional_state=None,
        management_notes=None,
        # Phase 8 V1 polish legacy fields (populated):
        trade_event_id=event.id,
        event_type=event.event_type,
        legacy_prior_stop=prior_stop,
        legacy_new_stop=new_stop,
        legacy_rationale=event.rationale,
        legacy_notes=event.notes,
    )


def build_daily_management_timeline_vm(
    *, trade_id: int, cfg: Config,
) -> DailyManagementTimelineVM | None:
    """Build the per-trade timeline VM (spec §7.2 + Phase 8 V1 polish Item #1).

    V1 polish: also surfaces Phase 7 ``trade_events`` rows of
    ``event_type='stop_adjust'`` that have NO corresponding Phase 8
    ``daily_management_records`` row referencing them via
    ``linked_trade_event_id`` (orphans). Dedup rule: a trade_event is an
    orphan iff its ``id`` is NOT in the set of ``linked_trade_event_id``
    values from the trade's event_log records. Orphans render with
    ``record_type='trade_event_legacy'``.

    Returns ``None`` when the trade does not exist.
    """
    from swing.data.repos.daily_management import list_for_trade_timeline
    from swing.data.repos.trades import list_events_for_trade

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None:
                return None
            # Two sequential SELECTs without a wrapping read transaction. A
            # concurrent ``record_event_log`` COMMIT landing between them can
            # produce a transient false legacy-orphan in the rendered page
            # (read-side snapshot inconsistency). Accepted V1 limitation —
            # see ``docs/phase3e-todo.md`` "Phase 8 V2 advisory items" for
            # the V2 fix options + impact framing.
            records = list_for_trade_timeline(conn, trade_id=trade_id)
            events = list_events_for_trade(conn, trade_id=trade_id)
    finally:
        conn.close()

    # Dedup: collect linked_trade_event_id values from event_log records.
    # Snapshots never carry linked_trade_event_id; the predicate also gates
    # on record_type defensively in case repo-layer semantics widen later.
    linked_event_ids = {
        r.linked_trade_event_id for r in records
        if r.record_type == "event_log" and r.linked_trade_event_id is not None
    }

    # Filter trade_events to orphan stop_adjusts (per §0.3 #4 of brief: ONLY
    # event_type='stop_adjust'; entry/exit/partial/review_complete have their
    # own surfaces and are intentionally excluded).
    orphan_stop_adjusts = [
        e for e in events
        if e.event_type == "stop_adjust" and e.id not in linked_event_ids
    ]

    record_rows = [_record_to_timeline_row(r) for r in records]
    orphan_rows = [_orphan_stop_adjust_to_timeline_row(e) for e in orphan_stop_adjusts]

    # Merge + sort by canonical timeline key. Tiebreak via a 4-tuple
    # (review_date, created_at, source_rank, abs_id):
    #   - source_rank=0 for legacy orphans → orphans sort BEFORE DMR rows
    #     within the same (review_date, created_at) bucket.
    #   - source_rank=1 for daily_management_records.
    #   - abs_id uses trade_event_id ASC for orphans (insertion order) and
    #     management_record_id ASC for DMR rows (preserves prior semantics).
    # Adversarial-review R1 M1+M3: replaces the negative-id tiebreak that
    # previously reversed insertion order for multi-orphan same-second ties.
    def _sort_key(row: DailyManagementTimelineRowVM) -> tuple:
        if row.record_type == "trade_event_legacy":
            return (row.review_date, row.created_at, 0, row.trade_event_id or 0)
        return (row.review_date, row.created_at, 1, row.management_record_id)

    merged = sorted(record_rows + orphan_rows, key=_sort_key)

    return DailyManagementTimelineVM(
        trade_id=trade_id, ticker=trade.ticker, rows=tuple(merged),
    )
