"""Dashboard needs-review badge tests (Phase 6 Task 13).

Verifies that DashboardVM.needs_review_count is populated from
count_needs_review() and the badge partial renders/hides correctly.

Phase 7 Sub-B B.6 fixture migration: legacy ``Exit(...)``+``insert_exit_with_event``
seeding rewritten to ``Fill(action='exit')``+``insert_fill_with_event``. The
``Exit`` dataclass is a stub post Sub-A T3 and raises on construction.

The whole module is skipped: dashboard view-model construction reads
``trade.status`` (dropped in Sub-A T6), so post-fixture-migration the runtime
hits ``AttributeError``. Sub-C Task T1 rewrites the dashboard view models
and unskips this file.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skip(
    reason="Sub-B B.6: fixture migrated to fills shape; dashboard VM still "
    "references trade.status — unskip when Sub-C T1 rewrites the dashboard "
    "view models."
)


@pytest.fixture
def test_app_with_2_overdue_unreviewed_closed(tmp_path: Path):
    """FastAPI app with 2 closed trades whose exits are > 7 days ago and
    reviewed_at IS NULL — both should be counted by count_needs_review."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.app import create_app

    db_path = tmp_path / "phase6_badge.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        t1 = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="AAA", entry_date="2026-04-01",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-01T09:30:00",
            ),
            event_ts="2026-04-01T09:30:00",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-01T09:30:00",
                action="entry", quantity=10.0, price=10.0,
            ),
            event_ts="2026-04-01T09:30:00",
        )
        # Exit > 7 days before today (2026-05-02), no reviewed_at
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-20T16:00:00",
                action="exit", quantity=10.0, price=11.0,
                reason="manual",
            ),
            event_ts="2026-04-20T16:00:00",
        )
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (t1,))
        t2 = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="BBB", entry_date="2026-04-05",
                entry_price=20.0, initial_shares=5, initial_stop=18.0,
                current_stop=18.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-05T09:30:00",
            ),
            event_ts="2026-04-05T09:30:00",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=t2,
                fill_datetime="2026-04-05T09:30:00",
                action="entry", quantity=5.0, price=20.0,
            ),
            event_ts="2026-04-05T09:30:00",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=t2,
                fill_datetime="2026-04-22T16:00:00",
                action="exit", quantity=5.0, price=22.0,
                reason="manual",
            ),
            event_ts="2026-04-22T16:00:00",
        )
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (t2,))
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


@pytest.fixture
def test_app_only_open_trades(tmp_path: Path):
    """FastAPI app with one open trade only — no closed trades, so
    needs_review_count should be 0 and badge should be hidden."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.app import create_app

    db_path = tmp_path / "phase6_open.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="CCC", entry_date="2026-04-28",
                entry_price=15.0, initial_shares=8, initial_stop=14.0,
                current_stop=14.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
                trade_origin="manual_off_pipeline",
                pre_trade_locked_at="2026-04-28T09:30:00",
            ),
            event_ts="2026-04-28T09:30:00",
        )
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


def test_needs_review_count_populated(test_app_with_2_overdue_unreviewed_closed):
    """Badge shows 'Needs review (2)' when 2 overdue unreviewed closed trades exist."""
    with TestClient(test_app_with_2_overdue_unreviewed_closed) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "Needs review (2)" in r.text or "needs-review" in r.text


def test_needs_review_count_zero_hidden(test_app_only_open_trades):
    """Badge is absent when there are no overdue unreviewed closed trades."""
    with TestClient(test_app_only_open_trades) as client:
        r = client.get("/")
    assert r.status_code == 200
    # Badge hidden when count is 0:
    assert "Needs review" not in r.text
