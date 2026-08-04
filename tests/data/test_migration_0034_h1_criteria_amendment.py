"""Migration 0034 - the H1 decision-criteria amendment (V2.1 section VII.F).

Governance amendment to a PRE-REGISTERED decision rule, so the acceptance
assertions here are the record of what was actually shipped.

THE REFERENT IS THE HASH, NEVER "matches the brief". The brief's section 1
renders the criterion WRAPPED across 8 markdown lines; the stored value is a
SINGLE LINE with wrap points collapsed to single spaces. "Byte-for-byte equal
to the brief" is therefore unfalsifiable -- the brief does not exist as those
bytes. Length 577 + sha256 6bdd723c... is the canonical referent (RD-derived,
CHARC-reproduced, and re-derived mechanically at authoring time from the
brief's own fenced block: three independent derivations, all agreeing).

The ORIGINAL pre-registered text is preserved on the row in the additive
nullable `preregistered_decision_criteria` column. NOT `status_change_reason`
-- see `test_the_preserved_original_survives_a_status_transition`, which is
the executable form of why that mechanism was rejected.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES,
    PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES,
    run_migrations,
)
from swing.data.repos.hypothesis import get_hypothesis

# --------------------------------------------------------------------------
# The canonical constants. This module OWNS them; other suites import them
# from here so a single edit cannot silently diverge across five files.
# --------------------------------------------------------------------------
AMENDED_H1_DECISION_CRITERIA = (
    "Mean R-multiple > 0 across the 20 closed labeled trades, AND no single trade "
    "contributes 50% or more of gross profit (gross profit = sum of positive "
    "R-multiples). COHORT: the 20 are STANDARD-intent trades only, per the "
    "2026-06-10 training-epoch declaration; pre-epoch hypothesis_test_by_design "
    "trades are settled tuition and do NOT count toward the 20. If the cohort has "
    "no winners, the mean-R criterion fails and the decision is negative. Win rate "
    "and its Wilson lower bound are REPORTED as diagnostics alongside median R and "
    "top-3 concentration, but do not gate the decision."
)

PREREGISTERED_H1_DECISION_CRITERIA = (
    "Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%"
)

_CANONICAL_SHA256 = (
    "6bdd723ce8a8ea1d00b8dbcfa7b50ec056a6282ee3a5110990b2f0894b7b3e73"
)
_CANONICAL_LENGTH = 577

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "swing" / "data" / "migrations"
    / "0034_h1_decision_criteria_amendment.sql"
)


def _v33(tmp_path: Path) -> sqlite3.Connection:
    """A RAW sqlite connection walked to v33. `connect()` refuses a
    non-current schema by design, so the raw form is the in-tree pattern."""
    conn = sqlite3.connect(str(tmp_path / "v33.db"))
    run_migrations(conn, target_version=33, backup_dir=tmp_path)
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 33
    return conn


def _v34(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "v34.db"))
    run_migrations(conn, target_version=34, backup_dir=tmp_path)
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 34
    return conn


def _criteria(conn: sqlite3.Connection) -> str:
    return conn.execute(
        "SELECT decision_criteria FROM hypothesis_registry "
        "WHERE name = 'A+ baseline'"
    ).fetchone()[0]


# --------------------------------------------------------------------------
# The hash. The one assertion the whole arc turns on.
# --------------------------------------------------------------------------
def test_the_module_constant_itself_hashes_to_the_canonical_digest():
    """Guards the CONSTANT above, which every other suite imports. Without
    this, a typo in the literal would propagate silently to five files and
    every one of them would agree with the typo."""
    assert len(AMENDED_H1_DECISION_CRITERIA) == _CANONICAL_LENGTH
    digest = hashlib.sha256(
        AMENDED_H1_DECISION_CRITERIA.encode("utf-8")).hexdigest()
    assert digest == _CANONICAL_SHA256


def test_stored_criterion_matches_the_canonical_hash(tmp_path):
    """RD acceptance 1, as CHARC replaced it: assert the DIGEST, never
    'matches brief section 1'."""
    conn = _v34(tmp_path)
    try:
        stored = _criteria(conn)
        assert len(stored) == _CANONICAL_LENGTH
        assert hashlib.sha256(
            stored.encode("utf-8")).hexdigest() == _CANONICAL_SHA256
        assert stored == AMENDED_H1_DECISION_CRITERIA
    finally:
        conn.close()


def test_stored_criterion_is_a_single_line_with_no_double_spaces(tmp_path):
    """The wrap points became SINGLE spaces. A migration that pasted the
    brief's wrapped block, or that joined on '\\n', fails here even if it
    somehow matched length -- and this names WHY the hash is 577."""
    conn = _v34(tmp_path)
    try:
        stored = _criteria(conn)
        assert "\n" not in stored
        assert "\r" not in stored
        assert "  " not in stored
        assert stored == stored.strip()
    finally:
        conn.close()


def test_the_cohort_clause_is_present_byte_for_byte(tmp_path):
    """The clause the operator added on 2026-07-29 changes a REAL count
    (H1 reads 2/20, not 3/20). Named explicitly so a future reader sees it
    was checked, not merely swept up by the digest."""
    conn = _v34(tmp_path)
    try:
        stored = _criteria(conn)
        assert (
            "COHORT: the 20 are STANDARD-intent trades only, per the "
            "2026-06-10 training-epoch declaration; pre-epoch "
            "hypothesis_test_by_design trades are settled tuition and do NOT "
            "count toward the 20."
        ) in stored
    finally:
        conn.close()


def test_the_migration_actually_changes_the_criterion(tmp_path):
    """The discriminator. A migration that shipped the ADD COLUMN and no
    UPDATE, or that wrote the amended text into a v33 DB that already held
    it, passes every other test in this file. This one asserts BOTH ends:
    v33 holds the pre-registered text, v34 holds the amended text."""
    conn = _v33(tmp_path)
    try:
        assert _criteria(conn) == PREREGISTERED_H1_DECISION_CRITERIA
        run_migrations(conn, target_version=34, backup_dir=tmp_path)
        assert _criteria(conn) == AMENDED_H1_DECISION_CRITERIA
    finally:
        conn.close()


# --------------------------------------------------------------------------
# The preservation mechanism
# --------------------------------------------------------------------------
def test_the_original_is_recoverable_verbatim_from_the_row(tmp_path):
    """RD acceptance 2 / CHARC acceptance 6."""
    conn = _v34(tmp_path)
    try:
        row = conn.execute(
            "SELECT preregistered_decision_criteria FROM hypothesis_registry "
            "WHERE name = 'A+ baseline'"
        ).fetchone()
        assert row[0] == PREREGISTERED_H1_DECISION_CRITERIA
    finally:
        conn.close()


def test_the_preserved_original_equals_the_0008_literal_on_disk(tmp_path):
    """Pins the preserved value against migration 0008's OWN source line
    rather than against a retyped copy of it. A drifted transcription fails
    here even though it would satisfy the test above."""
    src = (
        Path(__file__).resolve().parents[2]
        / "swing" / "data" / "migrations" / "0008_hypothesis_registry.sql"
    ).read_text(encoding="utf-8")
    assert f"'{PREREGISTERED_H1_DECISION_CRITERIA}'" in src
    conn = _v34(tmp_path)
    try:
        row = conn.execute(
            "SELECT preregistered_decision_criteria FROM hypothesis_registry "
            "WHERE name = 'A+ baseline'"
        ).fetchone()
        assert f"'{row[0]}'" in src
    finally:
        conn.close()


def test_the_column_is_null_on_every_other_row(tmp_path):
    """CHARC acceptance 7 + RD acceptance 3 (ids 2-5 untouched). NULL is
    DEFINED as 'never amended', not 'unknown'."""
    conn = _v34(tmp_path)
    try:
        rows = conn.execute(
            "SELECT name, preregistered_decision_criteria "
            "FROM hypothesis_registry WHERE name != 'A+ baseline' ORDER BY id"
        ).fetchall()
        assert len(rows) == 4
        assert all(r[1] is None for r in rows), rows
    finally:
        conn.close()


def test_the_migration_header_defines_the_null_semantic():
    """CHARC acceptance 7's second half. The NULL semantic is only safe
    BECAUSE it is written down; an undocumented NULL is 'unknown', which is
    the reading that would make rows 2-5 ambiguous."""
    header = _MIGRATION_PATH.read_text(encoding="utf-8").split("BEGIN;")[0]
    lowered = header.lower()
    assert "never been amended" in lowered
    assert "unknown" in lowered
    assert "preregistered_decision_criteria" in lowered


def test_the_preserved_original_survives_a_status_transition(tmp_path):
    """WHY `status_change_reason` WAS REJECTED, in executable form.

    Step 7 of every transition overwrites `status_change_reason`, and H1's
    criterion exists precisely to drive a transition at n=20 -- the
    preservation would have been destroyed by the very event it exists to
    inform. Nothing writes the new column at runtime, so it survives.
    """
    from swing.trades.hypothesis import update_hypothesis_status_with_audit

    conn = _v34(tmp_path)
    try:
        h1 = conn.execute(
            "SELECT id FROM hypothesis_registry WHERE name = 'A+ baseline'"
        ).fetchone()[0]
        outcome = update_hypothesis_status_with_audit(
            conn, hypothesis_id=h1, new_status="closed-target-met",
            change_reason="n=20 reached; criterion evaluated",
        )
        assert outcome == "transition"
        row = conn.execute(
            "SELECT preregistered_decision_criteria, decision_criteria, "
            "status, status_change_reason FROM hypothesis_registry "
            "WHERE id = ?", (h1,),
        ).fetchone()
        assert row[0] == PREREGISTERED_H1_DECISION_CRITERIA
        assert row[1] == AMENDED_H1_DECISION_CRITERIA
        assert row[2] == "closed-target-met"
        # The column the rejected mechanism would have used now holds the
        # transition reason -- i.e. it DID get clobbered.
        assert row[3] == "n=20 reached; criterion evaluated"
    finally:
        conn.close()


def test_the_model_and_repo_expose_both_texts(tmp_path):
    """Gotcha #11: the read-path mapper is widened in the SAME commit as the
    schema. A dataclass field added without widening `_SELECT_COLUMNS` reads
    None forever and nothing else notices."""
    conn = _v34(tmp_path)
    try:
        h1 = conn.execute(
            "SELECT id FROM hypothesis_registry WHERE name = 'A+ baseline'"
        ).fetchone()[0]
        entry = get_hypothesis(conn, h1)
        assert entry is not None
        assert entry.decision_criteria == AMENDED_H1_DECISION_CRITERIA
        assert entry.preregistered_decision_criteria == (
            PREREGISTERED_H1_DECISION_CRITERIA)
        other = get_hypothesis(conn, h1 + 1)
        assert other is not None
        assert other.preregistered_decision_criteria is None
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Additive-only + nothing else moved
# --------------------------------------------------------------------------
def test_the_registry_gains_exactly_one_column_and_loses_none(tmp_path):
    """RD acceptance 4 AS CORRECTED by the CHARC pass: this is NOT data-only.
    It is one additive nullable column -- and the delta is DERIVED from the
    real v33 shape, never hand-listed."""
    before = _v33(tmp_path)
    try:
        v33_cols = {
            r[1] for r in before.execute(
                "PRAGMA table_info(hypothesis_registry)")}
        v33_tables = {
            r[0] for r in before.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        run_migrations(before, target_version=34, backup_dir=tmp_path)
        v34_cols = {
            r[1] for r in before.execute(
                "PRAGMA table_info(hypothesis_registry)")}
        v34_tables = {
            r[0] for r in before.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        assert v34_cols == v33_cols | {"preregistered_decision_criteria"}
        assert v34_tables == v33_tables
    finally:
        before.close()


def test_the_new_column_is_nullable_text(tmp_path):
    conn = _v34(tmp_path)
    try:
        info = {
            r[1]: r for r in conn.execute(
                "PRAGMA table_info(hypothesis_registry)")}
        col = info["preregistered_decision_criteria"]
        assert col[2].upper() == "TEXT"
        assert col[3] == 0, "must be NULLable -- rows 2-5 carry NULL"
        assert col[4] is None, "no DEFAULT; NULL means never-amended"
    finally:
        conn.close()


def test_nothing_else_on_the_h1_row_changed(tmp_path):
    """RD acceptance 3: statement / target_sample_size / status untouched.
    Compared against the row's OWN v33 values, not against retyped copies."""
    conn = _v33(tmp_path)
    try:
        cols = ("statement, target_sample_size, status, "
                "consecutive_loss_tripwire, absolute_loss_tripwire_pct, "
                "created_at, status_changed_at, status_change_reason, notes")
        before = conn.execute(
            f"SELECT {cols} FROM hypothesis_registry WHERE name = 'A+ baseline'"
        ).fetchone()
        run_migrations(conn, target_version=34, backup_dir=tmp_path)
        after = conn.execute(
            f"SELECT {cols} FROM hypothesis_registry WHERE name = 'A+ baseline'"
        ).fetchone()
        assert after == before
        assert after[1] == 20, "target_sample_size stays 20"
        assert after[2] == "active"
    finally:
        conn.close()


