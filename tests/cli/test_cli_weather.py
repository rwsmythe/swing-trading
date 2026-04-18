"""CLI weather subcommand — runs classifier + writes row + prints status line."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def test_cli_weather_prints_status(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "project"; project_dir.mkdir()
    home_dir = tmp_path / "home"; home_dir.mkdir()
    cfg_path = _minimal_config(project_dir, home_dir)

    closes = [100.0 + i * 0.5 for i in range(60)]
    idx = pd.bdate_range(end="2026-04-15", periods=60)
    df = pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * 60,
    }, index=idx)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: df,
    )

    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    result = runner.invoke(main, ["--config", str(cfg_path), "weather"])

    assert result.exit_code == 0, result.output
    assert "Status:" in result.output
    assert "Bullish" in result.output
