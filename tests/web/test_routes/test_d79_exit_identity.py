"""D79 -- the exit route records the SELECTED broker order's link, once.

Plan: ``docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md``
(T1-c route half, T5, T6). The world is ``test_exit_rerender_anchor.py``'s
``world`` fixture: o1 = 2026-05-20 130.00 x 4, o2 = 2026-05-21 131.00 x 3,
o2 the default at index 1; the trade holds 10 shares.
"""
from __future__ import annotations

import html
import json
import re
import sqlite3

from fastapi.testclient import TestClient

import swing.web.routes.trades as routes_mod
from swing.trades import exit as exit_mod
from swing.web.app import create_app
from tests.web.test_routes.test_exit_rerender_anchor import (  # noqa: F401
    _browser_form,
    _checked_radios,
    _exit_fills,
    _post,
    world,
)


# ----------------------------------------------------------------- T1-c
def test_t1c_route_calls_record_exit_with_no_open_transaction(
        world, monkeypatch):
    """CHARC K1 (1) precondition, a PIN (green pre-fix): the web exit POST
    enters ``record_exit`` with no open transaction. Spied AT THE ROUTE'S
    BOUND NAME, so a future caller-side ``with conn:`` fails here."""
    seen: list[bool] = []
    real = exit_mod.record_exit

    def spy(conn, req):
        seen.append(conn.in_transaction)
        return real(conn, req)

    monkeypatch.setattr(routes_mod, "record_exit", spy)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _browser_form(tc.get(f"/trades/{world.tid}/exit/form").text)
        fd["reason"] = "manual"
        r = _post(tc, world.tid, fd)
    assert r.status_code == 200, r.text[:500]
    assert seen == [False]
    assert len(_exit_fills(world.cfg)) == 1


# ------------------------------------------------------------------- T5
def _single(world):
    """The single-candidate variant of ``world``: the stub returns o2 only."""
    world.box["orders"] = [o for o in world.box["orders"]
                           if o.order_id == "o2"]


def _persisted_envelopes(cfg) -> list[dict]:
    return [json.loads(env) for *_rest, env, _at in _exit_fills(cfg)
            if env is not None]


def test_t5a_single_candidate_stamps_the_selected_keys(world):
    """RD K3 precondition (4). PRE-FIX: none of these keys (round-0
    ``probe_f2b_single.json``)."""
    _single(world)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _browser_form(tc.get(f"/trades/{world.tid}/exit/form").text)
        [o2_hash] = json.loads(fd["schwab_source_value_json"])["candidates_map"]
        fd["reason"] = "manual"
        r = _post(tc, world.tid, fd)
    assert r.status_code == 200, r.text[:500]
    [env] = _persisted_envelopes(world.cfg)
    assert env["selected_candidate_signature_hash"] == o2_hash
    assert env["selected_candidate_order_id"] == "o2"
    assert env["other_candidate_signature_hashes"] == []


def test_t5b_bare_single_candidate_post_stamps_too(world):
    """A submission with the template's index-0 inputs STRIPPED stamps the
    same keys: the fix is server-side. NULL killed: a template-only fix."""
    _single(world)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _browser_form(tc.get(f"/trades/{world.tid}/exit/form").text)
        [o2_hash] = json.loads(fd["schwab_source_value_json"])["candidates_map"]
        fd = {k: v for k, v in fd.items()
              if not k.startswith("candidate_")}
        fd["reason"] = "manual"
        r = _post(tc, world.tid, fd)
    assert r.status_code == 200, r.text[:500]
    [env] = _persisted_envelopes(world.cfg)
    assert env["selected_candidate_signature_hash"] == o2_hash
    assert env["selected_candidate_order_id"] == "o2"
    assert env["other_candidate_signature_hashes"] == []


def test_t5_template_emits_index_zero_inputs_for_one_candidate(world):
    _single(world)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _browser_form(tc.get(f"/trades/{world.tid}/exit/form").text)
    [o2_hash] = json.loads(fd["schwab_source_value_json"])["candidates_map"]
    assert fd["candidate_signature_hash_0"] == o2_hash
    assert fd["candidate_order_id_0"] == "o2"
    assert "candidate_index" not in fd  # still no radio at length 1


