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
# THESE ARE REFERENCE COUNTS, NOT LINE COUNTS, AND AT THE CONSOLIDATION THE
# COINCIDENCE WAS A TRAP: the pre-change tree had 33 `_PRICE_DP` LINES (4
# definitions + 29 consumer lines) and 33 references, because several consumer
# lines carry TWO `round()` calls. The two 33s meant different things and
# neither could be derived from the other.
#
# THE MAP IS MAINTAINED, NOT FROZEN, AND THAT IS THE POINT. `order_intent.py`
# went 3 -> 5 when the below-pivot refusal started rounding BOTH of its operands
# to display precision (Codex R7 MAJOR), and this belt is what made the change
# visible instead of silent. A count that must be edited when the set of
# rounded comparisons changes is a count doing its job; the failure it exists to
# catch is a comparison quietly LOSING its rounding.
_EXPECTED_REFERENCES = {
    "swing/latches/orders.py": 8,
    "swing/latches/service.py": 20,
    "swing/latches/order_intent.py": 5,
    "swing/web/view_models/latches.py": 2,
}

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _source(rel_path: str) -> str:
    return (_REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _tree(rel_path: str) -> ast.Module:
    return ast.parse(_source(rel_path))


def _bindings_of(source: str, tree: ast.Module, names: set[str]) -> list[str]:
    """Every BINDING of `names`, at any scope, by any binding form.

    ASKED OF THE COMPILER, NOT OF AN ENUMERATION OF NODE TYPES. `symtable` is
    the symbol table CPython itself builds, so "is this name bound in this
    scope" is answered structurally: assignment, annotated assignment,
    augmented assignment, `for` target, `with ... as`, walrus, parameter,
    `except ... as`, every `match` capture, `def` / `class`, `global` /
    `nonlocal`, PEP-695 type parameters and imports are all just BINDINGS to it.

    THIS REPLACED A HAND-WRITTEN NODE-TYPE ROSTER THAT WAS WIDENED FIVE TIMES IN
    FIVE REVIEW ROUNDS -- `AnnAssign`, then `arg`, then alias / `MatchAs` /
    `MatchStar`, then `def` / `class`, then `MatchMapping.rest`, then PEP-695
    type parameters, the last of which ALSO broke the declared 3.11 floor by
    naming `ast.TypeVar` directly. Each widening was correct and each left the
    next hole open, because an enumeration can only ever be as complete as the
    grammar it was written against. A single-source guarantee with a documented
    hole in it is not a guarantee, and six rounds of patching a roster is the
    evidence that the roster was the wrong instrument.

    EXACTLY ONE BINDING IS PERMITTED: the MODULE-SCOPE IMPORT. `symtable` says a
    name is imported but not FROM WHERE, so the alias walk below still answers
    "which module" -- that is the one question the symbol table cannot answer,
    and it is why a `from somewhere_else import PRICE_DP` at module scope is
    caught here rather than by the compiler's own view.
    """
    import symtable

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
        if isinstance(node, ast.alias):
            bound = node.asname or node.name.split(".")[0]
            if bound in names and id(node) not in allowed_aliases:
                found.append(f"import of {bound} from somewhere else")

    def _scan(table, path: str) -> None:
        for sym in table.get_symbols():
            name = sym.get_name()
            if name not in names:
                continue
            bound = (sym.is_assigned() or sym.is_parameter()
                     or sym.is_imported())
            if not bound:
                continue                      # a pure READ, which is the point
            if (path == "" and sym.is_imported() and not sym.is_assigned()
                    and not sym.is_parameter()):
                continue                      # THE module-scope import
            found.append(f"{name} bound in scope {path or '<module>'}")
        for child in table.get_children():
            _scan(child, f"{path}.{child.get_name()}" if path
                  else child.get_name())

    _scan(symtable.symtable(source, "<single-source-belt>", "exec"), "")
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
    source = _source(rel_path)
    tree = ast.parse(source)

    bindings = _bindings_of(source, tree, {"PRICE_DP", "_PRICE_DP"})
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
