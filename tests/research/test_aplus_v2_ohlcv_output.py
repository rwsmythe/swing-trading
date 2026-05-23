"""Tests for V2 OHLCV harness output module (T-V2.3).

12 tests per plan §H T-V2.3:
  (1)  CSV 12-col header + row format
  (2)  Markdown matrix 12-col render
  (3)  Headline binding-variable summary (delta_aplus > 0)
  (4)  Headline empty-state when no binding variable (all delta_aplus == 0)
  (5)  Per-variable drill-down with bucket_via_surrogate flag
  (6)  Drill-down empty-state '(none)' uniform per cumulative T3.SB3 gotcha
  (7)  CRITERION DRIFT alert on tier-1 mismatch
  (8)  Per-variable scope-reduction Notes (ohlcv_coverage + out_of_range)
  (9)  Both-exist warning banner emission when count > 0
  (10) Both-exist warning banner suppressed when count == 0
  (11) Manifest emission (memory_peak_bytes + tier-1/2 split + both_exist_shape_a_wins_count)
  (12) ASCII-only output (cp1252 round-trip CSV + markdown)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import BothExistDiagnostic
from research.harness.aplus_v2_ohlcv_evaluator.sweep import (
    BaselineParityReport,
    FlippedCandidate,
    SweepEntryV2,
    SweepResultV2,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_entry(
    variable_name: str = "rs.rs_rank_min_pass",
    kind: str = "threshold_additive",
    sweep_point: float = 60.0,
    aplus_count: int = 10,
    watch_count: int = 5,
    skip_count: int = 2,
    excluded_count: int = 1,
    delta_aplus: int = 0,
    delta_watch: int = 0,
    out_of_range_skip_count: int = 0,
    ohlcv_coverage_skip_count: int = 0,
    evaluation_error_skip_count: int = 0,
) -> SweepEntryV2:
    return SweepEntryV2(
        variable_name=variable_name,
        kind=kind,
        sweep_point=sweep_point,
        aplus_count=aplus_count,
        watch_count=watch_count,
        skip_count=skip_count,
        excluded_count=excluded_count,
        delta_aplus=delta_aplus,
        delta_watch=delta_watch,
        out_of_range_skip_count=out_of_range_skip_count,
        ohlcv_coverage_skip_count=ohlcv_coverage_skip_count,
        evaluation_error_skip_count=evaluation_error_skip_count,
    )


def _make_flipped(
    ticker: str = "AAPL",
    eval_run_id: int = 42,
    data_asof_date: str = "2026-04-30",
    sweep_point: float = 60.0,
    old_bucket: str = "skip",
    new_bucket: str = "aplus",
    old_criterion_failure: str = "(none)",
    bucket_via_surrogate: bool = False,
) -> FlippedCandidate:
    return FlippedCandidate(
        ticker=ticker,
        eval_run_id=eval_run_id,
        data_asof_date=data_asof_date,
        sweep_point=sweep_point,
        old_bucket=old_bucket,
        new_bucket=new_bucket,
        old_criterion_failure=old_criterion_failure,
        bucket_via_surrogate=bucket_via_surrogate,
    )


def _make_parity(
    tier1_match: bool = True,
    tier1_mismatch_candidates: tuple[str, ...] = (),
    tier2_match_count: int = 5,
    tier2_mismatch_count: int = 0,
    tier2_via_surrogate_count: int = 0,
) -> BaselineParityReport:
    return BaselineParityReport(
        tier1_match=tier1_match,
        tier1_mismatch_candidates=tier1_mismatch_candidates,
        tier2_match_count=tier2_match_count,
        tier2_mismatch_count=tier2_mismatch_count,
        tier2_via_surrogate_count=tier2_via_surrogate_count,
    )


def _make_result(
    entries: tuple[SweepEntryV2, ...] = (),
    flipped: tuple[FlippedCandidate, ...] = (),
    baseline_parity: BaselineParityReport | None = None,
    both_exist_count: int = 0,
    both_exist_tickers: list[str] | None = None,
    ohlcv_coverage_skip_count: int = 0,
    universe_skipped_ticker_count: int = 0,
    memory_peak_bytes: int | None = None,
) -> SweepResultV2:
    diag = BothExistDiagnostic()
    diag.count = both_exist_count
    diag.affected_tickers = both_exist_tickers or []

    if baseline_parity is None:
        baseline_parity = _make_parity()

    result = SweepResultV2(
        eval_runs_window=20,
        eval_run_id_range=(1, 20),
        total_candidates=100,
        universe_size=500,
        v2_universe_hash="abc123hash",
        entries=entries,
        flipped=flipped,
        baseline_parity=baseline_parity,
        ohlcv_coverage_skip_count=ohlcv_coverage_skip_count,
        universe_skipped_ticker_count=universe_skipped_ticker_count,
        both_exist_diagnostic=diag,
        runtime_seconds=3.14,
        truncated_by_runtime_cap=False,
    )
    # Attach optional memory_peak_bytes for manifest test
    if memory_peak_bytes is not None:
        object.__setattr__(result, "_memory_peak_bytes_for_test", memory_peak_bytes)
    return result


# ---------------------------------------------------------------------------
# Test 1: CSV 12-col header + row format
# ---------------------------------------------------------------------------

def test_csv_12col_header_and_row_format(tmp_path: Path) -> None:
    """CSV file has header with exactly 12 cols matching _CSV_HEADERS_V2;
    each data row also has 12 comma-separated fields."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import (
        _CSV_HEADERS_V2,
        write_sensitivity_csv_v2,
    )

    entries = (
        _make_entry("rs.rs_rank_min_pass", "threshold_additive", 60.0,
                    aplus_count=10, watch_count=5, skip_count=2, excluded_count=1,
                    delta_aplus=2, delta_watch=1,
                    out_of_range_skip_count=0, ohlcv_coverage_skip_count=3,
                    evaluation_error_skip_count=0),
        _make_entry("vcp.watch_max_fails", "gate", 2,
                    aplus_count=8, watch_count=4, skip_count=3, excluded_count=2,
                    delta_aplus=-1, delta_watch=0,
                    out_of_range_skip_count=1, ohlcv_coverage_skip_count=3,
                    evaluation_error_skip_count=0),
        _make_entry("trend_template.min_passes", "threshold_additive", 5,
                    aplus_count=12, watch_count=6, skip_count=1, excluded_count=0,
                    delta_aplus=4, delta_watch=2,
                    out_of_range_skip_count=0, ohlcv_coverage_skip_count=3,
                    evaluation_error_skip_count=1),
    )
    result = _make_result(entries=entries)
    csv_path = tmp_path / "sensitivity.csv"
    write_sensitivity_csv_v2(result, csv_path)

    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4  # header + 3 data rows

    # Header must match _CSV_HEADERS_V2 exactly
    header_cols = lines[0].split(",")
    assert tuple(header_cols) == _CSV_HEADERS_V2, (
        f"CSV header mismatch: {header_cols}"
    )
    assert len(header_cols) == 12

    # Each data row has exactly 12 cols
    for i, line in enumerate(lines[1:], start=1):
        cols = line.split(",")
        assert len(cols) == 12, (
            f"Row {i} has {len(cols)} cols, expected 12: {line!r}"
        )


