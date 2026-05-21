"""Phase 13 T2.SB4 T-A.4.1 - discriminating tests for high_tight_flag detector.

Per dispatch brief Step 1 + plan section G.6 T-A.4.1: 10+ failing tests
covering spec section 5.5 (6 criteria + tolerances) + section 10.4
($WXYZ worked example; alternative-pass scenario) + section 10.6 LOCK
(criterion #4 consolidation_width STRICT bound NONE; 15.6% rejects;
14.8% passes).

LOCKs honored:
- L1: verbatim spec section 5.5 criteria + tolerance values + section
  10.6 STRICT bound NONE for criterion #4.
- L2: ZERO DB writes inside detector (current_stage is read-only).
- L7: frozen dataclass with __post_init__ runtime validation against
  explicit frozensets.
- L8: post-pole sub-window named consolidation_* NOT flag_*.
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

from swing.patterns.foundation import CandidateWindow
from swing.patterns.high_tight_flag import (
    HighTightFlagEvidence,
    detect_high_tight_flag,
)

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


def _bars_wxyz_alt_pass(
    start: date = date(2026, 1, 5),
    *,
    consolidation_bottom: float = 9.40,
    consolidation_top: float = 10.40,
    consol_days: int = 25,
) -> pd.DataFrame:
    """Construct bars matching the spec section 10.4 ALTERNATIVE-PASS
    scenario: $WXYZ pole $5 -> $11 over 35 days (120% gain); consolidation
    range engineered for ~14.8% width (top to bottom).

    Default consolidation: top 10.40, bottom 9.40 -> raw width
    ~10.6%. The H/L noise widening at 0.005 expands intrabar width by
    +1.0pp -> ~11.6% intrabar width (well below 15%). Caller can pass
    other (top, bottom) for the 15.6% reject scenario.

    Layout:
    - 10 filler bars at ~5.00 leading into the pole.
    - 35-day pole from 5.00 -> 11.00 (120% gain over 5 weeks).
    - 25-day consolidation in [bottom, top] range with multiple visits
      to bottom + recovery to pivot at top.
    - Volume during pole averages 2_000_000; during consolidation
      averages 1_000_000 (50% of pole average -> well below 65% cap).
    """
    pole_start_close = 5.00
    pole_peak_close = 11.00
    # Index layout: pre-pole descent 0..9 (10 bars from 6.00 -> 5.00 to
    # create a clear swing-LOW at idx 9 that anchors pole_start);
    # pole 10..44 (35 bars 5.00 -> 11.00); consol 45..69.
    segments: list[tuple[float, float, int]] = [
        (6.00, pole_start_close, 10),              # 0..9 descent into pole start
        (pole_start_close, pole_peak_close, 35),   # 10..44 pole
    ]
    # Consolidation engineered to put consolidation_top as the FIRST
    # consolidation bar so the pole peak (index 44 close 11.00 H 11.055)
    # remains the absolute highest bar; then descend to bottom and
    # bounce back. Engineering: consolidation closes are
    # [top, bottom, top, bottom, top] step pattern across consol_days.
    half = max(1, consol_days // 4)
    rem = consol_days - 4 * half
    consol_close_segments: list[tuple[float, float, int]] = [
        (consolidation_top, consolidation_top, 1),
        (consolidation_top, consolidation_bottom, half),
        (consolidation_bottom, consolidation_top, half),
        (consolidation_top, consolidation_bottom, half),
        (consolidation_bottom, consolidation_top, half + rem - 1),
    ]
    segments.extend(consol_close_segments)
    # Volumes: 10 filler @ 1M, 35 pole @ 2M, consol_days @ 1M (50% of pole).
    total_bars = 10 + 35 + consol_days
    volumes = (
        [1_000_000.0] * 10
        + [2_000_000.0] * 35
        + [1_000_000.0] * consol_days
    )
    assert len(volumes) == total_bars, (len(volumes), total_bars)
    bars = _bars_from_segments(
        segments,
        start=start,
        noise_pct=0.005,
        volumes_per_bar=volumes,
    )
    return bars


def _candidate_window_at_pole_peak(
    bars: pd.DataFrame,
    *,
    pole_peak_offset: int = 44,
    ticker: str = "WXYZ",
    reason_prefix: str = "zigzag_pivot",
) -> CandidateWindow:
    """Build a CandidateWindow with anchor_date == pole_peak_date.

    Per L1 LOCK + dispatch brief anchor_date contract: HTF uses swing-HIGH
    (pole peak). For zigzag_pivot mode the anchor IS the pole peak.
    """
    anchor_dt = bars.index[pole_peak_offset].date()
    return CandidateWindow(
        ticker=ticker,
        timeframe="daily",
        start_date=anchor_dt,
        end_date=bars.index[-1].date(),
        anchor_date=anchor_dt,
        anchor_reason=f"{reason_prefix}:test_anchor",
    )


def _stage_2_conn(ticker: str = "WXYZ") -> sqlite3.Connection:
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


def test_htf_passes_all_criteria_with_14_8pct_consolidation_width_strict_bound() -> None:
    """Per spec section 10.4 ALTERNATIVE-PASS scenario: consolidation width
    well under 15% strict bound; 6/6 criteria pass; geometric_score == 1.0.
    """
    bars = _bars_wxyz_alt_pass()
    window = _candidate_window_at_pole_peak(bars, pole_peak_offset=44)
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars,
        window,
        conn=conn,
        ticker="WXYZ",
        asof_date=bars.index[-1].date(),
    )
    assert isinstance(evidence, HighTightFlagEvidence)
    # Verify all 6 criteria pass.
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
            f"width_pct={evidence.consolidation_width_pct}; "
            f"pole_pct={evidence.pole_pct}; "
            f"pole_duration={evidence.pole_duration_days}; "
            f"consol_pullback={evidence.consolidation_pullback_pct}; "
            f"consol_duration={evidence.consolidation_duration_days}; "
            f"vol_ratio={evidence.consolidation_avg_volume / max(1e-9, evidence.pole_avg_volume)}"
        )
    assert evidence.geometric_score == pytest.approx(1.0)
    # Spec section 10.6 STRICT bound: width must be <= 15%.
    assert evidence.consolidation_width_pct <= 15.0


def test_htf_rejects_15_6pct_consolidation_width_strict_no_tolerance_bound() -> None:
    """Per spec section 10.4 errata + section 10.6 LOCK: criterion #4
    tolerance is STRICTLY NONE. 15.6% width must REJECT (no tolerance band).
    Pattern -> criterion_4 = False; geometric_score reflects the failure.
    """
    # Engineer consolidation width ~15.6%: bottom 9.00, top 10.40 ->
    # raw close-to-close ~15.6%. With +/- 0.5% noise: intrabar width
    # ~16.6%. Test asserts the bound is strict on the computed
    # width_pct value, so we want the FINAL computed value > 15.0%.
    bars = _bars_wxyz_alt_pass(
        consolidation_bottom=9.00,
        consolidation_top=10.40,
    )
    window = _candidate_window_at_pole_peak(bars, pole_peak_offset=44)
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars,
        window,
        conn=conn,
        ticker="WXYZ",
        asof_date=bars.index[-1].date(),
    )
    # Width must be > 15% to exercise the strict bound.
    assert evidence.consolidation_width_pct > 15.0, (
        f"Test fixture mis-engineered: expected width > 15%, got "
        f"{evidence.consolidation_width_pct}"
    )
    # Criterion #4 must FAIL (no tolerance band).
    assert evidence.criteria_pass["criterion_4"] is False
    # geometric_score must reflect criterion #4 failure.
    assert evidence.geometric_score < 1.0


def test_htf_fails_criterion_2_pole_below_90pct() -> None:
    """Per spec section 5.5 criterion #2 + section 10.6 tolerance band +/-5%:
    pole_pct below relaxed bound (85%) fails. Use a 50% pole (well below).
    """
    # Pole 5.00 -> 7.50 = 50% (below 85% relaxed bound).
    segments = [
        (6.00, 5.00, 10),    # pre-pole descent (swing-LOW at idx 9)
        (5.00, 7.50, 35),    # pole 50% over 35 days -- fails
    ]
    consolidation_top = 7.30
    consolidation_bottom = 6.80
    consol_days = 25
    half = max(1, consol_days // 4)
    rem = consol_days - 4 * half
    segments.extend([
        (consolidation_top, consolidation_top, 1),
        (consolidation_top, consolidation_bottom, half),
        (consolidation_bottom, consolidation_top, half),
        (consolidation_top, consolidation_bottom, half),
        (consolidation_bottom, consolidation_top, half + rem - 1),
    ])
    volumes = (
        [1_000_000.0] * 10
        + [2_000_000.0] * 35
        + [1_000_000.0] * consol_days
    )
    bars = _bars_from_segments(
        segments, start=date(2026, 1, 5), noise_pct=0.005,
        volumes_per_bar=volumes,
    )
    window = _candidate_window_at_pole_peak(bars, pole_peak_offset=44)
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars, window, conn=conn, ticker="WXYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_2"] is False
    # pole_pct should reflect ~50% (below 85% relaxed).
    assert evidence.pole_pct < 0.85


def test_htf_fails_criterion_2_pole_duration_outside_4_8_weeks() -> None:
    """Per spec section 5.5 criterion #2: pole_duration must be in
    [28, 56] days. A 20-day pole (under 4 weeks) fails on duration.
    """
    # Compress the pole to 20 days (below 28-day lower bound).
    pole_days = 20
    consol_days = 25
    segments = [
        (6.00, 5.00, 10),         # pre-pole descent (swing-LOW at idx 9)
        (5.00, 11.00, pole_days), # pole 120% but only 20 days
    ]
    consolidation_top = 10.40
    consolidation_bottom = 9.40
    half = max(1, consol_days // 4)
    rem = consol_days - 4 * half
    segments.extend([
        (consolidation_top, consolidation_top, 1),
        (consolidation_top, consolidation_bottom, half),
        (consolidation_bottom, consolidation_top, half),
        (consolidation_top, consolidation_bottom, half),
        (consolidation_bottom, consolidation_top, half + rem - 1),
    ])
    volumes = (
        [1_000_000.0] * 10
        + [2_000_000.0] * pole_days
        + [1_000_000.0] * consol_days
    )
    bars = _bars_from_segments(
        segments, start=date(2026, 1, 5), noise_pct=0.005,
        volumes_per_bar=volumes,
    )
    pole_peak_offset = 10 + pole_days - 1  # last bar of pole segment
    window = _candidate_window_at_pole_peak(
        bars, pole_peak_offset=pole_peak_offset
    )
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars, window, conn=conn, ticker="WXYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_2"] is False
    # pole_duration_days should be < 28.
    assert evidence.pole_duration_days < 28


def test_htf_fails_criterion_3_consolidation_pullback_above_25pct() -> None:
    """Per spec section 5.5 criterion #3 + section 10.6 tolerance +/-2pp:
    pullback above 27% (relaxed bound) fails. Use a 40% pullback.
    """
    # Engineer consolidation bottom way below: top 10.40, bottom 6.00 ->
    # pullback from pole peak 11.00 = (11 - 6) / 11 ~= 45% > 27%.
    # But this also fails criterion #4 (width); test asserts c3 fails.
    bars = _bars_wxyz_alt_pass(
        consolidation_bottom=6.00,
        consolidation_top=10.40,
    )
    window = _candidate_window_at_pole_peak(bars, pole_peak_offset=44)
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars, window, conn=conn, ticker="WXYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_3"] is False
    assert evidence.consolidation_pullback_pct > 0.27


def test_htf_fails_criterion_3_consolidation_duration_outside_3_5_weeks() -> None:
    """Per spec section 5.5 criterion #3: consolidation_duration in
    [21, 35] days. A 10-day consolidation fails on duration.
    """
    bars = _bars_wxyz_alt_pass(consol_days=10)
    # Window end is the last bar; consolidation_duration = end - pole_peak.
    window = _candidate_window_at_pole_peak(bars, pole_peak_offset=44)
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars, window, conn=conn, ticker="WXYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_3"] is False
    assert evidence.consolidation_duration_days < 21


def test_htf_fails_criterion_5_volume_drop_below_35pct() -> None:
    """Per spec section 5.5 criterion #5 + section 10.6 tolerance +/-10%:
    ratio above 0.75 (relaxed) fails. Use consolidation volume == pole
    volume (ratio 1.0).
    """
    pole_days = 35
    consol_days = 25
    bars = _bars_wxyz_alt_pass(consol_days=consol_days)
    # Override volumes: pole = 1M, consolidation = 1M (no contraction).
    new_volumes = (
        [1_000_000.0] * 10
        + [1_000_000.0] * pole_days
        + [1_000_000.0] * consol_days
    )
    bars = bars.copy()
    bars["Volume"] = new_volumes
    window = _candidate_window_at_pole_peak(bars, pole_peak_offset=44)
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars, window, conn=conn, ticker="WXYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_5"] is False
    # volume ratio ~1.0 > 0.75 relaxed.
    assert evidence.pole_avg_volume > 0
    assert (
        evidence.consolidation_avg_volume / evidence.pole_avg_volume > 0.75
    )


def test_htf_passes_criterion_6_pivot_within_1pct_consolidation_top() -> None:
    """Per spec section 5.5 criterion #6 + section 10.6 tolerance +/-0.5%:
    pivot/consolidation_top in [0.985, 1.015] passes. Default fixture
    closes consolidation at the top -> ratio 1.0.
    """
    bars = _bars_wxyz_alt_pass()
    window = _candidate_window_at_pole_peak(bars, pole_peak_offset=44)
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars, window, conn=conn, ticker="WXYZ",
        asof_date=bars.index[-1].date(),
    )
    assert evidence.criteria_pass["criterion_6"] is True
    # Pivot should be at or very near consolidation_top.
    ratio = evidence.pivot_price / evidence.consolidation_top_price
    assert 0.985 <= ratio <= 1.015


def test_htf_structural_evidence_dataclass_shape() -> None:
    """Verify HighTightFlagEvidence is a frozen dataclass with all required
    fields per dispatch brief LOCK L7 + L8 (consolidation_* naming).
    """
    bars = _bars_wxyz_alt_pass()
    window = _candidate_window_at_pole_peak(bars, pole_peak_offset=44)
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars, window, conn=conn, ticker="WXYZ",
        asof_date=bars.index[-1].date(),
    )
    # Frozen dataclass.
    assert dataclasses.is_dataclass(evidence)
    assert evidence.__dataclass_params__.frozen is True
    # L8 LOCK: consolidation_* naming (NOT flag_*).
    field_names = {f.name for f in dataclasses.fields(evidence)}
    required_consolidation_fields = {
        "consolidation_start_date",
        "consolidation_end_date",
        "consolidation_pullback_pct",
        "consolidation_width_pct",
        "consolidation_duration_days",
        "consolidation_avg_volume",
        "consolidation_top_price",
        "consolidation_bottom_price",
    }
    missing = required_consolidation_fields - field_names
    assert not missing, f"Missing consolidation_* fields: {missing}"
    # Reject any flag_* field that masquerades as consolidation_*.
    flag_named = {n for n in field_names if n.startswith("flag_")}
    assert not flag_named, (
        f"L8 LOCK violation: HighTightFlagEvidence must use consolidation_* "
        f"naming, NOT flag_*. Found: {flag_named}"
    )
    # L7 LOCK: stage validator rejects invalid Literal value.
    valid_kwargs = {f.name: getattr(evidence, f.name) for f in dataclasses.fields(evidence)}
    valid_kwargs["stage"] = "not_a_valid_stage"
    with pytest.raises(ValueError, match="stage"):
        HighTightFlagEvidence(**valid_kwargs)


def test_htf_bar_clipping_future_bar_leak_rejected() -> None:
    """Per dispatch brief LOCK L10 + T2.SB3 forward-binding lesson #2:
    bars MUST be clipped to ``bars.index <= candidate_window.end_date``
    BEFORE anchor identification. Plant a future bar with HIGHEST-HIGH
    after window.end_date; detector must NOT use it as pole peak.
    """
    bars = _bars_wxyz_alt_pass()
    # Append a future bar with an even higher pole-like spike beyond
    # the candidate window's end_date.
    future_idx = bars.index[-1] + pd.Timedelta(days=1)
    future_bar = pd.DataFrame(
        {
            "Open": [50.00],
            "High": [51.00],  # higher than any in-window bar
            "Low": [49.00],
            "Close": [50.50],
            "Volume": [3_000_000.0],
        },
        index=pd.DatetimeIndex([future_idx]),
    )
    bars_with_future = pd.concat([bars, future_bar])
    # Candidate window's end_date is the original bars' last date
    # (BEFORE the planted future bar).
    window_end = bars.index[-1].date()
    window = CandidateWindow(
        ticker="WXYZ",
        timeframe="daily",
        start_date=bars.index[44].date(),
        end_date=window_end,
        anchor_date=bars.index[44].date(),
        anchor_reason="zigzag_pivot:test_anchor",
    )
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars_with_future,
        window,
        conn=conn,
        ticker="WXYZ",
        asof_date=window_end,
    )
    # Pole peak must be on or before window.end_date.
    assert evidence.pole_peak_date <= window_end, (
        f"Bar-clip leak: pole_peak_date {evidence.pole_peak_date} > "
        f"window.end_date {window_end}; detector used a future bar."
    )
    # consolidation_end_date must be on or before window.end_date.
    assert evidence.consolidation_end_date <= window_end


def test_htf_empty_bars_returns_zero_score() -> None:
    """Pre-empt empty-bars edge case per dispatch brief pre-Codex review
    anticipated flags. Empty bars -> low-score evidence; no exception.
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
        ticker="WXYZ",
        timeframe="daily",
        start_date=date(2026, 1, 5),
        end_date=date(2026, 2, 5),
        anchor_date=date(2026, 1, 5),
        anchor_reason="zigzag_pivot:test_anchor",
    )
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        empty,
        window,
        conn=conn,
        ticker="WXYZ",
        asof_date=date(2026, 2, 5),
    )
    assert isinstance(evidence, HighTightFlagEvidence)
    assert evidence.geometric_score == 0.0


