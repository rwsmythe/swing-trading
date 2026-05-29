"""Shared fixtures for Phase 14 Sub-bundle 2 temporal-log tests (plan section L.4).

T-2.4 / T-2.5 / T-2.6 import ONE definition each from here.

STEP-0 fix applied (vs plan section L.4 literal): pipeline_runs.trigger is
TEXT NOT NULL CHECK (trigger IN ('scheduled','manual')) (migration 0003). The
plan's section L.4 INSERT statements omitted the `trigger` column and would
fail the NOT NULL constraint; `trigger='manual'` is added to both seed INSERTs
here (mirrors the verified harness _seed_pipeline_run in
tests/pipeline/test_step_pattern_detect.py).
"""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import date
import numpy as np
import pandas as pd
import pytest
from swing.data.db import run_migrations
from swing.data.models import PatternDetectionEvent


@pytest.fixture
def tmp_db_v22(tmp_path):
    """File-backed v22 DB; returns (conn, db_path). The observe step opens its
    OWN connect(db_path) for reads, so the DB MUST be file-backed."""
    db_path = tmp_path / "t.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    return conn, db_path


def _build_bars(start: date = date(2025, 6, 1), n_days: int = 180) -> pd.DataFrame:
    """Bar shape PORTED from the verified detect-step harness
    (tests/pipeline/test_step_pattern_detect.py:_build_bars): a mild uptrend
    with seeded random wiggle so zigzag swings exist (the candidate-window
    generator + detectors need swings; a smooth linspace yields NO windows ->
    NO emits). DatetimeIndex + capitalized OHLCV; H > Close > L; Volume > 0."""
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
        {"Open": opens, "High": highs, "Low": lows, "Close": closes,
         "Volume": volumes}, index=idx)


class _StubOhlcvCache:
    """get_or_fetch(*, ticker, window_days) -> the canned frame for ticker."""
    def __init__(self, bars_by_ticker: dict[str, pd.DataFrame]):
        self._b = bars_by_ticker

    def get_or_fetch(self, *, ticker: str, window_days: int = 180) -> pd.DataFrame:
        if ticker not in self._b:
            raise KeyError(ticker)  # mimic a fetch miss
        return self._b[ticker]


