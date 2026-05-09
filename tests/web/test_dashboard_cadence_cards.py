"""Dashboard cadence-card tests (Phase 6 Task 13).

Verifies that CadenceCardVM is populated from list_recent() and the
cadence_cards partial renders Daily/Weekly/Monthly headings with
appropriate scheduling/completion text.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_app_with_review_log_rows(tmp_path: Path):
    """FastAPI app with one review_log row per cadence (daily, weekly,
    monthly), all completed — confirms three cadence cards render."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.review_log import insert_pre_create, complete_review_atomic
    from swing.web.app import create_app

    db_path = tmp_path / "phase6_cadence.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        daily_id = insert_pre_create(
            conn, review_type="daily",
            period_start="2026-05-01", period_end="2026-05-01",
            scheduled_date="2026-05-01",
        )
        weekly_id = insert_pre_create(
            conn, review_type="weekly",
            period_start="2026-04-28", period_end="2026-05-02",
            scheduled_date="2026-05-02",
        )
        monthly_id = insert_pre_create(
            conn, review_type="monthly",
            period_start="2026-04-01", period_end="2026-04-30",
            scheduled_date="2026-04-30",
        )
    # complete_review_atomic manages its own transaction
    complete_review_atomic(
        conn, review_id=daily_id,
        completed_date="2026-05-01",
        duration_minutes=15,
        primary_lesson="Good discipline.",
        next_period_focus="Watch MA support.",
    )
    complete_review_atomic(
        conn, review_id=weekly_id,
        completed_date="2026-05-02",
        duration_minutes=30,
        primary_lesson="Week was clean.",
        next_period_focus="Tighten stops.",
    )
    complete_review_atomic(
        conn, review_id=monthly_id,
        completed_date="2026-04-30",
        duration_minutes=60,
        primary_lesson="Strong month.",
        next_period_focus="Scale into winners.",
    )
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


@pytest.fixture
def test_app_with_pending_daily(tmp_path: Path):
    """FastAPI app with one review_log row for daily cadence with
    completed_date IS NULL (pending) — confirms 'Scheduled'/'Pending' text."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.review_log import insert_pre_create
    from swing.web.app import create_app

    db_path = tmp_path / "phase6_pending.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        insert_pre_create(
            conn, review_type="daily",
            period_start="2026-05-02", period_end="2026-05-02",
            scheduled_date="2026-05-02",
        )
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return create_app(cfg)


def test_dashboard_renders_three_cadence_cards(test_app_with_review_log_rows):
    """Dashboard renders a cadence-card section with Daily/Weekly/Monthly headings."""
    with TestClient(test_app_with_review_log_rows) as client:
        r = client.get("/")
    assert r.status_code == 200
    # 3 cards (daily/weekly/monthly) — each article has class "cadence-card":
    assert r.text.count("cadence-card") >= 3
    assert "Daily" in r.text
    assert "Weekly" in r.text
    assert "Monthly" in r.text


def test_cadence_card_shows_scheduled_when_no_completion(test_app_with_pending_daily):
    """Pending daily card renders 'Scheduled' or 'Pending' text (no completed_date)."""
    with TestClient(test_app_with_pending_daily) as client:
        r = client.get("/")
    assert r.status_code == 200
    # Daily card has scheduled_date but no completed_date:
    assert "Scheduled" in r.text or "Pending" in r.text


# Task E.1: pending cadence card renders inline "Complete review" link
def test_pending_cadence_card_renders_complete_review_link(tmp_path: Path):
    """Pending daily card renders an inline link to /reviews/<id>/complete."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.review_log import insert_pre_create
    from swing.web.app import create_app

    db_path = tmp_path / "phase_e_pending_link.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        review_id = insert_pre_create(
            conn, review_type="daily",
            period_start="2026-05-08", period_end="2026-05-08",
            scheduled_date="2026-05-08",
        )
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    app = create_app(cfg)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    # Pending card MUST surface the "Complete review" link with the actual review_id:
    assert f'href="/reviews/{review_id}/complete"' in r.text
    assert "Complete review" in r.text


# Task E.2: completed cadence card does NOT render the "Complete review" link
def test_completed_cadence_card_does_not_render_complete_review_link(tmp_path: Path):
    """Completed cadence card MUST NOT render the inline 'Complete review' link."""
    from dataclasses import replace as dc_replace
    from swing.config import load
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.review_log import (
        complete_review_atomic,
        insert_pre_create,
    )
    from swing.web.app import create_app

    db_path = tmp_path / "phase_e_completed_no_link.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    with conn:
        daily_id = insert_pre_create(
            conn, review_type="daily",
            period_start="2026-05-08", period_end="2026-05-08",
            scheduled_date="2026-05-08",
        )
        weekly_id = insert_pre_create(
            conn, review_type="weekly",
            period_start="2026-05-04", period_end="2026-05-08",
            scheduled_date="2026-05-08",
        )
        monthly_id = insert_pre_create(
            conn, review_type="monthly",
            period_start="2026-04-01", period_end="2026-04-30",
            scheduled_date="2026-04-30",
        )
    complete_review_atomic(
        conn, review_id=daily_id,
        completed_date="2026-05-08",
        duration_minutes=15,
        primary_lesson="Done.",
        next_period_focus="Tomorrow.",
    )
    complete_review_atomic(
        conn, review_id=weekly_id,
        completed_date="2026-05-08",
        duration_minutes=30,
        primary_lesson="Week.",
        next_period_focus="Next.",
    )
    complete_review_atomic(
        conn, review_id=monthly_id,
        completed_date="2026-04-30",
        duration_minutes=60,
        primary_lesson="Month.",
        next_period_focus="Next month.",
    )
    conn.close()

    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    app = create_app(cfg)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    # All three cadences are completed — NO "Complete review" link should appear:
    assert "Complete review" not in r.text
    assert "/complete\"" not in r.text
