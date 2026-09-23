"""22-A2 Task 3 -- migration 0039: the provenance_corrections REBUILD.

CHARC ruled F12 = (A) under SIX binding conditions (ledger R0.12); each maps to
roster rows here:
  (1) derived from the STORED v38 DDL by exactly three edits  -> A2-10, A2-11
  (2) one transaction, explicit column list, sequence equal,
      FK check empty, row 1 byte-identical                     -> A2-12..A2-15
  (3) statement order; four objects VERBATIM                   -> A2-16, A2-17
  (4) the D51 manifest diff: four line pairs, zero deletions   -> A2-18, A2-19
  (5) the reversibility header                                 -> A2-20
  (6) P34 re-points to HEAD definitions                        -> the re-pointed
      closure tests (test_22a_al3_closure, test_22a_authorize_then_abort_closure,
      test_22a_task2_migration_0037, test_22a_task3_epoch_reader) + A2-25
plus the P28 gate row (A2-21; A2-22 is in test_backup_gate_table.py) and the
tier-2 trigger arm (A2-23..A2-31).

ROW 1 IN THE MIGRATION FIXTURES (SS-1). Once this task lands the production
service writes the v39 column list and cannot write a v38 row, so row 1 is
derived from the real emitter ONE VERSION UP (``build_cadl_case`` +
``correct_cohort_provenance`` on v39), and its 40 v38 columns are planted by
RAW INSERT on the same world at v38 -- where the v38 citation trigger must
ADMIT it. Never planted with a trigger dropped.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

from swing.data import db as db_mod
from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    _current_version,
    ensure_schema,
    open_connection,
    run_migrations,
)
from swing.data.models import (
    PROVENANCE_ADMISSION_TIER_LATCH_TIER2,
    PROVENANCE_ADMISSION_TIERS,
    PROVENANCE_TIER2_EVIDENCE_FIELD,
)
from swing.trades.frozen_value_evidence import FROZEN_VALUE_EVIDENCE_VERSION
from swing.trades.latched_origin import (
    AUTHORIZATION_VERDICTS,
    LATCH_PROBE_EVIDENCE_VERSION,
    LATCH_PROBE_TIER2_EVIDENCE_VERSION,
)
from tests._tier2_world_22a2 import (
    insert_payload,
    truthful_tier2_payload,
)
from tests.data._migration_text import create_statement_in, head_create_statement

REPO_ROOT = Path(__file__).resolve().parents[2]
MIG_DIR = REPO_ROOT / "swing" / "data" / "migrations"
M0036 = MIG_DIR / "0036_provenance_corrections.sql"
M0037 = MIG_DIR / "0037_latch_order_mandate_links.sql"
M0039 = MIG_DIR / "0039_provenance_corrections_tier2.sql"
CITATION = "trg_provenance_corrections_citation_graph"
APPEND_UPDATE = "trg_provenance_corrections_append_only_update"
VERBATIM = {
    "ux_provenance_corrections_trade": M0036,
    "ix_provenance_corrections_cited_candidate": M0036,
    "trg_provenance_corrections_append_only_delete": M0036,
    "trg_pc_no_replace": M0037,
}

# Edit 1, MEASURED on 3.50.4 and pinned (encoding E-3): SQLite's RENAME rewrites
# the stored name token to the quoted form.
EDIT1 = ("CREATE TABLE provenance_corrections (",
         'CREATE TABLE "provenance_corrections" (')
EDIT2 = ("'latch_ladder')", "'latch_ladder', 'latch_ladder_tier2')")
EDIT3 = ("cited_latch_probe_json TEXT",
         "cited_latch_probe_json TEXT, cited_frozen_value_evidence_json TEXT")


def _load_manifest_module():
    path = REPO_ROOT / "scripts" / "schema_manifest.py"
    spec = importlib.util.spec_from_file_location("_a2_schema_manifest", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_a2_schema_manifest", mod)
    spec.loader.exec_module(mod)
    return mod


def _db(tmp_path: Path, name: str, version: int) -> sqlite3.Connection:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    c = open_connection(root / "swing.db")
    run_migrations(c, target_version=version, backup_dir=root / "bak")
    return c


def _stored(conn: sqlite3.Connection, name: str) -> str:
    return conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()[0]


def _v38_columns(conn: sqlite3.Connection) -> list[str]:
    return [r[1] for r in conn.execute("PRAGMA table_info(provenance_corrections)")]


def _row1_payload_from_the_real_emitter(tmp_path: Path) -> dict:
    """Row 1 (trade 23 / CADL, last_word) as the PRODUCTION service writes it."""
    from swing.trades.cohort_provenance_correction import correct_cohort_provenance
    from tests.trades._cohort_provenance_fixtures import build_cadl_case

    c = ensure_schema(tmp_path / "emit" / "swing.db")
    try:
        ids = build_cadl_case(c)
        if c.in_transaction:
            c.commit()
        correct_cohort_provenance(
            c, trade_id=ids["trade_id"], cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=ids["daily_recommendation_id"],
            reason="22-A2 row-1 fixture, real emitter one version up")
        cols = _v38_columns(c)
        values = c.execute("SELECT * FROM provenance_corrections").fetchone()
        return dict(zip(cols, values, strict=True))
    finally:
        c.close()


def _v38_with_row1(tmp_path: Path, name: str = "v38") -> sqlite3.Connection:
    """A v38 database carrying row 1's REAL payload, planted by raw INSERT on
    the same world -- the v38 citation trigger ADMITS it."""
    from tests.trades._cohort_provenance_fixtures import build_cadl_case

    emitted = _row1_payload_from_the_real_emitter(tmp_path)
    c = _db(tmp_path, name, 38)
    build_cadl_case(c)
    if c.in_transaction:
        c.commit()
    v38_cols = _v38_columns(c)
    assert len(v38_cols) == 40
    payload = {k: emitted[k] for k in v38_cols}
    insert_payload(c, payload)
    c.commit()
    assert c.execute("SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1
    return c


def _quote_tuple(conn: sqlite3.Connection, cols: list[str]) -> tuple:
    return conn.execute(
        "SELECT " + ", ".join(f"quote({c})" for c in cols)
        + " FROM provenance_corrections ORDER BY provenance_correction_id").fetchone()


def _seq(conn: sqlite3.Connection):
    row = conn.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = 'provenance_corrections'"
    ).fetchone()
    return None if row is None else row[0]


def _migrate_to_head(conn: sqlite3.Connection, tmp_path: Path) -> None:
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION,
                   backup_dir=tmp_path / "gate_bak")
    assert _current_version(conn) == EXPECTED_SCHEMA_VERSION == 39


def _strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


# ---------------------------------------------------------------------------
# Condition 1
# ---------------------------------------------------------------------------
def test_a2_10_three_edits_of_the_v38_stored_ddl_equal_the_v39_stored_ddl(
        tmp_path: Path) -> None:
    c = _db(tmp_path, "c1", 38)
    try:
        v38 = _stored(c, "provenance_corrections")
        expected = v38
        for old, new in (EDIT1, EDIT2, EDIT3):
            assert expected.count(old) == 1, old
            expected = expected.replace(old, new)
        _migrate_to_head(c, tmp_path)
        v39 = _stored(c, "provenance_corrections")
    finally:
        c.close()
    # BYTEWISE -- a lost CHECK, an extra edit or a moved column all differ.
    assert v39 == expected


def test_a2_11_edit_anchors_occur_once_and_the_seventh_column_is_last(
        tmp_path: Path) -> None:
    c = _db(tmp_path, "c1b", 38)
    try:
        v38 = _stored(c, "provenance_corrections")
        assert v38.count("'latch_ladder')") == 1
        assert v38.count("cited_latch_probe_json TEXT") == 1
        # the seventh column may NOT go before the final ")": the stored text
        # ENDS with a table-level CHECK, so that edit would put a column after
        # a table constraint (a syntax error).
        assert v38.rstrip().endswith("= 'active')\n)") or v38.rstrip().endswith(")")
        assert "CHECK" in v38[v38.rindex("cited_latch_probe_json TEXT"):]
        v38_cols = _v38_columns(c)
        _migrate_to_head(c, tmp_path)
        v39_cols = _v38_columns(c)
    finally:
        c.close()
    assert len(v38_cols) == 40 and v38_cols[-1] == "cited_latch_probe_json"
    assert v39_cols == v38_cols + [PROVENANCE_TIER2_EVIDENCE_FIELD]


# ---------------------------------------------------------------------------
# Condition 2
# ---------------------------------------------------------------------------
def test_a2_12_row_1_is_byte_identical_across_the_rebuild(tmp_path: Path) -> None:
    c = _v38_with_row1(tmp_path)
    try:
        cols = _v38_columns(c)
        before = _quote_tuple(c, cols)
        _migrate_to_head(c, tmp_path)
        after = _quote_tuple(c, cols)
        seventh = c.execute(
            f"SELECT {PROVENANCE_TIER2_EVIDENCE_FIELD} IS NULL, admission_tier "
            "FROM provenance_corrections").fetchone()
    finally:
        c.close()
    assert before == after
    assert seventh == (1, "last_word")


def test_a2_13_the_sequence_is_carried_not_recomputed(tmp_path: Path) -> None:
    """seq 7 over max id 1: a naive copy leaves the new table's counter at 1
    (the next insert would reuse ids 2..7); the carried counter stays 7."""
    c = _v38_with_row1(tmp_path)
    try:
        c.execute("UPDATE sqlite_sequence SET seq = 7 "
                  "WHERE name = 'provenance_corrections'")
        c.commit()
        assert _seq(c) == 7
        assert c.execute("SELECT MAX(provenance_correction_id) "
                         "FROM provenance_corrections").fetchone()[0] == 1
        _migrate_to_head(c, tmp_path)
        assert _seq(c) == 7
        assert c.execute("SELECT COUNT(*) FROM sqlite_sequence WHERE name LIKE "
                         "'provenance_corrections%'").fetchone()[0] == 1
    finally:
        c.close()


def test_a2_14_live_shape_and_zero_row_sequences(tmp_path: Path) -> None:
    c = _v38_with_row1(tmp_path, "live")
    try:
        assert _seq(c) == 1
        _migrate_to_head(c, tmp_path / "l")
        assert _seq(c) == 1
    finally:
        c.close()
    z = _db(tmp_path, "zero", 38)
    try:
        assert _seq(z) is None
        _migrate_to_head(z, tmp_path / "z")
        assert _seq(z) is None
        assert z.execute("SELECT COUNT(*) FROM sqlite_sequence WHERE name = "
                         "'provenance_corrections__0039'").fetchone()[0] == 0
    finally:
        z.close()


def test_a2_15_foreign_key_check_is_empty_after_the_rebuild(tmp_path: Path) -> None:
    c = _v38_with_row1(tmp_path)
    try:
        _migrate_to_head(c, tmp_path)
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        c.close()


# ---------------------------------------------------------------------------
# Condition 3
# ---------------------------------------------------------------------------
def test_a2_16_statement_order(tmp_path: Path) -> None:
    code = _strip_comments(M0039.read_text(encoding="utf-8"))

    def pos(pattern: str) -> int:
        hits = [m.start() for m in re.finditer(pattern, code)]
        assert len(hits) == 1, (pattern, len(hits))
        return hits[0]

    create_new = pos(r"CREATE TABLE provenance_corrections__0039 \(")
    copy_rows = pos(r"INSERT INTO provenance_corrections__0039 \(")
    seq_carry = pos(r"INSERT INTO sqlite_sequence")
    drop_old = pos(r"DROP TABLE provenance_corrections;")
    rename = pos(r"ALTER TABLE provenance_corrections__0039 RENAME TO "
                 r"provenance_corrections;")
    creates = [m.start() for m in re.finditer(
        r"CREATE (?:UNIQUE )?(?:INDEX|TRIGGER)", code)]
    assert len(creates) == 6
    assert create_new < copy_rows < seq_carry < drop_old < rename < min(creates)
    assert max(creates) < pos(r"UPDATE schema_version SET version = 39;")


def test_a2_17_the_four_unchanged_objects_are_verbatim(tmp_path: Path) -> None:
    c = _db(tmp_path, "c3", EXPECTED_SCHEMA_VERSION)
    try:
        for name, source in VERBATIM.items():
            assert _stored(c, name) == create_statement_in(source, name), name
            # and the HEAD definition of each is the 0039 re-create
            assert head_create_statement(name)[0] == M0039, name
    finally:
        c.close()


# ---------------------------------------------------------------------------
# Condition 4 (D51)
# ---------------------------------------------------------------------------
def test_a2_18_the_manifest_diff_is_three_changed_objects_and_nothing_else(
        tmp_path: Path) -> None:
    sm = _load_manifest_module()
    c = _db(tmp_path, "c4", 38)
    try:
        v38 = sm.read_manifest(c)
        _migrate_to_head(c, tmp_path)
        v39 = sm.read_manifest(c)
    finally:
        c.close()
    diff = sm.compare(v38, v39)
    assert diff.missing == frozenset()
    assert diff.unexpected == frozenset()
    assert diff.changed == frozenset({
        ("table", "provenance_corrections"),
        ("trigger", APPEND_UPDATE),
        ("trigger", CITATION),
    })


def test_a2_19_the_committed_fixture_is_the_v39_head(tmp_path: Path) -> None:
    sm = _load_manifest_module()
    fixture = REPO_ROOT / "tests" / "data" / "schema_manifest_head.tsv"
    text = fixture.read_text(encoding="utf-8")
    assert "# schema_version 39\n" in text
    c = ensure_schema(tmp_path / "c5.db")
    try:
        head = sm.read_manifest(c)
    finally:
        c.close()
    assert sm.compare(sm.load_manifest(fixture), head).is_clean


# ---------------------------------------------------------------------------
# Condition 5 + P28
# ---------------------------------------------------------------------------
def test_a2_20_the_reversibility_header_names_the_edits_and_the_gate() -> None:
    text = M0039.read_text(encoding="utf-8")
    header = text[: text.index("\nBEGIN;")]
    assert "REVERSIBILITY HEADER" in header
    for needle in (
        'CREATE TABLE "provenance_corrections" (',
        "('last_word', 'latch_ladder', 'latch_ladder_tier2')",
        ", cited_frozen_value_evidence_json TEXT",
        'BackupGateSpec(38, "22a2", PHASE22_ARC_A2_PRE_MIGRATION_EXPECTED_TABLES,',
        '"_phase22_arc_a2_backup_gate", "pre-22-A2")',
        "LEGAL ONLY WHILE NO",
    ):
        assert needle in header, needle
    for obj in ("ux_provenance_corrections_trade",
                "ix_provenance_corrections_cited_candidate",
                "trg_provenance_corrections_append_only_delete",
                "trg_pc_no_replace", APPEND_UPDATE, CITATION):
        assert obj in header, obj


def test_a2_21_the_22a2_gate_fires_and_the_cli_echoes_its_image(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from click.testing import CliRunner

    from swing.cli import main
    from tests.cli.test_db_migrate_single_backup import _build, _config

    spec = db_mod.backup_gate_for_pre_version(38)
    assert spec is not None
    assert (spec.filename_stem, spec.gate_name, spec.label) == (
        "22a2", "_phase22_arc_a2_backup_gate", "pre-22-A2")
    assert spec.expected_tables is db_mod.PHASE22_ARC_A2_PRE_MIGRATION_EXPECTED_TABLES

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    cfg = _config(project, home)
    sd = home / "swing-data"
    _build(sd / "swing.db", 38)
    r = CliRunner().invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    images = sorted((sd / "backups").glob("swing-pre-22a2-migration-*.db"))
    assert len(images) == 1, images
    assert f"Backup (pre-migration gate, integrity-verified): {images[0]}" in r.output
    assert re.fullmatch(r"swing-pre-22a2-migration-\d{8}T\d{6}Z\.db", images[0].name)


# ---------------------------------------------------------------------------
# The tier enum and the verdict vocabulary (#11: the drift tests)
# ---------------------------------------------------------------------------
def test_a2_23_sql_admission_tier_check_equals_the_python_enum(tmp_path: Path) -> None:
    c = ensure_schema(tmp_path / "d.db")
    try:
        sql = _stored(c, "provenance_corrections")
    finally:
        c.close()
    found = re.findall(r"admission_tier IN \(([^)]*)\)", sql)
    assert len(found) == 1
    assert set(re.findall(r"'([^']+)'", found[0])) == PROVENANCE_ADMISSION_TIERS
    assert len(PROVENANCE_ADMISSION_TIERS) == 3


def test_a2_24_the_model_carries_the_three_way_paired_rule(tmp_path: Path) -> None:
    from dataclasses import replace

    from swing.data.repos.provenance_corrections import get_correction_for_trade
    from swing.trades.cohort_provenance_correction import correct_cohort_provenance
    from tests.trades._cohort_provenance_fixtures import build_cadl_case

    c = ensure_schema(tmp_path / "m.db")
    try:
        ids = build_cadl_case(c)
        if c.in_transaction:
            c.commit()
        correct_cohort_provenance(
            c, trade_id=ids["trade_id"], cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=ids["daily_recommendation_id"], reason="m")
        row = get_correction_for_trade(c, ids["trade_id"])
    finally:
        c.close()
    five = dict(cited_latch_link_id=1, cited_latch_validity_intent_id=2,
                cited_latch_place_intent_id=3, cited_latch_broker_order_id="X",
                cited_latch_probe_json="{}")
    # latch_ladder_tier2 with all six -> accepted
    replace(row, admission_tier=PROVENANCE_ADMISSION_TIER_LATCH_TIER2, **five,
            cited_frozen_value_evidence_json="{}")
    # ... the seventh missing -> "is missing"
    with pytest.raises(ValueError, match="is missing"):
        replace(row, admission_tier=PROVENANCE_ADMISSION_TIER_LATCH_TIER2, **five)
    # latch_ladder carrying the seventh -> rejected
    with pytest.raises(ValueError, match="may not disagree"):
        replace(row, admission_tier="latch_ladder", **five,
                cited_frozen_value_evidence_json="{}")
    # last_word carrying the seventh -> rejected
    with pytest.raises(ValueError, match="may not disagree"):
        replace(row, cited_frozen_value_evidence_json="{}")
    # an unknown tier -> rejected by the enum
    with pytest.raises(ValueError, match="is not one of"):
        replace(row, admission_tier="latch_ladder_tier3")
    # and the repo round-trips the seventh column (read + write in one tuple)
    from swing.data.repos import provenance_corrections as repo
    assert repo._COLUMNS[-1] == PROVENANCE_TIER2_EVIDENCE_FIELD


def test_a2_25_trigger_literals_equal_their_python_mirrors() -> None:
    """Tier literals, rung-9 verdict literals, probe-version literals and the
    seventh blob's version literal, parsed from the HEAD citation trigger."""
    path, stmt = head_create_statement(CITATION)
    assert path == M0039
    code = _strip_comments(stmt)
    tiers = set(re.findall(r"'(last_word|latch_ladder\w*)'", code))
    assert tiers == PROVENANCE_ADMISSION_TIERS, tiers
    verdicts = set(re.findall(
        r"'\$\.authorization\.rung9_stored_freeze_tier\.verdict'\)\s*=\s*'([^']+)'",
        code))
    assert verdicts == set(AUTHORIZATION_VERDICTS), verdicts
    tail = code.split(
        "json_extract(NEW.cited_latch_probe_json, '$.evidence_version')", 1)[1]
    case = tail.split(" END", 1)[0]
    assert set(re.findall(r"THEN '([^']+)'", case)) == {
        LATCH_PROBE_EVIDENCE_VERSION, LATCH_PROBE_TIER2_EVIDENCE_VERSION}
    seventh = set(re.findall(
        r"json_extract\(NEW\.cited_frozen_value_evidence_json, "
        r"'\$\.evidence_version'\) = '([^']+)'", code))
    assert seventh == {FROZEN_VALUE_EVIDENCE_VERSION}
    # the one literal is not hard-coded as a single member elsewhere
    assert "'escaped_by_tier2'" in code and "'pass'" in code


