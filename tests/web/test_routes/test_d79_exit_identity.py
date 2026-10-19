"""D79 -- the exit route records the SELECTED broker order's link, once.

Plan: ``docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md``
(T1-c route half, T5, T6). The world is ``test_exit_rerender_anchor.py``'s
``world`` fixture: o1 = 2026-05-20 130.00 x 4, o2 = 2026-05-21 131.00 x 3,
o2 the default at index 1; the trade holds 10 shares.
"""
from __future__ import annotations

import html
import json

from fastapi.testclient import TestClient

import swing.web.routes.trades as routes_mod
from swing.trades import exit as exit_mod
from swing.web.app import create_app
from tests.web.test_routes.test_exit_rerender_anchor import (  # noqa: F401
    _browser_form,
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


def test_t6h_multi_entry_map_with_no_selection_synthesizes_the_default(world):
    """Fork 2 (orchestrator): a claimed multi-entry envelope, top-level o2,
    NO candidate inputs. The route synthesizes the selected entry from the
    top-level quartet. (i) price edited -> F1 NO_CANDIDATE naming price;
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
