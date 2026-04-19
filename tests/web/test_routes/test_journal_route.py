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
    # Post-Task-7: `period: Literal[...]` produces a RequestValidationError.
    # A bare client (no HX-Request, no Accept: text/html) falls through to
    # FastAPI's default 422 JSON response per spec §3.3 precedence rule.
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/journal?period=fortnight")
    assert r.status_code in (400, 422, 500)


def test_journal_bad_period_htmx_returns_div_fragment(test_cfg, seeded_db):
    """HTMX GET /journal?period=<bad> → 400 <div> fragment (HX-Target absent)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/journal?period=fortnight",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert "<div" in r.text.lower()
    assert "period" in r.text.lower()
    assert "<tr" not in r.text.lower()


def test_journal_bad_period_nonhtmx_html_renders_page(test_cfg, seeded_db):
    """Non-HTMX GET with Accept: text/html → full-page 400, not 500."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/journal?period=fortnight",
            headers={"Accept": "text/html,application/xhtml+xml,*/*"},
        )
    assert r.status_code == 400
    assert "<html" in r.text.lower()
    assert "period" in r.text.lower()


def test_journal_happy_path_unchanged(test_cfg, seeded_db):
    """Valid period still renders the journal page."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=month")
    assert r.status_code == 200
