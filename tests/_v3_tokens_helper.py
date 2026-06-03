"""Shared test helper: write a v3 schwabdev SQLite tokens DB (Task 2.8 migration).

NOT a test module (no ``test_`` prefix -> not collected). Gives per-column control over
the issued timestamps + optional Fernet encryption, which the production
``_write_schwabdev_tokens_db`` (single ``issued_at``) cannot express -- needed by the
degraded / expiry-boundary status tests.
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def write_v3_tokens_db(
    path: Path,
    *,
    access_token: str = "AT",
    refresh_token: str = "RT",
    id_token: str = "ID",
    expires_in: int = 1800,
    token_type: str = "Bearer",
    scope: str = "api",
    access_token_issued: str | None = None,
    refresh_token_issued: str | None = None,
    fernet_key: str | None = None,
) -> Path:
    """Write a single-row v3 ``schwabdev`` SQLite tokens DB at ``path``."""
    from swing.integrations.schwab.auth import _V3_SCHWABDEV_DDL, _fernet_cipher

    now_iso = datetime.now(UTC).isoformat()
    # Distinguish None (use default fresh timestamp) from "" (an explicit empty value the
    # degraded-state tests need to exercise Signal 5).
    at_issued = now_iso if access_token_issued is None else access_token_issued
    rt_issued = now_iso if refresh_token_issued is None else refresh_token_issued
    cipher = _fernet_cipher(fernet_key) if fernet_key else None

    def _enc(value: str) -> str:
        return ("enc:" + cipher.encrypt(value.encode()).decode()) if cipher else value

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(_V3_SCHWABDEV_DDL)
        conn.execute("DELETE FROM schwabdev")
        conn.execute(
            "INSERT INTO schwabdev (access_token_issued, refresh_token_issued, "
            "access_token, refresh_token, id_token, expires_in, token_type, scope) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (at_issued, rt_issued, _enc(access_token), _enc(refresh_token),
             id_token, expires_in, token_type, scope),
        )
        conn.commit()
    finally:
        conn.close()
    return path