def test_t5c_single_candidate_two_tab_replay_is_refused_once(world):
    """Cell list 1 (single): two GETs, two unedited POSTs -> the second is
    refused at the service and exactly one fill exists. PRE-FIX: 2 fills."""
    _single(world)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        tab_a = _browser_form(tc.get(f"/trades/{world.tid}/exit/form").text)
        tab_b = _browser_form(tc.get(f"/trades/{world.tid}/exit/form").text)
        tab_a["reason"] = tab_b["reason"] = "manual"
        ra = _post(tc, world.tid, tab_a)
        rb = _post(tc, world.tid, tab_b)
    assert ra.status_code == 200, ra.text[:500]
    assert rb.status_code == 400, rb.text[:500]
    assert "already recorded" in rb.text
    assert len(_exit_fills(world.cfg)) == 1


# ------------------------------------------------------------------- T6
def _form(tc, tid) -> dict:
    fd = _browser_form(tc.get(f"/trades/{tid}/exit/form").text)
    fd["reason"] = "manual"
    return fd


def _env(fd) -> dict:
    return json.loads(fd["schwab_source_value_json"])


def _hash_of(env: dict, order_id: str) -> str:
    [sig] = [k for k, v in env["candidates_map"].items()
             if v["order_id"] == order_id]
    return sig


def _text(r) -> str:
    """The body with HTML entities decoded (the flag texts carry an
    apostrophe, which the template autoescapes)."""
    return html.unescape(r.text)


def _without_candidate_inputs(fd: dict) -> dict:
    return {k: v for k, v in fd.items() if not k.startswith("candidate_")}


def test_t6a_unconfirmed_contradiction_writes_nothing(world):
    """Orchestrator K7.3, the label: o1 picked (index 0), the inputs left at
    o2's values, no confirm -> NOTHING is written and the F1 flag names
    both orders. PRE-FIX: a ``schwab_auto_then_operator_corrected`` fill
    whose top-level id is o2 (round-0 Item 2)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        fd["candidate_index"] = "0"
        r = _post(tc, world.tid, fd)
    assert r.status_code == 400, r.text[:500]
    assert "match order o2, not the selected order o1" in _text(r)
    assert _exit_fills(world.cfg) == []


def test_t6d_padded_order_id_is_refused_before_record_exit(world, monkeypatch):
    """CHARC F2-(iv), the writer half: an envelope whose top-level id and
    map entry carry " o2" (padded, a hand-built CONSISTENT anchor) is
    refused by the authority read before ``record_exit`` is reached; the
    same POST with "o2" records. PRE-FIX: " o2" is persisted (the
    ``usable`` check passes). NULL killed: the check in the service only
    (it fails the zero-calls assertion)."""
    calls: list[int] = []
    real = exit_mod.record_exit

    def spy(conn, req):
        calls.append(1)
        return real(conn, req)

    monkeypatch.setattr(routes_mod, "record_exit", spy)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        env = _env(fd)
        for entry in env["candidates_map"].values():
            if entry["order_id"] == "o2":
                entry["order_id"] = " o2"
        env["schwab_order_id"] = " o2"
        padded = dict(fd, schwab_source_value_json=json.dumps(
            env, sort_keys=True), candidate_order_id_1=" o2")
        r = _post(tc, world.tid, padded)
        assert r.status_code == 400, r.text[:500]
        assert "malformed (padded or blank)" in _text(r)
        assert calls == []
        assert _exit_fills(world.cfg) == []
        ok = _post(tc, world.tid, fd)
    assert ok.status_code == 200, ok.text[:500]
    assert calls == [1]
    [env_ok] = _persisted_envelopes(world.cfg)
    assert env_ok["schwab_order_id"] == "o2"


def test_t6e_default_pick_with_an_edit_is_flagged(world):
    """Orchestrator K4 (the default included): o2 left selected, the price
    edited 131.00 -> 131.40, no confirm -> no fill, and the F1 flag names
    the one differing field. PRE-FIX: recorded as corrected."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        fd["exit_price"] = "131.40"
        r = _post(tc, world.tid, fd)
    assert r.status_code == 400, r.text[:500]
    body = _text(r)
    assert "differ from order o2's (2026-05-21, 131.00 x 3) in price." in body
    assert "match order" not in body
    assert _exit_fills(world.cfg) == []


