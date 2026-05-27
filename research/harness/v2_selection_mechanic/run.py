"""Top-level orchestration entrypoint for V2-selection-mechanic analytical investigation.

Run via:

  python -m research.harness.v2_selection_mechanic.run

Wires the 5 V2 cohort CSVs + D2 EXPANDED bias-free baseline through:

  1. Cohort enumeration  (read 5 V2 cohort CSVs)
  2. Detection invocation per substrate (pattern_cohort_evaluator)
  3. Substrate characterization (regime metrics)
  4. W-density measurement (canonical filter + adjacency merge)
  5. Compatibility synthesis (descriptive narrative; gotcha #33 LOCK)
  6. Emit smoke artifact directory + study writeup

V1 SIMPLIFICATION (banked V2 candidate): the actual
`pattern_cohort_evaluator` invocation is delegated to a helper that
operator can stub or replace with pre-emitted detection artifacts.
The orchestrator emits a manifest plus the per-variable signal CSV +
substrate characterization CSV + W-density detail CSV + compatibility
synthesis markdown.

L2 LOCK preserved: ZERO new Schwab API calls; ZERO yfinance imports;
ZERO production swing/ writes.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from research.harness.v2_selection_mechanic import (
    BINDING_SIGNALS_TABLE,
    CANONICAL_COMPOSITE_THRESHOLD,
    CANONICAL_RECENCY_DAYS,
    CANONICAL_SOURCE_PATH,
    CANONICAL_SOURCE_SHA256,
    D2_BASELINE_FILTERED_DENSITY,
    D2_BASELINE_FILTERED_W_COUNT,
    D2_BASELINE_MANIFEST_PATH,
    D2_BASELINE_UNIVERSE_SIZE,
    NON_WATCH_TRANSITION_GAP_TABLE,
)
from research.harness.v2_selection_mechanic.substrate_characterization import (
    CohortAggregateMetrics,
    PerTickerMetrics,
    compute_cohort_characterization,
    load_sector_map_from_finviz_csv,
)
from research.harness.v2_selection_mechanic.synthesis import (
    CompatibilitySynthesis,
    PerVariableSignal,
    build_per_variable_signal,
    synthesize,
)
from research.harness.v2_selection_mechanic.w_density_analysis import (
    WDensityMetrics,
    WPrimaryVerdict,
    apply_canonical_filter,
    baseline_metrics_snapshot,
    compute_w_density,
    merge_adjacency_5bd,
)


# Default per-variable cohort CSV paths (in dispatch brief Sec 2 LOCK).
DEFAULT_COHORT_CSV_BY_VARIABLE: dict[str, str] = {
    "vcp.tightness_range_factor": (
        "exports/research/cohorts/v2_tightness_range_factor_sp1_005.csv"
    ),
    "vcp.tightness_days_required": (
        "exports/research/cohorts/r2a_tightness_days_required_sp1.csv"
    ),
    "vcp.adr_min_pct": (
        "exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv"
    ),
    "vcp.proximity_max_pct": (
        "exports/research/cohorts/v2_proximity_max_pct_sp7_5.csv"
    ),
    "vcp.orderliness_max_bar_ratio": (
        "exports/research/cohorts/v2_orderliness_max_bar_ratio_sp3_75.csv"
    ),
}


class CohortCsvSchemaError(ValueError):
    """Raised when a cohort CSV is missing required headers OR contains
    malformed rows. Distinct from ValueError so callers can catch
    cohort-schema errors specifically. Codex R1 MAJOR #3 fix 2026-05-26 PM:
    prior implementation silently skipped malformed rows + accepted CSVs
    with wrong headers, allowing 5 malformed cohorts to converge to
    COMPATIBLE instead of failing closed.
    """


REQUIRED_COHORT_CSV_HEADERS: tuple[str, ...] = (
    "ticker",
    "asof_date",
    "cohort_label",
)


def read_cohort_csv(path: Path) -> list[tuple[str, date]]:
    """Read a cohort CSV (ticker, asof_date, cohort_label) -> list of pairs.

    Raises CohortCsvSchemaError if (a) the CSV lacks any of the 3 required
    headers (ticker / asof_date / cohort_label); (b) a data row has
    empty ticker / asof_date / cohort_label; (c) asof_date fails ISO
    parse; (d) the CSV has zero data rows (header-only). Fail-closed
    semantic per gotcha #28 + brief Sec 6(d): cohort artifacts feed
    analytical surfaces; silent skip OR empty cohort masks upstream
    drift.

    Codex R2 MAJOR #2 fix 2026-05-26 PM: prior implementation accepted
    a header-only CSV as a valid empty cohort, allowing five
    header-only artifacts to converge to COMPATIBLE classification
    through `synthesize()` (which enforces 5-signal contract but does
    NOT check that signals carry non-empty substrates).

    Codex R2 MINOR #1 fix 2026-05-26 PM: prior implementation required
    `cohort_label` header but never validated row value; now an empty
    cohort_label cell raises.
    """
    path = Path(path)
    pairs: list[tuple[str, date]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise CohortCsvSchemaError(
                f"Cohort CSV at {path} is empty or has no header row"
            )
        missing_headers = [
            h for h in REQUIRED_COHORT_CSV_HEADERS if h not in reader.fieldnames
        ]
        if missing_headers:
            raise CohortCsvSchemaError(
                f"Cohort CSV at {path} missing required headers: "
                f"{missing_headers}; actual headers: {list(reader.fieldnames)}"
            )
        for row_idx, row in enumerate(reader, start=2):
            ticker = (row.get("ticker") or "").strip().upper()
            asof_raw = (row.get("asof_date") or "").strip()
            cohort_label = (row.get("cohort_label") or "").strip()
            if not ticker:
                raise CohortCsvSchemaError(
                    f"Cohort CSV at {path} row {row_idx} has empty ticker"
                )
            if not asof_raw:
                raise CohortCsvSchemaError(
                    f"Cohort CSV at {path} row {row_idx} has empty asof_date"
                )
            if not cohort_label:
                raise CohortCsvSchemaError(
                    f"Cohort CSV at {path} row {row_idx} has empty cohort_label"
                )
            try:
                asof = date.fromisoformat(asof_raw)
            except ValueError as exc:
                raise CohortCsvSchemaError(
                    f"Cohort CSV at {path} row {row_idx} has malformed "
                    f"asof_date {asof_raw!r}: {exc}"
                )
            pairs.append((ticker, asof))
    if not pairs:
        raise CohortCsvSchemaError(
            f"Cohort CSV at {path} has zero data rows; a valid cohort "
            f"must contain at least one (ticker, asof_date) pair"
        )
    return pairs


class MissingCanonicalVariableError(KeyError):
    """Raised when a canonical V2 binding variable is absent from the
    cohort_pairs_by_variable or verdicts_by_variable inputs.

    Codex R2 MAJOR #3 fix 2026-05-26 PM: prior implementation silently
    substituted [] when a canonical variable was missing from either
    input dict; the function emitted a signal anyway (with None delta or
    F=0), materially altering the compatibility label while still
    satisfying the 5-row synthesize() contract.
    """


def run_analysis(
    *,
    cohort_pairs_by_variable: dict[str, list[tuple[str, date]]],
    verdicts_by_variable: dict[str, list[WPrimaryVerdict]],
    cache_dir: Path | None = None,
    finviz_sector_map: dict[str, str] | None = None,
    raw_w_counts_by_variable: dict[str, int] | None = None,
) -> CompatibilitySynthesis:
    """Pure analytical pipeline (testable with planted verdicts).

    Caller is responsible for invoking pattern_cohort_evaluator (or
    reading pre-emitted artifacts) to populate `verdicts_by_variable`.
    The orchestrator then applies canonical filter + adjacency merge +
    substrate characterization + synthesis.

    Raises MissingCanonicalVariableError if either input dict is missing
    a canonical V2 binding variable (per BINDING_SIGNALS_TABLE). The
    investigation contract requires ALL 5 V2 binding variables.

    Returns CompatibilitySynthesis (categorical label + narrative +
    per-variable signal table).
    """
    # Codex R2 MAJOR #3 fix: fail-closed on missing canonical variable.
    canonical_variables = [row[0] for row in BINDING_SIGNALS_TABLE]
    missing_cohort = [v for v in canonical_variables if v not in cohort_pairs_by_variable]
    missing_verdicts = [v for v in canonical_variables if v not in verdicts_by_variable]
    if missing_cohort:
        raise MissingCanonicalVariableError(
            f"cohort_pairs_by_variable missing canonical V2 variable(s): "
            f"{missing_cohort}. The 5-variable contract (BINDING_SIGNALS_TABLE) "
            f"requires all variables present."
        )
    if missing_verdicts:
        raise MissingCanonicalVariableError(
            f"verdicts_by_variable missing canonical V2 variable(s): "
            f"{missing_verdicts}. The 5-variable contract requires all "
            f"variables present (use empty list [] if the cohort produced "
            f"zero W primaries; do not omit the key)."
        )
    # Codex R3 MAJOR #1 fix: a canonical variable with EMPTY cohort_pairs
    # (substrate = zero tickers) is INVALID -- it indicates upstream cohort
    # enumeration failure. An empty cohort produces an empty substrate which
    # yields None density delta, silently counted as neutral by synthesize().
    # Empty verdicts_by_variable[v] is STILL allowed (zero-W primaries are a
    # valid analytical signal when the cohort has tickers but no patterns).
    empty_cohort_pairs = [
        v for v in canonical_variables if not cohort_pairs_by_variable[v]
    ]
    if empty_cohort_pairs:
        raise MissingCanonicalVariableError(
            f"cohort_pairs_by_variable has EMPTY substrate for canonical "
            f"V2 variable(s): {empty_cohort_pairs}. An empty substrate "
            f"(zero tickers) indicates upstream cohort enumeration failure; "
            f"the investigation contract requires non-empty cohorts for "
            f"all 5 V2 binding variables. Empty verdicts list is allowed "
            f"(zero W primaries is a valid analytical signal); empty cohort "
            f"pairs is not."
        )

    gap_lookup = {row[0]: row[2] for row in NON_WATCH_TRANSITION_GAP_TABLE}
    binding_lookup = {row[0]: (row[1], row[2]) for row in BINDING_SIGNALS_TABLE}
    signals: list[PerVariableSignal] = []
    for variable_name, _, sweep_point in BINDING_SIGNALS_TABLE:
        pairs = cohort_pairs_by_variable[variable_name]
        tickers = sorted({p[0] for p in pairs})
        # Substrate characterization
        _, aggregate = compute_cohort_characterization(
            cohort_label=variable_name,
            ticker_asof_pairs=pairs,
            cache_dir=cache_dir,
            finviz_sector_map=finviz_sector_map,
        )
        # W-density on caller-supplied verdicts (apply canonical filter + adjacency)
        raw_verdicts = verdicts_by_variable[variable_name]
        filtered = apply_canonical_filter(raw_verdicts)
        merged = merge_adjacency_5bd(filtered)
        # Raw W count = pre-canonical-filter verdict count (the caller's
        # raw_w_counts_by_variable mapping can override; defaults to len of
        # the verdicts list, which represents pre-filter primaries when the
        # caller extracted at composite_threshold=0.0).
        raw_count = (
            raw_w_counts_by_variable.get(variable_name, len(raw_verdicts))
            if raw_w_counts_by_variable is not None
            else len(raw_verdicts)
        )
        w_density = compute_w_density(
            cohort_label=variable_name,
            substrate_tickers=tickers,
            canonical_filtered_verdicts=merged,
            raw_w_count=raw_count,
        )
        signals.append(
            build_per_variable_signal(
                variable_name=variable_name,
                binding_sweep_point=sweep_point,
                max_delta_aplus=binding_lookup[variable_name][0],
                drill_down_watch_aplus_count=gap_lookup[variable_name],
                aggregate_metrics=aggregate,
                w_density=w_density,
            )
        )
    return synthesize(signals)


def write_per_variable_signal_csv(
    signals: Sequence[PerVariableSignal], path: Path
) -> None:
    """Emit per_variable_signals.csv (Sec 3.2).

    Emits BOTH density framings per brief Sec 0/1.6/1.7 dual-metric
    methodological clarification surfaced at slice 5 smoke run 2026-05-27:
      - filtered_density = F / T (brief Sec 1.6 LOCK; W per ticker)
      - canonical_survival_rate = F / R_raw (brief Sec 0/1.7 narrative;
        survival rate through canonical filter; ~12% / ~13% / ~3% framing
        in R2-A/R2-D findings doc Sec 2.1)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "variable_name",
                "binding_sweep_point",
                "max_delta_aplus",
                "drill_down_watch_aplus_count",
                "non_watch_transition_gap",
                "non_watch_transition_gap_pct",
                "substrate_ticker_count",
                "substrate_unique_ticker_asof_count",
                "raw_w_count",
                "filtered_w_count",
                "filtered_density",
                "canonical_survival_rate",
                "density_delta_vs_baseline",
                "regime_return_90d_median",
                "regime_atr_pct_20d_median",
                "regime_high_52w_proximity_pct_median",
                "dominant_sector",
            ]
        )
        for s in signals:
            w.writerow(
                [
                    s.variable_name,
                    s.binding_sweep_point,
                    s.max_delta_aplus,
                    s.drill_down_watch_aplus_count,
                    s.non_watch_transition_gap,
                    f"{s.non_watch_transition_gap_pct:.2f}",
                    s.substrate_ticker_count,
                    s.substrate_unique_ticker_asof_count,
                    s.raw_w_count,
                    s.filtered_w_count,
                    "" if s.filtered_density is None else f"{s.filtered_density:.6f}",
                    "" if s.canonical_survival_rate is None
                    else f"{s.canonical_survival_rate:.6f}",
                    "" if s.density_delta_vs_baseline is None
                    else f"{s.density_delta_vs_baseline:.6f}",
                    "" if s.regime_return_90d_median is None
                    else f"{s.regime_return_90d_median:.4f}",
                    "" if s.regime_atr_pct_20d_median is None
                    else f"{s.regime_atr_pct_20d_median:.4f}",
                    "" if s.regime_high_52w_proximity_pct_median is None
                    else f"{s.regime_high_52w_proximity_pct_median:.4f}",
                    s.dominant_sector,
                ]
            )


