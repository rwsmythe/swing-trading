"""Phase 12 Sub-bundle B T-B.2 — `SchwabIntegrationConfig.client_id` +
`client_secret` cfg fields + `FIELD_REGISTRY` masked entries.

Foundation task for credentials-in-file cascade: cfg dataclass + FIELD_REGISTRY
gain `client_id` + `client_secret` fields so T-B.1 (next task) can extend
`resolve_credentials_env_or_prompt` to consult them.

Defaults: empty string `""` (matches Finviz `token` precedent at config.py:221).
Mirrors `integrations.schwab.account_hash` FIELD_REGISTRY `masked=True` template.

Tests use `monkeypatch.setenv("USERPROFILE"/HOME)` per CLAUDE.md gotcha (operator
real user-config.toml must NOT be polluted by tests exercising write paths).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import (
    Config,
    SchwabIntegrationConfig,
    load,
)
from swing.config_overrides import apply_overrides
from swing.config_user import write_user_overrides
from tests.web.test_config_web import _write_cfg  # reuse helper


# ---------- Fixtures ----------

@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate USERPROFILE + HOME so write_user_overrides hits tmp, not operator real path.

    Per CLAUDE.md gotcha: tests touching user-config.toml MUST monkeypatch both
    env vars; `_user_home()` in swing/config_user.py reads them directly.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def base_cfg(tmp_path: Path, tmp_home: Path) -> Config:
    """Build a minimal Config from a swing.config.toml that includes the
    [integrations.schwab] tracked section (timeout_seconds + ladder only)."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    extra = """
[integrations.schwab]
timeout_seconds = 30.0
marketdata_ladder_enabled = true
"""
    cfg_path = _write_cfg(project_dir, tmp_home, extra=extra)
    return load(cfg_path)


# ---------- Test 1: dataclass accepts client_id + client_secret ----------

def test_schwab_config_accepts_client_id_and_client_secret_strings() -> None:
    """`SchwabIntegrationConfig(client_id="abc", client_secret="def")` constructs
    without raising; values stored verbatim."""
    cfg = SchwabIntegrationConfig(
        client_id="abc-client-id-test",
        client_secret="abc-client-secret-test",
    )
    assert cfg.client_id == "abc-client-id-test"
    assert cfg.client_secret == "abc-client-secret-test"


def test_schwab_config_default_client_id_and_client_secret_empty_strings() -> None:
    """Default value for both new fields is empty string `""` (Finviz `token`
    precedent at config.py:221). Operator with NO credentials configured sees
    empty-string defaults — env-var fallback in T-B.1 handles the active path."""
    cfg = SchwabIntegrationConfig()
    assert cfg.client_id == ""
    assert cfg.client_secret == ""


# ---------- Test 2: __post_init__ rejects non-str types ----------

def test_schwab_config_client_id_rejects_non_string_type() -> None:
    """`__post_init__` validates client_id is `str`; reject None/int/etc."""
    with pytest.raises(TypeError, match="client_id"):
        SchwabIntegrationConfig(client_id=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="client_id"):
        SchwabIntegrationConfig(client_id=12345)  # type: ignore[arg-type]


def test_schwab_config_client_secret_rejects_non_string_type() -> None:
    """`__post_init__` validates client_secret is `str`; reject None/int/etc."""
    with pytest.raises(TypeError, match="client_secret"):
        SchwabIntegrationConfig(client_secret=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="client_secret"):
        SchwabIntegrationConfig(client_secret=12345)  # type: ignore[arg-type]


# ---------- Test 3: tracked toml drop-from defensive ----------

def test_client_id_in_tracked_toml_is_dropped(
    tmp_path: Path, tmp_home: Path,
) -> None:
    """Sensitive credentials MUST NOT live in tracked swing.config.toml; any
    `client_id` row defensively dropped at load() time (mirrors Finviz token
    drop at config.py:426-427 + existing Schwab 4-field drop at L435-438)."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    extra = """
