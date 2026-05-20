"""Phase 13 T2.SB1 T-A.1.1b — watchlist_close_track repo CRUD discriminating tests.

Per plan §G.1 T-A.1.1b Step 1: 3+ discriminating tests covering
(a) insert_row roundtrips through SQL; (b) get_by_id returns inserted row;
(c) list_* paginates correctly. Caller-tx contract verified.

Covers BOTH ``watchlist_close_track_flags`` and
``watchlist_close_track_flag_events`` tables (Theme 4 Q4 audit pair per
spec §7.2 D-Q4.1 + D-Q4.7). Re-flag-after-clear scenario exercised per
Codex R1 M#9 closure (partial unique index on active flag only).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import (
    WatchlistCloseTrackFlag,
    WatchlistCloseTrackFlagEvent,
)
from swing.data.repos import watchlist_close_track as repo


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase13_t2sb1_repo_wclf.db"
    return ensure_schema(db_path)


def _make_flag(**overrides: object) -> WatchlistCloseTrackFlag:
    base = {
        "id": None,
        "ticker": "PTEN",
        "flagged_at": "2026-05-19T10:00:00.000",
        "flagged_by_surface": "web",
        "reason_text": None,
        "cleared_at": None,
        "cleared_reason": None,
    }
    base.update(overrides)
    return WatchlistCloseTrackFlag(**base)


def _make_event(flag_id: int, **overrides: object) -> WatchlistCloseTrackFlagEvent:
    base = {
        "id": None,
        "flag_id": flag_id,
        "event_type": "set",
        "event_at": "2026-05-19T10:00:00.000",
        "surface": "web",
        "reason_text": None,
    }
    base.update(overrides)
    return WatchlistCloseTrackFlagEvent(**base)


# ============================================================================
# watchlist_close_track_flags
# ============================================================================


def test_insert_flag_roundtrips_through_sql(conn: sqlite3.Connection) -> None:
    """insert_flag persists; SELECT post-INSERT returns matching values."""
    flag = _make_flag(ticker="PTEN", reason_text="at-breakout candidate")
    with conn:
        flag_id = repo.insert_flag(conn, flag)
    row = conn.execute(
        "SELECT ticker, flagged_by_surface, reason_text, cleared_at "
        "FROM watchlist_close_track_flags WHERE id = ?",
        (flag_id,),
    ).fetchone()
    assert row == ("PTEN", "web", "at-breakout candidate", None)


def test_get_flag_by_id_returns_inserted_row(conn: sqlite3.Connection) -> None:
    """get_flag_by_id reconstructs the dataclass; None on missing."""
    flag = _make_flag(ticker="CVGI")
    with conn:
        flag_id = repo.insert_flag(conn, flag)

    fetched = repo.get_flag_by_id(conn, flag_id)
    assert fetched is not None
    assert fetched.ticker == "CVGI"
    assert fetched.flagged_by_surface == "web"
    assert fetched.cleared_at is None

    assert repo.get_flag_by_id(conn, 999_999) is None


def test_list_flags_paginates_and_filters(conn: sqlite3.Connection) -> None:
    """list_flags + ticker + active_only + pagination."""
    # Seed: 2 active + 1 cleared.
    with conn:
        repo.insert_flag(conn, _make_flag(ticker="ABC"))
        repo.insert_flag(conn, _make_flag(ticker="XYZ"))
        repo.insert_flag(conn, _make_flag(
            ticker="MMM",
            cleared_at="2026-05-20T10:00:00.000",
            cleared_reason="operator_cleared",
        ))

    all_rows = repo.list_flags(conn)
    assert len(all_rows) == 3

    active = repo.list_flags(conn, active_only=True)
    assert len(active) == 2
    assert all(r.cleared_at is None for r in active)

    abc = repo.list_flags(conn, ticker="ABC")
    assert len(abc) == 1
    assert abc[0].ticker == "ABC"

    first = repo.list_flags(conn, limit=1, offset=0)
    second = repo.list_flags(conn, limit=1, offset=1)
    assert first[0].id < second[0].id


def test_re_flag_cleared_ticker_inserts_new_lifecycle_row(
    conn: sqlite3.Connection,
) -> None:
    """Per Codex R1 M#9 closure (spec §7.2 D-Q4.1): re-flagging a previously-
    cleared ticker INSERTs a new row (no UNIQUE collision); partial unique
    index ``idx_wclf_active_ticker`` is on ACTIVE flags only.
    """
    with conn:
        # 1st lifecycle: flag PTEN, then clear.
        flag1_id = repo.insert_flag(conn, _make_flag(ticker="PTEN"))
        conn.execute(
            "UPDATE watchlist_close_track_flags "
            "SET cleared_at = ?, cleared_reason = ? WHERE id = ?",
            ("2026-05-20T10:00:00.000", "operator_cleared", flag1_id),
        )

        # 2nd lifecycle: re-flag PTEN; should NOT collide.
        flag2_id = repo.insert_flag(
            conn,
            _make_flag(
                ticker="PTEN",
                flagged_at="2026-05-21T10:00:00.000",
            ),
        )

    assert flag1_id != flag2_id
    flag1 = repo.get_flag_by_id(conn, flag1_id)
    flag2 = repo.get_flag_by_id(conn, flag2_id)
    assert flag1 is not None and flag1.cleared_at is not None
    assert flag2 is not None and flag2.cleared_at is None


def test_re_flag_active_same_ticker_raises_integrity_error(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §7.2: at most one ACTIVE (cleared_at IS NULL) flag per ticker."""
    with conn:
        repo.insert_flag(conn, _make_flag(ticker="PTEN"))
    with pytest.raises(sqlite3.IntegrityError), conn:
        repo.insert_flag(conn, _make_flag(
            ticker="PTEN",
            flagged_at="2026-05-20T10:00:00.000",
        ))


