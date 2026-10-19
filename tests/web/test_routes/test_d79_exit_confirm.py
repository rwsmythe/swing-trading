"""D79 T7 -- the ONE confirm shape: flag dispatch, flag-bound acknowledgement,
the d2-strict fresh map, and the one route connection.

Plan: ``docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md`` T7
(orchestrator K5; RD K3 (1)-(3), K5c; CHARC FORK 2), with the executing
rulings in ``...exit-identity.exec-ledger.md``: FORK 1 (the precheck before
the question), FORK 3 (G1: a claimed anchor's flags render only when it is
restored) and the T7 read-connection ruling (no second connection). The
world is ``test_exit_rerender_anchor.py``'s ``world``: o1 = 2026-05-20
130.00 x 4, o2 = 2026-05-21 131.00 x 3 (the default, index 1); the trade
holds 10 shares.
"""
from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

import swing.web.routes.trades as routes_mod
from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos import trades as trades_repo
from swing.trades import exit as exit_mod
from swing.trades import exit_auto_fill as eaf
from swing.web.app import create_app
from tests.web.test_routes.test_d79_exit_identity import (
    _acks,
    _confirm,
    _env,
    _exit_rows,
    _form,
    _hash_of,
    _text,
)
from tests.web.test_routes.test_exit_rerender_anchor import (  # noqa: F401
    _NOTICE,
    _browser_form,
    _checked_radios,
    _hidden,
    _input_attr,
    _order,
    _post,
    _selected_reasons,
    world,
)


def _plant_fill(cfg, trade_id: int, *, day: str, price: float, qty: int,
                envelope: str | None = None) -> int:
    """A RAW non-entry fill (the 18-B.1 technique: the route can no longer
    produce some of these shapes). ``trades.current_size`` is NOT
    recomputed, so the world trade still holds 10 shares."""
    c = sqlite3.connect(str(cfg.paths.db_path))
    try:
        with c:
            cur = c.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, fill_origin, schwab_source_value_json) "
                "VALUES (?, ?, 'trim', ?, ?, 'operator_typed', ?)",
                (trade_id, f"{day}T16:00:00", qty, price, envelope))
        return int(cur.lastrowid)
    finally:
        c.close()


