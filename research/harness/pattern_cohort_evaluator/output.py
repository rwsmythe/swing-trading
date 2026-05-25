"""Pattern cohort harness output formatters: CSV + markdown + manifest JSON.

ASCII-only output per Windows cp1252 stdout safety lesson (cumulative
CLAUDE.md gotcha). All emitted text -- CSV cells AND markdown body AND
JSON values -- must be cp1252-encodable. Tests verify via text.encode("cp1252").

Empty-state representation per OQ-12 LOCK + cumulative T3.SB3 lesson:
'(none)' literal in markdown drill-down; empty string in CSV cells;
None in JSON-serialized fields.
"""
from __future__ import annotations

import csv
import hashlib
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

from research.harness.pattern_cohort_evaluator.detector_invoker import (
    CohortRunResult,
    CohortVerdict,
)

_CSV_HEADERS = (
    "cohort_entry_id",
    "cohort_label",
    "ticker",
    "asof_date",
    "candidate_id",
    "eval_run_id",
    "persisted_bucket",
    "persisted_pivot",
    "persisted_initial_stop",
    "window_index",
    "window_start_date",
    "window_end_date",
    "anchor_date",
    "anchor_reason",
    "pattern_class",
    "detector_version",
    "stage_observed",
    "geometric_score",
    "template_match_score",
    "composite_score",
    "template_match_nearest_exemplar_ids_json",
    "criteria_pass_json",
    "structural_evidence_json",
    "skip_reason",
)

assert len(_CSV_HEADERS) == 24, "CSV header column count drift; spec §I.2 LOCK"


def write_results_csv(result: CohortRunResult, path: Path) -> None:
    """Write 24-column CSV per spec §I.2.

    Empty fields emit empty string (CSV null convention) per OQ-12 LOCK.
    """
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_CSV_HEADERS)
        for v in result.verdicts:
            writer.writerow(_verdict_to_row(v))


def _verdict_to_row(v: CohortVerdict) -> tuple[str, ...]:
    """Render a CohortVerdict to a 24-tuple of strings. Empty -> ''.

    Per cumulative gotcha "Windows PowerShell stdout defaults to cp1252":
    NO non-ASCII glyphs. Floats formatted with explicit fixed precision
    to keep test fixtures deterministic.
    """

    def _s(x: object) -> str:
        if x is None:
            return ""
        return str(x)

    def _f(x: float | None) -> str:
        if x is None:
            return ""
        return f"{x:.6f}"

    return (
        _s(v.cohort_entry_id),
        _s(v.cohort_label),
        _s(v.ticker),
        v.asof_date.isoformat() if v.asof_date else "",
        _s(v.candidate_id),
        _s(v.eval_run_id),
        _s(v.persisted_bucket),
        _f(v.persisted_pivot),
        _f(v.persisted_initial_stop),
        _s(v.window_index),
        v.window_start_date.isoformat() if v.window_start_date else "",
        v.window_end_date.isoformat() if v.window_end_date else "",
        v.anchor_date.isoformat() if v.anchor_date else "",
        _s(v.anchor_reason),
        _s(v.pattern_class),
        _s(v.detector_version),
        _s(v.stage_observed),
        _f(v.geometric_score),
        _f(v.template_match_score),
        _f(v.composite_score),
        _s(v.template_match_nearest_exemplar_ids_json),
        _s(v.criteria_pass_json),
        _s(v.structural_evidence_json),
        _s(v.skip_reason),
    )


def write_summary_markdown(
    result: CohortRunResult,
    path: Path,
    *,
    cohort_input_mode: str,
    cohort_input_path: Path | None,
    harness_version: str,
) -> None:
    """Write analyst-readable markdown summary per spec §I.4."""
    lines: list[str] = []
    lines.append(_render_header(
        result,
        cohort_input_mode=cohort_input_mode,
        cohort_input_path=cohort_input_path,
        harness_version=harness_version,
    ))
    lines.append(_render_headline(result))
    lines.append(_render_per_class_drilldown(result))
    lines.append(_render_skip_summary(result))
    if result.both_exist_diagnostic.count > 0:
        lines.append(_render_both_exist_banner(result))
    lines.append(_render_notes())
    lines.append(_render_manifest_summary(result))
    body = "\n\n".join(lines) + "\n"
    # Sanity check: body MUST be cp1252-encodable per Windows stdout safety
    body.encode("cp1252")  # raises UnicodeEncodeError on drift
    path.write_text(body, encoding="utf-8")


