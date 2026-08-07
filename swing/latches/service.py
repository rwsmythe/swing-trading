"""The PURE latch derivation (Phase 21 Arc A).

No DB access, no network, no transaction management -- the Phase-12 classifier
convention. Every input arrives pre-fetched; `swing/latches/reader.py` owns the
I/O.

The two anchors (plan G.3, RD-CONFIRMED):

* ``horizon_session``    -- the FORWARD anchor (``action_session_for_run``).
  Answers "is the mandate live for the session I am about to trade", so it is
  what the HORIZON is measured against.
* ``derivation_session`` -- the BACKWARD anchor (``last_completed_session``).
  The newest session whose CLOSE can be judged, so it bounds the INVALIDATION
  bar walk. A bar newer than this is a look-ahead (the nightly warm legitimately
  writes one at 17:30 for the NEXT session).

They are not independent: production always passes
``derivation_session = session_offset(horizon_session, -1)``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import date

from swing.evaluation.dates import (
    is_trading_session,
    session_offset,
    sessions_behind,
)
from swing.latches.classification import admissible_decisions, governing_decision
from swing.latches.constants import (
    ARCHIVE_STATUS_OK,
    DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR,
    DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT,
    DEFAULT_CRITERIA_LAPSE_SESSIONS,
    DEFAULT_LATCH_HORIZON_SESSIONS,
    zone_cap_for_pivot,
)
from swing.latches.identity import LatchIdentity, parse_session_date
from swing.latches.models import (
    VERDICT_FAILED,
    VERDICT_PASSED,
    VERDICT_UNVERIFIABLE,
    DailyBar,
    DegradedFire,
    EntryRecord,
    FireRow,
    Latch,
    LatchDerivation,
)

# The display precision every price comparison rounds to (the
# price-precision-parity gotcha): a sub-cent float artifact must never fork a
# latch or flip an agreement flag.
_PRICE_DP = 2

# `declined` and `criteria_lapsed` BOTH REUSE `horizon_expired` (RD OQ-2's
# Option B -- ruled for `criteria_lapsed`, applied to `declined` as residual
# R1). The state enum is a MECHANISM -- everything that must tell these apart
# from a horizon expiry keys on the REASON, which is first-class: the
# stale-order severity (`orders.py` `_CRITICAL_STALE_CLEAR_REASONS`), the
# `framework_withdrawn` classifier rung, and the panel's `_state_label`
# branches. The alternative -- a new `LATCH_STATES` member -- is FOUR persisted
# CHECK clauses across migrations 0032 and 0033 and buys nothing the reason does
# not carry.
#
# THREE REASONS NOW SHARE ONE STATE, which is exactly what OQ-2 says the state
# enum is for -- and it is also the cost the render tests pin: a consumer that
# reads `state` instead of `clear_reason` conflates all three, so the obligation
# is pinned CALLER-SIDE by test rather than promised in a comment (gotcha #31).
_STATE_BY_CLEAR_REASON = {
    "fill": "filled",
    "invalidation": "invalidated",
    "horizon": "horizon_expired",
    "superseded": "superseded",
    "declined": "horizon_expired",
    "criteria_lapsed": "horizon_expired",
}


@dataclass
class _Draft:
    """A latch under construction during the per-ticker fold (MUTABLE)."""

    fire: FireRow
    anchor: date
    pivot: float
    stop: float
    horizon_expiry: date
    reconfirmation_candidate_ids: list[int] = field(default_factory=list)
    reconfirmation_sessions: list[str] = field(default_factory=list)

    @property
    def candidate_set(self) -> set[int]:
        return {self.fire.candidate_id, *self.reconfirmation_candidate_ids}

    @property
    def zone_cap(self) -> float:
        """The frozen buy-zone limit cap. Single-sourced in
        `swing/latches/constants.py` so the fill heuristic, the finalized
        `Latch` and the dashboard's buy limit cannot drift apart."""
        return zone_cap_for_pivot(self.pivot)


# THE PRECEDENCE LADDER (RD's R6 ruling, 2026-08-06), now COMPLETE:
#
#     fill > declined > superseded > invalidation > criteria_lapsed > horizon
#
# Its AUTHORITY is that ruling, not this table. Item 3a shipped the ladder
# PROJECTED onto five, because `criteria_lapsed` had no producer and a rung for
# a reason nothing can construct is a guard preceding its condition; item 3b
# gives it one, so the projection is now the whole ladder. The domain is pinned
# against `LATCH_CLEAR_REASONS` by test, so the vocabulary and its precedence
# cannot drift apart: adding a reason without ranking it fails immediately --
# which is what forced this entry rather than leaving the two out of step.
#
# `criteria_lapsed` sits BELOW `invalidation` and ABOVE `horizon`: framework
# EVIDENCE that the setup died outranks framework evidence that it merely
# decayed, and both outrank a DEADLINE.
#
# RANK BREAKS SAME-SESSION TIES AND NOTHING ELSE. A terminal is an event with a
# DATE and the EARLIEST one ends the mandate; nothing later can un-happen it
# (L10). A resolver that scanned for one reason before considering another would
# rewrite a terminal that had already resolved -- and would then compare the
# fill against the wrong date, attributing a buy to a mandate the framework had
# already retired.
#
# The reasoning behind the order is RD's: operator FACTS (a fill) beat operator
# DECISIONS (a decline) beat framework EVENTS (a re-fire, which is an
# affirmative CURRENT fact) beat framework EVIDENCE of decay (an invalidation)
# beat DEADLINES (the horizon).
#
# WHAT THIS TABLE DOES *NOT* CLAIM, stated so it is not read as more than it is
# (Codex R5). `superseded` is stamped by the FOLD, not selected here. This table
# supplies only the tie-breaking half of `_Terminal.order_key`, which orders by
# SESSION first and consults the rank when two terminals share a date; it never
# decides WHICH terminal a latch gets.
#
# A different-pivot re-fire dated exactly on the predecessor's `horizon_expiry`
# is settled in clause (iii), which builds the `superseded` candidate and ranks
# it against the resolver's own answer for that latch.
_CLEAR_REASON_RANK = {
    "fill": 0,
    "declined": 1,
    "superseded": 2,
    "invalidation": 3,
    "criteria_lapsed": 4,
    "horizon": 5,
}


@dataclass(frozen=True)
class _Terminal:
    reason: str
    session: date
    trade_id: int | None = None
    fill_link_basis: str | None = None

    @property
    def order_key(self) -> tuple[date, int]:
        """Earliest date first; rank only on a tie."""
        return (self.session, _CLEAR_REASON_RANK[self.reason])


def _validate_fire(fire: FireRow) -> tuple[date | None, str | None]:
    """Return ``(anchor, None)`` for a usable fire, else ``(None, reason)``.

    Every shape here was checked against the REAL write boundary (plan A.10):
    migration 0001 puts NO ``NOT NULL`` on ``candidates.pivot`` /
    ``initial_stop`` and no bucket<->pivot CHECK, and SQLite stores
    ``float('nan')`` as NULL -- so a ``bucket='aplus'`` row with a missing or
    non-finite price is reachable, not impossible.
    """
    try:
        anchor = parse_session_date("action_session_date", fire.action_session_date)
    except ValueError:
        return None, "bad_session_date"
    if not _usable_price(fire.pivot):
        return None, "pivot_missing"
    if not _usable_price(fire.initial_stop):
        return None, "stop_missing"
    if float(fire.initial_stop) >= float(fire.pivot):
        return None, "stop_not_below_pivot"
    return anchor, None


def _usable_price(value) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value)) and float(value) > 0.0


def _eligible_bars(
    bars: list[DailyBar], *, anchor: date, upper: date,
) -> list[DailyBar]:
    """The bar walk's eligible set: ``anchor <= session <= upper``, INCLUSIVE
    at BOTH ends (plan A.7).

    The anchor session's own bar counts (the mandate is live from that
    session's open); a bar before the anchor is history the pivot was computed
    FROM, not an invalidation of a mandate that did not yet exist.
    """
    return sorted(
        (b for b in bars if anchor <= b.session <= upper),
        key=lambda b: b.session,
    )


