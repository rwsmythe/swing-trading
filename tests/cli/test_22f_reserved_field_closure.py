"""22-F T-B3 -- the `ReservedJournalFieldError` closure (CHARC F-F2 RJFE).

STATIC HALF.  In `swing/trades/reconciliation_auto_correct.py`, compute the
PUBLIC functions (no leading `_`) from which a `raise ReservedJournalFieldError`
or `raise MultiRowCorrectionOverrideError` is reachable through the module's
OWN name graph: an edge from a function (or a module-level assignment, e.g.
the `_TIER2_HANDLERS` registry) to every module-level function it names.
Naming is enough -- a registry value is dispatched by lookup, never by a call
the walker could see.  Then every call site of those functions in
`swing/cli*.py` and `swing/web/routes/*.py` must sit in the BODY of a `Try`
whose handlers NAME each type reachable from the callee (both are bare
`Exception` subclasses, so there is no narrower base to name -- by name
only; `Exception`/`BaseException` never count), or be in `EXEMPT` with a
reason.  Both directions: an `EXEMPT` entry matching no uncovered site
FAILS (a stale exemption is an open door).

Keys use the stripped source line of the call, not a line number.

BEHAVIOURAL HALF: A5-a..A5-e (`tests/cli/test_22f_cli_typed_refusals.py`,
`tests/web/test_routes/test_22f_a5_reconcile_resolve_control.py`).
"""
from __future__ import annotations

import ast
from pathlib import Path

from tests._22f_ast import (
    REPO_ROOT,
    enclosing_function,
    enclosing_try_handler_names,
    iter_sources,
    parent_map,
)

_MODULE = "swing.trades.reconciliation_auto_correct"
_TYPES = frozenset({"ReservedJournalFieldError",
                    "MultiRowCorrectionOverrideError"})

# (relative path, enclosing function, stripped call line) -> reason.
EXEMPT: dict[tuple[str, str, str], str] = {
    ("web/routes/reconcile.py", "reconcile_discrepancy_resolve_post",
     "result = apply_tier2_resolution("):
        "caught by the route's defense-in-depth `except Exception` "
        "(routes/reconcile.py, the step-5 service call): a 500 "
        "`service_error` fragment, never the app-wide page -- census C1-05 "
        "puts the web route outside the escape set; pinned by the A5-e "
        "CONTROL",
}


def _reaching_public_functions(root: Path) -> dict[str, frozenset[str]]:
    """public function name -> the subset of `_TYPES` it can raise."""
    path = root / "trades" / "reconciliation_auto_correct.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes: dict[str, ast.AST] = {}
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes[stmt.name] = stmt
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            targets = (stmt.targets if isinstance(stmt, ast.Assign)
                       else [stmt.target])
            for t in targets:
                if isinstance(t, ast.Name):
                    nodes[t.id] = stmt
    raises: dict[str, set[str]] = {}
    edges: dict[str, set[str]] = {}
    for name, node in nodes.items():
        raises[name] = set()
        edges[name] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Raise) and isinstance(sub.exc, ast.Call):
                func = sub.exc.func
                if isinstance(func, ast.Name) and func.id in _TYPES:
                    raises[name].add(func.id)
            if (isinstance(sub, ast.Name) and sub.id in nodes
                    and sub.id != name):
                edges[name].add(sub.id)
    reach: dict[str, set[str]] = {n: set(r) for n, r in raises.items()}
    changed = True
    while changed:
        changed = False
        for name in nodes:
            for dep in edges[name]:
                if not reach[dep] <= reach[name]:
                    reach[name] |= reach[dep]
                    changed = True
    return {n: frozenset(r) for n, r in reach.items()
            if r and not n.startswith("_")
            and isinstance(nodes[n], (ast.FunctionDef, ast.AsyncFunctionDef))}


def _call_sites(root: Path, reaching: dict[str, frozenset[str]]):
    """Yield (key, reachable types, handler names) for every call of a
    reaching public function in the CLI modules and the web routes."""
    for rel, tree, lines in iter_sources(
            root, ("cli*.py", "web/routes/*.py")):
        local: dict[str, str] = {}      # local name -> public function
        mod_aliases: set[str] = set()   # names bound to the module itself
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == _MODULE:
                for alias in node.names:
                    if alias.name in reaching:
                        local[alias.asname or alias.name] = alias.name
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == _MODULE and alias.asname:
                        mod_aliases.add(alias.asname)
        if not local and not mod_aliases:
            continue
        parents = parent_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            target = None
            if isinstance(func, ast.Name) and func.id in local:
                target = local[func.id]
            elif (isinstance(func, ast.Attribute)
                  and isinstance(func.value, ast.Name)
                  and func.value.id in mod_aliases
                  and func.attr in reaching):
                target = func.attr
            if target is None:
                continue
            key = (rel, enclosing_function(node, parents),
                   lines[node.lineno - 1].strip())
            yield key, reaching[target], enclosing_try_handler_names(
                node, parents)


def _violations(root: Path) -> tuple[list, list]:
    reaching = _reaching_public_functions(root)
    uncovered = []
    matched_exempt = set()
    for key, types, handled in _call_sites(root, reaching):
        if types <= handled:
            continue
        if key in EXEMPT:
            matched_exempt.add(key)
            continue
        uncovered.append((key, sorted(types - handled)))
    stale = sorted(set(EXEMPT) - matched_exempt)
    return uncovered, stale


def test_reserved_field_types_are_named_at_every_operator_call_site():
    uncovered, stale = _violations(REPO_ROOT / "swing")
    assert uncovered == [], uncovered
    assert stale == [], f"stale EXEMPT entries (match no site): {stale}"


def test_the_walker_is_not_vacuous():
    """The graph finds the two tier surfaces T-A5 drove, and the call-site
    walk finds their three operator roots (two CLI commands, one route)."""
    root = REPO_ROOT / "swing"
    reaching = _reaching_public_functions(root)
    assert {"apply_tier2_resolution", "apply_tier3_override"} <= set(reaching)
    assert reaching["apply_tier2_resolution"] == _TYPES
    sites = {key for key, _t, _h in _call_sites(root, reaching)}
    assert {k[0] for k in sites} >= {"cli.py", "web/routes/reconcile.py"}
    assert len(sites) >= 3, sites
