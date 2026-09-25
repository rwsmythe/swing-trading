"""22-I test seam: drop named guards on a TEST DB, restore them on exit.

AL-10 (plan section 5, amended 2026-09-25 by CHARC's ruling to these FOUR
kinds; this docstring is the source of the list and AL-10 restates it): a
trigger cannot be bypassed by a raw INSERT the way a Python write-barrier can
(the 18-B.1 technique). Every call site carries its reason, and the kinds are:

  1. tests that plant HISTORICAL corruption to test DETECTION of a state the
     schema now forbids (a moved / deleted / rewritten row);
  2. CLAUSE PINS a 0041 guard makes unreachable: the a17 exemptions whose
     parent delete a 0041 ``no_delete`` refuses (DEAD-BY-PARENT-GUARD,
     AL-9); the FK ON DELETE actions earlier migrations still declare (the
     FK-pin tests, T16 rule (d)); and an older trigger's clause a newer 0041
     trigger pre-empts (test_migration_0032's identity trigger);
  3. test DISPOSAL of rows a production service wrote, between iterations
     (T16 rule (d), with reason);
  4. fixture construction over rows WRITTEN BY A MIGRATION that are held by
     BOTH a ``no_delete`` and an immutable/``no_update`` guard, which no raw
     INSERT can re-plant (T10's ``rebase_status_history_recorded_at``); it
     reproduces the live DB's shape. BOUNDED: a state a raw INSERT can plant
     uses T16 rule (a), never this seam.

A fifth kind is a REPORTED deviation, never a docstring edit alone.

A name absent from the DB is SKIPPED, so one test body runs at v40 (where the
0041 guards do not exist) and at v41. The triggers are re-created from their
own stored ``sqlite_master.sql`` text, byte-for-byte. Never call this on a
non-test database.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def guards_dropped(conn: sqlite3.Connection, *names: str) -> Iterator[list[str]]:
    """Drop each named trigger present in ``conn``'s schema; yield the names
    actually dropped; re-create them from their stored text on exit."""
    stored: list[tuple[str, str]] = []
    for name in names:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
            (name,)).fetchone()
        if row is not None:
            stored.append((name, row[0]))
    for name, _sql in stored:
        conn.execute(f"DROP TRIGGER {name}")
    try:
        yield [n for n, _ in stored]
    finally:
        for _name, sql in stored:
            conn.execute(sql)