def _match_fill(
    draft: _Draft,
    entries: list[EntryRecord],
    *,
    consumed: set[int],
    effective_end: date,
    as_of: date,
) -> tuple[EntryRecord | None, str | None]:
    """The two-rung fill ladder, EXACT first (plan A.6).

    Rung 1 (``candidate_id``): an entry whose ``candidate_id`` is in this
    latch's candidate set AND dated inside ``[anchor, as_of]``.
    Rung 2 (``windowed``): ONLY when ``entry.candidate_id IS NULL`` -- ticker
    match inside ``[anchor, min(effective_end, as_of)]``, where
    ``effective_end`` is the ACTUAL live window (bounded by the non-fill
    terminal), not the nominal horizon.

    The windowed rung ADDITIONALLY requires the entry price to sit inside this
    latch's own frozen executable zone (see `_price_in_executable_zone`). Date
    proximity alone is not identity: RD constraint 4 says "a pre-existing
    position or unrelated order in the same ticker must not read as this
    latch's fill", and `trades.candidate_id` is nullable (migration 0021
    backfilled every pre-v21 row to NULL), so an unrelated manual/legacy buy in
    the same ticker at an unrelated price would otherwise CLEAR the mandate --
    marking it `filled` and silencing the order alarms for a fire the operator
    never acted on.

    ``as_of`` IS LOAD-BEARING ON BOTH RUNGS. The open-latch rule's liveness
    PROBE asks "had this latch terminated by session S?", and a fill dated
    AFTER S has not happened yet as of S. Without the bound the probe sees a
    FUTURE fill, concludes the latch was already dead at S, and opens a second
    latch where the correct answer is a re-confirmation -- i.e. the probe and
    the final resolution disagree about the same latch.
    """
    cset = draft.candidate_set
    available = [e for e in entries if e.trade_id not in consumed]
    exact = [
        e for e in available
        if e.candidate_id is not None
        and e.candidate_id in cset
        and draft.anchor <= e.entry_date <= as_of
    ]
    if exact:
        return min(exact, key=lambda e: (e.entry_date, e.trade_id)), "candidate_id"
    windowed = [
        e for e in available
        if e.candidate_id is None
        and draft.anchor <= e.entry_date <= min(effective_end, as_of)
        and _price_in_executable_zone(e.entry_price, draft)
    ]
    if windowed:
        return min(windowed, key=lambda e: (e.entry_date, e.trade_id)), "windowed"
    return None, None


def _price_in_executable_zone(entry_price, draft: _Draft) -> bool:
    """Could a fill at `entry_price` have come from THIS latch's mandate?

    The mandate is a BUY STOP at the frozen pivot with a limit cap at
    pivot x 1.03, so an execution it produced lands in the CLOSED interval
    [pivot, zone_cap] -- a gap through the cap is exactly what the cap exists to
    refuse. Compared at display precision (the price-precision-parity gotcha).

    An ABSENT or non-finite price is NOT verifiable, so it does NOT match: the
    windowed rung is a heuristic for legacy rows, and a heuristic must not clear
    a live mandate on evidence it cannot check. The EXACT `candidate_id` rung is
    unaffected -- an explicit link is authoritative regardless of price.
    """
    if entry_price is None or isinstance(entry_price, bool):
        return False
    if not isinstance(entry_price, (int, float)):
        return False
    value = float(entry_price)
    if not math.isfinite(value):
        return False
    return (round(draft.pivot, _PRICE_DP)
            <= round(value, _PRICE_DP)
            <= round(draft.zone_cap, _PRICE_DP))


def _has_fill_link_anomaly(draft: _Draft, entries: list[EntryRecord]) -> bool:
    """A ``candidate_id`` match dated BEFORE the anchor is NOT a fill -- it is
    a mis-linked row, surfaced loudly rather than silently clearing a latch
    backwards."""
    cset = draft.candidate_set
    return any(
        e.candidate_id is not None
        and e.candidate_id in cset
        and e.entry_date < draft.anchor
        for e in entries
    )


def _resolve_decline(
    draft: _Draft, decisions, *, upper: date,
) -> _Terminal | None:
    """The ``declined`` terminal for this draft, or ``None`` (RD OQ-4).

    THE CROSS-KIND RESOLVER, NOT "THE LATEST DECLINE". ``governing_decision``
    resolves the ``place``/``decline`` FAMILY together because they are the two
    mutually exclusive answers to ONE question -- so ``decline(D5)`` followed by
    ``place(D6)`` yields a PLACE and this latch does not terminate. Keying on the
    latest DECLINE instead would withdraw a mandate the operator had corrected
    himself and re-placed, while the classifier went on scoring it ``accepted``:
    one latch, two contradictory answers. Sharing the resolver is the only thing
    that makes them agree.

    The family and window scoping live in ``admissible_decisions``, which BOTH
    this resolver and ``classify_latch`` call -- and the filter runs BEFORE the
    winner is chosen, never after (see that function).

    ``upper`` is the caller's as-of bound already capped at ``horizon_expiry``:
    an intent that has not happened yet as of a liveness probe must not decide
    it, and one recorded after the mandate lapsed is not a withdrawal OF it.
    """
    governing = governing_decision(admissible_decisions(
        decisions, candidate_set=draft.candidate_set,
        lower=draft.anchor, upper=upper))
    if governing is None or governing.intent_kind != "decline":
        return None
    try:
        session = date.fromisoformat(str(governing.action_session_date))
    except (TypeError, ValueError):        # pragma: no cover -- filtered above
        return None
    return _Terminal("declined", session)


def materiality_floor(
    *, adr_pct, pivot: float, adr_multiple: float, min_widening_pct: float,
) -> float | None:
    """The OQ-10 two-term materiality floor, in PRICE. `None` when unusable.

    THE ONLY PLACE THE FLOOR IS COMPUTED, which is what turns RD's "never a
    substitute constant" from a claim about a call graph into a property of one
    function: it returns `None` for a NULL or non-finite `adr_pct`, and
    returning ANY number IS the fallback he forbade. That is also what makes
    the rule testable at all -- an order-of-operations version is
    observationally invisible from outside, because an implementation with a
    silent substitute can ALSO emit a missing-ADR block reason and every
    black-box output is identical.

    BOTH TERMS ARE NECESSARY and each covers the other's blind spot:

    * ADR-scaling is weakest exactly where it matters most. With a pivot of 100
      and an ADR of 0.40%, the series 99.80/99.90/99.75/99.60/99.30 widens
      $0.50 and clears a $0.40 ADR-only floor -- the panel telling the operator
      to cancel a sub-1% consolidation the session before it could break out.
      The pivot term makes that floor $2.00 and refuses.
    * The ADR term is what stops a 12%-ADR name lapsing on ordinary noise.
    """
    if not _usable_price(pivot):
        return None
    if adr_pct is None or isinstance(adr_pct, bool):
        return None
    if not isinstance(adr_pct, (int, float)):
        return None
    value = float(adr_pct)
    if not math.isfinite(value) or value <= 0.0:
        return None
    return max(adr_multiple * (value / 100.0) * float(pivot),
               min_widening_pct / 100.0 * float(pivot))


def _enumerate_sessions(start: date, end: date) -> list[date]:
    """Every NYSE session in the CLOSED interval `[start, end]`.

    The completeness requirement is a safety check whose FAILURE can clear a
    breakout, so the enumeration is executable rather than left to judgement.
    """
    if end < start:
        return []
    out: list[date] = []
    cursor = start if is_trading_session(start) else session_offset(start, 1)
    while cursor <= end:
        out.append(cursor)
        cursor = session_offset(cursor, 1)
    return out


