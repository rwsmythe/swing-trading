"""Phase 7 Sub-B B.6 — review service-layer tests.

Covers ``swing.trades.review.complete_trade_review``:

  * State-precondition rejection: trade must be in ``'closed'`` exactly. The
    helper rejects reviewed (already-reviewed terminal state) AND every
    active state (entered/managing/partial_exited).
  * Positive path: the 10 review fields plus the ``closed → reviewed``
    state transition land atomically.
  * Atomicity: when the state-transition raises, the prior review-field
    UPDATE is rolled back (no half-written review row).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import run_migrations
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import get_trade, insert_trade_with_event
from swing.trades import review as review_module
from swing.trades.review import complete_trade_review


# ---- Fixture helpers ----

def _seed_v14(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "swing.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=16, backup_dir=tmp_path)
    return conn


def _seed_trade_with_state(
    conn: sqlite3.Connection, *, state: str,
) -> int:
    """Insert a trade row + entry fill, then UPDATE the state directly to
    bypass the state machine for fixture-seeding purposes.

    Direct UPDATE is intentional and contained to test fixtures: it produces
    a deterministic starting state across the lifecycle enum (``entered``,
    ``managing``, ``partial_exited``, ``closed``, ``reviewed``) without
    forcing each fixture to issue a multi-step transition chain.
    """
    event_ts = "2026-05-01T09:30:00"
    trade = Trade(
        id=None,
        ticker="AAPL",
        entry_date="2026-05-01",
        entry_price=180.0,
        initial_shares=10,
        initial_stop=170.0,
        current_stop=170.0,
        state="entered",
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at=event_ts,
    )
    with conn:
        trade_id = insert_trade_with_event(
            conn, trade, event_ts=event_ts, rationale="seed",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None,
                trade_id=trade_id,
                fill_datetime=event_ts,
                action="entry",
                quantity=10.0,
                price=180.0,
            ),
            event_ts=event_ts,
        )
        if state != "entered":
            conn.execute(
                "UPDATE trades SET state = ? WHERE id = ?",
                (state, trade_id),
            )
    return trade_id


def _complete_kwargs() -> dict:
    """Return a full set of kwargs for ``complete_trade_review`` so each
    test can extend or override only the fields under test."""
    return dict(
        reviewed_at="2026-05-05T16:00:00",
        mistake_tags_json=json.dumps(["none_observed"]),
        entry_grade="A",
        management_grade="A",
        exit_grade="A",
        process_grade="A",
        disqualifying_process_violation=False,
        realized_R_if_plan_followed=None,
        mistake_cost_confidence=None,
        lesson_learned="Process clean.",
        event_ts="2026-05-05T16:00:00",
        rationale="post-trade review",
    )


# ---- Tests ----

def test_complete_trade_review_transitions_closed_to_reviewed(
    tmp_path: Path,
) -> None:
    """Positive path: closed trade flips to reviewed and writes all 10 fields."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_trade_with_state(conn, state="closed")
        complete_trade_review(
            conn,
            trade_id,
            reviewed_at="2026-05-05T16:00:00",
            mistake_tags_json=json.dumps(["CHASED", "FOMO"]),
            entry_grade="C",
            management_grade="B",
            exit_grade="B",
            process_grade="C",
            disqualifying_process_violation=False,
            realized_R_if_plan_followed=2.0,
            mistake_cost_confidence="medium",
            lesson_learned="Wait for the breakout, not the build-up.",
            event_ts="2026-05-05T16:00:00",
            rationale="post-trade review complete",
        )

        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == "reviewed"
        assert trade.reviewed_at == "2026-05-05T16:00:00"

        # Verify all 10 review fields persisted.
        row = conn.execute(
            "SELECT reviewed_at, mistake_tags, entry_grade, management_grade, "
            "exit_grade, process_grade, disqualifying_process_violation, "
            "realized_R_if_plan_followed, mistake_cost_confidence, "
            "lesson_learned FROM trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
        assert row[0] == "2026-05-05T16:00:00"
        assert json.loads(row[1]) == ["CHASED", "FOMO"]
        assert row[2] == "C"
        assert row[3] == "B"
        assert row[4] == "B"
        assert row[5] == "C"
        assert row[6] == 0  # SQLite stores bool as int
        assert row[7] == 2.0
        assert row[8] == "medium"
        assert "breakout" in row[9]
    finally:
        conn.close()


def test_complete_trade_review_rejects_already_reviewed_trade(
    tmp_path: Path,
) -> None:
    """V1 single-review-per-trade: an already-reviewed trade is rejected.

    Discriminator vs. naive ``state in ('closed', 'reviewed')``: the
    precondition must use bare ``state == 'closed'`` so a second review
    attempt is blocked.
    """
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_trade_with_state(conn, state="reviewed")
        with pytest.raises(ValueError, match="not in closed state"):
            complete_trade_review(conn, trade_id, **_complete_kwargs())

        # No second state transition: the audit log only contains the
        # entry-fill events from seeding (no closed→reviewed audit).
        notes = conn.execute(
            "SELECT notes FROM trade_events WHERE trade_id = ? "
            "AND event_type = 'note'",
            (trade_id,),
        ).fetchall()
        assert all(
            "state_transition closed->reviewed" not in (n[0] or "")
            for n in notes
        )

        # Review fields remain unset (the helper aborted before writing).
        row = conn.execute(
            "SELECT reviewed_at, mistake_tags, lesson_learned "
            "FROM trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
        assert row[0] is None
        assert row[1] is None
        assert row[2] is None
    finally:
        conn.close()


@pytest.mark.parametrize("active_state", ["entered", "managing", "partial_exited"])
def test_complete_trade_review_rejects_active_states(
    tmp_path: Path, active_state: str,
) -> None:
    """Review is post-exit only; every active state is rejected."""
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_trade_with_state(conn, state=active_state)
        with pytest.raises(ValueError, match="not in closed state"):
            complete_trade_review(conn, trade_id, **_complete_kwargs())

        # State unchanged.
        trade = get_trade(conn, trade_id)
        assert trade is not None
        assert trade.state == active_state

        # No review fields written.
        row = conn.execute(
            "SELECT reviewed_at FROM trades WHERE id = ?", (trade_id,),
        ).fetchone()
        assert row[0] is None
    finally:
        conn.close()


def test_complete_trade_review_atomic_rollback_on_state_transition_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If state_transition raises, the review-field UPDATE is rolled back.

    Both writes share one transaction (``with conn:`` in
    ``complete_trade_review``); a raise inside the block triggers ROLLBACK,
    so the review fields must NOT persist.
    """
    conn = _seed_v14(tmp_path)
    try:
        trade_id = _seed_trade_with_state(conn, state="closed")

        def boom(*args, **kwargs):
            raise RuntimeError("simulated state-machine failure")

        monkeypatch.setattr(review_module, "state_transition", boom)

        with pytest.raises(RuntimeError, match="simulated state-machine"):
            complete_trade_review(conn, trade_id, **_complete_kwargs())

        # Review fields must be NULL (transaction rolled back).
        row = conn.execute(
            "SELECT reviewed_at, mistake_tags, lesson_learned, state "
            "FROM trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
        assert row[0] is None, "reviewed_at survived rollback"
        assert row[1] is None, "mistake_tags survived rollback"
        assert row[2] is None, "lesson_learned survived rollback"
        assert row[3] == "closed", "state should remain closed after rollback"
    finally:
        conn.close()


def test_complete_trade_review_unknown_trade_id_raises(tmp_path: Path) -> None:
    conn = _seed_v14(tmp_path)
    try:
        with pytest.raises(ValueError, match="trade 999 not found"):
            complete_trade_review(conn, 999, **_complete_kwargs())
    finally:
        conn.close()
