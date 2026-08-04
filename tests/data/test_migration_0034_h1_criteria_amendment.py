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
import re
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


def _header_prose(src: str) -> str:
    """The migration's comment header as one whitespace-normalized line.

    Strips only the LEADING `--` of each line (the header uses `--` inline as
    a dash too) and collapses runs of whitespace, so an assertion can span the
    header's line wrapping without depending on where it wraps.
    """
    head = src.split("BEGIN;", 1)[0]
    lines = [re.sub(r"^\s*--\s?", "", ln) for ln in head.splitlines()]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def test_the_migration_header_defines_the_null_semantic():
    """CHARC acceptance 7's second half. The NULL semantic is only safe
    BECAUSE it is written down; an undocumented NULL reads as 'unknown',
    which is what would make rows 2-5 ambiguous.

    Asserted as anchored PROPOSITIONS, not as loose substrings. Checking that
    the words "never been amended" and "unknown" merely APPEAR would pass on a
    header asserting the exact opposite -- "NULL means unknown; whether it was
    ever amended cannot be inferred" -- so the test has to pin what the header
    SAYS, not which words it contains.
    """
    prose = _header_prose(_MIGRATION_PATH.read_text(encoding="utf-8"))
    assert re.search(
        r"NULL means:? this row has never been amended", prose), prose
    assert re.search(r'NULL does NOT mean "unknown"', prose), prose
    assert "preregistered_decision_criteria" in prose


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
def _amendment_updates(src: str) -> list[str]:
    """The two `UPDATE hypothesis_registry` statements, lifted from the REAL
    migration file rather than retyped.

    Split on a semicolon that ENDS A LINE: both criterion texts contain an
    interior '; ' (mid-line, followed by a space), so a naive split on ';'
    would tear the literals apart. The count assertion below is the safety --
    a mis-parse fails the test loudly instead of silently testing nothing.
    """
    body = src.split("BEGIN;", 1)[1].rsplit("COMMIT;", 1)[0]
    stmts = []
    for chunk in re.split(r";\s*\n", body):
        # Drop the leading full-line `--` comments each statement carries.
        # Safe here: neither criterion literal contains a double hyphen.
        lines = [ln for ln in chunk.splitlines()
                 if not ln.strip().startswith("--")]
        s = "\n".join(lines).strip()
        if s:
            stmts.append(s)
    updates = [
        s + ";" for s in stmts
        if s.upper().startswith("UPDATE HYPOTHESIS_REGISTRY")
    ]
    assert len(updates) == 2, f"expected 2 registry UPDATEs, parsed {updates}"
    return updates


def test_running_the_migration_twice_through_the_runner_is_a_no_op(tmp_path):
    """The RUNNER-level property only: a second walk to 34 applies no SQL and
    leaves the row alone.

    This is deliberately NOT claimed as proof that the amendment DML is
    idempotent -- the runner skips an already-applied migration, so zero SQL
    executes and this would pass against almost any migration body. The DML
    itself is exercised by the replay test below.
    """
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


def test_replaying_the_amendment_dml_does_not_destroy_the_original(tmp_path):
    """CHARC acceptance 9, as a test that can actually FAIL.

    The preservation UPDATE writes a hard-coded LITERAL. The tempting
    alternative, `SET preregistered_decision_criteria = decision_criteria`,
    is correct on first application and CATASTROPHIC on any replay: it would
    preserve the ALREADY-AMENDED text and destroy the original -- silently,
    since both columns would then read plausibly. Replaying the real DML from
    the real file against an already-amended row is what distinguishes the
    two implementations; the runner-level test above cannot, because it
    executes no SQL at all.
    """
    conn = _v34(tmp_path)
    try:
        for stmt in _amendment_updates(
                _MIGRATION_PATH.read_text(encoding="utf-8")):
            conn.execute(stmt)
        conn.commit()
        row = conn.execute(
            "SELECT decision_criteria, preregistered_decision_criteria "
            "FROM hypothesis_registry WHERE name = 'A+ baseline'").fetchone()
        assert row[1] == PREREGISTERED_H1_DECISION_CRITERIA
        assert row[0] == AMENDED_H1_DECISION_CRITERIA
    finally:
        conn.close()


