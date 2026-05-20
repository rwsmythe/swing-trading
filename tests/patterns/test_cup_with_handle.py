"""Phase 13 T2.SB3 T-A.3.4 - discriminating tests for cup_with_handle detector.

Per plan section G.4 T-A.3.4 Step 1: 12+ failing tests covering spec
section 5.4 (8 criteria + tolerances) + section 10.3 (XYZ worked example;
rounded cup pass scenario) + section 10.7 (rounded-vs-V LOCK) +
section 10.6 (tolerance-semantics uniformity LOCK).

LOCKs honored:
- L1: verbatim spec section 5.4 criteria + tolerance values + section
  10.7 rounded-vs-V semantics.
- L2: ZERO DB writes inside detector and _is_rounded_cup helper.
- L7: frozen dataclass with __post_init__ runtime validation.
- L5: ASCII-only.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing.patterns.cup_with_handle import (
    CupWithHandleEvidence,
    _is_rounded_cup,
    detect_cup_with_handle,
)
from swing.patterns.foundation import CandidateWindow

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _bars_from_segments(
    segments: list[tuple[float, float, int]],
    start: date,
    *,
    noise_pct: float = 0.005,
    volumes_per_bar: list[float] | None = None,
) -> pd.DataFrame:
    """Build OHLCV bars by linearly interpolating across price segments.

    H/L derived around Close with the requested ``noise_pct`` half-width.
    """
    closes: list[float] = []
    for seg_start, seg_end, n in segments:
        if n < 1:
            raise ValueError("segment n must be >= 1")
        if not closes:
            xs = np.linspace(seg_start, seg_end, n)
            closes.extend(xs.tolist())
        else:
            xs = np.linspace(seg_start, seg_end, n + 1)[1:]
            closes.extend(xs.tolist())
    n_total = len(closes)
    idx = pd.DatetimeIndex(
        [pd.Timestamp(start) + pd.Timedelta(days=i) for i in range(n_total)]
    )
    closes_arr = np.array(closes, dtype=float)
    highs = closes_arr * (1.0 + noise_pct)
    lows = closes_arr * (1.0 - noise_pct)
    opens = closes_arr
    if volumes_per_bar is None:
        volumes = np.full(n_total, 1_000_000.0)
    else:
        if len(volumes_per_bar) != n_total:
            raise ValueError(
                f"volumes_per_bar length {len(volumes_per_bar)} must equal "
                f"bars length {n_total}"
            )
        volumes = np.array(volumes_per_bar, dtype=float)
    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes_arr,
            "Volume": volumes,
        },
        index=idx,
    )


def _bars_passing_all_criteria_xyz(
    start: date = date(2025, 9, 1),
) -> pd.DataFrame:
    """Construct bars matching the spec section 10.3 XYZ worked example.

    Layout (anchored to start so cup left edge falls at index 60):
    - 60 filler bars at ~17.00 leading into the cup left edge so the
      detector has enough lookback history.
    - Cup left edge index 60 at 20.00. Cup descent 20.00 -> 14.00 over
      ~45 days (criterion #2 depth 30%; cup_left_to_bottom 45 days >= 28).
      Linearly interpolated descent guarantees ~10 bars within the
      cup_bottom +/- 2% marginal zone -> section 10.7 ROUNDED PASS.
    - Cup recovery 14.00 -> 19.50 over ~45 days (cup right edge >= 95%
      of left edge; 19.50 / 20.00 = 0.975).
    - Handle: 19.50 -> 18.00 over 8 days (depth 7.7% <= 15%; >= 5d).
    - Pivot bar at 19.55 (within 1% of cup right edge 19.50).

    Volume: cup avg ~1M; handle avg ~0.80M -> ratio 0.80 <= 0.85
    criterion #8.
    """
    segments = [
        (16.80, 17.00, 60),       # 0..59 filler
        # Cup left edge at index 60 = 20.00.
        (17.00, 20.00, 10),       # 60..69 quick rise into left edge
        # Cup descent: 20.00 -> 14.00 over 45 bars (~6.4 weeks descent).
        (20.00, 14.00, 45),       # 70..114; cup_bottom at index 114 = 14.00
        # Cup recovery: 14.00 -> 19.50 over 45 bars (~6.4 weeks recovery).
        (14.00, 19.50, 45),       # 115..159; cup right edge at index 159 = 19.50
        # Handle: 19.50 -> 18.00 over 8 bars (depth 7.7%).
        (19.50, 18.00, 8),        # 160..167
        # Pivot bar at 19.55.
        (18.00, 19.55, 5),        # 168..172
    ]
    # Volume profile: filler + cup at ~1M; handle (last 13 bars) at ~0.80M.
    bars_len_check = 60 + 10 + 45 + 45 + 8 + 5
    volumes: list[float] = []
    for i in range(bars_len_check):
        if i >= 160 and i < 168:
            volumes.append(800_000.0)   # handle low-volume zone
        elif i >= 168:
            volumes.append(800_000.0)   # extend handle volume profile to pivot
        else:
            volumes.append(1_000_000.0)
    # Note: the actual _bars_from_segments output length may be 1 shorter
    # because segments share endpoints. Re-derive length by building
    # closes first.
    return _bars_from_segments(
        segments, start=start, noise_pct=0.005, volumes_per_bar=volumes
    )


def _candidate_window(
    bars: pd.DataFrame,
    *,
    anchor_offset: int,
    ticker: str = "XYZ",
    reason_prefix: str = "zigzag_pivot",
) -> CandidateWindow:
    """Build a CandidateWindow whose anchor is the bar at anchor_offset.

    For cup_with_handle with zigzag_pivot mode, the anchor_date IS the
    cup left edge (a swing-HIGH; different from VCP/flat_base swing-LOW
    semantics).
    """
    anchor_dt = bars.index[anchor_offset].date()
    return CandidateWindow(
        ticker=ticker,
        timeframe="daily",
        start_date=anchor_dt,
        end_date=bars.index[-1].date(),
        anchor_date=anchor_dt,
        anchor_reason=f"{reason_prefix}:test_anchor",
    )


def _stage_2_conn(ticker: str = "XYZ") -> sqlite3.Connection:
    """In-memory SQLite holding a Stage-2 candidate row for ticker."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE evaluation_runs ("
        "id INTEGER PRIMARY KEY, "
        "action_session_date TEXT, "
        "run_ts TEXT)"
    )
    conn.execute(
        "CREATE TABLE candidates ("
        "id INTEGER PRIMARY KEY, "
        "ticker TEXT, "
        "evaluation_run_id INTEGER)"
    )
    conn.execute(
        "CREATE TABLE candidate_criteria ("
        "candidate_id INTEGER, "
        "layer TEXT, "
        "result TEXT)"
    )
    conn.execute(
        "INSERT INTO evaluation_runs (id, action_session_date, run_ts) "
        "VALUES (1, '2025-09-01', '2025-09-01T16:00:00Z')"
    )
    conn.execute(
        "INSERT INTO candidates (id, ticker, evaluation_run_id) "
        "VALUES (1, ?, 1)",
        (ticker,),
    )
    for _ in range(8):
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, layer, result) "
            "VALUES (1, 'trend_template', 'pass')"
        )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Tests - 8 criteria + section 10.7 rounded-vs-V LOCK + dataclass shape
