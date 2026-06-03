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


def test_v3_schwabdev_ddl_matches_live_install(tmp_path: Path) -> None:
    """T1b: introspect the LIVE schwabdev table vs our pinned _V3_SCHWABDEV_DDL.
    NON-INTERACTIVE + deterministic lock release (R3-M1). This guard makes the
    OQ-3 floored pin (>=3.0.5,<4.0.0) merge-safe: a future 3.x that silently
    changes the private schema fails this test loudly."""
    import sqlite3

    db = tmp_path / "schwab-tokens.production.db"
    # Construct a real Client against an EMPTY tokens_db WITH the guard; v3 CREATEs +
    # commits the schwabdev table BEFORE the auth flow's BEGIN EXCLUSIVE (tokens.py:80,93,398),
    # then enters the interactive refresh path -> our _raise_on_auth fires.
    try:
        client = schwabdev.Client(
            app_key="k" * 32, app_secret="s" * 16, callback_url="https://127.0.0.1",
            tokens_db=str(db), call_on_auth=auth._raise_on_auth,
            open_browser_for_auth=False, timeout=5,
        )
        client = None  # pragma: no cover - guard should have raised
    except auth.SchwabAuthError:
        pass
    # DETERMINISTIC lock release: schwabdev holds an open BEGIN EXCLUSIVE (no try/finally
    # around call_for_auth). Drop locals + gc so the next connection is not "database is locked".
    locals().pop("client", None)
    gc.collect()

    conn = sqlite3.connect(str(db))
    cols = [(r[1], r[2]) for r in conn.execute("PRAGMA table_info(schwabdev)").fetchall()]
    conn.close()
    expected = [
        ("access_token_issued", "TEXT"), ("refresh_token_issued", "TEXT"),
        ("access_token", "TEXT"), ("refresh_token", "TEXT"), ("id_token", "TEXT"),
        ("expires_in", "INTEGER"), ("token_type", "TEXT"), ("scope", "TEXT"),
    ]
    # Pre-fix risk this guards: a future 3.x silently changing the private schema.
    # Post-fix: the live table matches our pinned 8-col copy.
    assert cols == expected, (
        f"schwabdev private table DDL drifted: live={cols} pinned={expected}. "
        "The W-A writer copies this DDL; the OQ-3 floored pin is unsafe until reconciled."
    )
