"""Phase 13 T2.SB4 T-A.4.2 - discriminating tests for double_bottom_w detector.

Per dispatch brief Step 1 + plan section G.6 T-A.4.2: 12+ failing tests
covering spec section 5.6 (8 criteria + criterion #8 undercut bonus) +
section 10.5 worked example ($UVWX recovery; evidence geometric_score
reaches 1.10 with undercut bonus per section 5.8 evidence-vs-composite
cap distinction) + section 10.6 tolerance semantics.

LOCKs honored:
- L1: verbatim spec section 5.6 criteria + tolerance values + section
  10.5 worked example + section 5.8 evidence-vs-composite cap
  distinction (evidence reaches 1.10; composite caps at 1.0) + section
  10.6 LOCK (criterion #1 + #5 STRICT NONE; criterion #8 LOCK +0.10).
- L2: ZERO DB writes inside detector (current_stage is read-only).
- L7: frozen dataclass with __post_init__ runtime validation against
  explicit frozensets.
- L10: bar-clipping at detector entry; future-bar leak preempted.
- L5: ASCII-only.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing.patterns.double_bottom_w import (
    DoubleBottomWEvidence,
    detect_double_bottom_w,
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

    H/L derived around Close with ``noise_pct`` half-width. Volume is a
    flat 1_000_000 per bar unless ``volumes_per_bar`` is supplied.
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


def _bars_uvwx_dbw(
    start: date = date(2026, 1, 5),
    *,
    prior_peak: float = 26.67,
    trough_1: float = 20.00,
    # Spec section 10.5 narrative states 60% retracement with peak 26.67 /
    # trough_1 20.00; the literal arithmetic with center_peak 23.00 is
    # 45% retracement, which would FAIL criterion #3 (>= 50%). Spec
    # worked-example numerics are internally inconsistent. Resolution per
    # dispatch brief LOCK (spec section 10.5 binding): use center_peak
    # that DOES satisfy criterion #3 with the standard retracement
    # formula (center - trough_1) / (prior_peak - trough_1). Setting
    # center_peak = 24.00 yields exactly 60% retracement, matching the
    # spec narrative + producing all-criteria-pass per section 10.5.
    center_peak: float = 24.00,
    trough_2: float = 19.00,
    pre_peak_days: int = 8,
    peak_to_t1_days: int = 12,
    t1_to_center_days: int = 20,
    center_to_t2_days: int = 18,
    post_t2_pivot_days: int = 6,
    t1_volume: float = 1_000_000.0,
    t2_volume: float = 1_400_000.0,
    other_volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """Construct bars per spec section 10.5 worked example ($UVWX).

    Layout:
    - Pre-peak: 6 filler bars at prior_peak * 0.95 climbing to prior_peak.
    - Peak -> trough_1: down-swing over peak_to_t1_days.
    - Trough_1 -> center_peak: up-swing over t1_to_center_days.
    - Center_peak -> trough_2: down-swing over center_to_t2_days.
    - Trough_2 -> pivot: up-swing over post_t2_pivot_days, ending at
      center_peak (pivot == center_peak).

    Default values: 25% drawdown peak->trough_1 (26.67->20); 50%+
    retracement to center_peak; 5% undercut at trough_2; pivot at center_peak.

    Volume profile: trough_2 average > trough_1 average (shakeout signal).
    """
    segments: list[tuple[float, float, int]] = [
        (prior_peak * 0.95, prior_peak, pre_peak_days),  # climb to peak
        (prior_peak, trough_1, peak_to_t1_days),         # peak -> trough_1
        (trough_1, center_peak, t1_to_center_days),      # trough_1 -> center
        (center_peak, trough_2, center_to_t2_days),      # center -> trough_2
        (trough_2, center_peak, post_t2_pivot_days),     # trough_2 -> pivot
    ]
    n_total = (
        pre_peak_days
        + peak_to_t1_days
        + t1_to_center_days
        + center_to_t2_days
        + post_t2_pivot_days
    )
    # Volume profile: simple 5-segment ladder.
    volumes: list[float] = []
    # pre_peak
    volumes.extend([other_volume] * pre_peak_days)
    # peak -> trough_1 (trough_1 volume tracks the down-swing tail)
    volumes.extend([t1_volume] * peak_to_t1_days)
    # trough_1 -> center_peak
    volumes.extend([other_volume] * t1_to_center_days)
    # center -> trough_2 (trough_2 volume tracks down-swing tail; shakeout)
    volumes.extend([t2_volume] * center_to_t2_days)
    # trough_2 -> pivot
    volumes.extend([other_volume] * post_t2_pivot_days)
    assert len(volumes) == n_total, (len(volumes), n_total)
    bars = _bars_from_segments(
        segments,
        start=start,
        noise_pct=0.005,
        volumes_per_bar=volumes,
    )
    return bars


def _candidate_window_at_end(
    bars: pd.DataFrame,
    *,
    ticker: str = "UVWX",
    reason_prefix: str = "ma_crossover",
) -> CandidateWindow:
    """Build a CandidateWindow whose anchor_date is the last bar
    (the pivot at center_peak height after trough_2 recovery).

    Default reason_prefix is ``ma_crossover`` (TRIGGER EVENT semantic):
    the last bar IS the trigger event, not the inferred base START.
    For DBW the inferred base START is trough_1 (the first W trough);
    ``zigzag_pivot`` mode anchor_date MUST align with trough_1 per
    foundation.py:458-461 + Codex R1 Major #2 (DBW backward-slice
    enforces alignment for zigzag_pivot mode). Tests that want zigzag
    semantics use :func:`_candidate_window_at_trough_1_zigzag` below.
    """
    anchor_dt = bars.index[-1].date()
    return CandidateWindow(
        ticker=ticker,
        timeframe="daily",
        start_date=bars.index[0].date(),
        end_date=anchor_dt,
        anchor_date=anchor_dt,
        anchor_reason=f"{reason_prefix}:test_anchor",
    )


def _candidate_window_at_trough_1_zigzag(
    bars: pd.DataFrame,
    trough_1_date: date,
    *,
    ticker: str = "UVWX",
) -> CandidateWindow:
    """Build a zigzag_pivot CandidateWindow with anchor_date == trough_1.

    Per spec + foundation.py:458-461 zigzag_pivot mode anchor_date IS the
    inferred base START. For DBW the base start is trough_1 (the first
    W trough). DBW backward-slice enforces alignment between the sliced
    trough_1 and candidate_window.anchor_date in zigzag_pivot mode
    (+/- 1 calendar day tolerance per Codex R1 Major #2 fix).
    """
    return CandidateWindow(
        ticker=ticker,
        timeframe="daily",
        start_date=trough_1_date,
        end_date=bars.index[-1].date(),
        anchor_date=trough_1_date,
        anchor_reason="zigzag_pivot:test_anchor",
    )


def _stage_2_conn(ticker: str = "UVWX") -> sqlite3.Connection:
    """In-memory SQLite with Stage-2 candidate row for ticker."""
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
        "VALUES (1, '2026-01-05', '2026-01-05T16:00:00Z')"
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
# Tests
# ---------------------------------------------------------------------------


def test_dbw_passes_all_criteria_with_undercut_geometric_score_equals_1_10() -> None:
    """Per spec section 10.5 line 1325 worked example + section 5.8 line
    718 evidence-vs-composite cap distinction: $UVWX 8/8 criteria pass +
    undercut bonus +0.10 -> EVIDENCE geometric_score == 1.10 (NOT 1.0).
    The composite formula (60% geometric + 40% template) applies its own
    ``min(1.0, ...)`` cap downstream per section 5.8; the detector emits
    the un-clipped 1.10 at the evidence layer.

    Closes Codex R1 Major #1 — the initial dispatch brief was wrong about
    capping evidence at 1.0; per spec section 5.8 + section 10.5 the
    evidence layer caps at 1.10 and composite layer caps at 1.0.
    """
    bars = _bars_uvwx_dbw()
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars,
        window,
        conn=conn,
        ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert isinstance(evidence, DoubleBottomWEvidence)
    # Verify all 6 mandatory criteria pass (#7 is optional evidence-only).
    for k in (
        "criterion_1",
        "criterion_2",
        "criterion_3",
        "criterion_4",
        "criterion_5",
        "criterion_6",
    ):
        assert evidence.criteria_pass[k] is True, (
            f"Expected {k} pass; got criteria_pass={evidence.criteria_pass}; "
            f"trough_1={evidence.trough_1_price}; "
            f"trough_1_drawdown={evidence.trough_1_drawdown_pct}; "
            f"center_peak_retracement={evidence.center_peak_retracement_pct}; "
            f"trough_2={evidence.trough_2_price}; "
            f"undercut={evidence.undercut}"
        )
    # Undercut is true -> bonus applied.
    assert evidence.undercut is True
    # Section 10.5 LOCK: evidence geometric_score == 1.10 (NOT capped at
    # 1.0). The composite layer caps; evidence layer does not.
    assert evidence.geometric_score == pytest.approx(1.10)


def test_dbw_undercut_increments_geometric_score_by_0_10() -> None:
    """Per spec section 5.6 criterion #8 LOCK: undercut adds +0.10 to
    geometric_score. With one mandatory criterion deliberately failing
    (so base score is 5/6 ~0.833), undercut should bump to ~0.933.

    Engineering: hold #1..#5 pass + fail #6 (pivot mismatch) + undercut.
    Base score before bonus: 5/6 ~= 0.833. After bonus: ~0.933 (NOT capped).
    """
    # Pivot far above center_peak (criterion #6 fails).
    # Pivot is the last close in the candidate window.
    bars = _bars_uvwx_dbw(post_t2_pivot_days=6)
    # Mutate the very last bar's Close to be far above center_peak so
    # pivot/center_peak ratio is outside [0.985, 1.015].
    bars = bars.copy()
    bars.iloc[-1, bars.columns.get_loc("Close")] = 30.00
    bars.iloc[-1, bars.columns.get_loc("High")] = 30.15
    bars.iloc[-1, bars.columns.get_loc("Low")] = 29.85
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_6"] is False
    assert evidence.undercut is True
    # Base = 5/6; bonus 0.10 -> ~0.933.
    base = 5.0 / 6.0
    assert evidence.geometric_score == pytest.approx(base + 0.10, abs=1e-6)


def test_dbw_no_undercut_geometric_score_at_1_0_without_bonus() -> None:
    """Per spec section 5.6 criterion #8 LOCK: no undercut -> NO bonus.

    Engineering: trough_2 == trough_1 (no undercut; within +/-5% bound).
    All criteria pass; geometric_score == 1.0 (no bonus added).
    """
    bars = _bars_uvwx_dbw(trough_2=20.00)  # equal to trough_1
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    # No undercut.
    assert evidence.undercut is False
    # All mandatory criteria still pass.
    for k in (
        "criterion_1",
        "criterion_2",
        "criterion_3",
        "criterion_4",
        "criterion_5",
        "criterion_6",
    ):
        assert evidence.criteria_pass[k] is True, (
            f"Expected {k} pass; got criteria_pass={evidence.criteria_pass}"
        )
    # Base score = 1.0; no undercut -> no bonus added -> evidence
    # geometric_score == 1.0 (well below the 1.10 evidence cap per spec
    # section 5.8 evidence-vs-composite distinction).
    assert evidence.geometric_score == pytest.approx(1.0)


def test_dbw_fails_criterion_2_trough_1_drawdown_below_15pct() -> None:
    """Per spec section 5.6 criterion #2 + section 10.6 tolerance +/-1%:
    drawdown below 14% (relaxed bound) fails. Plant 10% drawdown.
    """
    # 10% drawdown: prior_peak 22.22, trough_1 20.00 -> drawdown 10%.
    bars = _bars_uvwx_dbw(prior_peak=22.22, trough_1=20.00)
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_2"] is False
    assert evidence.trough_1_drawdown_pct < 0.14


def test_dbw_fails_criterion_3_center_peak_retracement_below_50pct() -> None:
    """Per spec section 5.6 criterion #3 + section 10.6 tolerance +/-2%:
    retracement below 48% (relaxed bound) fails. Plant ~30% retracement.
    """
    # peak 26.67, trough_1 20.00, center_peak should be ~22.00 for 30%
    # retracement: (22 - 20) / (26.67 - 20) = 0.30.
    bars = _bars_uvwx_dbw(center_peak=22.00)
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_3"] is False
    assert evidence.center_peak_retracement_pct < 0.48


def test_dbw_fails_criterion_4_trough_2_outside_5pct_of_trough_1() -> None:
    """Per spec section 5.6 criterion #4 + section 10.6 tolerance +/-0.5%:
    trough_2 outside relaxed 5.5% band of trough_1 fails. Plant trough_2
    at 8% below trough_1 (-8%; outside 5.5% relaxed).
    """
    # trough_1 = 20.00; trough_2 at 18.40 (8% below). |t2 - t1|/t1 = 8%.
    bars = _bars_uvwx_dbw(trough_2=18.40)
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_4"] is False


def test_dbw_passes_criterion_4_with_3pct_undercut_within_5pct_bound() -> None:
    """Per spec section 5.6 criterion #4: 3% undercut (within +/-5% bound)
    PASSES. Trough_2 = 19.40 (3% below trough_1 20.00) -> undercut + pass.
    """
    bars = _bars_uvwx_dbw(trough_2=19.40)
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_4"] is True
    # Within 3% undercut -> undercut flag true.
    assert evidence.undercut is True


def test_dbw_fails_criterion_5_duration_outside_5_35d() -> None:
    """Per spec section 5.6 criterion #5: BOTH durations in [5, 35].
    Plant t1_to_center duration = 40 days (above 35 upper bound).
    """
    bars = _bars_uvwx_dbw(t1_to_center_days=40)
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_5"] is False
    # t1_to_center_days > 35.
    assert evidence.trough_1_to_center_duration_days > 35


def test_dbw_passes_criterion_6_pivot_within_1pct_center_peak() -> None:
    """Per spec section 5.6 criterion #6 + section 10.6 tolerance +/-0.5%:
    pivot/center_peak in [0.985, 1.015] passes. Default fixture closes
    pivot at center_peak height -> ratio 1.0.
    """
    bars = _bars_uvwx_dbw()
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_6"] is True
    ratio = evidence.pivot_price / evidence.center_peak_price
    assert 0.985 <= ratio <= 1.015


def test_dbw_optional_criterion_7_volume_rises_increments_evidence() -> None:
    """Per spec section 5.6 criterion #7 (OPTIONAL): trough_2 avg volume /
    trough_1 avg volume in [1.0, 2.0] -> criterion_7 evidence flag true.

    Spec LOCK: criterion #7 does NOT increment geometric_score; only
    criterion #8 (undercut bonus) increments score. Verify the evidence
    flag flips, and verify the score is unchanged whether c7 fires or not.
    """
    # Default: t2_volume 1.4M, t1_volume 1.0M -> ratio 1.4 (in [1.0, 2.0]).
    bars = _bars_uvwx_dbw()
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence_with_c7 = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence_with_c7.criteria_pass["criterion_7"] is True

    # Now plant t2_volume 0.5M (below 1.0x ratio -> criterion_7 false).
    bars_no_c7 = _bars_uvwx_dbw(t2_volume=500_000.0)
    window_no = _candidate_window_at_end(bars_no_c7)
    evidence_no_c7 = detect_double_bottom_w(
        bars_no_c7, window_no, conn=_stage_2_conn(), ticker="UVWX",
        asof_date=bars_no_c7.index[-1].date(),
    )
    assert evidence_no_c7.criteria_pass["criterion_7"] is False
    # Spec LOCK: criterion #7 does NOT increment geometric_score; both
    # variants pass all mandatory criteria + undercut -> identical score.
    assert evidence_with_c7.geometric_score == pytest.approx(
        evidence_no_c7.geometric_score
    )


def test_dbw_stage_4_to_stage_2_transition_satisfies_criterion_1() -> None:
    """Per spec section 5.6 criterion #1: Stage 2 (with or without recent
    Stage 4 history) satisfies the hard gate. Plant Stage 2 -> criterion_1
    passes regardless of recent_stage.

    Per dispatch brief: V1 current_stage() returns 'stage_2'/'undefined'
    only; recent_stage is recorded symbolically in evidence.
    """
    bars = _bars_uvwx_dbw()
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_1"] is True
    assert evidence.stage == "stage_2"


def test_dbw_structural_evidence_dataclass_shape() -> None:
    """Verify DoubleBottomWEvidence is a frozen dataclass with all
    required fields per dispatch brief + spec section 5.6 structural
    evidence shape (trough_1_* / center_peak_* / trough_2_* / undercut /
    pivot_* / geometric_score).
    """
    bars = _bars_uvwx_dbw()
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    # Frozen dataclass.
    assert dataclasses.is_dataclass(evidence)
    assert evidence.__dataclass_params__.frozen is True
    field_names = {f.name for f in dataclasses.fields(evidence)}
    required_fields = {
        "stage",
        "trough_1_date",
        "trough_1_price",
        "trough_1_drawdown_pct",
        "trough_1_avg_volume",
        "center_peak_date",
        "center_peak_price",
        "center_peak_retracement_pct",
        "trough_2_date",
        "trough_2_price",
        "trough_2_avg_volume",
        "undercut",
        "pivot_price",
        "trough_1_to_center_duration_days",
        "center_to_trough_2_duration_days",
        "criteria_pass",
        "geometric_score",
    }
    missing = required_fields - field_names
    assert not missing, f"Missing required fields: {missing}"
    # L7 LOCK: stage validator rejects invalid Literal value.
    valid_kwargs = {
        f.name: getattr(evidence, f.name) for f in dataclasses.fields(evidence)
    }
    valid_kwargs["stage"] = "not_a_valid_stage"
    with pytest.raises(ValueError, match="stage"):
        DoubleBottomWEvidence(**valid_kwargs)


def test_dbw_bar_clipping_future_bar_leak_rejected() -> None:
    """Per dispatch brief LOCK L10 + T2.SB3 forward-binding lesson #2:
    bars MUST be clipped to ``bars.index <= candidate_window.end_date``
    BEFORE anchor identification. Plant a future bar with LOWEST-LOW
    (DBW's swing-LOW anchor for trough_1) after window.end_date;
    detector must NOT use it as trough_1.
    """
    bars = _bars_uvwx_dbw()
    # Append a future bar with an EVEN LOWER trough beyond window.end_date.
    future_idx = bars.index[-1] + pd.Timedelta(days=1)
    future_bar = pd.DataFrame(
        {
            "Open": [10.00],
            "High": [10.50],
            "Low": [9.50],   # MUCH lower than any in-window low (~19.0)
            "Close": [10.00],
            "Volume": [3_000_000.0],
        },
        index=pd.DatetimeIndex([future_idx]),
    )
    bars_with_future = pd.concat([bars, future_bar])
    # Window end is the original last in-window date.
    window_end = bars.index[-1].date()
    window = CandidateWindow(
        ticker="UVWX",
        timeframe="daily",
        start_date=bars.index[0].date(),
        end_date=window_end,
        anchor_date=window_end,
        anchor_reason="zigzag_pivot:test_anchor",
    )
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars_with_future,
        window,
        conn=conn,
        ticker="UVWX",
        asof_date=window_end,
    )
    # Trough_1 + trough_2 + center_peak dates MUST be on or before window.end_date.
    assert evidence.trough_1_date <= window_end, (
        f"Bar-clip leak: trough_1_date {evidence.trough_1_date} > "
        f"window.end_date {window_end}"
    )
    assert evidence.trough_2_date <= window_end, (
        f"Bar-clip leak: trough_2_date {evidence.trough_2_date} > "
        f"window.end_date {window_end}"
    )
    assert evidence.center_peak_date <= window_end


def test_dbw_empty_bars_returns_zero_score() -> None:
    """Pre-empt empty-bars edge case per dispatch brief pre-Codex review
    anticipated flags. Empty bars -> zero-score evidence; no exception.
    """
    empty = pd.DataFrame(
        {
            "Open": [],
            "High": [],
            "Low": [],
            "Close": [],
            "Volume": [],
        },
        index=pd.DatetimeIndex([]),
    )
    window = CandidateWindow(
        ticker="UVWX",
        timeframe="daily",
        start_date=date(2026, 1, 5),
        end_date=date(2026, 2, 5),
        anchor_date=date(2026, 2, 5),
        anchor_reason="zigzag_pivot:test_anchor",
    )
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        empty,
        window,
        conn=conn,
        ticker="UVWX",
        asof_date=date(2026, 2, 5),
    )
    assert isinstance(evidence, DoubleBottomWEvidence)
    assert evidence.geometric_score == 0.0


def test_dbw_nan_at_entry_raises_via_sanitize_bars() -> None:
    """Pre-empt NaN-handling per dispatch brief pre-Codex review anticipated
    flags. sanitize_bars at entry raises ValueError on NaN.
    """
    bars = _bars_uvwx_dbw()
    bars = bars.copy()
    bars.iloc[5, bars.columns.get_loc("Close")] = np.nan
    window = _candidate_window_at_end(bars)
    conn = _stage_2_conn()
    with pytest.raises(ValueError, match="NaN|non-finite"):
        detect_double_bottom_w(
            bars, window, conn=conn, ticker="UVWX",
            asof_date=bars.index[-1].date(),
        )


def test_dbw_stage_2_gate_fails_without_conn_returns_zero_score() -> None:
    """Criterion #1 (Stage 2) is a hard gate. Without a conn, stage is
    undefined; criterion_1 fails; geometric_score = 0.0.
    """
    bars = _bars_uvwx_dbw()
    window = _candidate_window_at_end(bars)
    evidence = detect_double_bottom_w(bars, window)
    assert evidence.criteria_pass["criterion_1"] is False
    assert evidence.geometric_score == 0.0


def test_dbw_zigzag_pivot_anchor_aligned_with_trough_1_detects_w() -> None:
    """Codex R1 Major #2 (positive case): for zigzag_pivot mode the
    candidate_window.anchor_date IS the inferred base START (per
    foundation.py:458-461 + spec section 5.1.3 line 502). For DBW the
    base start is trough_1 (the first W trough). With anchor_date ==
    trough_1_date and reason_prefix='zigzag_pivot', the detector finds
    the W and emits all-criteria-pass evidence.

    This test pins the canonical correct usage of the zigzag_pivot
    contract for DBW. Discriminating test below
    (test_dbw_zigzag_pivot_anchor_misaligned_with_trough_1_rejects)
    plants the WRONG anchor under the same reason_prefix and asserts
    rejection.
    """
    bars = _bars_uvwx_dbw()
    trough_1_date = date(2026, 1, 24)  # from _bars_uvwx_dbw layout
    window = _candidate_window_at_trough_1_zigzag(bars, trough_1_date)
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.trough_1_date == trough_1_date
    # All 6 mandatory criteria pass + undercut bonus -> evidence 1.10.
    assert evidence.geometric_score == pytest.approx(1.10)


def test_dbw_zigzag_pivot_anchor_misaligned_with_trough_1_rejects() -> None:
    """Codex R1 Major #2 (discriminating case): when the candidate
    window's reason_prefix is 'zigzag_pivot' but the anchor_date does
    NOT align with the bars-derived trough_1_date (more than +/- 1
    calendar day away), the detector rejects the candidate W and
    returns zero-evidence. Without the alignment check the detector
    would have happily scored the W structure in the same bars against
    a window anchored elsewhere.

    Layout: $UVWX bars have trough_1 at 2026-01-24. We plant the
    anchor at 2026-02-10 (~17 days off; the center_peak vicinity).
    Pre-fix behavior: detector ignores anchor_date and finds the W ->
    geometric_score 1.10 (wrong). Post-fix behavior:
    _backward_slice_dbw_structure enforces anchor alignment -> returns
    None -> _build_zero_evidence with criterion_1=True only ->
    geometric_score 0.0.
    """
    bars = _bars_uvwx_dbw()
    # Misaligned anchor: 2026-02-10 is in the center_peak vicinity
    # (center_peak at 2026-02-13); 17 calendar days from trough_1.
    misaligned_anchor = date(2026, 2, 10)
    window = CandidateWindow(
        ticker="UVWX",
        timeframe="daily",
        start_date=misaligned_anchor,
        end_date=bars.index[-1].date(),
        anchor_date=misaligned_anchor,
        anchor_reason="zigzag_pivot:misaligned_test_anchor",
    )
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    # Backward-slice returns None due to alignment mismatch ->
    # _build_zero_evidence path; criterion_1 is True (Stage 2 passed)
    # but no W landmarks -> geometric_score 0.0.
    assert evidence.criteria_pass["criterion_1"] is True
    # All structural criteria fail because no W found.
    assert evidence.criteria_pass["criterion_2"] is False
    assert evidence.criteria_pass["criterion_4"] is False
    assert evidence.geometric_score == 0.0


def test_dbw_zigzag_pivot_anchor_within_1day_tolerance_detects_w() -> None:
    """Codex R1 Major #2 tolerance band: +/- 1 calendar day tolerance is
    granted for off-by-one numerical edge cases at zigzag pivot
    identification. Anchor 1 day off from trough_1 STILL passes the
    alignment check.
    """
    bars = _bars_uvwx_dbw()
    # trough_1 detected at 2026-01-24; plant anchor at 2026-01-25
    # (1 day later -> within +/- 1 tolerance).
    one_day_off_anchor = date(2026, 1, 25)
    window = CandidateWindow(
        ticker="UVWX",
        timeframe="daily",
        start_date=one_day_off_anchor,
        end_date=bars.index[-1].date(),
        anchor_date=one_day_off_anchor,
        anchor_reason="zigzag_pivot:within_tolerance_anchor",
    )
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.trough_1_date == date(2026, 1, 24)
    # Within tolerance -> W is found + all criteria pass.
    assert evidence.geometric_score == pytest.approx(1.10)


def test_dbw_non_zigzag_mode_skips_anchor_alignment_check() -> None:
    """Codex R1 Major #2 mode-aware enforcement: for non-zigzag_pivot
    modes (ma_crossover, high_low_breakout) the anchor_date is a
    TRIGGER EVENT (not a base start) per foundation.py:462-469. The
    alignment check MUST be skipped; the detector backward-slices freely
    from end_date.

    This test pins the asymmetry: same misaligned anchor that the
    zigzag_pivot test rejects is ACCEPTED under ma_crossover reason
    because the alignment contract only applies to zigzag_pivot.
    """
    bars = _bars_uvwx_dbw()
    # Same anchor as the misaligned-zigzag test but with ma_crossover
    # reason -> alignment skipped -> W is found.
    anchor_dt = date(2026, 2, 10)
    window = CandidateWindow(
        ticker="UVWX",
        timeframe="daily",
        start_date=anchor_dt,
        end_date=bars.index[-1].date(),
        anchor_date=anchor_dt,
        anchor_reason="ma_crossover:test_anchor",
    )
    conn = _stage_2_conn()
    evidence = detect_double_bottom_w(
        bars, window, conn=conn, ticker="UVWX",
        asof_date=bars.index[-1].date(),
    )
    # Backward-slice from end_date succeeds; W found; criteria pass.
    assert evidence.trough_1_date == date(2026, 1, 24)
    assert evidence.geometric_score == pytest.approx(1.10)