def _sound_envelope(bar: DailyBar) -> bool:
    """Does this bar's OHLC actually hold together? (Codex R4 MAJOR.)

    `DailyBar.__post_init__` validates FINITENESS ONLY and the archive reader
    polices nothing else, so a row recording `open = 101` against `high = 99`
    constructs happily -- and this project has a MEASURED invalid-OHLC
    population (the 18-D research monitor baselines `invalid_ohlc` at 23 of 77
    unique signals), so it is a real shape rather than a hypothetical one.

    It matters because 2a asks *was the entry trigger reached* and answers from
    the HIGH alone. On such a bar the OPEN proves a touch the HIGH denies, and
    reading the high as complete evidence withdraws the mandate from a stock
    whose stop-limit would already have triggered -- the catastrophic direction.

    The framework must not pick the reading that favours withdrawal, and must
    not pick the other one either: the bar is UNTRUSTWORTHY, so its DATE becomes
    ambiguous and the existing coverage check refuses the window.

    COMPARED AT DISPLAY PRECISION, deliberately unlike the duplicate test above.
    The two ask opposite questions: there, rounding HID a real difference between
    two rows, so it must be raw; here, rounding avoids condemning a legitimate
    bar over a sub-cent float artifact, while a genuine inversion (101 vs 99) is
    orders of magnitude clear of a cent -- and a sub-cent inversion cannot move a
    materiality floor anyway.
    """
    o = round(bar.open, _PRICE_DP)
    h = round(bar.high, _PRICE_DP)
    low = round(bar.low, _PRICE_DP)
    c = round(bar.close, _PRICE_DP)
    if min(o, h, low, c) <= 0.0:
        return False
    # `<=` throughout: an untraded/flat session legitimately has all four equal,
    # and the QUALIFYING fixtures rely on `high == close`.
    return low <= min(o, c) and max(o, c) <= h and low <= h


def _canonical_bars(bars) -> tuple[dict[date, DailyBar], set[date]]:
    """Collapse duplicate bars per date. Returns `(by_session, ambiguous)`.

    A bar failing `_sound_envelope` is refused OUTRIGHT -- its date is ambiguous
    before any duplicate question is asked, because an incoherent bar is not
    evidence of anything.

    Two rows for one date collapse ONLY IF THEY AGREE ON EVERY FIELD THE
    CONJUNCTS READ -- the CLOSE and, because OQ-14 puts 2a on the session HIGH,
    THE HIGH TOO. A close-only canonicalization is unsafe: two rows both closing
    95 with highs 101 and 99 would collapse silently, and if the 99 row survived,
    2a would see no pivot touch and clear a latch whose stop-limit had already
    triggered at 101.

    A disagreement makes the DATE ambiguous -- the framework cannot say which
    was that session's bar, and `first(B)`, `min(B)` and the widening would all
    depend on row order. Canonicalization runs ONCE, ahead of every clause, so
    no clause ever sees a raw duplicate.
    """
    by_session: dict[date, DailyBar] = {}
    ambiguous: set[date] = set()
    for bar in bars:
        if not _sound_envelope(bar):
            # The final pop below clears the date even when a SOUND row for it
            # was seen first -- one incoherent row poisons the session.
            ambiguous.add(bar.session)
            continue
        prior = by_session.get(bar.session)
        if prior is None:
            by_session[bar.session] = bar
            continue
        # THE COMPARISON IS RAW, NOT ROUNDED, AND THE DIFFERENCE DECIDED A
        # WITHDRAWAL (Codex R1 CRITICAL). Rounding here contradicted the very
        # guarantee this function exists to give, because the MATERIALITY test
        # consumes RAW closes and rounds only the DIFFERENCE (deliberately, and
        # correctly -- see clause 4). So two D0 rows closing 64.0151 and 64.0249
        # both rounded to 64.02, collapsed as "identical", and whichever the
        # archive listed first decided the answer:
        #
        #     round(64.0249 - 61.0249, 2) == 3.00  -> WITHDRAWS  (floor 3.00)
        #     round(64.0151 - 61.0249, 2) == 2.99  -> preserves
        #
        # A cent-grain equality is the right comparison for a DISPLAYED price;
        # it is the wrong one for deciding that two rows ARE the same bar when a
        # sub-cent difference propagates into a threshold test. Any raw
        # disagreement now makes the DATE ambiguous -- the framework declines to
        # say which row was that session's bar -- and an ambiguous date is a
        # coverage gap, which never withdraws. Byte-identical duplicates (what a
        # re-written archive window actually produces) still collapse.
        if prior.close != bar.close or prior.high != bar.high:
            ambiguous.add(bar.session)
    for session in ambiguous:
        by_session.pop(session, None)
    return by_session, ambiguous


def _coverage_gap(
    by_session: dict[date, DailyBar], ambiguous: set[date],
    *, start: date, end: date,
) -> date | None:
    """The first session in `[start, end]` with no unambiguous bar, else None.

    THE COMPLETENESS REQUIREMENT IS NOT DEFENSIVE PADDING -- without it 2a is an
    ARGUMENT FROM SILENCE and its whole safety guarantee is void. With a pivot
    of 100 and five failing sessions whose true closes are 99/101/98/97/96, an
    archive missing the 101 bar leaves 99/98/97/96: no bar reaches the pivot,
    the window ends at its low, and the rule WITHDRAWS THE MANDATE FROM A STOCK
    THAT DID BREAK OUT. 2a's entire claim is "price never traded through the
    pivot", and a gap cannot support it.
    """
    for session in _enumerate_sessions(start, end):
        if session in ambiguous or session not in by_session:
            return session
    return None


@dataclass(frozen=True)
class _LapseAnalysis:
    """Everything the lapse rule computed, ARMED OR NOT.

    `criteria_lapse_armed` must change EXACTLY ONE thing -- whether the
    resolved terminal is returned -- so this is computed on every path. A flag
    that short-circuited the streak, the conjuncts or the diagnostics would make
    report-only measure NOTHING, which is the failure that would render RD's
    framing ruling worthless.
    """

    qualifying_session: date | None = None
    failed_sessions: tuple[date, ...] = ()
    unverifiable_sessions: tuple[date, ...] = ()
    unverifiable_causes: tuple[str, ...] = ()
    conflicted_sessions: tuple[date, ...] = ()
    unverifiable_tail: int = 0
    directional_evaluable: bool = True
    directional_block_reason: str | None = None


def _window_qualifies(
    window: list[date], *, draft: _Draft, by_session, ambiguous,
    floor: float,
) -> bool:
    """Conjuncts 2a + 2b for ONE candidate N-failure window.

    2a is a LIFETIME property over `[anchor, s]` where `s` is THIS WINDOW'S OWN
    terminal -- never `derivation_session`. Bounding it at "today" would let
    FUTURE evidence erase a PAST terminal: a latch closing 95/94/93/92/90 lapses
    on D5, and a D6 close of 105 would then disqualify 2a and RESURRECT a latch
    that had already cleared -- L10 broken through the conjunct instead of
    through the precedence. Evaluating each window through its own terminal
    makes the answer permanent.

    2a TESTS THE SESSION HIGH (OQ-14): the mandate is a GTC stop-limit that
    TRIGGERS ON A TOUCH, so 2a's question is *was the entry trigger reached*,
    and the touch is the fact. A close-based 2a would clear a mandate whose
    order may already have filled intraday. RD's constraint 6 ("closes, not
    intraday touches") stands untouched for INVALIDATION, which asks a
    different question -- did the mandate die -- and both choices err toward
    mandate-preservation.
    """
    s = window[-1]
    # --- 2a: LIFETIME, and it may only be ASSERTED over a COMPLETE range.
    if _coverage_gap(by_session, ambiguous, start=draft.anchor, end=s) is not None:
        return False
    pivot = round(draft.pivot, _PRICE_DP)
    for session, bar in by_session.items():
        if draft.anchor <= session <= s and round(bar.high, _PRICE_DP) >= pivot:
            return False
    # --- 2b: the decay test over the STREAK window, in BAR dates.
    #
    # BAR-DATED, RULED (OQ-11). `W` is in ACTION-SESSION dates and `B` in BAR
    # dates, and they differ by a session that is NOT reliably one -- a ticker
    # whose archive lagged the cohort is persisted with an older close under a
    # fresher stamp. So there is no offset at which a verdict/bar join would be
    # correct, and this makes NO join at any offset: it claims only *price
    # action during the period the gate was failing*.
    first_w, last_w = window[0], window[-1]
    if _coverage_gap(by_session, ambiguous,
                     start=first_w, end=last_w) is not None:
        return False
    b = [by_session[d] for d in _enumerate_sessions(first_w, last_w)]
    if len(b) < 2:                      # pragma: no cover -- N >= 2 + complete
        return False
    first_close = round(b[0].close, _PRICE_DP)
    last_close = round(b[-1].close, _PRICE_DP)
    if not last_close < first_close:
        return False
    # CLAUSE 3 IS LOAD-BEARING: a bare endpoint test clears a stock that
    # collapsed then rallied 19% off its low and is about to cross the pivot.
    if last_close > min(round(x.close, _PRICE_DP) for x in b):
        return False
    # CLAUSE 4 -- MATERIALITY, ROUNDED AFTER THE SUBTRACTION, NEVER BEFORE.
    # Rounding each operand first does not help: round(64.02, 2) -
    # round(61.02, 2) is still 2.999999999999993, because rounding a float
    # returns a float. Only rounding the DIFFERENCE yields 3.0. Getting this
    # wrong flips a terminal while the card displays exact equality -- the
    # price-precision-parity gotcha landing on the one comparison that
    # withdraws a mandate.
    widening = round(b[0].close - b[-1].close, _PRICE_DP)
    return widening >= round(floor, _PRICE_DP)