# ---------------------------------------------------------------------------


def test_cwh_passes_all_criteria_with_rounded_cup_returns_1_0() -> None:
    """Per spec section 10.3 (XYZ worked example) + section 10.7 ROUNDED:
    all 8 criteria pass and rounded-cup HARD PASS -> geometric_score == 1.0.
    """
    bars = _bars_passing_all_criteria_xyz()
    # Anchor at cup left edge (index 70 = end of pre-cup rise).
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    assert isinstance(evidence, CupWithHandleEvidence)
    assert evidence.geometric_score == pytest.approx(1.0)
    for k in (
        "criterion_1",
        "criterion_2",
        "criterion_3",
        "criterion_4",
        "criterion_5",
        "criterion_6",
        "criterion_7",
        "criterion_8",
    ):
        assert evidence.criteria_pass[k] is True, f"{k} failed"
    # Rounded-cup HARD PASS contributes 0.0 penalty.
    assert evidence.rounded_cup_passes is True
    assert evidence.rounded_cup_penalty == pytest.approx(0.0)
    # Marginal zone count is well above the 5-bar HARD PASS threshold.
    assert evidence.rounded_cup_bars_in_marginal_zone >= 5


def test_cwh_fails_criterion_2_cup_depth_below_12pct() -> None:
    """Per spec section 5.4 criterion #2: cup_depth_pct must be in
    [0.12, 0.35]. A shallow 8% cup depth -> FAILS.
    """
    # Shallow cup: 20.00 -> 18.40 (8% depth) -> 19.50.
    segments = [
        (16.80, 17.00, 60),
        (17.00, 20.00, 10),
        (20.00, 18.40, 45),       # only 8% depth
        (18.40, 19.50, 45),
        (19.50, 18.00, 8),
        (18.00, 19.55, 5),
    ]
    bars = _bars_from_segments(segments, start=date(2025, 9, 1))
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_2"] is False


