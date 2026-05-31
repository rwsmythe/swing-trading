"""Phase 14 SB4 Slice 0 Task 0.6: review page exit block + lazy chart cell.

The review page carries a lazy chart cell with the HTMX trinity attributes
(hx-get to the chart route, hx-trigger=load, hx-headers HX-Request) and an
exit-data block. build_review_vm sets review_chart_url.
"""
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.web.app import create_app


@pytest.fixture
def app_with_closed_trade(tmp_path: Path):
    db_path = tmp_path / "review_cell.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        tid = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="VIR", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-20T09:30:00"),
            event_ts="2026-04-20T09:30:00")
        insert_fill_with_event(
            conn,
            Fill(fill_id=None, trade_id=tid,
                 fill_datetime="2026-04-20T09:30:00", action="entry",
                 quantity=10.0, price=10.0),
            event_ts="2026-04-20T09:30:00")
        insert_fill_with_event(
            conn,
            Fill(fill_id=None, trade_id=tid,
                 fill_datetime="2026-04-25T15:00:00", action="exit",
                 quantity=10.0, price=11.5, reason="manual"),
            event_ts="2026-04-25T15:00:00")
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (tid,))
    conn.close()
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    app = create_app(cfg)
    app.state._tid = tid
    return app


def test_review_page_has_lazy_chart_cell(app_with_closed_trade):
    tid = app_with_closed_trade.state._tid
    with TestClient(app_with_closed_trade) as client:
        r = client.get(f"/trades/{tid}/review")
    assert r.status_code == 200
    assert f'hx-get="/trades/{tid}/review/chart"' in r.text
    assert 'hx-trigger="load"' in r.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text


def test_review_page_renders_exit_block(app_with_closed_trade):
    tid = app_with_closed_trade.state._tid
    with TestClient(app_with_closed_trade) as client:
        r = client.get(f"/trades/{tid}/review")
    assert r.status_code == 200
    # Exit VWAP for a single 10@11.5 exit = 11.50; last exit date shown.
    assert "11.50" in r.text
    assert "2026-04-25" in r.text
    # Total risk at open = 10*(10-9) = $10.00
    assert "10.00" in r.text


def test_build_review_vm_sets_chart_url(app_with_closed_trade):
    from swing.config_overrides import apply_overrides
    from swing.web.view_models.trades import build_review_vm
    tid = app_with_closed_trade.state._tid
    cfg = apply_overrides(app_with_closed_trade.state.cfg)
    vm = build_review_vm(trade_id=tid, cfg=cfg)
    assert vm.review_chart_url == f"/trades/{tid}/review/chart"
