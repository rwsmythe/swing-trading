"""Phase 12 Sub-bundle B Task T-B.4 — web `/schwab/setup` route tests.

Per dispatch brief §3 T-B.4 discriminating-test patterns (1)-(7):
- (1) GET /schwab/setup renders template with authorize URL constructed
      correctly from cfg + Schwab OAuth endpoint.
- (2) GET renders ``hx-headers='{"HX-Request": "true"}'`` attribute on
      form (regression for Phase 5 R1 M1).
- (3) POST with empty form + no credentials in cascade → 400 + error
      template.
- (4) POST with credentials + form callback URL → mock service returns
      success → 204 + HX-Redirect (target exists per route-table assert).
- (5) POST with ``setup_paste_flow_with_callback_url`` raising
      ``SchwabAuthError`` → response is 4xx (NOT 500) + error template.
- (6) Route-level integration test — assert service function invoked with
      correct credential args from cascade (T-A.3 gap pre-emption).
- (7) HX-Redirect target route exists (route-table assertion).

Plus T-B.4 acceptance criteria coverage:
- existing_tokens_db_warning surfaces when tokens DB exists.
- SchwabPipelineActiveError → 409.
- SchwabConfigMissingError (multi-account) → 400 + CLI hint.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


# ---------------------------------------------------------------------------
# (1) GET — form-render with authorize URL
# ---------------------------------------------------------------------------

def test_get_schwab_setup_renders_200_with_authorize_url(
    seeded_db, monkeypatch,
):
    """Test 1 — authorize URL constructed from cfg client_id + Schwab
    OAuth endpoint with the cfg callback URL as redirect_uri."""
    cfg, _cfg_path = seeded_db
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_client_id_value_12345")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_client_secret_abc")
    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/setup")
    assert r.status_code == 200
    body = r.text
    # Schwab OAuth endpoint
    assert "https://api.schwabapi.com/v1/oauth/authorize" in body
    # client_id pre-filled
    assert "client_id=test_client_id_value_12345" in body
    # redirect_uri pre-filled with cfg callback URL
    assert "redirect_uri=" in body


# ---------------------------------------------------------------------------
# (2) GET — hx-headers attribute on form
# ---------------------------------------------------------------------------

def test_get_form_includes_hx_headers_propagation(seeded_db, monkeypatch):
    """Test 2 (Phase 5 R1 M1 regression) — embedded form needs explicit
    hx-headers attribute so HX-Request propagates under OriginGuard."""
    cfg, _cfg_path = seeded_db
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_client_id_12345")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_client_secret_abc")
    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/setup")
    assert r.status_code == 200
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text


# ---------------------------------------------------------------------------
# (3) POST — no credentials + empty form → 400 + error template
# ---------------------------------------------------------------------------

def test_post_without_credentials_returns_400_error_template(
    seeded_db, monkeypatch,
):
    """Test 3 — credentials cascade returns (None, None) → 400."""
    cfg, _cfg_path = seeded_db
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)
    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=abc%40123"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert "Schwab credentials" in r.text
    assert (
        "swing config set integrations.schwab.client_id" in r.text
        or "/config" in r.text
    )


# ---------------------------------------------------------------------------
# (4) POST — happy path → 204 + HX-Redirect
# ---------------------------------------------------------------------------

def test_post_with_credentials_and_callback_url_returns_204_hx_redirect(
    seeded_db, monkeypatch,
):
    """Test 4 — happy path: mock service returns success → 204 +
    HX-Redirect with target route registered in app.routes."""
    cfg, _cfg_path = seeded_db
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")

    called_with = {}

    def _stub_service(
        cfg_arg, environment, client_id, client_secret,
        callback_url_with_code, conn, *, force=False, account_picker=None,
    ):
        called_with["client_id"] = client_id
        called_with["client_secret"] = client_secret
        called_with["callback_url"] = callback_url_with_code
        called_with["environment"] = environment
        return {
            "tokens_path": "/tmp/stub.db",
            "account_hash": "ABCD1234",
            "environment": environment,
            "call_id_setup": 1,
            "call_id_account_linked": 2,
            "num_accounts": 1,
            "oauth_http_status": 200,
        }

    import swing.web.routes.schwab as schwab_route
    monkeypatch.setattr(
        schwab_route,
        "setup_paste_flow_with_callback_url",
        _stub_service,
    )

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=abc%40xyz"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 204
    target = r.headers.get("HX-Redirect", "")
    assert target.startswith("/config"), (
        f"unexpected HX-Redirect target: {target!r}"
    )

    # Route-table assertion — target route MUST exist (Phase 6 I3 lesson).
    target_path = target.split("?", 1)[0]
    assert any(getattr(r_, "path", None) == target_path for r_ in app.routes), (
        f"HX-Redirect target {target_path} not in app.routes"
    )


# ---------------------------------------------------------------------------
# (5) POST — SchwabAuthError → 4xx + error template (NOT raw 500)
# ---------------------------------------------------------------------------

def test_post_with_setup_paste_flow_raising_auth_error_returns_4xx(
    seeded_db, monkeypatch,
):
    """Test 5 — SchwabAuthError handled cleanly → 502 + error template
    (NOT raw 500 via FastAPI's default exception handler)."""
    cfg, _cfg_path = seeded_db
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")

    from swing.integrations.schwab.client import SchwabAuthError

    def _stub_raise(*_args, **_kwargs):
        raise SchwabAuthError(401, "<oauth refused>")

    import swing.web.routes.schwab as schwab_route
    monkeypatch.setattr(
        schwab_route,
        "setup_paste_flow_with_callback_url",
        _stub_raise,
    )

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=abc%40xyz"},
            headers={"HX-Request": "true"},
        )
    # Mapped to 502 per route handler. Importantly NOT 500 (would mean
    # the exception escaped to FastAPI's default handler).
    assert r.status_code == 502, (
        f"expected 502, got {r.status_code}: {r.text[:200]}"
    )
    assert "Schwab setup failed" in r.text


