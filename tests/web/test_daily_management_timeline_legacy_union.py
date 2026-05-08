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


def test_orphan_stop_adjust_renders_label_in_trade_detail_page(cfg_with_db):
    """Discriminating test for the template branch:

    Pre-fix expectation (no template branch): the literal string "stop adjustment
    (legacy quick-adjust)" is absent from the trade-detail HTML even when an
    orphan trade_event exists.
    Post-fix expectation: the label appears in the timeline section AND the
    decoded prior_stop -> new_stop dollar amounts render."""
    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        _insert_orphan_stop_adjust(
            conn, trade_id=1,
            ts="2026-05-05T10:30:00",
            old_stop=90.0, new_stop=95.0,
            rationale="trail-up to entry+5",
            notes=None,
        )
    finally:
        conn.close()

    app = create_app(cfg)
    with TestClient(app) as client:
        response = client.get("/trades/1")
    assert response.status_code == 200
    body = response.text
    assert 'id="daily-management-timeline"' in body
    timeline_html = (
        body.split('id="daily-management-timeline"')[1].split("</section>")[0]
    )
    assert "Stop adjustment (legacy quick-adjust)" in timeline_html
    assert "$90.00" in timeline_html
    assert "$95.00" in timeline_html
    assert "trail-up to entry+5" in timeline_html


def test_dedup_linked_stop_adjust_does_not_double_appear(cfg_with_db):
    """Discriminating test for the dedup rule:

    Setup: insert a Phase 7 stop_adjust trade_event (id=E) AND a Phase 8
    event_log row whose `linked_trade_event_id = E`.

    Pre-fix expectation (no dedup): the trade_event surfaces as a
    'trade_event_legacy' row AND the event_log row also renders -> operator
    sees TWO rows describing the same stop change.
    Post-fix expectation: only the event_log row surfaces (canonical Phase 8
    audit row); the trade_event is suppressed by the linked_event_ids set."""
    from swing.data.repos.daily_management import insert_event_log

    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        event_id = _insert_orphan_stop_adjust(
            conn, trade_id=1,
            ts="2026-05-05T10:30:00",
            old_stop=90.0, new_stop=95.0,
            rationale="trail-up",
        )
        # The matching Phase 8 event_log row referencing this trade_event:
        insert_event_log(
            conn, trade_id=1,
            event_log_fields={
                "review_date": "2026-05-05",
                "data_asof_session": "2026-05-05",
                "created_at": "2026-05-05T10:30:00",
                "mfe_mae_precision_level": "daily_approximate",
                "stop_changed": 1,
                "prior_stop": 90.0,
                "new_stop": 95.0,
                "linked_trade_event_id": event_id,
                "stop_change_reason": "trail-up",
                "action_taken": "move_stop",
                "rule_violation_suspected": 0,
                "emotional_state": "[]",
            },
        )
    finally:
        # `insert_event_log` docstring (`swing/data/repos/daily_management.py`)
        # explicitly defers transaction control to the caller. Commit BEFORE
        # close — sqlite3 rolls back uncommitted work on connection close, so
        # without this the dedup setup row vanishes and the test no longer
        # discriminates the dedup logic.
        conn.commit()
        conn.close()

    vm = build_daily_management_timeline_vm(trade_id=1, cfg=cfg)
    assert vm is not None
    legacy_rows = [r for r in vm.rows if r.record_type == "trade_event_legacy"]
    event_log_rows = [r for r in vm.rows if r.record_type == "event_log"]
    assert legacy_rows == [], (
        f"linked stop_adjust should be deduped; got {len(legacy_rows)} legacy rows"
    )
    assert len(event_log_rows) == 1
    assert event_log_rows[0].new_stop == 95.0
    assert event_log_rows[0].prior_stop == 90.0


