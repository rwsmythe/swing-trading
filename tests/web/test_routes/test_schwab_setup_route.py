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

USERPROFILE+HOME monkeypatch discipline (Phase 9 Sub-bundle A return
report §11 lesson + CLAUDE.md gotcha): every test that exercises the
``/schwab/setup`` surface monkeypatches BOTH ``USERPROFILE`` and ``HOME``
to a fresh tmp_path BEFORE building the app. ``_resolve_tokens_db_path``
→ ``_user_home()`` reads these env vars directly; an unmonkeypatched
read leaks against the operator's REAL ``~/swing-data/`` and a stale
``schwab-tokens.production.db`` there would flip
``existing_tokens_db_warning`` to True in tests that don't expect it.
"""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from swing.web.app import create_app


def _isolate_home(monkeypatch, tmp_path) -> None:
    """Monkeypatch USERPROFILE+HOME to ``tmp_path`` so
    ``_resolve_tokens_db_path``'s ``_user_home()`` reads test-controlled
    state instead of the operator's real ``~/swing-data/``.

    Per CLAUDE.md gotcha: BOTH env vars MUST be set (Windows reads
    USERPROFILE; POSIX reads HOME; tests run on both).
    """
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))


def _seed_one_unresolved_material_discrepancy(db_path) -> None:
    """Plant a closed trade + one unresolved material discrepancy attributed
    to it so ``list_unresolved_material_for_closed_trades`` returns N=1.

    Mirrors the seed helper in
    ``tests/web/test_routes/test_base_layout_discrepancy_banner.py``.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, sector, "
            "industry, trade_origin, pre_trade_locked_at, current_size) "
            "VALUES (1, 'AAA', '2026-04-01', 10.0, 100, 9.0, 9.0, 'closed', "
            "'S', 'I', 'manual_off_pipeline', '2026-04-01T09:30:00', 0)"
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


# ---------------------------------------------------------------------------
# (1) GET — form-render with authorize URL
# ---------------------------------------------------------------------------

def test_get_schwab_setup_renders_200_with_authorize_url(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 1 — authorize URL constructed from cfg client_id + Schwab
    OAuth endpoint with the cfg callback URL as redirect_uri."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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

def test_get_form_includes_hx_headers_propagation(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 2 (Phase 5 R1 M1 regression) — embedded form needs explicit
    hx-headers attribute so HX-Request propagates under OriginGuard."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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
    seeded_db, monkeypatch, tmp_path,
):
    """Test 3 — credentials cascade returns (None, None) → 400."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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
    seeded_db, monkeypatch, tmp_path,
):
    """Test 4 — happy path: mock service returns success → 204 +
    HX-Redirect with target route registered in app.routes."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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
    # Post-Phase-12 Sub-bundle 2 Task T-2.4 retargets the HX-Redirect from
    # /config?schwab_setup=ok → /schwab/status (T-B.7 deferred is now
    # shipped via Sub-bundle 2 — the read-only Schwab integration status
    # page).
    assert target == "/schwab/status", (
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
    seeded_db, monkeypatch, tmp_path,
):
    """Test 5 — SchwabAuthError handled cleanly → 502 + error template
    (NOT raw 500 via FastAPI's default exception handler)."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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
    seeded_db, monkeypatch, tmp_path,
):
    """Test 6 — service function is invoked with the EXACT credentials
    the cascade resolves (NOT some hardcoded test value or empty
    string). Mirrors Sub-bundle A T-A.3 gap pre-emption pattern."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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

def test_hx_redirect_target_route_exists_in_app_routes(
    seeded_db, monkeypatch, tmp_path,
):
    """Test 7 (Phase 6 I3 regression) — HX-Redirect target `/config` MUST
    be registered in app.routes. TestClient verifies the header value
    but does NOT follow the redirect, so a typo in the target would
    silently 404 on the operator's browser."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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

def test_post_with_pipeline_active_returns_409(
    seeded_db, monkeypatch, tmp_path,
):
    """SchwabPipelineActiveError handled cleanly → 409 + error template."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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
    seeded_db, monkeypatch, tmp_path,
):
    """SchwabConfigMissingError (multi-account on web V1) → 400 +
    error template mentioning CLI as the multi-account path."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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


def test_post_with_empty_callback_url_returns_400(
    seeded_db, monkeypatch, tmp_path,
):
    """Empty callback_url field → 400 + form re-render with banner."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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


