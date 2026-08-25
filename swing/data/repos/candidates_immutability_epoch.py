"""THE ONE READER of the ``candidates`` immutability epoch (22-A, migration 0037).

CHARC's ruling, lifted verbatim into the design: *rows whose fire predates the
epoch do not admit structurally; rows at or after it do.  ONE reader, no date
arithmetic scattered through call sites* -- the same single-authority shape as
``cohort_intent``.  This module is that reader, and it is ALSO the only site
that performs the ``sqlite_master`` barrier-integrity query, so no call site
writes its own trigger-existence check.

**THE COMPARISON IS STRICTLY GREATER THAN** (inherited finding 22A-R9-02).  A
candidate whose id EQUALS ``max_candidate_id_at_barrier`` already existed when
the barrier was installed, so it is PRE-barrier.  ``>=`` would stamp it
``live_at_acceptance`` and mint a false structural-proof label for the one row
the boundary is named after.  The minting trigger's ``CASE`` in 0037 is this
rule's SQL twin, and a test runs BOTH spellings over the same fixtures --
asserting the EXPECTED TIER at below / equal / above, not merely that the two
agree, because two identically-wrong implementations agree.

**A NAME CHECK IS NOT AN INTEGRITY CHECK** (review 22A-R9-01, CHARC's ruled
repair).  ``SELECT COUNT(*) FROM sqlite_master WHERE name IN (...)`` checks
NAMES: dropping the real barriers and re-creating same-name NO-OP triggers
returns the same count while ``candidates`` is fully mutable, and rung 9 would
then stamp a mutable candidate structurally proven.  So the reader compares the
trigger BODY against a VERBATIM PINNED COPY -- the T1b pattern this repo
already runs for schwabdev's private DDL
(``swing/integrations/schwab/auth.py``), with ONE difference that matters:
T1b's comparison lives in a TEST and this one lives in the READER, because the
property is needed at every admission rather than once at CI.

**NORMALIZATION IS WHITESPACE ONLY, AND THAT BOUND IS THE RULING'S.**  Byte
comparison after whitespace normalization; NO semantic-equivalence judgments.
A comparator that decides two different bodies "mean the same thing" is a NEW
FREE DIMENSION, and a free dimension doing silent work is the defect class this
arc spent nine review rounds on.  A body differing only in whitespace is the
same barrier; a body differing any other way is NOT this barrier, and the
reader does not get to have an opinion about it.
"""
from __future__ import annotations

import re
import sqlite3

from swing.trades.latched_origin import (
    FREEZE_TIER_LIVE_AT_ACCEPTANCE,
    FREEZE_TIER_PRE_BARRIER,
)

# ---------------------------------------------------------------------------
# THE PINNED CANONICAL DDL -- byte-for-byte as migration 0037 writes it, minus
# the trailing semicolon SQLite strips when it stores the text.
#
# ALL THREE BARRIER TRIGGERS ARE PINNED, and the third one is why this comment
# exists.  CHARC's requirement was written when the barrier was
# UPDATE + DELETE; his own later generalisation -- that any DELETE-trigger
# barrier in this codebase is fail-open to REPLACE -- added
# ``trg_candidates_no_replace``, and it is the trigger that closes the MEASURED
# bypass (INSERT OR REPLACE moved the id, rewrote pivot/stop and cascade-wiped
# candidate_criteria with both other triggers present and unfired).  A body
# check that omitted it would certify a barrier that can be walked around, so
# "the barrier triggers" is read as the barrier AS IT NOW STANDS.  That is a
# strengthening in the fail-CLOSED direction and it is declared rather than
# absorbed.
# ---------------------------------------------------------------------------
_CANDIDATES_BARRIER_DDL: dict[str, str] = {
    "trg_candidates_no_update": (
        "CREATE TRIGGER trg_candidates_no_update BEFORE UPDATE ON candidates\n"
        "BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_no_update: "
        "candidates rows are IMMUTABLE from migration 0037. A re-evaluation "
        "APPENDS a new row; it never edits an existing one. To change a fire''s "
        "recorded values you must add an evaluation run. To retire the barrier "
        "see the reversibility header of 0037_latch_order_mandate_links.sql.'); "
        "END"
    ),
    "trg_candidates_no_delete": (
        "CREATE TRIGGER trg_candidates_no_delete BEFORE DELETE ON candidates\n"
        "BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_no_delete: "
        "candidates rows are PERMANENT from migration 0037. The latch identity "
        "space and every provenance citation address rows by a REUSABLE rowid, "
        "so a delete would silently repoint them. Pruning is a migration-level "
        "operation -- see the reversibility header of "
        "0037_latch_order_mandate_links.sql.'); END"
    ),
    "trg_candidates_no_replace": (
        "CREATE TRIGGER trg_candidates_no_replace BEFORE INSERT ON candidates\n"
        "WHEN EXISTS (SELECT 1 FROM candidates\n"
        "              WHERE (evaluation_run_id = NEW.evaluation_run_id AND "
        "ticker = NEW.ticker)\n"
        "                 OR (NEW.id IS NOT NULL AND id = NEW.id))\n"
        "BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_no_replace: "
        "candidates rows are PERMANENT from migration 0037. A conflicting "
        "INSERT (INSERT OR REPLACE / REPLACE / INSERT OR IGNORE) would DELETE "
        "the existing row, bypassing trg_candidates_no_delete, reusing its id "
        "and cascade-wiping candidate_criteria. A re-evaluation APPENDS a new "
        "row under a new evaluation_run_id. To retire the barrier see the "
        "reversibility header of 0037_latch_order_mandate_links.sql.'); END"
    ),
}

