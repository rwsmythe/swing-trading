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
        w_density = compute_w_density(
            cohort_label=variable_name,
            substrate_tickers=tickers,
            canonical_filtered_verdicts=merged,
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
    """Emit per_variable_signals.csv (Sec 3.2)."""
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
                "filtered_w_count",
                "filtered_density",
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
                    s.filtered_w_count,
                    "" if s.filtered_density is None else f"{s.filtered_density:.6f}",
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
    """Emit w_density_detail.csv (per-cohort F/T/D_filt/delta)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "cohort_label",
                "substrate_ticker_count",
                "filtered_w_count",
                "filtered_density",
                "density_delta_vs_baseline",
            ]
        )
        # D2 baseline as first row
        b = baseline_metrics_snapshot()
        w.writerow(
            [
                b.cohort_label,
                b.substrate_ticker_count,
                b.filtered_w_count,
                f"{b.filtered_density:.6f}",
                f"{b.density_delta_vs_baseline:.6f}",
            ]
        )
        for variable, m in metrics_by_variable.items():
            w.writerow(
                [
                    variable,
                    m.substrate_ticker_count,
                    m.filtered_w_count,
                    "" if m.filtered_density is None
                    else f"{m.filtered_density:.6f}",
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


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint -- emits smoke artifact directory.

    V1: detection invocation against each substrate is delegated to a
    follow-up slice; this CLI prints a "DRY RUN" placeholder validating
    cohort CSV presence + canonical source SHA + manifest emission.
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
    args = parser.parse_args(argv)

    if not args.dry_run:
        print(
            "ERROR: full detection-invocation pipeline is delegated to slice 5; "
            "run with --dry-run for V1 placeholder mode.",
            file=sys.stderr,
        )
        return 2

    out_root = Path(args.out_root)
    _, iso = _now_iso_utc()
    smoke_dir = out_root / f"v2-selection-mechanic-analysis-{iso}"

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
