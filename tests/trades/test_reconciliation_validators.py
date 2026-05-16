"""T-B.2 — dry-run validator shim tests.

Schema-CHECK-mirror predicates + FK existence + aggregate-invariant
dry-run. SELECT-only; NEVER mutates the DB (discriminating test for the
no-mutation property reads the row back after a rejected validation +
asserts unchanged).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Fill, Trade
from swing.trades.reconciliation_validators import (
    validate_cash_movement_correction,
    validate_fill_correction,
    validate_snapshot_correction,
    validate_trade_correction,
)
from tests.conftest import insert_trade_with_entry_fill, make_trade


# ---------------------------------------------------------------------------
# Shared in-memory DB fixture (schema v19)
# ---------------------------------------------------------------------------


@pytest.fixture
def conn_v19(tmp_path: Path) -> sqlite3.Connection:
    """Return a fresh sqlite3 Connection migrated to schema v19."""
    db_path = tmp_path / "test_validators.db"
    conn = ensure_schema(db_path)
    return conn


# ---------------------------------------------------------------------------
# Planted trade + entry-fill (CVGI 41-shaped)
# ---------------------------------------------------------------------------


@pytest.fixture
def conn_with_planted_cvgi_trade_and_fill(
    conn_v19: sqlite3.Connection,
) -> sqlite3.Connection:
    """Plant a CVGI-shaped trade + entry fill for validator tests.

    The fill_id is auto-assigned by AUTOINCREMENT; the helper returns the
    connection only — tests query fills.fill_id after fixture if they need
    the exact id, but most tests just use ``fill_id=1`` since the fixture
    plants exactly 1 fill.
    """
    trade = make_trade(
        ticker="CVGI",
        entry_date="2026-04-27",
        entry_price=5.23,
        initial_shares=100,
        initial_stop=4.50,
        current_stop=4.50,
        state="entered",
    )
    insert_trade_with_entry_fill(
        conn_v19, trade, event_ts="2026-04-27T10:00:00", rationale=None,
    )
    return conn_v19


# ---------------------------------------------------------------------------
# validate_fill_correction
# ---------------------------------------------------------------------------


def test_validate_fill_correction_passes_on_valid_price_update(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_fill_correction(conn, 1, {"price": 5.30})
    assert passes is True
    assert reason is None


def test_validate_fill_correction_rejects_negative_price(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_fill_correction(conn, 1, {"price": -1.0})
    assert passes is False
    assert "price" in (reason or "").lower()


def test_validate_fill_correction_rejects_zero_price(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_fill_correction(conn, 1, {"price": 0})
    assert passes is False
    assert "price" in (reason or "").lower()


def test_validate_fill_correction_rejects_zero_quantity(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_fill_correction(conn, 1, {"quantity": 0})
    assert passes is False
    assert "quantity" in (reason or "").lower()


def test_validate_fill_correction_rejects_bad_action(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_fill_correction(conn, 1, {"action": "bogus"})
    assert passes is False
    assert "action" in (reason or "").lower()


def test_validate_fill_correction_rejects_nonexistent_fill(
    conn_v19: sqlite3.Connection,
) -> None:
    passes, reason = validate_fill_correction(conn_v19, 99999, {"price": 5.30})
    assert passes is False
    assert "not found" in (reason or "").lower()


def test_validate_fill_correction_rejects_nonexistent_trade_fk(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    """Proposing trade_id update to a non-existent trade → FK check rejects."""
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_fill_correction(conn, 1, {"trade_id": 99999})
    assert passes is False
    assert "trade_id" in (reason or "").lower()
    assert "not found" in (reason or "").lower()


def test_validate_fill_correction_does_not_mutate_db(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    """Discriminating test: rejected validation does NOT write to DB."""
    conn = conn_with_planted_cvgi_trade_and_fill
    pre_row = conn.execute(
        "SELECT price FROM fills WHERE fill_id = 1"
    ).fetchone()
    pre_price = pre_row[0]
    # Attempt a rejected validation.
    passes, _reason = validate_fill_correction(conn, 1, {"price": -99.0})
    assert passes is False
    post_row = conn.execute(
        "SELECT price FROM fills WHERE fill_id = 1"
    ).fetchone()
    assert post_row[0] == pre_price


# ---------------------------------------------------------------------------
# Aggregate-invariant dry-run
# ---------------------------------------------------------------------------


@pytest.fixture
def conn_with_planted_trim_scenario(
    conn_v19: sqlite3.Connection,
) -> sqlite3.Connection:
    """Plant: trade with 1 entry (100 sh) + 1 trim (50 sh). current_size=50.

    Used to test the aggregate-invariant dry-run: proposing a correction to
    the entry fill's quantity to 30 would yield simulated_size = 30 - 50 =
    -20 < 0; validator MUST reject.
    """
    from swing.data.repos.fills import insert_fill_with_event

    trade = make_trade(
        ticker="TRIM",
        entry_date="2026-04-27",
        entry_price=10.0,
        initial_shares=100,
        initial_stop=9.0,
        current_stop=9.0,
        state="partial_exited",
    )
    insert_trade_with_entry_fill(
        conn_v19, trade, event_ts="2026-04-27T10:00:00",
    )
    # Add a trim fill (50 shares).
    insert_fill_with_event(
        conn_v19,
        Fill(
            fill_id=None, trade_id=1,
            fill_datetime="2026-04-27T14:00:00",
            action="trim",
            quantity=50.0,
            price=11.0,
        ),
        event_ts="2026-04-27T14:00:00",
    )
    return conn_v19


def test_validate_fill_correction_rejects_aggregate_invariant_violation(
    conn_with_planted_trim_scenario: sqlite3.Connection,
) -> None:
    """Plant: 1 entry (100sh) + 1 trim (50sh). Propose entry qty=30.

    Simulated current_size = 30 - 50 = -20 < 0 → validator rejects.
    """
    conn = conn_with_planted_trim_scenario
    passes, reason = validate_fill_correction(
        conn, fill_id=1, proposed_updates={"quantity": 30},
    )
    assert passes is False
    assert "current_size" in (reason or "").lower()


def test_validate_fill_correction_passes_when_aggregate_stays_nonneg(
    conn_with_planted_trim_scenario: sqlite3.Connection,
) -> None:
    """Same fixture; propose entry qty=80 → simulated_size = 80-50 = 30 >= 0."""
    conn = conn_with_planted_trim_scenario
    passes, reason = validate_fill_correction(
        conn, fill_id=1, proposed_updates={"quantity": 80},
    )
    assert passes is True
    assert reason is None


# ---------------------------------------------------------------------------
# validate_trade_correction
# ---------------------------------------------------------------------------


def test_validate_trade_correction_passes_on_valid_stop(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_trade_correction(conn, 1, {"current_stop": 5.0})
    assert passes is True
    assert reason is None


def test_validate_trade_correction_rejects_zero_stop(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_trade_correction(conn, 1, {"current_stop": 0})
    assert passes is False
    assert "current_stop" in (reason or "").lower()


def test_validate_trade_correction_rejects_negative_stop(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_trade_correction(conn, 1, {"current_stop": -1.0})
    assert passes is False
    assert "current_stop" in (reason or "").lower()


def test_validate_trade_correction_rejects_bad_state(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_trade_correction(conn, 1, {"state": "bogus"})
    assert passes is False
    assert "state" in (reason or "").lower()


def test_validate_trade_correction_rejects_nonexistent_trade(
    conn_v19: sqlite3.Connection,
) -> None:
    passes, reason = validate_trade_correction(conn_v19, 9999, {"current_stop": 5.0})
    assert passes is False
    assert "not found" in (reason or "").lower()


def test_validate_trade_correction_passes_when_no_validated_fields(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
) -> None:
    """Schema-mirror only: irrelevant field passes through (caller is
    responsible for higher-level domain rules)."""
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_trade_correction(conn, 1, {"notes": "x"})
    assert passes is True
    assert reason is None


# ---------------------------------------------------------------------------
# validate_cash_movement_correction
# ---------------------------------------------------------------------------


@pytest.fixture
def conn_with_planted_cash_movement(
    conn_v19: sqlite3.Connection,
) -> sqlite3.Connection:
    conn_v19.execute(
        "INSERT INTO cash_movements (id, date, kind, amount, ref) "
        "VALUES (?, ?, ?, ?, ?)",
        (1, "2026-04-27", "deposit", 1000.0, None),
    )
    conn_v19.commit()
    return conn_v19


def test_validate_cash_movement_correction_passes_on_valid(
    conn_with_planted_cash_movement: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cash_movement
    passes, reason = validate_cash_movement_correction(
        conn, 1, {"amount": 1500.0},
    )
    assert passes is True
    assert reason is None


def test_validate_cash_movement_correction_rejects_negative_amount(
    conn_with_planted_cash_movement: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cash_movement
    passes, reason = validate_cash_movement_correction(
        conn, 1, {"amount": -100.0},
    )
    assert passes is False
    assert "amount" in (reason or "").lower()


def test_validate_cash_movement_correction_rejects_bad_kind(
    conn_with_planted_cash_movement: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_cash_movement
    passes, reason = validate_cash_movement_correction(
        conn, 1, {"kind": "bogus"},
    )
    assert passes is False
    assert "kind" in (reason or "").lower()


def test_validate_cash_movement_correction_rejects_nonexistent_id(
    conn_v19: sqlite3.Connection,
) -> None:
    passes, reason = validate_cash_movement_correction(
        conn_v19, 9999, {"amount": 1000.0},
    )
    assert passes is False
    assert "not found" in (reason or "").lower()


# ---------------------------------------------------------------------------
# validate_snapshot_correction
# ---------------------------------------------------------------------------


@pytest.fixture
def conn_with_planted_snapshot(
    conn_v19: sqlite3.Connection,
) -> sqlite3.Connection:
    conn_v19.execute(
        """
        INSERT INTO account_equity_snapshots
          (snapshot_id, snapshot_date, equity_dollars, source,
           source_artifact_path, recorded_at, recorded_by, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, "2026-04-27", 2000.0, "manual", None,
         "2026-04-27T10:00:00", "operator", None),
    )
    conn_v19.commit()
    return conn_v19


