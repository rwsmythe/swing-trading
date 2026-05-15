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


# ===========================================================================
# Codex R1 Major #1 regression — audit row reflects END-TO-END setup
# success, NOT just OAuth-exchange success. Previously the audit row was
# closed 'success' BEFORE schwabdev.Client construction; if load-back
# failed (e.g. schwabdev tokens-file format drift), audit lied. Reorder:
# load-back verify → THEN close audit success.
# ===========================================================================


def test_audit_row_closes_auth_failed_when_schwabdev_loadback_fails(
    env_with_db, monkeypatch,
):
    """Major #1 regression — synthesize an invalid tokens file by stubbing
    schwabdev.Client to raise on construction; assert the audit row for
    `oauth.code_exchange` is `auth_failed` (NOT `success`), reflecting
    end-to-end setup failure.
    """
    cfg, conn, _tokens_path = env_with_db
    captured: dict = {}
    _install_stub_requests(
        monkeypatch,
        _StubResponse(
            ok=True, status_code=200,
            body={
                "access_token": "fresh_access_value_abcdef",
                "refresh_token": "fresh_refresh_value_xyzzy",
            },
        ),
        captured,
    )

    # Stub schwabdev.Client to RAISE on construction — simulating a
    # format-drift scenario where our written tokens file is no longer
    # consumable by the live schwabdev library.
    class _FailingClient:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("schwabdev rejected tokens file format")

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", _FailingClient)

    with pytest.raises(SchwabAuthError):
        setup_paste_flow_with_callback_url(
            cfg, "production",
            "id_xyz_abc",
            "secret_xyz_abc",
            "https://127.0.0.1/?code=AUTH%40SESSION",
            conn,
        )

    # Audit row closed 'auth_failed' (NOT 'success').
    rows = conn.execute(
        "SELECT endpoint, status FROM schwab_api_calls ORDER BY call_id",
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "oauth.code_exchange"
    assert rows[0][1] == "auth_failed", (
        f"Major #1 regression: audit row should be auth_failed when "
        f"schwabdev load-back fails, got {rows[0][1]!r}"
    )


def test_audit_row_closes_auth_failed_when_loadback_returns_no_access_token(
    env_with_db, monkeypatch,
):
    """Major #1 silent-failure variant — schwabdev.Client constructs
    successfully but the resulting `client.tokens.access_token` is
    None/empty (silent-failure mode per CLAUDE.md gotcha). Audit row
    MUST close 'auth_failed', NOT 'success'.
    """
    cfg, conn, _tokens_path = env_with_db
    captured: dict = {}
    _install_stub_requests(
        monkeypatch,
        _StubResponse(
            ok=True, status_code=200,
            body={
                "access_token": "fresh_access_value_abcdef",
                "refresh_token": "fresh_refresh_value_xyzzy",
            },
        ),
        captured,
    )

    class _SilentFailTokens:
        access_token = None  # schwabdev's silent-failure mode
        refresh_token = None

    class _SilentFailClient:
        def __init__(self, *_args, **_kwargs):
            self.tokens = _SilentFailTokens()

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", _SilentFailClient)

    with pytest.raises(SchwabAuthError):
        setup_paste_flow_with_callback_url(
            cfg, "production",
            "id_xyz_abc",
            "secret_xyz_abc",
            "https://127.0.0.1/?code=AUTH%40SESSION",
            conn,
        )

    rows = conn.execute(
        "SELECT endpoint, status FROM schwab_api_calls ORDER BY call_id",
    ).fetchall()
    assert len(rows) == 1
    assert rows[0] == ("oauth.code_exchange", "auth_failed")


# ===========================================================================
# Codex R1 Major #3 regression — concurrent-safe atomic write via
# tempfile.mkstemp (unique tmp path per call). Two concurrent setup
# flows must not truncate each other's tmp file before os.replace.
# ===========================================================================


def test_tokens_file_atomic_write_uses_unique_tmp_path(
    env_with_db, monkeypatch, tmp_path,
):
    """Major #3 regression — the helper writes through a UNIQUE tmp file
    (mkstemp), NOT the deterministic ``<name>.tmp`` sibling. Test by
    capturing all `os.replace` calls + asserting the source path is NOT
    the deterministic sibling.
    """
    from swing.integrations.schwab.auth import _write_schwabdev_tokens_file
    from datetime import datetime, timezone

    captured: dict = {"replace_calls": []}
    import os as _os
    real_replace = _os.replace

    def _spy_replace(src, dst):
        captured["replace_calls"].append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(_os, "replace", _spy_replace)

    tokens_path = tmp_path / "schwab-tokens.production.db"
    _write_schwabdev_tokens_file(
        tokens_path=tokens_path,
        token_dictionary={
            "access_token": "a", "refresh_token": "r",
        },
        issued_at=datetime.now(timezone.utc),
    )

    assert len(captured["replace_calls"]) == 1
    src, dst = captured["replace_calls"][0]
    # Destination must be the canonical path.
    assert dst == str(tokens_path)
    # Source MUST NOT be the deterministic .tmp sibling — that's the
    # pre-fix shape and would race under concurrent calls.
    deterministic_tmp = str(tokens_path.with_name(tokens_path.name + ".tmp"))
    assert src != deterministic_tmp, (
        f"Major #3 regression: write used the deterministic tmp path "
        f"{deterministic_tmp!r} (race-unsafe). Should use mkstemp."
    )
    # Source IS in the canonical path's parent dir (intra-volume rename).
    assert _os.path.dirname(src) == str(tokens_path.parent)


def test_tokens_file_concurrent_writes_unique_tmp_names(env_with_db, tmp_path):
    """Major #3 — assert TWO sequential writes use DIFFERENT tmp file
    names (mkstemp guarantees uniqueness). Pre-fix shape used the same
    deterministic name for every call.
    """
    from swing.integrations.schwab.auth import _write_schwabdev_tokens_file
    from datetime import datetime, timezone

    captured: list = []
    import os as _os
    real_replace = _os.replace

    def _spy_replace(src, dst):
        captured.append((str(src), str(dst)))
        return real_replace(src, dst)

    import unittest.mock as mock
    tokens_path = tmp_path / "schwab-tokens.production.db"

    with mock.patch.object(_os, "replace", side_effect=_spy_replace):
        for _ in range(2):
            _write_schwabdev_tokens_file(
                tokens_path=tokens_path,
                token_dictionary={
                    "access_token": "a", "refresh_token": "r",
                },
                issued_at=datetime.now(timezone.utc),
            )

    assert len(captured) == 2
    src_1, _dst_1 = captured[0]
    src_2, _dst_2 = captured[1]
    assert src_1 != src_2, (
        "Major #3: concurrent writes must use unique tmp names "
        f"(got identical: {src_1!r})"
    )


# ===========================================================================
# Codex R1 Major #5 regression — structured URL parsing handles realistic
# callback URL variants that schwabdev's raw substring search misses.
# ===========================================================================


def test_callback_url_with_state_param_after_code(env_with_db, monkeypatch):
    """Major #5 — callback URL with additional query params (e.g.
    `?state=XYZ&code=...%40...`) must extract the code correctly.
    """
    cfg, conn, _tokens_path = env_with_db
    captured: dict = {}
    _install_stub_requests(
        monkeypatch,
        _StubResponse(
            ok=True, status_code=200,
            body={
                "access_token": "fresh_at_xyz",
                "refresh_token": "fresh_rt_xyz",
            },
        ),
        captured,
    )
    _install_stub_schwabdev(
        monkeypatch,
        accounts=[{"accountNumber": "12345", "hashValue": "HASH_X"}],
    )

    summary = setup_paste_flow_with_callback_url(
        cfg, "production",
        "test_id_abc",
        "test_secret_xyz",
        "https://127.0.0.1/?state=xyz_state&code=AUTH_VALUE%40SESSION_TOK",
        conn,
    )
    assert summary["account_hash"] == "HASH_X"
    # Code extracted correctly despite preceding state param.
    assert captured["data"]["code"] == "AUTH_VALUE@"


def test_callback_url_with_code_before_other_at_encoded_params(
    env_with_db, monkeypatch,
):
    """Major #5 — guards against the schwabdev substring-search ambiguity
    where a state param containing %40 BEFORE the code param would have
    confused the byte-for-byte mirror.
    URL shape: `?code=GOOD%40DATA&state=NOISE%40MORE`. The fixed parser
    extracts the code's own value, not the state's `%40`.
    """
    cfg, conn, _tokens_path = env_with_db
    captured: dict = {}
    _install_stub_requests(
        monkeypatch,
        _StubResponse(
            ok=True, status_code=200,
            body={
                "access_token": "fresh_at",
                "refresh_token": "fresh_rt",
            },
        ),
        captured,
    )
    _install_stub_schwabdev(
        monkeypatch,
        accounts=[{"accountNumber": "99", "hashValue": "HASH_Y"}],
    )

    setup_paste_flow_with_callback_url(
        cfg, "production",
        "test_id_abc",
        "test_secret_xyz",
        "https://127.0.0.1/?code=GOOD%40DATA&state=NOISE%40MORE",
        conn,
    )
    # Code must be "GOOD@" — extracted from the `code` param's first
    # segment, NOT the schwabdev raw `url.index('%40')` substring which
    # could have landed on the state param's `%40`.
    assert captured["data"]["code"] == "GOOD@"


def test_callback_url_missing_code_param_raises_auth_error(
    env_with_db, monkeypatch,
):
    """Major #5 — URL with NO `code` query param is rejected cleanly."""
    cfg, conn, _tokens_path = env_with_db

    def _should_not_be_called(*_a, **_kw):
        raise AssertionError("requests.post should not run")

    import requests
    monkeypatch.setattr(requests, "post", _should_not_be_called)

    with pytest.raises(SchwabAuthError):
        setup_paste_flow_with_callback_url(
            cfg, "production",
            "test_id_abc",
            "test_secret_xyz",
            "https://127.0.0.1/?state=only",
            conn,
        )


def test_callback_url_code_value_missing_at_separator_raises(
    env_with_db, monkeypatch,
):
    """Major #5 — code param present but value lacks the `@` separator
    is rejected (Schwab always emits `<auth>@<session>` shape).
    """
    cfg, conn, _tokens_path = env_with_db

    def _should_not_be_called(*_a, **_kw):
        raise AssertionError("requests.post should not run")

    import requests
    monkeypatch.setattr(requests, "post", _should_not_be_called)

    with pytest.raises(SchwabAuthError) as exc_info:
        setup_paste_flow_with_callback_url(
            cfg, "production",
            "test_id_abc",
            "test_secret_xyz",
            "https://127.0.0.1/?code=NOATSEP",
            conn,
        )
    assert "@" in exc_info.value.body_excerpt or "separator" in (
        exc_info.value.body_excerpt.lower()
    )


def test_callback_url_with_literal_plus_in_code_preserved(
    env_with_db, monkeypatch,
):
    """Codex R3 Major #1 — OAuth authorization codes are opaque tokens
    that may contain literal '+' characters. The previous parser used
    ``urllib.parse.parse_qs`` which applies ``application/x-www-form-
    urlencoded`` semantics — it decodes ``+`` as space. If Schwab emits
    ``?code=ABC+DEF%40SESSION``, parse_qs would yield ``ABC DEF@SESSION``
    instead of the literal ``ABC+DEF@SESSION``, corrupting the code that
    gets POSTed back to /v1/oauth/token (→ invalid_grant).

    The fix is to split the raw query string by '&' + use
    ``urllib.parse.unquote`` (NOT ``unquote_plus``, which has the same
    '+'-as-space behavior) to decode percent-escapes while preserving
    '+' literally.

    Discriminating: pre-fix code passed ``ABC DEF@`` (space-corrupted)
    to the OAuth POST; post-fix passes the literal ``ABC+DEF@``.
    """
    cfg, conn, _tokens_path = env_with_db
    captured: dict = {}
    _install_stub_requests(
        monkeypatch,
        _StubResponse(
            ok=True, status_code=200,
            body={
                "access_token": "fresh_at_plus",
                "refresh_token": "fresh_rt_plus",
            },
        ),
        captured,
    )
    _install_stub_schwabdev(
        monkeypatch,
        accounts=[{"accountNumber": "777", "hashValue": "HASH_PLUS"}],
    )

    setup_paste_flow_with_callback_url(
        cfg, "production",
        "test_id_abc",
        "test_secret_xyz",
        "https://127.0.0.1/?code=ABC+DEF%40SESSION_TOK",
        conn,
    )
    # Code's literal '+' must be preserved; the schwabdev-shape truncation
    # at the first '@' then yields "ABC+DEF@".
    assert captured["data"]["code"] == "ABC+DEF@", (
        f"expected 'ABC+DEF@' (literal '+'), got {captured['data']['code']!r}"
    )


# ===========================================================================
# Codex R1 Major #2 regression — schwabdev tokens-file format compatibility.
# Imports REAL schwabdev (no stub) + asserts our written tokens file is
# loadable via the same json.load() schwabdev's Tokens.__init__ uses.
# Slow-marked because it imports real schwabdev.
# ===========================================================================


@pytest.mark.slow
def test_written_tokens_file_loadable_by_real_schwabdev_format(
    tmp_path, monkeypatch,
):
    """Major #2 — write a synthetic tokens file via
    ``_write_schwabdev_tokens_file`` + invoke real schwabdev
    ``Tokens.__init__`` against it. Assert ``tokens.access_token`` and
    ``tokens.refresh_token`` reflect the values WE wrote, proving real
    schwabdev's loader byte-for-byte accepts our format.

    Codex R2 Major #1 fix — previously this test re-implemented
    schwabdev's load semantics in test code (json.load + .get keys +
    fromisoformat); if schwabdev's loader were to change (e.g. rename
    ``token_dictionary`` to ``tokens`` or require new timestamp fields),
    the test would still PASS because it never touched schwabdev's own
    code. Now we construct the REAL ``schwabdev.tokens.Tokens(...)``
    against our written file + verify the resulting object's tokens
    match the sentinels we wrote.

    Network-I/O suppression — ``Tokens.__init__`` calls
    ``self.update_tokens()`` after loading. With fresh ISO-8601
    timestamps (issued_at = now()), the access-token-delta (1800s
    budget) and refresh-token-delta (604800s budget) both exceed the
    refresh thresholds (61s + 1800s respectively), so ``update_tokens()``
    returns False without any HTTP call. Defensive: we monkeypatch
    ``requests.post`` to raise if ever invoked during construction;
    test confirms it is NOT called.

    See ``schwabdev/tokens.py:52-66`` in the installed library for the
    canonical load shape.
    """
    import datetime
    import logging
    import types

    import requests

    # Import real schwabdev to assert it is importable + the Tokens class
    # exists. If schwabdev is renamed/removed, this fails fast.
    import schwabdev
    assert hasattr(schwabdev, "Client"), "schwabdev.Client surface missing"

    from schwabdev import tokens as schwabdev_tokens_mod
    assert hasattr(schwabdev_tokens_mod, "Tokens"), (
        "schwabdev.tokens.Tokens class missing — library format may have "
        "changed; setup_paste_flow_with_callback_url's tokens-file write "
        "may need updating"
    )

    from swing.integrations.schwab.auth import _write_schwabdev_tokens_file

    tokens_path = tmp_path / "schwab-tokens.production.db"
    sentinel_access = "fresh_access_token_for_compat_test_xyz"
    sentinel_refresh = "fresh_refresh_token_for_compat_test_abc"
    token_dict = {
        "access_token": sentinel_access,
        "refresh_token": sentinel_refresh,
        "token_type": "Bearer",
        "expires_in": 1800,
        "scope": "api",
    }
    # Fresh issued_at so update_tokens() short-circuits without HTTP.
    issued_at = datetime.datetime.now(datetime.timezone.utc)
    _write_schwabdev_tokens_file(
        tokens_path=tokens_path,
        token_dictionary=token_dict,
        issued_at=issued_at,
    )

    # Defensive: any HTTP call during construction means our timestamp
    # assumption is wrong + the test is no longer hermetic. Raise loudly.
    def _no_network(*_args, **_kwargs):  # noqa: D401
        raise AssertionError(
            "schwabdev.Tokens.__init__ attempted a network call — the "
            "fresh-issued_at assumption no longer holds; investigate "
            "schwabdev's update_tokens() threshold or library format drift"
        )

    monkeypatch.setattr(requests, "post", _no_network)

    # Real schwabdev.Tokens requires a `client` with a `.logger`
    # attribute. SimpleNamespace stub is sufficient.
    fake_client = types.SimpleNamespace(
        logger=logging.getLogger(
            "test_schwabdev_compat.tokens_format_validation",
        ),
    )
    # _validate_input enforces app_key len in (32, 48), app_secret len
    # in (16, 64), callback_url startswith https + no trailing /.
    app_key = "a" * 32
    app_secret = "b" * 16
    callback_url = "https://127.0.0.1"

    # Construct REAL schwabdev.Tokens — exercises the full json.load +
    # field extraction + update_tokens path. If schwabdev's private
    # format changes (renamed key, new required field, different
    # timestamp semantics), this construction fails loudly.
    tokens = schwabdev_tokens_mod.Tokens(
        client=fake_client,
        app_key=app_key,
        app_secret=app_secret,
        callback_url=callback_url,
        tokens_file=str(tokens_path),
    )

    # Assert the loaded values match what we wrote — proves byte-for-
    # byte compatibility through schwabdev's own load code path.
    assert tokens.access_token == sentinel_access, (
        f"schwabdev loader returned wrong access_token: "
        f"{tokens.access_token!r} (expected {sentinel_access!r})"
    )
    assert tokens.refresh_token == sentinel_refresh, (
        f"schwabdev loader returned wrong refresh_token: "
        f"{tokens.refresh_token!r} (expected {sentinel_refresh!r})"
    )