def test_t6f_default_unedited_control(world):
    """Control: the default, unedited -> ``schwab_auto``, top-level o2, one
    fill, 200."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        r = _post(tc, world.tid, _form(tc, world.tid))
    assert r.status_code == 200, r.text[:500]
    [(_fid, _action, _qty, origin, env, _at)] = _exit_fills(world.cfg)
    assert origin == "schwab_auto"
    assert json.loads(env)["schwab_order_id"] == "o2"


def test_t6h_multi_entry_map_with_no_selection_resolves_the_default(world):
    """Fork 2 (orchestrator), as narrowed by Fork D79-A-01 (branch B): a
    claimed multi-entry envelope, top-level o2, NO candidate inputs. The
    selected entry is the unique map entry naming the top-level order (o2)
    whose values the top-level quartet derives from. (i) price edited ->
    F1 NO_CANDIDATE naming price;
    (ii) typed values equal to o1's entry -> F1 OTHER_ORDER naming o1;
    (iii) unedited -> recorded, the control. PRE-FIX (legacy-only
    synthesis): (i) records ``schwab_auto_then_operator_corrected`` on the
    first POST."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        bare = _without_candidate_inputs(_form(tc, world.tid))
        r1 = _post(tc, world.tid, dict(bare, exit_price="131.40"))
        assert r1.status_code == 400, r1.text[:500]
        assert ("differ from order o2's (2026-05-21, 131.00 x 3) in price."
                in _text(r1))
        r2 = _post(tc, world.tid, dict(
            bare, exit_date="2026-05-20", exit_price="130.00", shares="4"))
        assert r2.status_code == 400, r2.text[:500]
        assert "match order o1, not the selected order o2" in _text(r2)
        assert _exit_fills(world.cfg) == []
        r3 = _post(tc, world.tid, bare)
    assert r3.status_code == 200, r3.text[:500]
    [(_fid, _action, _qty, origin, env, _at)] = _exit_fills(world.cfg)
    assert origin == "schwab_auto"
    assert json.loads(env)["schwab_order_id"] == "o2"


# ---------------------------------------------- the T7 confirm protocol
def _acks(body: str) -> list[str]:
    """The flag identities the flagged re-render emitted, in order."""
    return [html.unescape(v) for v in re.findall(
        r'name="acknowledged_flag" value="([^"]*)"', body)]


def _confirm(tc, tid, body: str, *, acks=None, **over):
    """Press Confirm on the re-rendered form ``body``: what a browser
    submits (``_browser_form``, which keeps ONE value per name, so the
    acknowledgements are re-read as a list) plus ``force=true``."""
    fd = _browser_form(body)
    fd.pop("acknowledged_flag", None)
    fd.update(over)
    data: dict = dict(fd, force="true")
    data["acknowledged_flag"] = _acks(body) if acks is None else list(acks)
    return _post(tc, tid, data)


def _exit_rows(cfg) -> list[tuple]:
    c = sqlite3.connect(str(cfg.paths.db_path))
    try:
        return c.execute(
            "SELECT fill_id, fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, price, quantity FROM fills "
            "WHERE action != 'entry' ORDER BY fill_id").fetchall()
    finally:
        c.close()


def _offered_order_ids(body: str) -> set[str]:
    return {v for k, v in _browser_form(body).items()
            if k.startswith("candidate_order_id_")}


