"""Arc 22-B Task 3 -- migration 0040 part 1: the `trades` rebuild (one edit),
the N4 terminal trigger, the 22b gate, v40, and the four `latch_view_events`
evidence belts.

FORWARD RULE (R0.I): every migration case here pins ``target_version=40`` --
never HEAD. A claim about HEAD belongs to the `_head` tests only.
"""
from __future__ import annotations

import copy
import importlib.util
import re
import sqlite3
import sys
from pathlib import Path

import pytest

from swing.data import db as db_mod
from swing.data.db import _current_version, open_connection, run_migrations
from tests._22b_fixtures import (
    AMN_CANDIDATE_ID,
    LVE_ROW5,
    seed_amn_row5,
    seed_fire,
    seed_trade20,
)
from tests.data._migration_text import create_statement_in
from tests.docs._contract_reader import clause4_sha256

REPO_ROOT = Path(__file__).resolve().parents[2]
MIG_DIR = REPO_ROOT / "swing" / "data" / "migrations"
M0040 = MIG_DIR / "0040_entry_intent_unintended_execution.sql"
CLAUSE4_SHA256 = "5a78e547f64df25e0f891bd271c8d5e51bbd884866ca6d04c6c85b7803ef3886"

ONE_EDIT_FROM = "entry_intent IN ('standard','hypothesis_test_by_design')"
ONE_EDIT_TO = ("entry_intent IN ('standard','hypothesis_test_by_design',"
               "'unintended_execution')")

N4 = "trg_trades_entry_intent_attested_terminal"
LVE_BELTS = (
    "trg_lve_actionable_ever_viewed_monotonic",
    "trg_lve_no_delete",
    "trg_lve_no_replace",
    "trg_lve_view_window_immutable",
)
# b22_25: the D51 ADDITIONS of 0040 (CHARC-S3.2's expectation). One named
# constant, extended by Task 4 with the attestation objects + the two twins.
EXPECTED_0040_ADDITIONS: frozenset[tuple[str, str]] = frozenset(
    {("trigger", N4)} | {("trigger", b) for b in LVE_BELTS})

# The five `trades` dependants and the migration each is re-created from.
DEPENDANT_SOURCES = {
    "ux_trades_one_open_per_ticker": "0014_phase7_state_machine_and_fills.sql",
    "idx_trades_candidate_id": "0021_phase13_t2_sb6c_trades_backlinks.sql",
    "idx_trades_pattern_evaluation_id": "0021_phase13_t2_sb6c_trades_backlinks.sql",
    "ux_trades_attempt_id": "0038_trade_attempt_identity.sql",
    "trg_trades_attempt_id_immutable": "0038_trade_attempt_identity.sql",
}

# Messages (the assertions match the REFUSING object's own words).
N4_MSG = "entry_intent is attested"
MONOTONIC_MSG = "actionable_ever_viewed is monotonic"
NO_DELETE_MSG = "rows cannot be deleted"
NO_REPLACE_MSG = "a conflicting INSERT"
WINDOW_MSG = "first_viewed_ts and ticker are immutable"


