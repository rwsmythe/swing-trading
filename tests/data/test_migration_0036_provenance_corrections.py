"""Migration 0036 -- the Demand C provenance-corrections audit table.

Every assertion reads the LIVE schema (`sqlite_master`, `PRAGMA`), never the
migration file's text: a test that greps the DDL it is validating proves only
that two strings match.

The `__post_init__` mirror is asserted at BOTH layers on each shape, because
they catch different callers -- a RAW `conn.execute` INSERT never constructs
the dataclass, so a validator-only design would accept every raw shape here,
and a CHECK-only design would let a caller build an incoherent row and only
discover it three statements later (#11).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    DEMAND_C_PRE_MIGRATION_EXPECTED_TABLES,
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _current_version,
    _demand_c_backup_gate,
    ensure_schema,
    open_connection,
    run_migrations,
)
from swing.data.models import (
    PROVENANCE_CORRECTED_FIELDS,
    ProvenanceCorrection,
)

RUN_TS_RAW = "2026-08-10T17:30:26"
FINISHED_RAW = "2026-08-10T17:44:45"
RUN_TS_UTC = "2026-08-11T03:30:26"
UPPER_UTC = "2026-08-11T03:44:45"
CAND_SESSION = "2026-08-11"
DR_SESSION = "2026-08-11"
FILL_SESSION = "2026-08-12"
FILL_DATETIME = "2026-08-12T16:00:00"


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def test_expected_schema_version_is_36() -> None:
    assert EXPECTED_SCHEMA_VERSION == 36


def test_migration_applies_and_stamps_version_36(conn) -> None:
    assert _current_version(conn) == 36


def test_table_and_both_indexes_exist_read_from_sqlite_master(conn) -> None:
    names = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','index')",
        ).fetchall()
    }
    assert "provenance_corrections" in names
    assert "ux_provenance_corrections_trade" in names
    assert "ix_provenance_corrections_cited_candidate" in names
    unique = conn.execute(
        "SELECT \"unique\" FROM pragma_index_list('provenance_corrections') "
        "WHERE name = 'ux_provenance_corrections_trade'",
    ).fetchone()[0]
    assert unique == 1


def test_every_declared_column_is_present_and_notnull_as_designed(conn) -> None:
    info = {
        r[1]: (r[2], r[3]) for r in conn.execute(
            "PRAGMA table_info(provenance_corrections)").fetchall()
    }
    # The two NULLABLE columns, and the reason each is nullable, are the whole
    # point of the design -- so they are named rather than inferred.
    nullable = {name for name, (_t, notnull) in info.items() if not notnull}
    assert nullable == {
        "provenance_correction_id",      # INTEGER PRIMARY KEY
        "entry_fill_id",                 # ON DELETE SET NULL by design
        "risk_policy_id_at_correction",  # ON DELETE SET NULL by design
        # NULL means the cited interval is STILL OPEN -- the shape the live H1
        # row has -- so it cannot be NOT NULL.
        "cited_hypothesis_status_effective_to",
    }
    for required in (
        "trade_id", "entry_fill_id_at_correction", "entry_fill_snapshot_json",
        "cited_candidate_id", "cited_daily_recommendation_id",
        "cited_evaluation_run_id", "cited_hypothesis_id",
        "cited_hypothesis_status_history_id",
        "cited_hypothesis_status_at_record", "cited_pipeline_finished_ts_raw",
        "cited_run_ts_utc", "cited_status_window_upper_utc",
        "cited_pipeline_run_id", "cited_pipeline_run_snapshot_json",
        "cited_hypothesis_status_recorded_at",
        "cited_hypothesis_status_effective_from",
        "cited_hypothesis_name_at_correction",
        "cited_candidate_action_session_date",
        "cited_recommendation_action_session_date",
        "entry_fill_session_date", "cited_run_ts_raw",
        "cited_recommendation_snapshot_json", "derivation_rule_version",
        "pre_value_json", "applied_value_json", "corrected_fields_json",
        "applied_at", "applied_by", "correction_reason",
    ):
        assert info[required][1] == 1, f"{required} must be NOT NULL"


def test_citation_fks_are_on_delete_restrict(conn) -> None:
    fks = {
        r[3]: (r[2], r[6]) for r in conn.execute(
            "PRAGMA foreign_key_list(provenance_corrections)").fetchall()
    }
    for col, table in (
        ("trade_id", "trades"),
        ("cited_candidate_id", "candidates"),
        ("cited_daily_recommendation_id", "daily_recommendations"),
        ("cited_evaluation_run_id", "evaluation_runs"),
        ("cited_hypothesis_id", "hypothesis_registry"),
        ("cited_hypothesis_status_history_id", "hypothesis_status_history"),
        ("cited_pipeline_run_id", "pipeline_runs"),
    ):
        assert fks[col] == (table, "RESTRICT"), col
    # The fill pointer is deliberately SET NULL: RESTRICT would make cohort
    # bookkeeping veto the money-bearing split handler.
    assert fks["entry_fill_id"] == ("fills", "SET NULL")
    assert fks["risk_policy_id_at_correction"] == ("risk_policy", "SET NULL")


def test_entry_fill_id_at_correction_carries_no_fk(conn) -> None:
    """It must SURVIVE the fill's deletion, so it cannot be an FK."""
    fk_cols = {
        r[3] for r in conn.execute(
            "PRAGMA foreign_key_list(provenance_corrections)").fetchall()
    }
    assert "entry_fill_id_at_correction" not in fk_cols


