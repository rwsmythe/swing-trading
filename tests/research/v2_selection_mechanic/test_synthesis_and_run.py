"""Synthesis + run.py + cumulative discipline tests for V2-selection-mechanic.

Includes BINDING gotcha #33 third canonical application discriminating
test (banned-verdict-terms) + L2 LOCK source-grep + ASCII discipline +
end-to-end orchestration on synthetic verdicts.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.harness.v2_selection_mechanic import (
    BINDING_SIGNALS_TABLE,
    D2_BASELINE_FILTERED_DENSITY,
    D2_BASELINE_UNIVERSE_SIZE,
)
from research.harness.v2_selection_mechanic.substrate_characterization import (
    CohortAggregateMetrics,
)
from research.harness.v2_selection_mechanic.synthesis import (
    BANNED_VERDICT_TERMS,
    PerVariableSignal,
    build_per_variable_signal,
    classify_compatibility,
    synthesize,
)
from research.harness.v2_selection_mechanic.w_density_analysis import (
    WDensityMetrics,
    WPrimaryVerdict,
)
from research.harness.v2_selection_mechanic import run as run_module
from research.harness.v2_selection_mechanic.run import (
    DEFAULT_COHORT_CSV_BY_VARIABLE,
    main as run_main,
    read_cohort_csv,
    run_analysis,
    write_per_variable_signal_csv,
    write_substrate_characterization_csv,
    write_w_density_detail_csv,
    write_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def _signal(
    variable: str = "vcp.test",
    sp: float = 1.0,
    max_delta: int = 10,
    drill: int = 10,
    t_count: int = 10,
    f_count: int = 1,
    d_filt: float | None = 0.1,
    delta_vs_baseline: float | None = -0.0376,
) -> PerVariableSignal:
    return PerVariableSignal(
        variable_name=variable,
        binding_sweep_point=sp,
        max_delta_aplus=max_delta,
        drill_down_watch_aplus_count=drill,
        non_watch_transition_gap=max_delta - drill,
        non_watch_transition_gap_pct=0.0,
        substrate_ticker_count=t_count,
        substrate_unique_ticker_asof_count=t_count,
        filtered_w_count=f_count,
        filtered_density=d_filt,
        density_delta_vs_baseline=delta_vs_baseline,
        regime_return_90d_median=10.0,
        regime_atr_pct_20d_median=2.5,
        regime_high_52w_proximity_pct_median=20.0,
        dominant_sector="Technology",
    )


# ============= GOTCHA #33 BANNED-VERDICT-TERMS BINDING TEST =============


def test_synthesis_output_has_no_banned_verdict_terms() -> None:
    """Gotcha #33 third canonical application LOCK: synthesis MUST NOT
    emit PARTIAL POSITIVE / NEGATIVE / POSITIVE verdict terminology.
    """
    signals = [
        _signal(variable=f"vcp.var{i}", delta_vs_baseline=-0.05) for i in range(5)
    ]
    result = synthesize(signals)
    lower = result.narrative_markdown.lower()
    for banned in BANNED_VERDICT_TERMS:
        assert banned.lower() not in lower, (
            f"synthesis output contains banned term {banned!r}; "
            f"gotcha #33 third canonical application VIOLATION"
        )


def test_banned_verdict_terms_lock_includes_expected_terms() -> None:
    """LOCK: the banned-terms list includes the 4 canonical reserved terms."""
    expected = {"PARTIAL POSITIVE", "POSITIVE", "NEGATIVE", "INSUFFICIENT SAMPLE"}
    assert set(BANNED_VERDICT_TERMS) == expected


def test_synthesis_emits_descriptive_categorical_label_only() -> None:
    """Synthesis emits COMPATIBLE / PARTIALLY-COMPATIBLE / INCOMPATIBLE."""
    signals = [_signal(delta_vs_baseline=-0.05) for _ in range(5)]
    result = synthesize(signals)
    assert result.categorical_label in {
        "COMPATIBLE",
        "PARTIALLY-COMPATIBLE",
        "INCOMPATIBLE",
    }


# ============= CLASSIFY_COMPATIBILITY DECISION-RULE TESTS =============


def test_classify_all_negative_yields_incompatible() -> None:
    signals = [_signal(delta_vs_baseline=-0.05) for _ in range(5)]
    label, neg, pos = classify_compatibility(signals)
    assert label == "INCOMPATIBLE"
    assert neg == 5
    assert pos == 0


def test_classify_two_negative_yields_partially_compatible() -> None:
    signals = (
        [_signal(delta_vs_baseline=-0.05) for _ in range(2)]
        + [_signal(delta_vs_baseline=+0.05) for _ in range(3)]
    )
    label, neg, pos = classify_compatibility(signals)
    assert label == "PARTIALLY-COMPATIBLE"
    assert neg == 2
    assert pos == 3


def test_classify_one_negative_yields_compatible() -> None:
    signals = (
        [_signal(delta_vs_baseline=-0.05)]
        + [_signal(delta_vs_baseline=+0.05) for _ in range(4)]
    )
    label, neg, pos = classify_compatibility(signals)
    assert label == "COMPATIBLE"


def test_classify_zero_signals_returns_compatible() -> None:
    label, neg, pos = classify_compatibility([])
    assert label == "COMPATIBLE"
    assert neg == 0
    assert pos == 0


def test_classify_none_delta_counts_as_neutral() -> None:
    """None delta (zero-substrate edge case) counts as positive_or_zero."""
    signals = [_signal(delta_vs_baseline=None) for _ in range(5)]
    label, neg, pos = classify_compatibility(signals)
    assert label == "COMPATIBLE"  # 0 negative; all neutral
    assert neg == 0
    assert pos == 5


# ============= build_per_variable_signal =============


def _aggregate(sector: str = "Tech") -> CohortAggregateMetrics:
    return CohortAggregateMetrics(
        cohort_label="test",
        unique_ticker_count=10,
        unique_ticker_asof_count=12,
        return_90d_pct_median=5.0,
        return_90d_pct_iqr=8.0,
        atr_pct_20d_median=2.0,
        atr_pct_20d_iqr=1.0,
        high_52w_proximity_pct_median=15.0,
        high_52w_proximity_pct_iqr=10.0,
        sector_counts={sector: 8, "UNKNOWN": 2},
    )


def _w_density() -> WDensityMetrics:
    return WDensityMetrics(
        cohort_label="test",
        substrate_ticker_count=10,
        filtered_w_count=2,
        filtered_density=0.2,
        density_delta_vs_baseline=0.2 - D2_BASELINE_FILTERED_DENSITY,
    )


def test_build_per_variable_signal_populates_all_fields() -> None:
    sig = build_per_variable_signal(
        variable_name="vcp.test",
        binding_sweep_point=1.0,
        max_delta_aplus=10,
        drill_down_watch_aplus_count=8,
        aggregate_metrics=_aggregate(),
        w_density=_w_density(),
    )
    assert sig.variable_name == "vcp.test"
    assert sig.non_watch_transition_gap == 2  # 10 - 8
    assert abs(sig.non_watch_transition_gap_pct - 20.0) < 1e-9
    assert sig.substrate_ticker_count == 10
    assert sig.filtered_w_count == 2
    assert sig.dominant_sector == "Tech"  # 8 > 2 UNKNOWN


def test_build_per_variable_signal_zero_max_delta_no_div_by_zero() -> None:
    """Defensive: max_delta=0 -> gap_pct=0 (no DivisionByZero)."""
    sig = build_per_variable_signal(
        variable_name="vcp.test",
        binding_sweep_point=1.0,
        max_delta_aplus=0,
        drill_down_watch_aplus_count=0,
        aggregate_metrics=_aggregate(),
        w_density=_w_density(),
    )
    assert sig.non_watch_transition_gap == 0
    assert sig.non_watch_transition_gap_pct == 0.0


# ============= run.py read_cohort_csv =============


def test_read_cohort_csv_against_committed_v2trf() -> None:
    """Reads the committed v2_tightness_range_factor cohort CSV (29 rows)."""
    path = REPO_ROOT / DEFAULT_COHORT_CSV_BY_VARIABLE["vcp.tightness_range_factor"]
    pairs = read_cohort_csv(path)
    assert len(pairs) == 29  # locked in v2_tightness_range_factor module
    tickers = {p[0] for p in pairs}
    assert tickers == {
        "YOU", "DK", "SSRM", "WULF", "TSHA", "NAT", "RLMD", "UCTT",
        "PTEN", "KOD", "RNG", "TROX", "FRO", "DNTH", "OII",
    }


def test_read_cohort_csv_against_committed_v2pmp() -> None:
    """Reads the committed v2_proximity_max_pct cohort CSV (3 rows)."""
    path = REPO_ROOT / DEFAULT_COHORT_CSV_BY_VARIABLE["vcp.proximity_max_pct"]
    pairs = read_cohort_csv(path)
    assert len(pairs) == 3
    assert {p[0] for p in pairs} == {"SEI", "YOU", "SLDB"}


def test_read_cohort_csv_against_committed_v2obr() -> None:
    """Reads the committed v2_orderliness_max_bar_ratio cohort CSV (1 row)."""
    path = REPO_ROOT / DEFAULT_COHORT_CSV_BY_VARIABLE["vcp.orderliness_max_bar_ratio"]
    pairs = read_cohort_csv(path)
    assert len(pairs) == 1
    assert pairs[0] == ("LASR", date(2026, 5, 15))


# ============= run_analysis end-to-end on planted verdicts =============


def _synthetic_df(start: date, n_days: int, base_price: float = 100.0) -> pd.DataFrame:
    dates = pd.bdate_range(start=pd.Timestamp(start), periods=n_days)
    closes = base_price + np.arange(n_days, dtype=float)
    highs = closes + 0.5
    lows = closes - 0.5
    opens = closes - 0.25
    volumes = np.full(n_days, 1000000, dtype=int)
    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dates,
    )
    df.index.name = "Date"
    return df


def test_run_analysis_end_to_end_synthetic(tmp_path: Path) -> None:
    """End-to-end run_analysis against planted ticker archives + verdicts.

    Validates that the orchestration pipeline (5 variables; planted
    substrates + verdicts) emits a CompatibilitySynthesis with all 5
    PerVariableSignal rows + a non-empty narrative.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    # Plant 1 ticker archive per variable
    plant_tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    for t in plant_tickers:
        df = _synthetic_df(date(2025, 1, 1), 300)
        df.to_parquet(cache_dir / f"{t}.parquet")
    asof = pd.bdate_range(start=pd.Timestamp(date(2025, 1, 1)), periods=300)[-1].date()
    cohort_pairs_by_variable = {
        v: [(plant_tickers[i], asof)]
        for i, (v, _, _) in enumerate(BINDING_SIGNALS_TABLE)
    }
    verdicts_by_variable = {
        v: [
            WPrimaryVerdict(
                ticker=plant_tickers[i],
                anchor_asof_date=asof,
                trough_1_date=date(asof.year, asof.month, 1),
                trough_2_date=date(asof.year, asof.month, 15),
                composite_score=0.6,
            )
        ]
        for i, (v, _, _) in enumerate(BINDING_SIGNALS_TABLE)
    }
    result = run_analysis(
        cohort_pairs_by_variable=cohort_pairs_by_variable,
        verdicts_by_variable=verdicts_by_variable,
        cache_dir=cache_dir,
    )
    assert len(result.per_variable_signal_table) == 5
    assert result.categorical_label in {
        "COMPATIBLE", "PARTIALLY-COMPATIBLE", "INCOMPATIBLE"
    }
    # Each cohort has 1 substrate ticker + 1 filtered W -> density = 1.0
    # Delta = 1.0 - 0.1376 = +0.862 (positive); all 5 -> COMPATIBLE
    assert result.categorical_label == "COMPATIBLE"
    assert result.negative_delta_count == 0
    # Banned-terms LOCK (defense in depth)
    lower = result.narrative_markdown.lower()
    for banned in BANNED_VERDICT_TERMS:
        assert banned.lower() not in lower