[integrations.schwab]
timeout_seconds = 30.0
marketdata_ladder_enabled = true
client_id = "leak-test-id-12345"
client_secret = "leak-test-secret-67890"
"""
    cfg_path = _write_cfg(project_dir, tmp_home, extra=extra)
    cfg = load(cfg_path)
    # Empty-string default applies; tracked-TOML values silently dropped.
    assert cfg.integrations.schwab.client_id == ""
    assert cfg.integrations.schwab.client_secret == ""


# ---------- Test 4: user-config.toml overrides populate the cfg fields ----------

def test_client_id_user_config_override_applied(
    base_cfg: Config, tmp_home: Path,
) -> None:
    """Writing client_id + client_secret to user-config.toml + `apply_overrides`
    populates the effective cfg with the override values (cascade tier 2 path
    that T-B.1 will consume)."""
    write_user_overrides({
        "integrations": {
            "schwab": {
                "client_id": "operator-real-id-abcdef",
                "client_secret": "operator-real-secret-zyx987",
            },
        },
    })
    eff = apply_overrides(base_cfg)
    assert eff.integrations.schwab.client_id == "operator-real-id-abcdef"
    assert eff.integrations.schwab.client_secret == "operator-real-secret-zyx987"


# ---------- Test 5: FIELD_REGISTRY entries masked + `swing config show` masking ----------

def test_field_registry_has_client_id_and_client_secret_masked_entries() -> None:
    """FIELD_REGISTRY contains both new paths as `masked=True` (mirrors existing
    `integrations.schwab.account_hash` entry template; auto-inherits the
    first-3 + `***` + last-2 mask rendering)."""
    from swing.config_validation import FIELD_REGISTRY, get_spec

    paths = {s.path for s in FIELD_REGISTRY}
    assert "integrations.schwab.client_id" in paths
    assert "integrations.schwab.client_secret" in paths

    cid_spec = get_spec("integrations.schwab.client_id")
    assert cid_spec.masked is True
    assert cid_spec.type is str
    assert cid_spec.default == ""

    cs_spec = get_spec("integrations.schwab.client_secret")
    assert cs_spec.masked is True
    assert cs_spec.type is str
    assert cs_spec.default == ""


def test_swing_config_show_masks_client_id_and_client_secret(
    base_cfg: Config, tmp_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`swing config show` walks FIELD_REGISTRY + applies `mask_sensitive_value`
    on masked entries. Setting cfg fields via user-config + invoking the CLI
    produces masked output (first-3 + `***` + last-2); raw sentinel value is
    NOT present in the output."""
    from click.testing import CliRunner

    from swing.cli_config import config_group

    # Plant sentinel values via user-config override path (cascade tier 2).
    write_user_overrides({
        "integrations": {
            "schwab": {
                "client_id": "SENTINEL-client-id-VALUE",
                "client_secret": "SENTINEL-client-secret-VALUE",
            },
        },
    })

    runner = CliRunner()
    # Invoke `config show` with the test base_cfg in click ctx.obj.
    result = runner.invoke(
        config_group,
        ["show"],
        obj={"config": base_cfg},
    )
    assert result.exit_code == 0, result.output
    # Raw sentinel values MUST NOT appear in CLI output (would mean masking is
    # bypassed for the new fields).
    assert "SENTINEL-client-id-VALUE" not in result.output
    assert "SENTINEL-client-secret-VALUE" not in result.output
    # Mask pattern (first-3 + `***` + last-2): "SEN***UE" shape present for each.
    # mask_sensitive_value("SENTINEL-client-id-VALUE") -> "SEN***UE"
    # mask_sensitive_value("SENTINEL-client-secret-VALUE") -> "SEN***UE"
    # We assert the FIELD label is rendered, and the mask shape appears at least
    # twice (once for each new masked field).
    assert "integrations.schwab.client_id" in result.output
    assert "integrations.schwab.client_secret" in result.output
    # Mask shape "SEN***UE" should appear at least once per field (twice min;
    # default column also masks empty-string default to "(not set)" / similar).
    assert result.output.count("SEN***UE") >= 2


# ---------- Test 6: Backwards-compat — env vars unchanged path still works ----------

def test_env_var_path_unaffected_by_new_cfg_fields(
    base_cfg: Config, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sub-bundle A operators relying on `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET`
    env vars continue to work unchanged (env vars are highest-priority tier).
    Discriminating: empty cfg fields + env vars set → `resolve_credentials_env_or_prompt`
    returns env-var values (existing T-A.1 behavior preserved). T-B.2 introduces
    the cfg-field foundation; T-B.1 (next task) wires the cascade — until then,
    env-var path is the SOLE source of credentials and must keep working."""
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt

    monkeypatch.setenv("SCHWAB_CLIENT_ID", "env-id-12345")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "env-secret-67890")
    # Empty cfg fields (default) — env vars should still be returned.
    # cfg + environment params reserved for future per-env resolution (currently
    # unused; see auth.py:142 `del cfg, environment`).
    cid, csec = resolve_credentials_env_or_prompt(
        base_cfg, base_cfg.integrations.schwab.environment,
    )
    assert cid == "env-id-12345"
    assert csec == "env-secret-67890"
    # Verify cfg fields are still empty-string defaults (T-B.2 doesn't change
    # them; T-B.1 will read them as fallback when env vars absent).
    assert base_cfg.integrations.schwab.client_id == ""
    assert base_cfg.integrations.schwab.client_secret == ""
