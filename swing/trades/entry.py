"""Trade entry service — wraps repo with cap enforcement + watchlist archival."""
from __future__ import annotations

import contextlib
import dataclasses
import logging
import sqlite3
import sys
import unicodedata
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from swing.data.db import _resolve_main_db_path, open_connection
from swing.data.models import Fill, Trade, WatchlistArchiveEntry
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import (
    find_trade_id_by_attempt_id,
    insert_trade_with_event,
    list_open_trades,
    validate_attempt_id,
)
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


# ===========================================================================
# 22-A3 -- THE LOG-CONTAINMENT IDIOM, STATED ONCE.
#
# **A FAILING LOGGING HANDLER MUST NEVER CHANGE A FUNCTION'S RESULT OR WHICH
# EXCEPTION PROPAGATES** (Codex 22A-R11-03).  SIX CLEANUP HANDLERS share the
# class -- **ONE in this module and FIVE in
# `cohort_provenance_correction.py`** -- reached through EIGHT branch-specific
# call expressions, because two of the handlers pick their message from
# `conn.in_transaction` and so call the idiom twice each (Codex A3R2-06: the
# predecessor comment said "two here and four", mixing this module's CALL
# EXPRESSIONS with the cohort module's HANDLERS and getting the second number
# wrong -- an inconsistency in exactly the completeness claim that is supposed
# to make "did site N get it" mechanical).  The fix is a shared idiom rather
# than eight local edits.  `ascii_safe` / `safe_text` are PART of the
# idiom rather than adjacent to it: a containment guard that formats a value
# which can raise, or which produces a string that cannot be encoded, is a
# containment guard that can raise.
#
# These four are NOT in `__all__`: that list is the entry service's
# caller-facing surface.
# ===========================================================================


def ascii_safe(text: str) -> str:
    """ASCII-only, and NEVER an exception.

    Two independent reasons, both MEASURED rather than reasoned about:

    * A Windows console encoder raises on any character OUTSIDE ITS
      REPERTOIRE, and these strings reach `click.echo` (`pytest`'s `capsys`
      bypasses the OS encoder and hides it).  **The claim is deliberately
      NOT "cp1252 raises on non-ASCII"** (Codex A3R3-07): cp1252 encodes a
      great deal of non-ASCII, including the accented characters and the
      em-dash this arc's own tests inject.  What it cannot encode is
      everything outside its 256 slots -- and NO codec can encode a LONE
      SURROGATE, which is the case that actually reaches `HTMLResponse`.
      ASCII coercion is chosen because it is safe under EVERY output
      encoding, not because non-ASCII is inherently fatal.
    * A custom `__repr__` may return a string containing a LONE SURROGATE.
      `html.escape` preserves it and `HTMLResponse` then raises
      `UnicodeEncodeError` encoding the body -- one frame OUTSIDE every
      guard in the degraded path, producing exactly the durable-row-plus-500
      outcome 22-A3 exists to remove.

    `backslashreplace` is ASCII-SAFE AND VISIBLY ESCAPED -- **not lossless,
    and the earlier word was wrong** (Codex A3R4-08): the mapping is NOT
    injective, because an input that already contains the six literal
    characters of an escape and an input carrying the character it denotes
    both render identically.  It is a DIAGNOSTIC rendering, not an encoding
    the original can be recovered from, and nothing here needs it to be.  It
    cannot itself fail on a surrogate (measured: a lone surrogate renders as
    literal escape text).

    **THE BUILT-IN SLOTS, NOT THE VIRTUAL METHODS** (Codex A3-AR-01, VERIFIED
    BY EXECUTION).  `text.encode(...)` and `.decode(...)` are overridable, and
    an exception's `__repr__` may LEGALLY return a `str` SUBCLASS whose
    `encode` returns an object whose `decode` returns a lone surrogate.
    Measured on this runtime: that string came back from `ascii_safe` with
    `.isascii()` False, reached `HTMLResponse` through the route's degraded
    path, and raised `UnicodeEncodeError` encoding the body -- INSIDE the
    outer `except`, where nothing catches it, i.e. the exact
    durable-row-plus-500 outcome this idiom exists to remove.  `str.encode`
    and `bytes.decode` called as unbound base functions cannot be overridden
    away.

    **AND THE POSTCONDITION IS ASSERTED RATHER THAN ARGUED**: the return is
    checked to be an EXACT `str` that is ASCII, because a helper whose whole
    contract is "the result is safe to interpolate" should establish that by
    measurement at the boundary, not by a chain of reasoning about which
    methods the base slots dispatch to.
    """
    try:
        out = bytes.decode(
            str.encode(text, "ascii", "backslashreplace"), "ascii")
    except BaseException:  # noqa: BLE001 -- the CLASS, not a roster
        return "<a value that could not be rendered as text>"
    if type(out) is not str or not out.isascii():
        return "<a value that could not be rendered as text>"
    return out


def safe_text(value: object) -> str:
    """`repr(value)`, ASCII-coerced, and NEVER an exception.

    Measured: an exception class overriding `__repr__` (and `__str__`) to
    raise is constructible, and the values formatted by the containment
    idiom and by the web route's degraded notice are exceptions raised by
    arbitrary code.
    """
    try:
        return ascii_safe(repr(value))
    except BaseException:  # noqa: BLE001
        pass
    try:
        return ascii_safe(str(value))
    except BaseException:  # noqa: BLE001
        pass
    return "<an object whose repr() and str() both raised>"


#: The evidence a cleanup site's caller is judged on, paired with the ACTUAL
#: base getset descriptors.
#:
#: **`BaseException.__getattribute__` DOES NOT BYPASS A SUBCLASS DATA
#: DESCRIPTOR** (Codex A3R4-01, VERIFIED BY EXECUTION -- and it corrects a
#: claim this module carried from the day the idiom was written).  It performs
#: ORDINARY lookup on `type(escaping)`, so a subclass `@property` named `args`
#: IS consulted and returns whatever it likes.  The claim happened to hold for
#: `__notes__`, which has NO base descriptor and is therefore a plain instance
#: attribute, and was wrongly generalised to these three, which DO have one.
#: Measured: `BaseException.__getattribute__(e, "args")` returned the
#: PROPERTY's value, while `BaseException.__dict__["args"].__get__(e, ...)`
#: returned the real slot and `.__set__` wrote it.
#:
#: Using the descriptors directly also closes the CASCADE the same finding
#: named: with generic access, restoring field N could run field N+1's hostile
#: GETTER, which re-corrupts field N after it was already put back.  A base
#: getset descriptor runs no user code at all.
_EVIDENCE_FIELDS = ("args", "__cause__", "__context__")
_EVIDENCE_SLOTS = tuple(BaseException.__dict__[_n] for _n in _EVIDENCE_FIELDS)
#: "this field could not be read", distinct from a legitimate `None`.
_UNREADABLE = object()


def _evidence_snapshot(escaping: BaseException) -> tuple:
    """`(args, __cause__, __context__)` read through the BASE slots.

    **PER FIELD, NOT ALL-OR-NOTHING** (Codex A3R3-03).  The predecessor read
    all three inside ONE `try` and returned `None` if any of them raised -- so
    a single hostile `args` data descriptor disabled preservation of
    `__cause__` and `__context__` too, widening the residue from "the
    diagnostic note cannot attach" to "the cleanup exception's chaining can be
    destroyed".  Each field now carries its own sentinel, so one unreadable
    field costs exactly itself.
    """
    out = []
    for slot in _EVIDENCE_SLOTS:
        try:
            out.append(slot.__get__(escaping, type(escaping)))
        except BaseException:  # noqa: BLE001 -- the CLASS
            out.append(_UNREADABLE)
    return tuple(out)


def _restore_evidence(escaping: BaseException, snapshot: tuple) -> None:
    """Put back anything a logging handler or a descriptor changed.

    Never raises.  A field that could not be READ is skipped rather than
    written with a sentinel.

    **WHAT IS RESTORED IS THE EXCEPTION'S OWN FIELDS, NOT THE OBJECT GRAPH
    UNDER THEM** (Codex A3R4-02, adjudicated with a MEASUREMENT that refutes
    half its premise).  The finding said `args` "can legally be assigned a
    mutable value"; it cannot -- `BaseException`'s own setter COERCES to a
    tuple (measured: assigning a two-element list reads back as an exact
    two-element tuple), and the base descriptor is what this function writes
    through.  What survives is narrower and is DECLARED: if an element INSIDE
    the args tuple is itself mutable and something mutates it in place, the
    tuple's identity is unchanged and nothing here notices.  Deep-copying an
    arbitrary object graph on a cleanup path would cost more than it protects.
    """
    for slot, value in zip(_EVIDENCE_SLOTS, snapshot, strict=True):
        if value is _UNREADABLE:
            continue
        try:
            if slot.__get__(escaping, type(escaping)) is not value:
                slot.__set__(escaping, value)
        except BaseException:  # noqa: BLE001 -- the CLASS
            continue


def _note_landed(escaping: BaseException, note: str) -> bool:
    """Is `note` READABLE back off the exception?

    **VERIFIED, NOT ASSUMED** (Codex A3R2-03, verified by execution).
    `BaseException.add_note` can RETURN SUCCESSFULLY and still lose the note:
    a `__notes__` DATA DESCRIPTOR whose getter SYNTHESIZES a fresh list has
    the note appended to a temporary that is then discarded.  Measured: the
    read-back came out empty while `add_note` reported success.  A helper
    whose entire purpose is refusing invisible failures may not take an
    attach on trust.
    """
    try:
        notes = BaseException.__getattribute__(escaping, "__notes__")
    except BaseException:  # noqa: BLE001 -- the CLASS
        return False
    try:
        # **IDENTITY, OR EXACT-`str` EQUALITY -- NEVER BARE `==`** (Codex
        # A3R4-03).  A `str` subclass whose `__eq__` returns True for
        # everything made a synthesizing getter's placeholder read as "the
        # note landed", skipping the repair whose setter WOULD have stored the
        # real one -- a false success in the one helper whose entire job is
        # refusing invisible failures.
        return any(n is note or (type(n) is str and n == note)
                   for n in list(notes))
    except BaseException:  # noqa: BLE001 -- a hostile iterator reads as absent
        return False


def log_contained(logger: logging.Logger, msg: str,
                  *args: object) -> BaseException | None:
    """Emit an ERROR record, containing a failure OF THE SINK.

    **A FAILING LOGGING HANDLER MUST NEVER CHANGE A FUNCTION'S RESULT OR
    WHICH EXCEPTION PROPAGATES** (Codex 22A-R11-03).  A logging sink is
    caller-installed infrastructure this package does not control, and
    every call site is a CLEANUP handler -- the place where an exception is
    already in flight and its identity is the caller's only evidence about
    what happened.  Measured pre-fix: a sink whose `emit()` raised replaced
    a `KeyError` cleanup error with its own `RuntimeError` and dropped the
    `raise ... from ...` chaining with it.

    Returns the sink's exception, or `None`.  It is RETURNED rather than
    swallowed because a silent `pass` trades one invisible failure for
    another (the R10-04 standard); each caller decides how to surface it.
    """
    try:
        logger.error(msg, *args)
    except BaseException as log_error:  # noqa: BLE001 -- the CLASS
        return log_error
    return None


