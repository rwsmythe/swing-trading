"""Phase 14 SB4 Slice 2 Task 2.1 — per-trade JournalRowVM rows.

Discriminating coverage:
  - closed single-leg: closing_price == single exit price (VWAP of one fill).
  - closed multi-leg: closing_price == share-weighted VWAP (60@11 + 40@13 ->
    11.80), NOT the naive mean (12.00).
  - open trade: closing_price is None and final_r is None.
  - has_hyprec_link derives from trade_origin == 'pipeline_watch_hyp_recs',
    NOT from candidate_id (an A+ candidate-backed trade is candidate-backed
    but NOT a hyp-rec -> has_hyprec_link is False).
  - entry flags (aplus_bucket / chart_pattern) are None-safe for a trade with
    no candidate / pattern.
"""
from __future__ import annotations

import pytest

from swing.data.db import connect
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event


def _insert_trade(conn, **overrides) -> int:
    base = dict(
        id=None, ticker="TST", entry_date="2026-04-15",
        entry_price=10.0, initial_shares=100, initial_stop=9.0,
        current_stop=9.0, state="closed", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )
    base.update(overrides)
    return insert_trade_with_event(
        conn, Trade(**base), event_ts="2026-04-15T09:30:00",
    )


def _insert_exit(conn, tid, *, price, quantity, when="2026-04-20T15:30:00"):
    insert_fill_with_event(
        conn,
        Fill(
            fill_id=None, trade_id=tid, fill_datetime=when,
            action="exit", quantity=quantity, price=price, reason="target",
        ),
        event_ts=when,
    )


def _insert_candidate(conn, *, ticker, bucket) -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count)
           VALUES ('2026-04-29T09:00:00','2026-04-28','2026-04-29',
                   NULL, 1, 0, 1, 0, 0, 0)"""
    )
    run_id = cur.lastrowid
    cur = conn.execute(
        """INSERT INTO candidates
           (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
            adr_pct, rs_method)
           VALUES (?, ?, ?, 10.0, 10.5, 9.5, 2.0, 'fallback_spy')""",
        (run_id, ticker, bucket),
    )
    return cur.lastrowid


@pytest.fixture
def single_leg_closed(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = _insert_trade(
                conn, ticker="ONE", entry_price=10.0, initial_shares=100,
                initial_stop=9.0,
            )
            _insert_exit(conn, tid, price=12.0, quantity=100)
    finally:
        conn.close()
    return Trade(
        id=tid, ticker="ONE", entry_date="2026-04-15", entry_price=10.0,
        initial_shares=100, initial_stop=9.0, current_stop=9.0,
        state="closed", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )


@pytest.fixture
def multi_leg_closed(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = _insert_trade(
                conn, ticker="MUL", entry_price=10.0, initial_shares=100,
                initial_stop=9.0,
            )
            _insert_exit(conn, tid, price=11.0, quantity=60,
                         when="2026-04-20T15:30:00")
            _insert_exit(conn, tid, price=13.0, quantity=40,
                         when="2026-04-21T15:30:00")
    finally:
        conn.close()
    return Trade(
        id=tid, ticker="MUL", entry_date="2026-04-15", entry_price=10.0,
        initial_shares=100, initial_stop=9.0, current_stop=9.0,
        state="closed", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )


@pytest.fixture
def open_trade(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = _insert_trade(
                conn, ticker="OPN", entry_price=10.0, initial_shares=50,
                initial_stop=9.0, state="managing",
            )
    finally:
        conn.close()
    return Trade(
        id=tid, ticker="OPN", entry_date="2026-04-15", entry_price=10.0,
        initial_shares=50, initial_stop=9.0, current_stop=9.0,
        state="managing", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )


@pytest.fixture
def aplus_trade_with_candidate(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cid = _insert_candidate(conn, ticker="APL", bucket="aplus")
            tid = _insert_trade(
                conn, ticker="APL", entry_price=10.0, initial_shares=100,
                initial_stop=9.0, state="managing",
                trade_origin="pipeline_aplus", candidate_id=cid,
            )
    finally:
        conn.close()
    return Trade(
        id=tid, ticker="APL", entry_date="2026-04-15", entry_price=10.0,
        initial_shares=100, initial_stop=9.0, current_stop=9.0,
        state="managing", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        trade_origin="pipeline_aplus", candidate_id=cid,
    )


@pytest.fixture
def hyprec_trade(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cid = _insert_candidate(conn, ticker="HYP", bucket="watch")
            tid = _insert_trade(
                conn, ticker="HYP", entry_price=10.0, initial_shares=100,
                initial_stop=9.0, state="managing",
                trade_origin="pipeline_watch_hyp_recs", candidate_id=cid,
            )
    finally:
        conn.close()
    return Trade(
        id=tid, ticker="HYP", entry_date="2026-04-15", entry_price=10.0,
        initial_shares=100, initial_stop=9.0, current_stop=9.0,
        state="managing", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        trade_origin="pipeline_watch_hyp_recs", candidate_id=cid,
    )


@pytest.fixture
def trade_no_candidate(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = _insert_trade(
                conn, ticker="NOC", entry_price=10.0, initial_shares=100,
                initial_stop=9.0, state="managing",
                trade_origin="manual_off_pipeline",
            )
    finally:
        conn.close()
    return Trade(
        id=tid, ticker="NOC", entry_date="2026-04-15", entry_price=10.0,
        initial_shares=100, initial_stop=9.0, current_stop=9.0,
        state="managing", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline",
    )


@pytest.fixture
def build_journal_for(seeded_db):
    from swing.web.view_models.journal import build_journal
    cfg, _ = seeded_db

    def _build(**kwargs):
        return build_journal(cfg=cfg, **kwargs)

    return _build


def test_journal_row_fields_closed_single_leg(build_journal_for, single_leg_closed):
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == single_leg_closed.id)
    assert row.open_price == 10.00
    assert row.shares == 100
    assert row.total_risk_dollars == 100.00
    assert row.closing_price == 12.00     # single-leg VWAP
    assert row.final_r is not None
    # (12-10)*100 / ((10-9)*100) = 2.0
    assert round(row.final_r, 4) == 2.0


def test_journal_row_multi_leg_vwap(build_journal_for, multi_leg_closed):
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == multi_leg_closed.id)
    # (60*11 + 40*13)/100 = 11.80, NOT (11+13)/2 = 12.00.
    assert row.closing_price == 11.80


def test_journal_row_open_trade_has_none_exit(build_journal_for, open_trade):
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == open_trade.id)
    assert row.closing_price is None and row.final_r is None


def test_has_hyprec_link_from_origin_not_candidate(
    build_journal_for, aplus_trade_with_candidate, hyprec_trade,
):
    vm = build_journal_for(period="all")
    aplus = next(r for r in vm.rows if r.trade_id == aplus_trade_with_candidate.id)
    hyp = next(r for r in vm.rows if r.trade_id == hyprec_trade.id)
    assert aplus.has_hyprec_link is False   # A+ is candidate-backed but NOT hyp-rec
    assert hyp.has_hyprec_link is True      # trade_origin == pipeline_watch_hyp_recs
    # A+ candidate-backed trade still surfaces its bucket.
    assert aplus.aplus_bucket == "aplus"


def test_entry_flags_none_safe(build_journal_for, trade_no_candidate):
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == trade_no_candidate.id)
    assert row.aplus_bucket is None and row.chart_pattern is None