def _manifest_module():
    path = REPO_ROOT / "scripts" / "schema_manifest.py"
    spec = importlib.util.spec_from_file_location("_b22_schema_manifest", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_b22_schema_manifest", mod)
    spec.loader.exec_module(mod)
    return mod


def _img(tmp_path: Path, name: str, version: int) -> sqlite3.Connection:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    c = open_connection(root / "swing.db")
    run_migrations(c, target_version=version, backup_dir=root / "bak")
    return c


def _to_40(c: sqlite3.Connection, tmp_path: Path, name: str = "bak40") -> None:
    run_migrations(c, target_version=40, backup_dir=tmp_path / name)
    assert _current_version(c) == 40


def _stored(c: sqlite3.Connection, name: str) -> str | None:
    row = c.execute("SELECT sql FROM sqlite_master WHERE name = ?",
                    (name,)).fetchone()
    return row[0] if row else None


def _plain(path: Path) -> sqlite3.Connection:
    """A plain sqlite3 connection (no service, no swing connect)."""
    c = sqlite3.connect(path)
    c.isolation_level = None
    return c


def _v40_path(tmp_path: Path, name: str = "v40") -> Path:
    c = _img(tmp_path, name, 40)
    c.close()
    return tmp_path / name / "swing.db"


# ---------------------------------------------------------------------------
# F6 / condition (1): the one-edit proof
# ---------------------------------------------------------------------------
def test_one_edit_of_the_v39_stored_ddl_equals_the_v40_stored_ddl_b22_20(
        tmp_path: Path) -> None:
    c = _img(tmp_path, "a", 39)
    try:
        v39 = _stored(c, "trades")
        assert v39.count(ONE_EDIT_FROM) == 1
        edited = v39.replace(ONE_EDIT_FROM, ONE_EDIT_TO)
        _to_40(c, tmp_path)
        v40 = _stored(c, "trades")
    finally:
        c.close()
    assert v40.encode("utf-8") == edited.encode("utf-8")


def _seed_children(c: sqlite3.Connection) -> None:
    """Three real-shape trades + a child row in each of the five FK tables."""
    seed_trade20(c)
    seed_trade20(c, id=21, ticker="CADL", notes="n", why_now="w",
                 entry_intent="standard", state="entered",
                 emotional_state_pre_trade=None)
    c.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
        "entry_intent, hypothesis_label) VALUES (22, 'VSTS', '2026-08-12', 7.5, "
        "10, 7.0, 7.0, 'entered', 'manual_off_pipeline', '2026-08-12T16:00:00', "
        "'hypothesis_test_by_design', 'H2 sub-a+ extension test')")
    c.execute("INSERT INTO trade_events (trade_id, ts, event_type) "
              "VALUES (20, '2026-08-07T16:00:00', 'entry')")
    c.execute(
        "INSERT INTO daily_management_records (trade_id, record_type, "
        "review_date, data_asof_session, created_at, mfe_mae_precision_level) "
        "VALUES (20, 'daily_snapshot', '2026-08-08', '2026-08-07', "
        "'2026-08-08T00:00:00', 'daily_approximate')")
    run_id = c.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES ('schwab_api', '2026-09-07T12:00:00', 'running')").lastrowid
    c.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, fill_id, ticker, field_name, expected_value_json, "
        "actual_value_json, material_to_review, resolution, ambiguity_kind, "
        "resolution_reason, created_at) VALUES (?, 'stop_mismatch', 20, NULL, "
        "'AMN', 'current_stop', '{\"current_stop\": 33.72}', "
        "'{\"current_stop\": 33.8}', 1, 'pending_ambiguity_resolution', "
        "'unsupported', 'fixture', '2026-09-07T12:00:00')", (run_id,))


CHILD_TABLES = ("fills", "daily_management_records", "trade_events",
                "reconciliation_discrepancies", "provenance_corrections")


def test_58_columns_in_order_and_every_row_tuple_identical_b22_21(
        tmp_path: Path) -> None:
    from tests._tier2_world_22a2 import (
        _seed_rows,
        base_last_word_payload,
        insert_payload,
        pinned_migration_clock,
    )

    payload = base_last_word_payload(tmp_path)
    root = tmp_path / "seeded"
    root.mkdir()
    c = open_connection(root / "swing.db")
    try:
        with pinned_migration_clock():
            run_migrations(c, target_version=39, backup_dir=root / "b39")
        _seed_rows(c, with_envelope_reading=True)
        insert_payload(c, payload)  # the provenance_corrections child
        _seed_children(c)
        c.commit()
        cols39 = list(c.execute("PRAGMA table_info(trades)"))
        rows39 = list(c.execute("SELECT * FROM trades ORDER BY id"))
        counts39 = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in CHILD_TABLES}
        with pinned_migration_clock():
            _to_40(c, tmp_path)
        cols40 = list(c.execute("PRAGMA table_info(trades)"))
        rows40 = list(c.execute("SELECT * FROM trades ORDER BY id"))
        counts40 = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in CHILD_TABLES}
        fk = list(c.execute("PRAGMA foreign_key_check"))
    finally:
        c.close()
    assert len(cols40) == 58
    assert cols40 == cols39
    assert len(rows39) >= 4 and rows40 == rows39
    notes20 = [r for r in rows40 if r[0] == 20][0]
    assert "condition disappeared.  This" in str(notes20)  # the two-space bytes
    assert counts40 == counts39 and all(counts39.values()), counts39
    assert fk == []


