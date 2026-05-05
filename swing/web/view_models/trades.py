"""Trade form view-models + builders for Phase 3b."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Literal

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Fill, ReviewLog, Trade
from swing.data.repos.cash import list_cash
from swing.data.repos.fills import (
    list_fills_for_trade,
)
from swing.data.repos.trades import (
    get_trade,
    list_all_exits,
    list_open_trades,
)
from swing.data.repos.watchlist import list_active_watchlist
from swing.recommendations.sizing import compute_shares
from swing.trades.entry import entry_rationale_options
from swing.trades.equity import current_equity
from swing.trades.exit import ExitReason
from swing.trades.stop_adjust import stop_adjust_rationale_options
from swing.web.chart_scope import latest_completed_pipeline_run
from swing.web.price_cache import PriceCache

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


def build_entry_form_vm(
    *, ticker: str, cfg: Config, cache: PriceCache, executor,
    origin: str = "watchlist",
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
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            wl = list_active_watchlist(conn)
            wl_entry = next((w for w in wl if w.ticker == ticker), None)
            open_trades = list_open_trades(conn)
            # C.10: migrates with equity.py refactor (legacy shim retained
            # so current_equity keeps working without touching equity.py).
            exits = list_all_exits(conn)
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
            cand_sector = ""
            cand_industry = ""
            cand_pivot: float | None = None
            cand_initial_stop: float | None = None
            if coerced_origin == "hyp-recs":
                sector_eval_id = pipeline_eval_id
            else:
                from swing.web.view_models.dashboard import (
                    latest_evaluation_run_id,
                )
                sector_eval_id = latest_evaluation_run_id(conn)
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
        initial_stop = wl_entry.initial_stop_target if wl_entry and wl_entry.initial_stop_target else 0.0

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
        entry_date=date.today().isoformat(),
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
        origin=coerced_origin,
        pipeline_finished_at=(
            pipeline_finished_at if coerced_origin == "hyp-recs" else None
        ),
        hypothesis_label=resolved_hypothesis_label,
    )


@dataclass(frozen=True)
class TradeExitFormVM:
    trade: Trade
    exit_date: str
    exit_price: float
    remaining_shares: int
    reasons: tuple[str, ...]


def build_exit_form_vm(
    *, trade_id: int, cfg: Config, cache: PriceCache, executor,
) -> TradeExitFormVM | None:
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

    return TradeExitFormVM(
        trade=trade,
        exit_date=date.today().isoformat(),
        exit_price=exit_price,
        remaining_shares=remaining,
        reasons=tuple(r.value for r in ExitReason),
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


def build_review_vm(*, trade_id: int, cfg: Config) -> ReviewVM | None:
    """Build the review-page VM. Returns None if trade not found, not closed,
    or already reviewed (V1 single-review-per-trade per brief §3.2).
    """
    from swing.trades.review import (
        DISQUALIFYING_VIOLATIONS,
        MISTAKE_TAGS,
        compute_actual_realized_R_effective,
    )

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
    finally:
        conn.close()
    exits = tuple(_fill_to_exit_like(f, trade) for f in non_entry_fills)
    actual_r = compute_actual_realized_R_effective(trade, list(exits))
    return ReviewVM(
        trade=trade,
        actual_realized_R_effective=actual_r,
        mistake_tag_categories=MISTAKE_TAGS,
        disqualifying_violations_reference=DISQUALIFYING_VIOLATIONS,
    )


@dataclass(frozen=True)
class CadenceCompleteVM:
    review: ReviewLog
    n_closed_trades_in_period: int
    # 5-VM existing-fields safe defaults:
    session_date: str = ""
    stale_banner: str = ""
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False


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


def build_reviews_pending_vm(*, cfg: Config) -> ReviewsPendingVM:
    from swing.data.repos.review_log import list_unreviewed_closed_trades
    conn = connect(cfg.paths.db_path)
    try:
        # Spec §3.1: list-view shows ALL closed-unreviewed (window_days=None).
        # Spec §2.6: the BADGE uses window_days (count_needs_review); that path
        # is unaffected.
        trades = list_unreviewed_closed_trades(
            conn, window_days=None, today_iso=None,
        )
    finally:
        conn.close()
    return ReviewsPendingVM(
        trades=tuple(trades),
        window_days=cfg.review.review_window_days,
    )


def build_cadence_complete_vm(*, review_id: int, cfg: Config) -> CadenceCompleteVM | None:
    """Returns None for unknown review or already-completed review (404 in route)."""
    from swing.data.repos.review_log import get
    conn = connect(cfg.paths.db_path)
    try:
        review = get(conn, review_id)
        if review is None or review.completed_date is not None:
            return None
        # Pre-render the count of closed trades in the period (helper text):
        from datetime import date as _date

        # C.10: migrates with equity.py refactor (legacy shim retained
        # so the closed-trades-in-period count keeps working without
        # touching the period-aggregation helpers).
        from swing.data.repos.trades import list_all_exits, list_closed_trades
        closed = list_closed_trades(conn)
        all_exits = list_all_exits(conn)
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
    finally:
        conn.close()
    return CadenceCompleteVM(review=review, n_closed_trades_in_period=n)


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
    emotional_state_pre_trade: str | None
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
    # 5-VM existing-fields safe defaults (CLAUDE.md base-layout VM rule):
    session_date: str = ""
    stale_banner: str = ""
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False


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
) -> TradeDetailVM | None:
    """Build the trade-detail page VM. Returns None if trade not found.

    Loads trade + fills + pre-trade-edit audit log + (optionally) the
    authoritative entry-fill's ``manual_entry_confidence`` and assembles
    the VM. Pure read; no DB writes.
    """
    from swing.data.repos.fills import get_authoritative_entry_fill

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None:
                return None
            fills = tuple(list_fills_for_trade(conn, trade_id))
            audit_entries = _load_audit_entries(conn, trade_id)
            entry_fill = get_authoritative_entry_fill(conn, trade_id)
    finally:
        conn.close()

    badge_label = STATE_BADGE_LABELS.get(trade.state, trade.state)
    has_pre_trade_data = trade.premortem_technical is not None
    manual_entry_confidence = (
        entry_fill.manual_entry_confidence if entry_fill is not None else None
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
        emotional_state_pre_trade=trade.emotional_state_pre_trade,
        manual_entry_confidence=manual_entry_confidence,
        market_regime=trade.market_regime,
        catalyst=trade.catalyst,
        catalyst_other_description=trade.catalyst_other_description,
        pre_trade_locked_at=trade.pre_trade_locked_at,
        trade_origin=trade.trade_origin,
        audit_entries=audit_entries,
        fills=fills,
    )
