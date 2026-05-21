"""Phase 13 T2.SB3 T-A.3.8 - E2E + slow validation for detectors batch 1.

Per plan section G.4 T-A.3.8:

- Fast E2E (Step 1): seed 3 aplus candidates (with passing VCP fixtures);
  invoke ``_step_pattern_detect`` directly; assert ``pattern_evaluations``
  has 3 tickers x 3 detector classes = 9 rows; assert every row carries
  a parseable ``feature_distribution_log_json``; assert
  ``composite_score == geometric_score`` per recon section 8 LOCK
  (template matching lands at T2.SB5).
- Slow E2E (Step 2): exercise the actual ``detect_vcp`` against a
  synthesized CVGI-like fixture matching spec section 10.1 (3
  contractions 22% / 11% / 5.6%; pivot within 0.8% of base_top; volume
  declining; 32-day base duration). Assert ``geometric_score`` lands in
  ``[0.9, 1.0]``.

LOCKs (per dispatch brief Section 6):
- L1 verbatim spec 5.2 + 10.1 numbers.
- L2 detectors are PURE functions; this test exercises the
  ``_step_pattern_detect`` integration without mocking the step internals
  beyond stub OhlcvCache + stub Lease.
- L5 ASCII-only.
- L7 PatternEvaluation dataclass shape contract verified.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.data.models import Candidate, CriterionResult, EvaluationRun
from swing.data.repos.candidates import (
    insert_candidates,
    insert_evaluation_run,
)
from swing.patterns.foundation import CandidateWindow
from swing.patterns.vcp import detect_vcp
from swing.pipeline.runner import _step_pattern_detect

# ---------------------------------------------------------------------------
# Fixture builders (mirror unit-test passing-fixture construction so the
# fast E2E exercises the production code path with deterministic VCP-
# passing bars; cf. tests/patterns/test_vcp.py::_bars_passing_all_criteria).
# ---------------------------------------------------------------------------


def _bars_from_segments(
    segments: list[tuple[float, float, int]],
    start: date,
) -> pd.DataFrame:
    """Linear-interpolate ``segments`` into OHLCV bars.

    Each segment is ``(start_close, end_close, num_bars)``; consecutive
    segments share the prior segment's endpoint (no duplication).
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
    highs = closes_arr * 1.005
    lows = closes_arr * 0.995
    opens = closes_arr
    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes_arr,
            "Volume": np.full(n_total, 1_000_000.0),
        },
        index=idx,
    )


def _vcp_passing_bars(start: date = date(2026, 1, 5)) -> pd.DataFrame:
    """Spec section 10.1 CVGI hypothetical: 7/7 hard + soft criteria
    pass; geometric_score == 1.0.

    Mirror of tests/patterns/test_vcp.py::_bars_passing_all_criteria. The
    fast E2E uses 3 instances of this fixture (varied start dates so the
    bar index spans differ); the slow E2E uses 1 instance + asserts the
    score lands in [0.9, 1.0] per spec section 10.1.
    """
    segments = [
        (3.40, 3.50, 5),       # filler pre-uptrend
        (3.50, 5.50, 55),      # prior uptrend ~57% gain over ~7.8 weeks
        (5.50, 4.29, 8),       # C1 22% depth
        (4.29, 5.42, 5),       # rally to next peak 5.42
        (5.42, 4.77, 9),       # C2 ~12% depth
        (4.77, 5.34, 4),       # rally to base_top 5.34
        (5.34, 5.05, 7),       # C3 ~5.4% depth
        (5.05, 5.30, 3),       # final rally to pivot 5.30 (within 0.75% of 5.34)
    ]
    bars = _bars_from_segments(segments, start=start)
    # Per-phase volume tagging: contractions decline (1.5M -> 1.1M -> 0.75M);
    # uptrend + rallies = baseline 1M.
    n = len(bars)
    vols = np.full(n, 1_000_000.0)
    idx_cursor = 0
    seg_indices: list[tuple[int, int]] = []
    for i, (_, _, count) in enumerate(segments):
        if i == 0:
            seg_indices.append((0, count - 1))
            idx_cursor = count - 1
        else:
            seg_indices.append((idx_cursor + 1, idx_cursor + count))
            idx_cursor += count
    # Contraction segments (downswings) are segments 2, 4, 6 (0-indexed).
    c1_lo, c1_hi = seg_indices[2]
    c2_lo, c2_hi = seg_indices[4]
    c3_lo, c3_hi = seg_indices[6]
    vols[c1_lo:c1_hi + 1] = 1_500_000.0
    vols[c2_lo:c2_hi + 1] = 1_100_000.0
    vols[c3_lo:c3_hi + 1] = 750_000.0
    bars["Volume"] = vols
    return bars


