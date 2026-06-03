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
    with patch.object(schwabdev, "Client", _fake_client_capture(captured)):
        try:
            auth.construct_authenticated_client(_FakeCfg(), "production", "id", "secret")
        except Exception:
            pass
    # Pre-fix path: captured has 'tokens_file'; 'tokens_db' absent -> FAIL.
    # Post-fix path: captured has 'tokens_db'; 'tokens_file' absent -> PASS.
    assert "tokens_db" in captured
    assert "tokens_file" not in captured
