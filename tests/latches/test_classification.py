"""The three-state disposition classifier - PURE (Arc 21-B Task 3).

Every rung has its own DISCRIMINATING test, and each cell of the
coverage/actionability matrix discriminates a DIFFERENT wrong implementation.
"""
from __future__ import annotations

from datetime import date

import pytest

from swing.data.models import LatchOrderIntent, LatchViewEvent
from swing.latches.classification import (
    COVERAGE_STATES,
    PROMPT_DISPOSITIONS,
    RD_COVERAGE_TABLE,
    LatchDisposition,
    TelemetryHealth,
    actionable_view_rows,
    assess_telemetry_health,
    awareness_view_rows,
    classify_latch,
    governing_intent,
    resolve_coverage,
)
from swing.latches.constants import (
    LATCH_DISPOSITIONS,
    LATCH_TELEMETRY_EPOCH_SESSION,
)
from swing.latches.identity import LatchIdentity
from swing.latches.models import Latch

EPOCH = LATCH_TELEMETRY_EPOCH_SESSION          # date(2026, 7, 29)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def _latch(*, anchor: date, last: date, state: str = "armed",
           clear_reason: str | None = None, clear_session: date | None = None,
           candidate_id: int = 11261, ticker: str = "FTRE",
           detection_date: str | None = None) -> Latch:
    return Latch(
        identity=LatchIdentity(
            candidate_id=candidate_id, evaluation_run_id=121, ticker=ticker,
            detection_date=detection_date or anchor.isoformat(),
            pipeline_run_id=None),
        latched_pivot=18.34, latched_initial_stop=14.88, zone_cap=18.8902,
        anchor=anchor, horizon_expiry=last, sessions_elapsed=1,
        sessions_to_horizon=1, state=state, clear_reason=clear_reason,
        clear_session=clear_session)


def _view(session: date, *, actionable: int = 1, surface: str = "latch_panel",
          state: str = "armed", candidate_id: int = 11261,
          ticker: str = "FTRE", detection_date: str = "2026-07-20",
          view_event_id: int = 1) -> LatchViewEvent:
    return LatchViewEvent(
        view_event_id=view_event_id, candidate_id=candidate_id,
        evaluation_run_id=121, ticker=ticker, detection_date=detection_date,
        pipeline_run_id=None, surface=surface,
        view_session_date=session.isoformat(),
        first_viewed_ts=f"{session.isoformat()}T10:00:00",
        last_viewed_ts=f"{session.isoformat()}T11:00:00", view_count=1,
        latch_state_at_first_view=state, latch_state_at_last_view=state,
        actionable_at_first_view=actionable, actionable_at_last_view=actionable,
        actionable_ever_viewed=actionable)


def _intent(kind: str, *, intent_id: int, recorded_ts: str,
            action_session_date: str = "2026-08-03",
            candidate_id: int = 11261, **over) -> LatchOrderIntent:
    kw = dict(
        intent_id=intent_id, candidate_id=candidate_id, evaluation_run_id=121,
        ticker="FTRE", detection_date="2026-07-20", pipeline_run_id=None,
        idempotency_key=f"k{intent_id}",
        action_session_date=action_session_date, recorded_ts=recorded_ts,
        surface="latch_panel", intent_kind=kind)
    if kind in ("place", "decline"):
        kw.update(
            framework_order_type="LIMIT", framework_duration="GOOD_TILL_CANCEL",
            framework_limit_price=18.89, framework_quantity=9,
            derivation_zone_cap_pct=3.0, derivation_sizing_equity=7500.0,
            derivation_max_risk_pct=0.005, derivation_position_pct_cap=0.15,
            derivation_sizing_basis="limit_price", derivation_regime_close=19.20,
            derivation_regime_close_session="2026-08-03",
            derivation_real_equity=1234.56, derivation_equity_floor=7500.0)
    if kind == "decline":
        kw["decline_reason"] = "too extended"
    if kind == "cancel":
        kw["actual_broker_order_id"] = "1002937461"
    kw.update(over)
    return LatchOrderIntent(**kw)


