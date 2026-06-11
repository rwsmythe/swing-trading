"""Phase 10 Sub-bundle E Task T-E.2 — ProcessGradeTrendVM tests.

Covers plan §H T-E.2 acceptance:
- VM extends BaseLayoutVM + populates unresolved_material_discrepancies_count.
- Inline SVG (§A.10 LOCK; no matplotlib).
- Confidence-floor + window-not-full + drawability text surface as
  SEPARATE template fields per lesson #23.
- Per-trade markers always emitted when trades exist; rolling polyline
  only when the §5.4 line band fires.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.metrics.process_grade_trend import RollingLinePoint
from swing.web.view_models.metrics.process_grade_trend import (
    COST_SVG_HEIGHT,
    ProcessGradeTrendVM,
    RollingSeriesDisplay,
    _cost_panel_bounds,
    _polyline_y,
    build_process_grade_trend_vm,
)
from swing.web.view_models.metrics.shared import BaseLayoutVM


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "phase10_pgt_vm.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )


def _seed_reviewed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    process_grade: str,
    disqualifying: int = 0,
    realized_R_if_plan_followed: float | None = 1.0,  # noqa: N803
    exit_price: float = 11.0,
    reviewed_at: str = "2026-04-01T16:00:00",
    last_fill_at: str = "2026-04-01T15:30:00",
    entry_intent: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "process_grade, entry_grade, management_grade, exit_grade, "
        "disqualifying_process_violation, realized_R_if_plan_followed, "
        "reviewed_at, last_fill_at, entry_intent) VALUES "
        "(?, ?, '2026-03-15', 10.0, 100, 9.0, 9.0, 'reviewed', 'S', 'I', "
        "'manual_off_pipeline', '2026-03-15T09:30:00', 0, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?)",
        (
            trade_id, ticker,
            process_grade, process_grade, process_grade, process_grade,
            disqualifying, realized_R_if_plan_followed,
            reviewed_at, last_fill_at, entry_intent,
        ),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES "
        "(?, '2026-03-15T09:30:00', 'entry', 100, 10.0, 'unreconciled')",
        (trade_id,),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES "
        "(?, ?, 'exit', 100, ?, 'unreconciled')",
        (trade_id, last_fill_at, exit_price),
    )
    conn.commit()


def _seed_n(conn: sqlite3.Connection, n: int, *, process_grade: str = "B") -> None:
    for i in range(n):
        day = (i % 27) + 1
        _seed_reviewed_trade(
            conn,
            trade_id=i + 1,
            ticker=f"T{i:03d}",
            process_grade=process_grade,
            reviewed_at=f"2026-04-{day:02d}T16:00:00",
            last_fill_at=f"2026-04-{day:02d}T15:30:00",
        )


# ---------------------------------------------------------------------------
# Base-layout integration
# ---------------------------------------------------------------------------

def test_vm_is_base_layout_vm(cfg) -> None:
    vm = build_process_grade_trend_vm(cfg=cfg)
    assert isinstance(vm, ProcessGradeTrendVM)
    assert isinstance(vm, BaseLayoutVM)


def test_vm_carries_base_layout_fields(cfg) -> None:
    vm = build_process_grade_trend_vm(cfg=cfg)
    assert vm.session_date
    assert vm.unresolved_material_discrepancies_count == 0


def test_vm_has_seven_rolling_series_per_a21_matrix(cfg) -> None:
    vm = build_process_grade_trend_vm(cfg=cfg)
    names = {s.metric_name for s in vm.rolling_series}
    assert names == {
        "process_grade_rolling_N",
        "entry_grade_rolling_N",
        "management_grade_rolling_N",
        "exit_grade_rolling_N",
        "mistake_cost_R_rolling_N_per_trade",
        "disqualifying_violation_rate_rolling_N",
        "mistake_cost_R_rolling_N_total",
    }


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

def test_vm_zero_trades_no_markers_all_suppressed(cfg) -> None:
    vm = build_process_grade_trend_vm(cfg=cfg)
    assert vm.per_trade_markers == ()
    for series in vm.rolling_series:
        assert series.is_suppressed is True
        assert series.suppressed_placeholder
        assert series.svg_polyline_segments == ()
        assert series.is_drawable is False


# ---------------------------------------------------------------------------
# Per-trade marker projection
# ---------------------------------------------------------------------------

def test_per_trade_markers_emit_in_review_order(cfg) -> None:
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        _seed_n(conn, 3, process_grade="A")
    finally:
        conn.close()
    vm = build_process_grade_trend_vm(cfg=cfg)
    assert len(vm.per_trade_markers) == 3
    # SVG coordinates monotonic in X.
    xs = [m.svg_x for m in vm.per_trade_markers]
    assert xs == sorted(xs)
    # Grade=A → numeric=4.0; svg_y = top margin (Y axis grows DOWN).
    for m in vm.per_trade_markers:
        assert m.process_grade_letter == "A"
        assert m.process_grade_numeric == 4.0
        assert m.svg_y is not None


def test_per_trade_markers_render_for_disqualifying_trade(cfg) -> None:
    """Disqualifying flag surfaces on the marker for ``data-disqualifying=1``."""
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        _seed_reviewed_trade(
            conn, trade_id=1, ticker="DQ", process_grade="D",
            disqualifying=1,
        )
    finally:
        conn.close()
    vm = build_process_grade_trend_vm(cfg=cfg)
    assert len(vm.per_trade_markers) == 1
    assert vm.per_trade_markers[0].disqualifying == 1


# ---------------------------------------------------------------------------
# Task 7 — marker entry_intent normalized CSS-class hook (#22 preserved)
# ---------------------------------------------------------------------------

def test_marker_carries_normalized_intent_css_class(cfg) -> None:
    """The raw hypothesis_test_by_design token normalizes to the spec §7.2
    `by-design` CSS hook (Codex R1-Major-2 — NOT the raw token)."""
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        _seed_reviewed_trade(
            conn, trade_id=1, ticker="STD", process_grade="B",
            entry_intent="standard",
        )
        _seed_reviewed_trade(
            conn, trade_id=2, ticker="BYD", process_grade="B",
            entry_intent="hypothesis_test_by_design",
            reviewed_at="2026-04-02T16:00:00",
            last_fill_at="2026-04-02T15:30:00",
        )
        _seed_reviewed_trade(
            conn, trade_id=3, ticker="UNC", process_grade="B",
            reviewed_at="2026-04-03T16:00:00",
            last_fill_at="2026-04-03T15:30:00",
        )
    finally:
        conn.close()
    vm = build_process_grade_trend_vm(cfg=cfg)
    by_id = {m.trade_id: m for m in vm.per_trade_markers}
    assert by_id[1].entry_intent == "standard"
    assert by_id[1].entry_intent_css_class == "standard"
    # Raw token normalizes to `by-design`, NOT `hypothesis_test_by_design`.
    assert by_id[2].entry_intent == "hypothesis_test_by_design"
    assert by_id[2].entry_intent_css_class == "by-design"
    assert by_id[3].entry_intent is None
    assert by_id[3].entry_intent_css_class == "unclassified"


# ---------------------------------------------------------------------------
# SVG polyline emission
# ---------------------------------------------------------------------------

def test_polyline_emitted_when_window_partial_drawable(cfg) -> None:
    """5≤effective_n<N — line drawable; polyline non-empty."""
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        _seed_n(conn, 5, process_grade="B")
    finally:
        conn.close()
    vm = build_process_grade_trend_vm(cfg=cfg)
    process_series = next(
        s for s in vm.rolling_series if s.metric_name == "process_grade_rolling_N"
    )
    assert process_series.is_drawable is True
    assert process_series.svg_polyline_segments  # non-empty
    for seg in process_series.svg_polyline_segments:
        assert seg.count(",") >= 2  # every segment is a >=2-point run
    # Drawability + warnings as SEPARATE distinct fields per lesson #23.
    assert process_series.drawability_text == "rolling line drawable"
    assert process_series.window_not_full_warning_text == "rolling window not yet at N"
    assert process_series.confidence_floor_warning_text == "below confidence floor (n<20)"


def test_polyline_omitted_when_suppressed(cfg) -> None:
    """effective_n<5 — line suppressed; markers still render."""
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        _seed_n(conn, 4, process_grade="B")
    finally:
        conn.close()
    vm = build_process_grade_trend_vm(cfg=cfg)
    assert len(vm.per_trade_markers) == 4
    process_series = next(
        s for s in vm.rolling_series if s.metric_name == "process_grade_rolling_N"
    )
    assert process_series.is_suppressed is True
    assert process_series.is_drawable is False
    assert process_series.svg_polyline_segments == ()


def test_grade_axis_labels_carry_numeric_encoding_text(cfg) -> None:
    """Lesson #19 — grade axis labels include numeric encoding visible inline."""
    vm = build_process_grade_trend_vm(cfg=cfg)
    label_texts = {label for _, label in vm.grade_axis_labels}
    assert "A=4" in label_texts
    assert "F=0" in label_texts


