"""The three-state disposition classifier (B2) -- PURE.

NO DB, NO network, NO transaction management (the Phase-12 classifier
convention). Every function here is a pure function of its arguments.

THE GOVERNING MEASUREMENT PRINCIPLE (RD, stated once, applied everywhere):

    DO NOT MERGE CATEGORIES THAT DIFFER IN EVIDENCE KIND, EVEN WHEN THEY AGREE
    IN OUTCOME. Merge only what is measured the same way.

Its three ruled instances in this arc:
  * `pre_telemetry` vs `away_unseen` -- both exclude the fire from the discipline
    signal, but "the instrument did not exist" is not "the instrument looked and
    saw nothing".
  * `attested_was_away` vs `away_unseen` -- both mean non-judgment non-action,
    but TESTIMONY IS NOT TELEMETRY.
  * a stale-close MISMATCH vs MATCH -- same input, same price, but one is an
    alarm you MAY raise and the other a claim you may NOT assert.

The practical test: before collapsing two labels because they route to the same
bucket, ask HOW EACH WAS MEASURED. If the answers differ, the labels stay -- and
if they must be summed for a reader, the sum is reported as its own explicitly
named figure rather than by erasing the distinction upstream.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from swing.evaluation.dates import session_offset
from swing.latches.constants import (
    _RULED_DISPOSITIONS,
    ACTIONABLE_VIEW_SURFACES,
    ATTESTED_AWAY_DISPOSITIONS,
    AWAY_RATE_COUNTED_DISPOSITIONS,
    DECISION_DISPOSITIONS,
    LATCH_DISPOSITIONS,
    LATCH_EXECUTION_OUTCOMES,
    LATCH_TELEMETRY_DARK_SESSIONS_THRESHOLD,
    LATCH_TELEMETRY_EPOCH_SESSION,
    PENDING_DISPOSITIONS,
    R_BUCKETS,
    UNATTRIBUTABLE_DISPOSITIONS,
)
from swing.latches.order_intent import compute_order_delta

# The LIVE latch states. A view recorded of a `filled` latch is not evidence
# about a decision window that had already closed, so telemetry records the state
# at view time precisely so this is a READ rather than a re-derivation against a
# world that has since changed.
_LIVE_VIEW_STATES = frozenset({"armed", "order_resting"})

# The sentinel the coverage table returns when the coverage question IS
# answerable and the section E rungs should decide.
_CLASSIFY_NORMALLY = "__classify_normally__"

CoverageKey = tuple[str, bool]   # (coverage, observation_recorded)

# ---------------------------------------------------------------------------
# RD's ruled coverage table, encoded AS A TABLE -- his explicit requirement.
#
# NOT as nested conditionals: nested branches are how a ruled table drifts
# silently under later edits, which is the exact failure this arc has been
# fighting elsewhere (a prose invariant survived three review rounds while the
# DDL contradicted it).
#
# THE TWO ROW SETS, NAMED APART:
#   awareness_view_rows  = view rows on a COUNTED surface inside the COVERED
#                          portion, OF EITHER ACTIONABILITY. "The instrument
#                          observed this latch here." Feeds the COVERAGE axis.
#   actionable_view_rows = the SUBSET with actionable_ever_viewed = 1. "An
#                          actionable mandate was presented." Feeds rungs 6-7.
#                          A STRICT SUBSET, asserted by a test.
#
#   observation_recorded = bool(awareness_view_rows)  -- the table's axis.
#
# The old name `awareness_established` is GONE, and its removal is the point: it
# read as "he became aware", which is TRUE only of an actionable row. Under RD's
# ruling 2 a WITHHELD render establishes NEITHER awareness NOR absence -- it is
# the instrument's silence, not his -- so the axis it feeds is
# INSTRUMENT-PRESENCE, not awareness.
#
# THE TWO AXES ARE SEPARATE, AND CONFLATING THEM MIS-IMPLEMENTS THE RULING. A
# withheld-but-recorded view IS an observation: the instrument existed and it
# observed. Requiring actionability HERE would classify that latch
# `pre_telemetry` -- asserting the apparatus was ABSENT when it was present and
# working, which is the conflation ruling 1 forbids. Actionability decides a
# DIFFERENT question one rung later: given that the instrument observed, was he
# shown a decision (-> discipline_lapse) or not (-> never_actionable).
# Coverage answers "can we know?"; actionability answers "what was he shown?".
# ---------------------------------------------------------------------------
RD_COVERAGE_TABLE: dict[CoverageKey, str] = {
    ("full",    True):  _CLASSIFY_NORMALLY,   # accepted / declined / away / lapse
    ("full",    False): _CLASSIFY_NORMALLY,   # -> away_unseen or never_actionable
    ("partial", True):  _CLASSIFY_NORMALLY,   # instrument OBSERVED - classify on it
    ("partial", False): "pre_telemetry",      # cannot distinguish away from dark
    ("none",    True):  "pre_telemetry",      # unreachable (no covered portion can
                                              # hold a record); present so the
                                              # table is TOTAL over the key space
    ("none",    False): "pre_telemetry",
}

COVERAGE_STATES = frozenset({"full", "partial", "none"})


@dataclass(frozen=True)
class TelemetryHealth:
    """The beacon's reliability over a window. `assess_telemetry_health` builds
    it; `classify_latch` consumes the verdict at rung 5."""

    verdict: str                     # ok | indeterminate | broken
    uninstrumented_sessions: int = 0
    covered_sessions: int = 0
    uncovered_sessions: int = 0

    def __post_init__(self) -> None:
        if self.verdict not in TELEMETRY_VERDICTS:
            raise ValueError(
                f"verdict must be in {sorted(TELEMETRY_VERDICTS)}, "
                f"got {self.verdict!r}")


TELEMETRY_VERDICTS = frozenset({"ok", "indeterminate", "broken"})


@dataclass(frozen=True)
class CoverageVerdict:
    """THE ONLY PLACE COVERAGE IS DECIDED.

    The section E rungs CONSUME this: no rung re-derives the epoch, the uncovered
    window or full-vs-partial, and no rung re-applies a coverage veto after the
    table has routed to `_CLASSIFY_NORMALLY`. A latch the table routes normally is
    classified on awareness and actionability ALONE.
    """

    coverage: str                    # full | partial | none
    observation_recorded: bool
    table_disposition: str           # a DISPOSITION or _CLASSIFY_NORMALLY
    covered_from: date | None
    covered_through: date | None

    @property
    def routed_normally(self) -> bool:
        return self.table_disposition == _CLASSIFY_NORMALLY


@dataclass(frozen=True)
class LatchDisposition:
    """TWO AXES, NOT ONE.

    `disposition` answers *what did the operator DECIDE*. It does NOT answer *did
    the order actually work* -- collapsing them would let a broker-REJECTED
    placement classify as a clean `accepted` and contribute to the agreement rate,
    which is the FTRE failure mode itself (a stop-limit placed above the market
    and rejected), so a ledger built to measure that failure must not be able to
    hide it.
    """

    candidate_id: int
    disposition: str                 # the DECISION axis -- LATCH_DISPOSITIONS
    execution_outcome: str           # the EXECUTION axis
    prompt_required: bool
    is_terminal: bool
    coverage: CoverageVerdict
    awareness_view_row_count: int = 0
    actionable_view_row_count: int = 0
    governing_place_intent_id: int | None = None
    telemetry_verdict: str = "ok"
    r_multiple: float | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if self.disposition not in LATCH_DISPOSITIONS:
            raise ValueError(
                f"disposition must be in {sorted(LATCH_DISPOSITIONS)}, "
                f"got {self.disposition!r}")
        if self.execution_outcome not in LATCH_EXECUTION_OUTCOMES:
            raise ValueError(
                f"execution_outcome must be in {sorted(LATCH_EXECUTION_OUTCOMES)}, "
                f"got {self.execution_outcome!r}")
        if self.prompt_required != (self.disposition in PROMPT_DISPOSITIONS):
            raise ValueError(
                "prompt_required is True on EXACTLY the dispositions in "
                f"PROMPT_DISPOSITIONS ({sorted(PROMPT_DISPOSITIONS)}); got "
                f"disposition={self.disposition!r}, "
                f"prompt_required={self.prompt_required!r}")

    @property
    def effective_disposition(self) -> str:
        return self.disposition


# `prompt_required` is True on EXACTLY ONE disposition.
#
# `never_actionable` is the newest and most important FALSE: prompting a man to
# attest about a decision the panel never presented is the purest form of the
# train-the-dismissal-reflex failure. A prompt on an objectively-resolved cell
# trains dismissal, and dismissal is what eventually kills the honest answer on
# the cell that matters.
PROMPT_DISPOSITIONS = frozenset({"discipline_lapse"})


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------
def _clear_or_horizon(latch) -> date:
    """The last session this latch's decision window could be observed in."""
    return latch.clear_session or latch.horizon_expiry


