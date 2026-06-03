"""OQ-1 Fernet cfg source: key resolution + masking (the cipher helpers are Slice 2)."""
import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

from swing.data.db import ensure_schema
from swing.integrations.schwab import auth


class _SchwabCfg:
    def __init__(self, encryption_key):
        self.encryption_key = encryption_key
        self.timeout_seconds = 5


class _Cfg:
    def __init__(self, *, encryption_key=None):
        self.integrations = type("I", (), {"schwab": _SchwabCfg(encryption_key)})()


def _cfg(*, encryption_key=None):
    return _Cfg(encryption_key=encryption_key)


def test_resolve_fernet_key_none_when_absent() -> None:
    assert auth._resolve_fernet_key(_cfg(encryption_key=None)) is None
    assert auth._resolve_fernet_key(_cfg(encryption_key="")) is None


def test_resolve_fernet_key_value_when_present() -> None:
    k = auth._generate_fernet_key()
    assert auth._resolve_fernet_key(_cfg(encryption_key=k)) == k


def test_config_show_masks_encryption_key(monkeypatch, tmp_path) -> None:
    # swing config show MUST mask encryption_key like client_secret.
    from click.testing import CliRunner

    from swing.cli import main

    key = auth._generate_fernet_key()
    # Monkeypatch BOTH USERPROFILE and HOME so write_user_overrides cannot leak to the
    # operator's real ~/swing-data (CLAUDE.md test-discipline gotcha).
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    swing_data = tmp_path / "swing-data"
    swing_data.mkdir(parents=True, exist_ok=True)
    (swing_data / "user-config.toml").write_text(
        f'[integrations.schwab]\nencryption_key = "{key}"\n', encoding="utf-8")
    result = CliRunner().invoke(main, ["config", "show"])
    assert result.exit_code == 0, result.output
    # Pre-fix: encryption_key unknown to config-show -> printed raw OR absent. Post-fix:
    # the key is present-but-masked; the RAW key bytes never appear.
    assert key not in result.output
    assert "encryption_key" in result.output  # the field IS surfaced (masked), not hidden
    assert "***" in result.output  # the mask token used for client_secret


def _td() -> dict:
    return {"access_token": "AT", "refresh_token": "RT", "id_token": "ID",
            "expires_in": 1800, "token_type": "Bearer", "scope": "api"}


def test_writer_enc_wraps_when_key_present(tmp_path) -> None:
    import gc

    import schwabdev
    key = auth._generate_fernet_key()
    p = tmp_path / "schwab-tokens.production.db"
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary=_td(),
                                    issued_at=datetime.now(timezone.utc), fernet_key=key)
    row = sqlite3.connect(str(p)).execute(
        "SELECT access_token, refresh_token FROM schwabdev").fetchone()
    # Pre-fix (key threaded but ignored): plaintext 'AT'/'RT'. Post-fix: enc:-prefixed.
    assert row[0].startswith("enc:") and row[1].startswith("enc:")
    # And a real Client(encryption=key) loads it:
    c = schwabdev.Client(app_key="k" * 32, app_secret="s" * 16,
                         callback_url="https://127.0.0.1", tokens_db=str(p), encryption=key,
                         call_on_auth=auth._raise_on_auth, open_browser_for_auth=False, timeout=5)
    try:
        assert c.tokens.access_token == "AT"
    finally:
        del c
        gc.collect()


