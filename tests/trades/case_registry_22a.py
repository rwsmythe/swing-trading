"""22-A acceptance-case REGISTRY -- the repaired case-to-task closure instrument.

WHY THIS FILE EXISTS (inherited finding 22A-R9-10, resolved here BEFORE any
arc code was written).  The plan specifies a case-to-task closure check that
"collects every case id named anywhere in S3, S3.7's lens and S5.1's reason
view, collects every case id named in an ACCEPTANCE cell of the ladder, and
asserts the two sets are EQUAL".  Run literally against its own plan that
check FAILS, for six independent reasons -- and one of the six is a defect in
the finding rather than in the plan:

  1. RANGES.  Acceptance cells carry ``35a-35c``, ``48a-48p``, ``cases 1-6``.
     A set-equality check over raw tokens cannot expand them without a stated
     expansion rule.
  2. IMPLICIT FAMILIES.  "their -pre twins" names fourteen ids and spells
     none of them.
  3. CARVED / STRUCK IDS.  S3 still names 32f, 32g, 40a-40f, 46a-46c,
     35d-35m, 45a-45d, 8b, 8c, 53b and the DELETED 28d.  The "static walk"
     does not say how to exclude them.
  4. SOURCE-SET INCOMPLETENESS.  The ladder accepts 33, 35*, 36, 51*, 34*,
     48*, 49*, 31, 37c and 50d/50e, none of which appears in the three
     DECLARED source sections.  The declared source set is not the plan's
     case universe.
  5. LEXICAL INCOMPLETENESS.  S4.3 introduces ``48a-48p`` and ``49a-49i`` in
     bullets that never use the word "case", so a word-anchored scan misses
     them entirely.  A grep bounds this family FROM BELOW; only a read
     establishes it.
  6. THE LENS TABLE CARRIES TWO ID NAMESPACES IN ONE TABLE.  Its LEFT column
     is CLAUSE numbers and its RIGHT column is CASE ids, and the two collide
     lexically (``9b``, ``11b``, ``13c``, ``38b``, ``54`` ...).  This is what
     makes a naive static walk unusable -- and it also falsifies one bullet of
     22A-R9-10 itself, which reports "task 6 still accepts case 11b, which
     S3.7 and S6 mark REMOVED".  S3.7's struck ``~~11b~~`` and S6's "``11b``
     and ``54``" are CLAUSE ROWS.  Case 11b is introduced LIVE by clause row
     13b (``declined`` refuses).  Task 6 accepts it correctly.

THE REPAIR.  A parsed-prose instrument cannot be made deterministic, so the
manifest is established by READ and recorded HERE, machine-readably, with an
explicit reasoned exclusion list -- the recipe's own prescription for a
hand-enumerated roster: "the fix is not the list; it is the CLOSURE CHECK that
walks what the code actually references and asserts every item is either on
the list or on a reasoned exclusion list."

``tests/trades/test_22a_case_closure.py`` runs three directions over it.

OWNERSHIP RULE, stated because three hand passes over the ladder each left
holes by leaving it unstated: **a case is owned by exactly ONE task -- the
EARLIEST task at which its FULL required outcome (as S3 / S3.7 states it) is
assertable.**  A later task may re-exercise a case it does not own.  This is
the ladder's own principle ("a task may only accept cases whose every
dependency has already shipped") turned into a tie-break.
"""
from __future__ import annotations

# --------------------------------------------------------------------------
# ALIASES -- ids the plan uses as a NAME for a pair it later split.
# --------------------------------------------------------------------------
ALIASES: dict[str, tuple[str, ...]] = {
    "4c": ("4c-i", "4c-ii"),        # S3.4c split by review 22A-R15-12
    "4d": ("4d(i)", "4d(ii)"),      # S3.4d names two shapes, (i) and (ii)
    "5": ("5a", "5b"),              # S3.5 split by RD 2026-08-24
    "15d": ("15d-i", "15d-ii"),     # S2.4.1 split by review 22A-R5-04
}