# ---------------------------------------------------------------------------
# The tier-2 arm, at the raw-INSERT trust boundary
# ---------------------------------------------------------------------------
def _refused(conn: sqlite3.Connection, payload: dict) -> bool:
    try:
        insert_payload(conn, payload)
    except sqlite3.IntegrityError as exc:
        assert "citation graph" in str(exc) or "provenance_corrections" in str(exc)
        conn.rollback()
        return True
    conn.rollback()
    return False


def test_a2_26_a_truthful_tier2_row_inserts(tmp_path: Path) -> None:
    conn, payload, _ids = truthful_tier2_payload(tmp_path)
    try:
        insert_payload(conn, payload)
        conn.commit()
        row = conn.execute(
            "SELECT admission_tier, cited_candidate_id, "
            f"{PROVENANCE_TIER2_EVIDENCE_FIELD} IS NOT NULL "
            "FROM provenance_corrections").fetchone()
    finally:
        conn.close()
    assert row == ("latch_ladder_tier2", 12284, 1)


def test_a2_27_a_blob_omitting_interval_is_refused_not_failed_open(
        tmp_path: Path) -> None:
    """The NULL-WHEN probe: every predicate on a missing key is NULL; only the
    enclosing COALESCE turns that into a refusal."""
    conn, payload, _ids = truthful_tier2_payload(tmp_path)
    try:
        blob = json.loads(payload[PROVENANCE_TIER2_EVIDENCE_FIELD])
        del blob["interval"]
        assert _refused(conn, {**payload,
                               PROVENANCE_TIER2_EVIDENCE_FIELD: json.dumps(blob)})
    finally:
        conn.close()