def _analyze_criteria_lapse(
    draft: _Draft,
    *,
    verdicts,
    bars: list[DailyBar],
    archive_status: str | None,
    upper: date,
    sessions: int,
    adr_multiple: float,
    min_widening_pct: float,
) -> _LapseAnalysis:
    """The whole `criteria_lapsed` computation. PURE, and ALWAYS RUN.

    THE STREAK'S DOMAIN IS EVALUATED SESSIONS, NOT CALENDAR SESSIONS, and an
    UNVERIFIABLE session PAUSES it rather than breaking it (OQ-17, on structural
    grounds): BREAK would make an off-screen name's real accumulated decay
    evidence vanish on the day it left the screen -- erasing history because the
    instrument went dark. What makes PAUSE sound is that the price evidence is
    CONTINUOUS by construction (2b requires complete coverage across the whole
    span, evaluated or not) and the gap is DISCLOSED rather than hidden.

    THE SCAN RETURNS THE EARLIEST QUALIFYING WINDOW, walking trailing
    N-failure windows chronologically. That is the only formulation satisfying
    both requirements at once: a window failing the conjunct does not end the
    matter (later windows are still tried), and once a window qualifies the
    answer never moves (re-deriving tomorrow returns the same window). "The last
    N failures" alone would slide the clear date forward every session.
    """
    in_domain = [
        v for v in (verdicts or ())
        if draft.anchor <= v.action_session <= upper
    ]
    in_domain.sort(key=lambda v: v.action_session)
    conflicted = tuple(
        v.action_session for v in in_domain if v.conflicted)

    # --- the CURRENT streak: everything after the last PASSED session.
    last_pass_index = -1
    for i, v in enumerate(in_domain):
        if v.classification == VERDICT_PASSED:
            last_pass_index = i
    tail_slice = in_domain[last_pass_index + 1:]
    failed_sessions = tuple(
        v.action_session for v in tail_slice
        if v.classification == VERDICT_FAILED)
    unverifiable = [
        v for v in tail_slice if v.classification == VERDICT_UNVERIFIABLE]
    unverifiable_sessions = tuple(v.action_session for v in unverifiable)
    unverifiable_causes = tuple(v.cause or "absent" for v in unverifiable)

    # --- the UNVERIFIABLE SUFFIX of the in-domain sequence, which is what
    # drives the UNVERIFIABLE render. Owned HERE rather than at the `Latch`
    # constructor, which never sees the PASSED sessions and so cannot tell a
    # genuine 2-tail from one that ignored an intervening PASS.
    tail = 0
    for v in reversed(in_domain):
        if v.classification != VERDICT_UNVERIFIABLE:
            break
        tail += 1

    by_session, ambiguous = _canonical_bars(
        _eligible_bars(bars, anchor=draft.anchor, upper=upper))

    # --- `directional_evaluable`: "IF this streak reached N, COULD the
    # directional test be evaluated?" It is NOT "2b currently holds" (2b is
    # undefined below N) and NOT a prediction. Without it the card can show a
    # complete failed streak beside a plain live status while the directional
    # predicate had no data at all -- telling the operator a withdrawal is one
    # session away when it is in fact unreachable.
    floor = materiality_floor(
        adr_pct=draft.fire.adr_pct, pivot=draft.pivot,
        adr_multiple=adr_multiple, min_widening_pct=min_widening_pct)
    block_reason: str | None = None
    if archive_status is not None and archive_status != ARCHIVE_STATUS_OK:
        block_reason = "archive unavailable"
    elif floor is None:
        block_reason = "no usable ADR on the fire's own candidates row"
    elif in_domain:
        gap = _coverage_gap(
            by_session, ambiguous,
            start=draft.anchor, end=in_domain[-1].action_session)
        if gap is not None:
            block_reason = f"archive gap {gap.isoformat()}"

    # THE SCAN IS GATED ON WHAT MAKES IT UNCOMPUTABLE, NEVER ON THE TRAILING-GAP
    # DIAGNOSTIC ABOVE (Codex R1 MAJOR). `block_reason` answers "could the
    # directional test be evaluated AS OF TODAY?" -- a statement about the
    # CURRENT edge of the evidence. Letting it gate the HISTORICAL scan re-opened
    # L10 one level above the place `_window_qualifies` closes it: a D6 session
    # the framework evaluated but whose archive bar has not landed (the ordinary
    # lag) set `qualifying` back to `None` although D1..D5 were complete and
    # qualifying. Armed, a mandate withdrawn on D5 comes back to life on D6
    # because a bar went missing; unarmed, the calibration read silently loses
    # the would-clear it exists to count -- in the COMMON case, not an exotic one.
    #
    # The completeness requirement is NOT weakened: `_window_qualifies` enforces
    # it PER WINDOW, over `[anchor, s]` and `[first_w, last_w]`, which is where
    # it belongs -- bounded by that window's own terminal, so the answer is
    # permanent. The two conditions kept here are different in kind: without a
    # floor there is no materiality test to run at all, and an UNREADABLE archive
    # is our own ignorance, which 21-G's asymmetry says may never license an
    # assertion.
    scan_blocked = (
        floor is None
        or (archive_status is not None and archive_status != ARCHIVE_STATUS_OK))

    qualifying: date | None = None
    if not scan_blocked:
        streak: list[date] = []
        for v in in_domain:
            if v.classification == VERDICT_PASSED:
                streak = []
                continue
            if v.classification != VERDICT_FAILED:
                continue                      # PAUSE -- neither reset nor step
            streak.append(v.action_session)
            if len(streak) < sessions:
                continue
            window = streak[-sessions:]
            if _window_qualifies(window, draft=draft, by_session=by_session,
                                 ambiguous=ambiguous, floor=floor):
                qualifying = window[-1]
                break                         # the EARLIEST qualifying window

    return _LapseAnalysis(
        qualifying_session=qualifying,
        failed_sessions=failed_sessions,
        unverifiable_sessions=unverifiable_sessions,
        unverifiable_causes=unverifiable_causes,
        conflicted_sessions=conflicted,
        unverifiable_tail=tail,
        directional_evaluable=block_reason is None,
        directional_block_reason=block_reason,
    )


