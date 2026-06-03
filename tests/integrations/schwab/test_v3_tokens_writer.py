"""T1: our v3-SQLite writer produces a DB a REAL schwabdev.Client constructs against.
Plus the pure cipher-helper round-trip (the helpers land in Slice 2; Slice 4 wires the
cfg key source)."""
import gc
from datetime import datetime, timezone
from pathlib import Path

import schwabdev

from swing.integrations.schwab import auth


def test_generate_and_cipher_roundtrip() -> None:
    key = auth._generate_fernet_key()
    assert isinstance(key, str) and len(key) > 16
    cipher = auth._fernet_cipher(key)
    assert cipher.decrypt(cipher.encrypt(b"secret-bytes")) == b"secret-bytes"


def test_writer_produces_loadable_v3_db(tmp_path: Path) -> None:
    tokens_path = tmp_path / "schwab-tokens.production.db"
    token_dictionary = {
        "access_token": "AT-abc", "refresh_token": "RT-def", "id_token": "ID-ghi",
        "expires_in": 1800, "token_type": "Bearer", "scope": "api",
    }
    issued = datetime.now(timezone.utc)
    # Pre-fix path: _write_schwabdev_tokens_file writes JSON -> schwabdev.Client() opening
    #   it as SQLite raises DatabaseError -> FAIL.
    # Post-fix path: writer emits the 8-col schwabdev row -> Client loads tokens.access_token.
    auth._write_schwabdev_tokens_db(
        tokens_path=tokens_path, token_dictionary=token_dictionary,
        issued_at=issued, fernet_key=None,
    )
    client = schwabdev.Client(
        app_key="k" * 32, app_secret="s" * 16, callback_url="https://127.0.0.1",
        tokens_db=str(tokens_path), call_on_auth=auth._raise_on_auth,
        open_browser_for_auth=False, timeout=5,
    )
    try:
        assert client.tokens.access_token == "AT-abc"
    finally:
        del client
        gc.collect()
