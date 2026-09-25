"""22-F T-E1 -- F-F5: every exception-text `ClickException` is ASCII-coerced
(CHARC F-F5 (3), the closure as the instrument; plan section 6).

Premise, CORRECTED (CHARC F-F5 (1)): `swing/cli.py` reconfigures stdout /
stderr to UTF-8 `errors="replace"` inside `try/except (AttributeError,
io.UnsupportedOperation)`, and the except branch PRESERVES the original
encoding on embedded consoles and non-`TextIOWrapper` streams -- so the
encode-side crash is unreachable where reconfigure works and REACHABLE where
it does not.  The fix is uniform.

STATIC.  Over `swing/cli.py`, `cli_schwab.py`, `cli_config.py`,
`cli_latches.py` (read as UTF-8): for every call whose func is
`click.ClickException` / `ClickException`, walk its arguments (positional and
keyword).  A TAINTED LEAF is (a) a `Name` bound by an enclosing
`except ... as <name>`, or (b) an `Attribute` whose `attr == "message"`.
Every tainted leaf must have an ancestor INSIDE the argument that is a call
to `ascii_safe` or `safe_text`.  One-level local-assignment follow: a
`ClickException(<Name>)` whose name is assigned in the same function from an
expression carrying an uncoerced tainted leaf is flagged too.  DECLARED
BOUND (a limit, not an exemption): a message built more than one assignment
away, or passed through a helper, is not seen (census 3.4).

BEHAVIOURAL (the R3-1 form): build the `Error:` line Click prints (`"Error:
" + exc.format_message()`) and `.encode("cp1252")` it.  Driven at
`trade assign-intent`'s `except ValueError` site and its REFUSED site with
text OUTSIDE cp1252 (U+2192 and a lone surrogate) planted at the service --
`--reason` never reaches either message (read: the service's refusal texts
are constants or `ascii()`-quoted; the reason is only blank-checked and
stored), so the input is planted where the message is made (exec ledger).
"""
from __future__ import annotations

import ast
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from tests._22f_ast import REPO_ROOT, enclosing_function, parent_map

_FILES = ("cli.py", "cli_schwab.py", "cli_config.py", "cli_latches.py")
_COERCERS = frozenset({"ascii_safe", "safe_text"})


def _func_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _handler_names(node: ast.AST, parents: dict) -> set[str]:
    names: set[str] = set()
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.ExceptHandler) and cur.name:
            names.add(cur.name)
        cur = parents.get(cur)
    return names


def _uncoerced_leaves(expr: ast.AST, bound: set[str], parents: dict
                      ) -> list[ast.AST]:
    """Tainted leaves in ``expr`` with no coercer call between them and
    ``expr`` (inclusive)."""
    out = []
    for leaf in ast.walk(expr):
        tainted = ((isinstance(leaf, ast.Name) and leaf.id in bound
                    and isinstance(leaf.ctx, ast.Load))
                   or (isinstance(leaf, ast.Attribute)
                       and leaf.attr == "message"))
        if not tainted:
            continue
        cur, covered = leaf, False
        while True:
            if (isinstance(cur, ast.Call)
                    and _func_name(cur.func) in _COERCERS):
                covered = True
                break
            if cur is expr:
                break
            cur = parents[cur]
        if not covered:
            out.append(leaf)
    return out


def _enclosing_def(node: ast.AST, parents: dict) -> ast.AST | None:
    cur = parents.get(node)
    while cur is not None and not isinstance(
            cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
        cur = parents.get(cur)
    return cur


def _assignments(fn: ast.AST, name: str):
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name
                   for t in node.targets):
                yield node, node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if (isinstance(node.target, ast.Name)
                    and node.target.id == name and node.value is not None):
                yield node, node.value


def _violations(root: Path) -> list[str]:
    out: list[str] = []
    for fname in _FILES:
        path = root / fname
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        parents = parent_map(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and _func_name(node.func) == "ClickException"):
                continue
            bound = _handler_names(node, parents)
            args = [*node.args, *(k.value for k in node.keywords)]
            bad = [arg for arg in args
                   if _uncoerced_leaves(arg, bound, parents)]
            # One-level local-assignment follow.
            for arg in args:
                if not (isinstance(arg, ast.Name) and arg.id not in bound):
                    continue
                fn = _enclosing_def(node, parents)
                if fn is None:
                    continue
                for stmt, value in _assignments(fn, arg.id):
                    if _uncoerced_leaves(value, _handler_names(stmt, parents),
                                         parents):
                        bad.append(arg)
                        break
            for arg in bad:
                out.append(f"{fname}:{node.lineno}: "
                           f"{enclosing_function(node, parents)}: "
                           f"{ast.unparse(arg)[:120]}")
    return sorted(out, key=lambda s: (s.split(":")[0], int(s.split(":")[1])))


