"""Tests for the diagnostic-run driver.

The driver wires:
    universe-variants loader → fetchers → instrumented_replay →
    per-criterion aggregation → CSV + manifest output

with:
    - ``--universe`` selecting the universe variant.
    - ``--capital-multiplier`` scaling the harness ``current_equity`` value.
    - ``--base-capital`` overriding the operator-config-derived baseline.

Tests use monkey-patched fetchers + a stub ``evaluate_one`` so they run
hermetically (no yfinance traffic, no real iShares CSV download).
"""
from __future__ import annotations

import csv
import json
from datetime import date

import pandas as pd
import pytest

from research.harness.earnings_proximity.fetchers import FetchStats
from research.harness.earnings_proximity.scripts import diagnostic_run
from swing.data.models import Candidate, CriterionResult


def _ohlcv(start: str = "2024-01-02", periods: int = 400) -> pd.DataFrame:
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


def _crit(name: str, layer: str, result: str = "pass") -> CriterionResult:
    return CriterionResult(criterion_name=name, layer=layer, result=result)


def _all_pass_criteria() -> tuple[CriterionResult, ...]:
    tt = (
        "TT1_close_above_ma200",
        "TT2_ma150_above_ma200",
        "TT3_ma200_rising",
        "TT4_ma50_above_ma150",
        "TT5_close_above_ma50",
        "TT6_close_high_52w_margin",
        "TT7_close_low_52w_min",
        "TT8_rs_rank",
    )
    vcp = (
        "prior_trend",
        "ma_stack_short",
        "rising_ma_short",
        "proximity",
        "adr",
        "pullback",
        "tightness",
        "vcp",
        "orderliness",
    )
    return (
        *(_crit(n, "trend_template") for n in tt),
        *(_crit(n, "vcp") for n in vcp),
        _crit("risk_feasibility", "risk"),
    )


def _aplus_candidate(ticker: str) -> Candidate:
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
        criteria=_all_pass_criteria(),
    )


def _risk_failing_candidate(ticker: str) -> Candidate:
    crits = list(_all_pass_criteria())
    crits[-1] = _crit("risk_feasibility", "risk", "fail")
    return Candidate(
        ticker=ticker,
        bucket="skip",
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
        criteria=tuple(crits),
    )


# ----------------------------------------------------------------------------
# Operator capital baseline
# ----------------------------------------------------------------------------


def test_operator_sizing_equity_uses_floor_when_starting_below(tmp_path):
    """sizing_equity = max(starting_equity, risk_equity_floor) — production
    `swing.trades.equity.sizing_equity` matches this rule."""
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(_minimal_config_toml(starting_equity=1200.0, floor=7500.0))
    assert diagnostic_run.operator_sizing_equity(cfg_path) == 7500.0


def test_operator_sizing_equity_uses_starting_when_above_floor(tmp_path):
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(_minimal_config_toml(starting_equity=50_000.0, floor=7500.0))
    assert diagnostic_run.operator_sizing_equity(cfg_path) == 50_000.0


# ----------------------------------------------------------------------------
# Capital-multiplier propagation
# ----------------------------------------------------------------------------


def test_capital_multiplier_scales_current_equity(monkeypatch, tmp_path):
    observed_equities: list[float] = []

    def fake_evaluate_one(ctx):
        observed_equities.append(ctx.current_equity)
        return _aplus_candidate(ctx.ticker)

    _patch_fetchers(monkeypatch)
    monkeypatch.setattr(
        "research.harness.earnings_proximity.instrumented_replay.evaluate_one",
        fake_evaluate_one,
    )

    diagnostic_run.run_diagnostic(
        universe_variant=_stub_universe(["AAPL"]),
        base_capital=10_000.0,
        capital_multiplier=5.0,
        window_start=date(2025, 6, 2),
        window_end=date(2025, 6, 3),
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
    )
    assert observed_equities  # At least one evaluator call
    assert all(e == pytest.approx(50_000.0) for e in observed_equities)


def test_default_capital_multiplier_is_one(monkeypatch, tmp_path):
    observed_equities: list[float] = []

    def fake_evaluate_one(ctx):
        observed_equities.append(ctx.current_equity)
        return _aplus_candidate(ctx.ticker)

    _patch_fetchers(monkeypatch)
    monkeypatch.setattr(
        "research.harness.earnings_proximity.instrumented_replay.evaluate_one",
        fake_evaluate_one,
    )

    diagnostic_run.run_diagnostic(
        universe_variant=_stub_universe(["AAPL"]),
        base_capital=7500.0,
        capital_multiplier=1.0,
        window_start=date(2025, 6, 2),
        window_end=date(2025, 6, 3),
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
    )
    assert all(e == pytest.approx(7500.0) for e in observed_equities)


