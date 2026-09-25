"""22-F T-B1 -- the parity closure (CHARC F-F2 (2)).

For every `except` handler in `swing/**/*.py` whose type names
`SchwabApiError` (bare, dotted, or in a tuple), ONE of:

* WIDENED -- the same handler names `SchwabSchemaParityError`;
* COVERED (R40) -- ANOTHER handler of the same `Try`, in ANY position, names
  `SchwabSchemaParityError` or `_RedactedMessageError` (the ruled COVER
  pair).  `Exception`, `BaseException` and `RuntimeError` NEVER cover, so a
  broad tail cannot make a site vacuously covered;
* UNREACHABLE -- ``(relative_path, enclosing_function, handler_line_text,
  ordinal)`` is in `UNREACHABLE`, with a one-line reason.

Both directions: an `UNREACHABLE` entry matching no handler FAILS.

THE ORDERING FACT (R40): `SchwabSchemaParityError` and `SchwabApiError` are
DISJOINT classes, so clause order among them is inert -- a parity clause
FOLLOWING a `SchwabApiError` clause catches exactly what it would catch
preceding it.  Order becomes load-bearing only if `SchwabSchemaParityError` is
ever re-based under `SchwabApiError`, which F-F2 refused; the MRO assertion
below fails loudly if that happens.

Keys use the handler's stripped source line, never a line number, plus an
ORDINAL (1-based, in source order) among handlers with the SAME text in the
SAME function -- measured necessary: `marketdata._call_endpoint` holds three
identical `except SchwabApiError as exc:` lines (rows 8, 9, 10) and
`trader._call_endpoint` two (rows 15, 16), which a text-only key collapses.
"""
from __future__ import annotations

import ast
from pathlib import Path

from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabSchemaParityError,
)
from tests._22f_ast import (
    REPO_ROOT,
    enclosing_function,
    handler_type_names,
    iter_handlers,
    iter_sources,
    parent_map,
)

_COVER_PAIR = ("SchwabSchemaParityError", "_RedactedMessageError")

# (relative path under swing/, enclosing function, stripped handler line,
#  ordinal among same-text handlers in that function)
_H = "except SchwabApiError as exc:"
UNREACHABLE: dict[tuple[str, str, str, int], str] = {
    ("cli_schwab.py", "schwab_refresh", _H, 1):
        "try body is force_refresh: auth.py has no mapper and no Parity "
        "token (row 1)",
    ("cli_schwab.py", "schwab_logout", _H, 1):
        "try body is revoke_and_delete: no mapper (row 2)",
    ("integrations/schwab/auth.py", "force_refresh", _H, 1):
        "try body is token calls only; no mapper (row 7)",
    ("integrations/schwab/marketdata.py", "_call_endpoint", _H, 1):
        "try body is the raw HTTP call client_method(); no mapper (row 8)",
    ("integrations/schwab/marketdata.py", "_call_endpoint", _H, 2):
        "try body is _extract_response_payload, which raises SchwabApiError "
        "only (row 9)",
    ("integrations/schwab/trader.py", "_call_endpoint", _H, 1):
        "try body is the raw HTTP call client_method(); no mapper (row 15)",
    ("integrations/schwab/trader.py", "_call_endpoint", _H, 2):
        "try body is _extract_response_payload, which raises SchwabApiError "
        "only (row 16)",
}


def _names_api_error(handler: ast.ExceptHandler) -> bool:
    return "SchwabApiError" in handler_type_names(handler)


def _classify(tree: ast.AST, rel: str, lines: list[str]):
    """Yield (key, state) for every SchwabApiError handler in ``tree``."""
    parents = parent_map(tree)
    seen: dict[tuple[str, str, str], int] = {}
    pairs = sorted(iter_handlers(tree), key=lambda p: p[1].lineno)
    for try_node, handler in pairs:
        if not _names_api_error(handler):
            continue
        base = (rel, enclosing_function(handler, parents),
                lines[handler.lineno - 1].strip())
        seen[base] = seen.get(base, 0) + 1
        key = (*base, seen[base])
        if "SchwabSchemaParityError" in handler_type_names(handler):
            yield key, "WIDENED"
            continue
        siblings = [h for h in try_node.handlers if h is not handler]
        if any(n in _COVER_PAIR for h in siblings
               for n in handler_type_names(h)):
            yield key, "COVERED"
            continue
        yield key, "OPEN"


def _violations(root: Path) -> tuple[list, list, dict]:
    open_sites: list = []
    states: dict = {}
    matched: set = set()
    for rel, tree, lines in iter_sources(root, ("**/*.py",)):
        for key, state in _classify(tree, rel, lines):
            states[key] = state
            if state != "OPEN":
                continue
            if key in UNREACHABLE:
                matched.add(key)
            else:
                open_sites.append(key)
    stale = sorted(set(UNREACHABLE) - matched)
    return open_sites, stale, states


def test_the_cover_pair_is_in_the_parity_mro():
    """A re-base of `SchwabSchemaParityError` fails here, loudly."""
    mro_names = {c.__name__ for c in SchwabSchemaParityError.__mro__}
    assert set(_COVER_PAIR) <= mro_names
    assert not issubclass(SchwabSchemaParityError, SchwabApiError)


def test_every_schwab_api_error_handler_is_widened_covered_or_exempt():
    open_sites, stale, _states = _violations(REPO_ROOT / "swing")
    assert open_sites == [], open_sites
    assert stale == [], f"stale UNREACHABLE entries (match no handler): {stale}"


def _synthetic(src: str) -> list:
    tree = ast.parse(src)
    return [(k, s) for k, s in _classify(tree, "synthetic.py",
                                          src.splitlines())]


def test_the_walker_flags_a_new_bare_handler():
    """Not vacuous: a 19th `except SchwabApiError:` in a new function is
    OPEN."""
    got = _synthetic(
        "def new_site():\n"
        "    try:\n"
        "        f()\n"
        "    except SchwabApiError:\n"
        "        pass\n")
    assert got == [(("synthetic.py", "new_site", "except SchwabApiError:",
                     1), "OPEN")]


def test_a_broad_tail_does_not_cover():
    """Not vacuous: `except SchwabApiError` followed by `except Exception`
    is OPEN -- a broad tail never covers (R40)."""
    got = _synthetic(
        "def g():\n"
        "    try:\n"
        "        f()\n"
        "    except SchwabApiError:\n"
        "        pass\n"
        "    except Exception:\n"
        "        pass\n")
    assert [s for _k, s in got] == ["OPEN"]


def test_a_following_parity_clause_covers():
    """The R40 ordering fact: a parity clause AFTER the `SchwabApiError`
    clause covers it (disjoint classes; order inert)."""
    got = _synthetic(
        "def h():\n"
        "    try:\n"
        "        f()\n"
        "    except SchwabApiError:\n"
        "        pass\n"
        "    except SchwabSchemaParityError:\n"
        "        pass\n")
    assert [s for _k, s in got] == ["COVERED"]
