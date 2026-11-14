"""D104 T1.1 -- migration 0042: provenance_corrections gains a second KIND.

Plan `docs/superpowers/plans/2026-11-11-sg-label-correction.md` T1.1-T1.5,
tests 1b-1m and 1v. The kind-2 row is built from trade 29's LIVE shape
(``build_sg_case``) by the production derivation helpers
(``watch_fire_payload``), never hand-written to pass.
"""
from __future__ import annotations

import copy
import json
import re
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    _current_version,
    ensure_schema,
    open_connection,
    run_migrations,
)
from swing.data.models import (
    ENTRY_INTENTS_ASSERTABLE,
    PROVENANCE_ADMISSION_TIERS,
    PROVENANCE_ADMISSION_TIERS_BY_KIND,
    PROVENANCE_CORRECTED_FIELDS,
    PROVENANCE_CORRECTION_KIND_FILL_UNSET,
    PROVENANCE_CORRECTION_KIND_WATCH_FIRE,
    PROVENANCE_CORRECTION_KINDS,
    PROVENANCE_WATCH_FIRE_CORRECTED_FIELDS,
    PROVENANCE_WATCH_FIRE_ENTRY_INTENT,
    PROVENANCE_WATCH_FIRE_ORIGIN,
)
from tests.data._migration_text import head_create_statement
from tests.trades._cohort_provenance_fixtures import (
    SG_FIRE_CANDIDATE_ID,
    SG_TRADE_ID,
    build_sg_case,
    watch_fire_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIG_DIR = REPO_ROOT / "swing" / "data" / "migrations"
M0039 = MIG_DIR / "0039_provenance_corrections_tier2.sql"
M0041 = MIG_DIR / "0041_replace_exposure_sweep.sql"
M0042 = MIG_DIR / "0042_provenance_corrections_watch_fire_relabel.sql"
CITATION = "trg_provenance_corrections_citation_graph"
APPEND_UPDATE = "trg_provenance_corrections_append_only_update"
KIND2_SENTENCE = "For correction_kind watch_fire_relabel (0042)"
APPEND_ONLY = "APPEND-ONLY"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _v42_sg(tmp_path: Path, name: str = "sg", **case) -> sqlite3.Connection:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    conn = ensure_schema(root / "swing.db", backup_dir=root / "bak")
    build_sg_case(conn, **case)
    conn.commit()
    return conn


def _insert(conn: sqlite3.Connection, payload: dict) -> int:
    cur = conn.execute(
        f"INSERT INTO provenance_corrections ({', '.join(payload)}) "
        f"VALUES ({', '.join('?' * len(payload))})", tuple(payload.values()))
    return int(cur.lastrowid)


def _refusal(conn: sqlite3.Connection, payload: dict) -> str:
    with pytest.raises(sqlite3.IntegrityError) as exc:
        _insert(conn, payload)
    conn.rollback()
    return str(exc.value)


def _truthful(tmp_path: Path) -> dict:
    """The truthful kind-2 row's columns, derived on a scratch SG world."""
    conn = _v42_sg(tmp_path, "payload_world")
    try:
        return watch_fire_payload(conn, apply_trade_update=False)
    finally:
        conn.close()


def _apply_trade_update(conn: sqlite3.Connection, payload: dict) -> None:
    applied = json.loads(payload["applied_value_json"])
    conn.execute(
        "UPDATE trades SET hypothesis_label = ?, candidate_id = ? WHERE id = ?",
        (applied["trades.hypothesis_label"], applied["trades.candidate_id"],
         payload["trade_id"]))


def _stored(conn: sqlite3.Connection, name: str) -> str:
    return conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()[0]


def _strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


# ---------------------------------------------------------------------------
# 1b -- the SG-shaped row: ACCEPTED as kind 2, REFUSED as kind 1
# ---------------------------------------------------------------------------
def test_1b_the_sg_row_is_accepted_as_kind_2(tmp_path: Path) -> None:
    conn = _v42_sg(tmp_path)
    try:
        payload = watch_fire_payload(conn)
        new_id = _insert(conn, payload)
        conn.commit()
        row = conn.execute(
            "SELECT correction_kind, admission_tier, cited_candidate_id, "
            "cited_daily_recommendation_id FROM provenance_corrections "
            "WHERE provenance_correction_id = ?", (new_id,)).fetchone()
    finally:
        conn.close()
    assert row == ("watch_fire_relabel", "last_fire", SG_FIRE_CANDIDATE_ID,
                   None)


def test_1b_the_same_row_is_refused_as_kind_1(tmp_path: Path) -> None:
    payload = _truthful(tmp_path)
    conn = _v42_sg(tmp_path, "kind1")
    try:
        _apply_trade_update(conn, payload)
        as_kind1 = dict(payload, correction_kind="fill_unset_provenance",
                        admission_tier="last_word")
        _refusal(conn, as_kind1)
        # and with no kind column at all (the DEFAULT is kind 1)
        no_kind = {k: v for k, v in payload.items() if k != "correction_kind"}
        no_kind["admission_tier"] = "last_word"
        _refusal(conn, no_kind)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1c / 1d -- an aplus citation; a post-dating citation
# ---------------------------------------------------------------------------
def test_1c_a_kind_2_row_citing_an_aplus_candidate_is_refused(
        tmp_path: Path) -> None:
    payload = _truthful(tmp_path)
    conn = _v42_sg(tmp_path, "aplus", buckets={SG_FIRE_CANDIDATE_ID: "aplus"})
    try:
        _apply_trade_update(conn, payload)
        msg = _refusal(conn, payload)
    finally:
        conn.close()
    assert KIND2_SENTENCE in msg


def test_1d_a_kind_2_row_whose_citation_post_dates_the_fill_is_refused(
        tmp_path: Path) -> None:
    payload = _truthful(tmp_path)
    conn = _v42_sg(tmp_path, "postdate")
    try:
        _apply_trade_update(conn, payload)
        late = dict(payload, cited_candidate_action_session_date="2026-11-07")
        _refusal(conn, late)
    finally:
        conn.close()


def test_1d_the_post_dating_check_itself_refuses_kind_2(tmp_path: Path) -> None:
    """The CHECK alone (the trigger is not in this scratch table)."""
    payload = _truthful(tmp_path)
    c = _bare_table()
    try:
        _insert(c, payload)  # the truthful row satisfies every CHECK
        c.rollback()
        late = dict(payload, cited_candidate_action_session_date="2026-11-07")
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _insert(c, late)
    finally:
        c.close()


# ---------------------------------------------------------------------------
# 1e -- a missing key is refused; the kind-2 COALESCE is load-bearing
# ---------------------------------------------------------------------------
def _table_statement() -> str:
    """0042's CREATE TABLE, named ``provenance_corrections`` (it is created
    under the scratch name and RENAMEd, so the HEAD-statement helper, which
    matches the exact name, cannot find it)."""
    text = M0042.read_text(encoding="utf-8")
    start = text.index("CREATE TABLE provenance_corrections__0042 (")
    end = text.index("\n);\n", start) + len("\n)")
    return text[start:end].replace(
        "provenance_corrections__0042", "provenance_corrections", 1)


def _bare_table(statement: str | None = None) -> sqlite3.Connection:
    """The 0042 CREATE TABLE alone, in memory, FKs off, no triggers: the
    CHECKs are the only gate, so a CHECK test cannot pass on the trigger."""
    if statement is None:
        statement = _table_statement()
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(statement)
    return c


def _drop_key(raw: str, key: str) -> str:
    env = json.loads(raw)
    del env[key]
    return json.dumps(env, sort_keys=True)


@pytest.mark.parametrize(("column", "key"), [
    ("applied_value_json", "trades.hypothesis_label"),
    ("pre_value_json", "trades.candidate_id"),
])
def test_1e_a_kind_2_envelope_missing_a_key_is_refused(
        tmp_path: Path, column: str, key: str) -> None:
    payload = _truthful(tmp_path)
    broken = dict(payload, **{column: _drop_key(payload[column], key)})
    c = _bare_table()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _insert(c, broken)
    finally:
        c.close()
    conn = _v42_sg(tmp_path, f"full_{column}")
    try:
        _apply_trade_update(conn, payload)
        _refusal(conn, broken)
    finally:
        conn.close()


def test_1e_the_kind_2_applied_coalesce_is_load_bearing(tmp_path: Path) -> None:
    """Mutation: the kind-2 applied arm written BARE accepts the row."""
    payload = _truthful(tmp_path)
    broken = dict(payload, applied_value_json=_drop_key(
        payload["applied_value_json"], "trades.hypothesis_label"))
    statement = _table_statement()
    arm_start = statement.index(
        "WHEN 'watch_fire_relabel' THEN\n"
        "           CASE WHEN json_valid(applied_value_json) THEN COALESCE(")
    arm_end = statement.index("= 'pipeline_watch_manual', 0)", arm_start)
    arm = statement[arm_start:arm_end + len("= 'pipeline_watch_manual', 0)")]
    bare_arm = (arm.replace("THEN COALESCE(", "THEN (", 1)
                [: -len(", 0)")] + ")")
    mutated = statement.replace(arm, bare_arm, 1)
    assert mutated != statement
    c = _bare_table(mutated)
    try:
        _insert(c, broken)  # ACCEPTED: the bare form passes a NULL CHECK
    finally:
        c.close()


# ---------------------------------------------------------------------------
# 1f -- REPLACE / ON CONFLICT DO NOTHING against an existing kind-2 row
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("verb", [
    "INSERT OR REPLACE", "REPLACE", "INSERT OR IGNORE"])
def test_1f_a_conflicting_insert_cannot_replace_a_kind_2_row(
        tmp_path: Path, verb: str) -> None:
    conn = _v42_sg(tmp_path)
    try:
        payload = watch_fire_payload(conn)
        first = _insert(conn, payload)
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError, match="trg_pc_no_replace"):
            conn.execute(
                f"{verb} INTO provenance_corrections ({', '.join(payload)}) "
                f"VALUES ({', '.join('?' * len(payload))})",
                tuple(payload.values()))
        conn.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="trg_pc_no_replace"):
            conn.execute(
                f"INSERT INTO provenance_corrections ({', '.join(payload)}) "
                f"VALUES ({', '.join('?' * len(payload))}) "
                "ON CONFLICT DO NOTHING", tuple(payload.values()))
        conn.rollback()
        rows = conn.execute(
            "SELECT provenance_correction_id FROM provenance_corrections"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [(first,)]


# ---------------------------------------------------------------------------
# 1g -- CHARC P5, BOTH halves, on a kind-2 row
# ---------------------------------------------------------------------------
def _kind2_row_world(tmp_path: Path, name: str = "p5") -> sqlite3.Connection:
    conn = _v42_sg(tmp_path, name)
    _insert(conn, watch_fire_payload(conn))
    # an existing daily_recommendations row (another ticker) to point at
    conn.execute(
        "INSERT INTO daily_recommendations (evaluation_run_id, data_asof_date,"
        " action_session_date, ticker, recommendation) VALUES "
        "(193, '2026-11-04', '2026-11-05', 'ZZZ', 'near_trigger')")
    conn.commit()
    return conn


def _rec_id(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT max(id) FROM daily_recommendations").fetchone()[0]


def _delete_the_cited_fill(conn: sqlite3.Connection) -> None:
    from tests._22i_guard_seam import guards_dropped

    conn.execute("PRAGMA foreign_keys = ON")
    # the fill's FEI reading goes with it (fixture disposal, seam kind 3)
    with guards_dropped(conn, "trg_fei_no_delete"):
        conn.execute("DELETE FROM fill_envelope_identity WHERE fill_id = 60")
    conn.execute("DELETE FROM fills WHERE fill_id = 60")


def test_1g_the_permitted_fk_set_null_succeeds_on_a_kind_2_row(
        tmp_path: Path) -> None:
    conn = _kind2_row_world(tmp_path)
    try:
        _delete_the_cited_fill(conn)
        conn.commit()
        row = conn.execute(
            "SELECT entry_fill_id, entry_fill_id_at_correction "
            "FROM provenance_corrections").fetchone()
    finally:
        conn.close()
    assert row == (None, 60)


@pytest.mark.parametrize("assignment", [
    "cited_daily_recommendation_id = {rec}",
    "correction_reason = 'x'",
    "correction_kind = 'fill_unset_provenance'",
])
def test_1g_a_forbidden_update_on_a_kind_2_row_is_aborted(
        tmp_path: Path, assignment: str) -> None:
    conn = _kind2_row_world(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match=APPEND_ONLY):
            conn.execute("UPDATE provenance_corrections SET "
                         + assignment.format(rec=_rec_id(conn)))
    finally:
        conn.close()


def _replace_update_trigger(conn: sqlite3.Connection, sql: str) -> None:
    conn.execute(f"DROP TRIGGER {APPEND_UPDATE}")
    conn.execute(sql)


def test_1g_sibling_the_live_0041_form_aborts_the_permitted_update(
        tmp_path: Path) -> None:
    """The pre-change direction: 0041's `=` under the COALESCE wrap ABORTS
    the FK SET NULL on a kind-2 row (NULL = NULL -> NULL -> 0 -> fires)."""
    from tests.data._migration_text import create_statement_in

    conn = _kind2_row_world(tmp_path)
    try:
        _replace_update_trigger(
            conn, create_statement_in(M0041, APPEND_UPDATE))
        with pytest.raises(sqlite3.IntegrityError, match=APPEND_ONLY):
            _delete_the_cited_fill(conn)
    finally:
        conn.close()


def test_1g_sibling_the_bare_form_fails_open_on_null_to_value(
        tmp_path: Path) -> None:
    """The fail-OPEN direction (0041's census case): with the FK-null branch
    TRUE in the same statement, the bare pre-0041 form (`WHEN NOT (`, `=`)
    goes NULL on the NULL -> value change and DOES NOT FIRE -- the refusal
    that remains is the presence CHECK's, never the append-only trigger's.
    Under 0042's `IS` the same statement is refused BY THE TRIGGER."""
    from tests.data._migration_text import create_statement_in

    messages = {}
    for form in ("bare", "0042"):
        conn = _kind2_row_world(tmp_path, f"p5_{form}")
        try:
            if form == "bare":
                _replace_update_trigger(
                    conn, create_statement_in(M0039, APPEND_UPDATE))
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM fills WHERE fill_id = 60")
            with pytest.raises(sqlite3.IntegrityError) as exc:
                conn.execute(
                    "UPDATE provenance_corrections SET entry_fill_id = NULL, "
                    f"cited_daily_recommendation_id = {_rec_id(conn)}")
            messages[form] = str(exc.value)
        finally:
            conn.close()
    assert APPEND_ONLY not in messages["bare"]
    assert "CHECK" in messages["bare"]
    assert APPEND_ONLY in messages["0042"]


# ---------------------------------------------------------------------------
# 1h / 1i -- the trigger's own message; malformed JSON reaches it
# ---------------------------------------------------------------------------
def test_1h_a_wrong_ticker_moved_anchor_raises_the_trigger_message(
        tmp_path: Path) -> None:
    payload = _truthful(tmp_path)
    conn = _v42_sg(tmp_path, "ticker")
    try:
        other = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
            "rs_method) VALUES (192, 'ZZZ', 'watch', 'fallback_spy')"
        ).lastrowid
        _apply_trade_update(conn, payload)
        pre = json.loads(payload["pre_value_json"])
        pre["trades.candidate_id"] = int(other)
        msg = _refusal(conn, dict(
            payload, pre_value_json=json.dumps(pre, sort_keys=True)))
    finally:
        conn.close()
    assert KIND2_SENTENCE in msg
    assert "CHECK" not in msg


def test_1h_a_standard_intent_trade_is_refused_by_the_trigger(
        tmp_path: Path) -> None:
    payload = _truthful(tmp_path)
    conn = _v42_sg(tmp_path, "standard", entry_intent="standard")
    try:
        _apply_trade_update(conn, payload)
        msg = _refusal(conn, payload)
    finally:
        conn.close()
    assert KIND2_SENTENCE in msg


@pytest.mark.parametrize("column", ["applied_value_json", "pre_value_json"])
def test_1i_malformed_json_is_refused_by_the_trigger_s_own_message(
        tmp_path: Path, column: str) -> None:
    payload = _truthful(tmp_path)
    conn = _v42_sg(tmp_path, f"malformed_{column}")
    try:
        _apply_trade_update(conn, payload)
        msg = _refusal(conn, dict(payload, **{column: "{not json"}))
    finally:
        conn.close()
    assert KIND2_SENTENCE in msg
    assert "malformed JSON" not in msg


@pytest.mark.parametrize("column", ["applied_value_json", "pre_value_json"])
def test_1i_the_json_valid_guard_is_load_bearing(
        tmp_path: Path, column: str) -> None:
    payload = _truthful(tmp_path)
    conn = _v42_sg(tmp_path, f"unguarded_{column}")
    try:
        sql = _stored(conn, CITATION)
        guarded = (f"CASE WHEN json_valid(NEW.{column})\n"
                   f"                                    THEN json_extract(NEW.{column},")
        assert sql.count(guarded) == 1
        start = sql.index(guarded)
        end = sql.index(" END", start) + len(" END")
        original = sql[start:end]
        bare = original.replace(
            f"CASE WHEN json_valid(NEW.{column})\n"
            "                                    THEN ", "", 1)[: -len(" END")]
        conn.execute(f"DROP TRIGGER {CITATION}")
        conn.execute(sql.replace(original, bare, 1))
        _apply_trade_update(conn, payload)
        with pytest.raises(sqlite3.OperationalError, match="malformed JSON"):
            _insert(conn, dict(payload, **{column: "{not json"}))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1j / 1k / 1l -- the migration itself
# ---------------------------------------------------------------------------
def _v41(tmp_path: Path, name: str = "v41") -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    c = open_connection(root / "swing.db")
    try:
        run_migrations(c, target_version=41, backup_dir=root / "bak")
    finally:
        c.close()
    return root / "swing.db"


def test_1j_0042_applies_on_a_v41_database_carrying_trg_eia_audit_trail(
        tmp_path: Path) -> None:
    db = _v41(tmp_path)
    c = open_connection(db)
    try:
        assert c.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'trg_eia_audit_trail'"
        ).fetchone() is not None
        run_migrations(c, target_version=42, backup_dir=tmp_path / "bak42")
        assert _current_version(c) == 42
    finally:
        c.close()