def _mut_probe_rung9(field: str, value):
    def apply(payload: dict) -> dict:
        probe = json.loads(payload["cited_latch_probe_json"])
        probe["authorization"]["rung9_stored_freeze_tier"][field] = value
        return {**payload, "cited_latch_probe_json": json.dumps(probe)}
    return apply


def _mut_seventh(fn):
    def apply(payload: dict) -> dict:
        blob = json.loads(payload[PROVENANCE_TIER2_EVIDENCE_FIELD])
        fn(blob)
        return {**payload, PROVENANCE_TIER2_EVIDENCE_FIELD: json.dumps(blob)}
    return apply


def _set(*path_and_value):
    *path, value = path_and_value

    def fn(blob: dict) -> None:
        target = blob
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return fn


def _reorder_segments(blob: dict) -> None:
    segs = blob["interval"]["segments"]
    segs[1], segs[2] = segs[2], segs[1]


A2_28_MUTATIONS = {
    "rung9_verdict_pass": _mut_probe_rung9("verdict", "pass"),
    "rung9_input_live": _mut_probe_rung9("input", "live_at_acceptance"),
    "seventh_null": lambda p: {**p, PROVENANCE_TIER2_EVIDENCE_FIELD: None},
    "seventh_malformed": lambda p: {**p, PROVENANCE_TIER2_EVIDENCE_FIELD: "{bad"},
    "extra_key": _mut_seventh(_set("extra", "x")),
    "evidence_version": _mut_seventh(_set("evidence_version", "2026-09-23.2")),
    "sha_39": _mut_seventh(_set("artifact_commit_sha",
                                "9f315cc64a8f171049b510021e6418bc261c50b")),
    "quoted_text_newline": _mut_seventh(
        lambda b: b.__setitem__("quoted_text", b["quoted_text"] + "\nmore")),
    "ticker_OIS": _mut_seventh(_set("quoted_ticker_text", "OIS")),
    # AMN IS in line 57 (a passing mention), so containment passes and only
    # the binding to the cited candidate's ticker refuses it.
    "ticker_AMN_in_text": _mut_seventh(_set("quoted_ticker_text", "AMN")),
    "pivot_text_absent": _mut_seventh(_set("quoted_pivot_text", "53.97")),
    "live_pivot_rounded": _mut_seventh(_set("live_pivot_raw", 53.98)),
    "pivot_verdict_0": _mut_seventh(_set("pivot_equal_at_dp", 0)),
    "compare_dp_3": _mut_seventh(_set("compare_dp", 3)),
    "fill_session_date": _mut_seventh(_set("fill_session_date", "2026-08-18")),
    "author_date_on_fill": _mut_seventh(_set("author_date_et", "2026-08-17")),
    "fire_lo_raw": _mut_seventh(_set("interval", "endpoints", "fire_lo", "raw",
                                     "2026-08-07T17:30:03")),
    "read_at_raw": _mut_seventh(_set("interval", "endpoints", "read_at", "raw",
                                     "2026-09-23T12:00:00.001")),
    "barrier_armed_at_raw": _mut_seventh(_set(
        "interval", "endpoints", "barrier_armed_at", "raw", "2026-09-02T10:03:33Z")),
    "segments_reordered": _mut_seventh(_reorder_segments),
    "action_session_08_11": _mut_seventh(_set("quoted_action_session_text", "08-11")),
}


