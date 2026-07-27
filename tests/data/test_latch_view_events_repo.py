"""latch_view_events repo - SELECT-then-UPDATE-or-INSERT, never INSERT OR REPLACE."""
from __future__ import annotations

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.latch_view_events import get_view, list_views_for_session, record_view
from swing.latches.identity import LatchIdentity


@pytest.fixture
def conn_and_identity(tmp_path):
    """A migrated DB with ONE real candidates row, plus the LatchIdentity that
    points at it (candidate_id is NOT NULL / ON DELETE RESTRICT)."""
    conn = ensure_schema(tmp_path / "t.db")
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(99, '2026-06-24T20:06:25', '2026-06-24', '2026-06-25', 1, 1, 0, 0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(99, 'VSTS', 'aplus', 13.49, 13.56, 11.62, 'universe')")
    ident = LatchIdentity(
        candidate_id=int(cur.lastrowid), evaluation_run_id=99, ticker="VSTS",
        detection_date="2026-06-25", pipeline_run_id=None)
    yield conn, ident
    conn.close()


def test_first_view_inserts_with_count_one(conn_and_identity):
    conn, ident = conn_and_identity
    with conn:
        rid = record_view(
            conn, identity=ident, view_session_date="2026-06-25",
            viewed_ts="2026-06-25T10:00:00", latch_state="armed")
    row = get_view(conn, evaluation_run_id=99, ticker="VSTS",
                   view_session_date="2026-06-25")
    assert row is not None and row.view_event_id == rid
    assert row.view_count == 1
    assert row.first_viewed_ts == row.last_viewed_ts == "2026-06-25T10:00:00"
    assert row.latch_state_at_first_view == "armed"
    assert row.candidate_id == ident.candidate_id


def test_second_view_same_session_updates_in_place_preserving_pk_and_first_ts(
        conn_and_identity):
    conn, ident = conn_and_identity
    with conn:
        rid = record_view(conn, identity=ident, view_session_date="2026-06-25",
                          viewed_ts="2026-06-25T10:00:00", latch_state="armed")
    with conn:
        rid2 = record_view(conn, identity=ident, view_session_date="2026-06-25",
                           viewed_ts="2026-06-25T15:30:00",
                           latch_state="order_resting")
    assert rid2 == rid, "PK must be preserved (no INSERT OR REPLACE)"
    row = get_view(conn, evaluation_run_id=99, ticker="VSTS",
                   view_session_date="2026-06-25")
    assert row.view_count == 2
    assert row.first_viewed_ts == "2026-06-25T10:00:00"     # IMMUTABLE
    assert row.last_viewed_ts == "2026-06-25T15:30:00"
    assert row.latch_state_at_first_view == "armed"          # IMMUTABLE
    assert row.latch_state_at_last_view == "order_resting"
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 1


def test_next_session_creates_a_second_row(conn_and_identity):
    conn, ident = conn_and_identity
    with conn:
        record_view(conn, identity=ident, view_session_date="2026-06-25",
                    viewed_ts="2026-06-25T10:00:00", latch_state="armed")
    with conn:
        record_view(conn, identity=ident, view_session_date="2026-06-26",
                    viewed_ts="2026-06-26T10:00:00", latch_state="armed")
    assert len(list_views_for_session(conn, view_session_date="2026-06-26")) == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 2


def test_list_views_for_latch_returns_the_session_history(conn_and_identity):
    """The panel's telemetry echo reads this; ordering by session must be
    stable so 'first viewed' is the earliest session, not an arbitrary row."""
    from swing.data.repos.latch_view_events import list_views_for_latch
    conn, ident = conn_and_identity
    for session in ("2026-06-26", "2026-06-25"):
        with conn:
            record_view(conn, identity=ident, view_session_date=session,
                        viewed_ts=f"{session}T10:00:00", latch_state="armed")
    rows = list_views_for_latch(conn, evaluation_run_id=99, ticker="VSTS")
    assert [r.view_session_date for r in rows] == ["2026-06-25", "2026-06-26"]