def _coverage_state(anchor: date, last: date, epoch: date) -> str:
    if anchor >= epoch:
        return "full"
    if last < epoch:
        return "none"
    return "partial"


def _is_awareness_row(row, latch, *, counted_surfaces, covered_from,
                      covered_through) -> bool:
    """THREE CONJUNCTS, each enforced for a different reason (section E.3).

    1. ON A COUNTED SURFACE -- enforced HERE, explicitly. A `surface` column that
       is never READ means the moment 21-F adds a second surface, a non-panel row
       silently satisfies the panel's "viewed" predicate and moves a disposition.
    2. INSIDE THE COVERED PORTION -- a row from the dark period cannot be an
       observation, because there was no instrument to make it.
    3. WHILE LIVE -- the session falls inside the latch's live window AND
       `latch_state_at_first_view` is a LIVE state. A view recorded of a `filled`
       latch is not evidence about a decision window that had already closed.

    ACTIONABILITY IS NOT A CONJUNCT HERE. This is the INSTRUMENT-PRESENCE axis:
    a withheld render proves the beacon fired, and requiring actionability would
    classify that latch `pre_telemetry` -- asserting the apparatus was absent
    when it was present and working.
    """
    if row.surface not in counted_surfaces:
        return False
    session = date.fromisoformat(row.view_session_date)
    if covered_from is None or covered_through is None:
        return False
    if not (covered_from <= session <= covered_through):
        return False
    if not (latch.anchor <= session <= _clear_or_horizon(latch)):
        return False
    return row.latch_state_at_first_view in _LIVE_VIEW_STATES


def resolve_coverage(
    latch, views, *, counted_surfaces=ACTIONABLE_VIEW_SURFACES,
    epoch: date = LATCH_TELEMETRY_EPOCH_SESSION,
) -> CoverageVerdict:
    """RD's ruled table, applied ONCE. See `RD_COVERAGE_TABLE`."""
    last = _clear_or_horizon(latch)
    coverage = _coverage_state(latch.anchor, last, epoch)
    if coverage == "none":
        covered_from = covered_through = None
    else:
        covered_from = max(latch.anchor, epoch)
        covered_through = last
    awareness = [
        r for r in views
        if _is_awareness_row(r, latch, counted_surfaces=counted_surfaces,
                             covered_from=covered_from,
                             covered_through=covered_through)
    ]
    observation_recorded = bool(awareness)
    return CoverageVerdict(
        coverage=coverage, observation_recorded=observation_recorded,
        table_disposition=RD_COVERAGE_TABLE[(coverage, observation_recorded)],
        covered_from=covered_from, covered_through=covered_through)


def awareness_view_rows(
    latch, views, *, counted_surfaces=ACTIONABLE_VIEW_SURFACES,
    epoch: date = LATCH_TELEMETRY_EPOCH_SESSION,
) -> tuple:
    verdict = resolve_coverage(
        latch, views, counted_surfaces=counted_surfaces, epoch=epoch)
    return tuple(
        r for r in views
        if _is_awareness_row(
            r, latch, counted_surfaces=counted_surfaces,
            covered_from=verdict.covered_from,
            covered_through=verdict.covered_through))


def actionable_view_rows(
    latch, views, *, counted_surfaces=ACTIONABLE_VIEW_SURFACES,
    epoch: date = LATCH_TELEMETRY_EPOCH_SESSION,
) -> tuple:
    """The STRICT SUBSET of `awareness_view_rows` with
    `actionable_ever_viewed = 1`.

    `actionable_ever_viewed` is the ONLY actionability column any classification,
    health or bucket rule may read. The `..._at_first_view` / `..._at_last_view`
    pair are AUDIT COMPANIONS to their own timestamps and are never a classifier
    input -- reading either would make the answer to "was the mandate offered this
    session" depend on which reload happened last.
    """
    return tuple(
        r for r in awareness_view_rows(
            latch, views, counted_surfaces=counted_surfaces, epoch=epoch)
        if r.actionable_ever_viewed == 1)


# ---------------------------------------------------------------------------
# ONE ORDERING RULE, STATED ONCE, BEFORE THE RUNGS
#
# `latch_order_intents` is append-only, so a latch can legitimately accumulate
# SEVERAL intents of the same kind -- including two `attest` rows carrying
# DIFFERENT `attested_disposition` values (he attests `was_away`, then corrects
# himself to `chose_not_to_act`; a correction is a NEW row, which is what
# append-only requires).
#
#   Within each intent KIND, the GOVERNING row is the LATEST by
#   (recorded_ts, intent_id).
#
# The tiebreak on `intent_id` is LOAD-BEARING -- `recorded_ts` is whole seconds,
# so two rows can share one -- and it is the same total order the report uses and
# the same one rung 3 of the execution resolver uses for validity children.
# Earlier rows are HISTORY: retained and readable, never silently authoritative.
#
# A CORRECTION MUST WIN, and that is the point of taking the LATEST: if he
# attests `was_away` and then corrects to `chose_not_to_act`, the correction moves
# the fire INTO the discipline signal AGAINST HIMSELF. Taking the earlier row
# would silently preserve the more flattering answer -- the one-sided bias RD
# named, arriving through the ordering door instead of the default door.
# ---------------------------------------------------------------------------
def _order_key(intent) -> tuple:
    return (intent.recorded_ts, intent.intent_id or 0)


