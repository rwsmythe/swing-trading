"""Trade entry service — wraps repo with cap enforcement + watchlist archival."""
from __future__ import annotations

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
) -> EntryResult:
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
        hypothesis_label=canonicalize_hypothesis_label(req.hypothesis_label),
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
    )

    archived = False
    try:
        with conn:
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
