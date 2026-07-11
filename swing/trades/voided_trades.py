"""20-A Task B-2 — the central voided-trade exclusion predicate.

A *voided* trade is a phantom / test trade (e.g. the SATL trade-11 journal-
only round trip that NEVER executed at the broker; D25 forensic 2026-07-10).
Per RD's semantic + the D19 doctrine it is NEVER raw-deleted: it is annotated
with an audited ``trade_events`` ``note`` row carrying ``payload_json`` with
``"voided": true`` (an operator/RD-run live-DB action, post-merge), and every
COHORT / STAT / EQUITY reader excludes it via this single predicate — while
the AUDIT / trade-detail surfaces keep displaying it (audit-visible).

This module is the SINGLE SOURCE OF TRUTH for "which trades are void"; no
CHECK-enum widening / new column is involved (SCHEMA-STOP honored).
"""
from __future__ import annotations

import sqlite3


def voided_trade_ids(conn: sqlite3.Connection) -> frozenset[int]:
    """Return the set of trade ids annotated void via a ``trade_events`` note.

    A trade is void when it has at least one ``trade_events`` row whose
    ``payload_json`` carries ``"voided": true`` (SQLite ``json_extract`` maps
    JSON ``true`` -> the integer ``1``). Pure read; caller owns no tx.
    """
    rows = conn.execute(
        "SELECT DISTINCT trade_id FROM trade_events "
        "WHERE json_extract(payload_json, '$.voided') IS 1"
    ).fetchall()
    return frozenset(int(r[0]) for r in rows if r[0] is not None)