def governing_intent(intents, kind: str):
    """The LATEST intent of `kind` by (recorded_ts, intent_id), or None."""
    matching = [i for i in intents if i.intent_kind == kind]
    if not matching:
        return None
    return max(matching, key=_order_key)


def governing_decision(intents):
    """The LATEST row of the `place`/`decline` DECISION FAMILY, or None.

    ONE resolution, used by the classifier, by the validity prompt and by the
    monthly report (Codex exec R7 MAJOR). They are the two MUTUALLY EXCLUSIVE
    answers to one question, so "the current cycle" is whichever he chose LAST --
    and resolving that in the classifier alone left the other two consumers still
    keyed on `governing_intent(intents, "place")`. After
    `place -> rejected validity -> later decline`, the prompt therefore still
    asked about the superseded place while the report neither scored its
    rejection nor listed it as an earlier cycle: real framework-failure evidence
    the ledger was holding and not showing.
    """
    family = [i for i in intents if i.intent_kind in ("place", "decline")]
    if not family:
        return None
    return max(family, key=_order_key)


def admissible_decisions(
    intents, *, candidate_set, lower, upper, upper_exclusive_kinds=(),
) -> tuple:
    """The `place`/`decline` DECISION FAMILY that can be ABOUT one latch. PURE.

    A decision is about a latch when it names that latch's CANDIDATE FAMILY and
    was recorded for a session inside the latch's live window. Both halves are
    load-bearing and each fails in its own direction:

    * **the family** -- a ticker carries many historical latches, so a
      ticker-scoped (or unscoped) resolution hands an OLD mandate's decline to a
      NEWER latch and withdraws a mandate the operator never declined. The set is
      the opening fire PLUS its re-confirmations, the same identity rule the fill
      ladder's exact rung uses.
    * **the window** -- a decision recorded after the mandate ended is not a
      decision about it, and one recorded after an as-of probe's bound has not
      happened yet as of that probe.

    THE FILTER RUNS BEFORE THE WINNER IS CHOSEN, NEVER AFTER, and that order is
    the whole point. `governing_decision` returns the LATEST of the family, so
    resolving first and rejecting the winner afterwards does not fall back to the
    earlier in-bound decision -- it yields nothing. With `decline(D5)` and
    `place(D10)` under a bound of D6, filter-first sees the decline (correct)
    while resolve-first sees the place, drops it, and reports NO decision at all.

    `upper_exclusive_kinds` makes that one boundary strict FOR NAMED KINDS ONLY,
    and it exists for exactly one case: a fill and a DECLINE on the SAME session.
    The lifecycle ranks the fill above the decline ("you cannot decline a filled
    mandate"), and an INCLUSIVE bound cannot deliver that on its own -- the
    decline would still be admissible and rung 1 would return `declined` for a
    FILLED latch. Every other terminal keeps the inclusive bound.

    IT IS KIND-SCOPED BECAUSE A FAMILY-WIDE STRICT BOUND CORRUPTS THE ORDINARY
    CASE. He places on D5 and it fills on D5 -- the commonest execution sequence
    there is. Excluding the whole family on that boundary drops the PLACE THAT
    PRODUCED THE FILL, so the latch classifies with no governing place,
    `execution_outcome` collapses to `not_applicable`, and the execution-parity
    measurement silently loses a real order. Only the DECLINE loses to a
    same-session fill; the place is exactly what the fill corroborates.

    An intent whose `action_session_date` will not parse is SKIPPED: it cannot be
    placed in the window, and a decision that cannot be placed must never
    withdraw a mandate (A6, and the safe direction is keep-alive).
    """
    out = []
    for intent in intents or ():
        if intent.intent_kind not in ("place", "decline"):
            continue
        if intent.candidate_id not in candidate_set:
            continue
        try:
            session = date.fromisoformat(str(intent.action_session_date))
        except (TypeError, ValueError):
            continue
        if session < lower:
            continue
        if session > upper:
            continue
        if session == upper and intent.intent_kind in upper_exclusive_kinds:
            continue
        out.append(intent)
    return tuple(out)


def decision_bounds_for(latch, *, fill_bound: date) -> tuple[date, date]:
    """The `(lower, upper)` window `admissible_decisions` applies to `latch`.

    SINGLE-SOURCED so the panel and the monthly report cannot derive it two ways
    -- the drift class this phase has spent itself closing.

    `upper` is bounded by the latch's ACTUAL TERMINAL, not merely by its nominal
    horizon: with a fill on D4 and a decline on D5, a horizon-bounded classifier
    returns `declined` while the lifecycle returns `fill`, putting a FILLED latch
    into `decision_r` as a decline. This is the classifier READING the
    lifecycle's answer rather than re-deriving it.

    `fill_bound` is the caller's as-of bound; on the production path it is the
    derivation's `horizon_session`, which every caller already holds. The fold's
    pulled-back probe bound applies INSIDE the fold only and never reaches here.
    """
    return (
        latch.anchor,
        min(latch.clear_session or latch.horizon_expiry, fill_bound),
    )


def current_cycle_place(intents):
    """The `place` row that drives the CURRENT execution cycle, or None.

    `None` when the governing decision is a DECLINE: there is no current order
    to validate, and every earlier place is a DISPLACED cycle the report must
    disclose rather than a prompt the panel should still be asking about.
    """
    decision = governing_decision(intents)
    if decision is None or decision.intent_kind != "place":
        return None
    return decision