# ---------------------------------------------------------------------------
# Decoupling — three distinct rendering targets per lesson #23
# ---------------------------------------------------------------------------

def test_decoupled_fields_are_distinct_template_targets(cfg) -> None:
    """Per lesson #23 + spec §5.4: confidence-floor + window-not-full +
    drawability surface as SEPARATE display fields."""
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        _seed_n(conn, 5, process_grade="B")
    finally:
        conn.close()
    vm = build_process_grade_trend_vm(cfg=cfg)
    series = next(
        s for s in vm.rolling_series if s.metric_name == "process_grade_rolling_N"
    )
    # All three populated independently:
    assert series.drawability_text is not None
    assert series.window_not_full_warning_text is not None
    assert series.confidence_floor_warning_text is not None
    # And they differ in content:
    assert series.drawability_text != series.window_not_full_warning_text
    assert series.window_not_full_warning_text != series.confidence_floor_warning_text


# ---------------------------------------------------------------------------
# Dataclass invariants
# ---------------------------------------------------------------------------

def test_vm_rejects_missing_metric_key(cfg) -> None:
    with pytest.raises(ValueError, match="metric names must match the §A.21"):
        ProcessGradeTrendVM(
            session_date="2026-05-13",
            unresolved_material_discrepancies_count=0,
            window_size=10,
            per_trade_markers=(),
            rolling_series=(),  # missing all 7
        )


