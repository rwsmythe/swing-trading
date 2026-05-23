"""V2 sensitivity output formatters: CSV + markdown analysis.

ASCII-only output per Windows cp1252 stdout safety lesson (cumulative
CLAUDE.md gotcha). All emitted text -- both CSV cells AND markdown body --
must be cp1252-encodable. Tests verify via text.encode("cp1252").

Empty-state representation: '(none)' literal string in drill-down /
flipped-candidate sections; per cumulative T3.SB3 lesson "Audit envelope
empty-state representation must be uniform".

L2 LOCK preserved: NO imports of the four forbidden modules
(yfinance, schwabdev, swing.integrations.schwab, ohlcv_archive).
Only stdlib + research.harness.aplus_v2_ohlcv_evaluator.* imports.
"""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from pathlib import Path

from research.harness.aplus_v2_ohlcv_evaluator.sweep import (
    FlippedCandidate,
    SweepResultV2,
)

# ---------------------------------------------------------------------------
# 12-column CSV header (per spec §G.1 + Expansion #11 taxonomy-propagation)
# ---------------------------------------------------------------------------

_CSV_HEADERS_V2 = (
    "variable_name", "kind", "sweep_point",
    "aplus_count", "watch_count", "skip_count", "excluded_count",
    "delta_aplus", "delta_watch",
    "out_of_range_skip_count", "ohlcv_coverage_skip_count",
    "evaluation_error_skip_count",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_sensitivity_csv_v2(result: SweepResultV2, path: Path) -> None:
    """Write 12-column CSV per spec §G.1.

    Per Expansion #11 taxonomy-propagation discipline, `kind` is the second
    column (immediately after variable_name). ASCII-only output per cumulative
    Windows cp1252 stdout safety gotcha.
    """
    path = Path(path)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_CSV_HEADERS_V2)
    for e in result.entries:
        writer.writerow([
            e.variable_name,
            e.kind,
            e.sweep_point,
            e.aplus_count,
            e.watch_count,
            e.skip_count,
            e.excluded_count,
            e.delta_aplus,
            e.delta_watch,
            e.out_of_range_skip_count,
            e.ohlcv_coverage_skip_count,
            e.evaluation_error_skip_count,
        ])
    path.write_text(buf.getvalue(), encoding="utf-8")


def write_sensitivity_markdown_v2(
    result: SweepResultV2,
    path: Path,
    *,
    memory_peak_bytes: int | None = None,
) -> None:
    """Write markdown analysis report per spec §G.

    Sections (in order):
      1. Header (generated time + eval_runs window + total candidates +
         V2 universe size + v2_universe_hash + ohlcv_coverage_skip_count +
         universe_skipped_ticker_count + runtime_seconds + truncated_by_runtime_cap)
      2. Headline (top binding variables by marginal A+ count per loosening
         unit per §G.1)
      3. CRITERION DRIFT (conditional top-level ## section when tier1_match=False
         per §G T-V2.3.5 LOCK; omitted entirely when tier1_match=True)
      4. V1<->V2 Baseline Parity section (always emitted; parity counts summary)
      5. Both-exist warning banner (when both_exist_diagnostic.count > 0
         per §G; per OQ-18 + Codex R4.M1)
      6. Sensitivity matrix (12 cols per spec §G.1)
      7. Per-variable drill-down (per §G.2; bucket_via_surrogate flag
         per OQ-15)
      8. Notes (per-variable scope-reduction + tier-2 surrogate count +
         OQ-15+OQ-18 caveats)
      9. Manifest (both_exist_shape_a_wins_count + accepted ticker counts +
         tier-1/tier-2 split + memory peak from tracemalloc per Codex R3.m3)

    ASCII-only output per cumulative Windows cp1252 stdout safety gotcha.
    Empty-state: '(none)' per cumulative T3.SB3 gotcha.
    """
    path = Path(path)
    lines: list[str] = []

    _write_header_section(lines, result)
    _write_headline_section(lines, result)
    _write_criterion_drift_section(lines, result)  # conditional; top-level ## when firing
    _write_parity_section(lines, result)            # always emitted; parity summary
    _write_both_exist_banner(lines, result)
    _write_matrix_section(lines, result)
    _write_drilldown_section(lines, result)
    _write_notes_section(lines, result)
    _write_manifest_section(lines, result, memory_peak_bytes=memory_peak_bytes)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Section writers
# ---------------------------------------------------------------------------

