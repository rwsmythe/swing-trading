"""ITEM 1 -- a one-sided stop leg FAILS the numerator; it is not `unknown`
(RD ruling, 2026-07-30).

A framework `STOP_LIMIT` against an actual `LIMIT` is NOT unknown -- both sides
are observed. `unknown` is for when the INSTRUMENT CANNOT OBSERVE; this is a
fully observed DISAGREEMENT, and excluding it from the denominator deletes a
real disagreement from the agreement rate.

RD's consistency check, carried in the code: `both_absent` is already a ruled
MATCH -- a determinable AGREEMENT. One-present-one-absent is the symmetric
determinable DISAGREEMENT. Scoring one and calling the other unknown is exactly
the asymmetry that produces a flattering metric.
"""
from __future__ import annotations

import pytest

from swing.latches.constants import LATCH_STOP_LEG_STATES
from swing.latches.order_intent import OrderDelta, compute_order_delta

_FW_STOP_LIMIT = {
    "order_type": "STOP_LIMIT", "duration": "GOOD_TILL_CANCEL",
    "stop_price": 18.34, "limit_price": 18.89, "quantity": 9,
}
_AC_PLAIN_LIMIT = {
    "order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
    "stop_price": None, "limit_price": 18.89, "quantity": 9,
}


def test_the_state_vocabulary_carries_the_observed_leg_difference():
    assert "one_sided" in LATCH_STOP_LEG_STATES
    assert {"both_absent", "compared", "unknown"} <= LATCH_STOP_LEG_STATES


def test_one_side_carrying_a_stop_is_a_DIFFERENCE_not_an_unknown():
    """THE DISCRIMINATOR, with the arithmetic under BOTH paths.

    PRE-FIX: `stop_leg='unknown'` -> `differences.append(None)` ->
             `any_difference is None` -> `compute_execution_parity` counts the
             observation as `actual_side_unknown` and it LEAVES the denominator.
    POST-FIX: `stop_leg='one_sided'` -> `differences.append(True)` ->
             `any_difference is True` -> the observation enters the denominator
             and FAILS the numerator.
    Every other field here AGREES, so the stop leg alone decides the verdict.
    """
    delta = compute_order_delta(_FW_STOP_LIMIT, _AC_PLAIN_LIMIT)
    assert delta.stop_leg == "one_sided"
    assert delta.stop_price_delta is None, (
        "there is no numeric delta between a price and an absent leg")
    assert "stop_price" not in delta.unknown_fields, (
        "we can SEE both sides; withholding here is the flattering omission")
    assert delta.any_difference is True


