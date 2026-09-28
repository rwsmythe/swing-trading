"""R-4 (2026-09-28) -- ``scripts/probe_22i_guard_census.py``'s ``#SUMMARY``
undercounted INFO.

Located cause: ``exposure()`` (~:708-713 pre-fix) writes an
``E-exposure ... empty ... INFO`` row for every EMPTY exposure table
WITHOUT ``p.n_info += 1``. The three other direct INFO writes (in
``g0041()``) DID increment it. So a DB with two empty exposure tables
printed 142 INFO rows against ``#SUMMARY INFO=140``, which RD saw at the
22-I witness.

This test never opens the live DB (``~/swing-data/swing.db``) -- a fresh
temp DB, migrated to HEAD, is used throughout.
"""
from __future__ import annotations

import importlib.util
import io
import sqlite3
import sys
from pathlib import Path

from swing.data.db import run_migrations

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "probe_22i_guard_census.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "probe_22i_guard_census_r4", _SCRIPT,
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["probe_22i_guard_census_r4"] = mod
    spec.loader.exec_module(mod)
    return mod


def _fresh_migrated_db(tmp_path: Path) -> Path:
    """A bare DB migrated to HEAD, with NO domain data seeded -- every
    EXPOSURE table is empty, the exact shape that undercounted #SUMMARY at
    the 22-I witness (an empty exposure table's INFO row went uncounted)."""
    db = tmp_path / "r4.db"
    conn = sqlite3.connect(db)
    try:
        run_migrations(conn, backup_dir=tmp_path / "bak")
    finally:
        conn.close()
    return db


def _write_summary(mod, p, out) -> None:
    """Mirrors main()'s own tail write exactly."""
    out.write(f"#SUMMARY\tPASS={p.n_pass}\tFAIL={p.n_fail}\tINFO={p.n_info}\n")


def test_summary_info_count_matches_the_actual_INFO_rows_exposure_only(
    tmp_path: Path,
) -> None:
    """The narrowest reproduction: exposure() alone, on a DB where every
    EXPOSURE table is empty (n>=1 empty table -- the brief's requirement).
    Pre-fix, exposure() writes N raw INFO rows via p.out.write without ever
    touching p.n_info, so #SUMMARY INFO=0 while N rows carry verdict=INFO."""
    mod = _load()
    db = _fresh_migrated_db(tmp_path)
    out = io.StringIO()
    p = mod.Probe(db, out)
    try:
        mod.exposure(p)
    finally:
        p.conn.close()
    _write_summary(mod, p, out)

    lines = out.getvalue().splitlines()
    info_rows = [
        ln for ln in lines
        if not ln.startswith("#") and ln.split("\t")[-1] == "INFO"
    ]
    assert info_rows, "fixture premise failed: no empty exposure table found"
    summary_line = next(ln for ln in lines if ln.startswith("#SUMMARY"))
    summary_info = int(summary_line.split("INFO=")[1])
    assert len(info_rows) == summary_info, (
        len(info_rows), summary_info, "the INFO row count and #SUMMARY's own "
        "INFO tally have diverged",
    )


def test_summary_info_count_matches_on_a_mixed_populated_and_empty_world(
    tmp_path: Path,
) -> None:
    """A more realistic reproduction: exposure() on the standard ``world``
    seed fixture (tests/data/_22i_seed.py), which populates MOST but not
    ALL exposure tables -- the mixed populated-and-empty shape RD actually
    hit (two empty tables among many populated ones), rather than the
    narrowest all-empty case above."""
    from tests.data._22i_seed import migrated

    mod = _load()
    conn = migrated(tmp_path, 41, world=True)
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    conn.close()

    out = io.StringIO()
    p = mod.Probe(db_path, out)
    try:
        mod.exposure(p)
    finally:
        p.conn.close()
    _write_summary(mod, p, out)

    lines = out.getvalue().splitlines()
    info_rows = [
        ln for ln in lines
        if not ln.startswith("#") and ln.split("\t")[-1] == "INFO"
    ]
    # at least one exposure table must be empty for this to be a real
    # regression reproduction (per the brief) -- and at least one must be
    # populated, or this collapses into the all-empty case above.
    empty_rows = [r for r in info_rows if r.split("\t")[3] == "empty"]
    assert empty_rows, "fixture premise failed: no empty exposure table found"
    assert len(empty_rows) < len(mod.EXPOSURE), (
        "fixture premise failed: every exposure table was empty -- this "
        "test is meant to cover the MIXED case"
    )
    summary_line = next(ln for ln in lines if ln.startswith("#SUMMARY"))
    summary_info = int(summary_line.split("INFO=")[1])
    assert len(info_rows) == summary_info


def test_no_direct_INFO_write_bypasses_the_counter() -> None:
    """Closure check (the brief's watch item: 'can any other INFO write
    bypass the counter?'). Walks the script's AST tracking the enclosing
    function of every ``<attr>.out.write(...)`` call whose source literally
    contains ``"INFO"``: the only two legitimate homes for such a write are
    ``Probe.run`` (verdict computed dynamically -- its call site has no
    literal ``"INFO"`` text, so it never appears here) and
    ``Probe.info_row`` (the ONE centralized direct-INFO writer, added by
    this rider). Anything else is exactly the class of bug R-4 fixes."""
    import ast

    source = _SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.func_stack: list[str] = []
            self.offenders: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.func_stack.append(node.name)
            self.generic_visit(node)
            self.func_stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            is_out_write = (
                isinstance(node.func, ast.Attribute) and node.func.attr == "write"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "out"
            )
            if is_out_write:
                src = ast.get_source_segment(source, node) or ""
                # broad substring match, NOT `'"INFO"' in src` -- the exact
                # bug this rider fixed used an f-string (`f"...\tINFO\n"`),
                # where "INFO" never appears as its own quoted literal, so a
                # quote-anchored check would have missed the very pattern
                # R-4 exists to catch (verified: it passed unchanged against
                # BOTH the pre-fix and post-fix source until broadened).
                if "INFO" in src:
                    enclosing = self.func_stack[-1] if self.func_stack else "<module>"
                    if enclosing != "info_row":
                        self.offenders.append(f"{enclosing}: {src}")
            self.generic_visit(node)

    visitor = _Visitor()
    visitor.visit(tree)
    assert visitor.offenders == []