# ---------------------------------------------------------------------------
# The EXECUTION axis -- ONE canonical resolver with an EXPLICIT precedence
# ---------------------------------------------------------------------------
def resolve_execution_outcome(latch, governing_place, validity_rows) -> str:
    """`not_applicable` | `accepted_by_broker` | its validity outcome | `unknown`.

    Rung 2 above rung 3 is DELIBERATE: A FILL IS AUTHORITATIVE OVER AN
    ATTESTATION. An order that filled was self-evidently accepted, the fill is a
    real position in the trades ledger rather than a recollection, and if the
    operator ever mis-attests `not_submitted` on an order that demonstrably
    filled, the ledger should believe the position.

    But rung 2 is PARENT-SCOPED, NOT LATCH-SCOPED. A latch may carry several
    place/validity cycles -- he places, it is rejected, he re-places -- and a
    latch-scoped fill rung would let the SECOND cycle's fill vouch for the FIRST
    cycle's rejected order, silently rewriting an execution-parity result that had
    been correctly recorded as a failure. So the fill vouches for the LATEST place
    intent ONLY; every earlier place intent resolves from its OWN validity child
    or stays `unknown`. TWO guards, not one: the latest-intent test bounds it
    FORWARD (an earlier cycle cannot borrow a later fill) and the DATE test bounds
    it BACKWARD (an older fill from a prior cycle cannot vouch for a newer intent).

    `latch.clear_reason` is an input the classifier ALREADY receives -- a named
    field on a value object, not a hidden `trades` read.
    """
    if governing_place is None:
        return "not_applicable"
    if (latch.clear_reason == "fill" and latch.clear_session is not None
            and latch.clear_session
            >= date.fromisoformat(governing_place.action_session_date)):
        return "accepted_by_broker"
    children = [
        r for r in validity_rows
        if r.validated_place_intent_id == governing_place.intent_id
    ]
    if children:
        # THE LATEST WITHIN THAT PARENT -- never "the latest validity row for this
        # latch", which would let a second place/validity cycle retroactively
        # rewrite the first one's reported outcome.
        return max(children, key=_order_key).validity_outcome
    return "unknown"


def resolve_execution_outcome_for(
    latch, place_intent, intents, *, place_view=None,
) -> str:
    """`resolve_execution_outcome` for ONE named place intent.

    The fill rung applies ONLY when `place_intent` IS the latch's LATEST place
    intent -- the FORWARD guard.

    `place_view` scopes THAT GUARD ONLY, and it must be the same view
    `place_intent` was selected from or the guard asks a question about a
    different population than the candidate came from. Item 3a's caller selects
    the place from the ADMISSIBLE decisions, so without this a place that is
    latest-in-window but not latest-overall (an out-of-bound later place) would
    fail the guard and lose its own fill's vouching -- reporting `unknown` for an
    order that demonstrably filled.

    `validity_rows` always come from the FULL `intents`: `place_view` carries the
    decision family only, and reading the children out of it would delete every
    validity answer on the latch.
    """
    if place_intent is None:
        return "not_applicable"
    latest_place = governing_intent(
        intents if place_view is None else place_view, "place")
    validity_rows = [i for i in intents if i.intent_kind == "validity"]
    if latest_place is not None and place_intent.intent_id == latest_place.intent_id:
        return resolve_execution_outcome(latch, place_intent, validity_rows)
    children = [
        r for r in validity_rows
        if r.validated_place_intent_id == place_intent.intent_id
    ]
    if children:
        return max(children, key=_order_key).validity_outcome
    return "unknown"


# ---------------------------------------------------------------------------
# The classifier
# ---------------------------------------------------------------------------
def classify_latch(
    *, latch, views=(), intents=(), telemetry_health: TelemetryHealth | None = None,
    counted_surfaces=ACTIONABLE_VIEW_SURFACES,
    epoch: date = LATCH_TELEMETRY_EPOCH_SESSION,
    r_multiple: float | None = None,
    decision_bounds: tuple[date, date] | None = None,
) -> LatchDisposition:
    """The section E precedence ladder. Each rung has its own discriminating test.

    WHY THE RUNG ORDER IS WHAT IT IS. Rungs 1-3 (explicit operator actions) are
    GROUND TRUTH and need no telemetry. Rung 4 (RD's table) decides whether the
    coverage question is answerable AT ALL, and nothing may pre-empt a ruling.
    Rung 5 (health) therefore bears only on a window the table says IS answerable
    -- a broken beacon must not be laundered into `away_unseen`. Rungs 6-7 read
    actionability, a DIFFERENT question from coverage: coverage answers *can we
    know?*, actionability answers *what was he shown?*
    """
    health = telemetry_health or TelemetryHealth(verdict="ok")
    intents = tuple(intents)
    views = tuple(views)
    verdict = resolve_coverage(
        latch, views, counted_surfaces=counted_surfaces, epoch=epoch)
    aware = awareness_view_rows(
        latch, views, counted_surfaces=counted_surfaces, epoch=epoch)
    actionable = tuple(r for r in aware if r.actionable_ever_viewed == 1)
    is_terminal = not latch.is_live

    # TWO VIEWS OF THE LEDGER, NAMED APART. `admissible` is the DECISION FAMILY
    # this latch's window can contain; `intents` stays the FULL set. Only the
    # decision axis is filtered -- replacing `intents` wholesale would make
    # attestations, cancels and validity evidence vanish.
    #
    # `admissible` feeds the `place` resolution as well as the decision rung,
    # because an out-of-bound or cross-latch place would otherwise still become
    # `governing_place_intent_id` and drive the EXECUTION outcome while a
    # different, in-bound decision drove the DISPOSITION -- one latch, two
    # answers, from two different rows.
    #
    # `decision_bounds=None` is the shipped behaviour (no filtering), so every
    # existing caller and fixture is unchanged.
    if decision_bounds is None:
        admissible = intents
    else:
        lower, upper = decision_bounds
        admissible = admissible_decisions(
            intents, candidate_set=latch.candidate_set,
            lower=lower, upper=upper,
            # The one strict boundary, and only a DECLINE on a FILL session:
            # see `admissible_decisions`. A decline dated ON the fill session
            # loses to the fill, so it is not a decision the ledger can still be
            # about -- while the PLACE dated that session is precisely what the
            # fill corroborates and must survive.
            upper_exclusive_kinds=(
                ("decline",) if latch.clear_reason == "fill" else ()))

    place = governing_intent(admissible, "place")
    execution_outcome = resolve_execution_outcome_for(
        latch, place, intents, place_view=admissible)

    def _out(disposition: str, detail: str = "") -> LatchDisposition:
        return LatchDisposition(
            candidate_id=latch.identity.candidate_id,
            disposition=disposition,
            execution_outcome=execution_outcome,
            prompt_required=disposition in PROMPT_DISPOSITIONS,
            is_terminal=is_terminal,
            coverage=verdict,
            awareness_view_row_count=len(aware),
            actionable_view_row_count=len(actionable),
            governing_place_intent_id=None if place is None else place.intent_id,
            telemetry_verdict=health.verdict,
            r_multiple=r_multiple,
            detail=detail)

    # RUNG 1+2 -- THE DECISION FAMILY, RESOLVED BY RECENCY RATHER THAN BY RANK
    # (Codex exec R6 MAJOR). `place` and `decline` are the two MUTUALLY EXCLUSIVE
    # answers to ONE question, selected by the two submit buttons of ONE form --
    # so ranking `place` above `decline` unconditionally meant a later decline
    # CORRECTING an earlier place was recorded and could never govern. That is
    # RD's ruling 3 (the governing answer is his LAST, never his last DISTINCT)
    # arriving at the DISPOSITION axis instead of at the idempotency key, and it
    # failed in the same direction: the ledger kept reporting that he acted on a
    # mandate he had since told it he was declining.
    #
    # Resolved by the SAME total order every other "latest by what?" ruling in
    # this arc uses -- `(recorded_ts, intent_id)`, with the id tiebreak
    # load-bearing because `recorded_ts` is whole seconds.
    #
    # THE ADMISSIBLE VIEW, NOT THE FULL SET (item 3a). Once a decline TERMINATES
    # the mandate, the lifecycle and this rung must agree about which decision
    # governs -- an unbounded resolution here would emit `declined` for a latch
    # the resolver cleared by `fill` or `invalidation`, scoring a filled mandate
    # in `decision_r` as a decline.
    decision = governing_decision(admissible)
    if decision is not None:
        if decision.intent_kind == "place":
            # This says he DECIDED to place, and NOTHING more: a rejected order
            # is still an accepted DECISION, and `execution_outcome` says so.
            return _out("accepted", "logged a prepared-order placement")
        return _out("declined", decision.decline_reason or "")
    # RUNG 3 -- an ATTESTATION. This is the rung where the ordering rule BITES,
    # because the attested dispositions differ from each other in R BUCKET, not
    # just in label.
    attest = governing_intent(intents, "attest")
    if attest is not None:
        return _out(
            f"attested_{attest.attested_disposition}",
            "operator attestation")
    # RUNG 4 -- RD's ruled table. THE ONLY ROUTE TO `pre_telemetry`; no rung below
    # re-decides coverage.
    #
    # THE TABLE IS CONSUMED BEFORE TELEMETRY HEALTH. Running health first would
    # let a partially-covered latch with no view rows and a dark covered portion
    # return `telemetry_unhealthy` instead of RD's ruled `pre_telemetry` -- health
    # PRE-EMPTING the ruling, and falsifying the claim that the table is the only
    # place coverage is decided. Where the table has already ruled the question
    # UNANSWERABLE, a health verdict adds nothing and must not overwrite the
    # reason.
    if not verdict.routed_normally:
        return _out(
            verdict.table_disposition,
            f"coverage={verdict.coverage}; the instrument was not there")
    # RUNG 5 -- telemetry health. `!= "ok"`, NOT `== "broken"`: excluding only
    # `broken` lets a SHORT fully-covered window with NO beacon witness
    # (`indeterminate`) score `away_unseen` and enter the away rate -- while the
    # seeded discriminator requires sibling view rows to prove the beacon was
    # alive before it will call anything away. The classifier must hold itself to
    # the standard its own test does.
    if health.verdict != "ok":
        return _out(
            "telemetry_unhealthy",
            f"telemetry verdict: {health.verdict}")
    # RUNG 6 -- an ACTIONABLE mandate was presented.
    if actionable:
        if latch.is_live:
            # REPORTED, NEVER SCORED: a latch that has not terminated is not an
            # observation yet, and its verdict would MOVE as the window runs.
            return _out("pending_live", "the mandate can still be acted on")
        # THE PESSIMISTIC DEFAULT, and it is load-bearing. `discipline_lapse`
        # IMMEDIATELY -- the instant the latch goes terminal, BEFORE any prompt is
        # rendered and whether or not one ever is. `prompt_required` rides on that
        # disposition: the prompt is shown BECAUSE the cell has already been
        # scored as a lapse, and attesting is the operator's opportunity to
        # CORRECT it. Scoring at terminal makes the default independent of whether
        # he ever comes back -- an intermediate "pending" state would let the lapse
        # sit forever unscored if he never opens the panel again, which is the
        # instrument flattering its subject through inaction.
        return _out(
            "discipline_lapse",
            "an actionable mandate was presented and no action was recorded")
    # RUNG 7 -- NO actionable mandate. Coverage is NOT re-tested here; reaching
    # this rung already means the table routed NORMALLY.
    if verdict.observation_recorded:
        # He looked, and the panel presented NO DECISION. Reachable from a
        # PARTIALLY covered window too: the instrument existed and observed, so
        # the honest answer is "nothing was shown to him", not "the instrument was
        # absent".
        return _out(
            "never_actionable",
            "the panel rendered but its prepared order was withheld throughout")
    # Reachable ONLY from a FULLY covered window: ("partial", False) and
    # ("none", *) were already returned by rung 4 as `pre_telemetry`.
    return _out("away_unseen", "the instrument looked and saw nothing")


