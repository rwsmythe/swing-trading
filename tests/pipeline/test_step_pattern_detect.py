"""Phase 13 T2.SB3 T-A.3.6 + T2.SB4 T-A.4.3 — `_step_pattern_detect` integration tests.

Per plan section G.4 T-A.3.6 Step 1 (T2.SB3 origin) + T2.SB4 T-A.4.3
extension: discriminating tests covering (a) step invokes ALL 5 detectors
(vcp, flat_base, cup_with_handle, high_tight_flag, double_bottom_w)
against candidate windows; (b) emits 1 pattern_evaluations row per
(ticker, pattern_class) tuple; (c) emits feature_distribution_log_json
on each row; (d) zero candidate windows -> step succeeds without writes.

T-A.4.3 contract change (3->5 detectors): existing TDD assertions
hard-coded the 3-detector universe (vcp + flat_base + cup_with_handle).
The data-driven `_pattern_detect_registry()` helper at runner.py:1246
now returns 5 tuples (T-A.4.3 adds high_tight_flag + double_bottom_w).
Tests updated accordingly; per-detector signature parity (kwargs:
conn, ticker, asof_date) confirmed before extension landing.

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
from swing.data.models import DETECTOR_PATTERN_CLASSES, Candidate, EvaluationRun
from swing.data.repos.candidates import (
    insert_candidates,
    insert_evaluation_run,
)
from swing.pipeline.runner import _pattern_detect_registry, _step_pattern_detect

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


def test_step_pattern_detect_invokes_all_5_detectors_per_candidate_window(
    seeded_env,
) -> None:
    """T-A.4.3: step invokes ALL 5 detectors (vcp, flat_base,
    cup_with_handle, high_tight_flag, double_bottom_w).

    Pre-T-A.4.3 (3-detector contract): assertion was ``classes ==
    ["cup_with_handle", "flat_base", "vcp"]``. Post-T-A.4.3 (5-detector
    contract): assertion is the lexicographically-sorted 5-tuple
    derived from ``DETECTOR_PATTERN_CLASSES`` (with HTF + DBW added).

    Discriminating predicate: AFTER step, pattern_evaluations contains
    rows for all 5 detector pattern_classes for ticker ABC. The
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
    # Lexicographic sort of the 5 detector pattern_classes:
    # cup_with_handle, double_bottom_w, flat_base, high_tight_flag, vcp
    assert classes == sorted(DETECTOR_PATTERN_CLASSES)
    assert len(classes) == 5


def test_step_pattern_detect_registry_returns_5_detectors() -> None:
    """T-A.4.3 unit test on the `_pattern_detect_registry()` helper.

    Asserts: (a) tuple has exactly 5 entries; (b) class_names are
    the canonical 5 ``DETECTOR_PATTERN_CLASSES`` (any order); (c) every
    callable is the actual detector function (smoke-tests imports);
    (d) every version_str is a non-empty string matching the
    ``<class>@v<ver>`` convention.
    """
    registry = _pattern_detect_registry()
    assert isinstance(registry, tuple)
    assert len(registry) == 5, (
        f"_pattern_detect_registry() must return exactly 5 detectors "
        f"(T-A.4.3 contract); got {len(registry)}: "
        f"{[t[1] for t in registry]}"
    )

    class_names = [t[1] for t in registry]
    # All 5 canonical pattern_classes are present (any order).
    assert set(class_names) == set(DETECTOR_PATTERN_CLASSES), (
        f"registry class_names = {class_names}; expected "
        f"{set(DETECTOR_PATTERN_CLASSES)}"
    )

    # Every callable is importable + callable.
    for detector_fn, pattern_class, version_str in registry:
        assert callable(detector_fn), (
            f"detector for {pattern_class!r} is not callable: {detector_fn!r}"
        )
        # Function name matches the convention `detect_<pattern_class>`.
        assert detector_fn.__name__ == f"detect_{pattern_class}", (
            f"detector name {detector_fn.__name__!r} != "
            f"detect_{pattern_class!r}"
        )
        # Version string is the `<class>@v<ver>` convention.
        assert isinstance(version_str, str) and version_str.startswith(
            f"{pattern_class}@v"
        ), (
            f"version_str for {pattern_class!r} = {version_str!r}; "
            f"expected to start with {pattern_class!r}@v"
        )


