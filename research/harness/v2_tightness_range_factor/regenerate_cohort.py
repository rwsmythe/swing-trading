"""Operator-facing regeneration entrypoint for V2 tightness_range_factor cohort artifacts.

Run via:

  python -m research.harness.v2_tightness_range_factor.regenerate_cohort

Reads the canonical V2 sensitivity smoke artifact at
`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`,
emits the cohort CSV + audit JSON sibling at
`exports/research/cohorts/v2_tightness_range_factor_sp1_005.csv` and
`*.flips_audit.json`. Validates the canonical 67/15/29 cohort
identity via the layered verifier; raises CohortExtractionError on
any deviation.

This is the SINGLE canonical generation path -- the committed
cohort artifacts MUST be regenerated through this entrypoint when
the upstream V2 sensitivity artifact changes.

By default the entrypoint enforces:
  - Source artifact SHA-256 + size match the canonical lock
  - Output paths match the canonical defaults

Both restrictions can be relaxed via --allow-non-canonical-paths
(operator-explicit opt-out for V2 / next-arc regeneration against
an updated source artifact).

ZERO production swing/ writes; ZERO new Schwab API calls (L2 LOCK).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from research.harness.v2_tightness_range_factor.cohort_csv import (
    generate_v2trf_cohort_artifacts,
)


DEFAULT_SOURCE = Path(
    "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
)
DEFAULT_COHORT_CSV = Path(
    "exports/research/cohorts/v2_tightness_range_factor_sp1_005.csv"
)


def main(argv: list[str] | None = None) -> int:
    """Regenerate the V2-TRF cohort artifacts in-place.

    Returns 0 on success; raises CohortExtractionError on any
    deviation from the canonical 67/15/29 cohort.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the canonical V2 tightness_range_factor cohort "
            "artifacts. Enforces canonical source SHA + canonical output "
            "paths by default."
        ),
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=str(DEFAULT_SOURCE),
        help=(
            "Path to the V2 sensitivity markdown source. Default: "
            f"{DEFAULT_SOURCE.as_posix()}. Non-default values require "
            "--allow-non-canonical-paths."
        ),
    )
    parser.add_argument(
        "cohort_csv",
        nargs="?",
        default=str(DEFAULT_COHORT_CSV),
        help=(
            "Output cohort CSV path. Default: "
            f"{DEFAULT_COHORT_CSV.as_posix()}. Non-default values require "
            "--allow-non-canonical-paths."
        ),
    )
    parser.add_argument(
        "--allow-non-canonical-paths",
        action="store_true",
        help=(
            "Permit non-default source / output paths AND skip the canonical "
            "source SHA-256 + size lock. The cohort-identity layered verifier "
            "still fires (the 67/15/29 EXPECTED_FLIPS / EXPECTED_TICKER_ASOF "
            "check is non-optional). Use this for V2 / next-arc regeneration "
            "against an updated source artifact. NOT INTENDED FOR ROUTINE USE."
        ),
    )
    args = parser.parse_args(argv)

    source = Path(args.source)
    csv_path = Path(args.cohort_csv)

    if not args.allow_non_canonical_paths:
        if source.as_posix() != DEFAULT_SOURCE.as_posix():
            print(
                f"ERROR: non-default source path {source.as_posix()!r} requires "
                f"--allow-non-canonical-paths. Canonical source: "
                f"{DEFAULT_SOURCE.as_posix()!r}",
                file=sys.stderr,
            )
            return 2
        if csv_path.as_posix() != DEFAULT_COHORT_CSV.as_posix():
            print(
                f"ERROR: non-default cohort CSV path {csv_path.as_posix()!r} "
                f"requires --allow-non-canonical-paths. Canonical CSV: "
                f"{DEFAULT_COHORT_CSV.as_posix()!r}",
                file=sys.stderr,
            )
            return 2

    artifacts = generate_v2trf_cohort_artifacts(
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