def test_the_partial_unique_still_refuses_a_second_open_trade_b22_22(
        tmp_path: Path) -> None:
    c = _plain(_v40_path(tmp_path))
    try:
        ins = ("INSERT INTO trades (ticker, entry_date, entry_price, "
               "initial_shares, initial_stop, current_stop, state, trade_origin, "
               "pre_trade_locked_at) VALUES ('ZZZ', '2026-08-01', 10, 1, 9, 9, "
               "?, 'manual_off_pipeline', '2026-08-01T16:00:00')")
        c.execute(ins, ("entered",))
        c.execute(ins, ("closed",))  # a closed twin is outside the partial index
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            c.execute(ins, ("managing",))
    finally:
        c.close()


def test_attempt_id_is_still_write_once_b22_23(tmp_path: Path) -> None:
    c = _plain(_v40_path(tmp_path))
    try:
        c.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
            "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
            "attempt_id) VALUES ('ZZZ', '2026-08-01', 10, 1, 9, 9, 'entered', "
            "'manual_off_pipeline', '2026-08-01T16:00:00', "
            "'2f1c3a4b-5d6e-4f70-8a9b-0c1d2e3f4a5b')")
        with pytest.raises(sqlite3.IntegrityError, match="WRITE-ONCE"):
            c.execute("UPDATE trades SET attempt_id = "
                      "'3f1c3a4b-5d6e-4f70-8a9b-0c1d2e3f4a5b'")
    finally:
        c.close()


def test_the_five_dependants_are_verbatim_from_their_sources_b22_24(
        tmp_path: Path) -> None:
    c = _img(tmp_path, "d", 40)
    try:
        for name, source in DEPENDANT_SOURCES.items():
            assert _stored(c, name) == create_statement_in(MIG_DIR / source, name), name
            assert create_statement_in(M0040, name) == create_statement_in(
                MIG_DIR / source, name), name
        names = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE tbl_name = 'trades' "
            "AND name NOT LIKE 'sqlite_autoindex%'")}
    finally:
        c.close()
    assert names == {"trades", N4, *DEPENDANT_SOURCES} | TRADES_TWINS_AT_TASK


# Task 3 creates no unattested twin (Task 4 does): the set of other `trades`
# objects created by 0040 at this commit.
TRADES_TWINS_AT_TASK: set[str] = set()


# ---------------------------------------------------------------------------
# R0.J: the bracket, the runner, the census, the foreign objects
# ---------------------------------------------------------------------------
_CENSUS_SQL = ("SELECT type, name FROM sqlite_master WHERE sql LIKE '%trades%' "
               "AND tbl_name <> 'trades' AND type IN ('trigger','view')")
# The 0040-created objects on OTHER tables whose bodies name `trades` (Task 4
# measures and fills it; empty before the attestation section exists).
V40_NEW_FOREIGN_TRADES_OBJECTS: frozenset[str] = frozenset()


def _foreign_trades_objects(c: sqlite3.Connection) -> dict[str, str]:
    return {name: _stored(c, name) for _t, name in c.execute(_CENSUS_SQL)}


