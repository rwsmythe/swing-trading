"""Migration 0032 - latch_view_events + the v31 -> v32 backup gate."""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES,
    ensure_schema,
)
from swing.latches.identity import LATCH_IDENTITY_COLUMNS

# NOTE (Arc 21-B): migration 0033 REBUILT this table, adding `surface` and the
# three actionability columns (all NOT NULL) and re-keying the UNIQUE onto
# (candidate_id, view_session_date, surface). This suite is the 0032-PRESERVATION
# suite -- every shape it proves the OLD table rejects, the NEW table must still
# reject -- so the raw INSERT is widened to the rebuilt column list and nothing
# else about what it asserts changes. The one place the rebuilt table is
# DELIBERATELY STRICTER than 0032 (the C.1.1 three-predicate date guard) is
# asserted in tests/data/test_migration_0033.py, against a REAL v32 fixture DB,
# so that the correction is proved to have CHANGED something.
_INSERT = (
    "INSERT INTO latch_view_events (candidate_id, evaluation_run_id, ticker, "
    "detection_date, pipeline_run_id, surface, view_session_date, "
    "first_viewed_ts, last_viewed_ts, view_count, latch_state_at_first_view, "
    "latch_state_at_last_view, actionable_at_first_view, "
    "actionable_at_last_view, actionable_ever_viewed) "
    "VALUES (?, 99, 'VSTS', ?, NULL, 'latch_panel', ?, "
    "'2026-06-25T10:00:00', '2026-06-25T10:00:00', 1, ?, 'armed', 1, 1, 1)")


def _fresh(tmp_path):
    """Schema + ONE real candidates row (candidate_id is NOT NULL / RESTRICT)."""
    conn = ensure_schema(tmp_path / "t.db")
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(99, '2026-06-24T20:06:25', '2026-06-24', '2026-06-25', 1, 1, 0, 0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(99, 'VSTS', 'aplus', 13.49, 13.56, 11.62, 'universe')")
    return conn, int(cur.lastrowid)


def test_expected_schema_version_is_current():
    """Bumped in lockstep by every schema migration (the project convention).

    0033 (Arc 21-B) took it to 33; the EXACT value is owned by the newest
    migration's own test (tests/data/test_migration_0033.py), and this
    assertion exists so a bump that misses a mirror fails loudly here too."""
    assert EXPECTED_SCHEMA_VERSION == 36


def test_table_exists_with_identity_block_first(tmp_path):
    conn, _ = _fresh(tmp_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(latch_view_events)")]
        assert cols[0] == "view_event_id"
        assert tuple(cols[1:6]) == LATCH_IDENTITY_COLUMNS
    finally:
        conn.close()


def test_candidate_id_is_not_null_and_restricts_deletes(tmp_path):
    """The IMMUTABLE BRIDGE KEY (Codex R2-2). NOT NULL, and a delete of the
    referenced candidates row must FAIL LOUDLY rather than silently severing
    the 21-A <-> 21-B join. SET NULL here would be the 'unrecoverable later'
    failure RD's finding 4 forbids."""
    conn, cid = _fresh(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, (None, "2026-06-25", "2026-06-25", "armed"))
        with conn:
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "armed"))
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute("DELETE FROM candidates WHERE id = ?", (cid,))
    finally:
        conn.close()


def test_state_check_rejects_an_unknown_state(tmp_path):
    conn, cid = _fresh(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "bogus"))
    finally:
        conn.close()


def test_state_check_accepts_every_value_in_latch_states(tmp_path):
    """#11 mirror: the SQL CHECK enum and the Python frozenset must not
    drift. `superseded` (the RD gate ruling) is the newest member."""
    from swing.latches.constants import LATCH_STATES
    conn, cid = _fresh(tmp_path)
    try:
        for i, state in enumerate(sorted(LATCH_STATES)):
            with conn:
                conn.execute(
                    _INSERT, (cid, "2026-06-25", f"2026-06-{25 - i:02d}", state))
        assert "superseded" in LATCH_STATES
    finally:
        conn.close()


