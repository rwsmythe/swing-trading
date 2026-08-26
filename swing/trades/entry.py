"""Trade entry service — wraps repo with cap enforcement + watchlist archival."""
from __future__ import annotations

import contextlib
import logging
import sqlite3
import unicodedata
from dataclasses import dataclass
from enum import Enum

from swing.data.models import Fill, Trade, WatchlistArchiveEntry
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event, list_open_trades
from swing.data.repos.watchlist import (
    archive_watchlist_entry,
    get_watchlist_entry,
)
from swing.trades.origin import EntryPath, derive_trade_origin
from swing.trades.state import (
    MissingPreTradeFieldsException,
    validate_for_operation,
)

log = logging.getLogger(__name__)


# Re-export for callers: ``from swing.trades.entry import
# MissingPreTradeFieldsException`` mirrors the route/CLI ergonomic pattern
# used for the other entry-service exceptions (SoftWarnError etc.).
__all__ = [
    "EntryRationale", "EntryRequest", "EntryResult",
    "entry_rationale_options", "record_entry",
    "SoftWarnError", "HardCapError",
    "DuplicateOpenPositionError", "MissingPreTradeFieldsException",
]


class EntryRationale(str, Enum):  # noqa: UP042  (match ExitReason's (str, Enum) pattern)
    """Closed taxonomy for trade-entry rationale (Tranche B-ops Bug 3a, spec §3).

    Values are persisted as plain strings in ``trade_events.rationale``;
    ``EntryRequest.rationale`` stays typed as ``str`` and route/CLI layers
    convert via ``EntryRationale(value)`` before constructing the request.

    Provenance — each value maps either to a concrete repo string or to a
    deliberate operator-vocabulary expansion (spec §3 table):

    * ``aplus-setup`` — repo: ``candidate.bucket == 'aplus'`` +
      ``recommendation == 'today_decision'``.
    * ``near-trigger-breakout`` — repo: ``recommendation == 'near_trigger'``
      combined with a breakout verb.
    * ``vcp-breakout`` — repo: ``candidate.criteria`` contains layer ``'vcp'``.
    * ``pivot-breakout`` — DELIBERATE EXPANSION. Minervini/operator
      base-breakout concept not currently a repo string.
    * ``post-earnings-continuation`` — DELIBERATE EXPANSION.
      Operator-vocabulary gap-up-on-earnings, not a repo string.
    * ``relative-strength`` — DELIBERATE EXPANSION. Minervini/IBD RS-rank
      concept, documented in ``reference/methodology/`` but not a repo string.
    * ``other`` — standard escape hatch; route/CLI require ``notes`` when selected.
    """

    APLUS_SETUP = "aplus-setup"
    NEAR_TRIGGER_BREAKOUT = "near-trigger-breakout"
    VCP_BREAKOUT = "vcp-breakout"
    PIVOT_BREAKOUT = "pivot-breakout"
    POST_EARNINGS_CONTINUATION = "post-earnings-continuation"
    RELATIVE_STRENGTH = "relative-strength"
    OTHER = "other"


_ENTRY_RATIONALE_LABELS: dict[EntryRationale, str] = {
    EntryRationale.APLUS_SETUP: "A+ setup (today's decision)",
    EntryRationale.NEAR_TRIGGER_BREAKOUT: "Near-trigger breakout",
    EntryRationale.VCP_BREAKOUT: "VCP breakout",
    EntryRationale.PIVOT_BREAKOUT: "Pivot breakout (non-VCP)",
    EntryRationale.POST_EARNINGS_CONTINUATION: "Post-earnings gap continuation",
    EntryRationale.RELATIVE_STRENGTH: "Relative strength leadership",
    EntryRationale.OTHER: "Other (see notes)",
}


def entry_rationale_options() -> tuple[tuple[str, str], ...]:
    """Return ``(value, display_label)`` pairs in spec-declared order.

    Template layer consumes this to render the ``<select>`` options.
    """
    return tuple((r.value, _ENTRY_RATIONALE_LABELS[r]) for r in EntryRationale)


class SoftWarnError(Exception):
    """Open count >= soft_warn_open without force=True."""


