"""22-I T12 -- review_log: the service twin FIRST, then the F-I3 writer, then the
triggers (plan section 3 T12; authorize-then-abort, harness section 5.1: a
trigger never ships ahead of its service check).

    T12a  complete_review_atomic refuses an ALREADY-completed row with the typed
          ReviewAlreadyCompletedError (RD S3-F3 (A); CHARC's scope ruling), and
          the CLI wraps it to click.ClickException("Review already completed")
          -- the web's 409 detail text (routes/trades.py:3766-3770) verbatim.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.review_log import (
    ReviewAlreadyCompletedError,
    complete_review_atomic,
    insert_pre_create,
)


def _all_columns(conn: sqlite3.Connection, review_id: int) -> tuple:
    return conn.execute("SELECT * FROM review_log WHERE review_id = ?",
                        (review_id,)).fetchone()


@pytest.fixture
def completed(tmp_path: Path):
    conn = ensure_schema(tmp_path / "rl.db")
    with conn:
        rid = insert_pre_create(conn, review_type="daily", period_start="2026-04-30",
                                period_end="2026-04-30", scheduled_date="2026-05-01")
    complete_review_atomic(conn, review_id=rid, completed_date="2026-05-02",
                           duration_minutes=10, primary_lesson="first lesson",
                           next_period_focus="first focus")
    yield conn, rid
    conn.close()


def test_complete_review_atomic_refuses_completed_row(completed) -> None:
    conn, rid = completed
    before = _all_columns(conn, rid)
    assert len(before) == 24
    assert before[5] == "2026-05-02"  # completed_date
    with pytest.raises(ReviewAlreadyCompletedError, match="Review already completed"):
        complete_review_atomic(conn, review_id=rid, completed_date="2026-06-01",
                               duration_minutes=99, primary_lesson="second lesson",
                               next_period_focus="second focus")
    assert _all_columns(conn, rid) == before
    assert not conn.in_transaction  # the existing except rolled back


def test_review_already_completed_error_is_a_value_error() -> None:
    """The type the CLI boundary catches; a ValueError subclass so a caller
    written against the service's existing ValueError contract still sees it."""
    assert issubclass(ReviewAlreadyCompletedError, ValueError)
