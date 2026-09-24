"""22-I test seam: drop named guards on a TEST DB, restore them on exit.

AL-10 (plan section 5): a trigger cannot be bypassed by a raw INSERT the way a
Python write-barrier can (the 18-B.1 technique), so exactly TWO kinds of test
use this seam, each with a one-line reason at the call site:

  1. tests that plant HISTORICAL corruption to test DETECTION of a state the
     schema now forbids (a moved / deleted / rewritten row);
  2. a17 CLAUSE PINS whose parent delete a 0041 ``no_delete`` refuses (the
     DEAD-BY-PARENT-GUARD exemptions, AL-9): the clause stays executable.

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
