"""Phase 13 T2.SB3 T-A.3.3 - discriminating tests for flat_base detector.

Per plan section G.4 T-A.3.3 Step 1: 9+ failing tests covering spec
section 5.3 (7 criteria + tolerance values) + section 10.2 (YOU worked
example + alternative-pass scenario) + section 10.6 (tolerance-semantics
LOCK; criterion #2 relaxed threshold = 20% - 2% = 18%).

LOCKs honored:
- L1 verbatim spec section 5.3 criteria + tolerance values.
- L2 ZERO DB writes inside detector.
- L7 frozen dataclass with __post_init__ runtime validation.
- L5 ASCII-only.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing.patterns.flat_base import FlatBaseEvidence, detect_flat_base
from swing.patterns.foundation import CandidateWindow

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _bars_from_segments(
    segments: list[tuple[float, float, int]],
    start: date,
    *,
    noise_pct: float = 0.005,
) -> pd.DataFrame:
    """Build OHLCV bars by linearly interpolating across price segments.

    H/L derived around Close with the requested ``noise_pct`` half-width
    (controls criterion #5 ATR; 0.005 -> 0.5% half-width = ~1% ATR which
    sits below the 2.5% bound).
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
    volumes = np.full(n_total, 1_000_000.0)
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


def _bars_passing_all_criteria_22pct(
    start: date = date(2026, 1, 5),
) -> pd.DataFrame:
    """Construct bars matching the spec section 10.2 ALTERNATIVE-PASS
    scenario: 22% prior uptrend, ~11.5% range, low slope, tight ATR,
    duration ~47 days (~6.7 weeks).

    Layout:
    - 5 filler bars at ~9.50 leading into the uptrend.
    - 36-day uptrend from 9.55 -> 11.65 (22% gain, ~5 weeks).
    - 47-day flat base spanning [10.55 close / 10.498 low,
      11.65 close / 11.708 high] -> width ~= 11.5% inside [3%, 12%]:
      - 11.65 stays at top 5 days
      - 11.65 -> 10.55 (10 days; visit range bottom)
      - 10.55 -> 11.65 (10 days)
      - 11.65 -> 10.60 (10 days; visit bottom-near)
      - 10.60 -> 11.62 (12 days; final pivot bar at 11.62)
    Pivot 11.62 close / range_top 11.708 (=11.65 close * 1.005 H) ~= 0.992
    inside [0.985, 1.015] tolerance band.
    Slope: balanced oscillation -> near zero (well below 0.005/wk).
    ATR: 0.5% half-width -> ~1% intrabar / mid ~11.10 ~= 0.009 << 0.025.
    Base START is index 41 (anchor target).
    """
    segments = [
        (9.45, 9.55, 5),       # 0..4 filler
        (9.55, 11.65, 36),     # 5..40 uptrend (22% gain over ~5 weeks)
        # Base spans index 41..87 (47 bars). Range close [10.55, 11.65]
        # (~10.4% close-to-close; with 0.5% H wiggle the H-L width is
        # ~11.5%, inside [3%, 12%]).
        (11.65, 11.65, 5),     # 41..45 hold near top (flat segment)
        (11.65, 10.55, 10),    # 46..55 visit range bottom
        (10.55, 11.65, 10),    # 56..65 back to top
        (11.65, 10.60, 10),    # 66..75 visit bottom-near
        (10.60, 11.62, 12),    # 76..87 final pivot bar at 11.62
    ]
    bars = _bars_from_segments(segments, start=start, noise_pct=0.005)
    return bars


def _candidate_window(
    bars: pd.DataFrame,
    *,
    anchor_offset: int,
    ticker: str = "YOU",
    reason_prefix: str = "zigzag_pivot",
) -> CandidateWindow:
    """Build a CandidateWindow whose anchor is the bar at anchor_offset."""
    anchor_dt = bars.index[anchor_offset].date()
    return CandidateWindow(
        ticker=ticker,
        timeframe="daily",
        start_date=anchor_dt,
        end_date=bars.index[-1].date(),
        anchor_date=anchor_dt,
        anchor_reason=f"{reason_prefix}:test_anchor",
    )