def test_the_state_enum_agrees_across_all_three_mirrors():
    """The #11 discipline made mechanical (Codex R8-1). The migration CHECK,
    the domain frozenset and the dataclass validator's set must be the SAME
    set -- parsed from the migration SQL so a future widening that touches only
    one of the three FAILS here.

    This is the dangerous asymmetry direction: a CHECK that ACCEPTS a value the
    Python validator REJECTS means the DB holds rows the read path cannot
    hydrate."""
    import re

    from swing.data.db import _MIGRATIONS_DIR
    from swing.data.models import _LATCH_VIEW_STATES
    from swing.latches.constants import LATCH_STATES

    sql = (_MIGRATIONS_DIR / "0032_latch_view_telemetry.sql").read_text(
        encoding="utf-8")
    block = re.search(
        r"CHECK \(latch_state_at_first_view IN\s*\((.*?)\)\)", sql, re.S)
    assert block, "could not locate the latch_state_at_first_view CHECK"
    sql_states = set(re.findall(r"'([a-z_]+)'", block.group(1)))

    assert sql_states == LATCH_STATES == set(_LATCH_VIEW_STATES)
    assert "superseded" in sql_states


def test_the_model_validator_is_the_same_object_not_a_copy():
    """Drift is impossible by construction, not merely detected after the
    fact: models.py IMPORTS the frozenset rather than re-declaring it."""
    from swing.data.models import _LATCH_VIEW_STATES
    from swing.latches.constants import LATCH_STATES
    assert _LATCH_VIEW_STATES is LATCH_STATES


def test_a_view_event_round_trips_with_superseded_in_both_state_fields(tmp_path):
    """Codex R8-1: the schema accepts `superseded`, so the model MUST too --
    otherwise a persisted row cannot be hydrated by the read path."""
    from swing.data.repos.latch_view_events import get_view
    conn, cid = _fresh(tmp_path)
    try:
        with conn:
            conn.execute(
                _INSERT, (cid, "2026-06-25", "2026-06-25", "superseded"))
            conn.execute(
                "UPDATE latch_view_events SET latch_state_at_last_view "
                "= 'superseded'")
        row = get_view(conn, candidate_id=cid,
                       view_session_date="2026-06-25", surface="latch_panel")
        assert row.latch_state_at_first_view == "superseded"
        assert row.latch_state_at_last_view == "superseded"
    finally:
        conn.close()


def test_unique_triple_blocks_a_second_row_for_the_same_latch_session(tmp_path):
    conn, cid = _fresh(tmp_path)
    try:
        with conn:
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "armed"))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "armed"))
    finally:
        conn.close()


def test_malformed_detection_date_rejected(tmp_path):
    conn, cid = _fresh(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, (cid, "2026-6-25", "2026-06-25", "armed"))
    finally:
        conn.close()


def test_pre_migration_expected_tables_equals_the_v31_set():
    """0031 added NO table, so the v31 set == the 18-H.6 pre-migration set."""
    from swing.data.db import PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES
    assert PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES == (
        PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES)