def _resolve_terminal(
    draft: _Draft,
    *,
    bars: list[DailyBar],
    entries: list[EntryRecord],
    consumed: set[int],
    horizon_ref: date,
    bar_bound: date,
    fill_bound: date,
    horizon_sessions: int,
    dry_run: bool,
    decisions=(),
    lapse_session: date | None = None,
) -> _Terminal | None:
    """Resolve this latch's terminal, or ``None`` when it is still live.

    Three passes (plan A.6 c), which is what removes the circularity between
    "the fill bounds the terminal" and "the terminal bounds the fill":

    1. the NON-FILL candidates -- the invalidation bar walk, the operator's
       governing decline, the framework's own ``criteria_lapsed`` withdrawal
       (only when the caller passes ``lapse_session``), and the horizon --
       resolved EARLIEST-DATE-FIRST with ``_CLEAR_REASON_RANK`` breaking a
       same-session tie only;
    2. the fill search, bounded by that non-fill terminal;
    3. the fill's own rung, which is the same ranked comparison: rank 0 means a
       fill AT OR BEFORE the winning non-fill terminal takes it.

    So the precedence is
    ``fill > declined > invalidation > criteria_lapsed > horizon`` (RD gate G.4
    as extended by his OQ-4 and R6 rulings: operator facts beat operator
    decisions beat framework evidence beats deadlines). ``superseded`` is stamped
    by the FOLD rather than here -- it is authored by the arrival of the NEXT
    fire, which this function cannot see -- and it carries its rank for the one
    comparison the fold makes.

    ``lapse_session`` IS THE CALLER'S DECISION, and that single conditional is
    the ONLY thing the OQ-9 arm flag gates. The lapse ANALYSIS runs on every
    path; a flag placed any earlier -- skipping the streak, the conjuncts or the
    diagnostics -- would make report-only measure nothing.

    THREE SEPARATE BOUNDS, because they answer different questions:

    * ``bar_bound``   -- the newest session whose CLOSE may be judged.
    * ``fill_bound``  -- the newest session whose FILL may be counted.
    * ``horizon_ref`` -- the session the horizon is measured against.

    They diverge for the liveness PROBE. "Was this latch live when a fire for
    session S arrived?" is asked at the moment that fire exists -- the evening
    BEFORE S -- so S's own bar and S's own fill have not happened yet and must
    NOT decide it. The HORIZON is different: a mandate whose window closes at S
    is already dead for S, so the horizon stays INCLUSIVE at S.

    ``dry_run`` makes this a read-only probe, so a probe never consumes a trade
    the real resolution must see.
    """
    candidates: list[_Terminal] = []
    # The walk stops at the HORIZON EXPIRY as well as at `bar_bound`: once the
    # mandate is dead, a later close below the stop is not an invalidation OF
    # IT. Without the cap a post-expiry break would overwrite `horizon_expired`
    # with `invalidated`, move the clear session forward, and escalate a stale
    # resting order from `warning` to `critical` -- all for a mandate that had
    # already lapsed. The expiry session ITSELF is still walked, so same-session
    # precedence (invalidation beats horizon) is preserved.
    for bar in _eligible_bars(
        bars, anchor=draft.anchor, upper=min(bar_bound, draft.horizon_expiry)
    ):
        # RD constraint 6: CLOSES, not intraday touches. Strict `<` -- a close
        # exactly AT the frozen stop is not below it -- and compared at DISPLAY
        # precision on BOTH sides, like every other price comparison in this
        # arc. A parquet float artifact (close 14.879999999 vs a 14.88 stop)
        # would otherwise CLEAR a live mandate while the panel renders both
        # numbers as 14.88, and clearing silences the no-resting-order alarm.
        # Rounding is conservative in the SAFE direction: it keeps a marginal
        # mandate armed rather than silently killing it.
        if round(bar.close, _PRICE_DP) < round(draft.stop, _PRICE_DP):
            candidates.append(_Terminal("invalidation", bar.session))
            break
    # THE OPERATOR'S OWN DECISION, capped at the expiry like every other walk.
    decline = _resolve_decline(
        draft, decisions, upper=min(fill_bound, draft.horizon_expiry))
    if decline is not None:
        candidates.append(decline)
    # THE FRAMEWORK'S OWN WITHDRAWAL. `lapse_session` is already bounded by
    # `min(bar_bound, horizon_expiry)` at the analysis, mirroring the
    # invalidation walk's cap verbatim and for the identical reason: once the
    # mandate is dead, a later structural failure is not a withdrawal OF IT.
    #
    # THE CALLER DECIDES WHETHER TO PASS IT, and that is the ONLY thing the arm
    # flag gates. The analysis itself runs on every path.
    if lapse_session is not None:
        candidates.append(_Terminal("criteria_lapsed", lapse_session))
    if sessions_behind(horizon_ref, draft.anchor) >= horizon_sessions:
        # Inclusive-expire, matching the in-tree observe-window precedent
        # (`swing/pipeline/runner.py` `sessions_since_detection >= max_pending`).
        #
        # THE HORIZON IS A RANKED CANDIDATE, NOT A FALLBACK, and the outcome is
        # identical: both other walks are capped AT the expiry, so any date they
        # produce is at-or-before it, and on the boundary session their ranks
        # win. Expressing it as a candidate is what makes `horizon`'s place in
        # the ladder a fact the table decides rather than one the control flow
        # implies.
        candidates.append(_Terminal("horizon", draft.horizon_expiry))

    nonfill = min(candidates, key=lambda t: t.order_key) if candidates else None

    effective_end = (
        draft.horizon_expiry if nonfill is None
        else min(draft.horizon_expiry, nonfill.session)
    )
    entry, basis = _match_fill(
        draft, entries, consumed=consumed, effective_end=effective_end,
        as_of=fill_bound)

    if entry is not None and not dry_run:
        # An accepted match is definitively THIS latch's trade, so it is
        # consumed either way -- rule (b), one trade fills at most one latch.
        consumed.add(entry.trade_id)
    if entry is not None:
        fill = _Terminal("fill", entry.entry_date, entry.trade_id, basis)
        # THE SAME RANKED COMPARISON as the non-fill candidates, so the fill's
        # place in the ladder is decided by the table too. Rank 0 is what makes
        # a fill dated exactly ON the winning terminal's session take it --
        # "you cannot decline a filled mandate", and the same for an
        # invalidation or an expiry landing that day.
        if nonfill is None or fill.order_key <= nonfill.order_key:
            return fill
    return nonfill


def _finalize(
    draft: _Draft,
    *,
    terminal: _Terminal | None,
    bars: list[DailyBar],
    horizon_session: date,
    derivation_session: date,
    horizon_sessions: int,
    fill_link_anomaly: bool,
    analysis: _LapseAnalysis | None = None,
    would_clear_session: date | None = None,
) -> Latch:
    eligible = _eligible_bars(
        bars, anchor=draft.anchor, upper=derivation_session)
    sessions_elapsed = sessions_behind(horizon_session, draft.anchor)
    state = "armed" if terminal is None else _STATE_BY_CLEAR_REASON[terminal.reason]
    analysis = analysis or _LapseAnalysis()
    return Latch(
        identity=LatchIdentity(
            candidate_id=draft.fire.candidate_id,
            evaluation_run_id=draft.fire.evaluation_run_id,
            ticker=draft.fire.ticker,
            detection_date=draft.fire.action_session_date,
            pipeline_run_id=draft.fire.pipeline_run_id,
        ),
        latched_pivot=draft.pivot,
        latched_initial_stop=draft.stop,
        zone_cap=draft.zone_cap,
        anchor=draft.anchor,
        horizon_expiry=draft.horizon_expiry,
        sessions_elapsed=sessions_elapsed,
        sessions_to_horizon=max(0, horizon_sessions - sessions_elapsed),
        state=state,
        clear_reason=None if terminal is None else terminal.reason,
        clear_session=None if terminal is None else terminal.session,
        clear_trade_id=None if terminal is None else terminal.trade_id,
        fill_link_basis=None if terminal is None else terminal.fill_link_basis,
        fill_link_anomaly=fill_link_anomaly,
        bars_available=bool(eligible),
        bars_through=eligible[-1].session if eligible else None,
        reconfirmation_candidate_ids=tuple(draft.reconfirmation_candidate_ids),
        reconfirmation_sessions=tuple(draft.reconfirmation_sessions),
        # The counts are DERIVED from the tuples by `Latch.__post_init__`,
        # which REJECTS a disagreement rather than absorbing it -- so these are
        # passed as `len(...)` at the one site that owns both.
        lapse_failed_sessions=analysis.failed_sessions,
        lapse_unverifiable_sessions=analysis.unverifiable_sessions,
        lapse_unverifiable_causes=analysis.unverifiable_causes,
        lapse_conflicted_sessions=analysis.conflicted_sessions,
        lapse_failed_count=len(analysis.failed_sessions),
        lapse_unchecked_count=len(analysis.unverifiable_sessions),
        lapse_unverifiable_tail=analysis.unverifiable_tail,
        directional_evaluable=analysis.directional_evaluable,
        directional_block_reason=analysis.directional_block_reason,
        lapse_qualifying_session=analysis.qualifying_session,
        lapse_would_clear_session=would_clear_session,
    )


