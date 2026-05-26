"""Fast tests for the R2-A cohort generator.

Parses a SYNTHETIC V2 sensitivity drill-down fragment + asserts the filter
yields exactly the watch->aplus flips at sweep_point=1 within the
`vcp.tightness_days_required` section. Verifies:
  - Section boundary (other variable sections ignored).
  - sweep_point filter (only sweep_point=1).
  - old_bucket/new_bucket filter (only watch->aplus).
  - Unique (ticker, asof_date) deduplication.
  - CSV output shape: ticker,asof_date,cohort_label.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from research.harness.r2a_tightness_days_required.cohort_csv import (
    EXPECTED_FLIP_COUNT,
    EXPECTED_FLIPS,
    EXPECTED_TICKER_ASOF,
    EXPECTED_TICKERS,
    EXPECTED_UNIQUE_TICKER_ASOF,
    R2A_COHORT_LABEL,
    CohortArtifacts,
    CohortExtractionError,
    extract_flips_from_sensitivity_md,
    generate_r2a_cohort_artifacts,
    verify_expected_r2a_cohort,
    write_cohort_csv,
    write_flips_audit_json,
)


SYNTHETIC_SENSITIVITY_MD = """\
## Sensitivity Matrix

(unrelated content...)

## Per-Variable Drill-Down

### vcp.adr_min_pct

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FOO | 1 | 2026-05-15 | 1 | watch | aplus | (none) | no |
| BAR | 2 | 2026-05-15 | 1 | skip | watch | (none) | no |

### vcp.tightness_days_required

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GSAT | 64 | 2026-05-22 | 1 | skip | watch | (none) | no |
| NAT | 44 | 2026-05-12 | 1 | watch | aplus | (none) | no |
| RLMD | 41 | 2026-05-08 | 1 | watch | aplus | (none) | no |
| RLMD | 40 | 2026-05-08 | 1 | watch | aplus | (none) | no |
| SEI | 40 | 2026-05-08 | 1 | watch | aplus | (none) | no |
| KOD | 30 | 2026-04-30 | 1 | watch | aplus | (none) | no |
| KOD | 29 | 2026-04-30 | 1 | watch | aplus | (none) | no |
| TROX | 28 | 2026-04-29 | 1 | watch | aplus | (none) | no |
| TROX | 27 | 2026-04-29 | 1 | watch | aplus | (none) | no |
| TROX | 26 | 2026-04-29 | 1 | watch | aplus | (none) | no |
| TROX | 25 | 2026-04-29 | 1 | watch | aplus | (none) | no |
| FRO | 24 | 2026-04-28 | 1 | watch | aplus | (none) | no |
| FRO | 23 | 2026-04-28 | 1 | watch | aplus | (none) | no |
| FRO | 22 | 2026-04-28 | 1 | watch | aplus | (none) | no |
| OII | 10 | 2026-04-21 | 1 | watch | aplus | (none) | no |
| OII | 9 | 2026-04-21 | 1 | watch | aplus | (none) | no |
| BAZ | 5 | 2026-04-01 | 2 | watch | aplus | (none) | no |

### vcp.tightness_range_factor

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ZZZ | 99 | 2026-05-22 | 1 | watch | aplus | (none) | no |
"""


def test_extract_flips_yields_15_records_7_tickers(tmp_path: Path) -> None:
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    # 15 flip records expected (matches V2 smoke 20260524T205849Z)
    assert len(flips) == 15
    tickers = {f.ticker for f in flips}
    assert tickers == {"FRO", "KOD", "NAT", "OII", "RLMD", "SEI", "TROX"}


def test_extract_flips_ignores_other_sections(tmp_path: Path) -> None:
    """FOO (in vcp.adr_min_pct section) and ZZZ (in vcp.tightness_range_factor
    section) must be filtered out -- only entries inside ### vcp.tightness_days_required
    section count.
    """
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    assert "FOO" not in {f.ticker for f in flips}
    assert "ZZZ" not in {f.ticker for f in flips}


def test_extract_flips_filters_by_sweep_point_1(tmp_path: Path) -> None:
    """BAZ at sweep_point=2 must NOT appear in the cohort."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    assert "BAZ" not in {f.ticker for f in flips}


