"""Phase 13 T3.SB3 T-B.3.4 — Period review helpers + persistence.

Per spec §E.5 LOCK signatures:
  * ``get_period_lessons_summary(conn, *, period_start, period_end) -> str``
  * ``get_period_mistake_tag_aggregate(conn, *, period_start, period_end)
        -> dict[str, int]``
  * ``get_period_cohort_health_deltas(conn, *, current_period_start,
        current_period_end, prior_period_start, prior_period_end)
        -> dict[str, float]``

Plus the persistence path: ``complete_review_atomic`` accepts
``auto_populated_field_keys_json`` (server-stamped) + uses ``... or None``
for the nullable JSON column (Phase 6 deviation #3 CLAUDE.md gotcha).
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import connect, ensure_schema


def _seed_review_log(
    conn: sqlite3.Connection,
    *,
    period_start: str,
    period_end: str,
    completed_date: str | None,
    primary_lesson: str | None = None,
    n_trades_reviewed: int = 0,
    review_type: str = "weekly",
) -> int:
    cursor = conn.execute(
        "INSERT INTO review_log ("
        "review_type, period_start, period_end, scheduled_date, "
        "completed_date, skipped, duration_minutes, n_trades_reviewed, "
        "total_mistake_cost_R, total_lucky_violation_R, "
        "primary_lesson, next_period_focus, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            review_type, period_start, period_end, period_end,
            completed_date, 0 if completed_date else 0,
            45 if completed_date else None,
            n_trades_reviewed, 0.0, 0.0,
            primary_lesson, None,
            f"{period_end}T17:00:00",
        ),
    )
    return cursor.lastrowid


def _seed_reviewed_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    sector: str = "",
    reviewed_at: str,
    mistake_tags: list[str] | None = None,
    realized_R_if_plan_followed: float | None = None,
    process_grade: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, "
        "pre_trade_locked_at, current_size, sector, "
        "reviewed_at, mistake_tags, realized_R_if_plan_followed, process_grade"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ticker, "2026-01-01", 10.0, 100, 9.0, 9.0, "reviewed",
            "manual_off_pipeline", "2026-01-01T09:30:00", 100.0,
            sector, reviewed_at,
            json.dumps(mistake_tags) if mistake_tags is not None else None,
            realized_R_if_plan_followed, process_grade,
        ),
    )
    return cursor.lastrowid


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "period_helpers.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    yield conn
    conn.close()


# --- §E.5 LOCK: helper signatures ---


def test_period_helper_signatures_match_spec_e5_lock() -> None:
    from swing.trades.review import (
        get_period_cohort_health_deltas,
        get_period_lessons_summary,
        get_period_mistake_tag_aggregate,
    )

    # §E.5 LOCK: lessons summary + mistake aggregate take (conn, *,
    # period_start: date, period_end: date).
    for fn in (
        get_period_lessons_summary, get_period_mistake_tag_aggregate,
    ):
        sig = inspect.signature(fn)
        params = list(sig.parameters)
        assert params == ["conn", "period_start", "period_end"], (
            f"{fn.__name__} signature must be "
            f"(conn, *, period_start, period_end); got {params}"
        )
        assert sig.parameters["period_start"].kind == inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["period_end"].kind == inspect.Parameter.KEYWORD_ONLY

    # §E.5 LOCK: cohort_health_deltas takes 4 date params (current +
    # prior period boundaries).
    sig = inspect.signature(get_period_cohort_health_deltas)
    params = list(sig.parameters)
    assert params == [
        "conn", "current_period_start", "current_period_end",
        "prior_period_start", "prior_period_end",
    ], f"cohort_health_deltas signature drift: {params}"
    for kw in (
        "current_period_start", "current_period_end",
        "prior_period_start", "prior_period_end",
    ):
        assert sig.parameters[kw].kind == inspect.Parameter.KEYWORD_ONLY


# --- (b) get_period_lessons_summary: concatenates completed-period
#         primary_lesson entries ---


def test_get_period_lessons_summary_concatenates_period_primary_lessons(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import get_period_lessons_summary

    # Two completed reviews within the period.
    _seed_review_log(
        db, period_start="2026-05-04", period_end="2026-05-08",
        completed_date="2026-05-08", primary_lesson="Lesson A",
    )
    _seed_review_log(
        db, period_start="2026-05-11", period_end="2026-05-15",
        completed_date="2026-05-15", primary_lesson="Lesson B",
    )
    # Outside the window — must NOT appear.
    _seed_review_log(
        db, period_start="2026-06-01", period_end="2026-06-05",
        completed_date="2026-06-05", primary_lesson="Lesson OUT",
    )
    # Incomplete — must NOT appear. Distinct period to satisfy UNIQUE
    # (review_type, period_start, period_end) constraint on review_log.
    _seed_review_log(
        db, period_start="2026-05-18", period_end="2026-05-19",
        completed_date=None, primary_lesson="Lesson INCOMPLETE",
    )
    db.commit()

    summary = get_period_lessons_summary(
        db, period_start=date(2026, 5, 1), period_end=date(2026, 5, 20),
    )
    assert isinstance(summary, str)
    assert "Lesson A" in summary
    assert "Lesson B" in summary
    assert "Lesson OUT" not in summary
    assert "Lesson INCOMPLETE" not in summary


def test_get_period_lessons_summary_empty_period_returns_empty_string(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import get_period_lessons_summary

    summary = get_period_lessons_summary(
        db, period_start=date(2026, 5, 1), period_end=date(2026, 5, 7),
    )
    assert summary == ""


# --- (c) get_period_mistake_tag_aggregate: tag → count ---


def test_get_period_mistake_tag_aggregate_counts_tags_across_period_reviews(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import get_period_mistake_tag_aggregate

    _seed_reviewed_trade(
        db, ticker="ABC", reviewed_at="2026-05-05T10:00:00",
        mistake_tags=["CHASED", "FOMO"],
    )
    _seed_reviewed_trade(
        db, ticker="DEF", reviewed_at="2026-05-10T10:00:00",
        mistake_tags=["CHASED"],
    )
    _seed_reviewed_trade(
        db, ticker="GHI", reviewed_at="2026-05-15T10:00:00",
        mistake_tags=["FOMO", "NO_STOP"],
    )
    # Outside the window — must NOT count.
    _seed_reviewed_trade(
        db, ticker="JKL", reviewed_at="2026-06-01T10:00:00",
        mistake_tags=["EARLY_ENTRY"],
    )
    db.commit()

    agg = get_period_mistake_tag_aggregate(
        db, period_start=date(2026, 5, 1), period_end=date(2026, 5, 20),
    )
    assert isinstance(agg, dict)
    assert agg == {"CHASED": 2, "FOMO": 2, "NO_STOP": 1}


def test_get_period_mistake_tag_aggregate_empty_period_returns_empty_dict(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import get_period_mistake_tag_aggregate

    agg = get_period_mistake_tag_aggregate(
        db, period_start=date(2026, 5, 1), period_end=date(2026, 5, 7),
    )
    assert agg == {}


# --- (d) get_period_cohort_health_deltas: cohort → delta ---


def test_get_period_cohort_health_deltas_returns_per_sector_delta(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import get_period_cohort_health_deltas

    # Current-period: 2 trades in "Tech" sector with realized R = 1.0 + 3.0 = 2.0 avg.
    _seed_reviewed_trade(
        db, ticker="ABC", sector="Tech", reviewed_at="2026-05-10T10:00:00",
        realized_R_if_plan_followed=1.0,
    )
    _seed_reviewed_trade(
        db, ticker="DEF", sector="Tech", reviewed_at="2026-05-15T10:00:00",
        realized_R_if_plan_followed=3.0,
    )
    # Prior-period: 1 trade in "Tech" sector with realized R = 0.5.
    _seed_reviewed_trade(
        db, ticker="GHI", sector="Tech", reviewed_at="2026-04-20T10:00:00",
        realized_R_if_plan_followed=0.5,
    )
    # Current-period only — "Energy" cohort with no prior.
    _seed_reviewed_trade(
        db, ticker="JKL", sector="Energy", reviewed_at="2026-05-12T10:00:00",
        realized_R_if_plan_followed=-1.0,
    )
    db.commit()

    deltas = get_period_cohort_health_deltas(
        db,
        current_period_start=date(2026, 5, 1),
        current_period_end=date(2026, 5, 20),
        prior_period_start=date(2026, 4, 1),
        prior_period_end=date(2026, 4, 30),
    )
    assert isinstance(deltas, dict)
    # Tech: current avg = 2.0; prior = 0.5; delta = 1.5.
    assert deltas["Tech"] == pytest.approx(1.5)
    # Energy: current only; delta = current avg (-1.0) - 0 = -1.0.
    assert deltas["Energy"] == pytest.approx(-1.0)


def test_get_period_cohort_health_deltas_empty_period_returns_empty_dict(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import get_period_cohort_health_deltas

    deltas = get_period_cohort_health_deltas(
        db,
        current_period_start=date(2026, 5, 1),
        current_period_end=date(2026, 5, 7),
        prior_period_start=date(2026, 4, 24),
        prior_period_end=date(2026, 4, 30),
    )
    assert deltas == {}


# --- (e) Discriminating `... or None` test: empty JSON form input persists
#         NULL, not empty-string (Phase 6 deviation #3 CLAUDE.md gotcha) ---


def test_complete_review_atomic_persists_null_when_audit_envelope_is_empty(
    db: sqlite3.Connection,
) -> None:
    from swing.data.repos.review_log import complete_review_atomic

    review_id = _seed_review_log(
        db, period_start="2026-05-04", period_end="2026-05-08",
        completed_date=None,
    )
    db.commit()

    # Submit with None — column must persist NULL, not empty string.
    complete_review_atomic(
        db, review_id=review_id,
        completed_date="2026-05-08",
        duration_minutes=30,
        primary_lesson="lesson",
        next_period_focus="focus",
        auto_populated_field_keys_json=None,
    )
    row = db.execute(
        "SELECT auto_populated_field_keys_json FROM review_log "
        "WHERE review_id = ?",
        (review_id,),
    ).fetchone()
    assert row[0] is None, (
        "auto_populated_field_keys_json must persist NULL when no audit "
        "envelope was server-stamped (NOT empty string — Phase 6 deviation "
        "#3 gotcha)."
    )


def test_complete_review_atomic_persists_audit_envelope_round_trip(
    db: sqlite3.Connection,
) -> None:
    from swing.data.repos.review_log import complete_review_atomic

    review_id = _seed_review_log(
        db, period_start="2026-05-04", period_end="2026-05-08",
        completed_date=None,
    )
    db.commit()

    envelope = json.dumps(["primary_lesson", "next_period_focus"])
    complete_review_atomic(
        db, review_id=review_id,
        completed_date="2026-05-08",
        duration_minutes=30,
        primary_lesson="lesson",
        next_period_focus="focus",
        auto_populated_field_keys_json=envelope,
    )
    row = db.execute(
        "SELECT auto_populated_field_keys_json FROM review_log "
        "WHERE review_id = ?",
        (review_id,),
    ).fetchone()
    assert row[0] == envelope
    decoded = json.loads(row[0])
    assert decoded == ["primary_lesson", "next_period_focus"]


def test_complete_review_atomic_audit_envelope_defaults_to_none() -> None:
    """Existing callsites that don't pass the kwarg must continue to work
    (backwards-compat with all Phase 6/7/8/9/10/11/12/12.5 callsites)."""
    from swing.data.repos.review_log import complete_review_atomic
    sig = inspect.signature(complete_review_atomic)
    assert "auto_populated_field_keys_json" in sig.parameters
    assert (
        sig.parameters["auto_populated_field_keys_json"].default is None
    )
