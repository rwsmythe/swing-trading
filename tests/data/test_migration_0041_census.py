"""22-I Reviewer B B2 -- THE KEY-FREEZE CENSUS (CHARC ruling, Branch A, condition (f)).

The class B2 found: `UPDATE OR REPLACE` that moves a row onto another row's key
deletes the holder through an implicit DELETE that no `no_delete` sees
(`recursive_triggers` OFF) and that no `no_replace` sees (it is BEFORE INSERT).
The only barrier on that path is a BEFORE UPDATE trigger that refuses the key
move, and the key of every guarded table is its rowid, reachable under four
names (`<pk>`, `rowid`, `oid`, `_rowid_`). An `UPDATE OF` list is keyed on
column NAMES, so it cannot freeze the rowid; only a BLANKET BEFORE UPDATE can.

Two halves, over EVERY table carrying a `no_replace` barrier (27 at v41):

(f1) MECHANICAL, read from `sqlite_master`: at least one BEFORE UPDATE trigger
     on the table has NO `UPDATE OF` list. Its LIMIT: blanket presence does not
     prove the trigger's predicate freezes the rowid. A blanket trigger with a
     WHEN admits whatever its WHEN admits; the three whose WHEN admits a named
     transition were read by hand and none admits a key move:
       - provenance_corrections (F-I2, `trg_provenance_corrections_append_only_update`):
         admits only the FK-driven nulling of entry_fill_id or
         risk_policy_id_at_correction with the parent row gone, and its body
         requires `NEW.provenance_correction_id = OLD.provenance_correction_id`
         (0041 section F-I2);
       - pattern_detection_events (a17, `trg_pde_no_update`): admits only
         chart_render_id / pipeline_run_id -> NULL with the parent gone; every
         other column, detection_id included, must be `IS OLD`;
       - risk_policy (`trg_rp_immutable`): admits is_active 1 -> 0 and the
         write-once NULL -> value of effective_to / superseded_by_policy_id;
         `NEW.policy_id IS OLD.policy_id` is required.
     (f2) is what PROVES the freeze, per table.
(f2) BY EXECUTION: every table gets a seeded row, then `UPDATE <t> SET rowid =
     <fresh>` must be refused by a trigger. A BEFORE trigger fires before any
     conflict resolution, so a refused fresh move is a refused conflicting move.

Seeding, per table (no table is left unseeded, so there is no declared
limitation here):
  - the 21 tables `seed_world` plants (raw INSERTs, every insert-side trigger
    SATISFIED -- the 0041 test world);
  - entry_intent_attestations, fill_envelope_identity, latch_view_events: trade
    20 attested through the PRODUCTION writer `assign` (`attest_trade20`), which
    also records the envelope reading and plants the AMN latch row 5 -- every
    insert-side trigger SATISFIED;
  - latch_order_intents, latch_order_mandate_links: an A+ fire, a place intent
    and a broker acceptance (`_latch_link_fixtures_22a`); the link is MINTED by
    `trg_latch_link_mint_on_acceptance` -- insert-side triggers SATISFIED;
  - provenance_corrections: trade 25's world corrected by the PRODUCTION
    service `correct_cohort_provenance` (the 22-A2 last_word world) -- the
    citation triggers SATISFIED.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from tests.data._22i_guard_spec import PK_IMMUTABLE_22I
from tests.data._22i_seed import migrated, open_plain, outcome

NO_REPLACE_TABLES = (
    "account_equity_snapshots", "candidate_criteria", "candidates",
    "daily_management_records", "entry_intent_attestations", "evaluation_runs",
    "fill_envelope_identity", "finviz_api_calls", "hypothesis_registry",
    "hypothesis_status_history", "latch_order_intents",
    "latch_order_mandate_links", "latch_view_events", "pattern_detection_events",
    "pattern_evaluations", "pattern_exemplars", "pattern_forward_observations",
    "provenance_corrections", "reconciliation_corrections",
    "reconciliation_discrepancies", "reconciliation_runs", "review_log",
    "risk_policy", "schwab_api_calls", "trade_events", "watchlist_archive",
    "yfinance_calls",
)
ATTEST_WORLD = ("entry_intent_attestations", "fill_envelope_identity",
                "latch_view_events")
LATCH_WORLD = ("latch_order_intents", "latch_order_mandate_links")
PC_WORLD = ("provenance_corrections",)
SEED_WORLD = tuple(t for t in NO_REPLACE_TABLES
                   if t not in ATTEST_WORLD + LATCH_WORLD + PC_WORLD)

_UPDATE_HEAD = re.compile(r"\bBEFORE\s+UPDATE\b(\s+OF\b)?", re.I)


def _triggers(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    return conn.execute("SELECT name, tbl_name, sql FROM sqlite_master "
                        "WHERE type = 'trigger'").fetchall()


def no_replace_tables(rows) -> set[str]:
    return {t for n, t, _s in rows if n.endswith("_no_replace")}


def blanket_update_triggers(rows) -> dict[str, set[str]]:
    """table -> the BEFORE UPDATE triggers on it with NO `UPDATE OF` list."""
    out: dict[str, set[str]] = {}
    for name, table, sql in rows:
        head = sql.split("BEGIN", 1)[0]
        m = _UPDATE_HEAD.search(head)
        if m and m.group(1) is None:
            out.setdefault(table, set()).add(name)
    return out


def census_gaps(rows) -> set[str]:
    """(f1): the no_replace tables with NO blanket BEFORE UPDATE trigger."""
    blanket = blanket_update_triggers(rows)
    return {t for t in no_replace_tables(rows) if not blanket.get(t)}


@pytest.fixture(scope="module")
def v41_triggers(tmp_path_factory) -> list[tuple[str, str, str]]:
    c = migrated(tmp_path_factory.mktemp("census"), 41)
    try:
        return _triggers(c)
    finally:
        c.close()


def test_the_roster_is_every_no_replace_table(v41_triggers) -> None:
    assert no_replace_tables(v41_triggers) == set(NO_REPLACE_TABLES)
    assert len(NO_REPLACE_TABLES) == 27


def test_f1_every_no_replace_table_has_a_blanket_update_guard(v41_triggers) -> None:
    assert census_gaps(v41_triggers) == set()


@pytest.mark.parametrize("table", list(PK_IMMUTABLE_22I))
def test_f1_goes_red_when_a_pk_freeze_is_missing(v41_triggers, table: str) -> None:
    """The census's own negative control: the same rows with ONE of the three
    B2 triggers removed report exactly that table. (No DB is mutated -- the
    census is a pure function of the sqlite_master rows.)"""
    trig = PK_IMMUTABLE_22I[table][0]
    rows = [r for r in v41_triggers if r[0] != trig]
    assert len(rows) == len(v41_triggers) - 1
    assert census_gaps(rows) == {table}


def test_f1_an_update_of_form_does_not_count(v41_triggers) -> None:
    """A trigger rewritten in the `UPDATE OF <pk>` form is not blanket."""
    trig, pk = PK_IMMUTABLE_22I["watchlist_archive"]
    rows = [(n, t, s if n != trig else
             f"CREATE TRIGGER {trig} BEFORE UPDATE OF {pk} ON {t} "
             "BEGIN SELECT RAISE(ABORT, 'x'); END")
            for n, t, s in v41_triggers]
    assert census_gaps(rows) == {"watchlist_archive"}


# ---------------------------------------------------------------------------
# (f2) by execution
# ---------------------------------------------------------------------------
def _seed_world_db(tmp_path: Path) -> sqlite3.Connection:
    return migrated(tmp_path, 41, world=True)


def _attest_world_db(tmp_path: Path) -> sqlite3.Connection:
    from tests._22b_fixtures import attest_trade20

    migrated(tmp_path, 41, name="attest.db").close()
    attest_trade20(tmp_path / "attest.db")
    return open_plain(tmp_path / "attest.db")


def _latch_world_db(tmp_path: Path) -> sqlite3.Connection:
    from tests._latch_link_fixtures_22a import accept_order, seed_fire

    c = migrated(tmp_path, 41, name="latch.db")
    accept_order(c, seed_fire(c))
    return c


def _pc_world_db(tmp_path: Path) -> sqlite3.Connection:
    from swing.trades import cohort_provenance_correction as cpc
    from tests._tier2_world_22a2 import (
        T25_APPLIED_AT,
        T25_CANDIDATE_ID,
        T25_REC_ID,
        T25_TRADE_ID,
        build_last_word_world,
    )
    c = build_last_word_world(tmp_path, "pc")
    original = cpc._APPLIED_AT_CLOCK
    cpc._APPLIED_AT_CLOCK = lambda: T25_APPLIED_AT
    try:
        cpc.correct_cohort_provenance(
            c, trade_id=T25_TRADE_ID, cited_candidate_id=T25_CANDIDATE_ID,
            cited_recommendation_id=T25_REC_ID, reason="22-I key-freeze census")
    finally:
        cpc._APPLIED_AT_CLOCK = original
        c.close()
    return open_plain(tmp_path / "pc" / "swing.db")


def _builder(table: str):
    if table in ATTEST_WORLD:
        return _attest_world_db
    if table in LATCH_WORLD:
        return _latch_world_db
    if table in PC_WORLD:
        return _pc_world_db
    return _seed_world_db


def test_f2_the_worlds_partition_the_roster() -> None:
    parts = (SEED_WORLD, ATTEST_WORLD, LATCH_WORLD, PC_WORLD)
    flat = [t for p in parts for t in p]
    assert sorted(flat) == sorted(NO_REPLACE_TABLES)
    assert len(SEED_WORLD) == 21


@pytest.mark.parametrize("table", NO_REPLACE_TABLES)
def test_f2_a_rowid_move_is_refused_by_a_blanket_trigger(tmp_path: Path,
                                                        table: str) -> None:
    c = _builder(table)(tmp_path)
    try:
        assert int(c.execute("SELECT version FROM schema_version").fetchone()[0]) == 41
        rowid = c.execute(f"SELECT min(rowid) FROM {table}").fetchone()[0]
        assert rowid is not None, f"{table}: the world seeded no row"
        fresh = c.execute(f"SELECT max(rowid) + 1000 FROM {table}").fetchone()[0]
        verdict = outcome(c, f"UPDATE {table} SET rowid = ? WHERE rowid = ?",
                          (fresh, rowid))
        blanket = blanket_update_triggers(_triggers(c)).get(table, set())
    finally:
        c.close()
    assert verdict.startswith("TRIGGER:"), (table, verdict)
    assert set(verdict[len("TRIGGER:"):].split("|")) & blanket, (table, verdict)
