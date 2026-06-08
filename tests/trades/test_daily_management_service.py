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
    ticker: str = "DHC",
    entry_price: float = 100.0,
    initial_stop: float = 90.0,
    initial_shares: int = 50,
    current_avg_cost: float = 100.0,
    current_size: float = 50.0,
    current_stop: float = 92.0,
    pre_trade_locked_at: str = "2026-05-01T09:30:00",
    state: str = "managing",
) -> None:
    """Mirror Phase 7 trades schema; sufficient to satisfy NOT NULL + CHECK."""
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, "
        " current_size, current_avg_cost) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual_off_pipeline', ?, ?, ?)",
        (
            trade_id, ticker, pre_trade_locked_at[:10],
            entry_price, initial_shares, initial_stop, current_stop, state,
            pre_trade_locked_at, current_size, current_avg_cost,
        ),
    )
    # Commit the seed so the service-under-test's `with conn:` rollback on
    # error does NOT also wipe the seeded trade row (T3.2 rollback tests
    # depend on the seed surviving the rolled-back inner transaction).
    conn.commit()


def _build_event_log_request(
    *,
    trade_id: int,
    stop_changed: int,
    prior_stop: float | None = None,
    new_stop: float | None = None,
    stop_change_reason: str | None = None,
    action_taken: str | None = None,
    action_reason: str | None = None,
    rule_violation_suspected: int = 0,
    emotional_state: str = '["calm"]',
    created_at: str = "2026-05-07T18:00:00",
    review_date: str = "2026-05-07",
    data_asof_session: str = "2026-05-07",
    mfe_mae_precision_level: str = "daily_approximate",
    thesis_status: str | None = None,
    management_notes: str | None = None,
):
    """Construct an EventLogRequest fixture for T3.2 service tests."""
    from swing.trades.daily_management import EventLogRequest

    return EventLogRequest(
        trade_id=trade_id,
        review_date=review_date,
        data_asof_session=data_asof_session,
        created_at=created_at,
        mfe_mae_precision_level=mfe_mae_precision_level,
        stop_changed=stop_changed,
        prior_stop=prior_stop,
        new_stop=new_stop,
        stop_change_reason=stop_change_reason,
        action_taken=action_taken,
        action_reason=action_reason,
        rule_violation_suspected=rule_violation_suspected,
        emotional_state=emotional_state,
        thesis_status=thesis_status,
        management_notes=management_notes,
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

    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        archive_df=df,
        expected_ticker="DHC",
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    fields = res.fields
    assert res.miss_reason is None
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
    HST = timezone(timedelta(hours=-10))
    run_now_aware_hst = datetime(2026, 5, 7, 18, 0, 0, tzinfo=HST)

    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=run_now_aware_hst,
        archive_df=df,
        expected_ticker="DHC",
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    fields = res.fields
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
    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        archive_df=None,
        expected_ticker="ZZZZ",
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    assert res.fields is None
    assert res.miss_reason == "warm_empty_or_stale"


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
    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),  # not in df
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        archive_df=df,
        expected_ticker="DHC",
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    assert res.fields is None
    assert res.miss_reason == "no_eligible_window"