def test_rerunning_the_migration_is_a_clean_no_op(conn) -> None:
    before = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='provenance_corrections'",
    ).fetchone()[0]
    run_migrations(conn)
    run_migrations(conn)
    assert _current_version(conn) == 36
    after = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='provenance_corrections'",
    ).fetchone()[0]
    assert after == before


def test_backup_gate_fires_at_35_and_not_at_34_or_36(tmp_path: Path) -> None:
    """STRICT equality on pre_version, asserted in BOTH directions."""
    db = tmp_path / "swing.db"
    c = ensure_schema(db)
    try:
        backups = tmp_path / "backups"
        # 34 -> not this gate's crossing.
        _demand_c_backup_gate(
            c, current_version=34, target_version=36, backup_dir=backups)
        assert not list(backups.glob("swing-pre-demand-c-migration-*.db"))
        # 36 -> already across.
        _demand_c_backup_gate(
            c, current_version=36, target_version=36, backup_dir=backups)
        assert not list(backups.glob("swing-pre-demand-c-migration-*.db"))
        # target below 36 -> not this gate.
        _demand_c_backup_gate(
            c, current_version=35, target_version=35, backup_dir=backups)
        assert not list(backups.glob("swing-pre-demand-c-migration-*.db"))
        # The real crossing.
        _demand_c_backup_gate(
            c, current_version=35, target_version=36, backup_dir=backups)
        made = list(backups.glob("swing-pre-demand-c-migration-*.db"))
        assert len(made) == 1
        snap = open_connection(made[0])
        try:
            tables = {
                r[0] for r in snap.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'",
                ).fetchall()
            }
        finally:
            snap.close()
        assert DEMAND_C_PRE_MIGRATION_EXPECTED_TABLES <= tables
    finally:
        c.close()


def test_backup_gate_refuses_an_in_memory_connection() -> None:
    c = sqlite3.connect(":memory:")
    try:
        with pytest.raises(MigrationBackupRequiredException):
            _demand_c_backup_gate(
                c, current_version=35, target_version=36, backup_dir=None)
    finally:
        c.close()


# ---------------------------------------------------------------------------
# Row shapes -- asserted at BOTH layers.
# ---------------------------------------------------------------------------