def _other_trade(cfg) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trades_repo.insert_trade_with_event(conn, Trade(
                id=None, ticker="AMD", entry_date="2026-04-15",
                entry_price=50.0, initial_shares=5, initial_stop=45.0,
                current_stop=45.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        return int(conn.execute("SELECT MAX(id) FROM trades").fetchone()[0])
    finally:
        conn.close()


_UNREADABLE_ENVELOPE = json.dumps({
    "schwab_order_id": " 123", "exit_date": "2026-05-10",
    "exit_price": 125.0, "closed_shares": 1})


# ------------------------------------------------------------------ T7-a
def test_t7a_value_tuple_match_asks_then_the_confirm_records(world):
    """Cell list 5, RD K5c. An anonymous ``operator_typed`` fill at o2's
    values; the first unedited o2 POST asks (no new fill, the value-tuple
    text names the fill), the confirm records -- with no caller-held
    transaction, or ``record_exit`` would raise. Never refused. PRE-FIX:
    the first POST records immediately."""
    fid = _plant_fill(world.cfg, world.tid, day="2026-05-21", price=131.0,
                      qty=3)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        r1 = _post(tc, world.tid, _form(tc, world.tid))
        assert r1.status_code == 400, r1.text[:500]
        assert (f"These values match recorded fill #{fid} (2026-05-21 at "
                "131.00 x 3), which carries no broker order id") in _text(r1)
        assert _acks(r1.text) == [f"value_tuple_match|{fid}"]
        assert 'name="force" value="true"' in r1.text
        assert len(_exit_rows(world.cfg)) == 1
        r2 = _confirm(tc, world.tid, r1.text)
    assert r2.status_code == 200, r2.text[:500]
    assert len(_exit_rows(world.cfg)) == 2


def test_t7b_an_unacknowledged_flag_re_asks(world):
    """K5: ``force`` is not a blanket waiver. The confirm drops the one
    identity from its acknowledgements -> asked again, nothing recorded."""
    _plant_fill(world.cfg, world.tid, day="2026-05-21", price=131.0, qty=3)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        r1 = _post(tc, world.tid, _form(tc, world.tid))
        assert r1.status_code == 400
        r2 = _confirm(tc, world.tid, r1.text, acks=[])
    assert r2.status_code == 400, r2.text[:500]
    assert "Confirm or retype before recording." in r2.text
    assert len(_exit_rows(world.cfg)) == 1


def test_t7c_a_changed_list_voids_the_confirmation(world):
    """K5, RD K3 (2): after the flag render the broker list gains o3, so
    the fresh map differs: the confirm is VOID -- refresh notice, NO flags,
    no new fill. NULL killed: confirm checked against the SUBMITTED map."""
    _plant_fill(world.cfg, world.tid, day="2026-05-21", price=131.0, qty=3)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        r1 = _post(tc, world.tid, _form(tc, world.tid))
        assert r1.status_code == 400
        world.box["orders"].append(_order("o3", "2026-05-22", 132.0, 2))
        r2 = _confirm(tc, world.tid, r1.text)
    assert r2.status_code == 400, r2.text[:500]
    assert _NOTICE in r2.text
    assert "the confirmation is void" in r2.text
    assert _acks(r2.text) == []
    assert "These values match recorded fill" not in r2.text
    assert len(_exit_rows(world.cfg)) == 1


def test_t7d_the_flagged_re_render_round_trips_the_pick(world):
    """K5, cell list 9: o1 picked (non-default), F1 flagged. The flagged
    re-render keeps the pick by hash, the typed values and the reason; the
    confirm persists o1's hash. NULL killed: a re-render that drops
    ``candidate_index`` re-targets the default o2."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        o1_hash = _hash_of(_env(fd), "o1")
        r1 = _post(tc, world.tid, dict(fd, candidate_index="0",
                                       reason="target"))
        assert r1.status_code == 400, r1.text[:500]
        assert _checked_radios(r1.text) == ["0"]
        assert _hidden(r1.text, "candidate_signature_hash_0") == o1_hash
        assert _input_attr(r1.text, "exit_date", "value") == "2026-05-21"
        assert _input_attr(r1.text, "exit_price", "value") == "131.00"
        assert _input_attr(r1.text, "shares", "value") == "3"
        assert _selected_reasons(r1.text) == ["target"]
        r2 = _confirm(tc, world.tid, r1.text)
    assert r2.status_code == 200, r2.text[:500]
    [(_fid, _o, env, _c, _p, _q)] = _exit_rows(world.cfg)
    assert json.loads(env)["selected_candidate_signature_hash"] == o1_hash


def test_t7e_the_identity_binds_the_typed_values(world):
    """Ledger "Plan intake": after an F1 flag on typed price 129.50 the
    operator retypes 129.60 and presses Confirm with the OLD
    acknowledgement -> asked again, the new text names 129.60, nothing
    recorded. NULL killed: acknowledgement by kind only."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        r1 = _post(tc, world.tid, dict(_form(tc, world.tid),
                                       exit_price="129.50"))
        assert r1.status_code == 400
        assert _acks(r1.text) == [
            "f1_matches_no_candidate|o2|2026-05-21|129.50|3"]
        r2 = _confirm(tc, world.tid, r1.text, exit_price="129.60")
    assert r2.status_code == 400, r2.text[:500]
    assert "129.60" in _text(r2)
    assert _acks(r2.text) == ["f1_matches_no_candidate|o2|2026-05-21|129.60|3"]
    assert _exit_rows(world.cfg) == []