def test_compute_daily_approximate_snapshot_unknown_trade_raises_ValueError(  # noqa: N802
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive: passing trade_id that doesn't exist raises ValueError;
    callers (pipeline runner) should not silently swallow."""
    with pytest.raises(ValueError, match="trade 999 not found"):
        compute_daily_approximate_snapshot(
            conn, trade_id=999,
            asof_session=date(2026, 5, 7),
            run_now=datetime(2026, 5, 7, 18, 0, 0),
            archive_df=None,
            expected_ticker="DHC",
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

    asof = sessions[-1].date()
    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=asof,
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        archive_df=df,
        expected_ticker="DHC",
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    fields = res.fields
    assert fields is not None
    # Coherent pair: both populated when archive history sufficient:
    assert fields["trail_MA_period_days"] == 21
    assert fields["trail_MA_candidate_price"] is not None
    # SMA mean of last 21 closes: closes[4..24] starting at 100.4 step 0.1 →
    # mean = (100.4 + 102.4) / 2 = 101.4
    assert fields["trail_MA_candidate_price"] == pytest.approx(101.4)


def test_compute_daily_approximate_snapshot_ticker_guard_skips_on_mismatch(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """Identity guard (spec §4.1 / Codex R1 MAJOR #1): bars warmed for
    expected_ticker but the in-fence trade row reports a different ticker ->
    skip (never combine old-ticker bars with the newly read trade row).

    EXACT pre-fix (no guard, if the param existed): a fully-populated field
    dict computed from DHC's bars (res.fields is a dict).
    EXACT post-fix: res.fields is None, res.miss_reason == 'ticker_changed'."""
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
    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        archive_df=df,
        expected_ticker="OLDTICKER",   # != the seeded "DHC"
        pipeline_run_id=1,
    )
    assert res.fields is None
    assert res.miss_reason == "ticker_changed"


def test_compute_daily_approximate_snapshot_empty_anchor_window_miss_reason(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """no_eligible_window sub-case B (Codex R3): frame has rows but NONE in
    [anchor, asof_session] (all rows predate the anchor) -> empty anchor window
    @daily_management.py:524.

    EXACT pre-fix: res is None (no reason).
    EXACT post-fix: res.fields is None, res.miss_reason == 'no_eligible_window'."""
    _seed_trade(
        conn, trade_id=1, ticker="DHC", entry_price=100.0,
        initial_stop=90.0, initial_shares=50,
        current_avg_cost=100.0, current_size=50.0,
        current_stop=92.0, pre_trade_locked_at="2026-05-01T09:30:00",
    )
    # All rows < anchor (2026-05-01) -> window_mask selects nothing:
    df = pd.DataFrame({
        "High":  [105.0, 115.0],
        "Low":   [98.0,  102.0],
        "Close": [104.0, 113.0],
    }, index=pd.to_datetime(["2026-04-25", "2026-04-28"]))
    res = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        archive_df=df,
        expected_ticker="DHC",
        pipeline_run_id=1,
    )
    assert res.fields is None
    assert res.miss_reason == "no_eligible_window"


def test_tier_upgrade_to_intraday_stubbed_for_V2(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """V1 schema reserves enum + path; service stubs V2 behavior.

    Plan §T3.1: tier 2/3 enum values are reserved without an emitter; the V2
    service entry-point ``tier_upgrade_to_intraday`` is a NotImplementedError
    stub. The schema and validator path ARE exercised at V1 via direct
    repo-level ``tier_upgrade_snapshot`` calls in T2.3 tests.
    """
    from swing.trades.daily_management import tier_upgrade_to_intraday

    with pytest.raises(NotImplementedError, match="Schwab API Phase B"):
        tier_upgrade_to_intraday(
            conn, trade_id=1, data_asof_session="2026-05-07",
            new_precision_level="intraday_estimated", snapshot_fields={},
        )


# ---------------------------------------------------------------------------
# Task 3.2: record_event_log single-transaction contract (the §A.1 critical task)
# ---------------------------------------------------------------------------


def test_record_event_log_happy_path_stop_change_and_state_transition(
    conn: sqlite3.Connection,
) -> None:
    """All 4 side-effects landed in single transaction (per plan §I happy path)."""
    from swing.trades.daily_management import record_event_log

    _seed_trade(conn, trade_id=1, state="entered", current_stop=92.0)
    req = _build_event_log_request(
        trade_id=1, stop_changed=1, prior_stop=92.0, new_stop=95.0,
        stop_change_reason="trail_to_breakout_low",
        action_taken="move_stop", action_reason="breakout_confirmed",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    rec_id = record_event_log(conn, trade_id=1, req=req)

    # Side-effect 1: event_log row inserted with linked_trade_event_id
    row = conn.execute(
        "SELECT linked_trade_event_id, new_stop FROM daily_management_records "
        "WHERE management_record_id = ?", (rec_id,),
    ).fetchone()
    assert row[0] is not None  # FK populated
    assert row[1] == 95.0
    # Side-effect 2: trade_events stop_adjust row inserted
    te_row = conn.execute(
        "SELECT id, event_type FROM trade_events WHERE id = ?", (row[0],),
    ).fetchone()
    assert te_row is not None
    assert te_row[1] == "stop_adjust"
    # Side-effect 3: trades.current_stop = 95.0
    cs = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1",
    ).fetchone()[0]
    assert cs == 95.0
    # Side-effect 4: trades.state = 'managing' (entered → managing transition)
    state = conn.execute(
        "SELECT state FROM trades WHERE id = 1",
    ).fetchone()[0]
    assert state == "managing"


def test_record_event_log_rolls_back_all_on_late_failure(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The §A.1 critical discriminating test: if event_log INSERT fails AFTER
    repo-level update_stop_with_event already wrote the stop_adjust row, the
    OUTER `with conn:` rollback wipes BOTH writes."""
    from swing.trades.daily_management import record_event_log

    _seed_trade(conn, trade_id=1, state="entered", current_stop=92.0)
    pre_stop = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1",
    ).fetchone()[0]
    pre_event_count = conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE trade_id = 1",
    ).fetchone()[0]

    # Inject a synthetic exception in the event_log INSERT step:
    def boom(*a: object, **kw: object) -> None:
        raise RuntimeError("synthetic-failure-after-stop-adjust")
    monkeypatch.setattr(
        "swing.trades.daily_management.insert_event_log", boom,
    )

    req = _build_event_log_request(
        trade_id=1, stop_changed=1, prior_stop=92.0, new_stop=95.0,
        stop_change_reason="trail",
        action_taken="move_stop", action_reason="x",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    with pytest.raises(RuntimeError, match="synthetic"):
        record_event_log(conn, trade_id=1, req=req)

    # Side-effects rolled back:
    post_stop = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1",
    ).fetchone()[0]
    post_event_count = conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE trade_id = 1",
    ).fetchone()[0]
    post_dmr_count = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records",
    ).fetchone()[0]
    assert post_stop == pre_stop  # NOT 95.0 — rolled back
    assert post_event_count == pre_event_count  # NO stop_adjust event
    assert post_dmr_count == 0  # NO event_log row


