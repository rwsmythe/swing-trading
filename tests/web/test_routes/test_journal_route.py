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


def test_get_journal_invalid_period_clamps_to_default(seeded_db):
    # Phase 14 SB4 Slice 2: `period` is now a plain str; build_journal clamps
    # an unknown value to the default 'month'. A bad period renders the page
    # (200), no longer a framework 422.
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=fortnight")
    assert r.status_code == 200
    assert "Journal" in r.text


def test_journal_bad_period_htmx_renders_200(test_cfg, seeded_db):
    """Slice 2: HTMX GET /journal?period=<bad> clamps + renders 200 (no 4xx)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/journal?period=fortnight",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200


def test_journal_bad_period_nonhtmx_html_renders_200(test_cfg, seeded_db):
    """Slice 2: non-HTMX HTML GET with a bad period clamps + renders 200."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/journal?period=fortnight",
            headers={"Accept": "text/html,application/xhtml+xml,*/*"},
        )
    assert r.status_code == 200
    assert "<html" in r.text.lower()


def test_journal_bad_page_param_still_422(seeded_db):
    """Slice 2: page/page_size remain typed ints — a non-int value still 422s
    (only `period` was loosened to str)."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?page=notanint")
    assert r.status_code == 422


def test_journal_happy_path_unchanged(test_cfg, seeded_db):
    """Valid period still renders the journal page."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=month")
    assert r.status_code == 200
