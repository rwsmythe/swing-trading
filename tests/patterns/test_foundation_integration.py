"""Phase 13 T2.SB2 T-A.2.6 — foundation primitives end-to-end integration.

Per plan section G.3 T-A.2.6 Step 1: ONE end-to-end test chaining all 5
V1 primitives (smoothing -> extrema -> candidate windows -> volume
profile -> trend state) against a deterministic synthesized OHLCV
fixture. Pins the integration contract that T2.SB3 (VCP + flat_base +
cup_with_handle) + T2.SB4 (high_tight_flag + double_bottom_W)
detectors will consume.

Plus the cross-bundle pin per plan section H.3 line 2617:
``test_foundation_primitives_consumed_by_detectors_invariant`` — planted
SKIPPED at T2.SB2; un-skips at T2.SB3 + T2.SB4 detector dispatch.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.evaluation.criteria.trend_template import CHECK_NAMES
from swing.patterns.foundation import (
    CandidateWindow,
    Swing,
    VolumeSegment,
    breakout_volume_ratio,
    current_stage,
    extract_zigzag_swings,
    generate_candidate_windows,
    smooth_ema,
    volume_trend_through_swings,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase13_t2sb2_integration.db"
    return ensure_schema(db_path)


def _build_synthesized_ohlcv() -> pd.DataFrame:
    """Build a 252-bar daily OHLCV fixture with a multi-stage uptrend and
    a VCP-style 3-contraction base near the end-of-year.

    Deterministic via ``np.random.default_rng(seed=42)`` so the test is
    reproducible. Anchored on a fixed start date so DB integration steps
    have a stable asof.
    """
    rng = np.random.default_rng(seed=42)
    n_bars = 252
    start = pd.Timestamp("2025-01-02")
    # Business-day index (252 bars ~= 1 year).
    idx = pd.bdate_range(start=start, periods=n_bars)

    # Build a Close series: smooth uptrend with noise + a VCP-style
    # 3-contraction base in the last ~9 weeks (45 bars).
    base_trend = np.linspace(50.0, 110.0, n_bars - 45)
    # Add small daily noise (~0.5% sigma).
    noise = rng.normal(loc=0.0, scale=0.4, size=n_bars - 45)
    trend_segment = base_trend + np.cumsum(noise) * 0.05

    # VCP-style contraction segment: 3 contractions of monotonically
    # decreasing depth at 12%, 8%, 5%. Each contraction spans 15 bars.
    pre_base_peak = float(trend_segment[-1])  # peak level entering base
    contraction_depths = [0.12, 0.08, 0.05]
    contraction_bars: list[float] = []
    last_peak = pre_base_peak
    for depth in contraction_depths:
        trough = last_peak * (1.0 - depth)
        # 7 bars down, 8 bars up — total 15.
        down_leg = np.linspace(last_peak, trough, 7)
        up_leg = np.linspace(trough, last_peak, 8)
        contraction_bars.extend(down_leg.tolist())
        contraction_bars.extend(up_leg.tolist())
    closes = np.concatenate([trend_segment, np.asarray(contraction_bars)])
    assert closes.shape[0] == n_bars

    # Build OHLC around Close: O = prior Close (or Close on bar 0);
    # H = max(O, C) * (1 + small noise); L = min(O, C) * (1 - small noise).
    opens = np.empty(n_bars, dtype=float)
    opens[0] = closes[0]
    opens[1:] = closes[:-1]
    bar_noise = rng.uniform(low=0.0, high=0.008, size=n_bars)
    highs = np.maximum(opens, closes) * (1.0 + bar_noise)
    lows = np.minimum(opens, closes) * (1.0 - bar_noise)

    # Volume: baseline ~1M shares with mild noise + a 2.5x spike on the
    # final bar (breakout-day) so breakout_volume_ratio has signal.
    volumes = rng.uniform(low=8e5, high=1.2e6, size=n_bars)
    volumes[-1] = volumes[-1] * 2.5

    df = pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        },
        index=idx,
    )
    return df


def _plant_stage_2_candidate_for_ticker(
    conn: sqlite3.Connection, ticker: str, action_session_iso: str
) -> None:
    """Mirror the planting pattern from
    ``tests/patterns/test_foundation_trend_state.py:_plant_aplus_candidate``
    so the ``current_stage`` step has a stable Phase 4 evaluation surface
    to read.
    """
    with conn:
        cur = conn.execute(
            """INSERT INTO evaluation_runs
               (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                tickers_evaluated, aplus_count, watch_count, skip_count,
                excluded_count, error_count,
                rs_universe_version, rs_universe_hash)
               VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
            (
                f"{action_session_iso}T21:00:00",
                action_session_iso,
                action_session_iso,
            ),
        )
        e_id = int(cur.lastrowid)
        cur = conn.execute(
            """INSERT INTO candidates
               (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                rs_method)
               VALUES (?, ?, 'aplus', 100.0, 101.0, 95.0, 'universe')""",
            (e_id, ticker),
        )
        c_id = int(cur.lastrowid)
        for name in CHECK_NAMES:
            conn.execute(
                """INSERT INTO candidate_criteria
                   (candidate_id, criterion_name, layer, result, value, rule)
                   VALUES (?, ?, 'trend_template', 'pass', NULL, NULL)""",
                (c_id, name),
            )


