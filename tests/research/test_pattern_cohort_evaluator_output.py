"""Tests for pattern cohort harness output module (CSV + markdown + manifest JSON)."""
from __future__ import annotations

import csv
import json
from datetime import date

from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
)
from research.harness.pattern_cohort_evaluator.detector_invoker import (
    CohortRunResult,
    CohortVerdict,
)
from research.harness.pattern_cohort_evaluator.output import (
    _CSV_HEADERS,
    write_manifest_json,
    write_results_csv,
    write_summary_markdown,
)


def _empty_result() -> CohortRunResult:
    return CohortRunResult(
        cohort_entries_count=0,
        cohort_unique_tickers_count=0,
        cohort_unique_asof_dates_count=0,
        verdicts=(),
        entries_processed=0,
        verdicts_emitted=0,
        skipped_entries={
            "coverage_skip": 0, "archive_missing_skip": 0,
            "window_generation_error": 0, "no_windows": 0,
            "detector_error_all": 0,
        },
        both_exist_diagnostic=BothExistDiagnostic(),
        pattern_exemplars_corpus_size_at_invocation=0,
        pattern_exemplars_filtered_size=0,
        detectors_invoked=("vcp", "flat_base", "cup_with_handle",
                           "high_tight_flag", "double_bottom_w"),
        window_mode="per-window",
        template_match_mode="off",
        runtime_seconds=1.234,
    )


def _verdict(*, skip: str | None = None, **kwargs) -> CohortVerdict:
    defaults = {
        "cohort_entry_id": 0, "cohort_label": None, "ticker": "X",
        "asof_date": date(2026, 4, 15),
        "candidate_id": None, "eval_run_id": None,
        "persisted_bucket": None, "persisted_pivot": None,
        "persisted_initial_stop": None,
        "window_index": None, "window_start_date": None, "window_end_date": None,
        "anchor_date": None, "anchor_reason": None,
        "pattern_class": None, "detector_version": None, "stage_observed": None,
        "geometric_score": None, "template_match_score": None,
        "composite_score": None,
        "template_match_nearest_exemplar_ids_json": None,
        "criteria_pass_json": None, "structural_evidence_json": None,
        "skip_reason": skip,
    }
    defaults.update(kwargs)
    return CohortVerdict(**defaults)


def _result_with_verdicts(*verdicts: CohortVerdict) -> CohortRunResult:
    r = _empty_result()
    return CohortRunResult(
        cohort_entries_count=1,
        cohort_unique_tickers_count=1,
        cohort_unique_asof_dates_count=1,
        verdicts=verdicts,
        entries_processed=1,
        verdicts_emitted=sum(1 for v in verdicts if v.skip_reason is None),
        skipped_entries=r.skipped_entries,
        both_exist_diagnostic=r.both_exist_diagnostic,
        pattern_exemplars_corpus_size_at_invocation=10,
        pattern_exemplars_filtered_size=8,
        detectors_invoked=r.detectors_invoked,
        window_mode="per-window",
        template_match_mode="on",
        runtime_seconds=2.5,
    )


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def test_csv_headers_24_columns_per_spec_lock():
    assert len(_CSV_HEADERS) == 24


def test_write_results_csv_header_only_empty_result(tmp_path):
    p = tmp_path / "results.csv"
    write_results_csv(_empty_result(), p)
    with p.open() as f:
        rows = list(csv.reader(f))
    assert len(rows) == 1
    assert tuple(rows[0]) == _CSV_HEADERS


def test_write_results_csv_non_skip_row(tmp_path):
    p = tmp_path / "results.csv"
    v = _verdict(
        pattern_class="vcp",
        detector_version="v1.0.0",
        stage_observed="stage_2",
        geometric_score=0.65,
        template_match_score=0.8,
        composite_score=0.71,
        window_index=0,
        window_start_date=date(2026, 3, 1),
        window_end_date=date(2026, 4, 1),
        anchor_date=date(2026, 3, 1),
        anchor_reason="zigzag_pivot:test",
        structural_evidence_json='{"k":"v"}',
    )
    write_results_csv(_result_with_verdicts(v), p)
    with p.open() as f:
        rows = list(csv.reader(f))
    assert len(rows) == 2
    data = dict(zip(rows[0], rows[1], strict=False))
    assert data["pattern_class"] == "vcp"
    assert data["detector_version"] == "v1.0.0"
    assert data["geometric_score"] == "0.650000"
    assert data["composite_score"] == "0.710000"
    assert data["skip_reason"] == ""


def test_write_results_csv_skip_row_emits_empty_columns(tmp_path):
    p = tmp_path / "results.csv"
    v = _verdict(skip="coverage_skip")
    write_results_csv(_result_with_verdicts(v), p)
    with p.open() as f:
        rows = list(csv.reader(f))
    data = dict(zip(rows[0], rows[1], strict=False))
    assert data["skip_reason"] == "coverage_skip"
    assert data["pattern_class"] == ""
    assert data["composite_score"] == ""


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def test_write_summary_markdown_empty_renders_none_placeholders(tmp_path):
    p = tmp_path / "summary.md"
    write_summary_markdown(
        _empty_result(),
        p,
        cohort_input_mode="inline",
        cohort_input_path=None,
        harness_version="0.1.0",
    )
    body = p.read_text()
    assert "# Pattern Cohort Detector Evaluator Summary" in body
    assert "| (none) | 0 | 0 | 0 | 0 | (none) |" in body
    assert "(none) -- no non-skip verdicts emitted" in body
    assert "## Skip-reason summary" in body
    # cp1252-safe (raises if not)
    body.encode("cp1252")


