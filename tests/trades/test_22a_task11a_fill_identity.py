"""22-A task 11a -- fill IDENTITY survives split-into-partials (case 22c).

WHY THIS EXISTS (plan S2.4a, review 22A-R3-02, verified on disk here).  22-A
establishes CONSUMPTION of an accepted broker order by scanning other trades'
entry-fill envelopes for that order id.  The supported
``split_into_partials`` handler DELETES the original fill and rebuilds N
replacements -- and its original-row SELECT does not read ``fill_origin`` or
``schwab_source_value_json``, and the replacement ``Fill(...)`` sets neither.
So a consumption that began in the supposedly authoritative representation
DISAPPEARS, and the same accepted order could be admitted for a second trade.

The fix is semantically correct independent of this arc: a partial of a
Schwab fill is still a Schwab fill.

DIMENSIONS THIS CASE PINS: the envelope's presence on EVERY partial (not just
the first), and ``fill_origin`` carrying through unchanged.  DELIBERATELY
FREE: the number of partials (2 is the shipped fixture shape), the quantities,
and the prices -- none of them interacts with the columns under test.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

from swing.trades.reconciliation_auto_correct import apply_tier2_resolution
from tests.trades.test_apply_tier2_resolution import (  # noqa: F401
    _seed_dhc_pending,
    conn,
)

SCHWAB_ENVELOPE = {
    "entry_date": "2026-04-27",
    "entry_date_source": "execution_leg",
    "entry_price": 7.50,
    "schwab_instrument_symbol": "DHC",
    "schwab_order_id": "1007523377009",
    "shares": 39,
}


@pytest.fixture
def dhc_schwab_world(conn: sqlite3.Connection) -> dict[str, Any]:  # noqa: F811
    world = _seed_dhc_pending(conn)
    conn.execute(
        "UPDATE fills SET fill_origin = ?, schwab_source_value_json = ?, "
        "auto_fill_audit_at = ? WHERE fill_id = ?",
        (
            "schwab_auto",
            json.dumps(SCHWAB_ENVELOPE, sort_keys=True),
            "2026-04-27T14:24:00",
            world["fill_id"],
        ),
    )
    conn.commit()
    return world


def test_split_into_partials_preserves_fill_identity_case_22c(
    conn: sqlite3.Connection,  # noqa: F811
    dhc_schwab_world: dict[str, Any],
) -> None:
    """Case 22c -- every partial keeps ``fill_origin`` + the order envelope.

    PRE-FIX: both replacement rows land ``fill_origin='operator_typed'`` and
    ``schwab_source_value_json=NULL`` -- the order id is GONE from the journal
    and the consumption scan is blind to it.
    POST-FIX: both rows carry ``'schwab_auto'`` and the byte-identical
    envelope, so the scan still sees order ``1007523377009``.
    """
    apply_tier2_resolution(
        conn,
        discrepancy_id=dhc_schwab_world["discrepancy_id"],
        choice_code="split_into_partials",
        operator_custom_payload=[
            {"qty": 20, "price": 7.57, "fill_datetime": "2026-04-27T14:23:00"},
            {"qty": 19, "price": 7.59, "fill_datetime": "2026-04-27T14:23:42"},
        ],
        operator_reason="Schwab broker statement shows 2 partial executions",
    )
    rows = conn.execute(
        "SELECT fill_origin, schwab_source_value_json, auto_fill_audit_at "
        "FROM fills WHERE trade_id = ? AND action = 'entry' "
        "ORDER BY fill_datetime ASC, fill_id ASC",
        (dhc_schwab_world["trade_id"],),
    ).fetchall()
    assert len(rows) == 2
    for origin, envelope_json, audit_at in rows:
        assert origin == "schwab_auto"
        assert envelope_json is not None, (
            "the replacement path stripped the Schwab envelope -- the "
            "consumption evidence 22-A rung 6 depends on is destructible"
        )
        assert json.loads(envelope_json) == SCHWAB_ENVELOPE
        assert json.loads(envelope_json)["schwab_order_id"] == "1007523377009"
        assert audit_at == "2026-04-27T14:24:00"


def test_split_into_partials_leaves_operator_typed_fills_unchanged(
    conn: sqlite3.Connection,  # noqa: F811
) -> None:
    """The ordinary (non-Schwab) split is byte-identical to ``main``'s.

    Without this the fix could have hard-coded ``'schwab_auto'`` onto every
    replacement and case 22c would still pass.
    """
    world = _seed_dhc_pending(conn)
    apply_tier2_resolution(
        conn,
        discrepancy_id=world["discrepancy_id"],
        choice_code="split_into_partials",
        operator_custom_payload=[
            {"qty": 20, "price": 7.57, "fill_datetime": "2026-04-27T14:23:00"},
            {"qty": 19, "price": 7.59, "fill_datetime": "2026-04-27T14:23:42"},
        ],
        operator_reason="operator-typed consolidated fill split by hand",
    )
    rows = conn.execute(
        "SELECT fill_origin, schwab_source_value_json, auto_fill_audit_at "
        "FROM fills WHERE trade_id = ? AND action = 'entry'",
        (world["trade_id"],),
    ).fetchall()
    assert len(rows) == 2
    for origin, envelope_json, audit_at in rows:
        assert origin == "operator_typed"
        assert envelope_json is None
        assert audit_at is None