# --------------------------------------------------------------------------
# 22A-R9-09 RE-VERIFIED against the R9-11-restructured ladder (not assumed).
# --------------------------------------------------------------------------
R9_09_REVERIFICATION = """\
HALF (1) -- CLOSED by the R9-11 restructure.  The finding reports "task 2
accepts 50a-50c".  Task 2's acceptance cell on the committed plan reads
"cases 26, 33, 35a-35c, 35n, 35p, 36, 43, 44, 51a-51e" and names no 50*
case; 50a-50e moved to task 3.  Confirmed by reading the cell, not by
assuming the restructure touched it.  Task 3 CAN run them: at task 3 the
one epoch reader ``freeze_tier_for_candidate`` exists and returns
``(tier, barrier_installed)``, which is the grain 50a-50e discriminate at.
The ADMIT/REFUSE language in S2.4d.1 is rung 9's CONSEQUENCE of that tuple,
and rung 9 lands in task 4.

HALF (2) -- CONFIRMED STILL OPEN, and repaired here.  Task 4 accepts
4c-i, 4c-ii and 15f while its own rung list is "1, 2, 3, 3b, 3c, 4, 5, 6, 7
and 9" and the cell states "RUNG 8 IS NOT HERE -- it is task 6a's".  All
three cases are rung-8 cases:
  * 15f  -> two live accepted orders on one ticker -> ``ambiguous_ticker_orders``
            (S5.1's reason view maps that reason to 4c-ii and 15f);
  * 4c-ii -> the same reason, reached the same way;
  * 4c-i  -> requires classifying the OTHER link as PROVEN-DEAD at the fill
            session (S2.4b's three-valued population) and returns
            ``mandate_not_alive`` on the second leg -- so it needs BOTH rung 8
            and ``mandate_alive_at`` (task 6).
REPAIR: all three move to task 6a, which is the ladder's own remedy for the
identical shape one row above them ("Cases 23, 23b-23d MOVE to task 6a --
liveness needs mandate_alive_at and the strict reader parameters").
"""

# --------------------------------------------------------------------------
# What the repaired instrument found BEYOND 22A-R9-10's own bullets.
# --------------------------------------------------------------------------
CLOSURE_FINDINGS = """\
N1  Lens clause row 63 says "cases 48a-48k" (ELEVEN) while S4.3's live
    specification and task 11's acceptance both say 48a-48p ("Sixteen, not
    eleven").  The lens is STALE at the pre-22A-R8-05 count.
N2  Lens clause row 69 says "cases 50a-50c" while S2.4d.1 (CHARC's ruled
    repair of 22A-R9-01) and task 3's acceptance say 50a-50e.  The lens did
    not move when the body check added 50d and 50e.
N3  Case 4b (S3.4b, the price-heuristic discriminator) is named in the lens
    (clause row 3) and in S8-L3 and is in NO acceptance cell.  UNOWNED.
    Assigned to task 4: it needs only the lookup, since no accepted link
    exists for it to authorize.
N4  Case 5c (S3.5c, the corrected-DATE discriminator) is named in the lens
    (clause row 8), in S2.4.2 and in S3.5 and is in NO acceptance cell.
    UNOWNED.  Assigned to task 8 -- the fill session is read from
    ``req.entry_date`` by ``resolve_latched_provenance``.
N5  Case 37b is named in lens clause row 66 and in S5.2-S5.5 and is in NO
    acceptance cell (22A-R9-10 found this one).  Assigned to task 10.
N6  Case 38 is named in lens clause row 45; task 3's acceptance DESCRIBES it
    ("the SQL-vs-Python freeze-tier drift test over SINGLE-STATE fixtures")
    without naming the id, so an id-keyed collector reads it as unowned.
    Assigned to task 3 -- and per 22A-R9-02 it must assert the EXPECTED TIER
    at below / equal / above, not merely that the two spellings agree.
N7  Case 30d is accepted by task 1 and appears in NO lens row: clause rows
    35, 35b and 35c name 30a, 30b and 30c only.  The lens under-covers the
    price rung by exactly the case 22A-R8-07 added.
N8  22A-R9-10's own bullet "task 6 still accepts case 11b, which S3.7 and S6
    mark REMOVED" is FALSE.  ``~~11b~~`` and ``~~54~~`` are LEFT-column
    CLAUSE ROW numbers; case 11b is introduced live by clause row 13b.  The
    two id namespaces in one table are precisely why the naive static walk
    "fails this plan immediately".
N9  The plan's twin roster lists 15d-i, 30b and 30d as twinned.  All three
    are pure-function envelope-guard cases that never reach rung 9, so the
    convention's own scope exempts them -- see TWIN_ROSTER_REPAIR.  Twinning
    them is unbuildable at the task that owns them.
"""