def test_rows_two_through_five_are_byte_identical_across_the_migration(tmp_path):
    """RD acceptance 3: ids 2-5 untouched -- EVERY column, not just the new
    one. H2/H3/H4 do not gate on Wilson and H5 only REPORTS it."""
    cols = ("id, name, statement, target_sample_size, decision_criteria, "
            "status, consecutive_loss_tripwire, absolute_loss_tripwire_pct, "
            "created_at, status_changed_at, status_change_reason, notes")
    conn = _v33(tmp_path)
    try:
        before = conn.execute(
            f"SELECT {cols} FROM hypothesis_registry "
            "WHERE name != 'A+ baseline' ORDER BY id").fetchall()
        assert len(before) == 4
        run_migrations(conn, target_version=34, backup_dir=tmp_path)
        after = conn.execute(
            f"SELECT {cols} FROM hypothesis_registry "
            "WHERE name != 'A+ baseline' ORDER BY id").fetchall()
        assert after == before
    finally:
        conn.close()


def test_the_status_history_table_gains_no_row(tmp_path):
    """The amendment is NOT a status change. CHARC's rejection reason 2:
    fabricating one would make the denormalized row disagree with the audit
    table."""
    conn = _v33(tmp_path)
    try:
        before = conn.execute(
            "SELECT COUNT(*) FROM hypothesis_status_history").fetchone()[0]
        run_migrations(conn, target_version=34, backup_dir=tmp_path)
        after = conn.execute(
            "SELECT COUNT(*) FROM hypothesis_status_history").fetchone()[0]
        assert after == before
        assert conn.execute(
            "SELECT status_changed_at FROM hypothesis_registry "
            "WHERE name = 'A+ baseline'").fetchone()[0] is None
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Re-runnability
# --------------------------------------------------------------------------
def test_running_the_migration_twice_is_a_no_op(tmp_path):
    """CHARC acceptance 9. The preservation UPDATE writes a hard-coded
    LITERAL, not `SET preregistered = decision_criteria` -- the latter is
    idempotent-looking but on a second pass would preserve the AMENDED text
    and destroy the original. This test is what distinguishes them."""
    conn = _v34(tmp_path)
    try:
        run_migrations(conn, target_version=34, backup_dir=tmp_path)
        assert conn.execute(
            "SELECT version FROM schema_version").fetchone()[0] == 34
        row = conn.execute(
            "SELECT decision_criteria, preregistered_decision_criteria "
            "FROM hypothesis_registry WHERE name = 'A+ baseline'").fetchone()
        assert row[0] == AMENDED_H1_DECISION_CRITERIA
        assert row[1] == PREREGISTERED_H1_DECISION_CRITERIA
        assert conn.execute(
            "SELECT COUNT(*) FROM hypothesis_registry").fetchone()[0] == 5
    finally:
        conn.close()