class HardCapError(Exception):
    """Open count >= hard_cap_open — never bypassable."""


class DuplicateOpenPositionError(Exception):
    """Already an open trade for this ticker."""


@dataclass(frozen=True)
class EntryRequest:
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    initial_stop: float
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    rationale: str
    event_ts: str
    # Operator-frozen pre-trade hypothesis (free-text, optional). Default None
    # preserves existing call sites and persists NULL on the trades row.
    hypothesis_label: str | None = None
    # Operator-override label for the chart-pattern flag (free-text,
    # canonicalized at record_entry boundary the same way as
    # hypothesis_label). Default None preserves existing call sites and
    # persists NULL.
    chart_pattern_operator: str | None = None
    # Resolved-at-entry-surface classification snapshot — persisted
    # AS-IS by record_entry (no re-lookup at submit). ToCToU fix per
    # spec §3.6 (R2 M3 + R3 M1): cache resolution happens once at
    # form/CLI render; the resolved values flow through the request and
    # the persisted trade row reflects the operator's view at submit
    # time, not whatever a fresh re-lookup would return.
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
    # Migration 0012 — sector/industry snapshot-at-entry-surface. Resolved
    # at form/CLI render time from the candidate row; persisted AS-IS by
    # record_entry. Defaults '' so off-pipeline / off-watchlist trade entries
    # (no candidate row to read) persist empty strings — graceful
    # degradation matches the hypothesis_label free-text behavior.
    sector: str = ""
    industry: str = ""
    # Phase 7 Sub-B B.1 — entry-path origin discriminator + 18 pre-trade
    # required fields. All `| None = None` defaults so legacy/external call
    # sites still type-check; the validation gate at record_entry's top
    # rejects any submission with required fields missing.
    entry_path: EntryPath = EntryPath.MANUAL_WEB_FORM
    thesis: str | None = None
    why_now: str | None = None
    invalidation_condition: str | None = None
    expected_scenario: str | None = None
    premortem_technical: str | None = None
    premortem_market_sector: str | None = None
    premortem_execution: str | None = None
    premortem_additional: str | None = None
    event_risk_present: int | None = None  # 0|1
    event_handling: str | None = None
    event_type: str | None = None
    event_date: str | None = None
    gap_risk_present: int | None = None  # 0|1
    gap_risk_handling: str | None = None
    emotional_state_pre_trade: str | None = None  # JSON-list TEXT
    market_regime: str | None = None
    catalyst: str | None = None
    catalyst_other_description: str | None = None
    manual_entry_confidence: str | None = None  # 'high'|'normal'|'low'
    # Phase 13 T3.SB1 T-B.1.4 — entry auto-fill audit columns persisted on the
    # fills row (per spec §6.1 + §6.4 + plan §G.2 T-B.1.4). All defaults None /
    # 'operator_typed' so legacy callers (CLI tests, bare cURL, pre-Phase-13
    # call sites) keep working unchanged.
    fill_origin: str = "operator_typed"
    schwab_source_value_json: str | None = None
    operator_corrected_value_json: str | None = None
    auto_fill_audit_at: str | None = None
    # Phase 13 T2.SB6c T-A.6c.4 §C.5 Layer 3 + OQ-11 + OQ-12 lifecycle.
    # ``pattern_evaluation_id`` is the server-re-derived value from the
    # web POST handler's 5-tier rejection ladder (NOT the operator-
    # submitted hidden input verbatim). ``candidate_id`` is derived
    # inside record_entry from the latest-complete-evaluation-run
    # candidate lookup (pipeline-origin) or left NULL (manual_off_pipeline).
    # Both default None so legacy callers (CLI tests, bare cURL) keep
    # working — record_entry's candidate-id resolution still fires.
    pattern_evaluation_id: int | None = None
    candidate_id: int | None = None
    # Tuition-vs-error instrument (spec §7.3). The operator's explicit
    # design-intent selection at entry; default None -> NULL (omitted CLI
    # flag / unselected web <select>). Validated against ENTRY_INTENTS in
    # __post_init__ (Literal[...] is NOT runtime-enforced); NEVER derived
    # from hypothesis_label here -- record_entry persists it AS-IS
    # (server-stamp / spec §5 SINGLE PREFILL RULE).
    entry_intent: str | None = None

    def __post_init__(self) -> None:
        from swing.data.models import ENTRY_INTENTS
        if (
            self.entry_intent is not None
            and self.entry_intent not in ENTRY_INTENTS
        ):
            raise ValueError(
                f"EntryRequest.entry_intent must be None or one of "
                f"{sorted(ENTRY_INTENTS)}; got {self.entry_intent!r}"
            )


