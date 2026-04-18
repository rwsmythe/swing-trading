"""Cash repo round-trip + ref-based dedup."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import CashMovement
from swing.data.repos.cash import insert_cash, list_cash, find_by_ref


def test_insert_and_list(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            insert_cash(conn, CashMovement(
                id=None, date="2026-04-01", kind="deposit",
                amount=500.0, ref="DEP-001", note=None,
            ))
            insert_cash(conn, CashMovement(
                id=None, date="2026-04-15", kind="withdraw",
                amount=100.0, ref="WD-001", note="margin call",
            ))
        rows = list_cash(conn)
        assert len(rows) == 2
        assert sum(1 for r in rows if r.kind == "deposit") == 1
    finally:
        conn.close()


def test_ref_dedup(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            insert_cash(conn, CashMovement(
                id=None, date="2026-04-01", kind="deposit",
                amount=500.0, ref="DEP-001", note=None,
            ))
        # Re-insert same ref must fail (UNIQUE INDEX)
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                insert_cash(conn, CashMovement(
                    id=None, date="2026-04-01", kind="deposit",
                    amount=500.0, ref="DEP-001", note=None,
                ))
        # find_by_ref returns the existing
        existing = find_by_ref(conn, "DEP-001")
        assert existing is not None and existing.amount == 500.0
    finally:
        conn.close()


def test_null_ref_allowed_multiple(tmp_path: Path):
    """Manual entries (no ref) can be duplicated."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            insert_cash(conn, CashMovement(
                id=None, date="2026-04-01", kind="deposit",
                amount=10.0, ref=None, note="cash"
            ))
            insert_cash(conn, CashMovement(
                id=None, date="2026-04-01", kind="deposit",
                amount=10.0, ref=None, note="cash"
            ))
        assert len(list_cash(conn)) == 2
    finally:
        conn.close()
