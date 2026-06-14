"""Phase 18 Arc 18-C: the top-level Click group callback installs the
surface='cli' yfinance audit base for archive-touching commands (eval, weather,
pattern label, ...) BY CONSTRUCTION, and SKIPS db-migrate/db-backup/pipeline."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

import swing.cli as cli
from swing.data import yfinance_audit_context as ctxmod
from swing.data.yfinance_audit_context import get_yfinance_audit_context
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture(autouse=True)
def _reset_ctx():
    ctxmod._reset_for_test()
    yield
    ctxmod._reset_for_test()


def _write_minimal_config(project_dir: Path, home_dir: Path) -> Path:
    return _minimal_config(project_dir, home_dir)


def _invoke_capturing_install(monkeypatch, cfg_path: Path, args: list[str]):
    """Invoke `args` and capture whether the cli base was installed (the surface
    seen by install_yfinance_cli_audit_context), via the real installer."""
    seen = {}
    real = cli.install_yfinance_cli_audit_context

    def spy(cfg):
        seen["installed"] = True
        real(cfg)
        seen["surface"] = get_yfinance_audit_context().surface
    monkeypatch.setattr(cli, "install_yfinance_cli_audit_context", spy)
    runner = CliRunner()
    runner.invoke(cli.main, ["--config", str(cfg_path)] + args)
    return seen


def test_db_migrate_does_not_install_cli_base(tmp_path, monkeypatch):
    project = tmp_path / "p"; home = tmp_path / "h"
    project.mkdir(); home.mkdir()
    cfg_path = _write_minimal_config(project, home)
    seen = _invoke_capturing_install(monkeypatch, cfg_path, ["db-migrate"])
    assert seen.get("installed") is None  # skipped


def test_pipeline_subgroup_does_not_install_cli_base(tmp_path, monkeypatch):
    project = tmp_path / "p"; home = tmp_path / "h"
    project.mkdir(); home.mkdir()
    cfg_path = _write_minimal_config(project, home)
    # `pipeline` is a group; invoking with no subcommand still routes the
    # top-level callback. The cli base install must be skipped for it.
    seen = _invoke_capturing_install(monkeypatch, cfg_path, ["pipeline"])
    assert seen.get("installed") is None


def test_weather_installs_cli_base(tmp_path, monkeypatch):
    project = tmp_path / "p"; home = tmp_path / "h"
    project.mkdir(); home.mkdir()
    cfg_path = _write_minimal_config(project, home)
    # migrate first so the divergence check (which runs before the install in
    # the group callback) has a real DB.
    CliRunner().invoke(cli.main, ["--config", str(cfg_path), "db-migrate"])
    ctxmod._reset_for_test()
    # weather reaches PriceFetcher -> must install the cli base. We don't need
    # the command to fully succeed; the callback runs before dispatch.
    seen = _invoke_capturing_install(
        monkeypatch, cfg_path, ["weather", "--ticker", "QQQ"])
    assert seen.get("installed") is True
    assert seen.get("surface") == "cli"