def test_t6b_confirmed_non_default_pick_links_the_selected_order(world):
    """Orchestrator K7.3, the link; RD K3 (iv). o1 picked, the inputs left
    at o2's values, CONFIRMED. The top level names o1 with o1's own values,
    the typed o2 values ride in ``operator_corrected_value_json``, and the
    next form offers only o2. PRE-FIX: no confirm exists; the first POST
    writes top-level o2 with o2's values."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        fd["candidate_index"] = "0"
        r1 = _post(tc, world.tid, fd)
        assert r1.status_code == 400, r1.text[:500]
        assert _exit_rows(world.cfg) == []
        r2 = _confirm(tc, world.tid, r1.text)
        assert r2.status_code == 200, r2.text[:500]
        nxt = tc.get(f"/trades/{world.tid}/exit/form").text
    [(_fid, origin, env, corrected, price, qty)] = _exit_rows(world.cfg)
    persisted = json.loads(env)
    assert origin == "schwab_auto_then_operator_corrected"
    assert persisted["schwab_order_id"] == "o1"
    assert persisted["selected_candidate_order_id"] == "o1"
    assert (persisted["exit_date"], persisted["exit_price"],
            persisted["closed_shares"]) == ("2026-05-20", 130.0, 4)
    assert json.loads(corrected) == {
        "exit_date": "2026-05-21", "exit_price": 131.0, "closed_shares": 3}
    assert (price, qty) == (131.0, 3.0)
    assert _offered_order_ids(nxt) == {"o2"}


def test_t6c_confirmed_correction_keeps_the_id_and_a_stale_replay_is_refused(
        world):
    """Cell list 3, F2-B closed. o1 picked, typed 2026-05-21 / 129.50 / 4,
    confirmed: the id o1 is KEPT and the next form does not offer o1. Then
    the FIRST GET's form, o1 picked and o1's exact values retyped, posted
    with NO force: no flag fires and ``record_exit`` refuses it. PRE-FIX:
    the id is dropped, o1 re-offered unflagged, and the re-record succeeds
    (round-0 ``probe_f2b.json``)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        first = _form(tc, world.tid)
        fd = dict(first, candidate_index="0", exit_date="2026-05-21",
                  exit_price="129.50", shares="4")
        r1 = _post(tc, world.tid, fd)
        assert r1.status_code == 400, r1.text[:500]
        r2 = _confirm(tc, world.tid, r1.text)
        assert r2.status_code == 200, r2.text[:500]
        [(_fid, _o, env, _c, _p, _q)] = _exit_rows(world.cfg)
        assert json.loads(env)["schwab_order_id"] == "o1"
        assert "o1" not in _offered_order_ids(
            tc.get(f"/trades/{world.tid}/exit/form").text)
        replay = dict(first, candidate_index="0", exit_date="2026-05-20",
                      exit_price="130.00", shares="4")
        r3 = _post(tc, world.tid, replay)
    assert r3.status_code == 400, r3.text[:500]
    assert "already recorded" in r3.text
    assert len(_exit_rows(world.cfg)) == 1


def test_t6g_legacy_no_map_edit_is_reconfirmed_and_its_confirm_is_void(world):
    """Codex R3-01, as amended by executing FORK 3 (G1). A claimed envelope
    carrying only o2's top-level quartet (no ``candidates_map``), price
    edited. FIRST POST: 400, no fill, the refresh notice, NO flag text, the
    FRESH map-bearing anchor, the typed values kept, and a message saying
    nothing was recorded because the list must be re-confirmed. A plain
    resubmit on that fresh anchor is then asked F1 against the fresh
    selection. CONFIRM LEG: the ORIGINAL legacy submission re-posted with
    ``force`` and a test-built identity is VOID under d2. PRE-FIX: recorded
    corrected on the first POST. NULL killed: F1 gated on a map entry.

    SUPERSEDES, by replacement, the plan's first-leg text (a 400 carrying
    the F1 flag): FORK 3 drops a flag about a selection the form no longer
    carries."""
    from tests.web.test_routes.test_exit_rerender_anchor import (
        _NOTICE,
        _hidden,
        _input_attr,
    )
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _without_candidate_inputs(_form(tc, world.tid))
        env = _env(fd)
        del env["candidates_map"]
        legacy = dict(fd, schwab_source_value_json=json.dumps(
            env, sort_keys=True), exit_price="131.40")
        r1 = _post(tc, world.tid, legacy)
        assert r1.status_code == 400, r1.text[:500]
        body1 = _text(r1)
        assert "must be re-confirmed" in body1
        assert _NOTICE in body1
        assert "differ from order" not in body1
        assert "Confirm or retype" not in body1
        assert _acks(r1.text) == []
        assert "candidates_map" in json.loads(
            _hidden(r1.text, "schwab_source_value_json"))
        assert _input_attr(r1.text, "exit_price", "value") == "131.40"
        assert _exit_rows(world.cfg) == []
        r2 = _post(tc, world.tid, _browser_form(r1.text))
        assert r2.status_code == 400, r2.text[:500]
        assert ("differ from order o2's (2026-05-21, 131.00 x 3) in price."
                in _text(r2))
        r3 = _post(tc, world.tid, dict(
            legacy, force="true",
            acknowledged_flag="f1_matches_no_candidate|o2|2026-05-21|131.40|3"))
    assert r3.status_code == 400, r3.text[:500]
    assert _NOTICE in _text(r3)
    assert "the confirmation is void" in _text(r3)
    assert _exit_rows(world.cfg) == []


