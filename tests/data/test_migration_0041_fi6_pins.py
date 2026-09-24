"""22-I T14 -- the F-I6 backstop pins (CHARC F-I6 (a); plan section 4.5).

F-I6 (a) CONFIRMED-with-cited-backstop: a validation trigger that is OPEN on
an input only a same-row NOT NULL / CHECK -- or a SIBLING trigger on the SAME
statement -- refuses is CONFIRMED, because the statement ABORTS every time
(the NULL-WHEN gotcha's harm is SILENT acceptance). What is unguarded is the
ASSUMPTION that the backstop stays, so each backstop gets ONE pin here:

  * precondition: the backstop fires on the SAME statement as the open
    trigger (every case below is a single INSERT; a backstop on a later
    statement would not qualify);
  * a NOT NULL / CHECK backstop can vanish only by a table REBUILD, which the
    D51 manifest reports as CHANGED on that table;
  * a sibling-trigger backstop is pinned with the FULL trigger set present --
    removing the sibling turns its pin RED.

Every row is planted RAW on a v41 DB (plain sqlite3, FK ON), each mutation
of a VALID real-shape row whose unmutated control is admitted. 0041 adds no
trigger here and touches none of these validators.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tests._22b_fixtures import record_envelope_readings, seed_amn_row5, seed_trade20
from tests.data._22i_seed import migrated, outcome
from tests.data.test_migration_0040_attestations import tier2_row

_EIA = "entry_intent_attestations"


def _eia_world(tmp_path: Path) -> sqlite3.Connection:
    """Trade 20 (+ fills 41/44 + AMN row 5) raw on a v41 DB: the 22-B tier-2
    world, in which ``tier2_row()`` -- the service's own row shape -- admits."""
    c = migrated(tmp_path, 41)
    seed_amn_row5(c)
    seed_trade20(c)
    record_envelope_readings(c)
    return c


def _ins(table: str, row: dict[str, Any]) -> tuple[str, tuple]:
    cols = list(row)
    return (f"INSERT INTO {table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})", tuple(row.values()))


def _raw_error(c: sqlite3.Connection, table: str, row: dict[str, Any]) -> str | None:
    c.execute("SAVEPOINT fi6")
    try:
        c.execute(*_ins(table, row))
        return None
    except sqlite3.IntegrityError as exc:
        return str(exc)
    finally:
        c.execute("ROLLBACK TO fi6")
        c.execute("RELEASE fi6")


def _table_sql(c: sqlite3.Connection, table: str) -> str:
    return c.execute("SELECT sql FROM sqlite_master WHERE type = 'table' "
                     "AND name = ?", (table,)).fetchone()[0]


def _has_trigger(c: sqlite3.Connection, name: str) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE type = 'trigger' "
                     "AND name = ?", (name,)).fetchone() is not None


def test_fi6_eia_control_admits(tmp_path: Path) -> None:
    """The control every eia pin mutates: the unmutated row is ADMITTED, so
    each refusal below is the mutation's, not the fixture's."""
    c = _eia_world(tmp_path)
    try:
        assert outcome(c, *_ins(_EIA, tier2_row())) == "OK"
    finally:
        c.close()


def test_fi6_1_admission_tier_null_is_refused_by_not_null(tmp_path: Path) -> None:
    """FI6-1. Open: trg_eia_structural and trg_eia_tier2 read admission_tier
    NULL as "not my tier". Backstop (entry_intent_attestations DDL, quoted from
    sqlite_master):

        admission_tier TEXT NOT NULL
            CHECK (admission_tier IN ('structural','contemporaneous_record')),
    """
    c = _eia_world(tmp_path)
    try:
        ddl = _table_sql(c, _EIA)
        assert "admission_tier TEXT NOT NULL" in ddl
        assert "CHECK (admission_tier IN ('structural','contemporaneous_record'))" in ddl
        err = _raw_error(c, _EIA, tier2_row(admission_tier=None))
    finally:
        c.close()
    assert err == "NOT NULL constraint failed: entry_intent_attestations.admission_tier"


def test_fi6_2_trade_id_null_is_refused_by_sibling_outcome(tmp_path: Path) -> None:
    """FI6-2. Open: trg_eia_audit_trail, trg_eia_cited_fields, trg_eia_tier2 on
    trade_id NULL. Backstop: the SIBLING trg_eia_outcome (BEFORE INSERT ON
    entry_intent_attestations), on the same statement."""
    c = _eia_world(tmp_path)
    try:
        assert _has_trigger(c, "trg_eia_outcome")
        verdict = outcome(c, *_ins(_EIA, tier2_row(trade_id=None)))
    finally:
        c.close()
    assert verdict == "TRIGGER:trg_eia_outcome", verdict


@pytest.mark.parametrize("cited", [None, ["why_now"], ["notes"]],
                         ids=["null", "member0-absent", "member1-absent"])