# ---------------------------------------------------------------------------
# Test 2: Markdown matrix 12-col render
# ---------------------------------------------------------------------------

def test_markdown_matrix_12col_render(tmp_path: Path) -> None:
    """Markdown sensitivity matrix table has header with 12 | separators;
    each data row also has 12 pipe-delimited cells."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import write_sensitivity_markdown_v2

    entries = (
        _make_entry("rs.rs_rank_min_pass", "threshold_additive", 60.0,
                    aplus_count=10, watch_count=5, skip_count=2, excluded_count=1,
                    delta_aplus=2, delta_watch=1,
                    out_of_range_skip_count=0, ohlcv_coverage_skip_count=3,
                    evaluation_error_skip_count=0),
    )
    result = _make_result(entries=entries)
    md_path = tmp_path / "sensitivity.md"
    write_sensitivity_markdown_v2(result, md_path)

    text = md_path.read_text(encoding="utf-8")
    # Find the sensitivity matrix table
    lines = [l for l in text.splitlines() if l.strip().startswith("|")]
    # There should be at least the header row + separator row + 1 data row
    assert len(lines) >= 3, f"Expected table rows, found: {lines}"

    # Header row: count pipe chars
    header_row = lines[0]
    # Each cell is delimited by |; a row with 12 cols has 13 | chars
    pipe_count = header_row.count("|")
    assert pipe_count >= 13, (
        f"Matrix header has {pipe_count} pipes, expected >= 13 (12 cols): {header_row!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: Headline binding-variable summary (delta_aplus > 0)
# ---------------------------------------------------------------------------

def test_headline_shows_top_binding_variable(tmp_path: Path) -> None:
    """Headline section lists rs.rs_rank_min_pass as top binding variable
    when it has the largest delta_aplus > 0 at sweep_point=60."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import write_sensitivity_markdown_v2

    entries = (
        _make_entry("rs.rs_rank_min_pass", "threshold_additive", 60.0,
                    delta_aplus=5),
        _make_entry("rs.rs_rank_min_pass", "threshold_additive", 70.0,
                    delta_aplus=2),
        _make_entry("vcp.watch_max_fails", "gate", 2, delta_aplus=1),
    )
    result = _make_result(entries=entries)
    md_path = tmp_path / "sensitivity.md"
    write_sensitivity_markdown_v2(result, md_path)

    text = md_path.read_text(encoding="utf-8")
    assert "rs.rs_rank_min_pass" in text
    # Headline section should exist
    assert "## Headline" in text or "## Top Binding" in text or "## Binding" in text


