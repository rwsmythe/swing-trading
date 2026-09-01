"""EVERY COHORT-PROVENANCE GUARD STATES WHICH OF **ENTRY** OR **LABEL** IT
REFUSES -- AT ITS SITE (RD's standing requirement, 2026-09-01).

**FOUR INSTANCES IN ONE ARC**: `NotSessionError`, case 37c, `R11-02`'s
uncontained `record_identity`, and the entry route's `schwab_order_id` rung.
Every guard written to protect the cohort keys defaulted to BLOCKING THE ENTRY,
and each was found individually, by a different reviewer, on a different round.
**That is not four slips; it is a default that must be inverted at the seam.**

TWO INSTRUMENTS, and this module is the SECOND of them:

  1. **The PROPERTY** -- `tests/trades/test_22a_task9_entry_wiring.py`
     (`test_EVERY_refusal_reason_still_writes_the_entry_*`): for every member of
     `DECLINE_REASONS`, in both recognition states, the trade row is still
     WRITTEN.  That is what actually stops a fifth instance, because it fails
     whether or not anyone recognised the new code as a cohort guard.
  2. **This DECLARATION WALK**, which is the standing requirement itself made
     mechanical: every site in `swing/` that cites the governing principle
     carries a `COHORT-GUARD REFUSES: <ENTRY|LABEL|n/a>` line, so the next one
     is a VISIBLE LINE rather than an invisible hole.

**WHAT THIS WALK IS, HONESTLY: a HEURISTIC DETECTOR over the arc's own
citation token, not a proof.**  It finds sites that CITE `0036:26-38`.  A guard
written without citing it is invisible here -- which is exactly why instrument
(1) exists and is the one that bites.  Declared with its blindness named rather
than widened along the axis it misses.

FROZEN CLOCK: nothing here reads a clock.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SWING = REPO_ROOT / "swing"

# The arc's own citation of the governing principle -- migration 0036's ruling
# lines.  Every Python site quoting it is asserting the principle about code it
# is standing next to.
PRINCIPLE = "0036:26-38"
DECLARATION = re.compile(r"COHORT-GUARD REFUSES:\s*(ENTRY|LABEL|n/a)\b")

# How far a declaration may sit from the citation.  Twelve lines is the width
# of the comment blocks this arc writes; a declaration further away is
# describing a different site.
WINDOW = 12


def _python_sources() -> list[Path]:
    return [p for p in sorted(SWING.rglob("*.py"))
            if "__pycache__" not in p.parts]


def _citation_sites() -> dict[str, list[int]]:
    """path -> 1-based line numbers citing the governing principle."""
    out: dict[str, list[int]] = {}
    for path in _python_sources():
        lines = path.read_text(encoding="utf-8").splitlines()
        hits = [n for n, line in enumerate(lines, 1) if PRINCIPLE in line]
        if hits:
            # POSIX separators, because the assertions below name paths
            # and a Windows-only spelling would make this module report
            # differently on the two platforms it runs on.
            out[path.relative_to(REPO_ROOT).as_posix()] = hits
    return out


def _declaration_near(path: str, lineno: int) -> str | None:
    lines = (REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
    lo = max(0, lineno - 1 - WINDOW)
    hi = min(len(lines), lineno + WINDOW)
    match = DECLARATION.search("\n".join(lines[lo:hi]))
    return match.group(1) if match else None


def test_every_principle_citation_carries_a_declaration() -> None:
    """A site that invokes the rule and does not say which side it refuses is
    the shape all four instances had."""
    undeclared: dict[str, list[int]] = {}
    for path, linenos in _citation_sites().items():
        missing = [n for n in linenos if _declaration_near(path, n) is None]
        if missing:
            undeclared[path] = missing
    assert not undeclared, (
        f"sites invoking the governing principle without a "
        f"`COHORT-GUARD REFUSES:` declaration: {undeclared}. Every "
        f"cohort-provenance guard states, AT ITS SITE, which of ENTRY or "
        f"LABEL it refuses -- and the answer is always LABEL unless it is the "
        f"one declared exception.")


def test_the_only_site_declaring_ENTRY_is_the_ruled_exception() -> None:
    """**THE DEFAULT IS INVERTED AT THE SEAM**, and this is what holds it
    there.

    Exactly ONE site may declare `ENTRY`: the relocated PE-anchor guard in
    `swing/trades/entry.py`, which RD ruled is a PRE-EXISTING production
    rejection moved from the route rather than a cohort-provenance guard, and
    which fires on the ORDINARY path only.  A SECOND `ENTRY` declaration is a
    fifth instance of the class announcing itself.
    """
    entry_sites: list[tuple[str, int]] = []
    for path, linenos in _citation_sites().items():
        for n in linenos:
            if _declaration_near(path, n) == "ENTRY":
                entry_sites.append((path, n))
    assert [p for p, _ in entry_sites] == ["swing/trades/entry.py"], (
        f"a cohort-provenance guard declares that it refuses the ENTRY: "
        f"{entry_sites}. Cohort bookkeeping never blocks a money-bearing "
        f"entry; if this is genuinely the relocated PE-anchor guard's twin, "
        f"it needs a RULING, not a declaration.")


def test_the_walk_finds_the_sites_it_claims_to() -> None:
    """THE CONTROL.  A walk that had stopped matching would satisfy both rows
    above while checking nothing -- the existence-is-not-completeness trap
    arriving through a pattern that quietly stopped matching."""
    sites = _citation_sites()
    total = sum(len(v) for v in sites.values())
    assert total >= 10, (
        f"the principle is cited at {total} Python sites; the walk has "
        f"stopped seeing them")
    assert "swing/trades/latched_origin.py" in sites
    assert "swing/web/routes/trades.py" in sites


def test_the_declaration_pattern_can_actually_fail() -> None:
    """And so can the matcher, measured on a shape it must NOT accept."""
    assert DECLARATION.search("# COHORT-GUARD REFUSES: LABEL")
    assert DECLARATION.search("# COHORT-GUARD REFUSES: ENTRY -- ruled")
    assert not DECLARATION.search("# COHORT-GUARD REFUSES: maybe")
    assert not DECLARATION.search("# the guard refuses the label")
