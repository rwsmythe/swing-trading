"""22-A4 Task 1 -- migration 0038, at the SCHEMA grain.

Every assertion reads the LIVE schema (``sqlite_master``, ``PRAGMA``) or
EXECUTES a statement against it.  The two deliberate exceptions are (m6),
whose subject IS the stored DDL text, and (r5), whose subject is a property
of the SOURCE TREE rather than of the schema.
"""
from __future__ import annotations

import ast
import dataclasses
import re
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES,
    PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES,
    MigrationBackupRequiredException,
    _current_version,
    _phase22_arc_a4_backup_gate,
    ensure_schema,
    open_connection,
    run_migrations,
)
from swing.data.models import Trade
from swing.data.repos.trades import ATTEMPT_ID_LENGTH

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    REPO_ROOT / "swing" / "data" / "migrations" / "0038_trade_attempt_identity.sql"
)
SWING = REPO_ROOT / "swing"

TOK_A = "00000000-0000-4000-8000-000000000001"
TOK_B = "00000000-0000-4000-8000-000000000002"

# 0037's three tables.
ARC_A_TABLES = (
    "candidates_immutability_epoch",
    "latch_order_mandate_links",
    "fill_envelope_identity",
)


@pytest.fixture()
def conn(tmp_path: Path):
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def _v37(tmp_path: Path, name: str = "v37.db") -> sqlite3.Connection:
    c = open_connection(tmp_path / name)
    run_migrations(c, target_version=37, backup_dir=tmp_path / "bak37")
    return c


def _seed_trade(c: sqlite3.Connection, ticker: str, **over) -> int:
    cols = {
        "ticker": ticker,
        "entry_date": "2026-09-07",
        "entry_price": 10.0,
        "initial_shares": 1,
        "initial_stop": 9.0,
        "current_stop": 9.0,
        "state": "closed",
        "trade_origin": "manual_off_pipeline",
        "pre_trade_locked_at": "2026-09-07T16:00:00",
    }
    cols.update(over)
    names = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    cur = c.execute(
        f"INSERT INTO trades ({names}) VALUES ({marks})", tuple(cols.values()))
    return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# (m1) The column, the CHECK, and the version
# ---------------------------------------------------------------------------
def test_m1_the_column_the_check_and_the_version(tmp_path: Path) -> None:
    """The FIRST assertion is the declared first red: an AssertionError on the
    constant (it reads 37), not an OperationalError -- only the SQL that NAMES
    the column produces that transcript, and it is further down."""
    assert EXPECTED_SCHEMA_VERSION == 38
    c = open_connection(tmp_path / "m1.db")
    try:
        run_migrations(c, target_version=38, backup_dir=tmp_path / "bak")
        cols = {r[1] for r in c.execute("PRAGMA table_info(trades)")}
        assert "attempt_id" in cols

        _seed_trade(c, "NUL", attempt_id=None)
        _seed_trade(c, "OK", attempt_id=TOK_A)
        assert c.execute(
            "SELECT attempt_id FROM trades WHERE ticker = 'OK'"
        ).fetchone()[0] == TOK_A

        # An empty string, a 35-character string and a 36-BYTE BLOB are each
        # refused by the CHECK.  The BLOB is the one a length-only CHECK
        # ADMITS (MEASURED), which is what makes the typeof half testable.
        for bad in ("", "x" * 35, b"y" * 36):
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint"):
                _seed_trade(c, "BAD", attempt_id=bad)
    finally:
        c.close()