class _FakeLease:
    """Minimal lease implementing only what the steps use: run_id, step(),
    fenced_write() (a contextmanager yielding a conn to the same file DB)."""
    def __init__(self, db_path, run_id: int, data_asof: str):
        self.db_path = db_path
        self.run_id = run_id
        self._data_asof = data_asof

    def step(self, name: str) -> None:  # no-op breadcrumb
        pass

    @contextmanager
    def fenced_write(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class _Cfg:
    """Lightweight cfg stub exposing only the attributes the steps read."""
    class _Paths:
        def __init__(self, db_path, cache_dir):
            self.db_path = db_path
            self.prices_cache_dir = cache_dir

    class _Pipeline:
        observe_max_pending_window_sessions = 30
        observe_max_post_trigger_window_sessions = 60

    def __init__(self, db_path, cache_dir):
        self.paths = self._Paths(db_path, cache_dir)
        self.pipeline = self._Pipeline()


def _cfg(tmp_path, db_path):
    cache = tmp_path / "ohlcv"
    cache.mkdir(exist_ok=True)
    return _Cfg(db_path, cache)


def _plant_detection(conn, *, ticker="AAA", data_asof_date="2026-05-28",
                     pivot=10.0, invalidation=8.0) -> int:
    """Insert one vcp PatternDetectionEvent via the repo; return detection_id."""
    from swing.data.repos.pattern_detection_events import insert_detection_event
    anchors = json.dumps({"window": {}, "evidence": {
        "pivot_price": pivot, "base_top_price": pivot,
        "contractions": [{"low": invalidation}]}})
    with conn:
        return insert_detection_event(conn, PatternDetectionEvent(
            detection_id=None, ticker=ticker, detection_date="2026-05-29",
            data_asof_date=data_asof_date, pattern_class="vcp",
            structural_anchors_json=anchors, composite_score=0.7,
            detector_version="vcp_v1", source="pipeline",
            per_pattern_metadata_json="{}", created_at="2026-05-29T00:00:00Z"))


def _stub_window(close, *, high=None, low=None, provider="yfinance", date_):
    """Return (df, provenance) shaped like resolve_ohlcv_window for ONE date."""
    df = pd.DataFrame([{
        "asof_date": date_, "open": close, "high": high or close,
        "low": low or close, "close": close, "volume": 1_000_000.0}])
    return df, {date_: provider}


def _seed_aplus_candidate_and_run(db, *, ticker="AAA", sector="", industry="",
                                  adr_pct=2.5, rs_rank=85,
                                  data_asof_date="2026-05-19",
                                  action_session_date="2026-05-20"):
    """Seed a pipeline_runs row + an EvaluationRun + one bucket='aplus'
    Candidate; return (conn, cfg, lease, eval_run_id). Uses the REAL repos so
    the INSERT shape matches production (anti-drift). Field shapes verbatim
    from the verified detect-step harness."""
    conn, db_path = db
    from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
    from swing.data.models import Candidate, EvaluationRun
    # pipeline_runs row (id=1) -- lease_data_asof reads its data_asof_date.
    # STEP-0 fix: include trigger='manual' (NOT NULL CHECK).
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date, "
        "action_session_date, lease_token, state) VALUES "
        "(1, ?, 'manual', ?, ?, 'tok-test-1', 'running')",
        ("2026-05-20T18:00:00", data_asof_date, action_session_date))
    eval_run_id = insert_evaluation_run(conn, EvaluationRun(
        id=None, run_ts="2026-05-20T18:00:00", data_asof_date=data_asof_date,
        action_session_date=action_session_date, finviz_csv_path=None,
        tickers_evaluated=1, aplus_count=1, watch_count=0, skip_count=0,
        excluded_count=0, error_count=0))
    insert_candidates(conn, eval_run_id, [Candidate(
        ticker=ticker, bucket="aplus", close=15.0, pivot=15.1, initial_stop=13.5,
        adr_pct=adr_pct, tight_streak=3, pullback_pct=5.0, prior_trend_pct=40.0,
        rs_rank=rs_rank, rs_return_12w_vs_spy=12.0, rs_method="universe",
        pattern_tag=None, notes=None, criteria=tuple(), sector=sector,
        industry=industry)])
    conn.commit()
    cfg = _cfg(db_path.parent, db_path)
    lease = _FakeLease(db_path, run_id=1, data_asof=data_asof_date)
    return conn, cfg, lease, eval_run_id


def _seed_run_with_zero_aplus(db):
    """Same scaffold but the only candidate is bucket='excluded' (no aplus)."""
    conn, db_path = db
    from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
    from swing.data.models import Candidate, EvaluationRun
    # STEP-0 fix: include trigger='manual' (NOT NULL CHECK).
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date, "
        "action_session_date, lease_token, state) VALUES "
        "(1, '2026-05-20T18:00:00', 'manual', '2026-05-19', '2026-05-20', "
        "'tok', 'running')")
    eval_run_id = insert_evaluation_run(conn, EvaluationRun(
        id=None, run_ts="2026-05-20T18:00:00", data_asof_date="2026-05-19",
        action_session_date="2026-05-20", finviz_csv_path=None,
        tickers_evaluated=1, aplus_count=0, watch_count=0, skip_count=0,
        excluded_count=1, error_count=0))
    insert_candidates(conn, eval_run_id, [Candidate(
        ticker="XYZ", bucket="excluded", close=8.0, pivot=None, initial_stop=None,
        adr_pct=1.5, tight_streak=0, pullback_pct=0.0, prior_trend_pct=0.0,
        rs_rank=10, rs_return_12w_vs_spy=-5.0, rs_method="universe",
        pattern_tag=None, notes=None, criteria=tuple())])
    conn.commit()
    return conn, _cfg(db_path.parent, db_path), _FakeLease(db_path, 1, "2026-05-19"), eval_run_id


def _drive_detect(conn, cfg, lease, eval_run_id, ohlcv_cache, run_warnings):
    """Drive the real _step_pattern_detect with the extension args."""
    from swing.pipeline.runner import _step_pattern_detect
    _step_pattern_detect(cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                         ohlcv_cache=ohlcv_cache, run_warnings=run_warnings)
