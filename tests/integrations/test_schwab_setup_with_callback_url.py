"""Phase 12 Sub-bundle B Task T-B.4 — `setup_paste_flow_with_callback_url`
service helper tests.

Tests the Outcome B manual-token-exchange path that powers the web
``/schwab/setup`` POST. Mocks the HTTP layer (`requests.post`) +
schwabdev.Client. Asserts:
- Happy-path: HTTP POST hits /v1/oauth/token with grant_type=
  authorization_code + extracted code + redirect_uri from cfg.
- Tokens file written in schwabdev-compatible JSON shape.
- Two audit rows opened (oauth.code_exchange + accounts.linked); both
  closed status='success'.
- account_hash persisted via write_user_overrides.
- Multi-account → SchwabConfigMissingError.
- HTTP 4xx from Schwab → SchwabAuthError + audit row closed
  'auth_failed' on the FIRST audit row (oauth.code_exchange).
- Missing 'code=' / '%40' in callback URL → SchwabAuthError.
- Pipeline-active without force=True → SchwabPipelineActiveError.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.config import load
from swing.data.db import ensure_schema
from swing.integrations.schwab.auth import (
    setup_paste_flow_with_callback_url,
)
from swing.integrations.schwab.client import (
    SchwabAuthError,
    SchwabConfigMissingError,
    SchwabPipelineActiveError,
)


@pytest.fixture
def env_with_db(tmp_path, monkeypatch):
    """Return (cfg, conn, tokens_path). Monkeypatches USERPROFILE+HOME
    so the user-config write doesn't leak (CLAUDE.md gotcha)."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    conn = sqlite3.connect(cfg.paths.db_path)
    tokens_path = home / "swing-data" / "schwab-tokens.production.db"
    yield cfg, conn, tokens_path
    conn.close()


class _StubResponse:
    """Mimic requests.Response shape used by the service helper."""

    def __init__(self, ok=True, status_code=200, body=None):
        self.ok = ok
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


