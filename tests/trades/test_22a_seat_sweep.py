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

**MEASURED 2026-09-01 on the leg's FINAL tree, and the numbers are the sweep's
result: 74 functions pin a refusal reason; 16 of them build more than one
accepted order; 1 was CHANGED** -- `4c-i`, whose second leg had been resolved
at the PROBE grain with the divergence declared in its docstring (honest, and
a resolution nobody had ruled).  The other fifteen each pass an explicitly
named order into the ladder, so the seat is stated in the call.

**AN EARLIER RUN OF THIS SWEEP REPORTED 57 AND 8, AND BOTH HALVES OF THE
DIFFERENCE ARE WORTH RECORDING.**  Eight of the extra multi-order cases became
multi-order IN THIS LEG: the twin repairs and the ticker-binding repair added
the rivals and the second forged link the audit said were missing, so the
sweep demanding their seats is the instrument working on its own leg's
output.  The rest of the growth is the AST matcher replacing a source-text
regex (Codex 22A-FIX-R1-05): the regex matched the phrase inside docstrings
and string literals -- it counted this module's OWN matcher control as a
pinning test -- and an inflated floor lets a genuine pin disappear while the
count stays green.

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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARC_GLOB = "tests/**/test_22a_*.py"

def _pins_a_reason(fn: ast.AST) -> bool:
    """Does this function actually COMPARE a ``.decline_reason`` to a string?

    **AST, NOT A REGEX OVER THE SOURCE** (Codex 22A-FIX-R1-05, which measured
    the difference: the regex counted 58 functions where 57 genuinely compare,
    the extra one being this module's own MATCHER CONTROL -- a function whose
    only occurrence of the phrase is inside a string literal).  A regex over a
    function's source text cannot tell an assertion from a docstring, and a
    count inflated by prose lets a genuine pin disappear while the floor stays
    green.
    """
    for node in ast.walk(fn):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, ast.Eq) for op in node.ops):
            continue
        operands = [node.left, *node.comparators]
        names_it = any(isinstance(v, ast.Attribute)
                       and v.attr == "decline_reason" for v in operands)
        against_a_literal = any(
            isinstance(v, ast.Constant) and isinstance(v.value, str)
            for v in operands)
        if names_it and against_a_literal:
            return True
    return False

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
_T4 = "tests/trades/test_22a_task4_authorization_ladder.py"
_T6 = "tests/trades/test_22a_task6_mandate_alive_at.py"
_T6A = "tests/trades/test_22a_task6a_competitor_liveness.py"

SEATS: dict[tuple[str, str], str] = {
    # Two links on ONE broker order id: the request names the ORDER, so both
    # links are the same seat and the reason is a property of the world.
    (_T4, "test_two_links_on_one_order_id_are_ambiguous_case_14"):
        "the subject's seat (the request names one order id; the two links "
        "are that order's)",
    # Task-6 PROBE grain: `_probe` is asked about ONE named order per branch.
    (_T6, "test_the_tie_does_not_widen_to_the_session_before_case_28e"):
        "each branch's own seat -- the order is named in the `_probe` call",
    (_T6, "test_decisions_are_ordered_against_the_fill_by_recorded_ts_case_20"):
        "each branch's own seat -- the order is named in the `_probe` call",
    # THE ONE THAT CHANGED.
    (_T6A, "test_a_dead_rival_is_dropped_and_its_own_leg_refuses_case_4c_i"):
        "BOTH seats, named: the SUBJECT's admits, the DEAD ORDER's refuses "
        "`mandate_not_alive` (the leg that moved from the probe grain to the "
        "ladder grain)",
    (_T6A,
     "test_a_dead_rival_does_not_rescue_a_pre_barrier_link_case_4c_i_pre"):
        "the subject's seat (`authorize(conn, cfg, subject_order)`)",
    (_T6A, "test_a_pre_barrier_competitor_is_unprovable_not_dead"):
        "the subject's seat; the rival's own probe is asserted separately and "
        "is labelled as such",
    (_T6A, "test_an_UNPROVABLE_subject_beside_a_live_rival_stays_AMBIGUOUS"):
        "the junk subject's seat (`authorize(conn, cfg, junk_order)`)",
    (_T6A, "test_a_PRE_BARRIER_subject_cannot_prove_its_own_death_either"):
        "the pre-barrier subject's seat",
    # EIGHT MORE, and they became multi-order IN THIS LEG -- the twin and
    # ticker-binding repairs added the rivals and the second forged link the
    # audit said were missing.  The sweep asking for their seats is the
    # instrument working, not a defect: each of the eight names ONE order in
    # its ladder call, and that order is the seat.
    (_T4, "test_a_link_whose_parent_is_not_a_place_row_is_incoherent_case_41a"):
        "each forged link's own seat -- the two shapes are authorized "
        "separately, one `_authorize` call each",
    (_T4, "test_a_mismatched_ticker_copy_is_unbound_case_47c"):
        "each forged link's own seat; the mismatched-ticker leg additionally "
        "names the REQUEST's ticker so rung 1 passes and only the candidate "
        "binding can refuse",
    (_T6A,
     "test_a_filtered_population_does_not_rescue_a_pre_barrier_link_case_23_pre"):
        "the subject's seat (`authorize(conn, cfg, subject_order)`); the "
        "three rivals are population, never seats",
    (_T6A, "test_a_later_refire_order_also_competes_case_15f"):
        "the subject's seat",
    (_T6A, "test_a_rival_over_an_incomplete_window_is_unverifiable_case_23b"):
        "the subject's seat",
    (_T6A,
     "test_a_rival_whose_decision_ledger_cannot_be_read_is_unverifiable_case_23c"):
        "the subject's seat",
    (_T6A, "test_a_rival_with_a_null_snapshot_is_unverifiable_case_23d"):
        "the subject's seat",
    (_T6A, "test_two_live_orders_on_one_ticker_are_ambiguous_case_4c_ii"):
        "the subject's seat -- and 4c-ii is the case where BOTH seats give "
        "the SAME reason, which is why it is the cardinality half",
}