def log_contained_note(logger: logging.Logger, escaping: BaseException,
                       msg: str, *args: object) -> None:
    """`log_contained` for a site that is about to RAISE `escaping`.

    The sink's failure is attached as a NOTE, so it travels in the
    traceback while the exception's TYPE, its args, its `__cause__` and its
    `__context__` are untouched -- the property the six call sites are
    judged on.

    **The attach goes through `BaseException.add_note` EXPLICITLY, not
    through `escaping.add_note`.**  `add_note` is overridable, and an
    overriding subclass that raises would otherwise make this helper
    SWALLOW the sink failure entirely -- the invisible failure its own
    docstring forbids.  Measured: the base implementation lands the note on
    exactly such a subclass.

    **AND THE BASE IMPLEMENTATION ITSELF CAN RAISE** (measured: assigning a
    TUPLE to `__notes__` makes it raise `TypeError: Cannot add note:
    __notes__ is not a list`).  So a malformed `__notes__` is REPAIRED
    in place -- every existing note preserved -- and the attach retried
    once.

    **THE RESIDUE, MEASURED AND DECLARED, AND NARROWED THREE TIMES.**  An
    exception that defines `__notes__` as a DATA DESCRIPTOR which REFUSES the
    write -- whether by raising (Codex A3-AR-03) or by SILENTLY DISCARDING it
    while a synthesizing getter returns a fresh list each read (Codex
    A3R2-03) -- cannot receive a note at all: a data descriptor is consulted
    by the base slots themselves, so there is no representation left to write
    into.  Both verified by execution.  The attach is now VERIFIED BY
    READ-BACK rather than trusted, so the helper no longer reports success in
    that case; it simply returns, having done everything available to it.

    The load-bearing property is UNAFFECTED either way -- the original
    exception still escapes with its type, args and chaining intact; what is
    lost is the diagnostic note, and this docstring says so rather than
    claiming the earlier, DISPROVED "only a non-BaseException defeats it".
    """
    # **THE PRESERVATION IS ENFORCED, NOT ASSUMED** (Codex A3R2-02, VERIFIED
    # BY EXECUTION).  `logger.error(msg, *args)` hands the escaping exception
    # to caller-installed handlers, and a handler that FORMATS the record
    # calls `__str__` on it -- which an exception may legally override to
    # MUTATE ITSELF and then raise.  Measured: `args` went from
    # `('the real args',)` to `('CORRUPTED',)` and `__cause__` from a
    # `ValueError` to `None`, while the sink's own exception was contained
    # exactly as advertised.  **Containing the sink's exception is not the
    # same as preserving the evidence, and the evidence IS this helper's
    # contract** -- at the rollback and savepoint sites the original error and
    # its chaining are what say whether a transaction may still be open.
    #
    # **AND THE PRESERVATION SPANS THE WHOLE SEQUENCE, NOT JUST THE LOG CALL**
    # (Codex A3R3-02).  Restoring immediately after logging left every later
    # step outside the boundary -- `safe_text(log_error)` (and `log_error` CAN
    # BE `escaping` itself, when a handler re-raises it), `add_note`, the
    # read-back, and the repair's own read and write.  A hostile `__notes__`
    # descriptor can mutate `args` / `__cause__` / `__context__` from its
    # getter or setter, and those mutations landed AFTER the sole restoration
    # and survived.  The restore is now a `finally` over the entire body.
    snapshot = _evidence_snapshot(escaping)
    try:
        _attach_sink_failure_note(logger, escaping, msg, *args)
    finally:
        _restore_evidence(escaping, snapshot)


def _attach_sink_failure_note(logger: logging.Logger, escaping: BaseException,
                              msg: str, *args: object) -> None:
    """`log_contained_note`'s body, wrapped by its evidence guard."""
    log_error = log_contained(logger, msg, *args)
    if log_error is None:
        return
    # **OBSERVATION-ONLY WORDING** (Codex A3-AR-06, VERIFIED BY EXECUTION):
    # `logger.error` raising means A HANDLER raised, NOT that no sink received
    # the record -- measured, an earlier handler emitted successfully before a
    # later one raised. A flat "could not be emitted" is the same after-effect
    # fallacy this project already corrected for rollback messages two arcs
    # ago, and a cleanup warning that is WRONG about the state teaches an
    # operator to distrust the right ones.
    note = (f"the ERROR log for this cleanup failure could not be emitted "
            f"cleanly -- a logging handler RAISED ({safe_text(log_error)}). "
            f"Some sinks may have received the record and some may not; the "
            f"condition it described is unchanged.")
    with contextlib.suppress(BaseException):
        BaseException.add_note(escaping, note)
    # **THE ATTACH IS VERIFIED** (Codex A3R2-03): `add_note` can return
    # successfully and still lose the note against a synthesizing descriptor,
    # so the early return is gated on READING IT BACK rather than on the call
    # not raising.
    if _note_landed(escaping, note):
        return
    try:
        # **THE READ BYPASSES `__getattribute__` TOO** (Codex 22A3-R6-05,
        # verified by execution).  A subclass overriding
        # `__getattribute__` to raise for `__notes__` defeats BOTH
        # `BaseException.add_note` (which reads the attribute through the
        # override) AND a plain `getattr(..., None)` -- whose default
        # swallows only `AttributeError`, and the override raises
        # `TypeError`.  MEASURED: `BaseException.__getattribute__` raises
        # a plain `AttributeError` on such an object, i.e. "absent", and
        # `BaseException.__setattr__` then installs the list successfully.
        # Read and write both go through the base slots, symmetrically.
        try:
            existing = BaseException.__getattribute__(escaping, "__notes__")
        except BaseException:  # noqa: BLE001 -- read it as ABSENT
            # `BaseException` rather than `AttributeError` (Codex A3-AR-03,
            # verified by execution): a subclass can define `__notes__` as a
            # DATA DESCRIPTOR whose getter raises `TypeError`, and the base
            # slot consults the descriptor, so the narrower clause let the
            # read escape into the outer guard and the sink failure was lost
            # without even attempting the write.
            existing = None
        # **EXACT TYPES ONLY** (Codex A3-AR-03, verified by execution): a
        # `tuple` SUBCLASS whose `__iter__` raises made `list(existing)` raise,
        # and the outer guard then discarded the sink failure silently -- the
        # invisible failure this helper exists to refuse. Anything that is not
        # one of the four exact built-in containers is rendered through
        # `safe_text`, which is total.
        if type(existing) is list:
            repaired = list(existing)
        elif existing is None:
            repaired = []
        elif type(existing) in (tuple, set, frozenset):
            repaired = list(existing)
        else:
            repaired = [safe_text(existing)]
        repaired.append(note)
        # **`BaseException.__setattr__`, NOT `escaping.__notes__ = ...`**
        # (Codex 22A3-R5-04).  A subclass overriding `__setattr__` to
        # raise would otherwise defeat the repair -- and the base slot
        # bypasses the override for exactly the reason
        # `BaseException.add_note` does one line up.  MEASURED on this
        # runtime: a class whose `__setattr__` always raises rejects
        # `add_note`, and the direct base `__setattr__` still installs the
        # repaired list.
        BaseException.__setattr__(escaping, "__notes__", repaired)
    except BaseException:  # noqa: BLE001
        return
    # **THE REPAIR IS VERIFIED TOO** (Codex A3R3-04).  Read-back gated only
    # the FIRST attach, so a STATEFUL descriptor that discards its first
    # setter call and stores the second silently lost the note while the
    # comments claimed the attachment was verified.  ONE bounded retry, then
    # give up -- the residue is declared rather than looped over.
    if _note_landed(escaping, note):
        return
    with contextlib.suppress(BaseException):
        BaseException.__setattr__(escaping, "__notes__", repaired)


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
    """**A STATEMENT ABOUT THE DURABLE STATE OF THE LEDGER, never about
    whether every subsequent step succeeded** (CHARC's contract, ruled
    2026-09-01, from Codex 22A-FIX-R9-03).

    ``post_commit_warnings`` carries what went wrong AFTER the entry became
    durable.  It defaults to empty, so every existing caller and construction
    is unchanged; a caller that wants to surface them reads the field.
    """

    trade_id: int
    warning: str | None
    watchlist_archived: bool
    post_commit_warnings: tuple[str, ...] = ()


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


# ===========================================================================
# 22-A4 -- THE PER-ATTEMPT IDENTITY.
#
# The primitive 22-A's declared residual is blocked on: a token CO-DURABLE
# with the row it identifies (written by the SAME INSERT in the SAME
# transaction -- anything else is a stamp, gotcha #30) and UNIQUE PER ATTEMPT
# (it survives rollback-and-retry, which a rowid does not: the engine hands a
# rolled-back id straight to the next insert).
#
# RD's canonical reading of "never reusable", ruled 2026-09-06 and binding on
# every future appeal: the mechanism must contain NO PATH THAT REISSUES a
# token.  The rowid fails because the ENGINE ITSELF reissues; `uuid4` has no
# reissue path at all, so a repetition would be an RNG failure rather than a
# behaviour of the mechanism.
# ===========================================================================


def _mint_attempt_token() -> str:
    """One canonical lowercase uuid4 string per attempt.

    A NAMED module-level function rather than an inline ``uuid.uuid4()`` call,
    so a test can plant a deterministic token and can make the mint raise.
    That is a testability decision, stated so it is not mistaken for
    indirection.  ``uuid.uuid4`` is reached through the MODULE so a test can
    patch one level below this function -- which is the only way to exclude a
    constant mint, since every ``_mint_attempt_token``-level patch blesses one.
    """
    return str(uuid.uuid4())


@dataclass(frozen=True)
class _AttemptIdentity:
    """What the attempt knows about itself before the transaction opens.

    ``db_path`` comes from THE CONNECTION (``PRAGMA database_list``) and never
    from ``cfg``: a caller may legally pass a connection to a different
    database than ``cfg`` names (every test does) and ``cfg`` may be ``None``.
    Sourcing it from configuration would be gotcha #30's shape one level up --
    a system-level value standing in for a per-object fact -- and would produce
    the worst possible error, a probe that reads the WRONG database.
    """

    token: str | None = None
    db_path: Path | None = None


def _begin_attempt_identity(conn: sqlite3.Connection) -> _AttemptIdentity:
    """Mint the token and capture the database path, CONTAINED.

    **NO ORDINARY FAILURE OR MALFORMED RETURN OF THE IDENTITY APPARATUS MAY
    CONVERT AN ENTRY THAT WOULD HAVE SUCCEEDED INTO A FAILURE.**  When it
    fails, ``token`` and/or ``db_path`` are ``None``, the settle is
    unavailable, and the behaviour is exactly today's.

    **THE RESULT IS VALIDATED, NOT ONLY THE CALL.**  A mint that RETURNS
    ``""`` / ``"short"`` / ``bytes`` raises nothing, so containment around the
    CALL does not cover it -- and the repo's pre-write validator would then
    reject it and fail an entry that would have succeeded, which is the one
    thing this helper exists to prevent, arriving through the containment's own
    blind spot.  Validation goes through ``validate_attempt_id``, **the SAME
    function the repo's pre-write guard calls**, because two hand-written
    predicates over one column are a mirror pair whose dangerous drift is the
    one where THIS side admits what the WRITE side refuses.

    ``Exception``, not ``BaseException``, and the asymmetry is the point: this
    runs PRE-COMMIT, where nothing is durable and failing is the HONEST answer,
    so a ``KeyboardInterrupt`` or ``SystemExit`` must propagate.  (That is the
    mirror image of 22-A3's route guard, which catches ``BaseException``
    precisely because it runs POST-commit.)

    TWO contained arms, and BOTH route through the module's ``log_contained``
    idiom: a raising log handler at either of them would otherwise convert a
    contained failure into a failed entry.

    The token is written even when ``db_path`` is ``None`` (an in-memory
    database, where no fresh connection to the same data is possible).  It
    costs nothing and leaves the row identifiable for forensics; only the probe
    is unavailable.
    """
    try:
        token = _mint_attempt_token()
        validate_attempt_id(token)
    except Exception as mint_error:  # noqa: BLE001 -- the CLASS
        log_contained(
            log,
            "22-A4: the attempt-identity mint failed or returned a value the "
            "single admission authority refuses (%s). The entry proceeds with "
            "NO token; only the settle-by-identity probe is unavailable.",
            safe_text(mint_error))
        return _AttemptIdentity()
    try:
        db_path = _resolve_main_db_path(conn)
    except Exception as path_error:  # noqa: BLE001 -- the CLASS
        log_contained(
            log,
            "22-A4: the attempt's database path could not be resolved from "
            "the connection (%s). The token is still written; only the "
            "settle-by-identity probe is unavailable.",
            safe_text(path_error))
        db_path = None
    return _AttemptIdentity(token=token, db_path=db_path)


