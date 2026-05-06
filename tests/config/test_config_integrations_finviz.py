import textwrap
from pathlib import Path

import pytest

from swing.config import Config, FinvizIntegrationConfig, IntegrationsConfig, load


def _strip_integrations_section(cfg_text: str) -> str:
    """Drop any ``[integrations.*]`` block (header + body until next section
    header or EOF) so tests that exercise an "absent integrations section"
    shape work regardless of whether the tracked swing.config.toml currently
    has one. Section header detection: line starts with ``[integrations``."""
    out: list[str] = []
    skipping = False
    for line in cfg_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("[") and stripped.rstrip().endswith("]"):
            skipping = stripped.startswith("[integrations")
            if skipping:
                continue
        if skipping:
            continue
        out.append(line)
    return "\n".join(out)


def test_finviz_integration_defaults_when_section_absent(tmp_path: Path) -> None:
    """Defaults apply when [integrations.finviz] absent (existing toml shape)."""
    cfg_text = _strip_integrations_section(Path("swing.config.toml").read_text())
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(cfg_text)
    cfg = load(cfg_path)
    assert cfg.integrations.finviz.token == ""
    assert cfg.integrations.finviz.screen_query == ""
    assert cfg.integrations.finviz.timeout_seconds == 30


def test_finviz_integration_tracked_toml_overrides_default_timeout(
    tmp_path: Path,
) -> None:
    """Tracked toml overrides default timeout_seconds (token + screen_query stay empty)."""
    cfg_text = _strip_integrations_section(Path("swing.config.toml").read_text())
    cfg_text += "\n\n[integrations.finviz]\ntimeout_seconds = 90\n"
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(cfg_text)
    cfg = load(cfg_path)
    assert cfg.integrations.finviz.timeout_seconds == 90
    assert cfg.integrations.finviz.token == ""
    assert cfg.integrations.finviz.screen_query == ""


def test_finviz_integration_tracked_toml_token_STRIPPED_at_load(tmp_path: Path) -> None:
    """Security carve-out: tracked toml MUST NOT deliver token / screen_query to cfg."""
    cfg_text = _strip_integrations_section(Path("swing.config.toml").read_text())
    cfg_text += textwrap.dedent('''
        [integrations.finviz]
        token = "TRACKED_TOKEN_LEAK"
        screen_query = "TRACKED_SCREEN_LEAK"
        timeout_seconds = 45
    ''').strip() + "\n"
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(cfg_text)
    cfg = load(cfg_path)
    assert cfg.integrations.finviz.token == ""  # stripped
    assert cfg.integrations.finviz.screen_query == ""  # stripped
    assert cfg.integrations.finviz.timeout_seconds == 45


def test_user_config_override_token_and_screen_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User-config OVERRIDE applies for token + screen_query."""
    user_cfg_dir = tmp_path / "swing-data"
    user_cfg_dir.mkdir()
    (user_cfg_dir / "user-config.toml").write_text(textwrap.dedent("""
        [integrations.finviz]
        token = "USER_CONFIG_TOKEN"
        screen_query = "v=152&f=test"
    """).strip())
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    cfg_path = Path("swing.config.toml")
    base_cfg = load(cfg_path)
    from swing.config_overrides import apply_overrides
    cfg = apply_overrides(base_cfg)
    assert cfg.integrations.finviz.token == "USER_CONFIG_TOKEN"
    assert cfg.integrations.finviz.screen_query == "v=152&f=test"


def test_config_direct_construction_still_works() -> None:
    """Existing test fixtures construct Config(...) directly; the new
    integrations field MUST have a safe default (factory) so old tests don't break."""
    from dataclasses import fields
    integrations_field = next(f for f in fields(Config) if f.name == "integrations")
    assert integrations_field.default_factory is IntegrationsConfig  # type: ignore[comparison-overlap]


def test_existing_2part_path_get_field_source_still_works(
    monkeypatch, tmp_path,
) -> None:
    """Codex R1 Major-4 regression check: extending _get to N-part paths
    must not break the existing 2-part registry consumers."""
    from pathlib import Path as _P

    from swing.config import load
    from swing.config_overrides import get_field_source

    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # empty user-config dir
    base_cfg = load(_P("swing.config.toml"))
    assert get_field_source(base_cfg, "web.chase_factor") in ("default", "tracked")
    assert get_field_source(base_cfg, "pipeline.chart_top_n_watch") in ("default", "tracked")
    assert get_field_source(base_cfg, "account.risk_equity_floor") in ("default", "tracked")
