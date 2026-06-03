"""T8/T9: the comprehensive preflight runs BEFORE non-setup construction and converts
old-format / stale-refresh / key-loss into a clean SchwabAuthError -- never a raw
DatabaseError, never an interactive prompt, never a leaked lock."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import schwabdev

from swing.integrations.schwab import auth
from swing.integrations.schwab.auth import SchwabAuthError


class _Cfg:
    class integrations:
        class schwab:
            callback_url = "https://127.0.0.1"
            timeout_seconds = 5


def _cfg():
    return _Cfg()


def _td() -> dict:
    return {"access_token": "AT", "refresh_token": "RT", "id_token": "ID",
            "expires_in": 1800, "token_type": "Bearer", "scope": "api"}


def test_t8_old_format_raises_before_construct(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "schwab-tokens.production.db"
    p.write_text('{"token_dictionary": {}}')  # 2.x JSON
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    constructed = {"n": 0}
    monkeypatch.setattr(schwabdev, "Client", lambda **k: constructed.__setitem__("n", 1))
    # Pre-fix: schwabdev.Client opens JSON-as-SQLite -> raw DatabaseError. Post-fix:
    # preflight raises SchwabAuthError BEFORE Client is constructed.
    with pytest.raises(SchwabAuthError):
        auth.construct_authenticated_client(_cfg(), "production", "id", "secret")
    assert constructed["n"] == 0  # never reached construction


def test_t9a_stale_refresh_raises_no_input(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "schwab-tokens.production.db"
    stale = datetime.now(timezone.utc) - timedelta(days=7)  # within 3630s of the 7d window
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary=_td(),
                                    issued_at=stale, fernet_key=None)
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("interactive prompt fired"))
    with pytest.raises(SchwabAuthError):
        auth._assert_v3_tokens_db_loadable_or_raise(p, fernet_key=None)


def test_t9b_keyloss_on_construction_path(tmp_path: Path) -> None:
    # enc:-prefixed columns but NO key configured -> clean key-loss SchwabAuthError.
    p = tmp_path / "schwab-tokens.production.db"
    key = auth._generate_fernet_key()
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary=_td(),
                                    issued_at=datetime.now(timezone.utc), fernet_key=key)
    with pytest.raises(SchwabAuthError):
        auth._assert_v3_tokens_db_loadable_or_raise(p, fernet_key=None)


def test_t9c_residual_race_guard_leaves_no_locked_db(tmp_path: Path, monkeypatch) -> None:
    """The residual-race BELT: if _raise_on_auth fires during construction, the wrapper
    drops refs + gc.collect()s so schwabdev's open BEGIN EXCLUSIVE releases -- a follow-up
    tokens read must SUCCEED, not hit 'database is locked'."""
    import gc
    import sqlite3

    db = tmp_path / "schwab-tokens.production.db"
    # An EMPTY v3 DB (table only, no row) forces v3 into the interactive refresh path at
    # construction; _raise_on_auth converts that to SchwabAuthError mid-construct.
    conn0 = sqlite3.connect(str(db))
    conn0.execute(auth._V3_SCHWABDEV_DDL)
    conn0.commit()
    conn0.close()
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: db)
    with pytest.raises(auth.SchwabAuthError):
        auth._construct_v3_client_with_guard(
            tokens_path=db, app_key="k" * 32, app_secret="s" * 16,
            callback_url="https://127.0.0.1", encryption=None, timeout=5)
    gc.collect()  # belt-and-suspenders; the wrapper already did this on the raise path
    # Pre-fix risk: schwabdev's BEGIN EXCLUSIVE (no try/finally around call_for_auth) leaves
    # the connection locked -> this read raises OperationalError. Post-fix: it succeeds.
    conn1 = sqlite3.connect(str(db), timeout=2)
    rows = conn1.execute("SELECT COUNT(*) FROM schwabdev").fetchone()[0]
    conn1.close()
    assert rows == 0
