"""Tests for pattern cohort harness detector_invoker.

Covers:
  - Production function signature locks (5 BINDING test #5 per plan §F.5)
  - CohortVerdict / CohortRunResult dataclass validators
  - get_detector_registry returns production tuple
  - invoke_cohort skip-path orchestration (5 enumerated reasons; gotcha #27)
  - per-entry pattern_class_filter precedence (OQ-5 LOCK)
  - window_mode 'last-only' vs 'per-window'
  - template_match_mode 'on' vs 'off'
  - empty cohort -> CohortRunResult with zero counters
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from research.harness.pattern_cohort_evaluator.cohort_reader import CohortEntry
from research.harness.pattern_cohort_evaluator.detector_invoker import (
    CohortRunResult,
    CohortVerdict,
    get_detector_registry,
    invoke_cohort,
)

# ---------------------------------------------------------------------------
# §F.5 BINDING test: production function signatures + cascade-call-graph
# ---------------------------------------------------------------------------

def test_production_function_signatures_unchanged():
    """L2 LOCK reinforcement test #5: lock all 6 production callsites.

    Per cumulative gotcha #17 (Expansion #2 refinement) + #19
    (Expansion #2 sub-refinement cascade-call-graph): brief-vs-actual-
    production-function-signature verification at test time guards against
    future production refactor.
    """
    import inspect
    import typing as _typing

    from swing.data.repos.pattern_exemplars import list_exemplars
    from swing.patterns.composite import compute_composite_score
    from swing.patterns.foundation import (
        current_stage,
        generate_candidate_windows,
    )
    from swing.patterns.template_matching import match_forward
    from swing.pipeline.runner import _pattern_detect_registry

    sig = inspect.signature(_pattern_detect_registry)
    assert list(sig.parameters.keys()) == []
    registry = _pattern_detect_registry()
    assert len(registry) == 5
    assert {p for _, p, _ in registry} == {
        "vcp", "flat_base", "cup_with_handle",
        "high_tight_flag", "double_bottom_w",
    }

    sig = inspect.signature(generate_candidate_windows)
    assert list(sig.parameters.keys()) == [
        "bars", "anchor_search_method", "ticker", "timeframe",
    ]

    sig = inspect.signature(current_stage)
    assert list(sig.parameters.keys()) == ["conn", "ticker", "asof_date"]
    hints = _typing.get_type_hints(current_stage)
    assert hints["asof_date"] is date

    sig = inspect.signature(compute_composite_score)
    assert list(sig.parameters.keys()) == ["geometric", "template_match"]

    sig = inspect.signature(match_forward)
    assert list(sig.parameters.keys()) == [
        "candidate_close_prices",
        "candidate_pattern_class",
        "candidate_ticker",
        "exemplar_corpus",
        "top_k",
        "geometric_score",
    ]

    sig = inspect.signature(list_exemplars)
    assert list(sig.parameters.keys()) == [
        "conn", "pattern_class", "label_source", "limit", "offset",
    ]


# ---------------------------------------------------------------------------
# get_detector_registry
# ---------------------------------------------------------------------------

def test_get_detector_registry_matches_production():
    """OQ-1 LOCK: harness re-imports the EXACT production registry."""
    from swing.pipeline.runner import _pattern_detect_registry
    harness_reg = get_detector_registry()
    prod_reg = _pattern_detect_registry()
    assert harness_reg == prod_reg
    assert len(harness_reg) == 5


# ---------------------------------------------------------------------------
# CohortVerdict.__post_init__
# ---------------------------------------------------------------------------

def test_cohort_verdict_rejects_unknown_skip_reason():
    with pytest.raises(ValueError, match="skip_reason must be one of"):
        CohortVerdict(
            cohort_entry_id=0, cohort_label=None, ticker="X",
            asof_date=date(2026, 4, 15),
            candidate_id=None, eval_run_id=None,
            persisted_bucket=None, persisted_pivot=None, persisted_initial_stop=None,
            window_index=None, window_start_date=None, window_end_date=None,
            anchor_date=None, anchor_reason=None,
            pattern_class=None, detector_version=None, stage_observed=None,
            geometric_score=None, template_match_score=None, composite_score=None,
            template_match_nearest_exemplar_ids_json=None,
            criteria_pass_json=None, structural_evidence_json=None,
            skip_reason="not_a_real_reason",
        )


@pytest.mark.parametrize("reason", [
    "coverage_skip", "archive_missing_skip", "window_generation_error",
    "no_windows", "detector_error_all",
])
def test_cohort_verdict_accepts_enumerated_skip_reasons(reason):
    v = CohortVerdict(
        cohort_entry_id=0, cohort_label=None, ticker="X",
        asof_date=date(2026, 4, 15),
        candidate_id=None, eval_run_id=None,
        persisted_bucket=None, persisted_pivot=None, persisted_initial_stop=None,
        window_index=None, window_start_date=None, window_end_date=None,
        anchor_date=None, anchor_reason=None,
        pattern_class=None, detector_version=None, stage_observed=None,
        geometric_score=None, template_match_score=None, composite_score=None,
        template_match_nearest_exemplar_ids_json=None,
        criteria_pass_json=None, structural_evidence_json=None,
        skip_reason=reason,
    )
    assert v.skip_reason == reason


# ---------------------------------------------------------------------------
# invoke_cohort skip-path orchestration
# ---------------------------------------------------------------------------

def _make_shape_a_parquet(path: Path, n_bars: int = 250, sentinel: float = 100.0):
    dates = pd.date_range(end="2026-04-30", periods=n_bars, freq="B")
    df = pd.DataFrame({
        "asof_date": [d.date().isoformat() for d in dates],
        "open": [sentinel] * n_bars,
        "high": [sentinel + 1.0] * n_bars,
        "low": [sentinel - 1.0] * n_bars,
        "close": [sentinel] * n_bars,
        "volume": [1_000_000] * n_bars,
    })
    df.to_parquet(path, index=False)


@pytest.fixture
def empty_db():
    """In-memory SQLite with minimal pattern_exemplars + candidates tables."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE pattern_exemplars (
            id INTEGER PRIMARY KEY,
            ticker TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            proposed_pattern_class TEXT NOT NULL,
            final_pattern_class TEXT,
            label_source TEXT NOT NULL,
            label_source_actor TEXT NOT NULL,
            final_decision TEXT NOT NULL,
            labeler_evidence_json TEXT,
            reviewer_evidence_json TEXT,
            review_state TEXT NOT NULL,
            review_state_changed_ts TEXT,
            reviewed_ts TEXT,
            created_ts TEXT NOT NULL,
            silver_decision TEXT,
            silver_decided_ts TEXT,
            cli_filter_signature_hash TEXT,
            reviewer_decision TEXT,
            structural_evidence_json TEXT
        );
        CREATE TABLE evaluation_runs (
            id INTEGER PRIMARY KEY,
            session_date TEXT NOT NULL,
            started_ts TEXT NOT NULL
        );
        CREATE TABLE candidates (
            id INTEGER PRIMARY KEY,
            evaluation_run_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            bucket TEXT NOT NULL
        );
        CREATE TABLE candidate_criteria (
            id INTEGER PRIMARY KEY,
            candidate_id INTEGER NOT NULL,
            criterion_key TEXT NOT NULL,
            pass_flag INTEGER NOT NULL
        );
    """)
    return conn


def test_invoke_cohort_empty_input(empty_db, tmp_path):
    result = invoke_cohort(
        (),
        conn=empty_db,
        cache_dir=tmp_path,
        window_mode="per-window",
        template_match_mode="off",
    )
    assert isinstance(result, CohortRunResult)
    assert result.cohort_entries_count == 0
    assert result.entries_processed == 0
    assert result.verdicts_emitted == 0
    assert result.verdicts == ()
    # Per-skip-reason counter present with zero values (uniform empty-state)
    assert set(result.skipped_entries.keys()) == {
        "coverage_skip", "archive_missing_skip", "window_generation_error",
        "no_windows", "detector_error_all",
    }
    assert all(v == 0 for v in result.skipped_entries.values())
    assert result.detectors_invoked == (
        "vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w",
    )


def test_invoke_cohort_archive_missing_skip(empty_db, tmp_path):
    """OhlcvCoverageError raised when neither parquet exists -> coverage_skip."""
    cohort = (CohortEntry(ticker="ZZNONE", asof_date=date(2026, 4, 15)),)
    result = invoke_cohort(
        cohort,
        conn=empty_db,
        cache_dir=tmp_path,
        window_mode="per-window",
        template_match_mode="off",
    )
    # Reader raises OhlcvCoverageError (not FileNotFoundError) when files absent
    assert result.skipped_entries["coverage_skip"] == 1
    assert result.entries_processed == 1
    assert result.verdicts_emitted == 0
    assert len(result.verdicts) == 1
    assert result.verdicts[0].skip_reason == "coverage_skip"


def test_invoke_cohort_no_windows_skip(empty_db, tmp_path, monkeypatch):
    """Detector window generation returns empty list -> no_windows skip."""
    _make_shape_a_parquet(tmp_path / "ZZNOWIN.yfinance.parquet", n_bars=250)
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.generate_candidate_windows",
        lambda *a, **kw: [],
    )
    cohort = (CohortEntry(ticker="ZZNOWIN", asof_date=date(2026, 4, 15)),)
    result = invoke_cohort(
        cohort,
        conn=empty_db,
        cache_dir=tmp_path,
        window_mode="per-window",
        template_match_mode="off",
    )
    assert result.skipped_entries["no_windows"] == 1
    assert result.verdicts[0].skip_reason == "no_windows"


def test_invoke_cohort_window_generation_error_skip(empty_db, tmp_path, monkeypatch):
    """generate_candidate_windows raises -> window_generation_error skip."""
    _make_shape_a_parquet(tmp_path / "ZZWERR.yfinance.parquet", n_bars=250)

    def _raise(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.generate_candidate_windows",
        _raise,
    )
    cohort = (CohortEntry(ticker="ZZWERR", asof_date=date(2026, 4, 15)),)
    result = invoke_cohort(
        cohort,
        conn=empty_db,
        cache_dir=tmp_path,
        window_mode="per-window",
        template_match_mode="off",
    )
    assert result.skipped_entries["window_generation_error"] == 1


def test_invoke_cohort_detector_error_all_skip(empty_db, tmp_path, monkeypatch):
    """All detectors raise -> detector_error_all skip emitted for entry."""
    _make_shape_a_parquet(tmp_path / "ZZALL.yfinance.parquet", n_bars=250)

    from swing.patterns.foundation import CandidateWindow
    window = CandidateWindow(
        ticker="ZZALL",
        timeframe="daily",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 1),
        anchor_date=date(2026, 3, 1),
        anchor_reason="zigzag_pivot:test",
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.generate_candidate_windows",
        lambda *a, **kw: [window],
    )

    # Stub registry: every detector raises
    def _raise(*a, **kw):
        raise RuntimeError("detector boom")

    fake_registry = tuple(
        (_raise, name, "v0.0.0")
        for name in ("vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w")
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.get_detector_registry",
        lambda: fake_registry,
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.current_stage",
        lambda conn, t, d: "undefined",
    )

    cohort = (CohortEntry(ticker="ZZALL", asof_date=date(2026, 4, 15)),)
    result = invoke_cohort(
        cohort,
        conn=empty_db,
        cache_dir=tmp_path,
        window_mode="per-window",
        template_match_mode="off",
    )
    assert result.skipped_entries["detector_error_all"] == 1
    assert result.verdicts[0].skip_reason == "detector_error_all"


# ---------------------------------------------------------------------------
# invoke_cohort happy path with stubbed detectors
# ---------------------------------------------------------------------------

def test_invoke_cohort_emits_one_verdict_per_detector(empty_db, tmp_path, monkeypatch):
    """Happy path: 5 detectors x 1 window = 5 verdict rows per entry."""
    _make_shape_a_parquet(tmp_path / "ZZHAPPY.yfinance.parquet", n_bars=250)
    from swing.patterns.foundation import CandidateWindow
    window = CandidateWindow(
        ticker="ZZHAPPY",
        timeframe="daily",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 1),
        anchor_date=date(2026, 3, 1),
        anchor_reason="zigzag_pivot:test",
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.generate_candidate_windows",
        lambda *a, **kw: [window],
    )

    def _stub_detector(*a, **kw):
        return SimpleNamespace(geometric_score=0.5, criteria_pass={"c1": True})

    fake_registry = tuple(
        (_stub_detector, name, "v0.0.0")
        for name in ("vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w")
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.get_detector_registry",
        lambda: fake_registry,
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.current_stage",
        lambda conn, t, d: "stage_2",
    )

    cohort = (CohortEntry(ticker="ZZHAPPY", asof_date=date(2026, 4, 15)),)
    result = invoke_cohort(
        cohort,
        conn=empty_db,
        cache_dir=tmp_path,
        window_mode="per-window",
        template_match_mode="off",
    )
    assert result.verdicts_emitted == 5
    assert all(v.skip_reason is None for v in result.verdicts)
    assert {v.pattern_class for v in result.verdicts} == {
        "vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w",
    }
    assert all(v.geometric_score == 0.5 for v in result.verdicts)
    assert all(v.stage_observed == "stage_2" for v in result.verdicts)


def test_invoke_cohort_per_entry_filter_precedence(empty_db, tmp_path, monkeypatch):
    """OQ-5 LOCK: per-entry pattern_class_filter takes precedence over CLI."""
    _make_shape_a_parquet(tmp_path / "ZZFILT.yfinance.parquet", n_bars=250)
    from swing.patterns.foundation import CandidateWindow
    window = CandidateWindow(
        ticker="ZZFILT",
        timeframe="daily",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 1),
        anchor_date=date(2026, 3, 1),
        anchor_reason="zigzag_pivot:test",
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.generate_candidate_windows",
        lambda *a, **kw: [window],
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.current_stage",
        lambda conn, t, d: "stage_2",
    )

    def _stub(*a, **kw):
        return SimpleNamespace(geometric_score=0.4)

    fake_registry = tuple(
        (_stub, name, "v0.0.0")
        for name in ("vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w")
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.get_detector_registry",
        lambda: fake_registry,
    )

    # CLI filter says "flat_base" only, but entry says "vcp" -> vcp wins
    cohort = (
        CohortEntry(
            ticker="ZZFILT",
            asof_date=date(2026, 4, 15),
            pattern_class_filter="vcp",
        ),
    )
    result = invoke_cohort(
        cohort,
        conn=empty_db,
        cache_dir=tmp_path,
        window_mode="per-window",
        template_match_mode="off",
        cli_pattern_class_filter=("flat_base",),
    )
    assert result.verdicts_emitted == 1
    assert result.verdicts[0].pattern_class == "vcp"


def test_invoke_cohort_cli_filter_when_no_per_entry(empty_db, tmp_path, monkeypatch):
    """CLI filter applies when entry has no per-entry override."""
    _make_shape_a_parquet(tmp_path / "ZZCLI.yfinance.parquet", n_bars=250)
    from swing.patterns.foundation import CandidateWindow
    window = CandidateWindow(
        ticker="ZZCLI",
        timeframe="daily",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 1),
        anchor_date=date(2026, 3, 1),
        anchor_reason="zigzag_pivot:test",
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.generate_candidate_windows",
        lambda *a, **kw: [window],
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.current_stage",
        lambda conn, t, d: "stage_2",
    )

    def _stub(*a, **kw):
        return SimpleNamespace(geometric_score=0.4)

    fake_registry = tuple(
        (_stub, name, "v0.0.0")
        for name in ("vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w")
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.get_detector_registry",
        lambda: fake_registry,
    )

    cohort = (CohortEntry(ticker="ZZCLI", asof_date=date(2026, 4, 15)),)
    result = invoke_cohort(
        cohort,
        conn=empty_db,
        cache_dir=tmp_path,
        window_mode="per-window",
        template_match_mode="off",
        cli_pattern_class_filter=("flat_base", "cup_with_handle"),
    )
    assert result.verdicts_emitted == 2
    assert {v.pattern_class for v in result.verdicts} == {"flat_base", "cup_with_handle"}


def test_invoke_cohort_window_mode_last_only(empty_db, tmp_path, monkeypatch):
    """OQ-7: last-only window_mode emits 1 window per entry."""
    _make_shape_a_parquet(tmp_path / "ZZLAST.yfinance.parquet", n_bars=250)
    from swing.patterns.foundation import CandidateWindow
    windows = [
        CandidateWindow(
            ticker="ZZLAST", timeframe="daily",
            start_date=date(2026, 2, 1), end_date=date(2026, 2, 28),
            anchor_date=date(2026, 2, 1),
            anchor_reason=f"zigzag_pivot:test_{i}",
        )
        for i in range(3)
    ]
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.generate_candidate_windows",
        lambda *a, **kw: windows,
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.current_stage",
        lambda conn, t, d: "stage_2",
    )

    def _stub(*a, **kw):
        return SimpleNamespace(geometric_score=0.4)

    fake_registry = ((_stub, "vcp", "v0.0.0"),)
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.get_detector_registry",
        lambda: fake_registry,
    )

    cohort = (CohortEntry(ticker="ZZLAST", asof_date=date(2026, 4, 15)),)
    result = invoke_cohort(
        cohort, conn=empty_db, cache_dir=tmp_path,
        window_mode="last-only", template_match_mode="off",
    )
    # 1 detector x 1 window (last-only) = 1 verdict
    assert result.verdicts_emitted == 1
    assert result.verdicts[0].window_index == 2  # last window (index 2 of [0,1,2])


def test_invoke_cohort_window_mode_per_window(empty_db, tmp_path, monkeypatch):
    """OQ-7: per-window window_mode emits one row per window per detector."""
    _make_shape_a_parquet(tmp_path / "ZZPER.yfinance.parquet", n_bars=250)
    from swing.patterns.foundation import CandidateWindow
    windows = [
        CandidateWindow(
            ticker="ZZPER", timeframe="daily",
            start_date=date(2026, 2, 1), end_date=date(2026, 2, 28),
            anchor_date=date(2026, 2, 1),
            anchor_reason=f"zigzag_pivot:test_{i}",
        )
        for i in range(3)
    ]
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.generate_candidate_windows",
        lambda *a, **kw: windows,
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.current_stage",
        lambda conn, t, d: "stage_2",
    )

    def _stub(*a, **kw):
        return SimpleNamespace(geometric_score=0.4)

    fake_registry = ((_stub, "vcp", "v0.0.0"),)
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.get_detector_registry",
        lambda: fake_registry,
    )

    cohort = (CohortEntry(ticker="ZZPER", asof_date=date(2026, 4, 15)),)
    result = invoke_cohort(
        cohort, conn=empty_db, cache_dir=tmp_path,
        window_mode="per-window", template_match_mode="off",
    )
    assert result.verdicts_emitted == 3  # 3 windows x 1 detector
    assert {v.window_index for v in result.verdicts} == {0, 1, 2}


def test_invoke_cohort_template_match_off_yields_none_template_score(
    empty_db, tmp_path, monkeypatch,
):
    """template_match_mode='off' -> template_match_score is None on verdicts."""
    _make_shape_a_parquet(tmp_path / "ZZTM.yfinance.parquet", n_bars=250)
    from swing.patterns.foundation import CandidateWindow
    window = CandidateWindow(
        ticker="ZZTM", timeframe="daily",
        start_date=date(2026, 3, 1), end_date=date(2026, 4, 1),
        anchor_date=date(2026, 3, 1), anchor_reason="zigzag_pivot:t",
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.generate_candidate_windows",
        lambda *a, **kw: [window],
    )
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.current_stage",
        lambda conn, t, d: "stage_2",
    )

    def _stub(*a, **kw):
        return SimpleNamespace(geometric_score=0.8)

    fake_registry = ((_stub, "vcp", "v0.0.0"),)
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.detector_invoker.get_detector_registry",
        lambda: fake_registry,
    )

    cohort = (CohortEntry(ticker="ZZTM", asof_date=date(2026, 4, 15)),)
    result = invoke_cohort(
        cohort, conn=empty_db, cache_dir=tmp_path,
        window_mode="per-window", template_match_mode="off",
    )
    assert result.verdicts[0].template_match_score is None
    assert result.verdicts[0].template_match_nearest_exemplar_ids_json is None


def test_invoke_cohort_runtime_seconds_recorded(empty_db, tmp_path):
    """CohortRunResult.runtime_seconds is set (>= 0)."""
    result = invoke_cohort(
        (), conn=empty_db, cache_dir=tmp_path,
        window_mode="per-window", template_match_mode="off",
    )
    assert result.runtime_seconds >= 0.0


def test_invoke_cohort_unique_ticker_asof_counts(empty_db, tmp_path):
    """Cohort dedupe counters reflect distinct tickers + asof_dates."""
    cohort = (
        CohortEntry(ticker="A", asof_date=date(2026, 4, 15)),
        CohortEntry(ticker="A", asof_date=date(2026, 4, 16)),
        CohortEntry(ticker="B", asof_date=date(2026, 4, 15)),
    )
    result = invoke_cohort(
        cohort, conn=empty_db, cache_dir=tmp_path,
        window_mode="per-window", template_match_mode="off",
    )
    assert result.cohort_entries_count == 3
    assert result.cohort_unique_tickers_count == 2
    assert result.cohort_unique_asof_dates_count == 2
