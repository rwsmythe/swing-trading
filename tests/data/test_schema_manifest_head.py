"""D51 -- scripts/schema_manifest.py: the schema-manifest comparator.

This is the instrument, not just a test of it: `test_head_manifest_matches_fixture`
is what a future rebuild (22-B's `trades` DROP+CREATE, e.g.) trips when it forgets
to re-create an index or a trigger. Its own correctness is therefore verified RED
before being trusted GREEN -- see that test's docstring for the exact procedure
and what was observed.

Module load follows the `tests/scripts/` idiom (`importlib.util.spec_from_file_location`
+ `sys.modules` registration), same as `test_backup_inventory.py` -- this file lives
under `tests/data/` (not `tests/scripts/`) per the brief's C1 note on comparator
placement, but the load idiom is identical.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from swing.data.db import ensure_schema

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "schema_manifest.py"
_FIXTURE = Path(__file__).resolve().parent / "schema_manifest_head.tsv"


def _load():
    spec = importlib.util.spec_from_file_location("schema_manifest", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["schema_manifest"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load()


@pytest.fixture()
def head_conn(tmp_path):
    conn = ensure_schema(tmp_path / "head.db")
    yield conn
    conn.close()


# --- test 1: the instrument itself ------------------------------------------

def test_head_manifest_matches_fixture(head_conn):
    """Migrate an empty DB to HEAD, compare its manifest to the committed
    fixture. THIS IS THE INSTRUMENT (brief C3.1): the RED-then-GREEN proof was
    run by hand before this test was committed GREEN --

        1. Deleted the `index  ux_trades_attempt_id  trades  <hash>` line from
           `tests/data/schema_manifest_head.tsv` (the sole occurrence, verified
           via `grep -c ux_trades_attempt_id` before/after: 1 -> 0).
        2. Ran this test: it FAILED. `compare(...).render()` printed
           `unexpected:\n  index ux_trades_attempt_id (trades)` -- the object
           the deleted line named, correctly classified per this comparator's
           OWN definition (C1: "unexpected (in actual, not in expected)"):
           `head_conn` (actual) still has the index; the edited fixture
           (expected) no longer lists it. The brief's C3.1 worked example
           predicted this would print under `missing:` -- verified INCORRECT
           against both the C1 definition and all four C3.2 discriminators
           (below), which pin `missing` unambiguously to the opposite
           direction: an object the FIXTURE still expects but a MUTATED DB no
           longer has (see `test_dropped_index_shows_as_missing_only`, which
           demonstrates exactly that direction and is the comparator's
           motivating production scenario -- a rebuild that drops an index).
           Reported to the orchestrator as a verified brief-premise
           correction, not a code change: `compare()`'s argument order
           (`expected=fixture`, `actual=head`) is required by, and
           consistent with, C1's definition and every C3.2 discriminator: it
           could not be reversed to match the C3.1 prose without breaking
           discriminator (a).
        3. Restored the fixture line (byte-identical to the original --
           verified via the full 12-test run going green again, and via
           `wc -l` returning to 164 lines: 1 header comment + 163 objects).
        4. Ran this test again: GREEN.
    """
    expected = mod.load_manifest(_FIXTURE)
    actual = mod.read_manifest(head_conn)
    diff = mod.compare(expected, actual)
    assert diff.is_clean, diff.render()


# --- test 2: comparator discriminators, each via ONE raw mutation ----------

def test_dropped_index_shows_as_missing_only(head_conn):
    expected = mod.read_manifest(head_conn)
    head_conn.execute("DROP INDEX ux_trades_attempt_id")
    actual = mod.read_manifest(head_conn)
    diff = mod.compare(expected, actual)
    assert diff.missing == frozenset({("index", "ux_trades_attempt_id")})
    assert diff.unexpected == frozenset()
    assert diff.changed == frozenset()


def test_added_index_shows_as_unexpected_only(head_conn):
    expected = mod.read_manifest(head_conn)
    head_conn.execute("CREATE INDEX ix_probe ON trades(ticker)")
    actual = mod.read_manifest(head_conn)
    diff = mod.compare(expected, actual)
    assert diff.missing == frozenset()
    assert diff.unexpected == frozenset({("index", "ix_probe")})
    assert diff.changed == frozenset()


def test_trigger_recreated_with_different_body_shows_as_changed_only(head_conn):
    expected = mod.read_manifest(head_conn)
    head_conn.execute("DROP TRIGGER trg_trades_attempt_id_immutable")
    # Same name, same table, same event -- a DIFFERENT body (WHEN 0 makes it
    # never fire). A comparator hashing anything other than the normalized
    # `sql` text (e.g. rootpage, row order) would miss this.
    head_conn.execute(
        "CREATE TRIGGER trg_trades_attempt_id_immutable "
        "BEFORE UPDATE OF attempt_id ON trades WHEN 0 "
        "BEGIN SELECT RAISE(ABORT, 'weakened'); END"
    )
    actual = mod.read_manifest(head_conn)
    diff = mod.compare(expected, actual)
    assert diff.missing == frozenset()
    assert diff.unexpected == frozenset()
    assert diff.changed == frozenset({("trigger", "trg_trades_attempt_id_immutable")})


def test_trigger_recreated_with_identical_ddl_is_clean(head_conn):
    """The boundary twin of the CHANGED discriminator above: drop and
    re-create the SAME object with the SAME DDL text (read back from
    `sqlite_master.sql` first, not retyped by hand) -- this is the
    discriminator against a comparator that hashes something OTHER than the
    normalized text (rootpage, row order): a comparator drifting on either
    of those would show a spurious diff here even though nothing changed."""
    expected = mod.read_manifest(head_conn)
    original_sql = head_conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' "
        "AND name='trg_trades_attempt_id_immutable'"
    ).fetchone()[0]
    head_conn.execute("DROP TRIGGER trg_trades_attempt_id_immutable")
    head_conn.execute(original_sql)
    actual = mod.read_manifest(head_conn)
    diff = mod.compare(expected, actual)
    assert diff.is_clean, diff.render()


# --- test 3: fixture round-trip ---------------------------------------------

def test_write_then_load_manifest_round_trips(head_conn, tmp_path):
    rows = mod.read_manifest(head_conn)
    out_path = tmp_path / "roundtrip.tsv"
    mod.write_manifest(out_path, rows)
    loaded = mod.load_manifest(out_path)
    assert loaded == sorted(rows, key=lambda r: (r.type, r.name))


def test_committed_fixture_is_sorted_one_line_per_object():
    """151 non-autoindex objects (42 tables, 82 indexes, 27 triggers, 0
    views) + 12 sqlite_autoindex_* rows = 163 total, MEASURED by running
    `python -c` against `ensure_schema` on an empty DB and counting
    `sqlite_master` rows grouped by type both with and without the
    `sqlite_autoindex_%`/`sqlite_sequence`/`sqlite_stat%` exclusions (the
    same query `read_manifest` runs), independently of CHARC's 151-object
    HEAD measurement in the brief (which excluded autoindexes; this
    fixture INCLUDES them per brief C1/C2's `sqlite_autoindex_*` note)."""
    lines = [
        line for line in _FIXTURE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert len(lines) == 163
    rows = mod.load_manifest(_FIXTURE)
    keys = [(r.type, r.name) for r in rows]
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))  # exactly one line per object