def _arc_modules() -> list[Path]:
    return [p for p in sorted(REPO_ROOT.glob(ARC_GLOB))
            if "__pycache__" not in p.parts]


def _reason_pinning_functions() -> dict[tuple[str, str], int]:
    """``(module, test name)`` -> how many order builders its body calls.

    **KEYED BY THE PAIR, NOT BY THE NAME** (Codex 22A-FIX-R1-06).  pytest
    permits identical test names in different modules, so a name-keyed result
    silently overwrites one with the other and a multi-order reason pin can
    disappear from BOTH directions of the roster check at once.  Unexploited
    in the arc today, which is why it is closed rather than reported.
    """
    out: dict[tuple[str, str], int] = {}
    for path in _arc_modules():
        module = path.relative_to(REPO_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not fn.name.startswith("test"):
                continue
            if not _pins_a_reason(fn):
                continue
            calls = 0
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                name = (node.func.id if isinstance(node.func, ast.Name)
                        else getattr(node.func, "attr", ""))
                if name in ORDER_BUILDERS:
                    calls += 1
            out[(module, fn.name)] = calls
    return out


def _multi_order_pins() -> set[tuple[str, str]]:
    return {key for key, calls in _reason_pinning_functions().items()
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
    for key, seat in SEATS.items():
        assert seat.strip(), key
        assert "seat" in seat or "grain" in seat, (
            f"{key}'s entry does not name a seat: {seat!r}")


def test_the_roster_is_keyed_by_MODULE_AND_NAME() -> None:
    """Codex 22A-FIX-R1-06: pytest permits identical test names in different
    modules, so a name-keyed roster silently drops one of a colliding pair --
    from BOTH directions at once.  Every key names a module that exists."""
    for module, name in SEATS:
        assert (REPO_ROOT / module).is_file(), module
        assert name.startswith("test"), name


def test_the_sweep_numbers_and_the_method_that_produced_them() -> None:
    """THE COMPLETENESS CLAIM, WITH ITS METHOD -- and it fails if the walk
    quietly stops matching, which is how a sweep becomes a feeling.

    The floors are floors, not equalities: the arc gains tests, and an
    equality here would make every new reason-pinning test a false red.  What
    must not happen is the count COLLAPSING, which is the direction that would
    make both directions above vacuous.
    """
    pins = _reason_pinning_functions()
    assert len(pins) >= 74, (
        f"the walk finds {len(pins)} reason-pinning tests; it found 74 when "
        f"the sweep was run, so it has stopped matching")
    assert len(_multi_order_pins()) >= 16, len(_multi_order_pins())
    assert ORDER_BUILDERS, "the builder roster is empty; nothing can be multi"


def _first_function(source: str):
    return next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef))


def test_the_walk_can_tell_a_pinning_test_from_a_non_pinning_one() -> None:
    """The matcher's own discriminator, over the shapes it must separate --
    including the two a REGEX could not (Codex 22A-FIX-R1-05).

    The last two rows are the reason this walk is an AST walk: the phrase
    appears in a STRING LITERAL and in a COMMENT, and a source-text regex
    counts both.  This module's own control was one of them, so the sweep's
    floor was inflated by its own test.
    """
    def pins(body: str) -> bool:
        lines = ["def test_x():", "    pass"]
        lines += [f"    {line}" for line in body.splitlines()]
        return _pins_a_reason(_first_function("\n".join(lines) + "\n"))

    assert pins('assert v.decline_reason == "x"')
    assert pins("assert v.decline_reason == 'x'")
    assert not pins("assert v.decline_reason is None")
    assert not pins("assert v.decline_reason != 'x'")
    assert not pins('# the decline_reason == "x" comparison is not made')
    assert not pins("doc = 'decline_reason == x'")