# =====================================================================
# Task 5 -- telemetry health (B5), the away rate, and the parity report.
# All PURE.
# =====================================================================


def _live_on(latch, session: date) -> bool:
    return latch.anchor <= session <= _clear_or_horizon(latch)


# The walk's hard bound. ~19 months of sessions -- generous for any real latch
# window, and a corrupt anchor trips it rather than walking the calendar.
_TELEMETRY_WINDOW_MAX_SESSIONS = 400


class TelemetryWindowTooLongError(RuntimeError):
    """The health window could not be enumerated COMPLETELY.

    A dedicated type because the callers must be able to tell "this window is
    unassessable" apart from an arbitrary failure, and because the ONLY safe
    response to either is the same: withhold the verdict. Never degrade to `ok`.
    """


def telemetry_window_sessions(latches, through: date) -> list[date]:
    """The NYSE sessions the health check assesses -- the union of the latches'
    live windows, bounded ABOVE by `through`.

    THE SILENT SESSIONS ARE THE POINT (Codex exec R2 MAJOR 4). Building the
    window from the sessions that already HAVE a view row supplies only sessions
    the beacon spoke on, so `assess_telemetry_health` could never SEE a dark
    session and `uncovered` would stay near zero: a mostly-dark month with one
    beacon hit would verdict `ok` and hand `away_unseen` to the away rate --
    manufacturing away-rate evidence out of an instrument that was dark. The
    window must therefore be ENUMERATED, not collected.

    Bounded BELOW by the earliest anchor rather than by the epoch: the epoch
    exclusion belongs to `assess_telemetry_health`, which counts those sessions
    as UNINSTRUMENTED rather than uncovered. Doing it here instead would hide
    the uninstrumented count, and that count is the honest part of the answer.

    SHARED BY THE PANEL AND THE CLI so the two surfaces cannot answer the same
    question differently.
    """
    starts = [latch.anchor for latch in latches]
    if not starts:
        return []
    start = min(starts)
    if start > through:
        return []
    sessions: list[date] = []
    cursor = through
    # A hard bound so a corrupt anchor cannot walk the calendar forever -- but
    # HITTING IT IS AN ERROR, NOT A TRUNCATION (Codex exec R5). Silently
    # returning the first 400 sessions recreates the very defect this function
    # was written to fix: an old post-epoch latch lying wholly OUTSIDE the
    # truncated window is then never assessed on any session it was live for,
    # so health returns `ok` off 0/0 coverage and the classifier scores its
    # missing views as `away_unseen` -- a fabricated away-fire out of a window
    # nobody looked at. An incomplete window must WITHHOLD, which is what every
    # caller's degrade path does with this.
    for _ in range(_TELEMETRY_WINDOW_MAX_SESSIONS):
        if cursor < start:
            return sessions
        sessions.append(cursor)
        cursor = session_offset(cursor, -1)
    raise TelemetryWindowTooLongError(
        f"the telemetry window from {start} through {through} exceeds "
        f"{_TELEMETRY_WINDOW_MAX_SESSIONS} sessions; it cannot be assessed "
        "completely, so no verdict may be asserted over it")