@pytest.mark.parametrize("maps_equal_stubbed", [False, True])
def test_t7f_a_confirmation_cannot_waive_an_already_recorded_order(
        world, monkeypatch, maps_equal_stubbed):
    """RD K3 (3), cell list 10 (cell 2's accepted choice 11). Tab A records
    o1 by pick and confirm. Tab B (same GET-time form) picks o1: its first
    response DROPS its flags (the fresh list no longer offers o1, FORK 3),
    so its acknowledgement is test-built. Base: the confirm is voided by d2
    first. With the maps stubbed EQUAL, the d2 check passes and the SERVICE
    refuses it. One o1 row either way. PRE-FIX: two o1 rows."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        tab_a = dict(_form(tc, world.tid), candidate_index="0")
        tab_b = dict(_form(tc, world.tid), candidate_index="0")
        ra = _post(tc, world.tid, tab_a)
        assert ra.status_code == 400
        ra2 = _confirm(tc, world.tid, ra.text)
        assert ra2.status_code == 200, ra2.text[:500]
        [(fid_a, *_rest)] = _exit_rows(world.cfg)
        rb = _post(tc, world.tid, tab_b)
        assert rb.status_code == 400
        assert _acks(rb.text) == []
        if maps_equal_stubbed:
            monkeypatch.setattr(routes_mod, "_exit_candidates_maps_equal",
                                lambda vm, env: True)
        rb2 = _post(tc, world.tid, dict(
            tab_b, force="true",
            acknowledged_flag="f1_matches_other_order|o1|2026-05-21|131.00|3"))
    assert rb2.status_code == 400, rb2.text[:500]
    if maps_equal_stubbed:
        assert f"already recorded as fill(s) #{fid_a}" in rb2.text
    else:
        assert _NOTICE in rb2.text
        assert "the confirmation is void" in rb2.text
    rows = _exit_rows(world.cfg)
    assert len(rows) == 1
    assert json.loads(rows[0][2])["schwab_order_id"] == "o1"


def test_t7g_two_tabs_record_the_default_once(world):
    """Cell list 1, F2-A through the route: two GETs, both tabs POST o2
    unedited -> 200 then 400 "already recorded", one fill. PRE-FIX: both
    200 and 2 fills (round-0 ``probe_f2a.json``)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        tab_a = _form(tc, world.tid)
        tab_b = _form(tc, world.tid)
        ra = _post(tc, world.tid, tab_a)
        rb = _post(tc, world.tid, tab_b)
    assert ra.status_code == 200, ra.text[:500]
    assert rb.status_code == 400, rb.text[:500]
    assert "already recorded" in rb.text
    assert len(_exit_rows(world.cfg)) == 1


@pytest.mark.parametrize("where", ["same_trade", "other_trade"])
def test_t7h_t7i_an_unreadable_recorded_envelope_asks_then_records(
        world, where):
    """CHARC FORK 2 F2-(i) (same trade) and F2-(ii) (another trade: the
    scan is GLOBAL). A raw fill F whose envelope carries a padded id: the
    first unedited (linked) o2 POST asks with the unreadable text naming F;
    the confirm records one new row. NULLs killed: 2a (a refusal with no
    confirm path) and 2b (records on the first POST); a per-trade scan
    (the other-trade case)."""
    owner = world.tid if where == "same_trade" else _other_trade(world.cfg)
    fid = _plant_fill(world.cfg, owner, day="2026-05-10", price=125.0, qty=1,
                      envelope=_UNREADABLE_ENVELOPE)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        r1 = _post(tc, world.tid, _form(tc, world.tid))
        assert r1.status_code == 400, r1.text[:500]
        body = _text(r1)
        assert f"Fill #{fid}'s envelope cannot be read" in body
        assert f"correct fill #{fid}" in body
        # D79-A2 (Fork A2, branch B): the identity names the linked order
        # the question is about (o2, the default) as well as the fill.
        assert _acks(r1.text) == [f"unreadable_envelope|o2|{fid}"]
        assert len(_exit_rows(world.cfg)) == 1
        r2 = _confirm(tc, world.tid, r1.text)
    assert r2.status_code == 200, r2.text[:500]
    assert len(_exit_rows(world.cfg)) == 2


def test_t7j_an_unlinked_exit_is_not_asked_about_an_unreadable_row(world):
    """CHARC FORK 2 scope control (the CLI-absent shape): an unclaimed
    ``operator_typed`` POST, no anonymous match, an unreadable row on
    another trade -> recorded on the FIRST POST (the unreadable question
    needs a linked exit)."""
    other = _other_trade(world.cfg)
    _plant_fill(world.cfg, other, day="2026-05-10", price=125.0, qty=1,
                envelope=_UNREADABLE_ENVELOPE)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        r = _post(tc, world.tid, {
            "exit_date": "2026-05-12", "exit_price": "117.25", "shares": "2",
            "reason": "manual", "notes": ""})
    assert r.status_code == 200, r.text[:500]
    assert len(_exit_rows(world.cfg)) == 2


