"""THE CANONICALISER VERSION IS RECORDED AND NOTHING READS IT (22A-R13-02).

`canonicalizer_version` appeared EXACTLY ONCE in migration 0037 -- its column
declaration -- while SEVEN sites referenced `fill_envelope_identity`.  The
round-12 rung-6 population clause became the seventh by copying its
neighbour's shape INCLUDING its omission, which is why the treatment here is
the CLASS and not the clause: *state the class once, then re-grep the whole
artifact.*

**THE RE-READ FOUND THAT THE OBVIOUS CLASS-WIDE FIX IS WRONG AT TWO OF THE
SEVEN.**  `last_word_subject_order_id` and `rung6_consumption_scan` consume a
stored reading as EVIDENCE OF ABSENCE, so filtering them on the version makes
a stale reading INVISIBLE and WIDENS acceptance; and the append-only conflict
barrier addresses the UNIQUE KEY rather than a reading, where a version filter
would admit a second row for the same document.  A blanket sweep of "all
seven" would have shipped both.  At the remaining four a version filter
manufactures a REFUSAL on the SERVICE path, because an AGREEING older reading
is deliberately left alone (`test_an_agreeing_older_reading_is_left_alone`).
Full reasoning, both halves measured: plan limitation **L19 (AL-11)**.

SO THIS MODULE DOES TWO THINGS:

1. **THE ARMING TRIPWIRE -- AND IT IS A LABEL COMPARATOR, NOT A STALENESS
   DETECTOR (declared 22A-R14-01; operator-ruled 2026-08-31).**  It compares
   `ENVELOPE_CANONICALIZER_VERSION` to the migration's
   `CANONICALIZER-VERSION-ANCHOR` marker, so **it detects a LABEL DISAGREEMENT
   between two hand-maintained copies -- it does NOT detect a BEHAVIOUR
   CHANGE.  A canonicaliser edit that changes what the function ANSWERS,
   without a version bump, is INVISIBLE to it.**  That is not a hypothetical:
   **this arc is its own counterexample.**  `22A-R13-01` made
   `canonical_envelope_identity` answer `refused` where it answered
   `canonical` for every non-`str` document, the constant did not move, and
   this tripwire -- shipped in the very next commit -- passed.  For six
   commits the migration carried a claim its own arc had already falsified.
   Declared here rather than widened, because *"do not claim exact when you
   are not"* is the principle, and a comparator over the canonicaliser's
   ANSWERS is a different instrument: it is routed to 22-A2 (plan S12.2b)
   with R14-01 as its founding evidence.  What the tripwire DOES buy is real
   and is measured below: a bump fails the suite, with the required work
   named, before a stale row can exist.  A comment promising future work is
   unenforceable (gotcha #31); a failing test is not, and the comparator is
   the only mirror that defends a set (gotcha #11).
2. **THE CLOSURE WALK.**  Every `FROM`/`JOIN` reference to the table in 0037
   carries an inline `-- FEI-CONSUMER <key> :: <claim>` marker.  Markers and
   references must INTERLEAVE one-for-one; each marker's CLAIM is measured
   against what its span actually contains; and the marker set is held against
   L19's roster in BOTH directions.

FROZEN CLOCK: nothing here reads a clock.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from swing.trades.latched_origin import ENVELOPE_CANONICALIZER_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_0037 = (
    REPO_ROOT / "swing" / "data" / "migrations"
    / "0037_latch_order_mandate_links.sql"
)
PLAN = (
    REPO_ROOT / "docs" / "superpowers" / "plans"
    / "2026-08-24-phase22-arc-a-entry-path-order-mandate-binding.md"
)
FEI_REPO = (
    REPO_ROOT / "swing" / "data" / "repos" / "fill_envelope_identity.py"
)

VERSION_COLUMN = "canonicalizer_version"
ANCHOR = re.compile(r"CANONICALIZER-VERSION-ANCHOR:\s*(\S+)")
MARKER = re.compile(r"--\s*FEI-CONSUMER\s+(\w+)\s*::\s*(\w+)")
# A REAL TABLE REFERENCE, never a mention.  `FROM`/`JOIN` is what distinguishes
# a query over the table from its CREATE TABLE, its CREATE INDEX, the three
# `... ON fill_envelope_identity` trigger targets, and the table NAME inside
# each barrier's RAISE message -- all of which name it and none of which reads
# a row.  Measured: the file contains sixteen mentions and SEVEN references.
REFERENCE = re.compile(r"\b(?:FROM|JOIN)\s+fill_envelope_identity\b")

NOT_A_READING = "NOT_A_READING"
VERSION_BLIND = "VERSION_BLIND"
VERSION_CHECKED = "VERSION_CHECKED"
CLAIMS = frozenset({NOT_A_READING, VERSION_BLIND, VERSION_CHECKED})


def _sql() -> str:
    return MIGRATION_0037.read_text(encoding="utf-8")


def _blanked(text: str) -> list[str]:
    """Comment lines blanked, never dropped, so line numbers stay TRUE.

    Blanked rather than removed for the same reason the sibling walks blank:
    a reported line number that does not match the file is a defect one level
    down, and prose describing a reference must not read as one.
    """
    return ["" if ln.lstrip().startswith("--") else ln
            for ln in text.splitlines()]


SEEDING_INSERT = re.compile(
    r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+fill_envelope_identity\b", re.IGNORECASE)


def _seeding_inserts(blanked_body: str) -> list[str]:
    """Every INSERT into the table, over COMMENT-BLANKED, JOINED text.

    Joined rather than per-line for 22A-R14-03's reason: a statement split
    across lines is one statement, and `\\s+` crosses a newline.
    """
    return SEEDING_INSERT.findall(blanked_body)


def _markers(text: str) -> list[tuple[int, str, str]]:
    """``(1-based line, key, claim)`` for every inline marker, in file order."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        m = MARKER.search(line)
        if m:
            out.append((i, m.group(1), m.group(2)))
    return out


