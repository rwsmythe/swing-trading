"""Phase 14 SB4 Slice 5 Task 5.4: TradeDrilldownVM + build_trade_drilldown_vm.

The VM carries the trade + chronology + thesis-at-open static decision columns
+ the base-banner fields (via _base_banner_fields) + a lazy chart_url; returns
None (-> route 404) when the trade is missing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import Config, load
from swing.data.db import connect, ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.view_models.journal import (
    TradeDrilldownVM,
    build_trade_drilldown_vm,
)


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


@pytest.fixture
def conn(cfg):
    c = connect(cfg.paths.db_path)
    yield c
    c.close()


class _Ref:
    def __init__(self, id):
        self.id = id


@pytest.fixture
def trade_mixed_sources(conn):
    with conn:
        tid = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="ABC", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="managing",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-20T09:30:00",
                thesis="breakout thesis", why_now="volume surge",
                invalidation_condition="loses 9.0"),
            event_ts="2026-04-20T09:30:00")
        insert_fill_with_event(
            conn,
            Fill(fill_id=None, trade_id=tid,
                 fill_datetime="2026-04-20T09:30:00", action="entry",
                 quantity=10.0, price=10.0),
            event_ts="2026-04-20T09:30:00")
    return _Ref(tid)


def test_drilldown_vm_assembles(conn, cfg, trade_mixed_sources):
    vm = build_trade_drilldown_vm(conn, cfg, trade_mixed_sources.id)
    assert vm is not None
    assert isinstance(vm, TradeDrilldownVM)
    assert vm.trade.id == trade_mixed_sources.id
    assert vm.chronology.entries
    assert vm.session_date  # base-banner field present
    assert vm.chart_url == f"/journal/trades/{trade_mixed_sources.id}/chart"
    # thesis-at-open static decision columns carried.
    assert vm.thesis == "breakout thesis"
    assert vm.why_now == "volume surge"
    assert vm.invalidation_condition == "loses 9.0"


def test_drilldown_vm_none_when_missing(conn, cfg):
    assert build_trade_drilldown_vm(conn, cfg, 999999) is None


def test_drilldown_vm_banner_resolve_link_guard():
    # Mirror the JournalVM banner_resolve_link __post_init__ guard.
    from swing.web.view_models.trade_chronology import TradeChronology
    trade_stub = object()
    with pytest.raises(ValueError):
        TradeDrilldownVM(
            trade=trade_stub,  # type: ignore[arg-type]
            chronology=TradeChronology(trade_id=1),
            chart_url="/journal/trades/1/chart",
            banner_resolve_link="not-a-path")