def test_non_stop_adjust_trade_events_do_not_appear_in_timeline(cfg_with_db):
    """Discriminating test for the event_type filter (per locked design §0.3 #4):

    Insert orphan trade_events of representative non-stop_adjust event_types
    that exist in the production CHECK constraint enum: 'entry', 'exit',
    'note', 'flag'. Lifecycle events (entry/exit) have their own UI surfaces
    (dashboard row, exit form) and MUST NOT also surface in the timeline.

    Pre-fix expectation (had we shipped a too-wide filter `event_type IN
    ('stop_adjust','entry','exit','note','flag')`): all four orphans appear.
    Post-fix expectation: ONLY stop_adjust orphans surface; entry/exit/note/
    flag rows are absent from the timeline."""
    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        for ts, event_type, payload in [
            ("2026-05-05T11:00:00", "entry",          '{"shares":50,"price":100.0}'),
            ("2026-05-05T11:30:00", "exit",           '{"shares":50,"price":105.0}'),
            ("2026-05-05T12:00:00", "note",           '{"note":"NOTE_MARKER"}'),
            ("2026-05-05T12:30:00", "flag",           '{"flag":"FLAG_MARKER"}'),
            ("2026-05-05T13:00:00", "pre_trade_edit", '{"field":"thesis"}'),
        ]:
            conn.execute(
                "INSERT INTO trade_events "
                "(trade_id, ts, event_type, payload_json, rationale, notes) "
                "VALUES (1, ?, ?, ?, NULL, NULL)",
                (ts, event_type, payload),
            )
        conn.commit()
    finally:
        conn.close()

    vm = build_daily_management_timeline_vm(trade_id=1, cfg=cfg)
    assert vm is not None
    assert vm.rows == (), (
        "Non-stop_adjust trade_events must NOT surface in the timeline; "
        f"got {len(vm.rows)} unexpected rows: "
        f"{[r.record_type for r in vm.rows]}"
    )


def test_timeline_orders_legacy_orphan_chronologically_with_dmr_rows(cfg_with_db):
    """Discriminating test for the merged sort order:

    Insert (in scrambled insertion order):
      - daily_snapshot for 2026-05-04 (created_at 2026-05-04T16:00:00)
      - orphan stop_adjust for 2026-05-05 (ts 2026-05-05T10:30:00)
      - event_log for 2026-05-06 (created_at 2026-05-06T09:00:00)

    Pre-fix expectation (had we appended orphans without sorting): they'd
    appear at the end of the rows list regardless of date.
    Post-fix expectation: rows ordered chronologically ascending - snapshot
    (4th), orphan (5th), event_log (6th)."""
    from swing.data.repos.daily_management import insert_event_log, insert_snapshot

    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        # Snapshot first chronologically:
        insert_snapshot(
            conn, trade_id=1,
            snapshot_fields={
                "review_date": "2026-05-04",
                "data_asof_session": "2026-05-04",
                "created_at": "2026-05-04T16:00:00",
                "mfe_mae_precision_level": "daily_approximate",
                "pipeline_run_id": None,
                "current_price": 110.0, "current_stop": 95.0,
                "current_size": 50.0, "current_avg_cost": 100.0,
                "open_R_effective": 1.0,
                "open_MFE_R_to_date": 1.5, "open_MAE_R_to_date": 0.2,
                "intraday_high": 111.0, "intraday_low": 109.0,
                "position_capital_utilization_pct": 0.15,
                "position_capital_denominator_dollars": 7500.0,
                "position_portfolio_heat_contribution_dollars": 50.0,
                "maturity_stage": "+1.5R_to_+2R",
                "trail_MA_candidate_price": 105.0,
                "trail_MA_period_days": 21,
                "trail_MA_eligibility_flag": 0,
            },
        )
        # Orphan in the middle:
        _insert_orphan_stop_adjust(
            conn, trade_id=1,
            ts="2026-05-05T10:30:00",
            old_stop=90.0, new_stop=95.0,
        )
        # Event_log last chronologically:
        insert_event_log(
            conn, trade_id=1,
            event_log_fields={
                "review_date": "2026-05-06",
                "data_asof_session": "2026-05-06",
                "created_at": "2026-05-06T09:00:00",
                "mfe_mae_precision_level": "daily_approximate",
                "stop_changed": 0,
                "action_taken": "hold",
                "rule_violation_suspected": 0,
                "emotional_state": "[]",
            },
        )
    finally:
        # See B.6 fix: insert_snapshot/insert_event_log defer commit to caller.
        conn.commit()
        conn.close()

    vm = build_daily_management_timeline_vm(trade_id=1, cfg=cfg)
    assert vm is not None
    assert len(vm.rows) == 3
    types_in_order = [r.record_type for r in vm.rows]
    assert types_in_order == [
        "daily_snapshot", "trade_event_legacy", "event_log",
    ], f"got order: {types_in_order}"
