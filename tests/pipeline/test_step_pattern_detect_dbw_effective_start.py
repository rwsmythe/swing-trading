"""D53.1 F2 -- the double_bottom_w EFFECTIVE window start in the runner.

After D53 the runner hands the DBW detector ``windows[-1]`` from the
production generator, whose ``start_date`` is the trough-2 anchor. The
pattern starts at trough 1. F2: for a DBW verdict with a non-zero
``geometric_score`` the runner computes ONE effective start
(``evidence.trough_1_date``) in Pass 1 and carries it to exactly two sites:
the template-match close slice and the persisted ``window_start_date``.
Other classes and zero-score DBW rows keep the generator start, and the
temporal log's anchors-JSON ``window`` block stays the generator's frozen
emission (RD ruling 1a).

All tests run the REAL generator + REAL detectors through
``_step_pattern_detect`` (cfg=None stub path) over synthetic W bars.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from swing.data.db import ensure_schema
from swing.data.models import (
    Candidate,
    CriterionResult,
    EvaluationRun,
    PatternExemplar,
)
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.data.repos.pattern_exemplars import insert_exemplar
from swing.metrics.pattern_outcomes import _count_reached_1r_hit_stop
from swing.patterns.foundation import generate_candidate_windows
from swing.pipeline.runner import _step_pattern_detect
from tests.patterns.test_double_bottom_w import _bars_uvwx_dbw

TICKER = "UVWX"
TROUGH_1 = date(2026, 1, 24)
TROUGH_2 = date(2026, 3, 3)


class _StubOhlcvCache:
    def __init__(self, bars):
        self._bars = bars

    def get_or_fetch(self, *, ticker: str, window_days: int = 200):
        if ticker.upper() != TICKER:
            raise ValueError(f"No data for {ticker}")
        return self._bars


class _StubLease:
    def __init__(self, conn: sqlite3.Connection, run_id: int):
        self._conn = conn
        self.run_id = run_id

    def fenced_write(self):
        @contextmanager
        def _cm():
            yield self._conn

        return _cm()


@pytest.fixture
def dbw_env(tmp_path: Path):
    conn = ensure_schema(tmp_path / "d53_1.db")
    run_id = int(conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, trigger, data_asof_date, action_session_date,
             state, lease_token)
        VALUES ('2026-03-10T18:00:00', 'manual', '2026-03-10',
                '2026-03-11', 'running', 'tok-d53-1')
        """
    ).lastrowid)
    eval_run_id = insert_evaluation_run(
        conn,
        EvaluationRun(
            id=None, run_ts="2026-03-10T18:00:00",
            data_asof_date="2026-03-10", action_session_date="2026-03-11",
            finviz_csv_path=None, tickers_evaluated=1, aplus_count=1,
            watch_count=0, skip_count=0, excluded_count=0, error_count=0,
        ),
    )
    # All 8 trend-template criteria pass -> current_stage == stage_2, so
    # the DBW detector's Stage-2 gate opens and the zigzag slice runs.
    insert_candidates(conn, eval_run_id, [Candidate(
        ticker=TICKER, bucket="aplus", close=24.0, pivot=24.1,
        initial_stop=19.0, adr_pct=2.5, tight_streak=3, pullback_pct=5.0,
        prior_trend_pct=40.0, rs_rank=85, rs_return_12w_vs_spy=12.0,
        rs_method="universe", pattern_tag=None, notes=None,
        criteria=tuple(
            CriterionResult(f"tt{i}", "trend_template", "pass")
            for i in range(1, 9)
        ),
    )])
    conn.commit()
    bars = _bars_uvwx_dbw()
    return {
        "conn": conn, "run_id": run_id, "eval_run_id": eval_run_id,
        "bars": bars, "lease": _StubLease(conn, run_id),
        "cache": _StubOhlcvCache(bars),
    }


def _run_step(env, monkeypatch=None, spy=None):
    if spy is not None:
        from swing.pipeline import runner as _runner_mod
        monkeypatch.setattr(_runner_mod, "match_forward", spy)
    _step_pattern_detect(
        cfg=None, lease=env["lease"], eval_run_id=env["eval_run_id"],
        ohlcv_cache=env["cache"],
    )


def _row(env, pattern_class: str):
    return env["conn"].execute(
        "SELECT window_start_date, window_end_date, geometric_score, "
        "structural_evidence_json FROM pattern_evaluations "
        "WHERE pipeline_run_id = ? AND ticker = ? AND pattern_class = ?",
        (env["run_id"], TICKER, pattern_class),
    ).fetchone()


def _generator_window(env):
    return generate_candidate_windows(
        env["bars"], "zigzag_pivot", ticker=TICKER, timeframe="daily",
    )[-1]


def test_fixture_premise_generator_start_is_trough_2_and_dbw_scores(dbw_env):
    """Pins the premise the other tests stand on: the production
    generator's last window starts at trough 2, and the runner's DBW
    verdict on it is non-zero with trough 1 earlier than that start."""
    window = _generator_window(dbw_env)
    assert window.start_date == TROUGH_2
    _run_step(dbw_env)
    start, _end, score, ev_json = _row(dbw_env, "double_bottom_w")
    ev = json.loads(ev_json)
    assert score > 0
    assert ev["trough_1_date"] == TROUGH_1.isoformat()
    assert ev["trough_2_date"] == TROUGH_2.isoformat()


def test_dbw_persisted_window_start_is_trough_1(dbw_env):
    _run_step(dbw_env)
    start, end, _score, _ev = _row(dbw_env, "double_bottom_w")
    window = _generator_window(dbw_env)
    assert start == TROUGH_1.isoformat()
    assert end == window.end_date.isoformat()


