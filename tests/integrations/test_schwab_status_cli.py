"""T-A.6 — `swing schwab status` CLI tests.

8 binding tests per plan §Tasks-A T-A.6 acceptance criteria.

Test discipline mirrors T-A.4 + T-A.5:
  - USERPROFILE+HOME monkeypatch (CLAUDE.md gotcha).
  - Tokens file shaped per recon §6.bis (JSON with `access_token_issued`,
    `refresh_token_issued`, `token_dictionary`).
  - Discriminating sentinel-leak test: plant known sentinel access_token +
    refresh_token bytes in the JSON tokens file; assert ZERO occurrences in
    `swing schwab status` stdout/stderr (the binding contract).
  - account_hash masking via `swing.config_validation.mask_sensitive_value`
    pattern (FIRST 3 + *** + LAST 2; per spec §3.5 mock).
  - `--environment` flag override resolves the correct per-env tokens path.

T-A.6 binding constraints (per dispatch brief + spec §3.5 + recon §6.bis):
  - READ-ONLY surface: no schwabdev.Client construction; no operator prompts;
    no `--force` flag.
  - 4 output sections: env header; cfg + tokens-file metadata; token validity;
    recent API calls (last 5).
  - Token bytes (access_token / refresh_token / id_token) NEVER in stdout.
  - schema-version check via `connect()` runs first (T-A.4 hotfix D3 pattern).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import UTC
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main

# Sentinel bytes. Test #2 (binding) asserts these never appear in stdout.
_SENTINEL_ACCESS_TOKEN = "SENTINEL_ACCESS_TOKEN_DO_NOT_LEAK_ABC123XYZ"
_SENTINEL_REFRESH_TOKEN = "SENTINEL_REFRESH_TOKEN_DO_NOT_LEAK_ZYX987ABC"
_SENTINEL_ID_TOKEN = "SENTINEL_ID_TOKEN_DO_NOT_LEAK_MMM999NNN"


# ============================================================================
# Fixtures (mirror T-A.5 test_schwab_refresh_logout_cli.py)
# ============================================================================


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated USERPROFILE+HOME pointing at tmp_path (CLAUDE.md gotcha)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def cfg_path(home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy of project's swing.config.toml with path overrides routed to
    tmp_path (mirrors T-A.4/T-A.5 fixture).
    """
    repo_root = Path(__file__).resolve().parents[2]
    src_cfg = repo_root / "swing.config.toml"
    cfg_text = src_cfg.read_text()
    db_path = home / "swing-data" / "swing.db"
    home_swing_data = (home / "swing-data").as_posix()
    home_finviz = (home / "finviz-inbox").as_posix()
    home_exports = (home / "exports").as_posix()
    home_rs = (home / "rs.csv").as_posix()
    new_paths_block = f"""[paths]
db_path = "{db_path.as_posix()}"
data_dir = "{home_swing_data}"
logs_dir = "{home_swing_data}/logs"
charts_dir = "{home_swing_data}/charts"
backups_dir = "{home_swing_data}/backups"
prices_cache_dir = "{home_swing_data}/prices-cache"
finviz_inbox_dir = "{home_finviz}"
exports_dir = "{home_exports}"
rs_universe_path = "{home_rs}"
"""
    cfg_text = re.sub(
        r"\[paths\]\n(?:[^\[]+)",
        new_paths_block + "\n",
        cfg_text,
        count=1,
    )
    cfg_file = home / "swing.config.toml"
    cfg_file.write_text(cfg_text)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    from swing.data.db import ensure_schema
    ensure_schema(db_path).close()
    return cfg_file


def _write_tokens_file(
    home: Path,
    *,
    env: str = "production",
    access_token_issued: str = "2026-05-14T11:28:13.234697+00:00",
    refresh_token_issued: str = "2026-05-14T11:28:13.234697+00:00",
    access_token: str = _SENTINEL_ACCESS_TOKEN,
    refresh_token: str = _SENTINEL_REFRESH_TOKEN,
    id_token: str = _SENTINEL_ID_TOKEN,
    expires_in: int = 1800,
) -> Path:
    """Write a v3 schwabdev SQLite tokens DB (Task 2.8 migration from the 2.x JSON)."""
    from tests._v3_tokens_helper import write_v3_tokens_db

    path = home / "swing-data" / f"schwab-tokens.{env}.db"
    return write_v3_tokens_db(
        path,
        access_token=access_token,
        refresh_token=refresh_token,
        id_token=id_token,
        expires_in=expires_in,
        access_token_issued=access_token_issued,
        refresh_token_issued=refresh_token_issued,
    )


def _invoke(cfg_path: Path, args: list) -> object:
    runner = CliRunner()
    return runner.invoke(main, ["--config", str(cfg_path), "schwab", *args])