# ---------------------------------------------------------------------------
# Stubs for OhlcvCache + Lease (test-stub path inside _step_pattern_detect).
# ---------------------------------------------------------------------------


class _StubOhlcvCache:
    """Duck-typed stub for ``OhlcvCache.get_or_fetch``."""

    def __init__(self, bars_by_ticker: dict[str, pd.DataFrame]):
        self._bars = bars_by_ticker

    def get_or_fetch(self, *, ticker: str, window_days: int = 200) -> pd.DataFrame:
        df = self._bars.get(ticker.upper())
        if df is None:
            raise ValueError(f"No bars stub for {ticker}")
        return df


class _StubLease:
    """Stub Lease yielding the shared conn through ``fenced_write``."""

    def __init__(self, conn: sqlite3.Connection, run_id: int):
        self._conn = conn
        self.run_id = run_id

    def fenced_write(self):
        @contextmanager
        def _cm():
            yield self._conn

        return _cm()


# ---------------------------------------------------------------------------
# Seeding helpers (production-shape rows: pipeline_runs + evaluation_runs +
# candidates with trend_template 8/8 pass criteria so ``current_stage``
# returns ``stage_2``).
# ---------------------------------------------------------------------------


def _seed_pipeline_run(
    conn: sqlite3.Connection, *, action_session_date: str = "2026-05-20"
) -> int:
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, trigger, data_asof_date, action_session_date,
             state, lease_token)
        VALUES (?, 'manual', ?, ?, 'running', ?)
        """,
        (
            f"{action_session_date}T18:00:00",
            "2026-05-19",
            action_session_date,
            "tok-e2e-1",
        ),
    )
    return int(cur.lastrowid)


def _seed_evaluation_run(
    conn: sqlite3.Connection, *, action_session_date: str = "2026-05-20"
) -> int:
    return insert_evaluation_run(
        conn,
        EvaluationRun(
            id=None,
            run_ts=f"{action_session_date}T18:00:00",
            data_asof_date="2026-05-19",
            action_session_date=action_session_date,
            finviz_csv_path=None,
            tickers_evaluated=3,
            aplus_count=3,
            watch_count=0,
            skip_count=0,
            excluded_count=0,
            error_count=0,
        ),
    )


def _aplus_candidate_with_stage_2(ticker: str) -> Candidate:
    """Build an aplus Candidate with 8 trend_template pass criteria so
    ``current_stage`` resolves to ``stage_2`` per spec section 5.1.5.
    """
    criteria = tuple(
        CriterionResult(
            criterion_name=f"TT{i}",
            layer="trend_template",
            result="pass",
            value=None,
            rule=None,
        )
        for i in range(1, 9)
    )
    return Candidate(
        ticker=ticker,
        bucket="aplus",
        close=5.30,
        pivot=5.30,
        initial_stop=4.80,
        adr_pct=3.5,
        tight_streak=3,
        pullback_pct=5.0,
        prior_trend_pct=57.0,
        rs_rank=90,
        rs_return_12w_vs_spy=18.0,
        rs_method="universe",
        pattern_tag=None,
        notes=None,
        criteria=criteria,
    )


# ===========================================================================
# Fast E2E
# ===========================================================================


def test_phase13_t2_sb3_detectors_e2e_fast(tmp_path: Path) -> None:
    """End-to-end exercise of ``_step_pattern_detect`` over 3 aplus tickers.

    Seeds 3 tickers with the spec section 10.1 CVGI VCP-passing fixture
    (varied start dates so each ticker has distinct bar indices). The
    step runs each ticker through all 3 detectors per recon section 4.4,
    emitting one ``pattern_evaluations`` row per (ticker, pattern_class)
    tuple.

    Assertions:
    - 9 rows total (3 tickers x 3 detector classes).
    - Every row carries a non-empty, parseable
      ``feature_distribution_log_json`` with the FeatureDistributionLog
      dataclass shape (spec section D.7).
    - ``composite_score == geometric_score`` on every row (T2.SB3 LOCK;
      template-match score is None until T2.SB5).
    - All ``geometric_score`` values lie in ``[0.0, 1.0]`` per spec
      section 5.2 LOCK + dataclass ``__post_init__`` invariant.

    Note: per recon section 7 + ``_step_pattern_detect`` line 1397, the
    step picks ``windows[-1]`` (most-recent zigzag down-swing). The
    section-10.1 fixture emits 3 candidate windows (one per contraction
    trough); ``windows[-1]`` anchors the C3 trough which yields too
    short a base forward and fails criterion #6 (base_duration >= 21d)
    -> geometric_score = 0.0. This is the EXPECTED V1 behavior of the
    integration step; the slow E2E below exercises the high-score path
    directly via ``detect_vcp`` with the correct base-start anchor.
    Validating high scores end-to-end through the step is a V2-deferred
    multi-anchor concern (recon section 7 LOCK).
    """
    db_path = tmp_path / "phase13_t2sb3_fast_e2e.db"
    conn = ensure_schema(db_path)

    pipeline_run_id = _seed_pipeline_run(conn)
    eval_run_id = _seed_evaluation_run(conn)

    tickers = ["AAA", "BBB", "CCC"]
    bars_by_ticker = {
        t: _vcp_passing_bars(start=date(2026, 1, 5) + pd.Timedelta(days=offset).to_pytimedelta())
        for t, offset in zip(tickers, [0, 1, 2], strict=True)
    }
    for ticker in tickers:
        insert_candidates(
            conn,
            eval_run_id,
            [_aplus_candidate_with_stage_2(ticker)],
        )
    conn.commit()

    cache = _StubOhlcvCache(bars_by_ticker)
    lease = _StubLease(conn, run_id=pipeline_run_id)

    _step_pattern_detect(
        cfg=None,
        lease=lease,
        eval_run_id=eval_run_id,
        ohlcv_cache=cache,
    )

    # Assertion 1: 15 rows (3 tickers x 5 detector classes per T2.SB4
    # T-A.4.3; T2.SB3 originally shipped 3 detectors -> 9 rows).
    row_count = conn.execute(
        "SELECT COUNT(*) FROM pattern_evaluations WHERE pipeline_run_id = ?",
        (pipeline_run_id,),
    ).fetchone()[0]
    assert row_count == 15, (
        f"Expected 15 pattern_evaluations rows (3 tickers x 5 detectors "
        f"per T-A.4.3); got {row_count}"
    )

    # Assertion 2: every row's pattern_class is one of the 5 expected
    # (T-A.4.3 added high_tight_flag + double_bottom_w).
    pattern_classes_present = {
        r[0] for r in conn.execute(
            "SELECT DISTINCT pattern_class FROM pattern_evaluations "
            "WHERE pipeline_run_id = ?",
            (pipeline_run_id,),
        ).fetchall()
    }
    assert pattern_classes_present == {
        "vcp",
        "flat_base",
        "cup_with_handle",
        "high_tight_flag",
        "double_bottom_w",
    }

    # Assertion 3: every row has parseable feature_distribution_log_json
    # AND composite_score == geometric_score (T2.SB3 LOCK).
    rows = conn.execute(
        "SELECT ticker, pattern_class, geometric_score, composite_score, "
        "feature_distribution_log_json, template_match_score "
        "FROM pattern_evaluations WHERE pipeline_run_id = ? "
        "ORDER BY ticker, pattern_class",
        (pipeline_run_id,),
    ).fetchall()
    assert len(rows) == 15
    for ticker, pat_class, geom, comp, fdl_json, tm_score in rows:
        assert fdl_json is not None and fdl_json != "", (
            f"feature_distribution_log_json empty for ({ticker}, {pat_class})"
        )
        fdl = json.loads(fdl_json)
        assert fdl["detector_class"] == pat_class
        assert "composite_score_histogram_bins" in fdl
        assert isinstance(fdl["composite_score_histogram_bins"], list)
        assert "smoothing_params" in fdl
        assert "universe_size" in fdl
        # composite_score == geometric_score (T2.SB3 LOCK; no template
        # matching yet).
        assert comp == pytest.approx(geom), (
            f"composite_score {comp} != geometric_score {geom} for "
            f"({ticker}, {pat_class}); T2.SB3 LOCK requires equality"
        )
        # template_match_score must be None until T2.SB5.
        assert tm_score is None

    # Assertion 4: every geometric_score lies in [0.0, 1.0] per spec
    # section 5.2 LOCK + dataclass __post_init__ invariant. (The step
    # picks ``windows[-1]`` which anchors a near-end-of-base swing; the
    # base forward window is too short to satisfy criterion #6, so the
    # section-10.1 fixture lands at 0.0 through the step; the slow E2E
    # below exercises the high-score path directly.)
    scores = conn.execute(
        "SELECT geometric_score FROM pattern_evaluations "
        "WHERE pipeline_run_id = ?",
        (pipeline_run_id,),
    ).fetchall()
    for (score,) in scores:
        assert 0.0 <= score <= 1.0, (
            f"geometric_score {score} outside [0.0, 1.0] LOCK band"
        )

    conn.close()


# ===========================================================================
# Slow E2E (spec section 10.1 worked example)
# ===========================================================================


@pytest.mark.slow
def test_phase13_t2_sb3_vcp_detection_against_cvgi_like_fixture_geometric_score_in_0_9_to_1_0(
    tmp_path: Path,
) -> None:
    """Direct ``detect_vcp`` invocation against the section-10.1 CVGI
    hypothetical reconstruction fixture.

    Per spec section 10.1 LOCK: 7/7 hard + soft criteria pass; criterion
    #8 (breakout) is optional. The synthesized fixture does NOT include a
    post-base breakout bar, so criterion #8 is False; the geometric
    score = 7/7 = 1.0 (criterion #8 does not reduce the score when
    absent per spec section 5.2 line 547 LOCK + line 1256 ("not observed
    pre-2026-05-15 in scenario")). Assertion uses ``[0.9, 1.0]`` band per
    dispatch brief Step 2; the fixture should land at 1.0.

    Fixture: synthesized (NOT loaded from operator's archive). The brief
    permits either path; synthesized is deterministic + ASCII-safe + does
    not require external file presence.
    """
    db_path = tmp_path / "phase13_t2sb3_slow_e2e.db"
    conn = ensure_schema(db_path)

    # Stage-2 candidate seeding so ``current_stage`` returns 'stage_2'.
    eval_run_id = _seed_evaluation_run(conn, action_session_date="2026-01-05")
    insert_candidates(
        conn, eval_run_id, [_aplus_candidate_with_stage_2("CVGI")]
    )
    conn.commit()

    bars = _vcp_passing_bars(start=date(2026, 1, 5))
    # Base starts at index 60 (end of uptrend segment per the section-10.1
    # construction).
    base_start_dt = bars.index[60].date()
    window = CandidateWindow(
        ticker="CVGI",
        timeframe="daily",
        start_date=base_start_dt,
        end_date=bars.index[-1].date(),
        anchor_date=base_start_dt,
        anchor_reason="zigzag_pivot:cvgi_section_10_1_test_anchor",
    )

    evidence = detect_vcp(
        bars,
        window,
        conn=conn,
        ticker="CVGI",
        asof_date=bars.index[-1].date(),
    )

    # Per spec section 10.1 LOCK: geometric_score in [0.9, 1.0].
    assert 0.9 <= evidence.geometric_score <= 1.0, (
        f"Section 10.1 fixture expected geometric_score in [0.9, 1.0]; "
        f"got {evidence.geometric_score}. criteria_pass={evidence.criteria_pass}"
    )
    # Spec section 10.1 explicit per-criterion expectations.
    assert evidence.criteria_pass["criterion_1"] is True   # stage_2
    assert evidence.criteria_pass["criterion_2"] is True   # prior uptrend
    assert evidence.criteria_pass["criterion_3"] is True   # monotonic
    assert evidence.criteria_pass["criterion_4"] is True   # depth bounds
    assert evidence.criteria_pass["criterion_5"] is True   # volume decline
    assert evidence.criteria_pass["criterion_6"] is True   # base duration
    assert evidence.criteria_pass["criterion_7"] is True   # pivot within top

    conn.close()