def _citation_graph_fires(c: sqlite3.Connection, payload: dict) -> None:
    """A 22-A2 fully-cited row INSERTS; its one-mutation twin ABORTS with the
    citation-graph trigger's OWN message (a `no such table` error is a FAIL)."""
    from tests._tier2_world_22a2 import insert_payload

    twin = copy.deepcopy(payload)
    twin["cited_candidate_id"] = AMN_CANDIDATE_ID  # exists, wrong graph
    with pytest.raises(sqlite3.IntegrityError) as exc:
        insert_payload(c, twin)
    assert "no such table" not in str(exc.value)
    assert "do not form the citation graph" in str(exc.value), str(exc.value)
    c.rollback()
    insert_payload(c, payload)
    c.commit()
    assert c.execute("SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1


@pytest.mark.parametrize("shape", ["fresh", "seeded"])
def test_every_foreign_object_referencing_trades_is_unchanged_and_still_fires_b22_44(
        tmp_path: Path, shape: str) -> None:
    from swing.data.db import ensure_schema
    from tests._tier2_world_22a2 import (
        _seed_rows,
        base_last_word_payload,
        pinned_migration_clock,
    )

    payload = base_last_word_payload(tmp_path)
    root = tmp_path / shape
    root.mkdir()
    c = open_connection(root / "swing.db")
    try:
        with pinned_migration_clock():
            run_migrations(c, target_version=39, backup_dir=root / "b39")
        if shape == "seeded":
            _seed_rows(c, with_envelope_reading=True)
            seed_amn_row5(c)
            c.commit()
        v39 = _foreign_trades_objects(c)
        with pinned_migration_clock():
            _to_40(c, tmp_path, f"b40_{shape}")
        v40 = _foreign_trades_objects(c)
        if shape == "fresh":
            _seed_rows(c, with_envelope_reading=True)
            seed_amn_row5(c)
            c.commit()
        assert set(v39) == {"trg_provenance_corrections_citation_graph"}
        for name, sql in v39.items():
            assert v40[name] == sql, name
        assert set(v40) - set(v39) == V40_NEW_FOREIGN_TRADES_OBJECTS
        _citation_graph_fires(c, payload)
    finally:
        c.close()
    if shape == "fresh":
        # A separate ensure_schema DB's foreign-object set equals the v39 one
        # plus 0040's own named additions, byte for byte.
        with pinned_migration_clock():
            e = ensure_schema(tmp_path / "ensure" / "swing.db")
        try:
            assert _foreign_trades_objects(e) == v40
        finally:
            e.close()


def test_header_states_the_r0j_census_b22_46(tmp_path: Path) -> None:
    text = M0040.read_text(encoding="utf-8")
    header = text[: text.index("\nBEGIN;")]
    flat = " ".join(line.lstrip("- ").strip() for line in header.splitlines())
    for needle in (
        "WHERE sql LIKE '%trades%' AND tbl_name <> 'trades'",
        "AND type IN ('trigger','view')",
        "-> 1 row,", "trg_provenance_corrections_citation_graph",
        "0 views", "0 objects name trades_new",
    ):
        assert needle in flat, needle
    c = _img(tmp_path, "census", 39)
    try:
        rows = list(c.execute(_CENSUS_SQL))
        views = c.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='view'").fetchone()[0]
        trades_new = c.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE sql LIKE '%trades_new%'"
        ).fetchone()[0]
    finally:
        c.close()
    assert rows == [("trigger", "trg_provenance_corrections_citation_graph")]
    assert views == 0 and trades_new == 0


def _statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines()
                     if not line.lstrip().startswith("--"))
    return [s.strip() for s in body.split(";") if s.strip()]


def test_the_legacy_bracket_is_exactly_three_statements_b22_47() -> None:
    text = M0040.read_text(encoding="utf-8")
    stmts = _statements(text)
    idx = [i for i, s in enumerate(stmts) if "legacy_alter_table" in s]
    assert len(idx) == 2, idx
    assert stmts[idx[0]: idx[1] + 1] == [
        "PRAGMA legacy_alter_table=ON",
        "ALTER TABLE trades_new RENAME TO trades",
        "PRAGMA legacy_alter_table=OFF",
    ]


@pytest.mark.parametrize("prior", [0, 1])
def test_runner_restores_the_prior_legacy_alter_table_value_b22_45(
        tmp_path: Path, prior: int) -> None:
    bad = tmp_path / "9999_bad.sql"
    bad.write_text("BEGIN;\nPRAGMA legacy_alter_table=ON;\n"
                   "CREATE TABLE t_ok (x);\nSELECT * FROM no_such_table;\nCOMMIT;\n",
                   encoding="utf-8")
    c = sqlite3.connect(tmp_path / "r.db")
    try:
        c.execute(f"PRAGMA legacy_alter_table={'ON' if prior else 'OFF'}")
        with pytest.raises(sqlite3.OperationalError):
            db_mod._apply_migration(c, bad)
        assert c.execute("PRAGMA legacy_alter_table").fetchone()[0] == prior
    finally:
        c.close()
    (tmp_path / "ok").mkdir()
    c = open_connection(tmp_path / "ok" / "swing.db")
    try:
        run_migrations(c, target_version=39, backup_dir=tmp_path / "okb")
        c.execute(f"PRAGMA legacy_alter_table={'ON' if prior else 'OFF'}")
        _to_40(c, tmp_path, "okb40")
        assert c.execute("PRAGMA legacy_alter_table").fetchone()[0] == prior
    finally:
        c.close()


