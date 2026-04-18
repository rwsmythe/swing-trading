"""Integration test for swing CLI: db-migrate + eval subcommands."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from swing.cli import main


def _minimal_finviz_csv(path: Path, tickers: list[str]) -> Path:
    df = pd.DataFrame({
        "No.": list(range(1, len(tickers) + 1)),
        "Ticker": tickers,
        "Price": [200.0 - i for i in range(len(tickers))],
    })
    df.to_csv(path, index=False)
    return path


def _minimal_universe(path: Path, tickers: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# version: test-v1\n# source: test\n# columns: ticker\nticker\n"
        + "\n".join(tickers) + "\n",
        encoding="utf-8",
    )
    return path


def _minimal_config(project_dir: Path, home_dir: Path) -> Path:
    """Write a config with db/cache in home_dir, universe in project_dir/reference."""
    cfg_path = project_dir / "swing.config.toml"
    _minimal_universe(project_dir / "reference" / "rs-universe.csv", ["AAPL", "MSFT"])

    cfg_path.write_text(
        f"""[paths]
db_path = "{(home_dir / 'swing-data' / 'swing.db').as_posix()}"
data_dir = "{(home_dir / 'swing-data').as_posix()}"
logs_dir = "{(home_dir / 'swing-data' / 'logs').as_posix()}"
charts_dir = "{(home_dir / 'swing-data' / 'charts').as_posix()}"
backups_dir = "{(home_dir / 'swing-data' / 'backups').as_posix()}"
prices_cache_dir = "{(home_dir / 'swing-data' / 'prices-cache').as_posix()}"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1200.0
starting_date = "2026-03-16"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 4
hard_cap_open = 6

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0
tightness_days_required = 2
tightness_range_factor = 0.67
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7
allowed_miss_names = ["TT8"]
rising_ma_period_days = 21
high_52w_margin_pct = 25.0
low_52w_min_pct = 30.0

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
""",
        encoding="utf-8",
    )
    return cfg_path


def test_cli_db_migrate_creates_schema(tmp_path: Path):
    project_dir = tmp_path / "project"
    home_dir = tmp_path / "home"
    project_dir.mkdir()
    home_dir.mkdir()
    cfg_path = _minimal_config(project_dir, home_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert result.exit_code == 0, result.output

    db = home_dir / "swing-data" / "swing.db"
    assert db.exists()
    conn = sqlite3.connect(db)
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == 1
    conn.close()


def test_cli_eval_writes_evaluation_run(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "project"
    home_dir = tmp_path / "home"
    project_dir.mkdir()
    home_dir.mkdir()
    cfg_path = _minimal_config(project_dir, home_dir)
    csv_path = project_dir / "finviz-test.csv"
    _minimal_finviz_csv(csv_path, ["AAPL", "MSFT"])

    def fake_get(self, ticker, lookback_days, *, as_of_date=None):
        closes = [10.0 + i * 0.15 for i in range(260)]
        idx = pd.bdate_range(end="2026-04-17", periods=260)
        return pd.DataFrame(
            {"Open": closes, "High": [c * 1.01 for c in closes],
             "Low": [c * 0.99 for c in closes], "Close": closes,
             "Volume": [1_000_000] * 260}, index=idx,
        )

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fake_get)

    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    result = runner.invoke(main, ["--config", str(cfg_path), "eval", "--csv", str(csv_path)])
    assert result.exit_code == 0, result.output

    db = home_dir / "swing-data" / "swing.db"
    conn = sqlite3.connect(db)
    runs = conn.execute("SELECT id, tickers_evaluated FROM evaluation_runs").fetchall()
    assert len(runs) == 1
    assert runs[0][1] == 2

    candidates = conn.execute("SELECT ticker, bucket FROM candidates").fetchall()
    assert {c[0] for c in candidates} == {"AAPL", "MSFT"}
    conn.close()


def test_cli_eval_writes_excluded_and_error_rows(tmp_path: Path, monkeypatch):
    """Excluded (ETF blocklist) and error (fetch failure) tickers get candidate rows."""
    project_dir = tmp_path / "project"
    home_dir = tmp_path / "home"
    project_dir.mkdir()
    home_dir.mkdir()
    cfg_path = _minimal_config(project_dir, home_dir)

    # Override config to put UCO on the manual_block list
    text = cfg_path.read_text(encoding="utf-8")
    text = text.replace('manual_block = []', 'manual_block = ["UCO"]')
    cfg_path.write_text(text, encoding="utf-8")

    csv_path = project_dir / "finviz.csv"
    _minimal_finviz_csv(csv_path, ["UCO", "BADFETCH", "AAPL"])

    def fake_get(self, ticker, lookback_days, *, as_of_date=None):
        if ticker == "BADFETCH":
            raise ValueError("Simulated fetch failure")
        closes = [10.0 + i * 0.15 for i in range(260)]
        idx = pd.bdate_range(end="2026-04-17", periods=260)
        return pd.DataFrame(
            {"Open": closes, "High": [c * 1.01 for c in closes],
             "Low": [c * 0.99 for c in closes], "Close": closes,
             "Volume": [1_000_000] * 260}, index=idx,
        )

    monkeypatch.setattr("swing.prices.PriceFetcher.get", fake_get)

    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    result = runner.invoke(main, ["--config", str(cfg_path), "eval", "--csv", str(csv_path)])
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(home_dir / "swing-data" / "swing.db")
    rows = conn.execute("SELECT ticker, bucket, notes FROM candidates ORDER BY ticker").fetchall()
    by_ticker = {r[0]: (r[1], r[2]) for r in rows}

    assert by_ticker["UCO"][0] == "excluded"
    assert "blocklist" in (by_ticker["UCO"][1] or "").lower()
    assert by_ticker["BADFETCH"][0] == "error"
    assert "fetch" in (by_ticker["BADFETCH"][1] or "").lower()
    assert by_ticker["AAPL"][0] in ("aplus", "watch", "skip")

    run = conn.execute("SELECT excluded_count, error_count FROM evaluation_runs").fetchone()
    assert run[0] == 1
    assert run[1] == 1
    conn.close()
