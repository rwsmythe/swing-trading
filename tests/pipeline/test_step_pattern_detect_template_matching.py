"""Phase 13 T2.SB5 T-A.5.4 - `_step_pattern_detect` template matching tests.

Per plan section G.7 T-A.5.4 + brief section 2 T-A.5.4 acceptance criteria.

Tests the integration of:
- match_forward invocation per detector verdict (geometric_score >= 0.4 pre-gate)
- template_match_score + template_match_nearest_exemplar_ids_json persistence
- composite_score recomputed via compute_composite_score(geometric, template_match)
- Backward-compat: empty exemplar corpus -> template_match_score IS NULL +
  composite_score = min(1.0, geometric_score) (pre-T2.SB5 LOCK preserved)
- Forward-binding (T2.SB4 R2 Critical #1): DBW evidence geometric=1.10 +
  template=1.0 -> composite_score column = 1.0 (clamped via
  compute_composite_score; drift_logging histogram doesn't error).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.data.models import (
    DETECTOR_PATTERN_CLASSES,
    Candidate,
    EvaluationRun,
    PatternExemplar,
)
from swing.data.repos.candidates import (
    insert_candidates,
    insert_evaluation_run,
)
from swing.data.repos.pattern_exemplars import insert_exemplar
from swing.pipeline.runner import _step_pattern_detect


def _build_bars(start: date = date(2025, 6, 1), n_days: int = 180) -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        [pd.Timestamp(start) + pd.Timedelta(days=i) for i in range(n_days)]
    )
    closes = np.linspace(10.0, 15.0, n_days)
    rng = np.random.RandomState(seed=42)
    closes = closes + rng.normal(0.0, 0.25, n_days)
    closes = np.maximum(closes, 0.5)
    highs = closes * 1.01
    lows = closes * 0.99
    opens = closes
    volumes = np.full(n_days, 1_000_000.0)
    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        },
        index=idx,
    )


class _StubOhlcvCache:
    def __init__(self, bars_by_ticker: dict[str, pd.DataFrame]):
        self._bars = bars_by_ticker

    def get_or_fetch(self, *, ticker: str, window_days: int = 200) -> pd.DataFrame:
        df = self._bars.get(ticker.upper())
        if df is None:
            raise ValueError(f"No data for {ticker}")
        return df


class _StubLease:
    def __init__(self, conn: sqlite3.Connection, run_id: int):
        self._conn = conn
        self.run_id = run_id

    def fenced_write(self):
        @contextmanager
        def _cm():
            yield self._conn

        return _cm()


def _seed_pipeline_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, trigger, data_asof_date, action_session_date,
             state, lease_token)
        VALUES (?, 'manual', ?, ?, 'running', ?)
        """,
        (
            "2026-05-21T18:00:00",
            "2026-05-20",
            "2026-05-21",
            "tok-t2sb5",
        ),
    )
    return int(cur.lastrowid)


def _seed_evaluation_run(conn: sqlite3.Connection) -> int:
    return insert_evaluation_run(
        conn,
        EvaluationRun(
            id=None,
            run_ts="2026-05-21T18:00:00",
            data_asof_date="2026-05-20",
            action_session_date="2026-05-21",
            finviz_csv_path=None,
            tickers_evaluated=1,
            aplus_count=1,
            watch_count=0,
            skip_count=0,
            excluded_count=0,
            error_count=0,
        ),
    )


def _seed_aplus_candidate(
    conn: sqlite3.Connection, eval_run_id: int, ticker: str = "ABC",
) -> None:
    cand = Candidate(
        ticker=ticker,
        bucket="aplus",
        close=15.0,
        pivot=15.1,
        initial_stop=13.5,
        adr_pct=2.5,
        tight_streak=3,
        pullback_pct=5.0,
        prior_trend_pct=40.0,
        rs_rank=85,
        rs_return_12w_vs_spy=12.0,
        rs_method="universe",
        pattern_tag=None,
        notes=None,
        criteria=tuple(),
    )
    insert_candidates(conn, eval_run_id, [cand])


def _seed_exemplar(
    conn: sqlite3.Connection,
    *,
    ticker: str = "HIST",
    pattern_class: str = "vcp",
    quality_grade: int = 5,
    # The candidate window from the synthetic bars + zigzag_pivot mode
    # spans ~10 bars at the right edge (2025-11-18 -> 2025-11-27); the
    # Sakoe-Chiba 10% band needs roughly length parity to be feasible.
    # Pick an exemplar window of similar length on a different historical
    # slice so template matching produces a finite DTW distance.
    start_date: str = "2025-11-15",
    end_date: str = "2025-11-25",
) -> int:
    return insert_exemplar(
        conn,
        PatternExemplar(
            id=None,
            ticker=ticker,
            timeframe="daily",
            start_date=start_date,
            end_date=end_date,
            proposed_pattern_class=pattern_class,
            final_decision="confirmed",
            label_source="curated_gold",
            structural_evidence_json="{}",
            created_at="2025-07-20T00:00:00",
            created_by="operator",
            quality_grade=quality_grade,
            gold_validated_at="2025-07-20T00:00:00",
            geometric_score_json="{}",
            labeler_evidence_json="{}",
        ),
    )


