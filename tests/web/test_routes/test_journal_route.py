"""GET /journal route."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_get_journal_default_period(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal")
    assert r.status_code == 200
    assert "Journal" in r.text


def test_get_journal_with_period(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=week")
    assert r.status_code == 200
    # Either the label "Last 7d" or "week" substring should appear in nav links.
    assert "week" in r.text.lower() or "Last 7d" in r.text


def test_get_journal_invalid_period(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    # raise_server_exceptions=False lets us observe the 500 response instead of
    # having TestClient re-raise the ValueError.
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/journal?period=fortnight")
    assert r.status_code == 500 or r.status_code == 400