def _validity(intent_id: int, parent_id: int, outcome: str, recorded_ts: str,
              action_session_date: str = "2026-08-03") -> LatchOrderIntent:
    import json
    env = json.dumps({
        "broker_snapshot_ts": recorded_ts,
        "broker_snapshot_branch": "presence",
        "broker_snapshot_digest": "c" * 64,
        "broker_snapshot_session": recorded_ts[:10],
        "attributable_order_count": 1,
        "exact_framework_match_count": 0,
        "indeterminate": False,
    })
    extra = {}
    if outcome == "accepted_by_broker":
        extra = dict(
            actual_order_type="LIMIT", actual_duration="GOOD_TILL_CANCEL",
            actual_limit_price=18.89, actual_quantity=10,
            actual_broker_order_id="1002937461")
    return _intent(
        "validity", intent_id=intent_id, recorded_ts=recorded_ts,
        action_session_date=action_session_date,
        validated_place_intent_id=parent_id, validity_outcome=outcome,
        validity_detail=env, **extra)


# --------------------------------------------------------------------------
# The section E.0 properties
# --------------------------------------------------------------------------
def test_the_coverage_table_is_TOTAL_over_the_key_product():
    """An unhandled combination cannot fall through to a default."""
    for coverage in sorted(COVERAGE_STATES):
        for observed in (True, False):
            assert (coverage, observed) in RD_COVERAGE_TABLE
    assert len(RD_COVERAGE_TABLE) == len(COVERAGE_STATES) * 2


def test_the_MONOTONE_property_asserted_THROUGH_classify_latch():
    """RD RULING 2'S DEFINING CONSEQUENCE: the classification can only move from
    unknown toward a POSITIVE fact, NEVER toward a negative inference drawn from
    a dark period.

    Asserted THROUGH `classify_latch` on CONCRETE substrates, NOT over the table's
    values: most table values are the `_CLASSIFY_NORMALLY` sentinel, so a
    table-level assertion proves NOTHING about the final disposition -- a broken
    `_CLASSIFY_NORMALLY` could still return the forbidden negative inference and
    pass.
    """
    substrates = {
        "full": _latch(anchor=EPOCH, last=date(2026, 8, 31)),
        "partial": _latch(anchor=date(2026, 7, 20), last=date(2026, 8, 31)),
        "none": _latch(anchor=date(2026, 7, 1), last=date(2026, 7, 20)),
    }
    for name, latch in substrates.items():
        for actionable in (0, 1):
            views = [_view(max(latch.anchor, EPOCH), actionable=actionable)]
            if name == "none":
                continue      # no covered portion can hold a record
            got = classify_latch(latch=latch, views=views)
            assert got.disposition != "away_unseen", (
                f"{name}/actionable={actionable}: adding an observation must "
                "never yield away_unseen -- that is a NEGATIVE inference drawn "
                "from a dark period")


def test_classify_latch_output_depends_only_on_what_the_verdict_carries():
    """NO RE-DERIVATION, asserted BEHAVIOURALLY over representative substrates.

    Deliberately NOT a source-text search for the absence of branches: the rungs
    legitimately branch on the verdict's OWN fields, so a source-text form is
    unsatisfiable and gets watered down until it stops detecting drift.

    Two substrates with the SAME CoverageVerdict shape and the same view sets must
    produce the same disposition even though their absolute dates differ.
    """
    a = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    b = _terminal(date(2026, 9, 1), date(2026, 9, 15))
    va = resolve_coverage(a, [_view(date(2026, 8, 5))])
    vb = resolve_coverage(b, [_view(date(2026, 9, 3))])
    assert (va.coverage, va.observation_recorded, va.table_disposition) == (
        vb.coverage, vb.observation_recorded, vb.table_disposition)
    assert (classify_latch(latch=a, views=[_view(date(2026, 8, 5))]).disposition
            == classify_latch(
                latch=b, views=[_view(date(2026, 9, 3))]).disposition)


