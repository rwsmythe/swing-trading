"""Phase 14 SB4 Slice 0 Task 0.4: ReviewVM exit-data fields + derivations.

Arithmetic discipline (feedback_verify_regression_test_arithmetic):
  Single-leg: 100 sh entry @10.00 stop 9.00; exit 100 @12.00
    total_risk = 100*(10-9) = 100.00 ; exit_vwap = 12.00
  Multi-leg: same entry; exits 60 @11.00 + 40 @13.00
    exit_vwap = (60*11 + 40*13)/100 = 1180/100 = 11.80 (NOT naive mean 12.00)
    total_risk = 100.00

build_review_vm is CLOSED-ONLY (returns None unless trade.state == 'closed'),
so the empty-exit case is tested on the _exit_vwap helper directly.
"""
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.view_models.trades import build_review_vm


def _seed_closed(db_path, *, ticker, entry_price, initial_stop, initial_shares,
                 exit_legs):
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        tid = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker=ticker, entry_date="2026-04-20",
                entry_price=entry_price, initial_shares=initial_shares,
                initial_stop=initial_stop, current_stop=initial_stop,
                state="entered", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-20T09:30:00"),
            event_ts="2026-04-20T09:30:00")
        insert_fill_with_event(
            conn,
            Fill(fill_id=None, trade_id=tid, fill_datetime="2026-04-20T09:30:00",
                 action="entry", quantity=float(initial_shares),
                 price=entry_price),
            event_ts="2026-04-20T09:30:00")
        for qty, px, ts in exit_legs:
            insert_fill_with_event(
                conn,
                Fill(fill_id=None, trade_id=tid, fill_datetime=ts,
                     action="exit", quantity=float(qty), price=px,
                     reason="manual"),
                event_ts=ts)
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (tid,))
    conn.close()
    return tid


def _cfg_for(db_path):
    base = load(Path("swing.config.toml"))
    return dc_replace(base, paths=dc_replace(base.paths, db_path=db_path))


@pytest.fixture
def build_review_vm_for():
    def _build(spec):
        cfg = _cfg_for(spec["db_path"])
        return build_review_vm(trade_id=spec["tid"], cfg=cfg)
    return _build


@pytest.fixture
def single_leg_closed(tmp_path):
    db = tmp_path / "single.db"
    tid = _seed_closed(
        db, ticker="ABC", entry_price=10.0, initial_stop=9.0,
        initial_shares=100,
        exit_legs=[(100, 12.00, "2026-04-25T15:00:00")])
    return {"db_path": db, "tid": tid}


@pytest.fixture
def multi_leg_closed(tmp_path):
    db = tmp_path / "multi.db"
    tid = _seed_closed(
        db, ticker="ABC", entry_price=10.0, initial_stop=9.0,
        initial_shares=100,
        exit_legs=[(60, 11.00, "2026-04-25T15:00:00"),
                   (40, 13.00, "2026-04-26T15:00:00")])
    return {"db_path": db, "tid": tid}


@pytest.fixture
def stop_above_entry(tmp_path):
    db = tmp_path / "inverted.db"
    tid = _seed_closed(
        db, ticker="ABC", entry_price=10.0, initial_stop=11.0,
        initial_shares=100,
        exit_legs=[(100, 12.00, "2026-04-25T15:00:00")])
    return {"db_path": db, "tid": tid}


def test_exit_vwap_single_leg(build_review_vm_for, single_leg_closed):
    vm = build_review_vm_for(single_leg_closed)
    assert vm.exit_price_vwap == 12.00
    assert vm.total_risk_dollars == 100.00
    assert vm.exit_date_last == "2026-04-25"
    assert len(vm.exit_legs) == 1


def test_exit_vwap_multi_leg(build_review_vm_for, multi_leg_closed):
    vm = build_review_vm_for(multi_leg_closed)
    assert vm.exit_price_vwap == 11.80   # share-weighted, NOT naive mean 12.00
    assert vm.total_risk_dollars == 100.00
    assert len(vm.exit_legs) == 2
    assert (vm.exit_legs[0].quantity, vm.exit_legs[1].quantity) == (60, 40)
    # exit_legs sorted ASC by fill_datetime:
    assert vm.exit_legs[0].fill_date == "2026-04-25"
    assert vm.exit_legs[1].fill_date == "2026-04-26"
    assert vm.exit_date_last == "2026-04-26"


def test_total_risk_none_when_stop_inverted(build_review_vm_for, stop_above_entry):
    assert build_review_vm_for(stop_above_entry).total_risk_dollars is None


def test_exit_vwap_helper_none_on_empty():
    from swing.web.view_models.trades import _exit_vwap
    assert _exit_vwap([]) is None  # defensive: no reducing fill -> None


def test_total_risk_helper_single_and_multi():
    from swing.web.view_models.trades import _total_risk_dollars
    t = Trade(id=1, ticker="ABC", entry_date="2026-04-20", entry_price=10.0,
              initial_shares=100, initial_stop=9.0, current_stop=9.0,
              state="closed", watchlist_entry_target=None,
              watchlist_initial_stop=None, notes=None)
    assert _total_risk_dollars(t) == 100.00  # 100*(10-9)
    inverted = dc_replace(t, initial_stop=11.0)
    assert _total_risk_dollars(inverted) is None