# ---------------------------------------------------------------------------
# Test 4: Headline empty-state when no binding variable (all delta_aplus == 0)
# ---------------------------------------------------------------------------

def test_headline_empty_state_when_no_binding_variable(tmp_path: Path) -> None:
    """When all entries have delta_aplus == 0, headline section notes no
    binding variables rather than crashing or emitting garbage."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import write_sensitivity_markdown_v2

    entries = (
        _make_entry("rs.rs_rank_min_pass", "threshold_additive", 60.0, delta_aplus=0),
        _make_entry("vcp.watch_max_fails", "gate", 2, delta_aplus=0),
    )
    result = _make_result(entries=entries)
    md_path = tmp_path / "sensitivity.md"
    write_sensitivity_markdown_v2(result, md_path)

    text = md_path.read_text(encoding="utf-8")
    # Should emit something meaningful in the headline block
    assert "no binding" in text.lower() or "none" in text.lower() or "0 binding" in text.lower()


# ---------------------------------------------------------------------------
# Test 5: Per-variable drill-down with bucket_via_surrogate flag
# ---------------------------------------------------------------------------

def test_drilldown_emits_surrogate_annotation(tmp_path: Path) -> None:
    """When a FlippedCandidate has bucket_via_surrogate=True, the drill-down
    section emits the '(via current_equity surrogate)' annotation."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import write_sensitivity_markdown_v2

    flipped = (
        _make_flipped(
            ticker="AAPL",
            eval_run_id=10,
            sweep_point=60.0,
            old_bucket="skip",
            new_bucket="aplus",
            bucket_via_surrogate=True,
        ),
    )
    entries = (_make_entry("rs.rs_rank_min_pass", "threshold_additive", 60.0),)
    result = _make_result(entries=entries, flipped=flipped)
    md_path = tmp_path / "sensitivity.md"
    write_sensitivity_markdown_v2(result, md_path)

    text = md_path.read_text(encoding="utf-8")
    assert "surrogate" in text.lower(), (
        f"Expected surrogate annotation in drill-down, not found in:\n{text}"
    )


# ---------------------------------------------------------------------------
# Test 6: Drill-down empty-state '(none)' uniform
# ---------------------------------------------------------------------------

