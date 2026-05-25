"""Pattern cohort detector evaluator harness CLI entry point.

Invoke via `python -m research.harness.pattern_cohort_evaluator.run
--cohort-csv PATH --db PATH --output-dir DIR` OR via
`swing diagnose pattern-cohort-detect` which delegates here.

L2 LOCK preserved: NO imports of forbidden modules (yfinance, schwabdev,
swing.integrations.schwab, swing.data.ohlcv_archive). DB opened via URI
mode=ro per V2 OHLCV Codex R2.M2 RESOLVED.
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from research.harness.pattern_cohort_evaluator import __version__
from research.harness.pattern_cohort_evaluator.cohort_reader import (
    CohortEntry,
    parse_inline_cohort,
    read_cohort_csv,
)
from research.harness.pattern_cohort_evaluator.detector_invoker import (
    invoke_cohort,
)
from research.harness.pattern_cohort_evaluator.exceptions import (
    BothCohortModesSuppliedError,
    NeitherCohortModeSuppliedError,
)
from research.harness.pattern_cohort_evaluator.output import (
    write_manifest_json,
    write_results_csv,
    write_summary_markdown,
)
from swing.config import Config


def _get_cfg() -> Config:
    """Load production cfg via Config.from_defaults().

    Isolated to a module-level helper so tests can monkeypatch it without
    importing run.py's internals directly. Mirrors V2 OHLCV evaluator precedent.
    """
    return Config.from_defaults()


def _resolve_cohort(
    cohort_csv: Path | None,
    cohort_inline: str | None,
) -> tuple[tuple[CohortEntry, ...], str, Path | None]:
    """Resolve cohort entries from Mode (a) or Mode (b) inputs.

    Raises:
      BothCohortModesSuppliedError: both flags supplied.
      NeitherCohortModeSuppliedError: neither flag supplied.
    """
    if cohort_csv is not None and cohort_inline is not None:
        raise BothCohortModesSuppliedError(
            "Exactly one of --cohort-csv or --cohort-inline required; "
            "both supplied"
        )
    if cohort_csv is None and cohort_inline is None:
        raise NeitherCohortModeSuppliedError(
            "Exactly one of --cohort-csv or --cohort-inline required; "
            "neither supplied"
        )
    if cohort_csv is not None:
        return read_cohort_csv(cohort_csv), "csv", cohort_csv
    assert cohort_inline is not None
    return parse_inline_cohort(cohort_inline), "inline", None


def run_harness(
    *,
    cohort_csv: Path | None,
    cohort_inline: str | None,
    db_path: Path,
    output_dir: Path,
    window_mode: str = "per-window",
    template_match_mode: str = "on",
    cli_pattern_class_filter: tuple[str, ...] | None = None,
) -> tuple[Path, Path, Path]:
    """Run the cohort harness + emit results CSV + summary markdown +
    manifest JSON into a fresh timestamped subdirectory under output_dir.

    Returns: (results_csv_path, summary_md_path, manifest_json_path).

    DB connection: opens via URI mode=ro per V2 OHLCV Codex R2.M2 precedent.
    """
    if window_mode not in ("last-only", "per-window"):
        raise ValueError(
            f"window_mode must be 'last-only' or 'per-window'; got {window_mode!r}"
        )
    if template_match_mode not in ("on", "off"):
        raise ValueError(
            f"template_match_mode must be 'on' or 'off'; got "
            f"{template_match_mode!r}"
        )
    if cli_pattern_class_filter is not None:
        from research.harness.pattern_cohort_evaluator.cohort_reader import (
            _ALLOWED_PATTERN_CLASSES,
        )
        unknown = [
            n for n in cli_pattern_class_filter
            if n not in _ALLOWED_PATTERN_CLASSES
        ]
        if unknown:
            raise ValueError(
                f"cli_pattern_class_filter contains unknown pattern_class names: "
                f"{unknown}; allowed: {sorted(_ALLOWED_PATTERN_CLASSES)}"
            )

    cohort, mode, cohort_path = _resolve_cohort(cohort_csv, cohort_inline)

    cfg = _get_cfg()
    cache_dir = cfg.paths.prices_cache_dir

    db_uri = db_path.resolve().as_uri() + "?mode=ro"
    started_iso = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(db_uri, uri=True)
    try:
        result = invoke_cohort(
            cohort,
            conn=conn,
            cache_dir=cache_dir,
            window_mode=window_mode,  # type: ignore[arg-type]
            template_match_mode=template_match_mode,  # type: ignore[arg-type]
            cli_pattern_class_filter=cli_pattern_class_filter,
        )
    finally:
        conn.close()
    finished_iso = datetime.now(UTC).isoformat()

    iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / f"pattern-cohort-detection-{iso}"
    run_dir.mkdir(parents=True, exist_ok=True)
    results_csv_path = run_dir / "results.csv"
    summary_md_path = run_dir / "summary.md"
    manifest_json_path = run_dir / "manifest.json"

    write_results_csv(result, results_csv_path)
    write_summary_markdown(
        result,
        summary_md_path,
        cohort_input_mode=mode,
        cohort_input_path=cohort_path,
        harness_version=__version__,
    )
    write_manifest_json(
        result,
        manifest_json_path,
        cohort_input_mode=mode,
        cohort_input_path=cohort_path,
        cache_dir=cache_dir,
        db_path=db_path,
        harness_version=__version__,
        started_at_utc=started_iso,
        finished_at_utc=finished_iso,
    )
    return results_csv_path, summary_md_path, manifest_json_path


def main(argv: list[str] | None = None) -> int:
    """argparse main for direct `python -m` invocation."""
    parser = argparse.ArgumentParser(
        description="Pattern cohort detector evaluator harness.",
    )
    cohort_group = parser.add_mutually_exclusive_group(required=False)
    cohort_group.add_argument(
        "--cohort-csv", type=Path, default=None, dest="cohort_csv",
    )
    cohort_group.add_argument(
        "--cohort-inline", type=str, default=None, dest="cohort_inline",
    )
    parser.add_argument("--db", required=True, type=Path, dest="db_path")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("exports/research"),
    )
    parser.add_argument(
        "--window-mode", choices=("last-only", "per-window"),
        default="per-window",
    )
    parser.add_argument(
        "--template-match", choices=("on", "off"), default="on",
        dest="template_match_mode",
    )
    parser.add_argument(
        "--pattern-class-filter", type=str, default=None,
        help="Comma-separated pattern_class filter.",
    )
    args = parser.parse_args(argv)

    filter_tuple: tuple[str, ...] | None = None
    if args.pattern_class_filter:
        filter_tuple = tuple(
            s.strip() for s in args.pattern_class_filter.split(",") if s.strip()
        )

    try:
        results_path, md_path, manifest_path = run_harness(
            cohort_csv=args.cohort_csv,
            cohort_inline=args.cohort_inline,
            db_path=args.db_path,
            output_dir=args.output_dir,
            window_mode=args.window_mode,
            template_match_mode=args.template_match_mode,
            cli_pattern_class_filter=filter_tuple,
        )
    except (
        ValueError,
        BothCohortModesSuppliedError,
        NeitherCohortModeSuppliedError,
    ) as exc:
        parser.error(str(exc))
        return 1  # unreachable

    print(f"Results CSV: {results_path}")
    print(f"Summary MD:  {md_path}")
    print(f"Manifest:    {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
