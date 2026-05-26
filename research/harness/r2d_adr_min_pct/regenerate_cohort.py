"""Operator-facing regeneration entrypoint for R2-D cohort artifacts.

Run via:

  python -m research.harness.r2d_adr_min_pct.regenerate_cohort

Reads the canonical V2 sensitivity smoke artifact at
`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`,
emits the cohort CSV + audit JSON sibling at
`exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv` and
`*.flips_audit.json`. Validates the canonical 11/4/4 cohort
identity via the layered verifier; raises CohortExtractionError on
any deviation.

This is the SINGLE canonical generation path -- the committed
cohort artifacts MUST be regenerated through this entrypoint when
the upstream V2 sensitivity artifact changes (R4.minor#3 inherited
from R2-A).

ZERO production swing/ writes; ZERO new Schwab API calls (L2 LOCK).
"""
from __future__ import annotations

import sys
from pathlib import Path

from research.harness.r2d_adr_min_pct.cohort_csv import (
    generate_r2d_cohort_artifacts,
)


DEFAULT_SOURCE = Path(
    "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
)
DEFAULT_COHORT_CSV = Path(
    "exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv"
)


def main(argv: list[str] | None = None) -> int:
    """Regenerate the R2-D cohort artifacts in-place.

    Returns 0 on success; raises CohortExtractionError on any
    deviation from the canonical 11/4/4 cohort.
    """
    argv = sys.argv[1:] if argv is None else argv
    source = Path(argv[0]) if argv else DEFAULT_SOURCE
    csv_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_COHORT_CSV
    artifacts = generate_r2d_cohort_artifacts(
        source_sensitivity_md=source,
        cohort_csv_path=csv_path,
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