@pytest.mark.parametrize("current,target,should_fire", [
    (31, 32, True),    # THE intended case -- without this cell a gate that
                       # NEVER fires passes the whole test (Codex R4-2)
    (30, 32, False),   # multi-version jump bypasses by design; also the cell
                       # that discriminates a buggy `current_version <= 31`
    (31, 31, False),   # target below the gate
    (32, 32, False),   # already past
])
def test_backup_gate_fires_only_on_the_strict_31_to_32_step(
        tmp_path, monkeypatch, current, target, should_fire):
    """STRICT `current_version == 31 AND target_version >= 32`, per the
    `pre_version == (target - 1)` gotcha (NEVER `<=`).

    The FULL boundary matrix is required. A single negative cell is not enough:
    a gate whose body is an unconditional `return` passes any all-negative
    test, and a silently-dead backup gate is the more dangerous failure of the
    two. (Verified arithmetic: cell (30,32) alone DOES discriminate the `<=`
    form, but nothing discriminated a dead gate until cell (31,32) was added.)
    """
    from swing.data import db as db_mod
    fired = []
    monkeypatch.setattr(
        db_mod, "_create_pre_phase21_arc_a_migration_backup",
        lambda src, *, dest_dir: (fired.append(src), tmp_path / "b.db")[1])
    monkeypatch.setattr(db_mod, "_verify_backup_integrity",
                        lambda path, *, expected_tables: None)
    monkeypatch.setattr(db_mod, "_resolve_main_db_path",
                        lambda conn: tmp_path / "src.db")
    db_mod._phase21_arc_a_backup_gate(
        sqlite3.connect(":memory:"), current_version=current,
        target_version=target, backup_dir=tmp_path)
    assert bool(fired) is should_fire


def test_backup_gate_verifies_against_the_declared_table_set(tmp_path, monkeypatch):
    """The gate must pass PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES to the
    verifier -- a gate that backs up but verifies nothing is a false net."""
    from swing.data import db as db_mod
    seen = {}
    monkeypatch.setattr(
        db_mod, "_create_pre_phase21_arc_a_migration_backup",
        lambda src, *, dest_dir: tmp_path / "b.db")
    monkeypatch.setattr(
        db_mod, "_verify_backup_integrity",
        lambda path, *, expected_tables: seen.update(t=expected_tables))
    monkeypatch.setattr(db_mod, "_resolve_main_db_path",
                        lambda conn: tmp_path / "src.db")
    db_mod._phase21_arc_a_backup_gate(
        sqlite3.connect(":memory:"), current_version=31,
        target_version=32, backup_dir=tmp_path)
    assert seen["t"] == PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES


def test_a_sqlite_normalisable_but_python_invalid_date_is_rejected(tmp_path):
    """Codex executing R5. `date('2026-02-30')` NORMALISES to '2026-03-02' --
    non-NULL and length 10 -- so the weaker `date(x) IS NOT NULL` CHECK ACCEPTS
    a value that `LatchViewEvent.__post_init__`'s `date.fromisoformat` REJECTS.
    That is the dangerous asymmetry: the DB holding rows the read path cannot
    hydrate. The CHECK requires ROUND-TRIP equality."""
    import datetime
    conn, cid = _fresh(tmp_path)
    try:
        # The premise, asserted inline so it cannot rot.
        assert conn.execute("SELECT date('2026-02-30')").fetchone()[0] == "2026-03-02"
        with pytest.raises(ValueError):
            datetime.date.fromisoformat("2026-02-30")
        # detection_date and view_session_date are both guarded.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, (cid, "2026-02-30", "2026-06-25", "armed"))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-02-30", "armed"))
    finally:
        conn.close()