def test_record_event_log_no_stop_change(conn: sqlite3.Connection) -> None:
    from swing.trades.daily_management import record_event_log

    _seed_trade(conn, trade_id=1, state="managing", current_stop=92.0)
    req = _build_event_log_request(
        trade_id=1, stop_changed=0, action_taken="hold", action_reason=None,
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    rec_id = record_event_log(conn, trade_id=1, req=req)
    row = conn.execute(
        "SELECT linked_trade_event_id, new_stop FROM daily_management_records "
        "WHERE management_record_id = ?", (rec_id,),
    ).fetchone()
    assert row[0] is None
    assert row[1] is None
    cs = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1",
    ).fetchone()[0]
    assert cs == 92.0  # unchanged


def test_record_event_log_validation_failure_rolls_back(
    conn: sqlite3.Connection,
) -> None:
    from swing.trades.daily_management import (
        ValidationException,
        record_event_log,
    )

    _seed_trade(conn, trade_id=1, state="managing", current_stop=92.0)
    req = _build_event_log_request(
        trade_id=1, stop_changed=1,
        prior_stop=92.0, new_stop=None,  # invalid: stop_changed=1 but new_stop missing
        stop_change_reason="x",
        action_taken="move_stop", action_reason="x",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    with pytest.raises(ValidationException):
        record_event_log(conn, trade_id=1, req=req)
    count = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records",
    ).fetchone()[0]
    assert count == 0


def test_record_event_log_rejects_stale_prior_stop(
    conn: sqlite3.Connection,
) -> None:
    """Codex R4 Major #2 discriminating test: a stale form (operator-rendered
    against an earlier trades.current_stop) submits prior_stop=92 while
    trades.current_stop has already moved to 93 via a racing stop_adjust."""
    from swing.trades.daily_management import (
        ValidationException,
        record_event_log,
    )

    _seed_trade(conn, trade_id=1, state="managing", current_stop=93.0)  # already 93
    pre_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records",
    ).fetchone()[0]
    pre_te = conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE trade_id = 1",
    ).fetchone()[0]
    req = _build_event_log_request(
        trade_id=1, stop_changed=1,
        prior_stop=92.0,  # STALE — actual is 93.0
        new_stop=95.0,
        stop_change_reason="trail_to_breakout_low",
        action_taken="move_stop", action_reason="x",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    with pytest.raises(ValidationException, match="stale form"):
        record_event_log(conn, trade_id=1, req=req)
    post_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records",
    ).fetchone()[0]
    post_te = conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE trade_id = 1",
    ).fetchone()[0]
    assert post_dmr == pre_dmr
    assert post_te == pre_te
    cs = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1",
    ).fetchone()[0]
    assert cs == 93.0  # unchanged