def test_1j_the_bare_rename_would_abort_0042(tmp_path: Path) -> None:
    db = _v41(tmp_path)
    text = M0042.read_text(encoding="utf-8")
    assert text.count("PRAGMA legacy_alter_table=ON;\n") == 1
    bare = (text.replace("PRAGMA legacy_alter_table=ON;\n", "", 1)
                .replace("PRAGMA legacy_alter_table=OFF;\n", "", 1))
    c = sqlite3.connect(db)
    c.isolation_level = None
    try:
        c.execute("PRAGMA foreign_keys = OFF")
        c.execute("PRAGMA legacy_alter_table = OFF")
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            c.executescript(bare)
    finally:
        try:
            c.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        c.close()


def _cadl_kind1_row(tmp_path: Path) -> dict:
    """The Demand-C row for the CADL shape, from the production service."""
    from swing.trades.cohort_provenance_correction import (
        correct_cohort_provenance,
    )
    from tests.trades._cohort_provenance_fixtures import build_cadl_case

    root = tmp_path / "cadl_head"
    root.mkdir()
    c = ensure_schema(root / "swing.db", backup_dir=root / "bak")
    try:
        ids = build_cadl_case(c)
        c.commit()
        correct_cohort_provenance(
            c, trade_id=ids["trade_id"], cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=ids["daily_recommendation_id"],
            reason="1k fixture")
        cols = [r[1] for r in c.execute(
            "PRAGMA table_info(provenance_corrections)")]
        row = c.execute("SELECT * FROM provenance_corrections").fetchone()
        return dict(zip(cols, row, strict=True))
    finally:
        c.close()


