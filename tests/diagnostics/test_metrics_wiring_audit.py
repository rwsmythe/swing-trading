"""T-T4.SB.1 §B.1 Sub-task 1F — metrics-wiring-audit module tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.diagnostics.metrics_wiring_audit import (
    SurfaceAuditRow,
    audit_surface_match_strategy,
    enumerate_metric_surfaces,
    write_metrics_wiring_audit_markdown,
)


def test_audit_enumerates_known_metric_surfaces() -> None:
    rows = enumerate_metric_surfaces()
    names = {r.surface_name for r in rows}
    # Per spec §B.7.2 + OQ-7.2: at minimum these are audited.
    assert "Dashboard hyp-progress card" in names
    assert "CLI compute_hypothesis_progress_breakdown" in names
    assert "list_trades_for_cohort" in names
    assert "count_per_cohort" in names
    # Each row carries file:line + match strategy + state filter.
    for r in rows:
        assert isinstance(r, SurfaceAuditRow)
        assert r.file_path
        assert r.match_strategy in {
            "exact_equality",
            "prefix_match",
            "delimiter_aware",
            "sql_like",
            "unknown",
        }


def test_audit_rows_are_frozen_dataclasses() -> None:
    import dataclasses

    import pytest

    rows = enumerate_metric_surfaces()
    assert len(rows) >= 4

    with pytest.raises(dataclasses.FrozenInstanceError):
        # frozen dataclass -- attribute assignment must fail.
        rows[0].surface_name = "tampered"  # type: ignore[misc]


def test_audit_surface_match_strategy_returns_passed_row() -> None:
    """V1 stub: ``audit_surface_match_strategy`` returns the row as-is.

    Banked V1 simplification per `_KNOWN_SURFACES` hand-maintained registry
    cumulative gotcha; T-T4.SB.2 broader audit may populate
    ``operator_db_count`` per-surface (see method record / V2 dependencies).
    """
    conn = sqlite3.connect(":memory:")
    rows = enumerate_metric_surfaces()
    out = audit_surface_match_strategy(conn, rows[0])
    assert out is rows[0]


def test_write_audit_markdown_is_ascii_clean(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    out_path = tmp_path / "audit.md"
    written = write_metrics_wiring_audit_markdown(conn, out_path)
    assert written == out_path
    text = out_path.read_text(encoding="utf-8")
    text.encode("cp1252")  # ASCII-safe
    assert "| Surface | File:line |" in text
    assert "Dashboard hyp-progress card" in text
    assert "count_per_cohort" in text


def test_write_audit_markdown_includes_per_surface_notes_section(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    out_path = tmp_path / "audit.md"
    write_metrics_wiring_audit_markdown(conn, out_path)
    text = out_path.read_text(encoding="utf-8")
    assert "## Notes per surface" in text
    # Each known surface has its own ### subsection.
    for row in enumerate_metric_surfaces():
        assert f"### {row.surface_name}" in text
