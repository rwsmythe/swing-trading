"""Phase 13 T2.SB5 T-A.5.6 closer - fast E2E for template matching layer.

Per plan section G.7 T-A.5.6 + brief section 2 T-A.5.6: invokes
``_step_pattern_detect`` with planted pattern_exemplars + multiple
aplus tickers; asserts that pattern_evaluations rows carry the full
spec section 5.8 formula-derived composite_score (geometric + template).

Mirrors the shape of `tests/integration/test_phase13_t2_sb4_detectors_e2e.py`
(stub OhlcvCache + stub Lease + direct ``_step_pattern_detect`` invocation).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
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
from swing.patterns.composite import compute_composite_score
from swing.pipeline.runner import _step_pattern_detect


def _build_bars(start: date = date(2025, 6, 1), n_days: int = 180) -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        [pd.Timestamp(start) + pd.Timedelta(days=i) for i in range(n_days)]
    )
    closes = np.linspace(10.0, 15.0, n_days)
    rng = np.random.RandomState(seed=42)
    closes = closes + rng.normal(0.0, 0.25, n_days)
    closes = np.maximum(closes, 0.5)
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes * 1.01,
            "Low": closes * 0.99,
            "Close": closes,
            "Volume": np.full(n_days, 1_000_000.0),
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
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) VALUES "
        "(?, 'manual', ?, ?, 'running', ?)",
        (
            "2026-05-21T18:00:00",
            "2026-05-20",
            "2026-05-21",
            "tok-t2sb5-e2e",
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
            tickers_evaluated=5,
            aplus_count=5,
            watch_count=0,
            skip_count=0,
            excluded_count=0,
            error_count=0,
        ),
    )


def _seed_aplus_candidate(
    conn: sqlite3.Connection, eval_run_id: int, *, ticker: str
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
    ticker: str,
    pattern_class: str,
    quality_grade: int = 5,
) -> int:
    return insert_exemplar(
        conn,
        PatternExemplar(
            id=None,
            ticker=ticker,
            timeframe="daily",
            start_date="2025-11-15",
            end_date="2025-11-25",
            proposed_pattern_class=pattern_class,
            final_decision="confirmed",
            label_source="curated_gold",
            structural_evidence_json="{}",
            created_at="2025-11-26T00:00:00",
            created_by="operator",
            quality_grade=quality_grade,
            gold_validated_at="2025-11-26T00:00:00",
            geometric_score_json="{}",
            labeler_evidence_json="{}",
        ),
    )


def test_phase13_t2_sb5_template_matching_e2e(tmp_path: Path) -> None:
    """T-A.5.6 fast E2E: 5 candidates x 5 detectors x planted exemplars.

    Plant 5 aplus candidates (A, B, C, D, E) + 5 exemplars (one per
    pattern_class on ticker HIST). Force all 5 detectors to return
    geometric_score=0.65 via stub registry so the pre-gate passes for
    every (candidate, pattern_class) cell.

    Assert:
    - exactly 5 * 5 = 25 pattern_evaluations rows written.
    - template_match_score is populated (non-NULL) on every row.
    - composite_score equals compute_composite_score(0.65, tm) for each
      row's (geometric, template_match) pair (per spec section 5.8).
    - template_match_nearest_exemplar_ids_json is parseable JSON list
      containing 1-3 exemplar IDs from the planted corpus.
    - feature_distribution_log_json is parseable (drift_log fires
      without histogram-bounds ValueError on the post-template
      composite universe).
    """
    db_path = tmp_path / "phase13_t2sb5_e2e.db"
    conn = ensure_schema(db_path)
    pipeline_run_id = _seed_pipeline_run(conn)
    eval_run_id = _seed_evaluation_run(conn)

    # 5 candidate tickers.
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    for t in tickers:
        _seed_aplus_candidate(conn, eval_run_id, ticker=t)
    # 5 exemplars (one per pattern_class) on a "HIST" ticker.
    planted_ids: dict[str, int] = {}
    for pc in DETECTOR_PATTERN_CLASSES:
        planted_ids[pc] = _seed_exemplar(
            conn, ticker="HIST", pattern_class=pc, quality_grade=5
        )
    conn.commit()

    bars = _build_bars()
    cache = _StubOhlcvCache({t: bars for t in (*tickers, "HIST")})
    lease = _StubLease(conn, run_id=pipeline_run_id)

    @dataclass(frozen=True)
    class _SyntheticEvidence:
        geometric_score: float = 0.65
        criteria_pass: dict | None = None

        def __post_init__(self):
            if self.criteria_pass is None:
                object.__setattr__(self, "criteria_pass", {})

    def _stub_detector(bars, window, **kwargs):
        return _SyntheticEvidence(geometric_score=0.65, criteria_pass={"ok": True})

    stub_registry = tuple(
        (_stub_detector, pc, f"{pc}@v0.0.e2e")
        for pc in DETECTOR_PATTERN_CLASSES
    )

    with patch(
        "swing.pipeline.runner._pattern_detect_registry",
        return_value=stub_registry,
    ):
        _step_pattern_detect(
            cfg=None,
            lease=lease,
            eval_run_id=eval_run_id,
            ohlcv_cache=cache,
        )

    rows = conn.execute(
        "SELECT ticker, pattern_class, geometric_score, composite_score, "
        "template_match_score, template_match_nearest_exemplar_ids_json, "
        "feature_distribution_log_json "
        "FROM pattern_evaluations "
        "WHERE pipeline_run_id = ? "
        "ORDER BY ticker, pattern_class",
        (pipeline_run_id,),
    ).fetchall()
    assert len(rows) == 25, (
        f"expected 5 tickers * 5 detectors = 25 rows; got {len(rows)}"
    )
    for ticker, pc, geo, composite, tm, tm_ids_json, fdl_json in rows:
        assert ticker in tickers
        assert pc in DETECTOR_PATTERN_CLASSES
        # Geometric_score persisted as the synthetic value (0.65).
        assert geo == pytest.approx(0.65, abs=1e-9), (
            f"ticker={ticker} pc={pc} geo={geo}"
        )
        # template_match_score must be populated (planted exemplar +
        # pre-gate passes).
        assert tm is not None, (
            f"ticker={ticker} pc={pc} has NULL template_match_score "
            "despite planted exemplar"
        )
        assert 0.0 <= float(tm) <= 1.0
        # composite_score = compute_composite_score(0.65, tm) per
        # spec section 5.8.
        expected_composite = compute_composite_score(
            geometric=0.65, template_match=float(tm)
        )
        assert composite == pytest.approx(expected_composite, abs=1e-9), (
            f"ticker={ticker} pc={pc} composite={composite} != "
            f"expected={expected_composite}"
        )
        # nearest_exemplar_ids_json is a parseable list containing
        # the planted exemplar's id.
        assert tm_ids_json is not None
        nearest_ids = json.loads(tm_ids_json)
        assert isinstance(nearest_ids, list)
        assert planted_ids[pc] in nearest_ids, (
            f"ticker={ticker} pc={pc} did not match planted exemplar "
            f"{planted_ids[pc]}; got {nearest_ids}"
        )
        # drift_log JSON parseable (no histogram ValueError).
        assert fdl_json is not None and fdl_json != ""
        fdl = json.loads(fdl_json)
        assert "composite_score_histogram_bins" in fdl

    conn.close()