def write_manifest_json(
    result: CohortRunResult,
    path: Path,
    *,
    cohort_input_mode: str,
    cohort_input_path: Path | None,
    cache_dir: Path,
    db_path: Path,
    harness_version: str,
    started_at_utc: str | None = None,
    finished_at_utc: str | None = None,
) -> None:
    """Write manifest JSON per spec §I.3 schema."""
    from research.harness.pattern_cohort_evaluator import ohlcv_reader as _reader

    if cohort_input_path is not None and cohort_input_path.exists():
        cohort_bytes = cohort_input_path.read_bytes()
        cohort_sha = hashlib.sha256(cohort_bytes).hexdigest()
        cohort_path_str: str | None = str(cohort_input_path.resolve())
    else:
        cohort_sha = None
        cohort_path_str = None

    sig = inspect.signature(_reader.read_yfinance_shape_a)
    sig_str = f"{sig.return_annotation}|{','.join(sig.parameters.keys())}"
    sig_hash = hashlib.sha256(sig_str.encode("utf-8")).hexdigest()

    now_iso = datetime.now(UTC).isoformat()
    manifest = {
        "harness_version": harness_version,
        "cohort_input_mode": cohort_input_mode,
        "cohort_input_path": cohort_path_str,
        "cohort_input_sha256": cohort_sha,
        "cohort_entries_count": result.cohort_entries_count,
        "cohort_unique_tickers_count": result.cohort_unique_tickers_count,
        "cohort_unique_asof_dates_count": result.cohort_unique_asof_dates_count,
        "db_path": str(db_path.resolve()),
        "cache_dir": str(cache_dir.resolve()),
        "ohlcv_reader_module": (
            "research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader"
        ),
        "ohlcv_reader_signature_hash": sig_hash,
        "pattern_exemplars_corpus_size_at_invocation": (
            result.pattern_exemplars_corpus_size_at_invocation
        ),
        "pattern_exemplars_corpus_filter": (
            "final_decision IN ('confirmed','watch')"
        ),
        "pattern_exemplars_filtered_size": result.pattern_exemplars_filtered_size,
        "detectors_invoked": list(result.detectors_invoked),
        "window_mode": result.window_mode,
        "template_match_mode": result.template_match_mode,
        "started_at_utc": started_at_utc or now_iso,
        "finished_at_utc": finished_at_utc or now_iso,
        "runtime_seconds": result.runtime_seconds,
        "entries_processed": result.entries_processed,
        "verdicts_emitted": result.verdicts_emitted,
        "skipped_entries": dict(result.skipped_entries),
        "both_exist_diagnostic": {
            "count": result.both_exist_diagnostic.count,
            "affected_tickers": list(
                result.both_exist_diagnostic.affected_tickers,
            ),
        },
        "l2_lock_preserved": True,
    }
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_header(
    result: CohortRunResult,
    *,
    cohort_input_mode: str,
    cohort_input_path: Path | None,
    harness_version: str,
) -> str:
    """Header section per spec §I.4 step 1."""
    iso = datetime.now(UTC).isoformat()
    path_repr = str(cohort_input_path) if cohort_input_path else "(inline)"
    return (
        f"# Pattern Cohort Detector Evaluator Summary\n\n"
        f"- generated_at_utc: {iso}\n"
        f"- harness_version: {harness_version}\n"
        f"- cohort_input_mode: {cohort_input_mode}\n"
        f"- cohort_input_path: {path_repr}\n"
        f"- cohort_entries_count: {result.cohort_entries_count}\n"
        f"- cohort_unique_tickers_count: {result.cohort_unique_tickers_count}\n"
        f"- cohort_unique_asof_dates_count: "
        f"{result.cohort_unique_asof_dates_count}\n"
        f"- window_mode: {result.window_mode}\n"
        f"- template_match_mode: {result.template_match_mode}\n"
        f"- runtime_seconds: {result.runtime_seconds:.2f}\n"
        f"- l2_lock_preserved: true"
    )


def _render_headline(result: CohortRunResult) -> str:
    """Headline per-pattern-class summary table per spec §I.4 step 2."""
    rows: list[str] = []
    rows.append("## Headline: per-pattern-class summary")
    rows.append("")
    rows.append(
        "| pattern_class | entries_evaluated | composite>=0.5 | "
        "composite>=0.7 | composite>=0.9 | max_composite |"
    )
    rows.append("|---|---|---|---|---|---|")
    by_class = _group_by_class(result.verdicts)
    if not by_class:
        rows.append("| (none) | 0 | 0 | 0 | 0 | (none) |")
        return "\n".join(rows)
    for cls in sorted(by_class.keys()):
        entries = by_class[cls]
        scores = [
            v.composite_score for v in entries
            if v.composite_score is not None
        ]
        cnt = len(entries)
        ge05 = sum(1 for s in scores if s >= 0.5)
        ge07 = sum(1 for s in scores if s >= 0.7)
        ge09 = sum(1 for s in scores if s >= 0.9)
        mx = f"{max(scores):.4f}" if scores else "(none)"
        rows.append(f"| {cls} | {cnt} | {ge05} | {ge07} | {ge09} | {mx} |")
    return "\n".join(rows)


