"""_step_daily_management integration tests (Task 4.0)."""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.pipeline.runner import _step_daily_management


def _seed_trade(
    conn,
    *,
    trade_id: int,
    ticker: str,
    state: str,
    entry_price: float,
    initial_stop: float,
    initial_shares: float,
    current_avg_cost: float,
    current_size: float,
    current_stop: float,
    pre_trade_locked_at: str,
) -> None:
    """Insert a trade row at a specific id with the minimum schema-required
    columns. Uses raw SQL because the test plan pins ``trade_id`` explicitly
    and we want to seed a closed trade alongside two open trades in one DB.
    """
    conn.execute(
        """
        INSERT INTO trades
            (id, ticker, entry_date, entry_price, initial_shares,
             initial_stop, current_stop, state,
             trade_origin, pre_trade_locked_at,
             current_size, current_avg_cost)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual_off_pipeline', ?, ?, ?)
        """,
        (
            trade_id, ticker, "2026-04-15", entry_price, initial_shares,
            initial_stop, current_stop, state,
            pre_trade_locked_at, current_size, current_avg_cost,
        ),
    )
    # Mirror insert_trade_with_event's mandatory 'entry' audit row.
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json)
        VALUES (?, ?, 'entry', '{}')
        """,
        (trade_id, pre_trade_locked_at),
    )


@pytest.fixture
def synthetic_lease_and_trades(tmp_path: Path, monkeypatch):
    """Sets up a fresh DB at v16, seeds 2 open trades (DHC managing, ZZ entered)
    + 1 closed trade (VIR), patches the OHLCV archive to return a synthetic
    DataFrame, and returns a (lease, conn) pair compatible with
    lease.fenced_write()."""
    db_path = tmp_path / "phase8.db"
    conn = ensure_schema(db_path)
    conn.execute("PRAGMA foreign_keys=ON")

    # Seed pipeline_run row FIRST so subsequent FK references are valid.
    # 'complete' (not 'completed') matches the pipeline_runs.state CHECK enum.
    conn.execute(
        """
        INSERT INTO pipeline_runs
            (id, started_ts, finished_ts, trigger,
             data_asof_date, action_session_date, state, lease_token)
        VALUES (?, ?, ?, 'manual', ?, ?, 'complete', 'tok-stub')
        """,
        (99, "2026-05-07T18:00:00", "2026-05-07T18:30:00",
         "2026-05-07", "2026-05-08"),
    )

    _seed_trade(conn, trade_id=1, ticker="DHC", state="managing",
                entry_price=100.0, initial_stop=90.0, initial_shares=50.0,
                current_avg_cost=100.0, current_size=50.0, current_stop=92.0,
                pre_trade_locked_at="2026-05-01T09:30:00")
    _seed_trade(conn, trade_id=2, ticker="ZZ", state="entered",
                entry_price=50.0, initial_stop=45.0, initial_shares=100.0,
                current_avg_cost=50.0, current_size=100.0, current_stop=45.0,
                pre_trade_locked_at="2026-05-06T09:30:00")
    _seed_trade(conn, trade_id=3, ticker="VIR", state="closed",
                entry_price=80.0, initial_stop=70.0, initial_shares=60.0,
                current_avg_cost=80.0, current_size=0.0, current_stop=70.0,
                pre_trade_locked_at="2026-04-15T09:30:00")
    conn.commit()

    # Synthetic OHLCV — same DataFrame for both tickers; covers the asof
    # session anchors used by the tests (2026-05-07, 2026-05-08, 2026-05-11).
    df = pd.DataFrame({
        "High":  [105.0, 115.0, 110.0, 112.0, 113.0, 114.0],
        "Low":   [98.0,  102.0, 100.0, 101.0, 102.0, 103.0],
        "Close": [104.0, 113.0, 108.0, 109.0, 110.0, 111.0],
    }, index=pd.to_datetime([
        "2026-05-05", "2026-05-06", "2026-05-07",
        "2026-05-08", "2026-05-10", "2026-05-11",
    ]))
    # Monkeypatch the source module — daily_management.compute_*
    # imports it lazily inside the function, so the SOURCE-module
    # name is what gets bound at call time. This matches the
    # existing tests/trades/test_daily_management_service.py convention.
    monkeypatch.setattr(
        "swing.data.ohlcv_archive.read_or_fetch_archive",
        lambda *a, **kw: df,
    )

    # Construct a minimal Lease stub that yields the connection from
    # fenced_write(). Mirrors the cadence-step test pattern; the runner
    # function only needs ``lease.fenced_write()`` to yield a usable conn.
    class _StubLease:
        # Codex R1 Critical 1: ``_step_daily_management`` reads
        # ``lease.run_id`` to wire ``pipeline_run_id`` into the snapshot
        # (FK to pipeline_runs.id). The fixture pre-seeded
        # pipeline_runs.id=99, so the stub must mirror that.
        run_id = 99

        def fenced_write(self):
            from contextlib import contextmanager

            @contextmanager
            def _cm():
                yield conn
            return _cm()

    return _StubLease(), conn


def test_step_emits_one_snapshot_per_open_trade(synthetic_lease_and_trades):
    """EXACT pre-fix: 0 daily_snapshot rows.
    EXACT post-fix: 2 daily_snapshot rows (DHC + ZZ); 0 for VIR."""
    lease, conn = synthetic_lease_and_trades
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),  # unused (archive monkeypatched)
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    rows = conn.execute(
        "SELECT trade_id FROM daily_management_records "
        "WHERE record_type = 'daily_snapshot' ORDER BY trade_id"
    ).fetchall()
    assert [r[0] for r in rows] == [1, 2]


def test_step_skips_closed_trades(synthetic_lease_and_trades):
    """EXACT post-fix: VIR (trade_id=3) has 0 snapshots."""
    lease, conn = synthetic_lease_and_trades
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    count = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records WHERE trade_id = 3"
    ).fetchone()[0]
    assert count == 0


def test_step_idempotent_same_day_rerun(synthetic_lease_and_trades):
    """Second run UPDATEs in place (preserves management_record_id).

    EXACT pre-fix (with REPLACE): rec_id_after_second != rec_id_after_first.
    EXACT post-fix: rec_id_after_second == rec_id_after_first."""
    lease, conn = synthetic_lease_and_trades
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    rec1 = conn.execute(
        "SELECT management_record_id FROM daily_management_records "
        "WHERE trade_id = 1"
    ).fetchone()[0]

    # Second run with same asof_session:
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 19, 0, 0),  # later same day
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    rec2 = conn.execute(
        "SELECT management_record_id FROM daily_management_records "
        "WHERE trade_id = 1"
    ).fetchone()[0]
    assert rec1 == rec2  # SAME PK


def test_step_triggers_entered_to_managing_transition(synthetic_lease_and_trades):
    """ZZ starts as 'entered'; after first snapshot, state = 'managing'."""
    lease, conn = synthetic_lease_and_trades
    pre_state = conn.execute(
        "SELECT state FROM trades WHERE id = 2").fetchone()[0]
    assert pre_state == "entered"

    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    post_state = conn.execute(
        "SELECT state FROM trades WHERE id = 2").fetchone()[0]
    assert post_state == "managing"


def test_step_no_back_fill_on_gap(synthetic_lease_and_trades, monkeypatch):
    """If pipeline ran at asof=Friday + asof=Monday (with Sat/Sun gap), NO
    rows emitted for Saturday/Sunday — gap-flagged policy (spec §4.3).

    EXACT post-fix expected: distinct(data_asof_session) for each trade ==
    {'2026-05-08', '2026-05-11'} — the two run anchors only, NOT a contiguous
    range filled in by back-fill."""
    lease, conn = synthetic_lease_and_trades

    # Monkeypatch last_completed_session at the runner-module scope so the
    # test fixture controls the asof anchor explicitly:
    runner_anchor_session: list[date] = [date(2026, 5, 8)]  # Fri

    def fake_last_completed_session(_now):
        return runner_anchor_session[0]

    monkeypatch.setattr(
        "swing.pipeline.runner.last_completed_session",
        fake_last_completed_session,
    )

    # Run #1: Friday session
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 8, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )

    # Skip Sat + Sun (no pipeline runs); next anchor = Monday
    runner_anchor_session[0] = date(2026, 5, 11)
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 11, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )

    # Per-trade distinct sessions:
    sessions_per_trade = conn.execute(
        "SELECT trade_id, GROUP_CONCAT(DISTINCT data_asof_session) "
        "FROM daily_management_records "
        "WHERE record_type = 'daily_snapshot' "
        "GROUP BY trade_id ORDER BY trade_id"
    ).fetchall()
    assert sessions_per_trade, "expected at least one snapshot row"
    for trade_id, sessions_csv in sessions_per_trade:
        sessions = sorted(sessions_csv.split(","))
        assert sessions == ["2026-05-08", "2026-05-11"], (
            f"trade {trade_id} got sessions {sessions!r}; "
            "expected exactly the two run anchors (no back-fill of Sat/Sun)"
        )


def test_step_failure_does_not_abort_pipeline(
    synthetic_lease_and_trades, monkeypatch, caplog,
):
    """Cadence-step semantics: synthetic failure in compute logs warning;
    rest of pipeline (other open trades) still emit snapshots.

    EXACT pre-fix (without try/except): RuntimeError propagates; 0 snapshots.
    EXACT post-fix: warning logged for failed trade; OTHER trades still emit."""
    lease, conn = synthetic_lease_and_trades

    def fail_for_trade_1(conn_inner, *, trade_id, **kwargs):
        if trade_id == 1:
            raise RuntimeError("synthetic-trade-1-failure")
        # For trade_id != 1, return a minimal valid snapshot dict:
        return {
            "review_date": "2026-05-07", "data_asof_session": "2026-05-07",
            "created_at": "2026-05-07T18:00:00",
            "mfe_mae_precision_level": "daily_approximate",
            "pipeline_run_id": kwargs.get("pipeline_run_id"),
            "current_price": 50.0, "current_stop": 45.0,
            "current_size": 100.0, "current_avg_cost": 50.0,
            "open_R_effective": 0.0, "open_MFE_R_to_date": 0.0,
            "open_MAE_R_to_date": 0.0, "intraday_high": 51.0,
            "intraday_low": 49.0,
            "position_capital_utilization_pct": 0.667,
            "position_capital_denominator_dollars": 7500.0,
            "position_portfolio_heat_contribution_dollars": 500.0,
            "maturity_stage": "pre_+1.5R",
            "trail_MA_candidate_price": None,
            "trail_MA_period_days": None,
            "trail_MA_eligibility_flag": None,
        }
    monkeypatch.setattr(
        "swing.trades.daily_management.compute_daily_approximate_snapshot",
        fail_for_trade_1,
    )

    with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
        _step_daily_management(
            lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
            eval_run_id=99, archive_history_days=120,
            ohlcv_archive_dir=Path("/dev/null"),
            capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
        )
    # Trade 2 (ZZ) snapshot exists; trade 1 (DHC) has none:
    rows = conn.execute(
        "SELECT trade_id FROM daily_management_records "
        "WHERE record_type = 'daily_snapshot' ORDER BY trade_id"
    ).fetchall()
    assert [r[0] for r in rows] == [2]
    # Warning was logged:
    assert any(
        "synthetic-trade-1-failure" in r.getMessage() for r in caplog.records
    )


def test_step_re_raises_LeaseRevoked(synthetic_lease_and_trades, monkeypatch):
    """Codex R2 Major #5 discriminating test: LeaseRevoked MUST propagate
    (force-clear authoritative); the broad `except Exception` MUST NOT catch it.

    EXACT pre-fix expected (broad-except only): no exception raised; warning logged.
    EXACT post-fix expected: LeaseRevoked propagates out of _step_daily_management."""
    from swing.pipeline.lease import LeaseRevoked
    lease, conn = synthetic_lease_and_trades

    def raise_revoked(conn_inner, *, trade_id, **kwargs):
        raise LeaseRevoked("synthetic-revoke-during-snapshot")
    monkeypatch.setattr(
        "swing.trades.daily_management.compute_daily_approximate_snapshot",
        raise_revoked,
    )

    with pytest.raises(LeaseRevoked, match="synthetic-revoke-during-snapshot"):
        _step_daily_management(
            lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
            eval_run_id=99, archive_history_days=120,
            ohlcv_archive_dir=Path("/dev/null"),
            capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
        )
