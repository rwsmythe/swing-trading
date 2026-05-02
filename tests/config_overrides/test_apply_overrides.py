"""apply_overrides(base_cfg) returns Config with V1 fields overridden."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import load
from swing.config_overrides import apply_overrides, get_field_source
from swing.config_user import write_user_overrides
from tests.web.test_config_web import _write_cfg  # reuse helper


@pytest.fixture
def base_cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Built from a minimal swing.config.toml. Isolated USERPROFILE."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    return load(cfg_path)


def test_no_user_config_returns_base_unchanged(base_cfg):
    eff = apply_overrides(base_cfg)
    assert eff.web.chase_factor == base_cfg.web.chase_factor
    assert eff.pipeline.chart_top_n_watch == base_cfg.pipeline.chart_top_n_watch
    assert eff.account.risk_equity_floor == base_cfg.account.risk_equity_floor


def test_chase_factor_override_applied(base_cfg):
    write_user_overrides({"web": {"chase_factor": 0.025}})
    eff = apply_overrides(base_cfg)
    assert eff.web.chase_factor == 0.025
    # Other fields untouched
    assert eff.pipeline.chart_top_n_watch == base_cfg.pipeline.chart_top_n_watch


def test_chart_top_n_watch_override_applied(base_cfg):
    write_user_overrides({"pipeline": {"chart_top_n_watch": 20}})
    eff = apply_overrides(base_cfg)
    assert eff.pipeline.chart_top_n_watch == 20


def test_risk_equity_floor_override_applied(base_cfg):
    write_user_overrides({"account": {"risk_equity_floor": 12000.0}})
    eff = apply_overrides(base_cfg)
    assert eff.account.risk_equity_floor == 12000.0


def test_three_overrides_compose(base_cfg):
    write_user_overrides({
        "web": {"chase_factor": 0.025},
        "pipeline": {"chart_top_n_watch": 20},
        "account": {"risk_equity_floor": 12000.0},
    })
    eff = apply_overrides(base_cfg)
    assert eff.web.chase_factor == 0.025
    assert eff.pipeline.chart_top_n_watch == 20
    assert eff.account.risk_equity_floor == 12000.0


def test_unknown_section_ignored(base_cfg):
    """Forward-compat: future fields in user-config don't crash V1."""
    write_user_overrides({
        "web": {"chase_factor": 0.025, "unknown_v2_field": 99},
        "future_section": {"hypothetical": True},
    })
    eff = apply_overrides(base_cfg)
    assert eff.web.chase_factor == 0.025  # known field still applied
    # No exception, no field-on-Web added at runtime.


def test_apply_re_reads_user_config_each_call(base_cfg):
    """Per-request semantic: subsequent call sees subsequent overrides."""
    write_user_overrides({"web": {"chase_factor": 0.025}})
    eff1 = apply_overrides(base_cfg)
    assert eff1.web.chase_factor == 0.025

    write_user_overrides({"web": {"chase_factor": 0.030}})
    eff2 = apply_overrides(base_cfg)
    assert eff2.web.chase_factor == 0.030


def test_get_field_source_default(base_cfg, tmp_path, monkeypatch):
    """No tracked-toml override + no user-config → 'default'.

    Uses a CFG built from the registry default (web.chase_factor=0.01),
    NOT a tracked-toml override. Helper _write_cfg omits a [web] block,
    so cfg.web.chase_factor falls back to the dataclass default.
    """
    assert get_field_source(base_cfg, "web.chase_factor") == "default"


def test_get_field_source_tracked(tmp_path, monkeypatch):
    """Tracked-toml row present + no user-config → 'tracked'."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(
        tmp_path / "project", tmp_path / "home",
        extra='[web]\nchase_factor = 0.015\n',
    )
    cfg = load(cfg_path)
    assert get_field_source(cfg, "web.chase_factor") == "tracked"


def test_get_field_source_override(base_cfg):
    write_user_overrides({"web": {"chase_factor": 0.02}})
    assert get_field_source(base_cfg, "web.chase_factor") == "override"


def test_get_field_source_override_even_when_value_equals_default(base_cfg):
    """Codex watch-item #4 — explicit override at default value is still 'override'.

    Operator's intent to lock the value is preserved by reporting the
    source as 'override'.
    """
    write_user_overrides({"web": {"chase_factor": 0.01}})  # == default
    assert get_field_source(base_cfg, "web.chase_factor") == "override"
