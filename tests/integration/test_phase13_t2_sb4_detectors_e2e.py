"""Phase 13 T2.SB4 T-A.4.6 - E2E integration for detectors batch 2 (HTF + DBW).

Per plan section G.6 T-A.4.6:

- Step 1: Write fast E2E test seeding 5 candidate windows (one per pattern
  class); invoking ``_step_pattern_detect``; asserting 5
  ``pattern_evaluations`` rows per window per applicable pattern.
- Step 2: Run E2E; verify PASS.
- Step 3: Commit.

T2.SB4 extends the detector registry from 3 (vcp + flat_base +
cup_with_handle) to 5 by adding ``high_tight_flag`` + ``double_bottom_w``
via the single-line registry tuple extension at
``swing/pipeline/runner.py:_pattern_detect_registry``. This E2E exercises
the integration end-to-end: seed 5 aplus candidates (the 5 V1 detector
pattern classes per spec section 3.0 DETECTOR_PATTERN_CLASSES LOCK) +
invoke ``_step_pattern_detect`` + assert 25 ``pattern_evaluations`` rows
(5 tickers x 5 detectors per ticker; emit-when-zero policy preserved per
T2.SB3 architectural lock).

LOCKs (per dispatch brief Section 6):
- L1 verbatim spec section 3.6 + plan section G.6 T-A.4.6.
- L3 NO INSERT OR REPLACE on pattern_evaluations writes (preserved at
  runner.py level; this E2E asserts the resulting behavior shape, NOT
  the SQL form).
- L6 branch base = af2ed5b.
- ASCII-only.

Mirrors the fixture-setup pattern from
``tests/integration/test_phase13_t2_sb3_detectors_e2e.py`` -- in-memory
sqlite3 conn via ``ensure_schema``; seed evaluation_runs + candidates;
stub OhlcvCache + Lease; production-shape invocation of
``_step_pattern_detect``.
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

from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema
from swing.data.models import (
    DETECTOR_PATTERN_CLASSES,
    Candidate,
    CriterionResult,
    EvaluationRun,
)
from swing.data.repos.candidates import (
    insert_candidates,
    insert_evaluation_run,
)
from swing.pipeline.runner import _step_pattern_detect

# ---------------------------------------------------------------------------
# Fixture builders.
#
# We synthesize a VCP-shape passing fixture (mirror of the T2.SB3 E2E
# fixture). The same fixture flows through all 5 detectors; many will
# return ``geometric_score = 0.0`` because the fixture isn't shaped for
# their criteria -- this is the EXPECTED behavior of the emit-when-zero
# architectural lock (T2.SB3). T2.SB4 inherits this discipline: every
# (ticker, pattern_class) tuple produces a row regardless of score.
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
    """Spec section 10.1 CVGI hypothetical reconstruction.

    Mirror of the T2.SB3 E2E fixture. Bars flow through all 5 detectors;
    HTF + DBW return geometric_score=0.0 because the fixture isn't shaped
    for their criteria, but rows ARE emitted (emit-when-zero policy).
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
# Seeding helpers.
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
            "tok-t2sb4-e2e-1",
        ),
    )
    return int(cur.lastrowid)


