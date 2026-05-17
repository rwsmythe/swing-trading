"""Post-Phase-12 Sub-bundle 2 Task T-2.2 — schwab_status.html.j2 template tests.

Per plan §B T-2.2 acceptance criteria (10 discriminating tests) + dispatch
brief §0.5 BINDING contracts:
- #8 Jinja2 autoescape preservation (`<script>` planted in state_reason →
  literal NOT in response + HTML-entity-escaped DOES appear).
- #7 sentinel-leak audit per Phase 11 Sub-bundle A T-A.10 D1 redaction
  (mirror of T-2.1 test 13 via template render).

State-condition seeding pattern (mirrors T-2.1's tests but with explicit
LIVE/PROVISIONAL/DEGRADED targeting):
- LIVE: fresh tokens DB on disk + valid refresh_token_issued (today) +
  most-recent call status='success'.
- PROVISIONAL: tokens DB MISSING on disk (signal 1).
- DEGRADED: tokens DB present + refresh_token_issued > 7 days ago
  (signal 7 — refresh_token expired).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from swing.web.app import create_app


def _isolate_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))


def _seed_tokens_db_live(tmp_path, env: str) -> None:
    """Plant a tokens DB that yields state='LIVE' from
    `_compute_degraded_state` — fresh refresh_token_issued + valid bytes."""
    swing_data = tmp_path / "swing-data"
    swing_data.mkdir(parents=True, exist_ok=True)
    tokens_path = swing_data / f"schwab-tokens.{env}.db"
    now_iso = datetime.now(UTC).isoformat()
    payload = {
        "access_token_issued": now_iso,
        "refresh_token_issued": now_iso,
        "token_dictionary": {
            "access_token": "abc-access",
            "refresh_token": "abc-refresh",
            "id_token": "abc-id",
            "expires_in": 1800,
        },
    }
    tokens_path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_tokens_db_degraded(tmp_path, env: str) -> None:
    """Plant a tokens DB that yields state='DEGRADED' — refresh_token_issued
    8 days ago (signal 7 in `_compute_degraded_state`)."""
    swing_data = tmp_path / "swing-data"
    swing_data.mkdir(parents=True, exist_ok=True)
    tokens_path = swing_data / f"schwab-tokens.{env}.db"
    eight_days_ago = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    payload = {
        "access_token_issued": eight_days_ago,
        "refresh_token_issued": eight_days_ago,
        "token_dictionary": {
            "access_token": "abc-access",
            "refresh_token": "abc-refresh",
            "id_token": "abc-id",
            "expires_in": 1800,
        },
    }
    tokens_path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_successful_call(db_path, env: str) -> None:
    """Plant a single success call so LIVE-state Signal 9 stays satisfied."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO schwab_api_calls "
            "(ts, endpoint, http_status, status, surface, environment) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.now(UTC).isoformat(timespec="milliseconds"),
                "accounts.orders.list", 200, "success", "cli", env,
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# (1) Template extends base layout.
# ---------------------------------------------------------------------------

def test_template_extends_base_layout(seeded_db, monkeypatch, tmp_path):
    """Test 1 — base.html.j2's nav present in rendered response."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    # Topbar nav from base.html.j2 — Dashboard link is a stable anchor.
    assert '<nav class="topbar">' in r.text
    assert '<a href="/">Dashboard</a>' in r.text


# ---------------------------------------------------------------------------
# (2) State LIVE → green indicator.
# ---------------------------------------------------------------------------

def test_state_live_renders_green_indicator(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 2 — fresh tokens DB + successful call → LIVE badge with
    class='state-ok' AND data-state='LIVE'."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    _seed_tokens_db_live(tmp_path, "production")
    _seed_successful_call(cfg.paths.db_path, "production")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    assert 'data-state="LIVE"' in r.text
    assert 'state-ok' in r.text


# ---------------------------------------------------------------------------
# (3) State PROVISIONAL → warn indicator + state_reason text.
# ---------------------------------------------------------------------------

def test_state_provisional_renders_warn_indicator_with_reason(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 3 — tokens DB missing on disk → PROVISIONAL badge with
    class='state-warn' AND data-state='PROVISIONAL' AND state_reason text
    rendered next to badge."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    # NO _seed_tokens_db call → signal 1 (tokens DB missing) → PROVISIONAL.
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    assert 'data-state="PROVISIONAL"' in r.text
    assert 'state-warn' in r.text
    # state_reason from _compute_degraded_state signal 1.
    assert "tokens DB missing" in r.text


# ---------------------------------------------------------------------------
# (4) State DEGRADED → error indicator + state_reason text.
# ---------------------------------------------------------------------------

def test_state_degraded_renders_error_indicator_with_reason(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 4 — refresh_token issued 8 days ago → DEGRADED badge with
    class='state-error' AND data-state='DEGRADED' AND state_reason text."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    _seed_tokens_db_degraded(tmp_path, "production")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    assert 'data-state="DEGRADED"' in r.text
    assert 'state-error' in r.text
    # state_reason from _compute_degraded_state signal 7.
    assert "refresh_token expired" in r.text


# ---------------------------------------------------------------------------
# (5) Refresh-token TTL countdown.
# ---------------------------------------------------------------------------

def test_refresh_token_ttl_countdown_renders(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 5 — refresh-token expires_at + days-remaining text surfaces
    under the 'Refresh token' dt label."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    _seed_tokens_db_live(tmp_path, "production")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    assert "Refresh token" in r.text
    # Fresh tokens DB → days-remaining text + 'expires' substring.
    assert "days remaining" in r.text
    assert "expires" in r.text


# ---------------------------------------------------------------------------
# (6) Recent-calls table present.
# ---------------------------------------------------------------------------

def test_recent_calls_table_present(seeded_db, monkeypatch, tmp_path):
    """Test 6 — <table> element + endpoint column header rendered."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    _seed_successful_call(cfg.paths.db_path, "production")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    assert 'data-table="schwab-recent-calls"' in r.text
    assert "<th>Endpoint</th>" in r.text
    # Seeded call's endpoint surfaces in a row.
    assert "accounts.orders.list" in r.text