# ---------------------------------------------------------------------------
# D51: the manifest diff (CHARC-S3.2's expectation)
# ---------------------------------------------------------------------------
def test_the_manifest_diff_is_one_changed_table_plus_additions_zero_deletions_b22_25(
        tmp_path: Path) -> None:
    sm = _manifest_module()
    c39 = _img(tmp_path, "m39", 39)
    c40 = _img(tmp_path, "m40", 40)
    try:
        diff = sm.compare(sm.read_manifest(c39), sm.read_manifest(c40))
    finally:
        c39.close()
        c40.close()
    assert diff.changed == frozenset({("table", "trades")})
    assert diff.missing == frozenset()
    assert diff.unexpected == EXPECTED_0040_ADDITIONS


def test_run_twice_is_a_noop_b22_27(tmp_path: Path) -> None:
    sm = _manifest_module()
    c = _img(tmp_path, "twice", 40)
    try:
        before = sm.read_manifest(c)
        run_migrations(c, target_version=40, backup_dir=tmp_path / "again")
        run_migrations(c, target_version=40, backup_dir=tmp_path / "again")
        assert sm.compare(before, sm.read_manifest(c)).is_clean
        assert _current_version(c) == 40
    finally:
        c.close()
    again = tmp_path / "again"
    assert not again.exists() or not list(again.glob("*.db"))


def test_the_22b_gate_fires_once_from_39_and_the_cli_echoes_one_image_b22_28(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from click.testing import CliRunner

    from swing.cli import main
    from tests.cli.test_db_migrate_single_backup import _build, _config

    spec = db_mod.backup_gate_for_pre_version(39)
    assert spec is not None
    assert (spec.pre_version, spec.filename_stem, spec.gate_name, spec.label) == (
        39, "22b", "_phase22_arc_b_backup_gate", "pre-22-B")
    assert spec.expected_tables is db_mod.PHASE22_ARC_B_PRE_MIGRATION_EXPECTED_TABLES

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    cfg = _config(project, home)
    sd = home / "swing-data"
    _build(sd / "swing.db", 39)
    r = CliRunner().invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    images = sorted((sd / "backups").glob("swing-pre-22b-migration-*.db"))
    assert len(images) == 1, images
    assert f"Backup (pre-migration gate, integrity-verified): {images[0]}" in r.output
    assert re.fullmatch(r"swing-pre-22b-migration-\d{8}T\d{6}Z\.db", images[0].name)
    assert not list(sd.glob("swing-pre-*.db"))  # none in the DB's parent


def test_header_carries_the_clause4_hash_and_it_matches_the_doc_b22_29() -> None:
    text = M0040.read_text(encoding="utf-8")
    header = text[: text.index("\nBEGIN;")]
    found = re.findall(r"^-- clause \(4\) sha256: ([0-9a-f]{64}) ", header, re.M)
    assert found == [CLAUSE4_SHA256]
    assert found[0] == clause4_sha256()  # derived independently, fresh


def test_migration_never_reads_the_docs_tree_b22_30() -> None:
    text = M0040.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("--"))
    assert "docs/" not in code


# ---------------------------------------------------------------------------
# N4 layer 3 ALONE on plain sqlite3 (no service)
# ---------------------------------------------------------------------------
def _attested_trade(tmp_path: Path, *, drop: tuple[str, ...] = ()) -> Path:
    """A v40 DB carrying trade 20 with the value set (triggers that would
    refuse a raw plant are dropped for the PLANT only, then re-created)."""
    p = _v40_path(tmp_path, "n4")
    c = _plain(p)
    try:
        seed_trade20(c, entry_intent=None)
        saved = {n: _stored(c, n) for n in (
            "trg_trades_entry_intent_unattested_update",) if _stored(c, n)}
        for n in saved:
            c.execute(f"DROP TRIGGER {n}")
        c.execute("UPDATE trades SET entry_intent = 'unintended_execution' "
                  "WHERE id = 20")
        for sql in saved.values():
            c.execute(sql)
        for n in drop:
            c.execute(f"DROP TRIGGER {n}")
    finally:
        c.close()
    return p