@pytest.mark.parametrize("label", list(A2_28_MUTATIONS))
def test_a2_28_each_single_mutation_of_the_truthful_row_is_refused(
        tmp_path: Path, label: str) -> None:
    conn, payload, _ids = truthful_tier2_payload(tmp_path)
    try:
        mutated = A2_28_MUTATIONS[label](copy.deepcopy(payload))
        assert mutated != payload
        if label == "barrier_armed_at_raw":
            # the world's epoch is stamped at migration time; the mutation is
            # the LIVE value, which this world's epoch is not.
            epoch = conn.execute(
                "SELECT applied_at FROM candidates_immutability_epoch").fetchone()[0]
            assert epoch != "2026-09-02T10:03:33Z"
        assert _refused(conn, mutated), label
        # the control: the unmutated row still inserts on the same world
        insert_payload(conn, payload)
        conn.rollback()
    finally:
        conn.close()


def test_a2_29_the_tier2_span_never_rounds_or_casts() -> None:
    stmt = head_create_statement(CITATION)[1]
    lines = stmt.split("\n")
    marks = [i for i, ln in enumerate(lines) if "-- TIER2-PREDICATE" in ln]
    assert len(marks) >= 20
    span = "\n".join(lines[marks[0]:marks[-1] + 1])
    code = re.sub(r"\s+", "", _strip_comments(span)).lower()
    for token in ("round(", "printf(", "format(", "cast("):
        assert token not in code, token
    # the whole HEAD trigger never ROUNDS (S4.3a), comment-stripped
    whole = re.sub(r"\s+", "", _strip_comments(stmt)).lower()
    assert "round(" not in whole


