"""Cash movements repo. Caller wraps in `with conn:`."""
from __future__ import annotations

import sqlite3

from swing.data.models import CashMovement


def insert_cash(conn: sqlite3.Connection, m: CashMovement) -> int:
    cur = conn.execute(
        """
        INSERT INTO cash_movements (date, kind, amount, ref, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (m.date, m.kind, m.amount, m.ref, m.note),
    )
    return int(cur.lastrowid)


def list_cash(conn: sqlite3.Connection) -> list[CashMovement]:
    rows = conn.execute(
        "SELECT id, date, kind, amount, ref, note FROM cash_movements ORDER BY date, id"
    ).fetchall()
    return [
        CashMovement(id=r[0], date=r[1], kind=r[2], amount=r[3], ref=r[4], note=r[5])
        for r in rows
    ]


def find_by_ref(conn: sqlite3.Connection, ref: str) -> CashMovement | None:
    row = conn.execute(
        "SELECT id, date, kind, amount, ref, note FROM cash_movements WHERE ref = ?",
        (ref,),
    ).fetchone()
    if row is None:
        return None
    return CashMovement(id=row[0], date=row[1], kind=row[2], amount=row[3], ref=row[4], note=row[5])