def assess_telemetry_health(
    *, sessions, latches, views,
    counted_surfaces=ACTIONABLE_VIEW_SURFACES,
    epoch: date = LATCH_TELEMETRY_EPOCH_SESSION,
    dark_threshold: int = LATCH_TELEMETRY_DARK_SESSIONS_THRESHOLD,
) -> TelemetryHealth:
    """THE AWAY RATE MUST NOT BE CONSUMED WITHOUT THIS CHECK (B5).

    A silently broken beacon makes EVERY fire look like an away-fire -- inflating
    the exact number that would justify stage-3 auto-place. The failure mode is
    not a wrong statistic; it is a wrong statistic POINTED AT THE BIGGEST PENDING
    DECISION.

    THE TWO FILTERS ARE DELIBERATELY DIFFERENT and the difference is not an
    oversight:
      * SURFACE filters BOTH counters -- the check is asking whether *the beacon
        we measure from* fired, so a row on an uncounted surface tells us nothing
        about it.
      * `actionable` filters NEITHER -- a row of EITHER value proves the beacon
        fired, which is the only question this check asks.

    HONEST ABOUT WHAT IT CANNOT DO: this check cannot distinguish "beacon broken"
    from "operator away for the whole window", and it does not claim to. It
    identifies the SHAPE and REFUSES THE NUMBER. The stronger check (an
    independent witness that the panel was rendered) is investigated and rejected
    for V1: `POST /latches/orders` does write a `schwab_api_calls` row on every
    panel render, but it is stamped `surface="trade_entry"`, which the trade-entry
    auto-fill also writes -- so it cannot attribute a render to the panel. Banked
    as V2: a dedicated audit surface value would make this check two-sided.
    RECORDING THE LIMITATION IS THE REQUIREMENT; over-claiming would be the
    failure.
    """
    sessions = sorted(set(sessions))
    latches = tuple(latches)
    counted_sessions = {
        date.fromisoformat(r.view_session_date)
        for r in views if r.surface in counted_surfaces
    }
    uninstrumented = 0
    covered = 0
    uncovered = 0
    for session in sessions:
        if session < epoch:
            # NOT "uncovered" -- UNINSTRUMENTED. Excluded from BOTH counts below.
            uninstrumented += 1
            continue
        if not any(_live_on(latch, session) for latch in latches):
            continue
        if session in counted_sessions:
            covered += 1
        else:
            uncovered += 1
    # THE DARK COUNT BINDS REGARDLESS OF `covered`. Keying `broken` on
    # `covered == 0` would let a 30-session window with ONE sibling view and 29
    # dark sessions verdict `ok` and hand `away_unseen` to the away rate --
    # manufacturing away-rate evidence out of an instrument that was dark for 97%
    # of the window. One beacon hit proves the beacon existed ONCE; it does not
    # make the window OBSERVED.
    if uncovered >= dark_threshold:
        verdict = "broken"
    elif covered == 0 and uncovered > 0:
        verdict = "indeterminate"
    else:
        verdict = "ok"
    return TelemetryHealth(
        verdict=verdict, uninstrumented_sessions=uninstrumented,
        covered_sessions=covered, uncovered_sessions=uncovered)


# ---------------------------------------------------------------------
# THE THREE (well, five) R BUCKETS -- a PARTITION over CELLS, computed by ONE
# function with NO DEFAULT.
# ---------------------------------------------------------------------
def r_bucket_for(disposition: str, *, is_terminal: bool) -> str:
    """EXACTLY ONE bucket, and NO DEFAULT.

    `is_terminal` IS REQUIRED AND IT GATES EVERYTHING. RD's ruling is "rates
    compute over TERMINAL, classifiable observations only", and a
    disposition-ONLY function CANNOT enforce that: `pending_live` is reached only
    for a LIVE latch that HAS actionable views and NO intent, so a live latch with
    a `place` intent would score `accepted` -> decision_r, a live latch with no
    views would score `away_unseen` -> away_r, and a live latch with withheld-only
    views would score `never_actionable`. All three are NON-TERMINAL observations
    entering SCORED buckets -- the exact corruption the ruling forbids, and it
    slipped in because the ruling was encoded as a DISPOSITION rather than as a
    GATE. TERMINALITY GATES THE BUCKET; the disposition only NAMES WHAT WAS SEEN.

    MEMBERSHIP FIRST -- THE TERMINALITY GATE IS A DEFAULT IN DISGUISE UNLESS IT
    IS. Running the gate BEFORE the membership ladder lets an unlisted disposition
    with `is_terminal=False` return `pending_r` and be silently absorbed -- the
    very thing the trailing `return "decision_r"` was deleted for, RELOCATED
    rather than removed.

    THE CHECK IS AGAINST THE RULED UNION, **NOT** AGAINST `LATCH_DISPOSITIONS`.
    Membership in the enum only says the CLASSIFIER can emit it; it says nothing
    about anyone having RULED its bucket, and a disposition added to the enum
    without a ruling is the exact case this guard exists for. Checking the enum
    would let that one straight through the gate into `pending_r`.

    RD singled this guard out as worth more than either ruling it produced,
    because the next unlisted disposition will be one nobody has thought of.
    DO NOT REINTRODUCE A DEFAULT.
    """
    if disposition not in _RULED_DISPOSITIONS:
        raise ValueError(
            f"{disposition!r} has no ruled R bucket; it must be added to one of "
            "the five bucket sets in swing/latches/constants.py -- a deliberate "
            "act with a reviewer")
    # COHERENCE SECOND. `pending_live` MEANS "the latch is LIVE", so
    # (pending_live, is_terminal=True) is not a state the classifier can
    # legitimately produce -- and silently bucketing it as pending would HIDE a
    # classifier bug in the very report layer built to stop silent absorption.
    if disposition in PENDING_DISPOSITIONS and is_terminal:
        raise ValueError(
            "incoherent cell: pending_live with is_terminal=True")
    # THE RULING, ENFORCED AS A GATE. Reached only for a KNOWN disposition, so it
    # can no longer absorb an unruled one.
    if not is_terminal:
        return "pending_r"
    if disposition in AWAY_RATE_COUNTED_DISPOSITIONS:   # telemetry-derived
        return "away_r"
    if disposition in ATTESTED_AWAY_DISPOSITIONS:       # testimony, not telemetry
        return "attested_away_r"
    if disposition in UNATTRIBUTABLE_DISPOSITIONS:      # the REMAINDER of the
        return "unattributable_r"                       # excluded set
    if disposition in DECISION_DISPOSITIONS:
        return "decision_r"
    # UNREACHABLE while _RULED_DISPOSITIONS is the union of the five sets -- kept
    # because a defence that depends on ANOTHER defence still holding is not a
    # defence.
    raise ValueError(
        f"{disposition!r} has no ruled R bucket; see the five bucket sets")


