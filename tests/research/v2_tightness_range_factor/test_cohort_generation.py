"""V2 tightness_range_factor cohort extraction + verifier tests.

Mirrors R2-A + R2-D test architecture for the sibling-module strategy
(per V2-selection-mechanic investigation dispatch brief Sec 4.1).
Covers: layered verifier (3 layers) / parser robustness / section-boundary
discipline / sweep_point FLOAT coercion / canonical source SHA + size
validation / audit JSON shape / CLI --allow-non-canonical-paths /
committed-artifact canonical lock / module constants.

L2 LOCK + ASCII-only discipline preserved per cumulative gotchas
#32 (declared ASCII scope) + #34 (brief-prescription cross-table) +
#26 (OHLCV cache temporal mutation) inherited from R2-D.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from research.harness.v2_tightness_range_factor import cohort_csv
from research.harness.v2_tightness_range_factor.cohort_csv import (
    CANONICAL_SOURCE_SHA256,
    CANONICAL_SOURCE_SIZE_BYTES,
    EXPECTED_FLIP_COUNT,
    EXPECTED_FLIPS,
    EXPECTED_TICKER_ASOF,
    EXPECTED_TICKERS,
    EXPECTED_UNIQUE_TICKER_ASOF,
    V2TRF_COHORT_LABEL,
    V2TRF_NEW_BUCKET,
    V2TRF_OLD_BUCKET,
    V2TRF_SWEEP_POINT,
    V2TRF_VARIABLE_NAME,
    CohortExtractionError,
    FlipRecord,
    extract_flips_from_sensitivity_md,
    generate_v2trf_cohort_artifacts,
    verify_canonical_source_identity,
    verify_expected_v2trf_cohort,
    write_cohort_csv,
    write_flips_audit_json,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_SOURCE = (
    REPO_ROOT
    / "exports"
    / "diagnostics"
    / "aplus-sensitivity-v2-20260524T205849Z.md"
)
COMMITTED_COHORT_CSV = (
    REPO_ROOT
    / "exports"
    / "research"
    / "cohorts"
    / "v2_tightness_range_factor_sp1_005.csv"
)
COMMITTED_AUDIT_JSON = (
    REPO_ROOT
    / "exports"
    / "research"
    / "cohorts"
    / "v2_tightness_range_factor_sp1_005.flips_audit.json"
)


# --------- Module constant + binding signal LOCK tests ---------


def test_module_constants_lock_binding_signal() -> None:
    """V2-TRF binding signal: variable name + sweep_point + bucket transition."""
    assert V2TRF_VARIABLE_NAME == "vcp.tightness_range_factor"
    assert V2TRF_SWEEP_POINT == 1.005
    assert V2TRF_OLD_BUCKET == "watch"
    assert V2TRF_NEW_BUCKET == "aplus"
    assert V2TRF_COHORT_LABEL == "v2_vcp_tightness_range_factor_sp1_005"


def test_expected_counts_lock() -> None:
    """Canonical cohort counts: 67 raw flips / 15 unique tickers / 29 unique pairs."""
    assert EXPECTED_FLIP_COUNT == 67
    assert EXPECTED_UNIQUE_TICKER_ASOF == 29
    assert len(EXPECTED_TICKERS) == 15
    assert len(EXPECTED_FLIPS) == 67
    assert len(EXPECTED_TICKER_ASOF) == 29


def test_expected_tickers_set_lock() -> None:
    """Canonical 15 ticker set lock (defends against silent ticker substitution)."""
    assert EXPECTED_TICKERS == frozenset(
        {
            "YOU", "DK", "SSRM", "WULF", "TSHA", "NAT", "RLMD", "UCTT",
            "PTEN", "KOD", "RNG", "TROX", "FRO", "DNTH", "OII",
        }
    )


def test_canonical_source_sha_lock() -> None:
    """Source SHA + size identity inherited from R2-A + R2-D (same source artifact)."""
    assert CANONICAL_SOURCE_SHA256 == (
        "b25bcde944c33c7a44d049167e78e9d5c7b3d4fc5538ccc5e9cdc8e01e27a143"
    )
    assert CANONICAL_SOURCE_SIZE_BYTES == 830034


# --------- Canonical source artifact identity check ---------


def test_canonical_source_file_matches_sha_lock() -> None:
    """The committed source artifact must match CANONICAL_SOURCE_SHA256 + size."""
    assert CANONICAL_SOURCE.exists(), f"missing source artifact at {CANONICAL_SOURCE}"
    h = hashlib.sha256()
    with CANONICAL_SOURCE.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    assert h.hexdigest() == CANONICAL_SOURCE_SHA256
    assert CANONICAL_SOURCE.stat().st_size == CANONICAL_SOURCE_SIZE_BYTES


def test_verify_canonical_source_identity_passes_on_canonical() -> None:
    """verify_canonical_source_identity passes on the committed canonical source."""
    verify_canonical_source_identity(CANONICAL_SOURCE)


def test_verify_canonical_source_identity_raises_on_mismatch(tmp_path: Path) -> None:
    """Non-canonical SHA -> CohortExtractionError."""
    bad = tmp_path / "fake.md"
    bad.write_text("not the canonical source", encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="SHA-256 mismatch"):
        verify_canonical_source_identity(bad)


def test_verify_canonical_source_identity_raises_on_missing(tmp_path: Path) -> None:
    """Missing source path -> FileNotFoundError (NOT silent fallback)."""
    with pytest.raises(FileNotFoundError):
        verify_canonical_source_identity(tmp_path / "nope.md")


# --------- Extraction + verifier (round-trip against canonical source) ---------


def test_extract_against_canonical_source_yields_67_flips() -> None:
    """Round-trip: extract from canonical source -> exactly 67 flip records."""
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    assert len(flips) == 67


def test_extract_against_canonical_source_matches_expected_flips() -> None:
    """Layer 1 raw flip identity against canonical source."""
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    parsed = {(f.ticker, f.eval_run_id, f.data_asof_date) for f in flips}
    assert parsed == EXPECTED_FLIPS


def test_verify_expected_v2trf_cohort_passes_on_canonical() -> None:
    """3-layer verifier passes on canonical extraction."""
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    verify_expected_v2trf_cohort(flips)  # no raise


# --------- Layer-by-layer verifier discriminating tests ---------


def test_verifier_layer_1_raw_flip_identity_mismatch() -> None:
    """Layer 1: missing a single canonical flip triple -> CohortExtractionError."""
    canonical = [
        FlipRecord(t, e, d) for (t, e, d) in sorted(EXPECTED_FLIPS)
    ]
    # Drop one canonical flip to break Layer 1
    bad = canonical[:-1]
    with pytest.raises(CohortExtractionError, match="flip identity mismatch"):
        verify_expected_v2trf_cohort(bad)


def test_verifier_layer_2_ticker_asof_set_mismatch() -> None:
    """Layer 2: asof_date corrupted preserving flip count + raw set membership broken."""
    canonical = [
        FlipRecord(t, e, d) for (t, e, d) in sorted(EXPECTED_FLIPS)
    ]
    # Swap one flip's date; raw set will differ but count preserved -> layer 1 fires.
    bad = canonical[:-1] + [
        FlipRecord(canonical[-1].ticker, canonical[-1].eval_run_id, date(2020, 1, 1))
    ]
    with pytest.raises(CohortExtractionError):
        verify_expected_v2trf_cohort(bad)


def test_verifier_layer_3_count_mismatch() -> None:
    """Layer 3: duplicate flip -> count != EXPECTED_FLIP_COUNT."""
    canonical = [
        FlipRecord(t, e, d) for (t, e, d) in sorted(EXPECTED_FLIPS)
    ]
    bad = canonical + [canonical[0]]  # duplicate one flip
    with pytest.raises(CohortExtractionError):
        verify_expected_v2trf_cohort(bad)


# --------- Sweep_point FLOAT coercion ---------


def test_sweep_point_float_coercion_against_canonical() -> None:
    """sweep_point cells render as '1.005'; float() coerces correctly + filter holds."""
    # If int() were applied to '1.005', it would raise ValueError -> 0 rows;
    # the FLOAT path yields 67. Round-trip is the discriminating evidence.
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    assert len(flips) == EXPECTED_FLIP_COUNT


def test_sweep_point_tolerance_in_filter() -> None:
    """Filter uses abs(sp - 1.005) <= 1e-9 (FLOAT comparison with tolerance)."""
    # Construct a synthetic markdown that puts a single watch->aplus row at sp=1.005
    # plus an off-tolerance row at sp=1.0050000005 (within 1e-9 tolerance) plus
    # an out-of-tolerance row at sp=1.006. Expect 2 admitted (the in-tolerance ones).
    md = (
        "# Test\n\n"
        "## section\n\n"
        f"### {V2TRF_VARIABLE_NAME}\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket | old_criterion_failure | bucket_via_surrogate |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| ABC | 99 | 2026-05-01 | 1.005 | watch | aplus | (none) | no |\n"
        "| DEF | 98 | 2026-04-30 | 1.0050000005 | watch | aplus | (none) | no |\n"
        "| GHI | 97 | 2026-04-29 | 1.006 | watch | aplus | (none) | no |\n"
    )
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write(md)
        tmp_path = Path(tf.name)
    try:
        flips = extract_flips_from_sensitivity_md(tmp_path)
        assert len(flips) == 2
        assert {f.ticker for f in flips} == {"ABC", "DEF"}
    finally:
        tmp_path.unlink()


# --------- Section-boundary discipline ---------


def test_section_boundary_stops_at_next_h3(tmp_path: Path) -> None:
    """Parser must NOT bleed past the next h3 heading line into adjacent sections."""
    md = (
        f"### {V2TRF_VARIABLE_NAME}\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ABC | 99 | 2026-05-01 | 1.005 | watch | aplus |\n"
        "\n"
        "### vcp.other_variable\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ZZZ | 1 | 2020-01-01 | 1.005 | watch | aplus |\n"
    )
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md_path)
    assert {f.ticker for f in flips} == {"ABC"}


def test_section_boundary_stops_at_next_h2(tmp_path: Path) -> None:
    """Parser must stop at next h2 heading line as well as h3."""
    md = (
        f"### {V2TRF_VARIABLE_NAME}\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ABC | 99 | 2026-05-01 | 1.005 | watch | aplus |\n"
        "\n"
        "## Other top-level section\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ZZZ | 1 | 2020-01-01 | 1.005 | watch | aplus |\n"
    )
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md_path)
    assert {f.ticker for f in flips} == {"ABC"}


def test_missing_section_heading_raises(tmp_path: Path) -> None:
    """No `### vcp.tightness_range_factor` heading anywhere -> CohortExtractionError."""
    md = "# no relevant section here"
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="line-anchored heading"):
        extract_flips_from_sensitivity_md(md_path)


def test_missing_required_column_raises(tmp_path: Path) -> None:
    """Table missing a required column -> CohortExtractionError."""
    md = (
        f"### {V2TRF_VARIABLE_NAME}\n\n"
        # Missing data_asof_date column
        "| ticker | eval_run_id | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| ABC | 99 | 1.005 | watch | aplus |\n"
    )
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="missing required columns"):
        extract_flips_from_sensitivity_md(md_path)


# --------- Filter selectivity tests ---------


def test_filter_rejects_non_watch_old_bucket(tmp_path: Path) -> None:
    """skip->aplus row at sp=1.005 is NOT admitted."""
    md = (
        f"### {V2TRF_VARIABLE_NAME}\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ABC | 99 | 2026-05-01 | 1.005 | skip | aplus |\n"
        "| DEF | 98 | 2026-05-01 | 1.005 | watch | aplus |\n"
    )
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md_path)
    assert {f.ticker for f in flips} == {"DEF"}


def test_filter_rejects_non_aplus_new_bucket(tmp_path: Path) -> None:
    """watch->skip row at sp=1.005 is NOT admitted."""
    md = (
        f"### {V2TRF_VARIABLE_NAME}\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ABC | 99 | 2026-05-01 | 1.005 | watch | skip |\n"
        "| DEF | 98 | 2026-05-01 | 1.005 | watch | aplus |\n"
    )
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md_path)
    assert {f.ticker for f in flips} == {"DEF"}


def test_filter_rejects_other_sweep_points(tmp_path: Path) -> None:
    """watch->aplus row at sp=1.01 is NOT admitted (only sp=1.005 admitted)."""
    md = (
        f"### {V2TRF_VARIABLE_NAME}\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ABC | 99 | 2026-05-01 | 1.01 | watch | aplus |\n"
        "| DEF | 98 | 2026-05-01 | 1.005 | watch | aplus |\n"
    )
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md_path)
    assert {f.ticker for f in flips} == {"DEF"}


# --------- write_cohort_csv + write_flips_audit_json ---------


def test_write_cohort_csv_deduplicates_and_sorts(tmp_path: Path) -> None:
    """CSV emits unique (ticker, asof) sorted by asof desc + ticker asc."""
    flips = [
        FlipRecord("ABC", 1, date(2026, 5, 1)),
        FlipRecord("ABC", 2, date(2026, 5, 1)),  # duplicate (ticker, asof)
        FlipRecord("DEF", 3, date(2026, 5, 2)),
    ]
    csv_path = tmp_path / "cohort.csv"
    n = write_cohort_csv(flips, csv_path)
    assert n == 2
    content = csv_path.read_text(encoding="utf-8")
    lines = content.strip().splitlines()
    assert lines[0] == "ticker,asof_date,cohort_label"
    # Sort: asof desc, ticker asc -> DEF 2026-05-02 first, ABC 2026-05-01 next
    assert lines[1].startswith("DEF,2026-05-02,")
    assert lines[2].startswith("ABC,2026-05-01,")
    assert all(V2TRF_COHORT_LABEL in line for line in lines[1:])


def test_write_flips_audit_json_preserves_all_eval_runs(tmp_path: Path) -> None:
    """Audit JSON preserves all 67 raw flips with eval_run_id audit metadata."""
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    audit_path = tmp_path / "audit.json"
    n = write_flips_audit_json(
        flips, audit_path, source_sensitivity_md=CANONICAL_SOURCE
    )
    assert n == EXPECTED_FLIP_COUNT
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert payload["flip_count"] == EXPECTED_FLIP_COUNT
    assert payload["variable_name"] == V2TRF_VARIABLE_NAME
    assert payload["sweep_point"] == V2TRF_SWEEP_POINT
    assert payload["old_bucket"] == V2TRF_OLD_BUCKET
    assert payload["new_bucket"] == V2TRF_NEW_BUCKET
    assert payload["cohort_label"] == V2TRF_COHORT_LABEL
    assert payload["cohort_selection_method"] == "v2_binding_variable_flips"
    assert payload["v2_binding_variable"] == V2TRF_VARIABLE_NAME
    assert payload["source_sensitivity_md_sha256"] == CANONICAL_SOURCE_SHA256
    assert payload["source_sensitivity_md_size_bytes"] == CANONICAL_SOURCE_SIZE_BYTES
    assert len(payload["flips"]) == EXPECTED_FLIP_COUNT
    parsed = {
        (row["ticker"], row["eval_run_id"], date.fromisoformat(row["data_asof_date"]))
        for row in payload["flips"]
    }
    assert parsed == EXPECTED_FLIPS


# --------- generate_v2trf_cohort_artifacts (one-call pipeline) ---------


def test_generate_artifacts_against_canonical_source(tmp_path: Path) -> None:
    """One-call generator produces 67-row audit + 29-row CSV against canonical source."""
    csv_path = tmp_path / "cohort.csv"
    artifacts = generate_v2trf_cohort_artifacts(
        source_sensitivity_md=CANONICAL_SOURCE,
        cohort_csv_path=csv_path,
    )
    assert artifacts.raw_flip_count == EXPECTED_FLIP_COUNT
    assert artifacts.unique_ticker_asof_count == EXPECTED_UNIQUE_TICKER_ASOF
    assert artifacts.cohort_csv_path.exists()
    assert artifacts.flips_audit_json_path.exists()


def test_generate_artifacts_refuses_non_canonical_source_without_opt_in(
    tmp_path: Path,
) -> None:
    """Default invocation requires canonical source SHA + size."""
    bad = tmp_path / "fake.md"
    bad.write_text("not canonical", encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="SHA-256 mismatch"):
        generate_v2trf_cohort_artifacts(
            source_sensitivity_md=bad,
            cohort_csv_path=tmp_path / "out.csv",
        )


# --------- Committed-artifact canonical lock ---------


def test_committed_cohort_csv_matches_regenerated() -> None:
    """The committed cohort CSV matches what the canonical generator would emit."""
    assert COMMITTED_COHORT_CSV.exists(), (
        f"missing committed cohort CSV at {COMMITTED_COHORT_CSV}"
    )
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    # Re-emit to a tmp file + diff bytes
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as tf:
        tmp_path = Path(tf.name)
    try:
        write_cohort_csv(flips, tmp_path)
        committed = COMMITTED_COHORT_CSV.read_bytes()
        regenerated = tmp_path.read_bytes()
        assert committed == regenerated, (
            "committed cohort CSV differs from canonical regeneration; "
            "re-run `python -m research.harness.v2_tightness_range_factor.regenerate_cohort`"
        )
    finally:
        tmp_path.unlink()


def test_committed_audit_json_lock() -> None:
    """Committed audit JSON has the canonical 67-flip shape + source SHA lock."""
    assert COMMITTED_AUDIT_JSON.exists(), (
        f"missing committed audit JSON at {COMMITTED_AUDIT_JSON}"
    )
    payload = json.loads(COMMITTED_AUDIT_JSON.read_text(encoding="utf-8"))
    assert payload["flip_count"] == EXPECTED_FLIP_COUNT
    assert payload["variable_name"] == V2TRF_VARIABLE_NAME
    assert payload["sweep_point"] == V2TRF_SWEEP_POINT
    assert payload["source_sensitivity_md_sha256"] == CANONICAL_SOURCE_SHA256
    assert len(payload["flips"]) == EXPECTED_FLIP_COUNT


# --------- CLI --allow-non-canonical-paths flag ---------


def test_cli_default_paths_against_canonical_source() -> None:
    """`python -m research.harness.v2_tightness_range_factor.regenerate_cohort`
    completes successfully against the canonical source + default output paths."""
    result = subprocess.run(
        [sys.executable, "-m", "research.harness.v2_tightness_range_factor.regenerate_cohort"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"regenerate_cohort failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "OK:" in result.stdout


def test_cli_refuses_non_default_paths_without_opt_in(tmp_path: Path) -> None:
    """Non-default cohort_csv path requires --allow-non-canonical-paths."""
    alt_csv = tmp_path / "alt.csv"
    result = subprocess.run(
        [
            sys.executable, "-m",
            "research.harness.v2_tightness_range_factor.regenerate_cohort",
            "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md",
            str(alt_csv),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "non-default cohort CSV path" in result.stderr


# --------- L2 LOCK + ASCII discipline ---------


def test_l2_lock_no_schwab_imports() -> None:
    """V2-TRF module set MUST NOT import schwabdev / yfinance / swing.integrations.schwab."""
    module_dir = Path(cohort_csv.__file__).resolve().parent
    for py in module_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "schwabdev" not in text, f"{py} imports schwabdev"
        assert "yfinance" not in text, f"{py} imports yfinance"
        assert "swing.integrations.schwab" not in text, (
            f"{py} imports swing.integrations.schwab"
        )


def test_ascii_discipline_module_files() -> None:
    """All V2-TRF module files encode as ASCII (gotcha #32 declared scope)."""
    module_dir = Path(cohort_csv.__file__).resolve().parent
    for py in module_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        try:
            text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise AssertionError(f"{py} contains non-ASCII: {exc}") from exc


def test_ascii_discipline_artifact_files() -> None:
    """Committed cohort CSV + audit JSON are ASCII-only."""
    for path in (COMMITTED_COHORT_CSV, COMMITTED_AUDIT_JSON):
        text = path.read_text(encoding="utf-8")
        try:
            text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise AssertionError(f"{path} contains non-ASCII: {exc}") from exc
