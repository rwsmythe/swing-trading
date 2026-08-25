"""Lift the 22-A ``candidates`` immutability barrier around a test mutation.

WHY THIS EXISTS.  Migration 0037 installs ``trg_candidates_no_update`` /
``trg_candidates_no_delete`` / ``trg_candidates_no_replace``, so ``candidates``
rows are structurally immutable from v37 onward.  That immutability IS the arc's
proof of RD's frozen-value gate and it is deliberate.  It also rejects the very
shape a whole class of PRE-EXISTING tests needs to plant: a candidate that MOVED
(the Demand-C drift reader's subject), a candidate carrying a junk value (the
structural-verdict degrade path), a DELETED candidate (the FK-action tests).

That is CLAUDE.md's *"adding a write-barrier breaks tests that seed invalid/edge
data THROUGH that function"* gotcha arriving at the SCHEMA layer rather than at a
repo function, so the 18-B.1 remedy -- plant the row by a path the barrier does
not see -- takes the only form available against a trigger: DROP it, mutate,
RE-CREATE it.  Each such test is testing DETECTION of a state the barrier now
prevents from arising, not the write path, exactly as the 18-B.1 monitor tests
plant non-finite OHLC by raw INSERT rather than through the barriered writer.

RE-CREATION IS NOT COSMETIC.  The 22-A admission reader compares each barrier
trigger's BODY against a verbatim pinned copy and refuses ``barrier_not_installed``
on any difference, so a helper that dropped and did not restore -- or restored an
approximation -- would silently disarm structural admission for every later
assertion sharing the connection.  The bodies are read back out of
``sqlite_master`` and replayed VERBATIM, so this helper can never drift from the
migration: it never spells a trigger body of its own.
"""
from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterator, Sequence

CANDIDATES_BARRIER_TRIGGERS: tuple[str, ...] = (
    "trg_candidates_no_update",
    "trg_candidates_no_delete",
    "trg_candidates_no_replace",
)


@contextlib.contextmanager
def candidates_barrier_lifted(
    conn: sqlite3.Connection,
    *,
    triggers: Sequence[str] = CANDIDATES_BARRIER_TRIGGERS,
) -> Iterator[None]:
    """Drop the named barrier triggers, run the body, restore them verbatim.

    A trigger absent from ``sqlite_master`` (a fixture built on a pre-0037
    schema) is simply not dropped and not restored -- the helper is a no-op
    there rather than an error, so a test can use it unconditionally.
    """
    placeholders = ",".join("?" * len(triggers))
    saved = conn.execute(
        f"SELECT name, sql FROM sqlite_master "
        f"WHERE type = 'trigger' AND name IN ({placeholders})",
        tuple(triggers),
    ).fetchall()
    for name, _sql in saved:
        conn.execute(f"DROP TRIGGER {name}")
    try:
        yield
    finally:
        for _name, sql in saved:
            conn.execute(sql)