def test_setup_generates_and_persists_key_then_enc_wraps(tmp_path, monkeypatch) -> None:
    """CRITICAL (Codex R1): on a fresh operator with NO encryption_key configured, setup
    GENERATES a key, persists it (masked) to user-config, and the tokens DB it writes is
    enc:-wrapped -- otherwise 'Fernet shipped' is false and setup silently writes plaintext."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    tokens_path = tmp_path / "swing-data" / "schwab-tokens.production.db"
    tokens_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: tokens_path)

    returned = auth._ensure_fernet_key_then_write_tokens(
        cfg=_cfg(encryption_key=None), environment="production", token_dictionary=_td())

    # Pre-fix: setup writes plaintext (no key generated) -> columns are 'AT'/'RT'.
    # Post-fix: a key was generated + persisted; columns are enc:-prefixed.
    row = sqlite3.connect(str(tokens_path)).execute(
        "SELECT access_token, refresh_token FROM schwabdev").fetchone()
    assert row[0].startswith("enc:") and row[1].startswith("enc:")
    # The generated key is persisted in user-config (so the NEXT construction decrypts):
    persisted = (tmp_path / "swing-data" / "user-config.toml").read_text(encoding="utf-8")
    assert "encryption_key" in persisted and returned in persisted


def test_keygen_persist_preserves_existing_credentials(tmp_path, monkeypatch) -> None:
    """Codex R2 MAJOR-2: generating the key must MERGE into user-config, not clobber the
    operator's client_id/client_secret (which would break the logout->setup->fetch gate)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_dir = tmp_path / "swing-data"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "user-config.toml").write_text(
        '[integrations.schwab]\nclient_id = "CID"\nclient_secret = "CSECRET"\n'
        'environment = "production"\n', encoding="utf-8")
    auth._persist_generated_encryption_key(auth._generate_fernet_key())
    merged = (cfg_dir / "user-config.toml").read_text(encoding="utf-8")
    # Pre-fix: write_user_overrides clobbered the dict -> client_id/secret GONE.
    # Post-fix: load/merge/write preserved them AND added the key.
    assert "CID" in merged and "CSECRET" in merged and 'environment = "production"' in merged
    assert "encryption_key" in merged


def test_t7b_logout_decrypts_encrypted_refresh(tmp_path, monkeypatch) -> None:
    import requests
    key = auth._generate_fernet_key()
    p = tmp_path / "schwab-tokens.production.db"
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary={
        "access_token": "AT", "refresh_token": "RT-secret", "id_token": "ID",
        "expires_in": 1800, "token_type": "Bearer", "scope": "api"},
        issued_at=datetime.now(timezone.utc), fernet_key=key)
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    monkeypatch.setattr(auth, "_resolve_fernet_key", lambda cfg: key)
    conn = ensure_schema(tmp_path / "swing.db")
    with patch.object(requests, "post",
                      return_value=type("R", (), {"status_code": 200})()) as rq:
        auth.revoke_and_delete(_cfg(), "production", "id", "secret", conn, force=True)
        # revoke body carries the DECRYPTED plaintext, not the enc: ciphertext.
        assert rq.call_args.kwargs["data"]["token"] == "RT-secret"


def test_t7e_encrypted_db_missing_key_falls_back_no_revoke(tmp_path, monkeypatch, caplog) -> None:
    """Key-loss on logout: enc: DB but no configured key -> NO ciphertext POSTed; DB still
    renamed aside; WARNING emitted (Codex R1 MAJOR)."""
    import requests
    key = auth._generate_fernet_key()
    p = tmp_path / "schwab-tokens.production.db"
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary=_td(),
                                    issued_at=datetime.now(timezone.utc), fernet_key=key)
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    monkeypatch.setattr(auth, "_resolve_fernet_key", lambda cfg: None)  # key LOST
    conn = ensure_schema(tmp_path / "swing.db")
    with patch.object(requests, "post") as rq:
        auth.revoke_and_delete(_cfg(), "production", "id", "secret", conn, force=True)
        rq.assert_not_called()  # undecryptable -> revoke NEVER attempted
    assert not p.exists()  # still renamed aside


def test_t7f_encrypted_db_wrong_key_falls_back_no_revoke(tmp_path, monkeypatch) -> None:
    """A WRONG key must also yield None (no ciphertext POST), not a decrypt exception."""
    import requests
    p = tmp_path / "schwab-tokens.production.db"
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary=_td(),
                                    issued_at=datetime.now(timezone.utc),
                                    fernet_key=auth._generate_fernet_key())
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    monkeypatch.setattr(auth, "_resolve_fernet_key", lambda cfg: auth._generate_fernet_key())
    conn = ensure_schema(tmp_path / "swing.db")
    with patch.object(requests, "post") as rq:
        auth.revoke_and_delete(_cfg(), "production", "id", "secret", conn, force=True)
        rq.assert_not_called()
    assert not p.exists()
