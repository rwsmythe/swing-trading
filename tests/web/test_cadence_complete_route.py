"""Cadence-completion web route tests (R1 Critical 1)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_app_with_pending_daily(tmp_path: Path):
    """FastAPI app with one closed trade + a pending (uncompleted) daily review."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Trade
    from swing.data.repos.review_log import insert_pre_create
    from swing.data.repos.trades import insert_trade_with_event
    from tests.conftest import insert_exit_fill
    from swing.web.app import create_app

    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        t1 = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="VIR", entry_date="2026-04-29",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-29T09:30:00",
        )
        insert_exit_fill(
            conn, trade_id=t1, exit_date="2026-04-30",
            exit_price=12.0, shares=10, reason="manual",
            fill_datetime="2026-04-30T09:30:00",
        )
        insert_pre_create(
            conn, review_type="daily",
            period_start="2026-04-30", period_end="2026-04-30",
            scheduled_date="2026-05-01",
        )
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


@pytest.fixture
def test_app_with_completed_daily(tmp_path: Path):
    """FastAPI app with one daily review that is already completed."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.models import Trade
    from swing.data.repos.review_log import complete_review_atomic, insert_pre_create
    from swing.data.repos.trades import insert_trade_with_event
    from tests.conftest import insert_exit_fill
    from swing.web.app import create_app

    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        t1 = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="VIR", entry_date="2026-04-29",
                entry_price=10.0, initial_shares=10, initial_stop=9.0,
                current_stop=9.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ),
            event_ts="2026-04-29T09:30:00",
        )
        insert_exit_fill(
            conn, trade_id=t1, exit_date="2026-04-30",
            exit_price=12.0, shares=10, reason="manual",
            fill_datetime="2026-04-30T09:30:00",
        )
        insert_pre_create(
            conn, review_type="daily",
            period_start="2026-04-30", period_end="2026-04-30",
            scheduled_date="2026-05-01",
        )
    conn.close()
    # complete_review_atomic manages its own transaction (BEGIN IMMEDIATE)
    conn2 = connect(db_path)
    complete_review_atomic(
        conn2, review_id=1,
        completed_date="2026-05-01",
        duration_minutes=15,
        primary_lesson="Done.",
        next_period_focus="Keep going.",
    )
    conn2.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


def test_get_cadence_complete_form(test_app_with_pending_daily):
    with TestClient(test_app_with_pending_daily) as client:
        r = client.get("/reviews/1/complete")
    assert r.status_code == 200
    assert "primary_lesson" in r.text
    assert "next_period_focus" in r.text
    assert "duration_minutes" in r.text


def test_post_cadence_complete_returns_204_with_hx_redirect(
    test_app_with_pending_daily,
):
    with TestClient(test_app_with_pending_daily) as client:
        r = client.post(
            "/reviews/1/complete",
            data={
                "duration_minutes": "12",
                "primary_lesson": "Inaugural.",
                "next_period_focus": "Same setup.",
            },
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
    assert r.status_code == 204
    assert r.headers.get("HX-Redirect") == "/"


def test_get_cadence_complete_404_for_unknown_review(test_app_with_pending_daily):
    with TestClient(test_app_with_pending_daily) as client:
        r = client.get("/reviews/9999/complete")
    assert r.status_code == 404


def test_get_cadence_complete_404_for_already_completed(test_app_with_completed_daily):
    with TestClient(test_app_with_completed_daily) as client:
        r = client.get("/reviews/1/complete")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 3e.16 — trade-activity section rendering.
# ---------------------------------------------------------------------------


def test_3e16_renders_trade_activity_section_when_populated(
    test_app_with_pending_daily,
):
    """The cadence-completion page must render the trade-activity heading
    and one row per in-period trade with a deep-link to /trades/{id}."""
    with TestClient(test_app_with_pending_daily) as client:
        r = client.get("/reviews/1/complete")
    assert r.status_code == 200
    assert "Trade activity during this period" in r.text
    # VIR was opened 2026-04-29 + closed 2026-04-30; the daily review period
    # is 2026-04-30, so the only in-period activity is the CLOSE.
    assert "[CLOSED]" in r.text
    # Deep-link to /trades/{id} present.
    assert 'href="/trades/1"' in r.text
    assert "VIR" in r.text


def test_3e16_renders_empty_state_when_no_activity(tmp_path: Path):
    """A pending review with no trade activity in its period must render
    the empty-state message (and still show the section heading)."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.review_log import insert_pre_create
    from swing.web.app import create_app

    db_path = tmp_path / "phase6.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    try:
        with conn:
            insert_pre_create(
                conn, review_type="daily",
                period_start="2026-06-15", period_end="2026-06-15",
                scheduled_date="2026-06-16",
            )
    finally:
        conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    app = create_app(cfg)

    with TestClient(app) as client:
        r = client.get("/reviews/1/complete")
    assert r.status_code == 200
    assert "Trade activity during this period" in r.text
    assert "No trade activity in this period." in r.text
