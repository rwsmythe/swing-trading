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
    CANONICAL_SIGNAL_COUNT,
    PerVariableSignal,
    SynthesisContractError,
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
    REQUIRED_COHORT_CSV_HEADERS,
    CohortCsvSchemaError,
    MissingCanonicalVariableError,
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
    dominant_sector: str = "Technology",
    raw_w_count: int = 10,
    canonical_survival_rate: float | None = 0.1,
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
        raw_w_count=raw_w_count,
        filtered_w_count=f_count,
        filtered_density=d_filt,
        canonical_survival_rate=canonical_survival_rate,
        density_delta_vs_baseline=delta_vs_baseline,
        regime_return_90d_median=10.0,
        regime_atr_pct_20d_median=2.5,
        regime_high_52w_proximity_pct_median=20.0,
        dominant_sector=dominant_sector,
    )


# ============= GOTCHA #33 BANNED-VERDICT-TERMS BINDING TEST =============


def test_synthesis_output_has_no_banned_verdict_terms() -> None:
    """Gotcha #33 third canonical application LOCK: synthesis MUST NOT
    emit PARTIAL POSITIVE / NEGATIVE / POSITIVE verdict terminology.
    """
    signals = [
        _signal(variable=f"vcp.var{i}", delta_vs_baseline=-0.05)
        for i in range(CANONICAL_SIGNAL_COUNT)
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
    signals = [_signal(delta_vs_baseline=-0.05) for _ in range(CANONICAL_SIGNAL_COUNT)]
    result = synthesize(signals)
    assert result.categorical_label in {
        "COMPATIBLE",
        "PARTIALLY-COMPATIBLE",
        "INCOMPATIBLE",
    }


# ----- Codex R1 MAJOR #4 fix: synthesize empty / non-canonical contract -----


def test_synthesize_raises_on_empty_signals() -> None:
    """Codex R1 MAJOR #4 fix: empty signals -> SynthesisContractError.

    Pre-fix returned categorical label COMPATIBLE on empty input,
    silently masking upstream orchestration failure.
    """
    with pytest.raises(SynthesisContractError, match="empty signals"):
        synthesize([])


def test_synthesize_raises_on_non_canonical_signal_count() -> None:
    """Canonical contract: exactly 5 signals. Other counts -> raise."""
    signals = [_signal() for _ in range(3)]
    with pytest.raises(SynthesisContractError, match="canonical"):
        synthesize(signals)


def test_synthesize_accepts_non_canonical_with_opt_in() -> None:
    """Ad-hoc analytical subsets allowed via require_canonical_signal_count=False."""
    signals = [_signal() for _ in range(3)]
    result = synthesize(signals, require_canonical_signal_count=False)
    assert len(result.per_variable_signal_table) == 3


def test_canonical_signal_count_lock() -> None:
    """LOCK: 5 V2 binding variables per dispatch brief Q2."""
    assert CANONICAL_SIGNAL_COUNT == 5


def test_synthesize_raises_on_banned_term_in_dominant_sector() -> None:
    """Codex R4 MAJOR #2 fix: pre-render validation catches banned
    verdict-term substrings embedded in PerVariableSignal fields.

    Pre-fix: a sector value like "Positive Services" would silently render
    into the narrative; post-render banned-terms discriminating test
    would fail with no clear attribution. Post-fix: SynthesisContractError
    at pre-render with offending field identified.
    """
    signals = [_signal(dominant_sector="Positive Services") for _ in range(5)]
    with pytest.raises(SynthesisContractError, match="banned verdict term"):
        synthesize(signals)


def test_synthesize_raises_on_banned_term_in_variable_name() -> None:
    """Variable name carrying a banned substring also rejected."""
    signals = [_signal(variable=f"vcp.var{i}") for i in range(5)]
    # Replace first signal's variable_name with one containing a banned substring
    from dataclasses import replace as _dc_replace
    signals[0] = _dc_replace(signals[0], variable_name="vcp.negative_trend")
    with pytest.raises(SynthesisContractError, match="banned verdict term"):
        synthesize(signals)


# ============= CLASSIFY_COMPATIBILITY DECISION-RULE TESTS =============


def test_classify_all_negative_yields_incompatible() -> None:
    signals = [_signal(delta_vs_baseline=-0.05) for _ in range(CANONICAL_SIGNAL_COUNT)]
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
    """classify_compatibility([]) returns COMPATIBLE; the strict empty-input
    guard lives at the synthesize() layer (test_synthesize_raises_on_empty_signals).
    classify_compatibility is the lower-level helper consumed by ad-hoc paths.
    """
    label, neg, pos = classify_compatibility([])
    assert label == "COMPATIBLE"
    assert neg == 0
    assert pos == 0


def test_classify_none_delta_counts_as_neutral() -> None:
    """None delta (zero-substrate edge case) counts as positive_or_zero."""
    signals = [_signal(delta_vs_baseline=None) for _ in range(CANONICAL_SIGNAL_COUNT)]
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
        raw_w_count=100,
        filtered_w_count=2,
        filtered_density=0.2,
        canonical_survival_rate=0.02,
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
    # Dual-density framing fields populated
    assert sig.raw_w_count == 100
    assert sig.canonical_survival_rate is not None


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


# ----- Codex R1 MAJOR #3 fix: cohort CSV schema validation -----


def test_required_cohort_csv_headers_lock() -> None:
    """LOCK: 3 required cohort CSV headers."""
    assert set(REQUIRED_COHORT_CSV_HEADERS) == {
        "ticker", "asof_date", "cohort_label"
    }


def test_read_cohort_csv_raises_on_missing_header(tmp_path: Path) -> None:
    """Cohort CSV missing required header -> CohortCsvSchemaError."""
    bad = tmp_path / "bad.csv"
    bad.write_text("symbol,date\nABC,2026-05-01\n", encoding="utf-8")
    with pytest.raises(CohortCsvSchemaError, match="missing required headers"):
        read_cohort_csv(bad)


def test_read_cohort_csv_raises_on_empty_ticker(tmp_path: Path) -> None:
    """Cohort CSV with empty ticker cell -> CohortCsvSchemaError."""
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "ticker,asof_date,cohort_label\n,2026-05-01,test\n",
        encoding="utf-8",
    )
    with pytest.raises(CohortCsvSchemaError, match="empty ticker"):
        read_cohort_csv(bad)


