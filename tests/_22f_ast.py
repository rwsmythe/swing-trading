"""22-F shared AST walkers for the closure tests (plan section 0.4).

Pure `ast` over files read as UTF-8 (the cp1252 decode side lies silently,
CLAUDE.md).  Nothing here imports the code under inspection.

* `iter_sources(root, patterns)` -- (relative posix path, parsed module).
* `parent_map(tree)` -- child -> parent, for ancestor walks.
* `enclosing_function(node, parents)` -- the dotted name of the innermost
  enclosing def (``Class.method`` / ``outer.inner``), ``"<module>"`` if none.
* `handler_type_names(handler)` -- the LAST dotted component of every class a
  handler names (bare, dotted, or in a tuple); ``()`` for a bare ``except:``.
* `iter_handlers(tree)` -- every `ExceptHandler` with its `Try` (so a test
  can see the SIBLING handlers of the same `Try`).
* `enclosing_try_handler_names(node, parents)` -- the union of handler names
  of every `Try` whose BODY (not a handler / else / finally) contains `node`.
"""
from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def iter_sources(root: Path, patterns: tuple[str, ...]
                 ) -> Iterator[tuple[str, ast.Module, list[str]]]:
    """Yield ``(relative_posix_path, tree, source_lines)`` for each file under
    ``root`` matching any glob in ``patterns`` (sorted, de-duplicated)."""
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path in seen or "__pycache__" in path.parts:
                continue
            seen.add(path)
            text = path.read_text(encoding="utf-8")
            yield (path.relative_to(root).as_posix(), ast.parse(text),
                   text.splitlines())


def parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    names: list[str] = []
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef,
                            ast.ClassDef)):
            names.append(cur.name)
        cur = parents.get(cur)
    return ".".join(reversed(names)) or "<module>"


def _type_names(expr: ast.AST | None) -> tuple[str, ...]:
    if expr is None:
        return ()
    if isinstance(expr, ast.Tuple):
        out: list[str] = []
        for elt in expr.elts:
            out.extend(_type_names(elt))
        return tuple(out)
    if isinstance(expr, ast.Name):
        return (expr.id,)
    if isinstance(expr, ast.Attribute):
        return (expr.attr,)
    return ()


def handler_type_names(handler: ast.ExceptHandler) -> tuple[str, ...]:
    return _type_names(handler.type)


def iter_handlers(tree: ast.AST
                  ) -> Iterator[tuple[ast.Try, ast.ExceptHandler]]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            for handler in node.handlers:
                yield node, handler


def _in_try_body(node: ast.AST, try_node: ast.Try,
                 parents: dict[ast.AST, ast.AST]) -> bool:
    """Whether ``node`` sits in ``try_node.body`` (walking up to the child of
    ``try_node`` that contains it)."""
    cur = node
    while cur is not None and parents.get(cur) is not try_node:
        cur = parents.get(cur)
    return cur is not None and any(cur is stmt for stmt in try_node.body)


def enclosing_try_handler_names(node: ast.AST,
                                parents: dict[ast.AST, ast.AST]
                                ) -> set[str]:
    names: set[str] = set()
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.Try) and _in_try_body(node, cur, parents):
            for handler in cur.handlers:
                names.update(handler_type_names(handler))
        cur = parents.get(cur)
    return names
