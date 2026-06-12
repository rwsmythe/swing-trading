"""Gate-run #100 witness fix #2 — the journal-direction cash tier-2 resolve.

The operator's resolve of live discrepancy 66 failed with
``sqlite3.OperationalError: no such column: net_amount`` (mislabeled as
"Database is busy" by the route's broad catch). Root cause: the cash
journal-direction emitter writes ``field_name='net_amount'`` (the honest
ENVELOPE semantic name), but the tier-2 generic SELECT/UPDATE helpers assume
field_name == column name — the ledger column is ``amount``. No prior test
exercised the cash update path end-to-end. This one mirrors row 66 verbatim.
"""
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_auto_correct import apply_tier2_resolution


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_cash_pending_like_66(conn: sqlite3.Connection) -> dict[str, Any]:
    cur = conn.execute(
        "INSERT INTO reconciliation_runs (source, state, started_ts, "
        "finished_ts, period_start, period_end) VALUES ('schwab_api', "
        "'completed', '1', '2', '2026-05-01', '2026-05-31')")
    run_id = int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO cash_movements (date, kind, amount, ref, note) "
        "VALUES ('2026-05-28', 'deposit', 100.0, NULL, NULL)")
    cash_id = int(cur.lastrowid)
    # Mirrors live row 66: journal-direction, field_name='net_amount',
    # expected = the journal side {"amount","date","kind"}, actual = the
    # load-bearing sole-key {"matched": null}.
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "field_name, cash_movement_id, material_to_review, created_at, "
        "resolution, ambiguity_kind, expected_value_json, actual_value_json) "
        "VALUES (?, 'cash_movement_mismatch', 'net_amount', ?, 0, '1', "
        "'pending_ambiguity_resolution', 'schwab_returned_no_match', "
        "'{\"amount\": 100.0, \"date\": \"2026-05-28\", \"kind\": \"deposit\"}', "
        "'{\"matched\": null}')", (run_id, cash_id))
    conn.commit()
    return {"discrepancy_id": int(cur.lastrowid), "cash_id": cash_id}


def test_operator_truth_on_66_shaped_cash_row_updates_amount_column(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_cash_pending_like_66(conn)
    apply_tier2_resolution(
        conn,
        discrepancy_id=seed["discrepancy_id"],
        choice_code="operator_truth",
        operator_custom_payload={"net_amount": 123.45},
        operator_reason="broker statement says 123.45",
    )
    # The DISCRIMINATOR: pre-fix this raises sqlite3.OperationalError
    # ("no such column: net_amount") before any write; post-fix the ledger
    # column `amount` carries the operator value.
    amount = conn.execute(
        "SELECT amount FROM cash_movements WHERE id = ?",
        (seed["cash_id"],)).fetchone()[0]
    assert amount == pytest.approx(123.45)
    res = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies WHERE "
        "discrepancy_id = ?", (seed["discrepancy_id"],)).fetchone()[0]
    assert res != "pending_ambiguity_resolution"