def _seed_evaluation_run(
    conn: sqlite3.Connection,
    *,
    action_session_date: str = "2026-05-20",
    tickers_evaluated: int = 5,
) -> int:
    return insert_evaluation_run(
        conn,
        EvaluationRun(
            id=None,
            run_ts=f"{action_session_date}T18:00:00",
            data_asof_date="2026-05-19",
            action_session_date=action_session_date,
            finviz_csv_path=None,
            tickers_evaluated=tickers_evaluated,
            aplus_count=tickers_evaluated,
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


def test_phase13_t2_sb4_detectors_e2e_fast(tmp_path: Path) -> None:
    """End-to-end exercise of ``_step_pattern_detect`` with all 5 detectors.

    Seeds 5 aplus tickers (one symbolically associated with each V1
    detector pattern class per spec section 3.0 DETECTOR_PATTERN_CLASSES
    LOCK). Each ticker carries the spec section 10.1 CVGI VCP-passing
    fixture (varied start dates so each ticker has distinct bar indices).
    The step runs each ticker through all 5 detectors per recon section
    4.4, emitting one ``pattern_evaluations`` row per (ticker,
    pattern_class) tuple via the registry iteration at
    ``swing/pipeline/runner.py:_pattern_detect_registry``.

    T2.SB4 extends T2.SB3's 3-detector registry to 5 by adding
    ``high_tight_flag`` + ``double_bottom_w`` (plan section G.6 T-A.4.3).
    This E2E proves the wiring landed end-to-end at the
    ``_step_pattern_detect`` integration boundary.

    Assertions:
    - 25 rows total (5 tickers x 5 detectors per ticker).
    - Every row's ``pattern_class`` is in ``DETECTOR_PATTERN_CLASSES``.
    - All 5 detector classes are present (HTF + DBW prove T2.SB4 wiring).
    - Every row has parseable + non-empty
      ``structural_evidence_json`` (dict shape).
    - Every row has parseable + non-empty
      ``feature_distribution_log_json`` (FeatureDistributionLog shape).
    - For non-DBW detectors (vcp, flat_base, cup_with_handle,
      high_tight_flag): ``composite_score == geometric_score`` (T2.SB3
      LOCK; template matching arrives at T2.SB5) and
      ``0.0 <= geometric_score <= 1.0``.
    - For DBW (double_bottom_w): evidence-tier
      ``0.0 <= geometric_score <= 1.10`` (rule-tier criteria up to 1.0
      plus criterion #8 undercut bonus +0.10 per spec section 5.8 line
      718 + section 10.5 line 1325) AND composite-tier
      ``composite_score == min(1.0, geometric_score)`` per spec section
      5.8 line 712 wrap (Codex R1 M1 + R2 Critical #1 + R3 Major #1
      LOCK; composite always in [0.0, 1.0]).
    - ``template_match_score`` is None on every row (pre-T2.SB5).
    - No duplicate ``(pipeline_run_id, ticker, pattern_class)`` tuples
      (idempotency / L3 no-INSERT-OR-REPLACE preservation).

    Note (mirrors T2.SB3 E2E note): the step picks ``windows[-1]`` for
    the candidate window; the section-10.1 fixture lands at score 0.0
    through the step for VCP (criterion #6 base_duration), and the
    non-VCP-shaped detectors (flat_base, cup_with_handle, HTF, DBW)
    also typically land at 0.0 on this fixture. Emit-when-zero policy
    is the contract under test -- rows MUST be emitted regardless.
    """
    db_path = tmp_path / "phase13_t2sb4_fast_e2e.db"
    conn = ensure_schema(db_path)

    pipeline_run_id = _seed_pipeline_run(conn)
    eval_run_id = _seed_evaluation_run(conn, tickers_evaluated=5)

    # One ticker per V1 pattern class (5 tickers total). Tickers are
    # purely symbolic -- all 5 detectors run on each ticker's bars
    # regardless of ticker name.
    tickers = ["VCP1", "FLT1", "CUP1", "HTF1", "DBW1"]
    bars_by_ticker = {
        t: _vcp_passing_bars(
            start=date(2026, 1, 5)
            + pd.Timedelta(days=offset).to_pytimedelta()
        )
        for t, offset in zip(tickers, [0, 1, 2, 3, 4], strict=True)
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

    # Assertion 1: 25 rows total (5 tickers x 5 detectors).
    row_count = conn.execute(
        "SELECT COUNT(*) FROM pattern_evaluations WHERE pipeline_run_id = ?",
        (pipeline_run_id,),
    ).fetchone()[0]
    assert row_count == 25, (
        f"Expected 25 pattern_evaluations rows (5 tickers x 5 detectors "
        f"per T-A.4.3 registry extension); got {row_count}"
    )

    # Assertion 2: every row's pattern_class is in
    # DETECTOR_PATTERN_CLASSES + all 5 classes are present (proves the
    # registry iteration covered all detectors -- HTF + DBW landed).
    pattern_classes_present = {
        r[0] for r in conn.execute(
            "SELECT DISTINCT pattern_class FROM pattern_evaluations "
            "WHERE pipeline_run_id = ?",
            (pipeline_run_id,),
        ).fetchall()
    }
    assert pattern_classes_present == set(DETECTOR_PATTERN_CLASSES), (
        f"Expected all 5 DETECTOR_PATTERN_CLASSES present "
        f"({set(DETECTOR_PATTERN_CLASSES)}); got {pattern_classes_present}"
    )
    # T2.SB4 wiring proof: HTF + DBW MUST be in the result set.
    assert "high_tight_flag" in pattern_classes_present, (
        "T2.SB4 T-A.4.3 wiring: high_tight_flag detector did not emit rows; "
        "registry tuple at swing/pipeline/runner.py:_pattern_detect_registry "
        "did not extend to HTF"
    )
    assert "double_bottom_w" in pattern_classes_present, (
        "T2.SB4 T-A.4.3 wiring: double_bottom_w detector did not emit rows; "
        "registry tuple at swing/pipeline/runner.py:_pattern_detect_registry "
        "did not extend to DBW"
    )

    # Assertion 3: every (ticker, pattern_class) tuple uniquely present
    # 5 rows per ticker x 5 tickers = 25 unique tuples (no dupes).
    unique_tuples = conn.execute(
        "SELECT DISTINCT ticker, pattern_class FROM pattern_evaluations "
        "WHERE pipeline_run_id = ?",
        (pipeline_run_id,),
    ).fetchall()
    assert len(unique_tuples) == 25, (
        f"Expected 25 unique (ticker, pattern_class) tuples; "
        f"got {len(unique_tuples)} (idempotency / L3 no-INSERT-OR-REPLACE "
        f"preservation)"
    )

    # Assertion 4: every row has parseable structural_evidence_json +
    # feature_distribution_log_json + composite_score == geometric_score
    # + template_match_score IS NULL (T2.SB3 LOCK preserved through SB4).
    rows = conn.execute(
        "SELECT ticker, pattern_class, geometric_score, composite_score, "
        "structural_evidence_json, feature_distribution_log_json, "
        "template_match_score "
        "FROM pattern_evaluations WHERE pipeline_run_id = ? "
        "ORDER BY ticker, pattern_class",
        (pipeline_run_id,),
    ).fetchall()
    assert len(rows) == 25
    for (
        ticker,
        pat_class,
        geom,
        comp,
        se_json,
        fdl_json,
        tm_score,
    ) in rows:
        # structural_evidence_json populated + parseable dict.
        assert se_json is not None and se_json != "", (
            f"structural_evidence_json empty for ({ticker}, {pat_class})"
        )
        se = json.loads(se_json)
        assert isinstance(se, dict), (
            f"structural_evidence_json not a dict for "
            f"({ticker}, {pat_class}): {type(se).__name__}"
        )
        assert len(se) > 0, (
            f"structural_evidence_json is empty dict for "
            f"({ticker}, {pat_class})"
        )
        # feature_distribution_log_json populated + parseable + carries
        # the FeatureDistributionLog shape (spec section D.7).
        assert fdl_json is not None and fdl_json != "", (
            f"feature_distribution_log_json empty for "
            f"({ticker}, {pat_class})"
        )
        fdl = json.loads(fdl_json)
        assert fdl["detector_class"] == pat_class, (
            f"feature_distribution_log_json.detector_class mismatch for "
            f"({ticker}, {pat_class}): got {fdl['detector_class']!r}"
        )
        assert "composite_score_histogram_bins" in fdl
        assert isinstance(fdl["composite_score_histogram_bins"], list)
        assert "smoothing_params" in fdl
        assert "universe_size" in fdl
        # composite_score == min(1.0, geometric_score) (T2.SB3 LOCK +
        # T2.SB4 Codex R2 Critical #1 clamp). Pre-T2.SB5 the composite
        # formula reduces to composite = min(1.0, geometric) since
        # template_match_score is None. DBW evidence may carry
        # geometric_score in [0.0, 1.10] (undercut bonus per spec
        # section 5.8 line 718 + section 10.5 line 1325); other 4
        # detectors carry geometric_score in [0.0, 1.0]. The composite
        # always clamps to [0.0, 1.0] -- otherwise
        # drift_logging._composite_score_histogram rejects the value
        # and aborts the entire Pass-2 emit loop for the run.
        if pat_class == "double_bottom_w":
            # DBW: evidence in [0.0, 1.10]; composite = min(1.0, geom).
            assert 0.0 <= geom <= 1.10, (
                f"DBW geometric_score {geom} outside [0.0, 1.10] "
                f"evidence-layer LOCK band for "
                f"({ticker}, {pat_class}); see spec section 5.8 line "
                f"718 + section 10.5 line 1325"
            )
            assert comp == pytest.approx(min(1.0, geom)), (
                f"DBW composite_score {comp} != min(1.0, {geom}) for "
                f"({ticker}, {pat_class}); Codex R2 Critical #1 "
                f"requires composite-layer clamp to [0.0, 1.0]"
            )
        else:
            # Other 4 detectors: evidence in [0.0, 1.0]; composite = geom.
            assert 0.0 <= geom <= 1.0, (
                f"geometric_score {geom} outside [0.0, 1.0] LOCK band "
                f"for ({ticker}, {pat_class})"
            )
            assert comp == pytest.approx(geom), (
                f"composite_score {comp} != geometric_score {geom} "
                f"for ({ticker}, {pat_class}); T2.SB3 LOCK requires "
                f"equality (geometric_score already <= 1.0 for "
                f"non-DBW detectors) until template matching lands "
                f"at T2.SB5"
            )
        # template_match_score is None until T2.SB5 lands template
        # matching.
        assert tm_score is None, (
            f"template_match_score expected None pre-T2.SB5; got "
            f"{tm_score!r} for ({ticker}, {pat_class})"
        )

    # Assertion 5: schema version v20 (T-A.1.1 baseline; T2.SB4 does
    # NOT change schema). Schema version is tracked in the
    # ``schema_version`` table (NOT ``PRAGMA user_version``) per
    # ``swing/data/db.py:current_version``.
    schema_version_row = conn.execute(
        "SELECT version FROM schema_version"
    ).fetchone()
    assert schema_version_row is not None, (
        "schema_version row missing; ensure_schema did not provision"
    )
    # T2.SB4 itself does NOT change schema; ensure_schema always provisions
    # the current HEAD. Track EXPECTED_SCHEMA_VERSION (the db.py constant) so
    # this assertion stays correct across migration bumps (v21 at T2.SB6c
    # post-migration 0021; v22 at Phase 14 Sub-bundle 2 post-migration 0022).
    assert schema_version_row[0] == EXPECTED_SCHEMA_VERSION, (
        f"Expected schema v{EXPECTED_SCHEMA_VERSION} (current db.py HEAD); got "
        f"v{schema_version_row[0]}"
    )

    conn.close()