def test_foundation_primitives_end_to_end_chain(conn: sqlite3.Connection) -> None:
    """Chain smooth_ema -> extract_zigzag_swings -> generate_candidate_windows
    -> volume_trend_through_swings -> breakout_volume_ratio -> current_stage.

    Verifies that the 5 V1 primitives compose without exception against
    a realistic synthesized OHLCV fixture; pins the integration contract
    that T2.SB3 + T2.SB4 detectors will consume.
    """
    ticker = "TESTVCP"
    bars = _build_synthesized_ohlcv()

    # Step 1: smooth_ema(window=10) — shape-preserving.
    smoothed = smooth_ema(bars["Close"].to_numpy(), window=10)
    assert smoothed.shape == (len(bars),)
    assert np.all(np.isfinite(smoothed))

    # Step 2: extract_zigzag_swings on the synthesized contraction pattern.
    swings = extract_zigzag_swings(
        bars, initial_threshold_pct=3.0, monotonic_narrow=True
    )
    assert isinstance(swings, list)
    # The 3 contractions with 12% / 8% / 5% depth should each yield at
    # least a down + up leg; we expect well >= 2 swings.
    assert len(swings) >= 2, (
        f"expected >= 2 swings on synthesized 3-contraction base, got "
        f"{len(swings)}"
    )
    for sw in swings:
        assert isinstance(sw, Swing)
        assert sw.direction in {"up", "down"}
        assert sw.depth_pct >= 0.0

    # Step 3: generate_candidate_windows via zigzag_pivot anchor mode.
    windows = generate_candidate_windows(
        bars,
        anchor_search_method="zigzag_pivot",
        ticker=ticker,
        timeframe="daily",
    )
    assert isinstance(windows, list)
    assert len(windows) >= 1, (
        f"expected >= 1 candidate window from zigzag_pivot anchor, got "
        f"{len(windows)}"
    )
    for w in windows:
        assert isinstance(w, CandidateWindow)
        assert w.ticker == ticker
        assert w.timeframe == "daily"

    # Step 4: volume_trend_through_swings — length matches swings count.
    segments = volume_trend_through_swings(bars, swings)
    assert isinstance(segments, list)
    assert len(segments) == len(swings)
    for seg in segments:
        assert isinstance(seg, VolumeSegment)
        assert seg.avg_volume >= 0.0
        assert np.isfinite(seg.avg_volume)

    # Step 5: breakout_volume_ratio on the last bar against 50d baseline.
    breakout_dt = bars.index[-1].date()
    ratio = breakout_volume_ratio(bars, breakout_date=breakout_dt, baseline_days=50)
    assert isinstance(ratio, float)
    assert np.isfinite(ratio)
    # Final bar has a 2.5x volume spike — ratio must be > 1.0.
    assert ratio > 1.0, (
        f"expected breakout-day volume ratio > 1.0 given 2.5x synth spike, "
        f"got {ratio:.3f}"
    )

    # Step 6: current_stage(conn, ticker, asof_date) — plant a stage_2
    # candidate row and assert the wrapper resolves to a valid label.
    asof = breakout_dt
    _plant_stage_2_candidate_for_ticker(
        conn, ticker=ticker, action_session_iso=asof.isoformat()
    )
    stage = current_stage(conn, ticker=ticker, asof_date=asof)
    assert stage in {"stage_1", "stage_2", "stage_3", "stage_4", "undefined"}
    # With all 8 TT criteria planted as pass, wrapper resolves to stage_2.
    assert stage == "stage_2", (
        f"expected stage_2 with all 8 TT pass, got {stage!r}"
    )