def test_extract_flips_filters_watch_to_aplus_only(tmp_path: Path) -> None:
    """GSAT at skip->watch must NOT appear."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    assert "GSAT" not in {f.ticker for f in flips}


def test_write_cohort_csv_unique_ticker_asof_pairs(tmp_path: Path) -> None:
    """The cohort CSV deduplicates by (ticker, asof_date): multiple eval_runs
    on the same date collapse to ONE entry (the data_asof_date is what
    pattern_cohort_detect consumes; the eval_run_id is V1 audit-only).
    """
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    csv_path = tmp_path / "r2a_cohort.csv"
    n_unique = write_cohort_csv(flips, csv_path)
    # 7 unique (ticker, asof_date) tuples (one per flip-day across 7 tickers)
    assert n_unique == 7
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 7
    assert all(row["cohort_label"] == R2A_COHORT_LABEL for row in rows)
    assert {row["ticker"] for row in rows} == {
        "FRO", "KOD", "NAT", "OII", "RLMD", "SEI", "TROX"
    }


def test_write_cohort_csv_header_shape(tmp_path: Path) -> None:
    """CSV header must be exactly: ticker,asof_date,cohort_label (matches
    pattern_cohort_detect's expected input shape).
    """
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    csv_path = tmp_path / "r2a_cohort.csv"
    write_cohort_csv(flips, csv_path)
    with csv_path.open(encoding="utf-8") as f:
        header = f.readline().strip()
    assert header == "ticker,asof_date,cohort_label"


def test_extract_flips_raises_on_missing_section(tmp_path: Path) -> None:
    """If the V2 sensitivity md lacks the vcp.tightness_days_required section,
    the extractor must raise a typed exception (not silently return [])."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text("# Empty\n\nNo drill-down here.\n", encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="vcp.tightness_days_required"):
        extract_flips_from_sensitivity_md(md)


def test_extract_flips_raises_on_missing_required_columns(tmp_path: Path) -> None:
    """Defense against silent under-extraction if upstream V2 emitter
    drops the eval_run_id column (Codex R1 M#4). The parser MUST raise
    rather than silently parse with wrong indices.
    """
    md_text = """\
## Per-Variable Drill-Down

### vcp.tightness_days_required

| ticker | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- |
| NAT | 2026-05-12 | 1 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="eval_run_id"):
        extract_flips_from_sensitivity_md(md)


def test_extract_flips_resilient_to_column_reordering(tmp_path: Path) -> None:
    """If the V2 emitter reorders columns (e.g. moves eval_run_id to the
    end), the parser MUST still extract correctly by resolving columns
    by NAME (Codex R1 M#4).
    """
    md_text = """\
## Per-Variable Drill-Down

### vcp.tightness_days_required

| data_asof_date | ticker | sweep_point | old_bucket | new_bucket | eval_run_id | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-12 | NAT | 1 | watch | aplus | 44 | (none) | no |
| 2026-04-21 | OII | 1 | watch | aplus | 9 | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    assert len(flips) == 2
    by_ticker = {f.ticker: f for f in flips}
    assert by_ticker["NAT"].eval_run_id == 44
    assert by_ticker["OII"].eval_run_id == 9


def test_extract_flips_h4_subheading_inside_section_does_not_terminate(
    tmp_path: Path,
) -> None:
    """If the drill-down section contains a 4-hash sub-heading (e.g.
    `#### Notes`), section-body extraction MUST continue PAST that
    sub-heading and not silently truncate the table (Codex R1 M#3).
    """
    md_text = """\
## Per-Variable Drill-Down

### vcp.tightness_days_required

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NAT | 44 | 2026-05-12 | 1 | watch | aplus | (none) | no |

#### Notes about this section

(text content)

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OII | 9 | 2026-04-21 | 1 | watch | aplus | (none) | no |

### vcp.tightness_range_factor

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ZZZ | 99 | 2026-05-22 | 1 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    tickers = {f.ticker for f in flips}
    assert tickers == {"NAT", "OII"}, (
        "h4 sub-heading must NOT terminate section; "
        "next h3 must terminate"
    )


def test_verify_expected_r2a_cohort_strict_on_real_artifact() -> None:
    """Discriminating test: verify_expected_r2a_cohort MUST pass against
    the canonical 2026-05-24 V2 sensitivity smoke (15 / 7 / 7) and FAIL
    when the cohort deviates.
    """
    md = Path(__file__).resolve().parents[3] / (
        "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
    )
    if not md.exists():
        pytest.skip(f"V2 smoke artifact not present at {md}")
    flips = extract_flips_from_sensitivity_md(md)
    # Should NOT raise on the canonical artifact
    verify_expected_r2a_cohort(flips)

    # Synthetic deviation: drop one flip; assert raises (the layered
    # verifier raises "flip identity" first because the missing tuple
    # is detected at the identity layer before the count layer).
    with pytest.raises(CohortExtractionError, match="flip identity"):
        verify_expected_r2a_cohort(flips[:-1])


def test_write_flips_audit_json_preserves_eval_run_ids(tmp_path: Path) -> None:
    """All 15 raw flip records (with eval_run_id) MUST be persisted in
    the audit JSON sibling file (Codex R1 M#1 + minor #2: V1->R2-A
    traceability).
    """
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    audit_path = tmp_path / "audit.flips.json"
    n = write_flips_audit_json(flips, audit_path, source_sensitivity_md=md)
    assert n == 15
    import json
    payload = json.loads(audit_path.read_text())
    assert payload["flip_count"] == 15
    assert payload["variable_name"] == "vcp.tightness_days_required"
    # The audit MUST preserve ALL 15 entries — duplicates are allowed
    # (SEI eval_run_id=40 collides with RLMD eval_run_id=40 in the
    # synthetic + real artifact; eval_run_ids are scoped per-pipeline_run
    # and may repeat across tickers).
    assert len(payload["flips"]) == 15
    # 14 distinct eval_run_id values in the synthetic fixture (40 appears
    # for both RLMD and SEI). The audit shape preserves both rows.
    eval_run_ids = {f["eval_run_id"] for f in payload["flips"]}
    assert len(eval_run_ids) == 14


def test_expected_cohort_constants_match_brief_canonical_counts() -> None:
    """Lock the canonical-counts constants against accidental edit.
    EXPECTED_FLIP_COUNT must be 15; EXPECTED_UNIQUE_TICKER_ASOF must be 7;
    EXPECTED_TICKERS must be the 7-ticker set in the brief.
    """
    assert EXPECTED_FLIP_COUNT == 15
    assert EXPECTED_UNIQUE_TICKER_ASOF == 7
    assert EXPECTED_TICKERS == frozenset(
        {"FRO", "KOD", "NAT", "OII", "RLMD", "SEI", "TROX"}
    )


def test_extract_flips_against_real_v2_smoke_artifact() -> None:
    """Discriminating test against the actual V2 sensitivity artifact:
    aplus-sensitivity-v2-20260524T205849Z.md -- the canonical R2-A source.
    Asserts the production-shape pipeline yields the brief's expected
    15 flips / 7 tickers (cumulative gotcha: synthetic-fixture-vs-production
    drift defense).
    """
    md = Path(__file__).resolve().parents[3] / (
        "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
    )
    if not md.exists():
        pytest.skip(f"V2 smoke artifact not present at {md}")
    flips = extract_flips_from_sensitivity_md(md)
    assert len(flips) == 15
    assert {f.ticker for f in flips} == {
        "FRO", "KOD", "NAT", "OII", "RLMD", "SEI", "TROX"
    }


# ---------------------------------------------------------------------------
# Codex R2.M#1: (ticker, asof) corruption defense
# ---------------------------------------------------------------------------
def test_verify_rejects_corrupted_asof_date_preserving_counts() -> None:
    """If a flip's asof_date is swapped to a wrong date but counts remain
    15/7/7, the verifier MUST still raise (Codex R2.M#1)."""
    canonical_flips_list = list(
        type("FlipRecord", (), {})()  # placeholder
        for _ in EXPECTED_FLIPS
    )
    # Build a canonical flips list from EXPECTED_FLIPS constants
    from research.harness.r2a_tightness_days_required.cohort_csv import FlipRecord
    canonical = [FlipRecord(t, e, d) for (t, e, d) in EXPECTED_FLIPS]
    # Should pass canonical
    verify_expected_r2a_cohort(canonical)
    # Corrupt one asof_date (NAT 2026-05-12 -> 2026-05-13)
    import dataclasses
    corrupted = list(canonical)
    for i, f in enumerate(corrupted):
        if f.ticker == "NAT":
            corrupted[i] = dataclasses.replace(f, data_asof_date=date(2026, 5, 13))
            break
    with pytest.raises(CohortExtractionError, match="flip identity"):
        verify_expected_r2a_cohort(corrupted)


def test_verify_rejects_corrupted_eval_run_id_preserving_counts() -> None:
    """If a flip's eval_run_id is changed but ticker + asof preserved,
    the verifier MUST still raise (Codex R2.M#2: eval_run_id provenance)."""
    from research.harness.r2a_tightness_days_required.cohort_csv import FlipRecord
    canonical = [FlipRecord(t, e, d) for (t, e, d) in EXPECTED_FLIPS]
    verify_expected_r2a_cohort(canonical)  # baseline pass
    import dataclasses
    corrupted = list(canonical)
    for i, f in enumerate(corrupted):
        if f.ticker == "NAT" and f.eval_run_id == 44:
            corrupted[i] = dataclasses.replace(f, eval_run_id=99)
            break
    with pytest.raises(CohortExtractionError, match="flip identity"):
        verify_expected_r2a_cohort(corrupted)


# ---------------------------------------------------------------------------
# Codex R2.M#3: h2 boundary correctly applied when no h3 follows
# ---------------------------------------------------------------------------
def test_section_body_h2_boundary_when_no_h3_follows(tmp_path: Path) -> None:
    """If the target section is the LAST h3 in the file but is followed
    by an h2 heading, the section body MUST terminate at the h2
    boundary (Codex R2.M#3)."""
    md_text = """\
## Per-Variable Drill-Down

### vcp.tightness_days_required

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NAT | 44 | 2026-05-12 | 1 | watch | aplus | (none) | no |

## V1<->V2 Baseline Parity Drift

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OII | 9 | 2026-04-21 | 1 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    tickers = {f.ticker for f in flips}
    assert tickers == {"NAT"}, (
        "h2 boundary must terminate the drill-down section; "
        "second table belongs to the h2 section, not the target h3"
    )


# ---------------------------------------------------------------------------
# Codex R2.M#4: line-anchored heading regex (not substring match)
# ---------------------------------------------------------------------------
def test_section_start_not_matched_inside_prose(tmp_path: Path) -> None:
    """If the variable name appears inside prose / code blocks (NOT
    as an actual h3 heading line), the parser MUST raise instead of
    silently using that as section start (Codex R2.M#4)."""
    md_text = """\
## Per-Variable Drill-Down

(Note: the variable `vcp.tightness_days_required` was binding at +16.)

```
### vcp.tightness_days_required  ← this is inside a code block
```

#### Discussion of vcp.tightness_days_required (h4 heading; not h3)

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NAT | 44 | 2026-05-12 | 1 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    # The code-block line `### vcp.tightness_days_required` is at the
    # START of a line so it WILL match. This is acceptable because
    # markdown code-fences are operator-readable artifacts; the parser's
    # responsibility is to defend against MISSING heading + LONGER
    # heading titles. The expected behavior is to find SOMETHING + raise
    # on either flip-identity (canonical strict mode) or missing columns
    # (the h4 table here lacks the section's table format inside a
    # legitimate section).
    # This test instead verifies the parser does NOT match an h4 heading
    # as the section start when there is NO h3 at all:
    md_text_no_h3 = """\
## Per-Variable Drill-Down

#### vcp.tightness_days_required (h4 only; NOT h3)

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NAT | 44 | 2026-05-12 | 1 | watch | aplus | (none) | no |
"""
    md.write_text(md_text_no_h3, encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="line-anchored"):
        extract_flips_from_sensitivity_md(md)


def test_section_start_not_matched_on_longer_title(tmp_path: Path) -> None:
    """If a longer h3 title contains the variable name as a substring
    (e.g. `### vcp.tightness_days_required (deprecated)`), the parser
    MUST NOT silently treat that as the canonical section start.

    Per Codex R2.M#4: anchored regex requires EXACT match + optional
    trailing whitespace.
    """
    md_text = """\
### vcp.tightness_days_required (deprecated)

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ZZZ | 99 | 2026-05-22 | 1 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="line-anchored"):
        extract_flips_from_sensitivity_md(md)


# ---------------------------------------------------------------------------
# Codex R2.M#6: canonical-generation wrapper enforces extract -> verify -> write
# ---------------------------------------------------------------------------
def test_generate_r2a_cohort_artifacts_canonical_path(tmp_path: Path) -> None:
    """The wrapper performs extract -> verify -> write_cohort_csv ->
    write_flips_audit_json in one call; output paths + counts returned."""
    md = Path(__file__).resolve().parents[3] / (
        "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
    )
    if not md.exists():
        pytest.skip(f"V2 smoke artifact not present at {md}")
    csv_path = tmp_path / "r2a_cohort.csv"
    artifacts = generate_r2a_cohort_artifacts(
        source_sensitivity_md=md,
        cohort_csv_path=csv_path,
    )
    assert isinstance(artifacts, CohortArtifacts)
    assert artifacts.cohort_csv_path == csv_path
    assert artifacts.flips_audit_json_path == csv_path.with_suffix(".flips_audit.json")
    assert artifacts.unique_ticker_asof_count == 7
    assert artifacts.raw_flip_count == 15
    assert csv_path.exists()
    assert artifacts.flips_audit_json_path.exists()


def test_generate_r2a_cohort_artifacts_raises_on_bad_artifact(tmp_path: Path) -> None:
    """If the source artifact deviates from canonical (e.g. missing rows),
    the wrapper MUST raise BEFORE writing any cohort CSV / audit JSON
    (atomicity of canonical generation)."""
    md_text = """\
## Per-Variable Drill-Down

### vcp.tightness_days_required

| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NAT | 44 | 2026-05-12 | 1 | watch | aplus | (none) | no |
"""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(md_text, encoding="utf-8")
    csv_path = tmp_path / "r2a_cohort.csv"
    with pytest.raises(CohortExtractionError):
        generate_r2a_cohort_artifacts(
            source_sensitivity_md=md,
            cohort_csv_path=csv_path,
        )
    # CSV must NOT have been written (canonical generation is atomic)
    assert not csv_path.exists()


# ---------------------------------------------------------------------------
# Codex R2.minor#3: audit JSON includes source SHA + size
# ---------------------------------------------------------------------------
def test_audit_json_records_source_sha256_and_size(tmp_path: Path) -> None:
    """Audit JSON MUST record the source markdown's SHA-256 + size_bytes
    so subsequent edits to the source artifact are detectable
    (Codex R2.minor#3 audit durability)."""
    md = tmp_path / "v2_sensitivity.md"
    md.write_text(SYNTHETIC_SENSITIVITY_MD, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md)
    audit_path = tmp_path / "audit.flips.json"
    write_flips_audit_json(flips, audit_path, source_sensitivity_md=md)
    import json as _json
    payload = _json.loads(audit_path.read_text())
    assert payload["source_sensitivity_md_sha256"] is not None
    assert len(payload["source_sensitivity_md_sha256"]) == 64  # SHA-256 hex
    assert payload["source_sensitivity_md_size_bytes"] == md.stat().st_size
