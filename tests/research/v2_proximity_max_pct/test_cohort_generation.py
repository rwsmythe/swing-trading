"""V2 proximity_max_pct cohort extraction + verifier tests.

Mirrors v2_tightness_range_factor test architecture (sibling-module
strategy per dispatch brief Sec 4.1). Covers layered verifier / parser
robustness / sweep_point FLOAT coercion / canonical source SHA / audit
JSON shape / CLI flag / committed-artifact lock / L2 LOCK / ASCII.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest

from research.harness.v2_proximity_max_pct import cohort_csv
from research.harness.v2_proximity_max_pct.cohort_csv import (
    CANONICAL_SOURCE_SHA256,
    CANONICAL_SOURCE_SIZE_BYTES,
    EXPECTED_FLIP_COUNT,
    EXPECTED_FLIPS,
    EXPECTED_TICKER_ASOF,
    EXPECTED_TICKERS,
    EXPECTED_UNIQUE_TICKER_ASOF,
    V2PMP_COHORT_LABEL,
    V2PMP_NEW_BUCKET,
    V2PMP_OLD_BUCKET,
    V2PMP_SWEEP_POINT,
    V2PMP_VARIABLE_NAME,
    CohortExtractionError,
    FlipRecord,
    extract_flips_from_sensitivity_md,
    generate_v2pmp_cohort_artifacts,
    verify_canonical_source_identity,
    verify_expected_v2pmp_cohort,
    write_cohort_csv,
    write_flips_audit_json,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_SOURCE = (
    REPO_ROOT / "exports" / "diagnostics"
    / "aplus-sensitivity-v2-20260524T205849Z.md"
)
COMMITTED_COHORT_CSV = (
    REPO_ROOT / "exports" / "research" / "cohorts"
    / "v2_proximity_max_pct_sp7_5.csv"
)
COMMITTED_AUDIT_JSON = (
    REPO_ROOT / "exports" / "research" / "cohorts"
    / "v2_proximity_max_pct_sp7_5.flips_audit.json"
)


def test_module_constants_lock_binding_signal() -> None:
    assert V2PMP_VARIABLE_NAME == "vcp.proximity_max_pct"
    assert V2PMP_SWEEP_POINT == 7.5
    assert V2PMP_OLD_BUCKET == "watch"
    assert V2PMP_NEW_BUCKET == "aplus"
    assert V2PMP_COHORT_LABEL == "v2_vcp_proximity_max_pct_sp7_5"


def test_expected_counts_lock() -> None:
    assert EXPECTED_FLIP_COUNT == 5
    assert EXPECTED_UNIQUE_TICKER_ASOF == 3
    assert len(EXPECTED_TICKERS) == 3
    assert len(EXPECTED_FLIPS) == 5
    assert len(EXPECTED_TICKER_ASOF) == 3


def test_expected_tickers_set_lock() -> None:
    assert EXPECTED_TICKERS == frozenset({"SEI", "YOU", "SLDB"})


def test_canonical_source_sha_lock() -> None:
    assert CANONICAL_SOURCE_SHA256 == (
        "b25bcde944c33c7a44d049167e78e9d5c7b3d4fc5538ccc5e9cdc8e01e27a143"
    )
    assert CANONICAL_SOURCE_SIZE_BYTES == 830034


def test_canonical_source_file_matches_sha_lock() -> None:
    assert CANONICAL_SOURCE.exists()
    h = hashlib.sha256()
    with CANONICAL_SOURCE.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    assert h.hexdigest() == CANONICAL_SOURCE_SHA256
    assert CANONICAL_SOURCE.stat().st_size == CANONICAL_SOURCE_SIZE_BYTES


def test_verify_canonical_source_identity_passes_on_canonical() -> None:
    verify_canonical_source_identity(CANONICAL_SOURCE)


def test_verify_canonical_source_identity_raises_on_mismatch(tmp_path: Path) -> None:
    bad = tmp_path / "fake.md"
    bad.write_text("not canonical", encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="SHA-256 mismatch"):
        verify_canonical_source_identity(bad)


def test_verify_canonical_source_identity_raises_on_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        verify_canonical_source_identity(tmp_path / "nope.md")


def test_extract_against_canonical_source_yields_5_flips() -> None:
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    assert len(flips) == 5


def test_extract_against_canonical_source_matches_expected_flips() -> None:
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    parsed = {(f.ticker, f.eval_run_id, f.data_asof_date) for f in flips}
    assert parsed == EXPECTED_FLIPS


def test_verify_expected_v2pmp_cohort_passes_on_canonical() -> None:
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    verify_expected_v2pmp_cohort(flips)


def test_verifier_layer_1_raw_flip_identity_mismatch() -> None:
    canonical = [FlipRecord(t, e, d) for (t, e, d) in sorted(EXPECTED_FLIPS)]
    bad = canonical[:-1]
    with pytest.raises(CohortExtractionError, match="flip identity mismatch"):
        verify_expected_v2pmp_cohort(bad)


def test_verifier_layer_3_count_mismatch() -> None:
    canonical = [FlipRecord(t, e, d) for (t, e, d) in sorted(EXPECTED_FLIPS)]
    bad = canonical + [canonical[0]]
    with pytest.raises(CohortExtractionError):
        verify_expected_v2pmp_cohort(bad)


def test_sweep_point_float_coercion_against_canonical() -> None:
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    assert len(flips) == EXPECTED_FLIP_COUNT


def test_section_boundary_stops_at_next_h3(tmp_path: Path) -> None:
    md = (
        f"### {V2PMP_VARIABLE_NAME}\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ABC | 99 | 2026-05-01 | 7.5 | watch | aplus |\n"
        "\n"
        "### vcp.other_variable\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ZZZ | 1 | 2020-01-01 | 7.5 | watch | aplus |\n"
    )
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md_path)
    assert {f.ticker for f in flips} == {"ABC"}


def test_missing_section_heading_raises(tmp_path: Path) -> None:
    md = "# no relevant section"
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="line-anchored heading"):
        extract_flips_from_sensitivity_md(md_path)


def test_filter_rejects_other_sweep_points(tmp_path: Path) -> None:
    md = (
        f"### {V2PMP_VARIABLE_NAME}\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ABC | 99 | 2026-05-01 | 8.0 | watch | aplus |\n"
        "| DEF | 98 | 2026-05-01 | 7.5 | watch | aplus |\n"
    )
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md_path)
    assert {f.ticker for f in flips} == {"DEF"}


def test_filter_rejects_non_watch_old_bucket(tmp_path: Path) -> None:
    md = (
        f"### {V2PMP_VARIABLE_NAME}\n\n"
        "| ticker | eval_run_id | data_asof_date | sweep_point | old_bucket | new_bucket |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ABC | 99 | 2026-05-01 | 7.5 | skip | aplus |\n"
        "| DEF | 98 | 2026-05-01 | 7.5 | watch | aplus |\n"
    )
    md_path = tmp_path / "test.md"
    md_path.write_text(md, encoding="utf-8")
    flips = extract_flips_from_sensitivity_md(md_path)
    assert {f.ticker for f in flips} == {"DEF"}


def test_write_cohort_csv_deduplicates_and_sorts(tmp_path: Path) -> None:
    flips = [
        FlipRecord("ABC", 1, date(2026, 5, 1)),
        FlipRecord("ABC", 2, date(2026, 5, 1)),
        FlipRecord("DEF", 3, date(2026, 5, 2)),
    ]
    csv_path = tmp_path / "cohort.csv"
    n = write_cohort_csv(flips, csv_path)
    assert n == 2
    content = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert content[0] == "ticker,asof_date,cohort_label"
    assert content[1].startswith("DEF,2026-05-02,")


def test_write_flips_audit_json_preserves_eval_runs(tmp_path: Path) -> None:
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    audit_path = tmp_path / "audit.json"
    n = write_flips_audit_json(
        flips, audit_path, source_sensitivity_md=CANONICAL_SOURCE
    )
    assert n == EXPECTED_FLIP_COUNT
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert payload["flip_count"] == EXPECTED_FLIP_COUNT
    assert payload["variable_name"] == V2PMP_VARIABLE_NAME
    assert payload["sweep_point"] == V2PMP_SWEEP_POINT
    assert payload["cohort_label"] == V2PMP_COHORT_LABEL
    assert payload["cohort_selection_method"] == "v2_binding_variable_flips"
    parsed = {
        (row["ticker"], row["eval_run_id"], date.fromisoformat(row["data_asof_date"]))
        for row in payload["flips"]
    }
    assert parsed == EXPECTED_FLIPS


def test_generate_artifacts_against_canonical_source(tmp_path: Path) -> None:
    csv_path = tmp_path / "cohort.csv"
    artifacts = generate_v2pmp_cohort_artifacts(
        source_sensitivity_md=CANONICAL_SOURCE,
        cohort_csv_path=csv_path,
    )
    assert artifacts.raw_flip_count == EXPECTED_FLIP_COUNT
    assert artifacts.unique_ticker_asof_count == EXPECTED_UNIQUE_TICKER_ASOF
    assert artifacts.cohort_csv_path.exists()
    assert artifacts.flips_audit_json_path.exists()


def test_generate_artifacts_refuses_non_canonical_source(tmp_path: Path) -> None:
    bad = tmp_path / "fake.md"
    bad.write_text("not canonical", encoding="utf-8")
    with pytest.raises(CohortExtractionError, match="SHA-256 mismatch"):
        generate_v2pmp_cohort_artifacts(
            source_sensitivity_md=bad,
            cohort_csv_path=tmp_path / "out.csv",
        )


def test_committed_cohort_csv_matches_regenerated() -> None:
    assert COMMITTED_COHORT_CSV.exists()
    flips = extract_flips_from_sensitivity_md(CANONICAL_SOURCE)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as tf:
        tmp_path = Path(tf.name)
    try:
        write_cohort_csv(flips, tmp_path)
        assert COMMITTED_COHORT_CSV.read_bytes() == tmp_path.read_bytes()
    finally:
        tmp_path.unlink()


def test_committed_audit_json_lock() -> None:
    assert COMMITTED_AUDIT_JSON.exists()
    payload = json.loads(COMMITTED_AUDIT_JSON.read_text(encoding="utf-8"))
    assert payload["flip_count"] == EXPECTED_FLIP_COUNT
    assert payload["variable_name"] == V2PMP_VARIABLE_NAME
    assert payload["sweep_point"] == V2PMP_SWEEP_POINT
    assert payload["source_sensitivity_md_sha256"] == CANONICAL_SOURCE_SHA256


def test_cli_default_paths_against_canonical_source() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "research.harness.v2_proximity_max_pct.regenerate_cohort"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "OK:" in result.stdout


def test_cli_refuses_non_default_paths_without_opt_in(tmp_path: Path) -> None:
    alt = tmp_path / "alt.csv"
    result = subprocess.run(
        [
            sys.executable, "-m",
            "research.harness.v2_proximity_max_pct.regenerate_cohort",
            "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md",
            str(alt),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "non-default cohort CSV path" in result.stderr


def test_l2_lock_no_schwab_imports() -> None:
    module_dir = Path(cohort_csv.__file__).resolve().parent
    for py in module_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "schwabdev" not in text
        assert "yfinance" not in text
        assert "swing.integrations.schwab" not in text


def test_ascii_discipline_module_files() -> None:
    module_dir = Path(cohort_csv.__file__).resolve().parent
    for py in module_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        text.encode("ascii")  # raises on non-ASCII


def test_ascii_discipline_artifact_files() -> None:
    for path in (COMMITTED_COHORT_CSV, COMMITTED_AUDIT_JSON):
        path.read_text(encoding="utf-8").encode("ascii")