# ============================================================================
# watchlist_close_track_flag_events (append-only audit)
# ============================================================================


def test_insert_flag_event_roundtrips_through_sql(
    conn: sqlite3.Connection,
) -> None:
    """insert_flag_event persists; SELECT post-INSERT returns matching values."""
    with conn:
        flag_id = repo.insert_flag(conn, _make_flag(ticker="PTEN"))
        event_id = repo.insert_flag_event(
            conn, _make_event(flag_id, event_type="set", surface="cli"),
        )
    row = conn.execute(
        "SELECT flag_id, event_type, surface "
        "FROM watchlist_close_track_flag_events WHERE id = ?",
        (event_id,),
    ).fetchone()
    assert row == (flag_id, "set", "cli")


def test_get_flag_event_by_id_returns_inserted_row(
    conn: sqlite3.Connection,
) -> None:
    """get_flag_event_by_id reconstructs the dataclass; None on missing."""
    with conn:
        flag_id = repo.insert_flag(conn, _make_flag(ticker="PTEN"))
        ev_id = repo.insert_flag_event(
            conn,
            _make_event(flag_id, reason_text="set via PTEN at-breakout dialog"),
        )

    fetched = repo.get_flag_event_by_id(conn, ev_id)
    assert fetched is not None
    assert fetched.flag_id == flag_id
    assert fetched.event_type == "set"
    assert fetched.surface == "web"
    assert fetched.reason_text == "set via PTEN at-breakout dialog"

    assert repo.get_flag_event_by_id(conn, 999_999) is None


def test_list_flag_events_paginates_and_filters(
    conn: sqlite3.Connection,
) -> None:
    """list_flag_events + flag_id + event_type filters + chronological order."""
    with conn:
        flag_id = repo.insert_flag(conn, _make_flag(ticker="PTEN"))
        repo.insert_flag_event(
            conn,
            _make_event(
                flag_id, event_type="set",
                event_at="2026-05-19T10:00:00.000",
            ),
        )
        repo.insert_flag_event(
            conn,
            _make_event(
                flag_id, event_type="clear",
                event_at="2026-05-20T10:00:00.000",
            ),
        )

    all_events = repo.list_flag_events(conn, flag_id=flag_id)
    assert len(all_events) == 2
    # Chronological order (event_at ASC).
    assert all_events[0].event_type == "set"
    assert all_events[1].event_type == "clear"

    set_events = repo.list_flag_events(conn, event_type="set")
    assert len(set_events) == 1


def test_repo_does_not_commit_within_function(
    conn: sqlite3.Connection,
) -> None:
    """Caller-tx contract on BOTH flag + event repo functions."""
    flag = _make_flag(ticker="ROLLED_BACK")
    conn.execute("BEGIN")
    flag_id = repo.insert_flag(conn, flag)
    repo.insert_flag_event(conn, _make_event(flag_id, event_type="set"))
    conn.rollback()

    assert repo.list_flags(conn, ticker="ROLLED_BACK") == []
    assert repo.list_flag_events(conn) == []
