"""Each schwabdev.Client construction site passes tokens_db= (v3), not tokens_file= (2.x).

Tree divergence from the plan's illustrative test: auth.py has NO module-level
`import schwabdev` -- every construction function does a LOCAL `import schwabdev`,
so we patch `schwabdev.Client` on the cached module (which the local import resolves to),
not a non-existent `auth.schwabdev` attribute.
"""
from unittest.mock import patch

import schwabdev

from swing.integrations.schwab import auth


class _FakeCfg:
    class integrations:
        class schwab:
            callback_url = "https://127.0.0.1"
            timeout_seconds = 5


def _fake_client_capture(captured: dict):
    class _FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.tokens = type("T", (), {"access_token": "x", "refresh_token": "y"})()

    return _FakeClient


def test_construct_authenticated_client_passes_tokens_db(monkeypatch, tmp_path) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        auth, "_resolve_tokens_db_path", lambda env: tmp_path / "schwab-tokens.production.db"
    )
    # No-op the Slice-2 preflight so this mechanical kwarg test reaches construction.
    monkeypatch.setattr(auth, "_assert_v3_tokens_db_loadable_or_raise", lambda *a, **k: None)
    with patch.object(schwabdev, "Client", _fake_client_capture(captured)):
        try:
            auth.construct_authenticated_client(_FakeCfg(), "production", "id", "secret")
        except Exception:
            pass
    # Pre-fix path: captured has 'tokens_file'; 'tokens_db' absent -> FAIL.
    # Post-fix path: captured has 'tokens_db'; 'tokens_file' absent -> PASS.
    assert "tokens_db" in captured
    assert "tokens_file" not in captured


def test_nonsetup_sites_pass_raise_on_auth_and_no_browser(monkeypatch, tmp_path) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        auth, "_resolve_tokens_db_path", lambda env: tmp_path / "schwab-tokens.production.db"
    )
    # Robust across Slice 2: once the preflight (Task 2.6) is wired before construction,
    # no-op it so this test still reaches the Client() call to inspect its kwargs.
    monkeypatch.setattr(
        auth, "_assert_v3_tokens_db_loadable_or_raise", lambda *a, **k: None, raising=False
    )
    with patch.object(schwabdev, "Client", _fake_client_capture(captured)):
        try:
            auth.construct_authenticated_client(_FakeCfg(), "production", "id", "secret")
        except Exception:
            pass
    # Pre-fix: captured lacks call_on_auth / open_browser_for_auth -> FAIL.
    # Post-fix: both present; open_browser_for_auth is False; call_on_auth is callable.
    assert captured.get("open_browser_for_auth") is False
    assert callable(captured.get("call_on_auth"))


def test_raise_on_auth_raises_schwab_auth_error() -> None:
    import pytest

    from swing.integrations.schwab.auth import SchwabAuthError, _raise_on_auth
    with pytest.raises(SchwabAuthError):
        _raise_on_auth("https://example/auth-url")  # never prompts; always raises