def test_t6h_confirm_leg_the_resolved_default_is_the_checked_radio(world):
    """Fork 2 addendum (RD's suggestion, adopted as REQUIRED): T6-h (i)'s
    flagged re-render checks o2's radio, and after the confirm the persisted
    selected hash is o2's and the top-level id is o2. Makes the coupling of
    the default radio and the top-level quartet a fact the suite holds."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        o2_hash = _hash_of(_env(fd), "o2")
        bare = _without_candidate_inputs(fd)
        r1 = _post(tc, world.tid, dict(bare, exit_price="131.40"))
        assert r1.status_code == 400, r1.text[:500]
        assert _checked_radios(r1.text) == ["1"]
        r2 = _confirm(tc, world.tid, r1.text)
    assert r2.status_code == 200, r2.text[:500]
    [(_fid, origin, env, _c, _p, _q)] = _exit_rows(world.cfg)
    persisted = json.loads(env)
    assert origin == "schwab_auto_then_operator_corrected"
    assert persisted["selected_candidate_signature_hash"] == o2_hash
    assert persisted["schwab_order_id"] == "o2"


# ------------------------------------------- executing FORK 1 (CHARC A1)
def test_fork1_ii_oversize_and_edited_is_refused_before_the_question(world):
    """Discriminator (ii): a claimed POST with shares over ``current_size``
    AND a price edited away from the selected entry -- an F1 trigger and a
    refusal at once. 400, "exceeds", NO confirm text and NO acknowledged-flag
    input, no fill. PRE-FIX (flags first): the confirm prompt renders and
    "exceeds" is absent."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        r = _post(tc, world.tid, dict(fd, shares="50", exit_price="131.40"))
    assert r.status_code == 400, r.text[:500]
    assert "exceeds" in r.text
    assert "Confirm or retype" not in r.text
    assert "differ from order" not in _text(r)
    assert _acks(r.text) == []
    assert 'name="force"' not in r.text
    assert _exit_rows(world.cfg) == []


def test_fork1_iii_one_spelling_called_from_both_sites(world, monkeypatch):
    """Discriminator (iii), the one-spelling pin: ``check_exit_preconditions``
    is called from BOTH sites on an accepted POST (route, then
    ``record_exit`` under its lock) and from the ROUTE ONLY on a refused one
    (``record_exit`` never entered). Patched where each site resolves the
    name. NULL killed: A2 (a route-side copy) and any later inline
    comparison against ``current_size``."""
    sites: list[str] = []
    real = exit_mod.check_exit_preconditions

    def at(site):
        def spy(trade, req):
            sites.append(site)
            return real(trade, req)
        return spy

    monkeypatch.setattr(routes_mod, "check_exit_preconditions", at("route"),
                        raising=False)
    monkeypatch.setattr(exit_mod, "check_exit_preconditions", at("service"))
    entered: list[int] = []
    real_record = exit_mod.record_exit

    def record_spy(conn, req):
        entered.append(1)
        return real_record(conn, req)

    monkeypatch.setattr(routes_mod, "record_exit", record_spy)
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        refused = _post(tc, world.tid, dict(_form(tc, world.tid), shares="50"))
        assert refused.status_code == 400, refused.text[:500]
        assert "exceeds" in refused.text
        assert sites == ["route"] and entered == []
        sites.clear()
        ok = _post(tc, world.tid, _form(tc, world.tid))
    assert ok.status_code == 200, ok.text[:500]
    assert sites == ["route", "service"] and entered == [1]


