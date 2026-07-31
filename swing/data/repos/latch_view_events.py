"""latch_view_events repository (migration 0032; RE-KEYED by 0033, Arc 21-B).

Caller-controlled tx discipline -- these functions issue NO BEGIN/COMMIT/
ROLLBACK; the route owns `with conn:`.

SELECT-then-UPDATE-or-INSERT ONLY. NEVER `INSERT OR REPLACE` (that is DELETE +
INSERT: it would issue a new PK and rewrite the immutable first-view facts).

THE NATURAL KEY MOVED WITH THE CONSTRAINT (21-B). 0033 re-keys the table's
UNIQUE onto `(candidate_id, view_session_date, surface)`, and a widened UNIQUE
is COSMETIC if the repo still looks up on the old triple: the second surface's
`record_view` would find the panel's row and UPDATE it, so two surfaces would
silently share one row and one `view_count`. So `surface` is part of the natural
key EVERYWHERE here, and it is a REQUIRED kwarg with NO default -- a default
would re-create the bug the first time a caller forgets it (the default-arg
filter gotcha).
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from swing.data.models import LatchViewEvent
from swing.latches.identity import LatchIdentity

_COLS = (
    "view_event_id, candidate_id, evaluation_run_id, ticker, detection_date, "
    "pipeline_run_id, surface, view_session_date, first_viewed_ts, "
    "last_viewed_ts, view_count, latch_state_at_first_view, "
    "latch_state_at_last_view, actionable_at_first_view, "
    "actionable_at_last_view, actionable_ever_viewed"
)


def _row_to_model(row: tuple) -> LatchViewEvent:
    return LatchViewEvent(
        view_event_id=row[0], candidate_id=row[1], evaluation_run_id=row[2],
        ticker=row[3], detection_date=row[4], pipeline_run_id=row[5],
        surface=row[6], view_session_date=row[7], first_viewed_ts=row[8],
        last_viewed_ts=row[9], view_count=row[10],
        latch_state_at_first_view=row[11], latch_state_at_last_view=row[12],
        actionable_at_first_view=row[13], actionable_at_last_view=row[14],
        actionable_ever_viewed=row[15],
    )


def _surface_clause(surfaces: Iterable[str] | None) -> tuple[str, tuple]:
    """Build an optional `surface IN (...)` leg.

    `None` means ALL surfaces (a RAW read). Every CLASSIFICATION caller passes
    `surfaces=ACTIONABLE_VIEW_SURFACES` explicitly, so no reader silently
    inherits a set it did not choose. sqlite3 cannot bind a list to one
    placeholder, so the `?` expansion is built here; an EMPTY iterable
    short-circuits (empty `IN ()` is invalid SQL) to a never-true predicate.
    """
    if surfaces is None:
        return "", ()
    vals = tuple(surfaces)
    if not vals:
        return " AND 0", ()
    return f" AND surface IN ({','.join('?' * len(vals))})", vals


def get_view(
    conn: sqlite3.Connection, *, candidate_id: int, view_session_date: str,
    surface: str,
) -> LatchViewEvent | None:
    """Read the ONE row for (latch, session, surface) -- the 0033 bridge key."""
    row = conn.execute(
        f"SELECT {_COLS} FROM latch_view_events "
        "WHERE candidate_id = ? AND view_session_date = ? AND surface = ?",
        (candidate_id, view_session_date, surface),
    ).fetchone()
    return None if row is None else _row_to_model(row)


def list_views_for_session(
    conn: sqlite3.Connection, *, view_session_date: str,
    surfaces: Iterable[str] | None = None,
) -> list[LatchViewEvent]:
    clause, params = _surface_clause(surfaces)
    rows = conn.execute(
        f"SELECT {_COLS} FROM latch_view_events WHERE view_session_date = ?"
        f"{clause} ORDER BY ticker, evaluation_run_id, surface",
        (view_session_date, *params),
    ).fetchall()
    return [_row_to_model(r) for r in rows]


def list_views_for_latch(
    conn: sqlite3.Connection, *, candidate_id: int,
    surfaces: Iterable[str] | None = None,
) -> list[LatchViewEvent]:
    clause, params = _surface_clause(surfaces)
    rows = conn.execute(
        f"SELECT {_COLS} FROM latch_view_events WHERE candidate_id = ?"
        f"{clause} ORDER BY view_session_date, surface",
        (candidate_id, *params),
    ).fetchall()
    return [_row_to_model(r) for r in rows]


def record_view(
    conn: sqlite3.Connection, *, identity: LatchIdentity, view_session_date: str,
    viewed_ts: str, latch_state: str, surface: str, actionable: int,
) -> int:
    """Record a view of `identity`'s latch on `view_session_date` / `surface`.

    First view of the (session, surface) INSERTs (view_count=1) with ALL THREE
    actionability columns taking the passed value. Subsequent views UPDATE IN
    PLACE:

      view_count               += 1
      last_viewed_ts            advances
      latch_state_at_last_view  advances
      actionable_at_first_view  NEVER rewritten
      actionable_at_last_view   OVERWRITTEN with the new value (may FALL 1 -> 0;
                                it describes the LATEST view)
      actionable_ever_viewed    MAX(existing, new) -- monotonic 0 -> 1, never
                                back; this is the column CLASSIFICATION reads

    `first_viewed_ts` + `latch_state_at_first_view` are NEVER rewritten.
    Returns the (stable) view_event_id.
    """
    if actionable not in (0, 1):
        raise ValueError(f"actionable must be 0 or 1; got {actionable!r}")

    def _merge(existing) -> int:
        # THE LAST-VIEW FIELDS ADVANCE ONLY ON A NEWER TIMESTAMP; THE MONOTONIC
        # `ever` COLUMN MERGES UNCONDITIONALLY (Codex exec R7 MAJOR).
        #
        # Two requests can complete OUT OF TIMESTAMP ORDER, and the schema
        # enforces `last_viewed_ts >= first_viewed_ts`. So an EARLIER-stamped
        # render arriving second would push `last_viewed_ts` BACKWARDS, the CHECK
        # would abort the UPDATE, the route would 409 -- and if that loser was
        # the ACTIONABLE render, `actionable_ever_viewed` would stay 0 forever
        # and a potential `discipline_lapse` would be recorded as
        # `never_actionable`. The flattering direction, reached through the very
        # recovery path added to close the flattering direction.
        #
        # `actionable_ever_viewed` is MONOTONIC and carries no ordering claim, so
        # it merges either way: it says an actionable render HAPPENED, not when.
        # `view_count` likewise counts views rather than ordering them.
        #
        # THE `newer` TEST LIVES IN SQL, EVALUATED AGAINST THE ROW BEING UPDATED
        # (RD + CHARC, 2026-07-30 -- the documented CLAUDE.md SELECT-then-INSERT
        # family). Deciding it in Python from `existing` compares against a row
        # read EARLIER: another writer can advance `last_viewed_ts` in between,
        # and the stale comparison then pushes the last-view fields BACKWARDS
        # onto an older render. The measurement stake is not cosmetic -- a lost
        # or duplicated view row moves a classification between LAPSE and AWAY.
        #
        # SQLite evaluates EVERY `SET` expression against the ORIGINAL row, so
        # all three `CASE`s see the same pre-update `last_viewed_ts` and cannot
        # disagree with each other about which render won.
        conn.execute(
            "UPDATE latch_view_events SET "
            "last_viewed_ts = "
            "    CASE WHEN ? >= last_viewed_ts THEN ? ELSE last_viewed_ts END, "
            "latch_state_at_last_view = "
            "    CASE WHEN ? >= last_viewed_ts THEN ? "
            "         ELSE latch_state_at_last_view END, "
            "actionable_at_last_view = "
            "    CASE WHEN ? >= last_viewed_ts THEN ? "
            "         ELSE actionable_at_last_view END, "
            "view_count = view_count + 1, "
            "actionable_ever_viewed = MAX(actionable_ever_viewed, ?) "
            "WHERE view_event_id = ?",
            (viewed_ts, viewed_ts, viewed_ts, latch_state, viewed_ts,
             actionable, actionable, existing.view_event_id))
        return int(existing.view_event_id)

    existing = get_view(
        conn, candidate_id=identity.candidate_id,
        view_session_date=view_session_date, surface=surface)
    if existing is not None:
        return _merge(existing)
    try:
        cur = conn.execute(
            "INSERT INTO latch_view_events (candidate_id, evaluation_run_id, "
            "ticker, detection_date, pipeline_run_id, surface, "
            "view_session_date, first_viewed_ts, last_viewed_ts, view_count, "
            "latch_state_at_first_view, latch_state_at_last_view, "
            "actionable_at_first_view, actionable_at_last_view, "
            "actionable_ever_viewed) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)",
            (identity.candidate_id, identity.evaluation_run_id, identity.ticker,
             identity.detection_date, identity.pipeline_run_id, surface,
             view_session_date, viewed_ts, viewed_ts, latch_state, latch_state,
             actionable, actionable, actionable))
    except sqlite3.IntegrityError:
        # THE LOST INSERT RACE (Codex exec R5 MAJOR 2). Two concurrent FIRST
        # beacons both observe no row; the loser hits the UNIQUE constraint. Left
        # to propagate it becomes a 409 at the route and the loser's render is
        # NEVER MERGED -- so when a WITHHELD render wins and an ACTIONABLE render
        # loses, `actionable_ever_viewed` stays 0 permanently and a potential
        # `discipline_lapse` is recorded as `never_actionable`. That is the
        # flattering direction, which is the one direction this ledger may not
        # fail in.
        #
        # The loser therefore takes the UPDATE path it WOULD have taken had it
        # seen the row: `actionable_ever_viewed` still advances monotonically and
        # the immutable first-view facts remain the winner's. A statement-level
        # constraint violation rolls back only that STATEMENT, so the caller's
        # transaction is intact and the re-read is valid.
        #
        # STILL NOT `INSERT OR REPLACE`: that is DELETE + INSERT -- a new PK and
        # a rewrite of the immutable first-view facts, which is the thing this
        # module exists to refuse.
        existing = get_view(
            conn, candidate_id=identity.candidate_id,
            view_session_date=view_session_date, surface=surface)
        if existing is None:
            raise
        return _merge(existing)
    return int(cur.lastrowid)