@pytest.fixture
def seeded_env(tmp_path: Path):
    db_path = tmp_path / "phase13_t2sb5_step.db"
    conn = ensure_schema(db_path)
    pipeline_run_id = _seed_pipeline_run(conn)
    eval_run_id = _seed_evaluation_run(conn)
    conn.commit()
    bars = _build_bars()
    cache = _StubOhlcvCache({"ABC": bars, "HIST": bars})
    lease = _StubLease(conn, run_id=pipeline_run_id)
    return {
        "conn": conn,
        "pipeline_run_id": pipeline_run_id,
        "eval_run_id": eval_run_id,
        "lease": lease,
        "cache": cache,
        "bars": bars,
        "db_path": db_path,
    }


# ============================================================================
# T-A.5.4 tests
# ============================================================================


def test_empty_exemplar_corpus_template_match_null_composite_min_geometric(
    seeded_env,
) -> None:
    """T-A.5.4 (a): no exemplars planted -> template_match_score IS NULL +
    composite_score = min(1.0, geometric_score) per spec section 5.8 line
    720 fallback LOCK (L5 forward-binding from T2.SB4 R2 Critical #1).
    """
    _seed_aplus_candidate(seeded_env["conn"], seeded_env["eval_run_id"])

    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    rows = seeded_env["conn"].execute(
        "SELECT pattern_class, geometric_score, composite_score, "
        "template_match_score, template_match_nearest_exemplar_ids_json "
        "FROM pattern_evaluations WHERE ticker = ? "
        "ORDER BY pattern_class",
        ("ABC",),
    ).fetchall()
    # 5 detectors per ticker (T-A.4.3 contract).
    assert len(rows) == 5
    for pattern_class, geo, composite, tm_score, tm_ids in rows:
        # Empty exemplar corpus -> NULL template_match values.
        assert tm_score is None, f"pattern={pattern_class}: tm_score={tm_score}"
        assert tm_ids is None, f"pattern={pattern_class}: tm_ids={tm_ids}"
        # Fallback composite = min(1.0, geometric_score).
        expected_composite = min(1.0, float(geo))
        assert composite == pytest.approx(expected_composite, abs=1e-9), (
            f"pattern={pattern_class}: composite={composite}, "
            f"geo={geo}, expected={expected_composite}"
        )


def test_with_matching_exemplar_template_match_populated(
    seeded_env,
) -> None:
    """T-A.5.4 (b): when a same-class exemplar is planted AND candidate
    has geometric_score >= 0.4, template_match_score becomes non-NULL +
    template_match_nearest_exemplar_ids_json is a parseable JSON list.

    Mocks the geometric_score to ensure the pre-gate fires (synthetic
    bars yield geometric_score 0.0 for most criteria so we need to
    explicitly elevate one detector's score for this test).
    """
    _seed_aplus_candidate(seeded_env["conn"], seeded_env["eval_run_id"])
    # Plant a VCP exemplar (same class as one of the 5 detectors).
    exemplar_id = _seed_exemplar(
        seeded_env["conn"],
        ticker="HIST",
        pattern_class="vcp",
        quality_grade=5,
    )
    seeded_env["conn"].commit()

    # Patch all detector functions to return a synthetic high-geometric_score
    # evidence so the pre-gate fires + match_forward is invoked.
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _SyntheticEvidence:
        geometric_score: float = 0.75
        criteria_pass: dict = None

        def __post_init__(self):
            if self.criteria_pass is None:
                object.__setattr__(self, "criteria_pass", {})

    def _stub_detector(bars, window, **kwargs):
        return _SyntheticEvidence(geometric_score=0.75, criteria_pass={"ok": True})

    # Patch the registry to use stubbed detectors for all 5 pattern_classes.
    stub_registry = tuple(
        (_stub_detector, pc, f"{pc}@v0.0.test")
        for pc in DETECTOR_PATTERN_CLASSES
    )
    with patch(
        "swing.pipeline.runner._pattern_detect_registry",
        return_value=stub_registry,
    ):
        _step_pattern_detect(
            cfg=None,
            lease=seeded_env["lease"],
            eval_run_id=seeded_env["eval_run_id"],
            ohlcv_cache=seeded_env["cache"],
        )

    # Examine the VCP row (matches the planted exemplar's pattern_class).
    row = seeded_env["conn"].execute(
        "SELECT geometric_score, composite_score, template_match_score, "
        "template_match_nearest_exemplar_ids_json "
        "FROM pattern_evaluations WHERE ticker = ? AND pattern_class = 'vcp'",
        ("ABC",),
    ).fetchone()
    assert row is not None, "no VCP row written"
    geo, composite, tm_score, tm_ids_json = row
    # geometric_score persists raw (0.75).
    assert geo == pytest.approx(0.75, abs=1e-9)
    # template_match_score must be populated (in [0, 1]) since a same-class
    # exemplar was planted + geometric_score >= 0.4 pre-gate passes.
    assert tm_score is not None, "template_match_score is NULL despite planted exemplar"
    assert 0.0 <= tm_score <= 1.0
    # template_match_nearest_exemplar_ids_json must be a parseable JSON list
    # containing the planted exemplar's id.
    assert tm_ids_json is not None
    ids = json.loads(tm_ids_json)
    assert isinstance(ids, list)
    assert exemplar_id in ids
    # composite_score must equal compute_composite_score(0.75, tm_score)
    # = min(1.0, 0.60 * 0.75 + 0.40 * tm_score).
    expected_composite = min(1.0, 0.60 * 0.75 + 0.40 * tm_score)
    assert composite == pytest.approx(expected_composite, abs=1e-9), (
        f"composite={composite}, expected={expected_composite} "
        f"(geo=0.75, tm={tm_score})"
    )