# ---------------------------------------------------------------------------
# (6) Route-level integration test — service invoked with cascade creds
# (T-A.3 gap pre-emption from Sub-bundle A)
# ---------------------------------------------------------------------------

def test_post_invokes_service_with_credentials_from_cascade(
    seeded_db, monkeypatch,
):
    """Test 6 — service function is invoked with the EXACT credentials
    the cascade resolves (NOT some hardcoded test value or empty
    string). Mirrors Sub-bundle A T-A.3 gap pre-emption pattern."""
    cfg, _cfg_path = seeded_db
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "cascaded_id_abc_1234567890")
    monkeypatch.setenv(
        "SCHWAB_CLIENT_SECRET", "cascaded_secret_xyz_abcdef",
    )

    captured: dict = {}

    def _stub_service(
        cfg_arg, environment, client_id, client_secret,
        callback_url_with_code, conn, *, force=False, account_picker=None,
    ):
        captured["client_id"] = client_id
        captured["client_secret"] = client_secret
        captured["callback_url"] = callback_url_with_code
        captured["environment"] = environment
        return {
            "tokens_path": "/tmp/stub.db",
            "account_hash": "HASH",
            "environment": environment,
            "call_id_setup": 1,
            "call_id_account_linked": 2,
            "num_accounts": 1,
            "oauth_http_status": 200,
        }

    import swing.web.routes.schwab as schwab_route
    monkeypatch.setattr(
        schwab_route,
        "setup_paste_flow_with_callback_url",
        _stub_service,
    )

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=Z%40A"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code in (204, 303), (
        f"expected success, got {r.status_code}: {r.text[:200]}"
    )
    assert captured["client_id"] == "cascaded_id_abc_1234567890"
    assert captured["client_secret"] == "cascaded_secret_xyz_abcdef"
    assert captured["callback_url"] == "https://127.0.0.1/?code=Z%40A"


# ---------------------------------------------------------------------------
# (7) HX-Redirect target route exists (route-table assertion)
# ---------------------------------------------------------------------------

