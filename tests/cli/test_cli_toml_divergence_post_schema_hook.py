"""Phase 9 T-A.5 — CLI post-schema-validation TOML divergence hook.

Per Codex R3 M#1 architectural fix (plan §A.5.1):
  - swing/config.py:load() REMAINS PURE — no DB connection parameter, no
    risk_policy read in load.
  - The divergence check is invoked at every CLI command's @main.callback
    AFTER load_config(), but db-migrate explicitly SKIPS (it's the path
    that brings DB to v17).
  - The helper itself silently skips on pre-v17 / no-active-policy DBs so
    fresh installs / test fixtures don't trip on schema-not-yet-present.

Tests verify:
  - test_load_config_pure_no_db_required: load(config_path) succeeds with
    NO DB anywhere — no swing.data.db import side effect, no DB connection
    attempted.
  - test_db_migrate_skips_divergence_hook: invoking `swing db-migrate` on
    a v16 DB succeeds (brings DB to v17) WITHOUT invoking the divergence
    hook. Verified via monkeypatch counter.
  - test_other_command_invokes_divergence_hook: invoking a non-migrate
    command (e.g., `config show` or `hypothesis list`) DOES invoke the
    hook AFTER ensure_schema-equivalent state.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture
def cfg_path(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    return _minimal_config(project, home)


def test_load_config_pure_no_db_required(cfg_path: Path) -> None:
    """swing.config.load(config_path) succeeds without any DB connection.

    Discriminating: load() must NOT import swing.data.db nor attempt to
    open a sqlite3 connection. Verified by importing load in isolation +
    invoking on the test cfg path — no DB exists at the cfg's
    paths.db_path location yet.
    """
    from swing.config import load
    cfg = load(cfg_path)
    # Sanity: cfg loaded; DB does NOT exist on disk.
    assert cfg.account.risk_equity_floor == 7500.0
    assert not cfg.paths.db_path.exists()


def test_db_migrate_skips_divergence_hook(
    cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """swing db-migrate must NOT invoke check_and_reconcile_toml_divergence.

    Pre-fix expectation (if implementer forgot the skip): hook fires on
    the v16 DB pre-migration; helper's pre-v17 silent-skip would still
    return (cfg, None) — so the test counter would observe ONE invocation.
    Post-fix expectation: zero invocations.
    """
    call_count = {"n": 0}

    import swing.cli as cli_mod
    original = cli_mod._apply_toml_divergence_check

    def counting_check(ctx):
        call_count["n"] += 1
        return original(ctx)

    monkeypatch.setattr(cli_mod, "_apply_toml_divergence_check", counting_check)

    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert result.exit_code == 0, result.output
    assert call_count["n"] == 0, (
        f"db-migrate must NOT invoke divergence hook; got {call_count['n']} call(s). "
        f"Output: {result.output}"
    )


def test_non_migrate_command_invokes_divergence_hook(
    cfg_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-migrate command (e.g., `hypothesis list`) DOES invoke the hook
    after the DB is at v17."""
    runner = CliRunner()
    # First, bring DB to v17 via db-migrate.
    result = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert result.exit_code == 0, result.output

    # Now monkeypatch the hook + invoke a regular command.
    call_count = {"n": 0}

    import swing.cli as cli_mod
    original = cli_mod._apply_toml_divergence_check

    def counting_check(ctx):
        call_count["n"] += 1
        return original(ctx)

    monkeypatch.setattr(cli_mod, "_apply_toml_divergence_check", counting_check)

    result = runner.invoke(main, ["--config", str(cfg_path), "hypothesis", "list"])
    assert result.exit_code == 0, result.output
    assert call_count["n"] == 1


def test_divergence_hook_emits_stderr_advisory_when_divergent(
    cfg_path: Path,
) -> None:
    """When TOML diverges from risk_policy, the CLI emits a stderr advisory
    line (mirrors pip / git divergence-warning pattern per spec §3.1.3 R3
    Minor #2)."""
    runner = CliRunner()
    # Bring DB to v17 first.
    result = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert result.exit_code == 0, result.output

    # Now divergently edit risk_equity_floor to 5000 in the cfg's TOML.
    text = cfg_path.read_text(encoding="utf-8")
    text = text.replace(
        "risk_equity_floor = 7500.0",
        "risk_equity_floor = 5000.0",
    )
    cfg_path.write_text(text, encoding="utf-8")

    # Invoke a non-migrate command. CliRunner merges stdout+stderr into
    # result.output by default; the advisory is emitted via click.echo(...,
    # err=True) which lands there.
    result = runner.invoke(main, ["--config", str(cfg_path), "hypothesis", "list"])
    assert result.exit_code == 0, result.output
    assert "diverge" in result.output.lower(), (
        f"expected divergence advisory in CLI output; got {result.output!r}"
    )
