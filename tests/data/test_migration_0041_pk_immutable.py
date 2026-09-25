"""22-I Reviewer B B2 -- the PK freezes (CHARC ruling, Branch A; plan AL-11, F-I5).

`UPDATE OR REPLACE` resolves a key conflict by an implicit DELETE of the row
that holds the key. Under `recursive_triggers` OFF (this repo never enables it)
that DELETE fires no `no_delete`, and the `no_replace` barrier is BEFORE INSERT,
so it never sees an UPDATE. Three guarded tables had update guards that were
ALL column-scoped (`UPDATE OF`) or absent -- pattern_exemplars, watchlist_archive
(no twin, AL-11) and latch_view_events (four `UPDATE OF` triggers, none naming
view_event_id) -- so moving a row onto another row's key deleted that row
silently.

An `UPDATE OF <pk>` trigger is not the fix: it is keyed on the column NAME, and
the rowid is reachable as `<pk>`, `rowid`, `oid` and `_rowid_` (case-
insensitive), so `SET rowid = <existing>` never fires it (the B2 fork,
`~/swing-data/review-transcripts/22-i-exec/reviewer-a/b2-fork/`). The ruled
form is a BLANKET `BEFORE UPDATE ... WHEN NOT COALESCE(NEW.<pk> IS OLD.<pk>, 0)`:
it compares the VALUE, so every spelling is refused and a same-value SET is a
true no-op.

Each probe is a (version, verdict) pair on the SAME seeded world: at v40 the
statement is EXPOSED, at v41 `trg_<abbr>_pk_immutable` refuses it; the measured
writers' UPDATEs are admitted at BOTH.

Seeding: pattern_exemplars / watchlist_archive rows 1 come from `seed_world`;
row 2 of each is a raw INSERT (pattern_exemplars row 2 is a `claude_silver` row,
the shape on which every measured writer's UPDATE satisfies the table's CHECKs).
latch_view_events rows 5 and 6 SATISFY the insert-side triggers: row 5 is the
real AMN row on its real A+ fire (`seed_amn_row5`, so
`trg_lve_identity_coherent_insert` admits it) and row 6 is the same fire on a
fresh `view_session_date`, so `trg_lve_no_replace`'s UNIQUE key is new.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests._22b_fixtures import LVE_ROW5, insert_row, seed_amn_row5
from tests.data._22i_guard_spec import LVE_WRITER_COLUMNS, PK_IMMUTABLE_22I
from tests.data._22i_seed import TS, migrated, outcome

PAIR = pytest.mark.parametrize("version", [40, 41])
REPO = Path(__file__).resolve().parents[2]

# table -> (pk, the row that is moved ONTO, the row that moves)
ROWS = {
    "pattern_exemplars": ("id", 1, 2),
    "watchlist_archive": ("id", 1, 2),
    "latch_view_events": ("view_event_id", 5, 6),
}
TABLES = tuple(ROWS)

PEX_SILVER = dict(
    id=2, ticker="OII", timeframe="daily", start_date="2026-07-01",
    end_date="2026-08-07", proposed_pattern_class="vcp", final_decision="confirmed",
    final_pattern_class=None, label_source="claude_silver",
    ai_labeler_version="v1", codex_reviewed=0, codex_agreement=None,
    geometric_score_json=None, labeler_evidence_json='{"src": "claude"}',
    structural_evidence_json="{}", parent_exemplar_id=None, created_at=TS,
    created_by="claude_dispatch")
WLA_2 = dict(
    id=2, ticker="OII", added_date="2026-07-02", removed_date="2026-08-08",
    reason="entered", qualification_count=2, last_data_asof_date="2026-08-07",
    notes=None)


def _world(tmp_path: Path, version: int):
    c = migrated(tmp_path, version, world=True)
    insert_row(c, "pattern_exemplars", PEX_SILVER)
    insert_row(c, "watchlist_archive", WLA_2)
    seed_amn_row5(c)
    insert_row(c, "latch_view_events",
               {**LVE_ROW5, "view_event_id": 6, "view_session_date": "2026-08-04"})
    return c


def _snapshot(c, table: str):
    pk = ROWS[table][0]
    return c.execute(f"SELECT * FROM {table} ORDER BY {pk}").fetchall()


def test_the_three_triggers_are_the_ruled_blanket_form(tmp_path: Path) -> None:
    """Branch A, structurally: a blanket BEFORE UPDATE (no `UPDATE OF` list)
    whose WHEN is the COALESCE-wrapped value comparison of the PK."""
    c = migrated(tmp_path, 41)
    try:
        for table, (trig, pk) in PK_IMMUTABLE_22I.items():
            tbl, sql = c.execute("SELECT tbl_name, sql FROM sqlite_master "
                                 "WHERE type = 'trigger' AND name = ?",
                                 (trig,)).fetchone()
            flat = " ".join(sql.split())
            assert tbl == table
            assert f"BEFORE UPDATE ON {table}" in flat, trig
            assert " UPDATE OF " not in flat.upper(), trig
            assert f"WHEN NOT COALESCE(NEW.{pk} IS OLD.{pk}, 0)" in flat, trig
            for word in ("rowid", "oid", "_rowid_", "recursive_triggers",
                         "UPDATE OR REPLACE"):
                assert word in flat, (trig, word)  # the message names the mechanism
    finally:
        c.close()


@PAIR
@pytest.mark.parametrize("spelling", ["pk", "rowid", "oid", "_rowid_", "ROWID"])
@pytest.mark.parametrize("table", TABLES)
def test_update_or_replace_onto_an_existing_pk(tmp_path: Path, table: str,
                                               spelling: str, version: int) -> None:
    pk, onto, mover = ROWS[table]
    key = pk if spelling == "pk" else spelling
    c = _world(tmp_path, version)
    try:
        before = _snapshot(c, table)
        verdict, after = outcome(
            c, f"UPDATE OR REPLACE {table} SET {key} = ? WHERE {pk} = ?",
            (onto, mover), post=lambda cc: _snapshot(cc, table))
        unchanged = _snapshot(c, table)
    finally:
        c.close()
    if version == 40:
        # the exposure: row `onto` is DELETED silently and `mover` takes its key
        assert verdict == "OK", verdict
        assert len(after) == len(before) - 1
        survivor = next(r for r in after if r[0] == onto)
        moved_from = next(r for r in before if r[0] == mover)
        assert survivor[1:] == moved_from[1:]
    else:
        assert verdict == f"TRIGGER:{PK_IMMUTABLE_22I[table][0]}", verdict
        assert unchanged == before


@PAIR
@pytest.mark.parametrize("spelling", ["pk", "rowid", "oid", "_rowid_"])
@pytest.mark.parametrize("table", TABLES)
def test_plain_set_pk_to_a_fresh_value(tmp_path: Path, table: str, spelling: str,
                                       version: int) -> None:
    pk, _onto, mover = ROWS[table]
    key = pk if spelling == "pk" else spelling
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, f"UPDATE {table} SET {key} = 987654 WHERE {pk} = ?",
                          (mover,))
    finally:
        c.close()
    if version == 40:
        assert verdict == "OK", verdict
    else:
        assert verdict == f"TRIGGER:{PK_IMMUTABLE_22I[table][0]}", verdict


@PAIR
@pytest.mark.parametrize("table", TABLES)
def test_a_same_value_set_of_the_pk_is_a_true_no_op(tmp_path: Path, table: str,
                                                    version: int) -> None:
    """Admitted at both (the value comparison sees no change), and nothing moves."""
    pk, _onto, mover = ROWS[table]
    c = _world(tmp_path, version)
    try:
        before = _snapshot(c, table)
        verdict, after = outcome(c, f"UPDATE OR REPLACE {table} SET {pk} = {pk} "
                                    f"WHERE {pk} = ?", (mover,),
                                 post=lambda cc: _snapshot(cc, table))
    finally:
        c.close()
    assert verdict == "OK", verdict
    assert after == before


# ---------------------------------------------------------------------------
# the measured writers (ledger + plan AL-11), admitted at BOTH versions
# ---------------------------------------------------------------------------
def _w_watchlist(c) -> None:
    from swing.data.repos.watchlist import update_archive_removed_date
    update_archive_removed_date(c, archive_id=2, removed_date="2026-08-09")


def _w_pex_repo(c) -> None:
    from swing.data.repos.pattern_exemplars import (
        update_exemplar_labeler_evidence_json,
    )
    update_exemplar_labeler_evidence_json(c, 2, '{"src": "backfill"}')


def _w_record_view(c) -> None:
    from swing.data.repos.latch_view_events import record_view
    from swing.latches.identity import LatchIdentity
    from tests._22b_fixtures import (
        AMN_CANDIDATE_ID,
        AMN_PIPELINE_ID,
        AMN_RUN_ID,
    )
    rid = record_view(
        c, identity=LatchIdentity(
            candidate_id=AMN_CANDIDATE_ID, evaluation_run_id=AMN_RUN_ID,
            ticker="AMN", detection_date="2026-08-03",
            pipeline_run_id=AMN_PIPELINE_ID),
        view_session_date="2026-08-03", viewed_ts="2026-08-03T09:00:00",
        latch_state="order_resting", surface="latch_panel", actionable=1)
    assert rid == 5  # the MERGE path (row 5 exists for that session)


# The inline SQL writers, copied from their source; `fragment` is asserted to
# be present in the cited file so a moved or edited writer is noticed.
_SQL_WRITERS = {
    "labeling.py:526": (
        "swing/patterns/labeling.py",
        '"UPDATE pattern_exemplars SET codex_reviewed = 1, "',
        "UPDATE pattern_exemplars SET codex_reviewed = 1, codex_agreement = ? "
        "WHERE id = ?", (0, 2)),
    "routes/patterns.py:290": (
        "swing/web/routes/patterns.py",
        '"labeler_evidence_json = ?, "',
        "UPDATE pattern_exemplars SET label_source = 'curated_gold', "
        "final_decision = 'confirmed', gold_validated_at = ?, "
        "labeler_evidence_json = ?, proposed_pattern_class = ?, "
        "final_pattern_class = NULL WHERE id = ?",
        (TS, '{"gold_promotion_at": "x"}', "flat_base", 2)),
    "routes/patterns.py:308": (
        "swing/web/routes/patterns.py",
        '"final_decision = \'confirmed\', gold_validated_at = ? "',
        "UPDATE pattern_exemplars SET label_source = 'curated_gold', "
        "final_decision = 'confirmed', gold_validated_at = ? WHERE id = ?",
        (TS, 2)),
    "routes/patterns.py:329": (
        "swing/web/routes/patterns.py",
        '"UPDATE pattern_exemplars SET final_decision = \'rejected\', "',
        "UPDATE pattern_exemplars SET final_decision = 'rejected', "
        "final_pattern_class = NULL WHERE id = ?", (2,)),
    "routes/patterns.py:337": (
        "swing/web/routes/patterns.py",
        '"UPDATE pattern_exemplars SET final_decision = \'watch\', "',
        "UPDATE pattern_exemplars SET final_decision = 'watch', "
        "final_pattern_class = NULL WHERE id = ?", (2,)),
    "routes/patterns.py:357": (
        "swing/web/routes/patterns.py",
        '"UPDATE pattern_exemplars SET final_decision = \'relabeled\', "',
        "UPDATE pattern_exemplars SET final_decision = 'relabeled', "
        "final_pattern_class = ? WHERE id = ?", ("flat_base", 2)),
}

# column -> (SET clause, params). actionable_at_last_view = 1 needs
# actionable_ever_viewed = 1 alongside it (the table's CHECK couples them, and
# record_view's MAX keeps them coupled).
_LVE_ADMITTED = {
    "last_viewed_ts": ("last_viewed_ts = ?", ("2026-08-03T10:00:00",)),
    "latch_state_at_last_view": ("latch_state_at_last_view = ?", ("order_resting",)),
    "actionable_at_last_view": (
        "actionable_at_last_view = ?, actionable_ever_viewed = ?", (1, 1)),
    "view_count": ("view_count = ?", (9,)),
    "actionable_ever_viewed": ("actionable_ever_viewed = ?", (1,)),  # 0 -> 1 only
}


def test_the_lve_admitted_roster_is_the_writer_set() -> None:
    assert set(_LVE_ADMITTED) == set(LVE_WRITER_COLUMNS)


def _writer_cases():
    yield pytest.param("watchlist_archive", _w_watchlist, id="watchlist.py:124")
    yield pytest.param("pattern_exemplars", _w_pex_repo, id="pattern_exemplars.py:188")
    for tag, (_f, _frag, sql, params) in _SQL_WRITERS.items():
        yield pytest.param("pattern_exemplars", (sql, params), id=tag)
    yield pytest.param("latch_view_events", _w_record_view,
                       id="latch_view_events.py:157-record_view")
    for col, (clause, params) in _LVE_ADMITTED.items():
        yield pytest.param(
            "latch_view_events",
            (f"UPDATE latch_view_events SET {clause} WHERE view_event_id = 5", params),
            id=f"lve-admitted-{col}")


@PAIR
@pytest.mark.parametrize("table,writer", list(_writer_cases()))
def test_measured_writers_are_admitted_at_both(tmp_path: Path, table: str, writer,
                                               version: int) -> None:
    c = _world(tmp_path, version)
    try:
        before = _snapshot(c, table)
        if callable(writer):
            verdict, after = outcome(c, writer, post=lambda cc: _snapshot(cc, table))
        else:
            sql, params = writer
            verdict, after = outcome(c, sql, params,
                                     post=lambda cc: _snapshot(cc, table))
    finally:
        c.close()
    assert verdict == "OK", verdict
    assert after != before  # the writer actually moved something
    assert [r[0] for r in after] == [r[0] for r in before]  # and no key moved


@pytest.mark.parametrize("tag", list(_SQL_WRITERS))
def test_the_inline_writer_shapes_are_still_in_their_source(tag: str) -> None:
    path, fragment, _sql, _params = _SQL_WRITERS[tag]
    assert fragment in (REPO / path).read_text(encoding="utf-8"), tag