def test_dbw_template_slice_first_bar_is_trough_1(dbw_env, monkeypatch):
    """RD's return QA condition: assert the SLICE (the measurement input),
    not only the column. A confirmed DBW exemplar on the same bars makes
    Pass 2 call match_forward; the spy records the candidate close series."""
    bars = dbw_env["bars"]
    insert_exemplar(dbw_env["conn"], PatternExemplar(
        id=None, ticker=TICKER, timeframe="daily",
        start_date=TROUGH_1.isoformat(), end_date=TROUGH_2.isoformat(),
        proposed_pattern_class="double_bottom_w", final_decision="confirmed",
        label_source="closed_loop_review", structural_evidence_json="{}",
        geometric_score_json="{}",
        created_at="2026-03-01T00:00:00", created_by="operator",
        gold_validated_at="2026-03-01T00:00:00",
    ))
    dbw_env["conn"].commit()
    seen: dict[str, np.ndarray] = {}

    def _spy(**kwargs):
        seen[kwargs["candidate_pattern_class"]] = kwargs[
            "candidate_close_prices"
        ]
        return []

    _run_step(dbw_env, monkeypatch, _spy)
    assert "double_bottom_w" in seen, "match_forward never saw the DBW slice"
    window = _generator_window(dbw_env)
    expected = bars.loc[
        (bars.index >= str(TROUGH_1)) & (bars.index <= str(window.end_date)),
        "Close",
    ].to_numpy(dtype=float)
    got = seen["double_bottom_w"]
    assert got[0] == pytest.approx(float(bars.loc[str(TROUGH_1), "Close"]))
    assert np.array_equal(got, expected)


def test_zero_score_dbw_keeps_generator_start(dbw_env):
    """A zero-score DBW verdict is a non-detection: its zero envelope
    stamps trough_1_date at the window END, so an implementation that took
    trough_1_date without the non-zero condition would persist the END as
    the start. The Stage-2 gate is closed here (no trend-template passes)."""
    dbw_env["conn"].execute("DELETE FROM candidate_criteria")
    dbw_env["conn"].commit()
    _run_step(dbw_env)
    start, end, score, ev_json = _row(dbw_env, "double_bottom_w")
    window = _generator_window(dbw_env)
    assert score == 0
    assert json.loads(ev_json)["trough_1_date"] == end
    assert start == window.start_date.isoformat()


def test_non_dbw_class_keeps_generator_start(dbw_env):
    """Discriminator against an over-wide change: every other class on the
    same run persists the generator window start."""
    _run_step(dbw_env)
    window = _generator_window(dbw_env)
    for pattern_class in (
        "vcp", "flat_base", "cup_with_handle", "high_tight_flag",
    ):
        start, _end, _score, _ev = _row(dbw_env, pattern_class)
        assert start == window.start_date.isoformat(), pattern_class


def test_anchors_json_window_block_stays_generator_emission(dbw_env):
    """RD ruling 1a: the temporal log's anchors-JSON window block is the
    generator's frozen emission, unchanged by F2."""
    _run_step(dbw_env)
    blob = dbw_env["conn"].execute(
        "SELECT structural_anchors_json FROM pattern_detection_events "
        "WHERE pipeline_run_id = ? AND ticker = ? AND pattern_class = ?",
        (dbw_env["run_id"], TICKER, "double_bottom_w"),
    ).fetchone()
    assert blob is not None
    anchors = json.loads(blob[0])
    window = _generator_window(dbw_env)
    assert anchors["window"]["start_date"] == window.start_date.isoformat()
    assert anchors["window"]["start_date"] == TROUGH_2.isoformat()
    assert anchors["window"]["anchor_date"] == TROUGH_2.isoformat()
    assert anchors["evidence"]["trough_1_date"] == TROUGH_1.isoformat()


def _seed_confirmed_dbw_exemplar(conn, *, start: date, end: date) -> None:
    insert_exemplar(conn, PatternExemplar(
        id=None, ticker=TICKER, timeframe="daily",
        start_date=start.isoformat(), end_date=end.isoformat(),
        proposed_pattern_class="double_bottom_w", final_decision="confirmed",
        label_source="closed_loop_review", structural_evidence_json="{}",
        geometric_score_json="{}",
        created_at="2026-03-12T00:00:00", created_by="operator",
        gold_validated_at="2026-03-12T00:00:00",
    ))
    conn.commit()


def test_pattern_outcomes_counts_exemplar_overlapping_only_trough_1_to_trough_2(
    dbw_env,
):
    """RD ruling 2a: an exemplar overlapping the DBW evaluation ONLY on
    [trough_1, trough_2) COUNTS once the persisted start is trough 1 (it did
    not while the start was trough 2)."""
    _run_step(dbw_env)
    _seed_confirmed_dbw_exemplar(
        dbw_env["conn"],
        start=TROUGH_1 - timedelta(days=10),
        end=TROUGH_2 - timedelta(days=1),
    )
    denominator, _r, _h = _count_reached_1r_hit_stop(
        dbw_env["conn"], pattern_class="double_bottom_w",
    )
    assert denominator == 1


def test_pattern_outcomes_exemplar_ending_before_trough_1_does_not_count(
    dbw_env,
):
    """RD ruling 2a boundary twin: an exemplar ending strictly before
    trough 1 does not overlap the evaluation and does not count."""
    _run_step(dbw_env)
    _seed_confirmed_dbw_exemplar(
        dbw_env["conn"],
        start=TROUGH_1 - timedelta(days=30),
        end=TROUGH_1 - timedelta(days=1),
    )
    denominator, _r, _h = _count_reached_1r_hit_stop(
        dbw_env["conn"], pattern_class="double_bottom_w",
    )
    assert denominator == 0