def _counterfactual_would_clear(
    draft: _Draft,
    *,
    forced: _Terminal | None,
    analysis: _LapseAnalysis,
    bars: list[DailyBar],
    entries: list[EntryRecord],
    consumed: set[int],
    horizon_session: date,
    derivation_session: date,
    horizon_sessions: int,
    decisions,
) -> date | None:
    """The session the ARMED rule would have withdrawn this mandate on, or None.

    Populated ONLY when a side-effect-free re-run of the ENTIRE terminal
    resolution -- INCLUDING THE FILL PASS -- resolves to `criteria_lapsed`.

    Two scopes, stated because neither is obvious:

    * When the FOLD authored the terminal (`superseded` / the R6 `declined`),
      the resolver is not consulted at all, so the counterfactual is the same
      RANKED comparison the resolver uses -- `min` over `order_key` -- rather
      than a second rule.
    * REPORT-ONLY MEASURES THE FIRST HYPOTHETICAL CLEAR PER LATCH, NOT THE
      WHOLE ARMED CORPUS, and that is an accepted limitation rather than an
      oversight. Arming changes latch TOPOLOGY: a post-lapse same-pivot re-fire
      RECONFIRMS the old latch when unarmed but opens a NEW latch when armed, so
      the unarmed derivation never produces that counterfactual successor and
      cannot measure its streak or its fill. What this measures is: for each
      latch the framework actually derives, would the rule have withdrawn it,
      and when. That is the right question for calibrating N; the calibration
      read must not claim more.
    """
    if analysis.qualifying_session is None:
        return None
    lapse = _Terminal("criteria_lapsed", analysis.qualifying_session)
    if forced is not None:
        winner = min((forced, lapse), key=lambda t: t.order_key)
        return winner.session if winner.reason == "criteria_lapsed" else None
    probe = _resolve_terminal(
        draft, bars=bars, entries=entries, consumed=consumed,
        horizon_ref=horizon_session, bar_bound=derivation_session,
        fill_bound=horizon_session, decisions=decisions,
        horizon_sessions=horizon_sessions, dry_run=True,
        lapse_session=analysis.qualifying_session)
    if probe is not None and probe.reason == "criteria_lapsed":
        return probe.session
    return None