def test_rolling_series_display_rejects_empty_placeholder_when_suppressed() -> None:
    with pytest.raises(ValueError, match="suppressed_placeholder required"):
        RollingSeriesDisplay(
            metric_name="process_grade_rolling_N",
            underlying_class="B",
            is_suppressed=True,
            suppressed_placeholder=None,
            point_value_text=None,
            ci_lower_text=None,
            ci_upper_text=None,
            drawability_text=None,
            window_not_full_warning_text=None,
            confidence_floor_warning_text=None,
            svg_polyline_segments=(),
            is_drawable=False,
        )


# ---------------------------------------------------------------------------
# Slice B (B2) — small-multiples per-panel grouping + 0-anchored cost bounds
# ---------------------------------------------------------------------------

_GRADE_NAMES = {
    "process_grade_rolling_N",
    "entry_grade_rolling_N",
    "management_grade_rolling_N",
    "exit_grade_rolling_N",
}


def test_vm_groups_series_into_three_panels(cfg) -> None:
    """grade/rate/cost panel groups are ADDITIVE; rolling_series stays all 7 for
    the table. _total is charted in NO panel group (table-only, OQ-3)."""
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        _seed_n(conn, 5, process_grade="B")
    finally:
        conn.close()
    vm = build_process_grade_trend_vm(cfg=cfg)
    assert {s.metric_name for s in vm.grade_series} == _GRADE_NAMES
    assert {s.metric_name for s in vm.rate_series} == {
        "disqualifying_violation_rate_rolling_N"
    }
    assert {s.metric_name for s in vm.cost_series} == {
        "mistake_cost_R_rolling_N_per_trade"
    }
    # _total stays in rolling_series (table) but in none of the panel groups.
    all_names = {s.metric_name for s in vm.rolling_series}
    assert "mistake_cost_R_rolling_N_total" in all_names
    panel_names = (
        {s.metric_name for s in vm.grade_series}
        | {s.metric_name for s in vm.rate_series}
        | {s.metric_name for s in vm.cost_series}
    )
    assert "mistake_cost_R_rolling_N_total" not in panel_names