def test_the_migration_applies_to_a_real_v33_db_without_error(tmp_path):
    """Catches SQL syntax, unbalanced quotes and unresolvable references --
    the class no prose review sees."""
    conn = _v33(tmp_path)
    try:
        run_migrations(conn, target_version=34, backup_dir=tmp_path)
        assert conn.execute(
            "SELECT version FROM schema_version").fetchone()[0] == 34
    finally:
        conn.close()


def test_the_migration_targets_by_name_not_by_id():
    """CHARC section 3.3: `name` is UNIQUE and is what the cohort readers key
    on; `id` is an autoincrement accident of seed order."""
    src = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "WHERE name = 'A+ baseline'" in src
    assert "WHERE id =" not in src


def test_the_migration_is_wrapped_in_an_explicit_transaction():
    """Gotcha #9: executescript runs in autocommit and _apply_migration does
    not open its own transaction, so a mid-script failure would leave the
    ADD COLUMN applied and the UPDATEs missing."""
    src = _MIGRATION_PATH.read_text(encoding="utf-8")
    body = src.split("BEGIN;", 1)[1]
    assert body.rstrip().endswith("COMMIT;")
    assert "UPDATE schema_version SET version = 34;" in body


# --------------------------------------------------------------------------
# Version + backup gate
# --------------------------------------------------------------------------
def test_expected_schema_version_is_34():
    assert EXPECTED_SCHEMA_VERSION == 34


