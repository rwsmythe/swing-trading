"""Trade form view-models + builders for Phase 3b."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.cash import list_cash
from swing.data.repos.trades import get_trade, list_all_exits, list_exits_for_trade, list_open_trades
from swing.data.repos.watchlist import list_active_watchlist
from swing.recommendations.sizing import compute_shares
from swing.trades.entry import entry_rationale_options
from swing.trades.equity import current_equity
from swing.trades.exit import ExitReason
from swing.trades.stop_adjust import stop_adjust_rationale_options
from swing.web.chart_scope import latest_completed_pipeline_run
from swing.web.price_cache import PriceCache


_VALID_ORIGINS = ("watchlist", "hyp-recs")


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
            if trade is None or trade.status != "open":
                return None
            exits = list_exits_for_trade(conn, trade_id)
    finally:
        conn.close()
    remaining = trade.initial_shares - sum(e.shares for e in exits)

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
            if trade is None or trade.status != "open":
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
    actual_realized_R_effective: float

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
        DISQUALIFYING_VIOLATIONS, MISTAKE_TAGS,
        compute_actual_realized_R_effective,
    )

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None or trade.status != "closed":
                return None
            if trade.reviewed_at is not None:
                return None  # V1: single-review-per-trade
            exits = list_exits_for_trade(conn, trade_id)
    finally:
        conn.close()
    actual_r = compute_actual_realized_R_effective(trade, list(exits))
    return ReviewVM(
        trade=trade,
        actual_realized_R_effective=actual_r,
        mistake_tag_categories=MISTAKE_TAGS,
        disqualifying_violations_reference=DISQUALIFYING_VIOLATIONS,
    )
