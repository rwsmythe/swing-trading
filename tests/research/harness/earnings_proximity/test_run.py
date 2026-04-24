"""End-to-end smoke test for the CLI orchestration.

Verifies the run.py pipeline wires together fetchers → replay → variants
→ simulator → metrics → manifest WITHOUT touching the network. The actual
live smoke invocation (producing artifacts under research/harness/
earnings_proximity/smoke-out/) is a separate CLI command documented in
README.md; this test exercises the same orchestration with mocked fetchers.
"""
from __future__ import annotations

import csv
import json
from datetime import date

import pandas as pd


def _synth_ohlcv(start: str = "2024-01-02", periods: int = 400) -> pd.DataFrame:
    """Realistic-ish trending frame — not used for A+ classification here
    (we mock evaluate_one) but supplies OHLCV bars the simulator can walk."""
    idx = pd.date_range(start, periods=periods, freq="B")
    closes = [100.0 + i * 0.05 for i in range(periods)]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 0.5 for c in closes],
            "Low": [c - 0.5 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * periods,
        },
        index=idx,
    )


def _aplus_candidate(ticker):
    from swing.data.models import Candidate

    return Candidate(
        ticker=ticker,
        bucket="aplus",
        close=109.5,
        pivot=110.0,
        initial_stop=100.0,
        adr_pct=4.5,
        tight_streak=3,
        pullback_pct=15.0,
        prior_trend_pct=30.0,
        rs_rank=80,
        rs_return_12w_vs_spy=0.15,
        rs_method="universe",
        pattern_tag=None,
        notes=None,
        criteria=(),
    )


def test_run_replay_end_to_end_produces_metrics_and_manifest(tmp_path, monkeypatch):
    """Drive run.run_replay with mocked fetchers; assert both output files
    exist, metrics.csv has one row per variant, and values are plausible."""
    from research.harness.earnings_proximity import replay, run

    # --- Mock fetchers so no yfinance traffic happens. ---
    all_tickers = {"AAPL", "SOFI", "SPY"}
    frames = {t: _synth_ohlcv() for t in all_tickers}

    def fake_load_ohlcv(tickers, *, start, end, cache_dir):
        return {t: frames[t] for t in tickers if t in all_tickers}

    def fake_load_earnings(tickers, *, cache_dir, cache_max_age_hours: int = 24):
        # SOFI has one upcoming earnings near the middle of the replay window;
        # AAPL has none (forces the absent/no-upcoming branches).
        return {t: ([date(2026, 4, 10)] if t == "SOFI" else []) for t in tickers}

    monkeypatch.setattr(run.fetchers, "load_ohlcv", fake_load_ohlcv)
    monkeypatch.setattr(run.fetchers, "load_earnings", fake_load_earnings)

    # --- Mock evaluate_one so we don't depend on OHLCV hitting A+. ---
    monkeypatch.setattr(
        replay,
        "evaluate_one",
        lambda ctx: _aplus_candidate(ctx.ticker),
    )

    output_dir = tmp_path / "smoke-out"
    cache_dir = tmp_path / "cache"

    rows = run.run_replay(
        tickers=["AAPL", "SOFI"],
        window_days=5,
        variant_list=[0, 3, 5, 7, 10],
        output_dir=output_dir,
        cache_dir=cache_dir,
        end_date=date(2026, 4, 3),  # Fri — a real NYSE session
    )

    # --- Five variants emitted. ---
    assert len(rows) == 5
    assert [r.variant_name for r in rows] == ["X=0", "X=3", "X=5", "X=7", "X=10"]
    assert [r.blackout_trading_days for r in rows] == [0, 3, 5, 7, 10]

    # --- Plausibility checks on the aggregated row. ---
    for r in rows:
        assert r.signal_count >= 0
        assert r.traded_count >= 0
        assert r.dropped_count >= 0
        assert 0.0 <= r.gap_through_rate <= 1.0
        # Expectancy is a finite float.
        assert r.expectancy_r == r.expectancy_r  # not NaN
        assert abs(r.expectancy_r) < 1e9  # finite

    # Monotone signal_count across increasing X is NOT strictly guaranteed
    # by the harness for AAPL (absent_data=True so never filtered) — what we
    # CAN assert is that at X=0 no signals are dropped by the variant filter.
    assert rows[0].signal_count == rows[0].traded_count + rows[0].dropped_count

    # --- Outputs on disk. ---
    metrics_path = output_dir / "metrics.csv"
    manifest_path = output_dir / "run_manifest.json"
    assert metrics_path.exists()
    assert manifest_path.exists()

    with metrics_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        lines = list(reader)
    assert len(lines) == 5
    assert {line["variant_name"] for line in lines} == {"X=0", "X=3", "X=5", "X=7", "X=10"}

    manifest = json.loads(manifest_path.read_text())
    for required in (
        "git_sha", "git_dirty", "run_ts", "yfinance_version",
        "universe_version_hash", "window_start", "window_end",
        "trading_days", "tickers", "variants",
        "cache_stats", "absent_data_count", "dropped_signal_count",
        "study_design_commit",
    ):
        assert required in manifest, f"manifest missing {required}"
    assert manifest["trading_days"] == 5
    assert manifest["tickers"] == 2
    assert manifest["variants"] == [0, 3, 5, 7, 10]


def test_parse_args_accepts_smoke_invocation():
    """Smoke command line invocation from the README parses into expected args."""
    from research.harness.earnings_proximity import run

    args = run._parse_args([
        "--tickers", "AAPL,SOFI",
        "--window-days", "10",
        "--variants", "0,3,5,7,10",
        "--output-dir", "out",
    ])
    assert args.tickers == "AAPL,SOFI"
    assert args.window_days == 10
    assert args.variants == "0,3,5,7,10"
    assert args.output_dir == "out"