def write_substrate_characterization_csv(
    per_variable_per_ticker: dict[str, list[PerTickerMetrics]],
    path: Path,
) -> None:
    """Emit substrate_characterization.csv (per-(variable, ticker) metrics)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "variable_name",
                "ticker",
                "asof_date",
                "return_90d_pct",
                "atr_pct_20d",
                "high_52w_proximity_pct",
                "sector",
            ]
        )
        for variable, rows in per_variable_per_ticker.items():
            for row in rows:
                w.writerow(
                    [
                        variable,
                        row.ticker,
                        row.asof_date.isoformat(),
                        "" if row.return_90d_pct is None
                        else f"{row.return_90d_pct:.6f}",
                        "" if row.atr_pct_20d is None
                        else f"{row.atr_pct_20d:.6f}",
                        "" if row.high_52w_proximity_pct is None
                        else f"{row.high_52w_proximity_pct:.6f}",
                        row.sector,
                    ]
                )


def write_w_density_detail_csv(
    metrics_by_variable: dict[str, WDensityMetrics], path: Path
) -> None:
    """Emit w_density_detail.csv (per-cohort dual-density framing)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "cohort_label",
                "substrate_ticker_count",
                "raw_w_count",
                "filtered_w_count",
                "filtered_density",
                "canonical_survival_rate",
                "density_delta_vs_baseline",
            ]
        )
        # D2 baseline as first row
        b = baseline_metrics_snapshot()
        w.writerow(
            [
                b.cohort_label,
                b.substrate_ticker_count,
                b.raw_w_count,
                b.filtered_w_count,
                f"{b.filtered_density:.6f}",
                "" if b.canonical_survival_rate is None
                else f"{b.canonical_survival_rate:.6f}",
                f"{b.density_delta_vs_baseline:.6f}",
            ]
        )
        for variable, m in metrics_by_variable.items():
            w.writerow(
                [
                    variable,
                    m.substrate_ticker_count,
                    m.raw_w_count,
                    m.filtered_w_count,
                    "" if m.filtered_density is None
                    else f"{m.filtered_density:.6f}",
                    "" if m.canonical_survival_rate is None
                    else f"{m.canonical_survival_rate:.6f}",
                    "" if m.density_delta_vs_baseline is None
                    else f"{m.density_delta_vs_baseline:.6f}",
                ]
            )