def test_dbw_undercut_clamp_composite_caps_at_one(
    seeded_env,
) -> None:
    """T-A.5.4 (DBW clamp regression): plant DBW evidence with
    geometric_score=1.10 (undercut bonus) + force template_match=1.0.

    Discriminating per `feedback_regression_test_arithmetic`:
    - pre-fix (no clamp): composite = 0.60 * 1.10 + 0.40 * 1.0 = 1.06
      -> drift_logging _composite_score_histogram raises ValueError
      (spec section 5.11 LOCK [0.0, 1.0]).
    - post-fix (clamp inside compute_composite_score): composite =
      min(1.0, 1.06) = 1.0 -> histogram succeeds.

    Test asserts: composite_score column = 1.0 (clamped); geometric_score
    column = 1.10 (raw evidence preserved); drift_log JSON parseable
    (histogram emitted without ValueError).
    """
    _seed_aplus_candidate(seeded_env["conn"], seeded_env["eval_run_id"])
    # Plant a DBW exemplar (matches the synthetic DBW evidence we'll inject).
    _seed_exemplar(
        seeded_env["conn"],
        ticker="HIST",
        pattern_class="double_bottom_w",
        quality_grade=5,
    )
    seeded_env["conn"].commit()

    # Synthetic DBW evidence with geometric_score=1.10 (undercut bonus).
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _DbwEvidence:
        geometric_score: float = 1.10
        criteria_pass: dict = None

        def __post_init__(self):
            if self.criteria_pass is None:
                object.__setattr__(self, "criteria_pass", {})

    def _stub_dbw_detector(bars, window, **kwargs):
        return _DbwEvidence(
            geometric_score=1.10,
            criteria_pass={"undercut_bonus": True},
        )

    # Synthetic non-DBW detectors return neutral score (0.0; below pre-gate
    # so they don't invoke template matching).
    @dataclass(frozen=True)
    class _NeutralEvidence:
        geometric_score: float = 0.0
        criteria_pass: dict = None

        def __post_init__(self):
            if self.criteria_pass is None:
                object.__setattr__(self, "criteria_pass", {})

    def _stub_neutral_detector(bars, window, **kwargs):
        return _NeutralEvidence(geometric_score=0.0, criteria_pass={})

    stub_registry = tuple(
        (
            _stub_dbw_detector if pc == "double_bottom_w" else _stub_neutral_detector,
            pc,
            f"{pc}@v0.0.test",
        )
        for pc in DETECTOR_PATTERN_CLASSES
    )

    # Force match_forward to return exactly similarity=1.0 (top-K max=1.0)
    # so the pre-clamp composite is 1.06 (would have triggered the drift_logging
    # ValueError pre-fix).
    from swing.patterns.template_matching import TemplateMatchHit

    def _stub_match_forward(*args, **kwargs):
        return [
            TemplateMatchHit(exemplar_id=1, distance=0.0, similarity_score=1.0)
        ]

    with patch(
        "swing.pipeline.runner._pattern_detect_registry",
        return_value=stub_registry,
    ), patch(
        "swing.pipeline.runner.match_forward",
        side_effect=_stub_match_forward,
    ):
        _step_pattern_detect(
            cfg=None,
            lease=seeded_env["lease"],
            eval_run_id=seeded_env["eval_run_id"],
            ohlcv_cache=seeded_env["cache"],
        )

    row = seeded_env["conn"].execute(
        "SELECT geometric_score, composite_score, template_match_score, "
        "feature_distribution_log_json "
        "FROM pattern_evaluations "
        "WHERE ticker = ? AND pattern_class = 'double_bottom_w'",
        ("ABC",),
    ).fetchone()
    assert row is not None, "no DBW row written"
    geo, composite, tm_score, fdl_json = row
    # geometric_score column persists RAW evidence (1.10).
    assert geo == pytest.approx(1.10, abs=1e-9)
    # composite_score column CLAMPED at 1.0 (post compute_composite_score).
    assert composite == 1.0, (
        f"composite={composite}; expected 1.0 (clamped from 1.06 pre-clamp)"
    )
    # template_match_score = 1.0 (per stubbed match_forward).
    assert tm_score == pytest.approx(1.0, abs=1e-9)
    # feature_distribution_log_json emitted (no ValueError from histogram).
    assert fdl_json is not None
    fdl = json.loads(fdl_json)
    assert "composite_score_histogram_bins" in fdl
