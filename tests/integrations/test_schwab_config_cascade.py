"""Schwab cfg cascade (T-A.2) — `cfg.integrations.schwab` sub-dataclass tests.

Covers plan §A.6 + recon doc §2.9 +1 deviation (6 fields, not 5; `callback_url`
added with __post_init__ trailing-slash/HTTPS/localhost validators).

Tests use `monkeypatch.setenv("USERPROFILE"/HOME)` per CLAUDE.md gotcha (operator
real user-config.toml must NOT be polluted by tests exercising write paths).
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from swing.config import (
    Config,
    IntegrationsConfig,
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
    [integrations.schwab] tracked section."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    extra = """
[integrations.schwab]
timeout_seconds = 30.0
marketdata_ladder_enabled = true
"""
    cfg_path = _write_cfg(project_dir, tmp_home, extra=extra)
    return load(cfg_path)


# ---------- (1) Default cascade ----------

def test_default_cascade_environment_production(base_cfg: Config) -> None:
    """[integrations.schwab] tracked section omits environment; in-code default
    'production' applies through dataclass field default."""
    assert base_cfg.integrations.schwab.environment == "production"
    assert base_cfg.integrations.schwab.account_hash is None
    assert base_cfg.integrations.schwab.lookback_days == 7
    assert base_cfg.integrations.schwab.timeout_seconds == 30.0
    assert base_cfg.integrations.schwab.marketdata_ladder_enabled is True
    assert base_cfg.integrations.schwab.callback_url == "https://127.0.0.1"


# ---------- (2-5) User-config overrides ----------

def test_environment_override_applied(base_cfg: Config, tmp_home: Path) -> None:
    write_user_overrides({"integrations": {"schwab": {"environment": "sandbox"}}})
    eff = apply_overrides(base_cfg)
    assert eff.integrations.schwab.environment == "sandbox"
    # Non-Schwab finviz untouched
    assert eff.integrations.finviz.token == ""


def test_account_hash_override_applied(base_cfg: Config, tmp_home: Path) -> None:
    write_user_overrides({
        "integrations": {"schwab": {"account_hash": "1A2B3C4D5E6F7G8H9F"}},
    })
    eff = apply_overrides(base_cfg)
    assert eff.integrations.schwab.account_hash == "1A2B3C4D5E6F7G8H9F"


def test_lookback_days_override_applied(base_cfg: Config, tmp_home: Path) -> None:
    write_user_overrides({"integrations": {"schwab": {"lookback_days": 14}}})
    eff = apply_overrides(base_cfg)
    assert eff.integrations.schwab.lookback_days == 14


def test_callback_url_override_applied(base_cfg: Config, tmp_home: Path) -> None:
    write_user_overrides({
        "integrations": {"schwab": {"callback_url": "https://127.0.0.1:8182"}},
    })
    eff = apply_overrides(base_cfg)
    assert eff.integrations.schwab.callback_url == "https://127.0.0.1:8182"


# ---------- (6) environment validator ----------

def test_environment_validator_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="environment"):
        SchwabIntegrationConfig(environment="invalid")


def test_environment_validator_accepts_sandbox_and_production() -> None:
    a = SchwabIntegrationConfig(environment="sandbox")
    b = SchwabIntegrationConfig(environment="production")
    assert a.environment == "sandbox"
    assert b.environment == "production"


# ---------- (7) lookback_days validator ----------

def test_lookback_days_validator_rejects_zero_and_negative() -> None:
    with pytest.raises(ValueError, match="lookback_days"):
        SchwabIntegrationConfig(lookback_days=0)
    with pytest.raises(ValueError, match="lookback_days"):
        SchwabIntegrationConfig(lookback_days=-1)


def test_lookback_days_validator_accepts_positive() -> None:
    cfg = SchwabIntegrationConfig(lookback_days=30)
    assert cfg.lookback_days == 30


# ---------- (8) timeout_seconds validator ----------

def test_timeout_seconds_validator_rejects_nonpositive_and_nan_inf() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        SchwabIntegrationConfig(timeout_seconds=0.0)
    with pytest.raises(ValueError, match="timeout_seconds"):
        SchwabIntegrationConfig(timeout_seconds=-1.0)
    with pytest.raises(ValueError, match="timeout_seconds"):
        SchwabIntegrationConfig(timeout_seconds=float("nan"))
    with pytest.raises(ValueError, match="timeout_seconds"):
        SchwabIntegrationConfig(timeout_seconds=math.inf)


def test_timeout_seconds_validator_accepts_positive() -> None:
    cfg = SchwabIntegrationConfig(timeout_seconds=15.5)
    assert cfg.timeout_seconds == 15.5


# ---------- (9) marketdata_ladder_enabled accept ----------

def test_marketdata_ladder_enabled_accepts_bool() -> None:
    a = SchwabIntegrationConfig(marketdata_ladder_enabled=True)
    b = SchwabIntegrationConfig(marketdata_ladder_enabled=False)
    assert a.marketdata_ladder_enabled is True
    assert b.marketdata_ladder_enabled is False


# ---------- (10) account_hash validator ----------

def test_account_hash_validator_rejects_empty_string_and_non_string() -> None:
    with pytest.raises(ValueError, match="account_hash"):
        SchwabIntegrationConfig(account_hash="")
    with pytest.raises(TypeError, match="account_hash"):
        SchwabIntegrationConfig(account_hash=12345)  # type: ignore[arg-type]


def test_account_hash_validator_accepts_none_and_nonempty_string() -> None:
    a = SchwabIntegrationConfig(account_hash=None)
    b = SchwabIntegrationConfig(account_hash="1A2B3C4D5E6F")
    assert a.account_hash is None
    assert b.account_hash == "1A2B3C4D5E6F"


# ---------- (11) callback_url accept ----------

def test_callback_url_validator_accepts_localhost_forms() -> None:
    a = SchwabIntegrationConfig(callback_url="https://127.0.0.1")
    b = SchwabIntegrationConfig(callback_url="https://127.0.0.1:8182")
    c = SchwabIntegrationConfig(callback_url="https://localhost")
    d = SchwabIntegrationConfig(callback_url="https://localhost:8182")
    assert a.callback_url == "https://127.0.0.1"
    assert b.callback_url == "https://127.0.0.1:8182"
    assert c.callback_url == "https://localhost"
    assert d.callback_url == "https://localhost:8182"


# ---------- (12) callback_url reject ----------

@pytest.mark.parametrize(
    "bad_url",
    [
        "",  # empty
        "http://127.0.0.1",  # non-HTTPS
        "https://example.com",  # non-localhost
        "https://127.0.0.1/",  # trailing slash
        "127.0.0.1",  # missing scheme
        "https://example.com:8080",  # non-localhost with port
    ],
)
def test_callback_url_validator_rejects_invalid_forms(bad_url: str) -> None:
    with pytest.raises(ValueError, match="callback_url"):
        SchwabIntegrationConfig(callback_url=bad_url)


# ---------- (13) +1 BONUS — account_hash masking through swing config show / VM ----------

def test_account_hash_masked_in_field_registry_and_vm_rendering(
    base_cfg: Config, tmp_home: Path,
) -> None:
    """The account_hash FIELD_REGISTRY entry has masked=True; the VM-rendered
    current_value matches a first-3 + asterisks + last-2 mask shape and does
    NOT include the raw hash bytes. None remains None at render time (template
    handles '(not set)' display)."""
    import re

    from swing.config_validation import FIELD_REGISTRY, get_spec
    from swing.web.view_models.config import build_config_vm

    # Field is registered with masked=True
    spec = get_spec("integrations.schwab.account_hash")
    assert spec.masked is True
    # FieldSpec list contains the schwab account_hash entry
    paths = {s.path for s in FIELD_REGISTRY}
    assert "integrations.schwab.account_hash" in paths

    # Plant a known account_hash and render via the VM
    secret = "1A2B3C4D5E6F7G8H9F"
    write_user_overrides({
        "integrations": {"schwab": {"account_hash": secret}},
    })
    eff = apply_overrides(base_cfg)
    vm = build_config_vm(eff, saved=False, conn=None)
    matching = [r for r in vm.rows if r.path == "integrations.schwab.account_hash"]
    assert len(matching) == 1
    row = matching[0]
    # Rendered value must NOT contain the raw bytes
    rendered = str(row.current_value)
    assert secret not in rendered
    # Must match first-3 + asterisks + last-2 pattern (e.g., "1A2***9F")
    assert re.match(r"^.{3}\*{3,}.{2}$", rendered), (
        f"Mask pattern violated; got {rendered!r}"
    )


def test_account_hash_masked_when_none_renders_not_set(base_cfg: Config) -> None:
    """When account_hash is None, the VM renders '(not set)' rather than
    asterisk-masking a None value."""
    from swing.web.view_models.config import build_config_vm

    vm = build_config_vm(base_cfg, saved=False, conn=None)
    matching = [r for r in vm.rows if r.path == "integrations.schwab.account_hash"]
    assert len(matching) == 1
    assert matching[0].current_value == "(not set)"


# ---------- Module-level invariant: IntegrationsConfig has schwab sub-dataclass ----------

def test_integrations_config_has_schwab_sub_dataclass() -> None:
    """Defense-in-depth: IntegrationsConfig.schwab default is a SchwabIntegrationConfig
    instance with all 6 fields at expected defaults."""
    integrations = IntegrationsConfig()
    s = integrations.schwab
    assert isinstance(s, SchwabIntegrationConfig)
    assert s.environment == "production"
    assert s.account_hash is None
    assert s.lookback_days == 7
    assert s.timeout_seconds == 30.0
    assert s.marketdata_ladder_enabled is True
    assert s.callback_url == "https://127.0.0.1"