# ---------------------------------------------------------------------------
# (m2) The UNIQUE partial index
# ---------------------------------------------------------------------------
def test_m2_the_unique_partial_index(conn) -> None:
    _seed_trade(conn, "AAA", attempt_id=TOK_A)
    with pytest.raises(
            sqlite3.IntegrityError,
            match=r"UNIQUE constraint failed: trades\.attempt_id"):
        _seed_trade(conn, "BBB", attempt_id=TOK_A)
    # N rows with NULL tokens all commit -- the half a duplicate-only test
    # would not cover, and the reason the index is PARTIAL.
    for n in range(4):
        _seed_trade(conn, f"N{n}", attempt_id=None)
    assert conn.execute(
        "SELECT COUNT(*) FROM trades WHERE attempt_id IS NULL").fetchone()[0] == 4
    # AND THE INDEX IS ACTUALLY PARTIAL (Codex R1 Minor 7). MEASURED: SQLite
    # treats NULLs as distinct in a FULL unique index too, so the duplicate
    # assertion and the four-NULL assertion above pass IDENTICALLY against
    # `CREATE UNIQUE INDEX ux_trades_attempt_id ON trades(attempt_id)` with no
    # WHERE clause. `PRAGMA index_list` is the only column that differs.
    partial = {
        row[1]: row[4] for row in conn.execute("PRAGMA index_list('trades')")
    }
    assert partial["ux_trades_attempt_id"] == 1, (
        "ux_trades_attempt_id is a FULL unique index; the schema is supposed "
        "to say that uniqueness is a claim about MINTED tokens only")
    assert "WHERE attempt_id IS NOT NULL" in conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'ux_trades_attempt_id'"
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# (m3a)-(m3c) The backup gate
# ---------------------------------------------------------------------------
def test_m3a_the_gate_fires_only_on_the_exact_37_to_38_crossing(
        tmp_path: Path) -> None:
    """STRICT EQUALITY on pre_version per the ``pre_version == target - 1``
    gotcha -- NOT ``<=``.  The 36-and-target-38 case is what distinguishes."""
    c = _v37(tmp_path)
    try:
        backup_dir = tmp_path / "bak"
        _phase22_arc_a4_backup_gate(
            c, current_version=37, target_version=38, backup_dir=backup_dir)
        made = sorted(backup_dir.glob("swing-pre-22a4-migration-*.db"))
        assert len(made) == 1
        # a pre-37 baseline does NOT fire it
        _phase22_arc_a4_backup_gate(
            c, current_version=36, target_version=38, backup_dir=backup_dir)
        assert sorted(backup_dir.glob("swing-pre-22a4-migration-*.db")) == made
        # and neither does a target below 38
        _phase22_arc_a4_backup_gate(
            c, current_version=37, target_version=37, backup_dir=backup_dir)
        assert sorted(backup_dir.glob("swing-pre-22a4-migration-*.db")) == made
        # BUT A TARGET *ABOVE* 38 STILL FIRES IT (Codex R1 Major 4). The three
        # cases above are satisfied identically by `target_version == 38`, and
        # that mutant SKIPS the pre-0038 backup for a v37 installation jumping
        # straight to a later head -- the one crossing where the pre-image is
        # the only ordinary way back. `>=` is the assertion; `39` is what
        # distinguishes it.
        # A SEPARATE DIRECTORY, because the backup filename is stamped to the
        # SECOND and two calls inside one second would otherwise collide and
        # the count would read 1 -- an artifact of the clock, not of the gate.
        above = tmp_path / "bak_above_38"
        _phase22_arc_a4_backup_gate(
            c, current_version=37, target_version=39, backup_dir=above)
        assert len(sorted(
            above.glob("swing-pre-22a4-migration-*.db"))) == 1
    finally:
        c.close()


def test_m3a_the_gate_requires_a_file_backed_source() -> None:
    c = sqlite3.connect(":memory:")
    try:
        with pytest.raises(MigrationBackupRequiredException):
            _phase22_arc_a4_backup_gate(
                c, current_version=37, target_version=38, backup_dir=None)
    finally:
        c.close()


