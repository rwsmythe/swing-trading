"""`fill_vouches_for` -- THE ONE SPELLING of "the framework's order filled" (D94 Task 1).

CHARC D94 1A: the resolver's fill rung is factored into ONE named predicate in
`swing/latches/classification.py`; the rung CALLS it and the latch panel's
explanation gate CALLS it, so neither re-spells the three conditions (the latch
cleared by FILL; on or after the place's session -- the BACKWARD guard; and the
place IS the latch's latest place -- the FORWARD guard). RD D94 item 2: the
prompt's explanation and the resolver's resolution are ONE rule.

T1.7 pins that the refactor is byte-identical for the resolver: the
single-place entry point and the per-place entry point agree over the grid.
"""
from __future__ import annotations

from datetime import date

import pytest

from swing.latches.classification import (
    fill_vouches_for,
    resolve_execution_outcome,
    resolve_execution_outcome_for,
)
from tests.latches.test_classification import _intent, _latch, _validity

ANCHOR = date(2026, 7, 27)
LAST = date(2026, 9, 14)


def _filled(clear_session=date(2026, 7, 28), *, clear_reason="fill"):
    return _latch(anchor=ANCHOR, last=LAST, state="filled",
                  clear_reason=clear_reason, clear_session=clear_session)


def _place(intent_id=1, *, recorded_ts="2026-07-27T09:00:00",
           action_session_date="2026-07-27", **over):
    return _intent("place", intent_id=intent_id, recorded_ts=recorded_ts,
                   action_session_date=action_session_date, **over)


def test_t1_1_the_latest_place_with_a_later_fill_is_vouched_for():
    place = _place()
    assert fill_vouches_for(_filled(date(2026, 7, 28)), place, [place]) is True


def test_t1_2_a_fill_on_the_place_session_is_vouched_for():
    """The backward guard is `>=`: he places and it fills the same session."""
    place = _place()
    assert fill_vouches_for(_filled(date(2026, 7, 27)), place, [place]) is True


def test_t1_3_a_fill_before_the_place_session_does_not_vouch():
    """The BACKWARD guard: an older fill cannot vouch for a newer intent."""
    place = _place()
    assert fill_vouches_for(_filled(date(2026, 7, 24)), place, [place]) is False


def test_t1_4_a_place_that_is_not_the_latest_place_is_not_vouched_for():
    """The FORWARD guard: an earlier cycle cannot borrow a later fill."""
    first = _place(1)
    second = _place(2, recorded_ts="2026-07-27T10:00:00")
    latch = _filled(date(2026, 7, 28))
    assert fill_vouches_for(latch, first, [first, second]) is False
    assert fill_vouches_for(latch, second, [first, second]) is True


def test_t1_5_a_latch_cleared_by_invalidation_never_vouches():
    place = _place()
    latch = _latch(anchor=ANCHOR, last=LAST, state="invalidated",
                   clear_reason="invalidation", clear_session=date(2026, 7, 28))
    assert fill_vouches_for(latch, place, [place]) is False


def test_t1_5_a_live_latch_with_no_clear_reason_never_vouches():
    place = _place()
    latch = _latch(anchor=ANCHOR, last=LAST)
    assert latch.clear_reason is None
    assert fill_vouches_for(latch, place, [place]) is False


def test_t1_5_a_missing_place_intent_never_vouches():
    assert fill_vouches_for(_filled(), None, []) is False


def test_t1_6_place_view_scopes_the_forward_guard_only():
    """Item 3a's case (`classification.py` `_for` docstring): a place latest IN
    VIEW but not latest overall (an out-of-bound later place) keeps its own
    fill's vouching when the caller passes the view it selected from."""
    mine = _place(1)
    foreign_later = _place(2, recorded_ts="2026-08-10T09:00:00",
                           action_session_date="2026-08-10",
                           candidate_id=99999)
    latch = _filled(date(2026, 7, 28))
    intents = [mine, foreign_later]
    assert fill_vouches_for(latch, mine, intents, place_view=[mine]) is True
    # The counterfactual: the same call with the view unscoped fails the guard.
    assert fill_vouches_for(latch, mine, intents) is False


@pytest.mark.parametrize("filled", [True, False])
@pytest.mark.parametrize("child", [
    None, "accepted_by_broker", "rejected_by_broker", "not_submitted"])
def test_t1_7_the_single_place_resolver_equals_the_per_place_resolver(
        filled, child):
    """The refactor is byte-identical: `resolve_execution_outcome(latch, p,
    rows)` is `resolve_execution_outcome_for(latch, p, [p, *rows])` over the
    grid fill/none x child/none (the child cell also spans the outcomes)."""
    place = _place()
    latch = (_filled(date(2026, 7, 28)) if filled
             else _latch(anchor=ANCHOR, last=LAST))
    rows = ([] if child is None
            else [_validity(5, place.intent_id, child, "2026-07-28T09:00:00",
                            action_session_date="2026-07-27")])
    got = resolve_execution_outcome(latch, place, rows)
    assert got == resolve_execution_outcome_for(latch, place, [place, *rows])
    # And the values the shipped rung produced on each cell, so the equality
    # cannot be satisfied by both sides drifting together.
    if filled:
        assert got == "accepted_by_broker"
    elif child is None:
        assert got == "unknown"
    else:
        assert got == child


def test_t1_7_a_missing_place_is_not_applicable_on_both_entry_points():
    latch = _filled()
    assert resolve_execution_outcome(latch, None, []) == "not_applicable"
    assert resolve_execution_outcome_for(latch, None, []) == "not_applicable"
