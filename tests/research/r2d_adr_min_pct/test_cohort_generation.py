"""Fast tests for the R2-D cohort generator.

Parses a SYNTHETIC V2 sensitivity drill-down fragment + asserts the filter
yields exactly the watch->aplus flips at sweep_point=2.0 within the
`vcp.adr_min_pct` section. Verifies:
  - Section boundary (other variable sections ignored).
  - sweep_point filter (only sweep_point=2.0; FLOAT-valued).
  - old_bucket/new_bucket filter (only watch->aplus).
  - Unique (ticker, asof_date) deduplication.
  - CSV output shape: ticker,asof_date,cohort_label.
"""
from __future__ import annotations

import csv
import dataclasses
import json
from datetime import date
from pathlib import Path

import pytest

from research.harness.r2d_adr_min_pct.cohort_csv import (
    CANONICAL_SOURCE_SHA256,
    CANONICAL_SOURCE_SIZE_BYTES,
    EXPECTED_FLIP_COUNT,
    EXPECTED_FLIPS,
    EXPECTED_TICKER_ASOF,
    EXPECTED_TICKERS,
    EXPECTED_UNIQUE_TICKER_ASOF,
    R2D_COHORT_LABEL,
    R2D_SWEEP_POINT,
    R2D_VARIABLE_NAME,
    CohortArtifacts,
    CohortExtractionError,
    FlipRecord,
    extract_flips_from_sensitivity_md,
    generate_r2d_cohort_artifacts,
    verify_expected_r2d_cohort,
    write_cohort_csv,
    write_flips_audit_json,
)


SYNTHETIC_SENSITIVITY_MD = """\
## Sensitivity Matrix

(unrelated content...)

## Per-Variable Drill-Down

### vcp.tightness_days_required

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FOO | 1 | 2026-05-15 | 1 | watch | aplus | (none) | no |
| BAR | 2 | 2026-05-15 | 1 | skip | watch | (none) | no |

### vcp.adr_min_pct

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OTHER | 100 | 2026-05-22 | 2.0 | skip | watch | (none) | no |
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
| OUT_OF_BAND | 5 | 2026-04-01 | 3.0 | watch | aplus | (none) | no |
| GSAT_SP1 | 50 | 2026-05-15 | 1 | watch | aplus | (none) | no |

### vcp.tightness_range_factor

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ZZZ | 99 | 2026-05-22 | 1.005 | watch | aplus | (none) | no |
"""


def test_extract_flips_yields_11_records_4_tickers(tmp_path: Path) -> None:
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    # 11 flip records expected (matches V2 smoke 20260524T205849Z at sp=2.0)
    assert len(flips) == 11
    tickers = {f.ticker for f in flips}
    assert tickers == {"AMX", "GLNG", "STNG", "XENE"}


def test_extract_flips_ignores_other_sections(tmp_path: Path) -> None:
    """FOO (vcp.tightness_days_required section) and ZZZ
    (vcp.tightness_range_factor section) must be filtered out -- only
    entries inside ### vcp.adr_min_pct section count.
    """
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    extracted = {f.ticker for f in flips}
    assert "FOO" not in extracted
    assert "ZZZ" not in extracted


def test_extract_flips_filters_by_sweep_point_2_0(tmp_path: Path) -> None:
    """OUT_OF_BAND at sweep_point=3.0 and GSAT_SP1 at sweep_point=1 must
    NOT appear in the cohort (only sweep_point=2.0 is the binding signal)."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    extracted = {f.ticker for f in flips}
    assert "OUT_OF_BAND" not in extracted
    assert "GSAT_SP1" not in extracted


def test_extract_flips_filters_watch_to_aplus_only(tmp_path: Path) -> None:
    """OTHER at skip->watch must NOT appear."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    extracted = {f.ticker for f in flips}
    assert "OTHER" not in extracted


