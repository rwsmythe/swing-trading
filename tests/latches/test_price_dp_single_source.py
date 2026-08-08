"""THE DISPLAY PRECISION IS ONE OBJECT, NOT FOUR EQUAL ONES.

Four modules each bound their own `_PRICE_DP = 2`: `swing/latches/orders.py`,
`swing/latches/service.py`, `swing/latches/order_intent.py` and
`swing/web/view_models/latches.py`. Four literals are four objects that can
drift; four names for ONE object cannot. That distinction is the whole point of
the consolidation, so it is what these tests assert.

THREE ASSERTIONS, BECAUSE THE FIRST TWO ALONE ARE SATISFIABLE BY A MODULE THAT
STILL HARD-CODES THE LITERAL. A module can import `PRICE_DP` and keep calling
`round(v, 2)`; the import would be dead and every comparison would still read a
private copy. So the third assertion checks that the CONSUMERS are reached.

`2 is 2` is True for small ints in CPython, so an `is`-identity test cannot
catch a module-level re-binding on its own -- the AST ban on binding the name
owns that job, and the identity test owns "the name is importable from all
four". Neither is sufficient alone and both are here.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from swing.latches import order_intent as order_intent_mod
from swing.latches import orders as orders_mod
from swing.latches import service as service_mod
from swing.latches.constants import PRICE_DP
from swing.web.view_models import latches as latches_vm_mod

# The four modules that used to bind their own copy. Each maps to the number of
# `PRICE_DP` references the consolidated tree must carry.
#
# 33 IS THE NUMBER OF REFERENCES, NOT THE NUMBER OF LINES, AND THE COINCIDENCE
# IS A TRAP: the pre-change tree also had 33 `_PRICE_DP` LINES (4 definitions +
# 29 consumer lines), because several consumer lines carry TWO `round()` calls
# (`orders.py:156`, `:315`, `:427`; `service.py:799`). The two 33s mean
# different things and neither may be derived from the other.
_EXPECTED_REFERENCES = {
    "swing/latches/orders.py": 8,
    "swing/latches/service.py": 20,
    "swing/latches/order_intent.py": 3,
    "swing/web/view_models/latches.py": 2,
}

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _tree(rel_path: str) -> ast.Module:
    return ast.parse((_REPO_ROOT / rel_path).read_text(encoding="utf-8"))


def _bindings_of(tree: ast.Module, names: set[str]) -> list[str]:
    """Every BINDING of `names`, at any scope, by any binding form.

    `ast.Name` in a `Store` context subsumes `Assign` / `AnnAssign` /
    `AugAssign` / `for` targets / `with ... as` / walrus; `ast.arg` covers
    function parameters (a parameter named `PRICE_DP` shadows the import inside
    that function while every other assertion here still passes);
    `ExceptHandler` and `MatchAs` bind through a bare string attribute rather
    than a `Name`, so each needs its own clause.

    IMPORTS ARE NOT EXEMPT BY NODE TYPE -- ONLY THE CANONICAL ONE IS ALLOWED
    (Codex R2 MINOR). An `import` binds through `ast.alias`, and treating that
    node type as permitted let a function-local `from somewhere_else import
    PRICE_DP`, or an `import x as PRICE_DP`, shadow the canonical constant while
    the identity test (which reads the MODULE attribute) and the reference count
    both still passed. So every `alias` binding either name is rejected EXCEPT
    the module-level `from swing.latches.constants import PRICE_DP` -- the one
    binding this whole file exists to require.

    Enumerating node TYPES was the shape that let `PRICE_DP: int = 2` slip past
    an `Assign`-only ban, and exempting a node type is the same mistake wearing
    an import's clothes. A single-source guarantee with a documented hole in it
    is not a guarantee.
    """
    allowed_aliases = {
        id(alias)
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "swing.latches.constants" and node.level == 0
        for alias in node.names
        if alias.name == "PRICE_DP" and alias.asname is None
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id in names:
                found.append(f"Name(Store) {node.id} at line {node.lineno}")
        elif isinstance(node, ast.arg) and node.arg in names:
            found.append(f"arg {node.arg} at line {node.lineno}")
        elif isinstance(node, ast.ExceptHandler) and node.name in names:
            found.append(f"except-as {node.name} at line {node.lineno}")
        elif isinstance(node, ast.MatchAs) and node.name in names:
            found.append(f"match-as {node.name} at line {node.lineno}")
        elif isinstance(node, ast.MatchStar) and node.name in names:
            found.append(f"match-star {node.name} at line {node.lineno}")
        elif isinstance(node, ast.alias):
            bound = node.asname or node.name.split(".")[0]
            if bound in names and id(node) not in allowed_aliases:
                found.append(f"import-alias {bound}")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for bound in node.names:
                if bound in names:
                    found.append(f"global/nonlocal {bound} at line {node.lineno}")
    return found


def _imports_price_dp_from_constants(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "swing.latches.constants":
            if any(alias.name == "PRICE_DP" and alias.asname is None for alias in node.names):
                return True
    return False


def _round_second_args(tree: ast.Module) -> list[tuple[int, ast.expr | None]]:
    out: list[tuple[int, ast.expr | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "round":
                second = node.args[1] if len(node.args) > 1 else None
                out.append((node.lineno, second))
    return out


def _price_dp_references(tree: ast.Module) -> int:
    return sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "PRICE_DP"
        and isinstance(node.ctx, ast.Load)
    )


@pytest.mark.parametrize("rel_path", sorted(_EXPECTED_REFERENCES))
def test_every_latch_price_comparison_reads_ONE_PRICE_DP(rel_path: str) -> None:
    tree = _tree(rel_path)

    bindings = _bindings_of(tree, {"PRICE_DP", "_PRICE_DP"})
    assert bindings == [], (
        f"{rel_path} BINDS the display precision instead of importing it: {bindings}")

    assert _imports_price_dp_from_constants(tree), (
        f"{rel_path} does not import PRICE_DP from swing.latches.constants")

    # THE CONSUMERS ARE REACHED. An import with a `round(v, 2)` left behind is a
    # dead import over a private copy -- the half-done consolidation.
    literal_rounds = [
        line for line, second in _round_second_args(tree)
        if not (isinstance(second, ast.Name) and second.id == "PRICE_DP")
    ]
    assert literal_rounds == [], (
        f"{rel_path} rounds a price to something other than PRICE_DP at lines {literal_rounds}")

    assert _price_dp_references(tree) == _EXPECTED_REFERENCES[rel_path], (
        f"{rel_path} carries {_price_dp_references(tree)} PRICE_DP references, "
        f"expected {_EXPECTED_REFERENCES[rel_path]}")


def test_the_consolidated_constant_is_the_SAME_OBJECT_at_every_consumer() -> None:
    """The name is importable from all four modules and is ONE object.

    RED on the pre-change tree for a blunt reason: the modules expose
    `_PRICE_DP`, not `PRICE_DP`, so `orders_mod.PRICE_DP` raises
    `AttributeError`. It does NOT kill a re-binding -- `2 is 2` is True -- and
    the AST ban above owns that job.
    """
    for module in (orders_mod, service_mod, order_intent_mod, latches_vm_mod):
        assert module.PRICE_DP is PRICE_DP, module.__name__
    assert PRICE_DP == 2


def test_the_regime_boundary_still_uses_display_precision() -> None:
    """GUARD: the consolidation must not move the rounding site.

    Green on both trees by construction -- that is the point. It fails a
    consolidation that changed WHICH comparisons round or at what precision.
    """
    assert orders_mod.expected_mandate_order_type(
        latched_pivot=18.34, last_close=18.339999) == "LIMIT"