# ------------------------------------------- the T7 read-connection ruling
def test_t7_an_accepted_claimed_post_opens_one_connection(world, monkeypatch):
    """The orchestrator's T7 read-connection ruling: the precheck's
    ``get_trade``, ``anonymous_fill_matches`` and the unreadable reader run
    on the route's ONE connection -- the one ``record_exit`` receives, with
    no transaction open. Counted at ``swing.web.routes.trades.connect`` AND
    pinned by identity at every read, so a second connection opened under
    any other name fails here too. PRE-FIX (no T7 reads): the advisory
    readers are never called on the route connection."""
    from tests._22f_proxies import patch_conn_opener

    built = patch_conn_opener(monkeypatch, "swing.web.routes.trades.connect",
                              lambda real: real)
    seen: dict[str, list] = {"get_trade": [], "anonymous": [],
                             "identities": [], "record": []}

    def spy(name, real):
        def wrapper(conn, *a, **k):
            seen[name].append(conn)
            return real(conn, *a, **k)
        return wrapper

    monkeypatch.setattr(routes_mod, "get_trade",
                        spy("get_trade", routes_mod.get_trade))
    monkeypatch.setattr(routes_mod, "anonymous_fill_matches",
                        spy("anonymous", eaf.anonymous_fill_matches))
    monkeypatch.setattr(routes_mod, "recorded_exit_identities",
                        spy("identities", exit_mod.recorded_exit_identities))
    at_entry: list[tuple[int, bool]] = []
    real_record = exit_mod.record_exit

    def record_spy(conn, req):
        seen["record"].append(conn)
        at_entry.append((len(built), conn.in_transaction))
        return real_record(conn, req)

    monkeypatch.setattr(routes_mod, "record_exit", record_spy)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        r = _post(tc, world.tid, _form(tc, world.tid))
    assert r.status_code == 200, r.text[:500]
    assert at_entry == [(1, False)]
    [route_conn] = seen["record"]
    assert route_conn is built[0]
    assert seen["get_trade"][0] is route_conn
    assert seen["anonymous"] == [route_conn]
    assert seen["identities"] == [route_conn]


# ------------------------------------------- D79-A2 (Reviewer A round 1)
def _entered_then_executed(oid: str, entered: str, executed: str,
                           price: float, qty: int):
    """A FILLED SELL order ENTERED on ``entered`` and EXECUTED on
    ``executed``: its K7.2 possible-partial window is [entered, executed]."""
    from swing.integrations.schwab.models import (
        SchwabExecutionLeg,
        SchwabOrderResponse,
    )
    return SchwabOrderResponse(
        order_id=oid, status="FILLED", enter_time=f"{entered}T14:30:00.000Z",
        instrument_symbol="NVDA", instruction="SELL", quantity=qty,
        order_type="LIMIT", price=price,
        executions=[SchwabExecutionLeg(
            leg_id=1, price=price, quantity=qty, mismarked_quantity=None,
            instrument_id=1, time=f"{executed}T14:30:00.000Z")])


