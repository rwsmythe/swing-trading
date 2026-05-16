"""Phase 12 Sub-bundle C T-A.5 — ReconciliationDiscrepancy.ambiguity_kind row deserializer.

Per plan §B.5: `_DISCREPANCY_SELECT_COLUMNS` (and `_D_ALIAS` companion) +
`_row_to_discrepancy` must read the new `ambiguity_kind` column added at
T-A.1 (migration 0019) and populate the dataclass field added at T-A.2.

Tests:
  1. Plant a row with resolution='pending_ambiguity_resolution' +
     ambiguity_kind='multi_partial_vs_consolidated'; read via
     get_discrepancy; verify dataclass field populated.
  2. Back-compat: plant a row with resolution='unresolved' +
     ambiguity_kind=NULL; read back; verify ambiguity_kind is None.
  3. Canonical query path (list_unresolved_material_for_active_trades) —
     verify the `_D_ALIAS` SELECT also surfaces the field (None on default
     row).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.datetime_helpers import now_ms
from swing.data.db import ensure_schema
from swing.data.repos.reconciliation import (
    get_discrepancy,
    list_unresolved_material_for_active_trades,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase12_T_A5.db"
    return ensure_schema(db_path)


def _insert_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        INSERT INTO reconciliation_runs (
            source, started_ts, state
        ) VALUES ('tos_csv', ?, 'completed')
        """,
        (now_ms(),),
    )
    conn.commit()
    return cur.lastrowid


def _insert_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str = "ABC",
    state: str = "entered",
) -> int:
    """Mirrors test_reconciliation_repo.py:_insert_trade."""
    conn.execute(
        "INSERT INTO trades ("
        "ticker, entry_date, entry_price, initial_shares, initial_stop, "
        "current_stop, state, sector, industry, trade_origin, "
        "pre_trade_locked_at, current_size"
        ") VALUES ("
        "?, '2026-05-15', 100.0, 10, 95.0, 95.0, ?, "
        "'Tech', 'Software', 'manual_off_pipeline', "
        "?, 10)",
        (ticker, state, now_ms()),
    )
    row = conn.execute(
        "SELECT id FROM trades WHERE ticker = ? AND entry_date = ?",
        (ticker, "2026-05-15"),
    ).fetchone()
    conn.commit()
    return row[0]


# ============================================================================
# §1 — discriminating test: pending_ambiguity_resolution + ambiguity_kind
# ============================================================================


def test_get_discrepancy_populates_ambiguity_kind_field(
    conn: sqlite3.Connection,
) -> None:
    run_id = _insert_run(conn)
    cur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, ticker, field_name,
            expected_value_json, actual_value_json,
            material_to_review, resolution, ambiguity_kind,
            created_at
        ) VALUES (
            ?, 'position_qty_mismatch', 'ABC', 'qty',
            '100', '50', 1,
            'pending_ambiguity_resolution',
            'multi_partial_vs_consolidated',
            ?
        )
        """,
        (run_id, now_ms()),
    )
    conn.commit()
    disc_id = cur.lastrowid

    disc = get_discrepancy(conn, disc_id)
    assert disc is not None
    assert disc.ambiguity_kind == "multi_partial_vs_consolidated"
    assert disc.resolution == "pending_ambiguity_resolution"


# ============================================================================
# §2 — back-compat: default (unresolved, NULL ambiguity_kind)
# ============================================================================


def test_get_discrepancy_default_ambiguity_kind_is_none(
    conn: sqlite3.Connection,
) -> None:
    run_id = _insert_run(conn)
    cur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, ticker, field_name,
            expected_value_json, actual_value_json,
            material_to_review, resolution,
            created_at
        ) VALUES (
            ?, 'stop_mismatch', 'XYZ', 'stop',
            '9.00', '8.50', 1, 'unresolved',
            ?
        )
        """,
        (run_id, now_ms()),
    )
    conn.commit()
    disc_id = cur.lastrowid

    disc = get_discrepancy(conn, disc_id)
    assert disc is not None
    assert disc.ambiguity_kind is None
    assert disc.resolution == "unresolved"


# ============================================================================
# §3 — canonical query (D-alias SELECT) also surfaces the field
# ============================================================================


def test_list_unresolved_material_for_active_trades_surfaces_ambiguity_kind(
    conn: sqlite3.Connection,
) -> None:
    run_id = _insert_run(conn)
    trade_id = _insert_trade(conn, ticker="ABC", state="entered")
    conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, ticker, field_name,
            expected_value_json, actual_value_json,
            material_to_review, resolution,
            created_at
        ) VALUES (
            ?, 'stop_mismatch', ?, 'ABC', 'stop',
            '9.00', '8.50', 1, 'unresolved',
            ?
        )
        """,
        (run_id, trade_id, now_ms()),
    )
    conn.commit()

    rows = list_unresolved_material_for_active_trades(conn)
    assert len(rows) == 1
    # Discriminating: the _D_ALIAS SELECT must include ambiguity_kind so the
    # dataclass field is populated (None here because the row defaults the
    # column to NULL).
    assert rows[0].ambiguity_kind is None
