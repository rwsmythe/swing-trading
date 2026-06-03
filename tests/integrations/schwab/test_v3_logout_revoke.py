"""T7: logout reads the refresh_token from v3 SQLite, reorders to rename-first/
best-effort-revoke, falls back to delete-without-revoke, and surfaces a clean error
on a hard rename failure -- never a silent partial state.

Adapted from the plan's illustrative tests: auth.py imports `requests` locally, so we
patch the cached `requests.post` (not a non-existent `auth.requests`); `auth.os` is the
module-level os, so `auth.os.replace` is patchable.
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab import auth


class _Cfg:
    class integrations:
        class schwab:
            timeout_seconds = 5


def _cfg():
    return _Cfg()


def _fresh_v3(tmp_path) -> Path:
    p = tmp_path / "schwab-tokens.production.db"
    auth._write_schwabdev_tokens_db(
        tokens_path=p,
        token_dictionary={"access_token": "AT", "refresh_token": "RT-revoke-me",
                          "id_token": "ID", "expires_in": 1800, "token_type": "Bearer",
                          "scope": "api"},
        issued_at=datetime.now(timezone.utc), fernet_key=None)
    return p


def test_t7a_fresh_db_revoke_and_rename(tmp_path, monkeypatch) -> None:
    import requests
    p = _fresh_v3(tmp_path)
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    conn = ensure_schema(tmp_path / "swing.db")
    mock_post = MagicMock(return_value=type("R", (), {"status_code": 200})())
    monkeypatch.setattr(requests, "post", mock_post)
    auth.revoke_and_delete(_cfg(), "production", "id", "secret", conn, force=True)
    # Pre-fix: json.load on the SQLite DB raised -> SchwabApiError, DB never renamed.
    # Post-fix: refresh_token read from SQLite -> revoke body carries RT-revoke-me; DB renamed.
    assert mock_post.call_args.kwargs["data"]["token"] == "RT-revoke-me"
    assert not p.exists()  # renamed aside


def test_t7c_old_format_fallback_renames_with_warning(tmp_path, monkeypatch, caplog) -> None:
    import requests
    p = tmp_path / "schwab-tokens.production.db"
    p.write_text('{"legacy": true}')  # old/unreadable as SQLite
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    conn = ensure_schema(tmp_path / "swing.db")
    mock_post = MagicMock()
    monkeypatch.setattr(requests, "post", mock_post)
    with caplog.at_level("WARNING"):
        auth.revoke_and_delete(_cfg(), "production", "id", "secret", conn, force=True)
    # Delete-without-revoke fallback: DB STILL renamed aside + a WARNING (not server-revoked).
    assert not p.exists()
    mock_post.assert_not_called()
    assert any("not server-side revoked" in r.message or "not revoked" in r.message.lower()
               for r in caplog.records)


def test_t7d_hard_rename_failure_clean_error(tmp_path, monkeypatch) -> None:
    p = _fresh_v3(tmp_path)
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    conn = ensure_schema(tmp_path / "swing.db")

    def _raise(*a, **k):
        raise PermissionError("file in use")

    # Simulate a locked/file-in-use rename failure through the bounded-retry path.
    monkeypatch.setattr(auth.os, "replace", _raise)
    with pytest.raises(Exception) as ei:  # a CLEAN actionable error, not a silent partial state
        auth.revoke_and_delete(_cfg(), "production", "id", "secret", conn, force=True)
    assert "retry" in str(ei.value).lower() or "close other" in str(ei.value).lower()
