"""Parity test: new evaluator matches legacy bucket assignments except for documented diffs.

Purpose: mechanical regression safety net during the rewrite. Marked `slow` — hits yfinance
on first run and takes several minutes per fixture. Fast default test runs skip this.

Parity is best-effort, not bit-for-bit: yfinance's view of historical bars can change over
time (splits, corrections, ticker remappings). Unexplained divergences may be real bugs OR
vendor drift — tag ambiguous ones as `"vendor_drift"` in expected-diffs.yaml.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from swing.cli import main as cli_main

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
BASELINE = FIXTURE_DIR / "parity-baseline.json"
DIFFS = FIXTURE_DIR / "finviz" / "expected-diffs.yaml"

_FN_RE = re.compile(
    r"^finviz(?P<day>\d{1,2})(?P<month>[A-Za-z]{3})(?P<year>\d{4})", re.IGNORECASE
)
_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _data_asof_from_filename(csv_name: str) -> str | None:
    m = _FN_RE.match(csv_name)
    if not m:
        return None
    return f"{m.group('year')}-{_MONTHS[m.group('month').lower()]}-{int(m.group('day')):02d}"


def _load_baseline() -> dict[str, dict[str, str]]:
    if not BASELINE.exists():
        pytest.skip("parity-baseline.json not captured yet")
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _load_diffs() -> dict[str, dict[str, str]]:
    if not DIFFS.exists():
        return {}
    data = yaml.safe_load(DIFFS.read_text(encoding="utf-8")) or {}
    return data


def _run_new_evaluator_on_csv(
    csv_path: Path, tmp_path: Path
) -> dict[str, str]:
    """Run CLI with a temp DB + frozen universe snapshot; return {ticker: bucket}."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    frozen_universe = FIXTURE_DIR / "rs-universe-at-baseline.csv"
    assert frozen_universe.exists(), (
        "Parity tests require tests/fixtures/rs-universe-at-baseline.csv. "
        "Snapshot it during Task 28 before running parity."
    )

    cfg_override = project_dir / "swing.config.toml"
    cfg_override.write_text(
        f"""[paths]
db_path = "{(tmp_path / "swing.db").as_posix()}"
data_dir = "{tmp_path.as_posix()}"
logs_dir = "{(tmp_path / "logs").as_posix()}"
charts_dir = "{(tmp_path / "charts").as_posix()}"
backups_dir = "{(tmp_path / "backups").as_posix()}"
prices_cache_dir = "{(tmp_path / "cache").as_posix()}"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "{frozen_universe.as_posix()}"

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

    runner = CliRunner()
    r1 = runner.invoke(cli_main, ["--config", str(cfg_override), "db-migrate"])
    assert r1.exit_code == 0, r1.output

    data_asof = _data_asof_from_filename(csv_path.name)
    eval_args = ["--config", str(cfg_override), "eval", "--csv", str(csv_path)]
    if data_asof:
        eval_args += ["--as-of-date", data_asof]
    r2 = runner.invoke(cli_main, eval_args)
    assert r2.exit_code == 0, r2.output

    conn = sqlite3.connect(tmp_path / "swing.db")
    rows = conn.execute("SELECT ticker, bucket FROM candidates").fetchall()
    conn.close()
    return {t.upper(): b.lower() for (t, b) in rows}


@pytest.mark.slow
@pytest.mark.parametrize(
    "csv_name",
    [f.name for f in sorted((FIXTURE_DIR / "finviz").glob("finviz*.csv"))],
)
def test_parity_per_ticker(csv_name: str, tmp_path: Path):
    baseline = _load_baseline().get(csv_name, {})
    if not baseline:
        pytest.skip(f"No baseline for {csv_name}")

    diffs = _load_diffs().get(csv_name, {})
    actual = _run_new_evaluator_on_csv(FIXTURE_DIR / "finviz" / csv_name, tmp_path)

    unexplained: list[tuple[str, str, str]] = []
    for ticker, legacy_bucket in baseline.items():
        new_bucket = actual.get(ticker, "missing")
        if new_bucket != legacy_bucket and ticker not in diffs:
            unexplained.append((ticker, legacy_bucket, new_bucket))

    if unexplained:
        # Auto-write suggested diffs for the operator to review + merge
        suggested_path = FIXTURE_DIR / "finviz" / f"suggested-diffs-{csv_name}.yaml"
        conn = sqlite3.connect(tmp_path / "swing.db")
        suggestions: dict[str, str] = {}
        for ticker, legacy, new in unexplained:
            rows = conn.execute(
                """
                SELECT cc.criterion_name FROM candidates c
                JOIN candidate_criteria cc ON cc.candidate_id = c.id
                WHERE c.ticker = ? AND cc.result IN ('fail', 'na')
                """,
                (ticker,),
            ).fetchall()
            failed = [r[0] for r in rows]
            suggestions[ticker] = (
                f"legacy={legacy} new={new}; failing criteria: "
                f"{', '.join(failed) if failed else 'none'}"
            )
        conn.close()
        suggested_path.write_text(
            yaml.safe_dump({csv_name: suggestions}), encoding="utf-8"
        )
        msg = "\n".join(f"  {t}: legacy={lb}, new={nb}" for t, lb, nb in unexplained)
        pytest.fail(
            f"Unexplained divergences in {csv_name}:\n{msg}\n"
            f"Suggestions written to {suggested_path.name}. "
            f"Review and merge into expected-diffs.yaml with a human reason per entry."
        )
