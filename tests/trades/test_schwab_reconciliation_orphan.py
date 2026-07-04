"""Arc 19-F — the FK-orphan predicate + orphan-reason composer.

``orphaned_affected_target`` recognizes a discrepancy whose referenced FK
subject row (fill / cash_movement / trade) was RAW-DELETED (D19's interim
doctrine), so the web + CLI resolve surfaces can route it to a terminal
``acknowledged_immaterial`` resolution instead of failing to read the gone row.

Seeding discipline (18-B.1): the dangling-FK orphan is planted via a RAW
``conn.execute`` INSERT with ``PRAGMA foreign_keys = OFF`` -- this tests
DETECTION of pre-existing bad state, not the write path, and mirrors how the
live orphan (disc 73 still holding ``cash_movement_id=5`` after row 5's raw
delete) could ever exist.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.schwab_reconciliation import (
    compose_orphan_reason,
    orphaned_affected_target,
)


class _Disc:
    """Minimal duck-typed discrepancy stand-in for the pure predicate."""

    def __init__(
        self,
        *,
        fill_id: int | None = None,
        cash_movement_id: int | None = None,
        trade_id: int | None = None,
    ) -> None:
        self.fill_id = fill_id
        self.cash_movement_id = cash_movement_id
        self.trade_id = trade_id


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "test.db")
    # Seed the corrupt (dangling-FK) state with FK enforcement OFF -- an FK-ON
    # connection would REJECT an INSERT referencing a nonexistent id.
    c.execute("PRAGMA foreign_keys = OFF")
    return c


def _seed_cash_movement(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO cash_movements (date, kind, amount) VALUES (?, ?, ?)",
        ("2026-06-15", "deposit", 100.0),
    )
    conn.commit()
    return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# orphaned_affected_target
# ---------------------------------------------------------------------------


def test_orphan_cash_movement_missing_returns_table_id(
    conn: sqlite3.Connection,
) -> None:
    """A discrepancy referencing a nonexistent cash_movement_id -> orphan."""
    disc = _Disc(cash_movement_id=999)  # never inserted
    assert orphaned_affected_target(conn, disc) == ("cash_movements", 999)


def test_existing_cash_movement_returns_none(conn: sqlite3.Connection) -> None:
    """The no-regression lock: a live FK row -> None (reaches tier-2 form)."""
    cm_id = _seed_cash_movement(conn)
    disc = _Disc(cash_movement_id=cm_id)
    assert orphaned_affected_target(conn, disc) is None


def test_all_fk_null_returns_none(conn: sqlite3.Connection) -> None:
    """All-FK-null (equity_delta / source-direction) -> None (own branch)."""
    assert orphaned_affected_target(conn, _Disc()) is None


def test_orphan_fill_missing_returns_fills_id(conn: sqlite3.Connection) -> None:
    disc = _Disc(fill_id=555)
    assert orphaned_affected_target(conn, disc) == ("fills", 555)


def test_orphan_trade_missing_returns_trades_id(
    conn: sqlite3.Connection,
) -> None:
    disc = _Disc(trade_id=444)
    assert orphaned_affected_target(conn, disc) == ("trades", 444)


def test_fk_precedence_fill_over_cash_over_trade(
    conn: sqlite3.Connection,
) -> None:
    """Precedence mirrors _resolve_affected_target: fill_id wins."""
    disc = _Disc(fill_id=111, cash_movement_id=222, trade_id=333)
    assert orphaned_affected_target(conn, disc) == ("fills", 111)


# ---------------------------------------------------------------------------
# compose_orphan_reason
# ---------------------------------------------------------------------------


def test_compose_orphan_reason_always_non_empty_names_row() -> None:
    reason = compose_orphan_reason("cash_movements", 5, None)
    assert reason
    assert "cash_movements id=5" in reason
    assert "no longer" in reason


def test_compose_orphan_reason_appends_operator_text() -> None:
    reason = compose_orphan_reason("cash_movements", 5, "subject row gone D19")
    assert "cash_movements id=5" in reason
    assert reason.endswith("subject row gone D19")


def test_compose_orphan_reason_blank_operator_text_omitted() -> None:
    reason = compose_orphan_reason("fills", 7, "   ")
    assert reason == compose_orphan_reason("fills", 7, None)
    assert reason.isascii()
