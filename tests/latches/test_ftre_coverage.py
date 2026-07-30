"""THE FTRE COVERAGE TRIPLE - the vacuity detector, away, and the lapse.

Arc 21-B Task 4. RD RULED 2026-07-28; the gate is CLOSED and no task is blocked.

WHY THIS FILE EXISTS AT ALL. The commissioning brief's binding acceptance test
was: *FTRE fired 07-20 during the operator's vacation -> the panel shows
viewed=NO across the armed window -> it classifies AWAY, is EXCLUDED from the
discipline signal, and its +1.22R lands in the away bucket.* CHARC then found it
VACUOUS and owned it, and RD confirmed and owned his half.

VERIFIED ON THE LIVE DB + FILESYSTEM, 2026-07-28:
  * `latch_view_events` holds ZERO rows (SELECT COUNT(*) on ~/swing-data/swing.db)
  * the table was created THAT DAY (pre-migration backup
    swing-20260728T111453.db; 0032 ran 2026-07-28 11:14:53)
  * so the earliest `view_session_date` the beacon could EVER write is 2026-07-29
    -- `action_session_for_run(datetime(2026,7,28,11,14,53))`
  * FTRE armed 2026-07-20 (candidates.id=11261, eval run 121, pivot 18.34 /
    stop 14.88), horizon 2026-08-31
  * FTRE's armed window is therefore PARTIALLY instrumented

So "viewed=NO across the armed window" is true of FTRE and EQUALLY TRUE OF EVERY
LATCH THAT HAS EVER EXISTED, for a reason having NOTHING to do with the operator's
behaviour: the instrument did not exist. A naive scheme mapping *no view rows ->
AWAY* passes that test IDENTICALLY whether he spent the week on a beach or staring
at the panel. It is not a discriminator. Worse, it is UNSTABLE IN THE FLATTERING
DIRECTION: FTRE stays armed until 2026-08-31, so one panel open on any session
from 2026-07-29 onward would flip it out of AWAY -- re-classifying a week he
genuinely spent away on the strength of behaviour AFTER that week.

RD's three rulings resolve it, and this file is where they are pinned.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from swing.latches.classification import (
    ParityObservation,
    TelemetryHealth,
    assess_telemetry_health,
    classify_latch,
    compute_execution_parity,
    r_bucket_for,
)
from swing.latches.constants import (
    LATCH_TELEMETRY_DARK_SESSIONS_THRESHOLD,
    LATCH_TELEMETRY_EPOCH_SESSION,
)
from swing.latches.identity import LatchIdentity
from swing.latches.models import Latch

EPOCH = LATCH_TELEMETRY_EPOCH_SESSION            # date(2026, 7, 29)
THRESHOLD = LATCH_TELEMETRY_DARK_SESSIONS_THRESHOLD

# THE REAL FTRE NUMBERS, from the live DB.
FTRE_CANDIDATE_ID = 11261
FTRE_EVAL_RUN = 121
FTRE_ANCHOR = date(2026, 7, 20)
FTRE_HORIZON = date(2026, 8, 31)
FTRE_PIVOT = 18.34
FTRE_STOP = 14.88
FTRE_R = 1.22                                    # the outcome under measurement


def _ftre(*, state: str = "armed", clear_reason: str | None = None,
          clear_session: date | None = None) -> Latch:
    return Latch(
        identity=LatchIdentity(
            candidate_id=FTRE_CANDIDATE_ID, evaluation_run_id=FTRE_EVAL_RUN,
            ticker="FTRE", detection_date=FTRE_ANCHOR.isoformat(),
            pipeline_run_id=None),
        latched_pivot=FTRE_PIVOT, latched_initial_stop=FTRE_STOP,
        zone_cap=round(FTRE_PIVOT * 1.03, 4), anchor=FTRE_ANCHOR,
        horizon_expiry=FTRE_HORIZON, sessions_elapsed=6, sessions_to_horizon=24,
        state=state, clear_reason=clear_reason, clear_session=clear_session)


def _seeded(*, anchor: date, last: date, candidate_id: int,
            ticker: str = "SEED") -> Latch:
    return Latch(
        identity=LatchIdentity(
            candidate_id=candidate_id, evaluation_run_id=130, ticker=ticker,
            detection_date=anchor.isoformat(), pipeline_run_id=None),
        latched_pivot=20.0, latched_initial_stop=17.0, zone_cap=20.6,
        anchor=anchor, horizon_expiry=last, sessions_elapsed=8,
        sessions_to_horizon=0, state="horizon_expired", clear_reason="horizon",
        clear_session=last)


class _View:
    """A view row stand-in carrying exactly the fields the classifier reads."""

    def __init__(self, session: date, *, candidate_id: int, actionable: int = 1,
                 surface: str = "latch_panel", state: str = "armed") -> None:
        self.view_session_date = session.isoformat()
        self.candidate_id = candidate_id
        self.surface = surface
        self.actionable_ever_viewed = actionable
        self.actionable_at_first_view = actionable
        self.actionable_at_last_view = actionable
        self.latch_state_at_first_view = state
        self.latch_state_at_last_view = state


# ==========================================================================
# T-A -- THE REAL-DATA ANCHOR, CORRECTED (RD ruling 3)
# ==========================================================================
def test_T_A_ftre_with_zero_view_rows_classifies_pre_telemetry_not_away():
    """RULING 1: `pre_telemetry` IS A DISTINCT CLASSIFICATION, NOT A FLAVOUR OF
    AWAY.

    RD, verbatim: *"AWAY means the instrument looked and saw nothing.
    PRE_TELEMETRY means the instrument did not exist. Those are different facts,
    and collapsing them lets an ABSENCE OF APPARATUS masquerade as an OBSERVATION
    ABOUT THE OPERATOR."*

    A NAIVE "no rows -> away" IMPLEMENTATION FAILS THIS TEST. It is no longer
    carrying the discriminating load -- T-B/T-C do that -- but it is the anchor to
    REAL DATA that RD required be KEPT rather than deleted: *"Do not lose the
    real-data anchor; correct what it asserts."*
    """
    latch = _ftre()
    got = classify_latch(latch=latch, views=[], epoch=EPOCH)
    assert got.disposition == "pre_telemetry"
    assert got.coverage.coverage == "partial", (
        "FTRE's armed window straddles the epoch: 07-20..07-28 can NEVER carry "
        "telemetry, 07-29..08-31 can")
    assert got.coverage.observation_recorded is False
    assert got.prompt_required is False


def test_T_A_ftres_plus_1_22R_is_NOT_scored_against_the_operators_judgment():
    """RULING 3, and the BUCKET is the part that changes.

    The away bucket is not merely "excluded" -- it is the NUMERATOR OF THE AWAY
    RATE, which RD named as *the quantified business case that will justify or kill
    stage-3 auto-place*. Putting an unclassifiable fire in it INFLATES THE EXACT
    NUMBER THAT ARGUES FOR AUTOMATING THE OPERATOR'S ENTRIES -- which is the
    corruption B5's telemetry-health gate exists to prevent, so following the
    brief's test literally would make this arc commit, in its very first
    observation, the bias its own B5 forbids.

    So `unattributable_r` is a THIRD bucket alongside `away_r` and `decision_r`,
    and FTRE's +1.22R lands there.
    """
    latch = _ftre(state="filled", clear_reason="fill",
                  clear_session=date(2026, 7, 24))
    got = classify_latch(latch=latch, views=[], epoch=EPOCH)
    assert got.disposition == "pre_telemetry"
    bucket = r_bucket_for(got.disposition, is_terminal=got.is_terminal)
    assert bucket == "unattributable_r"
    assert bucket != "away_r", "it must NOT inflate the away rate"
    assert bucket != "decision_r", "it must NOT be scored against his judgment"
    rep = compute_execution_parity(
        [ParityObservation(disposition=got, r_multiple=FTRE_R)],
        health=TelemetryHealth(verdict="ok", covered_sessions=3))
    assert rep.bucket_r["unattributable_r"] == FTRE_R
    assert rep.bucket_r["away_r"] == 0.0
    assert rep.bucket_r["decision_r"] == 0.0
    assert rep.away.classifiable_fires == 0
    assert rep.away.excluded_fires == 1


def test_T_A_the_live_consequence_every_pre_epoch_fire_is_pre_telemetry():
    """THE LIVE CONSEQUENCE, stated so nobody is surprised at the GUI witness: on
    today's substrate EVERY live latch is `pre_telemetry`. FTRE anchored 07-20 and
    VSTS anchored 07-27 both predate the 2026-07-29 epoch (RD: *"VSTS re-fired
    07-27, also pre-telemetry by a day"*). The instrument's first
    fully-classifiable observation is THE NEXT A+ FIRE ON OR AFTER 2026-07-29 --
    which is the honest answer to 'when does this start measuring', and it is ONE
    FIRE AWAY."""
    vsts = Latch(
        identity=LatchIdentity(
            candidate_id=11999, evaluation_run_id=122, ticker="VSTS",
            detection_date="2026-07-27", pipeline_run_id=None),
        latched_pivot=16.90, latched_initial_stop=14.20, zone_cap=17.407,
        anchor=date(2026, 7, 27), horizon_expiry=date(2026, 9, 8),
        sessions_elapsed=1, sessions_to_horizon=29, state="armed")
    for latch in (_ftre(), vsts):
        assert classify_latch(
            latch=latch, views=[], epoch=EPOCH).disposition == "pre_telemetry"


# ==========================================================================
# T-A2 -- THE STABILITY PROPERTY (ruling 2's defining consequence)
# ==========================================================================
@pytest.mark.parametrize("actionable,expect", [
    (1, "discipline_lapse"),
    (0, "never_actionable"),
])
def test_T_A2_a_view_row_moves_FTRE_off_pre_telemetry_but_NEVER_to_away(
        actionable, expect):
    """THE TEST THAT PINS "the classification can only move toward a POSITIVE
    fact".

    An implementation that re-evaluates coverage as "now we have some rows, so
    treat the window as covered" flips FTRE to `away_unseen` and FAILS. That is
    the instability the vacuity finding raised: FTRE must not be able to flip to
    away NEXT WEEK because of something that happens AFTER the window it
    describes.

    Only an `awareness_view_row` INSIDE THE COVERED PORTION can move it, and that
    record establishes awareness rather than absence -- so the destination is
    always an awareness-established cell.
    """
    latch = _ftre(state="horizon_expired", clear_reason="horizon",
                  clear_session=FTRE_HORIZON)
    views = [_View(date(2026, 8, 5), candidate_id=FTRE_CANDIDATE_ID,
                   actionable=actionable)]
    got = classify_latch(latch=latch, views=views, epoch=EPOCH)
    assert got.disposition == expect
    assert got.disposition != "away_unseen", (
        "adding an observation must NEVER yield a NEGATIVE inference drawn from "
        "the dark period")
    assert got.coverage.coverage == "partial"
    assert got.coverage.observation_recorded is True


def test_T_A2_a_view_row_in_the_UNCOVERED_portion_cannot_move_it_either():
    """A row dated inside the DARK period is not an observation, because there was
    NO INSTRUMENT to make it -- so it cannot exist, and if one appeared it must not
    resolve the question."""
    latch = _ftre(state="horizon_expired", clear_reason="horizon",
                  clear_session=FTRE_HORIZON)
    got = classify_latch(
        latch=latch,
        views=[_View(date(2026, 7, 22), candidate_id=FTRE_CANDIDATE_ID)],
        epoch=EPOCH)
    assert got.disposition == "pre_telemetry"


# ==========================================================================
# T-B -- THE SEEDED DISCRIMINATING TEST (RD ruling 3's replacement)
# ==========================================================================
_SEED_ANCHOR = date(2026, 8, 3)          # AFTER the epoch
_SEED_CLEAR = date(2026, 8, 14)
_SEED_SESSIONS = [
    _SEED_ANCHOR + timedelta(days=i)
    for i in range((_SEED_CLEAR - _SEED_ANCHOR).days + 1)
]


def _sibling_views(subject_id: int) -> list[_View]:
    """View rows for a SIBLING latch on the subject's own sessions -- the proof
    that THE BEACON WAS ALIVE. Without them the health gate turns the same input
    into `telemetry_unhealthy`, which is exactly the discrimination this fixture
    exists to have."""
    return [_View(s, candidate_id=subject_id + 1) for s in _SEED_SESSIONS]


def _seed_health(views) -> TelemetryHealth:
    subject = _seeded(anchor=_SEED_ANCHOR, last=_SEED_CLEAR, candidate_id=900)
    sibling = _seeded(anchor=_SEED_ANCHOR, last=_SEED_CLEAR, candidate_id=901,
                      ticker="SIB")
    return assess_telemetry_health(
        sessions=_SEED_SESSIONS, latches=[subject, sibling], views=views,
        epoch=EPOCH)


def test_T_B_a_fully_covered_window_with_a_live_beacon_and_no_views_is_away():
    """WHERE THE ACCEPTANCE SEMANTICS NOW LIVE. A seeded fire anchored 2026-08-03
    (after the epoch), cleared 2026-08-14, so its window is FULLY covered; ZERO
    view rows for IT, and view rows present for a SIBLING latch on those same
    sessions -- PROVING THE BEACON WAS ALIVE."""
    subject = _seeded(anchor=_SEED_ANCHOR, last=_SEED_CLEAR, candidate_id=900)
    views = _sibling_views(900)
    health = _seed_health(views)
    assert health.verdict == "ok", "the sibling rows must prove the beacon alive"
    got = classify_latch(
        latch=subject, views=[v for v in views if v.candidate_id == 900],
        telemetry_health=health, epoch=EPOCH)
    assert got.disposition == "away_unseen"
    assert got.coverage.coverage == "full"
    bucket = r_bucket_for(got.disposition, is_terminal=got.is_terminal)
    assert bucket == "away_r"
    rep = compute_execution_parity(
        [ParityObservation(disposition=got, r_multiple=0.8)], health=health)
    assert rep.away.away_unseen_fires == 1
    assert rep.away.classifiable_fires == 1
    assert rep.away.objective_rate == 1.0
    assert rep.bucket_r["away_r"] == 0.8
    # EXCLUDED from the discipline signal: away is not a judgment datum.
    assert rep.decision_r_logged == rep.decision_r_attested == 0
    assert rep.decision_r_inferred == 0


def test_T_B_STRIP_THE_SIBLING_ROWS_AND_IT_BECOMES_telemetry_unhealthy():
    """THE FIRST DISCRIMINATOR. With no beacon witness at all the health gate
    refuses the number rather than calling a dark window away -- and the window is
    longer than the dark threshold, so the verdict is `broken`."""
    subject = _seeded(anchor=_SEED_ANCHOR, last=_SEED_CLEAR, candidate_id=900)
    health = _seed_health([])
    assert len(_SEED_SESSIONS) >= THRESHOLD
    assert health.verdict == "broken"
    got = classify_latch(latch=subject, views=[], telemetry_health=health,
                         epoch=EPOCH)
    assert got.disposition == "telemetry_unhealthy"
    assert r_bucket_for(
        got.disposition, is_terminal=got.is_terminal) == "unattributable_r"
    rep = compute_execution_parity(
        [ParityObservation(disposition=got, r_multiple=0.8)], health=health)
    assert rep.away.objective_rate is None
    assert rep.away.attested_rate is None
    assert rep.away.withheld_reason


def test_T_B_MOVE_THE_ANCHOR_ONE_SESSION_BEFORE_THE_EPOCH_AND_IT_BECOMES_pre_telemetry():
    """THE SECOND DISCRIMINATOR. Same substrate, same beacon witness, anchor moved
    back across the epoch -> the coverage question is no longer answerable and the
    honest label changes with it."""
    subject = _seeded(anchor=EPOCH - timedelta(days=1), last=_SEED_CLEAR,
                      candidate_id=900)
    views = _sibling_views(900)
    health = _seed_health(views)
    got = classify_latch(
        latch=subject, views=[v for v in views if v.candidate_id == 900],
        telemetry_health=health, epoch=EPOCH)
    assert got.disposition == "pre_telemetry"
    assert got.coverage.coverage == "partial"


# ==========================================================================
# T-C -- THE PESSIMISTIC DEFAULT
# ==========================================================================
def test_T_C_the_same_substrate_WITH_a_view_row_for_THIS_latch_is_a_lapse():
    """THE VIEWED / NEVER-VIEWED DISCRIMINATOR. T-C is T-B plus a single view row
    for THIS latch: FLIP THAT ROW FROM PRESENT TO ABSENT AND T-C BECOMES T-B. That
    pair is exactly what the brief's single test does not contain.

    An unattested viewed-but-no-action cell is a `discipline_lapse`, NOT away. The
    pessimistic default is LOAD-BEARING: a permissive default silently FLATTERS the
    measurement, and an honest instrument does not flatter its subject.
    """
    subject = _seeded(anchor=_SEED_ANCHOR, last=_SEED_CLEAR, candidate_id=900)
    own = [_View(date(2026, 8, 5), candidate_id=900)]
    views = [*_sibling_views(900), *own]
    health = _seed_health(views)
    assert health.verdict == "ok"
    got = classify_latch(latch=subject, views=own, telemetry_health=health,
                         epoch=EPOCH)
    assert got.effective_disposition == "discipline_lapse"
    assert got.prompt_required is True, (
        "the prompt is shown BECAUSE the cell has already been scored as a "
        "lapse; attesting is his opportunity to CORRECT it")
    assert r_bucket_for(
        got.disposition, is_terminal=got.is_terminal) == "decision_r"
    rep = compute_execution_parity(
        [ParityObservation(disposition=got, r_multiple=-0.5)], health=health)
    assert rep.decision_r_inferred == 1
    assert rep.away.away_unseen_fires == 0


def test_T_C_deleting_the_row_reverses_it_to_T_B():
    """The pair, asserted as a PAIR."""
    subject = _seeded(anchor=_SEED_ANCHOR, last=_SEED_CLEAR, candidate_id=900)
    health = _seed_health(_sibling_views(900))
    with_row = classify_latch(
        latch=subject, views=[_View(date(2026, 8, 5), candidate_id=900)],
        telemetry_health=health, epoch=EPOCH)
    without_row = classify_latch(
        latch=subject, views=[], telemetry_health=health, epoch=EPOCH)
    assert with_row.disposition == "discipline_lapse"
    assert without_row.disposition == "away_unseen"


def test_T_C_never_prompt_where_telemetry_says_never_viewed():
    """An unnecessary prompt on an objectively-resolved cell TRAINS DISMISSAL, and
    dismissal is what eventually kills the honest answer on the cell that
    matters."""
    subject = _seeded(anchor=_SEED_ANCHOR, last=_SEED_CLEAR, candidate_id=900)
    health = _seed_health(_sibling_views(900))
    away = classify_latch(latch=subject, views=[], telemetry_health=health,
                          epoch=EPOCH)
    assert away.disposition == "away_unseen"
    assert away.prompt_required is False
    ftre = classify_latch(latch=_ftre(), views=[], epoch=EPOCH)
    assert ftre.prompt_required is False
    withheld_only = classify_latch(
        latch=subject, views=[_View(date(2026, 8, 5), candidate_id=900,
                                    actionable=0)],
        telemetry_health=health, epoch=EPOCH)
    assert withheld_only.disposition == "never_actionable"
    assert withheld_only.prompt_required is False, (
        "prompting a man to attest about a decision the panel NEVER PRESENTED is "
        "the purest form of the train-the-dismissal-reflex failure")
