"""Locks the COMMITTED R2-D cohort artifacts (CSV + audit JSON) against
the canonical 11/4/4 truth source (vcp.adr_min_pct at sweep_point=2.0).

The strict verifier protects regenerated output at runtime, but a stale
or hand-edited cohort CSV / audit JSON could sit in the repo while tests
pass (the real-artifact tests skip if the V2 sensitivity markdown is
absent). These tests read the COMMITTED artifacts directly and assert
canonical equality.

If these tests fail, regenerate the artifacts via the canonical
entrypoint:

  python -m research.harness.r2d_adr_min_pct.regenerate_cohort

The entrypoint validates the canonical 11/4/4 cohort identity via the
layered verifier; CohortExtractionError on deviation.
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from research.harness.r2d_adr_min_pct.cohort_csv import (
    CANONICAL_SOURCE_SHA256,
    CANONICAL_SOURCE_SIZE_BYTES,
    EXPECTED_FLIP_COUNT,
    EXPECTED_FLIPS,
    EXPECTED_TICKER_ASOF,
    R2D_COHORT_LABEL,
    R2D_NEW_BUCKET,
    R2D_OLD_BUCKET,
    R2D_SWEEP_POINT,
    R2D_VARIABLE_NAME,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
COHORT_CSV = REPO_ROOT / "exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv"
AUDIT_JSON = REPO_ROOT / "exports/research/cohorts/r2d_adr_min_pct_sp2_0.flips_audit.json"
SOURCE_SENSITIVITY_MD = (
    REPO_ROOT
    / "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
)


def test_committed_cohort_csv_matches_canonical_ticker_asof_set() -> None:
    """The COMMITTED cohort CSV at exports/research/cohorts/ MUST encode
    exactly EXPECTED_TICKER_ASOF (4 tuples). A stale file would fail
    this assertion.

    Also asserts:
      - Row count exactly equals len(EXPECTED_TICKER_ASOF) -- defends
        against duplicate-row contamination that preserves the unique
        set but inflates row count.
      - Pairs-as-set equals rows-as-set -- no within-CSV duplicates.
    """
    assert COHORT_CSV.exists(), f"committed cohort CSV missing at {COHORT_CSV}"
    with COHORT_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(EXPECTED_TICKER_ASOF), (
        f"committed cohort CSV row count={len(rows)}, expected "
        f"{len(EXPECTED_TICKER_ASOF)} -- duplicate rows would inflate "
        f"this without breaking the set-equality check"
    )
    pairs = {(r["ticker"], date.fromisoformat(r["asof_date"])) for r in rows}
    assert len(pairs) == len(rows), (
        f"committed cohort CSV contains duplicate rows: "
        f"{len(rows)} rows vs {len(pairs)} unique (ticker, asof) pairs"
    )
    assert pairs == EXPECTED_TICKER_ASOF, (
        f"committed cohort CSV deviates from canonical EXPECTED_TICKER_ASOF; "
        f"missing={sorted(EXPECTED_TICKER_ASOF - pairs)}, "
        f"extra={sorted(pairs - EXPECTED_TICKER_ASOF)}"
    )
    # Cohort label uniform
    assert all(r["cohort_label"] == R2D_COHORT_LABEL for r in rows)


def test_committed_audit_json_matches_canonical_flips() -> None:
    """The COMMITTED audit JSON at exports/research/cohorts/ MUST encode
    exactly EXPECTED_FLIPS (11 raw triples). A stale file would fail
    this assertion.

    Also asserts:
      - len(payload["flips"]) exactly matches flip_count + EXPECTED_FLIP_COUNT
        (defends against duplicate-row inflation preserving the set).
      - Metadata fields variable_name / sweep_point / old_bucket /
        new_bucket / cohort_label exactly match the module-level
        constants (defends against falsified-metadata sidecars where
        the raw flips are canonical but the selection method is
        mis-described).
    """
    assert AUDIT_JSON.exists(), f"committed audit JSON missing at {AUDIT_JSON}"
    payload = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert payload["flip_count"] == EXPECTED_FLIP_COUNT
    assert len(payload["flips"]) == EXPECTED_FLIP_COUNT, (
        f"audit JSON flips list length={len(payload['flips'])} but "
        f"flip_count={payload['flip_count']}; duplicate rows would "
        f"inflate the list while the set comparison still passed"
    )
    # Metadata fields
    assert payload["variable_name"] == R2D_VARIABLE_NAME
    assert payload["sweep_point"] == R2D_SWEEP_POINT
    assert payload["old_bucket"] == R2D_OLD_BUCKET
    assert payload["new_bucket"] == R2D_NEW_BUCKET
    assert payload["cohort_label"] == R2D_COHORT_LABEL
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
    """Unconditional SHA + size lock against the canonical V2 sensitivity
    smoke artifact (2026-05-24). Does NOT depend on the source artifact
    being present on disk -- locks the COMMITTED audit JSON's source
    identity claim, so stale audit JSON with an old SHA would fail here
    even if the source file was absent.
    """
    assert AUDIT_JSON.exists(), f"committed audit JSON missing at {AUDIT_JSON}"
    payload = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert payload["source_sensitivity_md_sha256"] == CANONICAL_SOURCE_SHA256, (
        f"committed audit JSON source SHA={payload['source_sensitivity_md_sha256']!r} "
        f"does not match canonical SHA={CANONICAL_SOURCE_SHA256!r}; "
        f"regenerate cohort artifacts or update CANONICAL_SOURCE_SHA256"
    )
    assert payload["source_sensitivity_md_size_bytes"] == (
        CANONICAL_SOURCE_SIZE_BYTES
    )


def test_committed_audit_json_source_sha_matches_disk_when_present() -> None:
    """Stronger check when the V2 sensitivity source artifact IS present
    on disk: re-hashes the actual file and asserts the audit JSON's
    SHA matches. Skips when artifact absent.
    """
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
    """Audit JSON source path MUST be POSIX (forward slashes) for
    cross-platform portability."""
    payload = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert "\\" not in payload["source_sensitivity_md"], (
        f"audit JSON source path contains backslashes: "
        f"{payload['source_sensitivity_md']!r}; expected POSIX path"
    )