def test_write_summary_markdown_with_verdicts_renders_per_class_table(tmp_path):
    p = tmp_path / "summary.md"
    v = _verdict(
        pattern_class="vcp",
        composite_score=0.85,
        geometric_score=0.85,
        stage_observed="stage_2",
        window_index=0,
    )
    write_summary_markdown(
        _result_with_verdicts(v),
        p,
        cohort_input_mode="csv",
        cohort_input_path=tmp_path / "cohort.csv",
        harness_version="0.1.0",
    )
    body = p.read_text()
    assert "### vcp" in body
    assert "0.8500" in body


def test_write_summary_markdown_renders_both_exist_banner_when_count_positive(tmp_path):
    p = tmp_path / "summary.md"
    diag = BothExistDiagnostic()
    diag.count = 1
    diag.affected_tickers.append("ZZBOTH")
    r = _empty_result()
    r = CohortRunResult(
        cohort_entries_count=r.cohort_entries_count,
        cohort_unique_tickers_count=r.cohort_unique_tickers_count,
        cohort_unique_asof_dates_count=r.cohort_unique_asof_dates_count,
        verdicts=r.verdicts, entries_processed=r.entries_processed,
        verdicts_emitted=r.verdicts_emitted, skipped_entries=r.skipped_entries,
        both_exist_diagnostic=diag,
        pattern_exemplars_corpus_size_at_invocation=0,
        pattern_exemplars_filtered_size=0,
        detectors_invoked=r.detectors_invoked,
        window_mode=r.window_mode, template_match_mode=r.template_match_mode,
        runtime_seconds=r.runtime_seconds,
    )
    write_summary_markdown(
        r, p, cohort_input_mode="inline", cohort_input_path=None,
        harness_version="0.1.0",
    )
    body = p.read_text()
    assert "Both-exist diagnostic" in body
    assert "ZZBOTH" in body


def test_markdown_is_ascii_only(tmp_path):
    """Cumulative Windows cp1252 stdout gotcha: ALL markdown must be cp1252-safe."""
    p = tmp_path / "summary.md"
    write_summary_markdown(
        _empty_result(), p,
        cohort_input_mode="inline", cohort_input_path=None,
        harness_version="0.1.0",
    )
    body = p.read_text()
    body.encode("cp1252")  # raises if non-cp1252 glyph slipped in


# ---------------------------------------------------------------------------
# Manifest JSON
# ---------------------------------------------------------------------------

def test_write_manifest_json_emits_required_keys(tmp_path):
    p = tmp_path / "manifest.json"
    write_manifest_json(
        _empty_result(), p,
        cohort_input_mode="inline",
        cohort_input_path=None,
        cache_dir=tmp_path / "cache",
        db_path=tmp_path / "swing.db",
        harness_version="0.1.0",
    )
    data = json.loads(p.read_text())
    required = {
        "harness_version", "cohort_input_mode", "cohort_input_sha256",
        "cohort_entries_count", "cohort_unique_tickers_count",
        "cohort_unique_asof_dates_count", "db_path", "cache_dir",
        "ohlcv_reader_module", "ohlcv_reader_signature_hash",
        "pattern_exemplars_corpus_size_at_invocation",
        "pattern_exemplars_corpus_filter", "pattern_exemplars_filtered_size",
        "detectors_invoked", "window_mode", "template_match_mode",
        "started_at_utc", "finished_at_utc", "runtime_seconds",
        "entries_processed", "verdicts_emitted", "skipped_entries",
        "both_exist_diagnostic", "l2_lock_preserved",
    }
    assert required.issubset(set(data.keys()))
    assert data["l2_lock_preserved"] is True
    assert data["ohlcv_reader_module"] == (
        "research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader"
    )


def test_write_manifest_json_csv_input_includes_sha256(tmp_path):
    cohort_csv = tmp_path / "cohort.csv"
    cohort_csv.write_text("ticker,asof_date\nRLMD,2026-04-15\n", encoding="utf-8")
    p = tmp_path / "manifest.json"
    write_manifest_json(
        _empty_result(), p,
        cohort_input_mode="csv",
        cohort_input_path=cohort_csv,
        cache_dir=tmp_path / "cache",
        db_path=tmp_path / "swing.db",
        harness_version="0.1.0",
    )
    data = json.loads(p.read_text())
    assert data["cohort_input_sha256"] is not None
    assert len(data["cohort_input_sha256"]) == 64


def test_write_manifest_json_inline_input_has_null_sha(tmp_path):
    p = tmp_path / "manifest.json"
    write_manifest_json(
        _empty_result(), p,
        cohort_input_mode="inline",
        cohort_input_path=None,
        cache_dir=tmp_path / "cache",
        db_path=tmp_path / "swing.db",
        harness_version="0.1.0",
    )
    data = json.loads(p.read_text())
    assert data["cohort_input_sha256"] is None
    assert data["cohort_input_path"] is None