@dataclass(frozen=True)
class EntryResult:
    trade_id: int
    warning: str | None
    watchlist_archived: bool


def canonicalize_hypothesis_label(raw: str | None) -> str | None:
    """Canonicalize the operator-frozen hypothesis label at the persistence
    boundary so journal-review grouping is invariant to input whitespace,
    embedded control bytes, invisible Unicode format characters, and
    NFC/NFD encoding differences (adversarial review rounds 1 + 2).

    Steps:
      1. Apply Unicode NFC normalization so canonically-equivalent text
         (composed `é` vs decomposed `e + ̀`) yields one stored form.
      2. Drop any character in Unicode category ``Cf`` (format) — zero-width
         space U+200B, ZWJ U+200D, bidi overrides U+202E/U+2066+, etc. —
         which would otherwise let two visually-identical labels group as
         distinct buckets (R2 M1 spoofing concern).
      3. Replace any character in Unicode category ``Cc`` (control: `\\n`,
         `\\r`, `\\t`, NUL, …) with a single space.
      4. Collapse all whitespace runs to a single space.
      5. Strip leading/trailing whitespace.
      6. Empty result → ``None`` (so an all-whitespace input persists as
         NULL, not as an unnamed labeled bucket).

    Operator-typed semantic spacing inside a label is preserved (single
    spaces between words); only artifacts that would split otherwise-
    identical labels into distinct grouping keys are removed.
    """
    if raw is None:
        return None
    nfc = unicodedata.normalize("NFC", raw)
    cleaned_chars = []
    for c in nfc:
        cat = unicodedata.category(c)
        if cat == "Cf":
            continue  # invisible format chars: drop entirely
        if cat == "Cc":
            cleaned_chars.append(" ")  # control bytes: replace with space
        else:
            cleaned_chars.append(c)
    canonical = " ".join("".join(cleaned_chars).split())
    return canonical or None


