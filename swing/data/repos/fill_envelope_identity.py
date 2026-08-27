"""The STORED canonical reading of a fill's Schwab envelope (22-A, round 11).

THE RULING THIS MODULE SERVES (CHARC 2026-08-26, adopting RD's sentence
verbatim):

    SQL VERIFIES A FACT; IT MUST NEVER RE-DERIVE A JUDGMENT ACROSS AN ENGINE
    BOUNDARY -- the twin mirrors the AUTHORITY by consuming its OUTPUT, not by
    reimplementing its reasoning.

So there is exactly ONE derivation of "what does this envelope say", it lives in
``swing/trades/latched_origin.canonical_envelope_identity``, and this module is
the only thing that writes its answer down.  Migration 0037 ships the table
EMPTY on purpose: a SQL backfill would be the same cross-engine re-derivation
moved to migration time.

WHY THE REPO LAYER IMPORTS THE SERVICE READER, and why the import is deferred.
The canonicaliser is a pure string function that belongs beside the ladder that
consumes it, and ``swing/data/repos`` already reaches into ``swing/trades`` this
way (``review_log.py``, ``trades.py``).  The import is function-local so that a
fill with NO envelope pays nothing at all -- LOCK clause (d)'s subject.
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

TABLE = "fill_envelope_identity"


class EnvelopeIdentityDriftError(RuntimeError):
    """A stored reading disagrees with what the authority reads TODAY.

    The row is append-only and bound to its document by ``envelope_raw``, so
    the only way this can fire is a canonicaliser change or a forged row.  It
    is LOUD rather than silently re-derived: silently preferring either answer
    would re-create the two-readings-of-one-document class the stored reading
    exists to delete.
    """


def table_exists(conn: sqlite3.Connection) -> bool:
    """Pre-0037 fixtures run at earlier target versions and have no table."""
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (TABLE,),
    ).fetchone() is not None


def stored_identity(
    conn: sqlite3.Connection, fill_id: int, envelope_raw: str,
) -> tuple[str, str | None, str | None] | None:
    """``(state, broker_order_id, instrument_symbol)`` for THIS document."""
    return conn.execute(
        "SELECT envelope_state, broker_order_id, instrument_symbol "
        f"  FROM {TABLE} WHERE fill_id = ? AND envelope_raw = ?",
        (int(fill_id), envelope_raw),
    ).fetchone()


def record_identity(
    conn: sqlite3.Connection, *, fill_id: int, envelope_raw: str,
) -> tuple[str, str | None, str | None]:
    """Derive THIS document's reading once and append it.  Idempotent.

    SELECT-then-INSERT, never ``INSERT OR REPLACE``: a REPLACE would DELETE the
    existing reading without firing the append-only DELETE trigger (measured on
    sqlite 3.50.4 at the default ``recursive_triggers=OFF``) and substitute a
    different identity for the same document.
    """
    from swing.trades.latched_origin import (
        ENVELOPE_CANONICALIZER_VERSION,
        canonical_envelope_identity,
    )

    identity = canonical_envelope_identity(envelope_raw)
    current = (identity.state, identity.broker_order_id,
               identity.instrument_symbol)
    existing = stored_identity(conn, fill_id, envelope_raw)
    if existing is not None:
        if tuple(existing) != current:
            raise EnvelopeIdentityDriftError(
                f"fill {fill_id}'s stored envelope reading {tuple(existing)!r} "
                f"disagrees with what the canonicaliser "
                f"({ENVELOPE_CANONICALIZER_VERSION}) reads out of the SAME "
                f"document today ({current!r}). The reading is append-only and "
                "bound to its document, so this is a canonicaliser change or a "
                "forged row; it is refused rather than silently re-derived."
            )
        return current
    conn.execute(
        f"INSERT INTO {TABLE} (fill_id, envelope_raw, envelope_state, "
        " broker_order_id, instrument_symbol, canonicalizer_version, "
        " recorded_ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (int(fill_id), envelope_raw, identity.state, identity.broker_order_id,
         identity.instrument_symbol, ENVELOPE_CANONICALIZER_VERSION,
         datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    return current


def ensure_entry_fill_identities(conn: sqlite3.Connection) -> int:
    """Read EVERY envelope-bearing ENTRY fill, appending or RE-VERIFYING.

    THIS IS THE 'BACKFILL', AND IT IS PERFORMED BY THE AUTHORITY.  The scans
    that consume the stored reading (rung 6 and rung 8's consumption check, and
    the citation trigger's own twin) can only see documents the service has
    read, so a population that has never been read is a population the scan
    would silently treat as empty.  Called from inside the ladder's write
    reservation, so the set it establishes cannot move under it.

    IT RE-VERIFIES, IT DOES NOT ONLY POPULATE (Codex 22A-R11-03, PROVEN BY
    EXECUTION).  This selected `fei.identity_id IS NULL`, so an EXISTING
    reading never passed through ``record_identity``'s drift check -- and the
    rows it excluded are exactly the population the consumption scans consult:
    OTHER trades' entry fills.  ``ENVELOPE_CANONICALIZER_VERSION``'s own
    comment claims a reading made under an older grammar is "DISTINGUISHABLE
    rather than silently trusted"; the pass that walks that population was the
    one place the claim was never tested.

    MEASURED, one dimension apart on the same world: a reading written by the
    PRODUCTION writer under an older grammar -- `(canonical, None)` -- let a
    SECOND trade be admitted from a mandate the first trade's entry fill
    already consumes, where the current-grammar reading refuses it
    `mandate_already_consumed`.  Only the CODE was advanced, which is what a
    canonicaliser bump IS; the data was never forged.

    THE DISCRIMINATOR IS THE ANSWER, NEVER THE VERSION LABEL.  An older reading
    that says the SAME thing is left exactly as it is -- filtering on the
    version string would fail every historical reading closed on the day the
    constant moves, a refusal manufactured by the guard.  A disagreement RAISES
    (append-only: the row cannot be corrected in place), and every caller on
    the ladder contains that raise into a fail-CLOSED refusal.

    Returns the number of readings APPENDED; re-verified rows are not counted,
    so an idempotent second call still returns 0.
    """
    if not table_exists(conn):
        return 0
    rows = conn.execute(
        "SELECT f.fill_id, f.schwab_source_value_json, fei.identity_id "
        "  FROM fills f "
        f" LEFT JOIN {TABLE} fei ON fei.fill_id = f.fill_id "
        "        AND fei.envelope_raw = f.schwab_source_value_json "
        " WHERE f.action = 'entry' AND f.schwab_source_value_json IS NOT NULL "
        " ORDER BY f.fill_id",
    ).fetchall()
    appended = 0
    for fill_id, raw, existing_id in rows:
        record_identity(conn, fill_id=int(fill_id), envelope_raw=raw)
        if existing_id is None:
            appended += 1
    return appended


def consuming_entry_fills(
    conn: sqlite3.Connection, broker_order_id: str, *, exclude_trade_id: int,
) -> list[int]:
    """Trade ids whose ENTRY fill's STORED reading names this broker order.

    ONE DOMAIN, ONE READING.  This replaced a union of SQLite's ``json_extract``
    and Python's parse, whose "SQL arm" fetched SQLite's value into Python and
    compared it there -- so the arm meant to preserve TEXT affinity was SQL's
    value judged by Python's rules (Codex 22A-R10-03, reproduced).  Both sides
    of the comparison below are TEXT columns, so equality is plain and neither
    engine has an opinion to disagree about.
    """
    if not table_exists(conn):
        return []
    return [
        int(r[0]) for r in conn.execute(
            "SELECT DISTINCT f.trade_id FROM fills f "
            f" JOIN {TABLE} fei ON fei.fill_id = f.fill_id "
            "                 AND fei.envelope_raw = f.schwab_source_value_json "
            " WHERE f.action = 'entry' AND fei.envelope_state = 'canonical' "
            "   AND fei.broker_order_id = ? AND f.trade_id IS NOT NULL "
            "   AND f.trade_id <> ? ORDER BY f.trade_id",
            (str(broker_order_id), int(exclude_trade_id)),
        ).fetchall()
    ]


def unreadable_entry_fills(
    conn: sqlite3.Connection, *, exclude_trade_id: int,
) -> list[int]:
    """ENTRY fills carrying an envelope the authority REFUSED to read.

    A refused document names no order the scan above can see, so a consumption
    that lives inside one is invisible to it.  That is ignorance, not absence,
    and the ladder's own three-valued rule says ignorance fails CLOSED -- the
    same shape rung 7 already uses for evidence the split handler destroyed.
    """
    if not table_exists(conn):
        return []
    return [
        int(r[0]) for r in conn.execute(
            "SELECT f.fill_id FROM fills f "
            f" JOIN {TABLE} fei ON fei.fill_id = f.fill_id "
            "                 AND fei.envelope_raw = f.schwab_source_value_json "
            " WHERE f.action = 'entry' AND fei.envelope_state = 'refused' "
            "   AND (f.trade_id IS NULL OR f.trade_id <> ?) ORDER BY f.fill_id",
            (int(exclude_trade_id),),
        ).fetchall()
    ]
