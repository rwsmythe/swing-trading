"""Locks the COMMITTED R2-A cohort artifacts (CSV + audit JSON) against
the canonical 15/7/7 truth source.

Per Codex R3 MAJOR #1: the strict verifier protects regenerated output
at runtime, but a stale or hand-edited cohort CSV / audit JSON could
sit in the repo while tests pass (the real-artifact tests skip if the
V2 sensitivity markdown is absent). These tests read the COMMITTED
artifacts directly and assert canonical equality.

If these tests fail, regenerate the artifacts via:

  python -c "from pathlib import Path; \\
      from research.harness.r2a_tightness_days_required.cohort_csv \\
        import generate_r2a_cohort_artifacts; \\
      generate_r2a_cohort_artifacts( \\
        source_sensitivity_md=Path('exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md'), \\
        cohort_csv_path=Path('exports/research/cohorts/r2a_tightness_days_required_sp1.csv'))"
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from research.harness.r2a_tightness_days_required.cohort_csv import (
    EXPECTED_FLIP_COUNT,
    EXPECTED_FLIPS,
    EXPECTED_TICKER_ASOF,
    R2A_COHORT_LABEL,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
COHORT_CSV = REPO_ROOT / "exports/research/cohorts/r2a_tightness_days_required_sp1.csv"
AUDIT_JSON = REPO_ROOT / "exports/research/cohorts/r2a_tightness_days_required_sp1.flips_audit.json"
SOURCE_SENSITIVITY_MD = (
    REPO_ROOT
    / "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
)


def test_committed_cohort_csv_matches_canonical_ticker_asof_set() -> None:
    """The COMMITTED cohort CSV at exports/research/cohorts/ MUST encode
    exactly EXPECTED_TICKER_ASOF (7 tuples). A stale file would fail
    this assertion (Codex R3.M#1)."""
    assert COHORT_CSV.exists(), f"committed cohort CSV missing at {COHORT_CSV}"
    with COHORT_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    pairs = {(r["ticker"], date.fromisoformat(r["asof_date"])) for r in rows}
    assert pairs == EXPECTED_TICKER_ASOF, (
        f"committed cohort CSV deviates from canonical EXPECTED_TICKER_ASOF; "
        f"missing={sorted(EXPECTED_TICKER_ASOF - pairs)}, "
        f"extra={sorted(pairs - EXPECTED_TICKER_ASOF)}"
    )
    # Cohort label uniform
    assert all(r["cohort_label"] == R2A_COHORT_LABEL for r in rows)


def test_committed_audit_json_matches_canonical_flips() -> None:
    """The COMMITTED audit JSON at exports/research/cohorts/ MUST encode
    exactly EXPECTED_FLIPS (15 raw triples). A stale file would fail
    this assertion (Codex R3.M#1)."""
    assert AUDIT_JSON.exists(), f"committed audit JSON missing at {AUDIT_JSON}"
    payload = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert payload["flip_count"] == EXPECTED_FLIP_COUNT
    triples = {
        (f["ticker"], int(f["eval_run_id"]), date.fromisoformat(f["data_asof_date"]))
        for f in payload["flips"]
    }
    assert triples == EXPECTED_FLIPS, (
        f"committed audit JSON deviates from canonical EXPECTED_FLIPS; "
        f"missing={sorted(EXPECTED_FLIPS - triples)}, "
        f"extra={sorted(triples - EXPECTED_FLIPS)}"
    )


def test_committed_audit_json_records_canonical_source_sha256() -> None:
    """If the V2 sensitivity source artifact is present on disk, the
    committed audit JSON's source_sensitivity_md_sha256 MUST match the
    actual file's SHA-256. Stale audit JSON cited to an old artifact
    version would fail here (Codex R3.M#1 + R2.minor#3)."""
    import pytest
    if not SOURCE_SENSITIVITY_MD.exists():
        pytest.skip(f"V2 sensitivity artifact not present at {SOURCE_SENSITIVITY_MD}")
    payload = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    import hashlib
    h = hashlib.sha256()
    h.update(SOURCE_SENSITIVITY_MD.read_bytes())
    actual_sha = h.hexdigest()
    assert payload["source_sensitivity_md_sha256"] == actual_sha, (
        f"committed audit JSON source SHA mismatch: "
        f"audit={payload['source_sensitivity_md_sha256'][:16]}... "
        f"vs file={actual_sha[:16]}...; regenerate cohort artifacts"
    )
    assert payload["source_sensitivity_md_size_bytes"] == (
        SOURCE_SENSITIVITY_MD.stat().st_size
    )


def test_committed_audit_json_source_path_is_posix() -> None:
    """Codex R3.minor#3: audit JSON source path MUST be POSIX (forward
    slashes) for cross-platform portability."""
    payload = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert "\\" not in payload["source_sensitivity_md"], (
        f"audit JSON source path contains backslashes: "
        f"{payload['source_sensitivity_md']!r}; expected POSIX path"
    )
