"""Template rendering: rows, source badges, reset forms, no-<tr>-root partial."""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from swing.config import load
from swing.config_user import write_user_overrides
from swing.web.app import create_app
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    cfg = load(cfg_path)
    app = create_app(cfg, cfg_path=cfg_path)
    with TestClient(app) as c:
        yield c


def test_template_renders_all_three_rows(client: TestClient):
    r = client.get("/config")
    body = r.text
    for label in ("Chase factor", "Watchlist chart count", "Risk floor"):
        assert label in body


def test_template_source_badge_default_when_no_overrides(client: TestClient):
    """At least 2 rows render source-default; risk_equity_floor renders source-tracked.

    The shared `_write_cfg` fixture sets `account.risk_equity_floor = 5000.0`
    in the project config, which differs from the FIELD_REGISTRY default
    (7500.0). So with no user overrides applied:
      - web.chase_factor (0.01)              -> source-default (matches default)
      - pipeline.chart_top_n_watch (10)      -> source-default (matches default)
      - account.risk_equity_floor (5000.0)   -> source-tracked (project-config override)
    Adjusted from the plan's `>= 3` to reflect actual fixture state.
    """
    r = client.get("/config")
    assert r.text.count("source-default") >= 2
    assert "source-tracked" in r.text


def test_template_source_badge_override_when_user_config_present(client: TestClient):
    write_user_overrides({"web": {"chase_factor": 0.02}})
    r = client.get("/config")
    assert "source-override" in r.text


def test_template_each_row_has_separate_reset_form(client: TestClient):
    r = client.get("/config")
    # Three reset-form occurrences (one per V1 field).
    assert r.text.count('class="reset-form"') == 3


def test_template_renders_schwab_setup_link(client: TestClient):
    """Orchestrator-inline gate-fix 2026-05-15 — operator-surfaced UX gap
    during Phase 12 Sub-bundle B operator-witnessed gate: /schwab/setup
    was reachable only by typing the URL. This discriminating test pins
    the presence of the link to /schwab/setup so future template edits
    don't silently regress the operator-discoverable navigation path.

    Pre-fix shape: response body lacks any reference to /schwab/setup.
    Post-fix shape: response body contains href="/schwab/setup" inside
    an 'External integrations' section.
    """
    r = client.get("/config")
    body = r.text
    assert 'href="/schwab/setup"' in body
    assert "External integrations" in body


def test_soft_warn_fragment_root_is_not_tr(client: TestClient):
    """CLAUDE.md HTMX <tr>-leading makeFragment guard.

    Codex R1 Minor 2 — this server-side assertion ONLY proves the
    response payload's first non-whitespace token is not '<tr'. It does
    NOT exercise htmx.js makeFragment parsing. The CANONICAL guard for
    the <tr>-leading pathology (failure mode 2026-04-29) is the operator-
    witnessed browser smoke in Task 7.0 step 4 — TestClient cannot
    detect a parser-mangled OOB swap because it only sees the response
    bytes, not the post-parse DOM. Treat this test as a structural
    sanity check, not a sufficient guard.
    """
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.05",
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
        },
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert not r.text.lstrip().startswith("<tr")
    # Form-values round-trip: the iterator emits hidden inputs.
    assert 'name="web.chase_factor"' in r.text
    assert 'value="0.05"' in r.text


def test_nav_link_present_on_dashboard(client: TestClient):
    """Static nav link added in base.html.j2.

    Verified via /config (which extends base.html.j2) rather than /
    because the dashboard route requires a migrated DB and this test
    only cares about the base-layout nav. The nav block is shared
    across every page that extends base.html.j2, so any base-extending
    route will surface a regression.
    """
    r = client.get("/config")
    assert 'href="/config"' in r.text


def test_saved_banner_renders_when_saved_query_set(client: TestClient):
    r = client.get("/config?saved=1")
    assert "Saved" in r.text or "saved" in r.text