# ----------------------------------------------------------------------------
# Output files
# ----------------------------------------------------------------------------


def test_diagnostic_run_writes_expected_outputs(monkeypatch, tmp_path):
    """End-to-end: diagnostic_run produces 4 output files with expected schemas."""
    def fake_evaluate_one(ctx):
        if ctx.ticker == "AAPL":
            return _aplus_candidate(ctx.ticker)
        return _risk_failing_candidate(ctx.ticker)

    _patch_fetchers(monkeypatch, frames=("AAPL", "MSFT"))
    monkeypatch.setattr(
        "research.harness.earnings_proximity.instrumented_replay.evaluate_one",
        fake_evaluate_one,
    )

    universe = _stub_universe(["AAPL", "MSFT"])
    output_dir = tmp_path / "out"
    diagnostic_run.run_diagnostic(
        universe_variant=universe,
        base_capital=7500.0,
        capital_multiplier=1.0,
        window_start=date(2025, 6, 2),
        window_end=date(2025, 6, 6),
        output_dir=output_dir,
        cache_dir=tmp_path / "cache",
    )

    assert (output_dir / "evaluations.csv").exists()
    assert (output_dir / "aplus_signals.csv").exists()
    assert (output_dir / "binding_constraints.csv").exists()
    assert (output_dir / "run_manifest.json").exists()

    # Aplus signals: only AAPL, one per trading day.
    with (output_dir / "aplus_signals.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert all(r["ticker"] == "AAPL" for r in rows)
    assert len(rows) >= 1

    # Binding constraints: AAPL → A+ (under <aplus> sentinel), MSFT → risk_feasibility.
    with (output_dir / "binding_constraints.csv").open() as fh:
        cb = {row["criterion"]: int(row["count"]) for row in csv.DictReader(fh)}
    assert cb.get("risk_feasibility", 0) >= 1
    assert cb.get("<aplus>", 0) >= 1

    # Manifest: capital + multiplier + universe info.
    manifest = json.loads((output_dir / "run_manifest.json").read_text())
    assert manifest["base_capital"] == 7500.0
    assert manifest["capital_multiplier"] == 1.0
    assert manifest["effective_equity"] == 7500.0
    assert manifest["universe_name"] == "spx_ndx_stub"


def test_diagnostic_run_records_universe_provenance(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "research.harness.earnings_proximity.instrumented_replay.evaluate_one",
        lambda ctx: _aplus_candidate(ctx.ticker),
    )
    _patch_fetchers(monkeypatch, frames=("AAPL",))

    universe = _stub_universe(["AAPL"], name="russell_3000_test", source_url="https://example/x")
    output_dir = tmp_path / "out"
    diagnostic_run.run_diagnostic(
        universe_variant=universe,
        base_capital=10_000.0,
        capital_multiplier=1.0,
        window_start=date(2025, 6, 2),
        window_end=date(2025, 6, 3),
        output_dir=output_dir,
        cache_dir=tmp_path / "cache",
    )
    manifest = json.loads((output_dir / "run_manifest.json").read_text())
    assert manifest["universe_name"] == "russell_3000_test"
    assert manifest["universe_source_url"] == "https://example/x"


# ----------------------------------------------------------------------------
# CLI smoke
# ----------------------------------------------------------------------------


def test_cli_main_invokes_run_diagnostic(monkeypatch, tmp_path):
    """`main(['--universe', 'spx_ndx', ...])` parses args and dispatches."""
    captured: dict = {}

    def fake_run_diagnostic(**kwargs):
        captured.update(kwargs)
        # Touch the output dir so post-call assertions can verify it.
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        (kwargs["output_dir"] / "run_manifest.json").write_text("{}")

    monkeypatch.setattr(diagnostic_run, "run_diagnostic", fake_run_diagnostic)
    monkeypatch.setattr(
        diagnostic_run,
        "load_universe_variant_at",
        lambda name, cache_dir: _stub_universe(["AAPL"], name=name),
    )

    rc = diagnostic_run.main(
        [
            "--universe", "spx_ndx",
            "--capital-multiplier", "5.0",
            "--base-capital", "12345.0",
            "--window-start", "2024-04-19",
            "--window-end", "2026-04-23",
            "--output-dir", str(tmp_path / "out"),
            "--cache-dir", str(tmp_path / "cache"),
        ]
    )
    assert rc == 0
    assert captured["base_capital"] == 12345.0
    assert captured["capital_multiplier"] == 5.0
    assert captured["window_start"] == date(2024, 4, 19)
    assert captured["window_end"] == date(2026, 4, 23)
    assert captured["universe_variant"].name == "spx_ndx"


def test_run_diagnostic_records_git_dirty_in_manifest(monkeypatch, tmp_path):
    """Manifest must carry a git_dirty boolean per the parity-check R1 lesson."""
    monkeypatch.setattr(
        "research.harness.earnings_proximity.instrumented_replay.evaluate_one",
        lambda ctx: _aplus_candidate(ctx.ticker),
    )
    _patch_fetchers(monkeypatch, frames=("AAPL",))
    # Force a deterministic dirty answer so the test does not depend on the
    # ambient working tree state.
    monkeypatch.setattr(diagnostic_run, "_git_dirty", lambda repo_root: False)

    output_dir = tmp_path / "out"
    diagnostic_run.run_diagnostic(
        universe_variant=_stub_universe(["AAPL"]),
        base_capital=7500.0,
        capital_multiplier=1.0,
        window_start=date(2025, 6, 2),
        window_end=date(2025, 6, 3),
        output_dir=output_dir,
        cache_dir=tmp_path / "cache",
    )
    manifest = json.loads((output_dir / "run_manifest.json").read_text())
    assert "git_dirty" in manifest
    assert manifest["git_dirty"] is False


def test_cli_main_dispatches_sp_1500_universe(monkeypatch, tmp_path):
    """`main(['--universe', 'sp_1500', ...])` resolves to the sp_1500 variant
    and threads it through to run_diagnostic at 1× capital."""
    captured: dict = {}

    def fake_run_diagnostic(**kwargs):
        captured.update(kwargs)
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        (kwargs["output_dir"] / "run_manifest.json").write_text("{}")

    monkeypatch.setattr(diagnostic_run, "run_diagnostic", fake_run_diagnostic)
    monkeypatch.setattr(
        diagnostic_run,
        "load_universe_variant_at",
        lambda name, cache_dir: _stub_universe(["AAPL", "MID1", "SML1"], name=name),
    )

    rc = diagnostic_run.main(
        [
            "--universe", "sp_1500",
            "--capital-multiplier", "1.0",
            "--base-capital", "7500.0",
            "--window-start", "2024-04-19",
            "--window-end", "2026-04-23",
            "--output-dir", str(tmp_path / "out"),
            "--cache-dir", str(tmp_path / "cache"),
        ]
    )
    assert rc == 0
    assert captured["universe_variant"].name == "sp_1500"
    assert captured["base_capital"] == 7500.0
    assert captured["capital_multiplier"] == 1.0
    assert captured["window_start"] == date(2024, 4, 19)
    assert captured["window_end"] == date(2026, 4, 23)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _stub_universe(tickers, *, name="spx_ndx_stub", source_url=None):
    from research.harness.earnings_proximity.universe_variants import UniverseVariant

    return UniverseVariant(
        name=name,
        tickers=tuple(sorted(set(tickers))),
        version=f"{name}_test",
        source_url=source_url,
        fetched_date=None,
    )


def _patch_fetchers(monkeypatch, *, frames=("AAPL", "SPY")):
    frames_data = {t: _ohlcv() for t in (*frames, "SPY")}

    def fake_load_ohlcv_with_stats(tickers, *, start, end, cache_dir):
        data = {t: frames_data[t] for t in tickers if t in frames_data}
        return data, FetchStats(hits=tuple(data.keys()), misses=())

    def fake_load_earnings_with_stats(tickers, *, cache_dir, cache_max_age_hours=24):
        data = {t: [] for t in tickers}
        return data, FetchStats(hits=tuple(data.keys()), misses=())

    monkeypatch.setattr(
        "research.harness.earnings_proximity.scripts.diagnostic_run.fetchers.load_ohlcv_with_stats",
        fake_load_ohlcv_with_stats,
    )
    monkeypatch.setattr(
        "research.harness.earnings_proximity.scripts.diagnostic_run.fetchers.load_earnings_with_stats",
        fake_load_earnings_with_stats,
    )


def _minimal_config_toml(*, starting_equity: float, floor: float) -> str:
    return f"""
[paths]
db_path = "swing-data/swing.db"
data_dir = "swing-data"
logs_dir = "swing-data/logs"
charts_dir = "swing-data/charts"
backups_dir = "swing-data/backups"
prices_cache_dir = "swing-data/prices-cache"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = {starting_equity}
starting_date = "2026-03-16"
risk_equity_floor = {floor}

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
closeness_to_pivot = 0.5
adr = 0.25
prior_trend = 0.25
"""