def test_cost_panel_bounds_zero_anchored_for_nonzero_costs() -> None:
    """Direct helper test (Codex R1-m1 — exact, not DB-seeded). 0-anchored:
    the min is ignored, the bound starts at 0."""
    bounds = _cost_panel_bounds((
        RollingLinePoint(0, 0.3),
        RollingLinePoint(1, 2.0),
        RollingLinePoint(2, 1.0),
    ))
    assert bounds == (0.0, 2.0)
    # The peak maps to the top margin (24), not clipped; baseline maps to 120.
    assert _polyline_y(
        2.0, y_min=0.0, y_max=2.0, layout_height=COST_SVG_HEIGHT,
        margin_top=24, margin_bottom=40,
    ) == 24.00
    assert _polyline_y(
        0.0, y_min=0.0, y_max=2.0, layout_height=COST_SVG_HEIGHT,
        margin_top=24, margin_bottom=40,
    ) == 120.00


def test_cost_panel_all_zero_uses_unit_fallback_not_degenerate(cfg) -> None:
    """The all-zero (perfect-process) edge uses [0,1] not [0,0]: _polyline_y
    centers when y_max==y_min, so a [0,0] zero line would float mid-panel (72)
    with degenerate labels. [0,1] keeps the zero line on the baseline (120)."""
    assert _cost_panel_bounds(()) == (0.0, 1.0)
    assert _cost_panel_bounds((
        RollingLinePoint(0, 0.0),
        RollingLinePoint(1, 0.0),
    )) == (0.0, 1.0)
    # Baseline Y discriminator: 120.00 (baseline) NOT 72.00 (panel midpoint).
    assert _polyline_y(
        0.0, y_min=0.0, y_max=1.0, layout_height=160,
        margin_top=24, margin_bottom=40,
    ) == 120.00
    # Build the VM with an all-zero-cost perfect-process seed (grade A, no
    # disqualifying, realized_R_if_plan_followed left as the 1.0 default so
    # mistake_cost is 0).
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        _seed_n(conn, 5, process_grade="A")
    finally:
        conn.close()
    vm = build_process_grade_trend_vm(cfg=cfg)
    assert vm.cost_y_max == 1.0
    cost_texts = tuple(text for _, text in vm.cost_axis_labels)
    assert cost_texts == ("0.00", "0.50", "1.00")


def test_rate_axis_labels_present_and_positioned(cfg) -> None:
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        _seed_n(conn, 5, process_grade="B")
    finally:
        conn.close()
    vm = build_process_grade_trend_vm(cfg=cfg)
    rate_texts = tuple(text for _, text in vm.rate_axis_labels)
    assert rate_texts == ("0.0", "0.5", "1.0")
    # Ys within the 160-panel plot band [margin_top=24, height-margin_bottom=120].
    for y, _ in vm.rate_axis_labels:
        assert 24.0 <= y <= 120.0


def test_vm_post_init_rejects_malformed_panel_groups(cfg) -> None:
    """The additive group validation rejects a cost_series carrying the wrong
    metric (mirror-the-contract, #11)."""
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        _seed_n(conn, 5, process_grade="B")
    finally:
        conn.close()
    vm = build_process_grade_trend_vm(cfg=cfg)
    wrong = vm.grade_series[0]  # process_grade series, not the per-trade cost
    with pytest.raises(ValueError, match="cost_series"):
        dc_replace(vm, cost_series=(wrong,))