def test_validate_snapshot_correction_passes_on_valid(
    conn_with_planted_snapshot: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_snapshot
    passes, reason = validate_snapshot_correction(
        conn, 1, {"equity_dollars": 2500.0},
    )
    assert passes is True
    assert reason is None


def test_validate_snapshot_correction_rejects_zero_equity(
    conn_with_planted_snapshot: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_snapshot
    passes, reason = validate_snapshot_correction(
        conn, 1, {"equity_dollars": 0.0},
    )
    assert passes is False
    assert "equity_dollars" in (reason or "").lower()


def test_validate_snapshot_correction_rejects_negative_equity(
    conn_with_planted_snapshot: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_snapshot
    passes, reason = validate_snapshot_correction(
        conn, 1, {"equity_dollars": -100.0},
    )
    assert passes is False
    assert "equity_dollars" in (reason or "").lower()


def test_validate_snapshot_correction_rejects_bad_source(
    conn_with_planted_snapshot: sqlite3.Connection,
) -> None:
    conn = conn_with_planted_snapshot
    passes, reason = validate_snapshot_correction(
        conn, 1, {"source": "bogus"},
    )
    assert passes is False
    assert "source" in (reason or "").lower()


def test_validate_snapshot_correction_rejects_nonexistent_id(
    conn_v19: sqlite3.Connection,
) -> None:
    passes, reason = validate_snapshot_correction(
        conn_v19, 9999, {"equity_dollars": 2000.0},
    )
    assert passes is False
    assert "not found" in (reason or "").lower()


# ---------------------------------------------------------------------------
# Codex R1 Major #2 — math.isfinite() guard on all numeric validator fields.
#
# `swing/data/models.py` REAL-field validators reject NaN/inf on REAL
# columns (cf. models.py:888-896). The shipped validators only checked
# type and inequality, so float('inf') passed positive checks and
# float('nan') ≤ 0 is False so NaN passed too. These tests pin the
# tightened contract: NaN/inf must be rejected at validator-shim time
# (before the schema CHECK fires) with a reason mentioning "finite".
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_validate_fill_correction_rejects_nan_or_inf_quantity(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
    bad_value: float,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_fill_correction(conn, 1, {"quantity": bad_value})
    assert passes is False
    assert "finite" in (reason or "").lower()


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_validate_fill_correction_rejects_nan_or_inf_price(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
    bad_value: float,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_fill_correction(conn, 1, {"price": bad_value})
    assert passes is False
    assert "finite" in (reason or "").lower()


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_validate_trade_correction_rejects_nan_or_inf_current_stop(
    conn_with_planted_cvgi_trade_and_fill: sqlite3.Connection,
    bad_value: float,
) -> None:
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_trade_correction(
        conn, 1, {"current_stop": bad_value},
    )
    assert passes is False
    assert "finite" in (reason or "").lower()


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_validate_cash_movement_correction_rejects_nan_or_inf_amount(
    conn_with_planted_cash_movement: sqlite3.Connection,
    bad_value: float,
) -> None:
    conn = conn_with_planted_cash_movement
    passes, reason = validate_cash_movement_correction(
        conn, 1, {"amount": bad_value},
    )
    assert passes is False
    assert "finite" in (reason or "").lower()


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_validate_snapshot_correction_rejects_nan_or_inf_equity_dollars(
    conn_with_planted_snapshot: sqlite3.Connection,
    bad_value: float,
) -> None:
    conn = conn_with_planted_snapshot
    passes, reason = validate_snapshot_correction(
        conn, 1, {"equity_dollars": bad_value},
    )
    assert passes is False
    assert "finite" in (reason or "").lower()
