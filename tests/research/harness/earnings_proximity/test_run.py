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
import pytest


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
    from research.harness.earnings_proximity.fetchers import FetchStats

    all_tickers = {"AAPL", "SOFI", "SPY"}
    frames = {t: _synth_ohlcv() for t in all_tickers}

    def fake_load_ohlcv_with_stats(tickers, *, start, end, cache_dir):
        data = {t: frames[t] for t in tickers if t in all_tickers}
        # All hits in this hermetic test (we don't actually round-trip to
        # disk; reporting them as hits is the closest analogue).
        return data, FetchStats(hits=tuple(data.keys()), misses=())

    def fake_load_earnings_with_stats(tickers, *, cache_dir, cache_max_age_hours: int = 24):
        # SOFI has one upcoming earnings near the middle of the replay window;
        # AAPL has none (forces the absent/no-upcoming branches).
        data = {t: ([date(2026, 4, 10)] if t == "SOFI" else []) for t in tickers}
        return data, FetchStats(hits=tuple(data.keys()), misses=())

    monkeypatch.setattr(run.fetchers, "load_ohlcv_with_stats", fake_load_ohlcv_with_stats)
    monkeypatch.setattr(run.fetchers, "load_earnings_with_stats", fake_load_earnings_with_stats)

    # --- Mock evaluate_one so we don't depend on OHLCV hitting A+. ---
    monkeypatch.setattr(
        replay,
        "evaluate_one",
        lambda ctx: _aplus_candidate(ctx.ticker),
    )

    output_dir = tmp_path / "smoke-out"
    cache_dir = tmp_path / "cache"
    # Synthetic 3-ticker universe (AAPL, SOFI, SPY) so the test is hermetic
    # — independent of the operator's reference/rs-universe.csv content.
    universe_csv = tmp_path / "test-universe.csv"
    universe_csv.write_text("# version: test-universe-v1\nticker\nAAPL\nSOFI\nSPY\n")

    rows = run.run_replay(
        tickers=["AAPL", "SOFI"],
        window_days=5,
        variant_list=[0, 3, 5, 7, 10],
        output_dir=output_dir,
        cache_dir=cache_dir,
        end_date=date(2026, 4, 3),  # Fri — a real NYSE session
        universe_csv=universe_csv,
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
    # Universe is now the loaded CSV, not the smoke filter — 3 tickers
    # (AAPL, SOFI, SPY) per the synthetic universe seeded above.
    assert manifest["tickers"] == 3
    assert manifest["variants"] == [0, 3, 5, 7, 10]
    # universe_version_hash reflects the CSV file, not the smoke ticker set.
    assert len(manifest["universe_version_hash"]) == 64  # SHA-256 hex
    # cache_stats: fetchers report all-hit since the test seeds the in-memory
    # frames directly. The stats schema is plumbed through correctly.
    assert manifest["cache_stats"]["ohlcv_hits"] == 3   # AAPL, SOFI, SPY
    assert manifest["cache_stats"]["ohlcv_misses"] == 0
    assert manifest["cache_stats"]["earnings_hits"] == 2  # AAPL, SOFI (no SPY)
    assert manifest["cache_stats"]["earnings_misses"] == 0
    # dropped_signal_count is run-level (not multiplied across variants).
    # Bound: <= total signals emitted before variant filtering. With 5
    # variants this would be 5x signals if the bug from adversarial review
    # were still present.
    signals_total = int(manifest["notes"][1].split(": ")[-1])
    assert manifest["dropped_signal_count"] <= signals_total


def test_run_replay_raises_when_universe_csv_missing(tmp_path, monkeypatch):
    """Fix for adversarial-review Round 2 issue 2: a missing universe CSV
    must NOT silently fall back to smoke-tickers-as-universe. Operator must
    pass --universe-csv explicitly or fix the default path."""
    from research.harness.earnings_proximity import run

    nonexistent = tmp_path / "does-not-exist.csv"

    with pytest.raises(FileNotFoundError, match="RS universe CSV not found"):
        run.run_replay(
            tickers=["AAPL"],
            window_days=5,
            variant_list=[0],
            output_dir=tmp_path / "out",
            cache_dir=tmp_path / "cache",
            end_date=date(2026, 4, 3),
            universe_csv=nonexistent,
        )


def test_run_replay_warns_on_smoke_ticker_outside_universe(tmp_path, monkeypatch):
    """Fix for adversarial-review Round 2 minor 1: a --tickers value not in
    the universe is silently ignored by replay (which iterates universe).
    Soft-warn the operator and record in manifest notes."""
    import warnings as warnings_mod

    from research.harness.earnings_proximity import replay, run
    from research.harness.earnings_proximity.fetchers import FetchStats

    universe_csv = tmp_path / "small-universe.csv"
    universe_csv.write_text("# version: tiny-v1\nticker\nAAPL\nSPY\n")  # NO MSFT

    frames = {t: _synth_ohlcv() for t in ("AAPL", "MSFT", "SPY")}

    def fake_load_ohlcv_with_stats(tickers, *, start, end, cache_dir):
        data = {t: frames[t] for t in tickers if t in frames}
        return data, FetchStats(hits=tuple(data.keys()), misses=())

    def fake_load_earnings_with_stats(tickers, *, cache_dir, cache_max_age_hours: int = 24):
        data = {t: [] for t in tickers}
        return data, FetchStats(hits=tuple(data.keys()), misses=())

    monkeypatch.setattr(run.fetchers, "load_ohlcv_with_stats", fake_load_ohlcv_with_stats)
    monkeypatch.setattr(run.fetchers, "load_earnings_with_stats", fake_load_earnings_with_stats)
    monkeypatch.setattr(replay, "evaluate_one", lambda ctx: _aplus_candidate(ctx.ticker))

    with warnings_mod.catch_warnings(record=True) as captured:
        warnings_mod.simplefilter("always")
        run.run_replay(
            tickers=["AAPL", "MSFT"],  # MSFT not in the small universe
            window_days=5,
            variant_list=[0],
            output_dir=tmp_path / "out",
            cache_dir=tmp_path / "cache",
            end_date=date(2026, 4, 3),
            universe_csv=universe_csv,
        )

    msgs = [str(w.message) for w in captured]
    assert any("MSFT" in m and "not in RS universe" in m for m in msgs), (
        f"expected out-of-universe warning, got: {msgs}"
    )

    manifest = json.loads((tmp_path / "out" / "run_manifest.json").read_text())
    assert any("MSFT" in n for n in manifest["notes"])


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