def test_the_symmetric_case_actual_carries_the_stop_and_framework_does_not():
    """A pullback mandate (no stop leg) against a resting STOP_LIMIT -- the
    FTRE shape the schema refuses to store on the framework side, arriving from
    the BROKER. Determinable in exactly the same way."""
    delta = compute_order_delta(
        {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": 18.89, "quantity": 9},
        {"order_type": "STOP_LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": 18.34, "limit_price": 18.89, "quantity": 9})
    assert delta.stop_leg == "one_sided"
    assert delta.any_difference is True


def test_a_STOP_LIMIT_MISSING_its_trigger_is_UNKNOWN_not_one_sided():
    """CODEX R1 MAJOR on the ruling pass. An absence is a FACT only when that
    side's own order type establishes it.

    A broker `STOP_LIMIT` carrying no stop price is not an order without a stop
    leg -- it is an order whose TRIGGER WE FAILED TO READ. The broker payload is
    unconstrained input and reaches `compute_order_delta` at prompt-render time,
    so the schema CHECK that forbids persisting this shape on an
    `accepted_by_broker` row does NOT cover the vector. Scoring it as a
    determinable disagreement is the same error the ruling fixed, pointed the
    other way: asserting an observation the instrument never made.
    """
    delta = compute_order_delta(
        _FW_STOP_LIMIT,
        {"order_type": "STOP_LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": 18.89, "quantity": 9})
    assert delta.stop_leg == "unknown"
    assert "stop_price" in delta.unknown_fields
    assert delta.any_difference is None


def test_an_UNKNOWN_broker_rendering_missing_a_trigger_is_also_UNKNOWN():
    """The same rule at the other unmapped shape: `UNKNOWN` is precisely the
    canonicalisation for a broker order type the framework could not read, so it
    cannot establish that the order has no stop leg."""
    delta = compute_order_delta(
        _FW_STOP_LIMIT,
        {"order_type": "UNKNOWN", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": 18.89, "quantity": 9})
    assert delta.stop_leg == "unknown"


def test_an_UNOBSERVED_actual_side_is_still_UNKNOWN():
    """THE LINE RD DREW. `unknown` keeps its meaning -- the instrument could
    not observe -- and this case must NOT be swept into the numerator."""
    delta = compute_order_delta(_FW_STOP_LIMIT, None)
    assert delta.stop_leg == "unknown"
    assert "stop_price" in delta.unknown_fields
    assert delta.any_difference is None


def test_both_absent_requires_BOTH_absences_to_be_ESTABLISHED():
    """CODEX R2 MINOR -- the round-1 fix reached by a different door.

    A framework `LIMIT` (correctly no stop leg) against a broker `STOP_LIMIT`
    whose trigger was UNREADABLE lands here with two `None`s, and calling that
    an AGREEMENT about leg presence is a fabricated match: the stop field would
    be scored as an observed match and omitted from `unknown_fields`, hiding the
    unreadable trigger entirely.
    """
    delta = compute_order_delta(
        {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": 18.89, "quantity": 9},
        {"order_type": "STOP_LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": 18.89, "quantity": 9})
    assert delta.stop_leg == "unknown"
    assert "stop_price" in delta.unknown_fields


def test_both_absent_is_STILL_a_MATCH():
    """The ruled tri-state semantic that must not regress: the pullback
    regime's RIGHT answer is a determinable AGREEMENT."""
    delta = compute_order_delta(
        {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": 18.89, "quantity": 9},
        {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": 18.89, "quantity": 9})
    assert delta.stop_leg == "both_absent"
    assert delta.any_difference is False


def test_the_delta_dataclass_refuses_a_price_delta_on_a_one_sided_leg():
    """`stop_price_delta` is set IFF `compared` -- the invariant is unchanged by
    the new state, and the validator must still enforce it."""
    OrderDelta(order_type_differs=True, duration_differs=False,
               stop_leg="one_sided", stop_price_delta=None,
               limit_price_delta=0.0, quantity_delta=0,
               any_difference=True, unknown_fields=())
    with pytest.raises(ValueError, match="stop_price_delta is set IFF"):
        OrderDelta(order_type_differs=True, duration_differs=False,
                   stop_leg="one_sided", stop_price_delta=1.0,
                   limit_price_delta=0.0, quantity_delta=0,
                   any_difference=True, unknown_fields=())


def test_the_report_ENTERS_the_denominator_and_NAMES_the_failing_field():
    """END TO END, through the report the arc publishes.

    PRE-FIX the observation landed in `actual_side_unknown` and
    `delta_totals['unknown']`, leaving `agreement_denominator == 0` -- a rate
    computed over a corpus with the disagreement quietly removed.
    POST-FIX it is 0/1 and the per-field table NAMES the stop leg, so the reader
    sees a failed agreement WITH its attributed cause rather than an
    unexplained one.
    """
    from swing.latches.classification import (
        CoverageVerdict,
        LatchDisposition,
        ParityObservation,
        TelemetryHealth,
        compute_execution_parity,
    )
    from swing.latches.constants import LATCH_TELEMETRY_EPOCH_SESSION as _EP

    coverage = CoverageVerdict(
        coverage="full", observation_recorded=True,
        table_disposition="__classify_normally__",
        covered_from=_EP, covered_through=_EP)
    rep = compute_execution_parity(
        [ParityObservation(
            disposition=LatchDisposition(
                candidate_id=1, disposition="accepted",
                execution_outcome="accepted_by_broker", prompt_required=False,
                is_terminal=True, coverage=coverage),
            framework=dict(_FW_STOP_LIMIT), actual=dict(_AC_PLAIN_LIMIT))],
        health=TelemetryHealth(verdict="ok", covered_sessions=5))
    assert rep.agreement_denominator == 1
    assert rep.agreement_numerator == 0
    assert rep.delta_totals["stop_price_differs"] == 1
    assert rep.delta_totals["unknown"] == 0
    assert rep.actual_side_unknown == 0