def test_pre_migration_expected_tables_is_the_v33_set_derived():
    """0033 added exactly one table (`latch_order_intents`) on top of the
    21-B set, which already includes `latch_view_events`. DERIVED, never
    hand-listed."""
    assert H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES == (
        PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES | {"latch_order_intents"})


@pytest.mark.parametrize("current,target,should_fire", [
    (33, 34, True),    # THE intended case -- without this cell a gate whose
                       # body is an unconditional `return` passes the test
    (32, 34, False),   # multi-version jump bypasses by design; also the cell
                       # that discriminates a buggy `current_version <= 33`
    (33, 33, False),   # target below the gate
    (34, 34, False),   # already past
])
def test_backup_gate_fires_only_on_the_strict_33_to_34_step(
        tmp_path, monkeypatch, current, target, should_fire):
    """STRICT `current_version == 33 AND target_version >= 34`, per the
    `pre_version == (target - 1)` gotcha (NEVER `<=`)."""
    from swing.data import db as db_mod
    fired = []
    monkeypatch.setattr(
        db_mod, "_create_pre_h1_amendment_migration_backup",
        lambda src, *, dest_dir: (fired.append(src), tmp_path / "b.db")[1])
    monkeypatch.setattr(db_mod, "_verify_backup_integrity",
                        lambda path, *, expected_tables: None)
    monkeypatch.setattr(db_mod, "_resolve_main_db_path",
                        lambda conn: tmp_path / "src.db")
    db_mod._h1_amendment_backup_gate(
        sqlite3.connect(":memory:"), current_version=current,
        target_version=target, backup_dir=tmp_path)
    assert bool(fired) is should_fire