def test_a2_30_the_latch_ladder_branch_refuses_an_escaped_or_tier2_versioned_blob(
        tmp_path: Path) -> None:
    """F11's inverse clause, per clause, on a TRUTHFUL latch_ladder row."""
    from tests.data.test_22a_task2_migration_0037 import seed_latch_ladder_citation

    c = ensure_schema(tmp_path / "ll.db")
    try:
        payload = seed_latch_ladder_citation(c)
        assert payload[PROVENANCE_TIER2_EVIDENCE_FIELD] is None
        probe = json.loads(payload["cited_latch_probe_json"])
        # (a) rung 9 says escaped_by_tier2, version unchanged -> refused
        esc = copy.deepcopy(probe)
        esc["authorization"]["rung9_stored_freeze_tier"]["verdict"] = "escaped_by_tier2"
        assert _refused(c, {**payload, "cited_latch_probe_json": json.dumps(esc)})
        # (b) the tier-2 blob version with rung 9 pass -> refused
        ver = copy.deepcopy(probe)
        ver["evidence_version"] = LATCH_PROBE_TIER2_EVIDENCE_VERSION
        assert _refused(c, {**payload, "cited_latch_probe_json": json.dumps(ver)})
        # (c) a seventh column on a latch_ladder row -> refused
        assert _refused(c, {**payload, PROVENANCE_TIER2_EVIDENCE_FIELD: "{}"})
        # the control: the truthful latch_ladder row inserts
        insert_payload(c, payload)
        c.commit()
    finally:
        c.close()


def test_an_escape_cannot_be_laundered_into_a_tier1_row(
        tmp_path: Path) -> None:
    conn, payload, _ids = truthful_tier2_payload(tmp_path)
    try:
        laundered = {**payload, "admission_tier": "latch_ladder",
                     PROVENANCE_TIER2_EVIDENCE_FIELD: None}
        assert _refused(conn, laundered)
    finally:
        conn.close()


def test_a2_31_the_tier2_row_is_append_only(tmp_path: Path) -> None:
    conn, payload, _ids = truthful_tier2_payload(tmp_path)
    try:
        insert_payload(conn, payload)
        conn.commit()
        rid = conn.execute(
            "SELECT provenance_correction_id FROM provenance_corrections").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
            conn.execute(
                f"UPDATE provenance_corrections SET "
                f"{PROVENANCE_TIER2_EVIDENCE_FIELD} = '{{}}' "
                "WHERE provenance_correction_id = ?", (rid,))
        conn.rollback()
        replay = {**payload, "provenance_correction_id": rid}
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT OR REPLACE INTO provenance_corrections "
                f"({', '.join(replay)}) VALUES ({', '.join('?' * len(replay))})",
                tuple(replay.values()))
        conn.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
            conn.execute("DELETE FROM provenance_corrections")
        conn.rollback()
        cols = _v38_columns(conn)
        assert len(cols) == 41
        head_update = head_create_statement(APPEND_UPDATE)[1]
        missing = [col for col in cols if f"NEW.{col} " not in head_update
                   and f"NEW.{col}\n" not in head_update]
        assert missing == [], missing
    finally:
        conn.close()



def test_the_head_citation_trigger_keeps_every_fei_consumer_marked() -> None:
    """P34 class (ii) + a HEAD pin. ``test_22a_canonicalizer_version_closure``
    asserts its marker/reference closure over 0037's OWN text (the FEI table,
    its anchor and its ships-empty property live there and nowhere else), so
    the citation trigger 0039 re-creates needs its own HEAD-level pin: every
    FROM/JOIN reference to ``fill_envelope_identity`` in the HEAD definition
    carries a ``FEI-CONSUMER`` marker, and the tier-2 arm added NO consumer --
    the marker set equals 0037's citation trigger's exactly."""
    marker = re.compile(r"--\s*FEI-CONSUMER\s+(\w+)\s*::\s*(\w+)")
    reference = re.compile(r"\b(?:FROM|JOIN)\s+fill_envelope_identity\b")
    head = head_create_statement(CITATION)[1]
    old = create_statement_in(M0037, CITATION)
    head_marks = marker.findall(head)
    assert sorted(head_marks) == sorted(marker.findall(old))
    blanked = "\n".join("" if ln.lstrip().startswith("--") else ln
                        for ln in head.split("\n"))
    assert len(reference.findall(blanked)) == len(head_marks)


# ---------------------------------------------------------------------------
# G-NEG (CHARC, 2026-09-23): match_only OPTIONAL, record_position inside the
# interval, and ONE length-consistency belt SQL can assert without a utc read.
# RD's F2.I-NEG cases on the trade-25 world with only the barrier moved.
# ---------------------------------------------------------------------------
_BELT = "-- TIER2-PREDICATE record_position_consistent"


