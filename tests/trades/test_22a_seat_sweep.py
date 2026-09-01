"""THE SEAT SWEEP -- a refusal reason is a property of ``(world, seat)``
(CHARC, canon `56e0773d`, from the case-4c-i ruling).

**A LADDER EVALUATED FROM A SEAT MAKES "THE REFUSAL REASON" A PROPERTY OF THE
PAIR, NOT OF THE WORLD -- so any spec or test pinning a reason MUST NAME THE
SEAT.**  S3.4c's second leg said *"refuse ``mandate_not_alive``"* without
saying whose seat, and from the dead order's seat the subject is a genuinely
proven-LIVE competitor, so rung 8 fired and `ambiguous_ticker_orders` was
EQUALLY TRUE.  **That one missing word read as a contradiction, then as a
fixture defect, then as a rung-ordering question -- three readings of one
omission**, across three rounds of adjudication.

THE SWEEP'S METHOD, stated because a completeness claim without one is a
feeling (recipe §5, "report every count with the method that produced it"):

  1. A STATIC walk over every ``test_22a_*.py`` module finds each module-level
     test function that PINS a refusal reason -- ``decline_reason == '...'``.
  2. **A seat ambiguity is possible ONLY where the world contains MORE THAN
     ONE accepted order.**  With one accepted order there is one seat and the
     reason is a property of the world alone, so the omission cannot bite.
     The walk therefore counts each function's calls to the arc's order
     builders.
  3. The multi-order set is held against the DECLARED roster below, in BOTH
     directions.  A ninth case fails here until someone states its seat --
     which is the whole point: the next omission is a VISIBLE LINE.

**MEASURED 2026-09-01, and the numbers are the sweep's result:**
**57 functions pin a refusal reason; 8 of them build more than one accepted
order; 1 was changed** (`4c-i`, whose second leg had been resolved at the
PROBE grain with the divergence declared in its docstring -- honest, and a
resolution nobody had ruled).  The other seven each pass an explicitly named
order into the ladder, so the seat is stated in the call.

WHAT THIS SWEEP DOES NOT SEE, declared rather than left to look complete: a
test that pins a reason through a helper whose call the walk cannot resolve,
or one that builds its orders through a builder not on the list below.  The
roster of builders is asserted non-empty and the pinning count is asserted at
a floor, so a walk that quietly stopped matching fails rather than reporting
zero problems.

FROZEN CLOCK: nothing here reads a clock.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARC_GLOB = "tests/**/test_22a_*.py"

_PINS_A_REASON = re.compile(r"decline_reason\s*==\s*[\"']")

# The arc's own order builders.  Every one mints or returns an
# ``AcceptedLatchOrder``; a fixture calling two of them has two seats.
ORDER_BUILDERS = frozenset({
    "accept", "_accept", "accept_and_link", "_accept_no_assert",
    "_forged_link", "order_for_candidate", "_mint_drifted_citation",
})

# ---------------------------------------------------------------------------
# THE DECLARED ROSTER: every reason-pinning test whose world has MORE THAN ONE
# accepted order, each with the seat its assertion is taken from.
#
# Hand-written because "which seat is this assertion about" is a JUDGMENT the
# walk cannot make.  What is mechanical is both directions of membership --
# so a ninth multi-order case cannot appear without a seat being stated.
# ---------------------------------------------------------------------------
SEATS: dict[str, str] = {
    # Two links on ONE broker order id: the request names the ORDER, so both
    # links are the same seat and the reason is a property of the world.
    "test_two_links_on_one_order_id_are_ambiguous_case_14":
        "the subject's seat (the request names one order id; the two links "
        "are that order's)",
    # Task-6 PROBE grain: `_probe` is asked about ONE named order per branch.
    "test_the_tie_does_not_widen_to_the_session_before_case_28e":
        "each branch's own seat -- the order is named in the `_probe` call",
    "test_decisions_are_ordered_against_the_fill_by_recorded_ts_case_20":
        "each branch's own seat -- the order is named in the `_probe` call",
    # THE ONE THAT CHANGED.
    "test_a_dead_rival_is_dropped_and_its_own_leg_refuses_case_4c_i":
        "BOTH seats, named: the SUBJECT's admits, the DEAD ORDER's refuses "
        "`mandate_not_alive` (the leg that moved from the probe grain to the "
        "ladder grain)",
    "test_a_dead_rival_does_not_rescue_a_pre_barrier_link_case_4c_i_pre":
        "the subject's seat (`authorize(conn, cfg, subject_order)`)",
    "test_a_pre_barrier_competitor_is_unprovable_not_dead":
        "the subject's seat; the rival's own probe is asserted separately and "
        "is labelled as such",
    "test_an_UNPROVABLE_subject_beside_a_live_rival_stays_AMBIGUOUS":
        "the junk subject's seat (`authorize(conn, cfg, junk_order)`)",
    "test_a_PRE_BARRIER_subject_cannot_prove_its_own_death_either":
        "the pre-barrier subject's seat",
}


def _arc_modules() -> list[Path]:
    return [p for p in sorted(REPO_ROOT.glob(ARC_GLOB))
            if "__pycache__" not in p.parts]


def _reason_pinning_functions() -> dict[str, int]:
    """test name -> how many order builders its body calls."""
    out: dict[str, int] = {}
    for path in _arc_modules():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not fn.name.startswith("test"):
                continue
            segment = ast.get_source_segment(source, fn) or ""
            if not _PINS_A_REASON.search(segment):
                continue
            calls = 0
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                name = (node.func.id if isinstance(node.func, ast.Name)
                        else getattr(node.func, "attr", ""))
                if name in ORDER_BUILDERS:
                    calls += 1
            out[fn.name] = calls
    return out


def _multi_order_pins() -> set[str]:
    return {name for name, calls in _reason_pinning_functions().items()
            if calls > 1}


def test_every_multi_order_reason_pin_names_its_seat() -> None:
    """DIRECTION A.  A ninth multi-order case is a NINTH SEAT QUESTION, and it
    fails here until someone answers it."""
    undeclared = sorted(_multi_order_pins() - set(SEATS))
    assert not undeclared, (
        f"{len(undeclared)} test(s) pin a refusal reason in a world with more "
        f"than one accepted order and name no seat: {undeclared}. A refusal "
        f"reason is a property of (world, seat); state which seat the "
        f"assertion is taken from in the roster above.")


def test_the_seat_roster_has_no_stale_entries() -> None:
    """DIRECTION B.  A stale entry describes a case that no longer exists and
    reads exactly like a covered one."""
    stray = sorted(set(SEATS) - _multi_order_pins())
    assert not stray, (
        f"the seat roster names tests that no longer pin a reason in a "
        f"multi-order world: {stray}")


def test_every_declared_seat_is_actually_stated() -> None:
    for name, seat in SEATS.items():
        assert seat.strip(), name
        assert "seat" in seat or "grain" in seat, (
            f"{name}'s entry does not name a seat: {seat!r}")


def test_the_sweep_numbers_and_the_method_that_produced_them() -> None:
    """THE COMPLETENESS CLAIM, WITH ITS METHOD -- and it fails if the walk
    quietly stops matching, which is how a sweep becomes a feeling.

    The floors are floors, not equalities: the arc gains tests, and an
    equality here would make every new reason-pinning test a false red.  What
    must not happen is the count COLLAPSING, which is the direction that would
    make both directions above vacuous.
    """
    pins = _reason_pinning_functions()
    assert len(pins) >= 57, (
        f"the walk finds {len(pins)} reason-pinning tests; it found 57 when "
        f"the sweep was run, so it has stopped matching")
    assert len(_multi_order_pins()) >= 8, len(_multi_order_pins())
    assert ORDER_BUILDERS, "the builder roster is empty; nothing can be multi"


def test_the_walk_can_tell_a_pinning_test_from_a_non_pinning_one() -> None:
    """The matcher's own discriminator, over the two shapes it must separate."""
    assert _PINS_A_REASON.search('assert v.decline_reason == "x"')
    assert _PINS_A_REASON.search("assert v.decline_reason == 'x'")
    assert not _PINS_A_REASON.search("assert v.decline_reason is None")
    assert not _PINS_A_REASON.search("# the decline_reason is not asserted")