def _read_resolution(conn: sqlite3.Connection, *, attempted: bool) -> str:
    """NAME the physical transaction state.  **NON-MUTATING**: it issues no
    SQL, performs no rollback, and cannot change what escapes.

    ``conn.in_transaction`` is an attribute read on the handle, not a
    statement, so this is safe to call on a connection whose rollback raised
    -- the one RD's rule (i) says must not be READ FROM.  ``attempted`` says
    whether THIS FRAME issued the rollback, which is the only thing
    distinguishing ``rolled_back`` from ``not_needed`` once the state is
    resolved.

    **THE SHARED THING IS THE READ, NEVER THE ROLLBACK.**  An earlier shape of
    this helper owned a rollback and contained its failure; it could not both
    do that and preserve the immediate ladder's ``raise cleanup_error from
    write_error``, and on the deferred path it retried on a wounded connection
    BEFORE the failure had been detected.  So the immediate path keeps its own
    rollback inline in its own pre-arc ladder, the deferred path performs none
    at all, and what the two share is this read.

    Contained in the ALARM direction for the same reason as
    ``_exit_rollback_failed``: an unreadable state is ``still_open``, which
    the settle gate REFUSES.  Refusing a settle costs today's behaviour;
    admitting one on an unknown state is the direction rule (i) forbids.
    """
    try:
        open_ = bool(conn.in_transaction)
    except BaseException:  # noqa: BLE001 -- the CLASS, and it ALARMS
        return "still_open"
    if open_:
        return "still_open"
    return "rolled_back" if attempted else "not_needed"


#: The ``__context__`` base getset descriptor, from the SAME source as
#: ``_EVIDENCE_SLOTS`` -- see the idiom at the head of this module.  A base
#: descriptor runs NO user code, which is the whole reason it is the read:
#: ``escaping.__context__`` is an ORDINARY attribute lookup, so a
#: ``sqlite3.OperationalError`` subclass defining ``__context__`` as a data
#: descriptor reads whatever it likes.  MEASURED on CPython 3.14.2: a getter
#: returning ``None`` made the bare read answer False while the real
#: ``OperationalError`` sat in the slot -- a FALSE NEGATIVE that admits a read
#: rule (i) would have refused; a getter that RAISES replaced the escaping
#: exception outright.
_CONTEXT_SLOT = BaseException.__dict__["__context__"]


def _exit_rollback_failed(escaping: BaseException,
                          ambient: BaseException | None) -> bool:
    """Did ``sqlite3.Connection.__exit__``'s OWN rollback raise?

    CALLED ONLY when the entry body completed and the commit's return was NOT
    observed.  Within that scope CPython's ``pysqlite_connection_exit_impl``
    -- the branch whose comment reads "Commit failed; try to rollback in order
    to unlock the database.  If rollback also fails, chain the exceptions." --
    leaves exactly two shapes:

      * rollback SUCCEEDS -> ``PyErr_SetRaisedException`` re-raises the
        COMMIT's exception, whose ``__context__`` is whatever the THREAD was
        already handling: ``ambient``, captured immediately before the
        ``with``, or ``None``;
      * rollback FAILS    -> ``_PyErr_ChainExceptions1`` raises the ROLLBACK's
        exception with the COMMIT's chained beneath it as ``__context__``,
        and the COMMIT's exception is never the ambient object.

    So within the scope, a ``__context__`` that is non-None AND IS NOT THE
    AMBIENT OBJECT is a link ``__exit__`` added.

    **SOURCE, ANCHORED ON CONTENT AND PINNED BY THE UPSTREAM DIGEST -- never
    on bare line numbers, and never on a local copy's hash.**  A line number
    into a file no reader here can open is unverifiable, and a local copy's
    digest pins WHICH BYTES WERE READ while saying nothing about WHOSE they
    were.  Grep the function name above, or the verbatim comment above, in:

      CPython v3.14.2, ``Modules/_sqlite/connection.c``
      fetched from
      ``https://raw.githubusercontent.com/python/cpython/v3.14.2/Modules/_sqlite/connection.c``
      UPSTREAM sha256
      ``8cc0d9df05860c0b3fe6929ff392f8f85c9e1a5ef89c0cba31ab09ba03b3369e``,
      80,695 bytes.

    **THE EXCLUSION IS BY ``is``-IDENTITY, NEVER EQUALITY.**  Equality would
    consult a hostile ``__eq__``, which is the same class of defect as the
    attribute read this function refuses to make.

    **IT IS DELIBERATELY FAIL-OPEN TOWARD THE ALARM, and the asymmetry is the
    argument.**  A FALSE POSITIVE costs the settle -- exactly today's
    behaviour.  A FALSE NEGATIVE admits a read rule (i) would have refused.
    So the slot read is contained in the ALARM direction: an unreadable
    context is treated as a rollback failure.

    **THE DECLARED RESIDUAL, rather than a claim of impossibility:** if the
    object ``__exit__`` chains beneath the rollback failure IS the captured
    ambient object, this answers False.  It is not constructible on the
    production path -- the chained object is the COMMIT's exception, raised
    fresh by SQLite inside ``__exit__``, and a freshly-raised exception is not
    one the caller was already handling -- and the rest of the gate still
    binds: a resolved transaction, a token and a ticker match are all still
    required.
    """
    try:
        context = _CONTEXT_SLOT.__get__(escaping, type(escaping))
    except BaseException:  # noqa: BLE001 -- the CLASS, and it ALARMS
        return True
    return context is not None and context is not ambient


#: The probe's busy timeout, BOUNDED and NAMED.  The project default is 30 s
#: (`DEFAULT_BUSY_TIMEOUT_MS`); a lost-commit probe that hangs a money-bearing
#: web submit for thirty seconds is a poor trade when the fallback -- re-raise,
#: the alarm -- is the safe direction anyway.  2 s is long enough to outlast a
#: passing lock and short enough that the operator sees an answer.  Pinned by
#: test (pr1), which asserts the NUMBER: a silent restoration of the project
#: default is exactly the shape a value-free assertion cannot see.
_PROBE_BUSY_TIMEOUT_MS = 2000


def _durability_probe(db_path: Path, attempt_id: str,
                      escaping: BaseException) -> tuple[int, str] | None:
    """Read the DURABLE ledger for this attempt's token, on a FRESH
    connection.  Returns the repo's ``(id, ticker)`` tuple, or ``None``.

    **THE CONNECTION IS FRESH BY CONSTRUCTION** -- ``open_connection`` on the
    path, never the writer's handle.  That is the half of R10-02 closed by
    construction rather than by discipline, and (RD-a2) pins it.

    **IT OPENS THROUGH A ``file:...?mode=rw`` URI, NOT A BARE PATH.**
    ``open_connection`` calls bare ``sqlite3.connect(...)``, **which CREATES
    the file when it is absent** -- so if the database is moved or renamed
    between the mint's path capture and this read, a bare path would write an
    empty database and then answer ABSENT: a filesystem artifact created on an
    already-failing money path, by the mechanism whose entire purpose is to
    observe without acting.  ``mode=rw`` and NOT ``mode=ro`` deliberately: on
    a WAL database a read-only connection can need to CREATE the ``-shm`` file
    and fails when it cannot, which is a new failure mode on the exact path
    that must be reliable when things are already going wrong.  ``rw`` buys
    the whole of the defect at no new risk.  (Tightening to ``ro`` is a
    candidate for a later arc, named here rather than left unexamined.)
    ``Path(...).resolve().as_uri()`` percent-encodes, so a path containing
    ``?`` or ``#`` cannot inject a URI parameter.

    **``open_connection``, not ``connect``:** ``connect`` adds a
    schema-version check -- another statement and another failure mode -- on a
    path whose entire job is to be reliable when things are already going
    wrong.  The schema version cannot have changed underneath us.

    **THE URI CARRIES ``cache=private``, AND THAT IS A CONSTRUCTION-TIME
    GUARANTEE, NOT A RUNTIME CHECK** (RD's `B-3` ruling, 2026-09-08).  Shared-
    cache mode is the only way a second connection could observe uncommitted
    data.  It is enabled nowhere in this repository today -- but that is a
    claim about the ABSENCE of a writer, which has a shelf life the moment a
    dependency or C extension flips the process-wide default; ``cache=private``
    closes the case at the URI instead of resting on that absence.  A runtime
    branch checking ``PRAGMA read_uncommitted`` would still be defensive dead
    code whose own test could only assert the pragma's default (that pragma
    only has effect UNDER shared cache, so a 0 reading is consistent with a
    shared-cache connection too) -- the precondition is pinned by test (h)'s
    assertion on the URI itself, which is the right instrument for a
    construction-time property.

    **THE CLOSE IS CONTAINED, and the ORDERING is the requirement:** a
    ``close()`` that raises AFTER a successful read must not discard the read.
    A naive ``finally: probe.close()`` throws the valid result away and makes
    ``record_entry`` re-raise **over a durable entry** -- clause 1's own
    subject, arriving inside the machinery built to serve it.  ``escaping`` is
    taken as a parameter for exactly this: the failure is reported through
    ``log_contained_note`` on the exception that would otherwise escape, which
    is the only object at this site whose evidence the caller will ever read.
    (S2.3's pseudocode showed two parameters; the third is what makes (pr2)'s
    named reporting channel reachable at all -- the same correction
    ``A4-R4-6`` made to ``_settle_by_attempt_identity``'s signature, for the
    same reason.)
    """
    probe = open_connection(
        Path(db_path).resolve().as_uri() + "?mode=rw&cache=private",
        uri=True,
        busy_timeout_ms=_PROBE_BUSY_TIMEOUT_MS,
    )
    try:
        found = find_trade_id_by_attempt_id(probe, attempt_id)
    except BaseException:
        # The READ failed.  Close best-effort and let the caller's own
        # containment decide what the failure means; nothing here may become
        # the exception the operator sees.
        with contextlib.suppress(BaseException):
            probe.close()
        raise
    try:
        probe.close()
    except BaseException as close_error:  # noqa: BLE001 -- the CLASS
        log_contained_note(
            log, escaping,
            "22-A4: the durability probe READ SUCCEEDED and its connection "
            "could not be closed (%s). The read is KEPT -- discarding a valid "
            "answer because the tidy-up failed would report a durable entry "
            "as a failure.", safe_text(close_error))
    return found


