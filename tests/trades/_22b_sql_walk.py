"""Arc 22-B Task 10 -- the static SQL-write walk behind b22_150 and b22_115.

Every ``.execute`` / ``.executemany`` / ``.executescript`` call in a source
tree is visited. Its first argument is RESOLVED statically into the set of
texts it can evaluate to: string literals, f-strings, module-level
constants, function-local names (see ``_local_bindings``), ``+``
concatenations and conditional expressions; every statically unknown piece
becomes a HOLE marker. ``classify`` then decides whether any hole can reach
a write; if one can, the site is UNRESOLVED and must sit on the reviewed
inventory (``DYNAMIC_SQL_SITES`` in the test module): a closure check,
never a hand list of writers.

A resolved text is classified into WRITES: ``(kind, table, columns)`` where
``kind`` is ``update`` (``UPDATE t SET ...``), ``upsert`` (``... ON CONFLICT
DO UPDATE SET ...``, the INSERT's table), ``insert`` / ``replace``
(``INSERT [OR x] INTO t (cols)`` / ``REPLACE INTO`` / ``INSERT OR REPLACE``)
and ``columns`` is the literal column set or ``{"*"}`` when the statement
names no column list.
"""
from __future__ import annotations

import ast
import itertools
import re
from dataclasses import dataclass
from pathlib import Path

HOLE = "\x00"
_EXECUTE_METHODS = frozenset({"execute", "executemany", "executescript"})
_MAX_TEXTS = 64


@dataclass(frozen=True)
class Write:
    kind: str
    table: str
    columns: frozenset[str]


@dataclass(frozen=True)
class Site:
    module: str
    function: str
    lineno: int
    source: str
    texts: tuple[str, ...]
    writes: tuple[Write, ...] | None  # None = UNRESOLVED

    @property
    def key(self) -> tuple[str, str]:
        return (self.module, self.function)


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------

def _module_constants(tree: ast.Module) -> dict[str, ast.expr]:
    out: dict[str, ast.expr] = {}
    counts: dict[str, int] = {}
    for node in tree.body:
        targets: list[ast.expr] = []
        value = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        for t in targets:
            if isinstance(t, ast.Name):
                counts[t.id] = counts.get(t.id, 0) + 1
                out[t.id] = value
    return {k: v for k, v in out.items() if counts[k] == 1}


def _local_bindings(func: ast.AST) -> dict[str, tuple[str, list] | None]:
    """name -> how it is built. ``("concat", pieces)``: exactly ONE plain
    ``=`` followed by ``+=`` appends (the incremental SQL-builder shape; the
    text is every piece concatenated in source order -- a SUPERSET of each
    run's text, so a write any run can perform is visible in it).
    ``("union", values)``: two or more plain ``=`` and nothing else (if/elif
    branches; the name holds ONE of them). Any other binding form (a mixed
    ``=``/``+=`` history, a non-``+`` augassign, a loop / with / except /
    parameter / walrus / import target, tuple unpacking) maps the name to
    None -- it resolves to a HOLE."""
    seen: dict[str, list[tuple[str, ast.expr | None, int]]] = {}

    def bind(name: str, kind: str, value: ast.expr | None, pos: int) -> None:
        seen.setdefault(name, []).append((kind, value, pos))

    if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        a = func.args
        for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg]:
            if arg is not None:
                bind(arg.arg, "other", None, 0)
    for node in ast.walk(func):
        pos = (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))
        pos_key = pos[0] * 10_000 + pos[1]
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    bind(t.id, "assign", node.value, pos_key)
                else:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            bind(n.id, "other", None, pos_key)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bind(node.target.id, "assign" if node.value is not None else "other",
                 node.value, pos_key)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            kind = "append" if isinstance(node.op, ast.Add) else "other"
            bind(node.target.id, kind, node.value, pos_key)
        elif isinstance(node, ast.NamedExpr):
            bind(node.target.id, "other", None, pos_key)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name):
                    bind(n.id, "other", None, pos_key)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            for n in ast.walk(node.optional_vars):
                if isinstance(n, ast.Name):
                    bind(n.id, "other", None, 0)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bind(node.name, "other", None, pos_key)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bind((alias.asname or alias.name).split(".")[0], "other", None, 0)
    out: dict[str, list[ast.expr] | None] = {}
    for name, binds in seen.items():
        binds = sorted(binds, key=lambda x: x[2])
        kinds = [k for k, _, _ in binds]
        if kinds.count("assign") == 1 and kinds[0] == "assign" and all(
                k in ("assign", "append") for k in kinds):
            out[name] = ("concat", [v for _, v, _ in binds])  # type: ignore
        elif kinds and all(k == "assign" for k in kinds):
            # if/elif branches each binding the name: any ONE of them.
            out[name] = ("union", [v for _, v, _ in binds])  # type: ignore
        else:
            out[name] = None
    return out


