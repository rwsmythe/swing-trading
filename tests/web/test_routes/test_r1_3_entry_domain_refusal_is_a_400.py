"""Codex R1-3 (sg-label exec round 1): the D86 entry-domain refusals reach
the web route as a typed error and render the standing 400 re-render, never
a 500.

The inputs are tamper/cURL-only (a browser's ``type=date`` / ``type=number``
cannot post them), but a refusal the system means to make is a 400 with the
form handed back, not an unhandled exception.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app
from tests.web.test_routes.test_d86_entry_raw_rung import _data, _world, _written


@pytest.mark.parametrize(("field", "value", "text"), [
    ("entry_price", "inf", "finite number"),
    ("entry_date", "20261019", "canonical form"),
    ("entry_date", "2026-W01-1", "canonical form"),
])
def test_r1_3_an_entry_domain_refusal_is_a_400_with_the_form(
        seeded_db, monkeypatch, field, value, text):
    cfg, cfg_path = seeded_db
    _world(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as client:
        resp = client.post("/trades/entry",
                           data=_data("", claimed=False, **{field: value}),
                           headers={"HX-Request": "true"})
    assert resp.status_code == 400, (resp.status_code, resp.text[:300])
    assert text in resp.text
    assert 'name="thesis"' in resp.text, "the form is handed back"
    assert _written(cfg) == []