@pytest.mark.parametrize("anchor,last,expect", [
    pytest.param(EPOCH, date(2026, 8, 31), "full", id="anchor-ON-the-epoch"),
    pytest.param(date(2026, 7, 28), date(2026, 8, 31), "partial",
                 id="anchor-one-day-before-the-epoch"),
    pytest.param(date(2026, 7, 20), EPOCH, "partial", id="clear-ON-the-epoch"),
    pytest.param(date(2026, 7, 20), date(2026, 7, 30), "partial",
                 id="clear-one-day-after-the-epoch"),
    pytest.param(date(2026, 7, 1), date(2026, 7, 28), "none",
                 id="clear-before-the-epoch"),
])
def test_the_coverage_arithmetic_at_every_boundary(anchor, last, expect):
    latch = _latch(anchor=anchor, last=last)
    assert resolve_coverage(latch, []).coverage == expect


# --------------------------------------------------------------------------
# THE COVERAGE / ACTIONABILITY MATRIX -- all four cells
# --------------------------------------------------------------------------
def _terminal(anchor: date, last: date) -> Latch:
    """`Latch.__post_init__` requires a terminal state to carry a clear_reason
    (and a live one to carry none), so a terminal fixture must supply both."""
    return _latch(anchor=anchor, last=last, state="horizon_expired",
                  clear_reason="horizon", clear_session=last)


def test_FULL_plus_no_observation_is_away_unseen():
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    assert classify_latch(latch=latch, views=[]).disposition == "away_unseen"


def test_FULL_plus_observation_with_no_actionable_row_is_never_actionable():
    """An implementation IGNORING the actionability column returns
    `discipline_lapse` or `away_unseen` -- and FAILS in OPPOSITE directions."""
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    got = classify_latch(
        latch=latch, views=[_view(date(2026, 8, 5), actionable=0)])
    assert got.disposition == "never_actionable"
    assert got.prompt_required is False


def test_PARTIAL_plus_observation_with_no_actionable_row_is_never_actionable():
    """An implementation RE-APPLYING a coverage veto after the table routed
    normally returns `pre_telemetry` and FAILS.

    `never_actionable` says *the instrument was there, it observed, and what it
    showed him was nothing actionable* -- true whenever awareness is established,
    regardless of how much of the window was instrumented.
    """
    latch = _terminal(date(2026, 7, 20), date(2026, 8, 31))
    got = classify_latch(
        latch=latch, views=[_view(date(2026, 7, 30), actionable=0)])
    assert got.disposition == "never_actionable"


def test_PARTIAL_plus_NO_observation_is_pre_telemetry_the_FTRE_geometry():
    """An implementation ranking ACTIONABILITY above COVERAGE flips the arc's
    headline case on the first page view and FAILS."""
    latch = _terminal(date(2026, 7, 20), date(2026, 8, 31))
    got = classify_latch(latch=latch, views=[])
    assert got.disposition == "pre_telemetry"
    assert got.coverage.coverage == "partial"


def test_the_coverage_axis_counts_rows_of_EITHER_actionability():
    """A WITHHELD render proves the beacon FIRED. Requiring actionability on the
    COVERAGE axis would classify that latch `pre_telemetry` -- asserting the
    apparatus was ABSENT when it was present and working, which is the conflation
    ruling 1 forbids and makes RD's THIRD THING unreachable."""
    latch = _terminal(date(2026, 7, 20), date(2026, 8, 31))
    v = resolve_coverage(latch, [_view(date(2026, 7, 30), actionable=0)])
    assert v.observation_recorded is True
    assert v.table_disposition != "pre_telemetry"


def test_actionable_view_rows_is_a_STRICT_SUBSET_of_awareness_view_rows():
    latch = _terminal(date(2026, 7, 20), date(2026, 8, 31))
    views = [_view(date(2026, 7, 30), actionable=0, view_event_id=1),
             _view(date(2026, 7, 31), actionable=1, view_event_id=2)]
    aware = awareness_view_rows(latch, views)
    act = actionable_view_rows(latch, views)
    assert set(act) < set(aware)
    assert len(aware) == 2 and len(act) == 1


# --------------------------------------------------------------------------
# The rung ORDER
# --------------------------------------------------------------------------
def test_the_coverage_table_is_consumed_BEFORE_telemetry_health():
    """HEALTH MAY NOT PRE-EMPT RD'S RULED TABLE. Where the table has already
    ruled the question UNANSWERABLE, a health verdict adds nothing and must not
    overwrite the REASON. A draft running health first returns
    `telemetry_unhealthy` and FAILS."""
    latch = _terminal(date(2026, 7, 20), date(2026, 8, 31))
    got = classify_latch(
        latch=latch, views=[],
        telemetry_health=TelemetryHealth(
            verdict="broken", covered_sessions=0, uncovered_sessions=9))
    assert got.disposition == "pre_telemetry"