def test_read_cohort_csv_raises_on_empty_asof(tmp_path: Path) -> None:
    """Cohort CSV with empty asof_date cell -> CohortCsvSchemaError."""
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "ticker,asof_date,cohort_label\nABC,,test\n",
        encoding="utf-8",
    )
    with pytest.raises(CohortCsvSchemaError, match="empty asof_date"):
        read_cohort_csv(bad)


def test_read_cohort_csv_raises_on_malformed_asof(tmp_path: Path) -> None:
    """Cohort CSV with malformed asof_date -> CohortCsvSchemaError."""
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "ticker,asof_date,cohort_label\nABC,not-a-date,test\n",
        encoding="utf-8",
    )
    with pytest.raises(CohortCsvSchemaError, match="malformed asof_date"):
        read_cohort_csv(bad)


def test_read_cohort_csv_raises_on_empty_file(tmp_path: Path) -> None:
    """Empty cohort CSV -> CohortCsvSchemaError."""
    bad = tmp_path / "empty.csv"
    bad.write_text("", encoding="utf-8")
    with pytest.raises(CohortCsvSchemaError, match="empty or has no header"):
        read_cohort_csv(bad)


def test_read_cohort_csv_raises_on_header_only_zero_data_rows(tmp_path: Path) -> None:
    """Codex R2 MAJOR #2 fix discriminator: header-only cohort CSV
    (valid headers but zero data rows) -> CohortCsvSchemaError.

    Pre-fix: header-only CSV returned []; five such CSVs converged to
    COMPATIBLE synthesis. Post-fix: fail-closed.
    """
    bad = tmp_path / "headeronly.csv"
    bad.write_text(
        "ticker,asof_date,cohort_label\n",
        encoding="utf-8",
    )
    with pytest.raises(CohortCsvSchemaError, match="zero data rows"):
        read_cohort_csv(bad)