def _seed_parents(conn: sqlite3.Connection) -> dict[str, int]:
    run = conn.execute(
        "INSERT INTO evaluation_runs (run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) "
        "VALUES (?, '2026-08-10', ?, 1, 1, 0, 0, 0, 0)",
        (RUN_TS_RAW, CAND_SESSION),
    ).lastrowid
    pipe = conn.execute(
        "INSERT INTO pipeline_runs (started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token, "
        "evaluation_run_id) VALUES (?, ?, 'scheduled', '2026-08-10', ?, "
        "'complete', 'tok', ?)",
        ("2026-08-10T17:30:00", FINISHED_RAW, CAND_SESSION, run),
    ).lastrowid
    cand = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
        "rs_method) VALUES (?, 'CADL', 'aplus', 'fallback_spy')",
        (run,),
    ).lastrowid
    dr = conn.execute(
        "INSERT INTO daily_recommendations (evaluation_run_id, "
        "data_asof_date, action_session_date, ticker, recommendation) "
        "VALUES (?, '2026-08-10', ?, 'CADL', 'today_decision')",
        (run, DR_SESSION),
    ).lastrowid
    trade = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, trade_origin, "
        "pre_trade_locked_at) "
        "VALUES ('CADL', ?, 10.81, 19, 9.16, 9.16, 'entered', "
        "'manual_off_pipeline', ?)",
        (FILL_SESSION, f"{FILL_SESSION}T16:00:00"),
    ).lastrowid
    fill = conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price) "
        "VALUES (?, ?, 'entry', 19, 10.81)",
        (trade, FILL_DATETIME),
    ).lastrowid
    conn.commit()
    return {
        "run": int(run), "pipeline": int(pipe), "candidate": int(cand),
        "dr": int(dr), "trade": int(trade), "fill": int(fill),
    }


def _row_kwargs(ids: dict[str, int], **overrides):
    base = dict(
        provenance_correction_id=None,
        trade_id=ids["trade"],
        entry_fill_id=ids["fill"],
        entry_fill_id_at_correction=ids["fill"],
        entry_fill_snapshot_json=json.dumps({
            "fill_id": ids["fill"], "trade_id": ids["trade"],
            "action": "entry", "fill_datetime": FILL_DATETIME,
        }, sort_keys=True),
        cited_candidate_id=ids["candidate"],
        cited_daily_recommendation_id=ids["dr"],
        cited_evaluation_run_id=ids["run"],
        cited_hypothesis_id=1,
        cited_hypothesis_status_history_id=1,
        cited_hypothesis_status_at_record="active",
        cited_pipeline_finished_ts_raw=FINISHED_RAW,
        cited_run_ts_utc=RUN_TS_UTC,
        cited_status_window_upper_utc=UPPER_UTC,
        cited_pipeline_run_id=ids["pipeline"],
        cited_pipeline_run_snapshot_json=json.dumps({
            "id": ids["pipeline"], "evaluation_run_id": ids["run"],
            "state": "complete", "started_ts": "2026-08-10T17:30:00",
            "finished_ts": FINISHED_RAW,
        }, sort_keys=True),
        cited_hypothesis_status_recorded_at="2026-04-25T00:00:00.000",
        cited_hypothesis_status_effective_from="2026-04-25T00:00:00.000",
        cited_hypothesis_status_effective_to=None,
        cited_hypothesis_name_at_correction="A+ baseline",
        cited_candidate_action_session_date=CAND_SESSION,
        cited_recommendation_action_session_date=DR_SESSION,
        entry_fill_session_date=FILL_SESSION,
        cited_run_ts_raw=RUN_TS_RAW,
        cited_recommendation_snapshot_json=json.dumps({
            "id": ids["dr"], "evaluation_run_id": ids["run"],
            "action_session_date": DR_SESSION, "ticker": "CADL",
        }, sort_keys=True),
        derivation_rule_version="2026-08-12.1",
        # The FULL three-key envelopes. The earlier one-key version claimed
        # all three corrected fields while carrying ONE -- a "well-formed"
        # fixture that the row's own manifest contradicted, and every
        # rejection test built on it inherited the defect.
        pre_value_json=json.dumps({
            "trades.hypothesis_label": None,
            "trades.candidate_id": None,
            "trades.trade_origin": "manual_off_pipeline",
        }, sort_keys=True),
        applied_value_json=json.dumps({
            "trades.hypothesis_label": "A+ baseline (aplus)",
            "trades.candidate_id": ids["candidate"],
            "trades.trade_origin": "pipeline_aplus",
        }, sort_keys=True),
        corrected_fields_json=json.dumps(list(PROVENANCE_CORRECTED_FIELDS)),
        applied_at="2026-08-13T00:00:00.000",
        applied_by="operator",
        correction_reason="because",
        risk_policy_id_at_correction=None,
    )
    base.update(overrides)
    return base