def test_health_excludes_INDETERMINATE_too_not_only_broken():
    """`!= "ok"`, NOT `== "broken"`. Excluding only `broken` lets a SHORT
    fully-covered window with NO beacon witness score `away_unseen` and enter the
    away rate -- while the seeded discriminator requires sibling view rows to
    prove the beacon was alive before it will call anything away. The classifier
    must hold itself to the standard its own test does."""
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    got = classify_latch(
        latch=latch, views=[],
        telemetry_health=TelemetryHealth(
            verdict="indeterminate", covered_sessions=0, uncovered_sessions=2))
    assert got.disposition == "telemetry_unhealthy"
    assert got.telemetry_verdict == "indeterminate"


def test_an_explicit_place_beats_every_telemetry_rung():
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    got = classify_latch(
        latch=latch, views=[],
        intents=[_intent("place", intent_id=1, recorded_ts="2026-08-04T10:00:00")],
        telemetry_health=TelemetryHealth(verdict="broken", uncovered_sessions=9))
    assert got.disposition == "accepted"


def test_a_decline_beats_the_telemetry_rungs_but_not_a_place():
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    intents = [_intent("decline", intent_id=1, recorded_ts="2026-08-04T10:00:00")]
    assert classify_latch(
        latch=latch, views=[], intents=intents).disposition == "declined"
    intents.append(
        _intent("place", intent_id=2, recorded_ts="2026-08-05T10:00:00"))
    assert classify_latch(
        latch=latch, views=[], intents=intents).disposition == "accepted", (
        "an earlier decline is HISTORY, not the outcome")


@pytest.mark.parametrize("attested,expect", [
    ("acted_manually", "attested_acted_manually"),
    ("chose_not_to_act", "attested_chose_not_to_act"),
    ("was_away", "attested_was_away"),
])
def test_each_attested_disposition_maps_to_its_own_label(attested, expect):
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    got = classify_latch(
        latch=latch, views=[],
        intents=[_intent("attest", intent_id=1,
                         recorded_ts="2026-08-15T10:00:00",
                         attested_disposition=attested)])
    assert got.disposition == expect


# --------------------------------------------------------------------------
# THE ORDERING RULE -- the governing row within a kind
# --------------------------------------------------------------------------
def test_two_conflicting_attestations_resolve_to_the_LATER_one_DETERMINISTICALLY():
    """A CORRECTION MUST WIN. If he attests `was_away` and then corrects to
    `chose_not_to_act`, the correction moves the fire INTO the discipline signal
    AGAINST HIMSELF. Taking the earlier row would silently preserve the more
    flattering answer -- the one-sided bias arriving through the ORDERING door
    instead of the default door.

    Asserted under BOTH list orders: an implementation reading "the first attest
    found" passes under one order and FAILS under the other, which IS the bug.
    """
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    early = _intent("attest", intent_id=1, recorded_ts="2026-08-15T10:00:00",
                    attested_disposition="was_away")
    late = _intent("attest", intent_id=2, recorded_ts="2026-08-16T10:00:00",
                  attested_disposition="chose_not_to_act")
    for order in ([early, late], [late, early]):
        got = classify_latch(latch=latch, views=[], intents=order)
        assert got.disposition == "attested_chose_not_to_act"


def test_the_intent_id_tiebreak_is_load_bearing_on_a_shared_second():
    """`recorded_ts` is WHOLE SECONDS, so two rows CAN share one."""
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    a = _intent("attest", intent_id=7, recorded_ts="2026-08-15T10:00:00",
                attested_disposition="was_away")
    b = _intent("attest", intent_id=8, recorded_ts="2026-08-15T10:00:00",
                attested_disposition="chose_not_to_act")
    for order in ([a, b], [b, a]):
        assert classify_latch(
            latch=latch, views=[], intents=order
        ).disposition == "attested_chose_not_to_act"
    assert governing_intent([a, b], "attest").intent_id == 8