def _write_header_section(lines: list[str], result: SweepResultV2) -> None:
    """Section 1: run metadata header."""
    now_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("# V2 OHLCV A+ Criterion Sensitivity Analysis")
    lines.append("")
    lines.append(f"Generated: {now_utc}")
    lines.append(f"Eval-runs window: {result.eval_runs_window} "
                 f"(ids {result.eval_run_id_range[0]}..{result.eval_run_id_range[1]})")
    lines.append(f"Total candidates evaluated: {result.total_candidates}")
    lines.append(f"V2 universe size: {result.universe_size}")
    lines.append(f"V2 universe hash: {result.v2_universe_hash}")
    lines.append(f"OHLCV coverage skips (global): {result.ohlcv_coverage_skip_count}")
    lines.append(f"Universe skipped tickers: {result.universe_skipped_ticker_count}")
    lines.append(f"Runtime seconds: {result.runtime_seconds:.2f}")
    truncated_str = "YES" if result.truncated_by_runtime_cap else "no"
    lines.append(f"Truncated by runtime cap: {truncated_str}")
    lines.append("")


def _write_headline_section(lines: list[str], result: SweepResultV2) -> None:
    """Section 2: top binding variables by max delta_aplus."""
    lines.append("## Headline: Top Binding Variables")
    lines.append("")

    # Find entries with delta_aplus > 0; rank by variable_name then max delta_aplus
    binding: dict[str, int] = {}
    for e in result.entries:
        if e.delta_aplus > 0 and (
            e.variable_name not in binding or e.delta_aplus > binding[e.variable_name]
        ):
            binding[e.variable_name] = e.delta_aplus

    if not binding:
        lines.append("No binding variables found (all delta_aplus == 0).")
        lines.append("")
        return

    ranked = sorted(binding.items(), key=lambda kv: kv[1], reverse=True)
    lines.append("| variable_name | max_delta_aplus |")
    lines.append("| --- | --- |")
    for var_name, max_delta in ranked:
        lines.append(f"| {var_name} | {max_delta} |")
    lines.append("")


def _write_criterion_drift_section(lines: list[str], result: SweepResultV2) -> None:
    """Section 3 (conditional): CRITERION DRIFT top-level warning section.

    Emitted ONLY when baseline_parity.tier1_match=False.
    Per spec §G T-V2.3.5 + plan §G T-V2.5 integration test LOCK:
    '## CRITERION DRIFT DETECTED' is a TOP-LEVEL section (level-2 ##),
    NOT a subsection of '## V1<->V2 Baseline Parity'.
    Omitted entirely when tier1_match=True.
    """
    parity = result.baseline_parity
    if parity.tier1_match:
        return  # suppressed when no mismatch

    lines.append("## CRITERION DRIFT DETECTED")
    lines.append("")
    lines.append("**BLOCKING:** V2 baseline (current-value sweep point) does NOT")
    lines.append("match V1 persisted results for the following tier-1 candidates:")
    lines.append("")
    for cand_key in parity.tier1_mismatch_candidates:
        lines.append(f"- {cand_key}")
    lines.append("")
    lines.append("Action required: investigate V1/V2 divergence before trusting")
    lines.append("V2 sensitivity results.")
    lines.append("")


def _write_parity_section(lines: list[str], result: SweepResultV2) -> None:
    """Section 4: V1<->V2 Baseline Parity summary (always emitted).

    Reports tier-1 match status + tier-2 counts.
    CRITERION DRIFT alert is in its own top-level section above this one
    (see _write_criterion_drift_section).
    """
    parity = result.baseline_parity
    lines.append("## V1<->V2 Baseline Parity")
    lines.append("")
    if parity.tier1_match:
        lines.append("Tier-1 match: PASS (V1 and V2 agree on all tier-1 candidates)")
    else:
        lines.append(
            "Tier-1 match: FAIL (see CRITERION DRIFT DETECTED section above)"
        )
    lines.append("")
    lines.append(f"Tier-2 match count: {parity.tier2_match_count}")
    lines.append(f"Tier-2 mismatch count: {parity.tier2_mismatch_count}")
    lines.append(f"Tier-2 via surrogate count: {parity.tier2_via_surrogate_count}")
    lines.append("")