def test_the_preservation_update_never_reads_the_column_it_is_replacing():
    """The structural companion to the replay test. The preservation SET
    clause must not mention `decision_criteria` at all -- reading it is the
    whole defect."""
    src = _MIGRATION_PATH.read_text(encoding="utf-8")
    preservation = next(
        s for s in _amendment_updates(src)
        if "SET preregistered_decision_criteria" in s
    )
    set_clause = preservation.split("SET", 1)[1].split("WHERE", 1)[0]
    assert "decision_criteria" not in set_clause.replace(
        "preregistered_decision_criteria", "")


# --------------------------------------------------------------------------
# The guards: this migration REFUSES to fail open
# --------------------------------------------------------------------------
def test_the_migration_aborts_when_the_criterion_has_already_drifted(tmp_path):
    """The worst outcome this arc can produce is a FABRICATED preservation:
    a live row whose criterion had drifted, silently overwritten while this
    file's hard-coded copy is written in as the 'original'. The migration
    must refuse and leave v33 intact rather than manufacture the record."""
    conn = _v33(tmp_path)
    try:
        conn.execute(
            "UPDATE hypothesis_registry SET decision_criteria = 'tampered' "
            "WHERE name = 'A+ baseline'")
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError) as exc:
            run_migrations(conn, target_version=34, backup_dir=tmp_path)
        assert "h1_amendment_refuses_unless_exactly_one" in str(exc.value)
        assert conn.execute(
            "SELECT version FROM schema_version").fetchone()[0] == 33
        assert _criteria(conn) == "tampered"
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(hypothesis_registry)")}
        assert "preregistered_decision_criteria" not in cols, (
            "the ALTER must have rolled back with the rest of the script")
    finally:
        conn.close()


def test_the_migration_aborts_when_the_governance_row_is_missing(tmp_path):
    """UNIQUE(name) guarantees AT MOST one row, not exactly one. A zero-row
    UPDATE is not a SQL error, so without the guard this migration would
    report success having amended nothing."""
    conn = _v33(tmp_path)
    try:
        conn.execute(
            "DELETE FROM hypothesis_status_history WHERE hypothesis_id IN "
            "(SELECT id FROM hypothesis_registry WHERE name = 'A+ baseline')")
        conn.execute(
            "DELETE FROM hypothesis_registry WHERE name = 'A+ baseline'")
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError) as exc:
            run_migrations(conn, target_version=34, backup_dir=tmp_path)
        assert "h1_amendment_refuses_unless_exactly_one" in str(exc.value)
        assert conn.execute(
            "SELECT version FROM schema_version").fetchone()[0] == 33
    finally:
        conn.close()


_REGISTRY_SNAPSHOT_COLUMNS = (
    "id, name, statement, target_sample_size, decision_criteria, status, "
    "consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at, "
    "status_changed_at, status_change_reason, notes"
)


def test_a_post_guard_failure_rolls_back_the_ENTIRE_script(tmp_path):
    """The POST guard aborting is only half the property. The half that
    matters is that NOTHING survives it.

    Asserting merely "schema_version is still 33" would pass against exactly
    the dangerous shape this migration exists to prevent: the ADD COLUMN and
    the two UPDATEs committed while the version bump did not -- a live row
    silently amended, at a version that says it was not. So this drives a
    mutated migration (one `||` join's trailing space removed, giving a
    576-character criterion) through the PRODUCTION apply path, and then
    asserts the whole world is untouched.
    """
    from swing.data.db import _apply_migration

    src = _MIGRATION_PATH.read_text(encoding="utf-8")
    broken = src.replace(
        "|| 'contributes 50% or more of gross profit (gross profit = sum of positive '",
        "|| 'contributes 50% or more of gross profit (gross profit = sum of positive'",
    )
    assert broken != src, "the mutation anchor did not match the migration"
    mutated = tmp_path / "0034_mutated.sql"
    mutated.write_text(broken, encoding="utf-8")

    conn = _v33(tmp_path)
    try:
        before = conn.execute(
            f"SELECT {_REGISTRY_SNAPSHOT_COLUMNS} FROM hypothesis_registry "
            "ORDER BY id").fetchall()
        with pytest.raises(sqlite3.IntegrityError) as exc:
            _apply_migration(conn, mutated)
        assert "wrong_length_or_a_lost_preservation" in str(exc.value)

        # The production apply path owns the rollback; nothing left open.
        assert not conn.in_transaction
        # The ADD COLUMN is gone.
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(hypothesis_registry)")}
        assert "preregistered_decision_criteria" not in cols
        # No row was amended -- H1 still holds the pre-registered text.
        assert _criteria(conn) == PREREGISTERED_H1_DECISION_CRITERIA
        assert conn.execute(
            f"SELECT {_REGISTRY_SNAPSHOT_COLUMNS} FROM hypothesis_registry "
            "ORDER BY id").fetchall() == before
        # The version did NOT move.
        assert conn.execute(
            "SELECT version FROM schema_version").fetchone()[0] == 33
        # Neither guard's temp table survived.
        temp = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_temp_master WHERE type='table'")}
        assert not {t for t in temp if t.startswith("_h1_amendment")}, temp
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