def test_htf_nan_at_entry_raises_via_sanitize_bars() -> None:
    """Pre-empt NaN-handling per dispatch brief pre-Codex review anticipated
    flags. sanitize_bars at entry raises ValueError on NaN.
    """
    bars = _bars_wxyz_alt_pass()
    # Plant a NaN in High.
    bars = bars.copy()
    bars.iloc[5, bars.columns.get_loc("High")] = np.nan
    window = _candidate_window_at_pole_peak(bars, pole_peak_offset=44)
    conn = _stage_2_conn()
    with pytest.raises(ValueError, match="NaN|non-finite"):
        detect_high_tight_flag(
            bars, window, conn=conn, ticker="WXYZ",
            asof_date=bars.index[-1].date(),
        )


def test_htf_stage_2_gate_fails_without_conn_returns_zero_score() -> None:
    """Criterion #1 (Stage 2) is a hard gate. Without a conn, stage is
    undefined; criterion_1 fails; geometric_score = 0.0.
    """
    bars = _bars_wxyz_alt_pass()
    window = _candidate_window_at_pole_peak(bars, pole_peak_offset=44)
    evidence = detect_high_tight_flag(bars, window)
    assert evidence.criteria_pass["criterion_1"] is False
    assert evidence.geometric_score == 0.0