def _drop_the_belt(conn: sqlite3.Connection) -> None:
    """Re-create the HEAD citation trigger with ONLY the belt clause cut, to
    prove the belt is what refuses (a test-world instrument; no production
    row is ever planted this way)."""
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'trigger' "
                       "AND name = ?", (CITATION,)).fetchone()[0]
    lines = sql.split("\n")
    start = next(i for i, ln in enumerate(lines) if _BELT in ln)
    end = next(i for i in range(start, len(lines))
               if lines[i].rstrip().endswith("ELSE 0 END"))
    cut = "\n".join(lines[:start] + lines[end + 1:])
    assert "record_position_consistent" not in cut
    assert "'$.interval.record_position'" in cut      # interval_closed still binds it
    assert len(cut.split("\n")) == len(lines) - (end - start + 1)
    conn.execute(f"DROP TRIGGER {CITATION}")
    conn.execute(cut)
    conn.commit()


@pytest.mark.parametrize(("barrier_z", "truthful", "forged"), [
    # record = barrier + 1 s: [fire, writer_absence_only, covered]
    ("2026-08-10T12:41:32Z", "inside_coverage", "before_barrier"),
    # record = barrier - 1 s: [fire, writer_absence_only, match_only 1 s, covered]
    ("2026-08-10T12:41:34Z", "before_barrier", "inside_coverage"),
])
def test_g_neg_the_record_position_belt_refuses_a_forged_position(
        tmp_path: Path, barrier_z: str, truthful: str, forged: str) -> None:
    from datetime import datetime

    from swing.trades import frozen_value_evidence as fve
    from tests._tier2_world_22a2 import (
        T25_AUTHOR_INSTANT,
        T25_PIPELINE_FINISHED,
        T25_RUN_TS,
    )

    segments = fve.build_interval(
        fire_lo_raw=T25_RUN_TS, fire_hi_raw=T25_PIPELINE_FINISHED,
        author_instant=datetime.fromisoformat(T25_AUTHOR_INSTANT),
        barrier_armed_raw=barrier_z, read_at="2026-09-23T12:00:00.000",
        barrier_installed=True)["segments"]
    assert len(segments) == (3 if truthful == "inside_coverage" else 4)
    conn, payload, _ids = truthful_tier2_payload(tmp_path)

    def shaped(position: str) -> dict:
        blob = json.loads(payload[PROVENANCE_TIER2_EVIDENCE_FIELD])
        blob["interval"]["segments"] = segments
        blob["interval"]["record_position"] = position
        return {**payload, PROVENANCE_TIER2_EVIDENCE_FIELD: json.dumps(blob)}

    try:
        # The control: the truthful position on this segment shape ADMITS
        # (the amended interval_segment_order accepts length 3 AND 4).
        assert not _refused(conn, shaped(truthful))
        # The forged position ABORTS.
        assert _refused(conn, shaped(forged))
        # ... and it is the belt that aborts it: with the belt cut, ACCEPTED.
        _drop_the_belt(conn)
        assert not _refused(conn, shaped(forged))
    finally:
        conn.close()


def test_g_neg_interval_admits_exactly_one_more_typed_key(tmp_path: Path) -> None:
    """interval_closed widens by exactly record_position IN the pair."""
    conn, payload, _ids = truthful_tier2_payload(tmp_path)

    def with_interval(fn) -> dict:
        blob = json.loads(payload[PROVENANCE_TIER2_EVIDENCE_FIELD])
        fn(blob["interval"])
        return {**payload, PROVENANCE_TIER2_EVIDENCE_FIELD: json.dumps(blob)}

    try:
        assert not _refused(conn, payload)
        assert _refused(conn, with_interval(lambda iv: iv.pop("record_position")))
        assert _refused(conn, with_interval(
            lambda iv: iv.__setitem__("record_position", "after_barrier")))
        assert _refused(conn, with_interval(
            lambda iv: iv.__setitem__("record_position", 1)))
        assert _refused(conn, with_interval(lambda iv: iv.__setitem__("extra", "x")))
        # length 2 and 5 refuse; a length-3 list whose [2] is match_only refuses
        assert _refused(conn, with_interval(
            lambda iv: iv.__setitem__("segments", iv["segments"][:2])))
        assert _refused(conn, with_interval(
            lambda iv: iv.__setitem__("segments", iv["segments"] + iv["segments"][-1:])))
        assert _refused(conn, with_interval(lambda iv: (
            iv.__setitem__("segments", iv["segments"][:3]),
            iv.__setitem__("record_position", "inside_coverage"))))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# G-T7F + G-T7F-AMEND (CHARC, 2026-09-23): the grammar/derivation split.  The
# blob carries ``derivation_version``; SQL asserts it is TEXT and nothing about
# its value (a derivation change is invisible to SQL by construction).  Each
# clause is proved to be the one refusing by re-creating the HEAD trigger
# with ONLY that clause cut (a test-world instrument, as the G-NEG belt).
# ---------------------------------------------------------------------------
_DV_TYPE_CLAUSE = ("             AND json_type(NEW.cited_frozen_value_evidence_json, "
                   "'$.derivation_version') = 'text'\n")
_DV_CLOSED_ENTRY = "'$.evidence_version', '$.derivation_version',"


def _recreate_citation_with(conn: sqlite3.Connection, old: str, new: str) -> None:
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'trigger' "
                       "AND name = ?", (CITATION,)).fetchone()[0]
    assert sql.count(old) == 1, old
    conn.execute(f"DROP TRIGGER {CITATION}")
    conn.execute(sql.replace(old, new))
    conn.commit()


def _with_seventh(payload: dict, fn) -> dict:
    blob = json.loads(payload[PROVENANCE_TIER2_EVIDENCE_FIELD])
    fn(blob)
    return {**payload, PROVENANCE_TIER2_EVIDENCE_FIELD: json.dumps(blob)}


def test_g_t7f_the_truthful_row_carries_the_derivation_version(tmp_path: Path) -> None:
    """The literal blob carries the key; blob_closed's +1 entry is what admits
    it (cut the entry -> the SAME truthful row is refused as an extra key)."""
    from swing.trades.frozen_value_evidence import FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION

    conn, payload, _ids = truthful_tier2_payload(tmp_path)
    try:
        blob = json.loads(payload[PROVENANCE_TIER2_EVIDENCE_FIELD])
        assert blob["derivation_version"] == FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION
        assert not _refused(conn, payload)
        _recreate_citation_with(conn, _DV_CLOSED_ENTRY, "'$.evidence_version',")
        assert _refused(conn, payload)
    finally:
        conn.close()


