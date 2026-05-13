"""Phase 10 Sub-bundle D T-D.5 — identification-funnel (spec §3.6) tests."""
from __future__ import annotations

import sqlite3
from dataclasses import fields
from datetime import date
from pathlib import Path

import exchange_calendars
import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.metrics.funnel import (
    APLUS_TAKE_RATE_ZERO_APLUS_SUPPRESSED_TEXT,
    TRADING_DAYS_WINDOW,
    TREND_MIN_RUNS,
    IdentificationFunnelPoint,
    IdentificationFunnelResult,
    compute_identification_funnel,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase10_funnel.db")


def _seed_run(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    run_date: str,
    aplus_count: int = 0,
    watch_count: int = 0,
) -> None:
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) VALUES "
        "(?, ?, ?, ?, 0, ?, ?, 0, 0, 0)",
        (run_id, run_date + "T13:00:00", run_date, run_date,
         aplus_count, watch_count),
    )
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token, "
        "evaluation_run_id) VALUES (?, ?, ?, 'manual', ?, ?, 'complete', "
        "'tok', ?)",
        (run_id, run_date + "T13:00:00", run_date + "T13:30:00",
         run_date, run_date, run_id),
    )


def _seed_candidate(
    conn: sqlite3.Connection,
    *,
    candidate_id: int,
    evaluation_run_id: int,
    ticker: str,
    bucket: str,
) -> None:
    conn.execute(
        "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, "
        "rs_method) VALUES (?, ?, ?, ?, 'universe')",
        (candidate_id, evaluation_run_id, ticker, bucket),
    )


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    trade_origin: str,
    pre_trade_locked_at: str,
    state: str = "managing",
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "current_avg_cost) VALUES (?, ?, '2026-05-01', 10.0, 100, 9.0, "
        "9.0, ?, 'S', 'I', ?, ?, 100, 10.0)",
        (trade_id, ticker, state, trade_origin, pre_trade_locked_at),
    )


# ---------------------------------------------------------------------------
# Spec §3.6 R1 Minor #2 LOCK
# ---------------------------------------------------------------------------

def test_no_watch_take_rate_per_run_field_in_v1():
    """Spec §3.6 R1 Minor #2 LOCK + plan §G T-D.5: NO `watch_take_rate_per_run`."""
    field_names = {f.name for f in fields(IdentificationFunnelPoint)}
    assert "watch_take_rate_per_run" not in field_names, (
        "Spec §3.6 R1 M#2 LOCK + plan §G T-D.5: V1 surfaces watch counts "
        f"ONLY; got fields: {field_names}"
    )


# ---------------------------------------------------------------------------
# Discriminating tests per plan §G T-D.5
# ---------------------------------------------------------------------------

def test_compute_funnel_zero_runs_returns_empty_with_trend_suppressed(conn):
    result = compute_identification_funnel(conn, asof_date=date(2026, 5, 12))
    assert isinstance(result, IdentificationFunnelResult)
    assert result.trend_runs == ()
    assert result.trend_suppressed is True