def _write_both_exist_banner(lines: list[str], result: SweepResultV2) -> None:
    """Section 4: both-exist warning banner (when count > 0 per OQ-18)."""
    diag = result.both_exist_diagnostic
    if diag.count == 0:
        return  # suppress banner entirely per Test 10

    lines.append("## WARNING: Both-Exist Archive Files Detected")
    lines.append("")
    lines.append(f"WARNING: {diag.count} tickers have both Shape A and legacy archive")
    lines.append("files present in the cache directory. Shape A wins unconditionally")
    lines.append("per OQ-18 LOCK. Verify no stale legacy files contaminate results.")
    lines.append("")
    if diag.affected_tickers:
        lines.append("Affected tickers (capped at 50):")
        lines.append("")
        for ticker in diag.affected_tickers[:50]:
            lines.append(f"- {ticker}")
    lines.append("")


def _write_matrix_section(lines: list[str], result: SweepResultV2) -> None:
    """Section 5: sensitivity matrix (12 cols per spec §G.1)."""
    lines.append("## Sensitivity Matrix")
    lines.append("")

    # Header row (13 pipe chars = 12 columns)
    lines.append(
        "| variable_name | kind | sweep_point"
        " | aplus_count | watch_count | skip_count | excluded_count"
        " | delta_aplus | delta_watch"
        " | out_of_range_skip_count | ohlcv_coverage_skip_count"
        " | evaluation_error_skip_count |"
    )
    lines.append(
        "| --- | --- | ---"
        " | --- | --- | --- | ---"
        " | --- | ---"
        " | --- | ---"
        " | --- |"
    )
    for e in result.entries:
        lines.append(
            f"| {e.variable_name} | {e.kind} | {e.sweep_point}"
            f" | {e.aplus_count} | {e.watch_count} | {e.skip_count}"
            f" | {e.excluded_count} | {e.delta_aplus} | {e.delta_watch}"
            f" | {e.out_of_range_skip_count} | {e.ohlcv_coverage_skip_count}"
            f" | {e.evaluation_error_skip_count} |"
        )
    lines.append("")


