"""End-to-end smoke test for the parity-comparator CLI.

Uses an in-memory schema-applied SQLite DB pre-populated with one
evaluation_run + a small candidate set, plus a monkeypatched PriceFetcher
that returns canned OHLCV. Asserts that ``run_parity`` writes:

- ``parity_table.csv`` (one row per ticker; expected columns).
- ``summary.csv`` (single-row aggregate + tier).
- ``run_manifest.json`` (provenance).

No real production data needed; D3 covers that.
"""
from __future__ import annotations

import csv
import json

import pandas as pd
import pytest

from research.parity.run import run_parity
from swing.data.db import ensure_schema
from swing.data.models import Candidate, CriterionResult, EvaluationRun
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.evaluation.rs import universe_version_hash


def _crit(name: str, layer: str, result: str = "pass") -> CriterionResult:
    return CriterionResult(criterion_name=name, layer=layer, result=result)


def _full_pass_criteria() -> tuple[CriterionResult, ...]:
    return (
        _crit("TT1_above_150_200", "trend_template", "pass"),
        _crit("TT2_150_above_200", "trend_template", "pass"),
        _crit("TT3_200_rising", "trend_template", "pass"),
        _crit("TT4_50_above_150_200", "trend_template", "pass"),
        _crit("TT5_above_50", "trend_template", "pass"),
        _crit("TT6_above_52w_low_30pct", "trend_template", "pass"),
        _crit("TT7_within_52w_high_25pct", "trend_template", "pass"),
        _crit("TT8_rs_rank", "trend_template", "pass"),
        _crit("prior_trend", "vcp", "pass"),
        _crit("ma_stack_10_20_50", "vcp", "pass"),
        _crit("ma_short_rising", "vcp", "pass"),
        _crit("proximity_20ma", "vcp", "pass"),
        _crit("adr", "vcp", "pass"),
        _crit("pullback", "vcp", "pass"),
        _crit("tightness", "vcp", "pass"),
        _crit("vcp_volume_contraction", "vcp", "pass"),
        _crit("orderliness", "vcp", "pass"),
        _crit("risk_feasibility", "risk", "pass"),
    )


def _candidate(ticker: str, *, bucket: str, criteria: tuple) -> Candidate:
    return Candidate(
        ticker=ticker, bucket=bucket, close=100.0, pivot=110.0, initial_stop=95.0,
        adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
        pattern_tag=None, notes=None, criteria=criteria,
    )


def _make_ohlcv(start: str, n_bars: int, base: float = 100.0) -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=n_bars)
    return pd.DataFrame({
        "Open": [base + i * 0.05 for i in range(n_bars)],
        "High": [base + i * 0.05 + 0.5 for i in range(n_bars)],
        "Low": [base + i * 0.05 - 0.5 for i in range(n_bars)],
        "Close": [base + i * 0.05 for i in range(n_bars)],
        "Volume": [1_000_000] * n_bars,
    }, index=idx)


class _MockFetcher:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []
        self.hits = 0
        self.misses = 0

    def get(self, ticker, lookback_days, *, as_of_date=None):
        self.requests.append((ticker, lookback_days))
        prior = sum(1 for t, _ in self.requests[:-1] if t == ticker)
        df = self.responses.get(ticker)
        if df is None:
            raise ValueError(f"No data for {ticker}")
        if prior > 0:
            self.hits += 1
        else:
            self.misses += 1
        return df


@pytest.fixture
def parity_setup(tmp_path):
    """Schema-applied DB + tiny rs-universe + a Config + Finviz CSV."""
    universe_csv = tmp_path / "rs-universe.csv"
    universe_csv.write_text(
        "# version: 2026-04-24-test\nticker\nAAPL\nMSFT\nNVDA\n",
        encoding="utf-8",
    )
    finviz_csv = tmp_path / "finviz_test.csv"
    finviz_csv.write_text(
        "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
        "1,AAPL,Tech,Hardware,USA,100,1,1000000,1.0,2.0,150,80,3000B\n"
        "2,MSFT,Tech,Software,USA,200,1,1000000,1.0,2.0,250,150,2000B\n",
        encoding="utf-8",
    )
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(f"""[paths]
db_path = "{(tmp_path / 'swing.db').as_posix()}"
data_dir = "{tmp_path.as_posix()}"
logs_dir = "{tmp_path.as_posix()}"
charts_dir = "{tmp_path.as_posix()}"
backups_dir = "{tmp_path.as_posix()}"
prices_cache_dir = "{tmp_path.as_posix()}"
finviz_inbox_dir = "{tmp_path.as_posix()}"
exports_dir = "{tmp_path.as_posix()}"
rs_universe_path = "{universe_csv.as_posix()}"

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
allowed_miss_names = ["TT8_rs_rank"]
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
""", encoding="utf-8")

    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)

    real_universe_hash = universe_version_hash(universe_csv)
    run_id = insert_evaluation_run(conn, EvaluationRun(
        id=None, run_ts="2026-04-24T21:00:00",
        data_asof_date="2026-04-24", action_session_date="2026-04-25",
        finviz_csv_path=str(finviz_csv),
        tickers_evaluated=2, aplus_count=0, watch_count=1, skip_count=1,
        excluded_count=0, error_count=0,
        rs_universe_version="2026-04-24-test",
        rs_universe_hash=real_universe_hash,
    ))
    insert_candidates(conn, run_id, [
        _candidate("AAPL", bucket="watch", criteria=_full_pass_criteria()),
        _candidate("MSFT", bucket="skip", criteria=_full_pass_criteria()),
    ])
    conn.commit()
    conn.close()

    return {
        "db_path": db_path,
        "cfg_path": cfg_path,
        "universe_csv": universe_csv,
        "finviz_csv": finviz_csv,
        "run_id": run_id,
        "tmp_path": tmp_path,
    }


