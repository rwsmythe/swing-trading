"""T-A.5 — `swing schwab refresh` + `swing schwab logout` CLI tests.

10 binding tests per plan §Tasks-A T-A.5 acceptance criteria.

Test discipline mirrors T-A.4 (`test_schwab_setup_cli.py`):
  - USERPROFILE+HOME monkeypatch (CLAUDE.md gotcha).
  - schwabdev.Client stubbed BEFORE call site — no real network I/O.
  - Token sentinel discriminating tests assert that tokens never leak to
    stdout / audit-row error_message (plan §H.5 + lesson #19).
  - Audit row shape pinned post-call by direct SQLite query.

Refresh-specific contracts (per dispatch brief + Codex R1 Minor #3):
  - `swing schwab refresh` has NO `--force` flag (concurrent-safe).
  - Refresh proceeds even when pipeline is running.

Logout-specific contracts (per plan §F.3):
  - `swing schwab logout` accepts `--force` (overrides pipeline-active).
  - Issues manual POST /v1/oauth/revoke (schwabdev exposes no
    `Tokens.revoke`; recon §6 §C).
  - On revoke failure (network/non-200): tokens file STILL renamed to
    `<path>.deleted-<ts>` for 24h recovery window.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from swing.cli import main

# Sentinel token bytes. Must mirror T-A.4 pattern so the discriminating
# leak-detector tests stay symmetrical.
_SENTINEL_ACCESS_TOKEN = "AUTH_BYTES_DO_NOT_LEAK_ABCDEF0123456789012345"
_SENTINEL_REFRESH_TOKEN = "REFRESH_BYTES_DO_NOT_LEAK_ZYXWVU09876543210987"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated USERPROFILE+HOME pointing at tmp_path."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def cfg_path(home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy of project's swing.config.toml with path overrides routed to
    tmp_path (mirrors T-A.4 fixture).
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


@pytest.fixture
def tokens_file(home: Path) -> Path:
    """Pre-existing tokens file at the per-env path. Mirrors what schwabdev
    would have written at T-A.4 setup time. Sentinel access/refresh tokens
    so leak-detector tests can pin redaction.
    """
    path = home / "swing-data" / "schwab-tokens.production.db"
    payload = {
        "access_token_issued": "2026-05-14T11:28:13.234697+00:00",
        "refresh_token_issued": "2026-05-14T11:28:13.234697+00:00",
        "token_dictionary": {
            "expires_in": 1800,
            "token_type": "Bearer",
            "scope": "api",
            "refresh_token": _SENTINEL_REFRESH_TOKEN,
            "access_token": _SENTINEL_ACCESS_TOKEN,
        },
    }
    path.write_text(json.dumps(payload, indent=4))
    return path


class _FakeTokens:
    """Stand-in for `client.tokens` carrying sentinel bytes + the
    `update_tokens(force_access_token=...)` entry point used by `force_refresh`.

    Codex R1 Major #1 — `update_tokens` rotates `access_token` by default
    (mirrors live schwabdev behavior). Tests that need silent-failure
    semantics pass `rotate_on_update=False` to simulate schwabdev's
    suppressed-failure path.
    """

    def __init__(
        self,
        *,
        raise_on_update: BaseException | None = None,
        rotate_on_update: bool = True,
        rotated_access_token: str = "ROTATED_ACCESS_TOKEN_NEW_VALUE_0123456789",
        clear_access_on_update: bool = False,
    ) -> None:
        self.access_token = _SENTINEL_ACCESS_TOKEN
        self.refresh_token = _SENTINEL_REFRESH_TOKEN
        self._raise_on_update = raise_on_update
        self._rotate_on_update = rotate_on_update
        self._rotated_access_token = rotated_access_token
        self._clear_access_on_update = clear_access_on_update
        self.update_call_count = 0
        self.last_update_kwargs: dict | None = None

    def update_tokens(self, force_access_token: bool = False, force_refresh_token: bool = False) -> bool:
        self.update_call_count += 1
        self.last_update_kwargs = {
            "force_access_token": force_access_token,
            "force_refresh_token": force_refresh_token,
        }
        if self._raise_on_update is not None:
            raise self._raise_on_update
        if self._clear_access_on_update:
            self.access_token = None
        elif self._rotate_on_update:
            self.access_token = self._rotated_access_token
        # else: leave access_token unchanged (silent-failure simulation).
        return True


class _FakeSchwabdevClient:
    """Stub Client. Real schwabdev.Client spawns a daemon thread + may
    block on stdin via Tokens.update_refresh_token; the stub does neither.
    """

    def __init__(
        self,
        *args: Any,
        raise_on_update: BaseException | None = None,
        rotate_on_update: bool = True,
        clear_access_on_update: bool = False,
        **kwargs: Any,
    ) -> None:
        self._init_kwargs = kwargs
        self.tokens = _FakeTokens(
            raise_on_update=raise_on_update,
            rotate_on_update=rotate_on_update,
            clear_access_on_update=clear_access_on_update,
        )
        self.tokens_file = kwargs.get("tokens_file")


def _make_stub(
    *,
    raise_on_update: BaseException | None = None,
    rotate_on_update: bool = True,
    clear_access_on_update: bool = False,
):
    def factory(*args: Any, **kwargs: Any) -> _FakeSchwabdevClient:
        return _FakeSchwabdevClient(
            *args,
            raise_on_update=raise_on_update,
            rotate_on_update=rotate_on_update,
            clear_access_on_update=clear_access_on_update,
            **kwargs,
        )
    return factory


def _patch_schwabdev(monkeypatch: pytest.MonkeyPatch, factory) -> None:
    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", factory)


def _invoke(cfg_path: Path, args: list[str], *, input: str | None = None) -> Any:
    runner = CliRunner()
    return runner.invoke(
        main,
        ["--config", str(cfg_path), "schwab", *args],
        input=input,
    )


def _read_audit_rows(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            "SELECT * FROM schwab_api_calls ORDER BY call_id",
        ).fetchall()]
    finally:
        conn.close()


def _plant_pipeline_running(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO pipeline_runs ("
            "started_ts, trigger, data_asof_date, action_session_date, "
            "state, lease_token"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-05-13T08:00:00", "manual", "2026-05-12",
             "2026-05-13", "running", "test-token"),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# Tests — `swing schwab refresh`
# ============================================================================


def test_refresh_happy_path(
    home: Path, cfg_path: Path, tokens_file: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 1 — refresh happy path. update_tokens succeeds; audit row
    closed with status='success'; success message printed to stdout.
    """
    _patch_schwabdev(monkeypatch, _make_stub())
    result = _invoke(
        cfg_path,
        ["refresh", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 1
    assert rows[0]["endpoint"] == "oauth.refresh"
    assert rows[0]["status"] == "success"
    assert rows[0]["surface"] == "cli"
    assert rows[0]["environment"] == "production"
    assert rows[0]["pipeline_run_id"] is None
    assert "Refresh complete" in result.output


def test_refresh_token_expired_path(
    home: Path, cfg_path: Path, tokens_file: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 2 — when update_tokens raises a refresh-token-expired marker
    (schwabdev itself does not raise a typed exception on refresh failure;
    the wrapper catches our project-defined SchwabRefreshTokenExpiredError
    bubbling up from a sentinel exception class injected via the stub) the
    audit row closes as status='auth_failed' + operator-actionable message
    is printed.
    """
    from swing.integrations.schwab.client import SchwabRefreshTokenExpiredError

    _patch_schwabdev(
        monkeypatch,
        _make_stub(raise_on_update=SchwabRefreshTokenExpiredError(
            401, "<refresh token expired>",
        )),
    )
    result = _invoke(
        cfg_path,
        ["refresh", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 1
    assert rows[0]["endpoint"] == "oauth.refresh"
    assert rows[0]["status"] == "auth_failed"
    # Operator-actionable message names the re-auth command.
    assert "swing schwab setup" in result.output


def test_refresh_does_not_accept_force_flag(
    home: Path, cfg_path: Path, tokens_file: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 3 — DISCRIMINATING per Codex R1 Minor #3. `refresh` is
    concurrent-safe and has NO `--force` flag. A `--force` invocation
    must produce a click usage error.
    """
    _patch_schwabdev(monkeypatch, _make_stub())
    result = _invoke(
        cfg_path,
        ["refresh", "--environment", "production", "--force"],
    )
    assert result.exit_code != 0, result.output
    # Click's "no such option" message includes the flag name verbatim.
    assert "--force" in result.output or "no such option" in result.output.lower()


def test_refresh_proceeds_when_pipeline_running(
    home: Path, cfg_path: Path, tokens_file: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 4 — DISCRIMINATING per Codex R1 Minor #3 + dispatch brief.
    Refresh has no pipeline-active concurrency gate. Plant a running
    pipeline row; assert refresh still succeeds + audit row closes.

    schwabdev's RLock + SQLite file lock handle the inner race naturally.
    """
    _plant_pipeline_running(home / "swing-data" / "swing.db")
    _patch_schwabdev(monkeypatch, _make_stub())
    result = _invoke(
        cfg_path,
        ["refresh", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    # Refresh row is the only schwab_api_calls row (pipeline_runs is separate).
    assert len(rows) == 1
    assert rows[0]["status"] == "success"


# ============================================================================
# Tests — `swing schwab logout`
# ============================================================================


def test_logout_happy_path(
    home: Path, cfg_path: Path, tokens_file: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 5 — logout happy path: POST /v1/oauth/revoke returns 200;
    audit row closes status='success'; tokens file RENAMED (not deleted)
    to `<path>.deleted-<ts>` for 24h recovery window.
    """
    posts: list[dict] = []

    class _FakeResponse:
        status_code = 200
        text = "ok"
        ok = True

    def fake_post(*args: Any, **kwargs: Any) -> Any:
        posts.append({"args": args, "kwargs": kwargs})
        return _FakeResponse()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)

    result = _invoke(
        cfg_path,
        ["logout", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    # POST was made.
    assert len(posts) == 1
    # tokens file was renamed (NOT removed entirely).
    assert not tokens_file.exists(), (
        "tokens file should have been renamed to <path>.deleted-<ts>"
    )
    # Some .deleted-* sibling exists in the swing-data dir.
    siblings = list((home / "swing-data").glob("schwab-tokens.production.db.deleted-*"))
    assert len(siblings) == 1, (
        f"expected one .deleted-<ts> sibling; got {siblings}"
    )
    # Audit row.
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 1
    assert rows[0]["endpoint"] == "oauth.revoke"
    assert rows[0]["status"] == "success"
    assert "Logout complete" in result.output


def test_logout_tolerates_revoke_network_failure(
    home: Path, cfg_path: Path, tokens_file: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 6 — POST /v1/oauth/revoke raises ConnectionError; audit row
    closes status='error' but tokens file IS STILL RENAMED (logout
    proceeds best-effort per plan §F.3).
    """
    import requests

    def fake_post(*args: Any, **kwargs: Any) -> Any:
        raise requests.exceptions.ConnectionError("network unreachable")

    monkeypatch.setattr(requests, "post", fake_post)

    result = _invoke(
        cfg_path,
        ["logout", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    # exit_code == 0: logout still completes (rename succeeded) even though
    # revoke failed. The audit row carries the failure.
    assert result.exit_code == 0, result.output
    assert not tokens_file.exists()
    siblings = list((home / "swing-data").glob("schwab-tokens.production.db.deleted-*"))
    assert len(siblings) == 1
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 1
    assert rows[0]["endpoint"] == "oauth.revoke"
    assert rows[0]["status"] == "error"


def test_logout_force_overrides_pipeline_active(
    home: Path, cfg_path: Path, tokens_file: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 7 — pipeline-active blocks logout without --force; --force
    overrides it. Mirrors setup's pipeline-active discipline.
    """
    _plant_pipeline_running(home / "swing-data" / "swing.db")

    class _FakeResponse:
        status_code = 200
        text = "ok"
        ok = True

    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResponse())

    # Without --force: blocked.
    result_blocked = _invoke(
        cfg_path,
        ["logout", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result_blocked.exit_code != 0, result_blocked.output
    assert ("Pipeline" in result_blocked.output
            or "pipeline" in result_blocked.output)
    # Tokens file untouched.
    assert tokens_file.exists()

    # With --force: proceeds.
    result_forced = _invoke(
        cfg_path,
        ["logout", "--environment", "production", "--force"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result_forced.exit_code == 0, result_forced.output
    assert not tokens_file.exists()


def test_logout_missing_tokens_file(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 8 — tokens file does NOT exist; logout surfaces a clean error
    + audit row closes status='error' (cannot extract refresh_token to
    revoke; nothing to rename).
    """
    # Note: do NOT use the `tokens_file` fixture (so the file does not exist).
    import requests
    monkeypatch.setattr(
        requests, "post",
        lambda *a, **k: pytest.fail(
            "requests.post should not be called when tokens file missing",
        ),
    )

    result = _invoke(
        cfg_path,
        ["logout", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 1
    assert rows[0]["endpoint"] == "oauth.revoke"
    assert rows[0]["status"] == "error"


# ============================================================================
# Tests — cross-cutting discriminators
# ============================================================================


def test_refresh_no_token_bytes_in_stdout_or_audit(
    home: Path, cfg_path: Path, tokens_file: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 9 — sentinel access_token + refresh_token bytes MUST NOT
    appear in stdout / stderr / audit row error_message across BOTH
    happy + error paths. Discriminating per plan §H.5 + lesson #19.
    """
    # Happy path.
    _patch_schwabdev(monkeypatch, _make_stub())
    result_ok = _invoke(
        cfg_path,
        ["refresh", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result_ok.exit_code == 0, result_ok.output
    assert _SENTINEL_ACCESS_TOKEN not in result_ok.output
    assert _SENTINEL_REFRESH_TOKEN not in result_ok.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    for r in rows:
        err = r["error_message"] or ""
        assert _SENTINEL_ACCESS_TOKEN not in err
        assert _SENTINEL_REFRESH_TOKEN not in err

    # Error path — make schwabdev raise an exception that interpolates
    # the sentinel access token; ensure the redaction strips it.
    _patch_schwabdev(
        monkeypatch,
        _make_stub(raise_on_update=RuntimeError(
            f"oauth refresh refused token={_SENTINEL_ACCESS_TOKEN}",
        )),
    )
    result_err = _invoke(
        cfg_path,
        ["refresh", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result_err.exit_code != 0, result_err.output
    assert _SENTINEL_ACCESS_TOKEN not in result_err.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    for r in rows:
        err = r["error_message"] or ""
        assert _SENTINEL_ACCESS_TOKEN not in err
        assert _SENTINEL_REFRESH_TOKEN not in err


def test_logout_tokens_path_resolves_under_tmp_home(
    home: Path, cfg_path: Path, tokens_file: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 10 — discriminating per CLAUDE.md USERPROFILE+HOME monkeypatch
    gotcha: the tokens DB path for logout MUST resolve under the
    monkeypatched home, NEVER under the operator's real home.
    """

    class _FakeResponse:
        status_code = 200
        text = "ok"
        ok = True

    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResponse())

    # Pre-condition: tokens file under monkeypatched home.
    assert str(tokens_file).startswith(str(home))
    assert tokens_file.name == "schwab-tokens.production.db"

    result = _invoke(
        cfg_path,
        ["logout", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    # Renamed sibling MUST be under tmp_path, not the operator's real home.
    siblings = list(home.rglob("schwab-tokens.production.db.deleted-*"))
    assert len(siblings) == 1
    assert str(siblings[0]).startswith(str(home))


# ============================================================================
# Codex R1 Major #1 — force_refresh silent-failure detection (parity with D1)
# ============================================================================


def test_refresh_detects_silent_failure_access_token_cleared(
    home: Path,
    cfg_path: Path,
    tokens_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex R1 Major #1 — schwabdev's `update_tokens` returns normally
    but leaves `client.tokens.access_token = None` (silent failure
    suppressed inside schwabdev, mirroring D1 paste-back failure mode).
    The refresh handler MUST close the audit row as `auth_failed` +
    raise `SchwabAuthError` rather than reporting success.

    Discriminating: pre-fix the handler closed audit `status='success'`
    because no exception was raised.
    """
    _patch_schwabdev(monkeypatch, _make_stub(clear_access_on_update=True))
    result = _invoke(
        cfg_path,
        ["refresh", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 1
    assert rows[0]["endpoint"] == "oauth.refresh"
    assert rows[0]["status"] == "auth_failed", (
        f"silent-failure (cleared access_token) MUST audit auth_failed; "
        f"got {rows[0]['status']!r}"
    )
    err = rows[0]["error_message"] or ""
    assert "access_token" in err, (
        f"audit error_message should mention access_token; got {err!r}"
    )


def test_refresh_rewraps_factory_when_third_party_replaced_it(
    home: Path,
    cfg_path: Path,
    tokens_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex R1 Major #2 — auth.py:force_refresh MUST call
    `ensure_schwab_log_redaction_factory_installed()` (not just
    `_install_*_once()`) before invoking schwabdev — otherwise a
    third-party library that replaced the process-global LogRecord
    factory after our initial install bypasses redaction.

    Discriminating: install Schwab factory; install no-op third-party
    factory; invoke refresh; assert post-call factory is OUR factory
    again (re-wrapped). Pre-fix `_install_*_once` would no-op the
    second-call install + leave the third-party factory in place.
    """
    import logging

    from swing.integrations.schwab.client import (
        _install_schwab_log_redaction_factory_once,
        _schwab_record_factory,
        register_schwab_secrets,
    )

    # Ensure our factory is installed first.
    register_schwab_secrets(["my_client_id", "my_client_secret"])
    _install_schwab_log_redaction_factory_once()
    assert logging.getLogRecordFactory() is _schwab_record_factory

    # Third-party replaces the factory AFTER our install.
    def third_party_factory(*args, **kwargs):
        return logging.LogRecord(*args, **kwargs)
    logging.setLogRecordFactory(third_party_factory)
    assert logging.getLogRecordFactory() is third_party_factory

    # Now invoke refresh — handler should re-wrap our factory before the
    # schwabdev call fires.
    _patch_schwabdev(monkeypatch, _make_stub())
    result = _invoke(
        cfg_path,
        ["refresh", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    # Discriminating: post-refresh, factory must be OURS again.
    assert logging.getLogRecordFactory() is _schwab_record_factory, (
        "auth.py:force_refresh did not call ensure_*; third-party factory "
        "remained in place + redaction silently disabled"
    )


def test_refresh_detects_silent_failure_access_token_unchanged(
    home: Path,
    cfg_path: Path,
    tokens_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex R1 Major #1 — schwabdev's `update_tokens` returns normally
    but leaves `client.tokens.access_token` byte-identical to the
    pre-call value (no rotation actually occurred). The refresh handler
    MUST close audit as auth_failed + raise.

    Discriminating: pre-fix the handler trusted the return value of
    schwabdev's update_tokens; an unchanged access_token slipped past
    as a success.
    """
    _patch_schwabdev(monkeypatch, _make_stub(rotate_on_update=False))
    result = _invoke(
        cfg_path,
        ["refresh", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 1
    assert rows[0]["endpoint"] == "oauth.refresh"
    assert rows[0]["status"] == "auth_failed", (
        f"silent-failure (unchanged access_token) MUST audit auth_failed; "
        f"got {rows[0]['status']!r}"
    )
    err = rows[0]["error_message"] or ""
    assert "unchanged" in err.lower() or "access_token" in err.lower()
