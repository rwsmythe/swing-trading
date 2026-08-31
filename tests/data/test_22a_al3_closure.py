"""AL-3 IS CLOSURE-CHECKED, NOT HAND-MAINTAINED (operator-ruled 2026-08-27).

AL-3 -- limitation **L17** in the arc plan -- declares which citation-trigger
clauses are SERVICE-VALIDATED: SQL asserts presence, type and verdict, and the
judgment rests on state no subquery can reach.  It has always ended with the
words *"AL-3's roster is exactly those three."*

**THAT ROSTER HAS BEEN WRONG THREE TIMES, IN BOTH DIRECTIONS, AND THE MIGRATION
RECORDS THE FIRST AGAINST ITSELF.**  ``22A-R9-05`` found a migration comment
citing AL-3 for a clause AL-3 does not name -- *"silently broadened a declared
limitation roster to cover something nobody had ruled on"*
(``0037:1279-1283``).  ``SS-12`` found the no-REPLACE barrier roster one member
short of what the schema installs.  ``22A-R12-02``/``22A-R12-03`` found AL-3
short by two.

The implementer's own sentence at ``SS-12`` is the instruction this file
encodes: **the roster is not the fix; the closure check is.**  So there is
exactly ONE hand-written AL-3 roster in the repo -- the marked region inside
L17 -- and this module holds it against what the CODE actually classifies and
what the MIGRATION actually binds, **in both directions**.  A clause added
later as service-validated without an L17 entry fails here; an L17 entry
claiming a clause the code calls SQL-bound fails here; an L17 entry whose
declared axis disagrees with the migration fails here.

WHAT THE CHECK FOUND ON ITS FIRST RUN, recorded because a closure check that
never reported anything would be indistinguishable from a decorative one:

  * ``fill_session_is_session`` -- classified ``SERVICE_VALIDATED`` in
    ``PROBE_GUARD_CLAUSES`` since ``22A-R6-06``, with a comment explaining that
    no subquery can enumerate the NYSE calendar, and named NOWHERE in AL-3.
    Its acceptance was already pinned by an executing test.  **The code was
    truthful and the declaration was not** -- which is the exact defect this
    arc spent twelve rounds eliminating everywhere else.
  * the anchoring-fill clause -- service-validated in AL-3's own sense and
    outside both blob rosters, so no amount of walking the blob rosters would
    ever have surfaced it; it is declared as a NON-BLOB member and carries its
    anchor in the migration text.
  * L17's PROSE was additionally stale in a THIRD way nobody had reported: it
    said *"rungs 7 and 8 and the five envelope guards ... these seven"* and
    *"the nine SQL-bound rungs"*, while the shipped migration SQL-binds all
    five envelope guards at correction time.  Measured: 14 SQL-bound and 5
    service-validated of 19 clauses, not 9 and 7 of 16.

FROZEN CLOCK: nothing here reads a clock.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from swing.trades.latched_origin import (
    AUTHORIZATION_CLAUSES,
    PROBE_GUARD_CLAUSES,
    SERVICE_VALIDATED,
    SQL_BOUND,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_0037 = (
    REPO_ROOT / "swing" / "data" / "migrations"
    / "0037_latch_order_mandate_links.sql"
)
PLAN = (
    REPO_ROOT / "docs" / "superpowers" / "plans"
    / "2026-08-24-phase22-arc-a-entry-path-order-mandate-binding.md"
)

ALL_CLAUSES = AUTHORIZATION_CLAUSES + PROBE_GUARD_CLAUSES
BY_KEY = {c.key: c for c in ALL_CLAUSES}

# The axis vocabulary.  A two-valued SQL_BOUND/SERVICE_VALIDATED label cannot
# say WHICH half is unproved -- ``decision_ordering``'s own comment says so in
# the source -- and that ambiguity is precisely how a clause whose INPUT is
# bound and whose VERDICT is not went unnamed for eleven dispatches.
INPUT_UNBOUND = "INPUT_UNBOUND"
VERDICT_UNPROVEN = "VERDICT_UNPROVEN"
PREDICATE_WEAKER = "PREDICATE_WEAKER_THAN_THE_SERVICE"
SET_INCOMPLETE = "SET_INCOMPLETE"
AXES = (INPUT_UNBOUND, VERDICT_UNPROVEN, PREDICATE_WEAKER, SET_INCOMPLETE)

# Axes whose members are blob clauses and must therefore be SERVICE_VALIDATED
# in the code roster.
_BLOB_AXES = (INPUT_UNBOUND, VERDICT_UNPROVEN, SET_INCOMPLETE)


# ---------------------------------------------------------------------------
# The plan's marked regions -- the ONE hand-written roster.
# ---------------------------------------------------------------------------
_REGION = "<!-- AL3-{name}-{edge} -->"
_BACKTICK = re.compile(r"`([^`]+)`")


def _region(name: str) -> str:
    text = PLAN.read_text(encoding="utf-8")
    begin, end = _REGION.format(name=name, edge="BEGIN"), _REGION.format(
        name=name, edge="END")
    assert begin in text and end in text, (
        f"the plan carries no AL-3 {name} region; L17 is the ONE place the "
        f"roster is written and this check cannot verify a roster that is not "
        f"there")
    return text.split(begin, 1)[1].split(end, 1)[0]


def _bullets(region: str) -> list[str]:
    out: list[str] = []
    for line in region.splitlines():
        if line.lstrip().startswith("* "):
            out.append(line.strip()[2:])
        elif out and line.strip():
            out[-1] += " " + line.strip()
    return out


def _parse(region: str) -> dict[str, dict[str, str | None]]:
    entries: dict[str, dict[str, str | None]] = {}
    for bullet in _bullets(region):
        ticks = _BACKTICK.findall(bullet)
        assert ticks, f"an AL-3 bullet names no clause: {bullet[:80]!r}"
        key = ticks[0]
        axes = [a for a in AXES if a in bullet]
        assert len(axes) == 1, (
            f"AL-3 entry `{key}` must name EXACTLY ONE axis from {AXES}; "
            f"found {axes}")
        pin = re.search(r"PIN: `([^`]+)`", bullet)
        anchor = re.search(r"ANCHOR: `([^`]+)`", bullet)
        assert pin, (
            f"AL-3 entry `{key}` carries no PIN. A declared limitation with no "
            f"executing test is an unfalsifiable claim -- the convention L18 "
            f"states and this check enforces on every member")
        assert key not in entries, f"AL-3 names `{key}` twice"
        entries[key] = {
            "axis": axes[0],
            "pin": pin.group(1),
            "anchor": anchor.group(1) if anchor else None,
        }
    return entries


def _roster() -> dict[str, dict[str, str | None]]:
    return _parse(_region("ROSTER"))


def _exclusions() -> dict[str, dict[str, str | None]]:
    return _parse(_region("EXCLUSIONS"))


# ---------------------------------------------------------------------------
# The migration half -- what the SQL actually binds.
# ---------------------------------------------------------------------------
_TRIGGER = "CREATE TRIGGER trg_provenance_corrections_citation_graph"
# `\\s*` BETWEEN THE PAREN AND `SELECT` IS LOAD-BEARING, and its absence was a
# live defect in THIS walk on its first run: SQL wraps long subqueries, so
# `NOT EXISTS (` followed by `SELECT 1` on the next line is the ordinary
# spelling -- and `decision_ordering`, whose every supplied pair IS bound by
# subquery, measured UNBOUND.  The same multi-line-spelling class as
# `22A-R12-04`, reappearing inside the instrument written to close it, and
# caught only because the axis is asserted in BOTH directions.
_BOUND_TO_A_SOURCE = re.compile(
    r"\(\s*SELECT|NEW\.(?!cited_latch_probe_json)\w+")


def _when_body() -> list[str]:
    """The citation trigger's WHEN clause, comment lines blanked.

    Blanked rather than dropped so a clause's span cannot silently absorb its
    neighbour's prose, and so a comment DESCRIBING a binding is never mistaken
    for one.
    """
    lines = MIGRATION_0037.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(_TRIGGER))
    end = next(i for i in range(start, len(lines)) if lines[i] == "BEGIN")
    return ["" if ln.lstrip().startswith("--") else ln
            for ln in lines[start:end]]


def _spans() -> dict[str, tuple[int, int]]:
    """Each clause key's span in the WHEN body, in file order.

    A span runs from the key's first mention to the NEXT key's first mention;
    the LAST key runs to the end of the WHEN body.  Getting that final boundary
    wrong is not hypothetical -- a first draft of this walk ended the last span
    at its own last mention and reported ``guard_broker_limit_bound``
    UNBOUND, because the subquery binding it sits on the following lines.
    """
    body = _when_body()
    first: dict[str, int] = {}
    for clause in ALL_CLAUSES:
        block = ("probe_guards" if clause in PROBE_GUARD_CLAUSES
                 else "authorization")
        needle = f"$.{block}.{clause.key}"
        hits = [i for i, ln in enumerate(body) if needle in ln]
        assert hits, (
            f"clause `{clause.key}` is in the Python roster and appears "
            f"NOWHERE in the citation trigger")
        first[clause.key] = hits[0]
    order = sorted(first, key=lambda k: first[k])
    spans: dict[str, tuple[int, int]] = {}
    for i, key in enumerate(order):
        end = first[order[i + 1]] if i + 1 < len(order) else len(body)
        spans[key] = (first[key], end)
    return spans


def _input_bound() -> dict[str, bool]:
    """Does the migration bind this clause's recorded input to a SOURCE?

    A source is a subquery or a ``NEW.<column>`` other than the probe blob
    itself -- reading the blob is reading the writer's own claim, which is the
    whole thing AL-3 says is not proof.
    """
    body = _when_body()
    spans = _spans()
    return {key: bool(_BOUND_TO_A_SOURCE.search("\n".join(body[a:b])))
            for key, (a, b) in spans.items()}


# ---------------------------------------------------------------------------
# THE CLOSURE, IN BOTH DIRECTIONS
# ---------------------------------------------------------------------------
def test_every_service_validated_clause_is_declared_or_excluded() -> None:
    """DIRECTION 1: nothing the code calls service-validated is unnamed.

    This is the direction that fired on the first run.  A clause added later
    with ``binding=SERVICE_VALIDATED`` and no L17 entry NARROWS a declared
    limitation silently -- the reader concludes SQL proved something it did
    not -- and it now fails loudly instead.
    """
    declared = set(_roster()) | set(_exclusions())
    service_validated = {c.key for c in ALL_CLAUSES
                         if c.binding == SERVICE_VALIDATED}
    missing = sorted(service_validated - declared)
    assert not missing, (
        f"these clauses are SERVICE_VALIDATED in the code and named nowhere "
        f"in AL-3: {missing}. AL-3 declares its roster EXACT, so an omission "
        f"is a false claim in the document whose entire job is to state what "
        f"is true")


def test_every_declared_blob_member_is_service_validated_in_the_code() -> None:
    """DIRECTION 2: nothing AL-3 claims is actually SQL-bound.

    The failure this catches is ``22A-R9-05``'s, from the other end: a roster
    BROADENED to cover a clause nobody ruled on.  A member the code SQL-binds
    would make AL-3 understate what the trigger proves, which reads as
    conservative and is simply false.
    """
    wrong: dict[str, str] = {}
    for key, entry in (_roster() | _exclusions()).items():
        if entry["axis"] == PREDICATE_WEAKER:
            continue
        assert key in BY_KEY, (
            f"AL-3 names `{key}` on a blob axis and it is not a clause in "
            f"AUTHORIZATION_CLAUSES or PROBE_GUARD_CLAUSES")
        if BY_KEY[key].binding != SERVICE_VALIDATED:
            wrong[key] = BY_KEY[key].binding
    assert not wrong, (
        f"AL-3 declares these service-validated and the code SQL-binds them: "
        f"{wrong}")


def test_a_non_blob_member_names_an_anchor_that_exists_in_0037() -> None:
    """A member outside both blob rosters must still be findable.

    The anchoring-fill clause is not a ``$.authorization`` entry, so no walk
    over the blob rosters could ever surface it -- which is exactly why it
    survived eleven dispatches.  Its declaration therefore carries a verbatim
    ANCHOR into the migration, held here so the entry cannot rot into a
    reference to text that no longer exists.
    """
    sql = MIGRATION_0037.read_text(encoding="utf-8")
    non_blob = {k: e for k, e in _roster().items()
                if e["axis"] == PREDICATE_WEAKER}
    assert non_blob, (
        "no NON-BLOB member is declared, so this check is vacuous and the "
        "anchoring-fill clause has quietly left the roster")
    for key, entry in non_blob.items():
        assert key not in BY_KEY, (
            f"`{key}` is declared NON-BLOB and IS a blob clause")
        assert entry["anchor"], f"non-blob member `{key}` carries no ANCHOR"
        assert entry["anchor"] in sql, (
            f"non-blob member `{key}`'s ANCHOR is not in 0037 verbatim: "
            f"{entry['anchor']!r}")


@pytest.mark.parametrize("key", sorted(_roster() | _exclusions()))
def test_every_al3_member_is_pinned_by_a_test_that_exists(key: str) -> None:
    """Every declared limitation is EXERCISED, never merely written down.

    L18 states the convention -- *"Pinned, not merely written down"* -- and
    AL-3b and 49j already follow it.  Enforcing it on every member is what
    stops the roster from growing entries nobody can falsify: the pin is the
    thing that fails if a later change makes the limitation narrower than the
    declaration.
    """
    pin = (_roster() | _exclusions())[key]["pin"]
    assert pin and "::" in pin, f"`{key}`'s PIN is not a node id: {pin!r}"
    path, func = pin.split("::", 1)
    module = REPO_ROOT / path
    assert module.is_file(), f"`{key}`'s PIN names a missing file: {path}"
    assert f"def {func}(" in module.read_text(encoding="utf-8"), (
        f"`{key}`'s PIN names `{func}`, which is not defined in {path}")


# ---------------------------------------------------------------------------
# THE MIGRATION HALF -- the declared axis against what the SQL actually does
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "key", sorted(c.key for c in ALL_CLAUSES if c.binding == SQL_BOUND))
def test_every_sql_bound_clause_really_binds_its_input(key: str) -> None:
    """A label is a claim, and this is the claim measured.

    ``22A-R6-06`` found ``fill_session_is_session`` labelled SQL_BOUND while
    the trigger checked only that its verdict read ``pass``.  A false label is
    worse than a declared limit: an auditor reading the roster concludes the
    predicate was proved.  So every SQL_BOUND clause must have a subquery or a
    ``NEW.<column>`` binding somewhere in its own span.
    """
    assert _input_bound()[key], (
        f"`{key}` is labelled {SQL_BOUND} and its span in the citation "
        f"trigger binds nothing to a source -- the label claims a proof the "
        f"SQL does not contain")


@pytest.mark.parametrize("key", sorted(_roster() | _exclusions()))
def test_the_declared_axis_agrees_with_the_migration(key: str) -> None:
    """The axis is not a free-text opinion; the SQL decides half of it.

    ``INPUT_UNBOUND`` means the migration binds NOTHING for this clause, and
    ``VERDICT_UNPROVEN``/``SET_INCOMPLETE`` mean it DOES bind the input and
    stops short of the predicate.  Asserting both directions is what stops the
    axis from becoming a label anyone can pick: a clause whose input quietly
    gains a binding can no longer keep saying ``INPUT_UNBOUND``, and one whose
    binding is quietly removed can no longer keep saying ``VERDICT_UNPROVEN``.
    """
    entry = (_roster() | _exclusions())[key]
    if entry["axis"] == PREDICATE_WEAKER:
        pytest.skip("a non-blob member has no $.authorization span")
    bound = _input_bound()[key]
    if entry["axis"] == INPUT_UNBOUND:
        assert not bound, (
            f"`{key}` is declared INPUT_UNBOUND and the migration DOES bind "
            f"its input; the declaration understates what SQL proves")
    else:
        assert bound, (
            f"`{key}` is declared {entry['axis']}, which asserts the INPUT is "
            f"bound and only the predicate is not -- and the migration binds "
            f"nothing, so the correct axis is INPUT_UNBOUND")


def test_the_measured_split_is_stated_and_not_paraphrased() -> None:
    """The COUNTS, because L17's prose carried two stale ones for eleven
    dispatches (nine SQL-bound, seven service-validated) while the shipped
    migration said something else.

    A count in prose is a paraphrase of a fact, and paraphrases rot silently.
    This is the fact.
    """
    sql_bound = [c.key for c in ALL_CLAUSES if c.binding == SQL_BOUND]
    service = [c.key for c in ALL_CLAUSES if c.binding == SERVICE_VALIDATED]
    assert len(ALL_CLAUSES) == 19
    assert len(sql_bound) == 14
    assert len(service) == 5
    blob_members = {k for k, e in _roster().items()
                    if e["axis"] in _BLOB_AXES} | set(_exclusions())
    assert sorted(service) == sorted(blob_members), (
        "the code's service-validated set and AL-3's blob members are the "
        "SAME set stated twice; they have just disagreed")


# ---------------------------------------------------------------------------
# THE CHECK'S OWN DISCRIMINATORS -- an instrument whose evasion case is
# untested is the same defect one level down.
# ---------------------------------------------------------------------------
def test_an_undeclared_service_validated_clause_FAILS_the_closure() -> None:
    """The red step, performed rather than promised.

    A synthetic clause is added to the derived set and the closure assertion
    is re-computed by hand exactly as the test above computes it.  Without
    this, a roster that happened to match today would read identically to one
    that can never report anything.
    """
    declared = set(_roster()) | set(_exclusions())
    service_validated = {c.key for c in ALL_CLAUSES
                         if c.binding == SERVICE_VALIDATED}
    service_validated.add("rung10_a_clause_nobody_declared")
    assert sorted(service_validated - declared) == [
        "rung10_a_clause_nobody_declared"]


def test_a_declared_member_the_code_SQL_BINDS_fails_the_reverse_closure(
) -> None:
    """The other direction's red step -- ``22A-R9-05``'s failure shape."""
    wrong = {k: BY_KEY[k].binding
             for k in list(_roster()) + ["rung1_link_ticker"]
             if k in BY_KEY and BY_KEY[k].binding != SERVICE_VALIDATED}
    assert wrong == {"rung1_link_ticker": SQL_BOUND}


def test_the_boundness_walk_can_tell_the_two_apart() -> None:
    """The migration walk's own discriminator.

    A walk that answered ``True`` for everything would make the axis check
    vacuous while reading as a guarantee, and a walk that answered ``False``
    for everything would make the SQL_BOUND family fail loudly for the wrong
    reason.  Both answers must actually occur, on the clauses whose status is
    not in dispute.
    """
    bound = _input_bound()
    assert bound["rung1_link_ticker"] is True
    assert bound["guard_broker_limit_bound"] is True     # the LAST span
    assert bound["rung7_consumption_scan_fill_ids"] is False
    assert bound["fire_membership"] is False
    assert set(bound.values()) == {True, False}


# ===========================================================================
# THIS CHECK IS A **HEURISTIC DETECTOR**, AND THIS IS ITS DECLARED RESIDUAL
# BLINDNESS (22A-R13-05; operator-ruled 2026-08-31).
#
# DECLARE, DO NOT WIDEN -- and the ground is the same one that governs the two
# envelope walks.  The proposed fix is "make each SQL-bound clause assert its
# specific authoritative operand and predicate shape", which is a per-clause
# assertion for NINETEEN clauses along the one axis the finding named: the
# unbounded widening that answers the example rather than the class.  The
# reviewer that raised it also reported that it looked for a MISLABELLED
# member and found NONE, so what is recorded here is test QUALITY, not a
# demonstrated present acceptance.
#
# WHAT THE CHECK DOES ESTABLISH, and it earned its place on its first run:
# it found `fill_session_is_session` service-validated in the code and named
# NOWHERE in AL-3, found the anchoring-fill clause that no walk over the blob
# rosters could ever have surfaced, found two stale prose counts, found a
# declared member with no acceptance pin at all, and found a defect in its own
# boundness walk through its own both-directions assertion.
#
# WHAT IT CANNOT ESTABLISH, named one by one:
#
#   1. THAT A BOUND OPERAND IS THE *AUTHORITATIVE* ONE, or that the predicate
#      over it proves the service's rule.  `_input_bound()` asks only whether
#      the clause's span contains a subquery or a non-probe `NEW.` reference.
#      The pin below MEASURES this: rung 3b keeps its `SELECT` and loses the
#      ordering that makes it the LATEST validity child, and the walk still
#      answers True.
#   2. THAT THE SELF-DISCRIMINATORS EXERCISE THE PRODUCTION INPUT.  Two of the
#      three mutate locally reconstructed sets rather than the real roster or
#      migration.  (The instrument written AFTER this one --
#      `tests/data/test_22a_canonicalizer_version_closure.py` -- splices into
#      the REAL migration text instead, which is the pattern 22-A2 should
#      apply here uniformly rather than one of three by hand at round 14.)
#   3. THAT A PIN IS COLLECTED BY PYTEST OR ASSERTS AN ACCEPTANCE.  The pin
#      check proves a `def` of that name exists in that file.
#
# ROUTED TO 22-A2 with the two envelope walks (plan S12.4): predicate-shape
# assertions, real-input discriminators, and pins validated through collection.
# ===========================================================================
def test_DECLARED_the_boundness_walk_cannot_see_a_WEAKENED_predicate(
        tmp_path, monkeypatch) -> None:
    """The declared blind spot, measured on the REAL migration text.

    Rung 3b binds its recorded input to *the LATEST validity child of the
    cited place intent*.  Strip the ordering and the limit -- leaving the
    `SELECT` -- and it binds to ANY validity child, which is strictly weaker
    than the service.  ``_input_bound()`` cannot tell the two apart.

    DIRECTION, deliberately: this asserts the walk STILL answers True.  If a
    later change makes it answer False, the walk has become sharper than this
    declaration says -- correct the declaration, never silence the test.
    """
    weakened = MIGRATION_0037.read_text(encoding="utf-8").replace(
        "                   AND x.intent_kind = 'validity'\n"
        "                 ORDER BY x.recorded_ts DESC, x.intent_id DESC "
        "LIMIT 1)",
        "                   AND x.intent_kind = 'validity')", 1)
    assert weakened != MIGRATION_0037.read_text(encoding="utf-8"), (
        "the weakening matched nothing, so this measures nothing")
    copy = tmp_path / "0037_weakened.sql"
    copy.write_text(weakened, encoding="utf-8")
    monkeypatch.setattr(
        "tests.data.test_22a_al3_closure.MIGRATION_0037", copy)
    assert _input_bound()["rung3b_latest_validity_child"] is True, (
        "the walk now distinguishes a weakened predicate; the declaration "
        "above is stale and must be corrected")
