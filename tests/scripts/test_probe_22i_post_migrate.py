"""22-I T18 step 1 -- ``scripts/probe_22i_guard_census.py --post-migrate``.

The flag adds ONE section, ``G-0041``, driven by the pure-data spec
(``tests/data/_22i_guard_spec.py``, loaded BY PATH so the probe never imports
``swing``). Per guarded table, on its first and last row by PK: A2 on each
conflict key, A4 the explicit conflicting PK, A6 DELETE, one UPDATE per
column with its class's refused transition (or, for a mutable / pending /
active column, an UPDATE the 0041 twin must NOT refuse), and per F column the
parent-PRESENT fk -> NULL.

On seeded temp DBs (``tests/data/_22i_seed.migrated``): at v41 ``G-0041``
reports FAIL = 0; at v40 EVERY abort-expected probe reports FAIL (the RED
control -- the section cannot pass without the triggers it names). The
probe's other sections need the live rows (trades 23/25) and are exercised on
the rehearsal copy, not here.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

from tests.data._22i_guard_spec import SPEC
from tests.data._22i_seed import migrated

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "probe_22i_guard_census.py"


def _load():
    spec = importlib.util.spec_from_file_location("probe_22i_guard_census", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["probe_22i_guard_census"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_g0041(tmp_path: Path, version: int) -> list[list[str]]:
    mod = _load()
    c = migrated(tmp_path, version, world=True)
    db = Path(c.execute("PRAGMA database_list").fetchone()[2])
    c.close()
    out = io.StringIO()
    p = mod.Probe(db, out)
    try:
        mod.g0041(p)
    finally:
        p.conn.close()
    return [ln.split("\t") for ln in out.getvalue().splitlines()
            if ln.startswith("G-0041\t")]


def test_the_probe_never_imports_swing() -> None:
    """By AST, not by text (prose may say "swing"): no import statement in
    the probe or in the spec it loads names the swing package."""
    import ast

    spec_path = _SCRIPT.parents[1] / "tests" / "data" / "_22i_guard_spec.py"
    for path in (_SCRIPT, spec_path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        mods = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                for a in n.names]
        mods += [n.module or "" for n in ast.walk(tree)
                 if isinstance(n, ast.ImportFrom)]
        assert not [m for m in mods if m == "swing" or m.startswith("swing.")], (
            path, mods)


@pytest.fixture(scope="module")
def rows41(tmp_path_factory: pytest.TempPathFactory) -> list[list[str]]:
    return _run_g0041(tmp_path_factory.mktemp("g41"), 41)


@pytest.fixture(scope="module")
def rows40(tmp_path_factory: pytest.TempPathFactory) -> list[list[str]]:
    return _run_g0041(tmp_path_factory.mktemp("g40"), 40)


def test_g0041_is_all_pass_at_41(rows41: list[list[str]]) -> None:
    assert rows41, "G-0041 emitted nothing"
    fails = [r for r in rows41 if r[-1] == "FAIL"]
    assert fails == [], fails[:10]


def test_g0041_covers_every_spec_table_and_every_0041_barrier(
        rows41: list[list[str]]) -> None:
    tables = {r[1].split("[", 1)[0] for r in rows41}
    assert tables == set(SPEC)
    named = {r[2] for r in rows41}
    for s in SPEC.values():
        for trig in s.triggers:
            assert trig in named, trig


def test_every_abort_expected_probe_fails_at_40(rows40: list[list[str]],
                                               rows41: list[list[str]]) -> None:
    """The RED control: at v40 (no 0041 triggers) every probe expecting a
    0041 trigger to FIRE reports FAIL -- and the same probe ids are the ones
    that PASS at 41."""
    fires40 = [r for r in rows40 if r[4].startswith("fires")]
    assert fires40
    assert all(r[-1] == "FAIL" for r in fires40), [
        r for r in fires40 if r[-1] != "FAIL"][:10]
    ids40 = {(r[1], r[3]) for r in fires40}
    ids41 = {(r[1], r[3]) for r in rows41 if r[4].startswith("fires")}
    assert ids40 == ids41
