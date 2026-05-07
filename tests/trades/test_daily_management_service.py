"""Service-layer tests for ``compute_daily_approximate_snapshot`` (Phase 8 T3.0).

Plan: docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md §T3.0.
Spec: §4.1 step body; §8.4 datetime impedance + naive UTC ISO; §6.6 trail-MA
period stamp; Codex R1 Major #5 fix (aware → naive UTC canonicalization).
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.trades.daily_management import compute_daily_approximate_snapshot


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "phase8.db"
    db_conn = ensure_schema(db_path)
    db_conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield db_conn
    finally:
        db_conn.close()


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    entry_price: float,
    initial_stop: float,
    initial_shares: int,
    current_avg_cost: float,
    current_size: float,
    current_stop: float,
    pre_trade_locked_at: str,
) -> None:
    """Mirror Phase 7 trades schema; sufficient to satisfy NOT NULL + CHECK."""
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, "
        " current_size, current_avg_cost) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'managing', 'manual_off_pipeline', ?, ?, ?)",
        (
            trade_id, ticker, pre_trade_locked_at[:10],
            entry_price, initial_shares, initial_stop, current_stop,
            pre_trade_locked_at, current_size, current_avg_cost,
        ),
    )


def test_compute_daily_approximate_snapshot_full_path(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: synthetic OHLCV archive returns DataFrame; service produces
    fully-populated SnapshotFields."""
    _seed_trade(
        conn, trade_id=1, ticker="DHC", entry_price=100.0,
        initial_stop=90.0, initial_shares=50,
        current_avg_cost=100.0, current_size=50.0,
        current_stop=92.0, pre_trade_locked_at="2026-05-01T09:30:00",
    )

    df = pd.DataFrame({
        "High":  [105.0, 115.0, 110.0],
        "Low":   [98.0,  102.0, 100.0],
        "Close": [104.0, 113.0, 108.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06", "2026-05-07"]))

    def fake_read_or_fetch_archive(*args: object, **kwargs: object) -> pd.DataFrame:
        return df

    monkeypatch.setattr(
        "swing.data.ohlcv_archive.read_or_fetch_archive",
        fake_read_or_fetch_archive,
    )

    fields = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        ohlcv_archive_dir=tmp_path / "ohlcv",
        archive_history_days=120,
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    assert fields is not None
    assert fields["mfe_mae_precision_level"] == "daily_approximate"
    assert fields["data_asof_session"] == "2026-05-07"
    assert fields["review_date"] == "2026-05-07"
    assert fields["current_price"] == 108.0  # close of asof_session
    assert fields["intraday_high"] == 110.0
    assert fields["intraday_low"] == 100.0
    # MFE = (115 - 100) / 10 = 1.5; MAE = (100 - 98) / 10 = 0.2:
    assert fields["open_MFE_R_to_date"] == 1.5
    assert fields["open_MAE_R_to_date"] == 0.2
    # maturity_stage: MFE 1.5 → '+1.5R_to_+2R'
    assert fields["maturity_stage"] == "+1.5R_to_+2R"
    # capital_utilization = (50 * 108) / 7500 = 0.72
    assert fields["position_capital_utilization_pct"] == pytest.approx(0.72)
    # portfolio_heat = max(0, (100 - 92) * 50) = 400
    assert fields["position_portfolio_heat_contribution_dollars"] == 400.0
    assert fields["position_capital_denominator_dollars"] == 7500.0
    # 21-day SMA needs 21 sessions; we have 3 → trail_MA_candidate_price NULL
    # AND trail_MA_period_days NULL coherently:
    assert fields["trail_MA_candidate_price"] is None
    assert fields["trail_MA_period_days"] is None
    # trail_MA_eligibility_flag NULL when candidate is NULL:
    assert fields["trail_MA_eligibility_flag"] is None
    # created_at is naive UTC ISO (no tz suffix):
    assert "T" in fields["created_at"]
    assert "+" not in fields["created_at"]
    assert "Z" not in fields["created_at"]
    # pipeline_run_id propagates:
    assert fields["pipeline_run_id"] == 1


def test_compute_daily_approximate_snapshot_canonicalizes_aware_run_now_to_naive_UTC(  # noqa: N802
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex R1 Major #5: aware run_now (e.g., HST or UTC-aware) MUST canonicalize
    to naive UTC ISO format before stamping created_at. Without canonicalization,
    the offset suffix breaks lexicographic ordering on the TEXT column when later
    compared to naive rows.

    EXACT pre-fix expected (without canonicalization): created_at like
    '2026-05-07T18:00:00-10:00' or '2026-05-07T18:00:00+00:00'.
    EXACT post-fix expected: created_at like '2026-05-08T04:00:00' for HST input
    (HST = UTC-10; 18:00 HST → 04:00 next-day UTC) — naive (no offset).
    """
    _seed_trade(
        conn, trade_id=1, ticker="DHC", entry_price=100.0,
        initial_stop=90.0, initial_shares=50,
        current_avg_cost=100.0, current_size=50.0,
        current_stop=92.0, pre_trade_locked_at="2026-05-01T09:30:00",
    )
    df = pd.DataFrame({
        "High":  [105.0, 110.0],
        "Low":   [98.0,  100.0],
        "Close": [104.0, 108.0],
    }, index=pd.to_datetime(["2026-05-06", "2026-05-07"]))
    monkeypatch.setattr(
        "swing.data.ohlcv_archive.read_or_fetch_archive",
        lambda *a, **kw: df,
    )

    HST = timezone(timedelta(hours=-10))
    run_now_aware_hst = datetime(2026, 5, 7, 18, 0, 0, tzinfo=HST)

    fields = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=run_now_aware_hst,
        ohlcv_archive_dir=tmp_path / "ohlcv",
        archive_history_days=120,
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    assert fields is not None
    # Naive (no offset suffix), and timestamp converted to UTC:
    assert "+" not in fields["created_at"]
    assert "Z" not in fields["created_at"]
    # 18:00 HST = 04:00 next-day UTC:
    assert fields["created_at"] == "2026-05-08T04:00:00"


def test_compute_daily_approximate_snapshot_returns_None_on_empty_archive(  # noqa: N802
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §A.4 lesson family: empty archive read → return None
    (operator-actionable signal that the ticker is delisted/invalid)."""
    _seed_trade(
        conn, trade_id=1, ticker="ZZZZ", entry_price=100.0,
        initial_stop=90.0, initial_shares=50,
        current_avg_cost=100.0, current_size=50.0,
        current_stop=92.0, pre_trade_locked_at="2026-05-01T09:30:00",
    )
    monkeypatch.setattr(
        "swing.data.ohlcv_archive.read_or_fetch_archive",
        lambda *a, **kw: None,
    )
    result = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        ohlcv_archive_dir=tmp_path / "ohlcv",
        archive_history_days=120,
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    assert result is None


def test_compute_daily_approximate_snapshot_returns_None_on_no_asof_row(  # noqa: N802
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the archive is non-empty but has no row for ``asof_session`` (market
    closed / weekend mismatch / data lag), return None — same operator-actionable
    pattern as the empty-archive case. Skips the upsert without polluting the
    table with partial fields."""
    _seed_trade(
        conn, trade_id=1, ticker="DHC", entry_price=100.0,
        initial_stop=90.0, initial_shares=50,
        current_avg_cost=100.0, current_size=50.0,
        current_stop=92.0, pre_trade_locked_at="2026-05-01T09:30:00",
    )
    df = pd.DataFrame({
        "High":  [105.0, 115.0],
        "Low":   [98.0,  102.0],
        "Close": [104.0, 113.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06"]))  # no 2026-05-07
    monkeypatch.setattr(
        "swing.data.ohlcv_archive.read_or_fetch_archive",
        lambda *a, **kw: df,
    )
    result = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),  # not in df
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        ohlcv_archive_dir=tmp_path / "ohlcv",
        archive_history_days=120,
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    assert result is None


def test_compute_daily_approximate_snapshot_unknown_trade_raises_ValueError(  # noqa: N802
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive: passing trade_id that doesn't exist raises ValueError;
    callers (pipeline runner) should not silently swallow."""
    monkeypatch.setattr(
        "swing.data.ohlcv_archive.read_or_fetch_archive",
        lambda *a, **kw: None,
    )
    with pytest.raises(ValueError, match="trade 999 not found"):
        compute_daily_approximate_snapshot(
            conn, trade_id=999,
            asof_session=date(2026, 5, 7),
            run_now=datetime(2026, 5, 7, 18, 0, 0),
            ohlcv_archive_dir=tmp_path / "ohlcv",
            archive_history_days=120,
            pipeline_run_id=1,
        )


def test_compute_daily_approximate_snapshot_stamps_trail_MA_period_days_when_window_sufficient(  # noqa: N802
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-row policy-versioned value stamping (CLAUDE.md gotcha 2026-05-06,
    Phase 8 R1 M5 lesson): with >= 21 sessions of close history,
    trail_MA_period_days is stamped from the ``trail_MA_period_days_default``
    arg (V1 default 21; Phase 9 risk-policy versioning will mutate the default
    for new rows but cannot retroactively change historical rows)."""
    _seed_trade(
        conn, trade_id=1, ticker="DHC", entry_price=100.0,
        initial_stop=90.0, initial_shares=50,
        current_avg_cost=100.0, current_size=50.0,
        current_stop=92.0, pre_trade_locked_at="2026-04-01T09:30:00",
    )
    # Build a 25-session DataFrame so the SMA window of 21 is fully populated.
    sessions = pd.bdate_range("2026-04-01", periods=25)
    df = pd.DataFrame({
        "High":  [105.0] * 25,
        "Low":   [98.0] * 25,
        "Close": [100.0 + i * 0.1 for i in range(25)],  # monotone increasing
    }, index=sessions)
    monkeypatch.setattr(
        "swing.data.ohlcv_archive.read_or_fetch_archive",
        lambda *a, **kw: df,
    )

    asof = sessions[-1].date()
    fields = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=asof,
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        ohlcv_archive_dir=tmp_path / "ohlcv",
        archive_history_days=120,
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    assert fields is not None
    # Coherent pair: both populated when archive history sufficient:
    assert fields["trail_MA_period_days"] == 21
    assert fields["trail_MA_candidate_price"] is not None
    # SMA mean of last 21 closes: closes[4..24] starting at 100.4 step 0.1 →
    # mean = (100.4 + 102.4) / 2 = 101.4
    assert fields["trail_MA_candidate_price"] == pytest.approx(101.4)