def _plant_audit_rows(db_path: Path, *, env: str = "production") -> None:
    """Plant some schwab_api_calls rows so the recent-calls section has
    content to render.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO schwab_api_calls ("
            "ts, endpoint, status, surface, environment, http_status"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-05-14T01:10:13", "oauth.code_exchange",
             "auth_failed", "cli", env, 200),
        )
        conn.execute(
            "INSERT INTO schwab_api_calls ("
            "ts, endpoint, status, surface, environment, http_status"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-05-14T01:14:19", "accounts.linked",
             "auth_failed", "cli", env, 200),
        )
        conn.execute(
            "INSERT INTO schwab_api_calls ("
            "ts, endpoint, status, surface, environment, http_status"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-05-14T01:27:39", "oauth.code_exchange",
             "success", "cli", env, 200),
        )
        conn.execute(
            "INSERT INTO schwab_api_calls ("
            "ts, endpoint, status, surface, environment, http_status"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-05-14T01:28:15", "accounts.linked",
             "success", "cli", env, 200),
        )
        conn.commit()
    finally:
        conn.close()


def _set_account_hash(home: Path, account_hash: str) -> None:
    """Persist account_hash to user-config.toml (cfg-cascade)."""
    from swing.config_user import load_user_overrides, write_user_overrides
    overrides = load_user_overrides()
    overrides.setdefault("integrations", {}).setdefault(
        "schwab", {},
    )["account_hash"] = account_hash
    write_user_overrides(overrides)


# ============================================================================
# Tests
# ============================================================================


def test_status_happy_path_renders_all_sections(
    home: Path, cfg_path: Path,
) -> None:
    """Test 1 — happy path. Tokens file exists with known dummy values;
    audit rows exist; account_hash set. Assert all 4 sections render +
    NO token bytes in output.
    """
    _set_account_hash(home, "A" * 60)  # 60-char synthetic hash
    _write_tokens_file(home, env="production")
    _plant_audit_rows(home / "swing-data" / "swing.db", env="production")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    # Section 1 — env header.
    assert "production" in result.output
    # Section 2 — cfg + tokens-file metadata.
    assert "account_hash" in result.output
    assert "Tokens DB" in result.output or "Tokens" in result.output
    # Section 3 — token validity (access + refresh).
    assert "Access token" in result.output or "access" in result.output.lower()
    assert "Refresh token" in result.output or "refresh" in result.output.lower()
    # Section 4 — recent API calls.
    assert "Recent API calls" in result.output or "recent" in result.output.lower()
    # 4 calls were planted — at least one endpoint name should render.
    assert "oauth.code_exchange" in result.output or "accounts.linked" in result.output
    # NO token bytes.
    assert _SENTINEL_ACCESS_TOKEN not in result.output
    assert _SENTINEL_REFRESH_TOKEN not in result.output
    assert _SENTINEL_ID_TOKEN not in result.output


def test_status_no_sentinel_token_leak_BINDING(  # noqa: N802
    home: Path, cfg_path: Path,
) -> None:
    """Test 2 (BINDING) — plant known sentinel tokens; assert ZERO matches
    in stdout / stderr. Mirrors plan §H.5 sentinel-leak audit + Phase 11
    Sub-bundle A T-A.10 forward-binding coverage extension. This is the
    discriminating contract for the status command's redaction discipline.
    """
    _write_tokens_file(home, env="production")
    _plant_audit_rows(home / "swing-data" / "swing.db", env="production")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    # Discriminating: zero matches.
    assert _SENTINEL_ACCESS_TOKEN not in result.output, (
        "access_token leaked to stdout — redaction broken"
    )
    assert _SENTINEL_REFRESH_TOKEN not in result.output, (
        "refresh_token leaked to stdout — redaction broken"
    )
    assert _SENTINEL_ID_TOKEN not in result.output, (
        "id_token leaked to stdout — redaction broken"
    )


def test_status_no_tokens_file(home: Path, cfg_path: Path) -> None:
    """Test 3 — tokens file does not exist; status surfaces a clean message
    + NO crash. NO Python traceback, NO 'FileNotFoundError'.
    """
    # No tokens file written.
    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    # Clean advisory message.
    assert "not present" in result.output or "not found" in result.output \
        or "no tokens" in result.output.lower() or "missing" in result.output.lower()
    assert "swing schwab setup" in result.output
    # No raw exception class.
    assert "Traceback" not in result.output


def test_status_tokens_file_unparseable(
    home: Path, cfg_path: Path,
) -> None:
    """Test 4 — file exists but is invalid JSON; status surfaces a clean
    error message + NO crash.
    """
    path = home / "swing-data" / "schwab-tokens.production.db"
    path.write_text("{this is not valid JSON [[[")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    # Clean parse-error message.
    out_lower = result.output.lower()
    assert (
        "unreadable" in out_lower or "invalid" in out_lower
        or "parse" in out_lower or "unparseable" in out_lower
        or "corrupt" in out_lower
    ), f"expected parse-error message; got: {result.output!r}"
    # No raw exception class.
    assert "Traceback" not in result.output


def test_status_expired_access_token(home: Path, cfg_path: Path) -> None:
    """Test 5 — access_token issued 60 minutes ago with expires_in=1800
    (30 minutes); access token is expired. Assert 'expired' messaging.
    """
    from datetime import datetime, timedelta
    issued = (datetime.now(UTC) - timedelta(minutes=60)).isoformat()
    # Refresh stays fresh.
    refresh_issued = datetime.now(UTC).isoformat()
    _write_tokens_file(
        home,
        env="production",
        access_token_issued=issued,
        refresh_token_issued=refresh_issued,
        expires_in=1800,
    )

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    # Access token expired.
    assert "expired" in result.output.lower()
    # Operator-actionable advisory.
    assert "swing schwab refresh" in result.output or \
        "swing schwab setup" in result.output


def test_status_expired_refresh_token(home: Path, cfg_path: Path) -> None:
    """Test 6 — refresh_token issued 8 days ago; refresh expires at 7 days.
    Assert 'expired' messaging + advisory to re-run setup.
    """
    from datetime import datetime, timedelta
    refresh_issued = (
        datetime.now(UTC) - timedelta(days=8)
    ).isoformat()
    access_issued = (
        datetime.now(UTC) - timedelta(days=8)
    ).isoformat()
    _write_tokens_file(
        home,
        env="production",
        access_token_issued=access_issued,
        refresh_token_issued=refresh_issued,
        expires_in=1800,
    )

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    # Refresh expired.
    assert "expired" in result.output.lower()
    # Operator must re-run setup (refresh alone cannot save them).
    assert "swing schwab setup" in result.output


def test_status_account_hash_masked(home: Path, cfg_path: Path) -> None:
    """Test 7 — account_hash rendered masked via FIELD_REGISTRY pattern
    (FIRST 3 + *** + LAST 2 chars). 64-char synthetic hash; middle 59
    chars MUST NOT appear in output.
    """
    full_hash = "ABCDEF" + "X" * 56 + "ZY"  # 64 chars; first 3 = "ABC", last 2 = "ZY"
    _set_account_hash(home, full_hash)
    _write_tokens_file(home, env="production")

    result = _invoke(cfg_path, ["status", "--environment", "production"])
    assert result.exit_code == 0, result.output
    # Masked form present.
    assert "ABC***ZY" in result.output, (
        f"expected masked 'ABC***ZY' in output; got: {result.output!r}"
    )
    # Full hash NEVER present.
    assert full_hash not in result.output
    # Middle 59 chars not present.
    middle = full_hash[3:-2]
    assert middle not in result.output


def test_status_environment_flag_override(home: Path, cfg_path: Path) -> None:
    """Test 8 — cfg env defaults to 'production' but --environment sandbox
    overrides. Tokens path MUST resolve to schwab-tokens.sandbox.db (NOT
    .production.db); audit-row filter MUST be env=sandbox.
    """
    # Plant tokens + audit rows for BOTH envs; status should select sandbox.
    _write_tokens_file(home, env="production",
                       access_token="PRODUCTION_DO_NOT_SHOW",
                       refresh_token="PRODUCTION_DO_NOT_SHOW_R",
                       id_token="PRODUCTION_DO_NOT_SHOW_I")
    _write_tokens_file(home, env="sandbox")
    _plant_audit_rows(home / "swing-data" / "swing.db", env="production")
    # Tag a sandbox-env audit row so we can pin the filter.
    conn = sqlite3.connect(home / "swing-data" / "swing.db")
    try:
        conn.execute(
            "INSERT INTO schwab_api_calls ("
            "ts, endpoint, status, surface, environment, http_status"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-05-14T02:00:00", "oauth.code_exchange",
             "success", "cli", "sandbox", 200),
        )
        conn.commit()
    finally:
        conn.close()

    result = _invoke(cfg_path, ["status", "--environment", "sandbox"])
    assert result.exit_code == 0, result.output
    # Sandbox env header.
    assert "sandbox" in result.output
    # Tokens path under sandbox (string match on filename — render must
    # surface the resolved path so the operator can verify).
    assert "schwab-tokens.sandbox.db" in result.output
    # Sandbox audit row visible.
    assert "2026-05-14T02:00:00" in result.output or \
        "02:00:00" in result.output
    # Production-only secrets (planted in production tokens file) MUST NOT
    # leak into a sandbox-scoped status call.
    assert "PRODUCTION_DO_NOT_SHOW" not in result.output
