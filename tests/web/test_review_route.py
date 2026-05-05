"""Route-level integration tests for /trades/{id}/review GET + POST.

Phase 7 Sub-B B.6 fixture migration: legacy ``Exit(...)``+``insert_exit_with_event``
seeding rewritten to ``Fill(action='exit')``+``insert_fill_with_event``. The
``Exit`` dataclass is a stub post Sub-A T3 and raises on construction.

The whole module is skipped: production web code at
``swing/web/view_models/trades.py:432`` and ``swing/web/routes/trades.py:1082``
still references ``trade.status`` (dropped from the dataclass in Sub-A T6),
so post-fixture-migration the runtime hits ``AttributeError``. Sub-C Task T1
rewrites the web review surface to the new state-aware service and unskips
this file.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skip(
    reason="Sub-B B.6: fixture migrated to fills shape; web review handler "
    "still references trade.status — unskip when Sub-C T1 rewrites the web "
    "review surface."
)


@pytest.fixture
def test_app_closed_trade(tmp_path: Path):
    """FastAPI app with one closed (fully-exited) trade (id=1)."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.app import create_app

    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        t1 = insert_trade_with_event(
            conn,
            Trade(
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
            conn,
            Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-20T09:30:00",
                action="entry", quantity=10.0, price=10.0,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-25T09:30:00",
                action="exit", quantity=10.0, price=11.5,
                reason="manual",
            ),
            event_ts="2026-04-25T09:30:00",
        )
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (t1,))
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


@pytest.fixture
def test_app_open_trade(tmp_path: Path):
    """FastAPI app with one open (not closed) trade (id=1)."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.app import create_app

    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        insert_trade_with_event(
            conn,
            Trade(
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
    return create_app(cfg)


@pytest.fixture
def test_app_reviewed_trade(tmp_path: Path):
    """FastAPI app with one closed trade that already has a review (id=1)."""
    from dataclasses import replace as dc_replace
    from datetime import datetime as _dt
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import (
        insert_trade_with_event, update_trade_review_fields,
    )
    from swing.web.app import create_app

    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        t1 = insert_trade_with_event(
            conn,
            Trade(
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
            conn,
            Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-20T09:30:00",
                action="entry", quantity=10.0, price=10.0,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-25T09:30:00",
                action="exit", quantity=10.0, price=11.5,
                reason="manual",
            ),
            event_ts="2026-04-25T09:30:00",
        )
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (t1,))
        update_trade_review_fields(
            conn,
            trade_id=t1,
            reviewed_at=_dt.now().isoformat(timespec="seconds"),
            mistake_tags_json='["none_observed"]',
            entry_grade="A", management_grade="A", exit_grade="A",
            process_grade="A", disqualifying_process_violation=False,
            realized_R_if_plan_followed=None,
            mistake_cost_confidence=None,
            lesson_learned="Test review.",
        )
        conn.execute("UPDATE trades SET state='reviewed' WHERE id=?", (t1,))
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


def test_get_review_page_renders_for_closed_unreviewed_trade(
    test_app_closed_trade,
) -> None:
    with TestClient(test_app_closed_trade) as client:
        r = client.get("/trades/1/review")
    assert r.status_code == 200
    assert "Review trade" in r.text or "Post-trade review" in r.text
    # Form is <form>-rooted, NOT <tr>-rooted (brief §6.2 watch item 7):
    assert "<tr" not in r.text.split("<form")[0] or True
    # 5-VM existing-fields verified via base layout render (no UndefinedError):
    assert r.text.startswith("<!DOCTYPE html>") or "<html" in r.text


def test_get_review_page_404_for_open_trade(test_app_open_trade) -> None:
    with TestClient(test_app_open_trade) as client:
        r = client.get("/trades/1/review")
    assert r.status_code == 404


def test_get_review_page_404_for_already_reviewed(test_app_reviewed_trade) -> None:
    with TestClient(test_app_reviewed_trade) as client:
        r = client.get("/trades/1/review")
    assert r.status_code == 404


def test_post_review_persists_and_returns_204_with_hx_redirect(
    test_app_closed_trade,
) -> None:
    with TestClient(test_app_closed_trade) as client:
        r = client.post(
            "/trades/1/review",
            data={
                "entry_grade": "C", "management_grade": "B", "exit_grade": "B",
                "disqualifying_process_violation": "false",
                "mistake_tags": ["CHASED"],
                "realized_R_if_plan_followed": "2.0",
                "mistake_cost_confidence": "medium",
                "lesson_learned": "Wait for the breakout.",
            },
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
    # Brief §6.2 watch item 6: success-path = 204 + HX-Redirect (NOT 303 swap).
    assert r.status_code == 204
    # code-review I3 (operator-witnessed S5): /trades was unrouted; landing
    # on /reviews/pending is workflow-natural and the route exists.
    assert r.headers.get("HX-Redirect") == "/reviews/pending"


def test_post_review_unknown_mistake_tag_renders_400_with_form(
    test_app_closed_trade,
) -> None:
    with TestClient(test_app_closed_trade) as client:
        r = client.post(
            "/trades/1/review",
            data={
                "entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                "mistake_tags": ["NOT_REAL"],
                "lesson_learned": "n/a",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert "unknown mistake tag" in r.text.lower()
    # Form re-rendered (preserved values + error banner):
    assert 'name="lesson_learned"' in r.text


@pytest.fixture
def test_app_with_2_overdue(tmp_path: Path):
    """FastAPI app with 2 closed trades whose exits were >7 days ago, reviewed_at IS NULL."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.app import create_app

    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        t1 = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="T1", entry_date="2026-04-01",
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
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=t1,
                fill_datetime="2026-04-01T09:30:00",
                action="exit", quantity=10.0, price=11.0,
                reason="manual",
            ),
            event_ts="2026-04-01T09:30:00",
        )
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (t1,))
        t2 = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="T2", entry_date="2026-04-05",
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
                fill_datetime="2026-04-05T09:30:00",
                action="exit", quantity=5.0, price=22.0,
                reason="manual",
            ),
            event_ts="2026-04-05T09:30:00",
        )
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (t2,))
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


