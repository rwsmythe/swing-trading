# tests/web/test_topbar_provenance_lint.py
"""Backstop: every `session_date` value assigned in the web layer must trace to
a topbar_session_date(...) call -- directly OR through a local variable bound in
the same function. Catches the intermediate-variable evasion the regex missed."""
import ast
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "swing" / "web"
_GOOD = "topbar_session_date"

# `session_date=` kwargs passed to these functions are NOT base-layout topbar
# dates -- they are daily-management data keys, deliberately anchored on
# ``last_completed_session(now)`` per the daily_management session-anchor
# contract (Codex R1 Major #1). The topbar-provenance lint scopes to VM render
# dates, so it excludes these known non-topbar consumers.
_NON_TOPBAR_CONSUMERS = {"has_update_today_for_trades"}


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name):
            return f.id
        if isinstance(f, ast.Attribute):
            return f.attr
    return None


def _banned_source(value: ast.AST, local_defs: dict[str, ast.AST]) -> str | None:
    """DENYLIST: return a reason if `value` traces to a RAW anchor (banned),
    else None. Resolves `.isoformat()`/`.date()` chains + one local-var hop. A
    string literal (the deliberate "n/a" fallback) and a topbar_session_date(...)
    call are NOT banned -- so the
    `try: session_date = topbar(...); except: session_date = "n/a"` shape does
    not false-positive."""
    node = value
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "today":
            return "date.today()"
        if node.func.attr == "date":
            return "datetime.now().date()"
        node = node.func.value  # unwrap .isoformat() etc.
    name = _call_name(node)
    if name in {"action_session_for_run", "last_completed_session"}:
        return f"{name}(...)"
    if name == _GOOD:
        return None  # explicitly OK
    if isinstance(node, ast.Name):
        bound = local_defs.get(node.id)
        if bound is not None:
            return _banned_source(bound, {})  # one resolution hop
    return None  # literals / unknowns are not raw anchors


def _offenders_in(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local_defs = {}
        for stmt in ast.walk(fn):
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        local_defs[t.id] = stmt.value
        for stmt in ast.walk(fn):
            vals = []
            if isinstance(stmt, ast.Call) and _call_name(stmt) not in _NON_TOPBAR_CONSUMERS:
                vals += [kw.value for kw in stmt.keywords if kw.arg == "session_date"]
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and t.id == "session_date":
                        vals.append(stmt.value)
            for v in vals:
                reason = _banned_source(v, local_defs)
                if reason:
                    out.append(f"{path.name}:{getattr(v, 'lineno', '?')} ({reason})")
    return out


def test_session_date_never_from_raw_anchor():
    offenders = []
    for path in WEB.rglob("*.py"):
        offenders += _offenders_in(path)
    assert not offenders, (
        "session_date must NOT come from a raw anchor (use topbar_session_date):\n"
        + "\n".join(offenders))