# --------------------------------------------------------------------------
# LIVE MANIFEST -- case id -> owning task id.
# --------------------------------------------------------------------------
PLAN_CASES: dict[str, str] = {}


def _own(task: str, *ids: str) -> None:
    for case_id in ids:
        if case_id in PLAN_CASES:                      # pragma: no cover
            raise AssertionError(
                f"case {case_id} owned twice: {PLAN_CASES[case_id]} and {task}"
            )
        PLAN_CASES[case_id] = task


# Task 1 -- envelope-shape guards: PURE functions over a hand-built order.
_own("1", "15a", "15b", "15c", "15d-i", "15d-ii", "15e",
     "30a", "30b", "30c", "30d")

# Task 2 -- migration 0037, schema grain.
_own("2", "26", "33", "35a", "35b", "35c", "35n", "35p", "36", "43", "44",
     "51a", "51b", "51c", "51d", "51e")

# Task 3 -- models / repos / the ONE epoch reader (S4.5C), reader grain.
_own("3", "25", "38", "50a", "50b", "50c", "50d", "50e")

# Task 4 -- lookup + ten of the eleven rungs.
_own("4", "4", "4b", "4d(i)", "4d(ii)", "13", "14", "22", "22b",
     "29a", "29b", "29c", "29d", "41a", "47a", "47b", "47c",
     "22-pre", "29d-pre")

# Task 5 -- EXT-1: behaviour-preservation only; no plan case ids.

# Task 6 -- mandate_alive_at, probe grain.
_own("6", "7", "7b", "8", "9", "9b", "10", "11", "11b", "11c", "16",
     "19", "20", "24", "27", "28a", "28b", "28c", "28d'", "28e", "28f",
     "41b", "41c", "41d", "41e",
     "8-pre", "10-pre", "24-pre", "27-pre", "28a-pre", "28b-pre", "28c-pre")

# Task 6a -- rung 8, competitor liveness (three-valued).
_own("6a", "4c-i", "4c-ii", "15f", "23", "23b", "23c", "23d",
     "4c-i-pre", "23-pre")

# Task 7 -- derive_cohort_keys_for_fire extraction: no plan case ids.

# Task 8 -- resolver composition.
_own("8", "18", "5c")

# Task 9 -- record_entry wiring, end-to-end / persisted-row grain.
_own("9", "1", "2", "3", "5a", "5b", "6", "12", "21", "21b", "37c",
     "1-pre", "5b-pre", "6-pre")

# Task 10 -- EXT-2, the route.
_own("10", "37", "37b")

# Task 11 -- Demand-C dispatch + the citation trigger's evidence contract.
_own("11", "17", "31",
     "34a", "34b", "34c", "34d", "34e", "34f", "34g",
     "39a", "39b", "39c",
     *[f"48{c}" for c in "abcdefghijklmnop"],
     *[f"49{c}" for c in "abcdefghij"])

# Task 11a -- fill-identity preservation through the split handler.
_own("11a", "22c")