def test_a2_an_acknowledged_partial_of_one_order_does_not_discharge_another(
        world):
    """D79-A2, orchestrator Fork A2 ruling branch B: the browser shape. Both
    candidates list fill #F as a possible partial (both windows open on
    2026-05-19; F is 2026-05-20 at 129.00 x 2, inside both and no larger
    than either). o1 is picked at its own values and its flag renders. The
    operator then switches the radio AND the values to o2 and presses
    Confirm with o1's acknowledgements. The map is unchanged, so d2 passes.
    Expected: 400, asked again about o2, no fill. PRE-FIX: both questions
    carry the identity ``possible_partial|F``, so o1's acknowledgement
    satisfies o2's and o2 is recorded (200, one row)."""
    world.box["orders"] = [
        _entered_then_executed("o1", "2026-05-19", "2026-05-20", 130.0, 4),
        _entered_then_executed("o2", "2026-05-19", "2026-05-21", 131.0, 3),
    ]
    fid = _plant_fill(world.cfg, world.tid, day="2026-05-20", price=129.0,
                      qty=2)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        r1 = _post(tc, world.tid, dict(
            fd, candidate_index="0", exit_date="2026-05-20",
            exit_price="130.00", shares="4"))
        assert r1.status_code == 400, r1.text[:500]
        assert _checked_radios(r1.text) == ["0"]
        assert (f"Possible partial of this order: fill #{fid}" in _text(r1))
        assert f"is not part of order o1" in _text(r1)
        assert _acks(r1.text) == [f"possible_partial|o1|{fid}"]
        o1_acks = _acks(r1.text)
        r2 = _confirm(tc, world.tid, r1.text, acks=o1_acks,
                      candidate_index="1", exit_date="2026-05-21",
                      exit_price="131.00", shares="3")
    assert r2.status_code == 400, r2.text[:500]
    assert "Confirm or retype before recording." in r2.text
    assert f"is not part of order o2" in _text(r2)
    assert _acks(r2.text) == [f"possible_partial|o2|{fid}"]
    assert len(_exit_rows(world.cfg)) == 1  # the planted F alone


# ------------------------------------------- R5-02 (Reviewer A round 5)
def test_r502_an_acknowledged_value_tuple_of_one_order_does_not_discharge_another(
        world):
    """Fork R5-02, branch A (orchestrator): the browser shape. o1 and o2 sell
    at ONE price and quantity (130.00 x 3); o1 is entered 2026-05-19 and
    executed 2026-05-20, o2 entered 2026-05-20 and executed 2026-05-21.
    Anonymous fill F is 2026-05-20 at 130.00 x 3: o1's execution date and
    o2's ENTERED date, so both orders' map lists carry F as a value-tuple
    match. o1 is picked at its own values and asked about F (the DB-derived
    match, deduplicated with o1's map item). The operator switches the radio
    AND the values to o2 and presses Confirm with o1's acknowledgement. The
    map is unchanged, so d2 passes, and o2's typed values match no fill in
    the DB. Expected: 400, asked about F under o2's order-scoped identity,
    no fill. PRE-FIX: o2's map-derived question carried the identity
    ``value_tuple_match|F``, which o1's acknowledgement satisfied, so o2
    recorded (200, two rows)."""
    world.box["orders"] = [
        _entered_then_executed("o1", "2026-05-19", "2026-05-20", 130.0, 3),
        _entered_then_executed("o2", "2026-05-20", "2026-05-21", 130.0, 3),
    ]
    fid = _plant_fill(world.cfg, world.tid, day="2026-05-20", price=130.0,
                      qty=3)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        r1 = _post(tc, world.tid, dict(
            fd, candidate_index="0", exit_date="2026-05-20",
            exit_price="130.00", shares="3"))
        assert r1.status_code == 400, r1.text[:500]
        assert _checked_radios(r1.text) == ["0"]
        assert _acks(r1.text) == [f"value_tuple_match|{fid}"]
        r2 = _confirm(tc, world.tid, r1.text, acks=_acks(r1.text),
                      candidate_index="1", exit_date="2026-05-21",
                      exit_price="130.00", shares="3")
    assert r2.status_code == 400, r2.text[:500]
    assert "Confirm or retype before recording." in r2.text
    assert _acks(r2.text) == [f"value_tuple_match|o2|{fid}"]
    assert len(_exit_rows(world.cfg)) == 1  # the planted F alone