def test_1k_the_live_shaped_kind_1_row_survives_byte_equal_and_twice_is_noop(
        tmp_path: Path) -> None:
    from tests.trades._cohort_provenance_fixtures import build_cadl_case

    head_row = _cadl_kind1_row(tmp_path)
    v41_row = {k: v for k, v in head_row.items() if k != "correction_kind"}
    db = _v41(tmp_path)
    c = open_connection(db)
    try:
        build_cadl_case(c)
        _insert(c, v41_row)
        c.execute("UPDATE sqlite_sequence SET seq = 7 "
                  "WHERE name = 'provenance_corrections'")
        c.commit()
        before = c.execute("SELECT * FROM provenance_corrections").fetchall()
        run_migrations(c, target_version=42, backup_dir=tmp_path / "b1")
        cols = [r[1] for r in c.execute(
            "PRAGMA table_info(provenance_corrections)")]
        after = c.execute("SELECT * FROM provenance_corrections").fetchall()
        seq = c.execute("SELECT seq FROM sqlite_sequence "
                        "WHERE name = 'provenance_corrections'").fetchall()
        schema1 = c.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
        run_migrations(c, target_version=42, backup_dir=tmp_path / "b2")
        assert c.execute(
            "SELECT * FROM provenance_corrections").fetchall() == after
        assert c.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY name"
        ).fetchall() == schema1
        assert c.execute("SELECT seq FROM sqlite_sequence WHERE name = "
                         "'provenance_corrections'").fetchall() == seq
    finally:
        c.close()
    assert cols[-1] == "correction_kind"
    assert [r[:-1] for r in after] == before
    assert [r[-1] for r in after] == ["fill_unset_provenance"]
    assert seq == [(7,)]


