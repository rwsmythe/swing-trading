"""T-T4.SB.1 §B.1 Sub-task 1C — output formatter tests."""
from __future__ import annotations

from pathlib import Path

from research.harness.aplus_sensitivity.output import (
    write_sensitivity_csv,
    write_sensitivity_markdown,
)
from research.harness.aplus_sensitivity.sweep import SweepEntry, SweepResult


def _build_synthetic_result() -> SweepResult:
    return SweepResult(
        eval_runs_window=20,
        eval_run_id_range=(101, 120),
        total_candidates=5000,
        entries=(
            SweepEntry("trend_template.min_passes", "gate", 5, 12, 80, 4908, 0, 11, 70),
            SweepEntry("trend_template.min_passes", "gate", 6, 4, 70, 4926, 0, 3, 60),
            SweepEntry("trend_template.min_passes", "gate", 7, 1, 10, 4989, 0, 0, 0),
            # Threshold variable -- delta columns serialize as 0 per V1.
            SweepEntry(
                "vcp.adr_min_pct", "threshold_multiplicative",
                2.5, 1, 10, 4989, 0, 0, 0,
            ),
        ),
    )


def test_output_formatter_emits_csv_and_markdown(tmp_path: Path) -> None:
    result = _build_synthetic_result()
    csv_path = tmp_path / "sweep.csv"
    md_path = tmp_path / "sweep.md"
    write_sensitivity_csv(result, csv_path)
    write_sensitivity_markdown(result, md_path)

    csv_text = csv_path.read_text(encoding="utf-8")
    # CSV must include all 9 columns (kind appended after variable_name) +
    # all data rows (3 gate + 1 threshold).
    assert "variable_name,kind,sweep_point,aplus_count,watch_count" in csv_text
    assert "trend_template.min_passes,gate,5,12,80,4908" in csv_text
    assert "trend_template.min_passes,gate,7,1,10,4989" in csv_text
    assert "vcp.adr_min_pct,threshold_multiplicative,2.5,1,10,4989" in csv_text

    md_text = md_path.read_text(encoding="utf-8")
    # ASCII-only (Windows cp1252 stdout safety).
    md_text.encode("cp1252")
    # Markdown must surface the sensitivity matrix table with Kind column.
    assert "| Variable | Kind | Sweep point | A+ | Watch | Skip" in md_text
    assert "**Eval-runs window:**" in md_text
    assert "**Total candidates:** 5000" in md_text
    # V1 limitation paragraph present + threshold-variable distinction visible.
    assert "V1 LIMITATION:" in md_text
    assert "Threshold variables (kind = threshold_additive |" in md_text
    assert "intentionally ZERO" in md_text
    # Per-row kind value rendered in the matrix cells.
    assert "| trend_template.min_passes | gate | 5 |" in md_text
    assert "| vcp.adr_min_pct | threshold_multiplicative | 2.5 |" in md_text


def test_markdown_output_distinguishes_gate_from_threshold(tmp_path: Path) -> None:
    """Pre-emptive regression: header includes Kind column + V1-limitation
    paragraph names both threshold_additive AND threshold_multiplicative."""
    result = _build_synthetic_result()
    md_path = tmp_path / "out.md"
    write_sensitivity_markdown(result, md_path)
    text = md_path.read_text(encoding="utf-8")
    assert "| Variable | Kind | Sweep point" in text
    assert "Threshold variables (kind = threshold_additive |" in text
    assert "intentionally ZERO" in text


def test_csv_header_columns_exactly_match_expected_set(tmp_path: Path) -> None:
    """Expansion #11 taxonomy propagation: kind column is part of CSV header."""
    result = _build_synthetic_result()
    csv_path = tmp_path / "out.csv"
    write_sensitivity_csv(result, csv_path)
    first_line = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == (
        "variable_name,kind,sweep_point,aplus_count,watch_count,"
        "skip_count,excluded_count,delta_aplus,delta_watch"
    )
