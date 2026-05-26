"""Operator-facing regeneration entrypoint for R2-A cohort artifacts.

Run via:

  python -m research.harness.r2a_tightness_days_required.regenerate_cohort

Reads the canonical V2 sensitivity smoke artifact at
`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`,
emits the cohort CSV + audit JSON sibling at
`exports/research/cohorts/r2a_tightness_days_required_sp1.csv` and
`*.flips_audit.json`. Validates the canonical 15/7/7 cohort
identity via the layered verifier; raises CohortExtractionError on
any deviation.

This is the SINGLE canonical generation path -- the committed
cohort artifacts MUST be regenerated through this entrypoint when
the upstream V2 sensitivity artifact changes (Codex R4.minor#3).

ZERO production swing/ writes; ZERO new Schwab API calls (L2 LOCK).
"""
from __future__ import annotations

import sys
from pathlib import Path

from research.harness.r2a_tightness_days_required.cohort_csv import (
    generate_r2a_cohort_artifacts,
)


DEFAULT_SOURCE = Path(
    "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
)
DEFAULT_COHORT_CSV = Path(
    "exports/research/cohorts/r2a_tightness_days_required_sp1.csv"
)


def main(argv: list[str] | None = None) -> int:
    """Regenerate the R2-A cohort artifacts in-place.

    Returns 0 on success; raises CohortExtractionError on any
    deviation from the canonical 15/7/7 cohort.
    """
    argv = sys.argv[1:] if argv is None else argv
    source = Path(argv[0]) if argv else DEFAULT_SOURCE
    csv_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_COHORT_CSV
    artifacts = generate_r2a_cohort_artifacts(
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