def _stage_2_conn(ticker: str = "YOU") -> sqlite3.Connection:
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
        "VALUES (1, '2026-04-01', '2026-04-01T16:00:00Z')"
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


def test_flat_base_passes_all_criteria_returns_geometric_score_1_0() -> None:
    """Per spec section 10.2 ALTERNATIVE-PASS scenario (22% uptrend):
    7/7 criteria pass; geometric_score == 1.0.
    """
    bars = _bars_passing_all_criteria_22pct()
    # Anchor at base START (index 41 = end of uptrend / start of range).
    window = _candidate_window(bars, anchor_offset=41)
    conn = _stage_2_conn()
    evidence = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    assert isinstance(evidence, FlatBaseEvidence)
    assert evidence.geometric_score == pytest.approx(1.0)
    for k in (
        "criterion_1",
        "criterion_2",
        "criterion_3",
        "criterion_4",
        "criterion_5",
        "criterion_6",
        "criterion_7",
    ):
        assert evidence.criteria_pass[k] is True, f"{k} failed"


def test_flat_base_passes_22pct_uptrend_above_tolerance_band() -> None:
    """Per spec section 10.2 alternative-pass: 22% prior uptrend >= 18%
    relaxed threshold -> criterion #2 PASSES.
    """
    bars = _bars_passing_all_criteria_22pct()
    window = _candidate_window(bars, anchor_offset=41)
    conn = _stage_2_conn()
    evidence = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_2"] is True
    # And the recorded prior uptrend reflects ~22% (not 14%).
    assert evidence.prior_uptrend_pct >= 18.0


def test_flat_base_rejects_14pct_uptrend_outside_2pct_tolerance_band() -> None:
    """Per spec section 10.2 errata + section 10.6 LOCK: tolerance band
    +/- 2 percentage points on the 20% bound. Relaxed threshold = 18%.
    A 14% prior uptrend is 4pp below the relaxed threshold -> FAILS.
    """
    # Same flat-base shape but compress the uptrend to 14%: 9.60 -> 10.944.
    segments = [
        (9.50, 9.60, 5),
        (9.60, 10.944, 36),    # 14% uptrend over ~5 weeks; below 18% relaxed
        (10.944, 11.30, 3),
        (11.30, 10.20, 10),
        (10.20, 11.30, 10),
        (11.30, 10.25, 10),
        (10.25, 11.28, 14),
    ]
    bars = _bars_from_segments(
        segments, start=date(2026, 1, 5), noise_pct=0.005
    )
    window = _candidate_window(bars, anchor_offset=41)
    conn = _stage_2_conn()
    evidence = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_2"] is False


def test_flat_base_fails_criterion_3_range_too_narrow_or_wide() -> None:
    """Per spec section 5.3 criterion #3 + section 10.6 tolerance:
    range_width = (range_top - range_bottom) / range_bottom must lie in
    [0.03, 0.12]; tolerance band ±0.5pp -> relaxed [0.025, 0.125]. A
    range_width of 0.018 (1.8%, narrower than the 2.5% relaxed lower
    bound) FAILS.
    """
    # Base entry has to RESET to the narrow range cleanly; anchor at the
    # bar AFTER the post-uptrend descent so range_top reflects the base
    # oscillation (not the descent). Range close [10.55, 10.70] with
    # 0.2% H/L wiggle -> H-L width ~= 1.8%, narrower than 2.5% relaxed
    # lower bound.
    segments = [
        (9.50, 9.60, 5),
        (9.60, 11.65, 36),     # uptrend 22% -> criterion #2 passes
        (11.65, 10.62, 3),     # 41..43 descent into range
        # Anchor at index 44 (first bar inside the narrow range).
        (10.62, 10.70, 8),     # 44..51 visit range top
        (10.70, 10.55, 10),    # 52..61
        (10.55, 10.70, 10),    # 62..71
        (10.70, 10.58, 10),    # 72..81
        (10.58, 10.68, 6),     # 82..87 pivot
    ]
    bars = _bars_from_segments(
        segments, start=date(2026, 1, 5), noise_pct=0.002
    )
    window = _candidate_window(bars, anchor_offset=44)
    conn = _stage_2_conn()
    evidence = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_3"] is False


