"""22-I T5 -- F-I5: `trg_lve_first_view_immutable` (RD (a) the IF; CHARC the
SHAPE, binding: plan section 1.4).

`BEFORE UPDATE OF candidate_id, evaluation_run_id, detection_date, surface,
view_session_date, latch_state_at_first_view, actionable_at_first_view` -- the
seven first-view columns the sole writer's UPDATE (`record_view`,
repos/latch_view_events.py:157-167) never names. No WHEN (an UPDATE OF trigger
has no NULL hazard).

Per-column discriminator, as a (version, verdict) pair. The ruling's incidental
fact "each named column's UPDATE is OK on v40" holds as measured for
view_session_date, latch_state_at_first_view and actionable_at_first_view
(1 -> 0). It does NOT hold for a LONE change of the three identity columns
(candidate_id, evaluation_run_id, detection_date): v40's own
`trg_lve_identity_coherent_update` refuses an incoherent identity, so their
v40 EXPOSURE is the COHERENT MOVE -- all three re-pointed together at another
A+ fire for the same ticker, which v40 admits (the first-view row moved to a
different fire) and v41 refuses. `surface` has no second admissible value
(CHECK (surface IN ('latch_panel'))), so its v40 verdict is the engine CHECK
and its v41 verdict is the trigger (a BEFORE trigger runs before the CHECK).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests._22b_fixtures import (
    AMN_CANDIDATE_ID,
    AMN_PIPELINE_ID,
    AMN_RUN_ID,
    seed_amn_row5,
    seed_fire,
)
from tests.data._22i_guard_spec import (
    LVE_FIRST_VIEW_COLUMNS,
    LVE_OTHER_COLUMNS,
    LVE_WRITER_COLUMNS,
)
from tests.data._22i_seed import is_engine_refusal, migrated, outcome

TWIN = "TRIGGER:trg_lve_first_view_immutable"
PAIR = pytest.mark.parametrize("version", [40, 41])
# A second A+ fire for AMN on another session: the coherent move's target.
MOVE_RUN, MOVE_PIPELINE, MOVE_CANDIDATE, MOVE_SESSION = 132, 146, 11927, "2026-08-04"


def _world(tmp_path: Path, version: int):
    c = migrated(tmp_path, version)
    seed_amn_row5(c, actionable_at_first_view=1, actionable_at_last_view=1,
                  actionable_ever_viewed=1)
    seed_fire(c, run_id=MOVE_RUN, pipeline_id=MOVE_PIPELINE,
              candidate_id=MOVE_CANDIDATE, ticker="AMN", action_session=MOVE_SESSION,
              data_asof="2026-08-01")
    return c


_IDENTITY_MOVE = (
    "candidate_id = ?, evaluation_run_id = ?, detection_date = ?, pipeline_run_id = ?",
    (MOVE_CANDIDATE, MOVE_RUN, MOVE_SESSION, MOVE_PIPELINE))
_SET = {
    "candidate_id": _IDENTITY_MOVE,
    "evaluation_run_id": _IDENTITY_MOVE,
    "detection_date": _IDENTITY_MOVE,
    "surface": ("surface = ?", ("dashboard",)),
    "view_session_date": ("view_session_date = ?", ("2026-08-05",)),
    "latch_state_at_first_view": ("latch_state_at_first_view = ?", ("invalidated",)),
    "actionable_at_first_view": ("actionable_at_first_view = ?", (0,)),
}


def test_the_roster_covers_the_seven_ruled_columns() -> None:
    assert set(_SET) == set(LVE_FIRST_VIEW_COLUMNS)


@PAIR
@pytest.mark.parametrize("col", LVE_FIRST_VIEW_COLUMNS)
def test_first_view_column_update(tmp_path: Path, col: str, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        clause, params = _SET[col]
        verdict = outcome(c, f"UPDATE latch_view_events SET {clause} "
                             "WHERE view_event_id = 5", params)
    finally:
        c.close()
    if version == 40:
        if col == "surface":
            assert verdict == "CONSTRAINT:CHECK"
        else:
            assert verdict == "OK", verdict  # the exposure
    else:
        assert verdict == TWIN, verdict


@PAIR
def test_the_identity_triple_alone_is_already_refused_at_v40(tmp_path: Path,
                                                             version: int) -> None:
    """The fact the coherent-move encoding rests on, pinned: a LONE identity
    change is v40's identity trigger's to refuse, at both versions."""
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, "UPDATE latch_view_events SET candidate_id = ? "
                             "WHERE view_event_id = 5", (MOVE_CANDIDATE,))
    finally:
        c.close()
    assert verdict.startswith("TRIGGER:"), verdict
    assert not is_engine_refusal(verdict)


def test_record_view_merge_unchanged(tmp_path: Path) -> None:
    """At v41 the sole writer's merge UPDATE moves the five writer columns and
    none of the seven."""
    from swing.data.repos.latch_view_events import record_view
    from swing.latches.identity import LatchIdentity

    c = _world(tmp_path, 41)
    try:
        before = c.execute("SELECT * FROM latch_view_events WHERE view_event_id = 5"
                           ).fetchone()
        names = [d[1] for d in c.execute("PRAGMA table_info(latch_view_events)")]
        rid = record_view(
            c, identity=LatchIdentity(
                candidate_id=AMN_CANDIDATE_ID, evaluation_run_id=AMN_RUN_ID,
                ticker="AMN", detection_date="2026-08-03",
                pipeline_run_id=AMN_PIPELINE_ID),
            view_session_date="2026-08-03", viewed_ts="2026-08-03T09:00:00",
            latch_state="order_resting", surface="latch_panel", actionable=0)
        after = c.execute("SELECT * FROM latch_view_events WHERE view_event_id = 5"
                          ).fetchone()
    finally:
        c.close()
    assert rid == 5
    moved = {n for n, b, a in zip(names, before, after, strict=True) if b != a}
    assert moved == {"last_viewed_ts", "latch_state_at_last_view",
                     "actionable_at_last_view", "view_count"}
    assert not moved & set(LVE_FIRST_VIEW_COLUMNS)


def test_lve_column_closure(tmp_path: Path) -> None:
    c = migrated(tmp_path, 41)
    try:
        cols = [r[1] for r in c.execute("PRAGMA table_info(latch_view_events)")]
    finally:
        c.close()
    parts = (LVE_FIRST_VIEW_COLUMNS, LVE_WRITER_COLUMNS, LVE_OTHER_COLUMNS)
    union = [x for p in parts for x in p]
    assert len(union) == len(set(union))  # disjoint
    assert sorted(union) == sorted(cols)
