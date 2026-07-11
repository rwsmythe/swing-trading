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

# The canonical void predicate as a SQL SUBQUERY (no parameter binding — the
# whole predicate is self-contained), for raw-SQL metric surfaces that do their
# own ``FROM trades`` and cannot route through the Python readers. Mirrors
# :func:`voided_trade_ids` EXACTLY (same json_valid guard) so the two cannot
# drift.
_VOIDED_TRADE_IDS_SUBQUERY = (
    "SELECT DISTINCT trade_id FROM trade_events "
    "WHERE payload_json IS NOT NULL AND json_valid(payload_json) "
    "AND json_extract(payload_json, '$.voided') IS 1"
)


def voided_exclusion_sql(trade_id_col: str = "id") -> str:
    """Return a SQL fragment ``AND <trade_id_col> NOT IN (<void subquery>)`` to
    splice into a raw ``FROM trades`` query's WHERE clause (20-A B-2). The
    fragment is self-contained (no bind params). ``trade_id_col`` is the
    caller's column expression for the trade id (e.g. ``"id"``, ``"t.id"``,
    ``"trades.id"``). Trusted caller-supplied identifier only (NOT user input).
    """
    return f" AND {trade_id_col} NOT IN ({_VOIDED_TRADE_IDS_SUBQUERY})"


def voided_trade_ids(conn: sqlite3.Connection) -> frozenset[int]:
    """Return the set of trade ids annotated void via a ``trade_events`` note.

    A trade is void when it has at least one ``trade_events`` row whose
    ``payload_json`` carries ``"voided": true`` (SQLite ``json_extract`` maps
    JSON ``true`` -> the integer ``1``). Pure read; caller owns no tx.
    """
    # Guard json_extract with json_valid (Codex R3 MAJOR): a single malformed
    # legacy/audit payload_json would otherwise raise sqlite3.OperationalError
    # and take down every measurement surface now sitting under this predicate.
    rows = conn.execute(
        "SELECT DISTINCT trade_id FROM trade_events "
        "WHERE payload_json IS NOT NULL AND json_valid(payload_json) "
        "  AND json_extract(payload_json, '$.voided') IS 1"
    ).fetchall()
    return frozenset(int(r[0]) for r in rows if r[0] is not None)
