"""22-F T-A8, C1-16 -- the RED ATTEMPT (plan section 2, T-A8 row C1-16).

`DecisionIntentsUnavailableError` is raised by `swing/latches/reader.py`'s
`load_decision_intents` in STRICT mode when a `list_intents_for_latch` read
fails (22-F plan section 1.2 row 1).  The attempt: drive `POST /latches/view`
and `POST /latches/intent` with that read planted to raise
`sqlite3.OperationalError("database is locked")` and observe whether anything
escapes.

Patch target: `swing.data.repos.latch_order_intents.list_intents_for_latch`
-- `reader.py` imports it FUNCTION-LOCALLY, so the module attribute is re-read
on every call.  Did-it-fire: a counting wrapper, asserted called >= 1.

These pin the OBSERVED outcome on this tree (the attempt's result is recorded
in the T-A8 commit and the exec ledger): neither route escapes, because both
reach the reader in its DEFAULT, non-strict mode, which degrades the failed
read to "no decision evidence" with a WARNING.
"""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from swing.web.app import create_app
from tests._22f_proxies import raising
from tests.web.test_latches_telemetry_beacon import ANCHOR, _seed_ftre
from tests.web.test_latches_telemetry_beacon import (  # noqa: F401
    frozen_clocks,
)
from tests.web.test_routes.test_latches_intent_route import (
    _anchor_form,
)
from tests.web.test_routes.test_latches_intent_route import (
    _seed as _seed_intent_world,
)

_HX = {"HX-Request": "true"}
_TARGET = "swing.data.repos.latch_order_intents.list_intents_for_latch"


def _plant(monkeypatch):
    planted = raising(sqlite3.OperationalError("database is locked"))
    monkeypatch.setattr(_TARGET, planted)
    return planted


def test_C1_16_view_beacon_read_failure_does_not_escape(
        seeded_db, frozen_clocks, monkeypatch):
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    planted = _plant(monkeypatch)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    assert planted.calls >= 1  # did-it-fire
    assert r.status_code == 204, (r.status_code, r.text[:300])


def test_C1_16_intent_read_failure_does_not_escape(
        seeded_db, frozen_clocks, monkeypatch):
    cfg, cfg_path = seeded_db
    cid = _seed_intent_world(cfg)
    form = _anchor_form(cfg, cid) | {"intent_kind": "place"}
    planted = _plant(monkeypatch)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as client:
        r = client.post("/latches/intent", headers=_HX, data=form)
    assert planted.calls >= 1  # did-it-fire
    assert r.status_code < 500, (r.status_code, r.text[:300])
