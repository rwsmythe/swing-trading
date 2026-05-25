"""Per-(cohort_entry, pattern_class, window) detector orchestration.

Re-imports production detector registry via
`swing.pipeline.runner._pattern_detect_registry()` per OQ-1 LOCK + cumulative
gotcha #19 (cascade-call-graph verification): the function is module-level
+ side-effect-free + returns a 5-tuple; safe to import; zero-drift discipline.

Per-entry try/except per cumulative T2.SB5 lesson: 5 enumerated skip reasons
surfaced via per-skip-reason counters + per-entry skip rows (NEVER silent;
this harness IS gotcha #27's architectural answer + models its discipline).
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
)
from research.harness.pattern_cohort_evaluator.cohort_reader import CohortEntry
from research.harness.pattern_cohort_evaluator.exceptions import (
    OhlcvCoverageError,
)
from research.harness.pattern_cohort_evaluator.ohlcv_reader import (
    read_yfinance_shape_a_sliced,
)
from swing.data.repos.pattern_exemplars import list_exemplars
from swing.patterns.composite import compute_composite_score
from swing.patterns.foundation import (
    CandidateWindow,
    current_stage,
    generate_candidate_windows,
)
from swing.patterns.template_matching import (
    GEOMETRIC_SCORE_PREGATE_THRESHOLD,
    TemplateMatchExemplar,
    match_forward,
)

log = logging.getLogger(__name__)

_WindowMode = Literal["last-only", "per-window"]
_TemplateMatchMode = Literal["on", "off"]

# Per spec §I.2 + cumulative gotcha #15 (Expansion #11 taxonomy propagation):
# skip_reason enum values are enumerated explicitly + propagated to
# CohortVerdict.skip_reason + output.py rendering + test fixtures.
_SKIP_REASONS: frozenset[str] = frozenset(
    {
        "coverage_skip",
        "archive_missing_skip",
        "window_generation_error",
        "no_windows",
        "detector_error_all",
    }
)


@dataclass(frozen=True)
class CohortVerdict:
    """One row in the harness output CSV per spec §I.2 (24 columns).

    For non-skip entries: per-(cohort_entry, pattern_class, window) verdict
    populated with detector evidence + template-match + composite_score.

    For skip entries: skip_reason populated; pattern_class + detector verdict
    columns NULL.
    """
    # Cohort-entry identifiers
    cohort_entry_id: int
    cohort_label: str | None
    ticker: str
    asof_date: date

    # Cohort-entry persisted metadata (from V1)
    candidate_id: int | None
    eval_run_id: int | None
    persisted_bucket: str | None
    persisted_pivot: float | None
    persisted_initial_stop: float | None

    # Window identification (None for skip rows)
    window_index: int | None
    window_start_date: date | None
    window_end_date: date | None
    anchor_date: date | None
    anchor_reason: str | None

    # Detector verdict (None for skip rows)
    pattern_class: str | None
    detector_version: str | None
    stage_observed: str | None

    geometric_score: float | None
    template_match_score: float | None
    composite_score: float | None

    # Audit envelope
    template_match_nearest_exemplar_ids_json: str | None
    criteria_pass_json: str | None
    structural_evidence_json: str | None

    # Skip-bearing audit (None for non-skip rows)
    skip_reason: str | None

    def __post_init__(self) -> None:
        if self.skip_reason is not None and self.skip_reason not in _SKIP_REASONS:
            raise ValueError(
                f"CohortVerdict.skip_reason must be one of "
                f"{sorted(_SKIP_REASONS)}, got {self.skip_reason!r}"
            )


@dataclass(frozen=True)
class CohortRunResult:
    """Top-level harness result emitted to output.py.

    Per cumulative gotcha #22 (Expansion #8 promotion: per-counter accumulation
    audit): each counter unit is per-cohort-entry (NOT per-(entry, pattern_class,
    window)) -- the harness skips at the entry level for OHLCV / window failures.
    """
    cohort_entries_count: int
    cohort_unique_tickers_count: int
    cohort_unique_asof_dates_count: int
    verdicts: tuple[CohortVerdict, ...]
    entries_processed: int
    verdicts_emitted: int  # non-skip rows
    skipped_entries: dict[str, int]  # per-skip-reason counter; keys subset of _SKIP_REASONS
    both_exist_diagnostic: BothExistDiagnostic
    pattern_exemplars_corpus_size_at_invocation: int
    pattern_exemplars_filtered_size: int
    detectors_invoked: tuple[str, ...]
    window_mode: _WindowMode
    template_match_mode: _TemplateMatchMode
    runtime_seconds: float


def get_detector_registry() -> tuple[tuple[object, str, str], ...]:
    """Return the production detector registry per OQ-1 LOCK.

    Re-imports `swing.pipeline.runner._pattern_detect_registry` which is a
    module-level, side-effect-free function returning a 5-tuple of
    (detector_callable, pattern_class, version_str). Verified via
    cascade-call-graph audit per cumulative gotcha #19.
    """
    from swing.pipeline.runner import _pattern_detect_registry
    return _pattern_detect_registry()


def load_exemplar_corpus(
    conn: sqlite3.Connection,
    cache_dir: Path,
    *,
    diagnostic: BothExistDiagnostic,
) -> tuple[dict[str, list[TemplateMatchExemplar]], int, int]:
    """Load pattern_exemplars corpus + slice close-price series per exemplar.

    Mirrors production Pass 2 corpus load except corpus reads from
    ohlcv_reader.read_yfinance_shape_a_sliced instead of OhlcvCache.

    Per cumulative T2.SB5 gotcha "Bad-exemplar isolation in retrieval
    functions": per-exemplar try/except inside the load loop.
    """
    exemplar_rows = list_exemplars(conn)
    corpus_size = len(exemplar_rows)
    bundles_by_class: dict[str, list[TemplateMatchExemplar]] = {}
    valid_decisions = ("confirmed", "watch")
    filtered_count = 0
    for ex_row in exemplar_rows:
        if ex_row.final_decision not in valid_decisions:
            continue
        filtered_count += 1
        try:
            ex_bars = read_yfinance_shape_a_sliced(
                ex_row.ticker,
                cache_dir,
                asof_date=ex_row.end_date,
                min_bars=1,
                diagnostic=diagnostic,
            )
            ts_start = pd.Timestamp(ex_row.start_date)
            ts_end = pd.Timestamp(ex_row.end_date)
            mask = (ex_bars.index >= ts_start) & (ex_bars.index <= ts_end)
            close_series = ex_bars.loc[mask, "Close"]
            if hasattr(close_series, "ndim") and close_series.ndim == 2:
                close_series = close_series.iloc[:, 0]
            close_arr = np.asarray(close_series.values, dtype=float)
            if close_arr.size == 0:
                continue
            bundle = TemplateMatchExemplar(
                exemplar=ex_row, close_prices=close_arr,
            )
        except Exception as exc:
            log.info(
                "pattern_cohort: exemplar bars fetch failed for "
                "exemplar_id=%s ticker=%s (continuing): %s",
                ex_row.id,
                ex_row.ticker,
                exc,
            )
            continue
        bundles_by_class.setdefault(
            ex_row.proposed_pattern_class, [],
        ).append(bundle)
    return bundles_by_class, corpus_size, filtered_count


def invoke_cohort(
    cohort: tuple[CohortEntry, ...],
    *,
    conn: sqlite3.Connection,
    cache_dir: Path,
    window_mode: _WindowMode,
    template_match_mode: _TemplateMatchMode,
    cli_pattern_class_filter: tuple[str, ...] | None = None,
) -> CohortRunResult:
    """Invoke 5 detectors per cohort entry + emit per-row verdicts.

    Per-entry try/except per cumulative T2.SB5 gotcha:
      OhlcvCoverageError on read -> coverage_skip
      FileNotFoundError on read -> archive_missing_skip
      generate_candidate_windows Exception -> window_generation_error
      empty windows -> no_windows
      ALL detectors raise -> detector_error_all
    """
    started = time.time()
    both_exist = BothExistDiagnostic()

    if template_match_mode == "on":
        exemplar_bundles_by_class, corpus_size, filtered_size = (
            load_exemplar_corpus(conn, cache_dir, diagnostic=both_exist)
        )
    else:
        exemplar_bundles_by_class = {}
        corpus_size = 0
        filtered_size = 0

    detectors = get_detector_registry()
    detector_names = tuple(p for _, p, _ in detectors)

    skipped: dict[str, int] = {r: 0 for r in _SKIP_REASONS}
    verdicts: list[CohortVerdict] = []
    entries_processed = 0
    verdicts_emitted = 0

    for entry_idx, entry in enumerate(cohort):
        entries_processed += 1

        # Step 1: read OHLCV + slice to <= asof_date
        try:
            sliced = read_yfinance_shape_a_sliced(
                entry.ticker,
                cache_dir,
                asof_date=entry.asof_date,
                min_bars=200,
                diagnostic=both_exist,
            )
        except OhlcvCoverageError:
            skipped["coverage_skip"] += 1
            verdicts.append(_skip_verdict(entry_idx, entry, "coverage_skip"))
            continue
        except (FileNotFoundError, OSError) as exc:
            log.warning(
                "pattern_cohort: archive missing for %s at %s: %s",
                entry.ticker,
                entry.asof_date,
                exc,
            )
            skipped["archive_missing_skip"] += 1
            verdicts.append(
                _skip_verdict(entry_idx, entry, "archive_missing_skip"),
            )
            continue

        # Step 2: generate candidate windows
        try:
            windows = generate_candidate_windows(
                sliced,
                "zigzag_pivot",
                ticker=entry.ticker,
                timeframe="daily",
            )
        except Exception as exc:
            log.warning(
                "pattern_cohort: generate_candidate_windows failed for %s: %s",
                entry.ticker,
                exc,
            )
            skipped["window_generation_error"] += 1
            verdicts.append(
                _skip_verdict(entry_idx, entry, "window_generation_error"),
            )
            continue

        if not windows:
            skipped["no_windows"] += 1
            verdicts.append(_skip_verdict(entry_idx, entry, "no_windows"))
            continue

        # Step 3: select windows per window_mode
        if window_mode == "last-only":
            target_windows: tuple[tuple[int, CandidateWindow], ...] = (
                (len(windows) - 1, windows[-1]),
            )
        else:
            target_windows = tuple(enumerate(windows))

        # Step 4: stage_observed lookup once per entry
        stage_obs = current_stage(conn, entry.ticker, entry.asof_date)

        # Step 5: per-(window, detector) invocation
        entry_verdict_emitted = False
        entry_detector_attempts = 0
        entry_detector_failures = 0
        per_entry_rows: list[CohortVerdict] = []
        for w_idx, window in target_windows:
            for detector_fn, pattern_class, version_str in detectors:
                # Per-entry pattern_class_filter takes precedence over CLI
                # global filter (OQ-5 LOCK)
                if (
                    entry.pattern_class_filter is not None
                    and entry.pattern_class_filter != pattern_class
                ):
                    continue
                if (
                    entry.pattern_class_filter is None
                    and cli_pattern_class_filter is not None
                    and pattern_class not in cli_pattern_class_filter
                ):
                    continue
                entry_detector_attempts += 1
                try:
                    evidence = detector_fn(
                        sliced,
                        window,
                        conn=conn,
                        ticker=entry.ticker,
                        asof_date=entry.asof_date,
                    )
                except Exception as exc:
                    entry_detector_failures += 1
                    log.warning(
                        "pattern_cohort: %s detector failed for %s window=%d: %s",
                        pattern_class,
                        entry.ticker,
                        w_idx,
                        exc,
                    )
                    continue

                geometric_score = float(
                    getattr(evidence, "geometric_score", 0.0),
                )

                # Template-match Pass 2 per OQ-6 LOCK
                template_match_score: float | None = None
                nearest_exemplar_ids: list[int] = []
                if template_match_mode == "on":
                    bundles = exemplar_bundles_by_class.get(pattern_class, [])
                    candidate_close = _slice_window_close(sliced, window)
                    if (
                        bundles
                        and candidate_close.size > 0
                        and geometric_score >= GEOMETRIC_SCORE_PREGATE_THRESHOLD
                    ):
                        try:
                            hits = match_forward(
                                candidate_close_prices=candidate_close,
                                candidate_pattern_class=pattern_class,
                                candidate_ticker=entry.ticker,
                                exemplar_corpus=bundles,
                                top_k=3,
                                geometric_score=geometric_score,
                            )
                        except Exception as exc:
                            log.warning(
                                "pattern_cohort: match_forward failed for "
                                "(%s, %s): %s",
                                entry.ticker,
                                pattern_class,
                                exc,
                            )
                            hits = []
                        if hits:
                            template_match_score = max(
                                h.similarity_score for h in hits
                            )
                            nearest_exemplar_ids = [
                                h.exemplar_id for h in hits
                            ]

                composite_score = compute_composite_score(
                    geometric=geometric_score,
                    template_match=template_match_score,
                )

                per_entry_rows.append(
                    _build_verdict(
                        entry_idx=entry_idx,
                        entry=entry,
                        window_idx=w_idx,
                        window=window,
                        pattern_class=pattern_class,
                        version_str=version_str,
                        stage_obs=stage_obs,
                        evidence=evidence,
                        geometric_score=geometric_score,
                        template_match_score=template_match_score,
                        composite_score=composite_score,
                        nearest_exemplar_ids=nearest_exemplar_ids,
                    ),
                )
                entry_verdict_emitted = True

        # Step 6: per-entry detector_error_all skip check
        if (
            entry_detector_attempts > 0
            and entry_detector_failures == entry_detector_attempts
            and not entry_verdict_emitted
        ):
            skipped["detector_error_all"] += 1
            verdicts.append(_skip_verdict(entry_idx, entry, "detector_error_all"))
            continue

        verdicts.extend(per_entry_rows)
        verdicts_emitted += len(per_entry_rows)

    runtime = time.time() - started
    return CohortRunResult(
        cohort_entries_count=len(cohort),
        cohort_unique_tickers_count=len({e.ticker for e in cohort}),
        cohort_unique_asof_dates_count=len({e.asof_date for e in cohort}),
        verdicts=tuple(verdicts),
        entries_processed=entries_processed,
        verdicts_emitted=verdicts_emitted,
        skipped_entries=skipped,
        both_exist_diagnostic=both_exist,
        pattern_exemplars_corpus_size_at_invocation=corpus_size,
        pattern_exemplars_filtered_size=filtered_size,
        detectors_invoked=detector_names,
        window_mode=window_mode,
        template_match_mode=template_match_mode,
        runtime_seconds=runtime,
    )


def _slice_window_close(
    bars: pd.DataFrame, window: CandidateWindow,
) -> np.ndarray:
    """Slice candidate's close-price series; mirrors production runner.py."""
    ts_start = pd.Timestamp(window.start_date)
    ts_end = pd.Timestamp(window.end_date)
    mask = (bars.index >= ts_start) & (bars.index <= ts_end)
    close_series = bars.loc[mask, "Close"]
    if hasattr(close_series, "ndim") and close_series.ndim == 2:
        close_series = close_series.iloc[:, 0]
    return np.asarray(close_series.values, dtype=float)


