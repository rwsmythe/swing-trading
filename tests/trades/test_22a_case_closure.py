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


_FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def case_ids_in_source(source: str, filename: str = "<source>") -> set[str]:
    """Covered case ids in ONE module's source, by parsing.  Never imports.

    Two conventions, both statically visible:
      * a **module-level** test function named ``..._case_<slug>``;
      * a **module-level** literal list/tuple bound to a name ending
        ``_CASE_IDS`` **that a module-level function REFERENCES** (in its body
        or in a decorator) -- the parametrized-family convention, where one
        function covers many cases.

    **THE REFERENCE REQUIREMENT IS G1'S REPAIR, AND IT IS WHAT MAKES THIS A
    GATE** (audit finding G1, verified BY EXECUTION at orchestrator QA).  The
    list alone used to bind, so six of the nine ``*_CASE_IDS`` lists were DEAD
    LITERALS with exactly ONE occurrence -- their own assignment -- and for
    `35a/35b/35c/35n/35p` and `51a`-`51e` that dead literal was the ONLY
    binding.  **Measured: stripping EVERY ``FunctionDef`` from
    ``test_22a_task2_migration_0037.py`` still reported 10 of 10 implemented.**
    A gate that can report green with zero functions is not a gate.  A
    decorator is a child of the ``FunctionDef`` it decorates, so removing the
    functions removes every reference and the ids stop binding.

    **THE SCOPE TEST IS G2'S REPAIR.**  The docstring said *module-level* and
    the walk used ``ast.walk`` with no scope test, so an ``Assign`` inside a
    function or a class body bound its ids, as did a nested ``def``.
    Unexploited when it was found, and it is the same shape as G1 one level
    down: a binding nobody meant to write.
    """
    by_slug = {slug(c): c for c in PLAN_CASES}
    tree = ast.parse(source, filename=filename)
    functions = [n for n in tree.body if isinstance(n, _FUNC_NODES)]

    covered: set[str] = set()
    for fn in functions:
        if not fn.name.startswith("test"):
            continue
        for suffix, case_id in by_slug.items():
            if fn.name.endswith(f"_case_{suffix}"):
                covered.add(case_id)

    referenced: set[str] = set()
    for fn in functions:
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                referenced.add(node.id)

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name)
                    and target.id.endswith("_CASE_IDS")):
                continue
            if target.id not in referenced:
                continue
            if isinstance(node.value, (ast.List, ast.Tuple)):
                for element in node.value.elts:
                    if isinstance(element, ast.Constant) and isinstance(
                        element.value, str
                    ):
                        covered.add(element.value)
    return covered


def implemented_case_ids() -> set[str]:
    """Every covered case id across the walked arc modules."""
    covered: set[str] = set()
    for path in _arc_test_files():
        covered |= case_ids_in_source(
            path.read_text(encoding="utf-8"), filename=str(path))
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


# ---------------------------------------------------------------------------
# THE GATE'S OWN DISCRIMINATORS (audit findings G1 / G2)
#
# "A gate that can report green with zero functions is not a gate" (CHARC).
# Both rows below run the PRODUCTION walk over MUTATED REAL SOURCE, never over
# an invented snippet, so a change to the walk cannot pass them by being
# correct about a shape the arc does not contain.
# ---------------------------------------------------------------------------
def _strip_functions(source: str) -> str:
    """The same module with every module-level ``def`` removed.

    Emitted with ``ast.unparse`` from the REAL parse tree, so what is measured
    is the arc's own module minus its functions rather than a hand-written
    approximation of one.
    """
    tree = ast.parse(source)
    tree.body = [n for n in tree.body if not isinstance(n, _FUNC_NODES)]
    return ast.unparse(ast.fix_missing_locations(tree))


@pytest.mark.parametrize(
    "module",
    ["tests/data/test_22a_task2_migration_0037.py",
     "tests/data/test_22a_task11_citation_evidence.py",
     "tests/trades/test_22a_task4_authorization_ladder.py"])
def test_G1_a_module_with_no_functions_implements_no_cases(module) -> None:
    """**MEASURED BEFORE THE FIX: stripping every ``FunctionDef`` from
    ``test_22a_task2_migration_0037.py`` still reported 10 of 10 implemented.**

    Its ten case ids were bound by two DEAD LITERALS -- ``THE_35_CASE_IDS`` and
    ``THE_51_CASE_IDS``, each occurring exactly once, at its own assignment --
    so the gate was reporting a list somebody typed rather than a test that
    runs.  The three modules below are the ones carrying ``*_CASE_IDS`` lists;
    each must report NOTHING once its functions are gone.
    """
    source = (REPO_ROOT / module).read_text(encoding="utf-8")
    assert case_ids_in_source(source, module), (
        f"{module} binds no case ids at all, so this row measures nothing")
    stripped = case_ids_in_source(_strip_functions(source), module)
    assert stripped == set(), (
        f"{module} still reports {sorted(stripped)} with EVERY function "
        f"removed; the binding is a literal somebody typed, not a test that "
        f"runs")


def test_G2_a_binding_inside_a_function_or_class_body_does_not_count() -> None:
    """``implemented_case_ids`` said *module-level* and used ``ast.walk`` with
    no scope test, so a nested ``def`` and an ``Assign`` inside a function or a
    class body both bound their ids.

    Unexploited in the arc when it was found -- which is why the repair is the
    scope test rather than a rule about where people may write things.
    """
    real = sorted(PLAN_CASES)[0]
    nested = (
        "def outer():\n"
        f"    NESTED_CASE_IDS = [{real!r}]\n"
        f"    def test_inner_case_{slug(real)}():\n"
        "        return NESTED_CASE_IDS\n"
        "\n"
        "class Holder:\n"
        f"    CLASS_CASE_IDS = [{real!r}]\n"
        f"    def test_method_case_{slug(real)}(self):\n"
        "        return Holder.CLASS_CASE_IDS\n"
    )
    assert case_ids_in_source(nested) == set(), (
        "a binding written inside a function or a class body still counts")

    # THE CONTROL: the SAME id at module level, referenced by a module-level
    # function, DOES count -- so the row above is a scope test and not a walk
    # that stopped working.
    top = (
        f"TOP_CASE_IDS = [{real!r}]\n"
        "def test_top():\n"
        "    return TOP_CASE_IDS\n"
    )
    assert case_ids_in_source(top) == {real}