def test_write_cohort_csv_unique_ticker_asof_pairs(tmp_path: Path) -> None:
    """The cohort CSV deduplicates by (ticker, asof_date): multiple eval_runs
    on the same date collapse to ONE entry."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    csv_path = tmp_path / "r2d_cohort.csv"
    n_unique = write_cohort_csv(flips, csv_path)
    # 4 unique (ticker, asof_date) tuples (AMX/GLNG/STNG/XENE distinct dates)
    assert n_unique == 4
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 4
    assert all(row["cohort_label"] == R2D_COHORT_LABEL for row in rows)
    assert {row["ticker"] for row in rows} == {"AMX", "GLNG", "STNG", "XENE"}


def test_write_cohort_csv_header_shape(tmp_path: Path) -> None:
    """CSV header must be exactly: ticker,asof_date,cohort_label (matches
    pattern_cohort_detect's expected input shape)."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    csv_path = tmp_path / "r2d_cohort.csv"
    write_cohort_csv(flips, csv_path)
    with csv_path.open(encoding="utf-8") as f:
        header = f.readline().strip()
    assert header == "ticker,asof_date,cohort_label"


def test_extract_flips_raises_on_missing_section(tmp_path: Path) -> None:
    """If the V2 sensitivity md lacks the vcp.adr_min_pct section,
    the extractor must raise a typed exception (not silently return [])."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text("# Empty\n\nNo drill-down here.\n", encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="vcp.adr_min_pct"):
        extract_flips_from_sensitivity_md(md)


def test_extract_flips_raises_on_missing_required_columns(tmp_path: Path) -> None:
    """Defense against silent under-extraction if upstream V2 emitter
    drops the eval_run_id column. The parser MUST raise rather than
    silently parse with wrong indices."""
    md_text = """\
## Per-Variable Drill-Down

### vcp.adr_min_pct

| ticker | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- |
| GLNG | 2026-05-18 | 2.0 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="eval_run_id"):
        extract_flips_from_sensitivity_md(md)


def test_extract_flips_resilient_to_column_reordering(tmp_path: Path) -> None:
    """If the V2 emitter reorders columns, the parser MUST still extract
    correctly by resolving columns by NAME."""
    md_text = """\
## Per-Variable Drill-Down

### vcp.adr_min_pct

| data_asof_date | ticker | sweep_point | old_bucket | new_bucket | eval_run_id | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-18 | GLNG | 2.0 | watch | aplus | 55 | (none) | no |
| 2026-04-17 | AMX | 2.0 | watch | aplus | 4 | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    assert len(flips) == 2
    by_ticker = {f.ticker: f for f in flips}
    assert by_ticker["GLNG"].eval_run_id == 55
    assert by_ticker["AMX"].eval_run_id == 4


def test_extract_flips_h4_subheading_inside_section_does_not_terminate(
    tmp_path: Path,
) -> None:
    """If the drill-down section contains a 4-hash sub-heading, section-body
    extraction MUST continue past it."""
    md_text = """\
## Per-Variable Drill-Down

### vcp.adr_min_pct

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GLNG | 55 | 2026-05-18 | 2.0 | watch | aplus | (none) | no |

#### Notes about this section

(text content)

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AMX | 4 | 2026-04-17 | 2.0 | watch | aplus | (none) | no |

### vcp.tightness_range_factor

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ZZZ | 99 | 2026-05-22 | 1.005 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    tickers = {f.ticker for f in flips}
    assert tickers == {"GLNG", "AMX"}, (
        "h4 sub-heading must NOT terminate section; "
        "next h3 must terminate"
    )


def test_verify_expected_r2d_cohort_strict_on_real_artifact() -> None:
    """Discriminating test: verify_expected_r2d_cohort MUST pass against
    the canonical 2026-05-24 V2 sensitivity smoke (11 / 4 / 4) and FAIL
    when the cohort deviates.
    """
    md = Path(__file__).resolve().parents[3] / (
        "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
    )
    if not md.exists():
        pytest.skip(f"V2 smoke artifact not present at {md}")
    flips = extract_flips_from_sensitivity_md(md)
    # Should NOT raise on the canonical artifact
    verify_expected_r2d_cohort(flips)

    # Synthetic deviation: drop one flip; assert raises
    with pytest.raises(CohortExtractionError, match="flip identity"):
        verify_expected_r2d_cohort(flips[:-1])