def test_cwh_fails_criterion_2_cup_depth_above_35pct() -> None:
    """Per spec section 5.4 criterion #2: cup_depth_pct must be in
    [0.12, 0.35]. A 45% cup depth -> FAILS.
    """
    # Deep cup: 20.00 -> 11.00 (45% depth) -> 19.50.
    segments = [
        (16.80, 17.00, 60),
        (17.00, 20.00, 10),
        (20.00, 11.00, 45),       # 45% depth (above 35% upper bound)
        (11.00, 19.50, 45),
        (19.50, 18.00, 8),
        (18.00, 19.55, 5),
    ]
    bars = _bars_from_segments(segments, start=date(2025, 9, 1))
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_2"] is False


def test_cwh_fails_criterion_3_cup_right_edge_below_95pct_cup_left_edge() -> None:
    """Per spec section 5.4 criterion #3: cup_right_edge / cup_left_edge
    must be >= 0.95. A right edge at 17.00 (only 85% of 20.00) -> FAILS.
    """
    segments = [
        (16.80, 17.00, 60),
        (17.00, 20.00, 10),
        (20.00, 14.00, 45),       # cup descent 30% depth -> #2 passes
        (14.00, 17.00, 45),       # right edge only 85% of left -> #3 FAILS
        (17.00, 16.00, 8),
        (16.00, 17.00, 5),
    ]
    bars = _bars_from_segments(segments, start=date(2025, 9, 1))
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_3"] is False


def test_cwh_fails_criterion_4_cup_duration_outside_6_26_weeks() -> None:
    """Per spec section 5.4 criterion #4: cup_duration_days must be in
    [42, 182]. A 28-day cup (4 weeks) -> FAILS.
    """
    # Short cup: 14-day descent + 14-day recovery = 28 days total.
    segments = [
        (16.80, 17.00, 60),
        (17.00, 20.00, 10),
        (20.00, 14.00, 14),       # short cup; total duration 28 days
        (14.00, 19.50, 14),
        (19.50, 18.00, 8),
        (18.00, 19.55, 5),
    ]
    bars = _bars_from_segments(segments, start=date(2025, 9, 1))
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_4"] is False


def test_cwh_fails_criterion_5_handle_depth_above_15pct() -> None:
    """Per spec section 5.4 criterion #5: handle_depth_pct must be <= 0.15.
    A handle from 19.50 -> 15.50 (~20% depth) -> FAILS.
    """
    segments = [
        (16.80, 17.00, 60),
        (17.00, 20.00, 10),
        (20.00, 14.00, 45),
        (14.00, 19.50, 45),
        (19.50, 15.50, 8),        # 20.5% handle depth
        (15.50, 19.55, 5),
    ]
    bars = _bars_from_segments(segments, start=date(2025, 9, 1))
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_5"] is False


def test_cwh_fails_criterion_5_handle_duration_below_5d() -> None:
    """Per spec section 5.4 criterion #5: handle_duration_days must be
    >= 5. A 3-day handle -> FAILS.
    """
    segments = [
        (16.80, 17.00, 60),
        (17.00, 20.00, 10),
        (20.00, 14.00, 45),
        (14.00, 19.50, 45),
        (19.50, 18.00, 3),        # 3-day handle (below 5d)
        (18.00, 19.55, 5),
    ]
    bars = _bars_from_segments(segments, start=date(2025, 9, 1))
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_5"] is False


