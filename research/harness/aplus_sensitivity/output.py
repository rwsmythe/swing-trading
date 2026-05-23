"""Sensitivity-sweep output formatters: CSV + markdown analysis.

ASCII-only output per Windows cp1252 stdout safety lesson (cumulative
CLAUDE.md gotcha). All emitted text -- both CSV cells AND markdown body --
must be cp1252-encodable. Tests verify this via ``text.encode("cp1252")``.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from research.harness.aplus_sensitivity.sweep import SweepResult


_CSV_HEADERS = (
    "variable_name", "kind", "sweep_point",
    "aplus_count", "watch_count", "skip_count", "excluded_count",
    "delta_aplus", "delta_watch",
)


def write_sensitivity_csv(result: SweepResult, path: Path) -> None:
    """Write the sweep result to ``path`` as a 9-column CSV.

    Per Expansion #11 taxonomy-propagation discipline, ``kind`` is the
    second column (immediately after ``variable_name``); this matches the
    markdown matrix's Kind column position.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_CSV_HEADERS)
        for e in result.entries:
            writer.writerow([
                e.variable_name, e.kind, e.sweep_point,
                e.aplus_count, e.watch_count, e.skip_count, e.excluded_count,
                e.delta_aplus, e.delta_watch,
            ])


def write_sensitivity_markdown(result: SweepResult, path: Path) -> None:
    """Write the sweep result to ``path`` as a markdown analysis report.

    Renders a sensitivity-matrix table (one row per (variable, sweep_point))
    + a Notes section. The Notes section MUST contain the V1 LIMITATION
    paragraph naming both threshold_additive AND threshold_multiplicative
    kinds + asserting ``delta_aplus`` / ``delta_watch`` are intentionally
    ZERO for threshold rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        "# A+ Criteria Sensitivity Sweep",
        "",
        f"**Generated:** {iso}",
        (
            f"**Eval-runs window:** last N={result.eval_runs_window} runs "
            f"(range {result.eval_run_id_range[0]}..{result.eval_run_id_range[1]})"
        ),
        f"**Total candidates:** {result.total_candidates}",
        "",
        "## Sensitivity matrix",
        "",
        "| Variable | Kind | Sweep point | A+ | Watch | Skip | Excluded | dA+ | dWatch |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for e in result.entries:
        lines.append(
            f"| {e.variable_name} | {e.kind} | {e.sweep_point} | "
            f"{e.aplus_count} | {e.watch_count} | {e.skip_count} | "
            f"{e.excluded_count} | {e.delta_aplus:+d} | {e.delta_watch:+d} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Sweep is 1D (one variable at a time); cross-coupling NOT modeled.",
        (
            "- Counts at current_value match the persisted bucket distribution"
            " (parity invariant); delta_aplus / delta_watch are relative to that"
            " anchor."
        ),
        (
            "- **V1 LIMITATION: Threshold variables (kind = threshold_additive |"
            " threshold_multiplicative -- 15 of 17 rows) report the persisted"
            " bucket distribution at each sweep point; their `delta_aplus` and"
            " `delta_watch` columns are intentionally ZERO. True per-criterion"
            " bucket resimulation against the substituted threshold requires the"
            " V2 OHLCV criterion-evaluator harness (banked at"
            " `research/method-records/aplus-criteria-calibration.md` V2"
            " dependencies). Gate variables (kind = gate -- 2 of 17 rows:"
            " `trend_template.min_passes`, `vcp.watch_max_fails`) DO produce real"
            " bucket-redistribution counts via faithful `bucket_for`"
            " resimulation.**"
        ),
        (
            "- Margin-of-failure semantics for non-numeric criteria fold to"
            " boolean-fail counts; see study writeup at"
            " `research/studies/aplus-criterion-sensitivity-2026-05-22.md`."
        ),
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