def test_hx_redirect_target_route_exists_in_app_routes(seeded_db):
    """Test 7 (Phase 6 I3 regression) — HX-Redirect target `/config` MUST
    be registered in app.routes. TestClient verifies the header value
    but does NOT follow the redirect, so a typo in the target would
    silently 404 on the operator's browser."""
    cfg, _cfg_path = seeded_db
    app = create_app(cfg, _cfg_path)
    assert any(getattr(r, "path", None) == "/config" for r in app.routes), (
        "HX-Redirect target /config not in app.routes; T-B.4 success "
        "path would 404 the operator"
    )
    # And /schwab/setup itself exists.
    assert any(
        getattr(r, "path", None) == "/schwab/setup" for r in app.routes
    ), "/schwab/setup not in app.routes"


# ---------------------------------------------------------------------------
# Additional acceptance-criteria coverage
# ---------------------------------------------------------------------------

def test_post_with_pipeline_active_returns_409(seeded_db, monkeypatch):
    """SchwabPipelineActiveError handled cleanly → 409 + error template."""
    cfg, _cfg_path = seeded_db
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")

    from swing.integrations.schwab.client import SchwabPipelineActiveError

    def _stub_raise(*_args, **_kwargs):
        raise SchwabPipelineActiveError("<pipeline running>")

    import swing.web.routes.schwab as schwab_route
    monkeypatch.setattr(
        schwab_route,
        "setup_paste_flow_with_callback_url",
        _stub_raise,
    )

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=Z%40A"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 409
    assert "pipeline" in r.text.lower()


def test_post_with_multi_account_returns_400_with_cli_hint(
    seeded_db, monkeypatch,
):
    """SchwabConfigMissingError (multi-account on web V1) → 400 +
    error template mentioning CLI as the multi-account path."""
    cfg, _cfg_path = seeded_db
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")

    from swing.integrations.schwab.client import SchwabConfigMissingError

    def _stub_raise(*_args, **_kwargs):
        raise SchwabConfigMissingError(
            "multi-account setup requires an account_picker callable; "
            "got 3 linked accounts and no picker",
        )

    import swing.web.routes.schwab as schwab_route
    monkeypatch.setattr(
        schwab_route,
        "setup_paste_flow_with_callback_url",
        _stub_raise,
    )

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=Z%40A"},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert "swing schwab setup" in r.text.lower()


def test_post_with_empty_callback_url_returns_400(seeded_db, monkeypatch):
    """Empty callback_url field → 400 + form re-render with banner."""
    cfg, _cfg_path = seeded_db
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")
    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/schwab/setup",
            data={"callback_url": ""},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert "callback URL is required" in r.text


def test_get_renders_existing_tokens_db_warning_when_present(
    seeded_db, monkeypatch, tmp_path,
):
    """existing_tokens_db_warning surfaces in the form when a tokens
    file exists at the per-env path."""
    cfg, _cfg_path = seeded_db
    # Point _user_home at tmp_path so the tokens DB resolves under our
    # control + write a sentinel file there.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")

    swing_data = tmp_path / "swing-data"
    swing_data.mkdir(parents=True, exist_ok=True)
    # cfg defaults to environment='production'
    (swing_data / "schwab-tokens.production.db").write_text("{}")

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/setup")
    assert r.status_code == 200
    assert 'data-banner="schwab-setup-existing-tokens-db"' in r.text


def test_non_htmx_post_blocked_by_origin_guard_strict_mode(seeded_db):
    """OriginGuard strict-mode contract — POST without HX-Request gets
    403 from middleware BEFORE reaching the route handler. The 303
    fallback branch in the route is dead-code-defense for future
    loosening of OriginGuard; this test pins the current contract
    (mirrors the account snapshot test_post_without_hx_request precedent).
    """
    cfg, _cfg_path = seeded_db
    app = create_app(cfg, _cfg_path)
    with TestClient(app, follow_redirects=False) as client:
        r = client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=Z%40A"},
        )
    assert r.status_code == 403