def test_cwh_fails_criterion_6_handle_low_below_cup_midpoint() -> None:
    """Per spec section 5.4 criterion #6: handle_low_price must be >
    cup_midpoint = (cup_left_edge + cup_bottom) / 2. For cup
    [20.00 -> 14.00 -> 19.50] cup_midpoint = (20.00 + 14.00) / 2 = 17.00.
    A handle low at 15.00 -> FAILS (15.00 < 17.00).
    """
    segments = [
        (16.80, 17.00, 60),
        (17.00, 20.00, 10),
        (20.00, 14.00, 45),
        (14.00, 19.50, 45),
        (19.50, 15.00, 8),        # handle low 15.00 < midpoint 17.00
        (15.00, 19.55, 5),
    ]
    bars = _bars_from_segments(segments, start=date(2025, 9, 1))
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_6"] is False


def test_cwh_fails_criterion_8_handle_volume_above_85pct_cup_volume() -> None:
    """Per spec section 5.4 criterion #8: handle_avg_volume /
    cup_avg_volume must be <= 0.85. A handle volume at 95% of cup
    volume -> FAILS.
    """
    # Build all-pass shape but with handle volume at 95% of cup volume.
    segments = [
        (16.80, 17.00, 60),
        (17.00, 20.00, 10),
        (20.00, 14.00, 45),
        (14.00, 19.50, 45),
        (19.50, 18.00, 8),
        (18.00, 19.55, 5),
    ]
    bars_len = 60 + 10 + 45 + 45 + 8 + 5
    # Handle bars are the last 13 (indices 160..172).
    volumes: list[float] = []
    for i in range(bars_len):
        if i >= 160:
            volumes.append(950_000.0)   # 95% of 1M cup volume -> FAILS #8
        else:
            volumes.append(1_000_000.0)
    bars = _bars_from_segments(
        segments, start=date(2025, 9, 1), volumes_per_bar=volumes
    )
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_8"] is False


# ---------------------------------------------------------------------------
# Section 10.7 rounded-vs-V LOCK tests
# ---------------------------------------------------------------------------