def test_step_pattern_detect_emits_one_row_per_ticker_pattern_class(
    seeded_env,
) -> None:
    """For N aplus tickers, write exactly 5N pattern_evaluations rows
    (T-A.4.3: 5 detectors x 1 verdict per (ticker, pattern_class)).

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
    # T-A.4.3: 5 detectors x 1 ticker = 5 rows for ABC; 0 for excluded XYZ.
    assert rows_abc == 5
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
    # T-A.4.3: 5 detectors emit 5 rows per ticker.
    assert len(rows) == 5
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


def test_step_pattern_detect_uses_eval_run_action_session_date_not_wall_clock(
    seeded_env, monkeypatch,
) -> None:
    """Codex R1 Major #2 - asof_date passed to detectors MUST be the
    eval_run's ``action_session_date`` (the run's OWN session date), NOT
    the wall-clock ``datetime.now()``.

    Pre-fix: ``_step_pattern_detect`` computed
    ``asof_today = _dt_inner.now(UTC).date()`` and passed that to every
    detector invocation. If the DB had a LATER ``evaluation_runs`` row
    (e.g. operator backfilling an earlier run), ``current_stage`` would
    select the latest row with ``action_session_date <= asof_today``
    yielding a FUTURE Stage-2 verdict for the earlier run's emit.

    Post-fix: derive ``asof_date`` from the eval_run row's
    ``action_session_date`` itself; this remains the eval_run's anchor
    even when run wall-clock-late.
    """
    conn = seeded_env["conn"]
    # Insert a SECOND eval_run that is EARLIER than the seeded eval_run's
    # 2026-05-20 anchor (and earlier than today's wall-clock). Backfill
    # the aplus candidate against THAT earlier run; the step is then
    # invoked with the EARLIER eval_run_id. Pre-fix: detectors would
    # receive today's wall-clock date (2026-05-20) -- NOT the earlier
    # run's 2026-01-15. Post-fix: the eval_run's own action_session_date
    # is the anchor.
    early_eval_run_id = insert_evaluation_run(
        conn,
        EvaluationRun(
            id=None,
            run_ts="2026-01-15T18:00:00",
            data_asof_date="2026-01-14",
            action_session_date="2026-01-15",
            finviz_csv_path=None,
            tickers_evaluated=1,
            aplus_count=1,
            watch_count=0,
            skip_count=0,
            excluded_count=0,
            error_count=0,
        ),
    )
    conn.commit()
    _seed_aplus_candidate(conn, early_eval_run_id)

    # Capture every (kwargs['asof_date']) passed to detector callables.
    seen_asof_dates: list[date] = []
    import swing.patterns.vcp as _vcp_mod
    real_detect_vcp = _vcp_mod.detect_vcp

    def _spy_detect_vcp(bars, window, *, conn=None, ticker=None, asof_date=None):
        seen_asof_dates.append(asof_date)
        return real_detect_vcp(
            bars, window, conn=conn, ticker=ticker, asof_date=asof_date
        )

    monkeypatch.setattr(_vcp_mod, "detect_vcp", _spy_detect_vcp)
    # The _pattern_detect_registry imports detect_vcp at call-time; patch
    # the runner-side binding too.
    import swing.pipeline.runner as _runner_mod
    if hasattr(_runner_mod, "detect_vcp"):
        monkeypatch.setattr(_runner_mod, "detect_vcp", _spy_detect_vcp)

    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=early_eval_run_id,
        ohlcv_cache=seeded_env["cache"],
    )

    # asof_date MUST equal the EARLY eval_run's action_session_date
    # (2026-01-15), NOT a wall-clock date (today / 2026-05-20 / etc.).
    expected_asof = date(2026, 1, 15)
    assert seen_asof_dates, "detector never invoked"
    for d in seen_asof_dates:
        assert d == expected_asof, (
            f"detector received asof_date={d!r}; expected eval_run's "
            f"action_session_date={expected_asof}"
        )


def test_step_pattern_detect_feature_distribution_histogram_populated_with_run_scores(
    seeded_env,
) -> None:
    """Codex R1 Major #3 - feature_distribution_log_json on each row MUST
    carry a histogram derived from the run's actual composite_scores.

    Pre-fix: ``universe_context['composite_scores']`` was initialized
    empty + never populated; the histogram persisted on every row was
    all-zeros + ALWAYS misleading.

    Post-fix (Option A two-pass): first pass collects all
    (ticker, pattern_class, geometric_score) tuples; second pass writes
    rows carrying the FULL universe histogram. Every row's histogram
    bin counts sum to the number of detector invocations (NOT zero).
    """
    _seed_aplus_candidate(seeded_env["conn"], seeded_env["eval_run_id"])
    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )
    rows = seeded_env["conn"].execute(
        "SELECT feature_distribution_log_json FROM pattern_evaluations "
        "WHERE ticker = ? ORDER BY pattern_class",
        ("ABC",),
    ).fetchall()
    # T-A.4.3: 5 detectors emit 5 rows; histogram spans all 5 scores.
    assert len(rows) == 5
    for (fdl_json,) in rows:
        fdl = json.loads(fdl_json)
        bins = fdl["composite_score_histogram_bins"]
        assert isinstance(bins, list) and len(bins) == 10
        total = sum(bins)
        # 1 ticker x 5 detectors -> 5 composite_scores collected.
        assert total == 5, (
            f"expected histogram bin counts to sum to 5 (1 ticker x 5 "
            f"detectors per T-A.4.3); got {total}: {bins}"
        )


class _SpyConn:
    """Wraps a sqlite3 connection and records calls to ``execute`` so
    tests can assert when BEGIN IMMEDIATE was issued.

    Codex R2 Major #1: ``_step_pattern_detect`` must NOT hold the
    write transaction across OHLCV fetches / window generation /
    detector invocations. The fix is to delay ``lease.fenced_write()``
    (which issues BEGIN IMMEDIATE) until the INSERT phase only.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.executed: list[str] = []
        self.begin_immediate_at: list[int] = []  # index into executed
        # Track which call-index the first detector invocation happened on.
        self.detector_invocation_index_first: int | None = None

    def execute(self, sql, *args, **kwargs):
        self.executed.append(sql)
        if "BEGIN IMMEDIATE" in sql.upper():
            self.begin_immediate_at.append(len(self.executed) - 1)
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _SpyLease:
    """Like _StubLease but every entry into fenced_write issues a real
    BEGIN IMMEDIATE on the underlying spy conn (mirroring the production
    Lease semantics)."""

    def __init__(self, spy_conn: _SpyConn, run_id: int):
        self._conn = spy_conn
        self.run_id = run_id

    def fenced_write(self):
        @contextmanager
        def _cm():
            # Production lease.fenced_write() issues BEGIN IMMEDIATE on entry.
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn._conn.commit()
            except Exception:
                self._conn._conn.rollback()
                raise

        return _cm()