def test_fi6_3_cited_fields_is_refused_by_sibling_cited_fields(
        tmp_path: Path, cited: list[str] | None) -> None:
    """FI6-3. Open: trg_eia_audit_trail on cited_fields_json NULL, or its
    `$[0]` / `$[1]` member absent. Backstop: the SIBLING trg_eia_cited_fields
    (BEFORE INSERT ON entry_intent_attestations), on the same statement."""
    c = _eia_world(tmp_path)
    try:
        assert _has_trigger(c, "trg_eia_cited_fields")
        value = None if cited is None else json.dumps(cited)
        verdict = outcome(c, *_ins(_EIA, tier2_row(cited_fields_json=value)))
    finally:
        c.close()
    assert verdict == "TRIGGER:trg_eia_cited_fields", verdict


def test_fi6_4_order_id_null_is_refused_by_sibling_trade_binding(tmp_path: Path) -> None:
    """FI6-4. Open: trg_eia_structural, trg_eia_tier2 on entry_broker_order_id
    NULL. Backstop: the SIBLING trg_eia_trade_binding (BEFORE INSERT ON
    entry_intent_attestations; its NULL-id close, RULING G1d item 3), on the
    same statement."""
    c = _eia_world(tmp_path)
    try:
        assert _has_trigger(c, "trg_eia_trade_binding")
        verdict = outcome(c, *_ins(_EIA, tier2_row(entry_broker_order_id=None)))
    finally:
        c.close()
    assert verdict == "TRIGGER:trg_eia_trade_binding", verdict


# ---------------------------------------------------------------------------
# provenance_corrections: the citation trigger's two schema backstops
# ---------------------------------------------------------------------------
_PC_CACHE: dict[str, Any] = {}


def _pc_payload(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Every column of the PRODUCTION service's last_word row for trade 25
    (``tests/_tier2_world_22a2.base_last_word_payload``), built once."""
    if "payload" not in _PC_CACHE:
        from tests._tier2_world_22a2 import base_last_word_payload

        _PC_CACHE["payload"] = base_last_word_payload(tmp_path_factory.mktemp("pc-base"))
    return dict(_PC_CACHE["payload"])


def _pc_world(tmp_path: Path) -> sqlite3.Connection:
    from tests._tier2_world_22a2 import build_last_word_world

    c = build_last_word_world(tmp_path)
    c.isolation_level = None
    assert c.execute("SELECT version FROM schema_version").fetchone()[0] == 41
    return c


def test_fi6_pc_control_admits(tmp_path: Path,
                               tmp_path_factory: pytest.TempPathFactory) -> None:
    c = _pc_world(tmp_path)
    try:
        assert _raw_error(c, "provenance_corrections", _pc_payload(tmp_path_factory)) is None
    finally:
        c.close()


@pytest.mark.parametrize("mode", ["absent", "json-null"])
@pytest.mark.parametrize("key", ["action", "fill_datetime", "fill_id", "trade_id"])
def test_fi6_5_snapshot_key_is_refused_by_the_pc_check(
        tmp_path: Path, tmp_path_factory: pytest.TempPathFactory,
        key: str, mode: str) -> None:
    """FI6-5. Open: trg_provenance_corrections_citation_graph on an
    entry_fill_snapshot_json key absent / JSON-null. Backstop: the table CHECK
    (provenance_corrections DDL, 0036, quoted from sqlite_master):

        CHECK (CASE WHEN json_valid(entry_fill_snapshot_json) THEN COALESCE(
                   json_extract(entry_fill_snapshot_json, '$.fill_id')
                       = entry_fill_id_at_correction
               AND json_extract(entry_fill_snapshot_json, '$.trade_id') = trade_id
               AND json_extract(entry_fill_snapshot_json, '$.action') = 'entry'
               AND json_extract(entry_fill_snapshot_json, '$.fill_datetime') IS NOT NULL
               AND substr(json_extract(entry_fill_snapshot_json, '$.fill_datetime'), 1, 10)
                       = entry_fill_session_date, 0)
               ELSE 0 END),
    """
    payload = _pc_payload(tmp_path_factory)
    snap = json.loads(payload["entry_fill_snapshot_json"])
    assert key in snap
    if mode == "absent":
        del snap[key]
    else:
        snap[key] = None
    payload["entry_fill_snapshot_json"] = json.dumps(snap, sort_keys=True)
    c = _pc_world(tmp_path)
    try:
        ddl = _table_sql(c, "provenance_corrections")
        assert "json_extract(entry_fill_snapshot_json, '$.action') = 'entry'" in ddl
        err = _raw_error(c, "provenance_corrections", payload)
    finally:
        c.close()
    assert err is not None and err.startswith("CHECK constraint failed"), err
    assert "entry_fill_snapshot_json" in err, err


def test_fi6_6_applied_at_null_is_refused_by_not_null(
        tmp_path: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    """FI6-6. Open: the citation trigger's last_word branch on applied_at NULL
    (not an input of that branch). Backstop (provenance_corrections DDL, quoted
    from sqlite_master):

        applied_at        TEXT NOT NULL,
    """
    payload = _pc_payload(tmp_path_factory)
    assert payload["admission_tier"] == "last_word"
    payload["applied_at"] = None
    c = _pc_world(tmp_path)
    try:
        assert "applied_at        TEXT NOT NULL," in _table_sql(c, "provenance_corrections")
        err = _raw_error(c, "provenance_corrections", payload)
    finally:
        c.close()
    assert err == "NOT NULL constraint failed: provenance_corrections.applied_at"