def test_read_cohort_csv_raises_on_empty_cohort_label(tmp_path: Path) -> None:
    """Codex R2 MINOR #1 fix discriminator: empty cohort_label cell ->
    CohortCsvSchemaError.
    """
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "ticker,asof_date,cohort_label\nABC,2026-05-01,\n",
        encoding="utf-8",
    )
    with pytest.raises(CohortCsvSchemaError, match="empty cohort_label"):
        read_cohort_csv(bad)


# ----- Codex R2 MAJOR #3 fix: run_analysis missing canonical variable -----


def _synthetic_asof() -> date:
    """A date that IS a business day in the synthetic OHLCV fixture
    (matches `_synthetic_df(date(2024, 1, 1), 400)` index range)."""
    return pd.bdate_range(start=pd.Timestamp(date(2024, 1, 1)), periods=400)[-1].date()


def _full_cohort_pairs() -> dict[str, list[tuple[str, date]]]:
    asof = _synthetic_asof()
    return {
        v: [("AAA", asof)] for v, _, _ in BINDING_SIGNALS_TABLE
    }


def _full_verdicts() -> dict[str, list[WPrimaryVerdict]]:
    asof = _synthetic_asof()
    return {
        v: [
            WPrimaryVerdict(
                ticker="AAA",
                anchor_asof_date=asof,
                trough_1_date=date(2025, 5, 1),
                trough_2_date=date(2025, 5, 15),
                composite_score=0.7,
            )
        ]
        for v, _, _ in BINDING_SIGNALS_TABLE
    }


def test_run_analysis_raises_on_missing_canonical_cohort_variable(tmp_path: Path) -> None:
    """Codex R2 MAJOR #3 fix: run_analysis fails closed if a canonical
    V2 binding variable is missing from cohort_pairs_by_variable.

    Pre-fix: missing variable silently substituted with []; signal still
    emitted with None delta; 5-row synthesize() contract satisfied;
    misleading COMPATIBLE classification.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    df = _synthetic_df(date(2024, 1, 1), 400)
    df.to_parquet(cache_dir / "AAA.parquet")

    cohort_pairs = _full_cohort_pairs()
    del cohort_pairs["vcp.proximity_max_pct"]  # remove canonical variable
    with pytest.raises(MissingCanonicalVariableError, match="vcp.proximity_max_pct"):
        run_analysis(
            cohort_pairs_by_variable=cohort_pairs,
            verdicts_by_variable=_full_verdicts(),
            cache_dir=cache_dir,
        )


def test_run_analysis_raises_on_missing_canonical_verdicts_variable(tmp_path: Path) -> None:
    """Codex R2 MAJOR #3 fix: run_analysis fails closed if a canonical
    V2 binding variable is missing from verdicts_by_variable.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    df = _synthetic_df(date(2024, 1, 1), 400)
    df.to_parquet(cache_dir / "AAA.parquet")

    verdicts = _full_verdicts()
    del verdicts["vcp.orderliness_max_bar_ratio"]
    with pytest.raises(MissingCanonicalVariableError, match="vcp.orderliness_max_bar_ratio"):
        run_analysis(
            cohort_pairs_by_variable=_full_cohort_pairs(),
            verdicts_by_variable=verdicts,
            cache_dir=cache_dir,
        )