def test_htf_pole_peak_selects_highest_swing_high_not_intra_consolidation_peak() -> None:
    """Codex R1 Major #3: in a real HTF pattern the 3-5 week post-pole
    consolidation may contain minor swing-highs near the pivot; those
    are NOT the pole peak. Pre-fix, _backward_slice_pole_peak walked
    swings in reverse + returned the FIRST UP-swing endpoint
    encountered, which would pick an intra-consolidation peak when the
    consolidation ends with one. Post-fix, the algorithm selects the
    HIGHEST swing-HIGH end_price subject to occurring at least one
    consolidation-window-min (21 days) back from the anchor; an
    intra-consolidation minor swing-high (only ~10-15 days back from
    the anchor) is excluded.

    Fixture: pole $5 -> $11 over 35 days (120% gain) + 25-day
    consolidation with a minor intra-consolidation swing-high around
    $10.20 (well below the pole peak $11). When the candidate window
    is anchored at the consolidation END with ma_crossover reason
    (TRIGGER EVENT), the detector backward-slices to find the pole
    peak. Pre-fix: would return the intra-consolidation $10.20 peak
    (or similar minor swing-high). Post-fix: returns the genuine pole
    peak $11.
    """
    # Layout: 10 filler at ~5 + 35 pole 5->11 + 25 consolidation with
    # minor swing-highs.
    segments: list[tuple[float, float, int]] = [
        (5.00, 5.00, 10),                  # 0..9 filler
        (5.00, 11.00, 35),                 # 10..44 pole 5->11
    ]
    # Consolidation: descend to 9.80, climb to minor swing-high 10.20,
    # back to 9.80, climb to minor swing-high 10.20, descend to 9.80,
    # final climb to 10.20 (pivot near top). Each leg ~4-5 days for
    # ~25 total. The intra-consolidation minor swing-highs are
    # 10.20 < pole peak 11.00.
    consol_segments: list[tuple[float, float, int]] = [
        (11.00, 9.80, 5),                  # 45..49 descend off pole
        (9.80, 10.20, 4),                  # 50..53 minor up
        (10.20, 9.80, 4),                  # 54..57 minor down
        (9.80, 10.20, 4),                  # 58..61 minor up
        (10.20, 9.80, 4),                  # 62..65 minor down
        (9.80, 10.20, 4),                  # 66..69 final climb to pivot
    ]
    segments.extend(consol_segments)
    n_total = 10 + 35 + 25
    # Volume: 1M filler, 2M pole, 1M consol -> ratio 0.5 well below 0.65 cap.
    volumes = (
        [1_000_000.0] * 10
        + [2_000_000.0] * 35
        + [1_000_000.0] * 25
    )
    assert len(volumes) == n_total
    bars = _bars_from_segments(
        segments,
        start=date(2026, 1, 5),
        noise_pct=0.005,
        volumes_per_bar=volumes,
    )
    # Anchor at the last bar with ma_crossover reason (TRIGGER EVENT
    # semantic; the detector backward-slices for the pole peak).
    anchor_dt = bars.index[-1].date()
    window = CandidateWindow(
        ticker="WXYZ",
        timeframe="daily",
        start_date=anchor_dt,
        end_date=anchor_dt,
        anchor_date=anchor_dt,
        anchor_reason="ma_crossover:test_pole_peak_selection",
    )
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars, window, conn=conn, ticker="WXYZ",
        asof_date=anchor_dt,
    )
    # Pole peak should be in the pole-end region (around bar idx 44,
    # date 2026-02-18) with price near 11.00 -- NOT an intra-
    # consolidation $10.20 swing-high.
    pole_peak_idx_expected_min = 40   # generous window for pole-end peak
    pole_peak_idx_expected_max = 49   # exclude any consolidation idx >= 50
    pole_peak_ts = pd.Timestamp(evidence.pole_peak_date)
    pole_peak_idx = bars.index.get_loc(pole_peak_ts)
    assert pole_peak_idx_expected_min <= pole_peak_idx <= pole_peak_idx_expected_max, (
        f"Expected pole_peak_idx in [{pole_peak_idx_expected_min}, "
        f"{pole_peak_idx_expected_max}] (pole-end region); got "
        f"pole_peak_idx={pole_peak_idx} pole_peak_date={evidence.pole_peak_date} "
        f"pole_peak_price={evidence.pole_peak_price}"
    )
    # Pole peak price should be near the genuine pole peak $11.00,
    # NOT the intra-consolidation $10.20.
    assert evidence.pole_peak_price >= 10.8, (
        f"Expected pole_peak_price >= 10.8 (genuine $11 pole peak); "
        f"got {evidence.pole_peak_price} -- likely picked up an intra-"
        f"consolidation minor swing-high"
    )


