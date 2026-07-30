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
            viewed_ts="2026-06-25T10:00:00", latch_state="armed",
            surface="latch_panel", actionable=1)
    row = get_view(conn, candidate_id=ident.candidate_id,
                   view_session_date="2026-06-25", surface="latch_panel")
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
                          viewed_ts="2026-06-25T10:00:00", latch_state="armed",
                          surface="latch_panel", actionable=1)
    with conn:
        rid2 = record_view(conn, identity=ident, view_session_date="2026-06-25",
                           viewed_ts="2026-06-25T15:30:00",
                           latch_state="order_resting",
                           surface="latch_panel", actionable=1)
    assert rid2 == rid, "PK must be preserved (no INSERT OR REPLACE)"
    row = get_view(conn, candidate_id=ident.candidate_id,
                   view_session_date="2026-06-25", surface="latch_panel")
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
                    viewed_ts="2026-06-25T10:00:00", latch_state="armed",
                    surface="latch_panel", actionable=1)
    with conn:
        record_view(conn, identity=ident, view_session_date="2026-06-26",
                    viewed_ts="2026-06-26T10:00:00", latch_state="armed",
                    surface="latch_panel", actionable=1)
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
                        viewed_ts=f"{session}T10:00:00", latch_state="armed",
                        surface="latch_panel", actionable=1)
    rows = list_views_for_latch(conn, candidate_id=ident.candidate_id)
    assert [r.view_session_date for r in rows] == ["2026-06-25", "2026-06-26"]


# ---------------------------------------------------------------------------
# Arc 21-B: `surface` + the THREE actionability columns.
# ---------------------------------------------------------------------------
def test_surface_and_actionable_are_REQUIRED_kwargs(conn_and_identity):
    """NO DEFAULT, deliberately. A default `surface` would re-create the bug the
    re-keyed UNIQUE fixes the first time a caller forgets it (the default-arg
    filter gotcha), and a default `actionable` would silently record a withheld
    render as a full 'he saw the mandate' view."""
    conn, ident = conn_and_identity
    with pytest.raises(TypeError):
        record_view(conn, identity=ident, view_session_date="2026-06-25",
                    viewed_ts="2026-06-25T10:00:00", latch_state="armed",
                    actionable=1)
    with pytest.raises(TypeError):
        record_view(conn, identity=ident, view_session_date="2026-06-25",
                    viewed_ts="2026-06-25T10:00:00", latch_state="armed",
                    surface="latch_panel")
    with pytest.raises(TypeError):
        get_view(conn, candidate_id=ident.candidate_id,
                 view_session_date="2026-06-25")


def test_an_offered_then_withheld_replay_moves_each_column_differently(
        conn_and_identity):
    """THE ORDERING IS THE DISCRIMINATOR.

    offered (actionable=1) THEN withheld (actionable=0), in ONE session:
        actionable_at_first_view  stays 1   (IMMUTABLE after insert)
        actionable_at_last_view   FALLS to 0 (it describes the LATEST view)
        actionable_ever_viewed    stays 1   (monotonic; what CLASSIFICATION reads)

    The REVERSE order passes under BOTH the correct rule AND the superseded
    "advance last with MAX()" rule, so a test written only that way proves
    nothing.
    """
    conn, ident = conn_and_identity
    with conn:
        rid = record_view(conn, identity=ident, view_session_date="2026-06-25",
                          viewed_ts="2026-06-25T09:00:00", latch_state="armed",
                          surface="latch_panel", actionable=1)
    with conn:
        rid2 = record_view(conn, identity=ident, view_session_date="2026-06-25",
                           viewed_ts="2026-06-25T18:00:00", latch_state="armed",
                           surface="latch_panel", actionable=0)
    assert rid2 == rid
    row = get_view(conn, candidate_id=ident.candidate_id,
                   view_session_date="2026-06-25", surface="latch_panel")
    assert row.actionable_at_first_view == 1
    assert row.actionable_at_last_view == 0
    assert row.actionable_ever_viewed == 1
    assert row.view_count == 2


