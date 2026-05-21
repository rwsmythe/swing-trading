"""Phase 13 T2.SB3 T-A.3.2 - discriminating tests for VCP detector.

Per plan section G.4 T-A.3.2 Step 1: 12+ failing tests covering spec
section 5.2 (8 criteria) + section 10.1 (CVGI worked example) +
section 10.6 (tolerance-semantics LOCK; 28% boundary = 30% - 2%).

LOCKs honored:
- L1 verbatim spec criteria + tolerance values.
- L2 ZERO DB writes inside detector.
- L7 frozen dataclasses with ``__post_init__`` runtime validation.
- L5 ASCII-only.
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing.patterns.foundation import CandidateWindow
from swing.patterns.vcp import VCPEvidence, detect_vcp

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _bars_from_segments(
    segments: list[tuple[float, float, int]],
    start: date,
    volume_per_segment: list[int] | None = None,
) -> pd.DataFrame:
    """Build OHLCV bars by linearly interpolating across price segments.

    Each segment is ``(start_close, end_close, num_bars)``; consecutive
    segments share the last close of the prior segment.

    H/L/O are derived to satisfy ``L < Close < H`` (no degenerate
    H==L==Close shortcuts).
    """
    closes: list[float] = []
    for seg_start, seg_end, n in segments:
        if n < 1:
            raise ValueError("segment n must be >= 1")
        if not closes:
            xs = np.linspace(seg_start, seg_end, n)
            closes.extend(xs.tolist())
        else:
            # Skip first interp point to avoid duplicating endpoint.
            xs = np.linspace(seg_start, seg_end, n + 1)[1:]
            closes.extend(xs.tolist())
    n_total = len(closes)
    idx = pd.DatetimeIndex(
        [pd.Timestamp(start) + pd.Timedelta(days=i) for i in range(n_total)]
    )
    closes_arr = np.array(closes, dtype=float)
    # Synthetic OHLC with ~0.5% intrabar wiggle to honor H > Close > L.
    highs = closes_arr * 1.005
    lows = closes_arr * 0.995
    opens = closes_arr
    if volume_per_segment is None:
        volumes = [1_000_000] * n_total
    else:
        volumes = []
        cursor = 0
        for (_, _, n), vol in zip(segments, volume_per_segment, strict=True):
            count = n if cursor == 0 else n
            volumes.extend([vol] * count)
            cursor += count
        # In case the volume list doesn't line up with closes (skip-first
        # interp shift), pad with last volume.
        if len(volumes) < n_total:
            volumes.extend([volumes[-1]] * (n_total - len(volumes)))
        volumes = volumes[:n_total]
    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes_arr,
            "Volume": np.array(volumes, dtype=float),
        },
        index=idx,
    )


def _bars_passing_all_criteria(start: date = date(2026, 1, 5)) -> pd.DataFrame:
    """Construct bars that satisfy all 7 hard-or-soft VCP criteria per
    section 10.1 CVGI hypothetical.

    Construction:
    - Prior uptrend: 3.50 -> 5.50 over ~57 days (~8.5 weeks, ~57% gain).
    - 3 contractions with strict-decreasing depths 22% / 12% / 5.5%
      (peaks at 5.50, 5.42, 5.34; troughs at 4.29, 4.77, 5.05).
    - Volume declines through contractions.
    - Total base duration 32 days.
    - Pivot at 5.30 within 1% of base_top 5.34 (5.30 / 5.34 ~= 0.992).
    """
    # Construct prior uptrend leg + base contractions.
    # Pre-prior bars: filler to give the detector enough history for the
    # uptrend lookback (60+ bars before base start).
    segments = [
        (3.40, 3.50, 5),    # filler pre-uptrend
        (3.50, 5.50, 55),   # prior uptrend over ~55 days (~7.8 weeks)
        # Base starts here (high = 5.50). 3 contractions follow.
        (5.50, 4.29, 8),    # C1: 22% depth, 8 days; peak 5.50, trough 4.29
        (4.29, 5.42, 5),    # C1 rally to next peak 5.42
        (5.42, 4.77, 9),    # C2: ~12% depth (5.42 -> 4.77), 9 days
        (4.77, 5.34, 4),    # rally to peak 5.34 (base_top)
        (5.34, 5.05, 7),    # C3: ~5.4% depth, 7 days
        (5.05, 5.30, 3),    # final rally to pivot 5.30 (within 0.75% of 5.34)
    ]
    bars = _bars_from_segments(segments, start=start)
    # Tag volume per phase: filler / uptrend = baseline 1M; contractions
    # decline (1.5M -> 1.1M -> 0.75M); rallies = baseline.
    n = len(bars)
    vols = np.full(n, 1_000_000.0)
    # Indices of contraction segments (post-uptrend): roughly index 60..68
    # for C1, index 73..81 for C2, index 86..92 for C3.
    # Recompute index ranges precisely from segments.
    idx_cursor = 0
    seg_indices: list[tuple[int, int]] = []
    for i, (_, _, count) in enumerate(segments):
        if i == 0:
            seg_indices.append((0, count - 1))
            idx_cursor = count - 1
        else:
            seg_indices.append((idx_cursor + 1, idx_cursor + count))
            idx_cursor += count
    # Contraction segments (downswings): segments 2, 4, 6 (0-indexed).
    c1_lo, c1_hi = seg_indices[2]
    c2_lo, c2_hi = seg_indices[4]
    c3_lo, c3_hi = seg_indices[6]
    vols[c1_lo : c1_hi + 1] = 1_500_000.0
    vols[c2_lo : c2_hi + 1] = 1_100_000.0
    vols[c3_lo : c3_hi + 1] = 750_000.0
    bars["Volume"] = vols
    return bars


def _candidate_window(
    bars: pd.DataFrame,
    *,
    anchor_offset: int,
    ticker: str = "CVGI",
    reason_prefix: str = "zigzag_pivot",
) -> CandidateWindow:
    """Build a CandidateWindow whose anchor is the bar at ``anchor_offset``.

    For ``zigzag_pivot`` mode, anchor_date == base start (no backward-slice
    needed). For ``ma_crossover`` or ``high_low_breakout``, the detector
    backward-slices.
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