# The three EVIDENCE KINDS inside `decision_r`. The bucket sums three DIFFERENT
# kinds of evidence -- directly logged decisions, self-attestation, and a
# telemetry-INFERRED lapse -- and the governing principle forbids merging
# categories that differ in evidence kind. The distinction IS preserved upstream
# (three distinct dispositions), so the remedy is at the REPORT: the sum may be
# reported, the distinction may not be erased.
DECISION_SUBKIND: dict[str, str] = {
    "accepted": "logged",
    "declined": "logged",
    "attested_acted_manually": "attested",
    "attested_chose_not_to_act": "attested",
    "discipline_lapse": "inferred",
}


@dataclass(frozen=True)
class AwayRateResult:
    """TWO RATES OVER ONE DENOMINATOR (RD ruling 2).

    The SAME denominator is what makes them comparable and what makes the second
    an UPPER BOUND on the first rather than a different statistic.

    THE AWAY RATE CANNOT BE OBTAINED WITHOUT ITS VERDICT: `health` is a REQUIRED
    constructor argument, so a caller cannot get either number without the verdict
    travelling with it. There is no function anywhere that returns a bare float
    away rate.
    """

    health: TelemetryHealth
    away_unseen_fires: int
    attested_was_away_fires: int
    # THE DENOMINATOR: TERMINAL, CLASSIFIABLE observations only (RD ruling 1).
    # Excludes pending_live (not an observation yet), and excludes pre_telemetry /
    # never_actionable / telemetry_unhealthy (unattributable).
    classifiable_fires: int
    pending_fires: int             # REPORTED, never scored -- so the reader sees
                                   # the PIPELINE rather than a silently smaller
                                   # corpus
    excluded_fires: int
    objective_rate: float | None = None   # away_unseen / classifiable -- PRIMARY
    attested_rate: float | None = None    # + attested_was_away -- the UPPER BOUND
    withheld_reason: str | None = None

    @property
    def unmeasured_kind(self) -> str | None:
        """`withheld` | `not_yet_measurable` | `None`.

        RD RULING 4 (2026-07-30): the ZERO-DATA state must be DISTINGUISHABLE
        from the GOOD state and must be LABELLED as unmeasured. It must also be
        distinguishable from the OTHER unmeasured state: an unreliable beacon
        and an empty corpus are different facts with different responses (fix
        the instrument vs wait for a fire), and printing one label for both
        hides a broken beacon behind a quiet start-up state.

        `None` means a rate is actually available.
        """
        if self.objective_rate is not None:
            return None
        if self.health.verdict != "ok":
            return "withheld"
        return "not_yet_measurable"


def compute_away_rate(
    *, bucket_counts: dict[str, int], health: TelemetryHealth,
) -> AwayRateResult:
    """Both rates, or BOTH `None` with a labelled reason.

    The gate applies to the PAIR: an unreliable beacon corrupts the objective
    numerator DIRECTLY and the bound derived from it CONSEQUENTLY.

    STAGE-3 AUTO-PLACE READS THE OBJECTIVE RATE AS PRIMARY, WITH THE ATTESTED RATE
    AS AN EXPLICIT UPPER BOUND. The report labels them that way, so the decision
    that would automate the operator's entries cannot quietly be taken on the
    LARGER number.

    THE BIAS GUARD IS DELIBERATELY ONE-SIDED AND A SYMMETRIC ONE MUST NOT BE
    ADDED: attesting "I saw it and chose not to act" when actually away is
    self-flagellating, unlikely, and CONSERVATIVE if it happens -- it moves a fire
    INTO the discipline signal against himself. Only the flattering direction
    needed a guard.
    """
    away = bucket_counts.get("away_r", 0)
    attested_away = bucket_counts.get("attested_away_r", 0)
    decision = bucket_counts.get("decision_r", 0)
    classifiable = decision + away + attested_away
    pending = bucket_counts.get("pending_r", 0)
    excluded = bucket_counts.get("unattributable_r", 0)
    if health.verdict != "ok":
        # `!= "ok"`, NOT `== "broken"` (Codex exec R4 MAJOR 5). The CLASSIFIER's
        # rung 5 already withholds on EVERY non-ok verdict, and this gate must
        # hold itself to the same standard or the two disagree in the flattering
        # direction: under `indeterminate`, explicit decisions enter at rungs
        # 1-3 and BYPASS rung 5 entirely, while every unobserved latch is routed
        # to `telemetry_unhealthy` and LEAVES the denominator -- so the report
        # would publish a confident `0.0%` computed over nothing but the fires
        # he explicitly logged. That is not a low away rate; it is the away rate
        # measured only where he was demonstrably present, which is the one
        # subset guaranteed to flatter him.
        return AwayRateResult(
            health=health, away_unseen_fires=away,
            attested_was_away_fires=attested_away,
            classifiable_fires=classifiable, pending_fires=pending,
            excluded_fires=excluded, objective_rate=None, attested_rate=None,
            withheld_reason=(
                f"telemetry verdict is {health.verdict.upper()} "
                f"(covered={health.covered_sessions}, "
                f"uncovered={health.uncovered_sessions}, "
                f"uninstrumented={health.uninstrumented_sessions}); "
                "an unreliable beacon makes every fire look like an away-fire, "
                "which would inflate the exact number that would justify "
                "stage-3 auto-place; only an OK verdict may be scored"))
    if classifiable == 0:
        return AwayRateResult(
            health=health, away_unseen_fires=away,
            attested_was_away_fires=attested_away,
            classifiable_fires=0, pending_fires=pending,
            excluded_fires=excluded, objective_rate=None, attested_rate=None,
            withheld_reason=(
                "no TERMINAL, CLASSIFIABLE observation exists yet -- the "
                "instrument's first fully-classifiable observation is the next "
                "A+ fire on or after the telemetry epoch"))
    return AwayRateResult(
        health=health, away_unseen_fires=away,
        attested_was_away_fires=attested_away,
        classifiable_fires=classifiable, pending_fires=pending,
        excluded_fires=excluded,
        objective_rate=away / classifiable,
        attested_rate=(away + attested_away) / classifiable,
        withheld_reason=None)


# ---------------------------------------------------------------------
# The parity report
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class ParityObservation:
    """ONE latch's contribution to the monthly read.

    `framework` / `actual` are the two ORDER SIDES the delta is computed from --
    the framework block off the governing `place` row and the observed block off
    its governing `validity` child. Either may be `None`.
    """

    disposition: LatchDisposition
    framework: dict | None = None
    actual: dict | None = None
    r_multiple: float | None = None

    @property
    def candidate_id(self) -> int:
        return self.disposition.candidate_id