def test_step_pattern_detect_pass_1_runs_outside_write_transaction(
    seeded_env,
) -> None:
    """Codex R2 Major #1 - the lock-duration regression.

    Pass 1 (read candidates, fetch bars, generate windows, invoke
    detectors) MUST run BEFORE the write transaction (BEGIN IMMEDIATE)
    is opened. Only Pass 2 (idempotency-check + INSERTs) runs inside
    BEGIN IMMEDIATE.

    Pre-fix: ``with lease.fenced_write() as conn:`` wrapped the entire
    flow (candidates read + bars fetch + detector loop + INSERTs). This
    held the lock for ~seconds per ticker.

    Post-fix: Pass 1 runs without a write transaction. BEGIN IMMEDIATE
    is issued exactly ONCE, right before the INSERT loop.

    Discriminating predicate: the call to ``ohlcv_cache.get_or_fetch``
    happens BEFORE the first BEGIN IMMEDIATE on the conn.
    """
    conn = seeded_env["conn"]
    spy_conn = _SpyConn(conn)
    spy_lease = _SpyLease(spy_conn, run_id=seeded_env["pipeline_run_id"])
    _seed_aplus_candidate(conn, seeded_env["eval_run_id"], ticker="ABC")
    conn.commit()

    # Spy on ohlcv_cache.get_or_fetch to record when (in executed-call
    # sequence) the fetch happens.
    bars_fetched_at: list[int] = []
    bars_df = seeded_env["bars"]

    class _RecordingCache:
        def get_or_fetch(self, *, ticker: str, window_days: int = 200):
            bars_fetched_at.append(len(spy_conn.executed))
            return bars_df

    _step_pattern_detect(
        cfg=None,
        lease=spy_lease,
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=_RecordingCache(),
    )

    # Discriminating assertion #1: bars were fetched at least once.
    assert bars_fetched_at, (
        "ohlcv_cache.get_or_fetch was never invoked"
    )
    # Discriminating assertion #2: the FIRST bars-fetch happened BEFORE
    # the FIRST BEGIN IMMEDIATE on the conn.
    assert spy_conn.begin_immediate_at, (
        f"No BEGIN IMMEDIATE issued; executed={spy_conn.executed!r}"
    )
    first_fetch = bars_fetched_at[0]
    first_begin = spy_conn.begin_immediate_at[0]
    assert first_fetch < first_begin, (
        f"OHLCV fetch happened at exec-call #{first_fetch} but "
        f"BEGIN IMMEDIATE issued at exec-call #{first_begin}; "
        f"Pass 1 must run BEFORE the write transaction. "
        f"executed={spy_conn.executed!r}"
    )
    # Discriminating assertion #3: BEGIN IMMEDIATE issued at most ONCE
    # (Pass 2 has one transaction; no extras).
    assert len(spy_conn.begin_immediate_at) == 1, (
        f"BEGIN IMMEDIATE issued {len(spy_conn.begin_immediate_at)} "
        f"times; expected exactly 1 (Pass 2 only). "
        f"executed={spy_conn.executed!r}"
    )


def test_step_pattern_detect_partial_retry_includes_existing_rows_in_histogram(
    seeded_env,
) -> None:
    """Codex R2 Major #2 - on retry after partial prior writes, the
    histogram persisted in NEW rows MUST include the composite_scores
    of PRE-EXISTING rows for the same pipeline_run_id.

    Pre-fix: existing rows skipped via SELECT-then-INSERT idempotency
    were NOT loaded into ``universe_context['composite_scores']``. New
    rows' histograms reflected only the newly-emitted scores, not the
    full universe.

    Post-fix (Option B): SELECT existing pattern_evaluations rows for
    the pipeline_run_id at step entry; seed
    ``universe_context['composite_scores']`` with their composite_scores.
    Pass 1 + Pass 2 append new scores onto the seed.

    Discriminating predicate: pre-seed N=2 existing rows with
    composite_score=0.5; invoke step (T-A.4.3: 1 ticker x 5 detectors
    produces 5 new rows for NEW (ticker, pattern_class) tuples not
    pre-seeded since the pre-seeded rows are for tickers PRE1/PRE2 not
    ABC); assert the histogram bin counts on the NEW rows sum to
    N + M = 2 + 5 = 7.
    """
    conn = seeded_env["conn"]
    pipeline_run_id = seeded_env["pipeline_run_id"]
    # Pre-seed 2 existing pattern_evaluations rows with composite_score=0.5
    # for the same pipeline_run_id but DIFFERENT tickers (so the
    # idempotency-check does NOT skip them when the step runs for ABC).
    for ticker in ("PRE1", "PRE2"):
        conn.execute(
            """
            INSERT INTO pattern_evaluations
                (pipeline_run_id, ticker, pattern_class, detector_version,
                 geometric_score, geometric_score_json, composite_score,
                 structural_evidence_json, feature_distribution_log_json,
                 window_start_date, window_end_date, created_at)
            VALUES (?, ?, 'vcp', 'vcp_v1.0',
                    0.5, '{}', 0.5, '{}', '{}',
                    '2026-05-01', '2026-05-15', '2026-05-20T18:00:00')
            """,
            (pipeline_run_id, ticker),
        )
    conn.commit()
    _seed_aplus_candidate(conn, seeded_env["eval_run_id"], ticker="ABC")
    conn.commit()

    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    # ABC produced 5 new rows (1 ticker x 5 detectors per T-A.4.3).
    # Plus the 2 pre-seeded rows for PRE1/PRE2. Total expected = 7.
    rows = conn.execute(
        "SELECT ticker, pattern_class, feature_distribution_log_json "
        "FROM pattern_evaluations WHERE pipeline_run_id = ? "
        "AND ticker = ? ORDER BY pattern_class",
        (pipeline_run_id, "ABC"),
    ).fetchall()
    assert len(rows) == 5, (
        f"expected 5 new ABC rows (T-A.4.3 5-detector contract); "
        f"got {len(rows)}"
    )
    for ticker, pattern_class, fdl_json in rows:
        fdl = json.loads(fdl_json)
        bins = fdl["composite_score_histogram_bins"]
        assert isinstance(bins, list) and len(bins) == 10
        total = sum(bins)
        # Total scores in histogram = pre-existing (2 rows @ 0.5) + new
        # (5 rows from the ABC detectors per T-A.4.3). Expected = 7.
        assert total == 7, (
            f"row ({ticker}, {pattern_class}): histogram bins sum to "
            f"{total}; expected 7 (2 pre-existing + 5 new T-A.4.3). "
            f"bins={bins}"
        )


