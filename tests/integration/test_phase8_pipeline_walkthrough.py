"""Phase 8 pipeline integration walk-through (Task 4.1).

End-to-end coverage that exercises the REAL ``Lease.fenced_write()`` path
against ``_step_daily_management`` (the Task 4.0 unit suite used a stub
lease that short-circuited the fence). Every test in this module drives
``run_pipeline_internal`` to completion, then asserts on the rows written
to ``daily_management_records``.

Plan reference: ``docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md``
Task 4.1 lines 3124-3318.

Implementer notes (per Task 4.0 hand-off):

  * Real ``Lease.fenced_write()`` is exercised — no ``_StubLease`` here.
  * Per-trade lease-fenced transaction isolation is intentional: a
    single-trade failure must not roll back the batch. T4.1's failure
    isolation test asserts trade 2 emits even when trade 1 raises.
  * The OHLCV archive monkeypatch targets the SOURCE module
    (``swing.data.ohlcv_archive.read_or_fetch_archive``) per the lazy-import
    convention in ``compute_daily_approximate_snapshot``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.pipeline.runner import run_pipeline_internal


# ---------------------------------------------------------------------------
# Synthetic OHLCV — covers the asof anchors used by the tests.
# ---------------------------------------------------------------------------


def _synthetic_ohlcv() -> pd.DataFrame:
    """OHLCV with enough lookback for trail-MA windows + recent bars covering
    the asof sessions exercised by the walk-through tests."""
    closes = [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end="2026-05-08", periods=len(closes))
    return pd.DataFrame({
        "Open": closes,
        "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes],
        "Close": closes,
        "Volume": [1_000_000] * len(closes),
    }, index=idx)


def _archive_ohlcv() -> pd.DataFrame:
    """OHLCV shape consumed by ``compute_daily_approximate_snapshot`` — needs
    Date-indexed High/Low/Close columns spanning the asof session."""
    return _synthetic_ohlcv()[["High", "Low", "Close"]]


# ---------------------------------------------------------------------------
# Trade-seeding helper (mirrors tests/pipeline/test_daily_management_step.py).
# Uses raw SQL because we want explicit trade_ids 1, 2, 3 to assert against.
# ---------------------------------------------------------------------------


def _seed_trade(
    conn: sqlite3.Connection, *,
    trade_id: int, ticker: str, state: str,
    entry_price: float, initial_stop: float, initial_shares: float,
    current_avg_cost: float, current_size: float, current_stop: float,
    pre_trade_locked_at: str,
) -> None:
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


# ---------------------------------------------------------------------------
# Fixture: real config + DB + finviz CSV + 2 open trades + 1 closed trade,
# with PriceFetcher and the OHLCV archive monkeypatched. Returns the
# already-loaded ``cfg`` so tests can call ``run_pipeline_internal(cfg=cfg)``
# directly (the real ``acquire_lease`` runs end-to-end).
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_pipeline_env(tmp_path: Path, monkeypatch):
    """Build a minimal-but-real pipeline environment that exercises the REAL
    ``Lease.fenced_write()`` against ``_step_daily_management``.

    Steps that are noisy / expensive AND not under test here are patched to
    no-ops:
      * ``_step_charts``  — mpl rendering skipped.
      * ``_step_export``  — briefing emission skipped.
      * ``_step_review_log_cadence`` — review_log pre-create skipped.

    Steps that participate in the real lease + DB lifecycle run unmodified:
      * weather, ``_step_finviz_fetch`` (no real Finviz token — patched),
        ``_step_evaluate``, ``_step_watchlist``, ``_step_recommendations``,
        and the unit-under-test ``_step_daily_management``.
    """
    from tests.cli.test_cli_eval import _minimal_config

    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load_config(cfg_path)
    ensure_schema(cfg.paths.db_path).close()

    # Finviz inbox CSV (real file — _step_evaluate calls pd.read_csv on it).
    inbox = cfg.paths.finviz_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    csv = inbox / "finviz15Apr2026.csv"
    cols = ("No.,Ticker,Sector,Industry,Country,Price,Change,"
            "Average Volume,Relative Volume,Average True Range,"
            "52-Week High,52-Week Low,Market Cap")
    csv.write_text(
        cols + "\n"
        "1,AAPL,Tech,Hardware,USA,180.0,2.5%,200000,1.5,5.0,200.0,150.0,3000000000\n"
        "2,MSFT,Tech,Software,USA,420.0,1.5%,250000,1.2,4.5,440.0,330.0,3500000000\n",
        encoding="utf-8",
    )

    # Seed 2 open trades (DHC managing, ZZ entered) + 1 closed trade (VIR).
    conn = sqlite3.connect(cfg.paths.db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
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
    finally:
        conn.close()

    # PriceFetcher returns synthetic OHLCV for all tickers (covers SPY +
    # finviz tickers + held tickers that get appended to _step_evaluate's
    # fetch loop).
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: _synthetic_ohlcv(),
    )

    # The OHLCV archive read inside compute_daily_approximate_snapshot is
    # imported lazily — patch the SOURCE module so the binding is resolved
    # at call time. Per CLAUDE.md gotcha + plan §4.1 lazy-import note.
    monkeypatch.setattr(
        "swing.data.ohlcv_archive.read_or_fetch_archive",
        lambda *a, **kw: _archive_ohlcv(),
    )

    # Patch out steps that are noise here. Keep _step_finviz_fetch as a
    # no-op so the test does not need a Finviz API token.
    monkeypatch.setattr("swing.pipeline.runner._step_finviz_fetch", lambda **kw: None)
    monkeypatch.setattr("swing.pipeline.runner._step_charts", lambda **kw: {})
    monkeypatch.setattr("swing.pipeline.runner._step_export", lambda **kw: None)
    monkeypatch.setattr("swing.pipeline.runner._step_review_log_cadence", lambda **kw: None)

    return cfg


# ---------------------------------------------------------------------------
# Test 1 — open trades emit snapshots; closed trade does not.
# Exercises real Lease.fenced_write() end-to-end.
# ---------------------------------------------------------------------------


def test_phase8_pipeline_emits_snapshots_for_open_trades_only(synthetic_pipeline_env):
    """Full pipeline run with 2 open + 1 closed trade.

    EXACT post-fix expected: SELECT trade_id from daily_management_records
    WHERE record_type='daily_snapshot' returns exactly the 2 open trades' ids;
    closed trade has 0 rows.

    Real ``Lease.fenced_write()`` is exercised — the lease is acquired by
    the runner itself via the SHIPPED ``acquire_lease`` path (no stub).
    """
    cfg = synthetic_pipeline_env
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete", (
        f"pipeline did not complete cleanly: state={result.state!r}, "
        f"error={result.error_message!r}"
    )

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT trade_id FROM daily_management_records "
            "WHERE record_type='daily_snapshot' ORDER BY trade_id"
        ).fetchall()
        assert [r[0] for r in rows] == [1, 2], (
            f"expected snapshots for open trades [1, 2]; got {[r[0] for r in rows]}"
        )
        # Closed trade VIR (id=3) must have no rows of any type.
        closed_count = conn.execute(
            "SELECT COUNT(*) FROM daily_management_records WHERE trade_id = 3"
        ).fetchone()[0]
        assert closed_count == 0, (
            f"closed-trade VIR (trade_id=3) must have 0 daily_management rows; "
            f"got {closed_count}"
        )
        # Verify pipeline_run_id FK populated for every snapshot.
        nulls = conn.execute(
            "SELECT COUNT(*) FROM daily_management_records "
            "WHERE record_type='daily_snapshot' AND pipeline_run_id IS NULL"
        ).fetchone()[0]
        assert nulls == 0, (
            f"every daily_snapshot row must have a non-NULL pipeline_run_id "
            f"(FK to pipeline_runs.id); got {nulls} NULL rows"
        )
        # Each snapshot's pipeline_run_id must reference a real pipeline_runs row.
        orphan = conn.execute(
            """SELECT COUNT(*) FROM daily_management_records d
               LEFT JOIN pipeline_runs pr ON pr.id = d.pipeline_run_id
               WHERE d.record_type='daily_snapshot' AND pr.id IS NULL"""
        ).fetchone()[0]
        assert orphan == 0, (
            f"pipeline_run_id values must FK-resolve to pipeline_runs rows; "
            f"got {orphan} orphan(s)"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 2 — second same-day run UPSERTs in place; PK preserved.
# ---------------------------------------------------------------------------


def test_phase8_pipeline_second_same_day_run_upserts(synthetic_pipeline_env):
    """Second pipeline run on the same data_asof_session updates existing
    rows in place; the management_record_id PK is preserved (UPSERT discipline
    per spec §4.2 + CLAUDE.md gotcha — REPLACE forbidden).

    EXACT post-fix expected: management_record_id of trade 1's snapshot
    after second run == its id after first run.
    """
    cfg = synthetic_pipeline_env

    result1 = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result1.state == "complete", (
        f"first run failed: state={result1.state!r}, "
        f"error={result1.error_message!r}"
    )

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        rec1 = conn.execute(
            "SELECT management_record_id FROM daily_management_records "
            "WHERE trade_id = 1 AND record_type='daily_snapshot'"
        ).fetchone()
        assert rec1 is not None, "first run must emit a snapshot for trade 1"
        rec1_id = rec1[0]
    finally:
        conn.close()

    result2 = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result2.state == "complete", (
        f"second run failed: state={result2.state!r}, "
        f"error={result2.error_message!r}"
    )
    # Different pipeline_runs row id from the first run — confirms a real
    # second pipeline_runs row was inserted (lease genuinely acquired).
    assert result2.run_id != result1.run_id, (
        "second run must insert its own pipeline_runs row "
        f"(got run_id={result2.run_id}; first was {result1.run_id})"
    )

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        rec2 = conn.execute(
            "SELECT management_record_id FROM daily_management_records "
            "WHERE trade_id = 1 AND record_type='daily_snapshot'"
        ).fetchone()
        assert rec2 is not None
        rec2_id = rec2[0]
        assert rec2_id == rec1_id, (
            f"UPSERT must preserve PK (rec1_id={rec1_id}, rec2_id={rec2_id}); "
            "REPLACE-style DELETE+INSERT would issue a fresh PK and is forbidden "
            "per spec §4.2"
        )
        # Exactly one snapshot row per open trade (UPSERT, not duplicate INSERT).
        count = conn.execute(
            "SELECT COUNT(*) FROM daily_management_records "
            "WHERE record_type='daily_snapshot' AND trade_id = 1"
        ).fetchone()[0]
        assert count == 1, (
            f"second run must UPDATE in place, not INSERT a duplicate; "
            f"got {count} daily_snapshot rows for trade 1"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 3 — operator-emitted event_log AFTER pipeline run links to a real
# trade_events row (linked_trade_event_id resolves to event_type='stop_adjust').
# ---------------------------------------------------------------------------


def test_phase8_pipeline_record_event_log_after_run_links_correctly(
    synthetic_pipeline_env,
):
    """Pipeline run → operator emits a stop-change event_log → assert the
    event_log row's ``linked_trade_event_id`` resolves to a Phase 7
    ``trade_events`` row with ``event_type='stop_adjust'``.

    EXACT post-fix expected: event_log row's linked_trade_event_id is non-NULL
    AND the trade_events row at that id has event_type='stop_adjust'.
    """
    cfg = synthetic_pipeline_env
    result = run_pipeline_internal(cfg=cfg, trigger="manual")
    assert result.state == "complete", (
        f"pipeline did not complete: state={result.state!r}, "
        f"error={result.error_message!r}"
    )

    # Build a stop-change event_log request. Trade 1 (DHC) currently has
    # current_stop=92.0 (per the seeded fixture); the event_log moves the
    # stop to 95.0 with reason 'trail_to_breakout_low'.
    from swing.trades.daily_management import EventLogRequest, record_event_log

    req = EventLogRequest(
        trade_id=1,
        review_date="2026-05-07",
        data_asof_session="2026-05-07",
        created_at="2026-05-07T19:00:00",
        mfe_mae_precision_level="daily_approximate",
        stop_changed=1,
        prior_stop=92.0,
        new_stop=95.0,
        stop_change_reason="trail_to_breakout_low",
        action_taken="move_stop",
        action_reason="breakout_confirmed",
        rule_violation_suspected=0,
        emotional_state='["calm"]',
    )

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        event_log_id = record_event_log(conn, trade_id=1, req=req)
        row = conn.execute(
            "SELECT linked_trade_event_id, record_type "
            "FROM daily_management_records "
            "WHERE management_record_id = ?",
            (event_log_id,),
        ).fetchone()
        assert row is not None, (
            f"record_event_log returned id {event_log_id} but no row at that id"
        )
        linked_id, record_type = row
        assert record_type == "event_log", (
            f"record_event_log must persist record_type='event_log'; "
            f"got {record_type!r}"
        )
        assert linked_id is not None, (
            "stop_changed=1 must populate linked_trade_event_id with the "
            "freshly-inserted Phase 7 trade_events row id"
        )
        te_type = conn.execute(
            "SELECT event_type FROM trade_events WHERE id = ?",
            (linked_id,),
        ).fetchone()
        assert te_type is not None, (
            f"linked_trade_event_id={linked_id} must FK-resolve to a "
            "trade_events row"
        )
        assert te_type[0] == "stop_adjust", (
            f"linked trade_event must be a stop_adjust; got {te_type[0]!r}"
        )
    finally:
        conn.close()