def _settle_by_attempt_identity(
        attempt: _AttemptIdentity, outcome: _CommitOutcome,
        req: EntryRequest,
        post_commit_error: BaseException) -> tuple[int, str] | None:
    """CLAUSE 2: the commit's own return was lost -- is the attempt DURABLE?

    Returns the probe's ``(id, ticker)`` tuple UNCHANGED, or ``None``, which
    is **THE ALARM**: the caller re-raises, which is today's behaviour.  There
    is no settlement dataclass and none is needed.

    **THE ESCAPING EXCEPTION IS A PARAMETER** (`A4-R3-5`): this helper must
    attach its own failures to THAT object through ``log_contained_note``, and
    it cannot reach it otherwise.

    ``None`` unless **ALL** of the following are observed:

    1. **the entry body ran to completion.**  This is ``record_entry``'s OWN
       pre-arc guard (``if result is None: raise``), which raises before this
       helper is ever called -- so the condition is enforced by the CALLER and
       this helper does not re-check what it cannot observe.  (RD-a5) asserts
       the caller-side obligation rather than pinning the callee's absence,
       which is gotcha #31's shape and the reason the removal of the old
       ``body_completed`` field is not merely a deletion.
    2. ``resolution in {"not_needed", "rolled_back"}`` **AND**
       ``cleanup_raised`` is False.  RD's rule (i), taken LITERALLY: *if the
       rollback itself raises, the connection is DISCARDED and NO read is
       attempted on it* -- so a raising rollback refuses the read **even when
       the state re-read shows the rollback took effect.**  Both fields are
       checked because they are two different facts: ``resolution`` describes
       the TRANSACTION, ``cleanup_raised`` describes the CALL.  ``"unattempted"``
       is a BELT rather than an expected value: ``_read_resolution`` runs on
       every path that can reach this gate, so it should be unreachable here
       -- and it is rejected anyway, because the alternative is a gate whose
       safety depends on an exhaustiveness argument about assignment
       placement.  **Rule (i) forecloses nothing:** in each refusal branch the
       refused read would have answered ABSENT, which is what the refusal
       produces.
    3. the attempt has BOTH a token and a database path.
    4. the probe returns a row, **and its ticker matches the request's.**

    **THE RETURNED ``trade_id`` COMES FROM THE PROBE, NOT FROM
    ``lastrowid``.**  ``result.trade_id`` is what the INSERT's cursor reported
    inside a transaction whose commit could not be observed; the probe's id is
    what the DURABLE table says.  They cannot legitimately differ, and using
    the probe's is the admissible choice rather than the equivalent one.

    **``outcome.committed`` IS NOT SET BY A SUCCESSFUL SETTLE.**  It means
    *the commit's own return was observed*, and it did not happen.  The settle
    produces a different, weaker-but-admissible fact -- *the ledger contains
    this attempt's row* -- and conflating the two would destroy the
    distinction this arc exists to draw.

    **CONTAINMENT IS ``BaseException``.**  Unlike S2.1's PRE-commit mint, the
    module's R11-03 property governs here: nothing that happens while
    DIAGNOSING a failure may change which exception escapes.  The cost is that
    an interrupt delivered during the probe is swallowed in favour of the
    commit's own exception; both are failures, so no false success can be
    manufactured, and the identity of what escapes is the property this
    codebase pins.  **An interrupt delivered AFTER the proof is swallowed in
    favour of the PROVEN ENTRY, exactly as clause 1 swallows one delivered
    after the commit returned: in both, a TRUE fact is reported** (RD, ruled
    2026-09-08 on `A4X-R2-01`).

    **THE PROOF IS CAPTURED BEFORE IT IS RETURNED, AND THE ``except`` SCOPE IS
    UNCHANGED.**  ``proven`` is bound the statement after the ticker
    corroboration succeeds, so the containment arm can hand back a proof that
    already existed instead of converting it to the alarm -- which is what a
    fault delivered AT the ``return`` used to do, discarding a durability the
    fresh read had already established and making ``record_entry`` re-raise
    over a durable entry.  **NARROWING the ``except`` around the ``return``
    was REJECTED** (the reviewer's shape, and the cell's): it changes WHICH
    exception escapes on a post-proof fault -- the fault instead of the
    original -- and that identity is the R11-03 property this module pins.
    Capture-then-return keeps the proof AND the identity property, and is the
    weakest sufficient change.  A SECOND PROBE was rejected too: a re-read's
    own return is the same window one frame later, it opens a second
    connection on an already-failing money path, and it contradicts the
    shipped one-probe-per-attempt assertion.

    **WHAT THE CAPTURE NARROWS AND WHAT IT DOES NOT** (Codex `22A4-R3-01`,
    reproduced by execution).  The class is IRREDUCIBLE and this is where the
    residue now sits: a fault delivered AT the capture statement itself lands
    with the probe's corroborated row already in hand and `proven` still
    `None`, so the arm ALARMS over a durable entry.  What the capture buys is
    that every boundary AFTER it reports the entry; what it cannot buy is a
    boundary that does not exist.  **The residue is DECLARED as a member of
    the alarm family** -- see the declaration above `_entry_transaction` --
    rather than argued away, and the arm's no-proof wording says only what it
    can observe.
    """
    #: The corroborated proof, or ``None``.  Declared BEFORE the ``try`` so
    #: the containment arm can read it on every path into that arm.
    proven: tuple[int, str] | None = None
    try:
        if outcome.resolution not in ("not_needed", "rolled_back"):
            return None
        if outcome.cleanup_raised:
            return None
        if attempt.token is None or attempt.db_path is None:
            log_contained_note(
                log, post_commit_error,
                "22-A4: the commit's own return was lost and the "
                "settle-by-identity probe is UNAVAILABLE (token=%s, "
                "database path=%s). The original failure is re-raised, which "
                "is the pre-arc behaviour.",
                attempt.token is not None, attempt.db_path is not None)
            return None
        found = _durability_probe(
            attempt.db_path, attempt.token, post_commit_error)
        if found is None:
            return None
        settled_id, settled_ticker = found
        if settled_ticker != req.ticker:
            # A MISMATCH MAY RAISE THE ALARM; ONLY A MATCH MAY BE ASSERTED
            # FROM.  A row carrying our token under a different ticker is
            # wrong in a way no design anticipated.
            log_contained_note(
                log, post_commit_error,
                "22-A4: a durable row carries this attempt's identity token "
                "under ticker %s while the request named %s. NOTHING is "
                "asserted from it; the original failure is re-raised.",
                safe_text(settled_ticker), safe_text(req.ticker))
            return None
        proven = found
        return proven
    except BaseException as settle_error:  # noqa: BLE001 -- the CLASS
        if proven is not None:
            # THE PROOF EXISTS AND IS RETURNED.  `settled_id` is bound
            # whenever `proven` is -- the unpack is two statements above the
            # binding -- and nothing in this branch can raise: `log_contained_
            # note` contains its own sink, and `safe_text` never raises.
            log_contained_note(
                log, post_commit_error,
                "22-A4: the settle-by-attempt-identity read SUCCEEDED (durable "
                "row %s) and a fault arrived AFTER the proof (%s). The durable "
                "row STANDS and is reported; the fault is swallowed in favour "
                "of a TRUE success, exactly as a fault after the commit's own "
                "return is.",
                settled_id, safe_text(settle_error))
            return proven
        # **NO PROOF WAS CAPTURED -- WHICH IS NOT THE SAME AS "THE READ
        # FAILED", AND THE WORDING SAYS ONLY WHAT IT CAN OBSERVE** (Codex
        # `22A4-R3-01`, REPRODUCED: a fault delivered AT the capture statement
        # itself leaves `proven` unbound-to-a-value while the probe HAD
        # returned a corroborated row, and the predecessor's "the read FAILED"
        # was then emitted over a durable entry -- the same false sentence the
        # ruling required be removed, one line further along).  Two different
        # events reach this arm: the read or the gate genuinely produced
        # nothing, OR a fault arrived before the capture landed.  This branch
        # cannot tell them apart, so it must not claim to.
        log_contained_note(
            log, post_commit_error,
            "22-A4: the settle-by-attempt-identity produced NO CORROBORATED "
            "PROOF (%s) -- either the read/gate yielded none, or a fault "
            "arrived before the proof was captured. The original failure is "
            "re-raised UNCHANGED -- the caller is told about the entry, never "
            "about the probe.",
            safe_text(settle_error))
        return None


