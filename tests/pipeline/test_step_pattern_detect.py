"""Phase 13 T2.SB3 T-A.3.6 — `_step_pattern_detect` integration tests.

Per plan section G.4 T-A.3.6 Step 1: 4 discriminating tests covering
(a) step invokes 3 detectors against candidate windows; (b) emits 1
pattern_evaluations row per (ticker, pattern_class) tuple;
(c) emits feature_distribution_log_json on each row; (d) zero
candidate windows -> step succeeds without writes.

Recon at docs/phase13-t2-sb3-recon.md sections 1-9 binds the
integration contract:
- NEW step inserted between _step_recommendations + _step_schwab_snapshot.
- Caller-tx via lease.fenced_write(); SELECT-then-INSERT idempotency.
- pipeline_run_id = lease.run_id (NOT eval_run_id).
- Pool predicate = candidates.bucket == 'aplus' (Stage-2 + RS-rank
  filtered per spec section 5.1.3).
- NO sandbox gating.
- Best-effort wrapper at runner.py mirrors _step_recommendations.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.data.models import Candidate, EvaluationRun
from swing.data.repos.candidates import (
    insert_candidates,
    insert_evaluation_run,
)
from swing.pipeline.runner import _step_pattern_detect

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_bars(start: date = date(2025, 6, 1), n_days: int = 180) -> pd.DataFrame:
    """Realistic OHLCV with H > Close > L divergence + Volume > 0.

    Produces a mild uptrend so detectors get past the first guard but most
    geometric criteria likely fail (geometric_score may be 0.0 for many
    windows). The test only requires the detector path executes + emits
    valid evidence; it does NOT require any criterion to pass.
    """
    idx = pd.DatetimeIndex(
        [pd.Timestamp(start) + pd.Timedelta(days=i) for i in range(n_days)]
    )
    closes = np.linspace(10.0, 15.0, n_days)
    # Add wiggle so zigzag swings exist (criterion #3 needs swings).
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
    """Minimal duck-typed stub for OhlcvCache.get_or_fetch signature."""

    def __init__(self, bars_by_ticker: dict[str, pd.DataFrame]):
        self._bars = bars_by_ticker

    def get_or_fetch(self, *, ticker: str, window_days: int = 200) -> pd.DataFrame:
        df = self._bars.get(ticker.upper())
        if df is None:
            raise ValueError(f"No data for {ticker}")
        return df


class _StubLease:
    """Stub Lease yielding the shared conn through fenced_write()."""

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
            "2026-05-20T18:00:00",
            "2026-05-19",
            "2026-05-20",
            "tok-test-1",
        ),
    )
    return int(cur.lastrowid)


def _seed_evaluation_run(conn: sqlite3.Connection) -> int:
    return insert_evaluation_run(
        conn,
        EvaluationRun(
            id=None,
            run_ts="2026-05-20T18:00:00",
            data_asof_date="2026-05-19",
            action_session_date="2026-05-20",
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


def _seed_excluded_candidate(
    conn: sqlite3.Connection, eval_run_id: int, ticker: str = "XYZ",
) -> None:
    """A non-aplus row that the step MUST skip (pool predicate)."""
    cand = Candidate(
        ticker=ticker,
        bucket="excluded",
        close=8.0,
        pivot=None,
        initial_stop=None,
        adr_pct=1.5,
        tight_streak=0,
        pullback_pct=0.0,
        prior_trend_pct=0.0,
        rs_rank=10,
        rs_return_12w_vs_spy=-5.0,
        rs_method="universe",
        pattern_tag=None,
        notes=None,
        criteria=tuple(),
    )
    insert_candidates(conn, eval_run_id, [cand])


@pytest.fixture
def seeded_env(tmp_path: Path):
    db_path = tmp_path / "phase13_t2sb3_step.db"
    conn = ensure_schema(db_path)
    pipeline_run_id = _seed_pipeline_run(conn)
    eval_run_id = _seed_evaluation_run(conn)
    conn.commit()
    bars = _build_bars()
    cache = _StubOhlcvCache({"ABC": bars})
    lease = _StubLease(conn, run_id=pipeline_run_id)
    return {
        "conn": conn,
        "pipeline_run_id": pipeline_run_id,
        "eval_run_id": eval_run_id,
        "lease": lease,
        "cache": cache,
        "bars": bars,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_step_pattern_detect_invokes_3_detectors_against_candidate_windows(
    seeded_env,
) -> None:
    """Step invokes all 3 detectors (vcp, flat_base, cup_with_handle).

    Discriminating predicate: AFTER step, pattern_evaluations contains
    rows for all 3 detector pattern_classes for ticker ABC. The
    geometric_score may be 0.0 (most synthetic bars won't pass all
    criteria) but the detector code path MUST have executed + persisted
    an evidence row per class.
    """
    _seed_aplus_candidate(seeded_env["conn"], seeded_env["eval_run_id"])

    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    rows = seeded_env["conn"].execute(
        "SELECT DISTINCT pattern_class FROM pattern_evaluations "
        "WHERE pipeline_run_id = ? AND ticker = ? "
        "ORDER BY pattern_class",
        (seeded_env["pipeline_run_id"], "ABC"),
    ).fetchall()
    classes = [r[0] for r in rows]
    assert classes == ["cup_with_handle", "flat_base", "vcp"]


def test_step_pattern_detect_emits_one_row_per_ticker_pattern_class(
    seeded_env,
) -> None:
    """For N aplus tickers, write exactly 3N pattern_evaluations rows
    (3 detectors x 1 verdict per (ticker, pattern_class)).

    Also pins the pool predicate: an 'excluded' bucket candidate MUST
    NOT contribute rows.
    """
    _seed_aplus_candidate(seeded_env["conn"], seeded_env["eval_run_id"], ticker="ABC")
    # Excluded candidate -- MUST be skipped by the step.
    _seed_excluded_candidate(seeded_env["conn"], seeded_env["eval_run_id"], ticker="XYZ")
    # Provide bars only for ABC; XYZ should be filtered out before fetch.
    seeded_env["conn"].commit()

    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    rows_abc = seeded_env["conn"].execute(
        "SELECT COUNT(*) FROM pattern_evaluations WHERE ticker = ?",
        ("ABC",),
    ).fetchone()[0]
    rows_xyz = seeded_env["conn"].execute(
        "SELECT COUNT(*) FROM pattern_evaluations WHERE ticker = ?",
        ("XYZ",),
    ).fetchone()[0]
    # 3 detectors x 1 ticker = 3 rows for ABC; 0 for excluded XYZ.
    assert rows_abc == 3
    assert rows_xyz == 0


def test_step_pattern_detect_emits_feature_distribution_log_json(
    seeded_env,
) -> None:
    """Every emitted row carries a non-empty, parseable
    feature_distribution_log_json with the expected dataclass shape
    (detector_class + composite_score_histogram_bins fields per spec
    section D.7).
    """
    _seed_aplus_candidate(seeded_env["conn"], seeded_env["eval_run_id"])

    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    rows = seeded_env["conn"].execute(
        "SELECT pattern_class, feature_distribution_log_json "
        "FROM pattern_evaluations WHERE ticker = ? ORDER BY pattern_class",
        ("ABC",),
    ).fetchall()
    assert len(rows) == 3
    for pattern_class, fdl_json in rows:
        assert fdl_json is not None and fdl_json != ""
        fdl = json.loads(fdl_json)
        # FeatureDistributionLog dataclass shape (spec section D.7).
        assert fdl["detector_class"] == pattern_class
        assert "composite_score_histogram_bins" in fdl
        assert isinstance(fdl["composite_score_histogram_bins"], list)
        assert "smoothing_params" in fdl
        assert "universe_size" in fdl


def test_step_pattern_detect_zero_candidates_succeeds_without_writes(
    seeded_env, caplog,
) -> None:
    """No aplus rows -> step exits cleanly with NO writes + an INFO log.

    Discriminating predicate: pattern_evaluations row count == 0 AND no
    exception raised AND log emitted at INFO level mentioning zero
    candidates.
    """
    # Note: NO aplus candidate seeded.
    caplog.set_level(logging.INFO, logger="swing.pipeline.runner")

    # Should not raise.
    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    row_count = seeded_env["conn"].execute(
        "SELECT COUNT(*) FROM pattern_evaluations"
    ).fetchone()[0]
    assert row_count == 0
    # An INFO log line should exist mentioning the zero-candidate path.
    info_msgs = [
        r.getMessage().lower()
        for r in caplog.records
        if r.levelno == logging.INFO
    ]
    assert any(
        "pattern_detect" in m and ("no candidate" in m or "zero" in m or "skip" in m)
        for m in info_msgs
    ), f"Expected zero-candidate INFO log; got: {info_msgs}"


def test_step_pattern_detect_idempotent_re_invocation(seeded_env) -> None:
    """Re-invoking the step with the same (pipeline_run_id, eval_run_id)
    MUST NOT raise IntegrityError + row count MUST stay the same.

    Per recon section 4.2: SELECT-then-INSERT idempotency (LOCK L3 forbids
    INSERT OR REPLACE). Second invocation skips existing rows.
    """
    _seed_aplus_candidate(seeded_env["conn"], seeded_env["eval_run_id"])

    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )
    count_after_first = seeded_env["conn"].execute(
        "SELECT COUNT(*) FROM pattern_evaluations"
    ).fetchone()[0]

    # Second invocation -- MUST be a no-op (no IntegrityError; same count).
    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )
    count_after_second = seeded_env["conn"].execute(
        "SELECT COUNT(*) FROM pattern_evaluations"
    ).fetchone()[0]
    assert count_after_first == count_after_second == 3