@pytest.mark.parametrize("new", ["standard", None])
def test_raw_update_of_an_attested_row_aborts_b22_34(tmp_path: Path, new) -> None:
    c = _plain(_attested_trade(tmp_path))
    try:
        with pytest.raises(sqlite3.IntegrityError, match=N4_MSG):
            c.execute("UPDATE trades SET entry_intent = ? WHERE id = 20", (new,))
        assert c.execute("SELECT entry_intent FROM trades WHERE id=20"
                         ).fetchone()[0] == "unintended_execution"
    finally:
        c.close()


def test_same_value_update_passes_b22_35(tmp_path: Path) -> None:
    c = _plain(_attested_trade(tmp_path))
    try:
        c.execute("UPDATE trades SET entry_intent = 'unintended_execution' "
                  "WHERE id = 20")
        c.execute("UPDATE trades SET notes = notes WHERE id = 20")
    finally:
        c.close()


def test_null_to_value_passes_b22_36(tmp_path: Path) -> None:
    # N4 alone: NULL -> the value is the assignment direction (the unattested
    # twin of Task 4 is a DIFFERENT object, not under test here).
    p = _v40_path(tmp_path, "n36")
    c = _plain(p)
    try:
        seed_trade20(c)
        for n in ("trg_trades_entry_intent_unattested_update",):
            if _stored(c, n):
                c.execute(f"DROP TRIGGER {n}")
        c.execute("UPDATE trades SET entry_intent = 'unintended_execution' "
                  "WHERE id = 20")
        assert c.execute("SELECT entry_intent FROM trades WHERE id=20"
                         ).fetchone()[0] == "unintended_execution"
    finally:
        c.close()


# Barrier triggers whose WHEN is not `NOT COALESCE(...)`: each shown non-NULL
# by execution over its NULL operand combinations.
TOTAL_WHEN: tuple[str, ...] = (N4, "trg_lve_no_replace")
UNCONDITIONAL = ("trg_lve_no_delete", "trg_lve_view_window_immutable")


def _triggers_in_0040() -> dict[str, str]:
    text = M0040.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("--"))
    out = {}
    for m in re.finditer(r"CREATE TRIGGER (\w+)(.*?)\bEND;", code, re.S):
        out[m.group(1)] = m.group(2)
    return out


def test_the_trigger_when_clause_is_never_null_b22_37() -> None:
    # (1) N4's WHEN over every NULL operand combination is never NULL.
    probe = sqlite3.connect(":memory:")
    try:
        for old in (None, "standard", "unintended_execution"):
            for new in (None, "standard", "unintended_execution"):
                v = probe.execute(
                    "SELECT COALESCE(?, '') = 'unintended_execution' AND ? IS NOT ?",
                    (old, new, old)).fetchone()[0]
                assert v is not None, (old, new)
        # trg_lve_no_replace: EXISTS is never NULL, even over NULL operands.
        probe.execute("CREATE TABLE t (a, b, c, d)")
        probe.execute("INSERT INTO t VALUES (1, NULL, NULL, NULL)")
        for args in ((None, None, None, None), (1, None, None, None)):
            v = probe.execute(
                "SELECT EXISTS (SELECT 1 FROM t WHERE (? != -1 AND a = ?) "
                "OR (b = ? AND c = ? AND d = ?))",
                (args[0], args[0], args[1], args[2], args[3])).fetchone()[0]
            assert v in (0, 1)
    finally:
        probe.close()
    # (2) the static half: every 0040 trigger has `WHEN NOT COALESCE(`, OR is
    # on TOTAL_WHEN, OR has NO WHEN (an unconditional barrier).
    for name, body in _triggers_in_0040().items():
        head = body.split("BEGIN", 1)[0]
        has_when = re.search(r"\bWHEN\b", head) is not None
        if name in TOTAL_WHEN:
            assert has_when, name
        elif not has_when:
            assert name in UNCONDITIONAL or name == "trg_trades_attempt_id_immutable", name
        else:
            assert "WHEN NOT COALESCE(" in " ".join(head.split()), name