def test_m3b_run_migrations_invokes_the_gate_and_the_gate_is_load_bearing(
        tmp_path: Path, monkeypatch) -> None:
    """A gate that is WRITTEN and never WIRED passes a direct-call test, and a
    gate whose failure does not STOP the migration is decoration.  Both halves
    are asserted through the RUNNER."""
    from swing.data import db as db_mod

    bak = tmp_path / "runner_bak"
    c = _v37(tmp_path, "wired.db")
    try:
        run_migrations(c, target_version=38, backup_dir=bak)
        assert len(sorted(bak.glob("swing-pre-22a4-migration-*.db"))) == 1
        assert _current_version(c) == 38
    finally:
        c.close()

    def _refuse(*_a, **_k):
        raise MigrationBackupRequiredException("planted")

    c2 = _v37(tmp_path, "blocked.db")
    try:
        monkeypatch.setattr(db_mod, "_phase22_arc_a4_backup_gate", _refuse)
        with pytest.raises(MigrationBackupRequiredException, match="planted"):
            run_migrations(c2, target_version=38, backup_dir=tmp_path / "b2")
        assert _current_version(c2) == 37
        assert "attempt_id" not in {
            r[1] for r in c2.execute("PRAGMA table_info(trades)")}
    finally:
        c2.close()


def test_m3c_the_expected_table_set_is_pinned_against_a_real_v37_database(
        tmp_path: Path) -> None:
    """SUPERSEDED BY RULING (CHARC, PRIMARY, 2026-09-07): BRANCH A.

    The plan demanded EQUALITY against a freshly-built v37 schema while
    prescribing a derivation that yields 37 names against 42 real tables.
    ``_verify_backup_integrity`` reads ``missing = expected_tables -
    actual_tables`` (``swing/data/db.py:575``) -- a SUBSET test, so the gate's
    contract has ALWAYS been a FLOOR, and a pre-image carrying MORE tables is
    still a valid backup.  Equality would not widen the roster; it would
    REVERSE the gate's direction.  So this row asserts the two things the
    gate's contract actually needs: the constant is a SUBSET of a real v37
    schema (naming the offending member on failure), and 0037's three tables
    are MEMBERS of it.

    The equality the plan wanted is BANKED to CHARC's register as a separate
    schema-manifest drift comparator; it lives beside the backup gate, not
    inside it, and is deliberately NOT built here.
    """
    c = _v37(tmp_path)
    try:
        actual = {
            r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'")
        }
    finally:
        c.close()
    absent = PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES - actual
    assert not absent, (
        "the pre-migration expected-table set names a table a real v37 "
        f"database does not have: {sorted(absent)}")
    for name in ARC_A_TABLES:
        assert name in PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES, (
            f"0037 created {name!r} and the 22-A4 gate does not require it")
    # AND THE DECLARED INHERITANCE ITSELF (Codex R1 Major 5). The two
    # assertions above are satisfied by a mutant constant containing ONLY the
    # three 0037 tables -- they are real members of a real v37 schema, so the
    # subset holds -- which would silently drop every inherited backup
    # requirement. This is EQUALITY against the SPECIFIED PARENT-DERIVED SET,
    # which is a different claim from the equality-against-the-real-v37-schema
    # the CHARC ruling above rejects: that one would reverse the gate's
    # floor direction, this one pins the constant to its own definition.
    assert PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES == (
        PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES | set(ARC_A_TABLES)), (
        "the 22-A4 expected-table set is no longer its declared parent set "
        "plus 0037's three tables")


# ---------------------------------------------------------------------------
# (m4) Re-running the migration is a no-op
# ---------------------------------------------------------------------------
def test_m4_rerunning_the_migration_is_a_no_op(tmp_path: Path) -> None:
    c = _v37(tmp_path)
    try:
        run_migrations(c, target_version=38, backup_dir=tmp_path / "bak")
        run_migrations(c, target_version=38, backup_dir=tmp_path / "bak")
        assert _current_version(c) == 38
        cols = [r[1] for r in c.execute("PRAGMA table_info(trades)")]
        assert cols.count("attempt_id") == 1
        idx = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name = 'ux_trades_attempt_id'")]
        assert idx == ["ux_trades_attempt_id"]
    finally:
        c.close()