# --------------------------------------------------------------------------
# EXCLUSIONS -- every id the plan names that is NOT a live 22-A case,
# each with the reason that makes it one.
# --------------------------------------------------------------------------
EXCLUDED_CASES: dict[str, str] = {
    "28d": "DELETED as unconstructable (S2.3.1b / SELF-SWEEP SS-01); "
           "replaced by 28d-prime which pins the unreachability",
    "32f": "CARVED to 22-A2 with the tier-2 evidence class (S12)",
    "32g": "CARVED to 22-A2 with the tier-2 time anchor (S12)",
    "40a": "CARVED to 22-A2 (cited_frozen_value_evidence_json, S4.3/S12)",
    "40b": "CARVED to 22-A2 (cited_frozen_value_evidence_json, S4.3/S12)",
    "40c": "CARVED to 22-A2 (cited_frozen_value_evidence_json, S4.3/S12)",
    "40d": "CARVED to 22-A2 (cited_frozen_value_evidence_json, S4.3/S12)",
    "40e": "CARVED to 22-A2 (cited_frozen_value_evidence_json, S4.3/S12)",
    "40f": "CARVED to 22-A2 with clause row 54 (uncovered_seconds)",
    "46a": "CARVED to 22-A2 (tier-2 exemption roster, S3 convention)",
    "46b": "CARVED to 22-A2 (tier-2 exemption roster, S3 convention)",
    "46c": "CARVED to 22-A2 (tier-2 exemption roster, S3 convention)",
    "35d": "ERA behaviour; travels to 22-A2 (S4.5C)",
    "35e": "ERA behaviour; travels to 22-A2 (S4.5C)",
    "35f": "ERA behaviour (spurious lower re-arm); travels to 22-A2",
    "35g": "ERA behaviour (CHARC's retirement case); travels to 22-A2",
    "35h": "retirement-window byte-identical restore twin; travels to 22-A2",
    "35i": "ERA behaviour; travels to 22-A2",
    "35j": "ERA behaviour; travels to 22-A2",
    "35k": "ERA behaviour; travels to 22-A2",
    "35l": "ERA behaviour; travels to 22-A2",
    "35m": "ERA behaviour; travels to 22-A2",
    "45a": "STRUCK with RD's withdrawal of the session-inclusive carve-out",
    "45b": "STRUCK with RD's withdrawal of the session-inclusive carve-out",
    "45c": "STRUCK with RD's withdrawal of the session-inclusive carve-out",
    "45d": "STRUCK with RD's withdrawal of the session-inclusive carve-out",
    "8b": "STRUCK -- R6-05's fill-session-close companion, withdrawn",
    "8c": "STRUCK -- R6-05's fill-session-close companion, withdrawn",
    "53b": "historical reference to a case in a withdrawn revision (header)",
    "1-tier2": "CARVED to 22-A2 -- there is no tier-2 in this arc",
    "54": "lens LEFT-column clause row, struck; NOT a case id",
    # --- twin-roster repairs; see TWIN_ROSTER_REPAIR below ----------------
    "15d-i-pre": "EXEMPT: 15d-i is a PURE-function envelope-guard case that "
                 "never reaches rung 9; the S3 convention's own scope is "
                 "'resolver cases admitted through ordinary latch_ladder "
                 "authority, which is what rung 9 governs'",
    "30b-pre": "EXEMPT: same reason as 15d-i-pre (pure-function price guard)",
    "30d-pre": "EXEMPT: same reason as 15d-i-pre (pure-function price guard)",
}

# Tokens the extractor sees that are GROUP references or prose, never ids.
NON_CASE_TOKENS: frozenset[str] = frozenset({"48", "49"})

TWIN_ROSTER_REPAIR = """\
The plan's twin-roster closure output lists SEVENTEEN admitting cases:
1, 4c-i, 5b, 6, 8, 10, 15d-i, 22, 23, 24, 27, 28a, 28b, 28c, 29d, 30b, 30d.

THREE of them -- 15d-i, 30b and 30d -- are cases on
``assert_fill_consistent_with_order``, a PURE function over a hand-constructed
``AcceptedLatchOrder`` (task 1, S7).  They never reach rung 9, so by the
convention's OWN stated scope two paragraphs above the roster ("the convention
applies to exactly one population: resolver cases admitted through ordinary
``latch_ladder`` authority, which is what rung 9 governs") they are EXEMPT.
Twinning them is not merely redundant -- it is unbuildable at the task that
owns them, which is the 22A-R7-09 class recurring inside the fix for it.

FOURTEEN twins are live: 1-pre, 4c-i-pre, 5b-pre, 6-pre, 8-pre, 10-pre,
22-pre, 23-pre, 24-pre, 27-pre, 28a-pre, 28b-pre, 28c-pre, 29d-pre.
"""

# Cases the arc does NOT build.  Every entry is a DECLARED DEVIATION and is
# reported to the orchestrator.  An empty dict is the intended end state.
DEFERRED_CASES: dict[str, str] = {}


def slug(case_id: str) -> str:
    """Canonical test-name suffix for a case id.

    ``4d(i)`` -> ``4d_i``; ``28d'`` -> ``28d_prime``; ``5b-pre`` -> ``5b_pre``.
    """
    return (
        case_id.replace("(", "_").replace(")", "")
        .replace("'", "_prime").replace("-", "_")
    )
