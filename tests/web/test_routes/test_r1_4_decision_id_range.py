"""Codex R1-4 (sg-label exec round 1), web half: a decision-night id outside
SQLite's signed 64-bit INTEGER range is the ladder's refusal (T2's 400 on a
non-latched entry), never an unbound ``OverflowError`` (a 500)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app
from tests.web.test_routes.test_d86_entry_raw_rung import _data, _world, _written


@pytest.mark.parametrize("big", [2 ** 63, -(2 ** 63) - 1])
def test_r1_4_an_out_of_range_night_id_is_the_ladder_400(
        seeded_db, monkeypatch, big):
    """The id is BOTH the choice and in the anchor, so the earlier rungs
    (not an integer, not in the offered set) pass and only the bound read
    would meet it -- Codex's reproduction."""
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    anchor = [{"candidate_id": big, "evaluation_run_id": 900, "label": None}]
    choice = str(big)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as client:
        resp = client.post(
            "/trades/entry",
            data=_data("", claimed=False,
                       decision_nights_anchor=json.dumps(anchor),
                       decision_candidate_id=choice),
            headers={"HX-Request": "true"})
    assert resp.status_code == 400, (resp.status_code, resp.text[:300])
    assert "decision-night anchor" in resp.text
    assert _written(cfg) == []
