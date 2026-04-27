"""Phase 5 Task 5.5 — CLI ``swing trade entry --chart-pattern-operator``
with cached-only refusal gate.

Spec §3.7 (R1 C1) — CLI parity with the web form's stub gate:

- For tickers WITHOUT a cached classification (out-of-scope, missing
  pipeline run, or only a classifier-error row), passing
  ``--chart-pattern-operator`` MUST refuse with a non-zero exit code
  and a specific error message.
- For tickers WITH a cached classification, the operator override
  persists alongside the algo snapshot the CLI resolved at command
  start (snapshot-at-entry-surface ToCToU pattern; spec §3.6).
- Backward-compat: existing invocations without the new flag still
  succeed.
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config
from tests.web.test_view_models._pattern_classification_seed import (
    seed_pipeline_with_classification,
)


def _setup(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def _read_chart_pattern_columns(cfg_path: Path, ticker: str):
    """Round-trip: read the four chart_pattern columns for an open trade."""
    import tomllib

    from swing.data.db import connect
    from swing.data.repos.trades import find_any_open_trade

    cfg_data = tomllib.loads(cfg_path.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        t = find_any_open_trade(conn, ticker=ticker)
        if t is None:
            return None
        return (
            t.chart_pattern_algo,
            t.chart_pattern_algo_confidence,
            t.chart_pattern_operator,
            t.chart_pattern_classification_pipeline_run_id,
        )
    finally:
        conn.close()


def _db_path_for_cfg(cfg_path: Path) -> Path:
    import tomllib

    cfg_data = tomllib.loads(cfg_path.read_text())
    return Path(cfg_data["paths"]["db_path"])


def test_cli_trade_entry_chart_pattern_operator_refused_without_cache(tmp_path: Path):
    """Spec §3.7 R1 C1: CLI refuses --chart-pattern-operator when no
    cached classification row exists for the ticker.

    Discriminating: pre-Task-5.5 the flag does not exist (Click
    rejects unknown options with usage error, exit_code != 0 for a
    different reason). Post-fix the flag is accepted but the refusal
    gate fires with the explicit error message; a regression that
    silently allows the override (e.g. drops the gate while keeping
    the option) would persist a trade row instead of raising and
    would NOT contain the "requires a cached classification" string
    in the output.
    """
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-26",
        "--entry-price", "10.0", "--shares", "1", "--initial-stop", "9.0",
        "--rationale", "aplus-setup",
        "--chart-pattern-operator", "flag",
    ])
    assert result.exit_code != 0, result.output
    output = result.output or (str(result.exception) if result.exception else "")
    assert "requires a cached classification" in output
    # Compounding-confound: no trade row should have been inserted.
    assert _read_chart_pattern_columns(cfg, "AAPL") is None


def test_cli_trade_entry_chart_pattern_operator_persists_when_cached(tmp_path: Path):
    """Cached path: --chart-pattern-operator flag persists alongside
    the algo snapshot the CLI resolved at command start."""
    runner, cfg = _setup(tmp_path)
    db_path = _db_path_for_cfg(cfg)
    run_id, _eval_id = seed_pipeline_with_classification(
        db_path, ticker="AAPL", pattern="flag", confidence=0.78,
    )
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-26",
        "--entry-price", "10.0", "--shares", "1", "--initial-stop", "9.0",
        "--rationale", "aplus-setup",
        "--chart-pattern-operator", "flag",
    ])
    assert result.exit_code == 0, result.output
    assert _read_chart_pattern_columns(cfg, "AAPL") == (
        "flag", 0.78, "flag", run_id,
    )


def test_cli_trade_entry_no_chart_pattern_flag_omitted_works_with_cache(
    tmp_path: Path,
):
    """Backward-compat: existing CLI invocations without
    --chart-pattern-operator still succeed; with a cached
    classification the snapshot rides along automatically (operator
    column NULL — the operator did not override)."""
    runner, cfg = _setup(tmp_path)
    db_path = _db_path_for_cfg(cfg)
    run_id, _eval_id = seed_pipeline_with_classification(
        db_path, ticker="AAPL", pattern="flag", confidence=0.78,
    )
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-26",
        "--entry-price", "10.0", "--shares", "1", "--initial-stop", "9.0",
        "--rationale", "aplus-setup",
    ])
    assert result.exit_code == 0, result.output
    assert _read_chart_pattern_columns(cfg, "AAPL") == (
        "flag", 0.78, None, run_id,
    )


def test_cli_trade_entry_no_chart_pattern_flag_omitted_works_without_cache(
    tmp_path: Path,
):
    """Backward-compat: no flag, no cache — trade row inserts with
    NULL chart_pattern columns. Confirms the resolution does not
    accidentally raise on the no-cache path."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-26",
        "--entry-price", "10.0", "--shares", "1", "--initial-stop", "9.0",
        "--rationale", "aplus-setup",
    ])
    assert result.exit_code == 0, result.output
    assert _read_chart_pattern_columns(cfg, "AAPL") == (
        None, None, None, None,
    )