# ---------------------------------------------------------------------------
# (m5) Existing rows survive and backfill to NULL
# ---------------------------------------------------------------------------
def test_m5_existing_rows_survive_and_backfill_to_null(tmp_path: Path) -> None:
    """An ADD COLUMN must not renumber anything; this is the assertion that
    would notice if the migration were a REBUILD."""
    c = _v37(tmp_path)
    try:
        ids = [_seed_trade(c, t) for t in ("AAA", "BBB", "CCC")]
        before = c.execute(
            "SELECT id, ticker, entry_price, state FROM trades ORDER BY id"
        ).fetchall()
        c.commit()
        run_migrations(c, target_version=38, backup_dir=tmp_path / "bak")
        after = c.execute(
            "SELECT id, ticker, entry_price, state FROM trades ORDER BY id"
        ).fetchall()
        assert after == before
        assert [r[0] for r in after] == ids
        assert c.execute(
            "SELECT COUNT(*) FROM trades WHERE attempt_id IS NULL"
        ).fetchone()[0] == 3
    finally:
        c.close()


# ---------------------------------------------------------------------------
# (m6) DRIFT COMPARATOR #1 -- the CHECK text versus the Python constant
# ---------------------------------------------------------------------------
def test_m6_the_check_text_mirrors_the_python_constant(conn) -> None:
    """Asserting only the LENGTH fragment would certify a CHECK that admits a
    36-byte BLOB, which is the one thing a drift comparator must never do."""
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'trades'").fetchone()[0]
    assert "typeof(attempt_id) = 'text'" in ddl
    assert f"length(attempt_id) = {ATTEMPT_ID_LENGTH}" in ddl


# ---------------------------------------------------------------------------
# (m7) HALF 1 -- the token is WRITE-ONCE at the schema
# ---------------------------------------------------------------------------
def test_m7_half1_a_direct_update_of_attempt_id_aborts(conn) -> None:
    """The planted value is CHECK-VALID so the trigger is isolated from every
    other constraint.  MEASURED: a BEFORE UPDATE trigger fires FIRST, so an
    invalid value would ALSO abort with the trigger's message -- the
    discriminator is not the CHECK ordering, it is that the message names the
    trigger."""
    tid = _seed_trade(conn, "AAA", attempt_id=TOK_A)
    with pytest.raises(sqlite3.IntegrityError,
                       match="trg_trades_attempt_id_immutable"):
        conn.execute(
            "UPDATE trades SET attempt_id = ? WHERE id = ?", (TOK_B, tid))
    assert conn.execute(
        "SELECT attempt_id FROM trades WHERE id = ?", (tid,)
    ).fetchone()[0] == TOK_A
    # NULL -> token and token -> NULL are refused too: the trigger carries no
    # WHEN clause, because a WHEN that can evaluate to NULL fails OPEN.
    other = _seed_trade(conn, "BBB", attempt_id=None)
    with pytest.raises(sqlite3.IntegrityError,
                       match="trg_trades_attempt_id_immutable"):
        conn.execute(
            "UPDATE trades SET attempt_id = ? WHERE id = ?", (TOK_B, other))
    with pytest.raises(sqlite3.IntegrityError,
                       match="trg_trades_attempt_id_immutable"):
        conn.execute("UPDATE trades SET attempt_id = NULL WHERE id = ?", (tid,))


def test_m7_half1_the_trigger_is_UNCONDITIONAL_not_merely_change_detecting(
        conn) -> None:
    """Codex R1 Minor 8. The three transitions above are ALL value-CHANGING,
    so they pass identically against a trigger carrying
    ``WHEN OLD.attempt_id IS NOT NEW.attempt_id`` -- which would still permit
    ``SET attempt_id = attempt_id`` and would falsify the migration header's
    stated contract that EVERY update of the column is refused.

    Two independent halves, because each is weak alone: the same-value
    assignment ABORTS (behaviour), and the stored trigger SQL carries no
    ``WHEN`` at all (structure -- a ``WHEN`` clause that can evaluate to NULL
    fails OPEN and silently, which is why the contract is no-WHEN rather than
    a-correct-WHEN)."""
    tid = _seed_trade(conn, "AAA", attempt_id=TOK_A)
    with pytest.raises(sqlite3.IntegrityError,
                       match="trg_trades_attempt_id_immutable"):
        conn.execute(
            "UPDATE trades SET attempt_id = attempt_id WHERE id = ?", (tid,))
    trigger_sql = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE name = 'trg_trades_attempt_id_immutable'").fetchone()[0]
    assert "WHEN" not in trigger_sql.upper(), trigger_sql