def test_compute_funnel_per_run_aggregation(conn):
    """Per-run point counts candidates + trades aligned to the run's session."""
    _seed_run(conn, run_id=1, run_date="2026-05-08")
    # Seed 3 A+ candidates + 5 watch candidates for run 1.
    for i in range(3):
        _seed_candidate(conn, candidate_id=10 + i,
                        evaluation_run_id=1,
                        ticker=f"AAP{i}", bucket="aplus")
    for i in range(5):
        _seed_candidate(conn, candidate_id=20 + i,
                        evaluation_run_id=1,
                        ticker=f"WAT{i}", bucket="watch")
    # Seed 2 A+ trades + 1 watch trade with locked_at on 2026-05-08.
    _seed_trade(conn, trade_id=1, ticker="AAP0",
                trade_origin="pipeline_aplus",
                pre_trade_locked_at="2026-05-08T09:30:00")
    _seed_trade(conn, trade_id=2, ticker="AAP1",
                trade_origin="pipeline_aplus",
                pre_trade_locked_at="2026-05-08T09:30:00")
    _seed_trade(conn, trade_id=3, ticker="WAT0",
                trade_origin="pipeline_watch_hyp_recs",
                pre_trade_locked_at="2026-05-08T09:30:00")
    result = compute_identification_funnel(
        conn, asof_date=date(2026, 5, 12),
    )
    assert len(result.trend_runs) == 1
    pt = result.trend_runs[0]
    assert pt.pipeline_run_id == 1
    assert pt.aplus_identifications_per_run == 3
    assert pt.aplus_trades_taken_per_run == 2
    assert pt.aplus_take_rate_per_run == pytest.approx(2 / 3)
    assert pt.watch_identifications_per_run == 5
    assert pt.watch_trades_taken_per_run == 1


def test_compute_funnel_zero_aplus_identifications_returns_suppressed_take_rate(
    conn,
):
    """Spec §A.20 + dispatch brief §0.11 BINDING: 0 A+ → suppressed text."""
    _seed_run(conn, run_id=1, run_date="2026-05-08")
    # Seed 2 watch but ZERO aplus.
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=1,
                    ticker="WW1", bucket="watch")
    _seed_candidate(conn, candidate_id=2, evaluation_run_id=1,
                    ticker="WW2", bucket="watch")
    result = compute_identification_funnel(
        conn, asof_date=date(2026, 5, 12),
    )
    pt = result.trend_runs[0]
    assert pt.aplus_identifications_per_run == 0
    assert pt.aplus_take_rate_per_run is None
    assert (
        pt.aplus_take_rate_suppressed_text
        == APLUS_TAKE_RATE_ZERO_APLUS_SUPPRESSED_TEXT
    )
    assert pt.aplus_take_rate_suppressed_text == (
        "N/A — 0 A+ identifications this run"
    )


def test_compute_funnel_trend_at_5_runs_suppressed(conn):
    """Spec §4.6 + plan §G T-D.5: trend suppressed at <10 runs."""
    cal = exchange_calendars.get_calendar("XNYS")
    asof = date(2026, 5, 12)
    sessions = sorted({
        ts.date().isoformat()
        for ts in cal.sessions_window(pd.Timestamp(asof), -5)
    })
    for i, sd in enumerate(sessions, start=1):
        _seed_run(conn, run_id=i, run_date=sd)
    result = compute_identification_funnel(conn, asof_date=asof)
    assert result.trend_suppressed is True
    assert result.trend_suppressed_text is not None


def test_compute_funnel_trend_at_10_runs_renders(conn):
    """Trend rendered once ≥10 runs."""
    cal = exchange_calendars.get_calendar("XNYS")
    asof = date(2026, 5, 12)
    sessions = sorted({
        ts.date().isoformat()
        for ts in cal.sessions_window(pd.Timestamp(asof), -10)
    })
    for i, sd in enumerate(sessions, start=1):
        _seed_run(conn, run_id=i, run_date=sd)
    result = compute_identification_funnel(conn, asof_date=asof)
    assert result.trend_suppressed is False
    assert len(result.trend_runs) == 10


def test_funnel_trend_30_sessions_inclusive_of_end(conn):
    """Plan §G T-D.5 + Codex R5/R6 BINDING: window includes exactly the
    most-recent 30 sessions ending at asof (off-by-one defense).

    Seed 31 sessions; assert only most-recent 30 are present.
    """
    cal = exchange_calendars.get_calendar("XNYS")
    asof = date(2026, 5, 12)
    sessions = sorted({
        ts.date().isoformat()
        for ts in cal.sessions_window(pd.Timestamp(asof), -31)
    })
    assert len(sessions) == 31
    for i, sd in enumerate(sessions, start=1):
        _seed_run(conn, run_id=i, run_date=sd)
    result = compute_identification_funnel(conn, asof_date=asof)
    assert len(result.trend_runs) == 30
    # Discriminating: the OLDEST seeded session is excluded.
    rendered_dates = {p.run_date for p in result.trend_runs}
    assert sessions[0] not in rendered_dates, (
        f"Oldest session {sessions[0]} must be excluded (window=30 ending "
        f"at {asof}); got rendered_dates: {sorted(rendered_dates)}"
    )
    # And the newest is INCLUDED (inclusive of end).
    assert sessions[-1] in rendered_dates


