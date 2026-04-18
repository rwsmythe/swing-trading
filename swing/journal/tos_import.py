"""TOS Account Statement reconciliation.

Parser splits the multi-section export by labels. Extractors consume normalized
columns and yield CashMovement / TosFill records. `reconcile_tos` returns a
ReconciliationReport — caller (CLI) decides what to commit.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Iterable

from swing.data.db import connect
from swing.data.models import CashMovement
from swing.data.repos.cash import find_by_ref
from swing.data.repos.trades import find_any_open_trade, find_open_trade_by_match


_SECTION_LABELS = (
    "Cash Balance",
    "Account Trade History",
    "Account Order History",
    "Futures Statements",
    "Forex Statements",
    "Account Summary",
)


@dataclass(frozen=True)
class TosFill:
    date: str
    side: str
    open_close: str
    ticker: str
    qty: int
    price: float


@dataclass(frozen=True)
class ReconciliationReport:
    matched_fills: list[TosFill] = field(default_factory=list)
    unmatched_open_fills: list[TosFill] = field(default_factory=list)
    unmatched_close_fills: list[TosFill] = field(default_factory=list)
    price_mismatch_fills: list[TosFill] = field(default_factory=list)
    # Historical TOS statements may contain fills for trades that are ALREADY
    # fully reconciled in the journal (entry + exit both recorded). These aren't
    # "unmatched" in a problem sense — they're just re-imports the user can
    # ignore. Tracked separately so the CLI can report cleanly.
    already_reconciled_fills: list[TosFill] = field(default_factory=list)
    new_cash_movements: list[CashMovement] = field(default_factory=list)
    duplicate_cash_movements: list[CashMovement] = field(default_factory=list)


def parse_tos_export(text: str) -> dict[str, list[dict]]:
    """Split multi-section TOS export into section -> row-dicts."""
    lines = text.splitlines()
    sections: dict[str, list[dict]] = {}
    cur_label: str | None = None
    cur_buf: list[str] = []

    def flush():
        if cur_label is None or not cur_buf:
            return
        clean = [l for l in cur_buf if l.strip()]
        if not clean:
            return
        reader = csv.DictReader(StringIO("\n".join(clean)))
        sections[cur_label] = [dict(r) for r in reader]

    for line in lines:
        stripped = line.strip()
        if stripped in _SECTION_LABELS:
            flush()
            cur_label = stripped
            cur_buf = []
        elif stripped.startswith("#"):
            continue
        else:
            cur_buf.append(line)
    flush()
    return sections


def _parse_tos_amount(raw: str) -> float:
    s = (raw or "").strip()
    if s in ("", "--", "N/A"):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "").strip()
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if neg else v


def extract_cash_movements(rows: Iterable[dict]) -> list[CashMovement]:
    out: list[CashMovement] = []
    for row in rows:
        ttype = (row.get("TYPE") or "").strip()
        if ttype in ("", "BAL"):
            continue
        amount = _parse_tos_amount(row.get("AMOUNT", ""))
        if amount == 0.0:
            continue
        ref_raw = (row.get("REF #") or "").strip().strip('"').replace("=", "")
        ref = ref_raw or None
        kind = "deposit" if amount > 0 else "withdraw"
        out.append(CashMovement(
            id=None, date=(row.get("DATE") or "").strip(),
            kind=kind, amount=abs(amount), ref=ref,
            note=(row.get("DESCRIPTION") or "").strip() or None,
        ))
    return out


def extract_stock_fills(rows: Iterable[dict]) -> list[TosFill]:
    out: list[TosFill] = []
    for row in rows:
        spread = (row.get("Spread") or "").strip().upper()
        if spread not in ("", "STOCK"):
            continue
        exp = (row.get("Exp") or "").strip()
        if exp and exp != "--":
            continue
        ticker = (row.get("Symbol") or "").strip().upper()
        if not ticker:
            continue
        side = (row.get("Side") or "").strip().upper()
        pos = (row.get("Pos Effect") or "").strip().upper()
        if "OPEN" in pos:
            oc = "OPEN"
        elif "CLOSE" in pos:
            oc = "CLOSE"
        else:
            oc = "OPEN" if side == "BUY" else "CLOSE"
        try:
            qty = int(row.get("Qty") or row.get("QTY") or 0)
        except ValueError:
            continue
        price = _parse_tos_amount(row.get("Price") or row.get("PRICE") or "")
        date_str = (row.get("Date") or row.get("DATE") or "").strip()
        if qty <= 0 or not date_str:
            continue
        out.append(TosFill(
            date=date_str, side=side, open_close=oc,
            ticker=ticker, qty=qty, price=price,
        ))
    return out


def reconcile_tos(
    *, db_path: Path, tos_text: str, price_tolerance: float = 0.01,
) -> ReconciliationReport:
    sections = parse_tos_export(tos_text)
    cash_rows = sections.get("Cash Balance", [])
    fills_rows = sections.get("Account Trade History", [])

    cash_candidates = extract_cash_movements(cash_rows)
    fills = extract_stock_fills(fills_rows)

    report = ReconciliationReport()
    conn = connect(db_path)
    try:
        for c in cash_candidates:
            if c.ref and find_by_ref(conn, c.ref) is not None:
                report.duplicate_cash_movements.append(c)
            else:
                report.new_cash_movements.append(c)

        within_batch_alloc: dict[int, int] = {}
        for f in fills:
            if f.open_close == "OPEN":
                t = find_open_trade_by_match(
                    conn, ticker=f.ticker, entry_date=f.date,
                    initial_shares=f.qty,
                )
                if t is not None:
                    if abs(t.entry_price - f.price) > price_tolerance:
                        report.price_mismatch_fills.append(f)
                    else:
                        report.matched_fills.append(f)
                    continue
                # No open trade matched. Check historical (closed) trades —
                # re-importing an old TOS statement is a routine case, and
                # already-reconciled fills shouldn't be reported as unmatched.
                if _matches_closed_trade(
                    conn, ticker=f.ticker, date=f.date, qty=f.qty,
                    price=f.price, side="OPEN", price_tolerance=price_tolerance,
                ):
                    report.already_reconciled_fills.append(f)
                else:
                    report.unmatched_open_fills.append(f)
            else:
                t = find_any_open_trade(conn, ticker=f.ticker)
                # Historical re-import detection: a CLOSE fill whose
                # (date, qty, price) matches a recorded exit on a PRIOR closed
                # trade is already reconciled. When a current open position
                # exists for the ticker (closed-then-reopened case, Round 2
                # Major 2), only exits whose exit_date strictly precedes the
                # current open's entry_date count — this stops
                # _matches_recorded_exit from swallowing fills that should
                # allocate to the current open lot (Round 3 Major 2).
                reference_entry_date = t.entry_date if t is not None else None
                if _matches_recorded_exit(
                    conn, ticker=f.ticker, date=f.date, qty=f.qty,
                    price=f.price, price_tolerance=price_tolerance,
                    before_date=reference_entry_date,
                ):
                    report.already_reconciled_fills.append(f)
                    continue
                if t is None:
                    report.unmatched_close_fills.append(f)
                    continue
                sold_in_db = conn.execute(
                    "SELECT COALESCE(SUM(shares), 0) FROM exits WHERE trade_id = ?",
                    (t.id,),
                ).fetchone()[0]
                already_allocated = within_batch_alloc.get(t.id or 0, 0)
                cumulative = sold_in_db + already_allocated + f.qty
                if cumulative > t.initial_shares:
                    report.unmatched_close_fills.append(f)
                else:
                    report.matched_fills.append(f)
                    within_batch_alloc[t.id or 0] = already_allocated + f.qty
    finally:
        conn.close()
    return report


def _matches_closed_trade(
    conn, *, ticker: str, date: str, qty: int, price: float,
    side: str, price_tolerance: float,
) -> bool:
    """True if a closed trade exists matching (ticker, entry_date, qty, entry_price±tolerance)
    — i.e., an OPEN fill already reconciled in the journal before the trade closed out."""
    rows = conn.execute(
        """
        SELECT entry_price FROM trades
        WHERE ticker=? AND entry_date=? AND initial_shares=? AND status='closed'
        """,
        (ticker, date, qty),
    ).fetchall()
    return any(abs(r[0] - price) <= price_tolerance for r in rows)


def _matches_recorded_exit(
    conn, *, ticker: str, date: str, qty: int, price: float,
    price_tolerance: float, before_date: str | None = None,
) -> bool:
    """True if a recorded exit on a CLOSED trade matches this fill by
    (exit_date, shares, exit_price±tolerance). When before_date is provided,
    only count exits whose exit_date strictly precedes it — used to distinguish
    a historical re-import from a live allocation when a new open position
    exists for the same ticker."""
    sql = (
        "SELECT e.exit_price FROM exits e "
        "JOIN trades t ON t.id = e.trade_id "
        "WHERE t.ticker=? AND e.exit_date=? AND e.shares=? AND t.status='closed'"
    )
    params: list = [ticker, date, qty]
    if before_date is not None:
        sql += " AND e.exit_date < ?"
        params.append(before_date)
    rows = conn.execute(sql, params).fetchall()
    return any(abs(r[0] - price) <= price_tolerance for r in rows)