# --------------------------------------------------------------------------
# The pessimistic default
# --------------------------------------------------------------------------
def test_a_terminal_viewed_unattested_cell_is_a_discipline_lapse_IMMEDIATELY():
    """No configuration, no grace window, no 'unknown' bucket. Scored the instant
    the latch goes terminal, BEFORE any prompt is rendered and whether or not one
    ever is -- which makes the default INDEPENDENT of whether he ever comes back."""
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    got = classify_latch(latch=latch, views=[_view(date(2026, 8, 5))])
    assert got.effective_disposition == "discipline_lapse"
    assert got.prompt_required is True
    assert got.disposition not in (
        "away_unseen", "pending_live", "pre_telemetry", "never_actionable")


def test_a_LIVE_latch_with_actionable_views_and_no_intent_is_pending_live():
    """REPORTED, NEVER SCORED: a latch that has not terminated is not an
    observation yet, and its verdict would MOVE as the window runs."""
    latch = _latch(anchor=date(2026, 8, 3), last=date(2026, 9, 14))
    got = classify_latch(latch=latch, views=[_view(date(2026, 8, 5))])
    assert got.disposition == "pending_live"
    assert got.prompt_required is False
    assert got.is_terminal is False


def test_prompt_required_is_True_on_EXACTLY_ONE_disposition():
    """Parametrised OVER the frozenset, never over a copied list, and stating no
    count -- so a future disposition added WITHOUT a decision about its prompt
    FAILS.

    Rationale, recorded because it constrains future change: a prompt on an
    objectively-resolved cell trains DISMISSAL, and dismissal is what eventually
    kills the honest answer on the cell that matters.
    """
    assert PROMPT_DISPOSITIONS <= LATCH_DISPOSITIONS
    assert len(PROMPT_DISPOSITIONS) == 1
    assert PROMPT_DISPOSITIONS == {"discipline_lapse"}


@pytest.mark.parametrize("disposition", sorted(LATCH_DISPOSITIONS))
def test_the_prompt_flag_is_pinned_for_every_member_of_the_roster(disposition):
    """Constructing a LatchDisposition with the WRONG prompt flag RAISES, so no
    code path can emit a prompt on an objectively-resolved cell."""
    from swing.latches.classification import CoverageVerdict
    cov = CoverageVerdict(coverage="full", observation_recorded=True,
                          table_disposition="__classify_normally__",
                          covered_from=EPOCH, covered_through=EPOCH)
    expected = disposition in PROMPT_DISPOSITIONS
    LatchDisposition(
        candidate_id=1, disposition=disposition, execution_outcome="unknown",
        prompt_required=expected, is_terminal=True, coverage=cov)
    with pytest.raises(ValueError, match="prompt_required"):
        LatchDisposition(
            candidate_id=1, disposition=disposition,
            execution_outcome="unknown", prompt_required=not expected,
            is_terminal=True, coverage=cov)


# --------------------------------------------------------------------------
# section E.3 conjunct 3 -- WHILE LIVE
# --------------------------------------------------------------------------
def test_a_view_recorded_against_a_TERMINAL_state_is_NOT_evidence():
    """A view recorded of a `filled` latch is not evidence about a decision window
    that had already CLOSED."""
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    got = classify_latch(
        latch=latch, views=[_view(date(2026, 8, 5), state="filled")])
    assert got.disposition == "away_unseen"
    assert got.awareness_view_row_count == 0


def test_a_view_dated_OUTSIDE_the_live_window_is_NOT_evidence():
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    got = classify_latch(latch=latch, views=[_view(date(2026, 8, 20))])
    assert got.disposition == "away_unseen"


def test_a_row_on_a_NON_COUNTED_surface_is_ignored_via_the_PARAMETER():
    """Exercised through `counted_surfaces=` over a VALID `latch_panel` row rather
    than by planting an invalid surface row: the schema CHECK plus the model
    validator make a second surface UNWRITABLE today, so a test planting a
    `dashboard` row could only pass by BYPASSING the very #11 mirror it exists to
    respect."""
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    views = [_view(date(2026, 8, 5))]
    assert classify_latch(
        latch=latch, views=views).disposition == "discipline_lapse"
    assert classify_latch(
        latch=latch, views=views,
        counted_surfaces=frozenset()).disposition == "away_unseen"