# ------------------------------------------------- RA-02 (Reviewer A R2)
def test_ra02_an_explicit_selection_on_a_map_less_claim_is_reconfirmed(world):
    """Fork RA-02, branch A (orchestrator): a claimed envelope with NO
    ``candidates_map`` (top-level o2) carrying an explicit selection
    (``candidate_index=0``, hash and order id o1), the typed values left at
    o2's. The server cannot resolve the pick against any list, so it is NOT
    synthesized: the Fork 3 G1 response -- 400, the refresh notice, the
    FRESH map-bearing anchor, the typed values kept, nothing recorded --
    even though the typed values derive from the top-level quartet.
    PRE-FIX: 200, one fill whose top level is o2 while
    ``selected_candidate_order_id`` claims o1."""
    from tests.web.test_routes.test_exit_rerender_anchor import (
        _NOTICE,
        _hidden,
        _input_attr,
    )
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        env = _env(fd)
        o1_hash = _hash_of(env, "o1")
        del env["candidates_map"]
        legacy = {k: v for k, v in fd.items()
                  if not k.startswith("candidate_")}
        legacy.update(schwab_source_value_json=json.dumps(env, sort_keys=True),
                      candidate_index="0", candidate_signature_hash_0=o1_hash,
                      candidate_order_id_0="o1")
        assert (legacy["exit_date"], legacy["exit_price"],
                legacy["shares"]) == ("2026-05-21", "131.00", "3")
        r = _post(tc, world.tid, legacy)
    assert r.status_code == 400, r.text[:500]
    body = _text(r)
    assert "must be re-confirmed" in body
    assert _NOTICE in body
    assert _acks(r.text) == []
    assert "candidates_map" in json.loads(
        _hidden(r.text, "schwab_source_value_json"))
    assert _input_attr(r.text, "exit_price", "value") == "131.00"
    assert _exit_rows(world.cfg) == []


# ------------------------------------------------- RA-03 (Reviewer A R2)
def test_ra03_an_omitted_radio_on_a_multi_entry_map_is_no_selection(world):
    """RA-03 (the Fork RA-02 ruling's note): index 0 is inferred only for a
    ONE-entry map. A two-candidate form with ONLY ``candidate_index``
    removed (every per-candidate hidden input kept) is a no-selection
    submission and takes the Fork D79-A-01 resolution: the selected entry
    is the visible default's map entry (o2).
    PRE-FIX: index 0 is inferred, so o1 is the selected entry and the
    unedited o2 values are asked F1 (400, no fill)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        assert "candidate_signature_hash_0" in fd
        assert "candidate_signature_hash_1" in fd
        fd.pop("candidate_index")
        r = _post(tc, world.tid, fd)
    assert r.status_code == 200, r.text[:500]
    [(_fid, origin, env, _c, _p, _q)] = _exit_rows(world.cfg)
    assert origin == "schwab_auto"
    assert json.loads(env)["schwab_order_id"] == "o2"


# ------------------------------------------------- D79-A-02 (Reviewer A R3)
_HUGE_INT = 10 ** 400  # a JSON int ``float()`` cannot hold: OverflowError


def test_a02_a_huge_int_top_level_price_is_not_well_formed(world):
    """D79-A-02, caller one (tier (d)): a claimed envelope whose top-level
    ``exit_price`` is a 401-digit JSON int. ``json.loads`` parses it as an
    int and ``float()`` overflows. It is NOT well formed: 400 with tier
    (d)'s text, the anchor cleared, no fill. PRE-FIX: the predicate's
    ``float()`` raised ``OverflowError`` -- a 500."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        env = _env(fd)
        env["exit_price"] = _HUGE_INT
        r = _post(tc, world.tid, dict(
            fd, schwab_source_value_json=json.dumps(env, sort_keys=True)))
    assert r.status_code == 400, r.text[:500]
    assert "contains invalid values" in r.text
    assert _exit_rows(world.cfg) == []


