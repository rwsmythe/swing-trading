"""Tests for the S&P 1500 D4 findings aggregator.

Covers sector breakdown counting, liquidity-distribution computation
from cached OHLCV, and the Wilson-95 % CI / rate-uplift derivation.
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from research.harness.earnings_proximity.scripts import sp1500_findings_aggregate as agg


def _write_aplus_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "ticker",
                "date",
                "entry_target",
                "initial_stop",
                "next_earnings_date",
                "absent_earnings_data",
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _write_ohlcv_parquet(cache_dir: Path, ticker: str, *, end: date, n_bars: int = 25) -> None:
    """Write a parquet with ``n_bars`` business days ending strictly before ``end``.

    Volume rises across bars so per-row dollar-volume varies, letting tests
    distinguish median/p25/p75 plausibly.
    """
    idx = pd.bdate_range(end=pd.Timestamp(end) - pd.Timedelta(days=1), periods=n_bars)
    bars = len(idx)
    closes = [10.0 + i * 0.5 for i in range(bars)]
    volumes = [100_000 * (i + 1) for i in range(bars)]
    df = pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 0.5 for c in closes],
            "Low": [c - 0.5 for c in closes],
            "Close": closes,
            "Volume": volumes,
        },
        index=idx,
    )
    out = cache_dir / "ohlcv" / f"{ticker.upper()}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)


def test_sector_breakdown_counts_and_concentration(tmp_path: Path):
    aplus = [
        {"ticker": "AAPL", "date": "2025-06-02", "entry_target": "100", "initial_stop": "90",
         "next_earnings_date": "", "absent_earnings_data": "0"},
        {"ticker": "MSFT", "date": "2025-06-03", "entry_target": "100", "initial_stop": "90",
         "next_earnings_date": "", "absent_earnings_data": "0"},
        {"ticker": "JPM", "date": "2025-06-04", "entry_target": "100", "initial_stop": "90",
         "next_earnings_date": "", "absent_earnings_data": "1"},
    ]
    sector_map = {"AAPL": "Information Technology", "MSFT": "Information Technology", "JPM": "Financials"}
    out = agg.compute_sector_breakdown(aplus, sector_map)
    assert out["total_aplus"] == 3
    assert out["largest_sector"] == "Information Technology"
    assert out["largest_sector_fraction"] == 2 / 3
    sectors = {b["sector"]: b for b in out["by_sector"]}
    assert sectors["Information Technology"]["count"] == 2
    assert sectors["Financials"]["count"] == 1


def test_sector_breakdown_with_universe_computes_index_ratios(tmp_path: Path):
    """When universe_tickers is provided, per-sector index_ratio surfaces over/under-indexing."""
    aplus = [
        {"ticker": "AAPL", "date": "2025-06-02", "entry_target": "100", "initial_stop": "90",
         "next_earnings_date": "", "absent_earnings_data": "0"},
        {"ticker": "MSFT", "date": "2025-06-03", "entry_target": "100", "initial_stop": "90",
         "next_earnings_date": "", "absent_earnings_data": "0"},
    ]
    # Universe: 4 IT tickers, 4 Financials, 2 Health Care.
    universe = ["AAPL", "MSFT", "NVDA", "ORCL", "JPM", "BAC", "C", "GS", "PFE", "JNJ"]
    sector_map = {
        "AAPL": "Information Technology", "MSFT": "Information Technology",
        "NVDA": "Information Technology", "ORCL": "Information Technology",
        "JPM": "Financials", "BAC": "Financials", "C": "Financials", "GS": "Financials",
        "PFE": "Health Care", "JNJ": "Health Care",
    }
    out = agg.compute_sector_breakdown(aplus, sector_map, universe_tickers=universe)
    assert out["universe_total"] == 10
    sectors = {b["sector"]: b for b in out["by_sector"]}
    # IT: 2/2 A+ = 100%; 4/10 universe = 40%; index_ratio = 100%/40% = 2.5.
    assert sectors["Information Technology"]["index_ratio"] == pytest.approx(2.5)
    # Financials: 0 A+; 4/10 universe = 40%; index_ratio = 0/40% = 0.
    assert sectors["Financials"]["index_ratio"] == 0.0
    # Universe-only sectors still appear in breakdown.
    assert "Health Care" in sectors


def test_sector_breakdown_unknown_ticker_falls_through(tmp_path: Path):
    aplus = [
        {"ticker": "EXOTIC", "date": "2025-06-02", "entry_target": "100", "initial_stop": "90",
         "next_earnings_date": "", "absent_earnings_data": "0"},
    ]
    out = agg.compute_sector_breakdown(aplus, {})
    assert out["largest_sector"] == "Unknown"
    assert out["by_sector"][0]["sector"] == "Unknown"


def test_liquidity_stats_uses_prior_20_bars(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    aplus_date = date(2025, 6, 2)
    _write_ohlcv_parquet(cache_dir, "AAA", end=aplus_date, n_bars=25)
    _write_ohlcv_parquet(cache_dir, "BBB", end=aplus_date, n_bars=25)
    aplus = [
        {"ticker": "AAA", "date": aplus_date.isoformat(), "entry_target": "100", "initial_stop": "90",
         "next_earnings_date": "", "absent_earnings_data": "0"},
        {"ticker": "BBB", "date": aplus_date.isoformat(), "entry_target": "100", "initial_stop": "90",
         "next_earnings_date": "", "absent_earnings_data": "0"},
    ]
    out = agg.compute_liquidity_stats(aplus, cache_dir)
    assert out["priced_count"] == 2
    assert out["unpriced_count"] == 0
    assert out["median"] is not None
    # Mean dollar vol for the 20-prior-bar window is positive and well above zero.
    assert out["median"] > 0


def test_liquidity_stats_records_unpriced(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    aplus_date = date(2025, 6, 2)
    aplus = [
        {"ticker": "MISSING", "date": aplus_date.isoformat(), "entry_target": "100", "initial_stop": "90",
         "next_earnings_date": "", "absent_earnings_data": "0"},
    ]
    out = agg.compute_liquidity_stats(aplus, cache_dir)
    assert out["priced_count"] == 0
    assert out["unpriced_count"] == 1
    assert out["unpriced_examples"][0]["ticker"] == "MISSING"
    assert out["unpriced_examples"][0]["reason"] == "no cache file"


def test_aggregate_findings_writes_full_report(tmp_path: Path):
    run_dir = tmp_path / "run"
    cache_dir = tmp_path / "cache"
    aplus_date = date(2025, 6, 2)
    _write_aplus_csv(
        run_dir / "aplus_signals.csv",
        [
            {"ticker": "AAA", "date": aplus_date.isoformat(), "entry_target": "100", "initial_stop": "90",
             "next_earnings_date": "", "absent_earnings_data": "0"},
            {"ticker": "BBB", "date": aplus_date.isoformat(), "entry_target": "100", "initial_stop": "90",
             "next_earnings_date": "", "absent_earnings_data": "1"},
        ],
    )
    _write_manifest(
        run_dir / "run_manifest.json",
        {
            "git_sha": "deadbeef",
            "universe_size": 1500,
            "universe_fetched_date": "2026-04-25",
            "trading_days": 504,
            "evaluations_total": 700_000,
            "ticker_days_total": 756_000,
            "ohlcv_hits": 1490,
            "ohlcv_misses": 10,
            "earnings_hits": 1450,
            "earnings_misses": 50,
        },
    )
    _write_ohlcv_parquet(cache_dir, "AAA", end=aplus_date, n_bars=25)
    _write_ohlcv_parquet(cache_dir, "BBB", end=aplus_date, n_bars=25)

    findings = agg.aggregate_findings(
        run_dir,
        cache_dir=cache_dir,
        sector_map={"AAA": "Information Technology", "BBB": "Financials"},
    )
    assert findings["aplus_total"] == 2
    assert findings["universe_size_post_dedupe"] == 1500
    # 2 / (1500 * 504) = 2.6455e-6 → 0.00026455 %
    assert findings["rate_per_ticker_day_pct"] > 0
    assert findings["rate_uplift_vs_spx_ndx_1x"] > 0
    # Wilson CI must include the point estimate.
    assert findings["wilson_95ci_low_pct"] <= findings["rate_per_ticker_day_pct"] <= findings["wilson_95ci_high_pct"]
    assert findings["data_quality"]["aplus_absent_earnings_fraction"] == 0.5
    assert findings["sector_breakdown"]["total_aplus"] == 2
    assert findings["liquidity"]["priced_count"] == 2


def test_aggregate_findings_pins_sector_map_to_manifest_fetch_date(tmp_path: Path):
    """When sector_map is None, aggregator must load the file matching universe_fetched_date.

    A different-dated sector map present in the cache MUST NOT be used —
    the aggregator pins to the manifest's date and errors if the file is
    missing rather than silently substituting.
    """
    run_dir = tmp_path / "run"
    cache_dir = tmp_path / "cache"
    aplus_date = date(2025, 6, 2)
    _write_aplus_csv(
        run_dir / "aplus_signals.csv",
        [
            {"ticker": "AAA", "date": aplus_date.isoformat(), "entry_target": "100", "initial_stop": "90",
             "next_earnings_date": "", "absent_earnings_data": "0"},
        ],
    )
    _write_manifest(
        run_dir / "run_manifest.json",
        {
            "git_sha": "deadbeef",
            "universe_size": 1,
            "universe_fetched_date": "2026-04-25",
            "trading_days": 1,
            "evaluations_total": 1,
            "ticker_days_total": 1,
            "ohlcv_hits": 1,
            "ohlcv_misses": 0,
            "earnings_hits": 1,
            "earnings_misses": 0,
        },
    )
    _write_ohlcv_parquet(cache_dir, "AAA", end=aplus_date, n_bars=25)

    # Write the WRONG-dated sector map; pinned-by-date loader must fail.
    snaps = cache_dir / "universe-snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    (snaps / "sp_1500_2026-04-30_sectors.json").write_text(
        json.dumps({"AAA": "Drift"}), encoding="utf-8"
    )

    with pytest.raises(FileNotFoundError, match="Pinned sector map not found"):
        agg.aggregate_findings(run_dir, cache_dir=cache_dir)

    # Now write the right-dated map; aggregator must succeed and use it.
    (snaps / "sp_1500_2026-04-25_sectors.json").write_text(
        json.dumps({"AAA": "Information Technology"}), encoding="utf-8"
    )
    # Also write a same-dated snapshot CSV so universe_tickers loads.
    (snaps / "sp_1500_2026-04-25.csv").write_text(
        "# fetched: 2026-04-25\nticker,source_url\nAAA,http://example\n",
        encoding="utf-8",
    )
    findings = agg.aggregate_findings(run_dir, cache_dir=cache_dir)
    sectors = {b["sector"]: b for b in findings["sector_breakdown"]["by_sector"]}
    assert "Information Technology" in sectors
    assert "Drift" not in sectors