def _write_drilldown_section(lines: list[str], result: SweepResultV2) -> None:
    """Section 6: per-variable drill-down (FlippedCandidate provenance).

    Empty-state: literal '(none)' per cumulative T3.SB3 gotcha.
    bucket_via_surrogate rendered per OQ-15.
    V1 simplification: old_criterion_failure is always '(none)' per
    T-V2.2 fix-commit 86e51cd (old_criterion_failure V1 stub comment).
    """
    lines.append("## Per-Variable Drill-Down")
    lines.append("")
    lines.append("Note: old_criterion_failure is '(none)' for all entries in V1.")
    lines.append("V2 candidate: compute from persisted candidate_criteria rows.")
    lines.append("")

    # Group flipped candidates by variable_name (from sweep_point context)
    # Since FlippedCandidate doesn't store variable_name, group by eval_run_id
    # and present all flipped candidates together per variable found in entries.
    # Per the plan: drill-down groups by variable_name from entries.

    # Build a per-variable_name set of candidate keys from entries
    variable_names = []
    seen_vars: set[str] = set()
    for e in result.entries:
        if e.variable_name not in seen_vars:
            variable_names.append(e.variable_name)
            seen_vars.add(e.variable_name)

    # Map sweep_point -> variable_name for flipped lookup
    # (FlippedCandidate carries sweep_point but not variable_name;
    # use sweep_points that appear in each variable's entries to associate)
    var_to_sweep_points: dict[str, set[float | int]] = {}
    for e in result.entries:
        var_to_sweep_points.setdefault(e.variable_name, set()).add(e.sweep_point)

    # Build per-variable flip lookup from flipped list
    # When multiple variables share the same sweep_point, a flipped candidate
    # at that point is ambiguous -- conservatively list under ALL variables
    # that contain that sweep_point.
    var_to_flipped: dict[str, list[FlippedCandidate]] = {v: [] for v in variable_names}
    for fc in result.flipped:
        for var_name, sp_set in var_to_sweep_points.items():
            if fc.sweep_point in sp_set:
                var_to_flipped[var_name].append(fc)

    for var_name in variable_names:
        lines.append(f"### {var_name}")
        lines.append("")
        flipped_for_var = var_to_flipped.get(var_name, [])
        if not flipped_for_var:
            lines.append("(none)")
            lines.append("")
            continue

        lines.append(
            "| ticker | eval_run_id | data_asof_date | sweep_point"
            " | old_bucket | new_bucket | old_criterion_failure"
            " | bucket_via_surrogate |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for fc in flipped_for_var:
            surrogate_note = "(via current_equity surrogate)" if fc.bucket_via_surrogate else "no"
            lines.append(
                f"| {fc.ticker} | {fc.eval_run_id} | {fc.data_asof_date}"
                f" | {fc.sweep_point} | {fc.old_bucket} | {fc.new_bucket}"
                f" | {fc.old_criterion_failure} | {surrogate_note} |"
            )
        lines.append("")


def _write_notes_section(lines: list[str], result: SweepResultV2) -> None:
    """Section 7: per-variable scope-reduction notes + caveats."""
    lines.append("## Notes")
    lines.append("")

    # Per-variable scope-reduction summary
    lines.append("### Per-Variable Skip Counts")
    lines.append("")
    lines.append(
        "| variable_name | ohlcv_coverage_skip_count"
        " | out_of_range_skip_count | evaluation_error_skip_count |"
    )
    lines.append("| --- | --- | --- | --- |")

    seen: set[str] = set()
    for e in result.entries:
        if e.variable_name in seen:
            continue
        seen.add(e.variable_name)
        lines.append(
            f"| {e.variable_name} | {e.ohlcv_coverage_skip_count}"
            f" | {e.out_of_range_skip_count} | {e.evaluation_error_skip_count} |"
        )
    lines.append("")

    # OQ-15 surrogate caveat
    lines.append("### OQ-15 Tier-2 Surrogate Caveat")
    lines.append("")
    lines.append(
        "Tier-2 candidates use current_equity from the most-recent snapshot"
        " available on or before the eval_run asof_date. When no snapshot"
        " exists, the capital_floor surrogate is used; bucket_via_surrogate=True"
        " in the drill-down above."
    )
    lines.append("")

    # OQ-18 both-exist caveat
    lines.append("### OQ-18 Both-Exist Policy Caveat")
    lines.append("")
    lines.append(
        "When both a yfinance Shape A parquet and a legacy parquet exist for a"
        " ticker, Shape A wins unconditionally per OQ-18 LOCK. Results may"
        " differ from a pure-legacy run. See WARNING banner above if any"
        " tickers were affected."
    )
    lines.append("")

    # V1 simplification note for old_criterion_failure
    lines.append("### V1 Simplification: old_criterion_failure")
    lines.append("")
    lines.append(
        "old_criterion_failure is '(none)' for all entries in this V1 release."
        " V2 candidate: compute per-criterion attribution from persisted"
        " candidate_criteria rows (deferred; see return report section 6)."
    )
    lines.append("")


def _write_manifest_section(
    lines: list[str],
    result: SweepResultV2,
    *,
    memory_peak_bytes: int | None = None,
) -> None:
    """Section 8: manifest (config summary + counters + memory peak)."""
    lines.append("## Manifest")
    lines.append("")

    lines.append(f"both_exist_shape_a_wins_count: {result.both_exist_diagnostic.count}")
    lines.append(f"accepted_ticker_count: {result.universe_size}")
    lines.append(f"total_candidates: {result.total_candidates}")
    lines.append(f"eval_runs_window: {result.eval_runs_window}")
    lines.append(f"v2_universe_hash: {result.v2_universe_hash}")

    # Tier-1 / tier-2 split from baseline parity report
    # Per spec §H T-V2.3.9: tier_1_count + tier_2_count are TOTAL candidate
    # counts at baseline (current_value sweep point), NOT mismatch counts.
    parity = result.baseline_parity
    lines.append(f"tier_1_count: {parity.tier_1_count}")
    lines.append(f"tier_2_count: {parity.tier_2_count}")
    lines.append(f"tier_2_via_surrogate_count: {parity.tier2_via_surrogate_count}")

    # Memory peak from tracemalloc (passed in from run.py; None if not measured)
    if memory_peak_bytes is not None:
        peak_mib = memory_peak_bytes / (1024 * 1024)
        lines.append(f"memory_peak_bytes: {memory_peak_bytes}")
        lines.append(f"memory_peak_mib: {peak_mib:.2f}")
    else:
        lines.append("memory_peak_bytes: (not measured)")

    lines.append(f"runtime_seconds: {result.runtime_seconds:.2f}")
    truncated_str = "YES" if result.truncated_by_runtime_cap else "no"
    lines.append(f"truncated_by_runtime_cap: {truncated_str}")
    lines.append("")