def test_1k_v42_is_head_and_the_header_names_the_gate_row() -> None:
    assert EXPECTED_SCHEMA_VERSION == 42
    text = M0042.read_text(encoding="utf-8")
    flat = " ".join(text.replace("--", " ").split())
    assert ('BackupGateSpec(41, "sg-label", '
            'PHASE22_SG_LABEL_PRE_MIGRATION_EXPECTED_TABLES, '
            '"_sg_label_backup_gate", "pre-sg-label")') in flat
    assert text.rstrip().endswith(
        "UPDATE schema_version SET version = 42;\n\nCOMMIT;".rstrip())


# ---------------------------------------------------------------------------
# 1m -- DRIFT: the SQL and Python spellings of both families (mandatory)
# ---------------------------------------------------------------------------
def test_1m_drift_sql_and_python_agree_for_both_kinds(tmp_path: Path) -> None:
    c = ensure_schema(tmp_path / "d.db")
    try:
        table = _strip_comments(_stored(c, "provenance_corrections"))
        cit = _strip_comments(_stored(c, CITATION))
        trades = _stored(c, "trades")
    finally:
        c.close()
    kinds = re.findall(r"correction_kind IN \(([^)]*)\)", table)
    assert len(kinds) == 1
    assert set(re.findall(r"'([^']+)'", kinds[0])) == PROVENANCE_CORRECTION_KINDS
    tiers = re.findall(r"CHECK \(admission_tier IN \(([^)]*)\)", table)
    assert len(tiers) == 1
    assert set(re.findall(r"'([^']+)'", tiers[0])) == PROVENANCE_ADMISSION_TIERS
    assert len(PROVENANCE_ADMISSION_TIERS) == 4
    # the coupling CHECK, per kind
    coupling = re.search(
        r"CHECK \(\(correction_kind = '([a-z_]+)'\s+AND admission_tier IN "
        r"\(([^)]*)\)\)\s+OR \(correction_kind = '([a-z_]+)'\s+"
        r"AND admission_tier = '([a-z_]+)'\)\)", table)
    assert coupling is not None
    assert {coupling.group(1): set(re.findall(r"'([^']+)'", coupling.group(2))),
            coupling.group(3): {coupling.group(4)}} == {
        k: set(v) for k, v in PROVENANCE_ADMISSION_TIERS_BY_KIND.items()}
    # the trigger's kind literals (edits 1, 2, 3) are exactly the Python set
    blocks = [cit[m.end():cit.index(" END", m.end())]
              for m in re.finditer(r"CASE NEW\.correction_kind", cit)]
    assert len(blocks) == 2  # edit 1 and edit 2
    for block in blocks:
        assert set(re.findall(r"WHEN '([a-z_]+)'", block)) == (
            PROVENANCE_CORRECTION_KINDS)
    assert set(re.findall(r"NEW\.correction_kind = '([a-z_]+)'", cit)) == (
        PROVENANCE_CORRECTION_KINDS)
    assert "WHEN 'watch_fire_relabel'    THEN 'watch'" in cit
    tier_literals = set(re.findall(r"'(last_word|last_fire|latch_ladder\w*)'", cit))
    assert tier_literals == PROVENANCE_ADMISSION_TIERS
    # the per-kind corrected-fields literals equal the two Python tuples
    cf = re.findall(
        r"WHEN '([a-z_]+)' THEN\s+CASE WHEN json_valid\(corrected_fields_json\)"
        r" THEN COALESCE\(\s+json_array_length\(corrected_fields_json\) = (\d)"
        r"((?:\s+AND json_extract\(corrected_fields_json, '\$\[\d\]'\)\s+= '[^']+')+)",
        table)
    got = {k: tuple(re.findall(r"= '([^']+)'", body)) for k, n, body in cf}
    assert got == {
        PROVENANCE_CORRECTION_KIND_FILL_UNSET: tuple(PROVENANCE_CORRECTED_FIELDS),
        PROVENANCE_CORRECTION_KIND_WATCH_FIRE:
            tuple(PROVENANCE_WATCH_FIRE_CORRECTED_FIELDS),
    }
    assert {k: int(n) for k, n, _ in cf} == {
        PROVENANCE_CORRECTION_KIND_FILL_UNSET: len(PROVENANCE_CORRECTED_FIELDS),
        PROVENANCE_CORRECTION_KIND_WATCH_FIRE:
            len(PROVENANCE_WATCH_FIRE_CORRECTED_FIELDS),
    }
    # the kind-2 origin and intent literals (edit 2) equal their mirrors
    assert set(re.findall(r"t\.trade_origin = '([a-z_]+)'", cit)) == {
        PROVENANCE_WATCH_FIRE_ORIGIN}
    assert set(re.findall(r"t\.entry_intent = '([a-z_]+)'", cit)) == {
        PROVENANCE_WATCH_FIRE_ENTRY_INTENT}
    assert PROVENANCE_WATCH_FIRE_ENTRY_INTENT in ENTRY_INTENTS_ASSERTABLE
    assert f"'{PROVENANCE_WATCH_FIRE_ENTRY_INTENT}'" in trades
    # the table's kind-2 origin literals (pre + applied) equal the mirror
    assert table.count(f"= '{PROVENANCE_WATCH_FIRE_ORIGIN}'") == 2