def test_write_flips_audit_json_preserves_eval_run_ids(tmp_path: Path) -> None:
    """All 11 raw flip records (with eval_run_id) MUST be persisted in
    the audit JSON sibling file (V1->R2-D traceability)."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    audit_path = tmp_path / "audit.flips.json"
    n = write_flips_audit_json(flips, audit_path, source_sensitivity_md=md)
    assert n == 11
    payload = json.loads(audit_path.read_text())
    assert payload["flip_count"] == 11
    assert payload["variable_name"] == "vcp.adr_min_pct"
    assert payload["sweep_point"] == 2.0
    assert len(payload["flips"]) == 11


def test_expected_cohort_constants_match_brief_canonical_counts() -> None:
    """Lock the canonical-counts constants against accidental edit.
    EXPECTED_FLIP_COUNT must be 11; EXPECTED_UNIQUE_TICKER_ASOF must be 4;
    EXPECTED_TICKERS must be {AMX, GLNG, STNG, XENE}.
    """
    assert EXPECTED_FLIP_COUNT == 11
    assert EXPECTED_UNIQUE_TICKER_ASOF == 4
    assert EXPECTED_TICKERS == frozenset({"AMX", "GLNG", "STNG", "XENE"})
    assert R2D_VARIABLE_NAME == "vcp.adr_min_pct"
    assert R2D_SWEEP_POINT == 2.0


def test_extract_flips_against_real_v2_smoke_artifact() -> None:
    """Discriminating test against the actual V2 sensitivity artifact:
    aplus-sensitivity-v2-20260524T205849Z.md -- the canonical R2-D source.
    Asserts the production-shape pipeline yields the brief's expected
    11 flips / 4 tickers (cumulative gotcha: synthetic-fixture-vs-production
    drift defense)."""
    md = Path(__file__).resolve().parents[3] / (
        "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
    )
    if not md.exists():
        pytest.skip(f"V2 smoke artifact not present at {md}")
    flips = extract_flips_from_sensitivity_md(md)
    assert len(flips) == 11
    assert {f.ticker for f in flips} == {"AMX", "GLNG", "STNG", "XENE"}


def test_verify_rejects_corrupted_asof_date_preserving_counts() -> None:
    """If a flip's asof_date is swapped to a wrong date but counts remain
    11/4/4, the verifier MUST still raise."""
    canonical = [FlipRecord(t, e, d) for (t, e, d) in EXPECTED_FLIPS]
    verify_expected_r2d_cohort(canonical)  # baseline pass
    corrupted = list(canonical)
    for i, f in enumerate(corrupted):
        if f.ticker == "GLNG":
            corrupted[i] = dataclasses.replace(f, data_asof_date=date(2026, 5, 19))
            break
    with pytest.raises(CohortExtractionError, match="flip identity"):
        verify_expected_r2d_cohort(corrupted)


def test_verify_rejects_corrupted_eval_run_id_preserving_counts() -> None:
    """If a flip's eval_run_id is changed but ticker + asof preserved,
    the verifier MUST still raise."""
    canonical = [FlipRecord(t, e, d) for (t, e, d) in EXPECTED_FLIPS]
    verify_expected_r2d_cohort(canonical)  # baseline pass
    corrupted = list(canonical)
    for i, f in enumerate(corrupted):
        if f.ticker == "GLNG" and f.eval_run_id == 55:
            corrupted[i] = dataclasses.replace(f, eval_run_id=99)
            break
    with pytest.raises(CohortExtractionError, match="flip identity"):
        verify_expected_r2d_cohort(corrupted)


def test_section_body_h2_boundary_when_no_h3_follows(tmp_path: Path) -> None:
    """If the target section is the LAST h3 in the file but is followed
    by an h2 heading, the section body MUST terminate at the h2 boundary."""
    md_text = """\