def _references(text: str) -> list[int]:
    """1-based line numbers of every FROM/JOIN reference, in file order."""
    return [i for i, line in enumerate(_blanked(text), 1)
            if REFERENCE.search(line)]


def _span_checks_version(text: str, start: int, end: int) -> bool:
    """Does the reference's own span filter on ``canonicalizer_version``?

    THE END BOUNDARY IS THE NEXT REFERENCE, and for the LAST reference it is
    the end of the enclosing statement -- a line that is `BEGIN`, `END;` or a
    new top-level `CREATE`.  Getting that final boundary wrong is not
    hypothetical: the AL-3 walk's first draft ran its last span to its own last
    mention and reported a bound clause UNBOUND.
    """
    body = _blanked(text)
    return VERSION_COLUMN in "\n".join(body[start - 1:end - 1])


def _statement_end(text: str, start: int) -> int:
    body = _blanked(text)
    for i in range(start, len(body)):
        stripped = body[i].strip()
        if stripped in ("BEGIN", "END;") or stripped.startswith("CREATE "):
            return i + 1
    return len(body) + 1


def _measured() -> dict[str, str]:
    """key -> the claim the SQL ACTUALLY supports, walked from the file."""
    text = _sql()
    marks, refs = _markers(text), _references(text)
    out: dict[str, str] = {}
    for i, (mline, key, _claim) in enumerate(marks):
        ref = refs[i]
        end = (refs[i + 1] if i + 1 < len(refs)
               else _statement_end(text, ref))
        assert mline < ref, (
            f"marker `{key}` at line {mline} does not precede its reference "
            f"at {ref}")
        out[key] = (VERSION_CHECKED if _span_checks_version(text, ref, end)
                    else VERSION_BLIND)
    return out