def test_backup_gate_verifies_against_the_declared_table_set(tmp_path, monkeypatch):
    """A gate that backs up but verifies nothing is a false net."""
    from swing.data import db as db_mod
    seen = {}
    monkeypatch.setattr(
        db_mod, "_create_pre_h1_amendment_migration_backup",
        lambda src, *, dest_dir: tmp_path / "b.db")
    monkeypatch.setattr(
        db_mod, "_verify_backup_integrity",
        lambda path, *, expected_tables: seen.update(t=expected_tables))
    monkeypatch.setattr(db_mod, "_resolve_main_db_path",
                        lambda conn: tmp_path / "src.db")
    db_mod._h1_amendment_backup_gate(
        sqlite3.connect(":memory:"), current_version=33,
        target_version=34, backup_dir=tmp_path)
    assert seen["t"] == H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES


def test_backup_snapshot_is_written_on_the_real_v33_to_v34_walk(tmp_path):
    """The gate is wired into run_migrations, not merely defined."""
    backups = tmp_path / "snaps"
    backups.mkdir()
    conn = sqlite3.connect(str(tmp_path / "live.db"))
    run_migrations(conn, target_version=33, backup_dir=backups)
    assert not list(backups.glob("swing-pre-h1-amendment-migration-*.db"))
    run_migrations(conn, target_version=34, backup_dir=backups)
    snaps = list(backups.glob("swing-pre-h1-amendment-migration-*.db"))
    assert len(snaps) == 1, snaps
    snap = sqlite3.connect(str(snaps[0]))
    try:
        assert snap.execute(
            "SELECT version FROM schema_version").fetchone()[0] == 33
        assert snap.execute(
            "SELECT decision_criteria FROM hypothesis_registry "
            "WHERE name = 'A+ baseline'").fetchone()[0] == (
                PREREGISTERED_H1_DECISION_CRITERIA)
    finally:
        snap.close()
        conn.close()