def write_manifest(
    manifest_path: Path,
    *,
    run_ts_utc: str,
    canonical_source_path: str,
    canonical_source_sha256: str,
    cohort_paths_by_variable: dict[str, str],
    d2_baseline_manifest_path: str,
    d2_baseline_universe_size: int,
    d2_baseline_filtered_w_count: int,
    canonical_composite_threshold: float,
    canonical_recency_days: int,
    compatibility_label: str,
) -> None:
    """Emit manifest.json for the V2-selection-mechanic smoke artifact."""
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "investigation": "v2-selection-mechanic-analysis",
        "investigation_type": "analytical_exploratory",
        "run_ts_utc": run_ts_utc,
        "canonical_source_path": canonical_source_path,
        "canonical_source_sha256": canonical_source_sha256,
        "cohort_paths_by_variable": cohort_paths_by_variable,
        "d2_baseline_manifest_path": d2_baseline_manifest_path,
        "d2_baseline_universe_size": d2_baseline_universe_size,
        "d2_baseline_filtered_w_count": d2_baseline_filtered_w_count,
        "canonical_composite_threshold": canonical_composite_threshold,
        "canonical_recency_days": canonical_recency_days,
        "compatibility_label": compatibility_label,
        "l2_lock_preserved": True,
        "schwab_api_calls": 0,
        "yfinance_fetches": 0,
        "production_swing_writes": 0,
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _now_iso_utc() -> tuple[datetime, str]:
    """Return (datetime, ISO-8601 string) for use as smoke artifact timestamp."""
    dt = datetime.now(timezone.utc)
    iso = dt.strftime("%Y%m%dT%H%M%SZ")
    return dt, iso


