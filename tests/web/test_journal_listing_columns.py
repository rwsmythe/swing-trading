"""Phase 14 SB4 gate-fix FIX-1 — Exit-date + Days-open journal columns.

Discriminating coverage:
  - JournalRowVM carries `exit_date` + `days_open`.
  - closed single-leg: exit_date == the (only) exit fill date; days_open ==
    exit_date - entry_date.
  - closed multi-leg: exit_date == the LAST exit (max), NOT the first; days_open
    measured to that last exit (feedback_verify_regression_test_arithmetic:
    arithmetic computed under both legs to confirm the test distinguishes).
  - open trade: exit_date is None; days_open == today - entry_date.
  - render: an "Exit" column header is emitted BEFORE the "Closing price"
    header, and a "Days open" header is present; both are sortable controls.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


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


def _insert_exit(conn, tid, *, price, quantity, when):
    insert_fill_with_event(
        conn,
        Fill(
            fill_id=None, trade_id=tid, fill_datetime=when,
            action="exit", quantity=quantity, price=price, reason="target",
        ),
        event_ts=when,
    )


@pytest.fixture
def build_journal_for(seeded_db):
    from swing.web.view_models.journal import build_journal
    cfg, _ = seeded_db

    def _build(**kwargs):
        return build_journal(cfg=cfg, **kwargs)

    return _build


@pytest.fixture
def single_leg_closed(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = _insert_trade(conn, ticker="ONE", entry_date="2026-04-15")
            _insert_exit(conn, tid, price=12.0, quantity=100,
                         when="2026-04-20T15:30:00")
    finally:
        conn.close()
    return tid


@pytest.fixture
def multi_leg_closed(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = _insert_trade(conn, ticker="MUL", entry_date="2026-04-15")
            _insert_exit(conn, tid, price=11.0, quantity=60,
                         when="2026-04-20T15:30:00")
            _insert_exit(conn, tid, price=13.0, quantity=40,
                         when="2026-04-21T15:30:00")
    finally:
        conn.close()
    return tid


@pytest.fixture
def open_managing(seeded_db):
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = _insert_trade(conn, ticker="OPN", entry_date="2026-04-15",
                                state="managing", initial_shares=50)
    finally:
        conn.close()
    return tid


def test_row_exit_date_single_leg(build_journal_for, single_leg_closed):
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == single_leg_closed)
    assert row.exit_date == "2026-04-20"
    # entry 2026-04-15 -> exit 2026-04-20 == 5 days.
    assert row.days_open == 5


def test_row_exit_date_multi_leg_is_last(build_journal_for, multi_leg_closed):
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == multi_leg_closed)
    # LAST exit (2026-04-21), NOT the first (2026-04-20).
    assert row.exit_date == "2026-04-21"
    # entry 2026-04-15 -> last exit 2026-04-21 == 6 days (NOT 5 to first leg).
    assert row.days_open == 6


def test_row_open_trade_days_open_uses_today(build_journal_for, open_managing):
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == open_managing)
    assert row.exit_date is None
    expected = (date.today() - date(2026, 4, 15)).days
    assert row.days_open == expected


@pytest.fixture
def closed_without_exit(seeded_db):
    # Legacy/operator data the code tolerates: a terminal-state trade with NO
    # exit fills. exit_date is unknown -> days_open must be None (NOT counted
    # to today, which would be a closed trade silently aging forever).
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = _insert_trade(conn, ticker="ORP", entry_date="2026-04-15",
                                state="closed")
    finally:
        conn.close()
    return tid


def test_closed_without_exit_has_no_days_open(build_journal_for, closed_without_exit):
    # Codex R1 MAJOR: a closed/reviewed trade with no exit fill must NOT show a
    # today-anchored days_open (only open states age to today).
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == closed_without_exit)
    assert row.exit_date is None
    assert row.days_open is None


def test_listing_exit_before_closing_price_header(seeded_db, single_leg_closed):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=all")
    assert r.status_code == 200
    assert "Exit" in r.text and "Days open" in r.text
    # "Exit" header must precede "Closing price".
    assert r.text.index(">Exit") < r.text.index("Closing price")


def test_exit_and_days_open_are_sortable(seeded_db, single_leg_closed):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=all")
    assert "sort=exit_date" in r.text
    assert "sort=days_open" in r.text
