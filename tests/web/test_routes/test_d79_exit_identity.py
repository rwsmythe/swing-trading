"""D79 -- the exit route records the SELECTED broker order's link, once.

Plan: ``docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md``
(T1-c route half, T5, T6). The world is ``test_exit_rerender_anchor.py``'s
``world`` fixture: o1 = 2026-05-20 130.00 x 4, o2 = 2026-05-21 131.00 x 3,
o2 the default at index 1; the trade holds 10 shares.
"""
from __future__ import annotations

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