def test_flat_base_fails_criterion_4_slope_too_steep() -> None:
    """Per spec section 5.3 criterion #4: regression_slope_pct_per_week
    must be <= 0.005 (in pct-of-range_bottom units per week). A
    rising-base shape with strong positive slope FAILS criterion #4.
    """
    # Strong upward drift inside the bounded range over 47 days.
    # Base: 10.50 -> 11.80 monotonically over 47 bars (drift ~12.4%/47
    # bars = ~0.39%/week of range_bottom -> well above 0.5% bound? Let's
    # make the slope unambiguously steep: 10.50 -> 11.80 linearly =
    # 0.0028 increase per day vs range_bottom 10.50 = 0.0267%/day =
    # 0.187% per week -> too low to fail.
    # Make it much steeper by compressing: 10.50 -> 12.20 over 35 bars =
    # ~16% over 5 weeks = ~3.2% per week -> well above 0.5%.
    segments = [
        (9.50, 9.60, 5),
        (9.60, 11.71, 36),
        (11.71, 10.50, 5),
        (10.50, 12.20, 35),    # strongly upward base, fails low-slope
    ]
    bars = _bars_from_segments(
        segments, start=date(2026, 1, 5), noise_pct=0.003
    )
    window = _candidate_window(bars, anchor_offset=46)   # anchor at base start
    conn = _stage_2_conn()
    evidence = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_4"] is False


def test_flat_base_fails_criterion_5_ATR_too_wide() -> None:  # noqa: N802
    """Per spec section 5.3 criterion #5: mean_atr_pct = avg(ATR_5d) /
    mid_range must be <= 0.025. A high-volatility intrabar range (5%
    half-width on every bar -> ATR ~10%) FAILS criterion #5.
    """
    bars = _bars_passing_all_criteria_22pct()
    # Override H/L to a wide 5% half-width -> ~10% intrabar range / mid
    # ~= 0.10 -> well above 0.025 bound.
    bars["High"] = bars["Close"] * 1.05
    bars["Low"] = bars["Close"] * 0.95
    window = _candidate_window(bars, anchor_offset=41)
    conn = _stage_2_conn()
    evidence = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_5"] is False


def test_flat_base_fails_criterion_6_duration_below_5_weeks() -> None:
    """Per spec section 5.3 criterion #6: (base_end - base_start).days
    must be >= 35 (5 weeks); tolerance NONE. A 21-day base FAILS.
    """
    # 21-day base (3 weeks, below 35-day bound).
    segments = [
        (9.50, 9.60, 5),
        (9.60, 11.71, 36),
        (11.71, 11.80, 2),
        (11.80, 10.50, 5),
        (10.50, 11.80, 5),
        (11.80, 10.55, 5),
        (10.55, 11.78, 4),
    ]
    bars = _bars_from_segments(
        segments, start=date(2026, 1, 5), noise_pct=0.005
    )
    window = _candidate_window(bars, anchor_offset=41)
    conn = _stage_2_conn()
    evidence = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_6"] is False


def test_flat_base_passes_criterion_7_pivot_within_1pct_of_range_top() -> None:
    """Per spec section 5.3 criterion #7 + section 10.6 LOCK: pivot
    within 1% of range_top (ratio in [0.99, 1.01]); tolerance 0.5%
    expands to [0.985, 1.015]. The all-pass fixture has pivot 11.78 /
    range_top 11.80 = 0.998 -> PASSES.
    """
    bars = _bars_passing_all_criteria_22pct()
    window = _candidate_window(bars, anchor_offset=41)
    conn = _stage_2_conn()
    evidence = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_7"] is True
    ratio = evidence.pivot_price / evidence.range_top_price
    assert 0.985 <= ratio <= 1.015


def test_flat_base_fails_criterion_1_stage_not_2_returns_geometric_score_0_0() -> None:
    """Per spec section 5.3 criterion #1: Stage 2 is a HARD GATE.
    Non-Stage-2 -> geometric_score == 0.0 regardless of other criteria.
    """
    # Empty candidates table -> current_stage returns 'undefined'.
    bars = _bars_passing_all_criteria_22pct()
    window = _candidate_window(bars, anchor_offset=41)
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
    evidence = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.geometric_score == pytest.approx(0.0)
    assert evidence.criteria_pass["criterion_1"] is False