# ---------------------------------------------------------------------------
# The four latch_view_events belts (R0.G/R0.H; R0.K), row 5 planted RAW
# ---------------------------------------------------------------------------
def _lve_db(tmp_path: Path, *, drop: tuple[str, ...] = ()) -> sqlite3.Connection:
    c = _plain(_v40_path(tmp_path, "lve"))
    seed_amn_row5(c)
    for n in drop:
        c.execute(f"DROP TRIGGER {n}")
    return c


def test_lve_raw_downgrade_of_row5_aborts_b22_38(tmp_path: Path) -> None:
    c = _lve_db(tmp_path)
    try:
        c.execute("UPDATE latch_view_events SET actionable_at_last_view = 1, "
                  "actionable_ever_viewed = 1 WHERE view_event_id = 5")
        with pytest.raises(sqlite3.IntegrityError, match=MONOTONIC_MSG):
            c.execute("UPDATE latch_view_events SET actionable_ever_viewed = 0, "
                      "actionable_at_last_view = 0 WHERE view_event_id = 5")
    finally:
        c.close()


def _record_view(conn, *, viewed_ts: str, actionable: int,
                 session: str = "2026-08-03"):
    from swing.data.repos.latch_view_events import record_view
    from swing.latches.identity import LatchIdentity

    ident = LatchIdentity(
        candidate_id=AMN_CANDIDATE_ID, evaluation_run_id=LVE_ROW5["evaluation_run_id"],
        ticker="AMN", detection_date="2026-08-03",
        pipeline_run_id=LVE_ROW5["pipeline_run_id"])
    return record_view(conn, identity=ident, view_session_date=session,
                       surface="latch_panel", viewed_ts=viewed_ts,
                       latch_state="armed", actionable=actionable)


def test_lve_writer_zero_to_one_passes_b22_39(tmp_path: Path) -> None:
    c = _lve_db(tmp_path)
    try:
        _record_view(c, viewed_ts="2026-08-03T09:00:00", actionable=1)
        assert c.execute("SELECT actionable_ever_viewed, view_count FROM "
                         "latch_view_events WHERE view_event_id=5").fetchone() == (1, 5)
    finally:
        c.close()


def test_lve_same_value_update_passes_b22_40(tmp_path: Path) -> None:
    c = _lve_db(tmp_path)
    try:
        c.execute("UPDATE latch_view_events SET actionable_ever_viewed = 0 "
                  "WHERE view_event_id = 5")
    finally:
        c.close()


