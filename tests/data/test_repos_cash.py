"""Cash repo round-trip + ref-based dedup."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import CashMovement
from swing.data.repos.cash import find_by_id, find_by_ref, insert_cash, list_cash


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


def test_find_by_id_round_trip_and_missing(tmp_path: Path):
    """FBI-V (cash-void carve-out #2): the additive find_by_id READ helper
    round-trips a persisted row + returns None on a missing id. The void WRITE
    reuses the existing insert_cash (no new write function)."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            cid = insert_cash(conn, CashMovement(
                id=None, date="2026-06-18", kind="withdraw",
                amount=372.48, ref="DEBIT-1", note="seed",
            ))
        got = find_by_id(conn, cid)
        assert got is not None
        assert got.id == cid
        assert (got.date, got.kind, got.amount, got.ref, got.note) == (
            "2026-06-18", "withdraw", 372.48, "DEBIT-1", "seed")
        # A missing id returns None (the not-found path the CLI rejects on).
        assert find_by_id(conn, 99999) is None
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