@pytest.mark.parametrize(("label", "mutate"), [
    ("absent", lambda b: b.pop("derivation_version")),
    ("integer", lambda b: b.__setitem__("derivation_version", 1)),
    ("null", lambda b: b.__setitem__("derivation_version", None)),
    ("object", lambda b: b.__setitem__("derivation_version", {"v": "x"})),
])
def test_g_t7f_an_absent_or_non_text_derivation_version_aborts(
        tmp_path: Path, label: str, mutate) -> None:
    """ABORT on the raw INSERT; ACCEPTED with the ``derivation_version`` type
    clause cut.  NOTE the attribution: blob_closed (``json_remove(...) = '{}'``)
    refuses an EXTRA key and passes an ABSENT one, so absence aborts on the
    type clause -- whose ``json_type`` of a missing path is NULL, collapsed to a
    refusal by the enclosing COALESCE (the NULL-WHEN gotcha)."""
    conn, payload, _ids = truthful_tier2_payload(tmp_path)
    try:
        bad = _with_seventh(payload, mutate)
        assert _refused(conn, bad), label
        assert not _refused(conn, payload)
        _recreate_citation_with(conn, _DV_TYPE_CLAUSE, "")
        assert not _refused(conn, bad), label
    finally:
        conn.close()


def test_g_t7f_sql_asserts_the_derivation_version_type_and_never_its_value() -> None:
    code = _strip_comments(head_create_statement(CITATION)[1])
    assert code.count("'$.derivation_version'") == 2
    assert _DV_CLOSED_ENTRY in code
    assert _DV_TYPE_CLAUSE.strip() in code
    assert "json_extract(NEW.cited_frozen_value_evidence_json, '$.derivation_version')" \
        not in code


def test_g_t7f_blob_closed_path_list_equals_the_python_roster() -> None:
    """The #11 comparator for the seventh blob's CLOSED roster: the trigger's
    ``json_remove`` path list IS the Python ``FROZEN_VALUE_BLOB_KEYS``."""
    from swing.trades.frozen_value_evidence import FROZEN_VALUE_BLOB_KEYS

    code = _strip_comments(head_create_statement(CITATION)[1])
    block = re.search(
        r"json_remove\(NEW\.cited_frozen_value_evidence_json,(.*?)\)\s*=\s*'\{\}'",
        code, re.S)
    assert block, "could not locate the blob_closed path list"
    paths = re.findall(r"'\$\.([a-z_]+)'", block.group(1))
    assert paths == list(FROZEN_VALUE_BLOB_KEYS)
    assert len(paths) == 29 and "derivation_version" in paths


def test_g_t7f_amend_the_header_declares_the_grammar_bump_obligation() -> None:
    text = M0039.read_text(encoding="utf-8")
    header = text[: text.index("\nBEGIN;")]
    for needle in ("GRAMMAR-BUMP OBLIGATION", "FROZEN_VALUE_EVIDENCE_VERSION",
                   "PRE-EXISTING", "per-version recompute adapter",
                   "declared exclusion", "FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION"):
        assert needle in header, needle


# ---------------------------------------------------------------------------
# G-T12 P34-1 + S-1 (CHARC, 2026-09-23): the interval vocabulary's SQL-vs-
# Python comparator, and the behavioural leg for uncovered_barrier_absent.
# ---------------------------------------------------------------------------
def test_the_interval_vocabulary_sql_and_python_agree() -> None:
    """S-1 -- THE COMPARATOR IS MANDATORY (CLAUDE.md #11, the 22-A amendment:
    the drift test is the one mirror that defends the set).

    The interval vocabulary crosses SQL (0039's ``interval_closed`` ..
    ``record_position_consistent`` predicates) and Python
    (``frozen_value_evidence.py:134-152``'s ``INTERVAL_ENDPOINTS``,
    ``_ENDPOINT_DOMAIN_SOURCE``, ``SEGMENT_KINDS``, ``SEGMENT_COVERED``,
    ``SEGMENT_UNCOVERED_BARRIER_ABSENT``, ``RECORD_POSITIONS``) with NO
    comparator before this test.  Four legs, each direction covered by
    set/tuple equality (a member only in SQL or only in Python both fail the
    same assertion, naming the disagreeing side).
    """
    from swing.trades.frozen_value_evidence import (
        INTERVAL_ENDPOINTS,
        RECORD_POSITIONS,
        SEGMENT_COVERED,
        SEGMENT_KINDS,
        SEGMENT_UNCOVERED_BARRIER_ABSENT,
        _ENDPOINT_DOMAIN_SOURCE,
    )

    code = head_create_statement(CITATION)[1]

    # Leg 1 -- record_position's IN-list.
    m = re.search(r"'\$\.interval\.record_position'\)\s*IN\s*\(([^)]*)\)", code)
    assert m, "could not locate the interval.record_position IN-list"
    found1 = set(re.findall(r"'([^']+)'", m.group(1)))
    assert found1 == set(RECORD_POSITIONS), (
        f"record_position IN-list vs RECORD_POSITIONS disagree: "
        f"only in SQL {sorted(found1 - set(RECORD_POSITIONS))}, "
        f"only in Python {sorted(set(RECORD_POSITIONS) - found1)}"
    )

    # Leg 2 -- the terminal IN-list, BOTH occurrences (the length-4 branch's
    # segments[3] and the length-3 branch's segments[2]), and the ORDERED
    # non-terminal kinds at segments[0..2] (segments[2] read from the
    # length-4 branch's literal EQUALITY -- 'match_only' -- never the
    # length-3 branch's terminal IN-list, which the regex below cannot match
    # since it requires '=' immediately, not 'IN').
    terminal_groups = re.findall(
        r"segments\[\d+\]\.kind'\)\s*IN\s*\(([^)]*)\)", code)
    assert len(terminal_groups) == 2, (
        f"expected 2 terminal segment.kind IN-lists, found "
        f"{len(terminal_groups)}: the parser found nothing it expected"
    )
    terminal_set = {SEGMENT_COVERED, SEGMENT_UNCOVERED_BARRIER_ABSENT}
    for group in terminal_groups:
        found2 = set(re.findall(r"'([^']+)'", group))
        assert found2 == terminal_set, (
            f"terminal segment.kind IN-list vs "
            f"{{SEGMENT_COVERED, SEGMENT_UNCOVERED_BARRIER_ABSENT}} disagree: "
            f"only in SQL {sorted(found2 - terminal_set)}, "
            f"only in Python {sorted(terminal_set - found2)}"
        )

    def _kind_eq(index: int) -> str:
        eq = re.search(rf"segments\[{index}\]\.kind'\)\s*=\s*'([^']+)'", code)
        assert eq, f"could not locate a literal segments[{index}].kind equality"
        return eq.group(1)

    ordered = (_kind_eq(0), _kind_eq(1), _kind_eq(2))
    assert ordered == SEGMENT_KINDS, (
        f"ordered segments[0..2].kind {ordered} != SEGMENT_KINDS {SEGMENT_KINDS}"
    )

    # Leg 3 -- the endpoints json_remove closure list.
    marker = ("json_remove(json_extract(NEW.cited_frozen_value_evidence_json, "
              "'$.interval.endpoints'),")
    assert marker in code, "could not locate the interval.endpoints closure marker"
    closure = code.split(marker, 1)[1].split("= '{}'", 1)[0]
    found3 = set(re.findall(r"'\$\.(\w+)'", closure))
    assert found3 == set(INTERVAL_ENDPOINTS), (
        f"interval.endpoints closure list vs INTERVAL_ENDPOINTS disagree: "
        f"only in SQL {sorted(found3 - set(INTERVAL_ENDPOINTS))}, "
        f"only in Python {sorted(set(INTERVAL_ENDPOINTS) - found3)}"
    )

    # Leg 4 -- per-endpoint clock_domain + source literals.
    for name in INTERVAL_ENDPOINTS:
        domain_m = re.search(
            rf"'\$\.interval\.endpoints\.{name}\.clock_domain'\)\s*=\s*'([^']+)'",
            code)
        source_m = re.search(
            rf"'\$\.interval\.endpoints\.{name}\.source'\)\s*=\s*'([^']+)'",
            code)
        assert domain_m, f"could not locate {name}.clock_domain literal"
        assert source_m, f"could not locate {name}.source literal"
        found4 = (domain_m.group(1), source_m.group(1))
        assert found4 == _ENDPOINT_DOMAIN_SOURCE[name], (
            f"{name}: SQL (clock_domain, source) {found4} != Python "
            f"_ENDPOINT_DOMAIN_SOURCE {_ENDPOINT_DOMAIN_SOURCE[name]}"
        )