def test_flat_base_structural_evidence_dataclass_shape() -> None:
    """FlatBaseEvidence is a frozen dataclass with __post_init__ runtime
    validation against allowed Literal values (per L7).
    """
    bars = _bars_passing_all_criteria_22pct()
    window = _candidate_window(bars, anchor_offset=41)
    conn = _stage_2_conn()
    evidence = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    # Frozen: cannot mutate attributes.
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.geometric_score = 0.5  # type: ignore[misc]
    # __post_init__ rejects invalid stage literal.
    with pytest.raises(ValueError):
        FlatBaseEvidence(
            stage="bogus",  # type: ignore[arg-type]
            prior_uptrend_pct=22.0,
            prior_uptrend_weeks=5,
            base_start_date=date(2026, 1, 1),
            base_end_date=date(2026, 2, 17),
            range_top_price=11.80,
            range_bottom_price=10.50,
            range_width_pct=12.4,
            regression_slope_pct_per_week=0.003,
            mean_atr_pct=0.021,
            base_duration_days=47,
            pivot_price=11.78,
            pivot_within_top_pct=-0.17,
            criteria_pass={f"criterion_{i}": True for i in range(1, 8)},
            geometric_score=1.0,
        )
    # __post_init__ rejects geometric_score outside [0.0, 1.0].
    with pytest.raises(ValueError):
        FlatBaseEvidence(
            stage="stage_2",
            prior_uptrend_pct=22.0,
            prior_uptrend_weeks=5,
            base_start_date=date(2026, 1, 1),
            base_end_date=date(2026, 2, 17),
            range_top_price=11.80,
            range_bottom_price=10.50,
            range_width_pct=12.4,
            regression_slope_pct_per_week=0.003,
            mean_atr_pct=0.021,
            base_duration_days=47,
            pivot_price=11.78,
            pivot_within_top_pct=-0.17,
            criteria_pass={f"criterion_{i}": True for i in range(1, 8)},
            geometric_score=1.5,
        )
    # __post_init__ rejects missing criteria_pass keys.
    with pytest.raises(ValueError):
        FlatBaseEvidence(
            stage="stage_2",
            prior_uptrend_pct=22.0,
            prior_uptrend_weeks=5,
            base_start_date=date(2026, 1, 1),
            base_end_date=date(2026, 2, 17),
            range_top_price=11.80,
            range_bottom_price=10.50,
            range_width_pct=12.4,
            regression_slope_pct_per_week=0.003,
            mean_atr_pct=0.021,
            base_duration_days=47,
            pivot_price=11.78,
            pivot_within_top_pct=-0.17,
            criteria_pass={"criterion_1": True},   # missing 2..7
            geometric_score=1.0,
        )


def test_flat_base_pure_function_no_db_writes() -> None:
    """Per L2: detect_flat_base MUST NOT write to the connection.
    Snapshot pre/post sqlite_master + each user table; assert unchanged.
    """
    bars = _bars_passing_all_criteria_22pct()
    window = _candidate_window(bars, anchor_offset=41)
    conn = _stage_2_conn()
    before_master = conn.execute(
        "SELECT name, sql FROM sqlite_master ORDER BY name"
    ).fetchall()
    before_rows = {
        tbl: conn.execute(
            f"SELECT * FROM {tbl} ORDER BY rowid"
        ).fetchall()
        for tbl in ("evaluation_runs", "candidates", "candidate_criteria")
    }
    _ = detect_flat_base(
        bars,
        window,
        conn=conn,
        ticker="YOU",
        asof_date=bars.index[-1].date(),
    )
    after_master = conn.execute(
        "SELECT name, sql FROM sqlite_master ORDER BY name"
    ).fetchall()
    after_rows = {
        tbl: conn.execute(
            f"SELECT * FROM {tbl} ORDER BY rowid"
        ).fetchall()
        for tbl in ("evaluation_runs", "candidates", "candidate_criteria")
    }
    assert before_master == after_master
    assert before_rows == after_rows
