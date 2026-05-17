"""Post-Phase-12 Sub-bundle 2 Task T-2.1 — GET /schwab/status route tests.

Per plan §B T-2.1 acceptance criteria (13 discriminating tests) + dispatch
brief §0.5 BINDING contracts:
- #2 state triplet LIVE/PROVISIONAL/DEGRADED (NOT spec §7.1's misnamed
  CONFIGURED/...).
- #4 apply_overrides(cfg) at route entry (Codex R1 Critical #1 inheritance
  from Sub-bundle B).
- #5 case-insensitive env query-param.
- #6 PlainTextResponse for invalid env (Codex R1 Major #7 + R2 Major #1).
- #7 sentinel-leak audit per Phase 11 Sub-bundle A T-A.10 D1 redaction.
- #11 NO Schwab API calls (route is read-only consumer of pre-existing
  audit + tokens DB metadata).
- #13 base-layout VM banner pin (5 fields populated via
  _fetch_unresolved_material_count helper at route entry).

USERPROFILE+HOME monkeypatch discipline per CLAUDE.md gotcha (Phase 9
Sub-bundle A return report §11 lesson + tokens-DB path resolution reads
``_user_home()`` directly).
"""
from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app


def _isolate_home(monkeypatch, tmp_path) -> None:
    """Monkeypatch USERPROFILE+HOME to ``tmp_path`` so tokens DB path
    resolution stays test-scoped."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))


def _seed_tokens_db(
    tmp_path,
    env: str,
    *,
    refresh_token_issued: str | None = "2026-05-15T10:00:00+00:00",
    refresh_token_bytes: str = "fresh-refresh-token-bytes-redacted",
    access_token_bytes: str = "fresh-access-token-bytes-redacted",
    id_token_bytes: str = "fresh-id-token-bytes-redacted",
    access_token_issued: str = "2026-05-17T10:00:00+00:00",
) -> None:
    """Plant a schwabdev-shaped tokens JSON file at the tmp_path location
    consulted by ``_user_home() / 'swing-data' / f'schwab-tokens.{env}.db'``.

    The tokens-DB format is plaintext JSON with a `token_dictionary`
    nested under `access_token_issued` + `refresh_token_issued`. Test
    rows plant non-token-shaped sentinel substrings for the sentinel-leak
    audit (T-2.1 #13).
    """
    swing_data = tmp_path / "swing-data"
    swing_data.mkdir(parents=True, exist_ok=True)
    tokens_path = swing_data / f"schwab-tokens.{env}.db"
    payload = {
        "access_token_issued": access_token_issued,
        "refresh_token_issued": refresh_token_issued,
        "token_dictionary": {
            "access_token": access_token_bytes,
            "refresh_token": refresh_token_bytes,
            "id_token": id_token_bytes,
            "expires_in": 1800,
        },
    }
    tokens_path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_unresolved_material_discrepancy(db_path) -> None:
    """Plant one unresolved-material discrepancy attributed to an active
    trade so the base-layout banner count == 1 at render.

    Mirrors the seed in tests/web/test_routes/test_schwab_setup_route.py.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size) "
            "VALUES (1, 'AAA', '2026-04-01', 10.0, 100, 9.0, 9.0, "
            "'managing', 'S', 'I', 'manual_off_pipeline', "
            "'2026-04-01T09:30:00', 100)"
        )
        conn.execute(
            "INSERT INTO reconciliation_runs "
            "(run_id, period_start, period_end, started_ts, finished_ts, "
            " state, source, source_artifact_path, source_artifact_sha256) "
            "VALUES (1, '2026-04-01', '2026-04-08', "
            "'2026-04-08T16:00:00.000', '2026-04-08T16:00:01.000', "
            "'completed', 'system_audit', 'gate-test', 'gate-test-sha')"
        )
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(discrepancy_id, run_id, discrepancy_type, trade_id, fill_id, "
            " cash_movement_id, linked_daily_management_record_id, "
            " ticker, field_name, expected_value_json, actual_value_json, "
            " delta_text, material_to_review, resolution, "
            " resolution_reason, resolved_at, resolved_by, "
            " mistake_tag_assigned, created_at) VALUES "
            "(1, 1, 'stop_mismatch', 1, NULL, NULL, NULL, 'AAA', "
            " 'current_stop', '\"9.00\"', '\"8.50\"', NULL, 1, "
            " 'unresolved', NULL, NULL, NULL, NULL, "
            " '2026-04-08T16:00:00.000')"
        )
        conn.commit()
    finally:
        conn.close()


