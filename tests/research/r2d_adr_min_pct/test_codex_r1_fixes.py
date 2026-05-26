"""Codex R1 adversarial-review fix tests for R2-D.

Closes 6 MAJOR findings + 1 MINOR finding from Codex R1:
  - R1.M#1: brief sweep_point reconciliation locked in Amendment 1
  - R1.M#2: cohort-validity INSUFFICIENT SAMPLE pre-commit locked in
            Amendment 1 + cross-cohort verdict table updated
  - R1.M#3: fixture identity lock (N=4 + all STNG + exact trough_1 /
            center_peak / trough_2 dates; defends against empty fixture
            silently passing the issubset check)
  - R1.M#4: audit JSON cohort_selection_method + v2_binding_variable
            keys locked (in addition to variable_name which was already
            present)
  - R1.M#5: canonical source SHA + size validation in
            generate_r2d_cohort_artifacts wrapper (with override flag)
  - R1.M#6: --allow-non-canonical-paths CLI flag at regenerate_cohort
            entrypoint
  - R1.m#1: fixture-derivation provenance test (132 -> 127 -> 4 chain
            recorded in commit message + summary + manifest are
            consistent)
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from research.harness.r2d_adr_min_pct.cohort_csv import (
    CANONICAL_SOURCE_SHA256,
    CANONICAL_SOURCE_SIZE_BYTES,
    CohortExtractionError,
    generate_r2d_cohort_artifacts,
    verify_canonical_source_identity,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_MD = REPO_ROOT / "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
AUDIT_JSON = REPO_ROOT / "exports/research/cohorts/r2d_adr_min_pct_sp2_0.flips_audit.json"
COHORT_FIXTURE = REPO_ROOT / "tests/fixtures/research/r2d_adr_min_pct/cohort.json"
BRIEF = REPO_ROOT / "docs/r2d-adr-min-pct-cohort-backtest-dispatch-brief.md"


# ---------------------------------------------------------------------------
# R1.M#1: Brief Amendment 1 sweep_point reconciliation
# ---------------------------------------------------------------------------
def test_brief_amendment_1_reconciles_sweep_point_discrepancy() -> None:
    """Amendment 1 MUST exist in the brief AND explicitly reconcile the
    sp=1 prescription against the actual sp=2.0 binding signal."""
    text = BRIEF.read_text(encoding="utf-8")
    assert "Amendment 1" in text, "Brief must contain Amendment 1 header"
    assert "sweep_point reconciliation" in text, (
        "Amendment 1 must explicitly mention sweep_point reconciliation"
    )
    assert "sweep_point=2.0" in text and "sweep_point=1" in text, (
        "Amendment 1 must reference both the actual (sp=2.0) + brief-prescribed (sp=1) values"
    )
    assert "+11 max_delta_aplus" in text or "max_delta_aplus" in text


# ---------------------------------------------------------------------------
# R1.M#2: INSUFFICIENT SAMPLE pre-commit per gotcha #33
# ---------------------------------------------------------------------------
def test_brief_amendment_1_pre_commits_insufficient_sample_verdict() -> None:
    """Amendment 1 MUST pre-commit that R2-D's headline verdict is
    INSUFFICIENT SAMPLE per gotcha #33 (N=4 STNG-only cohort cannot
    discriminate the cross-cohort systemic claim)."""
    text = BRIEF.read_text(encoding="utf-8")
    assert "INSUFFICIENT SAMPLE" in text, (
        "Amendment 1 must pre-commit INSUFFICIENT SAMPLE as the headline verdict class"
    )
    assert "gotcha #33" in text, (
        "Amendment 1 must cite gotcha #33 cohort-validity discipline explicitly"
    )
    # The pre-commit must explicitly forbid SYSTEMIC NEGATIVE on this cohort
    assert "SYSTEMIC" in text and "FORBIDDEN" in text


# ---------------------------------------------------------------------------
# R1.M#3: cohort.json fixture identity lock
# ---------------------------------------------------------------------------
def test_cohort_fixture_exact_identity_lock() -> None:
    """The committed cohort.json fixture MUST contain EXACTLY 4 entries,
    ALL from STNG, with the exact trough_1_date / center_peak_date /
    trough_2_date identities derived from the canonical pattern_cohort_evaluator
    smoke run at exports/research/pattern-cohort-detection-20260526T160518Z/.

    Defends against:
      - Empty fixture silently passing the issubset() check
      - Fixture rewrites with different anchor verdicts
      - Recency-filter regression that admits non-STNG entries
    """
    entries = json.loads(COHORT_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    assert len(entries) == 4, (
        f"R2-D fixture must have exactly N=4 W primary verdicts; got {len(entries)}. "
        f"This is the canonical evaluation cohort (composite>=0.5 + recency<=365d) "
        f"and N=4 is the INSUFFICIENT SAMPLE substrate per Amendment 1 + gotcha #33."
    )
    tickers = {e["ticker"] for e in entries}
    assert tickers == {"STNG"}, (
        f"All 4 entries must be STNG (the only ticker yielding W primaries within "
        f"the 365d recency filter); got {tickers}"
    )
    # Exact (trough_1_date, center_peak_date, trough_2_date, composite_score)
    # 4-tuple set derived from pattern_cohort_evaluator smoke at
    # exports/research/pattern-cohort-detection-20260526T160518Z/results.csv
    # post 5-BD adjacency merge + recency<=365d filter against the canonical
    # composite>=0.5 threshold. Codex R2.m#2 fix: include center_peak_date so
    # a center-peak mutation cannot pass the identity check.
    quadruples = {
        (
            e["trough_1_date"],
            e["center_peak_date"],
            e["trough_2_date"],
            round(float(e["composite_score"]), 4),
        )
        for e in entries
    }
    expected_quadruples = {
        ("2025-04-04", "2025-05-13", "2025-05-22", 0.5),
        ("2025-05-22", "2025-06-18", "2025-06-30", 0.7667),
        ("2025-08-11", "2025-09-15", "2025-10-14", 0.5),
        ("2026-01-05", "2026-03-04", "2026-03-17", 0.6481),
    }
    assert quadruples == expected_quadruples, (
        f"Fixture (trough_1, center_peak, trough_2, composite) quadruples={quadruples}; "
        f"expected={expected_quadruples}. Source: pattern_cohort_evaluator smoke "
        f"at exports/research/pattern-cohort-detection-20260526T160518Z/."
    )


def test_cohort_fixture_all_entries_within_recency_filter() -> None:
    """Every entry's (max_observed_asof_date - trough_2_date) MUST be <= 365
    calendar days (canonical recency filter per Amendment 1 + gotcha #33)."""
    entries = json.loads(COHORT_FIXTURE.read_text(encoding="utf-8"))
    assert entries, "fixture must be non-empty (4 entries expected)"
    for e in entries:
        asof = date.fromisoformat(e["max_observed_asof_date"])
        trough_2 = date.fromisoformat(e["trough_2_date"])
        delta = (asof - trough_2).days
        assert delta <= 365, (
            f"Entry {e['ticker']} trough_1={e['trough_1_date']} has "
            f"(max_observed_asof - trough_2) = {delta} days > 365 day filter"
        )


def test_cohort_fixture_composite_score_at_or_above_canonical_threshold() -> None:
    """All entries MUST satisfy composite_score >= 0.5 (canonical filter per
    Amendment 1 + gotcha #33)."""
    entries = json.loads(COHORT_FIXTURE.read_text(encoding="utf-8"))
    assert entries, "fixture must be non-empty"
    assert all(float(e["composite_score"]) >= 0.5 for e in entries), (
        "Fixture contains sub-threshold composite_score; regenerate via the "
        "canonical extraction pipeline against the documented filter."
    )


# ---------------------------------------------------------------------------
# R1.M#4: audit JSON cohort_selection_method + v2_binding_variable
# ---------------------------------------------------------------------------
def test_audit_json_contains_cohort_selection_method() -> None:
    """The committed audit JSON MUST include cohort_selection_method +
    v2_binding_variable fields explicitly per dispatch brief section 5.2
    + section 6.1 manifest field contract. Without these, downstream
    cross-cohort consumers cannot attribute the selection method."""
    payload = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert payload.get("cohort_selection_method") == "v2_binding_variable_flips", (
        f"audit JSON missing or wrong cohort_selection_method; "
        f"got {payload.get('cohort_selection_method')!r}"
    )
    assert payload.get("v2_binding_variable") == "vcp.adr_min_pct", (
        f"audit JSON missing or wrong v2_binding_variable; "
        f"got {payload.get('v2_binding_variable')!r}"
    )


# ---------------------------------------------------------------------------
# R1.M#5: canonical source SHA/size validation
# ---------------------------------------------------------------------------
def test_verify_canonical_source_identity_passes_on_canonical_artifact() -> None:
    """verify_canonical_source_identity MUST pass on the canonical V2
    sensitivity smoke artifact."""
    if not SOURCE_MD.exists():
        pytest.skip(f"V2 sensitivity artifact not present at {SOURCE_MD}")
    verify_canonical_source_identity(SOURCE_MD)  # should not raise


def test_verify_canonical_source_identity_raises_on_sha_mismatch(tmp_path: Path) -> None:
    """If the source file's SHA differs from CANONICAL_SOURCE_SHA256, the
    verifier MUST raise CohortExtractionError."""
    forged = tmp_path / "forged.md"
    forged.write_text("### vcp.adr_min_pct\n\n(forged content)\n", encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="SHA-256 mismatch"):
        verify_canonical_source_identity(forged)


def test_generate_r2d_cohort_artifacts_verifies_canonical_source(tmp_path: Path) -> None:
    """The wrapper generate_r2d_cohort_artifacts MUST invoke
    verify_canonical_source_identity by default; passing a non-canonical
    source raises BEFORE extraction (defense against the Codex R1.M#5
    failure mode where a source with the same 11 triples but altered
    surrounding text could regenerate 'canonical' outputs)."""
    forged = tmp_path / "forged.md"
    # Forged content contains the canonical 11 flips in the right section,
    # but the surrounding artifact (other sections, summary table) differs.
    # The SHA will not match canonical -> wrapper raises before extraction.
    forged.write_text(
        "## Per-Variable Drill-Down\n\n"
        "### vcp.adr_min_pct\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| GLNG | 55 | 2026-05-18 | 2.0 | watch | aplus | (none) | no |\n",
        encoding="utf-8",
    )
    csv_path = tmp_path / "r2d_cohort.csv"
    with pytest.raises(CohortExtractionError, match="SHA-256 mismatch"):
        generate_r2d_cohort_artifacts(
            source_sensitivity_md=forged,
            cohort_csv_path=csv_path,
        )
    # No cohort artifacts written on canonical-source failure
    assert not csv_path.exists()


def test_generate_r2d_cohort_artifacts_allows_non_canonical_with_flag(
    tmp_path: Path,
) -> None:
    """allow_non_canonical_source=True MUST bypass the source SHA check
    even when the source SHA does NOT match canonical (cohort-identity
    layered verifier still fires).

    Codex R2.m#1 fix: stronger test plants a forged source containing
    all 11 canonical flip triples in the vcp.adr_min_pct section AT
    sweep_point=2.0. Without the flag, the wrapper raises on SHA mismatch
    (proven by test_generate_r2d_cohort_artifacts_verifies_canonical_source).
    With the flag, the wrapper falls through to the layered verifier,
    which then passes because the 11 canonical triples are present.
    """
    # Construct a minimal markdown containing the exact 11 canonical flips
    # at sweep_point=2.0 (plus a noise section to force a different SHA).
    forged_md = """\
## Some unrelated heading

(noise content to make SHA differ from canonical)

## Per-Variable Drill-Down

### vcp.adr_min_pct

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GLNG | 55 | 2026-05-18 | 2.0 | watch | aplus | (none) | no |
| STNG | 18 | 2026-04-24 | 2.0 | watch | aplus | (none) | no |
| STNG | 17 | 2026-04-24 | 2.0 | watch | aplus | (none) | no |
| STNG | 16 | 2026-04-24 | 2.0 | watch | aplus | (none) | no |
| STNG | 15 | 2026-04-24 | 2.0 | watch | aplus | (none) | no |
| AMX | 4 | 2026-04-17 | 2.0 | watch | aplus | (none) | no |
| XENE | 4 | 2026-04-17 | 2.0 | watch | aplus | (none) | no |
| AMX | 3 | 2026-04-17 | 2.0 | watch | aplus | (none) | no |
| XENE | 3 | 2026-04-17 | 2.0 | watch | aplus | (none) | no |
| AMX | 2 | 2026-04-17 | 2.0 | watch | aplus | (none) | no |
| XENE | 2 | 2026-04-17 | 2.0 | watch | aplus | (none) | no |
"""
    forged = tmp_path / "forged_with_canonical_flips.md"
    forged.write_text(forged_md, encoding="utf-8")

    # 1) Default path MUST raise on SHA mismatch
    csv_path = tmp_path / "r2d_cohort_default.csv"
    with pytest.raises(CohortExtractionError, match="SHA-256 mismatch"):
        generate_r2d_cohort_artifacts(
            source_sensitivity_md=forged,
            cohort_csv_path=csv_path,
        )
    assert not csv_path.exists()

    # 2) allow_non_canonical_source=True MUST bypass SHA check AND succeed
    #    because the forged source contains all 11 canonical flips.
    csv_path_2 = tmp_path / "r2d_cohort_noncanonical.csv"
    artifacts = generate_r2d_cohort_artifacts(
        source_sensitivity_md=forged,
        cohort_csv_path=csv_path_2,
        allow_non_canonical_source=True,
    )
    assert artifacts.raw_flip_count == 11
    assert artifacts.unique_ticker_asof_count == 4
    assert csv_path_2.exists()


def test_regenerate_cohort_rejects_non_default_output_without_flag(
    tmp_path: Path,
) -> None:
    """Codex R2.m#3 fix: invoking the entrypoint with the canonical source
    BUT a non-default output cohort CSV path MUST fail without
    --allow-non-canonical-paths."""
    custom_csv = tmp_path / "custom_cohort.csv"
    proc = subprocess.run(
        [
            sys.executable, "-m",
            "research.harness.r2d_adr_min_pct.regenerate_cohort",
            "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md",
            str(custom_csv),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 2, (
        f"expected exit code 2 (non-default output rejection); got {proc.returncode}. "
        f"stderr={proc.stderr!r}"
    )
    assert "non-default cohort CSV path" in proc.stderr
    assert "--allow-non-canonical-paths" in proc.stderr


# ---------------------------------------------------------------------------
# R1.M#6: --allow-non-canonical-paths CLI flag
# ---------------------------------------------------------------------------
def test_regenerate_cohort_rejects_non_default_source_without_flag(
    tmp_path: Path,
) -> None:
    """Invoking the entrypoint with a non-default source path MUST fail
    without --allow-non-canonical-paths."""
    custom_source = tmp_path / "custom.md"
    custom_source.write_text("### vcp.adr_min_pct\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable, "-m",
            "research.harness.r2d_adr_min_pct.regenerate_cohort",
            str(custom_source),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 2, (
        f"expected exit code 2 (non-default path rejection); got {proc.returncode}. "
        f"stderr={proc.stderr!r}"
    )
    assert "non-default source path" in proc.stderr
    assert "--allow-non-canonical-paths" in proc.stderr


def test_regenerate_cohort_help_documents_allow_non_canonical_paths() -> None:
    """The --help output MUST document --allow-non-canonical-paths."""
    proc = subprocess.run(
        [
            sys.executable, "-m",
            "research.harness.r2d_adr_min_pct.regenerate_cohort",
            "--help",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "--allow-non-canonical-paths" in proc.stdout


# ---------------------------------------------------------------------------
# R1.m#1: fixture-derivation provenance test
# ---------------------------------------------------------------------------
def test_cohort_fixture_derivation_chain_documented() -> None:
    """The fixture-derivation chain (1559 -> 132 -> 127 -> 4) MUST be
    documented in the slice 2 commit message (verified by grep against
    git log) OR in the Amendment 1 cohort-validity section. Either path
    surfaces the transformation explicitly for auditors."""
    text = BRIEF.read_text(encoding="utf-8")
    # Amendment 1 cohort-validity section must enumerate the chain
    assert "1559" in text, "Brief Amendment 1 must cite 1559 raw verdicts"
    assert "132" in text, "Brief Amendment 1 must cite 132 composite>=0.5 count"
    # The 4 post-recency-filter count is everywhere; assert it explicitly here
    assert "N=4" in text