def _roster() -> dict[str, str]:
    """L19's roster: key -> declared claim, from the ONE marked region."""
    body = PLAN.read_text(encoding="utf-8")
    begin = body.index("<!-- AL11-ROSTER-BEGIN -->")
    end = body.index("<!-- AL11-ROSTER-END -->")
    region = body[begin:end]
    entries: dict[str, str] = {}
    for bullet in re.finditer(r"\*\s+`(\w+)`\s+--\s+(\w+)\s+--", region):
        key, claim = bullet.group(1), bullet.group(2)
        assert key not in entries, f"L19 names `{key}` twice"
        assert claim in CLAIMS, f"L19 gives `{key}` an unknown claim: {claim}"
        entries[key] = claim
    assert entries, "L19's roster region parsed to nothing"
    return entries


# ---------------------------------------------------------------------------
# 1. THE ARMING TRIPWIRE
# ---------------------------------------------------------------------------
def test_the_migration_anchor_MIRRORS_the_python_constant() -> None:
    """THE DECLARED-LABEL COMPARATOR -- it fails loudly on a LABEL move.

    Every consumer in 0037 was written against ONE canonicaliser grammar.  A
    stored reading can only become STALE if this constant moves between two
    writes -- a row bearing a version nobody ever shipped is a FORGED identity
    row, which is L10/AL-10's declared class, not this one.

    So the day someone bumps the constant, this fails, and the message says
    what the bump now owes: 22-A2's append-only re-attestation, or a migration
    that re-creates the six consumers against the new grammar.  A version
    filter in the triggers is NOT the remedy -- L19 measures why, in both of
    its halves.

    **WHAT IT DOES NOT DO, stated at the assertion rather than a section
    away:** it compares two hand-maintained copies of a LABEL.  A
    canonicaliser edit that changes the ANSWER without moving the label passes
    it, and `test_DECLARED_a_behaviour_change_WITHOUT_a_bump_is_invisible`
    measures exactly that on this very function.
    """
    found = ANCHOR.search(_sql())
    assert found, (
        "0037 carries no CANONICALIZER-VERSION-ANCHOR; without it the mirror "
        "has one representation and cannot drift-check anything")
    assert found.group(1) == ENVELOPE_CANONICALIZER_VERSION, (
        f"the canonicaliser was bumped to "
        f"{ENVELOPE_CANONICALIZER_VERSION!r} while 0037's consumers were "
        f"written against {found.group(1)!r}. Every stored reading taken "
        f"under the older grammar is now UNVERIFIABLE BY SQL, and the six "
        f"trigger consumers accept it (plan L19). Do NOT simply update this "
        f"anchor: a bump owes either 22-A2's append-only re-attestation "
        f"design or a migration that re-attests the population. THE ONE "
        f"EXCEPTION, and it is a FACT rather than a judgment: while 0037 is "
        f"UNAPPLIED there is no reading to re-attest, because the migration "
        f"creates the table and inserts nothing into it -- which "
        f"test_the_migration_SHIPS_THE_TABLE_EMPTY asserts. Once the first "
        f"reading is written that carve-out is SPENT.")


def test_the_anchor_check_can_FAIL(monkeypatch) -> None:
    """The tripwire's own discriminator, on the REAL file.

    A tripwire that cannot fire is decorative, and the failure mode is silent:
    it reads exactly like one that passed.
    """
    monkeypatch.setattr(
        "tests.data.test_22a_canonicalizer_version_closure."
        "ENVELOPE_CANONICALIZER_VERSION", "9999-01-01.0")
    with pytest.raises(AssertionError, match="UNVERIFIABLE BY SQL"):
        test_the_migration_anchor_MIRRORS_the_python_constant()


