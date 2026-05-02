"""swing config show/set/reset — CLI parity with web routes."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.config_user import load_user_overrides, write_user_overrides
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def runner_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    return CliRunner(), cfg_path


def test_show_lists_three_fields_default_source(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, ["--config", str(cfg_path), "config", "show"])
    assert r.exit_code == 0, r.output
    assert "Chase factor" in r.output
    assert "Watchlist chart count" in r.output
    assert "Risk floor" in r.output
    assert "default" in r.output
    # Default values present
    assert "0.01" in r.output
    assert "10" in r.output
    assert "7500" in r.output


def test_show_marks_override_after_set(runner_env):
    runner, cfg_path = runner_env
    write_user_overrides({"web": {"chase_factor": 0.025}})
    r = runner.invoke(main, ["--config", str(cfg_path), "config", "show"])
    assert "override" in r.output
    assert "0.025" in r.output


def test_set_writes_user_config(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "set", "web.chase_factor", "0.015",
    ])
    assert r.exit_code == 0
    assert load_user_overrides() == {"web": {"chase_factor": 0.015}}


def test_set_hard_refuse_exits_nonzero_with_stderr(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "set", "web.chase_factor", "0.5",
    ])
    assert r.exit_code != 0
    assert "must be" in r.output.lower() or "<=" in r.output
    assert load_user_overrides() == {}


def test_set_soft_warn_prompts_yes(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(
        main,
        ["--config", str(cfg_path), "config", "set", "web.chase_factor", "0.05"],
        input="y\n",
    )
    assert r.exit_code == 0
    assert "Confirm" in r.output or "above the typical" in r.output
    assert load_user_overrides() == {"web": {"chase_factor": 0.05}}


def test_set_soft_warn_prompts_no_does_not_write(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(
        main,
        ["--config", str(cfg_path), "config", "set", "web.chase_factor", "0.05"],
        input="n\n",
    )
    assert r.exit_code != 0  # aborted
    assert load_user_overrides() == {}


def test_set_force_skips_prompt_for_soft_warn(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "set",
        "--force", "web.chase_factor", "0.05",
    ])
    assert r.exit_code == 0
    assert load_user_overrides() == {"web": {"chase_factor": 0.05}}


def test_set_force_does_not_bypass_hard_refuse(runner_env):
    """Discriminating-test: --force only bypasses soft-warn, NEVER hard-refuse."""
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "set",
        "--force", "web.chase_factor", "0.5",  # hard fail
    ])
    assert r.exit_code != 0
    assert load_user_overrides() == {}


def test_set_unknown_field_exits_nonzero(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "set", "web.fake_field", "1.0",
    ])
    assert r.exit_code != 0


def test_reset_removes_field(runner_env):
    runner, cfg_path = runner_env
    write_user_overrides({"web": {"chase_factor": 0.025}})
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "reset", "web.chase_factor",
    ])
    assert r.exit_code == 0
    assert load_user_overrides() == {}


def test_reset_unknown_field_exits_nonzero(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "reset", "web.fake_field",
    ])
    assert r.exit_code != 0
