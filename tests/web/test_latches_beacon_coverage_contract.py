"""ITEM 5 -- the beacon's payload contract is NAMED, and a SHORTFALL between
what was RENDERED and what was REPORTED is DETECTABLE (RD + CHARC, 2026-07-30).

RD'S BINDING REQUIREMENT, and all he asserts: **silent under-reporting must not
be possible.** Under-reporting views pushes latches toward `away`, inflating the
number that would justify stage-3 auto-place. Whatever the contract becomes, the
difference between RENDERED and REPORTED must be DETECTABLE rather than assumed
equal.

CHARC'S ENGINEERING INPUT: the accepted shape belongs in ONE named contract
consumed by BOTH the emitter and the reader -- the same argument as item 6. A
payload contract enforced by convention at two ends is the same drift hazard in
a different costume.

THE DETECTION IS SERVER-SIDE AND DOES NOT TRUST THE PAYLOAD: the handler already
re-derives the live set as of the anchor, so it compares the two lists against
ITS OWN re-derivation rather than against a count the client also supplies. A
client-supplied total would be tautological -- the emitter builds all three from
one source, so it could only ever agree with itself.

WHY A SHORTFALL REFUSES RATHER THAN INGESTING WHAT IT GOT: a partial write is
the flattering direction. The omitted latches keep no view evidence and are
classified `away_unseen` -- an away rate manufactured from a truncated
instrument. A refusal instead leaves the whole session dark, which
`assess_telemetry_health` reports as unhealthy and the classifier WITHHOLDS on.
Loud and unmeasured beats quiet and flattering.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.latches.constants import (
    BEACON_FIELD_ACTIONABLE,
    BEACON_FIELD_SESSION,
    BEACON_FIELD_WITHHELD,
    BEACON_PAYLOAD_FIELDS,
    beacon_coverage_gap,
    build_beacon_payload,
)
from swing.web.app import create_app

NOW = datetime(2026, 7, 25, 12, 0)     # Saturday -> action session 2026-07-27
ANCHOR = "2026-07-27"
_HX = {"HX-Request": "true"}


def _seed(cfg, ticker: str, pivot: float, stop: float) -> int:
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(121, '2026-07-17T17:30:05', '2026-07-17', '2026-07-20', "
            "2, 2, 0, 0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, ?, 'aplus', ?, ?, ?, 'universe')",
            (ticker, pivot - 0.5, pivot, stop))
        cid = int(cur.lastrowid)
    conn.close()
    return cid


@pytest.fixture
def frozen_clocks(monkeypatch):
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)


def _view_rows(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute(
            "SELECT candidate_id FROM latch_view_events "
            "ORDER BY view_event_id").fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# ONE named contract, consumed at BOTH ends
# --------------------------------------------------------------------------
def test_the_emitter_builds_its_payload_THROUGH_the_named_contract(
        seeded_db, frozen_clocks):
    """The panel's `beacon_payload_json` field set IS the contract's field set,
    read from the contract rather than re-typed in the view model."""
    cfg, cfg_path = seeded_db
    cid = _seed(cfg, "FTRE", 18.34, 14.88)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        client.get("/latches")
    from swing.web.view_models.latches import build_latch_panel_vm

    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_panel_vm(conn, cfg)
    finally:
        conn.close()
    payload = json.loads(vm.beacon_payload_json)
    assert set(payload) == set(BEACON_PAYLOAD_FIELDS)
    assert payload[BEACON_FIELD_SESSION] == ANCHOR
    assert payload[BEACON_FIELD_ACTIONABLE] or payload[BEACON_FIELD_WITHHELD]
    reported = {
        int(x) for f in (BEACON_FIELD_ACTIONABLE, BEACON_FIELD_WITHHELD)
        for x in payload[f].split(",") if x
    }
    assert reported == {cid}


def test_the_contract_helper_is_the_ONE_place_the_field_names_are_spelled():
    built = build_beacon_payload(
        view_session_date=ANCHOR, actionable_ids=[3, 1], withheld_ids=[2])
    assert set(built) == set(BEACON_PAYLOAD_FIELDS)
    assert built[BEACON_FIELD_ACTIONABLE] == "3,1"
    assert built[BEACON_FIELD_WITHHELD] == "2"


def test_the_coverage_gap_helper_names_the_MISSING_live_latches():
    assert beacon_coverage_gap(reported_ids=[1, 2], live_ids=[1, 2]) == ()
    assert beacon_coverage_gap(reported_ids=[1], live_ids=[1, 2, 3]) == (2, 3)
    assert beacon_coverage_gap(reported_ids=[1, 9], live_ids=[1]) == (), (
        "an EXTRA id is not a shortfall -- the existence gate already ignores "
        "it, and treating it as one would reject a stale-but-honest render")


# --------------------------------------------------------------------------
# THE DISCRIMINATOR -- a truncated payload can no longer pass as full coverage
# --------------------------------------------------------------------------
def test_a_TRUNCATED_payload_is_REFUSED_and_writes_NOTHING(
        seeded_db, frozen_clocks, caplog):
    """PRE-FIX: 204, one view row written, and the omitted latch -- with no view
    evidence of its own -- classified `away_unseen`. A silently inflated away
    rate from an incomplete instrument.
    POST-FIX: a named 400 that lists the missing ids, and NO row written.
    """
    cfg, cfg_path = seeded_db
    first = _seed(cfg, "FTRE", 18.34, 14.88)
    second = _seed(cfg, "VSTS", 16.90, 13.90)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX, data={
            BEACON_FIELD_SESSION: ANCHOR,
            BEACON_FIELD_ACTIONABLE: "",
            BEACON_FIELD_WITHHELD: str(first)})
    assert r.status_code == 400
    assert str(second) in r.text
    assert _view_rows(cfg) == [], (
        "a partial write is the flattering direction: the omitted latch would "
        "keep no view evidence and classify as away_unseen")


def test_a_COMPLETE_payload_is_still_accepted(seeded_db, frozen_clocks):
    """The other half of the pair -- the gate must not simply refuse everything.
    Built THROUGH the contract helper, which is the emitter's own path."""
    cfg, cfg_path = seeded_db
    first = _seed(cfg, "FTRE", 18.34, 14.88)
    second = _seed(cfg, "VSTS", 16.90, 13.90)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX, data=build_beacon_payload(
            view_session_date=ANCHOR, actionable_ids=[first],
            withheld_ids=[second]))
    assert r.status_code == 204
    assert sorted(x[0] for x in _view_rows(cfg)) == sorted([first, second])


def test_the_ROUND_TRIP_the_panel_renders_is_accepted_by_the_route(
        seeded_db, frozen_clocks):
    """THE ANTI-DRIFT PIN: the payload the PANEL actually emits is posted
    verbatim and must be accepted. If the emitter and the reader ever disagree
    about the field set or about coverage, this fails -- which is the property a
    convention at two ends cannot give."""
    cfg, cfg_path = seeded_db
    _seed(cfg, "FTRE", 18.34, 14.88)
    _seed(cfg, "VSTS", 16.90, 13.90)
    app = create_app(cfg, cfg_path)
    conn = connect(cfg.paths.db_path)
    try:
        from swing.web.view_models.latches import build_latch_panel_vm
        vm = build_latch_panel_vm(conn, cfg)
    finally:
        conn.close()
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data=json.loads(vm.beacon_payload_json))
    assert r.status_code == 204
    assert len(_view_rows(cfg)) == 2