# ---------------------------------------------------------------------------
# THE TRIPWIRE'S **DECLARED** SCOPE -- 22A-R14-01, operator-ruled 2026-08-31.
#
# The finding: the tripwire above passed through the one leg in which the
# canonicaliser's ANSWER actually moved.  `22A-R13-01` made
# `canonical_envelope_identity` return `refused` for every non-`str` document
# where it had returned `canonical`, the version constant did not move, and
# this tripwire -- written in the very next commit -- was green.  It compares a
# Python constant to a SQL COMMENT: **two hand-maintained copies of a LABEL,
# and neither of them is the canonicaliser's BEHAVIOUR.**
#
# DECLARED, NOT WIDENED, on the ruling that produced the two walk declarations
# one round earlier: **the principle was never "make every instrument exact";
# it is "do not claim exact when you are not."**  A tripwire declared as a
# label comparator is honest.  One presented as a staleness detector is the
# false claim this arc exists to remove -- and the counterexample is already in
# the ledger, in this arc's own history.  The class-level fix -- binding the
# version to a DIGEST of the canonicaliser and its dependencies, with an
# append-only `(version, digest)` history, exactly as
# `DERIVATION_RULE_HISTORY` already does for `_derive` -- is routed to 22-A2
# (plan S12.2b) with R14-01 as its founding evidence.
#
# PINNED IN THE DIRECTION THAT FAILS IF IT EVER NARROWS: the case below asserts
# the blindness is CURRENTLY REAL.  If a later change makes a behaviour move
# visible to the tripwire, THIS FAILS -- and the right response is to correct
# the declaration, never to silence the test.  The L18 convention applied to an
# instrument instead of to a trigger.
# ---------------------------------------------------------------------------
def test_DECLARED_a_behaviour_change_WITHOUT_a_bump_is_invisible(
        monkeypatch) -> None:
    """The counterexample, EXECUTED rather than described.

    The retired predicate is restored verbatim -- ``if not isinstance(raw, str)
    or not raw.strip(): return True``, one predicate answering two questions --
    and the SAME document then reads `canonical` where today it reads
    `refused`.  That IS a canonicaliser bump by the constant's own contract.
    The label does not move, and the tripwire passes.
    """
    import swing.trades.latched_origin as lo

    doc = b'{"schwab_order_id": "1002937461"}'
    assert lo.canonical_envelope_identity(doc).state == "refused", (
        "the premise: today's authority REFUSES a document it cannot read")
    before = lo.ENVELOPE_CANONICALIZER_VERSION

    real = lo.envelope_is_canonical

    def pre_r13_01(raw):
        if not isinstance(raw, str) or not raw.strip():
            return True
        return real(raw)

    monkeypatch.setattr(lo, "envelope_is_canonical", pre_r13_01)
    assert lo.canonical_envelope_identity(doc).state == "canonical", (
        "the behaviour change did not take, so this measures nothing")
    assert lo.ENVELOPE_CANONICALIZER_VERSION == before, (
        "the label must NOT move -- an unbumped behaviour change is the "
        "whole subject")
    # AND THE TRIPWIRE IS GREEN.  Called directly rather than asserted about,
    # so the claim is the production check's own verdict.
    test_the_migration_anchor_MIRRORS_the_python_constant()


def test_the_migration_SHIPS_THE_TABLE_EMPTY() -> None:
    """The FACT that made the 2026-08-31.1 bump owe no re-attestation.

    A bump normally owes re-attestation of every reading taken under the older
    grammar.  0037 CREATES `fill_envelope_identity` and inserts nothing into
    it, so on any database that has just applied 0037 there is no such reading
    -- and 0037 is unapplied, so there is none anywhere.  That is a fact about
    this file, which is why it is asserted here rather than argued in a commit
    message.  **Once the first reading is written the carve-out is SPENT**, and
    this test is not what enforces that -- the anchor comparison above is.
    """
    body = "\n".join(_blanked(_sql()))
    assert "CREATE TABLE fill_envelope_identity" in body, (
        "the migration no longer creates the table, so its emptiness proves "
        "nothing about this arc")
    assert not _seeding_inserts(body), (
        f"0037 now seeds fill_envelope_identity: {_seeding_inserts(body)}. "
        f"The re-attestation carve-out recorded at the "
        f"CANONICALIZER-VERSION-ANCHOR rests on the table shipping EMPTY")