# --- test 4: the CLI ---------------------------------------------------------

def test_cli_check_exits_zero_on_committed_fixture():
    rc = mod.main(["--check", "--fixture", str(_FIXTURE)])
    assert rc == 0


def test_cli_db_exits_zero_on_a_clean_head_db(tmp_path):
    db_path = tmp_path / "head.db"
    conn = ensure_schema(db_path)
    conn.close()
    rc = mod.main(["--db", str(db_path), "--fixture", str(_FIXTURE)])
    assert rc == 0


def test_cli_db_exits_one_and_prints_missing_line_when_index_dropped(tmp_path, capsys):
    db_path = tmp_path / "head.db"
    conn = ensure_schema(db_path)
    conn.execute("DROP INDEX ux_trades_attempt_id")
    conn.commit()
    conn.close()
    rc = mod.main(["--db", str(db_path), "--fixture", str(_FIXTURE)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing:" in out
    assert "index ux_trades_attempt_id (trades)" in out


def test_cli_db_never_writes_beside_a_read_only_target(tmp_path):
    """`--db` is READ-ONLY: assert the target file's own mtime and size are
    unchanged after the run (SQLite's own `-shm`/`-wal` sidecars from the
    `mode=ro` open are a separate, documented, EXPECTED byproduct -- see the
    script's module docstring -- and are not asserted against here)."""
    db_path = tmp_path / "head.db"
    conn = ensure_schema(db_path)
    conn.close()
    before = db_path.stat()
    rc = mod.main(["--db", str(db_path), "--fixture", str(_FIXTURE)])
    after = db_path.stat()
    assert rc == 0
    assert before.st_mtime_ns == after.st_mtime_ns
    assert before.st_size == after.st_size


def test_write_then_check_round_trips_through_the_cli(tmp_path):
    fixture_path = tmp_path / "fixture.tsv"
    rc_write = mod.main(["--write", "--fixture", str(fixture_path)])
    assert rc_write == 0
    assert fixture_path.exists()
    rc_check = mod.main(["--check", "--fixture", str(fixture_path)])
    assert rc_check == 0