def record_entry(
    conn: sqlite3.Connection, req: EntryRequest, *,
    soft_warn: int, hard_cap: int, force: bool,
    cfg=None,
) -> EntryResult:
    """22-A adds ONE keyword-only parameter, ``cfg``, and that is the whole
    signature change in the arc.  Both production call sites already have it
    (``swing/cli.py``, ``swing/web/routes/trades.py``).

    ``cfg=None`` DECLINES the latch path with reason ``no_config`` and leaves
    every PRE-ARC COLUMN of the persisted row byte-identical to the pre-arc
    behaviour, so every pre-existing caller and test is unaffected.

    **22-A4 AMENDS THAT SENTENCE RATHER THAN LEAVING IT TO READ TRUE WHILE THE
    CODE MOVED UNDERNEATH IT** (gotcha #31).  The row now also carries a
    per-attempt ``attempt_id`` token, minted REGARDLESS of ``cfg``, which is
    not part of the pre-arc row and carries NO domain meaning: no consumer
    reads it, and its only purpose is to let a lost commit be resolved by
    identity rather than by a reusable rowid.
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
    from swing.trades.latched_origin import envelope_recognises_an_order

    # THE RECOGNITION QUESTION IS THE RESOLVER'S OWN, NOT A SECOND SPELLING OF
    # IT (self-sweep SS-1).
    #
    # This site asked `broker_order_id_from_envelope(...) is not None`, which
    # is the PYTHON reader alone -- so an envelope Python reads as ABSENT and
    # SQLite reads as a REAL LINKED order took NO reservation, never called the
    # resolver at all, and ran the ordinary current-candidate chain. The
    # canonicality guard 22A-R8-01 added for exactly that disagreement sat
    # behind a door this line never opened. MEASURED end to end on three
    # shapes (duplicate key whose LAST value is null / numeric / empty): the
    # persisted row was `pipeline_aplus` + TODAY's candidate.
    #
    # `envelope_recognises_an_order` is that question asked ONCE, in the
    # module that owns it. It stays a PURE STRING READ, so LOCK clause (d) --
    # a request with no usable order id costs ZERO additional database
    # queries -- is untouched, and so is its subject: an envelope naming no
    # order that both domains read alike is still unrecognised and still takes
    # the deferred `with conn:` exactly as before.

    # THE ORDER ID IS PARSED WHETHER OR NOT A CONFIG WAS SUPPLIED (Codex
    # 22A-R7-01).
    #
    # AND `cfg=None` IS NO LONGER "THE PRE-ARC PATH" WITHOUT QUALIFICATION
    # (Codex 22A-R9-07): it is the pre-arc path for a request whose envelope
    # resolves to NO LINK. A request whose order IS linked is RECOGNISED and
    # refused, and the row lands honest-unset. Stated here because the earlier
    # unqualified sentence was a security-relevant caller contract that the
    # 22A-R7-01 fix had made false while it still read true (#31).
    #
    # Gating the PARSE on `cfg` meant an order-bearing request
    # from a caller who omitted the config took no reservation, never
    # consulted the link table, and ran the ordinary current-candidate chain
    # -- a wrong ACCEPTANCE reachable by leaving one keyword off. The parse
    # is a pure string read and costs no query, so LOCK clause (d) -- "no
    # usable order id costs ZERO additional database queries" -- is untouched:
    # its subject is a request with NO ORDER ID, and that request still takes
    # the deferred `with conn:` exactly as before.
    _recognised_order_id = envelope_recognises_an_order(
        getattr(req, "schwab_source_value_json", None))
    # THE TRIGGER IS "THE REQUEST CARRIES A USABLE ORDER ID", NEVER "THE
    # RECOGNITION FOUND A LINK" (plan S2.2 rule 3, review 22A-R3-01).  A
    # request whose preliminary answer was NO LINK can acquire a matching
    # validity row before the INSERT and would otherwise take the ordinary
    # path on a stale negative.  A negative result is as perishable as a
    # positive one, and the reservation covers both (case 21b).
    _reserve = _recognised_order_id
    if _reserve and conn.in_transaction:
        raise CallerHeldEntryTransactionError(
            "record_entry owns BEGIN IMMEDIATE for an order-id-bearing "
            "request and REJECTS a caller-held transaction rather than "
            "auto-detecting one; an auto-detect guard re-introduces the race "
            "the explicit lock closed. Nothing was written."
        )

    # THE RESULT IS A STATEMENT ABOUT THE DURABLE STATE OF THE LEDGER
    # (CHARC's contract, ruled 2026-09-01, from Codex 22A-FIX-R9-03), AS
    # SPLIT BY CHARC + RD 2026-09-02 -- `docs/22-a-merge-request.md` S4.4.
    # **ALL THREE CLAUSES STAND, AND CLAUSE 2 IS CONDITIONAL** (22-A4).  This
    # sentence read *"CLAUSE 2 IS REVERTED to re-raise"* until this arc, and it
    # is amended rather than left to read true while the code moved underneath
    # it (gotcha #31): a commit whose own return was LOST now SETTLES BY
    # ATTEMPT IDENTITY on a fresh connection when every precondition of
    # `_settle_by_attempt_identity` is observed, and re-raises -- the ALARM,
    # which is the pre-arc behaviour -- when any one of them is not.  The
    # declaration above `_entry_transaction` carries both reproductions, how
    # each precondition is now supplied, and what the ALARM still costs.
    #
    # `outcome` is how the transaction wrapper tells this function the ONE
    # fact it cannot otherwise observe -- whether the COMMIT ITSELF RETURNED.
    # It is a mutable carrier rather than a return value because the commit
    # happens in the context manager's exit, AFTER the inner function has
    # already produced its result, so there is no return value left to carry
    # it.
    result: EntryResult | None = None
    outcome = _CommitOutcome()
    # 22-A4: the attempt begins HERE -- after the entire pre-existing gauntlet
    # (validation, the stop check, the duplicate check, the hard cap, the soft
    # warn, the recognition read and the caller-held-transaction refusal) and
    # BEFORE the guarded region.  Each of those refusals issues ZERO new
    # statements and raises exactly as before; the mint changes no branch and
    # no ordering, so LOCK clause (c) holds.  Not every pre-existing refusal is
    # upstream of it -- the PE-anchor guard and the latch resolver's own
    # refusals run INSIDE the transaction -- and under this shape the
    # difference costs one wasted uuid4.
    identity = _begin_attempt_identity(conn)
    # ===================== THE GUARDED REGION STARTS HERE ==================
    #
    # **CLAUSE 1: AFTER A SUCCESSFUL COMMIT, NOTHING MAY CONVERT THE RESULT TO
    # FAILURE.**  Every post-commit step -- event emission, identity
    # recording, cache invalidation, logging -- is BEST-EFFORT: it is caught,
    # logged at ERROR with the `trade_id` and the step that failed, and the
    # SUCCESS result returns carrying the warning.
    #
    # CHARC's reason, kept at the site because it is the whole argument:
    # *the operator sees what is TRUE -- the entry exists.  Reporting a
    # durable write as a failure is not conservative; it is a wrong answer in
    # the direction that causes a DOUBLE ENTRY, which is the expensive
    # direction.*
    #
    # **THE `try` OPENS BEFORE THE `with`, NOT AFTER IT** (Codex
    # 22A-FIX-R10-01, reproduced by execution on BOTH paths).  A guard that
    # began only after the `with` statement had fully exited did not cover the
    # context manager's OWN return/unwind: an exception delivered on
    # `_entry_transaction`'s generator-return event, AFTER the real commit,
    # escaped it on both paths and left a durable entry reported as a failure
    # -- the exact hazard clause 1 exists to close, one frame outside the
    # thing built to close it.  The `with` statement itself is therefore
    # INSIDE the region.
    #
    # THERE IS NO POST-COMMIT STEP TODAY, and the guard is here anyway: the
    # region is where the next one goes, and the contract is a property of
    # this function rather than of the steps that happen to exist.  A step
    # added outside it re-opens the exposure silently.
    #
    # 22-A4 -- THE AMBIENT CAPTURE, AND THE CAPTURE POINT IS PART OF THE
    # DESIGN.  On the DEFERRED path the rollback belongs to
    # `sqlite3.Connection.__exit__`, so its failure is readable only off the
    # exception that arrives, whose `__context__` `__exit__` sets (see
    # `_exit_rollback_failed`).  On the rollback-SUCCEEDED arm that
    # `__context__` is the THREAD's currently-handled exception, so a caller
    # running inside an `except` would otherwise be a false positive; the
    # ambient object is excluded by `is`-IDENTITY at the read.
    #
    # **IMMEDIATELY BEFORE THE `try`, NOT AT FUNCTION ENTRY.**  Any `except`
    # frame between the capture and the `with`'s exit must belong to
    # `record_entry` itself, and only a capture adjacent to the `with`
    # guarantees that.  `try:` is not a handler, so nothing between this line
    # and the context manager can change what the thread is handling, and the
    # name is unconditionally BOUND when the handler runs.
    #
    # **`sys.exc_info()[1]`, NOT `sys.exception()`** -- the latter is Python
    # 3.12+ and `pyproject.toml` declares `requires-python = ">=3.11"`.  The
    # two return the same object; only one of them is inside the floor.
    ambient = sys.exc_info()[1]
    try:
        with _entry_transaction(conn, immediate=_reserve, outcome=outcome):
            result = _record_entry_inner(
                conn, req,
                cfg=cfg,
                derived_origin=derived_origin,
                entry_iso=entry_iso,
                warning=warning,
                reserve=_reserve,
                attempt_id=identity.token,
            )
        # ---- everything from here to the return is POST-COMMIT ----
        return result
    except BaseException as post_commit_error:  # noqa: BLE001 -- the CLASS
        # **THE GATE IS THE COMMIT'S OWN RETURN, NEVER A READ OF THE LEDGER.**
        # `outcome.committed` is set on the statement after `commit()` returns
        # normally; it is this function's own call reporting what it did, not
        # the writer reading the table to decide what its call must have done
        # (which is the read the ORIGINAL clause 2 was reverted for -- see
        # the declaration below.  Clause 2 now RETURNS, on a FRESH connection
        # and a per-attempt token; what stays reverted is resolving a lost
        # commit from the WRITER'S OWN handle, which is a different read).
        #
        # Both conditions are stated because the gate must assert what is
        # TRUE rather than what their coupling implies: `result is None` says
        # the body never finished, `not outcome.committed` says the commit
        # never returned.  Either one means there is no entry to report, and
        # the honest answer is the original exception.
        #
        # **22-A4 SPLITS THE GATE INTO TWO BRANCHES, AND THEY NO LONGER DO
        # THE SAME THING.**  Task 3 split one `or` into two `if`s with the
        # same bare `raise`, which was behaviour-preserving; TASK 4 THEN
        # CHANGED THE SECOND BRANCH, and this comment is corrected rather
        # than left reading true (gotcha #31):
        #
        #   * `result is None` -- the body never finished.  UNCONDITIONAL
        #     re-raise, byte-for-byte the pre-arc behaviour, and the branch
        #     this arc must not touch.
        #   * `not outcome.committed` -- the body finished and the commit's
        #     own return was never observed.  This branch takes the deferred
        #     path's two observations and then CONSULTS CLAUSE 2's settle: it
        #     re-raises only when the settle refuses, and otherwise returns a
        #     degraded SUCCESS carrying the probe's trade id.
        #
        # The split was the precondition for that: without it there is no
        # `not outcome.committed` branch for the observations to sit under --
        # an observation placed after the combined guard is UNREACHABLE
        # whenever `committed` is False, and one placed before it would run on
        # the body-raise branch.
        if result is None:
            raise
        if not outcome.committed:
            # ---- THE DEFERRED PATH'S TWO OBSERVATIONS, both of them ----
            #
            # THEY LIVE HERE AND NOT IN `_entry_transaction` BECAUSE THIS IS
            # THE ONLY FRAME WHERE THE SCOPE IS OBSERVABLE WITHOUT WRITING A
            # STATEMENT INTO THE BYTE-LOCKED DEFERRED BRANCH: `result is not
            # None` (one line up) says the body completed, and
            # `not outcome.committed` says the commit's return was not
            # observed.  The pre-arc BODY-RAISE branch is excluded by code
            # that already ships, which is why the branch above needs no
            # `try`, no `except` and no added statement.
            #
            # `not _reserve` -- DEFERRED PATH ONLY.  The IMMEDIATE path took
            # both observations in `_entry_transaction`, from its OWN
            # rollback call, and layering an inference over a direct
            # observation is the one thing this arc exists not to do.
            #
            # **DETECTION FIRST, THEN THE READ.**  Nothing in this block
            # mutates the connection -- there is no retry rollback here, by
            # design -- but the ORDER states rule (i) rather than merely
            # satisfying it: the failure is DETECTED before anything else
            # touches the handle, and what remains is `in_transaction`, an
            # attribute read that issues no SQL.
            #
            # **NO ROLLBACK, NO LOG, NO STATEMENT.**  `__exit__` owns this
            # path's rollback and its failure is ALREADY what escaped, so a
            # second louder report from us would replace an exception the
            # caller's tests pin, for no new information.
            if not _reserve:
                if _exit_rollback_failed(post_commit_error, ambient):
                    outcome.cleanup_raised = True
                # `attempted=False`: THIS FRAME issued no rollback.
                outcome.resolution = _read_resolution(conn, attempted=False)
            # ---- CLAUSE 2: SETTLE BY ATTEMPT IDENTITY, OR ALARM ----
            #
            # THE OBSERVATIONS ARE TAKEN FIRST AND THE GATE IS CONSULTED
            # SECOND, and the order is a requirement rather than a
            # convenience: a gate consulted before the read would see
            # `resolution == "unattempted"`, refuse, and report a DURABLE
            # entry as a failure -- the `A4-R1-3` defect relocated rather
            # than fixed.  (k3a)'s Task-4 half asserts the lexical order.
            settled = _settle_by_attempt_identity(
                identity, outcome, req, post_commit_error)
            if settled is None:
                raise    # THE ALARM -- unchanged, today's behaviour
            settled_trade_id, _settled_ticker = settled
            # THE PROBE'S ID, NOT `lastrowid`: what the DURABLE table says,
            # not what a cursor reported inside a transaction whose commit we
            # could not observe.
            result = dataclasses.replace(result, trade_id=settled_trade_id)
        # Rendered ONCE and used in BOTH places (Codex A3R5-03): the
        # warning used `safe_text` while the `log.error` below still
        # received the RAW object, so a FORMATTING handler invoked its
        # `__str__` a second time -- which a hostile exception can use to
        # mutate itself or raise, obscuring what actually failed. The
        # arc's other diagnostic paths were corrected in the previous
        # round; this one was missed.
        post_commit_error_text = safe_text(post_commit_error)
        # **`safe_text`, NOT `{post_commit_error!r}`** (22-A3 Task 4, ruled
        # 2026-09-02: *"the envelope covers outcome-corrupting
        # exception-formatting on the post-commit path of `record_entry`,
        # wherever it occurs in the function."*).  A post-commit failure whose
        # `__repr__` RAISES made this line raise BEFORE the degraded
        # `EntryResult` existed at all -- so `record_entry` reported a failure
        # over a durable entry, which is clause 1's own subject, one line
        # above the guard that implements it.
        if not outcome.committed:
            # THE LOST-COMMIT TEXT.  It says a DIFFERENT thing from the
            # post-commit-STEP warning below and must not be confused with
            # it: the commit's own return was never observed, and durability
            # is a statement about the LEDGER read by attempt identity.
            warning_text = (
                f"the commit's own RETURN was LOST and the entry is DURABLE "
                f"(trade {result.trade_id}), confirmed by ATTEMPT IDENTITY "
                f"on a fresh connection ({post_commit_error_text}). The "
                f"entry exists -- do NOT retry.")
        else:
            warning_text = (
                f"the entry is DURABLE (trade {result.trade_id}) and a step "
                f"AFTER the commit failed ({post_commit_error_text}). The "
                f"entry exists -- do NOT retry.")
        degraded = dataclasses.replace(
            result,
            post_commit_warnings=result.post_commit_warnings + (
                warning_text,),
        )
        # **THE LOG CALL IS BEST-EFFORT IN FACT, NOT ONLY IN THE PROSE**
        # (Codex 22A-FIX-R10-04, reproduced: a logging handler whose `emit()`
        # raised propagated out over a committed row).  Clause 1 names logging
        # as a best-effort post-commit step, so a failing sink may not convert
        # a durable write into a failure.  The degraded result is BUILT FIRST
        # and the failure of the log is itself surfaced as a warning rather
        # than swallowed -- a silent `pass` here would trade one invisible
        # failure for another.
        try:
            log.error(
                "22-A: trade %s IS DURABLE and a POST-COMMIT step failed "
                "(%s). The entry exists; the failure is reported as a warning "
                "and NOT as a failed entry -- reporting a durable write as a "
                "failure is what causes a double entry.",
                result.trade_id, post_commit_error_text)
        except BaseException as log_error:  # noqa: BLE001 -- the CLASS
            degraded = dataclasses.replace(
                degraded,
                post_commit_warnings=degraded.post_commit_warnings + (
                    # `safe_text` for the same ruled reason as the warning
                    # above: if the SINK's own exception has a hostile
                    # `__repr__`, this formatting raised INSIDE the `except`
                    # clause, over a durable row -- a raising logging handler
                    # still changing the function's result at the one site
                    # R10-04 had declared safe.
                    f"the ERROR log for the warning above could not be "
                    f"emitted cleanly -- a logging handler RAISED "
                    f"({safe_text(log_error)}). Some sinks may have received "
                    f"the record and some may not; the ledger is "
                    f"unaffected.",),
            )
        return degraded


class CallerHeldEntryTransactionError(RuntimeError):
    """``record_entry`` was called with an open transaction on the latched
    path.  Single-transaction services own ``BEGIN IMMEDIATE`` / COMMIT /
    ROLLBACK and REJECT a caller-held transaction (CLAUDE.md)."""


@dataclass
class _CommitOutcome:
    """The ONE thing the transaction wrapper knows and its caller cannot ask
    for afterwards: **did the COMMIT ITSELF RETURN?**

    ``record_entry``'s post-commit guard has to tell "the write never landed"
    from "the write landed and an exception arrived afterwards", and once the
    context manager has exited there is nothing left to interrogate.  The
    connection cannot answer it either: ``in_transaction`` reads False for a
    COMMITTED transaction and for a ROLLED-BACK one alike.

    **It is an OBSERVATION, never an inference.**  It is set on the statement
    after the commit call returns normally, on each path, and nothing else
    sets it.  That is exactly why it is admissible where the reverted
    resolve-by-read was not: it is the writer reporting what its OWN CALL
    did, not the writer reading the ledger to decide what its own call must
    have done.

    **22-A4 ADDS TWO MORE FIELDS, FOR THREE IN TOTAL -- ACROSS FOUR
    PATH-SPECIFIC PROVENANCE CASES, of which THREE are direct observations in
    the same sense ``committed`` is and ONE is a derivation** (``committed``;
    ``resolution`` on either path; ``cleanup_raised`` on the IMMEDIATE path;
    and ``cleanup_raised`` on the DEFERRED path, which is the derivation --
    see below).  A direct observation is of:
    of a call the WRITING frame itself made, of the connection's own state, or
    of an exception that frame itself caught.  "The writing frame" is
    ``_entry_transaction`` on the IMMEDIATE path and ``record_entry`` on the
    DEFERRED one, and the distinction is load-bearing rather than incidental:
    each field is written where the fact is DIRECTLY available, so no arm of
    this design has to reason about what another frame must have done.

    **THE FOURTH CASE IS THE DERIVATION, AND THIS SAYS SO** (Codex R1 Minor
    9; the count made consistent at R2 Minor 4 -- THREE FIELDS, FOUR CASES).
    An earlier wording said *"never an inference"* of all of them, which is
    false of ``cleanup_raised`` ON THE DEFERRED PATH: ``__exit__`` owns that
    rollback, NO Python frame observes the call, and the fact is DERIVED from
    the escaping exception's ``__context__`` by ``_exit_rollback_failed``.  The
    derivation is sound on the whole supported range -- CPython restores the
    commit's exception when its internal rollback succeeds and chains it
    beneath the rollback's when it fails, on the declared 3.11 floor and on
    3.14.2 alike (SOURCE, pinned by upstream digest at that helper) -- and it
    is contained toward the ALARM, so an unreadable context refuses the settle
    rather than admitting one.  Calling it an observation flattered it; the
    other three ARE direct observations, and the difference is exactly the
    kind a reader is entitled to see stated.

    ``resolution`` and ``cleanup_raised`` ARE TWO DIFFERENT FACTS and a
    reader must not collapse them.  ``resolution`` describes the
    TRANSACTION; ``cleanup_raised`` describes the CALL.  The tree already
    contains the counterexample to conflating them --
    ``tests/trades/test_22a_task9_entry_wiring.py``'s
    ``_RollbackAfterEffect`` performs the REAL rollback and THEN raises, so
    the transaction is RESOLVED, the row is GONE, and an implementation that
    inferred "unresolved" from the raise would be false about it.

    **THERE IS DELIBERATELY NO ``body_completed`` FIELD.**  ``record_entry``
    already observes that fact and has since 22-A3: ``result`` is
    pre-initialised to ``None`` before the guarded region and assigned inside
    it from ``_record_entry_inner``'s return, so ``result is not None`` is
    non-None if and only if the body ran to completion.  A second field
    mirroring it would be the mirror-drift class (gotcha #11) bought for
    nothing -- and on the deferred path the only place to set it would be
    INSIDE ``with conn:``, the one suite this arc promises is byte-identical.

    **ALL THREE OBSERVATIONS ARE NOW CONSUMED, NOT MERELY RECORDED.**
    ``committed`` gates CLAUSE 1, above ``_entry_transaction``: a commit that
    RETURNED may never be reported as a failure.  ``resolution`` and
    ``cleanup_raised`` gate CLAUSE 2's settle, ``_settle_by_attempt_identity``,
    below ``_entry_transaction`` -- a commit whose own return was LOST is
    resolved by a durable-visibility read only when these two say the
    connection's rollback (if any) took effect cleanly.  See the declaration
    above ``_entry_transaction`` for how.
    """

    committed: bool = False
    #: The PHYSICAL transaction state, RE-READ from ``conn.in_transaction``
    #: after any rollback attempt and NEVER inferred from the fact that a call
    #: raised: ``"unattempted"`` / ``"not_needed"`` / ``"rolled_back"`` /
    #: ``"still_open"``.  Written by ``_entry_transaction``'s own failure
    #: handler on the immediate path and by ``record_entry``'s post-commit
    #: handler on the deferred one, through the SAME non-mutating
    #: ``_read_resolution`` so the two paths cannot drift on the one thing
    #: they share.
    resolution: str = "unattempted"
    #: A rollback call RAISED -- a fact about the CALL, not about the
    #: transaction.  On the IMMEDIATE path it is a direct observation of the
    #: wrapper's OWN ``rollback()``.  On the DEFERRED path
    #: ``sqlite3.Connection.__exit__`` owns the rollback, so no frame can
    #: observe the call; the failure is read off the exception that arrives,
    #: by ``_exit_rollback_failed``, AND FROM NOWHERE ELSE on that path --
    #: which is what makes the flag's provenance a property of the code
    #: rather than of a fixture.
    cleanup_raised: bool = False


# ===========================================================================
# **THE DECLARED RESIDUAL, AS RULED 2026-09-02 AND AS SUPPLIED HERE IN
# 22-A4: A COMMIT WHOSE OWN RETURN IS LOST RE-RAISES OVER A ROW THAT MAY BE
# DURABLE -- UNLESS THE ATTEMPT CAN NOW PROVE ITS OWN DURABILITY.**  (CHARC +
# RD, ruled 2026-09-02 -- `docs/22-a-merge-request.md` S4.4.)
#
# WHAT THE RESIDUAL WAS.  CLAUSE 2 -- *"if `commit()` itself raises, RESOLVE
# BY READ"* -- was first implemented as `_entry_is_durable` +
# `_settle_lost_commit`, and was REVERTED to unconditional re-raise: the read
# those helpers performed was never implementable as ruled, and BOTH reasons
# were reproduced by execution against the shipped helpers, in the SAME leg
# that shipped them:
#
#   * **VISIBILITY** -- the confirming read must observe DURABLE state.  A
#     read taken on the writer's OWN connection inside an unresolved
#     transaction observes the writer's own uncommitted view: THE WRITER
#     QUOTING ITSELF.  Reproduced (Codex 22A-FIX-R10-02): with a rollback
#     that raised BEFORE taking effect, `_settle_lost_commit` returned True
#     with `conn.in_transaction` still True -- a FALSE SUCCESS carrying a
#     "DURABLE" warning over a merely-pending row, which is the one direction
#     the contract says must never be produced.  The helper's own docstring
#     said the resolution "rolls back FIRST and only then reads"; it handled
#     the rollback SUCCEEDING and not the rollback FAILING.  A failed
#     rollback VOIDS the read -- it does not license reading anyway.
#   * **IDENTITY** -- the read must identify OUR attempt.  `SELECT 1 FROM
#     trades WHERE id = ?` establishes only that *a* row with that id exists,
#     and A ROLLED-BACK ROWID IS REUSABLE (`sqlite_sequence` rolls back with
#     the insert, so even `AUTOINCREMENT` does not pin it).  Reproduced
#     (Codex 22A-FIX-R10-03): trade 1 was rolled back, a second connection
#     inserted ticker `OTHER` and was issued id 1, and `_settle_lost_commit`
#     confirmed that row as ours.  **THIS PRECONDITION DID NOT EXIST IN THE
#     SCHEMA AT RULING TIME.**
#
# SO THE HONEST ANSWER WAS THE ALARM, ALWAYS.  Canon (RD): **ALARM-NEVER-
# ASSERT AT THE TRANSACTION BOUNDARY** -- the function may RAISE the
# indeterminate, and may never ASSERT durability from evidence that cannot
# identify the attempt.  That canon is UNCHANGED by what follows; only the
# EVIDENCE available to it has changed.
#
# HOW EACH PRECONDITION IS NOW SUPPLIED (22-A4, Tasks 3-4).  The follow-on
# ruled and deliberately NOT built at the time of the ruling above -- a
# CO-DURABLE, UNIQUE-PER-ATTEMPT identity resolved on a DURABLE-VISIBILITY
# read -- is built here:
#
#   * **CO-DURABLE.**  `_begin_attempt_identity` mints a fresh `uuid4` token
#     BEFORE the guarded region opens, and `_record_entry_inner` writes it as
#     a COLUMN OF THE SAME `INSERT` that writes the row
#     (`insert_trade_with_event(..., attempt_id=attempt_id)`) -- never a
#     post-commit stamp.  Anything else is gotcha #30's shape one level down:
#     a value standing in for the fact it is supposed to co-durably attest.
#   * **UNIQUE-PER-ATTEMPT.**  Migration `0038`'s `ux_trades_attempt_id` is a
#     partial UNIQUE index over non-NULL `attempt_id`, and every attempt
#     mints its OWN token -- so a rolled-back-and-retried attempt collides
#     with nothing: the rowid-reuse defect (R10-03) does not apply to a
#     value the engine never hands back.
#   * **DURABLE-VISIBILITY READ.**  `_durability_probe` opens a FRESH
#     connection via `open_connection` on a `file:...?mode=rw` URI -- never
#     the writer's own handle -- which is the half of R10-02 closed by
#     CONSTRUCTION rather than by discipline: there is no code path by which
#     this read can observe the writer's own uncommitted view, because it is
#     not the writer's connection.
#
# THE GATE ITSELF, `_settle_by_attempt_identity`, IS CLAUSE 2, RETURNING.  It
# returns the probe's `(id, ticker)` -- an ADMISSIBLE, weaker-but-durable
# fact, distinct from `outcome.committed` -- only when ALL of: (1) the body
# ran to completion (the CALLER's own pre-arc guard, not re-checked here);
# (2) `resolution in {"not_needed", "rolled_back"}` AND `cleanup_raised` is
# False, RD's rule (i) taken LITERALLY -- a rollback that raised VOIDS the
# read even where the state re-read shows it took effect; (3) the attempt
# minted BOTH a token and a database path; (4) the probe finds a row AND its
# ticker matches the request's.  Any one unmet is the ALARM: `None`, and the
# caller re-raises -- honest, in the way the reverted read was not, because
# it never asserts a row exists on evidence that cannot identify the
# attempt.
#
# CONDITION 3's TOKEN HALF IS A PRECONDITION, NOT A REACHABLE BRANCH --
# VERIFIED AT THE CODE.  `_begin_attempt_identity`'s mint `except` arm
# returns a bare `_AttemptIdentity()` -- token `None` **and** `db_path`
# `None` -- BEFORE `_resolve_main_db_path` is ever reached; only a
# SUCCESSFUL mint proceeds to resolve the path (which can itself fail,
# leaving `db_path` alone `None`).  So the state "token is `None` WITH a
# resolved `db_path`" is not producible by this code.  Condition 3 checks it
# anyway, for the SAME reason condition 2 rejects `"unattempted"` (S2.4): a
# gate whose safety rests on an exhaustiveness argument about a DIFFERENT
# function's internal statement ordering is not a gate.
#
# WHAT THE RESIDUAL COSTS NOW, stated rather than implied.  The ALARM still
# fires -- narrower than before, but not empty -- whenever the preconditions
# above are NOT observed: a rollback that raised on the deferred path
# (`cleanup_raised`), an in-memory database (`db_path` unavailable), a mint
# failure (`token` unavailable), a probe that itself fails, a token found
# under the WRONG ticker (an anomaly no design anticipated, and the honest
# response is still the alarm rather than an assertion), and -- NAMED HERE AS
# TWO MORE MEMBERS OF THE SAME FAMILY (ruled 2026-09-08; their WIDTH corrected
# 2026-09-08 after Codex `22A4-R3-01`/`-02` MEASURED both, and the measurement
# is the reason these two paragraphs are stated in boundaries rather than in
# statement counts) -- an asynchronous `BaseException` delivered at either of
# these two places:
#
#   (A) **THE SETTLE'S CAPTURE BOUNDARY.**  `_settle_by_attempt_identity`
#       captures the corroborated proof and then returns it, so every boundary
#       AFTER the capture reports the DURABLE ENTRY -- clause 1's direction,
#       one rung down.  What the capture cannot buy is a boundary that does
#       not exist: a fault landing AT the capture statement arrives with the
#       probe's row already in hand and no proof yet bound, and the helper
#       ALARMS.  REPRODUCED: a `sys.settrace` fault at that statement re-raised
#       the original commit error with one durable row on disk.
#
#   (B) **`record_entry`'s WHOLE POST-SETTLE TAIL, from the settle's return
#       THROUGH `return degraded`** -- the unpack, the `dataclasses.replace`,
#       `post_commit_error_text = safe_text(...)`, the `warning_text` branch,
#       the degraded result's construction, and the return itself.  **It is
#       NOT two statements**: an exception raised inside an `except` suite is
#       not caught by the `try` whose handler is running, and the only nested
#       handler in that tail protects the `log.error` call alone.  REPRODUCED
#       at `post_commit_error_text = ...` and again at `return degraded`:
#       both escaped over a durable row, carrying the original commit error as
#       `__context__` -- an honest chain, and this family's cost rather than a
#       new one.
#
# NEITHER CAN BE MADE ZERO-WIDTH, which is why both are declared rather than
# fixed.  For (A) a weakest-sufficient change existed and was made -- it moved
# the boundary, it did not remove it.  For (B) nothing cheaper than the
# declaration exists.
#
# EVERY MEMBER ABOVE CARRIES THE SAME COST AND THE SAME BELT.  On the ALARM
# the row can still be durable while the caller is told the entry failed, so
# the caller may RETRY -- and the retry hits `ux_trades_one_open_per_ticker`
# (UNIQUE on ticker WHERE state IN entered/managing/partial_exited) and
# REFUSES, naming the existing position.  A confusing error, not a double
# position.  **THE BELT DOES NOT COVER A TICKER CLOSED BETWEEN THE TWO
# ATTEMPTS**, and that remains the uncovered direction of this declaration,
# unchanged by this arc.
#
# THE COMPOSITION, STATED ONCE FOR THE WHOLE FAMILY rather than once per
# member -- because a per-member statement is what lets a new member look
# like a new direction:  the ONLY path from ANY alarm-family member to a
# SECOND POSITION is  alarm  x  operator retry  x  the position closed
# between the two attempts.  And the third factor is not free-standing: an
# EXIT recorded against a row the operator was told does not exist requires
# him to have SEEN that row.
#
# THE TWO NEW MEMBERS' BOUND, in its weakest sufficient form: each is bounded
# ABOVE by the rate of asynchronous faults landing in ITS OWN window on an
# already-failing path -- ONE STATEMENT for (A), and for (B) the post-settle
# tail through `return degraded`.  **NO INDEPENDENCE IS ASSUMED AND NO
# STRICTNESS IS CLAIMED** -- an upper bound, never an estimate, and the
# factors above are not asserted to be independent of each other.  The bound
# is stated by NAMING ITS ENDPOINTS rather than by counting statements,
# because the statement count was the half of this declaration that was WRONG:
# it read "two" while the exposure ran to the function's return, and a number
# in a bound is exactly the kind of claim that reads as measured when it was
# assumed.
#
# WHAT IS *NOT* REVERTED: clauses 1 and 3.  The post-commit region in
# `record_entry` still guarantees that a commit which RETURNED cannot be
# turned into a reported failure, on BOTH paths.  That guarantee rests on the
# commit's own return (`_CommitOutcome.committed`), which needs neither
# visibility nor identity.
# ===========================================================================


@contextlib.contextmanager
def _entry_transaction(conn: sqlite3.Connection, *, immediate: bool,
                       outcome: _CommitOutcome):
    """The ONE transaction the entry row is written in.

    ``immediate=False`` is the pre-arc path, byte-for-byte: Python's sqlite3
    implicit DEFERRED transaction via ``with conn:``.

    ``immediate=True`` is the latched path.  ``with conn:`` acquires NO write
    reservation until its first write, so a resolution performed "inside" it
    still reads without reserving and another connection can commit between
    that read and the INSERT.  The explicit ``BEGIN IMMEDIATE`` takes the
    reservation FIRST, following Demand C's shape verbatim including its
    caller-held-transaction refusal.

    ``outcome.committed`` is set on the statement AFTER the commit returns
    normally, on BOTH paths (clause 3).  That single fact is everything
    ``record_entry``'s post-commit guard needs, and it costs neither of the
    two preconditions the reverted clause-2 read could not meet -- it is an
    observation of THIS function's own call, not a reading of the ledger.

    **ON THE IMMEDIATE PATH, THIS FUNCTION'S OWN FAILURE HANDLER ALSO WRITES
    ``outcome.resolution`` AND ``outcome.cleanup_raised`` (22-A4).**  Both are
    set from THIS frame's own ``rollback()`` call -- an observation, not an
    inference about another frame -- through the shared, non-mutating
    ``_read_resolution``.  They are what makes clause 2's settle,
    ``_settle_by_attempt_identity``, admissible on this path exactly as
    ``committed`` makes clause 1 admissible: each is this function reporting
    what it itself did, never a reading of the ledger to guess it.  The
    deferred path (``immediate=False``) writes the SAME two fields, but from
    ``record_entry`` itself, one frame OUT -- see the declaration above
    ``_entry_transaction`` for why the frame differs and the fact does not.
    """
    if not immediate:
        # **CLAUSE 3: THE CONTRACT BINDS BOTH PATHS** (CHARC).  `with conn:`
        # COMMITS ON CONTEXT EXIT and therefore has the IDENTICAL post-commit
        # exposure -- an exception delivered as that commit returns leaves a
        # durable entry and a reported failure.  Binding only the latched path
        # would make the PRE-ARC path the one that double-enters, which is the
        # opposite of a conservative change.
        with conn:
            yield
        # `sqlite3.Connection.__exit__` COMMITTED and returned; a failure of
        # that commit propagates from the `with` above and never reaches
        # here, so this line is reached only after a commit that returned.
        outcome.committed = True
        return
    # THE ACQUISITION IS INSIDE THE PROTECTED REGION (reviewer B, post-fix
    # tree; ARC-INTRODUCED by `ed897bc5`, so fixed here rather than banked).
    # `BEGIN IMMEDIATE` sat OUTSIDE this `try`, so an interrupt landing
    # between the statement TAKING THE WRITE RESERVATION and the `try` being
    # entered skipped the handler entirely -- and B reproduced exactly that
    # with a proxy executing the real `BEGIN` and then raising:
    # `conn.in_transaction` stayed TRUE.  On the MONEY-BEARING entry path
    # that is a reservation held on a connection the caller goes on using.
    #
    # This is the shape `cohort_provenance_correction.py` already carries at
    # both of its transaction sites; the entry path is the one that writes a
    # TRADE, and it was the one left out.
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield
        # THE COMMIT IS INSIDE THE HANDLER'S REACH (Codex 22A-R4-03).  It sat
        # in an `else:` clause, OUTSIDE `except BaseException:` -- so a commit
        # that raises (SQLITE_BUSY, disk-full, I/O) left the transaction AND
        # its write reservation open on a connection the caller goes on
        # reusing.  A failed COMMIT is exactly the moment a rollback matters
        # most, and it was the one path that did not get one.
        #
        # A COMMIT THAT RAISES PROPAGATES FROM HERE, over a row that may well
        # be durable.  **THIS SITE does NOT try to settle it** -- neither the
        # exception nor a same-connection read is evidence about what the
        # commit did -- and that is unchanged by 22-A4.  What IS new is that
        # `record_entry`, one frame OUT, may now settle it by ATTEMPT IDENTITY
        # on a FRESH connection: a different read, on a different handle, with
        # a token this frame wrote inside the same INSERT.  The declaration
        # above `_entry_transaction` carries the whole argument.
        conn.commit()
        # **AND THE COMMIT'S OWN RETURN IS RECORDED HERE** (Codex
        # 22A-FIX-R10-01).  An earlier version deliberately carried no
        # `committed` flag, on the reasoning that control leaving this `try`
        # normally made any such flag unreachable.  That reasoning was about
        # THIS function's outer handler and it is still true of it -- but
        # `record_entry`'s post-commit guard lives one frame OUT, and the
        # window between this commit and that guard is reachable: an
        # exception on the generator's own return/unwind was reproduced on
        # both paths, escaping with a durable entry and a reported failure.
        # The flag is what lets the caller tell "never landed" from "landed,
        # then an exception arrived".
        outcome.committed = True
    except BaseException as write_error:
        # AND THE ROLLBACK'S OWN FAILURE IS NOT SUPPRESSED (reviewer B).
        # This was `contextlib.suppress(sqlite3.Error)`: B reproduced an inner
        # write plus a `ValueError` with `rollback()` raising, and the
        # reported exception carried NO cleanup cause, `in_transaction` stayed
        # true, and the PARTIAL ROW stayed visible for a later accidental
        # commit.  `AL-15`'s standard -- a cleanup failure is the MORE
        # DANGEROUS of two simultaneous conditions and must surface loudly --
        # was applied three times in the correction module and not here.
        #
        # THE ROUTE'S `finally: conn.close()` IS NOT A REASON TO LEAVE IT
        # (B's reachability line): it contains the open transaction for the
        # web surface, and `record_entry` TAKES a connection rather than
        # owning one, so every reusable service caller stays exposed.
        #
        # `conn.in_transaction` rather than a remembered flag: on the
        # interrupted-acquisition path only the connection knows whether the
        # transaction opened.
        if conn.in_transaction:
            try:
                conn.rollback()
            except BaseException as cleanup_error:  # noqa: BLE001 -- the CLASS
                # 22-A4 -- THE TWO OBSERVATIONS, AND THEY ARE TWO FACTS.
                # `cleanup_raised` is about THE CALL: this frame issued the
                # rollback and watched it raise, which is a direct
                # observation and not an inference about another frame.
                outcome.cleanup_raised = True
                # AND THE STATE IS RE-READ, NEVER INFERRED FROM THE RAISE --
                # the same re-derivation the two existing messages below
                # already do, for the same reason.  `_RollbackAfterEffect`
                # (already in this tree) performs the REAL rollback and THEN
                # raises: the transaction is RESOLVED and the row is GONE, so
                # a field that read "unresolved" here would be false.
                outcome.resolution = _read_resolution(conn, attempted=True)
                # THE MESSAGE IS RE-DERIVED FROM THE CONNECTION, NOT ASSUMED
                # FROM THE FACT THAT ROLLBACK RAISED (Codex 22A-FIX-R9-05).
                # An AFTER-EFFECT exception -- SQLite performing the rollback
                # and the interrupt landing as the call returns -- leaves the
                # transaction CLOSED and the partial row GONE, and the first
                # version of this handler still announced "STILL OPEN with a
                # partial row in it".  A cleanup warning that is WRONG about
                # the state teaches an operator to distrust the right ones.
                #
                # R11-03 CONTAINMENT (22-A3 Task 2), BOTH BRANCHES: the sink
                # is caller-installed infrastructure, and a raising handler
                # here used to REPLACE `cleanup_error` with its own exception
                # and drop the `from write_error` chaining with it.  See the
                # idiom at the head of this module.
                if conn.in_transaction:
                    log_contained_note(
                        log, cleanup_error,
                        "22-A: the entry write failed (%s) AND could not be "
                        "rolled back (%s). The WRITE transaction is STILL "
                        "OPEN with a partial row in it, its reservation still "
                        "held, and this connection MUST BE DISCARDED rather "
                        "than reused -- a later commit on it would make the "
                        "partial row durable.", write_error, cleanup_error)
                else:
                    log_contained_note(
                        log, cleanup_error,
                        "22-A: the entry write failed (%s) and the rollback "
                        "TOOK EFFECT but then raised (%s). The transaction is "
                        "CLOSED and nothing partial is visible; the failure "
                        "is reported because a connection whose rollback "
                        "raises is of unknown health and should not be "
                        "reused silently.", write_error, cleanup_error)
                # **AND THE CHAINED RE-RAISE IS THE IMMEDIATE PATH'S OWN AND
                # STAYS HERE.**  A shared helper that CONTAINED this cleanup
                # failure could not preserve it, which is exactly why the
                # shared thing is the non-mutating READ and not the rollback.
                raise cleanup_error from write_error
            # **RE-READ AFTER THE RETURNING ARM TOO** -- a rollback that
            # RETURNS is not the same fact as a rollback that TOOK EFFECT.
            # Assigning "rolled_back" unconditionally here would honour the
            # field's own contract (*re-read after ANY rollback attempt*) on
            # the raising arm and INFER it on the returning one, and a
            # rollback that returned without taking effect would then be
            # labelled `rolled_back` and ADMIT the settle.
            outcome.resolution = _read_resolution(conn, attempted=True)
        else:
            # NO ROLLBACK WAS NEEDED: the transaction was already resolved (or
            # never opened) when the failure arrived.  `attempted=False` is
            # what distinguishes that from a rollback this frame issued.
            outcome.resolution = _read_resolution(conn, attempted=False)
        raise


def _record_entry_inner(
    conn: sqlite3.Connection, req: EntryRequest, *,
    cfg,
    derived_origin: str,
    entry_iso: str,
    warning: str | None,
    reserve: bool,
    attempt_id: str | None = None,
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

    if reserve:
        # THE ORIGIN IS RE-DERIVED INSIDE THE RESERVATION (Codex 22A-R4-01).
        # The preliminary value at the call site above is computed BEFORE
        # `BEGIN IMMEDIATE`, so a pipeline run can commit between the two --
        # and that value fed BOTH the persisted ordinary origin AND the PE-
        # anchor guard below, whose comment claimed it read "the world the
        # write lands in".  It did not.  A comment asserting an invariant the
        # code does not hold is worse than no comment, because it reads true
        # (gotcha #31, inside a fix written to avoid it).
        #
        # THE PRELIMINARY VALUE IS STILL LOAD-BEARING and is NOT removed: the
        # validator runs on it, before the reservation, and moving that read
        # would move LOCK clause (c)'s ordering.  The validator requires
        # `trade_origin` for PRESENCE and never keys a rule on its VALUE
        # (pinned by `test_the_validator_never_keys_a_rule_on_the_trade_origin_VALUE`),
        # so the two reads can differ without changing any pre-existing branch.
        #
        # ONLY the reserved path re-derives.  The unreserved path is the
        # pre-arc path byte-for-byte and takes no reservation to be inside of.
        derived_origin = derive_trade_origin(conn, req.ticker, req.entry_path)

    # THE AUTHORITATIVE RESOLUTION, inside the reservation.  The preliminary
    # answer computed outside it is DISCARDED -- it exists only to decide
    # whether to reserve.
    # THE UNRESERVED BRANCH ASKS THE SAME QUESTION, IN THE SAME WORDS (RD's
    # 22A-R3-13 ruling). An absent envelope names no order, so it takes NO
    # reservation -- LOCK clause (d) -- and therefore never reaches the
    # resolver at all. The inconsistency check is a PURE, query-free predicate
    # for exactly that reason, and it is IMPORTED rather than re-spelled here:
    # two callers answering one question two ways is the class this arc has
    # paid for repeatedly.
    from swing.trades.latched_origin import (
        origin_and_envelope_are_inconsistent,
    )

    _envelope = getattr(req, "schwab_source_value_json", None)
    if reserve:
        latched = resolve_latched_provenance(conn, cfg, req)
    elif origin_and_envelope_are_inconsistent(
            getattr(req, "fill_origin", "operator_typed"), _envelope):
        log.warning(
            "22-A: fill for %s claims origin %r, which carries a Schwab "
            "envelope BY CONSTRUCTION, and its envelope is ABSENT (%r); no "
            "production writer produces that pair, so the envelope was "
            "stripped, tampered with or corrupted. The entry records with "
            "honest-unset cohort keys rather than with the latest run's "
            "candidate. WARRANTS INVESTIGATION",
            req.ticker, getattr(req, "fill_origin", None), _envelope)
        latched = LatchedProvenance(
            admitted=False, recognised_but_underivable=True,
            decline_reason="origin_envelope_inconsistent")
    else:
        latched = LatchedProvenance(
            admitted=False, recognised_but_underivable=False,
            decline_reason="no_config" if cfg is None else "no_order_id")

    # THE PE-ANCHOR GUARD, RELOCATED FROM THE ROUTE AND NOT MERELY DEFERRED
    # (review 22A-R9-03).  The route rejects a `pattern_evaluation_id` anchor
    # whose server-derived origin is `manual_off_pipeline`; for order-id-
    # bearing requests the route now defers to here, so WITHOUT this block the
    # deferral would DELETE a live production rejection and the row would be
    # written.  Case 37c is the stable no-link outcome that fails a deferral-
    # without-relocation implementation; every other case in the plan passes
    # one.
    #
    # INSIDE THE TRANSACTION IS THE WHOLE POINT, AND IT IS ONLY TRUE BECAUSE
    # OF THE RE-DERIVATION ABOVE (Codex 22A-R4-01): the guard's input is
    # `derive_trade_origin`, which reads the latest evaluation run -- the same
    # world the race can move.  Relocating the guard inside the transaction
    # while it judged the value computed OUTSIDE bought nothing; the comment
    # read true and the code did not hold it.  What makes the claim honest is
    # that `derived_origin` is re-read under the reservation, so the value the
    # guard judges is the value the row is written with.
    #
    # AND IT FIRES ON THE ORDINARY PATH ONLY (RD, ruled 2026-08-25).  The
    # condition was `not latched.admitted`, and `recognised_but_underivable`
    # IS a not-admitted state -- so an entry whose mandate the ladder
    # RECOGNISED and REFUSED was blocked, and no row was written.  That is the
    # COHORT-GUARD REFUSES: ENTRY -- and it is the ONE declared exception,
    # ruled by RD: this is a PRE-EXISTING production rejection RELOCATED
    # from the route (22A-R9-03), not a cohort-provenance guard, and it
    # fires on the ORDINARY path only.  Pinned at
    # `test_THE_DECLARED_EXCEPTION_the_pe_anchor_guard_still_bites_on_the_ordinary_path`.
    #
    # `0036:26-38` inversion: **cohort bookkeeping never blocks a
    # money-bearing entry.**  A refusal here is about the LABEL, never about
    # the ENTRY, so `recognised_but_underivable` is not-admitted AND must pass
    # through to the honest-unset row.  One clause too wide, the same class
    # this arc has already paid for twice.
    #
    # CASE 37c IS UNAFFECTED and is what proves the guard still bites: an
    # UNMATCHED order id leaves BOTH flags false, so the ordinary path runs
    # and the guard refuses exactly as the route does today.
    if (
        reserve
        and not latched.admitted
        and not latched.recognised_but_underivable
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
            # 22-A4: CO-DURABLE by construction -- the token is a column of
            # THIS INSERT, in this transaction, not a post-commit stamp.
            attempt_id=attempt_id,
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
        #
        # **THE MATCH IS NARROWED TO THE TICKER INDEX, IN THE SAME TASK THAT
        # ADDS A SECOND UNIQUE INDEX TO THIS TABLE** (22-A4 S2.5).  The
        # predecessor tested `"UNIQUE" in str(exc) and "trades" in str(exc)`,
        # which migration 0038's `ux_trades_attempt_id` also satisfies -- so a
        # duplicate attempt-identity token would have been re-labelled
        # "Already an open position in <ticker> (race-detected)" over a ticker
        # with NO open position: loud, and mislabelled as exactly the position
        # race the residual's honesty argument depends on it not being.
        # MEASURED, both messages: `UNIQUE constraint failed: trades.ticker`
        # and `UNIQUE constraint failed: trades.attempt_id`.
        if "UNIQUE constraint failed: trades.ticker" in str(exc):
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
