"""T-A.4 — `swing schwab setup` OAuth paste-back CLI tests.

15 binding tests per plan §Tasks-A T-A.4 acceptance criteria.

Test discipline:
  - USERPROFILE+HOME monkeypatch (CLAUDE.md gotcha — `write_user_overrides`
    reads them unmonkeypatched and writes would leak to operator's real
    user-config.toml).
  - schwabdev.Client stubbed BEFORE the call site references it; tests
    never trigger real OAuth / network I/O.
  - Token sentinel discriminating tests assert that tokens never leak to
    stdout / stderr / audit-row error_message (plan §H.5 discipline +
    `swing/integrations/schwab/client.py:_redact_message` defense-in-depth).
  - Audit-row row shape pinned post-call by querying the SQLite DB
    directly (validates service-layer wiring + reject-caller-held-tx
    discipline).
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from swing.cli import main

# Sentinel token bytes — if these leak into stdout / audit-row error_message
# the discriminating tests below catch it. Choose a long alphanumeric run that
# the `_redacted_excerpt` substitution + the schwabdev wrapper's
# `_redact_message` regex both target.
_SENTINEL_ACCESS_TOKEN = "AUTH_BYTES_DO_NOT_LEAK_ABCDEF0123456789012345"
_SENTINEL_REFRESH_TOKEN = "REFRESH_BYTES_DO_NOT_LEAK_ZYXWVU09876543210987"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated USERPROFILE+HOME pointing at tmp_path.

    CRITICAL per CLAUDE.md gotcha: BOTH env vars must be set; either path
    alone leaks writes to the operator's real user-config.toml.
    """
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def cfg_path(home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy of project's swing.config.toml with path overrides routed to
    tmp_path so the CLI's `ctx.obj["config"]` points at an isolated DB.
    """
    repo_root = Path(__file__).resolve().parents[2]
    src_cfg = repo_root / "swing.config.toml"
    cfg_text = src_cfg.read_text()
    # Override paths section to point at home.
    db_path = home / "swing-data" / "swing.db"
    # Replace path lines (db_path, data_dir, etc.) with tmp-path equivalents.
    home_swing_data = (home / "swing-data").as_posix()
    home_finviz = (home / "finviz-inbox").as_posix()
    home_exports = (home / "exports").as_posix()
    home_rs = (home / "rs.csv").as_posix()
    # Surgically replace path lines under [paths] section.
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
    # Replace the [paths] section start through next [section] header.
    cfg_text = re.sub(
        r"\[paths\]\n(?:[^\[]+)",
        new_paths_block + "\n",
        cfg_text,
        count=1,
    )
    cfg_file = home / "swing.config.toml"
    cfg_file.write_text(cfg_text)
    # Initialise the DB so audit_service can write.
    db_path.parent.mkdir(parents=True, exist_ok=True)
    from swing.data.db import ensure_schema
    ensure_schema(db_path).close()
    return cfg_file


class _FakeTokens:
    """Stand-in for `client.tokens` attribute bag with sentinel bytes."""

    access_token = _SENTINEL_ACCESS_TOKEN
    refresh_token = _SENTINEL_REFRESH_TOKEN


class _FakeSchwabdevClient:
    """Test stub mimicking schwabdev.Client surface area used by T-A.4.

    The real Client(__init__) prints consent URL + blocks on stdin. The
    stub does neither — it constructs cleanly + carries `tokens` plus
    `account_linked()` returning whatever the test injected.
    """

    def __init__(self, *args: Any, accounts: list[dict] | None = None, **kwargs: Any) -> None:
        self._init_args = args
        self._init_kwargs = kwargs
        self.tokens = _FakeTokens()
        self._accounts = accounts if accounts is not None else [
            {"accountNumber": "12345678", "hashValue": "ABCDEFHASH1"},
        ]
        # Persist the tokens_file kwarg so we can assert per-env DB path.
        self.tokens_file = kwargs.get("tokens_file")

    def account_linked(self) -> list[dict]:
        return self._accounts


def _make_schwabdev_stub(
    *,
    accounts: list[dict] | None = None,
    raise_on_init: BaseException | None = None,
    raise_on_account_linked: BaseException | None = None,
):
    """Return a `schwabdev.Client`-shaped factory function."""

    def factory(*args: Any, **kwargs: Any) -> _FakeSchwabdevClient:
        if raise_on_init is not None:
            raise raise_on_init
        client = _FakeSchwabdevClient(*args, accounts=accounts, **kwargs)
        if raise_on_account_linked is not None:
            def _raiser() -> list[dict]:
                raise raise_on_account_linked
            client.account_linked = _raiser  # type: ignore[method-assign]
        return client

    return factory


def _patch_schwabdev(monkeypatch: pytest.MonkeyPatch, factory):
    """Patch schwabdev.Client in the modules that import it."""
    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", factory)


def _invoke(
    cfg_path: Path,
    args: list[str],
    *,
    input: str | None = None,
) -> Any:
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


def _read_user_overrides(home: Path) -> dict:
    import tomllib
    path = home / "swing-data" / "user-config.toml"
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


# ============================================================================
# Tests
# ============================================================================


def test_setup_happy_path_single_account(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 1 — happy path, single account, all defaults.

    Asserts: exit code 0, audit rows in DB (2 rows: setup + accounts.linked,
    both status='success'), user-config.toml carries the account_hash.
    """
    _patch_schwabdev(
        monkeypatch,
        _make_schwabdev_stub(
            accounts=[{"accountNumber": "12345678", "hashValue": "SINGLEHASH"}],
        ),
    )
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    overrides = _read_user_overrides(home)
    assert overrides["integrations"]["schwab"]["account_hash"] == "SINGLEHASH"
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 2
    assert rows[0]["status"] == "success"
    assert rows[0]["endpoint"] == "oauth.code_exchange"
    assert rows[1]["status"] == "success"
    assert rows[1]["endpoint"] == "accounts.linked"


def test_setup_happy_path_multi_account_picks_via_prompt(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 2 — multi-account branch: operator prompted for choice.

    Provide '2' as stdin pick — assert chosen hash matches accounts[1].
    """
    _patch_schwabdev(
        monkeypatch,
        _make_schwabdev_stub(
            accounts=[
                {"accountNumber": "11111111", "hashValue": "FIRSTHASH"},
                {"accountNumber": "22222222", "hashValue": "SECONDHASH"},
            ],
        ),
    )
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n2\n",
    )
    assert result.exit_code == 0, result.output
    overrides = _read_user_overrides(home)
    assert overrides["integrations"]["schwab"]["account_hash"] == "SECONDHASH"


def test_setup_auth_failure_audit_status_and_sentinel_redaction(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 3 — schwabdev.Client raises → exit non-zero, audit status=
    auth_failed, sentinel bytes never appear in stdout OR audit row error.

    DISCRIMINATING per plan: an unredacted implementation that interpolates
    the exception arg verbatim would fail this test.
    """
    sentinel = _SENTINEL_ACCESS_TOKEN  # would-be leaked bytes
    _patch_schwabdev(
        monkeypatch,
        _make_schwabdev_stub(
            raise_on_init=RuntimeError(f"oauth refused token={sentinel}"),
        ),
    )
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    # Sentinel MUST NOT appear in stdout.
    assert sentinel not in result.output, (
        f"sentinel leaked to stdout:\n{result.output}"
    )
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 1
    assert rows[0]["status"] == "auth_failed"
    assert rows[0]["endpoint"] == "oauth.code_exchange"
    # Sentinel MUST NOT appear in audit-row error_message.
    err = rows[0]["error_message"] or ""
    assert sentinel not in err, (
        f"sentinel leaked to audit error_message: {err!r}"
    )


def test_setup_missing_client_id_rejected(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 4 — empty client_id at prompt → non-zero exit."""
    _patch_schwabdev(monkeypatch, _make_schwabdev_stub())
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="\nignored_secret\n",
    )
    assert result.exit_code != 0, result.output


def test_setup_missing_client_secret_rejected(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 5 — empty client_secret at prompt → non-zero exit."""
    _patch_schwabdev(monkeypatch, _make_schwabdev_stub())
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="some_client_id\n\n",
    )
    assert result.exit_code != 0, result.output


def test_setup_cfg_cascade_write_round_trip(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 6 — after setup, reload cfg + assert
    cfg.integrations.schwab.account_hash matches written hash.
    """
    _patch_schwabdev(
        monkeypatch,
        _make_schwabdev_stub(
            accounts=[{"accountNumber": "12345678", "hashValue": "ROUNDTRIPHASH"}],
        ),
    )
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    from swing.config import load as load_cfg
    from swing.config_overrides import apply_overrides
    cfg = apply_overrides(load_cfg(cfg_path))
    assert cfg.integrations.schwab.account_hash == "ROUNDTRIPHASH"


def test_setup_advisory_warning_printed(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 7 — happy-path stdout carries the plaintext-tokens advisory line."""
    _patch_schwabdev(monkeypatch, _make_schwabdev_stub())
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    assert "WARNING" in result.output
    assert "plaintext OAuth state" in result.output
    assert "Do not back this file up" in result.output


def test_setup_success_message_printed(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 8 — happy-path stdout names the tokens DB file path."""
    _patch_schwabdev(monkeypatch, _make_schwabdev_stub())
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    assert "Setup complete." in result.output
    # Tokens path includes environment name + lives under home/swing-data.
    expected_path_fragment = "schwab-tokens.production.db"
    assert expected_path_fragment in result.output


def test_setup_tokens_path_resolves_under_tmp_home(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 9 — tokens DB path lands under monkeypatched USERPROFILE+HOME.

    Discriminating per CLAUDE.md gotcha: a leaky `_user_home` implementation
    would write under operator's real home.
    """
    captured: dict = {}

    def capture_factory(*args: Any, **kwargs: Any) -> _FakeSchwabdevClient:
        captured.update(kwargs)
        return _FakeSchwabdevClient(*args, **kwargs)

    _patch_schwabdev(monkeypatch, capture_factory)
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    tokens_path = Path(captured["tokens_file"])
    # tokens_path MUST be under tmp_path (str-prefix containment).
    assert str(tokens_path).startswith(str(home)), (
        f"tokens_path {tokens_path} escaped tmp home {home}"
    )
    assert tokens_path.name == "schwab-tokens.production.db"


def test_setup_pipeline_active_rejects_without_force(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 10a — pipeline_runs row with state='running' → non-zero exit
    without --force.
    """
    # Plant pipeline-active row.
    db_path = home / "swing-data" / "swing.db"
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
    _patch_schwabdev(monkeypatch, _make_schwabdev_stub())
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    assert "Pipeline" in result.output or "pipeline" in result.output


def test_setup_pipeline_active_force_override_proceeds(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 10b — `--force` override allows the setup to proceed under
    pipeline-active state.
    """
    # Plant pipeline-active row.
    db_path = home / "swing-data" / "swing.db"
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
    _patch_schwabdev(monkeypatch, _make_schwabdev_stub())
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production", "--force"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output


def test_setup_environment_sandbox_routes_to_sandbox_tokens_db(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 11 — `--environment sandbox` writes per-env tokens DB with
    'sandbox' in the filename.
    """
    captured: dict = {}

    def capture_factory(*args: Any, **kwargs: Any) -> _FakeSchwabdevClient:
        captured.update(kwargs)
        return _FakeSchwabdevClient(*args, **kwargs)

    _patch_schwabdev(monkeypatch, capture_factory)
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "sandbox"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    tokens_path = Path(captured["tokens_file"])
    assert tokens_path.name == "schwab-tokens.sandbox.db"
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert rows[0]["environment"] == "sandbox"


def test_setup_environment_defaults_to_production_when_flag_omitted(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 12 — without `--environment` flag, defaults to cfg
    environment (production by default).
    """
    captured: dict = {}

    def capture_factory(*args: Any, **kwargs: Any) -> _FakeSchwabdevClient:
        captured.update(kwargs)
        return _FakeSchwabdevClient(*args, **kwargs)

    _patch_schwabdev(monkeypatch, capture_factory)
    result = _invoke(
        cfg_path,
        ["setup"],  # no --environment flag
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    tokens_path = Path(captured["tokens_file"])
    assert tokens_path.name == "schwab-tokens.production.db"


def test_setup_audit_row_setup_call_fields(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 13 — record_call_start was invoked with surface='cli',
    environment=<env>, endpoint='oauth.code_exchange', pipeline_run_id=None.
    """
    _patch_schwabdev(monkeypatch, _make_schwabdev_stub())
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert rows[0]["surface"] == "cli"
    assert rows[0]["environment"] == "production"
    assert rows[0]["endpoint"] == "oauth.code_exchange"
    assert rows[0]["pipeline_run_id"] is None


def test_setup_audit_row_terminal_status_success_on_happy_path(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 14 — happy path → both audit rows end with status='success'."""
    _patch_schwabdev(monkeypatch, _make_schwabdev_stub())
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert all(r["status"] == "success" for r in rows)
    # Both rows have http_status=200 + non-null response_time_ms.
    assert all(r["http_status"] == 200 for r in rows)
    assert all(r["response_time_ms"] is not None for r in rows)


def test_setup_token_bytes_never_appear_in_stdout_or_audit_on_happy_path(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 15 — happy path: tokens DO NOT leak to stdout / audit row /
    captured log output. Defense-in-depth — even on success, no token
    bytes should ever cross the audit + UI surfaces.
    """
    _patch_schwabdev(monkeypatch, _make_schwabdev_stub())
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code == 0, result.output
    assert _SENTINEL_ACCESS_TOKEN not in result.output
    assert _SENTINEL_REFRESH_TOKEN not in result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    for r in rows:
        err = r["error_message"] or ""
        assert _SENTINEL_ACCESS_TOKEN not in err
        assert _SENTINEL_REFRESH_TOKEN not in err


def test_setup_account_linked_failure_audits_auth_failed(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bonus test 16 — `account_linked()` failure path: first audit row
    succeeds (setup OK); second row status='auth_failed'; user-config.toml
    NOT updated with account_hash.
    """
    _patch_schwabdev(
        monkeypatch,
        _make_schwabdev_stub(
            raise_on_account_linked=RuntimeError("network unreachable"),
        ),
    )
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 2
    assert rows[0]["status"] == "success"
    assert rows[0]["endpoint"] == "oauth.code_exchange"
    assert rows[1]["status"] == "auth_failed"
    assert rows[1]["endpoint"] == "accounts.linked"
    # user-config.toml NOT updated (account_hash absent).
    overrides = _read_user_overrides(home)
    assert "integrations" not in overrides or "schwab" not in overrides.get(
        "integrations", {},
    ) or "account_hash" not in overrides["integrations"]["schwab"]


# ============================================================================
# T-A.4 phase-2 hotfix regression tests (2026-05-14)
# ============================================================================


class _FakeTokensEmpty:
    """Stub for the D1 regression — schwabdev returns a Client whose
    `tokens.access_token` is missing / empty / non-string.
    """

    access_token = None
    refresh_token = None


class _FakeSchwabdevClientNoTokens:
    """D1 regression stub — Client built successfully but OAuth exchange
    failed silently inside schwabdev (matches operator's 2026-05-14
    paste-back run where the 30-second code window expired).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.tokens = _FakeTokensEmpty()
        self.tokens_file = kwargs.get("tokens_file")

    def account_linked(self) -> list[dict]:
        # Should never be called; included for shape symmetry.
        return []


def test_setup_d1_schwabdev_client_returns_without_tokens_marked_auth_failed(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D1 regression — schwabdev.Client(...) returns a Client object whose
    `tokens.access_token` is None / empty / non-string. The original T-A.4
    implementation incorrectly closed the audit row as `status='success'`
    because no exception was raised; the hotfix detects the empty token +
    closes the audit row as `auth_failed` + raises SchwabAuthError.
    """
    def factory(*args: Any, **kwargs: Any) -> _FakeSchwabdevClientNoTokens:
        return _FakeSchwabdevClientNoTokens(*args, **kwargs)
    _patch_schwabdev(monkeypatch, factory)
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 1, (
        f"expected exactly one audit row (setup; no accounts.linked call); "
        f"got {len(rows)}: {rows}"
    )
    assert rows[0]["status"] == "auth_failed"
    assert rows[0]["endpoint"] == "oauth.code_exchange"
    # account_hash NOT persisted.
    overrides = _read_user_overrides(home)
    assert (
        "integrations" not in overrides
        or "schwab" not in overrides.get("integrations", {})
        or "account_hash" not in overrides["integrations"]["schwab"]
    )


def test_setup_d2_account_linked_returns_dict_marked_auth_failed(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D2 regression — `client.account_linked()` returns a dict-shaped
    Schwab error envelope (not a list). The original implementation would
    crash with `KeyError: 0` on `accounts[0]`; the hotfix detects the
    unexpected shape + closes audit row as `auth_failed` + raises.

    The first audit row (setup) still ends with `status='success'` because
    `schwabdev.Client(...)` construction did succeed (test stub).
    """

    class _ClientWithDictAccounts(_FakeSchwabdevClient):
        def account_linked(self) -> Any:
            return {"errors": ["fake error envelope"]}

    def factory(*args: Any, **kwargs: Any) -> _ClientWithDictAccounts:
        return _ClientWithDictAccounts(*args, **kwargs)

    _patch_schwabdev(monkeypatch, factory)
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 2
    assert rows[0]["status"] == "success", (
        "setup audit row should still be success (Client construction "
        "succeeded in the stub)"
    )
    assert rows[0]["endpoint"] == "oauth.code_exchange"
    assert rows[1]["status"] == "auth_failed"
    assert rows[1]["endpoint"] == "accounts.linked"


def test_setup_d2_account_linked_returns_list_with_non_dict_entries_raises(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D2 regression — `client.account_linked()` returns a list whose
    entries are not dicts (e.g. ['not-a-dict']). Hotfix rejects with
    auth_failed audit close + SchwabAuthError.
    """

    class _ClientWithBadListEntries(_FakeSchwabdevClient):
        def account_linked(self) -> Any:
            return ["not-a-dict"]

    def factory(*args: Any, **kwargs: Any) -> _ClientWithBadListEntries:
        return _ClientWithBadListEntries(*args, **kwargs)

    _patch_schwabdev(monkeypatch, factory)
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 2
    assert rows[0]["status"] == "success"
    assert rows[1]["status"] == "auth_failed"
    assert rows[1]["endpoint"] == "accounts.linked"


def test_setup_d2_account_linked_returns_dict_entries_missing_hashvalue_raises(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D2 regression — `client.account_linked()` returns dicts but they
    lack the `hashValue` key. Hotfix rejects with auth_failed + raises.
    """

    class _ClientWithDictsNoHash(_FakeSchwabdevClient):
        def account_linked(self) -> Any:
            return [{"accountNumber": "12345678"}]

    def factory(*args: Any, **kwargs: Any) -> _ClientWithDictsNoHash:
        return _ClientWithDictsNoHash(*args, **kwargs)

    _patch_schwabdev(monkeypatch, factory)
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 2
    assert rows[0]["status"] == "success"
    assert rows[1]["status"] == "auth_failed"
    assert rows[1]["endpoint"] == "accounts.linked"


def test_setup_d3_schema_mismatch_exits_before_prompting_credentials(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D3 regression — when `connect()` raises `SchemaVersionMismatchError`
    (DB at older version than `EXPECTED_SCHEMA_VERSION`), the handler MUST
    exit BEFORE prompting for credentials. The original implementation
    called click.prompt() before connect(), wasting operator typing on
    a fail-fast condition the system already knew about.

    Construction: stamp the DB's schema_version to 0 so connect() rejects.
    schwabdev.Client is still stubbed so an accidental call site reach
    doesn't drag in real network I/O.
    """
    # Corrupt the schema_version so connect() raises.
    db_path = home / "swing-data" / "swing.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE schema_version SET version = 0")
        conn.commit()
    finally:
        conn.close()

    _patch_schwabdev(monkeypatch, _make_schwabdev_stub())
    # Provide credentials in stdin anyway — they should NOT be consumed
    # because connect() should raise before click.prompt() runs.
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    # The prompt strings MUST NOT appear in output — confirms no prompt was
    # rendered before the schema-mismatch error.
    assert "Schwab app client_id" not in result.output, (
        f"client_id prompt rendered before schema check:\n{result.output}"
    )
    assert "Schwab app client_secret" not in result.output, (
        f"client_secret prompt rendered before schema check:\n{result.output}"
    )
    # The exception should be SchemaVersionMismatchError (uncaught in the
    # handler — bubbles up through CliRunner).
    from swing.data.db import SchemaVersionMismatchError
    assert isinstance(result.exception, SchemaVersionMismatchError), (
        f"expected SchemaVersionMismatchError; got "
        f"{type(result.exception).__name__}: {result.exception}"
    )


# ============================================================================
# Codex R1 Major #3 — empty-list accounts.linked MUST audit auth_failed
# (and NOT success-then-raise)
# ============================================================================


def test_setup_account_linked_empty_list_audits_auth_failed(
    home: Path, cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex R1 Major #3 — `client.account_linked()` returns `[]`. The
    audit row for the accounts.linked endpoint MUST be closed as
    `auth_failed`, NOT `success`-then-raise. Pre-fix ordering closed the
    success row before the empty-list raise fired, mis-reporting an
    auth failure as a successful call in the audit table.

    Discriminating: assertions pin (a) status == 'auth_failed' (not
    'success'), (b) error_message mentions the empty list, (c) exit
    code is non-zero, (d) NO account_hash persisted to user-config.
    """

    class _ClientWithEmptyAccounts(_FakeSchwabdevClient):
        def account_linked(self) -> list[dict]:
            return []

    def factory(*args: Any, **kwargs: Any) -> _ClientWithEmptyAccounts:
        return _ClientWithEmptyAccounts(*args, **kwargs)

    _patch_schwabdev(monkeypatch, factory)
    result = _invoke(
        cfg_path,
        ["setup", "--environment", "production"],
        input="my_client_id\nmy_client_secret\n",
    )
    assert result.exit_code != 0, result.output
    rows = _read_audit_rows(home / "swing-data" / "swing.db")
    assert len(rows) == 2
    # The setup audit row is the first one; Client construction succeeded.
    assert rows[0]["endpoint"] == "oauth.code_exchange"
    assert rows[0]["status"] == "success"
    # The accounts.linked row MUST be auth_failed — NOT success.
    assert rows[1]["endpoint"] == "accounts.linked"
    assert rows[1]["status"] == "auth_failed", (
        f"empty-list accounts.linked MUST audit auth_failed (pre-fix bug "
        f"closed as success then raised); got {rows[1]['status']!r}"
    )
    err = rows[1]["error_message"] or ""
    assert "empty" in err.lower() or "list" in err.lower(), (
        f"error_message should reference empty-list condition; got {err!r}"
    )
    # account_hash NOT persisted (raise short-circuited persistence).
    overrides = _read_user_overrides(home)
    assert (
        "integrations" not in overrides
        or "schwab" not in overrides.get("integrations", {})
        or "account_hash" not in overrides["integrations"]["schwab"]
    )
