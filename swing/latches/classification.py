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

from dataclasses import dataclass, field
from datetime import date

from swing.latches.constants import (
    ACTIONABLE_VIEW_SURFACES,
    LATCH_DISPOSITIONS,
    LATCH_EXECUTION_OUTCOMES,
    LATCH_TELEMETRY_EPOCH_SESSION,
)

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


def resolve_execution_outcome_for(latch, place_intent, intents) -> str:
    """`resolve_execution_outcome` for ONE named place intent.

    The fill rung applies ONLY when `place_intent` IS the latch's LATEST place
    intent -- the FORWARD guard.
    """
    if place_intent is None:
        return "not_applicable"
    latest_place = governing_intent(intents, "place")
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

    place = governing_intent(intents, "place")
    execution_outcome = resolve_execution_outcome_for(latch, place, intents)

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

    # RUNG 1 -- an explicit PLACE. This says he DECIDED to place, and NOTHING
    # more: a rejected order is still an accepted DECISION, and it is
    # `execution_outcome` that says so.
    if place is not None:
        return _out("accepted", "logged a prepared-order placement")
    # RUNG 2 -- an explicit DECLINE (the highest-information datum).
    decline = governing_intent(intents, "decline")
    if decline is not None:
        return _out("declined", decline.decline_reason or "")
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


@dataclass(frozen=True)
class ClassificationCorpus:
    """A convenience bundle for callers assembling many latches. PURE."""

    dispositions: tuple[LatchDisposition, ...] = field(default_factory=tuple)