def test_1m_the_head_citation_and_update_triggers_live_in_0042() -> None:
    assert head_create_statement(CITATION)[0] == M0042
    assert head_create_statement(APPEND_UPDATE)[0] == M0042


# ---------------------------------------------------------------------------
# 1v -- E2: no kind-1 outcome changes (the two live rows' shapes, v41 vs v42)
# ---------------------------------------------------------------------------
def _cadl_world(tmp_path: Path, version: int, name: str) -> sqlite3.Connection:
    from tests.trades._cohort_provenance_fixtures import build_cadl_case

    root = tmp_path / name
    root.mkdir()
    c = open_connection(root / "swing.db")
    run_migrations(c, target_version=version, backup_dir=root / "bak")
    build_cadl_case(c)
    c.commit()
    return c


def _outcome(conn: sqlite3.Connection, payload: dict) -> str:
    try:
        _insert(conn, payload)
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return "refused:citation" if "citation graph" in str(exc) else (
            f"refused:{exc}")
    conn.rollback()
    return "accepted"


@pytest.mark.parametrize("version", [41, 42])
def test_1v_the_cadl_last_word_shape_outcomes_are_unchanged(
        tmp_path: Path, version: int) -> None:
    row = _cadl_kind1_row(tmp_path)
    row.pop("provenance_correction_id")
    if version == 41:
        row.pop("correction_kind")
    conn = _cadl_world(tmp_path, version, f"cadl{version}")
    try:
        conn.execute("UPDATE trades SET hypothesis_label = ?, candidate_id = ?,"
                     " trade_origin = 'pipeline_aplus'",
                     (json.loads(row["applied_value_json"])[
                         "trades.hypothesis_label"], row["cited_candidate_id"]))
        assert _outcome(conn, row) == "accepted"
        broken = dict(row, cited_evaluation_run_id=row["cited_evaluation_run_id"] + 99)
        assert _outcome(conn, broken) == "refused:citation"
    finally:
        conn.close()


