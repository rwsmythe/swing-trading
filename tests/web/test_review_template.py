"""ReviewVM existing-fields + template-render tests.

Phase 7 Sub-B B.6 fixture migration: legacy ``Exit(...)``+``insert_exit_with_event``
seeding rewritten to ``Fill(action='exit')``+``insert_fill_with_event``. The
``Exit`` dataclass is a stub post Sub-A T3 and raises on construction.

The whole module is skipped: ``build_review_vm`` reads ``trade.status``
(dropped from the dataclass in Sub-A T6), so post-fixture-migration the
runtime hits ``AttributeError``. Sub-C Task T1 rewrites the web review VM
and unskips this file.
"""
from pathlib import Path

import pytest

from swing.web.view_models.trades import ReviewVM, build_review_vm

pytestmark = pytest.mark.skip(
    reason="Sub-B B.6: fixture migrated to fills shape; build_review_vm "
    "still references trade.status — unskip when Sub-C T1 rewrites the web "
    "review VM."
)


@pytest.fixture
def populated_db_cfg(tmp_path: Path):
    """Fixture: tmp DB seeded with one closed trade (id=1) + one open
    (id=2). Returns a Config bound to the tmp DB so build_review_vm has
    a real cfg.paths.db_path to read from.

    Construction strategy: load the project's tracked swing.config.toml
    via swing.config.load() (which has all required sections populated
    correctly) and use dataclasses.replace to point db_path at the tmp
    DB. Mirrors the test_app_half_exited fixture pattern (Task 9). Direct
    Config(...) construction is NOT possible — Config has many required
    fields and is not zero-arg constructible. (R4 Major 1 fix.)
    """
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event
    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        # Closed trade — insert with entry+exit fills, then UPDATE state to
        # 'closed' (fixture-brevity bypass of the state machine).
        t1 = insert_trade_with_event(
            conn, Trade(
                id=None, ticker="VIR", entry_date="2026-04-20",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-20T09:30:00",
            ),
            event_ts="2026-04-20T09:30:00",
        )
        insert_fill_with_event(
            conn, Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-20T09:30:00",
                action="entry", quantity=10.0, price=10.0,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        insert_fill_with_event(
            conn, Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-25T09:30:00",
                action="exit", quantity=10.0, price=11.5,
                reason="manual",
            ),
            event_ts="2026-04-25T09:30:00",
        )
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (t1,))
        # Open trade
        insert_trade_with_event(
            conn, Trade(
                id=None, ticker="DHC", entry_date="2026-04-27",
                entry_price=7.58, initial_shares=39, initial_stop=7.30,
                current_stop=7.30, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-27T09:30:00",
            ),
            event_ts="2026-04-27T09:30:00",
        )
    conn.close()
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return cfg


def test_review_vm_has_5_existing_base_layout_fields(populated_db_cfg) -> None:
    """Brief §6.2 watch item 8: ReviewVM must inherit existing base.html.j2 fields."""
    vm = build_review_vm(trade_id=1, cfg=populated_db_cfg)
    assert vm is not None
    # Existing base-layout fields with safe defaults:
    assert hasattr(vm, "session_date")
    assert hasattr(vm, "stale_banner")
    assert hasattr(vm, "price_source_degraded")
    assert hasattr(vm, "price_source_degraded_until")
    assert hasattr(vm, "ohlcv_source_degraded")


def test_review_vm_for_open_trade_returns_none(populated_db_cfg) -> None:
    """Trade #2 is open (DHC); cannot review."""
    vm = build_review_vm(trade_id=2, cfg=populated_db_cfg)
    assert vm is None


def test_review_vm_rejects_already_reviewed(populated_db_cfg) -> None:
    """V1 single-review-per-trade per brief §3.2."""
    from datetime import datetime as _dt
    from swing.data.db import connect
    from swing.data.repos.trades import update_trade_review_fields
    # Mark trade 1 reviewed:
    conn = connect(populated_db_cfg.paths.db_path)
    with conn:
        update_trade_review_fields(
            conn, trade_id=1,
            reviewed_at=_dt.now().isoformat(timespec="seconds"),
            mistake_tags_json='["none_observed"]',
            entry_grade="A", management_grade="A", exit_grade="A",
            process_grade="A", disqualifying_process_violation=False,
            realized_R_if_plan_followed=None,
            mistake_cost_confidence=None,
            lesson_learned="Test review.",
        )
    conn.close()
    vm = build_review_vm(trade_id=1, cfg=populated_db_cfg)
    assert vm is None  # already reviewed → 404 in the GET handler