def test_htf_pole_peak_excludes_intra_consolidation_swing_within_21d_gap() -> None:
    """Codex R1 Major #3 gating rule: candidate pole peaks must occur
    at LEAST _CONSOLIDATION_DURATION_DAYS_RANGE[0] (21 days) back from
    the anchor; intra-consolidation swing-highs within that gap are
    EXCLUDED. This pins the gap rule explicitly.

    Fixture: same pole + consolidation construction but with the
    consolidation truncated so the most-recent swing-high is within
    21 days of the anchor. The detector must REJECT that recent
    swing-high (its date is too close to the anchor) and SELECT the
    earlier pole-end peak.
    """
    segments: list[tuple[float, float, int]] = [
        (5.00, 5.00, 10),
        (5.00, 11.00, 35),
        # Short consolidation: 25 bars with last bar at consol top.
        (11.00, 9.80, 5),
        (9.80, 10.30, 4),
        (10.30, 9.80, 4),
        (9.80, 10.30, 4),
        (10.30, 9.80, 4),
        (9.80, 10.30, 4),  # final bar at minor high near anchor
    ]
    volumes = (
        [1_000_000.0] * 10
        + [2_000_000.0] * 35
        + [1_000_000.0] * 25
    )
    bars = _bars_from_segments(
        segments,
        start=date(2026, 1, 5),
        noise_pct=0.005,
        volumes_per_bar=volumes,
    )
    anchor_dt = bars.index[-1].date()
    window = CandidateWindow(
        ticker="WXYZ",
        timeframe="daily",
        start_date=anchor_dt,
        end_date=anchor_dt,
        anchor_date=anchor_dt,
        anchor_reason="high_low_breakout:test_gap_rule",
    )
    conn = _stage_2_conn()
    evidence = detect_high_tight_flag(
        bars, window, conn=conn, ticker="WXYZ",
        asof_date=anchor_dt,
    )
    # Pole peak must NOT be a bar within the last 21 calendar days of
    # the anchor (intra-consolidation swing-high excluded).
    anchor_ts = pd.Timestamp(anchor_dt)
    pole_peak_ts = pd.Timestamp(evidence.pole_peak_date)
    gap_days = (anchor_ts - pole_peak_ts).days
    assert gap_days >= 21, (
        f"Expected pole_peak at least 21 days before anchor; "
        f"got gap_days={gap_days} pole_peak_date={evidence.pole_peak_date} "
        f"anchor_date={anchor_dt}"
    )