def test_foundation_primitives_consumed_by_detectors_invariant() -> None:
    """Cross-bundle pin: T2.SB3 + T2.SB4 detectors (VCP / flat_base /
    cup_with_handle / high_tight_flag / double_bottom_w) MUST consume
    foundation primitives at the locked signatures. First un-skipped at
    T-A.3.9 (T2.SB3 closer) per plan H.3 row 5 (3-detector body);
    extended at T-A.4.7 (T2.SB4 closer) to cover the 2 new T2.SB4
    detectors (high_tight_flag + double_bottom_w) per dispatch brief
    section 1 + section 4.3 #17 + plan H.3 row 5.

    Verifies via ``inspect.getsource`` on each detector module that the
    expected foundation primitives are imported + referenced.

    Per detector imports (verified against actual module source at
    T-A.4.7 closer; HTF / DBW import only 4 primitives - neither uses
    ``volume_trend_through_swings``, both compute their own
    pole/consolidation or trough-window volume aggregates inline):
    - vcp: CandidateWindow, current_stage, extract_zigzag_swings,
      volume_trend_through_swings, adaptive_initial_threshold_pct
    - flat_base: CandidateWindow, current_stage, extract_zigzag_swings,
      adaptive_initial_threshold_pct
    - cup_with_handle: CandidateWindow, current_stage,
      extract_zigzag_swings, adaptive_initial_threshold_pct
    - high_tight_flag: CandidateWindow, current_stage,
      extract_zigzag_swings, adaptive_initial_threshold_pct
    - double_bottom_w: CandidateWindow, current_stage,
      extract_zigzag_swings, adaptive_initial_threshold_pct
    """
    import inspect

    from swing.patterns import (
        cup_with_handle,
        double_bottom_w,
        flat_base,
        high_tight_flag,
        vcp,
    )

    # 5 V1 detectors: each MUST reference the foundation primitives that
    # the spec invariant requires they consume. Per spec sections 5.2 /
    # 5.3 / 5.4 / 5.5 / 5.6 + recon section 7: all 5 consume
    # CandidateWindow inputs, extract_zigzag_swings for swing extraction,
    # current_stage for the Phase-4 evaluation surface read, and
    # adaptive_initial_threshold_pct for zigzag threshold seeding. VCP
    # additionally consumes volume_trend_through_swings; the other 4
    # compute their own per-segment volume aggregates inline (no shared
    # primitive). Asserting falsely that HTF / DBW import
    # volume_trend_through_swings would create a brittle invariant the
    # detectors do not satisfy.
    expected_primitives_per_detector = {
        "vcp": (
            vcp,
            (
                "CandidateWindow",
                "current_stage",
                "extract_zigzag_swings",
                "volume_trend_through_swings",
                "adaptive_initial_threshold_pct",
            ),
        ),
        "flat_base": (
            flat_base,
            (
                "CandidateWindow",
                "current_stage",
                "extract_zigzag_swings",
                "adaptive_initial_threshold_pct",
            ),
        ),
        "cup_with_handle": (
            cup_with_handle,
            (
                "CandidateWindow",
                "current_stage",
                "extract_zigzag_swings",
                "adaptive_initial_threshold_pct",
            ),
        ),
        "high_tight_flag": (
            high_tight_flag,
            (
                "CandidateWindow",
                "current_stage",
                "extract_zigzag_swings",
                "adaptive_initial_threshold_pct",
            ),
        ),
        "double_bottom_w": (
            double_bottom_w,
            (
                "CandidateWindow",
                "current_stage",
                "extract_zigzag_swings",
                "adaptive_initial_threshold_pct",
            ),
        ),
    }

    for detector_name, (module, expected_primitives) in (
        expected_primitives_per_detector.items()
    ):
        source = inspect.getsource(module)
        for primitive in expected_primitives:
            assert primitive in source, (
                f"detector {detector_name!r} does not reference foundation "
                f"primitive {primitive!r} (cross-bundle pin invariant)"
            )

        # Verify the import statement specifically pulls from
        # swing.patterns.foundation (not a re-export elsewhere).
        assert "from swing.patterns.foundation import" in source, (
            f"detector {detector_name!r} does not import from "
            f"swing.patterns.foundation (cross-bundle pin invariant)"
        )
