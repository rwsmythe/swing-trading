"""T2/T4/T5: the v3 reader returns presence-only fields, tolerates a locked DB, and
detects the old format."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from swing.cli_schwab import _read_tokens_metadata
from swing.integrations.schwab import auth


def _write_v3(tmp_path) -> Path:
    p = tmp_path / "schwab-tokens.production.db"
    auth._write_schwabdev_tokens_db(
        tokens_path=p,
        token_dictionary={"access_token": "AT", "refresh_token": "RT", "id_token": "ID",
                          "expires_in": 1800, "token_type": "Bearer", "scope": "api"},
        issued_at=datetime.now(timezone.utc), fernet_key=None)
    return p


def test_t2_reader_returns_no_secret_bytes(tmp_path) -> None:
    meta, err = _read_tokens_metadata(_write_v3(tmp_path))
    assert err is None
    # Post-fix: presence-only fields; NO access_token / refresh_token VALUE present.
    assert set(meta) == {"access_token_issued", "refresh_token_issued", "expires_in",
                         "refresh_token_present"}
    assert "AT" not in str(meta) and "RT" not in str(meta)
    assert meta["refresh_token_present"] is True


def test_t5_old_format_json_detected(tmp_path) -> None:
    p = tmp_path / "schwab-tokens.production.db"
    p.write_text('{"token_dictionary": {"refresh_token": "RT"}}')  # 2.x JSON
    meta, err = _read_tokens_metadata(p)
    # Pre-fix: json.load succeeded on JSON; on a v3 SQLite it would crash. Post-fix:
    # SQLite open of JSON -> DatabaseError -> actionable old-format message, meta None.
    assert meta is None and err is not None and "logout" in err


def test_t4_locked_db_tolerated(tmp_path) -> None:
    p = _write_v3(tmp_path)
    holder = sqlite3.connect(str(p))
    holder.execute("BEGIN EXCLUSIVE")
    try:
        meta, err = _read_tokens_metadata(p)
        # mode=ro read under an exclusive lock -> OperationalError -> "busy" message, no crash.
        assert meta is None and err is not None and "busy" in err.lower()
    finally:
        holder.rollback()
        holder.close()