def test_run_analysis_accepts_empty_verdicts_list_for_canonical_variable(tmp_path: Path) -> None:
    """Empty verdicts list [] for a canonical variable is ALLOWED (cohort
    produced zero W primaries); the variable's PRESENCE in the dict is
    the contract, not non-empty value. The cohort itself MUST be non-empty
    (R3 MAJOR #1 fix; tested separately)."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    df = _synthetic_df(date(2024, 1, 1), 400)
    df.to_parquet(cache_dir / "AAA.parquet")
    asof = df.index[-1].date()
    cohort_pairs = {v: [("AAA", asof)] for v, _, _ in BINDING_SIGNALS_TABLE}
    verdicts = {
        v: [
            WPrimaryVerdict(
                ticker="AAA",
                anchor_asof_date=asof,
                trough_1_date=date(2025, 5, 1),
                trough_2_date=date(2025, 5, 15),
                composite_score=0.7,
            )
        ]
        for v, _, _ in BINDING_SIGNALS_TABLE
    }
    verdicts["vcp.orderliness_max_bar_ratio"] = []  # explicitly empty verdicts
    result = run_analysis(
        cohort_pairs_by_variable=cohort_pairs,
        verdicts_by_variable=verdicts,
        cache_dir=cache_dir,
    )
    assert len(result.per_variable_signal_table) == 5
    obr_signal = next(
        s for s in result.per_variable_signal_table
        if s.variable_name == "vcp.orderliness_max_bar_ratio"
    )
    assert obr_signal.filtered_w_count == 0


def test_run_analysis_raises_on_empty_cohort_pairs(tmp_path: Path) -> None:
    """Codex R3 MAJOR #1 fix discriminator: a canonical variable with
    EMPTY cohort_pairs list -> MissingCanonicalVariableError.

    Pre-fix (R2): missing variable raised; but variable PRESENT with
    EMPTY value silently substituted with empty substrate; synthesize()
    5-row contract satisfied; signal counted as neutral. Post-fix: empty
    cohort_pairs value also raises (the substrate cannot be empty for a
    canonical V2 variable).

    Empty VERDICTS list is still allowed (zero W primaries is a valid
    analytical signal when the cohort has tickers).
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    df = _synthetic_df(date(2024, 1, 1), 400)
    df.to_parquet(cache_dir / "AAA.parquet")
    cohort_pairs = _full_cohort_pairs()
    cohort_pairs["vcp.proximity_max_pct"] = []  # empty substrate
    with pytest.raises(MissingCanonicalVariableError, match="EMPTY substrate"):
        run_analysis(
            cohort_pairs_by_variable=cohort_pairs,
            verdicts_by_variable=_full_verdicts(),
            cache_dir=cache_dir,
        )


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
        raw_w_count=100,
        filtered_w_count=2,
        filtered_density=0.2,
        canonical_survival_rate=0.02,
        density_delta_vs_baseline=0.2 - D2_BASELINE_FILTERED_DENSITY,
    )}
    out = tmp_path / "w_density.csv"
    write_w_density_detail_csv(metrics, out)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("cohort_label,substrate_ticker_count,")
    # D2 baseline as first DATA row (universe 516; raw_w_count 0 because
    # D2 results.csv not emitted in V1 -- Option B fallback)
    assert lines[1].startswith("d2_expanded_baseline_sp500,516,0,71,")


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


def test_cli_dry_run_verifies_canonical_source_sha(tmp_path: Path) -> None:
    """Codex R1 MAJOR #2 fix discriminator: dry-run mode hashes the
    canonical source artifact + raises if SHA does not match the LOCK.

    Discriminating: pre-fix CLI advertised SHA validation but main()
    never read CANONICAL_SOURCE_PATH or hashed it; a tampered source
    could still emit a placeholder manifest.

    Runs the CLI from tmp_path (so canonical source path resolves to a
    non-existent file); PYTHONPATH is set to REPO_ROOT so the module
    loads. CLI must exit 2 with a clear error.
    """
    out_root = tmp_path / "out"
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [
            sys.executable, "-m",
            "research.harness.v2_selection_mechanic.run",
            "--dry-run",
            "--out-root", str(out_root),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2, (
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "canonical source" in result.stderr.lower()


def test_cli_refuses_with_no_mode_flag() -> None:
    """CLI requires either --dry-run or --execute."""
    result = subprocess.run(
        [sys.executable, "-m", "research.harness.v2_selection_mechanic.run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "specify either --dry-run" in result.stderr


def test_cli_refuses_mutually_exclusive_flags() -> None:
    """CLI refuses both --dry-run and --execute simultaneously."""
    result = subprocess.run(
        [sys.executable, "-m", "research.harness.v2_selection_mechanic.run",
         "--dry-run", "--execute"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "mutually exclusive" in result.stderr


def test_cli_execute_refuses_missing_db(tmp_path: Path) -> None:
    """--execute fails closed if --db path doesn't exist."""
    result = subprocess.run(
        [sys.executable, "-m", "research.harness.v2_selection_mechanic.run",
         "--execute", "--db", str(tmp_path / "no.db"),
         "--out-root", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "swing.db not found" in result.stderr


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