_COLUMNS = (
    "trade_id, entry_fill_id, entry_fill_id_at_correction, "
    "entry_fill_snapshot_json, cited_candidate_id, "
    "cited_daily_recommendation_id, cited_evaluation_run_id, "
    "cited_hypothesis_id, cited_hypothesis_status_history_id, "
    "cited_hypothesis_status_at_record, cited_pipeline_finished_ts_raw, "
    "cited_run_ts_utc, cited_status_window_upper_utc, cited_pipeline_run_id, "
    "cited_pipeline_run_snapshot_json, cited_hypothesis_status_recorded_at, "
    "cited_hypothesis_status_effective_from, "
    "cited_hypothesis_status_effective_to, "
    "cited_hypothesis_name_at_correction, "
    "cited_candidate_action_session_date, "
    "cited_recommendation_action_session_date, entry_fill_session_date, "
    "cited_run_ts_raw, cited_recommendation_snapshot_json, "
    "derivation_rule_version, pre_value_json, applied_value_json, "
    "corrected_fields_json, applied_at, applied_by, correction_reason, "
    "risk_policy_id_at_correction"
)


def _raw_insert(conn: sqlite3.Connection, kwargs: dict) -> int:
    names = [c.strip() for c in _COLUMNS.split(",")]
    values = [kwargs[n] for n in names]
    cur = conn.execute(
        f"INSERT INTO provenance_corrections ({_COLUMNS}) VALUES "
        f"({', '.join('?' * len(names))})",
        values,
    )
    return int(cur.lastrowid)


def test_a_well_formed_row_inserts_at_both_layers(conn) -> None:
    ids = _seed_parents(conn)
    kw = _row_kwargs(ids)
    ProvenanceCorrection(**kw)  # constructs
    assert _raw_insert(conn, kw) > 0


def test_second_row_for_one_trade_raises_integrity_error(conn) -> None:
    ids = _seed_parents(conn)
    _raw_insert(conn, _row_kwargs(ids))
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, _row_kwargs(ids))


@pytest.mark.parametrize("overrides", [
    # A post-dating candidate anchor.
    {"cited_candidate_action_session_date": "2026-08-13"},
    # A post-dating recommendation anchor.
    {"cited_recommendation_action_session_date": "2026-08-13"},
    # A non-active cited status.
    {"cited_hypothesis_status_at_record": "paused"},
    # A retrospective interval (recorded AFTER the window START, UTC).
    {"cited_hypothesis_status_recorded_at": "2026-08-11T03:30:27"},
    # An empty reason / rule version.
    {"correction_reason": "   "},
    {"derivation_rule_version": ""},
    # A non-operator author.
    {"applied_by": "system"},
])
def test_scalar_violations_are_rejected_at_both_layers(conn, overrides) -> None:
    ids = _seed_parents(conn)
    kw = _row_kwargs(ids, **overrides)
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, kw)


@pytest.mark.parametrize("bad_date", ["2026-99-99", "2026-02-30", "0000-01-01"])
def test_three_predicate_date_guard_rejects_at_both_layers(
    conn, bad_date,
) -> None:
    """The 0033 lesson: a SQLite CHECK PASSES on NULL, so `date(x) = x` alone
    accepts a length-correct invalid date; `IS NOT NULL` alone accepts a
    normalising one; the year floor catches year zero, which SQLite
    round-trips happily and `date.fromisoformat` RAISES on."""
    ids = _seed_parents(conn)
    kw = _row_kwargs(ids, cited_candidate_action_session_date=bad_date)
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, kw)


def test_week_date_form_is_rejected_at_both_layers(conn) -> None:
    """`2026-W31-5` is LENGTH 10 and `date.fromisoformat` parses it, so a
    length-plus-parseability mirror would accept what SQL refuses."""
    ids = _seed_parents(conn)
    kw = _row_kwargs(ids, cited_candidate_action_session_date="2026-W31-5")
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, kw)