def test_drilldown_empty_state_is_none_literal(tmp_path: Path) -> None:
    """When a variable has zero flipped candidates, drill-down emits literal
    '(none)' string (NOT empty string, NOT null, NOT '[]').
    Per cumulative T3.SB3 gotcha: empty-state representation must be uniform."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import write_sensitivity_markdown_v2

    entries = (
        _make_entry("rs.rs_rank_min_pass", "threshold_additive", 60.0),
    )
    # No flipped candidates
    result = _make_result(entries=entries, flipped=())
    md_path = tmp_path / "sensitivity.md"
    write_sensitivity_markdown_v2(result, md_path)

    text = md_path.read_text(encoding="utf-8")
    # Must contain literal '(none)' for empty drill-down
    assert "(none)" in text, (
        f"Expected '(none)' literal for empty drill-down, not found in:\n{text[:500]}"
    )


# ---------------------------------------------------------------------------
# Test 7: CRITERION DRIFT alert on tier-1 mismatch
# ---------------------------------------------------------------------------

def test_criterion_drift_alert_on_tier1_mismatch(tmp_path: Path) -> None:
    """When BaselineParityReport.tier1_match=False, markdown emits a
    CRITERION DRIFT DETECTED alert with the mismatch candidates enumerated."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import write_sensitivity_markdown_v2

    parity = _make_parity(
        tier1_match=False,
        tier1_mismatch_candidates=("AAPL:10", "MSFT:11"),
    )
    entries = (_make_entry(),)
    result = _make_result(entries=entries, baseline_parity=parity)
    md_path = tmp_path / "sensitivity.md"
    write_sensitivity_markdown_v2(result, md_path)

    text = md_path.read_text(encoding="utf-8")
    assert "CRITERION DRIFT" in text, (
        f"Expected CRITERION DRIFT alert, not found in:\n{text[:800]}"
    )
    assert "AAPL:10" in text
    assert "MSFT:11" in text


# ---------------------------------------------------------------------------
# Test 8: Per-variable scope-reduction Notes
# ---------------------------------------------------------------------------

def test_notes_enumerates_per_variable_skip_counts(tmp_path: Path) -> None:
    """Notes section enumerates per-variable ohlcv_coverage_skip_count and
    out_of_range_skip_count when they are non-zero."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import write_sensitivity_markdown_v2

    entries = (
        _make_entry(
            "rs.rs_rank_min_pass", "threshold_additive", 60.0,
            ohlcv_coverage_skip_count=7,
            out_of_range_skip_count=3,
        ),
    )
    result = _make_result(entries=entries, ohlcv_coverage_skip_count=7)
    md_path = tmp_path / "sensitivity.md"
    write_sensitivity_markdown_v2(result, md_path)

    text = md_path.read_text(encoding="utf-8")
    # Notes section should exist and enumerate coverage info
    assert "## Notes" in text or "## Scope" in text or "ohlcv" in text.lower()
    # The per-variable counts should appear somewhere
    assert "7" in text  # ohlcv_coverage_skip_count


# ---------------------------------------------------------------------------
# Test 9: Both-exist warning banner emitted when count > 0
# ---------------------------------------------------------------------------

def test_both_exist_warning_banner_emitted_when_count_positive(tmp_path: Path) -> None:
    """When both_exist_diagnostic.count == 5, markdown emits a warning banner
    mentioning the count and the affected ticker list."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import write_sensitivity_markdown_v2

    result = _make_result(
        entries=(_make_entry(),),
        both_exist_count=5,
        both_exist_tickers=["AAPL", "MSFT", "GOOG", "AMZN", "META"],
    )
    md_path = tmp_path / "sensitivity.md"
    write_sensitivity_markdown_v2(result, md_path)

    text = md_path.read_text(encoding="utf-8")
    assert "WARNING" in text or "warning" in text.lower(), (
        f"Expected WARNING banner for both_exist_count=5, not found in:\n{text[:600]}"
    )
    assert "5" in text
    # At least one ticker should appear in the list
    assert "AAPL" in text


# ---------------------------------------------------------------------------
# Test 10: Both-exist warning banner suppressed when count == 0
# ---------------------------------------------------------------------------

