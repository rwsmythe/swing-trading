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
from pathlib import Path

import pytest

from research.harness.r2a_tightness_days_required.cohort_csv import (
    R2A_COHORT_LABEL,
    extract_flips_from_sensitivity_md,
    write_cohort_csv,
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
    with pytest.raises(ValueError, match="vcp.tightness_days_required"):
        extract_flips_from_sensitivity_md(md)


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
