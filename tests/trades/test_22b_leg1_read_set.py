"""Arc 22-B Task 11 -- leg 1's READ SET equals its BELT SET (R0.K-RULING.1).

RD's class rule: every ``latch_view_events`` column leg 1 READS is a column
the schema GUARDS. Both sides are DERIVED, never listed from memory:

* the READ SET by SQLite's authorizer (``SQLITE_READ`` on
  ``latch_view_events``, any source -- the service's own statements AND the
  compile of every attestation ``BEFORE INSERT`` trigger, ``trg_eia_tier2``
  included) while the real service runs, minus the named
  ``LEG1_RECORDED_NOT_DECIDED`` columns, each with its reason;
* the BELT SET by parsing the ``BEFORE UPDATE OF <columns>`` lists out of the
  STORED ``sqlite_master.sql`` of the four named belts.

b22_201 makes the exclusion a CHECKED claim: a raw move of either
recorded-not-decided column leaves every verdict field unchanged.

FORWARD RULE (R0.I): every image pins ``target_version=40``.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import swing.trades.entry_intent_assignment as svc
from swing.data.db import open_connection
from tests._22b_fixtures import envelope, record_envelope_readings
from tests.trades.test_22b_assignment_service import CITE, REASON, _speaking, _world

LVE = "latch_view_events"
LVE_EVIDENCE_BELTS = (
    "trg_lve_actionable_ever_viewed_monotonic",
    "trg_lve_no_delete",
    "trg_lve_no_replace",
    "trg_lve_view_window_immutable",
)
# The belts that guard the ROW SET (which rows exist), not a column.
ROW_SET_BELTS = ("trg_lve_no_delete", "trg_lve_no_replace")
LEG1_RECORDED_NOT_DECIDED = {
    "view_event_id": (
        "the evidence id written into leg_evidence_json; no leg-1 branch "
        "decides on it (b22_201 proves by execution that moving it moves no "
        "verdict; drift (iv) names a post-assignment change)"),
    "view_session_date": (
        "recorded, and bound to live by trg_eia_tier2 at insert; R0.H says "
        "never view_session_date and R0.K branch (a) leaves it out on purpose "
        "(b22_201 proves by execution that moving it moves no verdict)"),
}
EXPECTED = {"actionable_ever_viewed", "first_viewed_ts", "ticker"}
_UPDATE_OF = re.compile(r"\bBEFORE\s+UPDATE\s+OF\s+(.+?)\s+ON\s+latch_view_events\b",
                        re.IGNORECASE | re.DOTALL)
_OFFER_DAY = "2026-08-06"


def _telemetry_admit_world(tmp_path: Path, name: str):
    """b22_90's fixture: a speaking 0 row before the 08-06 placement."""
    c, cfg, path = _world(tmp_path, name, env=envelope(entry_date=_OFFER_DAY))
    _speaking(c, first="2026-08-05T09:00:00", ever=0)
    return c, cfg, path


def _offered_refuse_world(tmp_path: Path, name: str):
    """b22_84's fixture: the same speaking row flipped to actionable."""
    c, cfg, path = _telemetry_admit_world(tmp_path, name)
    c.execute("UPDATE latch_view_events SET actionable_ever_viewed = 1, "
              "actionable_at_last_view = 1 WHERE view_event_id = 6")
    c.commit()
    return c, cfg, path


def _read_set(tmp_path: Path, name: str, *, drop: str | None = None) -> set[str]:
    """Every ``latch_view_events`` column the leg-1 code path READS, by the
    authorizer, on a FRESH connection (no cached statement escapes it)."""
    reads: set[str] = set()

    def authorizer(action, arg1, arg2, _db, _source):
        if action == sqlite3.SQLITE_READ and arg1 == LVE:
            reads.add(arg2)
        return sqlite3.SQLITE_OK

    admit_c, cfg, admit_path = _telemetry_admit_world(tmp_path, f"{name}_admit")
    refuse_c, _, refuse_path = _offered_refuse_world(tmp_path, f"{name}_refuse")
    for c in (admit_c, refuse_c):
        if drop is not None:
            c.execute(f"DROP TRIGGER {drop}")
        record_envelope_readings(c)
        c.commit()
        c.close()

    fresh = open_connection(admit_path)
    try:
        fresh.set_authorizer(authorizer)
        admitted = svc.assign(fresh, cfg, trade_id=20, cite=list(CITE),
                              reason=REASON, applied_by="operator", dry_run=False)
    finally:
        fresh.close()
    assert admitted.admitted and admitted.admitted_leg == "telemetry", admitted.message
    fresh = open_connection(refuse_path)
    try:
        fresh.set_authorizer(authorizer)
        refused = svc.preflight(fresh, cfg, trade_id=20, cite=list(CITE), reason=REASON)
    finally:
        fresh.close()
    assert (refused.admitted, refused.refusal_code) == (False, "instrument_offered")
    assert set(LEG1_RECORDED_NOT_DECIDED) <= reads, reads
    return reads - set(LEG1_RECORDED_NOT_DECIDED)