@pytest.mark.parametrize("column,factory", [
    ("cited_recommendation_snapshot_json", "rec"),
    ("cited_pipeline_run_snapshot_json", "pipe"),
    ("entry_fill_snapshot_json", "fill"),
])
@pytest.mark.parametrize("shape", ["empty_object", "malformed", "wrong_id"])
def test_snapshot_shapes_rejected_at_both_layers(
    conn, column, factory, shape,
) -> None:
    ids = _seed_parents(conn)
    good = json.loads(_row_kwargs(ids)[column])
    if shape == "empty_object":
        bad = "{}"
    elif shape == "malformed":
        bad = "{not json"
    else:
        key = "fill_id" if factory == "fill" else "id"
        bad = json.dumps({**good, key: 987654}, sort_keys=True)
    kw = _row_kwargs(ids, **{column: bad})
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, kw)


@pytest.mark.parametrize("column,keys", [
    ("cited_recommendation_snapshot_json",
     ("id", "evaluation_run_id", "action_session_date")),
    ("cited_pipeline_run_snapshot_json",
     ("id", "evaluation_run_id", "state", "finished_ts")),
    ("entry_fill_snapshot_json",
     ("fill_id", "trade_id", "action", "fill_datetime")),
])
def test_partial_snapshot_missing_each_key_in_turn_is_rejected(
    conn, column, keys,
) -> None:
    """Existence != completeness: guarding `$.id` ALONE still accepted
    `{"id": 172}`, because the remaining comparisons went NULL and a SQLite
    CHECK passes on NULL. One case per key, not merely `{}`."""
    ids = _seed_parents(conn)
    good = json.loads(_row_kwargs(ids)[column])
    for dropped in keys:
        partial = {k: v for k, v in good.items() if k != dropped}
        kw = _row_kwargs(ids, **{column: json.dumps(partial, sort_keys=True)})
        with pytest.raises(ValueError):
            ProvenanceCorrection(**kw)
        with pytest.raises(sqlite3.IntegrityError):
            _raw_insert(conn, kw)


def test_pipeline_snapshot_finished_ts_must_be_the_RAW_bound(conn) -> None:
    """The round-5 shape: a snapshot whose `finished_ts` equals the NORMALIZED
    upper bound. The snapshot is the pipeline row verbatim, so it must match
    the naive-LOCAL column; matching the UTC one is proof of a mixed-domain
    write."""
    ids = _seed_parents(conn)
    snap = json.loads(_row_kwargs(ids)["cited_pipeline_run_snapshot_json"])
    snap["finished_ts"] = UPPER_UTC
    kw = _row_kwargs(
        ids, cited_pipeline_run_snapshot_json=json.dumps(snap, sort_keys=True))
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, kw)


def test_fill_snapshot_naming_a_different_fill_is_rejected(conn) -> None:
    ids = _seed_parents(conn)
    for bad in (
        {"fill_id": 999}, {"trade_id": ids["trade"] + 500},
        {"action": "exit"}, {"fill_datetime": "2026-08-11T16:00:00"},
    ):
        snap = json.loads(_row_kwargs(ids)["entry_fill_snapshot_json"])
        snap.update(bad)
        kw = _row_kwargs(
            ids, entry_fill_snapshot_json=json.dumps(snap, sort_keys=True))
        with pytest.raises(ValueError):
            ProvenanceCorrection(**kw)
        with pytest.raises(sqlite3.IntegrityError):
            _raw_insert(conn, kw)


def test_entry_fill_id_must_agree_with_the_frozen_scalar(conn) -> None:
    ids = _seed_parents(conn)
    other = conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price) "
        "VALUES (?, '2026-08-14T16:00:00', 'entry', 1, 1.0)",
        (ids["trade"],),
    ).lastrowid
    kw = _row_kwargs(ids, entry_fill_id=int(other))
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, kw)