def test_m7_half1_the_reversibility_header_names_both_droppables() -> None:
    """A property OF THE FILE, not of the schema, and it cannot be established
    any other way: the header must name BOTH retirement statements."""
    text = MIGRATION.read_text(encoding="utf-8")
    assert "DROP INDEX ux_trades_attempt_id;" in text
    assert "DROP TRIGGER trg_trades_attempt_id_immutable;" in text


# ---------------------------------------------------------------------------
# (r4) DRIFT COMPARATOR #2 -- the schema versus the model
# ---------------------------------------------------------------------------
def test_r4_schema_versus_model_drift(conn) -> None:
    """EQUALITY, NEVER A SUPERSET CHECK -- the mandatory member of the mirror
    set (gotcha #11's 2026-08-24 amendment: the comparator is the one mirror
    that does not depend on choosing the right grep).  A ``>=`` or subset form
    would silently absorb the next column added without a decision.

    ``risk_policy_id_at_lock``: stamped by ``record_entry`` in the entry
    transaction (Phase 9 T-A.7); read paths resolve the policy, so it is
    deliberately not a ``Trade`` field.
    ``attempt_id``: the 22-A4 per-attempt identity token.  It carries NO
    domain meaning, is never read by any consumer of ``Trade``, and is
    resolved by an id lookup, so it is deliberately not a ``Trade`` field
    either (S2.0's divergence, verified by CHARC on the live database).
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(trades)")}
    fields = {f.name for f in dataclasses.fields(Trade)}
    assert cols - fields == {"risk_policy_id_at_lock", "attempt_id"}


# ---------------------------------------------------------------------------
# (r5) STATIC CLOSURE CHECK -- every entry INSERT carries the column
# ---------------------------------------------------------------------------
_INSERT_TRADES = re.compile(r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+trades\b", re.I)

# THE REASONED EXCLUSION LIST.  Each entry is consumed AT MOST ONCE, which is
# what makes this a closure check rather than a predicate a new writer would
# also satisfy: a fifth statement duplicating an era fails the distinctness
# assertion below.
_EXCLUSIONS = {
    "v27_to_v37": (
        "the entry_intent era.  A v27-v37 database has no attempt_id column, "
        "and naming it would raise OperationalError: no such column."
    ),
    "v21_to_v26": (
        "the candidate_id/pattern_evaluation_id era, before entry_intent."
    ),
    "pre_v21": "the pre-backlink era.",
}


def _era_of(sql: str) -> str:
    if "entry_intent" in sql:
        return "v27_to_v37"
    if "candidate_id" in sql:
        return "v21_to_v26"
    return "pre_v21"


def _statements() -> list[tuple[str, str]]:
    """Every entry-INSERT statement in ``swing/``.

    STRING CONSTANTS via ``ast`` (so a statement cannot hide in a nested
    scope) PLUS a raw-text count per file, asserted equal, so the walk cannot
    be defeated by an f-string or any other construct the ast pass renders
    differently.  ``__pycache__`` is excluded, and the table name is matched as
    a TOKEN with a word boundary -- a raw substring also matches the Phase-7
    rebuild's ``trades_new``, a DIFFERENT table, which would otherwise be
    reported as an unreasoned writer.
    """
    found: list[tuple[str, str]] = []
    for path in sorted(SWING.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        raw_hits = len(_INSERT_TRADES.findall(text))
        if raw_hits == 0:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        ast_hits = 0
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                chunk = node.value
            elif isinstance(node, ast.JoinedStr):
                chunk = "".join(
                    v.value for v in node.values
                    if isinstance(v, ast.Constant) and isinstance(v.value, str)
                )
            else:
                continue
            hits = len(_INSERT_TRADES.findall(chunk))
            if hits:
                ast_hits += hits
                found.extend((rel, chunk) for _ in range(hits))
        assert ast_hits == raw_hits, (
            f"{rel}: {raw_hits} raw entry-INSERT statement(s) but the ast walk "
            f"found {ast_hits} -- one is hidden in a construct this walk does "
            "not render")
    return found


def test_r5_every_entry_insert_carries_the_column_or_is_excluded() -> None:
    stmts = _statements()
    assert len(stmts) == 4, (
        "expected FOUR entry-INSERT statements (one carrying the column plus "
        f"three reasoned era exclusions), found {len(stmts)}: "
        f"{sorted({p for p, _ in stmts})}")
    carrying = [s for s in stmts if "attempt_id" in s[1]]
    excluded = [s for s in stmts if "attempt_id" not in s[1]]
    assert len(carrying) == 1, (
        "exactly one entry-INSERT statement carries attempt_id; found "
        f"{len(carrying)}")
    assert len(excluded) == 3
    eras = [_era_of(sql) for _, sql in excluded]
    assert sorted(eras) == sorted(_EXCLUSIONS), (
        "every non-carrying entry-INSERT must map to a DISTINCT reasoned era "
        f"exclusion; got {sorted(eras)}")
    assert {p for p, _ in stmts} == {"swing/data/repos/trades.py"}


# ---------------------------------------------------------------------------
# (m9) THE FILE'S OWN TRANSACTION FRAMING -- Codex R1 Major 6
# ---------------------------------------------------------------------------
# Gotcha #9: `sqlite3.executescript()` issues an implicit COMMIT and runs its
# statements in AUTOCOMMIT, so a migration file without its own BEGIN/COMMIT
# could leave the column present with neither its index nor its immutability
# trigger, and the version stamp ahead of the schema. The success and rerun
# rows above pass identically against a file with the framing REMOVED, because
# nothing on the happy path ever fails partway.
def _executable_statements(sql_text: str) -> list[str]:
    """The migration's statements with comments and blank lines removed."""
    body = re.sub(r"--[^\n]*", "", sql_text)
    return [s.strip() for s in body.split(";") if s.strip()]