def _detect_substrate(
    cohort_csv_path: Path,
    *,
    db_path: Path,
    detect_out_root: Path,
    template_match_mode: str = "on",
) -> Path:
    """Invoke pattern_cohort_evaluator.run_harness against a cohort CSV.

    Returns the results.csv path emitted by the detection harness. The
    harness writes manifest.json + summary.md + results.csv to a fresh
    timestamped subdirectory under detect_out_root.

    L2 LOCK preserved: pattern_cohort_evaluator is the canonical
    Phase 13 detection harness; we invoke it via its public API + read
    only its emitted artifacts. ZERO production swing/ writes; ZERO
    Schwab API calls; the harness reads OHLCV from legacy parquet
    archives via its existing ohlcv_reader.
    """
    from research.harness.pattern_cohort_evaluator.run import run_harness

    results_csv, _summary_md, _manifest_json = run_harness(
        cohort_csv=cohort_csv_path,
        cohort_inline=None,
        db_path=db_path,
        output_dir=detect_out_root,
        window_mode="per-window",
        template_match_mode=template_match_mode,
        cli_pattern_class_filter=("double_bottom_w",),
    )
    return results_csv


def _primary_verdicts_from_results_csv(results_csv: Path) -> list[WPrimaryVerdict]:
    """Extract double_bottom_w primary verdicts from a pattern_cohort_evaluator
    results.csv via D1 backtest helper `extract_primary_verdicts_from_csv`.

    Reuses the D1 PrimaryVerdict -> WPrimaryVerdict shape conversion;
    the D1 helper handles structural_evidence_json parsing + per-(ticker,
    trough_1_date) highest-composite dedup. The output is then passed
    through the V2-selection-mechanic canonical filter + 5-BD adjacency
    merge (in run_analysis -> apply_canonical_filter + merge_adjacency_5bd).
    """
    from research.harness.double_bottom_w_backtest.cohort import (
        extract_primary_verdicts_from_csv,
    )

    # Use composite threshold 0.0 to extract ALL D1 primaries; the
    # canonical filter (0.5) is applied downstream via apply_canonical_filter.
    primaries = extract_primary_verdicts_from_csv(
        results_csv, composite_threshold=0.0
    )
    return [
        WPrimaryVerdict(
            ticker=p.ticker.upper(),
            anchor_asof_date=p.anchor_asof_date,
            trough_1_date=p.trough_1_date,
            trough_2_date=p.trough_2_date,
            composite_score=p.composite_score,
        )
        for p in primaries
    ]