class _ConcurrentInsertLease:
    """Stub Lease that simulates a concurrent INSERT between the step's
    seed-read (at step entry) and Pass 2's recheck (inside
    ``fenced_write``).

    Codex R3 Major #1: After the step's seed-read populates
    ``universe_context['composite_scores']`` + ``existing_idempotency_keys``,
    another caller MAY have inserted a row for a NEW (ticker, pattern_class)
    tuple BEFORE Pass 2 begins. The Pass 2 recheck SELECT will find that
    row + skip the INSERT (idempotent), but unless the recheck ALSO amends
    ``universe_context['composite_scores']``, subsequent INSERTs in the
    SAME emit_queue carry a STALE histogram missing that concurrent row's
    score.

    This lease injects the concurrent INSERT inside ``fenced_write()`` ON
    ENTRY (before yielding the connection to the step's Pass 2 loop) so
    the recheck SELECT will hit the row.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        concurrent_inserts: list[tuple[str, str, float]],
    ) -> None:
        # concurrent_inserts: list of (ticker, pattern_class, composite_score)
        # to insert when the step enters fenced_write() for Pass 2.
        self._conn = conn
        self.run_id = run_id
        self._concurrent_inserts = concurrent_inserts
        self._injected = False

    def fenced_write(self):
        @contextmanager
        def _cm():
            # Inject the concurrent row ONCE, on first fenced_write() entry.
            # Mirrors a real concurrent caller landing a row between the
            # step's seed-read (which happens OUTSIDE fenced_write in the
            # test-stub cfg=None path) + Pass 2's recheck.
            if not self._injected:
                for ticker, pattern_class, score in self._concurrent_inserts:
                    self._conn.execute(
                        """
                        INSERT INTO pattern_evaluations
                            (pipeline_run_id, ticker, pattern_class,
                             detector_version, geometric_score,
                             geometric_score_json, composite_score,
                             structural_evidence_json,
                             feature_distribution_log_json,
                             window_start_date, window_end_date, created_at)
                        VALUES (?, ?, ?, 'concurrent_v1.0',
                                ?, '{}', ?, '{}', '{}',
                                '2026-05-01', '2026-05-15',
                                '2026-05-20T18:00:00')
                        """,
                        (
                            self.run_id,
                            ticker,
                            pattern_class,
                            score,
                            score,
                        ),
                    )
                self._conn.commit()
                self._injected = True
            yield self._conn

        return _cm()


def test_step_pattern_detect_pass_2_concurrent_insert_amends_histogram(
    seeded_env,
) -> None:
    """Codex R3 Major #1 (assertion UPDATED at Codex R4) - Pass-2 histogram
    reflects the FINAL persisted set, never a queued-but-not-persisted score.

    Codex R4 architectural correction: the R3 fix (per-recheck-hit amend +
    KEEP the queued score in universe_context) over-counted -- the queued
    score for the concurrent-skipped tuple was a phantom that never landed
    in the table, yet it polluted the histogram. The R4 fix restructures
    Pass 2 to: (a) RE-READ canonical existing rows inside fenced_write;
    (b) RECONCILE emit_queue against that re-read set, dropping any tuple
    whose (ticker, pattern_class) is already persisted; (c) BUILD final
    universe = existing_scores + surviving_queued_scores; (d) SERIALIZE +
    INSERT each surviving row against that SAME final universe.

    Invariant: ``universe_context['composite_scores']`` represents the
    FINAL set of persisted rows for this pipeline_run_id (existing + this
    step's new inserts). NO Pass-1-staged-but-skipped score ever enters
    the histogram.

    Discriminating predicate (post-R4 + T-A.4.3 5-detector contract):
      - Pre-seed NO existing rows.
      - The lease injects a concurrent INSERT for (ABC, vcp) with
        composite_score=0.99 INSIDE ``fenced_write()`` on first entry.
      - Pass 1 produces emit_queue = 5 rows for ABC (vcp, flat_base,
        cup_with_handle, high_tight_flag, double_bottom_w) with
        Pass-1-emitted composite_scores.
      - Pass 2 enters fenced_write() -> injection plants (ABC, vcp, 0.99)
        -> re-read finds it -> reconcile drops (ABC, vcp) from emit list
        -> final universe = [0.99 (existing)] + [4 surviving queued
        scores] = 5 entries.
      - 4 surviving rows INSERT with the SAME 5-entry universe. The
        Pass-1-queued (ABC, vcp) score is DROPPED (it was a phantom).

    Pre-R4 expectation (over-count): histogram bins sum to 6 (5 Pass-1
    + 1 concurrent-amend, including the phantom queued vcp score).
    Post-R4 expectation (correct): histogram bins sum to 5 (final
    universe = 1 existing + 4 surviving = 5 persisted rows).
    """
    conn = seeded_env["conn"]
    pipeline_run_id = seeded_env["pipeline_run_id"]
    _seed_aplus_candidate(conn, seeded_env["eval_run_id"], ticker="ABC")
    conn.commit()

    # Replace the seeded_env lease with a concurrent-insert lease that
    # plants (ABC, vcp) with composite_score=0.99 when the step enters
    # fenced_write for Pass 2. The pre-existing _StubLease seeded the
    # _conn attribute correctly; we just need to swap in the concurrent
    # behavior.
    lease = _ConcurrentInsertLease(
        conn,
        run_id=pipeline_run_id,
        concurrent_inserts=[("ABC", "vcp", 0.99)],
    )

    _step_pattern_detect(
        cfg=None,
        lease=lease,
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    # Inspect the histograms written for ABC's 4 surviving detectors
    # (flat_base, cup_with_handle, high_tight_flag, double_bottom_w).
    # The (ABC, vcp) row is the concurrent-injected one (composite_score=0.99,
    # detector_version='concurrent_v1.0'), and the recheck-hit path
    # idempotent-skips it. The 4 OTHER rows MUST carry a histogram that
    # reflects the FINAL persisted set (5 rows: 1 existing + 4 surviving).
    rows = conn.execute(
        "SELECT ticker, pattern_class, composite_score, detector_version, "
        "feature_distribution_log_json FROM pattern_evaluations "
        "WHERE pipeline_run_id = ? AND ticker = 'ABC' "
        "ORDER BY pattern_class",
        (pipeline_run_id,),
    ).fetchall()
    # T-A.4.3: All 5 (ABC, *) rows present (vcp concurrent + 4 step-emitted).
    assert len(rows) == 5, (
        f"expected 5 ABC rows total (T-A.4.3); got {len(rows)}: {rows}"
    )

    # Find the 4 step-emitted rows (NOT the concurrent vcp).
    step_emitted_rows = [
        r for r in rows if r[3] != "concurrent_v1.0"
    ]
    assert len(step_emitted_rows) == 4, (
        f"expected 4 step-emitted rows (flat_base + cup_with_handle + "
        f"high_tight_flag + double_bottom_w per T-A.4.3); "
        f"got {len(step_emitted_rows)}: {step_emitted_rows}"
    )

    # Each step-emitted row's histogram MUST reflect the FINAL persisted
    # set (5 rows total): the concurrent 0.99 + the 4 surviving queued
    # scores. The Pass-1-queued vcp score is DROPPED (would have been
    # double-counted under R3 semantics).
    for ticker, pattern_class, _score, _dv, fdl_json in step_emitted_rows:
        fdl = json.loads(fdl_json)
        bins = fdl["composite_score_histogram_bins"]
        assert isinstance(bins, list) and len(bins) == 10
        total = sum(bins)
        assert total == 5, (
            f"row ({ticker}, {pattern_class}): histogram bins sum to "
            f"{total}; expected 5 (1 existing concurrent + 4 surviving "
            f"queued inserts per T-A.4.3). bins={bins}. "
            f"Pre-R4 over-count: total == 6 (R3 kept the phantom "
            f"Pass-1-queued vcp score AND added the concurrent score). "
            f"Post-R4: total == 5 (reconcile drops the phantom; "
            f"universe reflects ONLY persisted rows)."
        )


def test_step_pattern_detect_pass_2_does_not_overcount_concurrent_skipped_queued_score(
    seeded_env,
) -> None:
    """Codex R4 Major #1 - Pass-2 final-universe semantics: NO queued
    score for a concurrent-skipped tuple may appear in the histogram.

    Pre-R4 (R3 semantics): Pass 1 appends EVERY queued detector score to
    ``universe_context['composite_scores']`` BEFORE any insert. When Pass
    2 finds a concurrent-existing row, R3 added that row's score AND
    KEPT the Pass-1-staged queued score in the histogram -> the queued
    score (which is NOT persisted) phantoms a phantom entry. Net effect:
    histogram sums OVER the count of actual persisted rows.

    Post-R4: Pass 2 RE-READS canonical existing rows; RECONCILES emit
    list (drops any queued tuple whose (ticker, pattern_class) is in the
    re-read set); BUILDS final universe = existing_scores + surviving
    queued scores ONLY. The Pass-1-queued vcp score is dropped because
    its tuple now exists in the persisted set (via the concurrent
    insert).

    Discriminating predicate (T-A.4.3 5-detector contract):
      - Pre-seed NO existing rows.
      - Concurrent INSERT injects (ABC, vcp, composite_score=0.9) inside
        fenced_write before Pass 2's loop.
      - Pass 1 produces 5 queued tuples (ABC vcp, ABC flat_base, ABC
        cup_with_handle, ABC high_tight_flag, ABC double_bottom_w).
      - Post-R4: reconcile drops (ABC, vcp) from emit list -> final
        universe = [0.9 (existing concurrent)] + [4 surviving queued
        scores] = 5 entries.
      - Final persisted rows: 1 (vcp concurrent) + 4 (4 surviving
        inserts) = 5 rows per T-A.4.3.
      - Each surviving row's histogram MUST sum to 5 (the FINAL
        persisted count), NOT 6 (which would include the phantom
        Pass-1-queued vcp score).

    Pre-fix (R3) FAIL: total == 6 (over-count by 1 = the phantom queued
      vcp score that never landed in the table).
    Post-fix (R4) PASS: total == 5 (queued vcp score reconciled away;
      universe reflects ONLY persisted rows).
    """
    conn = seeded_env["conn"]
    pipeline_run_id = seeded_env["pipeline_run_id"]
    _seed_aplus_candidate(conn, seeded_env["eval_run_id"], ticker="ABC")
    conn.commit()

    lease = _ConcurrentInsertLease(
        conn,
        run_id=pipeline_run_id,
        concurrent_inserts=[("ABC", "vcp", 0.9)],
    )

    _step_pattern_detect(
        cfg=None,
        lease=lease,
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    rows = conn.execute(
        "SELECT ticker, pattern_class, composite_score, detector_version, "
        "feature_distribution_log_json FROM pattern_evaluations "
        "WHERE pipeline_run_id = ? AND ticker = 'ABC' "
        "ORDER BY pattern_class",
        (pipeline_run_id,),
    ).fetchall()
    # T-A.4.3: Final persisted = vcp (concurrent) + 4 surviving = 5.
    assert len(rows) == 5, (
        f"expected 5 ABC rows total (T-A.4.3); got {len(rows)}: {rows}"
    )

    # Find the 4 step-emitted rows (NOT the concurrent vcp).
    step_emitted_rows = [r for r in rows if r[3] != "concurrent_v1.0"]
    assert len(step_emitted_rows) == 4, (
        f"expected 4 step-emitted rows (T-A.4.3 5 detectors - 1 "
        f"concurrent vcp); got {len(step_emitted_rows)}"
    )

    # Each surviving row's histogram MUST sum to 5 (FINAL persisted set
    # count per T-A.4.3), AND bin 9 (containing 0.9) MUST be populated
    # by the concurrent existing row.
    for ticker, pattern_class, _score, _dv, fdl_json in step_emitted_rows:
        fdl = json.loads(fdl_json)
        bins = fdl["composite_score_histogram_bins"]
        assert isinstance(bins, list) and len(bins) == 10
        total = sum(bins)
        assert total == 5, (
            f"row ({ticker}, {pattern_class}): histogram bins sum to "
            f"{total}; expected 5 (FINAL persisted set = 1 concurrent "
            f"existing + 4 surviving queued inserts per T-A.4.3). "
            f"Pre-R4 (R3 semantics): total == 6 (over-count: phantom "
            f"Pass-1-queued vcp score never persisted but kept in "
            f"universe). bins={bins}"
        )
        # The 0.9 score MUST land in bin 9 (containing [0.9, 1.0]).
        assert bins[9] >= 1, (
            f"row ({ticker}, {pattern_class}): bin 9 (containing 0.9) "
            f"is empty; concurrent existing row's composite_score=0.9 "
            f"missing from histogram universe. bins={bins}"
        )


def test_step_pattern_detect_pass_2_amendment_not_order_dependent(
    seeded_env,
) -> None:
    """Codex R4 Major #2 - Pass-2 amendment must not be order-dependent.

    Pre-R4 (R3 semantics): the amend-on-recheck-hit code path only fires
    when the recheck loop REACHES the conflicting tuple. Any rows
    SERIALIZED EARLIER in emit_queue see a STALE histogram that OMITS
    the concurrent row's score. The R3 test happened to use a vcp
    concurrent conflict (FIRST in detector order), so the order
    dependence was not exposed -- but if the concurrent row lands on
    cup_with_handle (LAST in detector order), then ALL rows serialized
    before it carry a stale histogram.

    Post-R4: Pass 2 builds final universe ONCE (after re-read +
    reconcile) and ALL surviving rows serialize against that SAME
    universe. NO order dependence in serialization.

    Discriminating predicate (T-A.4.3 5-detector contract):
      - Pre-seed NO existing rows.
      - Concurrent INSERT injects (ABC, cup_with_handle, 0.95) inside
        fenced_write before Pass 2's loop. cup_with_handle is the THIRD
        in the detector registry order (vcp, flat_base, cup_with_handle,
        high_tight_flag, double_bottom_w).
      - Pass 1 produces 5 queued tuples (ABC vcp, ABC flat_base, ABC
        cup_with_handle, ABC high_tight_flag, ABC double_bottom_w).
      - Post-R4: reconcile drops (ABC, cup_with_handle); final universe
        = [0.95 (existing)] + [4 surviving queued scores] = 5 entries.
      - ALL 4 surviving rows see the SAME 5-entry universe with bin 9
        (containing 0.95) populated.

    Pre-fix (R3) FAIL: vcp is FIRST in emit_queue, so its histogram is
      serialized BEFORE the cup_with_handle recheck-hit fires. The vcp
      row's histogram is STALE -- excludes the concurrent 0.95.
      bins[9] for the vcp row == 0 (no 0.95).
    Post-fix (R4) PASS: all 4 surviving histograms contain 0.95 via
      bin 9 (the final universe was built before any insert).
    """
    conn = seeded_env["conn"]
    pipeline_run_id = seeded_env["pipeline_run_id"]
    _seed_aplus_candidate(conn, seeded_env["eval_run_id"], ticker="ABC")
    conn.commit()

    # Concurrent insert lands on the LAST detector in the registry order.
    lease = _ConcurrentInsertLease(
        conn,
        run_id=pipeline_run_id,
        concurrent_inserts=[("ABC", "cup_with_handle", 0.95)],
    )

    _step_pattern_detect(
        cfg=None,
        lease=lease,
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    rows = conn.execute(
        "SELECT ticker, pattern_class, composite_score, detector_version, "
        "feature_distribution_log_json FROM pattern_evaluations "
        "WHERE pipeline_run_id = ? AND ticker = 'ABC' "
        "ORDER BY pattern_class",
        (pipeline_run_id,),
    ).fetchall()
    # T-A.4.3: Final persisted = cup_with_handle (concurrent) +
    # 4 surviving step-emitted = 5.
    assert len(rows) == 5, (
        f"expected 5 ABC rows total (T-A.4.3); got {len(rows)}: {rows}"
    )

    # 4 step-emitted rows (vcp + flat_base + high_tight_flag +
    # double_bottom_w); cup_with_handle is the concurrent-injected one.
    step_emitted_rows = [r for r in rows if r[3] != "concurrent_v1.0"]
    assert len(step_emitted_rows) == 4, (
        f"expected 4 step-emitted rows (T-A.4.3 5 detectors - 1 "
        f"concurrent cup_with_handle); got "
        f"{len(step_emitted_rows)}: {step_emitted_rows}"
    )

    # ALL 4 step-emitted rows' histograms MUST contain bin 9 (containing
    # the concurrent 0.95). Pre-R4: rows serialized BEFORE the
    # cup_with_handle recheck-hit have bins[9] == 0 because that
    # recheck-hit had not yet fired.
    for ticker, pattern_class, _score, _dv, fdl_json in step_emitted_rows:
        fdl = json.loads(fdl_json)
        bins = fdl["composite_score_histogram_bins"]
        assert isinstance(bins, list) and len(bins) == 10
        total = sum(bins)
        assert total == 5, (
            f"row ({ticker}, {pattern_class}): histogram bins sum to "
            f"{total}; expected 5 (FINAL persisted set per T-A.4.3). "
            f"Pre-R4: rows serialized BEFORE the cup_with_handle "
            f"recheck-hit have stale histograms. "
            f"bins={bins}"
        )
        assert bins[9] >= 1, (
            f"row ({ticker}, {pattern_class}): bin 9 (containing 0.95) "
            f"is empty -- the concurrent cup_with_handle row's score "
            f"is missing from this row's histogram universe. "
            f"This is the ORDER-DEPENDENT bug (R3 amend-on-hit only "
            f"fires when loop REACHES the conflicting tuple, but "
            f"{pattern_class} was serialized BEFORE cup_with_handle). "
            f"bins={bins}"
        )


def test_step_pattern_detect_aborts_on_missing_eval_run_action_session_date(
    seeded_env, caplog,
) -> None:
    """Codex R2 Major #3 - the wall-clock fallback in
    ``_resolve_eval_run_action_session_date`` reintroduces the
    future-stage leak under exactly the metadata-failure path the
    Major #2 fix was meant to harden.

    Pre-fix: when the eval_run row is missing or the
    action_session_date is null/malformed, the helper falls back to
    ``datetime.now(UTC).date()`` (wall-clock) and emits a WARNING but
    keeps going.

    Post-fix: REMOVE the wall-clock fallback. Raise an exception
    (e.g. ``EvalRunResolutionError``); the best-effort wrapper at
    ``runner.py:819-834`` catches it -> WARNING log -> SKIP pattern
    detection for this run (no rows written).

    Discriminating predicate: pattern detect invoked with an
    eval_run_id that does NOT exist in evaluation_runs MUST result in
    (a) NO pattern_evaluations rows written; (b) a WARNING log; (c) no
    silent fallback to today's wall-clock date.
    """
    conn = seeded_env["conn"]
    # Use a bogus eval_run_id; the helper should fail to resolve it.
    bogus_eval_run_id = 99_999_999
    # Seed a candidate against the bogus eval_run_id so the step at
    # least gets PAST the "no candidates" early-return. We INSERT raw
    # rather than calling _seed_aplus_candidate, because that helper
    # requires the eval_run row to exist (FK). Instead, mimic the
    # earlier-seeded eval_run path: seed candidates for the seeded
    # eval_run_id, then invoke step with the bogus id (the candidates
    # SELECT will return [] under FK semantics, so the step would
    # short-circuit on zero candidates). To force the failure path
    # AFTER candidate-load, seed candidates against the bogus id by
    # disabling FK checks. SQLite by default has FKs OFF; ensure_schema
    # may have enabled them.
    conn.execute("PRAGMA foreign_keys = OFF")
    cand = Candidate(
        ticker="ABC",
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
    insert_candidates(conn, bogus_eval_run_id, [cand])
    conn.commit()
    caplog.set_level(logging.WARNING, logger="swing.pipeline.runner")

    # Best-effort wrapper at runner.py:819-834 catches the exception;
    # mirror that here so the test asserts the contract end-to-end.
    from swing.pipeline.runner import EvalRunResolutionError

    raised: Exception | None = None
    try:
        _step_pattern_detect(
            cfg=None,
            lease=seeded_env["lease"],
            eval_run_id=bogus_eval_run_id,
            ohlcv_cache=seeded_env["cache"],
        )
    except EvalRunResolutionError as exc:  # noqa: BLE001 (intentional)
        raised = exc

    # The function MUST raise the typed error (the best-effort wrapper
    # in runner.py:819-834 catches it).
    assert raised is not None, (
        "expected EvalRunResolutionError to be raised when eval_run "
        "row is missing"
    )
    # No pattern_evaluations rows written.
    row_count = conn.execute(
        "SELECT COUNT(*) FROM pattern_evaluations"
    ).fetchone()[0]
    assert row_count == 0, (
        f"expected zero pattern_evaluations rows on missing eval_run; "
        f"got {row_count}"
    )


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
    # T-A.4.3: 5 detectors x 1 ticker -> 5 rows; idempotent re-invocation
    # leaves the count unchanged.
    assert count_after_first == count_after_second == 5


# ---------------------------------------------------------------------------
# Codex R2 Critical #1 -- DBW geometric_score=1.10 composite-layer clamp.
#
# Spec section 5.8 line 718 + section 10.5 line 1325: DBW evidence
# geometric_score may reach 1.10 (base 1.0 + undercut bonus 0.10). The
# COMPOSITE formula at section 5.8 line 712 wraps with min(1.0, ...).
# Pre-fix: pipeline composite_score = geometric_score (LOCK pre-T2.SB5;
# template_match_score None); a DBW evidence score of 1.10 propagated
# verbatim to composite_score and downstream drift_logging
# _composite_score_histogram (section 5.11 LOCK [0.0, 1.0]) raised
# ValueError that aborted the entire Pass-2 emit loop for the run.
# Post-fix: pipeline applies composite_score = min(1.0, geometric_score)
# so the EVIDENCE score stays at 1.10 in structural_evidence_json but
# the COMPOSITE clamps to 1.0.
# ---------------------------------------------------------------------------


def _build_synthetic_dbw_evidence(geometric_score: float):
    """Construct a DoubleBottomWEvidence with the requested geometric_score.

    Helper for the R2 Critical #1 discriminating tests. The score may
    reach 1.10 at the evidence layer per spec section 5.8 line 718 +
    section 10.5 line 1325 (undercut bonus); construction validates the
    dataclass __post_init__ contract.
    """
    from swing.patterns.double_bottom_w import DoubleBottomWEvidence

    return DoubleBottomWEvidence(
        stage="stage_2",
        recent_stage="undefined",
        trough_1_date=date(2026, 1, 5),
        trough_1_price=10.0,
        trough_1_drawdown_pct=0.20,
        trough_1_avg_volume=1_000_000.0,
        center_peak_date=date(2026, 1, 15),
        center_peak_price=12.0,
        center_peak_retracement_pct=0.50,
        trough_2_date=date(2026, 1, 25),
        trough_2_price=9.5,
        trough_2_avg_volume=1_200_000.0,
        undercut=True,
        trough_1_to_center_duration_days=10,
        center_to_trough_2_duration_days=10,
        pivot_price=12.1,
        criteria_pass={f"criterion_{i}": True for i in range(1, 9)},
        geometric_score=geometric_score,
    )




def test_step_pattern_detect_dbw_evidence_1_10_clamps_composite_to_1_0(
    seeded_env, monkeypatch,
) -> None:
    """Codex R2 Critical #1: DBW evidence geometric_score=1.10 (undercut
    bonus per spec section 5.8 line 718 + section 10.5 line 1325) MUST
    clamp composite_score to 1.0 at the pipeline composite-derivation
    step. The evidence score MUST remain 1.10 in
    structural_evidence_json (the EVIDENCE layer preserves the bonus;
    the COMPOSITE layer caps).

    Discriminating predicate:
      - Monkeypatch the DBW detector to return evidence with
        geometric_score=1.10 (a fully-passing W with undercut bonus).
      - Run _step_pattern_detect.
      - Assert pattern_evaluations row for double_bottom_w has
        composite_score == 1.0 (NOT 1.10).
      - Assert structural_evidence_json carries
        ``geometric_score: 1.10`` verbatim.

    Pre-fix: composite_score = geometric_score = 1.10 -> downstream
    drift_logging _composite_score_histogram raises ValueError ->
    Pass-2 emit loop catches + continues, skipping the insert (and ALL
    other queued inserts for this run since the histogram is shared
    universe-context state). The DBW row would NEVER persist; this
    test would fail because the row would be absent.
    Post-fix: composite_score = min(1.0, 1.10) = 1.0; histogram accepts;
    insert succeeds; row persists with evidence score 1.10 preserved.
    """
    _seed_aplus_candidate(seeded_env["conn"], seeded_env["eval_run_id"])

    # Override the DBW detector to return our synthetic 1.10 evidence.
    fake_dbw_evidence = _build_synthetic_dbw_evidence(geometric_score=1.10)

    def _fake_dbw_detector(*args, **kwargs):
        return fake_dbw_evidence

    # Monkeypatch _pattern_detect_registry to substitute the DBW slot.
    from swing.pipeline import runner as _runner_mod

    original_registry = _runner_mod._pattern_detect_registry

    def _patched_registry():
        tuples = original_registry()
        out = []
        for det_fn, pat_class, version in tuples:
            if pat_class == "double_bottom_w":
                out.append((_fake_dbw_detector, pat_class, version))
            else:
                out.append((det_fn, pat_class, version))
        return tuple(out)

    monkeypatch.setattr(
        _runner_mod, "_pattern_detect_registry", _patched_registry
    )

    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    # Verify DBW row persisted with composite clamped + evidence preserved.
    row = seeded_env["conn"].execute(
        "SELECT composite_score, structural_evidence_json "
        "FROM pattern_evaluations "
        "WHERE pipeline_run_id = ? AND ticker = ? AND pattern_class = ?",
        (
            seeded_env["pipeline_run_id"],
            "ABC",
            "double_bottom_w",
        ),
    ).fetchone()
    assert row is not None, (
        "expected DBW pattern_evaluations row to persist; got None. "
        "Pre-fix symptom: composite_score=1.10 hits "
        "drift_logging._composite_score_histogram which raises "
        "ValueError; the Pass-2 emit loop catches + continues, "
        "skipping the insert."
    )
    composite_score, se_json = row
    # Composite MUST be clamped to 1.0 (NOT 1.10).
    assert composite_score == pytest.approx(1.0), (
        f"expected composite_score clamped to 1.0 (Codex R2 Critical "
        f"#1 fix); got {composite_score}. Pre-fix would have written "
        f"1.10 -- but the pre-fix drift_logging.ValueError prevented "
        f"the insert from happening at all."
    )
    # Evidence score MUST remain 1.10 in structural_evidence_json.
    se = json.loads(se_json)
    assert se.get("geometric_score") == pytest.approx(1.10), (
        f"expected structural_evidence_json.geometric_score == 1.10 "
        f"(evidence layer preserves the undercut bonus per spec "
        f"section 5.8 line 718); got {se.get('geometric_score')!r}"
    )


def test_step_pattern_detect_dbw_1_10_does_not_abort_other_rows(
    seeded_env, monkeypatch,
) -> None:
    """Codex R2 Critical #1 multi-row regression: a single DBW row
    with geometric_score=1.10 MUST NOT suppress drift_logging emit for
    the OTHER 4 detector rows in the same run.

    Pre-fix symptom: drift_logging._composite_score_histogram is built
    from universe_context["composite_scores"] which carries the queued
    1.10 score; any call to capture_feature_distribution for any row
    raises ValueError; the Pass-2 emit loop catches + continues,
    skipping the insert. Effect: ONE all-pass DBW undercut row would
    silently drop the OTHER 4 detector rows from the run.

    Post-fix: composite_score = min(1.0, 1.10) = 1.0 at queue time;
    histogram accepts; all 5 rows persist.
    """
    _seed_aplus_candidate(seeded_env["conn"], seeded_env["eval_run_id"])

    # DBW returns 1.10 (the poisoning row); the other 4 detectors run
    # against the synthetic bars normally (most will geometric_score=0
    # on mild-uptrend fixture, which is fine -- we just need them to
    # emit a row in [0.0, 1.0]).
    fake_dbw = _build_synthetic_dbw_evidence(geometric_score=1.10)

    from swing.pipeline import runner as _runner_mod

    original_registry = _runner_mod._pattern_detect_registry

    def _patched_registry():
        tuples = original_registry()
        out = []
        for det_fn, pat_class, version in tuples:
            if pat_class == "double_bottom_w":
                out.append((lambda *a, **k: fake_dbw, pat_class, version))
            else:
                out.append((det_fn, pat_class, version))
        return tuple(out)

    monkeypatch.setattr(
        _runner_mod, "_pattern_detect_registry", _patched_registry
    )

    _step_pattern_detect(
        cfg=None,
        lease=seeded_env["lease"],
        eval_run_id=seeded_env["eval_run_id"],
        ohlcv_cache=seeded_env["cache"],
    )

    # ALL 5 detector rows MUST persist; the DBW 1.10 row MUST NOT
    # suppress the other 4.
    rows = seeded_env["conn"].execute(
        "SELECT pattern_class, composite_score "
        "FROM pattern_evaluations "
        "WHERE pipeline_run_id = ? AND ticker = ? "
        "ORDER BY pattern_class",
        (seeded_env["pipeline_run_id"], "ABC"),
    ).fetchall()
    classes_persisted = [r[0] for r in rows]
    assert classes_persisted == sorted(DETECTOR_PATTERN_CLASSES), (
        f"expected all 5 detector rows to persist; got "
        f"{classes_persisted}. Pre-fix symptom: ONE DBW row with "
        f"geometric_score=1.10 poisons drift_logging via "
        f"composite_score = geometric_score path; "
        f"_composite_score_histogram raises ValueError; Pass-2 emit "
        f"loop catches + continues, dropping the row's insert. ALL "
        f"rows are affected because the histogram universe is "
        f"SHARED across the run."
    )
    # DBW row's composite is clamped to 1.0.
    by_class = dict(rows)
    assert by_class["double_bottom_w"] == pytest.approx(1.0)
    # All other detectors' composite scores MUST be in [0.0, 1.0] (the
    # real detectors return zero or low scores on the mild-uptrend
    # fixture; no clamp needed).
    for pat_class, comp_score in rows:
        if pat_class == "double_bottom_w":
            continue
        assert 0.0 <= comp_score <= 1.0, (
            f"{pat_class}: composite_score {comp_score} outside "
            f"[0.0, 1.0] (non-DBW detectors don't get the undercut "
            f"bonus)"
        )