def test_cwh_rounded_vs_v_test_centered_on_cup_bottom_date_5_bars_pass() -> None:
    """Per spec section 10.7 LOCK: 5+ bars within 2% of cup_bottom_price
    in the cup_bottom_date +/- 10-day window -> HARD PASS (rounded).
    """
    # Build a bars frame with 7 bars at cup_bottom +/- 2%, centered on
    # cup_bottom_date.
    n = 21
    idx = pd.DatetimeIndex(
        [pd.Timestamp(date(2025, 12, 5)) + pd.Timedelta(days=i)
         for i in range(n)]
    )
    cup_bottom_price = 14.00
    closes = np.full(n, 14.50, dtype=float)
    # Plant 7 bars within 2% of cup_bottom (low <= 14.28) clustered
    # around the cup_bottom_date (the middle of the window, index 10).
    for offset in (-3, -2, -1, 0, 1, 2, 3):
        closes[10 + offset] = 14.10
    bars = pd.DataFrame(
        {
            "Open": closes,
            "High": closes * 1.01,
            "Low": closes * 0.99,
            "Close": closes,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )
    cup_bottom_date = bars.index[10].date()
    passes, penalty = _is_rounded_cup(
        bars,
        cup_bottom_date,
        cup_bottom_price,
        marginal_zone_pct=2.0,
    )
    assert passes is True
    assert penalty == pytest.approx(0.0)


def test_cwh_rounded_vs_v_test_2_bars_rejects_as_v_shape() -> None:
    """Per spec section 10.7 LOCK: <= 2 bars within marginal zone in
    cup_bottom_date +/- 10-day window -> HARD FAIL (V-shape; penalty
    contribution = +inf).
    """
    n = 21
    idx = pd.DatetimeIndex(
        [pd.Timestamp(date(2025, 12, 5)) + pd.Timedelta(days=i)
         for i in range(n)]
    )
    cup_bottom_price = 14.00
    closes = np.full(n, 18.00, dtype=float)
    # Only 2 bars within 2% of cup_bottom (low <= 14.28).
    closes[9] = 14.10
    closes[11] = 14.20
    bars = pd.DataFrame(
        {
            "Open": closes,
            "High": closes * 1.01,
            "Low": closes * 0.99,
            "Close": closes,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )
    cup_bottom_date = bars.index[10].date()
    passes, penalty = _is_rounded_cup(
        bars,
        cup_bottom_date,
        cup_bottom_price,
        marginal_zone_pct=2.0,
    )
    assert passes is False
    assert penalty == float("inf")


def test_cwh_rounded_vs_v_test_3_4_bars_marginal_zone_applies_penalty_0_10() -> None:
    """Per spec section 10.7 LOCK: 3-4 bars within marginal zone in
    cup_bottom_date +/- 10-day window -> MARGINAL (rounded enough; 0.10
    penalty subtracted from geometric_score).
    """
    n = 21
    idx = pd.DatetimeIndex(
        [pd.Timestamp(date(2025, 12, 5)) + pd.Timedelta(days=i)
         for i in range(n)]
    )
    cup_bottom_price = 14.00
    closes = np.full(n, 18.00, dtype=float)
    # 3 bars within 2% of cup_bottom -> MARGINAL.
    closes[9] = 14.10
    closes[10] = 14.05
    closes[11] = 14.20
    bars = pd.DataFrame(
        {
            "Open": closes,
            "High": closes * 1.01,
            "Low": closes * 0.99,
            "Close": closes,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )
    cup_bottom_date = bars.index[10].date()
    passes, penalty = _is_rounded_cup(
        bars,
        cup_bottom_date,
        cup_bottom_price,
        marginal_zone_pct=2.0,
    )
    assert passes is True
    assert penalty == pytest.approx(0.10)

    # Verify the 4-bar case also lands in MARGINAL.
    closes_4 = closes.copy()
    closes_4[8] = 14.15
    bars_4 = bars.copy()
    bars_4["Close"] = closes_4
    bars_4["Low"] = closes_4 * 0.99
    bars_4["High"] = closes_4 * 1.01
    bars_4["Open"] = closes_4
    passes_4, penalty_4 = _is_rounded_cup(
        bars_4,
        cup_bottom_date,
        cup_bottom_price,
        marginal_zone_pct=2.0,
    )
    assert passes_4 is True
    assert penalty_4 == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# Hard-gate criterion #1 + dataclass shape tests
# ---------------------------------------------------------------------------


def test_cwh_fails_criterion_1_stage_not_2_returns_geometric_score_0_0() -> None:
    """Per spec section 5.4 criterion #1: Stage 2 is a HARD GATE.
    Non-Stage-2 -> geometric_score == 0.0 regardless of other criteria.
    """
    bars = _bars_passing_all_criteria_xyz()
    window = _candidate_window(bars, anchor_offset=70)
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE evaluation_runs ("
        "id INTEGER PRIMARY KEY, "
        "action_session_date TEXT, "
        "run_ts TEXT)"
    )
    conn.execute(
        "CREATE TABLE candidates ("
        "id INTEGER PRIMARY KEY, "
        "ticker TEXT, "
        "evaluation_run_id INTEGER)"
    )
    conn.execute(
        "CREATE TABLE candidate_criteria ("
        "candidate_id INTEGER, "
        "layer TEXT, "
        "result TEXT)"
    )
    conn.commit()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.geometric_score == pytest.approx(0.0)
    assert evidence.criteria_pass["criterion_1"] is False


def test_cwh_structural_evidence_dataclass_shape() -> None:
    """CupWithHandleEvidence is a frozen dataclass with __post_init__
    runtime validation against allowed Literal values (per L7).
    """
    bars = _bars_passing_all_criteria_xyz()
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    evidence = detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    # Frozen: cannot mutate attributes.
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.geometric_score = 0.5  # type: ignore[misc]
    # __post_init__ rejects invalid stage literal.
    with pytest.raises(ValueError):
        CupWithHandleEvidence(
            stage="bogus",  # type: ignore[arg-type]
            cup_left_edge_price=20.0,
            cup_left_edge_date=date(2025, 11, 1),
            cup_right_edge_price=19.5,
            cup_right_edge_date=date(2026, 2, 15),
            cup_bottom_price=14.0,
            cup_bottom_date=date(2025, 12, 15),
            cup_depth_pct=30.0,
            cup_duration_days=106,
            cup_right_edge_pct_of_left_edge=97.5,
            handle_high_price=19.5,
            handle_low_price=18.0,
            handle_start_date=date(2026, 2, 15),
            handle_end_date=date(2026, 2, 23),
            handle_depth_pct=7.7,
            handle_duration_days=8,
            handle_low_vs_cup_midpoint_pct=5.88,
            handle_volume_vs_cup_volume_pct=80.0,
            pivot_price=19.55,
            pivot_within_cup_right_edge_pct=0.26,
            rounded_cup_passes=True,
            rounded_cup_penalty=0.0,
            rounded_cup_bars_in_marginal_zone=6,
            criteria_pass={f"criterion_{i}": True for i in range(1, 9)},
            geometric_score=1.0,
        )
    # __post_init__ rejects geometric_score outside [0.0, 1.0].
    with pytest.raises(ValueError):
        CupWithHandleEvidence(
            stage="stage_2",
            cup_left_edge_price=20.0,
            cup_left_edge_date=date(2025, 11, 1),
            cup_right_edge_price=19.5,
            cup_right_edge_date=date(2026, 2, 15),
            cup_bottom_price=14.0,
            cup_bottom_date=date(2025, 12, 15),
            cup_depth_pct=30.0,
            cup_duration_days=106,
            cup_right_edge_pct_of_left_edge=97.5,
            handle_high_price=19.5,
            handle_low_price=18.0,
            handle_start_date=date(2026, 2, 15),
            handle_end_date=date(2026, 2, 23),
            handle_depth_pct=7.7,
            handle_duration_days=8,
            handle_low_vs_cup_midpoint_pct=5.88,
            handle_volume_vs_cup_volume_pct=80.0,
            pivot_price=19.55,
            pivot_within_cup_right_edge_pct=0.26,
            rounded_cup_passes=True,
            rounded_cup_penalty=0.0,
            rounded_cup_bars_in_marginal_zone=6,
            criteria_pass={f"criterion_{i}": True for i in range(1, 9)},
            geometric_score=1.5,
        )
    # __post_init__ rejects missing criteria_pass keys.
    with pytest.raises(ValueError):
        CupWithHandleEvidence(
            stage="stage_2",
            cup_left_edge_price=20.0,
            cup_left_edge_date=date(2025, 11, 1),
            cup_right_edge_price=19.5,
            cup_right_edge_date=date(2026, 2, 15),
            cup_bottom_price=14.0,
            cup_bottom_date=date(2025, 12, 15),
            cup_depth_pct=30.0,
            cup_duration_days=106,
            cup_right_edge_pct_of_left_edge=97.5,
            handle_high_price=19.5,
            handle_low_price=18.0,
            handle_start_date=date(2026, 2, 15),
            handle_end_date=date(2026, 2, 23),
            handle_depth_pct=7.7,
            handle_duration_days=8,
            handle_low_vs_cup_midpoint_pct=5.88,
            handle_volume_vs_cup_volume_pct=80.0,
            pivot_price=19.55,
            pivot_within_cup_right_edge_pct=0.26,
            rounded_cup_passes=True,
            rounded_cup_penalty=0.0,
            rounded_cup_bars_in_marginal_zone=6,
            criteria_pass={f"criterion_{i}": True for i in range(1, 8)},
            geometric_score=1.0,
        )


def test_cwh_detector_writes_zero_db_rows() -> None:
    """LOCK L2: detect_cup_with_handle MUST NOT write to the DB. The
    conn is read-only for ``current_stage``.
    """
    bars = _bars_passing_all_criteria_xyz()
    window = _candidate_window(bars, anchor_offset=70)
    conn = _stage_2_conn()
    # Snapshot table contents BEFORE detection.
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    table_names = sorted(r[0] for r in cur.fetchall())
    pre_counts = {}
    for t in table_names:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        pre_counts[t] = cur.fetchone()[0]
    detect_cup_with_handle(
        bars,
        window,
        conn=conn,
        ticker="XYZ",
        asof_date=bars.index[-1].date(),
    )
    # Assert post-detection counts unchanged.
    for t in table_names:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        assert cur.fetchone()[0] == pre_counts[t], (
            f"detect_cup_with_handle modified table {t}"
        )
