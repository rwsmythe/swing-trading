"""Phase 10 Sub-bundle E Task T-E.1 — §3.8 process-grade-trend tests.

Covers plan §H T-E.1 acceptance:

- Numeric grade encoding A=4..F=0 (spec §3.8 line 217).
- Per-metric Class assignment per §A.21 BINDING matrix.
- Class D 3-tuple decoupling per spec §5.4 (line drawable from
  effective_n>=5; window-not-full + confidence-floor warnings remain
  decoupled — Codex R1 M#1 fix).
- N=10 HARDCODED (spec §8.5 LOCK).
- ORDER BY ``reviewed_at, id`` deterministic tiebreaker (forward-binding
  lesson #26).
- Lesson #18 cadence-grain rejection: aggregation iterates per-trade
  Phase 6 stored grades + Phase 6 ``compute_mistake_cost_R`` (NOT
  cadence-grain ``review_log.total_*`` aggregates).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.metrics.honesty import (
    BootstrapCI,
    SuppressedMetric,
    WilsonCI,
)
from swing.metrics.process_grade_trend import (
    DEFAULT_WINDOW_SIZE,
    GRADE_TO_NUMERIC,
    PROCESS_GRADE_TREND_METRIC_CLASSES,
    ProcessGradeTrendPoint,
    ProcessGradeTrendResult,
    RollingLinePoint,
    RollingMetricSeries,
    compute_process_grade_trend,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase10_pgt.db")


def _seed_reviewed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    process_grade: str | None,
    entry_grade: str | None = None,
    management_grade: str | None = None,
    exit_grade: str | None = None,
    disqualifying: int = 0,
    realized_R_if_plan_followed: float | None = 1.0,  # noqa: N803
    exit_price: float = 11.0,
    initial_shares: int = 100,
    entry_price: float = 10.0,
    initial_stop: float = 9.0,
    reviewed_at: str = "2026-04-01T16:00:00",
    last_fill_at: str = "2026-04-01T15:30:00",
) -> None:
    """Seed a reviewed trade with stored Phase 6 grades.

    risk_per_share = entry - stop = $1; risk_budget = $1 * shares.
    actual_realized_R = (exit_price - entry_price) / risk_per_share.
    mistake_cost_R = max(0, realized_R_if_plan_followed - actual_realized_R).
    """
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "process_grade, entry_grade, management_grade, exit_grade, "
        "disqualifying_process_violation, realized_R_if_plan_followed, "
        "reviewed_at, last_fill_at) VALUES "
        "(?, ?, '2026-03-15', ?, ?, ?, ?, 'reviewed', 'S', 'I', "
        "'manual_off_pipeline', '2026-03-15T09:30:00', ?, ?, ?, ?, ?, "
        "?, ?, ?, ?)",
        (
            trade_id, ticker, entry_price, initial_shares, initial_stop,
            initial_stop, 0,  # current_size=0 (fully exited)
            process_grade, entry_grade or process_grade,
            management_grade or process_grade,
            exit_grade or process_grade,
            disqualifying, realized_R_if_plan_followed,
            reviewed_at, last_fill_at,
        ),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES "
        "(?, '2026-03-15T09:30:00', 'entry', ?, ?, 'unreconciled')",
        (trade_id, initial_shares, entry_price),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES "
        "(?, ?, 'exit', ?, ?, 'unreconciled')",
        (trade_id, last_fill_at, initial_shares, exit_price),
    )
    conn.commit()


def _seed_n_reviewed_trades(
    conn: sqlite3.Connection,
    *,
    n: int,
    process_grade: str = "B",
    disqualifying: int = 0,
    starting_trade_id: int = 1,
    realized_R_if_plan_followed: float | None = 1.0,  # noqa: N803
    exit_price: float = 11.0,  # actual R = +1.0 by default; mistake_cost = 0
) -> None:
    for i in range(n):
        # reviewed_at varies by day so ORDER BY is deterministic.
        day = (i % 27) + 1
        _seed_reviewed_trade(
            conn,
            trade_id=starting_trade_id + i,
            ticker=f"T{starting_trade_id + i:03d}",
            process_grade=process_grade,
            disqualifying=disqualifying,
            realized_R_if_plan_followed=realized_R_if_plan_followed,
            exit_price=exit_price,
            reviewed_at=f"2026-04-{day:02d}T16:00:00",
            last_fill_at=f"2026-04-{day:02d}T15:30:00",
        )


# ---------------------------------------------------------------------------
# Encoding + matrix
# ---------------------------------------------------------------------------

def test_grade_letter_to_numeric_encoding():
    """Per spec §3.8 line 217 numeric encoding."""
    assert GRADE_TO_NUMERIC["A"] == 4
    assert GRADE_TO_NUMERIC["B"] == 3
    assert GRADE_TO_NUMERIC["C"] == 2
    assert GRADE_TO_NUMERIC["D"] == 1
    assert GRADE_TO_NUMERIC["F"] == 0


def test_per_metric_class_matrix_matches_a21():
    """Per plan §A.21 BINDING per-metric matrix (Codex R2 M#1)."""
    assert PROCESS_GRADE_TREND_METRIC_CLASSES["process_grade_rolling_N"] == "B"
    assert PROCESS_GRADE_TREND_METRIC_CLASSES["entry_grade_rolling_N"] == "B"
    assert PROCESS_GRADE_TREND_METRIC_CLASSES["management_grade_rolling_N"] == "B"
    assert PROCESS_GRADE_TREND_METRIC_CLASSES["exit_grade_rolling_N"] == "B"
    assert PROCESS_GRADE_TREND_METRIC_CLASSES["mistake_cost_R_rolling_N_per_trade"] == "B"
    assert PROCESS_GRADE_TREND_METRIC_CLASSES["disqualifying_violation_rate_rolling_N"] == "A"
    assert PROCESS_GRADE_TREND_METRIC_CLASSES["mistake_cost_R_rolling_N_total"] == "point"


def test_default_window_size_is_10():
    """Spec §8.5 LOCK: N=10 HARDCODED for V1."""
    assert DEFAULT_WINDOW_SIZE == 10


# ---------------------------------------------------------------------------
# Zero-trade base case
# ---------------------------------------------------------------------------

def test_compute_process_grade_trend_zero_trades_returns_all_suppressed(
    conn: sqlite3.Connection,
) -> None:
    result = compute_process_grade_trend(conn)
    assert isinstance(result, ProcessGradeTrendResult)
    assert result.window_size == 10
    assert result.per_trade_markers == ()
    for metric_name, klass in PROCESS_GRADE_TREND_METRIC_CLASSES.items():
        series = result.rolling_series[metric_name]
        assert isinstance(series, RollingMetricSeries)
        assert series.underlying_class == klass
        assert isinstance(series.suppressed, SuppressedMetric), (
            f"{metric_name} should be SuppressedMetric at n=0"
        )
        assert series.rendered_value is None
        assert series.badges is None
        assert series.drawability_text is None
        assert series.line_points == ()


# ---------------------------------------------------------------------------
# Per-trade markers
# ---------------------------------------------------------------------------

def test_per_trade_markers_one_per_closed_reviewed_trade(
    conn: sqlite3.Connection,
) -> None:
    _seed_n_reviewed_trades(conn, n=3, process_grade="A")
    result = compute_process_grade_trend(conn)
    assert len(result.per_trade_markers) == 3
    for i, marker in enumerate(result.per_trade_markers):
        assert isinstance(marker, ProcessGradeTrendPoint)
        assert marker.ordinal == i
        assert marker.process_grade_letter == "A"
        assert marker.process_grade_numeric == 4.0


def test_per_trade_markers_ordered_by_reviewed_at_then_id(
    conn: sqlite3.Connection,
) -> None:
    """Forward-binding lesson #26 — deterministic ORDER BY tiebreaker."""
    # Two trades reviewed at the same ms-ISO timestamp: id ordering must
    # win deterministically.
    _seed_reviewed_trade(
        conn, trade_id=10, ticker="ZZZ", process_grade="A",
        reviewed_at="2026-04-15T16:00:00",
        last_fill_at="2026-04-15T15:30:00",
    )
    _seed_reviewed_trade(
        conn, trade_id=5, ticker="AAA", process_grade="B",
        reviewed_at="2026-04-15T16:00:00",
        last_fill_at="2026-04-15T15:30:00",
    )
    result = compute_process_grade_trend(conn)
    assert len(result.per_trade_markers) == 2
    # id=5 emits first per the secondary ORDER BY id tiebreaker.
    assert result.per_trade_markers[0].trade_id == 5
    assert result.per_trade_markers[1].trade_id == 10


def test_mistake_cost_R_computed_per_trade_not_via_review_log(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """Lesson #18 cadence-grain rejection.

    Seed a trade with realized_R_if_plan_followed=2.0 and actual realized
    R = 1.0 (exit at +1.0R → exit_price = entry + risk_per_share = 11.0).
    mistake_cost_R should be 1.0 (plan − actual = 2.0 − 1.0). Confirms the
    helper iterates per-trade and uses Phase 6's compute_mistake_cost_R
    (NOT review_log.total_mistake_cost_R which is cadence-grain and would
    aggregate differently across all trades in the review window).
    """
    _seed_reviewed_trade(
        conn, trade_id=1, ticker="AAA", process_grade="B",
        realized_R_if_plan_followed=2.0,
        exit_price=11.0,  # actual R = (11-10)/1 = +1.0
    )
    result = compute_process_grade_trend(conn)
    assert len(result.per_trade_markers) == 1
    assert result.per_trade_markers[0].mistake_cost_R == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# §5.4 Class D 3-tuple decoupling — 4 bands
# ---------------------------------------------------------------------------

def test_compute_process_grade_trend_5_trades_window_10_partial_window_render(
    conn: sqlite3.Connection,
) -> None:
    """Spec §5.4 5<=effective_n<N band:

    - rolling line drawable (drawability_text='rolling line drawable').
    - window_not_full_warning=True (effective_n=5 < N=10).
    - confidence_floor_warning=True (effective_n=5 < global_floor=20).
    """
    _seed_n_reviewed_trades(conn, n=5, process_grade="B")
    result = compute_process_grade_trend(conn)
    series = result.rolling_series["process_grade_rolling_N"]
    assert series.suppressed is None
    assert series.drawability_text == "rolling line drawable"
    assert series.badges is not None
    assert series.badges.window_not_full_warning is True
    assert series.badges.confidence_floor_warning is True


def test_compute_process_grade_trend_10_trades_window_10_full_window_below_floor(
    conn: sqlite3.Connection,
) -> None:
    """Spec §5.4 N<=effective_n<global_floor band: full window + floor warning persists."""
    _seed_n_reviewed_trades(conn, n=10, process_grade="B")
    result = compute_process_grade_trend(conn)
    series = result.rolling_series["process_grade_rolling_N"]
    assert series.suppressed is None
    assert series.drawability_text == "rolling line drawable"
    assert series.badges is not None
    assert series.badges.window_not_full_warning is False
    assert series.badges.confidence_floor_warning is True


def test_compute_process_grade_trend_20_trades_drops_confidence_floor_warning(
    conn: sqlite3.Connection,
) -> None:
    """Spec §5.4 effective_n>=global_floor band: confidence-floor warning drops.

    BINDING semantics per honesty.py implementation (Sub-bundle A): the
    confidence-floor predicate compares ``effective_n=len(samples_in_window)``
    against ``policy.global_confidence_floor_n`` — so the warning only drops
    when the window itself reaches the global floor. With the production
    default ``N=10`` the warning never drops by construction; to verify
    the band exists we exercise ``window_size=20`` (mirroring spec §5.4
    band where N >= global_confidence_floor_n).

    The §A.21 spec-deviation note about this is banked at writing-plans:
    the operationally relevant rolling cadence is N=10 + persistent
    floor warning by design. This test verifies the band semantics are
    reachable when an explicit window_size hits the floor.
    """
    for i in range(20):
        day = (i % 27) + 1
        month = 3 if i < 14 else 4
        _seed_reviewed_trade(
            conn, trade_id=i + 1, ticker=f"T{i:03d}",
            process_grade="B",
            reviewed_at=f"2026-{month:02d}-{day:02d}T16:00:00",
            last_fill_at=f"2026-{month:02d}-{day:02d}T15:30:00",
        )
    result = compute_process_grade_trend(conn, window_size=20)
    series = result.rolling_series["process_grade_rolling_N"]
    assert series.suppressed is None
    assert series.drawability_text == "rolling line drawable"
    assert series.badges is not None
    assert series.badges.window_not_full_warning is False
    assert series.badges.confidence_floor_warning is False


def test_below_line_floor_suppresses(
    conn: sqlite3.Connection,
) -> None:
    """effective_n<5 → SuppressedMetric; markers still render."""
    _seed_n_reviewed_trades(conn, n=4, process_grade="B")
    result = compute_process_grade_trend(conn)
    series = result.rolling_series["process_grade_rolling_N"]
    assert isinstance(series.suppressed, SuppressedMetric)
    # markers always render even when rolling line is suppressed
    assert len(result.per_trade_markers) == 4


# ---------------------------------------------------------------------------
# §A.21 per-metric class value-slot type
# ---------------------------------------------------------------------------

def test_process_grade_rolling_N_value_slot_carries_BootstrapCI(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """Plan §A.21: underlying_class='B' → BootstrapCI."""
    _seed_n_reviewed_trades(conn, n=10, process_grade="B")
    series = compute_process_grade_trend(conn).rolling_series[
        "process_grade_rolling_N"
    ]
    assert isinstance(series.rendered_value, BootstrapCI)
    # B=3, so all 10 sample values are 3.0 → BootstrapCI point ≈ 3.0.
    assert series.rendered_value.point == pytest.approx(3.0)


def test_disqualifying_violation_rate_rolling_N_value_slot_carries_WilsonCI(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """Plan §A.21: underlying_class='A' + events_in_window=k → WilsonCI."""
    # Mix: 3 disqualifying + 7 not → events=3 over n=10.
    for i in range(10):
        day = (i % 27) + 1
        _seed_reviewed_trade(
            conn, trade_id=i + 1, ticker=f"T{i:03d}",
            process_grade="B",
            disqualifying=1 if i < 3 else 0,
            reviewed_at=f"2026-04-{day:02d}T16:00:00",
            last_fill_at=f"2026-04-{day:02d}T15:30:00",
        )
    series = compute_process_grade_trend(conn).rolling_series[
        "disqualifying_violation_rate_rolling_N"
    ]
    assert isinstance(series.rendered_value, WilsonCI)
    assert series.rendered_value.point == pytest.approx(3.0 / 10.0)


def test_mistake_cost_R_rolling_N_total_value_slot_carries_float_only(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """Plan §A.21 spec-conformance deviation: 'point' class → bare float (sum)."""
    # 10 trades each with mistake_cost_R = 1.0 (plan=2, actual=1 → cost=1).
    for i in range(10):
        day = (i % 27) + 1
        _seed_reviewed_trade(
            conn, trade_id=i + 1, ticker=f"T{i:03d}",
            process_grade="B",
            realized_R_if_plan_followed=2.0,
            exit_price=11.0,  # actual R = +1.0
            reviewed_at=f"2026-04-{day:02d}T16:00:00",
            last_fill_at=f"2026-04-{day:02d}T15:30:00",
        )
    series = compute_process_grade_trend(conn).rolling_series[
        "mistake_cost_R_rolling_N_total"
    ]
    assert series.suppressed is None
    assert isinstance(series.rendered_value, float)
    # SUM of cost over window of 10 = 10.0
    assert series.rendered_value == pytest.approx(10.0)


def test_mistake_cost_R_rolling_N_per_trade_value_slot_carries_BootstrapCI(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """Plan §A.21 + spec §5.2: per-trade-cost (Class B) → BootstrapCI."""
    for i in range(10):
        day = (i % 27) + 1
        _seed_reviewed_trade(
            conn, trade_id=i + 1, ticker=f"T{i:03d}",
            process_grade="B",
            realized_R_if_plan_followed=2.0,
            exit_price=11.0,
            reviewed_at=f"2026-04-{day:02d}T16:00:00",
            last_fill_at=f"2026-04-{day:02d}T15:30:00",
        )
    series = compute_process_grade_trend(conn).rolling_series[
        "mistake_cost_R_rolling_N_per_trade"
    ]
    assert isinstance(series.rendered_value, BootstrapCI)
    # MEAN of cost over window of 10 = 1.0
    assert series.rendered_value.point == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Rolling line points
# ---------------------------------------------------------------------------

def test_rolling_line_points_emit_per_position(
    conn: sqlite3.Connection,
) -> None:
    """One RollingLinePoint per closed-reviewed trade ordinal; None for <3
    samples (operational floor); finite mean once the window has >=3."""
    _seed_n_reviewed_trades(conn, n=5, process_grade="B")
    series = compute_process_grade_trend(conn).rolling_series[
        "process_grade_rolling_N"
    ]
    assert len(series.line_points) == 5
    # First two have <3 samples → None.
    assert series.line_points[0].value is None
    assert series.line_points[1].value is None
    # Positions 2..4 have 3..5 samples → mean = 3.0 (all B=3).
    for i in range(2, 5):
        assert series.line_points[i].value == pytest.approx(3.0)


def test_rolling_line_points_class_A_renders_as_rate_not_mean(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """Class A rolling LINE is k/n per window — NOT mean(1.0)=1.0."""
    # 3 disqualifying + 7 not → window-end rate = 3/10 = 0.3.
    for i in range(10):
        day = (i % 27) + 1
        _seed_reviewed_trade(
            conn, trade_id=i + 1, ticker=f"T{i:03d}",
            process_grade="B",
            disqualifying=1 if i < 3 else 0,
            reviewed_at=f"2026-04-{day:02d}T16:00:00",
            last_fill_at=f"2026-04-{day:02d}T15:30:00",
        )
    series = compute_process_grade_trend(conn).rolling_series[
        "disqualifying_violation_rate_rolling_N"
    ]
    assert len(series.line_points) == 10
    # Last point: 3 events of 10 trades = 0.3.
    assert series.line_points[-1].value == pytest.approx(0.3)
    # NOT 1.0 (which would indicate the broken "mean of sentinel" path).
    assert series.line_points[-1].value != pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Dataclass invariants
# ---------------------------------------------------------------------------

def test_rolling_metric_series_rejects_metric_name_outside_matrix():
    with pytest.raises(ValueError, match="metric_name must be one of"):
        RollingMetricSeries(
            metric_name="nonsense_rolling",
            underlying_class="B",
            line_points=(),
            rendered_value=None,
            badges=None,
            drawability_text=None,
            suppressed=SuppressedMetric(
                metric_name="nonsense_rolling", n=0, n_required=5,
                placeholder_text="[nonsense_rolling: ...]",
            ),
        )


def test_rolling_metric_series_rejects_class_mismatch_for_metric():
    """Constructor MUST reject underlying_class diverging from §A.21 matrix."""
    with pytest.raises(ValueError, match="must match the §A.21"):
        RollingMetricSeries(
            metric_name="process_grade_rolling_N",
            underlying_class="A",   # wrong — should be 'B'
            line_points=(),
            rendered_value=None,
            badges=None,
            drawability_text=None,
            suppressed=SuppressedMetric(
                metric_name="process_grade_rolling_N", n=0, n_required=5,
                placeholder_text="[process_grade_rolling_N: ...]",
            ),
        )


def test_process_grade_trend_result_rejects_missing_metric_key():
    with pytest.raises(ValueError, match="rolling_series keys must match"):
        ProcessGradeTrendResult(
            window_size=10, per_trade_markers=(), rolling_series={},
        )


def test_process_grade_trend_point_post_init_rejects_invalid_disqualifying():
    with pytest.raises(ValueError, match="disqualifying must be 0 or 1"):
        ProcessGradeTrendPoint(
            ordinal=0, trade_id=1, ticker="A", review_date="2026-04-01",
            process_grade_letter="A", process_grade_numeric=4.0,
            entry_grade_numeric=4.0, management_grade_numeric=4.0,
            exit_grade_numeric=4.0,
            disqualifying=2,  # invalid
            mistake_cost_R=0.0,
        )


def test_rolling_line_point_post_init_rejects_negative_ordinal():
    with pytest.raises(ValueError, match="ordinal must be >= 0"):
        RollingLinePoint(ordinal=-1, value=1.0)


# ---------------------------------------------------------------------------
# Window-size override
# ---------------------------------------------------------------------------

def test_compute_process_grade_trend_window_size_zero_raises(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ValueError, match="window_size must be > 0"):
        compute_process_grade_trend(conn, window_size=0)


def test_compute_process_grade_trend_respects_window_override(
    conn: sqlite3.Connection,
) -> None:
    """When called with window_size=5 (N=5), the window-not-full warning
    drops at effective_n=5 (instead of staying True until 10)."""
    _seed_n_reviewed_trades(conn, n=5, process_grade="B")
    series = compute_process_grade_trend(
        conn, window_size=5,
    ).rolling_series["process_grade_rolling_N"]
    assert series.suppressed is None
    assert series.badges is not None
    # At effective_n=5 with N=5 → full window; window_not_full_warning=False.
    assert series.badges.window_not_full_warning is False
    # confidence_floor_warning still True (5 < 20 global floor).
    assert series.badges.confidence_floor_warning is True
