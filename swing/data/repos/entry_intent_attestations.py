"""Repository for `entry_intent_attestations` (Arc 22-B, migration 0040).

The table's SCHEMA IS THE EVIDENCE RULE: append-only (update/delete/replace
barriers), and every admission predicate the assignment service checks has an
SQL twin trigger. This module is the ONLY `INSERT INTO entry_intent_attestations`
site under `swing/` besides migration 0040 (the repo-per-table precedent of
every evidence table -- CHARC's section-3 condition 1); its one caller is
`swing.trades.entry_intent_assignment.assign`, which owns the transaction.

No transaction management here: the caller's transaction (one BEGIN IMMEDIATE,
this row FIRST, then the `trades` UPDATE -- both or neither). The INSERT carries
no ON CONFLICT clause, so the conflict-scoped no-REPLACE barrier never meets a
DO-NOTHING belt (the REPLACE gotcha's third facet).
"""
from __future__ import annotations

import sqlite3

from swing.data.models import EntryIntentAttestation

_COLUMNS: tuple[str, ...] = (
    "attestation_id", "trade_id", "assigned_value", "admission_tier",
    "trade_entry_date", "entry_fill_id", "entry_fill_id_at_assignment",
    "entry_broker_order_id", "placement_session", "placement_session_source",
    "admitted_leg", "leg_evidence_json", "cited_latch_link_id",
    "cited_latch_terminal_rung", "cited_latch_terminal_session",
    "cited_latch_probe_json", "cited_fields_json", "cited_text_snapshot_json",
    "audit_trail_checked_at", "corrections_touching_cited_fields",
    "outcome_known_at", "reason", "applied_at", "applied_by",
)


def _row_to_attestation(row: tuple) -> EntryIntentAttestation:
    return EntryIntentAttestation(*row)


def insert_attestation(
    conn: sqlite3.Connection, attestation: EntryIntentAttestation,
) -> int:
    """INSERT one attestation row in the CALLER's transaction; return its id.

    ``attestation.attestation_id`` must be None (the engine assigns it).
    """
    if attestation.attestation_id is not None:
        raise ValueError("insert_attestation: attestation_id is assigned by the DB")
    cols = _COLUMNS[1:]
    values = tuple(getattr(attestation, c) for c in cols)
    cur = conn.execute(
        f"INSERT INTO entry_intent_attestations ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' * len(cols))})",
        values,
    )
    return int(cur.lastrowid)


def get_attestation(
    conn: sqlite3.Connection, trade_id: int,
) -> EntryIntentAttestation | None:
    """The attestation of ``trade_id`` (one per trade, UNIQUE), or None."""
    row = conn.execute(
        f"SELECT {', '.join(_COLUMNS)} FROM entry_intent_attestations "
        "WHERE trade_id = ?", (trade_id,)).fetchone()
    return None if row is None else _row_to_attestation(tuple(row))