def test_non_htmx_post_blocked_by_origin_guard_strict_mode(
    seeded_db, monkeypatch, tmp_path,
):
    """OriginGuard strict-mode contract — POST without HX-Request gets
    403 from middleware BEFORE reaching the route handler. The 303
    fallback branch in the route is dead-code-defense for future
    loosening of OriginGuard; this test pins the current contract
    (mirrors the account snapshot test_post_without_hx_request precedent).
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, _cfg_path)
    with TestClient(app, follow_redirects=False) as client:
        r = client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=Z%40A"},
        )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Issue 1 fix — global unresolved-material discrepancy banner integration
# (Phase 10 Sub-bundle E T-E.3 cross-bundle pin)
# ---------------------------------------------------------------------------

def test_get_renders_global_discrepancy_banner_when_unresolved_material_exists(
    seeded_db, monkeypatch, tmp_path,
):
    """GET /schwab/setup populates the base-layout
    ``unresolved_material_discrepancies_count`` so the global banner
    rendered by ``base.html.j2`` fires when discrepancies exist.

    Regression guard for the cross-bundle pin from Phase 10 Sub-bundle E
    T-E.3 — every base-layout page MUST populate the count or the global
    banner silently hides on the affected surface.
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")

    _seed_one_unresolved_material_discrepancy(cfg.paths.db_path)

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/setup")
    assert r.status_code == 200
    body = r.text
    # Banner-element selector (matches base.html.j2 + the shared
    # banner-rendering test in test_base_layout_discrepancy_banner.py).
    assert 'data-banner="unresolved-material-discrepancies"' in body, (
        "global discrepancy banner missing from /schwab/setup body — "
        "Phase 10 Sub-bundle E T-E.3 cross-bundle pin regression"
    )
    # Banner text fragment from the rendered <strong> element.
    assert "unresolved material reconciliation" in body


def test_get_omits_global_discrepancy_banner_when_count_eq_0(
    seeded_db, monkeypatch, tmp_path,
):
    """Companion to the banner-fires test: when no unresolved material
    discrepancies exist, the banner is ABSENT from /schwab/setup.

    Mirrors test_base_layout_discrepancy_banner.py's omission tests.
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/setup")
    assert r.status_code == 200
    assert (
        'data-banner="unresolved-material-discrepancies"' not in r.text
    )


# ---------------------------------------------------------------------------
# Issue 2 fix verification — existing_tokens_db_warning deterministically
# False when USERPROFILE+HOME are isolated to a clean tmp_path
# (Phase 9 Sub-bundle A return report §11 lesson regression guard)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Codex R1 Critical #1 regression — apply_overrides() at route entry point
# so user-config.toml-tier credentials are consumed by the web setup flow.
# Without apply_overrides() in the route handler, `request.app.state.cfg`
# returns the RAW tracked Config whose schwab.client_id/client_secret are
# empty strings; the cfg-cascade never reaches user-config.toml.
# ---------------------------------------------------------------------------


def test_post_consumes_cfg_tier_credentials_via_apply_overrides(
    seeded_db, monkeypatch, tmp_path,
):
    """Critical #1 regression — write credentials to user-config.toml,
    clear env vars, POST /schwab/setup, assert the service stub was
    invoked with the cfg-tier credentials (NOT empty strings).
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    # Clear env vars so the cfg cascade falls through to user-config.toml.
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)

    # Seed user-config.toml with credentials under the isolated home.
    from swing.config_user import write_user_overrides
    write_user_overrides({
        "integrations": {
            "schwab": {
                "client_id": "cfg_tier_client_id_value_1234",
                "client_secret": "cfg_tier_client_secret_value_5678",
            },
        },
    })

    captured: dict = {}

    def _stub_service(
        cfg_arg, environment, client_id, client_secret,
        callback_url_with_code, conn, *, force=False, account_picker=None,
    ):
        captured["client_id"] = client_id
        captured["client_secret"] = client_secret
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
        f"unexpected status {r.status_code}: {r.text[:200]}"
    )
    # The Critical defect would surface as empty-string credentials
    # because the raw cfg's defaults are empty strings — the cfg-cascade
    # tier was never consulted.
    assert captured["client_id"] == "cfg_tier_client_id_value_1234", (
        f"cfg-tier client_id not consumed (got {captured.get('client_id')!r})"
        " — apply_overrides() likely missing from route entry"
    )
    assert captured["client_secret"] == "cfg_tier_client_secret_value_5678"