def test_m9_the_migration_is_framed_BEGIN_first_and_COMMIT_last() -> None:
    statements = _executable_statements(MIGRATION.read_text(encoding="utf-8"))
    assert statements[0].upper() == "BEGIN", statements[0]
    assert statements[-1].upper() == "COMMIT", statements[-1]
    # THE VERSION BUMP IS THE FINAL STATEMENT BEFORE COMMIT. A bump placed
    # ahead of later DDL would stamp a version the schema has not reached yet
    # if the transaction were ever truncated -- the Phase 9 section A.0
    # precedent this file's own header cites.
    assert statements[-2].upper().startswith("UPDATE SCHEMA_VERSION"), (
        statements[-2])


def test_m9_a_failure_inside_the_script_persists_NOTHING(
        tmp_path: Path) -> None:
    """The counterexample, and it is what makes the framing test more than a
    text assertion: plant a failing statement immediately before the version
    bump and assert a real v37 database is UNTOUCHED afterwards.

    Against a file with `BEGIN;`/`COMMIT;` REMOVED every earlier statement
    autocommits, so the column, the index and the trigger all persist and each
    assertion below fails. Against the shipped file the whole script is one
    transaction and the rollback undoes all of it."""
    text = MIGRATION.read_text(encoding="utf-8")
    marker = "UPDATE schema_version SET version = 38;"
    assert marker in text
    planted = text.replace(
        marker,
        "INSERT INTO a_table_that_does_not_exist_planted VALUES (1);\n"
        + marker,
    )
    c = _v37(tmp_path, "framing.db")
    try:
        with pytest.raises(sqlite3.OperationalError):
            c.executescript(planted)
        c.rollback()
        cols = {r[1] for r in c.execute("PRAGMA table_info(trades)")}
        assert "attempt_id" not in cols, cols
        names = {
            r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE name IN "
                "('ux_trades_attempt_id', 'trg_trades_attempt_id_immutable')")
        }
        assert names == set(), names
        assert _current_version(c) == 37
    finally:
        c.close()