def _passing_window(bars: pd.DataFrame) -> CandidateWindow:
    # Base starts at index 60 (end of uptrend segment per the construction).
    return _candidate_window(bars, anchor_offset=60)


def _stage_2_conn() -> sqlite3.Connection:
    """In-memory SQLite holding a Stage-2 candidate row for ticker CVGI."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE evaluation_runs ("
                 "id INTEGER PRIMARY KEY, "
                 "action_session_date TEXT, "
                 "run_ts TEXT)")
    conn.execute("CREATE TABLE candidates ("
                 "id INTEGER PRIMARY KEY, "
                 "ticker TEXT, "
                 "evaluation_run_id INTEGER)")
    conn.execute("CREATE TABLE candidate_criteria ("
                 "candidate_id INTEGER, "
                 "layer TEXT, "
                 "result TEXT)")
    conn.execute(
        "INSERT INTO evaluation_runs (id, action_session_date, run_ts) "
        "VALUES (1, '2026-01-05', '2026-01-05T16:00:00Z')"
    )
    conn.execute(
        "INSERT INTO candidates (id, ticker, evaluation_run_id) "
        "VALUES (1, 'CVGI', 1)"
    )
    # 8 TT passes for Stage 2.
    for _tt in range(8):
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, layer, result) "
            "VALUES (1, 'trend_template', 'pass')"
        )
    conn.commit()
    return conn


def _not_stage_2_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE evaluation_runs ("
                 "id INTEGER PRIMARY KEY, "
                 "action_session_date TEXT, "
                 "run_ts TEXT)")
    conn.execute("CREATE TABLE candidates ("
                 "id INTEGER PRIMARY KEY, "
                 "ticker TEXT, "
                 "evaluation_run_id INTEGER)")
    conn.execute("CREATE TABLE candidate_criteria ("
                 "candidate_id INTEGER, "
                 "layer TEXT, "
                 "result TEXT)")
    # Empty: current_stage returns 'undefined'.
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_vcp_passes_all_criteria_returns_geometric_score_1_0() -> None:
    """Per spec section 10.1 CVGI hypothetical: 7/7 hard + soft criteria
    pass; geometric_score == 1.0.
    """
    bars = _bars_passing_all_criteria()
    window = _passing_window(bars)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    assert isinstance(evidence, VCPEvidence)
    assert evidence.geometric_score == pytest.approx(1.0)
    assert evidence.criteria_pass["criterion_1"] is True
    assert evidence.criteria_pass["criterion_2"] is True
    assert evidence.criteria_pass["criterion_3"] is True
    assert evidence.criteria_pass["criterion_4"] is True
    assert evidence.criteria_pass["criterion_5"] is True
    assert evidence.criteria_pass["criterion_6"] is True
    assert evidence.criteria_pass["criterion_7"] is True


def test_vcp_fails_criterion_1_stage_not_2_returns_geometric_score_0_0() -> None:
    """Per spec section 5.2 criterion #1: Stage 2 is a HARD GATE.
    Non-Stage-2 -> geometric_score == 0.0 regardless of other criteria.
    """
    bars = _bars_passing_all_criteria()
    window = _passing_window(bars)
    conn = _not_stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.geometric_score == pytest.approx(0.0)
    assert evidence.criteria_pass["criterion_1"] is False


def test_vcp_fails_criterion_2_uptrend_below_28pct_with_tolerance_rejects() -> None:
    """Per spec section 10.6 LOCK: tolerance band +/- 2% on the 30% bound.
    Relaxed threshold = 28%. An uptrend of 27.9% (just below 28%) FAILS.
    """
    # Construct a base where prior uptrend is only 27% (3.50 -> 4.445).
    segments = [
        (3.40, 3.50, 5),
        (3.50, 4.445, 55),   # 27% uptrend; below 28% relaxed threshold
        (4.445, 3.467, 8),   # C1: 22% depth
        (3.467, 4.380, 5),
        (4.380, 3.854, 9),   # C2: 12% depth
        (3.854, 4.316, 4),
        (4.316, 4.082, 7),   # C3: 5.4% depth
        (4.082, 4.290, 3),
    ]
    bars = _bars_from_segments(segments, start=date(2026, 1, 5))
    # Volume tag: contractions decline.
    n = len(bars)
    vols = np.full(n, 1_000_000.0)
    bars["Volume"] = vols
    window = _candidate_window(bars, anchor_offset=60)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_2"] is False


def test_vcp_passes_criterion_2_uptrend_at_28pct_within_tolerance_band() -> None:
    """Per spec section 10.6 LOCK: 28% == 30% - 2% relaxed threshold.
    Boundary case MUST pass.
    """
    # 28% uptrend exactly: 3.50 -> 4.48.
    segments = [
        (3.40, 3.50, 5),
        (3.50, 4.48, 55),    # 28% uptrend EXACT
        (4.48, 3.495, 8),    # C1: 22% depth
        (3.495, 4.414, 5),
        (4.414, 3.884, 9),   # C2: 12% depth
        (3.884, 4.350, 4),
        (4.350, 4.116, 7),   # C3: 5.4% depth
        (4.116, 4.325, 3),
    ]
    bars = _bars_from_segments(segments, start=date(2026, 1, 5))
    n = len(bars)
    vols = np.full(n, 1_000_000.0)
    bars["Volume"] = vols
    window = _candidate_window(bars, anchor_offset=60)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_2"] is True


def test_vcp_fails_criterion_3_non_monotonic_contractions() -> None:
    """Per spec section 5.2 criterion #3: contraction depths must
    monotonically decrease. A non-monotonic sequence (e.g., 22% -> 5% -> 12%)
    FAILS even though all depths are within criterion #4 bounds.
    """
    # Construct contractions with depths 22%, 5%, 12% - non-monotonic.
    segments = [
        (3.40, 3.50, 5),
        (3.50, 5.50, 55),
        (5.50, 4.29, 8),     # C1: 22%
        (4.29, 5.42, 5),
        (5.42, 5.15, 9),     # C2: 5% (TIGHTER than C3 below; out of order)
        (5.15, 5.34, 4),
        (5.34, 4.706, 7),    # C3: 12% (BIGGER than C2; non-monotonic)
        (4.706, 5.30, 3),
    ]
    bars = _bars_from_segments(segments, start=date(2026, 1, 5))
    n = len(bars)
    vols = np.full(n, 1_000_000.0)
    bars["Volume"] = vols
    window = _candidate_window(bars, anchor_offset=60)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_3"] is False


def test_vcp_passes_criterion_3_with_0_5pct_tolerance_on_monotonicity() -> None:
    """Per spec section 5.2 criterion #3 + dispatch brief: tolerance is
    +/- 0.5 percentage points on the monotonic-strict bound. A sequence
    22% -> 11% -> 11.4% passes (11.4 - 11 = 0.4 < 0.5pp tolerance).
    """
    # C2 = 11%, C3 = 11.4% (next depth exceeds prior by 0.4pp, inside the
    # 0.5pp tolerance band).
    segments = [
        (3.40, 3.50, 5),
        (3.50, 5.50, 55),
        (5.50, 4.29, 8),     # C1: 22%
        (4.29, 5.42, 5),
        (5.42, 4.824, 9),    # C2: 11%
        (4.824, 5.34, 4),
        (5.34, 4.732, 7),    # C3: 11.4% (slightly above C2; in tolerance)
        (4.732, 5.30, 3),
    ]
    bars = _bars_from_segments(segments, start=date(2026, 1, 5))
    n = len(bars)
    vols = np.full(n, 1_000_000.0)
    bars["Volume"] = vols
    window = _candidate_window(bars, anchor_offset=60)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_3"] is True


def test_vcp_fails_criterion_4_t1_depth_below_10pct() -> None:
    """Per spec section 5.2 criterion #4: T1 depth in [10%, 35%]. T1 = 8%
    is below the lower bound -> FAILS.
    """
    # T1 = 8%, T2 = 5%, T3 = 3% (all monotonic but T1 below 10% bound).
    segments = [
        (3.40, 3.50, 5),
        (3.50, 5.50, 55),
        (5.50, 5.06, 8),     # C1: 8% depth (below 10% lower bound)
        (5.06, 5.42, 5),
        (5.42, 5.149, 9),    # C2: 5%
        (5.149, 5.34, 4),
        (5.34, 5.18, 7),     # C3: 3%
        (5.18, 5.30, 3),
    ]
    bars = _bars_from_segments(segments, start=date(2026, 1, 5))
    n = len(bars)
    vols = np.full(n, 1_000_000.0)
    bars["Volume"] = vols
    window = _candidate_window(bars, anchor_offset=60)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_4"] is False


def test_vcp_fails_criterion_5_volume_declining_violation() -> None:
    """Per spec section 5.2 criterion #5: volume MUST decline across
    contractions. Volumes 1M -> 1.5M -> 0.75M violate (C2 > C1).
    """
    bars = _bars_passing_all_criteria()
    # Override volumes to break the decline: make C2 larger than C1.
    # Segment indices for the 8-segment construction.
    segments = [
        (3.40, 3.50, 5),
        (3.50, 5.50, 55),
        (5.50, 4.29, 8),
        (4.29, 5.42, 5),
        (5.42, 4.77, 9),
        (4.77, 5.34, 4),
        (5.34, 5.05, 7),
        (5.05, 5.30, 3),
    ]
    n_total = len(bars)
    vols = np.full(n_total, 1_000_000.0)
    idx_cursor = 0
    seg_indices: list[tuple[int, int]] = []
    for i, (_, _, count) in enumerate(segments):
        if i == 0:
            seg_indices.append((0, count - 1))
            idx_cursor = count - 1
        else:
            seg_indices.append((idx_cursor + 1, idx_cursor + count))
            idx_cursor += count
    c1_lo, c1_hi = seg_indices[2]
    c2_lo, c2_hi = seg_indices[4]
    c3_lo, c3_hi = seg_indices[6]
    vols[c1_lo : c1_hi + 1] = 1_000_000.0
    vols[c2_lo : c2_hi + 1] = 1_500_000.0   # VIOLATION: > C1
    vols[c3_lo : c3_hi + 1] = 750_000.0
    bars["Volume"] = vols
    window = _candidate_window(bars, anchor_offset=60)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_5"] is False


def test_vcp_fails_criterion_6_duration_outside_3_12_weeks() -> None:
    """Per spec section 5.2 criterion #6: base duration in [21, 84] days
    (3-12 weeks). A 15-day base (< 21 days) FAILS.
    """
    # Compress the base to 15 days total: 3 contractions of (5, 4, 3) days
    # plus rallies (1, 1, 1).
    segments = [
        (3.40, 3.50, 5),
        (3.50, 5.50, 55),
        (5.50, 4.29, 5),      # C1
        (4.29, 5.42, 1),
        (5.42, 4.77, 4),      # C2
        (4.77, 5.34, 1),
        (5.34, 5.05, 3),      # C3
        (5.05, 5.30, 1),
    ]
    bars = _bars_from_segments(segments, start=date(2026, 1, 5))
    n = len(bars)
    vols = np.full(n, 1_000_000.0)
    bars["Volume"] = vols
    window = _candidate_window(bars, anchor_offset=60)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_6"] is False


def test_vcp_passes_criterion_7_pivot_within_1pct_of_base_top() -> None:
    """Per spec section 5.2 criterion #7: pivot must be within 1% of
    base_top (in [0.99, 1.01] ratio). The all-pass fixture has pivot
    5.30 / base_top 5.34 = 0.9925 -> PASSES.
    """
    bars = _bars_passing_all_criteria()
    window = _passing_window(bars)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_7"] is True
    ratio = evidence.pivot_price / evidence.base_top_price
    assert 0.985 <= ratio <= 1.015   # tolerance 0.5%; passing fixture is 0.992


def test_vcp_optional_criterion_8_breakout_observed_increments_evidence() -> None:
    """Per spec section 5.2 criterion #8: optional; breakout volume >= 1.40x
    50d avg sets ``breakout_observed=True``. The all-pass fixture does
    NOT include a breakout bar; absence of breakout MUST NOT zero the
    geometric_score (per CVGI worked example, score is still 1.0).
    """
    bars = _bars_passing_all_criteria()
    window = _passing_window(bars)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    # Without breakout bar: observed False; score unaffected by #8 (optional).
    assert evidence.breakout_observed is False
    assert evidence.geometric_score == pytest.approx(1.0)


def test_vcp_structural_evidence_dataclass_shape_correctness() -> None:
    """VCPEvidence is a frozen dataclass with __post_init__ runtime
    validation against allowed Literal values (per L7).
    """
    # Frozen: cannot mutate attributes.
    bars = _bars_passing_all_criteria()
    window = _passing_window(bars)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.geometric_score = 0.5  # type: ignore[misc]
    # __post_init__ rejects invalid stage literal.
    with pytest.raises(ValueError):
        VCPEvidence(
            stage="bogus",  # type: ignore[arg-type]
            prior_uptrend_pct=30.0,
            prior_uptrend_weeks=8,
            base_start_date=date(2026, 1, 1),
            base_end_date=date(2026, 2, 1),
            contractions=tuple(),
            pivot_price=5.30,
            base_top_price=5.34,
            pivot_within_top_pct=0.75,
            volume_decline_passes=True,
            breakout_observed=False,
            breakout_volume_ratio=None,
            criteria_pass={f"criterion_{i}": True for i in range(1, 9)},
            geometric_score=1.0,
        )
    # __post_init__ rejects geometric_score outside [0.0, 1.0].
    with pytest.raises(ValueError):
        VCPEvidence(
            stage="stage_2",
            prior_uptrend_pct=30.0,
            prior_uptrend_weeks=8,
            base_start_date=date(2026, 1, 1),
            base_end_date=date(2026, 2, 1),
            contractions=tuple(),
            pivot_price=5.30,
            base_top_price=5.34,
            pivot_within_top_pct=0.75,
            volume_decline_passes=True,
            breakout_observed=False,
            breakout_volume_ratio=None,
            criteria_pass={f"criterion_{i}": True for i in range(1, 9)},
            geometric_score=1.5,
        )
    # criteria_pass must contain all 8 keys.
    with pytest.raises(ValueError):
        VCPEvidence(
            stage="stage_2",
            prior_uptrend_pct=30.0,
            prior_uptrend_weeks=8,
            base_start_date=date(2026, 1, 1),
            base_end_date=date(2026, 2, 1),
            contractions=tuple(),
            pivot_price=5.30,
            base_top_price=5.34,
            pivot_within_top_pct=0.75,
            volume_decline_passes=True,
            breakout_observed=False,
            breakout_volume_ratio=None,
            criteria_pass={"criterion_1": True},
            geometric_score=1.0,
        )


def test_vcp_evidence_to_json_round_trips() -> None:
    """VCPEvidence -> dataclasses.asdict + json.dumps -> json.loads
    round-trips losslessly (per recon section 8 production-shape JSON
    encoding contract).
    """
    bars = _bars_passing_all_criteria()
    window = _passing_window(bars)
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    payload = json.dumps(dataclasses.asdict(evidence), default=str)
    decoded = json.loads(payload)
    assert decoded["stage"] == evidence.stage
    assert decoded["geometric_score"] == pytest.approx(evidence.geometric_score)
    assert decoded["criteria_pass"]["criterion_1"] is True
    assert decoded["base_top_price"] == pytest.approx(evidence.base_top_price)
    assert decoded["pivot_price"] == pytest.approx(evidence.pivot_price)
    # Contractions list shape: list of dicts with depth_pct + duration_days.
    assert isinstance(decoded["contractions"], list)
    assert len(decoded["contractions"]) == len(evidence.contractions)
    assert decoded["contractions"][0]["depth_pct"] == pytest.approx(
        evidence.contractions[0].depth_pct
    )


def test_vcp_rejects_bars_with_nan() -> None:
    """The shared NaN sanitizer at swing/patterns/_sanitize.py rejects
    bars with NaN in any OHLCV column; detect_vcp inherits this
    discipline.
    """
    bars = _bars_passing_all_criteria()
    bars.iloc[10, bars.columns.get_loc("Close")] = float("nan")
    window = _passing_window(bars)
    conn = _stage_2_conn()
    with pytest.raises(ValueError, match="NaN"):
        detect_vcp(
            bars,
            window,
            conn=conn,
            ticker="CVGI",
            asof_date=bars.index[-1].date(),
        )


def test_vcp_no_conn_auto_fails_criterion_1() -> None:
    """Per spec section 5.2 criterion #1: Stage 2 is a HARD GATE; when
    conn is None (no stage lookup available), the detector treats Stage
    2 as unknown -> criterion #1 FAILS -> geometric_score == 0.0.
    """
    bars = _bars_passing_all_criteria()
    window = _passing_window(bars)
    evidence = detect_vcp(bars, window, conn=None)
    assert evidence.criteria_pass["criterion_1"] is False
    assert evidence.geometric_score == pytest.approx(0.0)


def test_vcp_ma_crossover_window_backward_slices_to_base_start() -> None:
    """Per recon section 5: for ``ma_crossover`` and ``high_low_breakout``
    candidate windows, ``anchor_date`` is the TRIGGER EVENT, NOT the base
    start. The detector backward-slices to find the base start (most-
    recent prior swing-LOW preceding the trigger by at least the uptrend
    requirement).
    """
    bars = _bars_passing_all_criteria()
    # ma_crossover anchor at last bar (end of construction). Detector must
    # backward-slice to find the base start at the post-uptrend low.
    anchor_idx = len(bars) - 1
    window = CandidateWindow(
        ticker="CVGI",
        timeframe="daily",
        start_date=bars.index[anchor_idx].date(),
        end_date=bars.index[-1].date(),
        anchor_date=bars.index[anchor_idx].date(),
        anchor_reason="ma_crossover:50_above_150_at_test",
    )
    conn = _stage_2_conn()
    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )
    # Detector backward-slices; base_start should be earlier than the
    # trigger event bar.
    assert evidence.base_start_date < bars.index[anchor_idx].date()