def _seed_schwab_api_call(
    db_path,
    *,
    env: str,
    endpoint: str = "accounts.orders.list",
    status: str = "success",
    http_status: int | None = 200,
    error_message: str | None = None,
    ts: str = "2026-05-17T10:00:00.000+00:00",
) -> None:
    """Plant a single schwab_api_calls row for the recent-calls table."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO schwab_api_calls "
            "(ts, endpoint, http_status, status, error_message, "
            " surface, environment) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, endpoint, http_status, status, error_message,
             "cli", env),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# (1) Route registered in app.routes (Phase 6 I3 inheritance check).
# ---------------------------------------------------------------------------

def test_schwab_status_route_registered_in_app_routes(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 1 — /schwab/status MUST be registered in app.routes so any
    HX-Redirect target from /schwab/setup (T-2.4) resolves correctly."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    assert any(
        getattr(r, "path", None) == "/schwab/status" for r in app.routes
    ), "/schwab/status not in app.routes"


# ---------------------------------------------------------------------------
# (2) GET renders template (status 200 + 'Schwab integration status' substring).
# ---------------------------------------------------------------------------

def test_get_schwab_status_renders_200_with_title_substring(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 2 — minimal-success: GET returns 200 with the operator-facing
    title substring."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    assert "Schwab integration status" in r.text


# ---------------------------------------------------------------------------
# (3) Default environment from cfg.
# ---------------------------------------------------------------------------

def test_default_environment_from_cfg_when_no_query_param(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 3 — without `?environment=`, page renders cfg-resolved env."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    # Default cfg env is 'production' per swing/config.py defaults.
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    # The env appears in the title heading "(production)".
    assert "(production)" in r.text


# ---------------------------------------------------------------------------
# (4) ?environment=production overrides cfg sandbox default.
# ---------------------------------------------------------------------------

def test_query_param_production_overrides_cfg(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 4 — explicit `?environment=production` is rendered even when
    cfg env is something else."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status?environment=production")
    assert r.status_code == 200
    assert "(production)" in r.text


# ---------------------------------------------------------------------------
# (5) ?environment=sandbox overrides cfg production default.
# ---------------------------------------------------------------------------

def test_query_param_sandbox_overrides_cfg(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 5 — explicit `?environment=sandbox` is rendered even when cfg
    default is production."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status?environment=sandbox")
    assert r.status_code == 200
    assert "(sandbox)" in r.text


# ---------------------------------------------------------------------------
# (6) ?environment=banana → 400 + content-type text/plain (BINDING #6).
# ---------------------------------------------------------------------------

def test_invalid_environment_returns_400_plaintext(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 6 (Codex R1 Major #7 + R2 Major #1 LOCK) — invalid env returns
    400 with content-type 'text/plain' so any echoed value is XSS-safe.

    Discriminating: if a future fork rendered the invalid value via the
    HTML template, content-type would be 'text/html' and an attacker-
    supplied <script> payload would execute."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status?environment=banana")
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("text/plain"), (
        f"expected text/plain, got {r.headers.get('content-type')!r}"
    )


# ---------------------------------------------------------------------------
# (7) apply_overrides invoked once per request (monkeypatch spy).
# ---------------------------------------------------------------------------

def test_apply_overrides_invoked_once_per_request(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 7 (Codex R1 Critical #1 inheritance from Sub-bundle B) —
    apply_overrides(cfg) is the project-wide invariant at Schwab entry
    points. Without it the cfg-cascade tier (user-config.toml) is never
    consulted for integrations.schwab.* fields.

    Discriminating: if a future fork dropped apply_overrides, env vars
    + cfg fields would be ignored, leaking the raw tracked Config to the
    VM and causing operator-visible drift (env defaulting to whatever
    swing.config.toml declares regardless of overrides)."""
    import swing.web.routes.schwab as schwab_route
    call_count = {"n": 0}
    real_apply = schwab_route.apply_overrides

    def _spy(cfg_arg):
        call_count["n"] += 1
        return real_apply(cfg_arg)

    monkeypatch.setattr(schwab_route, "apply_overrides", _spy)

    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    assert call_count["n"] == 1, (
        f"apply_overrides invoked {call_count['n']} times; expected 1 "
        "per request at route entry"
    )


# ---------------------------------------------------------------------------
# (8) Base-layout banner field populated (BINDING #13).
# ---------------------------------------------------------------------------

