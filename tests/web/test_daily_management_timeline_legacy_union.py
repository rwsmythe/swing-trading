"""Phase 8 V1 polish Item #1: Phase 7 stop-adjust trade_events that have NO
corresponding Phase 8 event_log row (orphans) surface in the per-trade
timeline labelled "Stop adjustment (legacy quick-adjust)".

Plan: docs/superpowers/plans/2026-05-07-phase8-v1-polish.md.

The union happens at the VM layer (build_daily_management_timeline_vm);
repo functions stay atomic.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.web.app import create_app
from swing.web.price_cache import PriceCache
from swing.web.view_models.trades import build_daily_management_timeline_vm


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str = "DHC",
    state: str = "managing",
    current_stop: float = 92.0,
) -> None:
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, "
        " current_size, current_avg_cost) "
        "VALUES (?, ?, '2026-05-01', 100.0, 50, 90.0, ?, ?, "
        " 'manual_off_pipeline', '2026-05-01T09:30:00', 50.0, 100.0)",
        (trade_id, ticker, current_stop, state),
    )
    conn.commit()


@pytest.fixture
def cfg_with_db(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *args, **kwargs: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    db_path = tmp_path / "phase8_polish_timeline.db"
    ensure_schema(db_path).close()
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )
    return cfg, db_path


def _insert_orphan_stop_adjust(
    conn: sqlite3.Connection, *, trade_id: int, ts: str,
    old_stop: float, new_stop: float,
    rationale: str = "trail-up",
    notes: str | None = "manual",
) -> int:
    """Mirrors Phase 7 update_stop_with_event INSERT shape exactly so the
    orphan row is byte-identical to a row written by the legacy code path,
    minus the trades.current_stop UPDATE side-effect (which is irrelevant
    for read-side timeline rendering)."""
    payload = {"old_stop": old_stop, "new_stop": new_stop}
    cur = conn.execute(
        "INSERT INTO trade_events "
        "(trade_id, ts, event_type, payload_json, rationale, notes) "
        "VALUES (?, ?, 'stop_adjust', ?, ?, ?)",
        (trade_id, ts, json.dumps(payload, sort_keys=True), rationale, notes),
    )
    conn.commit()
    return cur.lastrowid


def test_orphan_stop_adjust_surfaces_in_timeline_post_fix(cfg_with_db):
    """Discriminating test (Item #1):

    Pre-fix expectation: with one orphan trade_events row of event_type=
    'stop_adjust' and zero daily_management_records, the timeline VM has
    `len(rows) == 0` (the existing build function only consults
    daily_management_records).
    Post-fix expectation: `len(rows) == 1` with `rows[0].record_type ==
    'trade_event_legacy'` carrying the decoded prior_stop/new_stop.
    """
    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        event_id = _insert_orphan_stop_adjust(
            conn, trade_id=1,
            ts="2026-05-05T10:30:00",
            old_stop=90.0, new_stop=95.0,
            rationale="trail-up",
            notes="trail to entry+5",
        )
    finally:
        conn.close()

    vm = build_daily_management_timeline_vm(trade_id=1, cfg=cfg)
    assert vm is not None
    assert len(vm.rows) == 1
    row = vm.rows[0]
    assert row.record_type == "trade_event_legacy"
    assert row.trade_event_id == event_id
    assert row.event_type == "stop_adjust"
    assert row.legacy_prior_stop == 90.0
    assert row.legacy_new_stop == 95.0
    assert row.legacy_rationale == "trail-up"
    assert row.legacy_notes == "trail to entry+5"
    # Sort key mapping per §A.2:
    assert row.review_date == "2026-05-05"
    assert row.created_at == "2026-05-05T10:30:00"
    assert row.management_record_id == -event_id