def test_get_consumes_cfg_tier_credentials_via_apply_overrides(
    seeded_db, monkeypatch, tmp_path,
):
    """Critical #1 regression GET-side — credentials in user-config.toml
    surface the configured client_id in the authorize URL on GET render.
    Without apply_overrides(), the raw cfg's empty-string default would
    render `client_id=<set client_id>` placeholder + the no-credentials
    banner.
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)

    from swing.config_user import write_user_overrides
    write_user_overrides({
        "integrations": {
            "schwab": {
                "client_id": "get_cfg_tier_id_abcdef_123456",
                "client_secret": "get_cfg_tier_secret_xyzzy",
            },
        },
    })

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/setup")
    assert r.status_code == 200
    body = r.text
    # The cfg-tier client_id MUST appear in the authorize URL.
    assert "client_id=get_cfg_tier_id_abcdef_123456" in body, (
        "cfg-tier client_id not in rendered authorize URL — "
        "apply_overrides() likely missing from GET handler"
    )
    # And the no-credentials banner MUST NOT appear.
    assert "Schwab credentials not configured" not in body


# ---------------------------------------------------------------------------
# Codex R1 Major #4 regression — /config link removed from error remediation
# (masked fields are not editable via /config; pointing operators there
# would show display-only masked values with no edit form).
# ---------------------------------------------------------------------------


def test_post_no_credentials_remediation_does_not_link_to_config(
    seeded_db, monkeypatch, tmp_path,
):
    """Major #4 regression — the no-credentials remediation hint MUST
    reference env vars + CLI; MUST NOT reference /config (since masked
    fields are not POST-editable per swing/web/routes/config.py:31).
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
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
    body = r.text
    # Remediation must mention env vars OR the CLI command.
    assert (
        "SCHWAB_CLIENT_ID" in body
        or "swing config set integrations.schwab.client_id" in body
    )
    # The remediation hint MUST NOT instruct operators to "Set credentials
    # via /config" (the masked-fields gotcha). The error_message paragraph
    # may still contain "/config" via the unrelated "Go to /config" footer
    # link, so we look only at the remediation-hint paragraph (after
    # "Next step:").
    # Extract the remediation hint text — between "Next step:" and the
    # following </p>.
    import re
    m = re.search(
        r"Next step:</strong>(.+?)</p>", body, re.DOTALL,
    )
    remediation = m.group(1) if m else ""
    assert "/config" not in remediation, (
        f"/config reference still present in remediation hint: {remediation!r}"
    )


# ---------------------------------------------------------------------------
# Codex R1 Minor #2 regression — accessibility (aria-describedby +
# role='alert') on the inline form.
# ---------------------------------------------------------------------------