def _resolve(expr: ast.expr, local: dict, module: dict,
             depth: int = 0) -> list[str]:
    """Every text ``expr`` can evaluate to, with each statically unknown piece
    replaced by HOLE. Never None: an unknown expression IS a hole, and the
    classifier decides whether a hole can reach a write target."""
    if depth > 20:
        return [HOLE]
    if isinstance(expr, ast.Constant):
        return [expr.value] if isinstance(expr.value, str) else [HOLE]
    if isinstance(expr, ast.JoinedStr):
        parts: list[str] = []
        for v in expr.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
                continue
            sub = [HOLE]
            if (isinstance(v, ast.FormattedValue) and v.conversion == -1
                    and v.format_spec is None):
                sub = _resolve(v.value, local, module, depth + 1)
            parts.append(sub[0] if len(sub) == 1 else HOLE)
        return ["".join(parts)]
    if isinstance(expr, ast.Name):
        if expr.id in local:
            binding = local[expr.id]
            if binding is None:
                return [HOLE]
            mode, pieces = binding
            if mode == "union":
                out = [t for piece in pieces
                       for t in _resolve(piece, local, module, depth + 1)]
                return out if len(out) <= _MAX_TEXTS else [HOLE]
            acc = [""]
            for piece in pieces:
                nxt = _resolve(piece, local, module, depth + 1)
                acc = [x + y for x, y in itertools.product(acc, nxt)]
                if len(acc) > _MAX_TEXTS:
                    return [HOLE]
            return acc
        if expr.id in module:
            return _resolve(module[expr.id], {}, module, depth + 1)
        return [HOLE]
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left = _resolve(expr.left, local, module, depth + 1)
        right = _resolve(expr.right, local, module, depth + 1)
        out = [x + y for x, y in itertools.product(left, right)]
        return out if len(out) <= _MAX_TEXTS else [HOLE]
    if isinstance(expr, ast.IfExp):
        out = (_resolve(expr.body, local, module, depth + 1)
               + _resolve(expr.orelse, local, module, depth + 1))
        return out if len(out) <= _MAX_TEXTS else [HOLE]
    return [HOLE]


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

_IDENT = r'(?:"?[A-Za-z_\x00][\w\x00]*"?)'
_UPDATE = re.compile(rf"\bUPDATE\s+(?:OR\s+\w+\s+)?({_IDENT})\s+SET\b", re.I)
_INSERT = re.compile(
    rf"\b(INSERT(?:\s+OR\s+(\w+))?|REPLACE)\s+INTO\s+({_IDENT})\s*"
    r"(\(([^()]*)\))?", re.I | re.S)
_UPSERT = re.compile(r"\bDO\s+UPDATE\s+SET\b", re.I)
_REGION_END = re.compile(r"(WHERE|FROM|RETURNING)\b", re.I)
_TRIGGER_BODY = re.compile(
    r"\bCREATE\s+TRIGGER\b.*?\bBEGIN\b.*?\bEND\b", re.I | re.S)


def _norm(name: str) -> str:
    return name.strip().strip('"').lower()