@pytest.mark.parametrize(("barrier_z", "record_position", "length"), [
    # record = barrier + 1 s: [fire, writer_absence_only, uncovered_barrier_absent]
    ("2026-08-10T12:41:32Z", "inside_coverage", 3),
    # record = barrier - 1 s: [fire, writer_absence_only, match_only,
    #                          uncovered_barrier_absent]
    ("2026-08-10T12:41:34Z", "before_barrier", 4),
])
def test_uncovered_barrier_absent_terminal_is_accepted_both_shapes(
        tmp_path: Path, barrier_z: str, record_position: str, length: int) -> None:
    """The behavioural leg (G-T12 S-1): NO PRODUCTION WRITE PATH CAN EMIT
    ``uncovered_barrier_absent`` -- an ABSENCE, WITH ITS SEARCH, so this raw-
    blob trigger test IS the leg (the ruling's fallback, taken).

    ``evaluate_conjunction`` (the only caller of ``build_interval``, A2-75)
    has exactly TWO call sites (grep, ``swing/``):
    ``frozen_value_evidence.py:1223`` inside ``replay_verdict`` -- a READ-ONLY
    recompute for a stored-vs-recomputed COMPARISON; the segments array it
    builds is never persisted (doctrine #6, E-15: recorded-only keys,
    including segments, are never compared and this call never INSERTs) --
    and ``latched_origin.py:2034`` inside ``_rung9_tier2_escape``, the ONLY
    call site that feeds an INSERT-bound blob.

    ``_rung9_tier2_escape`` is reached only from the ``both_pre`` branch
    (``latched_origin.py:1941-1944``), which runs only AFTER the earlier
    guard ``if not installed: return _refuse("barrier_not_installed", ...)``
    (``latched_origin.py:1908-1914``) has ALREADY returned when the barrier
    is absent -- so at line 1944's call site ``barrier_installed=installed``
    is ALWAYS ``True`` (``installed`` is
    ``candidates_immutability_epoch.barrier_installed(conn)``, returned
    straight through by ``freeze_tier_for_candidate``,
    ``candidates_immutability_epoch.py:237-253``).  No production caller can
    ever pass ``False`` into ``build_interval`` on a path that reaches an
    INSERT -- confirmed by the sole write site,
    ``swing/data/repos/provenance_corrections.py:insert_provenance_correction``
    (``def`` at line 82), called from exactly one place,
    ``cohort_provenance_correction.py:3061``, with
    ``cited_frozen_value_evidence_json=latch.frozen_value_evidence_json`` --
    itself ``_rung9_tier2_escape``'s output.

    ``build_interval`` -- a real service function, never a hand-typed dict --
    still supplies the segments (the G-NEG precedent's own technique,
    ``test_g_neg_the_record_position_belt_refuses_a_forged_position`` above),
    so the trigger is exercised against a genuinely service-computed blob on
    a raw INSERT rather than an invented one.
    """
    from datetime import datetime

    from swing.trades import frozen_value_evidence as fve
    from tests._tier2_world_22a2 import (
        T25_AUTHOR_INSTANT,
        T25_PIPELINE_FINISHED,
        T25_RUN_TS,
    )

    interval = fve.build_interval(
        fire_lo_raw=T25_RUN_TS, fire_hi_raw=T25_PIPELINE_FINISHED,
        author_instant=datetime.fromisoformat(T25_AUTHOR_INSTANT),
        barrier_armed_raw=barrier_z, read_at="2026-09-23T12:00:00.000",
        barrier_installed=False)
    segments = interval["segments"]
    assert len(segments) == length
    assert segments[-1]["kind"] == "uncovered_barrier_absent"
    assert interval["record_position"] == record_position

    conn, payload, _ids = truthful_tier2_payload(tmp_path)
    try:
        blob = json.loads(payload[PROVENANCE_TIER2_EVIDENCE_FIELD])
        blob["interval"]["segments"] = segments
        blob["interval"]["record_position"] = record_position
        accepted = {**payload,
                   PROVENANCE_TIER2_EVIDENCE_FIELD: json.dumps(blob)}
        assert not _refused(conn, accepted)

        # A FOREIGN terminal is refused (same shape, same record_position;
        # only the terminal kind moves off the closed vocabulary).
        blob["interval"]["segments"][-1]["kind"] = "not_a_real_terminal"
        forged = {**payload,
                 PROVENANCE_TIER2_EVIDENCE_FIELD: json.dumps(blob)}
        assert _refused(conn, forged)
    finally:
        conn.close()
