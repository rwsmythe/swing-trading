"""22-I T11 -- daily_management_records: the state-machine twin (RD F-I1 row 10,
S3-F2, and RD's plan-stage FLIP tightening; plan section 1.3).

An UPDATE is admitted iff every I column and the F `linked_trade_event_id`
hold AND the row takes one of four transitions:

    ACTIVE_STAY  active -> active, DATA free (the reflow, daily_management.py:621)
    FLIP         is_superseded 0 -> 1, pointer NULL both sides, DATA frozen (:822)
    WINDOW       superseded, pointer NULL -> value, DATA frozen (:875)
    FROZEN_FK    superseded, pointer unchanged, only pipeline_run_id nulled with
                 its run GONE (a17)

`is_superseded` 1 -> 0 and the self-FK `superseded_by_record_id` value -> NULL
/ other have NO admitting clause. Seeded world (tests/data/_22i_seed.py): row
1 ACTIVE (session 08-10, run 1); row 2 SUPERSEDED by row 3 (session 08-11,
run 2 -- the bare run); row 3 ACTIVE (08-11, higher tier, run 2).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.data._22i_seed import TRADE_ID, TS, migrated, outcome

TWIN = "TRIGGER:trg_dmr_immutable"
PAIR = pytest.mark.parametrize("version", [40, 41])


def _world(tmp_path: Path, version: int):
    return migrated(tmp_path, version, world=True)


def _snap(session: str, precision: str, **kw) -> dict:
    base = dict(
        review_date=session, data_asof_session=session, created_at=TS,
        mfe_mae_precision_level=precision, pipeline_run_id=1, current_price=37.5,
        current_stop=33.72, current_size=5.0, current_avg_cost=36.43,
        open_R_effective=0.3, open_MFE_R_to_date=0.4, open_MAE_R_to_date=0.1,
        intraday_high=38.0, intraday_low=36.0,
        position_capital_utilization_pct=0.1,
        position_capital_denominator_dollars=7500.0,
        position_portfolio_heat_contribution_dollars=13.5,
        maturity_stage="pre_+1.5R", trail_MA_candidate_price=None,
        trail_MA_period_days=None, trail_MA_eligibility_flag=0)
    base.update(kw)
    return base


def _exposed_or(verdict: str, version: int) -> None:
    if version == 40:
        assert verdict == "OK", verdict
    else:
        assert verdict == TWIN, verdict


def _upd(sql: str, rid: int) -> tuple[str, tuple]:
    return (f"UPDATE daily_management_records SET {sql} WHERE management_record_id = ?",
            (rid,))


FLIP_1 = _upd("is_superseded = 1", 1)


# ---------------------------------------------------------------------------
# the production writers, admitted at 41
# ---------------------------------------------------------------------------
def test_active_stay_reflow_upsert_twice_admitted(tmp_path: Path) -> None:
    from swing.data.repos.daily_management import upsert_snapshot

    c = _world(tmp_path, 41)
    try:
        def twice(k):
            a = upsert_snapshot(k, trade_id=TRADE_ID,
                                snapshot_fields=_snap("2026-08-10", "daily_approximate"))
            b = upsert_snapshot(k, trade_id=TRADE_ID, snapshot_fields=_snap(
                "2026-08-10", "daily_approximate", current_price=38.0, pipeline_run_id=2))
            assert a == b == 1
        assert outcome(c, twice) == "OK"
    finally:
        c.close()


def test_tier_upgrade_snapshot_end_to_end_admitted(tmp_path: Path) -> None:
    """Steps 3 (FLIP) -> 4 (successor INSERT) -> 5 (WINDOW), the production
    function, at 41."""
    from swing.data.repos.daily_management import tier_upgrade_snapshot

    c = _world(tmp_path, 41)
    try:
        verdict, seen = outcome(
            c, lambda k: tier_upgrade_snapshot(
                k, trade_id=TRADE_ID, data_asof_session="2026-08-10",
                new_precision_level="intraday_estimated",
                snapshot_fields=_snap("2026-08-10", "intraday_estimated")),
            post=lambda k: k.execute(
                "SELECT is_superseded, superseded_by_record_id IS NOT NULL, current_price "
                "FROM daily_management_records WHERE management_record_id = 1").fetchone())
    finally:
        c.close()
    assert (verdict, seen) == ("OK", (1, 1, 37.0))


# ---------------------------------------------------------------------------
# S3-F2 + RD's FLIP tightening
# ---------------------------------------------------------------------------
@PAIR
def test_the_window_step5_after_the_flip_is_admitted(tmp_path: Path, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        successor = ("INSERT INTO daily_management_records (trade_id, record_type, "
                     "review_date, data_asof_session, created_at, mfe_mae_precision_level, "
                     "is_superseded) VALUES (?, 'daily_snapshot', '2026-08-10', "
                     "'2026-08-10', ?, 'intraday_exact', 0)", (TRADE_ID, TS))
        verdict = outcome(c, *_upd("superseded_by_record_id = "
                                   "(SELECT MAX(management_record_id) FROM "
                                   "daily_management_records)", 1),
                          setup=[FLIP_1, successor])
    finally:
        c.close()
    assert verdict == "OK"


@PAIR
def test_a_data_column_on_a_superseded_row_aborts(tmp_path: Path, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, *_upd("current_stop = 30.0", 2))
    finally:
        c.close()
    _exposed_or(verdict, version)


@PAIR
def test_the_step5_shape_plus_a_data_column_aborts(tmp_path: Path, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, *_upd("superseded_by_record_id = 3, current_stop = 30.0", 1),
                          setup=[FLIP_1])
    finally:
        c.close()
    _exposed_or(verdict, version)


@PAIR
def test_flip_plus_a_data_column_in_one_statement_aborts(tmp_path: Path,
                                                        version: int) -> None:
    """RD's plan-stage tightening: a FLIP that rewrites DATA in the same
    statement would freeze the rewritten value as the predecessor's verbatim
    data. The bare step-3 flip (below) is admitted."""
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, *_upd("is_superseded = 1, current_stop = 30.0", 1))
    finally:
        c.close()
    _exposed_or(verdict, version)


@PAIR
def test_the_bare_step3_flip_is_admitted(tmp_path: Path, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        assert outcome(c, *FLIP_1) == "OK"
    finally:
        c.close()


@PAIR
def test_is_superseded_one_to_zero_aborts(tmp_path: Path, version: int) -> None:
    """Row 2 back to active would collide with row 3 on the active index at
    v40 unless row 3 is also moved; flip row 3 first (a FLIP, admitted), then
    un-supersede row 2."""
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, *_upd("is_superseded = 0, superseded_by_record_id = NULL", 2),
                          setup=[_upd("is_superseded = 1", 3)])
        bare = outcome(c, *_upd("is_superseded = 0", 2),
                       setup=[_upd("is_superseded = 1", 3)])
    finally:
        c.close()
    _exposed_or(verdict, version)
    _exposed_or(bare, version)


@PAIR
@pytest.mark.parametrize("new", ["NULL", "1"])
def test_the_supersede_pointer_value_to_null_or_other_aborts(tmp_path: Path, new: str,
                                                             version: int) -> None:
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, *_upd(f"superseded_by_record_id = {new}", 2))
    finally:
        c.close()
    _exposed_or(verdict, version)


# ---------------------------------------------------------------------------
# FROZEN_FK (a17 on the superseded row) + the ACTIVE row's reflow of the FK
# ---------------------------------------------------------------------------
@PAIR
def test_frozen_fk_run_delete_nulls_a_superseded_rows_run_link(tmp_path: Path,
                                                               version: int) -> None:
    """C4a, DELETABLE-NO-PRODUCTION-DELETER: a PROBE delete of the bare run 2
    ("probe delete, no production deleter"); the SET NULL action reaches the
    superseded row 2 (FROZEN_FK) and the active row 3 (ACTIVE_STAY)."""
    c = _world(tmp_path, version)
    try:
        verdict, seen = outcome(
            c, "DELETE FROM pipeline_runs WHERE id = 2",
            post=lambda k: k.execute(
                "SELECT management_record_id, pipeline_run_id FROM "
                "daily_management_records WHERE management_record_id IN (2, 3) "
                "ORDER BY 1").fetchall())
    finally:
        c.close()
    assert (verdict, seen) == ("OK", [(2, None), (3, None)])


@PAIR
def test_frozen_fk_with_the_run_present_aborts(tmp_path: Path, version: int) -> None:
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, *_upd("pipeline_run_id = NULL", 2))
    finally:
        c.close()
    _exposed_or(verdict, version)


# ---------------------------------------------------------------------------
# the no_replace barrier on both partial UNIQUE keys
# ---------------------------------------------------------------------------
def _dmr_insert(verb: str, session: str, precision: str, superseded: int):
    return (f"{verb} INTO daily_management_records (trade_id, record_type, review_date, "
            "data_asof_session, created_at, mfe_mae_precision_level, is_superseded) "
            "VALUES (?, 'daily_snapshot', ?, ?, ?, ?, ?)",
            (TRADE_ID, session, session, TS, precision, superseded))


@PAIR
@pytest.mark.parametrize("key", ["active_per_session", "precision_per_session"])
@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "INSERT OR IGNORE"])
def test_no_replace_on_both_partial_keys(tmp_path: Path, key: str, verb: str,
                                         version: int) -> None:
    c = _world(tmp_path, version)
    try:
        if key == "active_per_session":  # a second ACTIVE row on session 08-10
            stmt = _dmr_insert(verb, "2026-08-10", "intraday_exact", 0)
        else:  # a superseded row at row 1's own precision on session 08-10
            stmt = _dmr_insert(verb, "2026-08-10", "daily_approximate", 1)
        verdict = outcome(c, *stmt)
    finally:
        c.close()
    if version == 40:
        assert verdict == "OK", verdict
    else:
        assert verdict == "TRIGGER:trg_dmr_no_replace", verdict


@PAIR
def test_a_tier_upgrade_successor_insert_passes(tmp_path: Path, version: int) -> None:
    """After the step-3 FLIP, an INSERT at a different precision on the now
    superseded session is the tier-upgrade successor: admitted at both."""
    c = _world(tmp_path, version)
    try:
        verdict = outcome(c, *_dmr_insert("INSERT", "2026-08-10", "intraday_estimated", 0),
                          setup=[FLIP_1])
    finally:
        c.close()
    assert verdict == "OK"