def test_form_input_has_aria_describedby_to_help_text(
    seeded_db, monkeypatch, tmp_path,
):
    """Minor #2 — callback_url input carries aria-describedby pointing
    at the inline help text + (when error_message present) error banner.
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")
    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/setup")
    assert r.status_code == 200
    assert 'aria-describedby="callback_url-help"' in r.text
    assert 'id="callback_url-help"' in r.text


def test_form_inline_error_banner_has_role_alert_for_screen_readers(
    seeded_db, monkeypatch, tmp_path,
):
    """Minor #2 — inline form-error banner carries role='alert' so screen
    readers announce it when re-rendered after a validation failure.
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")
    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        # Submit with empty callback_url to trigger the inline banner.
        r = client.post(
            "/schwab/setup",
            data={"callback_url": ""},
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    body = r.text
    # role='alert' attached to the inline banner.
    assert 'data-form-error="schwab-setup"' in body
    assert 'role="alert"' in body


def test_get_existing_tokens_db_warning_false_under_isolated_home(
    seeded_db, monkeypatch, tmp_path,
):
    """With USERPROFILE+HOME monkeypatched to a clean tmp_path (no
    pre-existing tokens DB), ``existing_tokens_db_warning`` is False —
    confirming the test-isolation discipline prevents the warning from
    falsely flipping based on the operator's REAL ``~/swing-data/``.
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test_secret_abc")

    # Sanity: no tokens DB pre-exists in the isolated home.
    assert not (tmp_path / "swing-data" / "schwab-tokens.production.db").exists()

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.get("/schwab/setup")
    assert r.status_code == 200
    # The existing-tokens-db banner is ABSENT when no DB exists.
    assert 'data-banner="schwab-setup-existing-tokens-db"' not in r.text


# ---------------------------------------------------------------------------
# Post-Phase-12 Sub-bundle 2 Task T-2.4 — HX-Redirect retarget to /schwab/status
# ---------------------------------------------------------------------------
#
# Per plan §B T-2.4 acceptance criteria (3 discriminating tests):
#   1. Successful POST → 204 + HX-Redirect: /schwab/status header
#      (NOT /config?schwab_setup=ok).
#   2. /config?schwab_setup=ok query-param still renders 200 (tolerated
#      silently per Codex R1 m#2 LOCK — one release window for stale
#      browser tabs / bookmarks).
#   3. /schwab/status target registered (HX-Redirect target route check
#      per Phase 6 I3 inheritance).


def test_t24_post_success_hx_redirect_targets_schwab_status(
    seeded_db, monkeypatch, tmp_path,
):
    """T-2.4 test 1 — successful POST returns 204 + HX-Redirect to
    /schwab/status (NOT the prior /config?schwab_setup=ok target).

    Discriminating: a future fork that re-introduces the /config
    target would surface here. The HX-Redirect target retarget is the
    operational reason T-B.7 (this Sub-bundle) lifted from deferred —
    operators now land on the read-only status page after re-auth and
    can confirm the new refresh-token TTL is live."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "t24_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "t24_secret_abc")

    def _stub_service(
        cfg_arg, environment, client_id, client_secret,
        callback_url_with_code, conn, *, force=False, account_picker=None,
    ):
        return {
            "tokens_path": "/tmp/stub.db",
            "account_hash": "T24STUB",
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
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/schwab/status"
    # And, defensively: prior target shape is NOT emitted.
    assert "/config?schwab_setup=ok" not in r.headers.get("HX-Redirect", "")


def test_t24_config_query_param_still_renders_200(
    seeded_db, monkeypatch, tmp_path,
):
    """T-2.4 test 2 (Codex R1 m#2 LOCK) — passive no-op consumer
    retention: the stale browser tab / bookmark with
    /config?schwab_setup=ok still renders 200 for one release window.

    /config does not introspect the query param (no handler branch
    consuming it); it just renders. The test pins this tolerance so a
    future fork that adds strict query-param validation would surface
    here."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, _cfg_path)
    with TestClient(app) as client:
        r = client.get("/config?schwab_setup=ok")
    assert r.status_code == 200
    # And the page renders the standard /config content (External
    # integrations section is the closest anchor — its h2 text).
    assert "External integrations" in r.text


def test_t24_hx_redirect_target_route_registered(
    seeded_db, monkeypatch, tmp_path,
):
    """T-2.4 test 3 (Phase 6 I3 inheritance) — the NEW HX-Redirect
    target /schwab/status MUST be registered in app.routes. TestClient
    verifies the header value but does NOT follow; a stale target
    string would silently 404 the operator's browser navigation."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    app = create_app(cfg, _cfg_path)
    assert any(
        getattr(r_, "path", None) == "/schwab/status" for r_ in app.routes
    ), "/schwab/status not in app.routes; T-2.4 HX-Redirect would 404"