def test_a_withheld_then_offered_replay_raises_ever_and_never_lowers_it(
        conn_and_identity):
    """The reverse order, pinning that `actionable_ever_viewed` rises 0 -> 1 and
    never falls."""
    conn, ident = conn_and_identity
    with conn:
        record_view(conn, identity=ident, view_session_date="2026-06-25",
                    viewed_ts="2026-06-25T09:00:00", latch_state="armed",
                    surface="latch_panel", actionable=0)
    with conn:
        record_view(conn, identity=ident, view_session_date="2026-06-25",
                    viewed_ts="2026-06-25T18:00:00", latch_state="armed",
                    surface="latch_panel", actionable=1)
    row = get_view(conn, candidate_id=ident.candidate_id,
                   view_session_date="2026-06-25", surface="latch_panel")
    assert row.actionable_at_first_view == 0
    assert row.actionable_at_last_view == 1
    assert row.actionable_ever_viewed == 1
    # ...and a THIRD withheld view still cannot lower it.
    with conn:
        record_view(conn, identity=ident, view_session_date="2026-06-25",
                    viewed_ts="2026-06-25T19:00:00", latch_state="armed",
                    surface="latch_panel", actionable=0)
    row = get_view(conn, candidate_id=ident.candidate_id,
                   view_session_date="2026-06-25", surface="latch_panel")
    assert row.actionable_ever_viewed == 1


def test_a_bad_actionable_value_is_rejected_before_it_reaches_sql(
        conn_and_identity):
    conn, ident = conn_and_identity
    with pytest.raises(ValueError, match="actionable"):
        record_view(conn, identity=ident, view_session_date="2026-06-25",
                    viewed_ts="2026-06-25T09:00:00", latch_state="armed",
                    surface="latch_panel", actionable=2)


def test_the_surfaces_filter_is_explicit_and_an_empty_set_matches_nothing(
        conn_and_identity):
    """Every CLASSIFICATION caller passes `surfaces=` EXPLICITLY, so no reader
    silently inherits a set it did not choose.

    Exercised through the PARAMETER over a VALID `latch_panel` row rather than by
    planting an invalid surface: `CHECK (surface IN ('latch_panel'))` plus the
    model validator make a second surface UNWRITABLE today, so a test planting a
    `dashboard` row could only pass by BYPASSING the very #11 mirror it exists to
    respect.
    """
    from swing.data.repos.latch_view_events import (
        list_views_for_latch,
        list_views_for_session,
    )
    conn, ident = conn_and_identity
    with conn:
        record_view(conn, identity=ident, view_session_date="2026-06-25",
                    viewed_ts="2026-06-25T09:00:00", latch_state="armed",
                    surface="latch_panel", actionable=1)
    assert len(list_views_for_latch(
        conn, candidate_id=ident.candidate_id,
        surfaces=frozenset({"latch_panel"}))) == 1
    assert list_views_for_latch(
        conn, candidate_id=ident.candidate_id, surfaces=frozenset()) == []
    assert len(list_views_for_session(
        conn, view_session_date="2026-06-25",
        surfaces=frozenset({"latch_panel"}))) == 1
    assert list_views_for_session(
        conn, view_session_date="2026-06-25", surfaces=frozenset()) == []
    # `None` means ALL surfaces -- a RAW read, chosen deliberately.
    assert len(list_views_for_latch(
        conn, candidate_id=ident.candidate_id, surfaces=None)) == 1


def test_actionable_view_surfaces_is_a_subset_of_the_writable_enum():
    """An uncounted-but-unwritable surface is a TYPO, not a design. The two sets
    are deliberately separate and deliberately EQUAL today: adding a surface to
    the CHECK enum is a SCHEMA decision, adding it to ACTIONABLE_VIEW_SURFACES is
    a MEASUREMENT decision and RD's."""
    from swing.latches.constants import (
        ACTIONABLE_VIEW_SURFACES,
        LATCH_VIEW_SURFACES,
    )
    assert ACTIONABLE_VIEW_SURFACES <= LATCH_VIEW_SURFACES
    assert ACTIONABLE_VIEW_SURFACES == LATCH_VIEW_SURFACES == {"latch_panel"}