@dataclass(frozen=True)
class ExecutionParityReport:
    """What RD reads at the monthly cadence.

    Every bucket in `R_BUCKETS` is carried, built BY ITERATING that frozenset
    rather than by listing them -- so a sixth bucket added to the resolver cannot
    be added and silently omitted from the report.
    """

    bucket_counts: dict[str, int]
    bucket_r: dict[str, float]
    # HOW MANY observations in each bucket actually CARRIED an R (Codex exec R4
    # MAJOR 3). Without it `bucket_r` cannot distinguish "the R summed to zero"
    # from "no R was ever attributed", and a renderer has no way to tell a
    # measurement from its own absence.
    bucket_r_attributed: dict[str, int]
    disposition_counts: dict[str, int]
    away: AwayRateResult
    # `decision_r`'s three EVIDENCE-KIND sub-counts. Computed AFTER bucketing:
    # only rows whose BUCKET is `decision_r` may enter one. Counting by
    # disposition NAME instead would let a LIVE `accepted` into
    # `decision_r_logged` while its R correctly sat in `pending_r`, so the
    # sub-counts would stop summing to the total.
    decision_r_logged: int
    decision_r_attested: int
    decision_r_inferred: int
    agreement_numerator: int
    agreement_denominator: int
    validity_unknown: int
    validity_failed: int
    actual_side_unknown: int
    delta_totals: dict[str, int]
    total_observations: int
    duplicate_latch_observations: int = 0

    @property
    def agreement_rate(self) -> float | None:
        if self.agreement_denominator == 0:
            return None
        return self.agreement_numerator / self.agreement_denominator


def compute_execution_parity(
    observations, *, health: TelemetryHealth,
) -> ExecutionParityReport:
    """The monthly read, over DISTINCT LATCH IDENTITIES.

    RD CARRY 1 (2026-07-29) -- THE LEDGER'S UNIT IS THE LATCH (THE OPPORTUNITY),
    NOT THE FIRE. RD traced the property and found it correct today by
    construction (classification is per-latch, the intent table is per-decision
    and append-only, and 21-A collapses same-action-session duplicate fires
    upstream) -- but nothing PINNED it, and *"correct by construction with no pin
    is exactly how a ruling silently regresses, which is the entire reason I made
    it a ruling rather than an observation."*

    So the corpus is DEDUPED ON DISTINCT LATCH IDENTITY (`candidate_id`, the
    immutable bridge key) BEFORE bucketing. If anything ever feeds MULTIPLE fire
    rows per latch into this function, the denominators DO NOT INFLATE: three rows
    for one opportunity would TRIPLE-COUNT that opportunity and inflate EVERY
    denominator -- including the away rate, the number that will justify or kill
    stage-3 auto-place.

    The reduction is LABELLED, not silent: `duplicate_latch_observations` carries
    the count, because an unlabelled reduction is a quiet all-clear by omission.
    The FIRST observation per latch in input order is kept.
    """
    seen: dict[int, ParityObservation] = {}
    duplicates = 0
    for obs in observations:
        if obs.candidate_id in seen:
            duplicates += 1
            continue
        seen[obs.candidate_id] = obs
    unique = tuple(seen.values())

    bucket_counts = dict.fromkeys(sorted(R_BUCKETS), 0)
    bucket_r = dict.fromkeys(sorted(R_BUCKETS), 0.0)
    bucket_r_attributed = dict.fromkeys(sorted(R_BUCKETS), 0)
    disposition_counts: dict[str, int] = {}
    sub = {"logged": 0, "attested": 0, "inferred": 0}
    numerator = denominator = 0
    validity_unknown = validity_failed = actual_side_unknown = 0
    delta_totals = {
        "order_type_differs": 0, "duration_differs": 0,
        "stop_price_differs": 0, "limit_price_differs": 0,
        "quantity_differs": 0, "unknown": 0,
    }
    for obs in unique:
        d = obs.disposition
        bucket = r_bucket_for(d.disposition, is_terminal=d.is_terminal)
        bucket_counts[bucket] += 1
        if obs.r_multiple is not None:
            bucket_r[bucket] = round(bucket_r[bucket] + obs.r_multiple, 6)
            bucket_r_attributed[bucket] += 1
        disposition_counts[d.disposition] = (
            disposition_counts.get(d.disposition, 0) + 1)
        # THE SUB-COUNTS ARE REFINEMENTS OF *TERMINAL* `decision_r`, computed
        # AFTER bucketing -- only rows whose BUCKET is decision_r may enter one.
        if bucket == "decision_r":
            sub[DECISION_SUBKIND[d.disposition]] += 1
        if d.disposition != "accepted":
            continue
        # THE AGREEMENT RATE. A place intent the broker REJECTED is a FINDING, not
        # an agreement and not a disagreement -- the framework and the operator
        # may have agreed perfectly on an order the market would not accept, which
        # is precisely the FTRE class. Folding it into either the numerator or the
        # denominator would HIDE it.
        if d.execution_outcome == "unknown":
            validity_unknown += 1
            continue
        if d.execution_outcome in ("rejected_by_broker", "not_submitted"):
            validity_failed += 1
            continue
        if d.execution_outcome != "accepted_by_broker":
            continue
        if obs.actual is None:
            actual_side_unknown += 1
            continue
        delta = compute_order_delta(obs.framework, obs.actual)
        if delta.any_difference is None:
            actual_side_unknown += 1
            delta_totals["unknown"] += 1
            continue
        denominator += 1
        if delta.any_difference is False:
            numerator += 1
        else:
            if delta.order_type_differs:
                delta_totals["order_type_differs"] += 1
            if delta.duration_differs:
                delta_totals["duration_differs"] += 1
            # `one_sided` COUNTS HERE TOO (RD ruling, 2026-07-30). It fails the
            # numerator, so the per-field table must NAME the field that failed
            # it -- otherwise the reader sees a failed agreement with every
            # attributed cause reading zero.
            if delta.stop_leg == "one_sided" or (
                    delta.stop_leg == "compared" and delta.stop_price_delta):
                delta_totals["stop_price_differs"] += 1
            if delta.limit_price_delta:
                delta_totals["limit_price_differs"] += 1
            if delta.quantity_delta:
                delta_totals["quantity_differs"] += 1
    away = compute_away_rate(bucket_counts=bucket_counts, health=health)
    return ExecutionParityReport(
        bucket_counts=bucket_counts, bucket_r=bucket_r,
        bucket_r_attributed=bucket_r_attributed,
        disposition_counts=disposition_counts, away=away,
        decision_r_logged=sub["logged"], decision_r_attested=sub["attested"],
        decision_r_inferred=sub["inferred"],
        agreement_numerator=numerator, agreement_denominator=denominator,
        validity_unknown=validity_unknown, validity_failed=validity_failed,
        actual_side_unknown=actual_side_unknown, delta_totals=delta_totals,
        total_observations=len(unique),
        duplicate_latch_observations=duplicates)