def test_a02_a_huge_int_selected_entry_price_is_not_well_formed(world):
    """D79-A-02, caller two (the selected-entry check): o1 picked, and o1's
    map entry carries a 401-digit JSON int price; the top level is o2's,
    well formed. 400 with the selected-entry text, no fill. PRE-FIX: a
    500 (``OverflowError`` from the same predicate)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        env = _env(fd)
        env["candidates_map"][_hash_of(env, "o1")]["price"] = _HUGE_INT
        r = _post(tc, world.tid, dict(
            fd, candidate_index="0",
            schwab_source_value_json=json.dumps(env, sort_keys=True)))
    assert r.status_code == 400, r.text[:500]
    assert "the selected auto-fill candidate carries invalid values" in r.text
    assert _exit_rows(world.cfg) == []



# ------------------------------------------------- A-F02 (Reviewer A R4)
def test_af02_a_huge_int_top_level_quantity_is_not_well_formed(world):
    """A-F02, caller one (tier (d)): the top-level ``closed_shares`` is a
    401-digit JSON int. The quantity is held to the price's bound -- an int
    that cannot convert to a finite float is NOT well formed: 400 with tier
    (d)'s text, no fill. PRE-FIX (measured): ``isinstance(int)`` alone
    passed it, tier (d) did not fire, the form's checked radio selected an
    entry whose values then REPLACED the tampered top level, and the POST
    recorded -- 200, so red. A tampered anchor is refused at the ladder, as
    a huge-int price already is (D79-A-02)."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        env = _env(fd)
        env["closed_shares"] = _HUGE_INT
        r = _post(tc, world.tid, dict(
            fd, schwab_source_value_json=json.dumps(env, sort_keys=True)))
    assert r.status_code == 400, r.text[:500]
    assert "contains invalid values" in r.text
    assert _exit_rows(world.cfg) == []


def test_af02_a_huge_int_selected_entry_quantity_is_not_well_formed(world):
    """A-F02, caller two (the selected-entry check): o1 picked, and o1's map
    entry carries a 401-digit JSON int ``quantity``. 400 with the
    selected-entry text, no fill. PRE-FIX: the entry passed the check and
    the POST was asked F1 instead (``derives_from`` catches the overflow and
    reads it as not deriving) -- the selected-entry text absent, so red."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        env = _env(fd)
        env["candidates_map"][_hash_of(env, "o1")]["quantity"] = _HUGE_INT
        r = _post(tc, world.tid, dict(
            fd, candidate_index="0",
            schwab_source_value_json=json.dumps(env, sort_keys=True)))
    assert r.status_code == 400, r.text[:500]
    assert "the selected auto-fill candidate carries invalid values" in r.text
    assert _exit_rows(world.cfg) == []


# ------------------------------------------------- D79-A-03 (Reviewer A R3)
def test_a03_a_huge_integer_share_count_is_refused_as_exceeds(world):
    """D79-A-03, the caller: a POST whose ``shares`` is a 401-digit integer
    reaches the route's precheck and gets the existing "exceeds" refusal
    re-render (400), never a 500, and records nothing. PRE-FIX: the
    helper's ``float(req.shares)`` raised ``OverflowError`` out of the
    route -- a 500."""
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        fd = _form(tc, world.tid)
        r = _post(tc, world.tid, dict(fd, shares=str(_HUGE_INT)))
    assert r.status_code == 400, r.text[:500]
    assert "exceeds remaining current_size" in r.text
    assert _exit_rows(world.cfg) == []