def record_entry(
    conn: sqlite3.Connection, req: EntryRequest, *,
    soft_warn: int, hard_cap: int, force: bool,
    cfg=None,
) -> EntryResult:
    """22-A adds ONE keyword-only parameter, ``cfg``, and that is the whole
    signature change in the arc.  Both production call sites already have it
    (``swing/cli.py``, ``swing/web/routes/trades.py``).

    ``cfg=None`` DECLINES the latch path with reason ``no_config`` and leaves
    every persisted value byte-identical to the pre-arc behaviour, so every
    pre-existing caller and test is unaffected.
    """
    # Phase 7 Sub-B B.1 — non-bypassable pre-trade required-field gate. Per
    # spec §9.3, MissingPreTradeFieldsException is NOT force-bypassable; it
    # fires BEFORE the existing stop / duplicate / cap checks so an operator
    # can never sneak a partial-state row past the lock by toggling --force.
    # The validator's required-field set + conditional rules live in
    # ``swing.trades.state``; this service just calls + raises.
    #
    # Note: the validator's "always required" set includes `trade_origin` +
    # `pre_trade_locked_at`, which the route/CLI layer doesn't populate on
    # EntryRequest. `pre_trade_locked_at` still uses an interim shim
    # (event_ts); the canonical atomic insert+fill flow lands at B.3.
    #
    # B.2: `trade_origin` is now derived BEFORE validation via the origin
    # service so the validator and the eventual INSERT see the same value
    # the row will be persisted with. The 4-value enum returned by
    # derive_trade_origin always satisfies the validator's required-field
    # check (non-NULL string), so this preserves the gate-fires-first
    # discipline regardless of (bucket × entry_path) combo.
    derived_origin = derive_trade_origin(conn, req.ticker, req.entry_path)
    req_view: dict = {
        f: getattr(req, f, None)
        for f in (
            "ticker", "entry_date", "entry_price", "initial_stop",
            "thesis", "why_now", "invalidation_condition", "expected_scenario",
            "premortem_technical", "premortem_market_sector",
            "premortem_execution", "event_risk_present", "event_handling",
            "event_type", "event_date", "gap_risk_present",
            "gap_risk_handling", "emotional_state_pre_trade",
            "market_regime", "catalyst", "catalyst_other_description",
            "manual_entry_confidence",
        )
    }
    req_view["initial_shares"] = req.shares
    req_view["trade_origin"] = derived_origin
    # Codex R4 Major 1: pre_trade_locked_at + first-fill datetime must
    # reflect when the trade actually entered the market (req.entry_date),
    # not when the operator typed the command (req.event_ts).
    # Codex R5 Major 1: trades.entry_date column is date-only and downstream
    # consumers (advisory, journal/flags+analyze, briefing, CLI hold-duration)
    # call date.fromisoformat(trade.entry_date) directly. So entry_date must
    # remain YYYY-MM-DD only at the API boundary; reject T-form before
    # storing. Synthesis of T16:00:00 for fill_datetime / pre_trade_locked_at
    # happens via the shared helper after the date-only guard.
    from swing.trades.exit import _normalize_trade_event_date_to_iso
    if "T" in req.entry_date:
        raise ValueError(
            f"entry_date {req.entry_date!r} must be YYYY-MM-DD only "
            f"(not a full ISO datetime); the trades.entry_date column is "
            f"date-only and downstream consumers (advisory, journal, "
            f"briefing, CLI hold-duration) call date.fromisoformat on it"
        )
    entry_iso = _normalize_trade_event_date_to_iso(
        req.entry_date, field_name="entry_date",
    )
    req_view["pre_trade_locked_at"] = entry_iso
    missing = validate_for_operation(req_view, op="entry_create", current_state=None)
    if missing:
        raise MissingPreTradeFieldsException(missing_fields=missing)

    if req.initial_stop >= req.entry_price:
        raise ValueError(
            f"stop must be < entry; got entry={req.entry_price}, stop={req.initial_stop}"
        )

    # 20-A B-2 (Codex R11 MAJOR): the entry write-gate does NOT exclude voided
    # trades. The B-2 void is a disposition for CLOSED/reviewed phantom trades
    # (SATL is reviewed); a voided-but-OPEN trade is out of V1 scope -- the
    # note-void does not transition state, and the DB partial unique index
    # `ux_trades_one_open_per_ticker` (migration 0014) still enforces one open
    # position per ticker across ALL open states. Excluding voided here would
    # be a FALSE PROMISE (the Python check would pass, then the INSERT would
    # fail on the index and re-map to DuplicateOpenPositionError). The gate
    # therefore treats all open trades uniformly, consistent with the DB.
    open_trades = list_open_trades(conn)
    if any(t.ticker == req.ticker for t in open_trades):
        raise DuplicateOpenPositionError(
            f"Already an open position in {req.ticker}"
        )

    open_count = len(open_trades)
    if open_count >= hard_cap:
        raise HardCapError(
            f"Hard cap reached: {open_count} >= {hard_cap}"
        )
    warning: str | None = None
    if open_count >= soft_warn:
        if not force:
            raise SoftWarnError(
                f"Open count {open_count} >= soft warn {soft_warn}; use --force"
            )
        warning = f"Soft warn exceeded: {open_count} open positions (soft={soft_warn})"

    # Phase 13 T2.SB6c T-A.6c.4 §C.5 Layer 3 + OQ-11 lifecycle —
    # resolve candidate_id from the latest-complete-evaluation-run
    # candidate row for pipeline-origin trades. NULL for
    # manual_off_pipeline (no candidate row exists) OR when the
    # caller already provided one (CLI / E2E paths). Path 1
    # (evaluation_run_id filter) per plan §B.1; we leverage the
    # existing _latest_complete_evaluation_run_id helper.
    #
    # Codex R1 MAJOR #3 closure: when ``req.pattern_evaluation_id`` is
    # non-NULL, resolve ``candidate_id`` via the PE row's
    # ``pipeline_run_id → pipeline_runs.evaluation_run_id`` chain
    # rather than the latest-complete fallback. Without this, a fresh
    # pipeline run landing between form render and POST would corrupt
    # paired backlink semantics: ``pattern_evaluation_id`` validates
    # against the form-render run's id, but ``candidate_id`` would
    # bind to a NEWER run's candidate row for the same ticker.
    # =====================================================================
    # 22-A -- THE LATCH SEAM.  Everything above this line is UNTOUCHED, in
    # its original order, so the LOCK's clause (c) -- every pre-existing
    # failure branch raises the same exception, with the same message, at the
    # same point -- is true by construction rather than by inspection.
    #
    # THE RECOGNITION READ IS OUTSIDE THE TRANSACTION AND QUERY-FREE.  It
    # parses the operator-submitted envelope and nothing else, so a fill with
    # no usable broker order id costs ZERO additional database queries
    # (LOCK clause (d)) and takes the deferred ``with conn:`` exactly as
    # before.
    # =====================================================================
    from swing.trades.latched_origin import broker_order_id_from_envelope

    _recognised_order_id = (
        None if cfg is None
        else broker_order_id_from_envelope(
            getattr(req, "schwab_source_value_json", None))
    )
    # THE TRIGGER IS "THE REQUEST CARRIES A USABLE ORDER ID", NEVER "THE
    # RECOGNITION FOUND A LINK" (plan S2.2 rule 3, review 22A-R3-01).  A
    # request whose preliminary answer was NO LINK can acquire a matching
    # validity row before the INSERT and would otherwise take the ordinary
    # path on a stale negative.  A negative result is as perishable as a
    # positive one, and the reservation covers both (case 21b).
    _reserve = _recognised_order_id is not None
    if _reserve and conn.in_transaction:
        raise CallerHeldEntryTransactionError(
            "record_entry owns BEGIN IMMEDIATE for an order-id-bearing "
            "request and REJECTS a caller-held transaction rather than "
            "auto-detecting one; an auto-detect guard re-introduces the race "
            "the explicit lock closed. Nothing was written."
        )

    with _entry_transaction(conn, immediate=_reserve):
        return _record_entry_inner(
            conn, req,
            cfg=cfg,
            derived_origin=derived_origin,
            entry_iso=entry_iso,
            warning=warning,
            reserve=_reserve,
        )


