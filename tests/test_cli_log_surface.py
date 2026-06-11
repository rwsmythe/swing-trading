from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from click.testing import CliRunner

import swing.cli as cli
from swing.config import load
from tests.cli.test_cli_eval import _minimal_config


def _cfg_path(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    return _minimal_config(project, home)


def test_non_pipeline_command_installs_cli_log(tmp_path):
    cfg_path = _cfg_path(tmp_path)
    logs_dir = load(cfg_path).paths.logs_dir
    # `config show` is a benign read-only command that goes through the group cb.
    result = CliRunner().invoke(cli.main, ["--config", str(cfg_path), "config", "show"])
    assert result.exit_code == 0, result.output
    root = logging.getLogger()
    cli_handlers = [
        h for h in root.handlers
        if isinstance(h, RotatingFileHandler)
        and getattr(h, "_swing_surface", None) == "cli"
        and h.baseFilename == os.path.abspath(logs_dir / "cli.log")
    ]
    assert len(cli_handlers) == 1


def test_cli_log_is_redacted(tmp_path):
    # Belt B on cli.log: a non-Schwabdev sentinel emitted while the cli surface is
    # installed must be redacted. Discriminator: with no formatter wired the
    # SENTINEL would survive.
    sentinel = "deadbeef" * 8  # 64 hex chars -> caught by the shape heuristic
    cfg_path = _cfg_path(tmp_path)
    logs_dir = load(cfg_path).paths.logs_dir
    result = CliRunner().invoke(cli.main, ["--config", str(cfg_path), "config", "show"])
    assert result.exit_code == 0, result.output
    logging.getLogger("swing.cli.audit").warning("leaked token=%s", sentinel)
    for h in logging.getLogger().handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    text = (logs_dir / "cli.log").read_text(encoding="utf-8")
    assert sentinel not in text


def test_pipeline_run_converges_to_pipeline_log(tmp_path, monkeypatch):
    # Routing: `swing pipeline run` ends with EXACTLY ONE swing handler whose
    # surface is "pipeline". Under skip-install the group callback never installs
    # cli.log for the pipeline subgroup, so pipeline.log is the only swing handler.
    import swing.config_overrides as config_overrides
    import swing.pipeline as pipeline_pkg
    from swing.pipeline.runner import RunResult

    cfg_path = _cfg_path(tmp_path)
    logs_dir = load(cfg_path).paths.logs_dir
    monkeypatch.setattr(config_overrides, "apply_overrides", lambda cfg: cfg)
    monkeypatch.setattr(
        pipeline_pkg, "run_pipeline",
        lambda *, cfg, trigger: RunResult(run_id=1, state="complete", error_message=None),
    )
    result = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "pipeline", "run", "--manual"]
    )
    assert result.exit_code == 0, result.output
    swing_handlers = [
        h for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler)
        and getattr(h, "_swing_surface", None) is not None
    ]
    assert len(swing_handlers) == 1
    assert swing_handlers[0]._swing_surface == "pipeline"
    assert swing_handlers[0].baseFilename == os.path.abspath(logs_dir / "pipeline.log")


def test_pipeline_list_subcommand_installs_cli_log(tmp_path):
    # R2-major-1: `pipeline list` (a NON-run pipeline subcommand) must get cli.log
    # per spec §5.1 ("every command except `pipeline run` -> cli.log"). The
    # pipeline_group callback installs it for non-run subcommands.
    from swing.data.db import ensure_schema

    cfg_path = _cfg_path(tmp_path)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()  # `pipeline list` reads pipeline_runs
    logs_dir = cfg.paths.logs_dir
    result = CliRunner().invoke(cli.main, ["--config", str(cfg_path), "pipeline", "list"])
    assert result.exit_code == 0, result.output
    cli_handlers = [
        h for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler)
        and getattr(h, "_swing_surface", None) == "cli"
        and h.baseFilename == os.path.abspath(logs_dir / "cli.log")
    ]
    assert len(cli_handlers) == 1
    # And no pipeline.log handler (list is a cli-surface command).
    assert not any(
        getattr(h, "_swing_surface", None) == "pipeline"
        for h in logging.getLogger().handlers
    )


def test_pipeline_run_with_malformed_logging_never_writes_cli_log(tmp_path, monkeypatch):
    # R1-major-1 discriminator: a MALFORMED [logging] value makes install_logging
    # replay a parse diagnostic immediately after attaching a handler. Under the OLD
    # rely-on-replacement design the group's cli.log handler would receive that
    # diagnostic BEFORE pipeline.log installs -> cli.log gets content in a pipeline
    # process (invariant violated). Under skip-install the pipeline subgroup never
    # installs cli.log, so cli.log is never even created.
    import swing.config_overrides as config_overrides
    import swing.pipeline as pipeline_pkg
    from swing.config import load
    from swing.pipeline.runner import RunResult

    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    # Append a malformed [logging] level so a parse diagnostic is collected.
    with open(cfg_path, "a", encoding="utf-8") as fh:
        fh.write('\n[logging]\nlevel = "LOUD"\n')
    logs_dir = load(cfg_path).paths.logs_dir
    monkeypatch.setattr(config_overrides, "apply_overrides", lambda cfg: cfg)
    monkeypatch.setattr(
        pipeline_pkg, "run_pipeline",
        lambda *, cfg, trigger: RunResult(run_id=1, state="complete", error_message=None),
    )
    result = CliRunner().invoke(
        cli.main, ["--config", str(cfg_path), "pipeline", "run", "--manual"]
    )
    assert result.exit_code == 0, result.output
    # The diagnostic landed in pipeline.log (proves it was emitted), and cli.log
    # was NEVER created in this pipeline process.
    for h in logging.getLogger().handlers:
        if isinstance(h, RotatingFileHandler):
            h.flush()
    assert (logs_dir / "pipeline.log").exists()
    assert "LOUD" in (logs_dir / "pipeline.log").read_text(encoding="utf-8")
    assert not (logs_dir / "cli.log").exists()
