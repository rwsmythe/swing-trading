"""Phase 12 Sub-bundle B T-B.3 — `swing config set integrations.schwab.client_id|
client_secret` cascade emitter.

T-B.2 added the cfg fields + FIELD_REGISTRY entries (masked=True). T-B.1 wired the
cascade resolver to consult them. T-B.3 closes the loop by allowing operators to
WRITE the credentials via the existing `swing config set <path> <value>` CLI
(previously masked fields were filtered out of `_EDITABLE_SPECS`; the registry
entries for client_id/client_secret are masked too, so they were also blocked).

The existing CLI also assumed 2-part dotted paths (`section.key`) — the new
fields are 3-part (`integrations.schwab.client_id`), so the write paths in
`swing/cli_config.py` AND `swing/config_user.py:delete_user_override` need to
handle N-part nested dicts.

Tests use `monkeypatch.setenv("USERPROFILE"/HOME)` per CLAUDE.md gotcha (operator
real user-config.toml must NOT be polluted by tests exercising write paths).
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.config_user import (
    get_user_config_path,
    load_user_overrides,
    write_user_overrides,
)
from tests.web.test_config_web import _write_cfg

# ---------- Fixtures ----------

@pytest.fixture
def runner_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolated USERPROFILE+HOME + minimal swing.config.toml (cfg) on disk.

    Per CLAUDE.md gotcha: tests touching user-config.toml MUST monkeypatch both
    USERPROFILE + HOME; `_user_home()` in swing/config_user.py reads them directly.
    """
    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    cfg_path = _write_cfg(project, home)
    return CliRunner(), cfg_path, home


# ---------- Test 1: BINDING — `swing config set` writes client_id to user-config.toml ----------

def test_set_writes_client_id_to_user_config_toml(runner_env) -> None:
    """`swing config set integrations.schwab.client_id "test-id-value"` writes
    the key+value to ~/swing-data/user-config.toml under `[integrations.schwab]`.

    BINDING per brief §3 T-B.3 discriminating-test pattern #1.
    """
    runner, cfg_path, _home = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "set",
        "integrations.schwab.client_id", "test-id-value",
    ])
    assert r.exit_code == 0, r.output

    # Read user-config.toml directly + assert the key/value persisted under
    # the correct nested section.
    user_config = get_user_config_path()
    assert user_config.exists(), "user-config.toml not created"
    with open(user_config, "rb") as f:
        data = tomllib.load(f)
    assert data == {"integrations": {"schwab": {"client_id": "test-id-value"}}}


# ---------- Test 2: BINDING — `swing config set` + `swing config show` renders masked ----------

def test_set_then_show_renders_masked_not_raw(runner_env) -> None:
    """After `swing config set integrations.schwab.client_id "SENTINEL-CLI-WRITE-ID"`,
    invoking `swing config show` renders the masked form (first-3 + `***` +
    last-2 per `mask_sensitive_value`); raw sentinel value NOT in output.

    BINDING per brief §3 T-B.3 discriminating-test pattern #2.
    """
    runner, cfg_path, _home = runner_env
    sentinel = "SENTINEL-CLI-WRITE-ID"  # 21 chars; long enough to mask
    r1 = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "set",
        "integrations.schwab.client_id", sentinel,
    ])
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "show",
    ])
    assert r2.exit_code == 0, r2.output
    # Raw sentinel MUST NOT appear (would mean masking bypassed)
    assert sentinel not in r2.output
    # Masked shape: first-3 ("SEN") + "***" + last-2 ("ID") → "SEN***ID"
    assert "SEN***ID" in r2.output
    # Override source surfaced
    assert "override" in r2.output


# ---------- Test 3: client_secret also writeable (parallel to Test 1) ----------

def test_set_writes_client_secret_to_user_config_toml(runner_env) -> None:
    """Parallel coverage for client_secret — same write path discipline."""
    runner, cfg_path, _home = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "set",
        "integrations.schwab.client_secret", "test-secret-value",
    ])
    assert r.exit_code == 0, r.output
    assert load_user_overrides() == {
        "integrations": {"schwab": {"client_secret": "test-secret-value"}},
    }


# ---------- Test 4: both fields coexist in user-config.toml after two sets ----------