def test_the_ships_empty_check_can_FAIL(monkeypatch) -> None:
    """Spliced into the REAL migration text, per this module's convention."""
    text = _sql().replace(
        "CREATE INDEX ix_fei_broker_order_id ON fill_envelope_identity",
        "INSERT INTO\n  fill_envelope_identity (fill_id) VALUES (1);\n"
        "CREATE INDEX ix_fei_broker_order_id ON fill_envelope_identity",
        1)
    assert text != _sql(), "the splice matched nothing"
    monkeypatch.setattr(
        "tests.data.test_22a_canonicalizer_version_closure._sql",
        lambda: text)
    with pytest.raises(AssertionError, match="now seeds"):
        test_the_migration_SHIPS_THE_TABLE_EMPTY()


# ---------------------------------------------------------------------------
# 2. THE CLOSURE WALK, IN BOTH DIRECTIONS
# ---------------------------------------------------------------------------
def test_every_table_REFERENCE_carries_a_marker_and_they_interleave() -> None:
    """A consumer added later without a marker FAILS HERE.

    The interleaving assertion is what makes the pairing mechanical rather
    than positional-by-luck: marker[i] must sit between reference[i-1] and
    reference[i], so a marker attached to the wrong clause, a missing marker
    and a spare marker are all distinguishable.
    """
    text = _sql()
    marks, refs = _markers(text), _references(text)
    assert len(marks) == len(refs), (
        f"{len(refs)} FROM/JOIN references to fill_envelope_identity and "
        f"{len(marks)} FEI-CONSUMER markers: every reference consumes or "
        f"scopes a stored reading and must declare which")
    for i, (mline, key, claim) in enumerate(marks):
        assert claim in CLAIMS, f"marker `{key}` claims {claim!r}"
        assert mline < refs[i], f"marker `{key}` follows its reference"
        if i:
            assert refs[i - 1] < mline, (
                f"marker `{key}` sits before the PREVIOUS reference, so the "
                f"markers and references do not interleave")


def test_every_marker_is_declared_in_L19_and_agrees_with_it() -> None:
    """DIRECTION 1: nothing the migration does is unnamed in the plan."""
    marks = {key: claim for _l, key, claim in _markers(_sql())}
    roster = _roster()
    missing = sorted(set(marks) - set(roster))
    assert not missing, (
        f"these consumers are marked in 0037 and named nowhere in L19: "
        f"{missing}. L19 declares its roster EXACT")
    disagree = {k: (marks[k], roster[k]) for k in marks
                if marks[k] != roster[k]}
    assert not disagree, (
        f"the migration's marker and L19 disagree (key -> (sql, plan)): "
        f"{disagree}")


def test_every_L19_entry_names_a_marker_that_exists() -> None:
    """DIRECTION 2: the roster claims nothing the migration does not carry.

    22A-R9-05's failure from the other end -- a roster BROADENED to cover a
    clause nobody ruled on reads as conservative and is simply false.
    """
    marks = {key for _l, key, _c in _markers(_sql())}
    orphans = sorted(set(_roster()) - marks)
    assert not orphans, (
        f"L19 declares these and 0037 carries no such marker: {orphans}")


@pytest.mark.parametrize("key", sorted(_roster()))
def test_each_marker_CLAIM_matches_what_its_span_actually_contains(
        key: str) -> None:
    """The claim is a claim, and this is the claim MEASURED.

    A clause that quietly GAINS a version check can no longer keep saying
    VERSION_BLIND -- which would leave L19 overstating the exposure -- and one
    that claims VERSION_CHECKED while filtering nothing fails loudly, which is
    the false-label direction 22A-R6-06 found on a different roster.
    """
    measured = _measured()[key]
    declared = _roster()[key]
    if declared == NOT_A_READING:
        assert measured == VERSION_BLIND, (
            f"`{key}` is declared NOT_A_READING -- a conflict scope over the "
            f"UNIQUE KEY -- and its span filters on {VERSION_COLUMN}, which "
            f"would admit a second row for the same document")
        return
    assert measured == declared, (
        f"`{key}` is declared {declared} and the migration measures "
        f"{measured}")