# ---------------------------------------------------------------------------
# (7) Environment switcher links.
# ---------------------------------------------------------------------------

def test_environment_switcher_links_rendered(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 7 — both ?environment=production AND ?environment=sandbox
    links rendered for env-toggling."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    assert 'href="/schwab/status?environment=production"' in r.text
    assert 'href="/schwab/status?environment=sandbox"' in r.text


# ---------------------------------------------------------------------------
# (8) Re-auth link `/schwab/setup` present when PROVISIONAL OR DEGRADED.
# ---------------------------------------------------------------------------

def test_reauth_link_present_when_provisional(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 8a — PROVISIONAL state → re-auth link to /schwab/setup."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    # NO tokens DB → PROVISIONAL.
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    assert 'data-link="schwab-reauth"' in r.text
    assert 'href="/schwab/setup"' in r.text


def test_reauth_link_absent_when_live(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 8b (mirror of 8a) — LIVE state → re-auth link is ABSENT.

    Discriminating: a future fork that rendered the link unconditionally
    would clutter the LIVE-state page with a misleading "re-authorize"
    affordance even when the integration is healthy."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    _seed_tokens_db_live(tmp_path, "production")
    _seed_successful_call(cfg.paths.db_path, "production")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    assert 'data-link="schwab-reauth"' not in r.text


# ---------------------------------------------------------------------------
# (9) Autoescape regression.
# ---------------------------------------------------------------------------

def test_autoescape_state_reason_html_payload(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 9 (BINDING #8 — Jinja2 autoescape preservation) — plant
    `<script>alert(1)</script>` into the state_reason rendering surface;
    assert literal `<script>` does NOT appear in response + HTML-entity-
    escaped `&lt;script&gt;` DOES appear.

    Approach: monkeypatch `_compute_degraded_state` (the source of
    `state_reason`) to return an attacker-controlled HTML payload. This
    discriminates whether the template autoescapes the field — a future
    fork that used `{{ vm.state_reason | safe }}` (or templating against
    a non-autoescape file extension) would render the literal script
    tag and the browser would execute it."""
    import swing.cli_schwab as cli_schwab
    payload = "<script>alert(1)</script>"
    monkeypatch.setattr(
        cli_schwab, "_compute_degraded_state",
        lambda *_args, **_kwargs: ("DEGRADED", payload),
    )

    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    # Literal `<script>` NOT in body (autoescape effective).
    assert "<script>alert(1)</script>" not in r.text
    # HTML-entity-escaped DOES appear (proof autoescape ran).
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in r.text


# ---------------------------------------------------------------------------
# (10) Sentinel-leak audit (mirror T-2.1 test 13 via this template path).
# ---------------------------------------------------------------------------

def test_sentinel_leak_audit_via_template(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 10 (BINDING #7 — mirror of T-2.1 test 13 + plan §B T-2.2
    test #10) — plant sentinels into BOTH tokens DB AND a
    schwab_api_calls.error_message row; assert ZERO substring matches
    via the template's rendered response body. Defense-in-depth: T-2.1
    test 13 covers the route surface; T-2.2 test 10 covers the template
    surface as a separate ratchet.

    Codex R3 Minor #1 strengthening: prior version planted token-file
    sentinels only; plan §B T-2.2 test #10 requires both tokens DB
    AND audit error_message row sentinels.
    """
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    sentinels = [
        "LEAK_TPL_TOKEN_BYTES_ACCESS_SENTINEL",
        "LEAK_TPL_TOKEN_BYTES_REFRESH_SENTINEL",
        "LEAK_TPL_TOKEN_BYTES_ID_SENTINEL",
        "LEAK_TPL_AUDIT_ERROR_MESSAGE_SENTINEL",
    ]
    swing_data = tmp_path / "swing-data"
    swing_data.mkdir(parents=True, exist_ok=True)
    tokens_path = swing_data / "schwab-tokens.production.db"
    now_iso = datetime.now(UTC).isoformat()
    payload = {
        "access_token_issued": now_iso,
        "refresh_token_issued": now_iso,
        "token_dictionary": {
            "access_token": sentinels[0],
            "refresh_token": sentinels[1],
            "id_token": sentinels[2],
            "expires_in": 1800,
        },
    }
    tokens_path.write_text(json.dumps(payload), encoding="utf-8")
    # Plant the audit-row sentinel (the route test plants under
    # 'production' env; planting here too preserves the per-test
    # isolation contract; the template test's seeded_db is also fresh).
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        conn.execute(
            "INSERT INTO schwab_api_calls "
            "(ts, endpoint, http_status, status, error_message, "
            " surface, environment) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-05-17T12:00:00.000+00:00",
                "accounts.orders.list", 401, "auth_failed",
                sentinels[3], "cli", "production",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    for sentinel in sentinels:
        assert sentinel not in r.text, (
            f"sentinel-leak in template render: {sentinel!r} found in "
            "response body — VM/template surfaced raw token bytes OR "
            "an unredacted audit-row sentinel"
        )