def _execute_full_run(
    out_root: Path,
    iso: str,
    *,
    db_path: Path,
    cache_dir: Path,
    finviz_sector_map: dict[str, str] | None = None,
) -> int:
    """Full-run mode: invoke detection per substrate; emit smoke artifact dir.

    Returns 0 on success; non-zero on any failure.
    """
    smoke_dir = out_root / f"v2-selection-mechanic-analysis-{iso}"
    detect_out_root = smoke_dir / "detection_runs"
    detect_out_root.mkdir(parents=True, exist_ok=True)

    cohort_pairs_by_variable: dict[str, list[tuple[str, date]]] = {}
    verdicts_by_variable: dict[str, list[WPrimaryVerdict]] = {}

    for variable in DEFAULT_COHORT_CSV_BY_VARIABLE:
        cohort_csv_path = Path(DEFAULT_COHORT_CSV_BY_VARIABLE[variable])
        pairs = read_cohort_csv(cohort_csv_path)
        cohort_pairs_by_variable[variable] = pairs

        print(
            f"  detection: {variable} ({len(pairs)} (ticker, asof) pairs) ...",
            flush=True,
        )
        results_csv = _detect_substrate(
            cohort_csv_path,
            db_path=db_path,
            detect_out_root=detect_out_root,
        )
        primaries = _primary_verdicts_from_results_csv(results_csv)
        verdicts_by_variable[variable] = primaries
        print(f"    -> {len(primaries)} double_bottom_w primaries extracted")

    print("  substrate characterization + W-density + synthesis ...", flush=True)
    # Run pure analytical pipeline + capture per-ticker metrics for CSV emission
    per_variable_per_ticker: dict[str, list[PerTickerMetrics]] = {}
    w_density_by_variable: dict[str, "WDensityMetrics"] = {}
    for variable in DEFAULT_COHORT_CSV_BY_VARIABLE:
        per_ticker, _aggregate = compute_cohort_characterization(
            cohort_label=variable,
            ticker_asof_pairs=cohort_pairs_by_variable[variable],
            cache_dir=cache_dir,
            finviz_sector_map=finviz_sector_map,
        )
        per_variable_per_ticker[variable] = per_ticker

    synthesis_result = run_analysis(
        cohort_pairs_by_variable=cohort_pairs_by_variable,
        verdicts_by_variable=verdicts_by_variable,
        cache_dir=cache_dir,
        finviz_sector_map=finviz_sector_map,
    )

    # Map per-variable W-density metrics back from synthesis output
    for sig in synthesis_result.per_variable_signal_table:
        from research.harness.v2_selection_mechanic.w_density_analysis import WDensityMetrics
        w_density_by_variable[sig.variable_name] = WDensityMetrics(
            cohort_label=sig.variable_name,
            substrate_ticker_count=sig.substrate_ticker_count,
            raw_w_count=sig.raw_w_count,
            filtered_w_count=sig.filtered_w_count,
            filtered_density=sig.filtered_density,
            canonical_survival_rate=sig.canonical_survival_rate,
            density_delta_vs_baseline=sig.density_delta_vs_baseline,
        )

    # Emit artifacts
    write_per_variable_signal_csv(
        synthesis_result.per_variable_signal_table,
        smoke_dir / "per_variable_signals.csv",
    )
    write_substrate_characterization_csv(
        per_variable_per_ticker,
        smoke_dir / "substrate_characterization.csv",
    )
    write_w_density_detail_csv(
        w_density_by_variable,
        smoke_dir / "w_density_detail.csv",
    )
    (smoke_dir / "compatibility_synthesis.md").write_text(
        synthesis_result.narrative_markdown, encoding="utf-8"
    )
    write_manifest(
        smoke_dir / "manifest.json",
        run_ts_utc=iso,
        canonical_source_path=CANONICAL_SOURCE_PATH,
        canonical_source_sha256=CANONICAL_SOURCE_SHA256,
        cohort_paths_by_variable=dict(DEFAULT_COHORT_CSV_BY_VARIABLE),
        d2_baseline_manifest_path=D2_BASELINE_MANIFEST_PATH,
        d2_baseline_universe_size=D2_BASELINE_UNIVERSE_SIZE,
        d2_baseline_filtered_w_count=D2_BASELINE_FILTERED_W_COUNT,
        canonical_composite_threshold=CANONICAL_COMPOSITE_THRESHOLD,
        canonical_recency_days=CANONICAL_RECENCY_DAYS,
        compatibility_label=synthesis_result.categorical_label,
    )
    # Emit a brief summary.md alongside manifest.json
    summary_lines = [
        "# V2-Selection-Mechanic Smoke Run Summary",
        "",
        f"Run timestamp (UTC): {iso}",
        f"Compatibility categorical label: {synthesis_result.categorical_label}",
        f"Substrates analyzed: {len(synthesis_result.per_variable_signal_table)}",
        f"Below-baseline density count: {synthesis_result.negative_delta_count}",
        f"At-or-above-baseline density count: {synthesis_result.positive_or_zero_delta_count}",
        "",
        "Detection runs emitted under detection_runs/ subdirectory (one per substrate).",
        "Analytical CSVs + compatibility narrative emitted alongside manifest.json.",
    ]
    (smoke_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"OK: emitted smoke artifact at {smoke_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint -- emits smoke artifact directory.

    Two modes:
      --dry-run : V1 placeholder mode (validates cohort CSV presence +
                  canonical source SHA + emits placeholder manifest).
      --execute : full-run mode (invokes pattern_cohort_evaluator per
                  substrate; computes W-density + substrate
                  characterization + compatibility synthesis; emits
                  full artifact directory).
    """
    parser = argparse.ArgumentParser(
        description="V2-selection-mechanic analytical investigation orchestrator"
    )
    parser.add_argument(
        "--out-root",
        default="exports/research",
        help="Root directory for smoke artifact emission (default: exports/research)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "V1 placeholder mode: validates cohort CSV presence + canonical "
            "source SHA + emits manifest with empty detection results."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Full-run mode: invoke pattern_cohort_evaluator per substrate; "
            "compute analytical surfaces; emit full smoke artifact directory."
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path.home() / "swing-data" / "swing.db",
        help="Path to swing.db (required for --execute; default ~/swing-data/swing.db)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / "swing-data" / "prices-cache",
        help="OHLCV legacy parquet cache dir (default ~/swing-data/prices-cache)",
    )
    parser.add_argument(
        "--finviz-csv",
        type=Path,
        default=None,
        help=(
            "Optional finviz CSV path for sector resolution. If unset, all "
            "tickers resolve to UNKNOWN_SECTOR per V1 simplification."
        ),
    )
    args = parser.parse_args(argv)

    if args.dry_run and args.execute:
        print("ERROR: --dry-run and --execute are mutually exclusive", file=sys.stderr)
        return 2

    if not args.dry_run and not args.execute:
        print(
            "ERROR: specify either --dry-run (V1 placeholder) or --execute "
            "(full-run; requires --db pointing to a populated swing.db).",
            file=sys.stderr,
        )
        return 2

    out_root = Path(args.out_root)
    _, iso = _now_iso_utc()
    smoke_dir = out_root / f"v2-selection-mechanic-analysis-{iso}"

    if args.execute:
        # Canonical source verification + cohort CSV presence (shared with
        # dry-run path; bail early if locks fail).
        canonical_source = Path(CANONICAL_SOURCE_PATH)
        if not canonical_source.exists():
            print(
                f"ERROR: canonical source artifact not found at {canonical_source}",
                file=sys.stderr,
            )
            return 2
        import hashlib
        h = hashlib.sha256()
        with canonical_source.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        if h.hexdigest() != CANONICAL_SOURCE_SHA256:
            print(
                f"ERROR: canonical source SHA mismatch at {canonical_source}",
                file=sys.stderr,
            )
            return 2
        if not args.db.exists():
            print(
                f"ERROR: swing.db not found at {args.db}; --execute requires "
                f"the production DB for exemplar corpus loading.",
                file=sys.stderr,
            )
            return 2
        if not args.cache_dir.exists():
            print(
                f"ERROR: OHLCV cache dir not found at {args.cache_dir}",
                file=sys.stderr,
            )
            return 2
        # Optional finviz sector map
        finviz_sector_map = (
            load_sector_map_from_finviz_csv(args.finviz_csv)
            if args.finviz_csv is not None
            else None
        )
        return _execute_full_run(
            out_root,
            iso,
            db_path=args.db,
            cache_dir=args.cache_dir,
            finviz_sector_map=finviz_sector_map,
        )

    # Codex R1 MAJOR #2 fix: verify canonical source SHA in dry-run mode.
    # Prior implementation advertised SHA validation in module docstring
    # but main() never read CANONICAL_SOURCE_PATH or hashed it; a missing
    # / tampered source could still emit a manifest with the locked SHA
    # constant.
    canonical_source = Path(CANONICAL_SOURCE_PATH)
    if not canonical_source.exists():
        print(
            f"ERROR: canonical source artifact not found at "
            f"{canonical_source}. Brief Sec 6(d): CLEAR ERROR + halt.",
            file=sys.stderr,
        )
        return 2
    import hashlib
    h = hashlib.sha256()
    with canonical_source.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    actual_sha = h.hexdigest()
    if actual_sha != CANONICAL_SOURCE_SHA256:
        print(
            f"ERROR: canonical source SHA mismatch at {canonical_source}: "
            f"actual={actual_sha} vs locked={CANONICAL_SOURCE_SHA256}",
            file=sys.stderr,
        )
        return 2

    # Validate cohort CSV presence (per dispatch brief Sec 5.1)
    missing: list[str] = []
    for variable, path_str in DEFAULT_COHORT_CSV_BY_VARIABLE.items():
        if not Path(path_str).exists():
            missing.append(f"{variable}: {path_str}")
    if missing:
        print(
            "ERROR: missing cohort CSV(s):\n  " + "\n  ".join(missing),
            file=sys.stderr,
        )
        return 2

    # Emit a placeholder manifest (slice 5 will populate the analytical fields)
    write_manifest(
        smoke_dir / "manifest.json",
        run_ts_utc=iso,
        canonical_source_path=CANONICAL_SOURCE_PATH,
        canonical_source_sha256=CANONICAL_SOURCE_SHA256,
        cohort_paths_by_variable=dict(DEFAULT_COHORT_CSV_BY_VARIABLE),
        d2_baseline_manifest_path=D2_BASELINE_MANIFEST_PATH,
        d2_baseline_universe_size=D2_BASELINE_UNIVERSE_SIZE,
        d2_baseline_filtered_w_count=D2_BASELINE_FILTERED_W_COUNT,
        canonical_composite_threshold=CANONICAL_COMPOSITE_THRESHOLD,
        canonical_recency_days=CANONICAL_RECENCY_DAYS,
        compatibility_label="DRY_RUN_PENDING_DETECTION_SLICE_5",
    )
    print(f"OK: emitted dry-run smoke artifact at {smoke_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