# --------------------------------------------------------------------------
# The TWO-AXIS separation + the execution resolver
# --------------------------------------------------------------------------
def test_a_rejected_placement_is_still_an_ACCEPTED_decision():
    """An implementation COLLAPSING the axes returns a clean `accepted` with no
    execution signal and FAILS both halves -- and that is the FTRE failure mode
    itself, so a ledger built to measure it must not be able to hide it."""
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    place = _intent("place", intent_id=1, recorded_ts="2026-08-04T10:00:00")
    val = _validity(2, 1, "rejected_by_broker", "2026-08-06T10:00:00")
    got = classify_latch(latch=latch, views=[], intents=[place, val])
    assert got.disposition == "accepted"
    assert got.execution_outcome == "rejected_by_broker"


def test_an_unobserved_validity_resolves_UNKNOWN_never_a_success_value():
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    place = _intent("place", intent_id=1, recorded_ts="2026-08-04T10:00:00")
    got = classify_latch(latch=latch, views=[], intents=[place])
    assert got.execution_outcome == "unknown"


def test_no_governing_place_intent_yields_not_applicable():
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    got = classify_latch(latch=latch, views=[])
    assert got.execution_outcome == "not_applicable"


def test_a_FILL_beats_a_mis_attested_not_submitted():
    """RUNG 2 ABOVE RUNG 3, deliberately: A FILL IS AUTHORITATIVE OVER AN
    ATTESTATION. An order that filled was self-evidently accepted, the fill is a
    real position in the trades ledger rather than a recollection, and if the
    operator ever mis-attests on an order that demonstrably filled, the ledger
    should believe the POSITION."""
    latch = _latch(anchor=date(2026, 8, 3), last=date(2026, 8, 14),
                   state="filled", clear_reason="fill",
                   clear_session=date(2026, 8, 6))
    place = _intent("place", intent_id=1, recorded_ts="2026-08-04T10:00:00")
    val = _validity(2, 1, "not_submitted", "2026-08-07T10:00:00")
    got = classify_latch(latch=latch, views=[], intents=[place, val])
    assert got.execution_outcome == "accepted_by_broker"


def test_a_fill_dated_BEFORE_the_place_intent_does_NOT_vouch_for_it():
    """The BACKWARD guard: an older fill from a prior cycle cannot vouch for a
    NEWER intent."""
    latch = _latch(anchor=date(2026, 8, 3), last=date(2026, 8, 14),
                   state="filled", clear_reason="fill",
                   clear_session=date(2026, 8, 4))
    place = _intent("place", intent_id=1, recorded_ts="2026-08-10T10:00:00",
                    action_session_date="2026-08-10")
    got = classify_latch(latch=latch, views=[], intents=[place])
    assert got.execution_outcome == "unknown"


def test_a_second_place_validity_cycle_does_NOT_rewrite_the_first_ones_outcome():
    """PARENT-SCOPED, NOT LATCH-SCOPED. A latch-scoped fill rung would let the
    SECOND cycle's fill vouch for the FIRST cycle's rejected order, silently
    rewriting an execution-parity result that had been correctly recorded as a
    FAILURE."""
    from swing.latches.classification import resolve_execution_outcome_for
    latch = _latch(anchor=date(2026, 8, 3), last=date(2026, 8, 14),
                   state="filled", clear_reason="fill",
                   clear_session=date(2026, 8, 12))
    p1 = _intent("place", intent_id=1, recorded_ts="2026-08-04T10:00:00",
                 action_session_date="2026-08-04")
    v1 = _validity(2, 1, "rejected_by_broker", "2026-08-05T10:00:00",
                   action_session_date="2026-08-04")
    p2 = _intent("place", intent_id=3, recorded_ts="2026-08-10T10:00:00",
                 action_session_date="2026-08-10")
    intents = [p1, v1, p2]
    assert resolve_execution_outcome_for(
        latch, p1, intents) == "rejected_by_broker"
    assert resolve_execution_outcome_for(
        latch, p2, intents) == "accepted_by_broker"
    # ...and the latch's own governing outcome follows the LATEST place.
    assert classify_latch(
        latch=latch, views=[], intents=intents
    ).execution_outcome == "accepted_by_broker"