BARRIER_TRIGGER_NAMES: tuple[str, ...] = tuple(_CANDIDATES_BARRIER_DDL)

_WHITESPACE = re.compile(r"\s+")


def normalize_trigger_sql(sql: str) -> str:
    """Collapse whitespace runs to one space and strip the ends.  NOTHING ELSE.

    It does NOT lower-case, re-order, parse SQL, or decide that two different
    bodies are equivalent.
    """
    return _WHITESPACE.sub(" ", sql).strip()


def barrier_installed(conn: sqlite3.Connection) -> bool:
    """True iff EVERY barrier trigger is present, on ``candidates``, verbatim.

    The claim rung 9 makes is about THIS admission, NOW -- which is why the
    check lives here rather than in a CI-time guard.  A CI guard proves the
    barrier was canonical when CI ran; that is a different property and it is
    not the load-bearing one.
    """
    rows = {
        name: (tbl_name, sql)
        for name, tbl_name, sql in conn.execute(
            "SELECT name, tbl_name, sql FROM sqlite_master "
            "WHERE type = 'trigger' AND name IN "
            f"({', '.join('?' * len(BARRIER_TRIGGER_NAMES))})",
            BARRIER_TRIGGER_NAMES,
        )
    }
    for name, pinned in _CANDIDATES_BARRIER_DDL.items():
        found = rows.get(name)
        if found is None:
            return False
        tbl_name, sql = found
        if tbl_name != "candidates":
            return False
        if sql is None or normalize_trigger_sql(sql) != normalize_trigger_sql(pinned):
            return False
    return True


def epoch_boundary(conn: sqlite3.Connection) -> int | None:
    """``max_candidate_id_at_barrier``, or ``None`` if the epoch is absent.

    Absent means a pre-0037 database, where NOTHING is post-barrier.
    """
    present = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' "
        "AND name = 'candidates_immutability_epoch'"
    ).fetchone()
    if present is None:
        # A PRE-0037 database. The table's ABSENCE is the honest answer -- not
        # an error to swallow and not a boundary to invent -- and it degrades
        # in the fail-CLOSED direction: with no boundary, nothing is
        # post-barrier and every fire reads pre_barrier_reconstructed.
        return None
    row = conn.execute(
        "SELECT max_candidate_id_at_barrier FROM candidates_immutability_epoch "
        "WHERE epoch_id = 1"
    ).fetchone()
    return None if row is None else int(row[0])


def freeze_tier_for_candidate(
    conn: sqlite3.Connection, candidate_id: int,
) -> tuple[str, bool]:
    """``(tier, barrier_installed)`` for one fire.  THE only epoch reader.

    Returning the pair rather than the tier alone is what keeps the existence
    check in ONE place: a caller cannot obtain a tier without also obtaining the
    verdict on whether the guarantee behind it is still standing.
    """
    boundary = epoch_boundary(conn)
    if boundary is None:
        tier = FREEZE_TIER_PRE_BARRIER
    elif candidate_id > boundary:
        tier = FREEZE_TIER_LIVE_AT_ACCEPTANCE
    else:
        tier = FREEZE_TIER_PRE_BARRIER
    return tier, barrier_installed(conn)