def test_historical_funnel_uses_current_trade_state(conn):
    """Plan §A.0.1 + dispatch brief §0.10: historical point counts a
    trade with origin='pipeline_aplus' even if its current state is
    'closed' — uses CURRENT state, not historical reconstruction."""
    _seed_run(conn, run_id=1, run_date="2026-05-08")
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=1,
                    ticker="ZZZ", bucket="aplus")
    # Seed a trade that's now CLOSED but was locked at that session.
    _seed_trade(conn, trade_id=1, ticker="ZZZ",
                trade_origin="pipeline_aplus",
                pre_trade_locked_at="2026-05-08T09:30:00",
                state="closed")
    result = compute_identification_funnel(
        conn, asof_date=date(2026, 5, 12),
    )
    pt = result.trend_runs[0]
    # Closed trade still counts (CURRENT state pipeline_aplus + locked_at
    # matches run.session).
    assert pt.aplus_trades_taken_per_run == 1
    assert pt.aplus_take_rate_per_run == 1.0


def test_funnel_excludes_legacy_origin_trades(conn):
    """Discriminating: trade_origin='manual_off_pipeline' NOT counted."""
    _seed_run(conn, run_id=1, run_date="2026-05-08")
    _seed_candidate(conn, candidate_id=1, evaluation_run_id=1,
                    ticker="ZZZ", bucket="aplus")
    _seed_trade(conn, trade_id=1, ticker="ZZZ",
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-05-08T09:30:00")
    result = compute_identification_funnel(
        conn, asof_date=date(2026, 5, 12),
    )
    pt = result.trend_runs[0]
    assert pt.aplus_trades_taken_per_run == 0


def test_funnel_session_anchor_uses_backward_looking(conn):
    """Plan §A.15 LOCK: asof_date is backward-looking."""
    # Default asof should be `last_completed_session(now)`.
    result = compute_identification_funnel(conn)
    # asof_date pulled from helper; just verify it's an ISO string.
    assert isinstance(result.asof_date, str)
    assert len(result.asof_date) == len("YYYY-MM-DD")


def test_compute_funnel_returns_window_size(conn):
    result = compute_identification_funnel(
        conn, asof_date=date(2026, 5, 12), run_window=15,
    )
    assert result.trend_window_sessions == 15


def test_dataclass_post_init_rejects_invalid_inputs():
    base = dict(
        pipeline_run_id=1,
        run_date="2026-05-08",
        aplus_identifications_per_run=0,
        aplus_trades_taken_per_run=0,
        aplus_take_rate_per_run=None,
        aplus_take_rate_suppressed_text=None,
        watch_identifications_per_run=0,
        watch_trades_taken_per_run=0,
    )
    with pytest.raises(ValueError, match="pipeline_run_id"):
        IdentificationFunnelPoint(**{**base, "pipeline_run_id": 0})
    with pytest.raises(ValueError, match="aplus_identifications_per_run"):
        IdentificationFunnelPoint(
            **{**base, "aplus_identifications_per_run": -1}
        )
    with pytest.raises(ValueError, match="aplus_take_rate_per_run"):
        IdentificationFunnelPoint(
            **{**base, "aplus_take_rate_per_run": 1.5}
        )


def test_trend_window_constant_is_30():
    assert TRADING_DAYS_WINDOW == 30
    assert TREND_MIN_RUNS == 10