# ------------------------------------------- RA-04 (Reviewer A round 2)
def test_ra04_a_void_confirm_whose_prefetch_is_none_builds_once(
        world, monkeypatch):
    """RA-04 (choice 13): a ``force`` confirm whose fresh VM is ``None``
    (the trade is gone or closed) is VOID, and the void re-render reuses
    that prefetched ``None`` -- the banner-only fragment -- instead of
    building the VM a second time. PRE-FIX: ``fresh_vm=None`` reads as
    "not prefetched", so the builder runs twice."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        calls: list[int] = []

        def gone(**kw):
            calls.append(1)
            return None

        monkeypatch.setattr(routes_mod, "build_exit_form_vm", gone)
        r = _post(tc, world.tid, dict(
            fd, force="true", acknowledged_flag="value_tuple_match|1"))
    assert r.status_code == 400, r.text[:500]
    assert "the confirmation is void" in r.text
    assert calls == [1]
    assert _exit_rows(world.cfg) == []


# ------------------------------------------- RA-05 (Reviewer A round 2)
def test_ra05_every_identity_must_be_acknowledged_not_any(world):
    """RA-05, K5 (EVERY flag's identity): one unedited (linked) o2 POST
    raises TWO flags at once -- the (c) value-tuple match on an anonymous
    fill at o2's values, and the unreadable envelope of a fill on another
    trade. A confirm acknowledging ONE re-asks and records nothing; a
    confirm acknowledging BOTH records. NULL killed: recording when the
    acknowledgements merely INTERSECT the flags."""
    anon = _plant_fill(world.cfg, world.tid, day="2026-05-21", price=131.0,
                       qty=3)
    bad = _plant_fill(world.cfg, _other_trade(world.cfg), day="2026-05-10",
                      price=125.0, qty=1, envelope=_UNREADABLE_ENVELOPE)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        r1 = _post(tc, world.tid, _form(tc, world.tid))
        assert r1.status_code == 400, r1.text[:500]
        both = _acks(r1.text)
        assert both == [f"value_tuple_match|{anon}",
                        f"unreadable_envelope|o2|{bad}"]
        for one in both:
            r = _confirm(tc, world.tid, r1.text, acks=[one])
            assert r.status_code == 400, r.text[:500]
            assert "Confirm or retype before recording." in r.text
            assert len(_exit_rows(world.cfg)) == 2  # the two planted rows
        r2 = _confirm(tc, world.tid, r1.text, acks=both)
    assert r2.status_code == 200, r2.text[:500]
    assert len(_exit_rows(world.cfg)) == 3


# ---------------------------------------- D79-A-01 (Reviewer A round 3)
def _o2_carries_a_partial(world) -> int:
    """o1 = 2026-05-20 130.00 x 4 as in ``world``; o2 ENTERED 2026-05-19 and
    EXECUTED 2026-05-21 at 131.00 x 3, so its K7.2 window is [05-19, 05-21].
    The planted anonymous fill F (2026-05-19 at 129.00 x 2) sits inside o2's
    window only, so the DEFAULT (o2) map entry lists F as a possible
    partial and o1's does not."""
    world.box["orders"] = [
        _order("o1", "2026-05-20", 130.0, 4),
        _entered_then_executed("o2", "2026-05-19", "2026-05-21", 131.0, 3),
    ]
    return _plant_fill(world.cfg, world.tid, day="2026-05-19", price=129.0,
                       qty=2)


def test_a01_an_omitted_radio_asks_the_default_candidates_partial(world):
    """Fork D79-A-01, branch B (orchestrator), the ruled RED: a default o2
    carrying a possible partial, submitted with the radio omitted (every
    per-candidate input kept, and again with none). The selected entry IS
    o2's map entry, so its partial is asked: 400, the partial text naming
    o2, its order-scoped identity, o2's radio checked, no fill. The confirm
    then records o2 with the selected/other hashes stamped. PRE-FIX: the
    synthesized entry carries no ``possible_duplicates``, so nothing is
    asked and the first POST records (200)."""
    fid = _o2_carries_a_partial(world)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        env = _env(fd)
        o1_hash, o2_hash = _hash_of(env, "o1"), _hash_of(env, "o2")
        assert [d["fill_id"] for d in env["candidates_map"][o2_hash][
            "possible_duplicates"]] == [fid]
        assert env["candidates_map"][o1_hash]["possible_duplicates"] == []
        no_radio = {k: v for k, v in fd.items() if k != "candidate_index"}
        bare = {k: v for k, v in fd.items() if not k.startswith("candidate_")}
        for shape in (no_radio, bare):
            r1 = _post(tc, world.tid, shape)
            assert r1.status_code == 400, r1.text[:500]
            assert f"Possible partial of this order: fill #{fid}" in _text(r1)
            assert "is not part of order o2" in _text(r1)
            assert _acks(r1.text) == [f"possible_partial|o2|{fid}"]
            assert _checked_radios(r1.text) == ["1"]
            assert len(_exit_rows(world.cfg)) == 1  # the planted F alone
        r2 = _confirm(tc, world.tid, r1.text)
    assert r2.status_code == 200, r2.text[:500]
    [_f, (_fid, origin, env_json, _c, _p, _q)] = _exit_rows(world.cfg)
    persisted = json.loads(env_json)
    assert origin == "schwab_auto"
    assert persisted["schwab_order_id"] == "o2"
    assert persisted["selected_candidate_signature_hash"] == o2_hash
    assert persisted["selected_candidate_order_id"] == "o2"
    assert persisted["other_candidate_signature_hashes"] == [o1_hash]


def test_a01_an_unedited_omitted_radio_stamps_the_resolved_entry(world):
    """Branch B's stamping half, with no flag in play: the radio omitted,
    the values unedited, so the POST records at once -- and the persisted
    envelope names the resolved entry (selected hash o2's, selected order
    o2, the other key o1's). PRE-FIX: recorded with NO ``selected_*`` keys
    (the synthesized entry has no map key), an anonymous confirmation."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        env = _env(fd)
        o1_hash, o2_hash = _hash_of(env, "o1"), _hash_of(env, "o2")
        r = _post(tc, world.tid,
                  {k: v for k, v in fd.items() if k != "candidate_index"})
    assert r.status_code == 200, r.text[:500]
    [(_fid, origin, env_json, _c, _p, _q)] = _exit_rows(world.cfg)
    persisted = json.loads(env_json)
    assert origin == "schwab_auto"
    assert persisted["schwab_order_id"] == "o2"
    assert persisted["selected_candidate_signature_hash"] == o2_hash
    assert persisted["selected_candidate_order_id"] == "o2"
    assert persisted["other_candidate_signature_hashes"] == [o1_hash]


def _assert_reconfirmed(r, cfg) -> None:
    """The Fork 3 (G1) response: 400, the re-confirm text, the refresh
    notice, no flag, the FRESH map-bearing anchor, nothing recorded."""
    assert r.status_code == 400, r.text[:500]
    body = _text(r)
    assert "must be re-confirmed" in body
    assert _NOTICE in body
    assert _acks(r.text) == []
    fresh = json.loads(_hidden(r.text, "schwab_source_value_json"))
    assert fresh["schwab_order_id"] == "o2" and "candidates_map" in fresh
    assert _exit_rows(cfg) == []


def test_a01_a_top_level_id_no_map_entry_carries_is_reconfirmed(world):
    """Branch B, zero matches: a map-bearing claim with no selection whose
    top-level ``schwab_order_id`` (o9) no map entry carries resolves to no
    entry -> the G1 re-confirm, the typed values kept. PRE-FIX: the
    synthesized o9 entry derives, the retention rule pops o9, and an
    anonymous exit records (200)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        env = _env(fd)
        env["schwab_order_id"] = "o9"
        r = _post(tc, world.tid, dict(
            {k: v for k, v in fd.items() if not k.startswith("candidate_")},
            schwab_source_value_json=json.dumps(env, sort_keys=True)))
    _assert_reconfirmed(r, world.cfg)
    assert _input_attr(r.text, "exit_price", "value") == "131.00"


def test_a01_two_map_entries_matching_the_top_level_are_reconfirmed(world):
    """Branch B, several matches. The map is keyed by signature hash and the
    POST never recomputes a key from its entry, so a client-edited envelope
    CAN carry two keys whose entries are o2's identical order id and
    quartet. Neither is THE unique entry -> the G1 re-confirm. PRE-FIX: the
    synthesized entry derives and the exit records (200)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        env = _env(fd)
        o2_hash = _hash_of(env, "o2")
        env["candidates_map"]["f" * 16] = dict(env["candidates_map"][o2_hash])
        r = _post(tc, world.tid, dict(
            {k: v for k, v in fd.items() if not k.startswith("candidate_")},
            schwab_source_value_json=json.dumps(env, sort_keys=True)))
    _assert_reconfirmed(r, world.cfg)