def test_a_LOST_INSERT_RACE_merges_into_the_winner_rather_than_losing_the_claim(
        conn_and_identity, monkeypatch):
    """CODEX EXEC R5 MAJOR 2. `record_view` was SELECT-then-INSERT with no
    conflict recovery: two concurrent first beacons both observe no row, and the
    loser hits the UNIQUE constraint. The route turns that into a 409 and the
    loser's render is never merged -- so if a WITHHELD render wins and an
    ACTIONABLE render loses, `actionable_ever_viewed` stays 0 permanently and a
    potential `discipline_lapse` becomes `never_actionable`. It fails in the
    flattering direction.

    The loser must MERGE, which for this table means taking the UPDATE path it
    would have taken had it seen the row -- so `actionable_ever_viewed` still
    advances monotonically and the immutable first-view facts stay the winner's.

    THE RACE IS SIMULATED AT THE SEAM: `get_view` is monkeypatched to return
    None ONCE after the winner's row already exists, which is exactly the state
    the loser observes. A test that merely called `record_view` twice would take
    the ordinary UPDATE path and prove nothing.
    """
    from swing.data.repos import latch_view_events as repo

    conn, identity = conn_and_identity
    winner = repo.record_view(
        conn, identity=identity, view_session_date="2026-07-29",
        viewed_ts="2026-07-29T09:00:00", latch_state="armed",
        surface="latch_panel", actionable=0)

    real_get_view = repo.get_view
    calls = {"n": 0}

    def _blind_once(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return None          # the loser's stale read
        return real_get_view(*a, **k)

    monkeypatch.setattr(repo, "get_view", _blind_once)
    loser = repo.record_view(
        conn, identity=identity, view_session_date="2026-07-29",
        viewed_ts="2026-07-29T09:00:01", latch_state="armed",
        surface="latch_panel", actionable=1)

    assert loser == winner, "the loser must return the WINNER's row, not raise"
    row = real_get_view(conn, candidate_id=identity.candidate_id,
                        view_session_date="2026-07-29", surface="latch_panel")
    assert row.view_count == 2
    assert row.actionable_ever_viewed == 1, (
        "the loser's ACTIONABLE claim must survive; losing it converts a "
        "potential discipline_lapse into never_actionable")
    assert row.actionable_at_first_view == 0, "the winner's first view stands"
    assert row.actionable_at_last_view == 1


def test_an_OUT_OF_ORDER_loser_still_merges_its_actionable_claim(
        conn_and_identity, monkeypatch):
    """CODEX EXEC R7 MAJOR -- the flattering direction reached through the very
    recovery path added to close the flattering direction.

    Two requests can complete OUT OF TIMESTAMP ORDER, and the schema enforces
    `last_viewed_ts >= first_viewed_ts`. So an EARLIER-stamped render arriving
    second pushed `last_viewed_ts` BACKWARDS, the CHECK aborted the UPDATE, the
    route 409'd -- and when that loser was the ACTIONABLE render,
    `actionable_ever_viewed` stayed 0 forever and a potential `discipline_lapse`
    was recorded as `never_actionable`.

    `actionable_ever_viewed` carries NO ordering claim (it says an actionable
    render HAPPENED, not when), so it merges either way; only the LAST-VIEW
    fields are ordered and they advance only on a newer stamp.
    """
    from swing.data.repos import latch_view_events as repo

    conn, identity = conn_and_identity
    winner = repo.record_view(
        conn, identity=identity, view_session_date="2026-07-29",
        viewed_ts="2026-07-29T15:00:00", latch_state="armed",
        surface="latch_panel", actionable=0)

    real_get_view = repo.get_view
    calls = {"n": 0}

    def _blind_once(*a, **k):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_get_view(*a, **k)

    monkeypatch.setattr(repo, "get_view", _blind_once)
    # EARLIER than the winner's stamp -- the ordering the previous fix assumed
    # away.
    loser = repo.record_view(
        conn, identity=identity, view_session_date="2026-07-29",
        viewed_ts="2026-07-29T09:00:00", latch_state="armed",
        surface="latch_panel", actionable=1)

    assert loser == winner
    row = real_get_view(conn, candidate_id=identity.candidate_id,
                        view_session_date="2026-07-29", surface="latch_panel")
    assert row.actionable_ever_viewed == 1, (
        "losing this claim converts a potential discipline_lapse into "
        "never_actionable")
    assert row.last_viewed_ts == "2026-07-29T15:00:00", (
        "the last-view fields carry an ORDERING claim and never move backwards")
    assert row.first_viewed_ts == "2026-07-29T15:00:00"
    assert row.view_count == 2