## Per-Variable Drill-Down

### vcp.adr_min_pct

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GLNG | 55 | 2026-05-18 | 2.0 | watch | aplus | (none) | no |

## V1<->V2 Baseline Parity Drift

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AMX | 4 | 2026-04-17 | 2.0 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    tickers = {f.ticker for f in flips}
    assert tickers == {"GLNG"}, (
        "h2 boundary must terminate the drill-down section"
    )


def test_section_start_not_matched_on_longer_title(tmp_path: Path) -> None:
    """If a longer h3 title contains the variable name as a substring,
    the parser MUST NOT silently treat that as the canonical section start."""
    md_text = """\
### vcp.adr_min_pct (deprecated)

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ZZZ | 99 | 2026-05-22 | 2.0 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="line-anchored"):
        extract_flips_from_sensitivity_md(md)


def test_generate_r2d_cohort_artifacts_canonical_path(tmp_path: Path) -> None:
    """The wrapper performs extract -> verify -> write_cohort_csv ->
    write_flips_audit_json in one call; output paths + counts returned."""
    md = Path(__file__).resolve().parents[3] / (
        "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
    )
    if not md.exists():
        pytest.skip(f"V2 smoke artifact not present at {md}")
    csv_path = tmp_path / "r2d_cohort.csv"
    artifacts = generate_r2d_cohort_artifacts(
        source_sensitivity_md=md,
        cohort_csv_path=csv_path,
    )
    assert isinstance(artifacts, CohortArtifacts)
    assert artifacts.cohort_csv_path == csv_path
    assert artifacts.flips_audit_json_path == csv_path.with_suffix(".flips_audit.json")
    assert artifacts.unique_ticker_asof_count == 4
    assert artifacts.raw_flip_count == 11
    assert csv_path.exists()
    assert artifacts.flips_audit_json_path.exists()


def test_generate_r2d_cohort_artifacts_raises_on_bad_artifact(tmp_path: Path) -> None:
    """If the source artifact deviates from canonical, the wrapper MUST raise
    BEFORE writing any cohort CSV / audit JSON (atomicity)."""
    md_text = """\
## Per-Variable Drill-Down

### vcp.adr_min_pct

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GLNG | 55 | 2026-05-18 | 2.0 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    csv_path = tmp_path / "r2d_cohort.csv"
    with pytest.raises(CohortExtractionError):
        generate_r2d_cohort_artifacts(
            source_sensitivity_md=md,
            cohort_csv_path=csv_path,
        )
    # CSV must NOT have been written
    assert not csv_path.exists()


def test_audit_json_records_source_sha256_and_size(tmp_path: Path) -> None:
    """Audit JSON MUST record the source markdown's SHA-256 + size_bytes
    so subsequent edits to the source artifact are detectable."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    audit_path = tmp_path / "audit.flips.json"
    write_flips_audit_json(flips, audit_path, source_sensitivity_md=md)
    payload = json.loads(audit_path.read_text())
    assert payload["source_sensitivity_md_sha256"] is not None
    assert len(payload["source_sensitivity_md_sha256"]) == 64
    assert payload["source_sensitivity_md_size_bytes"] == md.stat().st_size


def test_canonical_source_constants_match_real_artifact() -> None:
    """Lock CANONICAL_SOURCE_SHA256 + CANONICAL_SOURCE_SIZE_BYTES against
    the real V2 sensitivity artifact (regression defense if the artifact
    changes upstream)."""
    md = Path(__file__).resolve().parents[3] / (
        "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
    )
    if not md.exists():
        pytest.skip(f"V2 smoke artifact not present at {md}")
    import hashlib
    actual_sha = hashlib.sha256(md.read_bytes()).hexdigest()
    actual_size = md.stat().st_size
    assert actual_sha == CANONICAL_SOURCE_SHA256
    assert actual_size == CANONICAL_SOURCE_SIZE_BYTES
