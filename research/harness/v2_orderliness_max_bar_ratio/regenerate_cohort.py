"""Operator-facing regeneration entrypoint for V2 orderliness_max_bar_ratio cohort artifacts.

Run via:

  python -m research.harness.v2_orderliness_max_bar_ratio.regenerate_cohort

Validates the canonical 1/1/1 cohort identity via the layered verifier.

ZERO production swing/ writes; ZERO new Schwab API calls (L2 LOCK).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from research.harness.v2_orderliness_max_bar_ratio.cohort_csv import (
    generate_v2obr_cohort_artifacts,
)


DEFAULT_SOURCE = Path(
    "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
)
DEFAULT_COHORT_CSV = Path(
    "exports/research/cohorts/v2_orderliness_max_bar_ratio_sp3_75.csv"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the canonical V2 orderliness_max_bar_ratio cohort artifacts."
        ),
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=str(DEFAULT_SOURCE),
        help=f"V2 sensitivity markdown source. Default: {DEFAULT_SOURCE.as_posix()}",
    )
    parser.add_argument(
        "cohort_csv",
        nargs="?",
        default=str(DEFAULT_COHORT_CSV),
        help=f"Output cohort CSV path. Default: {DEFAULT_COHORT_CSV.as_posix()}",
    )
    parser.add_argument(
        "--allow-non-canonical-paths",
        action="store_true",
        help=(
            "Permit non-default paths AND skip canonical source SHA + size lock."
        ),
    )
    args = parser.parse_args(argv)
    source = Path(args.source)
    csv_path = Path(args.cohort_csv)
    if not args.allow_non_canonical_paths:
        if source.as_posix() != DEFAULT_SOURCE.as_posix():
            print(
                f"ERROR: non-default source path {source.as_posix()!r} requires "
                f"--allow-non-canonical-paths",
                file=sys.stderr,
            )
            return 2
        if csv_path.as_posix() != DEFAULT_COHORT_CSV.as_posix():
            print(
                f"ERROR: non-default cohort CSV path {csv_path.as_posix()!r} "
                f"requires --allow-non-canonical-paths",
                file=sys.stderr,
            )
            return 2
    artifacts = generate_v2obr_cohort_artifacts(
        source_sensitivity_md=source,
        cohort_csv_path=csv_path,
        allow_non_canonical_source=args.allow_non_canonical_paths,
    )
    print(
        f"OK: wrote {artifacts.cohort_csv_path} "
        f"({artifacts.unique_ticker_asof_count} unique (ticker, asof) rows) "
        f"+ {artifacts.flips_audit_json_path} "
        f"({artifacts.raw_flip_count} raw flips)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