def _set_region(text: str, start: int) -> str:
    """The SET list after ``start``: up to the first TOP-LEVEL (paren depth
    0, outside a string literal) WHERE / FROM / RETURNING / ``;`` / end."""
    depth, i, n = 0, start, len(text)
    while i < n:
        ch = text[i]
        if ch == "'":
            j = text.find("'", i + 1)
            i = n if j < 0 else j + 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and (ch == ";" or (
                (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_"))
                and _REGION_END.match(text, i))):
            return text[start:i]
        i += 1
    return text[start:]


def _set_columns(region: str) -> frozenset[str]:
    """The assigned column of each TOP-LEVEL comma item ``col = expr``."""
    items, depth, cur, i = [], 0, [], 0
    while i < len(region):
        ch = region[i]
        if ch == "'":
            j = region.find("'", i + 1)
            j = len(region) - 1 if j < 0 else j
            cur.append(region[i:j + 1])
            i = j + 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    items.append("".join(cur))
    cols = set()
    for item in items:
        if "=" in item:
            cols.add(_norm(item.split("=", 1)[0]))
    return frozenset(cols)


_LEADING = re.compile(r"\s*(?:--[^\n]*\n\s*)*([A-Za-z]+)")
# Leads whose single statement cannot write a row whatever a hole holds:
# a query, a pragma, or transaction control naming a savepoint.
_NON_WRITING_LEADS = frozenset({
    "select", "pragma", "savepoint", "release", "rollback", "begin", "commit"})
_WRITE_LEADS = frozenset({"insert", "update", "replace", "delete"})


def _strip_comments_and_literals(text: str) -> str:
    """Blank SQL comments (``--`` to end of line, ``/* */``) and the CONTENT
    of single-quoted string literals (``''`` escapes honoured). A comment or a
    string VALUE is never a statement: prose naming ``INSERT OR REPLACE INTO
    trades`` in a RAISE message or a header comment performs no write, and a
    hole inside a literal is a value, not SQL."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "-" and text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            out.append(" ")
            continue
        if ch == "/" and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")
            continue
        if ch == "'":
            j = i + 1
            while j < n:
                if text[j] == "'":
                    if j + 1 < n and text[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            out.append("''")
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def classify(text: str, tables: frozenset[str],
             script: bool = False) -> tuple[Write, ...] | None:
    """The writes ``text`` performs, or None when a hole can reach a write
    (the site is then UNRESOLVED and must be inventoried).

    A hole is harmless only where it provably cannot become a write: in an
    ``execute``/``executemany`` (ONE statement -- sqlite3 refuses more) whose
    LITERAL leading keyword is SELECT or PRAGMA, or inside an
    INSERT/UPDATE/REPLACE/DELETE outside the write target (table name, SET
    list, column list) on one of ``tables``. A hole in an ``executescript``,
    a hole at the head, or a hole under any other leading keyword (WITH can
    lead a write; CREATE TRIGGER can carry one) is unresolved.

    Trigger BODIES in a HOLE-FREE text are statements the ENGINE runs, not
    this call site's writes -- the schema's own mirrors, cut before matching."""
    text = _strip_comments_and_literals(text)
    if HOLE in text:
        if script:
            return None
        lead = _LEADING.match(text)
        if lead is None:
            return None
        verb = lead.group(1).lower()
        if verb in _NON_WRITING_LEADS:
            return ()
        if verb not in _WRITE_LEADS:
            return None
    text = _TRIGGER_BODY.sub(" ", text)
    writes: list[Write] = []
    for m in _UPDATE.finditer(text):
        table = _norm(m.group(1))
        if HOLE in table:
            return None
        region = _set_region(text, m.end())
        if table in tables and HOLE in region:
            return None
        writes.append(Write("update", table, _set_columns(region)))
    for m in _INSERT.finditer(text):
        verb = m.group(1).split()[0].lower()
        conflict = (m.group(2) or "").lower()
        table = _norm(m.group(3))
        if HOLE in table:
            return None
        cols_text = m.group(5)
        if cols_text is None:
            cols = frozenset({"*"})
        else:
            if table in tables and HOLE in cols_text:
                return None
            cols = frozenset(_norm(c) for c in cols_text.split(",") if c.strip())
        kind = "replace" if verb == "replace" or conflict == "replace" else "insert"
        writes.append(Write(kind, table, cols))
        tail_end = len(text)
        nxt = _INSERT.search(text, m.end())
        if nxt:
            tail_end = nxt.start()
        for u in _UPSERT.finditer(text, m.end(), tail_end):
            region = _set_region(text, u.end())
            if table in tables and HOLE in region:
                return None
            writes.append(Write("upsert", table, _set_columns(region)))
    return tuple(writes)


# --------------------------------------------------------------------------
# the walk
# --------------------------------------------------------------------------

def _qualnames(tree: ast.Module) -> dict[int, tuple[str, ast.AST | None]]:
    """id(call node) -> (qualified enclosing function, that function node)."""
    out: dict[int, tuple[str, ast.AST | None]] = {}

    def visit(node: ast.AST, prefix: str, func: ast.AST | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                name = f"{prefix}.{child.name}" if prefix else child.name
                fn = child if not isinstance(child, ast.ClassDef) else func
                visit(child, name, fn)
            else:
                if isinstance(child, ast.Call):
                    out[id(child)] = (prefix or "<module>", func)
                visit(child, prefix, func)

    visit(tree, "", None)
    return out


def walk_source(source: str, module: str,
                tables: frozenset[str]) -> list[Site]:
    tree = ast.parse(source)
    consts = _module_constants(tree)
    owners = _qualnames(tree)
    local_cache: dict[int, dict] = {}
    sites: list[Site] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in _EXECUTE_METHODS):
            continue
        qual, func = owners.get(id(node), ("<module>", None))
        if func is None:
            local: dict = {}
        else:
            local = local_cache.setdefault(id(func), _local_bindings(func))
        texts = _resolve(node.args[0], local, consts) if node.args else [HOLE]
        script = node.func.attr == "executescript"
        writes: tuple[Write, ...] | None = ()
        for t in texts:
            w = classify(t, tables, script=script)
            if w is None:
                writes = None
                break
            writes = writes + w
        src = ast.unparse(node.args[0]) if node.args else "<no args>"
        sites.append(Site(module, qual, node.lineno, src[:120], tuple(texts),
                          writes))
    return sites


def walk_tree(root: Path, repo_root: Path,
              tables: frozenset[str]) -> list[Site]:
    sites: list[Site] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(repo_root).as_posix()
        sites.extend(walk_source(path.read_text(encoding="utf-8"), rel, tables))
    return sites