def _install_stub_requests(monkeypatch, response: _StubResponse, captured: dict):
    import swing.integrations.schwab.auth as auth_mod

    real_post = None  # placeholder so any prior real call could've been mocked

    def _stub_post(url, headers=None, data=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        captured["timeout"] = timeout
        return response

    import requests
    monkeypatch.setattr(requests, "post", _stub_post)
    return real_post


def _install_stub_schwabdev(monkeypatch, accounts):
    """Stub schwabdev.Client so its construction reads the tokens file
    written by the service helper + returns an object whose
    account_linked() returns the seeded accounts."""

    class _StubTokens:
        def __init__(self, tokens_file):
            with open(tokens_file) as f:
                data = json.load(f)
            td = data.get("token_dictionary", {})
            self.access_token = td.get("access_token") or "fresh_access"
            self.refresh_token = td.get("refresh_token") or "fresh_refresh"

    class _StubClient:
        def __init__(
            self,
            app_key=None, app_secret=None, callback_url=None,
            tokens_file=None, timeout=None, **_kw,
        ):
            self.tokens = _StubTokens(tokens_file)

        def account_linked(self):
            return accounts

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", _StubClient)


def test_happy_path_singleton_account(env_with_db, monkeypatch):
    """Test 1 — full happy-path: HTTP success → tokens written → Client
    constructed → account_linked returns singleton → account_hash
    persisted. Both audit rows closed status='success'."""
    cfg, conn, tokens_path = env_with_db
    captured: dict = {}
    _install_stub_requests(
        monkeypatch,
        _StubResponse(
            ok=True, status_code=200,
            body={
                "access_token": "fresh_access_token_value_abcdefghij",
                "refresh_token": "fresh_refresh_token_value_kkkkkkkk",
                "token_type": "Bearer",
                "expires_in": 1800,
                "scope": "api",
            },
        ),
        captured,
    )
    _install_stub_schwabdev(
        monkeypatch,
        accounts=[{"accountNumber": "12345", "hashValue": "HASHED_ABC"}],
    )

    summary = setup_paste_flow_with_callback_url(
        cfg,
        "production",
        "test_client_id_value_xyz",
        "test_secret_value_aaa",
        "https://127.0.0.1/?code=AUTH_CODE_HERE%40SESSION_TOKEN",
        conn,
    )

    # Service return shape
    assert summary["account_hash"] == "HASHED_ABC"
    assert summary["environment"] == "production"
    assert summary["num_accounts"] == 1
    assert summary["oauth_http_status"] == 200

    # HTTP POST called with the right URL + grant_type + redirect_uri.
    assert captured["url"] == "https://api.schwabapi.com/v1/oauth/token"
    assert captured["data"]["grant_type"] == "authorization_code"
    # Code extracted: "AUTH_CODE_HERE@"
    assert captured["data"]["code"] == "AUTH_CODE_HERE@"
    assert captured["data"]["redirect_uri"].startswith("https://")

    # Tokens file written + parseable + has access_token + refresh_token.
    assert tokens_path.exists()
    on_disk = json.loads(tokens_path.read_text())
    assert "access_token_issued" in on_disk
    assert "refresh_token_issued" in on_disk
    td = on_disk["token_dictionary"]
    assert td["access_token"] == "fresh_access_token_value_abcdefghij"
    assert td["refresh_token"] == "fresh_refresh_token_value_kkkkkkkk"

    # Two audit rows, both success.
    rows = conn.execute(
        "SELECT endpoint, status, surface "
        "FROM schwab_api_calls ORDER BY call_id",
    ).fetchall()
    assert len(rows) == 2
    assert rows[0] == ("oauth.code_exchange", "success", "cli")
    assert rows[1] == ("accounts.linked", "success", "cli")


def test_callback_url_missing_code_raises_auth_error(env_with_db, monkeypatch):
    """Test 2 — callback URL with no `code=` substring raises
    SchwabAuthError (HTTP layer never called)."""
    cfg, conn, _tokens_path = env_with_db

    called: dict = {"count": 0}

    def _should_not_be_called(*_a, **_kw):
        called["count"] += 1
        raise AssertionError("requests.post should not run on validation failure")

    import requests
    monkeypatch.setattr(requests, "post", _should_not_be_called)

    with pytest.raises(SchwabAuthError) as exc_info:
        setup_paste_flow_with_callback_url(
            cfg,
            "production",
            "test_client_id_value_xyz",
            "test_secret_value_aaa",
            "https://127.0.0.1/?session=foo",  # no code=
            conn,
        )
    # SchwabAuthError.__str__ is redacted to "(status=400, body=<N bytes>)" —
    # body_excerpt carries the human-readable error message.
    assert "code" in exc_info.value.body_excerpt.lower()
    assert exc_info.value.status_code == 400
    assert called["count"] == 0

    # Audit row opened + closed 'auth_failed'.
    rows = conn.execute(
        "SELECT endpoint, status FROM schwab_api_calls",
    ).fetchall()
    assert len(rows) == 1
    assert rows[0] == ("oauth.code_exchange", "auth_failed")


def test_callback_url_missing_at_marker_raises_auth_error(
    env_with_db, monkeypatch,
):
    """Test 3 — callback URL without `%40` marker rejected."""
    cfg, conn, _tokens_path = env_with_db

    def _should_not_be_called(*_a, **_kw):
        raise AssertionError("requests.post should not run")

    import requests
    monkeypatch.setattr(requests, "post", _should_not_be_called)

    with pytest.raises(SchwabAuthError):
        setup_paste_flow_with_callback_url(
            cfg,
            "production",
            "test_client_id_value_xyz",
            "test_secret_value_aaa",
            "https://127.0.0.1/?code=NOAT_HERE",  # no %40
            conn,
        )


def test_http_4xx_from_schwab_audits_auth_failed_and_raises(
    env_with_db, monkeypatch,
):
    """Test 4 — HTTP 401 from /v1/oauth/token → SchwabAuthError + audit
    row closed 'auth_failed'. Tokens file MUST NOT be written."""
    cfg, conn, tokens_path = env_with_db
    captured: dict = {}
    _install_stub_requests(
        monkeypatch,
        _StubResponse(ok=False, status_code=401, body={}),
        captured,
    )

    with pytest.raises(SchwabAuthError):
        setup_paste_flow_with_callback_url(
            cfg,
            "production",
            "test_client_id_value_xyz",
            "test_secret_value_aaa",
            "https://127.0.0.1/?code=AUTH%40SESSION",
            conn,
        )

    # Tokens file NOT written.
    assert not tokens_path.exists()
    # Audit row closed 'auth_failed'.
    rows = conn.execute(
        "SELECT endpoint, status, http_status FROM schwab_api_calls",
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "oauth.code_exchange"
    assert rows[0][1] == "auth_failed"


def test_multi_account_without_picker_raises_config_missing(
    env_with_db, monkeypatch,
):
    """Test 5 — multi-account response from account_linked() + no
    account_picker → SchwabConfigMissingError (web V1 LOCK)."""
    cfg, conn, _tokens_path = env_with_db
    captured: dict = {}
    _install_stub_requests(
        monkeypatch,
        _StubResponse(
            ok=True, status_code=200,
            body={
                "access_token": "fresh_access_token_value",
                "refresh_token": "fresh_refresh_token_value",
            },
        ),
        captured,
    )
    _install_stub_schwabdev(
        monkeypatch,
        accounts=[
            {"accountNumber": "111", "hashValue": "HASH_A"},
            {"accountNumber": "222", "hashValue": "HASH_B"},
        ],
    )

    with pytest.raises(SchwabConfigMissingError) as exc_info:
        setup_paste_flow_with_callback_url(
            cfg,
            "production",
            "test_client_id_value",
            "test_secret_value_abc",
            "https://127.0.0.1/?code=AUTH%40SESSION",
            conn,
            account_picker=None,
        )
    assert "multi-account" in str(exc_info.value).lower()


def test_pipeline_active_without_force_raises(env_with_db, monkeypatch):
    """Test 6 — pipeline_runs has a state='running' row + force=False
    → SchwabPipelineActiveError before any HTTP call."""
    cfg, conn, _tokens_path = env_with_db
    # Seed a running pipeline row. Schema requires trigger, data_asof_date,
    # action_session_date, state, lease_token (all NOT NULL).
    conn.execute(
        "INSERT INTO pipeline_runs ("
        "  started_ts, trigger, data_asof_date, action_session_date, "
        "  state, lease_token"
        ") VALUES ("
        "  '2026-05-15T10:00:00', 'manual', '2026-05-15', '2026-05-15', "
        "  'running', 'test-lease'"
        ")",
    )
    conn.commit()

    def _should_not_be_called(*_a, **_kw):
        raise AssertionError("requests.post should not run when blocked")

    import requests
    monkeypatch.setattr(requests, "post", _should_not_be_called)

    with pytest.raises(SchwabPipelineActiveError):
        setup_paste_flow_with_callback_url(
            cfg,
            "production",
            "test_client_id_value",
            "test_secret_value_abc",
            "https://127.0.0.1/?code=AUTH%40SESSION",
            conn,
        )


def test_invalid_environment_raises_config_missing(env_with_db):
    """Test 7 — environment outside ('sandbox', 'production') rejected
    before any other work."""
    cfg, conn, _ = env_with_db
    with pytest.raises(SchwabConfigMissingError):
        setup_paste_flow_with_callback_url(
            cfg,
            "invalid_env",
            "id_xyz",
            "secret_abc",
            "https://127.0.0.1/?code=A%40B",
            conn,
        )


def test_empty_credentials_raise_config_missing(env_with_db):
    """Test 8 — empty client_id / client_secret rejected."""
    cfg, conn, _ = env_with_db
    with pytest.raises(SchwabConfigMissingError):
        setup_paste_flow_with_callback_url(
            cfg, "production", "", "secret", "https://127.0.0.1/?code=A%40B",
            conn,
        )
    with pytest.raises(SchwabConfigMissingError):
        setup_paste_flow_with_callback_url(
            cfg, "production", "id", "", "https://127.0.0.1/?code=A%40B",
            conn,
        )


def test_empty_callback_url_raises_config_missing(env_with_db):
    """Test 9 — empty callback URL rejected with config-missing-class
    error (operator-actionable + caught early before any I/O)."""
    cfg, conn, _ = env_with_db
    with pytest.raises(SchwabConfigMissingError):
        setup_paste_flow_with_callback_url(
            cfg, "production", "id_xyz", "secret_abc", "", conn,
        )


def test_account_hash_persisted_to_user_overrides(env_with_db, monkeypatch):
    """Test 10 — happy path persists the chosen account_hash to the
    cfg-cascade write (user-config.toml under [integrations.schwab])."""
    cfg, conn, _tokens_path = env_with_db
    captured: dict = {}
    _install_stub_requests(
        monkeypatch,
        _StubResponse(
            ok=True, status_code=200,
            body={
                "access_token": "fresh_access_token_value",
                "refresh_token": "fresh_refresh_token_value",
            },
        ),
        captured,
    )
    _install_stub_schwabdev(
        monkeypatch,
        accounts=[
            {"accountNumber": "12345", "hashValue": "PERSISTED_HASH"},
        ],
    )

    setup_paste_flow_with_callback_url(
        cfg, "production",
        "id_xyz_abc",
        "secret_xyz_abc",
        "https://127.0.0.1/?code=A%40B",
        conn,
    )

    from swing.config_user import load_user_overrides
    overrides = load_user_overrides()
    assert (
        overrides.get("integrations", {}).get("schwab", {}).get("account_hash")
        == "PERSISTED_HASH"
    )