def _build_verdict(
    *,
    entry_idx: int,
    entry: CohortEntry,
    window_idx: int,
    window: CandidateWindow,
    pattern_class: str,
    version_str: str,
    stage_obs: str,
    evidence: object,
    geometric_score: float,
    template_match_score: float | None,
    composite_score: float,
    nearest_exemplar_ids: list[int],
) -> CohortVerdict:
    """Build a non-skip CohortVerdict row.

    Per cumulative T3.SB3 lesson "Audit envelope empty-state representation
    must be uniform across emit + persist paths": empty
    nearest_exemplar_ids -> None (NOT "[]" and NOT "").
    """
    import dataclasses
    import json

    if dataclasses.is_dataclass(evidence):
        ev_dict = dataclasses.asdict(evidence)
    else:
        ev_dict = {"raw_repr": repr(evidence)}

    criteria_pass = ev_dict.get("criteria_pass")
    if criteria_pass is not None:
        criteria_pass_json: str | None = json.dumps(criteria_pass, sort_keys=True, default=str)
    else:
        criteria_pass_json = None

    structural_json: str | None = json.dumps(ev_dict, sort_keys=True, default=str)

    # uniform empty-state per OQ-12 LOCK: empty list -> None (NOT "[]" NOT "")
    nearest_json: str | None = (
        json.dumps(nearest_exemplar_ids) if nearest_exemplar_ids else None
    )

    return CohortVerdict(
        cohort_entry_id=entry_idx,
        cohort_label=entry.cohort_label,
        ticker=entry.ticker,
        asof_date=entry.asof_date,
        candidate_id=entry.candidate_id,
        eval_run_id=entry.eval_run_id,
        persisted_bucket=entry.bucket,
        persisted_pivot=entry.pivot,
        persisted_initial_stop=entry.initial_stop,
        window_index=window_idx,
        window_start_date=window.start_date,
        window_end_date=window.end_date,
        anchor_date=window.anchor_date,
        anchor_reason=window.anchor_reason,
        pattern_class=pattern_class,
        detector_version=version_str,
        stage_observed=stage_obs,
        geometric_score=geometric_score,
        template_match_score=template_match_score,
        composite_score=composite_score,
        template_match_nearest_exemplar_ids_json=nearest_json,
        criteria_pass_json=criteria_pass_json,
        structural_evidence_json=structural_json,
        skip_reason=None,
    )


def _skip_verdict(
    entry_idx: int, entry: CohortEntry, skip_reason: str,
) -> CohortVerdict:
    """Build a skip-bearing CohortVerdict row per spec §I.2."""
    return CohortVerdict(
        cohort_entry_id=entry_idx,
        cohort_label=entry.cohort_label,
        ticker=entry.ticker,
        asof_date=entry.asof_date,
        candidate_id=entry.candidate_id,
        eval_run_id=entry.eval_run_id,
        persisted_bucket=entry.bucket,
        persisted_pivot=entry.pivot,
        persisted_initial_stop=entry.initial_stop,
        window_index=None,
        window_start_date=None,
        window_end_date=None,
        anchor_date=None,
        anchor_reason=None,
        pattern_class=None,
        detector_version=None,
        stage_observed=None,
        geometric_score=None,
        template_match_score=None,
        composite_score=None,
        template_match_nearest_exemplar_ids_json=None,
        criteria_pass_json=None,
        structural_evidence_json=None,
        skip_reason=skip_reason,
    )
