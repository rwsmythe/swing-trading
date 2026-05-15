"""T-A.1 — SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET env-var resolution.

10 binding tests per dispatch brief §3 T-A.1 acceptance criteria:

  1. Both env vars set + non-empty → returned; NO prompt fires.
  2. Partial: CLIENT_ID set, CLIENT_SECRET unset → SchwabConfigMissingError.
  3. Partial: CLIENT_ID unset, CLIENT_SECRET set → SchwabConfigMissingError.
  4. Partial: CLIENT_ID set, CLIENT_SECRET="" (empty) → SchwabConfigMissingError.
  5. Both empty strings → SchwabConfigMissingError.
  6. Both whitespace-only → SchwabConfigMissingError.
  7. Both absent + allow_prompt=True → prompter fires; values returned.
  8. Both absent + allow_prompt=False → returns (None, None).
  9. Sentinel-leak guarantee: env-var values redacted from log records.
  10. Status regression: `swing schwab status` does NOT prompt even when
      env vars are absent + click.prompt would raise.

Tests are unit-level (helper-direct invocation) PLUS the status regression
which uses CliRunner.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from click.testing import CliRunner

# Sentinel bytes — discriminating substrings the redactor must scrub from
# any log record / audit-row error_message. Chosen long enough (24+ chars)
# that Layer-1 base64 heuristic would catch them even without registry.
_SENTINEL_CLIENT_ID = "ENVVAR_CLIENT_ID_SENTINEL_ABCDEFGHIJKLMNOPQRSTUV"
_SENTINEL_CLIENT_SECRET = "ENVVAR_CLIENT_SECRET_SENTINEL_ZYXWVUTSRQPONMLKJI"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated USERPROFILE+HOME pointing at tmp_path.

    CRITICAL per CLAUDE.md gotcha: BOTH env vars must be set; either path
    alone leaks writes to operator's real user-config.toml.
    """
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def clear_credentials_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET are absent at test entry.

    The operator's real shell may have these set; explicit `delenv` keeps
    tests deterministic regardless of host environment.
    """
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)


@pytest.fixture
def fake_cfg() -> SimpleNamespace:
    """Minimal cfg shaped like `swing.config.Config`. The helper consults
    `cfg.integrations.schwab` namespacing — we provide a SimpleNamespace
    that quacks the same way without dragging full Config validation in.
    """
    return SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment="production",
                callback_url="https://127.0.0.1",
                timeout_seconds=10,
            ),
        ),
    )


# ============================================================================
# Tests
# ============================================================================


def test_both_env_vars_set_skips_prompt_and_returns(
    home: Path,
    clear_credentials_env: None,
    fake_cfg: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 1 — happy path: both env vars set + non-empty.

    Returns the tuple; prompter MUST NOT fire. Test fails the prompter
    via an AssertionError-raising stub.
    """
    from swing.integrations.schwab.auth import _resolve_credentials_env_or_prompt

    monkeypatch.setenv("SCHWAB_CLIENT_ID", _SENTINEL_CLIENT_ID)
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", _SENTINEL_CLIENT_SECRET)

    def _no_prompt(*args: Any, **kwargs: Any) -> str:
        raise AssertionError(
            "prompter must NOT fire when both env vars are set",
        )

    client_id, client_secret = _resolve_credentials_env_or_prompt(
        fake_cfg, "production", allow_prompt=True, prompter=_no_prompt,
    )
    assert client_id == _SENTINEL_CLIENT_ID
    assert client_secret == _SENTINEL_CLIENT_SECRET


