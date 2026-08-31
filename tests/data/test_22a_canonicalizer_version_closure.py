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

1. **THE ARMING TRIPWIRE.**  A reading can only be STALE if
   `ENVELOPE_CANONICALIZER_VERSION` moved between two writes.  The migration
   mirrors the constant in a `CANONICALIZER-VERSION-ANCHOR` marker and this
   module COMPARES THE TWO REPRESENTATIONS, so a bump fails the suite -- with
   the required work named -- before a stale row can exist.  A comment
   promising future work is unenforceable (gotcha #31); a failing test is not,
   and the comparator is the only mirror that defends a set (gotcha #11).
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
    """THE ONLY ACTION THAT CAN ARM L19, AND IT NOW FAILS LOUDLY.

    Every consumer in 0037 was written against ONE canonicaliser grammar.  A
    stored reading can only become STALE if this constant moves between two
    writes -- a row bearing a version nobody ever shipped is a FORGED identity
    row, which is L10/AL-10's declared class, not this one.

    So the day someone bumps the constant, this fails, and the message says
    what the bump now owes: 22-A2's append-only re-attestation, or a migration
    that re-creates the six consumers against the new grammar.  A version
    filter in the triggers is NOT the remedy -- L19 measures why, in both of
    its halves.
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
        f"design or a migration that re-attests the population.")


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
