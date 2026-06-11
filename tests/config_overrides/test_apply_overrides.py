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


def test_apply_overrides_short_circuits_on_non_dataclass_cfg():
    """Phase 12 Sub-bundle B Codex R1 Critical #1 follow-up — defensive
    short-circuit when base_cfg is NOT a dataclass instance.

    Background: ``apply_overrides`` is now called at every Schwab CLI
    entry point (setup/refresh/logout) and the web /schwab/setup route.
    Some legacy test stubs build cfg via ``types.SimpleNamespace`` (e.g.
    ``tests/integrations/test_schwab_pipeline_active_exclusion.py``);
    the final ``dataclasses.replace(base_cfg, ...)`` call would raise
    ``TypeError: replace() should be called on dataclass instances``
    for such stubs.

    The defensive guard short-circuits + returns the stub unchanged so
    tests that exercise behavior BEFORE the cfg-cascade matters (e.g.
    pipeline-active rejection) keep working.
    """
    from types import SimpleNamespace
    stub = SimpleNamespace(
        paths=SimpleNamespace(db_path="/tmp/test.db"),
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(client_id="", client_secret=""),
        ),
    )
    result = apply_overrides(stub)
    # Same identity — short-circuit returned the stub unchanged.
    assert result is stub


def test_logging_override_preserves_base_logger_levels(base_cfg):
    # Codex R1-minor: a user [logging] override that touches only max_bytes must
    # NOT erase the base [logging.loggers] table. Seed base loggers, override an
    # unrelated logging field, assert the per-logger levels survive.
    import logging
    from dataclasses import replace

    seeded = replace(
        base_cfg,
        logging=replace(base_cfg.logging, logger_levels={"httpx": logging.WARNING}),
    )
    write_user_overrides({"logging": {"max_bytes": 1234567}})
    eff = apply_overrides(seeded)
    assert eff.logging.max_bytes == 1234567
    assert eff.logging.resolved_logger_levels() == {"httpx": logging.WARNING}


def test_logging_override_merges_logger_levels_per_key(base_cfg):
    # An override [logging.loggers] table merges onto the base per key (user wins).
    import logging
    from dataclasses import replace

    seeded = replace(
        base_cfg,
        logging=replace(
            base_cfg.logging,
            logger_levels={"httpx": logging.WARNING, "yfinance": logging.ERROR},
        ),
    )
    write_user_overrides({"logging": {"loggers": {"httpx": "DEBUG", "urllib3": "ERROR"}}})
    eff = apply_overrides(seeded)
    assert eff.logging.resolved_logger_levels() == {
        "httpx": logging.DEBUG,        # user override wins
        "yfinance": logging.ERROR,     # base preserved
        "urllib3": logging.ERROR,      # user addition
    }