def _executable_statements(src: str) -> list[str]:
    """The migration's statements with all full-line `--` comments removed."""
    lines = [ln for ln in src.splitlines()
             if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def test_the_migration_is_wrapped_in_an_explicit_transaction():
    """Gotcha #9: executescript runs in autocommit and _apply_migration does
    not open its own transaction, so a mid-script failure would leave the
    ADD COLUMN applied and the UPDATEs missing.

    Asserting only that `BEGIN;` appears SOMEWHERE is not enough -- that
    accepts an ALTER TABLE placed before it, or an early COMMIT that lets the
    version bump land outside the transaction. So pin the FIRST and LAST
    executable statements, and pin that COMMIT occurs exactly once.
    """
    src = _MIGRATION_PATH.read_text(encoding="utf-8")
    stmts = _executable_statements(src)
    assert stmts[0].upper() == "BEGIN", stmts[0]
    assert stmts[-1].upper() == "COMMIT", stmts[-1]
    assert sum(1 for s in stmts if s.upper() == "COMMIT") == 1
    assert sum(1 for s in stmts if s.upper() == "BEGIN") == 1
    assert "UPDATE schema_version SET version = 34" in stmts[-2]


# --------------------------------------------------------------------------
# Version + backup gate
# --------------------------------------------------------------------------
def test_expected_schema_version_is_34():
    assert EXPECTED_SCHEMA_VERSION == 34


def test_pre_migration_expected_tables_is_the_v33_set_derived():
    """0033 added exactly one table (`latch_order_intents`) on top of the
    21-B set, which already includes `latch_view_events`. DERIVED, never
    hand-listed -- plus `hypothesis_registry`, added explicitly."""
    assert H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES == (
        PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES
        | {"latch_order_intents", "hypothesis_registry"})


def test_the_backup_gate_requires_the_table_it_exists_to_preserve():
    """These expected-table sets are a PRESENCE subset, not a manifest, and
    the inherited chain never listed `hypothesis_registry` -- so this gate
    would have approved a backup missing the very governance row the backup
    is taken to preserve. A belt that does not check the one table its
    migration amends is not fail-closed."""
    assert "hypothesis_registry" in H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES
    assert ("hypothesis_registry"
            not in PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES), (
        "this test documents an inherited gap; if the shared chain is ever "
        "fixed, drop the explicit add rather than leaving both")


def test_a_backup_missing_the_governance_table_is_REJECTED(tmp_path):
    """The constant is only a belt if `_verify_backup_integrity` enforces it.
    Build a structurally valid v33 backup, drop `hypothesis_registry` from it,
    and require verification to refuse."""
    from swing.data import db as db_mod

    conn = _v33(tmp_path)
    try:
        backup = tmp_path / "b.db"
        dest = sqlite3.connect(str(backup))
        try:
            conn.backup(dest)
            dest.execute("DROP TABLE hypothesis_registry")
            dest.commit()
        finally:
            dest.close()
        with pytest.raises(Exception) as exc:
            db_mod._verify_backup_integrity(
                backup,
                expected_tables=H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES,
            )
        assert "hypothesis_registry" in str(exc.value), exc.value
    finally:
        conn.close()


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