# ============= write_per_variable_signal_csv =============


def test_write_per_variable_signal_csv(tmp_path: Path) -> None:
    signals = [_signal(variable=f"vcp.var{i}") for i in range(3)]
    out = tmp_path / "per_variable_signals.csv"
    write_per_variable_signal_csv(signals, out)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("variable_name,binding_sweep_point,")
    assert len(lines) == 4  # header + 3 rows


def test_write_w_density_detail_csv_includes_baseline_first(tmp_path: Path) -> None:
    metrics = {"vcp.var1": WDensityMetrics(
        cohort_label="vcp.var1",
        substrate_ticker_count=10,
        filtered_w_count=2,
        filtered_density=0.2,
        density_delta_vs_baseline=0.2 - D2_BASELINE_FILTERED_DENSITY,
    )}
    out = tmp_path / "w_density.csv"
    write_w_density_detail_csv(metrics, out)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("cohort_label,substrate_ticker_count,")
    # D2 baseline as first DATA row
    assert lines[1].startswith("d2_expanded_baseline_sp500,516,71,")


def test_write_manifest_payload_shape(tmp_path: Path) -> None:
    out = tmp_path / "manifest.json"
    write_manifest(
        out,
        run_ts_utc="20260526T120000Z",
        canonical_source_path="some/path.md",
        canonical_source_sha256="abc",
        cohort_paths_by_variable={"v1": "p1"},
        d2_baseline_manifest_path="d2/path",
        d2_baseline_universe_size=516,
        d2_baseline_filtered_w_count=71,
        canonical_composite_threshold=0.5,
        canonical_recency_days=365,
        compatibility_label="COMPATIBLE",
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["investigation"] == "v2-selection-mechanic-analysis"
    assert payload["investigation_type"] == "analytical_exploratory"
    assert payload["l2_lock_preserved"] is True
    assert payload["schwab_api_calls"] == 0
    assert payload["yfinance_fetches"] == 0
    assert payload["production_swing_writes"] == 0
    assert payload["compatibility_label"] == "COMPATIBLE"


# ============= CLI dry-run =============


def test_cli_dry_run_succeeds_against_committed_cohorts(tmp_path: Path) -> None:
    out_root = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable, "-m",
            "research.harness.v2_selection_mechanic.run",
            "--dry-run",
            "--out-root", str(out_root),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "OK: emitted dry-run smoke artifact" in result.stdout
    # Manifest should exist under out_root / v2-selection-mechanic-analysis-*/
    subdirs = list(out_root.iterdir())
    assert len(subdirs) == 1
    assert (subdirs[0] / "manifest.json").exists()


def test_cli_refuses_non_dry_run_v1() -> None:
    """Non-dry-run mode is V1-deferred; CLI returns 2 with a clear error."""
    result = subprocess.run(
        [sys.executable, "-m", "research.harness.v2_selection_mechanic.run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "delegated to slice 5" in result.stderr


# ============= L2 LOCK source-grep across NEW module set =============


def test_l2_lock_no_schwab_imports_across_module_set() -> None:
    """Parametrized L2 LOCK source-grep across v2_selection_mechanic module set."""
    from research.harness import v2_selection_mechanic as pkg
    module_dir = Path(pkg.__file__).resolve().parent
    files = sorted(module_dir.glob("*.py"))
    assert len(files) >= 5, f"Expected >=5 modules; got {[f.name for f in files]}"
    for py in files:
        text = py.read_text(encoding="utf-8")
        assert "schwabdev" not in text, f"{py} imports schwabdev"
        assert "import yfinance" not in text, f"{py} imports yfinance"
        assert "from yfinance" not in text, f"{py} imports yfinance"
        assert "swing.integrations.schwab" not in text, (
            f"{py} imports swing.integrations.schwab"
        )


def test_l2_lock_no_yfinance_fetch_calls_across_module_set() -> None:
    """No `.download(` / `Ticker(` yfinance-like fetch calls in module bodies."""
    from research.harness import v2_selection_mechanic as pkg
    module_dir = Path(pkg.__file__).resolve().parent
    for py in module_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "yf.download" not in text, f"{py} calls yf.download"
        assert "yf.Ticker" not in text, f"{py} calls yf.Ticker"


# ============= ASCII discipline across NEW module + test set =============


def test_ascii_discipline_module_files() -> None:
    from research.harness import v2_selection_mechanic as pkg
    module_dir = Path(pkg.__file__).resolve().parent
    for py in module_dir.glob("*.py"):
        py.read_text(encoding="utf-8").encode("ascii")


def test_ascii_discipline_test_files() -> None:
    test_dir = Path(__file__).resolve().parent
    for py in test_dir.glob("*.py"):
        py.read_text(encoding="utf-8").encode("ascii")