@pytest.mark.parametrize("version", [41, 42])
def test_1v_the_tier2_shape_outcomes_are_unchanged(
        tmp_path: Path, version: int) -> None:
    from tests._tier2_world_22a2 import (
        T25_ORDER_ID,
        base_last_word_payload,
        build_pre_barrier_world,
        load_seventh_blob,
        tier2_probe_blob,
    )

    base = base_last_word_payload(tmp_path)
    conn, ids = build_pre_barrier_world(tmp_path, f"t25_{version}",
                                        target_version=version)
    try:
        payload = copy.deepcopy(base)
        payload.pop("provenance_correction_id")
        if version == 41:
            payload.pop("correction_kind")
        payload.update(
            admission_tier="latch_ladder_tier2",
            cited_latch_link_id=ids["link_id"],
            cited_latch_validity_intent_id=ids["validity_id"],
            cited_latch_place_intent_id=ids["place_id"],
            cited_latch_broker_order_id=T25_ORDER_ID,
            cited_latch_probe_json=json.dumps(tier2_probe_blob(conn, ids)),
            cited_frozen_value_evidence_json=json.dumps(
                load_seventh_blob(conn, applied_at=payload["applied_at"])))
        assert _outcome(conn, payload) == "accepted"
        broken = dict(payload,
                      cited_evaluation_run_id=payload["cited_evaluation_run_id"] + 99)
        assert _outcome(conn, broken) == "refused:citation"
    finally:
        conn.close()