def test_partial_env_var_id_only_raises(
    home: Path,
    clear_credentials_env: None,
    fake_cfg: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 2 — partial: only CLIENT_ID set; SECRET absent.

    Must raise SchwabConfigMissingError. Error message must NOT contain
    raw client_id value (masked-form check via `mask_sensitive_value`).
    """
    from swing.integrations.schwab.auth import _resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import SchwabConfigMissingError

    monkeypatch.setenv("SCHWAB_CLIENT_ID", _SENTINEL_CLIENT_ID)
    # SECRET absent (cleared by fixture).

    with pytest.raises(SchwabConfigMissingError) as excinfo:
        _resolve_credentials_env_or_prompt(
            fake_cfg, "production", allow_prompt=True,
        )
    msg = str(excinfo.value)
    # Raw sentinel MUST NOT appear in masked error.
    assert _SENTINEL_CLIENT_ID not in msg, (
        f"raw client_id sentinel leaked into error message: {msg!r}"
    )
    # Helpful error: mentions both env-var names.
    assert "SCHWAB_CLIENT_ID" in msg
    assert "SCHWAB_CLIENT_SECRET" in msg


def test_partial_env_var_secret_only_raises(
    home: Path,
    clear_credentials_env: None,
    fake_cfg: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 3 — partial: only CLIENT_SECRET set; CLIENT_ID absent.

    Symmetric to Test 2 — must raise SchwabConfigMissingError; raw
    secret value MUST NOT leak into the error message.
    """
    from swing.integrations.schwab.auth import _resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import SchwabConfigMissingError

    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", _SENTINEL_CLIENT_SECRET)

    with pytest.raises(SchwabConfigMissingError) as excinfo:
        _resolve_credentials_env_or_prompt(
            fake_cfg, "production", allow_prompt=True,
        )
    msg = str(excinfo.value)
    assert _SENTINEL_CLIENT_SECRET not in msg, (
        f"raw client_secret sentinel leaked into error message: {msg!r}"
    )


def test_partial_env_var_id_set_secret_empty_raises(
    home: Path,
    clear_credentials_env: None,
    fake_cfg: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 4 — CLIENT_ID set; CLIENT_SECRET present but empty string.

    Empty-string treated as ABSENT per acceptance criterion #3 → partial
    rule → SchwabConfigMissingError.
    """
    from swing.integrations.schwab.auth import _resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import SchwabConfigMissingError

    monkeypatch.setenv("SCHWAB_CLIENT_ID", _SENTINEL_CLIENT_ID)
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "")

    with pytest.raises(SchwabConfigMissingError):
        _resolve_credentials_env_or_prompt(
            fake_cfg, "production", allow_prompt=True,
        )


def test_both_env_vars_empty_raises(
    home: Path,
    clear_credentials_env: None,
    fake_cfg: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 5 — both env vars present but empty string.

    Per dispatch brief: empty-string treated as ABSENT (per partial rule);
    same error. NOT same as both-absent (which falls back to prompt).

    Discriminating: if helper treats empty == absent globally + falls back
    to prompt, this test fails (no prompter passed). The contract is
    "both empty == partial-style failure mode" because a partially-
    set-then-cleared shell config is more likely operator error than
    legitimate intent.
    """
    from swing.integrations.schwab.auth import _resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import SchwabConfigMissingError

    monkeypatch.setenv("SCHWAB_CLIENT_ID", "")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "")

    with pytest.raises(SchwabConfigMissingError):
        _resolve_credentials_env_or_prompt(
            fake_cfg, "production", allow_prompt=True,
        )


def test_both_env_vars_whitespace_only_raises(
    home: Path,
    clear_credentials_env: None,
    fake_cfg: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 6 — whitespace-only env vars treated as ABSENT per partial rule."""
    from swing.integrations.schwab.auth import _resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import SchwabConfigMissingError

    monkeypatch.setenv("SCHWAB_CLIENT_ID", "   ")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "\t\n  ")

    with pytest.raises(SchwabConfigMissingError):
        _resolve_credentials_env_or_prompt(
            fake_cfg, "production", allow_prompt=True,
        )


def test_both_absent_allow_prompt_true_prompts(
    home: Path,
    clear_credentials_env: None,
    fake_cfg: SimpleNamespace,
) -> None:
    """Test 7 — both absent + allow_prompt=True → prompter fires.

    Prompter receives the per-prompt label kwargs from click.prompt so the
    helper must invoke it once for client_id + once for client_secret.
    Returned tuple matches what the prompter returned.
    """
    from swing.integrations.schwab.auth import _resolve_credentials_env_or_prompt

    calls: list[str] = []

    def _stub_prompter(label: str, *args: Any, **kwargs: Any) -> str:
        calls.append(label)
        if "secret" in label.lower():
            return "prompted_secret_value"
        return "prompted_id_value"

    client_id, client_secret = _resolve_credentials_env_or_prompt(
        fake_cfg, "production", allow_prompt=True, prompter=_stub_prompter,
    )
    assert client_id == "prompted_id_value"
    assert client_secret == "prompted_secret_value"
    # Prompter was invoked twice (once per credential).
    assert len(calls) == 2
    assert any("client_id" in c.lower() for c in calls)
    assert any("client_secret" in c.lower() for c in calls)


def test_both_absent_allow_prompt_false_returns_none_tuple(
    home: Path,
    clear_credentials_env: None,
    fake_cfg: SimpleNamespace,
) -> None:
    """Test 8 — both absent + allow_prompt=False → (None, None).

    This is the pipeline-path contract (T-A.3 will consume). Distinguishes
    "incomplete env vars" (raises) from "absent entirely" (returns Nones).
    """
    from swing.integrations.schwab.auth import _resolve_credentials_env_or_prompt

    def _no_prompt(*args: Any, **kwargs: Any) -> str:
        raise AssertionError(
            "prompter must NOT fire when allow_prompt=False",
        )

    result = _resolve_credentials_env_or_prompt(
        fake_cfg, "production", allow_prompt=False, prompter=_no_prompt,
    )
    assert result == (None, None)


def test_env_var_values_registered_for_redaction(
    home: Path,
    clear_credentials_env: None,
    fake_cfg: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test 9 — sentinel-leak guarantee.

    After successful env-var resolution, the credentials MUST be in the
    process-global known-secrets registry so any schwabdev log record
    that interpolates them is scrubbed by the Layer-2 redaction factory.

    Discriminating test: register a sentinel via env var, resolve, then
    emit a Schwabdev-named log record containing the sentinel and assert
    the captured record was redacted.
    """
    from swing.integrations.schwab.auth import _resolve_credentials_env_or_prompt
    from swing.integrations.schwab.client import (
        ensure_schwab_log_redaction_factory_installed,
    )

    monkeypatch.setenv("SCHWAB_CLIENT_ID", _SENTINEL_CLIENT_ID)
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", _SENTINEL_CLIENT_SECRET)

    client_id, client_secret = _resolve_credentials_env_or_prompt(
        fake_cfg, "production", allow_prompt=False,
    )
    assert client_id == _SENTINEL_CLIENT_ID
    assert client_secret == _SENTINEL_CLIENT_SECRET

    # The helper MUST have ensured the redaction factory is installed +
    # registered both sentinels. Now emit a Schwabdev-named log record
    # containing both sentinels + assert they are scrubbed.
    ensure_schwab_log_redaction_factory_installed()
    schwabdev_logger = logging.getLogger("Schwabdev.test_t_a_1")
    caplog.set_level(logging.DEBUG, logger="Schwabdev")
    schwabdev_logger.warning(
        "test record interpolating id=%s secret=%s",
        _SENTINEL_CLIENT_ID,
        _SENTINEL_CLIENT_SECRET,
    )
    # Gather all captured message bytes.
    captured = "\n".join(r.getMessage() for r in caplog.records)
    assert _SENTINEL_CLIENT_ID not in captured, (
        f"client_id sentinel leaked into Schwabdev log records:\n{captured}"
    )
    assert _SENTINEL_CLIENT_SECRET not in captured, (
        f"client_secret sentinel leaked into Schwabdev log records:\n{captured}"
    )


def test_status_command_does_not_prompt_with_no_env_vars(
    home: Path,
    clear_credentials_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test 10 — `swing schwab status` MUST NOT prompt even when env vars
    are absent. Status is a READ-ONLY surface (no schwabdev.Client
    construction); does not consume credentials.

    Discriminating: patch click.prompt globally to raise AssertionError —
    if any code path attempts a prompt during status invocation the test
    catches the regression.
    """
    import click

    from swing.cli import main

    # Build minimal cfg + DB so the status command can read its surface.
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

    # Patch click.prompt globally to raise — if status invokes it, fail.
    def _no_prompt_fires(*args: Any, **kwargs: Any) -> str:
        raise AssertionError(
            "click.prompt fired during `swing schwab status` "
            "(status is read-only and MUST NOT prompt)",
        )

    monkeypatch.setattr(click, "prompt", _no_prompt_fires)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--config", str(cfg_file), "schwab", "status",
         "--environment", "production"],
    )
    # Even if status surfaces a "tokens absent" message, it must complete
    # without invoking the prompt. exit_code can be 0 or non-zero per the
    # underlying status logic (we just assert no AssertionError leaked).
    assert "click.prompt fired" not in result.output, result.output
    # And no exception about the prompt should have been raised.
    if result.exception is not None:
        msg = str(result.exception)
        assert "click.prompt fired" not in msg, msg