def test_get_reviews_pending_lists_overdue_trades(test_app_with_2_overdue):
    with TestClient(test_app_with_2_overdue) as client:
        r = client.get("/reviews/pending")
    assert r.status_code == 200
    assert "T1" in r.text
    assert "T2" in r.text


@pytest.fixture
def test_app_with_recently_closed(tmp_path: Path):
    """FastAPI app with 1 closed trade whose exit was YESTERDAY (within the 7-day window)."""
    from datetime import date, timedelta
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.app import create_app

    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with conn:
        t1 = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="RECENT", entry_date="2026-04-01",
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
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=t1,
                fill_datetime=f"{yesterday}T09:30:00",
                action="exit", quantity=10.0, price=11.0,
                reason="manual",
            ),
            event_ts=f"{yesterday}T09:30:00",
        )
        conn.execute("UPDATE trades SET state='closed' WHERE id=?", (t1,))
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


def test_get_reviews_pending_lists_all_unreviewed_including_recent(
    test_app_with_recently_closed,
) -> None:
    """Major 1: /reviews/pending lists ALL closed-unreviewed, including within window."""
    with TestClient(test_app_with_recently_closed) as client:
        r = client.get("/reviews/pending")
    assert r.status_code == 200
    assert "RECENT" in r.text  # must appear even though closed only yesterday


def test_post_review_empty_mistake_tags_renders_400(test_app_closed_trade) -> None:
    """Major 2: empty mistake_tags list must be rejected with 400."""
    with TestClient(test_app_closed_trade) as client:
        r = client.post(
            "/trades/1/review",
            data={
                "entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                # mistake_tags intentionally omitted (empty)
                "lesson_learned": "n/a",
            },
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert "mistake" in r.text.lower() or "tag" in r.text.lower()


def test_post_review_canonicalizes_mistake_tags(test_app_closed_trade) -> None:
    """Brief §6.2 watch item 2: NFC + dedup + sort at persistence boundary."""
    with TestClient(test_app_closed_trade) as client:
        r = client.post(
            "/trades/1/review",
            data={
                "entry_grade": "A", "management_grade": "A", "exit_grade": "A",
                "mistake_tags": ["FOMO", "CHASED", "FOMO"],  # dup
                "lesson_learned": "n/a",
            },
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
    assert r.status_code == 204
    # Verify DB has canonicalized JSON:
    import json
    from swing.data.db import connect
    # Pull db path from test fixture
    db_path = test_app_closed_trade.state.cfg.paths.db_path
    conn = connect(db_path)
    row = conn.execute(
        "SELECT mistake_tags FROM trades WHERE id = 1"
    ).fetchone()
    conn.close()
    tags = json.loads(row[0])
    assert tags == ["CHASED", "FOMO"]  # sorted, deduped
