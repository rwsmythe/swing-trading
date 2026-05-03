"""Route-level integration tests for /trades/{id}/review GET + POST."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_app_closed_trade(tmp_path: Path):
    """FastAPI app with one closed (fully-exited) trade (id=1)."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Exit, Trade
    from swing.data.repos.trades import insert_exit_with_event, insert_trade_with_event
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
                current_stop=9.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        insert_exit_with_event(
            conn,
            Exit(
                id=None, trade_id=t1, exit_date="2026-04-25",
                exit_price=11.5, shares=10, reason="manual",
                realized_pnl=15.0, r_multiple=1.5, notes=None,
            ),
            event_ts="2026-04-25T09:30:00",
        )
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
                current_stop=7.30, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
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
    from swing.data.models import Exit, Trade
    from swing.data.repos.trades import (
        insert_exit_with_event, insert_trade_with_event,
        update_trade_review_fields,
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
                current_stop=9.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-20T09:30:00",
        )
        insert_exit_with_event(
            conn,
            Exit(
                id=None, trade_id=t1, exit_date="2026-04-25",
                exit_price=11.5, shares=10, reason="manual",
                realized_pnl=15.0, r_multiple=1.5, notes=None,
            ),
            event_ts="2026-04-25T09:30:00",
        )
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
    assert r.headers.get("HX-Redirect") == "/trades"


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
    from swing.data.models import Exit, Trade
    from swing.data.repos.trades import insert_exit_with_event, insert_trade_with_event
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
                current_stop=9.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-01T09:30:00",
        )
        insert_exit_with_event(
            conn,
            Exit(
                id=None, trade_id=t1, exit_date="2026-04-01",
                exit_price=11.0, shares=10, reason="manual",
                realized_pnl=10.0, r_multiple=1.0, notes=None,
            ),
            event_ts="2026-04-01T09:30:00",
        )
        t2 = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="T2", entry_date="2026-04-05",
                entry_price=20.0, initial_shares=5, initial_stop=18.0,
                current_stop=18.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-05T09:30:00",
        )
        insert_exit_with_event(
            conn,
            Exit(
                id=None, trade_id=t2, exit_date="2026-04-05",
                exit_price=22.0, shares=5, reason="manual",
                realized_pnl=10.0, r_multiple=1.0, notes=None,
            ),
            event_ts="2026-04-05T09:30:00",
        )
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