def test_the_LATEST_validity_row_within_a_parent_wins():
    """A CORRECTION is a NEW row. Resolution is the LATEST by
    (recorded_ts, intent_id) FOR THAT PARENT -- never 'the latest validity row for
    this latch'."""
    latch = _terminal(date(2026, 8, 3), date(2026, 8, 14))
    place = _intent("place", intent_id=1, recorded_ts="2026-08-04T10:00:00")
    early = _validity(2, 1, "rejected_by_broker", "2026-08-05T10:00:00")
    late = _validity(3, 1, "accepted_by_broker", "2026-08-06T10:00:00")
    for order in ([early, late], [late, early]):
        got = classify_latch(latch=latch, views=[], intents=[place, *order])
        assert got.execution_outcome == "accepted_by_broker"


# --------------------------------------------------------------------------
# The value type
# --------------------------------------------------------------------------
def test_an_unknown_disposition_or_execution_outcome_is_rejected():
    from swing.latches.classification import CoverageVerdict
    cov = CoverageVerdict(coverage="full", observation_recorded=True,
                          table_disposition="__classify_normally__",
                          covered_from=EPOCH, covered_through=EPOCH)
    with pytest.raises(ValueError, match="disposition must be in"):
        LatchDisposition(candidate_id=1, disposition="vibes",
                         execution_outcome="unknown", prompt_required=False,
                         is_terminal=True, coverage=cov)
    with pytest.raises(ValueError, match="execution_outcome must be in"):
        LatchDisposition(candidate_id=1, disposition="accepted",
                         execution_outcome="filled", prompt_required=False,
                         is_terminal=True, coverage=cov)


def test_an_unknown_telemetry_verdict_is_rejected():
    with pytest.raises(ValueError, match="verdict must be in"):
        TelemetryHealth(verdict="fine")


# --------------------------------------------------------------------------
# the health WINDOW -- Codex exec R2 MAJOR 4
# --------------------------------------------------------------------------
def test_the_window_ENUMERATES_the_silent_sessions_not_only_the_ones_with_rows():
    """CODEX EXEC R2 MAJOR 4. A window COLLECTED from the sessions that already
    HAVE a view row can never contain a dark session, so `uncovered` stays at
    zero by construction and the dark-count branch is unreachable. The window
    must be WALKED.

    The assertion is against the NYSE session walk, not against a count: the
    sessions between the anchor and `through` are the sessions the beacon was
    supposed to speak on, and every one of them must be offered to the check.
    """
    from swing.evaluation.dates import session_offset
    from swing.latches.classification import telemetry_window_sessions
    anchor = date(2026, 7, 29)
    through = date(2026, 8, 12)
    latch = _latch(anchor=anchor, last=through)
    got = telemetry_window_sessions([latch], through)
    expected = []
    cursor = through
    while cursor >= anchor:
        expected.append(cursor)
        cursor = session_offset(cursor, -1)
    assert got == expected
    assert len(got) > 2                     # not just {anchor, through}


def test_the_enumerated_window_lets_a_MOSTLY_DARK_month_verdict_BROKEN():
    """The consequence, and the reason MAJOR 4 was a major rather than a tidy.
    One beacon hit proves the beacon existed ONCE; it does not make the window
    OBSERVED. Under a collected window this same fixture verdicts `ok` and hands
    `away_unseen` straight to the away rate -- manufacturing away-rate evidence
    out of an instrument that was dark.
    """
    from swing.latches.classification import telemetry_window_sessions
    anchor = date(2026, 7, 29)
    through = date(2026, 8, 12)
    latch = _latch(anchor=anchor, last=through)
    views = [_view(anchor)]                 # exactly ONE beacon hit
    collected = sorted({date.fromisoformat(v.view_session_date) for v in views}
                       | {latch.anchor})
    assert assess_telemetry_health(
        sessions=collected, latches=[latch], views=views).verdict == "ok"
    enumerated = telemetry_window_sessions([latch], through)
    assert assess_telemetry_health(
        sessions=enumerated, latches=[latch], views=views).verdict == "broken"
