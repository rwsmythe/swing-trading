"""20-A Task A-4 — the re-correction alarm (the #34 killer + override clobber).

A tier-1 fill correction that would CHANGE the fill's already-effective
canonical value to a DIFFERENT one is BLOCKED (ReCorrectionContradictionError)
and routed to a material tier-2 stamp. Keyed on the fill's EFFECTIVE chain
head (persists across discrepancies), so it blocks the FRESH-discrepancy #34
re-fire AND a tier-1 that would clobber a B1 operator override.

Pre/post: pre-fix the service applies a 2nd auto-correct (the #34 corruption)
/ silently no-ops on a terminal discrepancy; post-fix it raises + the fill
stays put.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import ReconciliationCorrection
from swing.data.repos.reconciliation_corrections import insert_correction
from swing.trades.reconciliation_auto_correct import (
    ReCorrectionContradictionError,
    apply_tier1_correction,
)
from swing.trades.reconciliation_classifier import ClassificationResult


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_fill(conn, *, fill_price: float) -> tuple[int, int, int]:
    cur = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("AMN", "2026-07-01", fill_price, 3, fill_price - 1.0, fill_price - 1.0,
         "managing", "manual_off_pipeline", "2026-07-01T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-07-07T14:00:00", "entry", 3, fill_price,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    run_cur = conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state, "
        "period_start, period_end) VALUES (?, ?, ?, ?, ?)",
        ("schwab_api", "2026-07-10T12:00:00", "running", "2026-07-01",
         "2026-07-10"),
    )
    run_id = int(run_cur.lastrowid)
    conn.commit()
    return trade_id, fill_id, run_id


def _plant_chain_head(
    conn, *, fill_id: int, run_id: int, trade_id: int, value: float,
    action: str,
) -> int:
    """Insert a prior effective (superseded_by NULL) correction on the fill,
    anchored on a prior (terminal) discrepancy."""
    prior_disc = conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, fill_id, ticker, field_name, expected_value_json, "
        "actual_value_json, delta_text, material_to_review, resolution, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, "entry_price_mismatch", trade_id, fill_id, "AMN", "price",
         json.dumps({"price": value}), json.dumps({"price": value}), "prior",
         1, "auto_corrected_from_schwab", "2026-07-08T12:00:00"),
    ).lastrowid
    applied = json.dumps({"price": value}, sort_keys=True)
    correction = ReconciliationCorrection(
        correction_id=0,
        discrepancy_id=int(prior_disc),
        correction_action=action,
        correction_choice=None,
        affected_table="fills",
        affected_row_id=fill_id,
        field_name="price",
        pre_correction_value_json=json.dumps({"price": 0.0}),
        source_canonical_value_json=applied,
        applied_value_json=applied,
        operator_truth_value_json=(
            applied if action == "operator_overridden" else None
        ),
        applied_at="2026-07-08T12:00:00",
        applied_by="auto" if action == "auto_applied" else "operator",
        correction_set_id=None,
        superseded_by_correction_id=None,
        risk_policy_id_at_correction=None,
        schwab_api_call_id=None,
        reconciliation_run_id=run_id,
        correction_reason="prior correction (fixture)",
        notes=None,
    )
    return insert_correction(conn, correction)


def _new_discrepancy(conn, *, run_id: int, trade_id: int, fill_id: int) -> int:
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, fill_id, ticker, field_name, expected_value_json, "
        "actual_value_json, delta_text, material_to_review, resolution, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, "entry_price_mismatch", trade_id, fill_id, "AMN", "price",
         json.dumps({"price": 35.65}), json.dumps({"price": 32.06}),
         "-3.59", 1, "unresolved", "2026-07-10T12:00:00"),
    )
    conn.commit()
    return int(cur.lastrowid)


def _tier1(price: float) -> ClassificationResult:
    return ClassificationResult(
        tier=1, ambiguity_kind=None, correction_target={"price": price},
        correction_reason="tier-1 (test)", candidate_choices=None,
    )


def test_number_34_replay_is_blocked(conn) -> None:
    """Chain head 35.65 (auto_applied); a FRESH tier-1 proposes 32.06 ->
    ReCorrectionContradictionError; the fill stays 35.65 (no 2nd auto-apply)."""
    trade_id, fill_id, run_id = _seed_fill(conn, fill_price=35.65)
    _plant_chain_head(conn, fill_id=fill_id, run_id=run_id,
                      trade_id=trade_id, value=35.65,
                      action="auto_applied")
    disc_id = _new_discrepancy(conn, run_id=run_id, trade_id=trade_id,
                               fill_id=fill_id)
    with pytest.raises(ReCorrectionContradictionError):
        apply_tier1_correction(
            conn, discrepancy_id=disc_id, classification=_tier1(32.06),
            environment="production",
        )
    price = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fill_id,),
    ).fetchone()[0]
    assert price == 35.65


def test_operator_override_clobber_is_blocked(conn) -> None:
    """Chain head operator_overridden 13.00; a tier-1 proposes 12.305 ->
    blocked (the corrector can never remove the human)."""
    trade_id, fill_id, run_id = _seed_fill(conn, fill_price=13.00)
    _plant_chain_head(conn, fill_id=fill_id, run_id=run_id,
                      trade_id=trade_id, value=13.00,
                      action="operator_overridden")
    disc_id = _new_discrepancy(conn, run_id=run_id, trade_id=trade_id,
                               fill_id=fill_id)
    with pytest.raises(ReCorrectionContradictionError):
        apply_tier1_correction(
            conn, discrepancy_id=disc_id, classification=_tier1(12.305),
            environment="production",
        )
    price = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fill_id,),
    ).fetchone()[0]
    assert price == 13.00


def test_identical_reapply_is_not_a_contradiction(conn) -> None:
    """A tier-1 proposing the SAME effective value is not a contradiction —
    the guard does not over-fire (it proceeds normally)."""
    trade_id, fill_id, run_id = _seed_fill(conn, fill_price=35.65)
    _plant_chain_head(conn, fill_id=fill_id, run_id=run_id,
                      trade_id=trade_id, value=35.65,
                      action="auto_applied")
    disc_id = _new_discrepancy(conn, run_id=run_id, trade_id=trade_id,
                               fill_id=fill_id)
    # Proposing 35.65 again: no contradiction (applies a redundant correction).
    result = apply_tier1_correction(
        conn, discrepancy_id=disc_id, classification=_tier1(35.65),
        environment="production",
    )
    assert result.correction_id is not None


def test_terminal_path_belt_raises_on_differing_value(conn) -> None:
    """A tier-1 targeting an already-operator_overridden (terminal)
    discrepancy with a DIFFERING value raises the contradiction instead of a
    silent idempotent no-op."""
    trade_id, fill_id, run_id = _seed_fill(conn, fill_price=13.00)
    _plant_chain_head(conn, fill_id=fill_id, run_id=run_id,
                      trade_id=trade_id, value=13.00,
                      action="operator_overridden")
    disc_id = _new_discrepancy(conn, run_id=run_id, trade_id=trade_id,
                               fill_id=fill_id)
    # Mark the discrepancy terminal (operator_overridden).
    conn.execute(
        "UPDATE reconciliation_discrepancies SET resolution = "
        "'operator_overridden' WHERE discrepancy_id = ?", (disc_id,),
    )
    conn.commit()
    with pytest.raises(ReCorrectionContradictionError):
        apply_tier1_correction(
            conn, discrepancy_id=disc_id, classification=_tier1(12.305),
            environment="production",
        )


def test_later_non_price_head_does_not_mask_price_head(conn) -> None:
    """Codex R1 MAJOR — a LATER unsuperseded head touching a DIFFERENT field
    must not mask the effective PRICE head: a fresh tier-1 proposing a value
    that differs from the price head is still blocked."""
    trade_id, fill_id, run_id = _seed_fill(conn, fill_price=13.00)
    # Effective PRICE head 13.00 (operator override).
    _plant_chain_head(conn, fill_id=fill_id, run_id=run_id,
                      trade_id=trade_id, value=13.00,
                      action="operator_overridden")
    # A LATER unsuperseded head touching `quantity` (a non-price field).
    prior_disc = conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, fill_id, ticker, field_name, expected_value_json, "
        "actual_value_json, delta_text, material_to_review, resolution, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, "position_qty_mismatch", trade_id, fill_id, "AMN",
         "quantity", json.dumps({"quantity": 3}), json.dumps({"quantity": 3}),
         "qty", 1, "auto_corrected_from_schwab", "2026-07-09T12:00:00"),
    ).lastrowid
    from swing.data.repos.reconciliation_corrections import insert_correction
    insert_correction(conn, ReconciliationCorrection(
        correction_id=0, discrepancy_id=int(prior_disc),
        correction_action="auto_applied", correction_choice=None,
        affected_table="fills", affected_row_id=fill_id, field_name="quantity",
        pre_correction_value_json=json.dumps({"quantity": 0}),
        source_canonical_value_json=json.dumps({"quantity": 3}),
        applied_value_json=json.dumps({"quantity": 3}),
        operator_truth_value_json=None, applied_at="2026-07-09T12:00:00",
        applied_by="auto", correction_set_id=None,
        superseded_by_correction_id=None, risk_policy_id_at_correction=None,
        schwab_api_call_id=None, reconciliation_run_id=run_id,
        correction_reason="qty head", notes=None,
    ))
    disc_id = _new_discrepancy(conn, run_id=run_id, trade_id=trade_id,
                               fill_id=fill_id)
    conn.commit()
    with pytest.raises(ReCorrectionContradictionError):
        apply_tier1_correction(
            conn, discrepancy_id=disc_id, classification=_tier1(12.305),
            environment="production",
        )
    price = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fill_id,),
    ).fetchone()[0]
    assert price == 13.00


def test_first_correction_not_blocked(conn) -> None:
    """A fill with NO prior chain head applies its first tier-1 normally."""
    trade_id, fill_id, run_id = _seed_fill(conn, fill_price=35.65)
    disc_id = _new_discrepancy(conn, run_id=run_id, trade_id=trade_id,
                               fill_id=fill_id)
    result = apply_tier1_correction(
        conn, discrepancy_id=disc_id, classification=_tier1(35.65),
        environment="production",
    )
    assert result.correction_id is not None


# ---------------------------------------------------------------------------
# Both firing sites (pivot + backfill) route a blocked re-correction to a
# material tier-2 stamp (never a 2nd auto-apply / errored no-op).
# ---------------------------------------------------------------------------


from dataclasses import dataclass  # noqa: E402


@dataclass
class _Order:
    status: str
    price: float
    quantity: float
    instrument_symbol: str
    order_type: str = "MARKET"
    instruction: str = "BUY"
    order_id: str = "ORD1"
    executions: object = None
    enter_time: str = "2026-07-07T14:00:00.000Z"


class _Account:
    def __init__(self):
        self.net_liquidating_value = 2000.0
        self.positions = []


def _leg(price, qty=3.0, time="2026-07-07T14:00:00.000Z"):
    from swing.integrations.schwab.models import SchwabExecutionLeg
    return SchwabExecutionLeg(
        leg_id=1, price=price, quantity=qty, mismarked_quantity=0.0,
        instrument_id=None, time=time,
    )


def test_pivot_firing_site_blocks_and_stamps_tier2(conn) -> None:
    """Pivot: a single-candidate Shape-D tier-1 (5.28) on a fill (5.23) whose
    effective chain head is 5.30 -> A-4 blocks -> the discrepancy is stamped
    tier-2 (pending) inside the same run; the fill stays 5.23."""
    trade_id, fill_id, run_id = _seed_fill(conn, fill_price=5.23)
    _plant_chain_head(conn, fill_id=fill_id, run_id=run_id,
                      trade_id=trade_id, value=5.30, action="auto_applied")
    conn.commit()
    from swing.trades.schwab_reconciliation import run_schwab_reconciliation
    run = run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-07-07", period_end="2026-07-07",
        schwab_orders=[
            _Order(status="FILLED", price=5.28, quantity=3.0,
                   instrument_symbol="AMN", instruction="BUY",
                   executions=[_leg(5.28)]),
        ],
        schwab_transactions=[],
        schwab_account=_Account(),
    )
    price = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fill_id,),
    ).fetchone()[0]
    assert price == 5.23  # NOT re-corrected
    row = conn.execute(
        "SELECT resolution, ambiguity_kind FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND discrepancy_type = 'entry_price_mismatch'",
        (run.run_id,),
    ).fetchone()
    assert row is not None
    assert row[0] == "pending_ambiguity_resolution"
    assert row[1] == "multi_match_within_window"


def test_backfill_firing_site_blocks_and_stamps_tier2(conn) -> None:
    """Backfill: a legacy Shape-C unresolved discrepancy (proposing 5.28) on a
    fill (5.23) whose effective chain head is 5.30 -> A-4 blocks -> tier-2
    stamp; the fill stays 5.23."""
    trade_id, fill_id, run_id = _seed_fill(conn, fill_price=5.23)
    _plant_chain_head(conn, fill_id=fill_id, run_id=run_id,
                      trade_id=trade_id, value=5.30, action="auto_applied")
    shape_c = json.dumps({
        "price": 5.28,
        "execution_legs": [
            {"leg_id": 1, "price": 5.28, "quantity": 3.0,
             "time": "2026-07-07T14:00:00"},
        ],
        "schwab_order_id": "ORD1",
        "schwab_order_price": 5.28,
    }, sort_keys=True)
    disc_id = conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, fill_id, ticker, field_name, expected_value_json, "
        "actual_value_json, delta_text, material_to_review, resolution, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, "entry_price_mismatch", trade_id, fill_id, "AMN", "price",
         json.dumps({"price": 5.23}), shape_c, "+0.05", 1, "unresolved",
         "2026-07-10T12:00:00"),
    ).lastrowid
    conn.commit()
    from swing.trades.reconciliation_backfill import run_backfill
    run_backfill(
        conn, dry_run=False, schwab_client=None, environment="production",
        account_hash=None,
    )
    price = conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (fill_id,),
    ).fetchone()[0]
    assert price == 5.23  # NOT re-corrected
    resolution = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()[0]
    assert resolution == "pending_ambiguity_resolution"