def test_lve_raw_delete_aborts_b22_41(tmp_path: Path) -> None:
    c = _lve_db(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match=NO_DELETE_MSG):
            c.execute("DELETE FROM latch_view_events WHERE view_event_id = 5")
        assert c.execute("SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 1
    finally:
        c.close()


@pytest.mark.parametrize("key", ["unique_key", "primary_key"])
def test_lve_insert_or_replace_on_row5_key_aborts_b22_42(
        tmp_path: Path, key: str) -> None:
    c = _lve_db(tmp_path)
    try:
        c.execute("UPDATE latch_view_events SET actionable_at_last_view = 1, "
                  "actionable_ever_viewed = 1 WHERE view_event_id = 5")
        row = dict(LVE_ROW5)
        row["actionable_ever_viewed"] = 0
        if key == "unique_key":
            del row["view_event_id"]
        else:
            row["view_session_date"] = "2026-08-04"  # a different UNIQUE key
        cols = ", ".join(row)
        with pytest.raises(sqlite3.IntegrityError, match=NO_REPLACE_MSG):
            c.execute(f"INSERT OR REPLACE INTO latch_view_events ({cols}) "
                      f"VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
        assert c.execute("SELECT actionable_ever_viewed FROM latch_view_events "
                         "WHERE view_event_id=5").fetchone() == (1,)
    finally:
        c.close()


def test_lve_plain_insert_on_existing_key_takes_the_update_path_b22_43(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from swing.data.repos import latch_view_events as lve

    c = _lve_db(tmp_path)
    try:
        real = lve.get_view
        calls = {"n": 0}

        def once_none(*a, **k):
            calls["n"] += 1
            return None if calls["n"] == 1 else real(*a, **k)

        monkeypatch.setattr(lve, "get_view", once_none)
        _record_view(c, viewed_ts="2026-08-03T09:00:00", actionable=1)
        assert calls["n"] >= 2  # the lost-race handler re-read the row
        assert c.execute(
            "SELECT view_count, actionable_ever_viewed FROM latch_view_events "
            "WHERE view_event_id = 5").fetchone() == (5, 1)
        assert c.execute("SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 1
    finally:
        c.close()


_WINDOW_CASES = {
    # (A) RD's discriminator verbatim: on row 5 it ALSO violates the table
    # CHECK last_viewed_ts >= first_viewed_ts, so only the MESSAGE discriminates.
    "rd_verbatim": ("UPDATE latch_view_events SET first_viewed_ts="
                    "'2026-08-03T00:00:00' WHERE view_event_id=5", "CHECK"),
    # (B) the CHECK-clean manufacturing move: row 5 into the SPEAK window as a 0.
    "check_clean_move": ("UPDATE latch_view_events SET first_viewed_ts="
                         "'2026-08-03T00:00:00', last_viewed_ts="
                         "'2026-08-03T00:00:00' WHERE view_event_id=5", None),
    # (C) a same-value SET: UPDATE OF fires on the SET list.
    "same_value": ("UPDATE latch_view_events SET first_viewed_ts = "
                   "first_viewed_ts WHERE view_event_id=5", None),
}


@pytest.mark.parametrize("case", list(_WINDOW_CASES))
def test_lve_raw_first_viewed_ts_update_of_row5_aborts_b22_197(
        tmp_path: Path, case: str) -> None:
    sql, control_refusal = _WINDOW_CASES[case]
    c = _lve_db(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match=WINDOW_MSG):
            c.execute(sql)
    finally:
        c.close()
    ctl = _lve_db(tmp_path / "control", drop=("trg_lve_view_window_immutable",))
    try:
        if control_refusal is None:
            ctl.execute(sql)  # the belt is the refusing object
        else:
            with pytest.raises(sqlite3.IntegrityError) as exc:
                ctl.execute(sql)
            assert control_refusal in str(exc.value)
            assert WINDOW_MSG not in str(exc.value)
    finally:
        ctl.close()


def test_lve_coherent_ticker_repoint_aborts_b22_198(tmp_path: Path) -> None:
    def repoint(c: sqlite3.Connection) -> None:
        seed_fire(c, run_id=200, pipeline_id=300, candidate_id=22222,
                  ticker="OII", action_session="2026-08-05")
        c.execute(
            "UPDATE latch_view_events SET candidate_id = 22222, "
            "evaluation_run_id = 200, ticker = 'OII', "
            "detection_date = '2026-08-05', pipeline_run_id = 300 "
            "WHERE view_event_id = 5")

    c = _lve_db(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match=WINDOW_MSG):
            repoint(c)
    finally:
        c.close()
    ctl = _lve_db(tmp_path / "control", drop=("trg_lve_view_window_immutable",))
    try:
        repoint(ctl)  # coherence alone does not protect the scope
        assert ctl.execute("SELECT ticker FROM latch_view_events").fetchone() == ("OII",)
    finally:
        ctl.close()


def test_lve_writer_last_view_update_passes_under_all_four_belts_b22_199(
        tmp_path: Path) -> None:
    c = _lve_db(tmp_path)
    try:
        for b in LVE_BELTS:
            assert _stored(c, b), b
        updated: set[str] = set()

        def auth(action, arg1, arg2, dbname, source):
            if action == sqlite3.SQLITE_UPDATE and arg1 == "latch_view_events":
                updated.add(arg2)
            return sqlite3.SQLITE_OK

        c.set_authorizer(auth)
        _record_view(c, viewed_ts="2026-08-03T10:00:00", actionable=0)
        c.set_authorizer(None)
        row = c.execute(
            "SELECT last_viewed_ts, view_count, first_viewed_ts, ticker "
            "FROM latch_view_events WHERE view_event_id = 5").fetchone()
    finally:
        c.close()
    assert row == ("2026-08-03T10:00:00", 5, LVE_ROW5["first_viewed_ts"], "AMN")
    assert updated == {"last_viewed_ts", "latch_state_at_last_view",
                       "actionable_at_last_view", "view_count",
                       "actionable_ever_viewed"}
    assert not updated & {"first_viewed_ts", "ticker"}