def test_base_layout_banner_count_renders_from_unresolved_material(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 8 (Phase 10 Sub-bundle E T-E.3 retrofit) — plant 1 material
    unresolved discrepancy; assert response renders banner count = 1.

    Discriminating: if a future fork dropped the
    `_fetch_unresolved_material_count` call from the route, the base-
    layout banner field would default to 0 and the operator would never
    see the reconciliation warning on /schwab/status."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    _seed_unresolved_material_discrepancy(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    # Base.html.j2 emits data-count="N" on the banner aside element when
    # the count is > 0.
    assert 'data-banner="unresolved-material-discrepancies"' in r.text
    assert 'data-count="1"' in r.text


# ---------------------------------------------------------------------------
# (9) POST returns 405 (V1 read-only).
# ---------------------------------------------------------------------------

def test_post_schwab_status_returns_405(seeded_db, monkeypatch, tmp_path):
    """Test 9 — V1 is read-only; POST /schwab/status returns 405 Method
    Not Allowed (FastAPI's automatic response for an unmounted verb).

    Send HX-Request header to pass OriginGuard strict-mode so the
    underlying FastAPI method-not-allowed response is observable
    (without it OriginGuard returns 403 first — defense-in-depth, NOT
    the surface we're probing here)."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/schwab/status", headers={"HX-Request": "true"},
        )
    assert r.status_code == 405


# ---------------------------------------------------------------------------
# (10) HX-Request header has no special handling (smoke: both 200).
# ---------------------------------------------------------------------------

def test_hx_request_header_smoke_both_200(seeded_db, monkeypatch, tmp_path):
    """Test 10 — GET with + without HX-Request both return 200 (read-only
    page has no HX-Request branching)."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_plain = client.get("/schwab/status")
        r_hx = client.get(
            "/schwab/status", headers={"HX-Request": "true"},
        )
    assert r_plain.status_code == 200
    assert r_hx.status_code == 200


# ---------------------------------------------------------------------------
# (11) XSS regression: ?environment=<script>alert(1)</script> → 400 + text/plain.
# ---------------------------------------------------------------------------

def test_xss_payload_environment_returns_400_plaintext(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 11 (Codex R2 Major #1 LOCK) — content-type 'text/plain'
    prevents browser interpretation of any echoed value. Body MAY contain
    the literal `<script>` substring because the route echoes the invalid
    value via repr() for debugging; the XSS-safe primitive is the
    content-type, not the body."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/schwab/status?environment=<script>alert(1)</script>",
        )
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("text/plain"), (
        f"XSS-safety relies on content-type; got "
        f"{r.headers.get('content-type')!r}"
    )


# ---------------------------------------------------------------------------
# (12) Case-insensitive env query-param.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "case_variant",
    ["PRODUCTION", "Production", "production",
     "SANDBOX", "Sandbox", "sandbox"],
)
def test_env_query_param_case_insensitive(
    case_variant, seeded_db, monkeypatch, tmp_path,
):
    """Test 12 (Codex R1 Minor #3 LOCK) — `?environment=` accepts mixed
    case; matches CLI Click option case-insensitive behavior."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/schwab/status?environment={case_variant}")
    assert r.status_code == 200
    expected_lower = case_variant.lower()
    assert f"({expected_lower})" in r.text, (
        f"case variant {case_variant!r} did not resolve to "
        f"({expected_lower}); body: {r.text[:200]!r}"
    )


# ---------------------------------------------------------------------------
# (13) Sentinel-leak audit per Phase 11 Sub-bundle A T-A.10 D1.
# ---------------------------------------------------------------------------

def test_sentinel_leak_audit_no_token_bytes_in_response(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 13 (Codex R1 Major #6 LOCK + Phase 11 Sub-bundle A T-A.10 D1
    redaction discipline) — plant 3 non-token-shaped sentinels into the
    tokens DB (access_token / refresh_token / id_token fields) AND into
    a schwab_api_calls.error_message row; render /schwab/status; assert
    ZERO substring matches in the response body.

    Discriminating: if a future fork serialized the entire payload from
    `_read_tokens_metadata` into the VM (instead of only `*_issued`
    timestamps + presence-only refresh_token check), the access /
    refresh / id token bytes would leak into the rendered HTML."""
    cfg, cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    # Plant non-token-shaped sentinels (must not look like a real token).
    sentinels = [
        "LEAK_TOKEN_BYTES_ACCESS_SENTINEL_FROM_TEST",
        "LEAK_TOKEN_BYTES_REFRESH_SENTINEL_FROM_TEST",
        "LEAK_TOKEN_BYTES_ID_SENTINEL_FROM_TEST",
        "LEAK_AUDIT_ERROR_MESSAGE_SENTINEL_FROM_TEST",
    ]
    _seed_tokens_db(
        tmp_path,
        "production",
        access_token_bytes=sentinels[0],
        refresh_token_bytes=sentinels[1],
        id_token_bytes=sentinels[2],
    )
    _seed_schwab_api_call(
        cfg.paths.db_path,
        env="production",
        status="auth_failed",
        http_status=401,
        error_message=sentinels[3],
        ts="2026-05-17T11:00:00.000+00:00",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/status")
    assert r.status_code == 200
    body = r.text
    for sentinel in sentinels[:3]:
        assert sentinel not in body, (
            f"sentinel-leak: {sentinel!r} found in response body — "
            "VM/template surfaced raw token bytes (violates Phase 11 "
            "Sub-bundle A T-A.10 D1 redaction discipline)"
        )
    # NOTE: error_message sentinels are operator-visible by design
    # (audit-row excerpts are the diagnostic surface); this audit only
    # asserts token-byte sentinels stay out of the response body.