def test_the_identity_block_must_match_its_candidate_id(tmp_path):
    """Codex executing R5. `candidate_id` is a real FK but `evaluation_run_id`,
    `ticker` and `detection_date` are denormalised COPIES, so without a trigger
    a row could point at FTRE's fire while carrying VSTS's evaluation identity
    -- making the 21-A <-> 21-B join disagree with itself about which latch the
    record describes. RD's finding 4 asks for the linkage to be EXACT rather
    than by convention."""
    conn, cid = _fresh(tmp_path)
    try:
        wrong_ticker = _INSERT.replace("'VSTS'", "'FTRE'")
        with pytest.raises(sqlite3.IntegrityError, match="identity block"):
            conn.execute(wrong_ticker, (cid, "2026-06-25", "2026-06-25", "armed"))
        wrong_run = _INSERT.replace(", 99, ", ", 4242, ")
        with pytest.raises(sqlite3.IntegrityError, match="identity block"):
            conn.execute(wrong_run, (cid, "2026-06-25", "2026-06-25", "armed"))
        # detection_date must be the FIRE's action_session_date (2026-06-25),
        # not some other session.
        with pytest.raises(sqlite3.IntegrityError, match="identity block"):
            conn.execute(_INSERT, (cid, "2026-06-24", "2026-06-25", "armed"))
        # ...and the coherent row still inserts.
        with conn:
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "armed"))
        assert conn.execute(
            "SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 1
    finally:
        conn.close()


def test_the_identity_trigger_also_guards_updates(tmp_path):
    """An UPDATE that re-points the identity block must fail the same way."""
    conn, cid = _fresh(tmp_path)
    try:
        with conn:
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "armed"))
        with pytest.raises(sqlite3.IntegrityError, match="identity block"):
            with conn:
                conn.execute("UPDATE latch_view_events SET ticker = 'FTRE'")
        # The repo's own monotonic UPDATE (view_count/last_viewed_ts) must NOT
        # be caught by the trigger -- it does not touch the identity columns.
        with conn:
            conn.execute(
                "UPDATE latch_view_events SET view_count = view_count + 1, "
                "last_viewed_ts = '2026-06-25T15:00:00'")
        assert conn.execute(
            "SELECT view_count FROM latch_view_events").fetchone()[0] == 2
    finally:
        conn.close()


def test_the_identity_trigger_requires_an_aplus_candidate(tmp_path):
    """Codex executing R6. A latch only ever describes an A+ FIRE, so a
    coherent-but-`watch` candidate must not be recordable as one."""
    conn = ensure_schema(tmp_path / "t.db")
    try:
        with conn:
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) VALUES "
                "(99, '2026-06-24T20:06:25', '2026-06-24', '2026-06-25', "
                "1, 0, 1, 0, 0, 0)")
            cur = conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(99, 'VSTS', 'watch', 13.49, 13.56, 11.62, 'universe')")
            watch_id = int(cur.lastrowid)
        with pytest.raises(sqlite3.IntegrityError, match="identity block"):
            conn.execute(_INSERT, (watch_id, "2026-06-25", "2026-06-25", "armed"))
    finally:
        conn.close()


def test_the_identity_trigger_requires_the_pipeline_twin_to_be_this_runs(tmp_path):
    """The DETECTION half of RD finding 4: a non-NULL `pipeline_run_id` must be
    THIS evaluation run's twin -- the exact linkage the reader derives it from.
    The two id spaces collide on integers, so a wrong twin is a live confusion
    trap rather than a theoretical one. A NULL twin stays legal (the normal case
    for every pre-June-2026 fire)."""
    conn, cid = _fresh(tmp_path)
    try:
        with conn:
            # A pipeline run linked to a DIFFERENT evaluation run.
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) VALUES "
                "(77, '2026-06-01T20:06:25', '2026-06-01', '2026-06-02', "
                "1, 0, 0, 0, 0, 0)")
            conn.execute(
                "INSERT INTO pipeline_runs (id, started_ts, trigger, state, "
                "lease_token, data_asof_date, action_session_date, "
                "evaluation_run_id) VALUES "
                "(500, '2026-06-01T17:00:00', 'manual', 'complete', 'lease-500', "
                "'2026-06-01', '2026-06-02', 77)")
        bad_twin = _INSERT.replace("NULL, 'latch_panel',", "500, 'latch_panel',")
        assert "500, 'latch_panel'," in bad_twin, (
            "the pipeline_run_id substitution must actually land -- the 21-B "
            "rebuild widened the INSERT column list, and a replace() that "
            "silently misses would leave this test asserting NOTHING")
        with pytest.raises(sqlite3.IntegrityError, match="twin"):
            conn.execute(bad_twin, (cid, "2026-06-25", "2026-06-25", "armed"))
        # NULL twin is fine.
        with conn:
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "armed"))
    finally:
        conn.close()