def test_every_exception_text_clickexception_is_ascii_coerced():
    bad = _violations(REPO_ROOT / "swing")
    assert bad == [], f"{len(bad)} uncoerced:\n" + "\n".join(bad)


def test_the_walker_is_not_vacuous(tmp_path):
    """Synthetic modules: each tainted shape is flagged, each coerced shape
    passes, and the one-level follow fires."""
    src = '''
import click
from swing.trades.entry import ascii_safe, safe_text

def f():
    try:
        pass
    except ValueError as exc:
        raise click.ClickException(str(exc))                     # flag
    except KeyError as exc:
        raise click.ClickException(ascii_safe(str(exc)))         # ok
    except OSError as err:
        raise click.ClickException(f"bad: {err!r}")               # flag
    except TypeError as err:
        raise click.ClickException(f"bad: {safe_text(err)}")     # ok
    except IndexError as e:
        msg = f"x {e}"
        raise click.ClickException(msg)                          # flag
    result = object()
    raise click.ClickException(f"REFUSED: {result.message}")     # flag
'''
    for name in _FILES:
        (tmp_path / name).write_text("", encoding="utf-8")
    (tmp_path / "cli.py").write_text(src, encoding="utf-8")
    bad = _violations(tmp_path)
    assert len(bad) == 4, bad
    assert [b.split(": ", 2)[2] for b in bad] == [
        "str(exc)", "f'bad: {err!r}'", "msg", "f'REFUSED: {result.message}'",
    ], bad
    # the real tree is walked: the modules carry many ClickException calls
    real = sum(ast.unparse(n.func).endswith("ClickException")
               for f in _FILES
               for n in ast.walk(ast.parse(
                   (REPO_ROOT / "swing" / f).read_text(encoding="utf-8")))
               if isinstance(n, ast.Call))
    assert real >= 150, real


# ---------------------------------------------------------------------------
# the R3-1 behavioural discriminators: `trade assign-intent`
# ---------------------------------------------------------------------------

_HOSTILE = "x → y \udc80"


def _error_line(result) -> str:
    """The line Click's standalone mode prints for the raised
    ClickException (`ClickException.show`)."""
    exc = result.exception
    assert isinstance(exc, SystemExit), (type(exc), result.output)
    ctx = result.exc_info[1].__context__
    assert isinstance(ctx, click.ClickException), repr(ctx)
    return "Error: " + ctx.format_message()


@pytest.fixture
def world(tmp_path, monkeypatch):
    from swing.cli import main
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    cfg = _minimal_config(project, home)
    r = CliRunner().invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    return main, cfg


def _invoke(main, cfg):
    return CliRunner().invoke(main, [
        "--config", str(cfg), "trade", "assign-intent", "1",
        "--value", "unintended_execution", "--cite", "notes",
        "--reason", "r"], catch_exceptions=True)


def test_E1a_assign_intent_value_error_line_encodes_cp1252(world, monkeypatch):
    """PRE-FIX: `UnicodeEncodeError` encoding the `Error:` line.  POST-FIX:
    it encodes.  The `ValueError` is planted as `assign` (the command imports
    it function-locally from its home module, so the module attribute is the
    name resolved per call)."""
    from tests._22f_proxies import raising
    main, cfg = world
    planted = raising(ValueError(f"bad input {_HOSTILE}"))
    monkeypatch.setattr("swing.trades.entry_intent_assignment.assign",
                        planted)
    result = _invoke(main, cfg)
    assert planted.calls >= 1  # did-it-fire
    assert result.exit_code == 1
    _error_line(result).encode("cp1252")


def test_E1b_assign_intent_refused_line_encodes_cp1252(world, monkeypatch):
    """The REFUSED path: `result.message` carrying the hostile text."""
    from swing.trades.entry_intent_assignment import AssignmentResult
    from tests._22f_proxies import CountingWrapper
    main, cfg = world
    refused = AssignmentResult(admitted=False, refusal_code="planted",
                               message=f"refused {_HOSTILE}")
    planted = CountingWrapper(lambda *_a, **_k: refused)
    monkeypatch.setattr("swing.trades.entry_intent_assignment.assign",
                        planted)
    result = _invoke(main, cfg)
    assert planted.calls >= 1  # did-it-fire
    assert result.exit_code == 1
    line = _error_line(result)
    assert line.startswith("Error: REFUSED (planted): refused x ")
    line.encode("cp1252")


def test_E1c_control_ascii_message_is_byte_unchanged(world, monkeypatch):
    """CONTROL: ASCII text is byte-for-byte what it was."""
    from tests._22f_proxies import raising
    main, cfg = world
    planted = raising(ValueError("plain ascii text"))
    monkeypatch.setattr("swing.trades.entry_intent_assignment.assign",
                        planted)
    result = _invoke(main, cfg)
    assert planted.calls >= 1
    assert _error_line(result) == "Error: plain ascii text"
    assert result.output == "Error: plain ascii text\n"