def test_record_event_log_rejects_noop_stop_change(
    conn: sqlite3.Connection,
) -> None:
    """Codex R1 Major #4 discriminating test: stop_changed=1 with new_stop ==
    current trades.current_stop is a no-op at the repo layer (returns early,
    no INSERT)."""
    from swing.trades.daily_management import (
        ValidationException,
        record_event_log,
    )

    _seed_trade(conn, trade_id=1, state="managing", current_stop=92.0)
    pre_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records",
    ).fetchone()[0]
    req = _build_event_log_request(
        trade_id=1, stop_changed=1,
        prior_stop=92.0, new_stop=92.0,  # SAME as current — no-op
        stop_change_reason="ostensible reason",
        action_taken="move_stop", action_reason="x",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    with pytest.raises(ValidationException, match="no-op stop change"):
        record_event_log(conn, trade_id=1, req=req)
    post_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records",
    ).fetchone()[0]
    assert post_dmr == pre_dmr
    cs = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1",
    ).fetchone()[0]
    assert cs == 92.0  # unchanged


# ---------------------------------------------------------------------------
# Codex R2 Major #1: write-path active-state guard for record_event_log.
# ---------------------------------------------------------------------------
#
# UI hides the form for closed/reviewed trades (R1 M2 fix), but the WRITE
# PATH is not guarded. A direct POST or programmatic caller can pollute a
# closed-trade timeline. record_event_log MUST reject closed/reviewed
# trades regardless of stop_changed branch.


@pytest.mark.parametrize("closed_state", ["closed", "reviewed"])
def test_record_event_log_rejects_closed_trade_no_stop_change(
    conn: sqlite3.Connection, closed_state: str,
) -> None:
    """Closed/reviewed trade + stop_changed=0 must raise + insert nothing.

    Pre-fix: stop_changed=0 path skipped the repo-level active-state guard
    in update_stop_with_event, so insert_event_log polluted closed-trade
    timelines. Post-fix: service rejects at the top before branching.
    """
    from swing.trades.daily_management import ValidationException, record_event_log

    _seed_trade(conn, trade_id=1, state=closed_state, current_stop=92.0)
    pre_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records",
    ).fetchone()[0]
    req = _build_event_log_request(
        trade_id=1, stop_changed=0,
        action_taken="hold", action_reason=None,
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    with pytest.raises(ValidationException, match="not active"):
        record_event_log(conn, trade_id=1, req=req)
    post_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records",
    ).fetchone()[0]
    assert post_dmr == pre_dmr


@pytest.mark.parametrize("closed_state", ["closed", "reviewed"])
def test_record_event_log_rejects_closed_trade_with_stop_change(
    conn: sqlite3.Connection, closed_state: str,
) -> None:
    """Closed/reviewed trade + stop_changed=1 must raise + insert nothing.

    Codex R3 Minor #1 (post-R2 Major #1 fix): the service-level guard
    short-circuits BEFORE invoking the repo, so the canonical raise is
    ``ValidationException`` — the repo-level ``ValueError`` path is no
    longer reachable here. The earlier permissive
    ``raises((ValidationException, ValueError))`` would silently mask a
    regression that re-introduced the repo-level fall-through. Pin to
    ``ValidationException`` only and match on the service-level
    \"not active\" message so a missing service guard would surface
    explicitly.
    """
    from swing.trades.daily_management import ValidationException, record_event_log

    _seed_trade(conn, trade_id=1, state=closed_state, current_stop=92.0)
    pre_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records",
    ).fetchone()[0]
    pre_te = conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE trade_id = 1",
    ).fetchone()[0]
    req = _build_event_log_request(
        trade_id=1, stop_changed=1,
        prior_stop=92.0, new_stop=95.0,
        stop_change_reason="trail",
        action_taken="move_stop", action_reason="x",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    with pytest.raises(ValidationException, match="not active"):
        record_event_log(conn, trade_id=1, req=req)
    post_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records",
    ).fetchone()[0]
    post_te = conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE trade_id = 1",
    ).fetchone()[0]
    assert post_dmr == pre_dmr
    assert post_te == pre_te



