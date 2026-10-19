"""D79 -- the exit route records the SELECTED broker order's link, once.

Plan: ``docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md``
(T1-c route half, T5, T6). The world is ``test_exit_rerender_anchor.py``'s
``world`` fixture: o1 = 2026-05-20 130.00 x 4, o2 = 2026-05-21 131.00 x 3,
o2 the default at index 1; the trade holds 10 shares.
"""
from __future__ import annotations

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