def _render_per_class_drilldown(result: CohortRunResult) -> str:
    """Per-pattern-class drill-down per spec §I.4 step 3."""
    rows: list[str] = []
    rows.append("## Per-pattern-class drill-down")
    by_class = _group_by_class(result.verdicts)
    if not by_class:
        rows.append("")
        rows.append("(none) -- no non-skip verdicts emitted")
        return "\n".join(rows)
    for cls in sorted(by_class.keys()):
        rows.append("")
        rows.append(f"### {cls}")
        rows.append("")
        rows.append(
            "| cohort_entry_id | ticker | asof_date | window_index | "
            "stage_observed | geometric_score | template_match_score | "
            "composite_score |"
        )
        rows.append("|---|---|---|---|---|---|---|---|")
        # cap at first 50 per spec §I.4 step 3 "top-N if cohort large"
        ranked = sorted(
            by_class[cls],
            key=lambda v: -(v.composite_score or 0.0),
        )[:50]
        for v in ranked:
            tm = (
                f"{v.template_match_score:.4f}"
                if v.template_match_score is not None else "(none)"
            )
            rows.append(
                f"| {v.cohort_entry_id} | {v.ticker} | "
                f"{v.asof_date.isoformat()} | {v.window_index} | "
                f"{v.stage_observed or '(none)'} | "
                f"{(v.geometric_score or 0.0):.4f} | {tm} | "
                f"{(v.composite_score or 0.0):.4f} |"
            )
    return "\n".join(rows)


def _render_skip_summary(result: CohortRunResult) -> str:
    """Skip-reason summary table per spec §I.4 step 4."""
    rows: list[str] = []
    rows.append("## Skip-reason summary")
    rows.append("")
    rows.append("| skip_reason | count |")
    rows.append("|---|---|")
    for r in sorted(result.skipped_entries.keys()):
        rows.append(f"| {r} | {result.skipped_entries[r]} |")
    return "\n".join(rows)


def _render_both_exist_banner(result: CohortRunResult) -> str:
    """Both-exist warning banner per spec §I.4 step 5 (conditional)."""
    rows: list[str] = []
    rows.append("## Both-exist diagnostic (Shape A wins per OQ-18 V2 LOCK)")
    rows.append("")
    rows.append(f"- count: {result.both_exist_diagnostic.count}")
    rows.append("- affected_tickers (capped at 50):")
    for t in result.both_exist_diagnostic.affected_tickers[:50]:
        rows.append(f"  - {t}")
    return "\n".join(rows)


def _render_notes() -> str:
    """Notes section per spec §I.4 step 6 + §L.2 limitation templates."""
    return (
        "## Notes\n\n"
        "- pattern_exemplars corpus is read at harness invocation time; "
        "corpus drift between cohort-input-time and invocation-time may "
        "shift template-match Pass 2 verdicts. See method-record "
        "L1 limitation.\n"
        "- OHLCV archive bar-content TEMPORAL mutation per cumulative "
        "gotcha #26 family: intervening pipeline runs may overwrite "
        "historical bars between cohort-input-time and harness-invocation-"
        "time. See method-record L2 limitation.\n"
        "- current_stage lookup uses CURRENT operator DB state; if eval_runs "
        "have been pruned between cohort-input-time and harness-invocation-"
        "time, stage_observed may shift. See method-record L3 limitation."
    )


def _render_manifest_summary(result: CohortRunResult) -> str:
    """Manifest summary footer per spec §I.4 step 7."""
    return (
        "## Manifest summary\n\n"
        f"- entries_processed: {result.entries_processed}\n"
        f"- verdicts_emitted: {result.verdicts_emitted}\n"
        f"- detectors_invoked: "
        f"{', '.join(result.detectors_invoked)}\n"
        f"- pattern_exemplars_corpus_size_at_invocation: "
        f"{result.pattern_exemplars_corpus_size_at_invocation}\n"
        f"- pattern_exemplars_filtered_size: "
        f"{result.pattern_exemplars_filtered_size}\n"
        f"- runtime_seconds: {result.runtime_seconds:.2f}\n"
        f"- both_exist_diagnostic.count: "
        f"{result.both_exist_diagnostic.count}"
    )


def _group_by_class(
    verdicts: tuple[CohortVerdict, ...],
) -> dict[str, list[CohortVerdict]]:
    """Group non-skip verdicts by pattern_class. Skip rows excluded."""
    out: dict[str, list[CohortVerdict]] = {}
    for v in verdicts:
        if v.skip_reason is not None or v.pattern_class is None:
            continue
        out.setdefault(v.pattern_class, []).append(v)
    return out
