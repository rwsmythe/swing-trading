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

_INSERT = (
    "INSERT INTO latch_view_events (candidate_id, evaluation_run_id, ticker, "
    "detection_date, pipeline_run_id, view_session_date, first_viewed_ts, "
    "last_viewed_ts, view_count, latch_state_at_first_view, "
    "latch_state_at_last_view) VALUES (?, 99, 'VSTS', ?, NULL, ?, "
    "'2026-06-25T10:00:00', '2026-06-25T10:00:00', 1, ?, 'armed')")


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


def test_expected_schema_version_is_32():
    assert EXPECTED_SCHEMA_VERSION == 32


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
        row = get_view(conn, evaluation_run_id=99, ticker="VSTS",
                       view_session_date="2026-06-25")
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