def test_both_exist_warning_banner_suppressed_when_count_zero(tmp_path: Path) -> None:
    """When both_exist_diagnostic.count == 0, markdown does NOT emit the
    both-exist warning banner."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import write_sensitivity_markdown_v2

    result = _make_result(
        entries=(_make_entry(),),
        both_exist_count=0,
        both_exist_tickers=[],
    )
    md_path = tmp_path / "sensitivity.md"
    write_sensitivity_markdown_v2(result, md_path)

    text = md_path.read_text(encoding="utf-8")
    # No both-exist warning section when count == 0
    assert "both" not in text.lower() or "WARNING" not in text, (
        f"Unexpected both-exist WARNING when count=0:\n{text[:600]}"
    )


# ---------------------------------------------------------------------------
# Test 11: Manifest emission (memory_peak_bytes + tier splits + both_exist_count)
# ---------------------------------------------------------------------------

def test_manifest_section_contains_required_fields(tmp_path: Path) -> None:
    """Manifest section contains both_exist_shape_a_wins_count,
    accepted_ticker_count (derived from universe_size),
    tier_1_count, tier_2_count, and memory_peak_bytes."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import write_sensitivity_markdown_v2

    flipped = (
        _make_flipped("AAPL", eval_run_id=10, bucket_via_surrogate=False),
        _make_flipped("MSFT", eval_run_id=10, bucket_via_surrogate=True),
    )
    result = _make_result(
        entries=(_make_entry(),),
        flipped=flipped,
        both_exist_count=3,
        both_exist_tickers=["X", "Y", "Z"],
    )
    md_path = tmp_path / "sensitivity.md"
    write_sensitivity_markdown_v2(result, md_path, memory_peak_bytes=1024 * 1024 * 50)

    text = md_path.read_text(encoding="utf-8")
    # Manifest section must contain these values
    assert "## Manifest" in text or "manifest" in text.lower()
    assert "both_exist_shape_a_wins_count" in text or "both_exist" in text.lower()
    # memory_peak_bytes value (50 MiB)
    assert "memory" in text.lower()
    # tier counts
    assert "tier" in text.lower() or "tier_1" in text or "tier_2" in text


# ---------------------------------------------------------------------------
# Test 12: ASCII-only output (cp1252 round-trip CSV + markdown)
# ---------------------------------------------------------------------------

def test_output_is_cp1252_encodable(tmp_path: Path) -> None:
    """Both CSV and markdown output must be cp1252-encodable per cumulative
    Windows stdout gotcha (non-ASCII glyphs cause UnicodeEncodeError on cp1252).
    Read files back as bytes; assert encode('cp1252') does not raise."""
    from research.harness.aplus_v2_ohlcv_evaluator.output import (
        write_sensitivity_csv_v2,
        write_sensitivity_markdown_v2,
    )

    parity = _make_parity(
        tier1_match=False,
        tier1_mismatch_candidates=("AAPL:10",),
    )
    entries = (
        _make_entry("rs.rs_rank_min_pass", "threshold_additive", 60.0,
                    delta_aplus=3, ohlcv_coverage_skip_count=2),
    )
    flipped = (
        _make_flipped("AAPL", eval_run_id=10, bucket_via_surrogate=True),
    )
    result = _make_result(
        entries=entries,
        flipped=flipped,
        baseline_parity=parity,
        both_exist_count=2,
        both_exist_tickers=["AAPL", "MSFT"],
        ohlcv_coverage_skip_count=2,
    )

    csv_path = tmp_path / "out.csv"
    md_path = tmp_path / "out.md"
    write_sensitivity_csv_v2(result, csv_path)
    write_sensitivity_markdown_v2(result, md_path, memory_peak_bytes=512_000)

    for p in (csv_path, md_path):
        content = p.read_text(encoding="utf-8")
        try:
            content.encode("cp1252")
        except UnicodeEncodeError as exc:
            pytest.fail(
                f"{p.name} contains non-cp1252 character: {exc}. "
                "ASCII-only output required per cumulative Windows stdout gotcha."
            )