def _fold_ticker(
    ticker_fires: list[FireRow],
    *,
    bars: list[DailyBar],
    entries: list[EntryRecord],
    horizon_session: date,
    derivation_session: date,
    horizon_sessions: int,
    decisions=(),
    verdicts=(),
    archive_status: str | None = None,
    criteria_lapse_armed: bool = False,
    criteria_lapse_sessions: int = DEFAULT_CRITERIA_LAPSE_SESSIONS,
    criteria_lapse_min_widening_adr: float = (
        DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR),
    criteria_lapse_min_widening_pct: float = (
        DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT),
) -> tuple[list[Latch], list[DegradedFire]]:
    """The per-ticker fold implementing the OPEN-LATCH rule (plan A.2).

    Module-level (not a closure) so the loop variables it reads are BOUND
    parameters -- a closure over the enclosing per-ticker loop would be a
    late-binding hazard, and `consumed` in particular must be exactly this
    ticker's running set.
    """
    latches: list[Latch] = []
    degraded: list[DegradedFire] = []
    consumed: set[int] = set()
    open_draft: _Draft | None = None

    def _lapse_for(draft: _Draft, upper: date) -> _LapseAnalysis:
        """The lapse analysis for `draft`, bounded at `upper`.

        THE BOUND IS A PARAMETER BECAUSE THE PROBES ASK A DIFFERENT QUESTION.
        A liveness probe asks "had this latch terminated by session S?", and
        the facts that may decide that stop STRICTLY BEFORE the re-fire's own
        session -- exactly as the probe already treats the invalidation walk and
        the fill. Re-using the final bound here would let a lapse resolved ON
        the re-fire session decide a probe taken the session before it.
        """
        return _analyze_criteria_lapse(
            draft, verdicts=verdicts, bars=bars, archive_status=archive_status,
            upper=min(upper, draft.horizon_expiry),
            sessions=criteria_lapse_sessions,
            adr_multiple=criteria_lapse_min_widening_adr,
            min_widening_pct=criteria_lapse_min_widening_pct)

    def _armed_lapse(analysis: _LapseAnalysis) -> date | None:
        """THE ARM GATE, in ONE place so the probes and the final resolution
        cannot disagree about whether the rule is live."""
        return analysis.qualifying_session if criteria_lapse_armed else None

    def _close(draft: _Draft, *, forced: _Terminal | None = None) -> Latch:
        """`forced` is a terminal the FOLD authored rather than the resolver.

        `superseded` is the only such reason: it is created by the ARRIVAL of
        the next fire, which `_resolve_terminal` cannot see. The R6 branch below
        passes the winner of `declined` vs `superseded` through the same
        parameter, so the fold has exactly ONE stamping path.

        THE LAPSE ANALYSIS RUNS ON EVERY PATH, ARMED OR NOT (OQ-9). The arm flag
        changes exactly one thing -- whether the resolved terminal is RETURNED --
        because a flag that short-circuited the computation would measure
        nothing, and measurement is the entire purpose of shipping unarmed.
        """
        analysis = _lapse_for(draft, derivation_session)
        # THE COUNTERFACTUAL RUNS **BEFORE** THE ACTUAL RESOLUTION, and the
        # order is load-bearing rather than stylistic. The actual pass CONSUMES
        # the trade it matches (rule (b): one trade fills at most one latch), so
        # a counterfactual run afterwards would find the fill already consumed,
        # see no fill at all, and report a withdrawal on a mandate the armed
        # rule would have cleared BY FILL -- inflating the exact count the
        # calibration decision reads. The probe is `dry_run`, so running it
        # first consumes nothing.
        would_clear = _counterfactual_would_clear(
            draft, forced=forced, analysis=analysis, bars=bars,
            entries=entries, consumed=consumed,
            horizon_session=horizon_session,
            derivation_session=derivation_session,
            horizon_sessions=horizon_sessions, decisions=decisions)
        if forced is not None:
            terminal: _Terminal | None = forced
        else:
            terminal = _resolve_terminal(
                draft, bars=bars, entries=entries, consumed=consumed,
                horizon_ref=horizon_session, bar_bound=derivation_session,
                fill_bound=horizon_session, decisions=decisions,
                horizon_sessions=horizon_sessions, dry_run=False,
                # THE ARM FLAG GATES THIS ONE EXPRESSION, AND THAT IS THE WHOLE
                # DESIGN (OQ-9). `analysis.qualifying_session` is resolved on
                # EVERY path, armed or not; only whether it is OFFERED to the
                # ladder is conditional. A flag placed any earlier -- skipping
                # the streak fold, the conjuncts or the diagnostics -- would make
                # report-only measure nothing, which defeats the ruling that
                # created it.
                lapse_session=_armed_lapse(analysis))
        # THE COUNTERFACTUAL IS THE PRECEDENCE-RESOLVED ANSWER, NOT THE RAW
        # QUALIFYING SESSION -- and conflating them makes report-only LIE.
        # With an invalidation on D3, a fill on D4 and a qualifying lapse on
        # D5, the ARMED resolver clears by `fill`; a field that merely echoed
        # the qualifying session would nonetheless report "would withdraw on
        # D5", measuring a withdrawal the armed rule would never perform and
        # inflating exactly the count the calibration decision reads.
        #
        # AND A SECOND `min(...)` OVER THE NON-FILL CANDIDATES IS NOT THE FULL
        # LADDER. The fill is a SEPARATE pass whose window depends on which
        # non-fill terminal won, so a candidate-list-only counterfactual misses
        # a FILL-ONLY collision entirely. So it is the SAME ladder invoked a
        # second time with the lapse forced IN and `dry_run=True` -- no second
        # implementation, and only the ACTUAL pass may consume a trade.
        closed = _finalize(
            draft, terminal=terminal, bars=bars,
            horizon_session=horizon_session,
            derivation_session=derivation_session,
            horizon_sessions=horizon_sessions,
            fill_link_anomaly=_has_fill_link_anomaly(draft, entries),
            analysis=analysis, would_clear_session=would_clear)
        latches.append(closed)
        return closed

    for fire in sorted(ticker_fires, key=lambda f: f.sort_key):
        anchor, reason = _validate_fire(fire)
        if reason is not None:
            degraded.append(DegradedFire(
                candidate_id=fire.candidate_id,
                evaluation_run_id=fire.evaluation_run_id,
                ticker=fire.ticker,
                action_session_date=fire.action_session_date,
                reason=reason))
            continue

        if open_draft is not None:
            if open_draft.anchor == anchor:                       # clause (i)
                open_draft.reconfirmation_candidate_ids.append(fire.candidate_id)
                open_draft.reconfirmation_sessions.append(fire.action_session_date)
                continue
            # The facts that may decide liveness stop STRICTLY BEFORE the
            # re-fire's own session (see `_resolve_terminal`); the horizon
            # stays inclusive AT it.
            prior = session_offset(anchor, -1)
            # THE PROBES MUST SEE THE LAPSE TOO WHEN THE RULE IS ARMED, or the
            # fold's TOPOLOGY silently describes the unarmed world: a latch the
            # armed rule had already withdrawn would still look live, so a later
            # re-fire would fold in as a RE-CONFIRMATION rather than opening its
            # own mandate. Each probe gets the analysis bounded at ITS OWN
            # as-of, so a lapse resolved ON the re-fire session cannot decide a
            # probe taken the session before it.
            live_probe = _resolve_terminal(
                open_draft, bars=bars, entries=entries, consumed=consumed,
                horizon_ref=anchor,
                bar_bound=min(prior, derivation_session),
                fill_bound=prior, decisions=decisions,
                horizon_sessions=horizon_sessions, dry_run=True,
                lapse_session=_armed_lapse(
                    _lapse_for(open_draft, min(prior, derivation_session))))
            # THE FINAL RESOLUTION CAN REVERSE THE PROBE, AND THAT REVERSAL
            # OUTRANKS BOTH BRANCHES BELOW.
            #
            # The probe deliberately cannot see the re-fire session's own fill,
            # so it can report the old latch dead-by-horizon (clause iii) OR
            # still-live (clause ii) while the FINAL resolution -- which CAN see
            # it -- resolves that same latch to a FILL at-or-after this fire's
            # session. Arming a new mandate on top of that tells the operator to
            # buy a position he has JUST BOUGHT: the worst output this surface
            # can produce. Checked ONCE, ahead of both branches, so the horizon
            # path and the supersede path cannot diverge on it.
            final_probe = _resolve_terminal(
                open_draft, bars=bars, entries=entries, consumed=consumed,
                horizon_ref=horizon_session, bar_bound=derivation_session,
                fill_bound=horizon_session, decisions=decisions,
                horizon_sessions=horizon_sessions, dry_run=True,
                lapse_session=_armed_lapse(
                    _lapse_for(open_draft, derivation_session)))
            if (final_probe is not None
                    and final_probe.reason == "fill"
                    and final_probe.session >= anchor):
                closed = _close(open_draft)
                latches[-1] = replace(
                    closed,
                    reconfirmation_candidate_ids=(
                        *closed.reconfirmation_candidate_ids, fire.candidate_id),
                    reconfirmation_sessions=(
                        *closed.reconfirmation_sessions, fire.action_session_date),
                )
                open_draft = None
                continue

            # THE FULL RESOLUTION CAN ALSO REVERSE THE PROBE TO *STILL LIVE*,
            # and that reversal must take clause (ii) as well (Codex R5).
            # The probe cannot see a decision recorded after the re-fire's own
            # session, so `decline(D3)` + a correcting `place(D5)` makes the
            # probe report the old latch DEAD (declined at D3) while the final
            # resolution -- which sees the place -- says it is STILL LIVE. Taking
            # clause (iii) there would `_close` it as live (`terminal=None`) and
            # then open the incoming fire as a SECOND latch: TWO ARMED MANDATES
            # on one ticker, which the open-latch rule exists to make impossible.
            #
            # INERT FOR EVERY PRE-DECISION CASE, and that is checkable rather
            # than hoped: the probe's bounds are a SUBSET of the final one's, so
            # any invalidation or horizon it finds the final pass finds too --
            # `live_probe is not None` therefore implied `final_probe is not
            # None` before decisions entered the resolver.
            if live_probe is None or final_probe is None:          # clause (ii)
                same_pivot = (
                    round(float(fire.pivot), _PRICE_DP)
                    == round(open_draft.pivot, _PRICE_DP))
                if same_pivot:                                    # branch (a)
                    open_draft.reconfirmation_candidate_ids.append(fire.candidate_id)
                    open_draft.reconfirmation_sessions.append(
                        fire.action_session_date)
                    continue
                # branch (b) -- R6 (RD, 2026-08-06): `declined` OUTRANKS
                # `superseded`. If the operator had already declined this
                # mandate it was not live to be re-based, and stamping
                # `superseded` would overwrite his own recorded decision with a
                # framework inference. The fold must consult the decline HERE
                # because the liveness probe deliberately stops short of the
                # re-fire's own session, so a same-session decline is invisible
                # to it. Resolved by the SAME ranked comparison the resolver
                # uses -- one ladder, not a second hand-written rule.
                declined = _resolve_decline(
                    open_draft, decisions,
                    upper=min(anchor, open_draft.horizon_expiry))
                supersede = _Terminal("superseded", anchor)
                _close(open_draft, forced=min(
                    [t for t in (declined, supersede) if t is not None],
                    key=lambda t: t.order_key))
            else:                                                 # clause (iii)
                # R6 AT THE EXPIRY TIE (RD, 2026-08-07 -- banked from the item-3a
                # gate). `superseded` OUTRANKS `horizon`: a re-fire is an
                # affirmative CURRENT fact, so "re-based" must not file as "went
                # stale" -- at the tie as everywhere.
                #
                # The tie is reachable only here. The horizon stays INCLUSIVE at
                # the re-fire session, so when `horizon_expiry == anchor` BOTH
                # probes find the horizon terminal, clause (ii) is skipped, and
                # branch (b) -- the only place a `superseded` candidate was ever
                # built -- never ran. The rank existed and was never consulted.
                #
                # THE DATE COMPARISON IS WHAT KEEPS THIS INSIDE L10, and it is
                # the same ranked `order_key` the resolver uses rather than a
                # second hand-written rule: the supersede candidate is dated at
                # the RE-FIRE's session, so a terminal that resolved EARLIER
                # (an invalidation two sessions back, a fill) still wins on date
                # and nothing is rewritten. Only a terminal landing on the
                # re-fire's own session can lose to it, and then only on rank.
                #
                # `final_probe` is the comparison basis rather than `live_probe`
                # because it is the resolver's ACTUAL answer for this latch;
                # both are non-None here (clause (ii) absorbed every None), and
                # it is a `dry_run` probe, so consulting it consumes no trade.
                same_pivot = (
                    round(float(fire.pivot), _PRICE_DP)
                    == round(open_draft.pivot, _PRICE_DP))
                supersede = _Terminal("superseded", anchor)
                if not same_pivot and supersede.order_key < final_probe.order_key:
                    _close(open_draft, forced=supersede)
                else:
                    _close(open_draft)
            open_draft = None

        open_draft = _Draft(
            fire=fire, anchor=anchor,
            pivot=float(fire.pivot), stop=float(fire.initial_stop),
            horizon_expiry=session_offset(anchor, horizon_sessions))

    if open_draft is not None:
        _close(open_draft)
    return latches, degraded