def test_set_both_fields_coexist_in_user_config_toml(runner_env) -> None:
    """Two sequential `swing config set` calls produce a merged TOML — second
    set MUST NOT clobber the first; both keys present under [integrations.schwab].
    """
    runner, cfg_path, _home = runner_env
    r1 = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "set",
        "integrations.schwab.client_id", "id-A",
    ])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "set",
        "integrations.schwab.client_secret", "secret-B",
    ])
    assert r2.exit_code == 0, r2.output
    assert load_user_overrides() == {
        "integrations": {
            "schwab": {"client_id": "id-A", "client_secret": "secret-B"},
        },
    }


# ---------- Test 5: reset path clears client_id (3-part path) ----------

def test_reset_clears_client_id_from_user_config_toml(runner_env) -> None:
    """`swing config reset integrations.schwab.client_id` removes the field from
    user-config.toml; load_user_overrides reflects the deletion.

    Discriminating: `delete_user_override` previously rejected non-2-part paths
    with ValueError (`field_path must be 'section.key'`); T-B.3 generalized it
    to N-part nested dicts.
    """
    runner, cfg_path, _home = runner_env
    write_user_overrides({
        "integrations": {
            "schwab": {
                "client_id": "to-be-deleted",
                "client_secret": "untouched",
            },
        },
    })
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "reset",
        "integrations.schwab.client_id",
    ])
    assert r.exit_code == 0, r.output
    # client_id removed; client_secret retained
    assert load_user_overrides() == {
        "integrations": {"schwab": {"client_secret": "untouched"}},
    }


# ---------- Test 6: reset removes entire nested section when empty ----------

def test_reset_prunes_empty_nested_section(runner_env) -> None:
    """Removing the only key under [integrations.schwab] prunes the section AND
    the parent [integrations] table (mirror existing 2-part `if not section` cleanup).
    """
    runner, cfg_path, _home = runner_env
    write_user_overrides({
        "integrations": {
            "schwab": {"client_id": "only-key"},
        },
    })
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "reset",
        "integrations.schwab.client_id",
    ])
    assert r.exit_code == 0, r.output
    # Entire nested chain pruned (section empty)
    assert load_user_overrides() == {}


# ---------- Test 7: discriminating — masked fields ARE in CLI editable choices ----------

def test_masked_credential_fields_are_in_cli_choice_allowlist() -> None:
    """T-B.3 pins masked T-B.2 entries (client_id + client_secret) into the
    `swing config set` field-path choice allowlist. Regression for any future
    refactor that re-narrows the allowlist back to `not s.masked`.

    Discriminating: assert the new paths are present; account_hash precedent
    (read-only masked entry) MAY or MAY NOT remain excluded — this test only
    binds the two new paths.
    """
    from swing.cli_config import _FIELD_PATHS

    assert "integrations.schwab.client_id" in _FIELD_PATHS
    assert "integrations.schwab.client_secret" in _FIELD_PATHS


# ---------- Test 8: end-to-end — set via CLI + cascade reads cfg value ----------

def test_set_via_cli_then_cascade_returns_cfg_values(
    runner_env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After `swing config set` writes both fields, env vars are absent, and
    `resolve_credentials_env_or_prompt(..., allow_prompt=False)` returns the
    cfg values. End-to-end binding test for the CLI write path → cfg-cascade
    read path round-trip (T-B.1 + T-B.2 + T-B.3 integration).
    """
    runner, cfg_path, _home = runner_env
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)

    r1 = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "set",
        "integrations.schwab.client_id", "cfg-id-from-cli",
    ])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(main, [
        "--config", str(cfg_path),
        "config", "set",
        "integrations.schwab.client_secret", "cfg-secret-from-cli",
    ])
    assert r2.exit_code == 0, r2.output

    # Read cfg + apply overrides + invoke the cascade resolver. allow_prompt=False
    # so a regression that re-broke the cfg-tier would surface as (None, None)
    # or SchwabConfigMissingError, NOT a prompt.
    from swing.config import load
    from swing.config_overrides import apply_overrides
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt

    base_cfg = load(cfg_path)
    eff_cfg = apply_overrides(base_cfg)
    cid, csec = resolve_credentials_env_or_prompt(
        eff_cfg, eff_cfg.integrations.schwab.environment, allow_prompt=False,
    )
    assert cid == "cfg-id-from-cli"
    assert csec == "cfg-secret-from-cli"