def test_run_parity_writes_expected_artifacts(parity_setup):
    s = parity_setup
    output_dir = s["tmp_path"] / "out"

    fetcher = _MockFetcher({
        "AAPL": _make_ohlcv("2025-04-01", 250, base=100.0),
        "MSFT": _make_ohlcv("2025-04-01", 250, base=200.0),
        "NVDA": _make_ohlcv("2025-04-01", 250, base=300.0),
        "SPY":  _make_ohlcv("2025-04-01", 250, base=400.0),
    })

    from swing.config import load
    cfg = load(s["cfg_path"])

    summary = run_parity(
        cfg=cfg, evaluation_run_id=s["run_id"], fetcher=fetcher,
        finviz_tickers=("AAPL", "MSFT"), output_dir=output_dir,
        harness_git_sha="testsha",
    )

    assert (output_dir / "parity_table.csv").exists()
    assert (output_dir / "summary.csv").exists()
    assert (output_dir / "run_manifest.json").exists()

    # parity_table.csv schema check.
    with (output_dir / "parity_table.csv").open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert set(reader.fieldnames) >= {
            "ticker", "prod_bucket", "harness_bucket", "bucket_match",
            "criterion_total_compared", "criterion_match_count",
            "criterion_disagreements_summary",
        }
        rows = list(reader)
    tickers_in_output = {r["ticker"] for r in rows}
    assert tickers_in_output == {"AAPL", "MSFT"}

    # summary.csv schema check.
    with (output_dir / "summary.csv").open(encoding="utf-8", newline="") as fh:
        srow = next(csv.DictReader(fh))
    assert int(srow["bucket_total"]) == 2
    assert int(srow["criterion_total"]) > 0
    assert srow["tier"] in {"1", "2", "3"}

    # run_manifest.json provenance.
    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["evaluation_run_id"] == s["run_id"]
    assert manifest["harness_git_sha"] == "testsha"
    assert "finviz_csv_path" in manifest
    assert "finviz_csv_sha256" in manifest
    assert "current_equity" in manifest
    assert "equity_derivation" in manifest
    assert "universe_version_recorded" in manifest
    assert "universe_hash_recorded" in manifest
    assert "universe_match_with_production" in manifest
    assert "tier" in manifest
    assert "bucket_agreement_rate" in manifest
    assert "criterion_agreement_rate" in manifest
    assert "skipped_tickers" in manifest

    # Programmatic return is the ParitySummary; tier ∈ {1,2,3}.
    assert summary.tier in {1, 2, 3}
    assert summary.bucket_total == 2


def test_run_parity_handles_universe_drift_without_failing(parity_setup, monkeypatch):
    s = parity_setup
    # Mutate the rs-universe to create a hash mismatch with what we
    # recorded on the eval row.
    s["universe_csv"].write_text(
        "# version: 2026-04-25-test\nticker\nAAPL\nMSFT\nNVDA\nGOOG\n",
        encoding="utf-8",
    )
    fetcher = _MockFetcher({
        "AAPL": _make_ohlcv("2025-04-01", 250, base=100.0),
        "MSFT": _make_ohlcv("2025-04-01", 250, base=200.0),
        "NVDA": _make_ohlcv("2025-04-01", 250, base=300.0),
        "GOOG": _make_ohlcv("2025-04-01", 250, base=500.0),
        "SPY":  _make_ohlcv("2025-04-01", 250, base=400.0),
    })
    from swing.config import load
    cfg = load(s["cfg_path"])
    output_dir = s["tmp_path"] / "out_drift"
    summary = run_parity(
        cfg=cfg, evaluation_run_id=s["run_id"], fetcher=fetcher,
        finviz_tickers=("AAPL", "MSFT"), output_dir=output_dir,
        harness_git_sha="testsha",
    )
    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["universe_match_with_production"] is False
    assert summary is not None