def _belt_set(path: Path, *, require_all: bool) -> set[str]:
    """The union of the ``BEFORE UPDATE OF`` column lists of the named belts,
    parsed from the STORED schema."""
    c = sqlite3.connect(path)
    try:
        stored = dict(c.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
            f"AND tbl_name = '{LVE}'").fetchall())
    finally:
        c.close()
    if require_all:
        assert set(LVE_EVIDENCE_BELTS) <= set(stored), sorted(stored)
    columns: set[str] = set()
    for name in LVE_EVIDENCE_BELTS:
        sql = stored.get(name)
        if sql is None:
            continue
        m = _UPDATE_OF.search(sql)
        if m is not None:
            columns |= {col.strip() for col in m.group(1).split(",")}
    return columns


def _db_of(tmp_path: Path, name: str) -> Path:
    return tmp_path / f"{name}_admit" / "swing.db"


def test_leg1_read_set_equals_the_belt_set_b22_200(tmp_path: Path) -> None:
    read = _read_set(tmp_path, "real")
    belts = _belt_set(_db_of(tmp_path, "real"), require_all=True)
    assert read == belts == EXPECTED, (read, belts)
    c = sqlite3.connect(_db_of(tmp_path, "real"))
    try:
        names = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' "
            f"AND tbl_name = '{LVE}'")}
    finally:
        c.close()
    assert set(ROW_SET_BELTS) <= names


def test_leg1_gap_twin_with_the_window_belt_dropped_b22_200(tmp_path: Path) -> None:
    """The discriminating twin (the R0.H three-belt state): with
    ``trg_lve_view_window_immutable`` DROPPED the same derivation reports the
    gap {first_viewed_ts, ticker} -- exactly what the fourth belt closes."""
    drop = "trg_lve_view_window_immutable"
    read = _read_set(tmp_path, "twin", drop=drop)
    belts = _belt_set(_db_of(tmp_path, "twin"), require_all=False)
    assert belts == {"actionable_ever_viewed"}
    assert read == EXPECTED
    assert read - belts == {"first_viewed_ts", "ticker"}


def _verdict(c: sqlite3.Connection, cfg) -> tuple:
    r = svc.preflight(c, cfg, trade_id=20, cite=list(CITE), reason=REASON)
    return (r.admitted, r.refusal_code, r.tier, r.admitted_leg)


def test_recorded_not_decided_columns_cannot_move_a_verdict_b22_201(
        tmp_path: Path) -> None:
    moves = (
        # a free session date, clear of the UNIQUE (candidate_id,
        # view_session_date, surface): row 5 holds 2026-08-03
        "UPDATE latch_view_events SET view_session_date = '2026-08-04' "
        "WHERE view_event_id = 6",
        "UPDATE latch_view_events SET view_event_id = 60 WHERE view_event_id = 6",
    )
    expected = {
        "admit": (True, None, "contemporaneous_record", "telemetry"),
        "refuse": (False, "instrument_offered", None, None),
    }
    for label, build in (("admit", _telemetry_admit_world),
                         ("refuse", _offered_refuse_world)):
        c, cfg, _ = build(tmp_path, f"b201_{label}")
        try:
            names = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                f"AND tbl_name = '{LVE}'")}
            assert set(LVE_EVIDENCE_BELTS) <= names
            record_envelope_readings(c)
            c.commit()
            before = _verdict(c, cfg)
            assert before == expected[label]
            for sql in moves:
                assert c.execute(sql).rowcount == 1
                c.commit()
                assert _verdict(c, cfg) == before, (label, sql)
        finally:
            c.close()


def test_a_decided_column_does_move_the_verdict_b22_201(tmp_path: Path) -> None:
    """The counterfactual that makes b22_201's comparison non-vacuous: the
    same verdict tuple DOES move when a DECIDED column moves. With the window
    belt dropped (it would refuse the UPDATE), the speaking row's first view
    is pushed past the placement: the telemetry admission becomes the leg-2
    refusal."""
    c, cfg, _ = _telemetry_admit_world(tmp_path, "b201_decided")
    try:
        record_envelope_readings(c)
        c.commit()
        assert _verdict(c, cfg) == (True, None, "contemporaneous_record", "telemetry")
        c.execute("DROP TRIGGER trg_lve_view_window_immutable")
        c.execute("UPDATE latch_view_events SET first_viewed_ts = "
                  "'2026-08-07T09:00:00', last_viewed_ts = '2026-08-07T09:00:00' "
                  "WHERE view_event_id = 6")
        c.commit()
        assert _verdict(c, cfg) == (False, "instrument_existed", None, None)
    finally:
        c.close()
