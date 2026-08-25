"""The 22-A case-to-task CLOSURE CHECK -- the repaired instrument (22A-R9-10).

Three directions, because every hand pass over the ladder found only the
direction it was looking for:

  P  PLAN -> REGISTRY.  Every case-id token the plan names is LIVE, or
     EXCLUDED with a reason, or an ALIAS of live members.  Declared LIMIT:
     the extractor is word-anchored, so it bounds the family FROM BELOW.  The
     manifest itself was established by READ (see the registry docstring);
     this direction is the regression guard on it.
  T  REGISTRY -> LADDER.  Every live case has exactly one owning task drawn
     from the plan's task ids, and the ``-pre`` twin roster is internally
     coherent (every twin's base case is live and admitting).
  I  REGISTRY <-> TESTS.  A STATIC ast walk of the arc's test modules -- not
     a run trace, because a trace only sees the branches a fixture happened to
     take, which is exactly how eleven cases stayed invisible through two
     reviews and a self-sweep.  BOTH directions fail loudly: a live case with
     no test is an UNOWNED test; a test naming an unknown id is a PHANTOM.

Direction I is the arc's completeness gate and is RED until the arc is built.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.trades.case_registry_22a import (
    ALIASES,
    DEFERRED_CASES,
    EXCLUDED_CASES,
    NON_CASE_TOKENS,
    PLAN_CASES,
    slug,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_NAME = "2026-08-24-phase22-arc-a-entry-path-order-mandate-binding.md"

# The plan's task ids, read off the S7 ladder's first column.
LADDER_TASKS = frozenset(
    {"1", "2", "3", "4", "5", "6", "6a", "7", "8", "9", "10", "11", "11a",
     "12", "13"}
)

# Test modules the static walk covers.  A module added to the arc OUTSIDE these
# globs would make direction I silently under-count -- the case would read as
# unimplemented and, worse, a DEFERRAL could then be declared for a case that
# already has a test.  The globs are therefore RECURSIVE and a companion test
# asserts they cover every ``test_22a_*.py`` on disk.
#
# THE COMPANION TEST DID NOT EXIST WHEN THIS COMMENT FIRST CLAIMED IT DID
# ("...asserted to match the on-disk glob (test_arc_modules_are_all_walked)").
# Existence is not completeness, arriving in the instrument written to enforce
# that distinction.  It exists now, below, under the name the comment promised.
ARC_TEST_GLOBS = ("tests/**/test_22a_*.py",)

# ---------------------------------------------------------------------------
# THE LEXICAL SPEC, as code rather than as prose.
# ---------------------------------------------------------------------------
_ID = r"\d{1,3}[a-z]?(?:'(?!s)|\(i{1,3}\)|-i{1,3}(?![a-z])|-pre(?![a-z]))?"
_PHRASE = re.compile(
    r"\b[Cc]ases?\b((?:\s|\*|`|,|/|;|\+|\band\b|\bor\b|\bthe\b|\btheir\b"
    r"|\bnew\b|\brevised\b|-|" + _ID + r")+)"
)
_LETTER_RANGE = re.compile(r"^(\d{1,3})([a-z])-(\d{1,3})([a-z])$")
_NUM_RANGE = re.compile(r"^(\d{1,3})-(\d{1,3})$")


def _plan_path() -> Path:
    hits = sorted(REPO_ROOT.glob(f"docs/**/{PLAN_NAME}"))
    assert hits, (
        f"22-A plan {PLAN_NAME} not found under docs/. The closure check is "
        f"specified against the plan (S7); a move is a decision, not a skip."
    )
    return hits[0]


def extract_plan_case_tokens(text: str) -> set[str]:
    """Word-anchored extraction with ranges expanded. Bounds FROM BELOW."""
    found: set[str] = set()
    for match in _PHRASE.finditer(text):
        for raw in re.split(r"[,/;]|\band\b|\bor\b|\*|`|\s+", match.group(1)):
            piece = raw.strip().strip("*`")
            if not piece:
                continue
            letters = _LETTER_RANGE.match(piece)
            if letters and letters.group(1) == letters.group(3):
                lo, hi = ord(letters.group(2)), ord(letters.group(4))
                if lo <= hi:
                    found.update(
                        f"{letters.group(1)}{chr(c)}" for c in range(lo, hi + 1)
                    )
                    continue
            nums = _NUM_RANGE.match(piece)
            if nums:
                lo, hi = int(nums.group(1)), int(nums.group(2))
                if lo < hi <= lo + 9:
                    found.update(str(n) for n in range(lo, hi + 1))
                    continue
            if re.fullmatch(_ID, piece):
                found.add(piece)
    return found


# ---------------------------------------------------------------------------
# DIRECTION P
# ---------------------------------------------------------------------------
def test_every_plan_case_token_is_live_or_excluded_with_a_reason() -> None:
    tokens = extract_plan_case_tokens(_plan_path().read_text(encoding="utf-8"))
    known = set(PLAN_CASES) | set(EXCLUDED_CASES) | set(ALIASES) | NON_CASE_TOKENS
    unknown = sorted(tokens - known)
    assert not unknown, (
        "the plan names case ids the registry does not classify: "
        f"{unknown}. Add each to PLAN_CASES with an owning task, or to "
        "EXCLUDED_CASES with the reason that makes it excluded."
    )


def test_every_alias_expands_to_live_members() -> None:
    for alias, members in ALIASES.items():
        missing = [m for m in members if m not in PLAN_CASES]
        assert not missing, f"alias {alias} expands to unknown members {missing}"


def test_excluded_cases_carry_a_reason_and_are_not_also_live() -> None:
    for case_id, reason in EXCLUDED_CASES.items():
        assert reason.strip(), f"exclusion {case_id} has no reason"
        assert case_id not in PLAN_CASES, (
            f"{case_id} is both live and excluded -- the ambiguity the "
            f"instrument exists to remove"
        )


# ---------------------------------------------------------------------------
# DIRECTION T
# ---------------------------------------------------------------------------
def test_every_live_case_has_exactly_one_task_from_the_ladder() -> None:
    bad = {c: t for c, t in PLAN_CASES.items() if t not in LADDER_TASKS}
    assert not bad, f"cases owned by tasks not in the S7 ladder: {bad}"


def test_pre_twins_are_coherent_with_their_base_case() -> None:
    """A twin exists only for a live base case, and the base is not itself a twin."""
    for case_id in PLAN_CASES:
        if not case_id.endswith("-pre"):
            continue
        base = case_id[: -len("-pre")]
        assert base in PLAN_CASES, (
            f"twin {case_id} has no live base case {base}"
        )
        assert not base.endswith("-pre"), f"twin of a twin: {case_id}"


def test_deferred_cases_are_a_subset_of_the_live_manifest() -> None:
    stray = sorted(set(DEFERRED_CASES) - set(PLAN_CASES))
    assert not stray, f"DEFERRED_CASES names non-live ids: {stray}"


# ---------------------------------------------------------------------------
# DIRECTION I -- the static walk
# ---------------------------------------------------------------------------
def _arc_test_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ARC_TEST_GLOBS:
        files.extend(sorted(REPO_ROOT.glob(pattern)))
    return files


def implemented_case_ids() -> set[str]:
    """Collect covered case ids by parsing, never by importing or running.

    Two conventions, both statically visible:
      * a test function named ``..._case_<slug>``;
      * a module-level literal list/tuple bound to a name ending
        ``_CASE_IDS`` whose elements are case-id strings (for parametrized
        families, where one function covers many cases).
    """
    by_slug = {slug(c): c for c in PLAN_CASES}
    covered: set[str] = set()
    for path in _arc_test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
                for suffix, case_id in by_slug.items():
                    if node.name.endswith(f"_case_{suffix}"):
                        covered.add(case_id)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if not (isinstance(target, ast.Name)
                            and target.id.endswith("_CASE_IDS")):
                        continue
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for element in node.value.elts:
                            if isinstance(element, ast.Constant) and isinstance(
                                element.value, str
                            ):
                                covered.add(element.value)
    return covered


def test_arc_modules_are_all_walked() -> None:
    """Every ``test_22a_*.py`` on disk is inside the walked set.

    A module the walk cannot see makes direction I under-count in the ONE
    direction that is dangerous: a case would read as unimplemented, and the
    documented remedy for an unimplemented case is a DECLARED DEFERRAL -- so an
    unwalked module could turn a built case into a recorded deviation.
    """
    walked = {p.resolve() for p in _arc_test_files()}
    on_disk = {
        p.resolve() for p in REPO_ROOT.glob("tests/**/test_22a_*.py")
        if "__pycache__" not in p.parts
    }
    missing = sorted(str(p.relative_to(REPO_ROOT)) for p in on_disk - walked)
    assert not missing, (
        f"22-A test modules outside ARC_TEST_GLOBS: {missing}. Widen the glob "
        f"or move the module; do NOT leave it unwalked."
    )


def test_arc_test_modules_exist() -> None:
    assert _arc_test_files(), (
        "no 22-A arc test modules found; direction I would vacuously pass, "
        "which is the 'existence is not completeness' trap this check exists "
        "to avoid"
    )


def test_no_phantom_cases_in_the_arc_test_modules() -> None:
    phantom = sorted(implemented_case_ids() - set(PLAN_CASES))
    assert not phantom, (
        f"arc tests claim case ids the registry does not know: {phantom}"
    )


def test_every_live_case_is_implemented_by_a_test() -> None:
    expected = set(PLAN_CASES) - set(DEFERRED_CASES)
    missing = sorted(expected - implemented_case_ids())
    assert not missing, (
        f"{len(missing)} live 22-A cases have no test: {missing}. Either "
        f"implement them or DECLARE the deviation in "
        f"case_registry_22a.DEFERRED_CASES with its reason."
    )


@pytest.mark.parametrize("case_id", sorted(PLAN_CASES))
def test_case_slug_round_trips(case_id: str) -> None:
    """The slug must be a valid Python identifier suffix and collision-free."""
    assert re.fullmatch(r"[0-9a-z_]+", slug(case_id)), case_id
    collisions = [c for c in PLAN_CASES if c != case_id and slug(c) == slug(case_id)]
    assert not collisions, f"slug collision: {case_id} vs {collisions}"