# ---------------------------------------------------------------------------
# THE WALK'S OWN DISCRIMINATORS -- and they mutate the REAL migration text,
# not a locally reconstructed set (22A-R13-05's criticism of the AL-3 walk,
# answered in the instrument written after it).
# ---------------------------------------------------------------------------
def test_an_UNMARKED_reference_spliced_into_the_REAL_sql_is_caught(
        monkeypatch) -> None:
    """The red step, performed on the production artifact.

    An eighth consumer is spliced into a copy of the actual file and the walk
    is re-run over it: the counts diverge and the interleaving assertion
    reports it.  Without this the pairing could match today by accident and
    read identically to one that can never report anything.
    """
    text = _sql().replace(
        "         AND NOT EXISTS (SELECT 1 FROM fill_envelope_identity fei\n",
        "         AND NOT EXISTS (SELECT 1 FROM fill_envelope_identity fei9\n"
        "                         WHERE fei9.fill_id = -1)\n"
        "         AND NOT EXISTS (SELECT 1 FROM fill_envelope_identity fei\n",
        1)
    assert len(_references(text)) == len(_references(_sql())) + 1, (
        "the splice did not add a reference, so this discriminator proves "
        "nothing")
    monkeypatch.setattr(
        "tests.data.test_22a_canonicalizer_version_closure._sql",
        lambda: text)
    with pytest.raises(AssertionError, match="FEI-CONSUMER markers"):
        test_every_table_REFERENCE_carries_a_marker_and_they_interleave()


def test_a_span_that_GAINS_a_version_filter_is_MEASURED_as_checked(
        monkeypatch) -> None:
    """The other direction, also on the real text.

    A VERSION_BLIND declaration must stop being true the moment the SQL starts
    checking -- otherwise L19 would overstate the exposure forever and nobody
    would notice the limitation had narrowed.
    """
    text = _sql().replace(
        "                       AND fei3.envelope_state = 'canonical'))",
        "                       AND fei3.envelope_state = 'canonical'\n"
        "                       AND fei3.canonicalizer_version = 'x'))",
        1)
    assert text != _sql(), "the splice matched nothing"
    monkeypatch.setattr(
        "tests.data.test_22a_canonicalizer_version_closure._sql",
        lambda: text)
    assert _measured()["rung6_population_has_been_read"] == VERSION_CHECKED
    with pytest.raises(AssertionError, match="measures VERSION_CHECKED"):
        test_each_marker_CLAIM_matches_what_its_span_actually_contains(
            "rung6_population_has_been_read")


# ---------------------------------------------------------------------------
# THE PYTHON HALF -- the same limitation, and it is not omitted
# ---------------------------------------------------------------------------
def test_the_repo_readers_are_version_blind_and_L19_says_so() -> None:
    """The service readers carry no version filter either.

    They are SAFE where the SQL is not, because every ladder caller runs
    `ensure_entry_fill_identities` first and it raises on disagreement.  The
    assertion runs in the direction that matters: if someone ADDS a filter
    here, this fails and forces L19 to be corrected rather than silently
    narrowed -- and if someone REMOVES the population pass that makes the
    blindness safe, the reason recorded below stops matching the code.
    """
    source = FEI_REPO.read_text(encoding="utf-8")
    for reader in ("def stored_identity", "def consuming_entry_fills",
                   "def unreadable_entry_fills"):
        assert reader in source, f"{reader} has moved; re-derive L19's claim"
    selects = [ln for ln in source.splitlines()
               if VERSION_COLUMN in ln and "SELECT" in ln.upper()]
    assert not selects, (
        f"a repo reader now filters or projects {VERSION_COLUMN}: {selects}. "
        f"That may be correct -- but L19 declares these readers version-blind, "
        f"and a declaration the code has outgrown is the defect this arc "
        f"exists to remove")
    plan = PLAN.read_text(encoding="utf-8")
    assert "THE PYTHON HALF IS THE SAME LIMITATION" in plan, (
        "L19 no longer declares the Python half, so the boundary is stated in "
        "the code and not in the limitation")