class CallerHeldEntryTransactionError(RuntimeError):
    """``record_entry`` was called with an open transaction on the latched
    path.  Single-transaction services own ``BEGIN IMMEDIATE`` / COMMIT /
    ROLLBACK and REJECT a caller-held transaction (CLAUDE.md)."""


@contextlib.contextmanager
def _entry_transaction(conn: sqlite3.Connection, *, immediate: bool):
    """The ONE transaction the entry row is written in.

    ``immediate=False`` is the pre-arc path, byte-for-byte: Python's sqlite3
    implicit DEFERRED transaction via ``with conn:``.

    ``immediate=True`` is the latched path.  ``with conn:`` acquires NO write
    reservation until its first write, so a resolution performed "inside" it
    still reads without reserving and another connection can commit between
    that read and the INSERT.  The explicit ``BEGIN IMMEDIATE`` takes the
    reservation FIRST, following Demand C's shape verbatim including its
    caller-held-transaction refusal.
    """
    if not immediate:
        with conn:
            yield
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise
    else:
        conn.commit()


def _record_entry_inner(
    conn: sqlite3.Connection, req: EntryRequest, *,
    cfg,
    derived_origin: str,
    entry_iso: str,
    warning: str | None,
    reserve: bool,
) -> EntryResult:
    """Never opens or closes a transaction; the caller owns it.

    Every read below therefore sees the world the write lands in, which is the
    entire point of the reservation.
    """
    from swing.trades.latched_origin import (
        LatchedProvenance,
        resolve_latched_provenance,
    )
    from swing.trades.origin import _latest_complete_evaluation_run_id

    resolved_candidate_id: int | None = req.candidate_id

    # THE AUTHORITATIVE RESOLUTION, inside the reservation.  The preliminary
    # answer computed outside it is DISCARDED -- it exists only to decide
    # whether to reserve.
    latched = (
        resolve_latched_provenance(conn, cfg, req) if reserve
        else LatchedProvenance(
            admitted=False, recognised_but_underivable=False,
            decline_reason="no_config" if cfg is None else "no_order_id")
    )

    # THE PE-ANCHOR GUARD, RELOCATED FROM THE ROUTE AND NOT MERELY DEFERRED
    # (review 22A-R9-03).  The route rejects a `pattern_evaluation_id` anchor
    # whose server-derived origin is `manual_off_pipeline`; for order-id-
    # bearing requests the route now defers to here, so WITHOUT this block the
    # deferral would DELETE a live production rejection and the row would be
    # written.  Case 37c is the stable no-link outcome that fails a deferral-
    # without-relocation implementation; every other case in the plan passes
    # one.
    #
    # INSIDE THE TRANSACTION IS THE WHOLE POINT: the guard's input is
    # `derive_trade_origin`, which reads the latest evaluation run -- the same
    # world the race can move.  Evaluated at the route it reads a world that
    # may be stale by the time the row is written.
    if (
        reserve
        and not latched.admitted
        and req.pattern_evaluation_id is not None
        and derived_origin == "manual_off_pipeline"
    ):
        raise PatternEvaluationAnchorError(_PE_ANCHOR_MESSAGE)

    hypothesis_label = req.hypothesis_label
    if latched.admitted:
        # ALL THREE KEYS MOVE TOGETHER (plan S2.6).  A row carrying origin and
        # candidate but a NULL label is incoherent AND permanently
        # uncorrectable: Demand C's `_gate_on_unset_state` refuses a trade
        # carrying any of the three.
        log.info(
            "22-A: fill for %s admitted from latched mandate %s (link %s, "
            "order %s, validity intent %s); writing trade_origin=%s "
            "candidate_id=%s",
            req.ticker, latched.candidate_id,
            latched.order.link_id if latched.order else None,
            latched.order.broker_order_id if latched.order else None,
            latched.order.validity_intent_id if latched.order else None,
            latched.trade_origin, latched.candidate_id,
        )
        if req.candidate_id is not None and req.candidate_id != latched.candidate_id:
            log.warning(
                "22-A: caller-supplied candidate_id %s disagrees with the "
                "latched fire %s for %s; THE LATCH WINS -- it is keyed to a "
                "broker-accepted order rather than to a form render",
                req.candidate_id, latched.candidate_id, req.ticker)
        derived_origin = latched.trade_origin
        resolved_candidate_id = latched.candidate_id
        hypothesis_label = latched.hypothesis_label
    elif latched.recognised_but_underivable:
        # THE HONEST-UNSET ROW, and the ordinary candidate/origin chain is
        # SUPPRESSED rather than allowed to fall back.  For a ticker that is
        # `aplus` in TODAY's latest run the ordinary chain would write
        # `pipeline_aplus` plus TODAY's candidate -- a DIFFERENT mandate from
        # the one this fill demonstrably came from.  Silent-wrong, not
        # honest-NULL (case 12).
        log.warning(
            "22-A: a latched mandate was RECOGNISED for %s (order %s) and "
            "REFUSED (%s); the entry records honest-unset cohort keys rather "
            "than the latest run's candidate, and the submitted "
            "hypothesis_label %r is discarded -- a non-NULL label would make "
            "the row permanently uncorrectable",
            req.ticker,
            latched.order.broker_order_id if latched.order else None,
            latched.decline_reason, req.hypothesis_label)
        derived_origin = "manual_off_pipeline"
        resolved_candidate_id = None
        hypothesis_label = None

    if latched.admitted or latched.recognised_but_underivable:
        pass                      # the ordinary chain is not consulted
    elif resolved_candidate_id is None and derived_origin != "manual_off_pipeline":
        _eval_run_for_candidate: int | None = None
        if req.pattern_evaluation_id is not None:
            _chain_row = conn.execute(
                "SELECT pr.evaluation_run_id FROM pattern_evaluations pe "
                "JOIN pipeline_runs pr ON pr.id = pe.pipeline_run_id "
                "WHERE pe.id = ?",
                (int(req.pattern_evaluation_id),),
            ).fetchone()
            if _chain_row is not None and _chain_row[0] is not None:
                _eval_run_for_candidate = int(_chain_row[0])
        if _eval_run_for_candidate is None:
            _eval_run_for_candidate = _latest_complete_evaluation_run_id(conn)
        if _eval_run_for_candidate is not None:
            _cand_row = conn.execute(
                "SELECT id FROM candidates "
                "WHERE evaluation_run_id = ? AND ticker = ? "
                "ORDER BY id DESC LIMIT 1",
                (_eval_run_for_candidate, req.ticker),
            ).fetchone()
            if _cand_row is not None:
                resolved_candidate_id = int(_cand_row[0])

    trade = Trade(
        id=None, ticker=req.ticker, entry_date=req.entry_date,
        entry_price=req.entry_price, initial_shares=req.shares,
        initial_stop=req.initial_stop, current_stop=req.initial_stop,
        # Phase 7: state lifecycle replaces the legacy `status` column.
        # New entries land in 'entered'; the state-mutation service
        # transitions to 'managing' once the first non-entry fill arrives.
        state="entered",
        watchlist_entry_target=req.watchlist_entry_target,
        watchlist_initial_stop=req.watchlist_initial_stop,
        notes=req.notes,
        hypothesis_label=canonicalize_hypothesis_label(hypothesis_label),
        # Snapshot AS-IS — no re-resolve here (spec §3.6 ToCToU fix).
        # The operator override re-uses canonicalize_hypothesis_label
        # because spec §3.6 specifies identical NFC + control-byte rules
        # for both free-text labels.
        chart_pattern_algo=req.chart_pattern_algo,
        chart_pattern_algo_confidence=req.chart_pattern_algo_confidence,
        chart_pattern_operator=canonicalize_hypothesis_label(req.chart_pattern_operator),
        chart_pattern_classification_pipeline_run_id=req.chart_pattern_classification_pipeline_run_id,
        sector=req.sector,
        industry=req.industry,
        # Phase 7 lifecycle fields (NOT NULL in schema). `trade_origin`
        # comes from derive_trade_origin (B.2); `pre_trade_locked_at`
        # comes from entry_date-derived ISO datetime (Codex R4 M1 fix —
        # was req.event_ts which is the command time, not the actual entry
        # chronology — back-recorded entries broke aggregation).
        trade_origin=derived_origin,
        pre_trade_locked_at=entry_iso,
        # Phase 7 pre-trade decision fields — passed through from the request.
        thesis=req.thesis,
        why_now=req.why_now,
        invalidation_condition=req.invalidation_condition,
        expected_scenario=req.expected_scenario,
        premortem_technical=req.premortem_technical,
        premortem_market_sector=req.premortem_market_sector,
        premortem_execution=req.premortem_execution,
        premortem_additional=req.premortem_additional,
        event_risk_present=req.event_risk_present,
        event_handling=req.event_handling,
        event_type=req.event_type,
        event_date=req.event_date,
        gap_risk_present=req.gap_risk_present,
        gap_risk_handling=req.gap_risk_handling,
        emotional_state_pre_trade=req.emotional_state_pre_trade,
        market_regime=req.market_regime,
        catalyst=req.catalyst,
        catalyst_other_description=req.catalyst_other_description,
        # Phase 13 T2.SB6c T-A.6c.4 OQ-11 + OQ-12 lifecycle backlinks.
        # candidate_id: resolved above via the latest-complete-evaluation-
        # run lookup (Path 1 per plan §B.1); NULL for manual_off_pipeline.
        # pattern_evaluation_id: server-re-derived value from the route
        # handler's 5-tier rejection ladder (T3.SB3 R1 M#2 LOCK).
        candidate_id=resolved_candidate_id,
        pattern_evaluation_id=req.pattern_evaluation_id,
        # Tuition-vs-error: persisted AS-IS from the operator's explicit
        # choice (server-stamp); NEVER suggested from the label here (spec §5).
        entry_intent=req.entry_intent,
    )

    archived = False
    try:
        trade_id = insert_trade_with_event(
            conn, trade, event_ts=req.event_ts, rationale=req.rationale,
        )
        # Phase 9 T-A.7 — stamp risk_policy_id_at_lock from the active
        # policy in the SAME transaction. Spec §3.1.1: preserves
        # at-trade-time semantics for capital_floor / scratch_epsilon /
        # trail-MA periods even when the policy is later superseded.
        # When no active policy exists (operator manually flipped seed
        # inactive), the SELECT sub-query returns NULL → column stays
        # NULL; spec §9.4 backwards-compatibility contract says NULL is
        # legal and read paths fall back to current active policy.
        conn.execute(
            "UPDATE trades SET risk_policy_id_at_lock = "
            "(SELECT policy_id FROM risk_policy WHERE is_active = 1) "
            "WHERE id = ?",
            (trade_id,),
        )
        # Phase 7 Sub-B B.3 — atomic first entry-fill insert in the
        # SAME transaction as the trade row. The fill's
        # _recompute_aggregates updates trades.current_size,
        # current_avg_cost, last_fill_at to authoritative values
        # (fixing the R2 Minor 1 transient half-state that B.1's
        # docstring on insert_trade_with_event warns OTHER callers
        # about — record_entry now satisfies that contract).
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=trade_id,
                # Codex R4 M1: fill_datetime keyed to entry_date for
                # chronology consistency (matches B.4 exit-side fix).
                fill_datetime=entry_iso,
                action="entry",
                quantity=float(req.shares),
                price=req.entry_price,
                manual_entry_confidence=req.manual_entry_confidence,
                # Phase 13 T3.SB1 T-B.1.4 — auto-fill provenance audit
                # columns. Per spec §6.4 + plan §G.2 T-B.1.4. Defaults
                # on the dataclass preserve backward-compat: when
                # EntryRequest is built without these fields (CLI tests
                # / bare cURL), Fill defaults to operator_typed + None.
                fill_origin=req.fill_origin,
                schwab_source_value_json=req.schwab_source_value_json,
                operator_corrected_value_json=(
                    req.operator_corrected_value_json
                ),
                auto_fill_audit_at=req.auto_fill_audit_at,
            ),
            event_ts=req.event_ts,
            rationale=req.rationale,
            # Hotfix 2026-05-05 (operator-witnessed gate finding S3):
            # insert_trade_with_event above already emitted an 'entry'
            # trade_event row; suppress the duplicate emission here.
            emit_event=False,
        )
        wl = get_watchlist_entry(conn, req.ticker)
        if wl is not None:
            archive_watchlist_entry(conn, WatchlistArchiveEntry(
                id=None, ticker=req.ticker, added_date=wl.added_date,
                removed_date=req.entry_date, reason="entered",
                qualification_count=wl.qualification_count,
                last_data_asof_date=wl.last_data_asof_date,
                notes=wl.notes,
            ))
            archived = True
    except sqlite3.IntegrityError as exc:
        # Schema-level safety net (ux_trades_one_open_per_ticker, migration 0004):
        # two concurrent record_entry calls raced past the app-layer list_open_trades
        # check; the partial unique index rejected the second INSERT. Map to the same
        # DuplicateOpenPositionError callers already handle.
        if "UNIQUE" in str(exc) and "trades" in str(exc):
            raise DuplicateOpenPositionError(
                f"Already an open position in {req.ticker} (race-detected)"
            ) from exc
        raise

    return EntryResult(trade_id=trade_id, warning=warning, watchlist_archived=archived)


class PatternEvaluationAnchorError(ValueError):
    """The request carries a ``pattern_evaluation_id`` anchor while the
    server-derived origin is ``manual_off_pipeline`` and no latched mandate
    admitted.

    RELOCATED FROM THE ROUTE, not invented here (review 22A-R9-03).  The
    message is the route's own, so the operator sees the same text whichever
    surface makes the refusal.
    """


_PE_ANCHOR_MESSAGE = (
    "Trade entry rejected: pattern_evaluation_id anchor "
    "present but server-derived trade_origin is "
    "manual_off_pipeline. The candidate row may have rolled "
    "out of the latest pipeline run; the form has been "
    "regenerated."
)