def derive_latches(
    *,
    fires,
    bars_by_ticker,
    entries_by_ticker,
    horizon_session: date,
    derivation_session: date,
    horizon_sessions: int = DEFAULT_LATCH_HORIZON_SESSIONS,
    bar_status_by_ticker=None,
    decision_intents_by_candidate_id=None,
    structural_verdicts_by_ticker=None,
    criteria_lapse_armed: bool = False,
    criteria_lapse_sessions: int = DEFAULT_CRITERIA_LAPSE_SESSIONS,
    criteria_lapse_min_widening_adr: float = (
        DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR),
    criteria_lapse_min_widening_pct: float = (
        DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT),
) -> LatchDerivation:
    """Fold every A+ fire into latches. PURE.

    ``structural_verdicts_by_ticker`` (item 3b) is the per-session A+
    STRUCTURAL verdict sequence, loaded by ``reader.py`` the way ``bars`` and
    ``entries`` already arrive. ``None`` or an empty tuple means NO lapse is
    ever resolved -- the feature is inert, never a fabricated clear.

    ``criteria_lapse_armed`` IS A PARAMETER, NOT A ``cfg`` READ: this module is
    PURE (L8) and cannot reach config, so it is threaded
    ``build_latch_derivation -> derive_latches -> _fold_ticker ->
    _resolve_terminal`` exactly as ``horizon_sessions`` already is. **Its
    default is FALSE so a caller that forgets it gets the SAFE state** -- an
    omitted flag can never silently arm a mandate withdrawal.

    The three calibrations are keyword parameters with module-level defaults
    mirroring ``LatchesConfig``, so every EXISTING direct caller and fixture
    stays valid; production passes all four from ``cfg.latches``.

    ``decision_intents_by_candidate_id`` (item 3a) is the operator's
    ``place``/``decline`` ledger keyed by CANDIDATE ID, the way ``bars`` and
    ``entries`` already arrive -- loaded by ``reader.py``, never read from a DB
    in here (L8).

    BOTH HALVES OF THAT NAME ARE LOAD-BEARING. ``decision``, not ``decline``:
    the resolver needs the whole family or a decline the operator CORRECTED by
    re-placing would still withdraw his mandate. ``by_candidate_id``, not
    ``by_ticker``: a ticker carries many historical latches, and a ticker-keyed
    mapping hands an old mandate's decline to a NEWER latch. Each latch selects
    the intents in its OWN candidate family -- the opening fire plus its
    re-confirmations, the identity rule the fill ladder's exact rung already
    uses.

    ``bar_status_by_ticker`` (Arc 21-G) is the per-ticker archive READ status
    in ``ARCHIVE_STATUSES``, carried onto ``LatchDerivation`` alongside the
    per-ticker ``{session -> close}`` map derived from ``bars_by_ticker``.

    **THE FOLD NOW CONSULTS ``bar_status_by_ticker`` (item 3b)** -- it was
    pass-through display context through 21-G, and conjunct 2a's COMPLETENESS
    gate changed that: "price never traded through the pivot" may not be
    ASSERTED from an archive that could not be READ, which is 21-G's own
    asymmetry (an absence caused by our ignorance never licenses an assertion).
    ``archive_closes`` remains pure pass-through. The INVALIDATION walk, the
    eligible set, ``bars_available`` and ``bars_through`` are all still
    bit-for-bit unchanged -- the status is read only by the lapse analysis.

    THE OPEN-LATCH RULE (plan A.2, RD-RULED). Processing a ticker's fires in
    ``(action_session_date, run_ts, candidate_id)`` order, each row is
    dispositioned against that ticker's most recent latch:

    (i)  SAME-SESSION CLAUSE -- unconditional collapse. If the latch's anchor
         equals this row's action session, the row is a RE-CONFIRMATION *even
         if that latch already cleared during that session*. A trading session
         is the atomic unit: it has ONE verdict, so at most one latch per
         ``(ticker, action_session_date)`` can ever be opened.
    (ii) ARMED RE-FIRE -- two branches. If the latch is still LIVE as of this
         row's session:
           (a) SAME frozen pivot  -> RE-CONFIRMATION (no new latch, no
               re-freeze; the count and the session list grow);
           (b) DIFFERENT pivot    -> the old latch CLEARS at this row's session
               and a NEW latch ARMS at the new frozen values. The reason is
               ``superseded`` UNLESS the operator had already recorded a
               governing ``decline`` for that same session or earlier, in which
               case it is ``declined`` (R6: his decision outranks the framework's
               inference about a mandate he had already ended).
    (iii) otherwise the row opens a new latch normally.

    The hazard constraint 1 guards is not re-freezing as such -- it is
    re-freezing SILENTLY. A supersede is loud: the old latch terminates with a
    RECORDED reason, distinguishable from `horizon` forever.
    """
    horizon_sessions = int(horizon_sessions)
    by_ticker: dict[str, list[FireRow]] = {}
    for fire in fires:
        by_ticker.setdefault(fire.ticker, []).append(fire)

    latches: list[Latch] = []
    degraded: list[DegradedFire] = []

    decisions_by_candidate = dict(decision_intents_by_candidate_id or {})
    for ticker in sorted(by_ticker):
        # Flattened per TICKER here; `admissible_decisions` then applies the
        # per-LATCH candidate-family rule inside the fold, so the family
        # predicate is stated once rather than duplicated at the assembly site.
        ticker_decisions = tuple(
            intent
            for fire in by_ticker[ticker]
            for intent in decisions_by_candidate.get(fire.candidate_id, ())
        )
        ticker_latches, ticker_degraded = _fold_ticker(
            by_ticker[ticker],
            bars=list(bars_by_ticker.get(ticker) or ()),
            entries=list(entries_by_ticker.get(ticker) or ()),
            horizon_session=horizon_session,
            derivation_session=derivation_session,
            horizon_sessions=horizon_sessions,
            decisions=ticker_decisions,
            verdicts=tuple(
                (structural_verdicts_by_ticker or {}).get(ticker) or ()),
            # The fold NOW CONSULTS `bar_status_by_ticker` -- 2a's completeness
            # gate refuses to assert "price never traded through the pivot"
            # from an archive that could not be READ. It is no longer
            # pass-through provenance.
            archive_status=(bar_status_by_ticker or {}).get(ticker),
            criteria_lapse_armed=criteria_lapse_armed,
            criteria_lapse_sessions=criteria_lapse_sessions,
            criteria_lapse_min_widening_adr=criteria_lapse_min_widening_adr,
            criteria_lapse_min_widening_pct=criteria_lapse_min_widening_pct,
        )
        latches.extend(ticker_latches)
        degraded.extend(ticker_degraded)

    latches.sort(key=lambda x: (x.identity.ticker, x.anchor, x.identity.candidate_id))
    degraded.sort(key=lambda x: (x.ticker, x.action_session_date, x.candidate_id))
    # The witness map is derived HERE, from the bars the caller already passed,
    # so it cannot drift from the bars the walk saw. It is not consulted above.
    archive_closes = {
        ticker: {b.session: b.close for b in (bars or ())}
        for ticker, bars in (bars_by_ticker or {}).items()
    }
    return LatchDerivation(
        latches=tuple(latches),
        degraded=tuple(degraded),
        derivation_session=derivation_session,
        horizon_session=horizon_session,
        horizon_sessions=horizon_sessions,
        archive_closes=archive_closes,
        archive_status=dict(bar_status_by_ticker or {}),
    )