def test_sg_fixture_reads_trade_29_live_shape(tmp_path: Path) -> None:
    conn = _v42_sg(tmp_path)
    try:
        t = conn.execute(
            "SELECT ticker, trade_origin, entry_intent, hypothesis_label, "
            "candidate_id FROM trades WHERE id = ?", (SG_TRADE_ID,)).fetchone()
    finally:
        conn.close()
    assert t == ("SG", "pipeline_watch_manual", "hypothesis_test_by_design",
                 "Broad-watch baseline (watch); failed: proximity_20ma, "
                 "tightness", 15980)


# Codex R1-7 (sg-label exec round 1): the kind-2 label arms' whitespace set is
# PYTHON's (`str.strip()`, i.e. `str.isspace`), so a raw insert the model would
# refuse while hydrating is refused at the table first. Every code point is
# enumerated from Python itself, so the comparator cannot drift from the
# reader it mirrors.
_PY_WHITESPACE = "".join(
    chr(c) for c in range(0x110000) if chr(c).isspace())


def _with_label(raw: str, label: str) -> str:
    env = json.loads(raw)
    env["trades.hypothesis_label"] = label
    return json.dumps(env, sort_keys=True)


@pytest.mark.parametrize("column", ["applied_value_json", "pre_value_json"])
@pytest.mark.parametrize("label", [pytest.param(ch, id=f"U+{ord(ch):04X}")
                                   for ch in _PY_WHITESPACE]
                         + [pytest.param(_PY_WHITESPACE, id="all")])
def test_r1_7_a_python_whitespace_kind_2_label_is_refused_by_the_table(
        tmp_path: Path, column: str, label: str) -> None:
    assert label.strip() == "", "the premise: Python refuses this label"
    payload = _truthful(tmp_path)
    broken = dict(payload, **{column: _with_label(payload[column], label)})
    c = _bare_table()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _insert(c, broken)
    finally:
        c.close()


def test_r1_7_a_padded_kind_2_label_is_not_refused_by_the_table(
        tmp_path: Path) -> None:
    """The counterfactual: the widened set refuses only whitespace-ONLY
    labels; the truthful payload and a label with inner text still pass."""
    payload = _truthful(tmp_path)
    padded = dict(payload, applied_value_json=_with_label(
        payload["applied_value_json"], "\tx　"))
    for row in (payload, padded):
        c = _bare_table()
        try:
            _insert(c, row)
        finally:
            c.close()