@pytest.mark.parametrize("bad_fields", [
    ["trades.entry_date"],                       # not a member at all
    ["trades.hypothesis_label"],                 # a SUBSET, which the first
                                                 # draft accepted
    ["trades.hypothesis_label", "trades.candidate_id"],
    ["trades.candidate_id", "trades.hypothesis_label",
     "trades.trade_origin"],                     # right members, WRONG order
    [],
])
def test_corrected_fields_must_be_EXACTLY_the_manifest(conn, bad_fields):
    """A SUBSET rule accepted a row claiming ONE corrected field while the
    service always writes all three -- an audit row asserting a partial cohort
    assignment that cannot have happened."""
    ids = _seed_parents(conn)
    kw = _row_kwargs(ids, corrected_fields_json=json.dumps(bad_fields))
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, kw)


@pytest.mark.parametrize("column,bad", [
    # The APPLIED envelope naming a DIFFERENT candidate than the row cites.
    ("applied_value_json", {"trades.candidate_id": 987654}),
    # A partial envelope -- one key missing, which json_extract cannot
    # distinguish from a JSON null.
    ("applied_value_json", {"__drop__": "trades.trade_origin"}),
    ("pre_value_json", {"__drop__": "trades.candidate_id"}),
    # A PRE envelope that contradicts the unset-state gate that let the
    # correction be written at all.
    ("pre_value_json", {"trades.trade_origin": "pipeline_aplus"}),
    ("pre_value_json", {"trades.hypothesis_label": "already set"}),
    ("pre_value_json", {"trades.candidate_id": 5}),
])
def test_value_envelopes_must_describe_this_correction(conn, column, bad):
    """`pre_value_json` and `applied_value_json` were unconstrained TEXT that
    nothing ever parsed: a row could declare an applied candidate unrelated to
    `cited_candidate_id`, or a pre-state contradicting its own precondition."""
    ids = _seed_parents(conn)
    env = json.loads(_row_kwargs(ids)[column])
    if "__drop__" in bad:
        env.pop(bad["__drop__"])
    else:
        env.update(bad)
    kw = _row_kwargs(ids, **{column: json.dumps(env, sort_keys=True)})
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, kw)


@pytest.mark.parametrize("overrides", [
    # The interval begins AFTER the window starts.
    {"cited_hypothesis_status_effective_from": "2026-08-11T03:30:27"},
    # The interval ends INSIDE the window.
    {"cited_hypothesis_status_effective_to": "2026-08-11T03:40:00.000"},
    # ...or exactly at its upper bound (half-open: `to` must be STRICTLY past).
    {"cited_hypothesis_status_effective_to": UPPER_UTC},
])
def test_the_cited_interval_must_COVER_the_frozen_window(conn, overrides):
    """The FK pins WHICH history row was cited and does nothing about that row
    CHANGING; `update_close_open_interval` rewrites `effective_to` IN PLACE on
    every supported transition."""
    ids = _seed_parents(conn)
    kw = _row_kwargs(ids, **overrides)
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, kw)


def test_fk_enforcement_restricts_deleting_a_cited_candidate(conn) -> None:
    ids = _seed_parents(conn)
    _raw_insert(conn, _row_kwargs(ids))
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "DELETE FROM candidates WHERE id = ?", (ids["candidate"],))
    conn.rollback()


def test_inserting_a_nonexistent_candidate_citation_raises(conn) -> None:
    ids = _seed_parents(conn)
    kw = _row_kwargs(ids, cited_candidate_id=987654)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert(conn, kw)


def test_deleting_the_cited_fill_nulls_the_pointer_and_keeps_the_snapshot(
    conn,
) -> None:
    """The SET NULL half of the design, exercised directly: the pointer goes,
    the frozen number and the snapshot stay."""
    ids = _seed_parents(conn)
    cid = _raw_insert(conn, _row_kwargs(ids))
    conn.commit()
    conn.execute("DELETE FROM fills WHERE fill_id = ?", (ids["fill"],))
    conn.commit()
    row = conn.execute(
        "SELECT entry_fill_id, entry_fill_id_at_correction, "
        "entry_fill_snapshot_json FROM provenance_corrections "
        "WHERE provenance_correction_id = ?",
        (cid,),
    ).fetchone()
    assert row[0] is None
    assert row[1] == ids["fill"]
    assert json.loads(row[2])["fill_id"] == ids["fill"]