# ---------------------------------------------------------------------------
# Codex R3 Major #1: record_event_log must open a single transaction with
# BEGIN IMMEDIATE so the validation read + writes are atomic against
# concurrent writers (default sqlite3 ``with conn:`` opens DEFERRED — locks
# are not acquired until the first WRITE statement, so the stale-form
# ``prior_stop`` check can pass while another writer mutates
# ``trades.current_stop`` between read and write).
# Spec §4.4: "BEGIN IMMEDIATE / COMMIT".
# ---------------------------------------------------------------------------


def test_record_event_log_issues_begin_immediate_before_validation_read(
    conn: sqlite3.Connection,
) -> None:
    """The service must issue BEGIN IMMEDIATE BEFORE its validation SELECT.

    Captures the SQL statement trace via ``set_trace_callback`` and asserts
    that a ``BEGIN IMMEDIATE`` statement appears before the first ``SELECT``
    against the trades table. Pre-fix: ``with conn:`` is the only transaction
    boundary, which is DEFERRED — locks are not acquired until the first
    write statement, so the validation read can pass while another writer
    mutates ``trades.current_stop`` between read and the repo write.
    """
    from swing.trades.daily_management import record_event_log

    _seed_trade(
        conn, trade_id=1, state="managing", current_stop=92.0,
    )

    statements: list[str] = []

    def _trace(sql: str) -> None:
        statements.append(sql)

    conn.set_trace_callback(_trace)
    try:
        req = _build_event_log_request(
            trade_id=1, stop_changed=0,
            action_taken="hold", action_reason=None,
            rule_violation_suspected=0, emotional_state='["calm"]',
            created_at="2026-05-07T18:00:00",
        )
        record_event_log(conn, trade_id=1, req=req)
    finally:
        conn.set_trace_callback(None)

    upper_stmts = [s.upper() for s in statements]
    begin_idx = next(
        (
            i for i, s in enumerate(upper_stmts)
            if s.strip().startswith("BEGIN IMMEDIATE")
        ),
        None,
    )
    select_trade_idx = next(
        (
            i for i, s in enumerate(upper_stmts)
            if "SELECT" in s and "FROM TRADES" in s
        ),
        None,
    )
    assert begin_idx is not None, (
        "record_event_log did not issue BEGIN IMMEDIATE; "
        f"statements: {statements!r}"
    )
    assert select_trade_idx is not None, (
        f"validation SELECT FROM trades not observed; statements: {statements!r}"
    )
    assert begin_idx < select_trade_idx, (
        "BEGIN IMMEDIATE must precede the validation SELECT FROM trades; "
        f"begin_idx={begin_idx}, select_trade_idx={select_trade_idx}, "
        f"statements: {statements!r}"
    )


def test_record_event_log_rejects_caller_held_transaction(
    conn: sqlite3.Connection,
) -> None:
    """Codex R4 Major #1: ``record_event_log`` MUST own its own transaction
    boundary. If the caller already holds an open transaction at entry, the
    service raises ``RuntimeError`` rather than reusing the caller's
    transaction.

    Background: an earlier ``in_transaction``-aware code path (introduced in
    R3 Major #1's "nested-call safety" guard) re-introduced the very race
    condition the BEGIN-IMMEDIATE fix was meant to close — a DEFERRED caller
    transaction would let the validation read of ``trades.current_stop``
    happen without a write lock, and a late failure inside the function
    could leak partial state out via the caller's later ``commit()``. The
    fix is to refuse the unsafe contract outright (Option A): callers MUST
    pass a fresh connection without a wrapping ``with conn:`` (or other
    open transaction).
    """
    from swing.trades.daily_management import record_event_log

    _seed_trade(
        conn, trade_id=1, state="managing", current_stop=92.0,
    )
    conn.execute("BEGIN IMMEDIATE")
    assert conn.in_transaction
    req = _build_event_log_request(
        trade_id=1, stop_changed=0,
        action_taken="hold", action_reason=None,
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    with pytest.raises(RuntimeError, match="open transaction"):
        record_event_log(conn, trade_id=1, req=req)
    # Caller is still responsible for its own transaction; clean up so the
    # fixture teardown does not see a dangling BEGIN.
    conn.rollback()
    n = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records "
        "WHERE trade_id = 1 AND record_type = 'event_log'",
    ).fetchone()[0]
    assert n == 0
