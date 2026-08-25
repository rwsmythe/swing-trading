"""``latch_order_mandate_links`` repo (migration 0037) -- 22-A.

READ-ONLY BY CONSTRUCTION, and that is not a convention here: the table's rows
are MINTED BY A TRIGGER at broker acceptance and its append-only triggers ABORT
every UPDATE and DELETE, so there is nothing for a writer to do.  A repo
function that inserted a link would be minting provenance by hand -- the exact
thing the trigger exists to make impossible.

THE LOOKUP RETURNS A LIST, NEVER AN ``Optional``.  There is deliberately no
UNIQUE on ``broker_order_id`` (a duplicate would abort the LEDGER write, and
cohort bookkeeping must never block a money-bearing operation), so cardinality
is the READER's COUNT: two links sharing one order id refuse
``ambiguous_accepted_orders`` at admission.  Returning a list makes that
expressible in the TYPE rather than only in prose -- a ``fetchone()`` signature
would silently pick one and look correct.

Pure CRUD inside the CALLER's transaction: these functions DO NOT commit.
"""
from __future__ import annotations

import sqlite3

from swing.data.models import LatchOrderMandateLink

# ONE column list, shared by every read, so a widening lands in one place (#11).
_COLUMNS: tuple[str, ...] = (
    "link_id",
    "validity_intent_id",
    "place_intent_id",
    "candidate_id",
    "evaluation_run_id",
    "ticker",
    "detection_date",
    "broker_order_id",
    "frozen_pivot",
    "frozen_invalidation",
    "actual_quantity",
    "freeze_tier",
    "linked_at",
)

_SELECT = ", ".join(_COLUMNS)


def _row_to_link(row: tuple) -> LatchOrderMandateLink:
    return LatchOrderMandateLink(**dict(zip(_COLUMNS, row, strict=True)))


def list_links_for_broker_order(
    conn: sqlite3.Connection, broker_order_id: str,
) -> list[LatchOrderMandateLink]:
    """EVERY link naming this broker order, oldest first.

    The caller counts; this function does not choose.
    """
    rows = conn.execute(
        f"SELECT {_SELECT} FROM latch_order_mandate_links "
        f"WHERE broker_order_id = ? ORDER BY link_id",
        (broker_order_id,),
    ).fetchall()
    return [_row_to_link(r) for r in rows]


def list_links_for_ticker(
    conn: sqlite3.Connection, ticker: str,
) -> list[LatchOrderMandateLink]:
    """Every link on a ticker -- the competitor population's raw input.

    Liveness, authority and consumption are decided by the resolver, not here:
    a repo that pre-filtered would be making an admission judgment in the data
    layer, where no test of the ladder can see it.
    """
    rows = conn.execute(
        f"SELECT {_SELECT} FROM latch_order_mandate_links "
        f"WHERE ticker = ? ORDER BY link_id",
        (ticker,),
    ).fetchall()
    return [_row_to_link(r) for r in rows]


def get_link(
    conn: sqlite3.Connection, link_id: int,
) -> LatchOrderMandateLink | None:
    row = conn.execute(
        f"SELECT {_SELECT} FROM latch_order_mandate_links WHERE link_id = ?",
        (link_id,),
    ).fetchone()
    return None if row is None else _row_to_link(row)
