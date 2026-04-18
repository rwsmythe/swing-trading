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
    # TOS statements carry a fill time per row. Keeping it lets reconcile_tos
    # sort fills by (date, time) before claim-tracking so attribution is
    # deterministic regardless of CSV row order (adversarial review Batch 3
    # Round 6 Major 2). Empty string when the export omits the TIME column.
    time: str = ""


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
        time_str = (row.get("Time") or row.get("TIME") or "").strip()
        if qty <= 0 or not date_str:
            continue
        out.append(TosFill(
            date=date_str, side=side, open_close=oc,
            ticker=ticker, qty=qty, price=price, time=time_str,
        ))
    return out


def reconcile_tos(
    *, db_path: Path, tos_text: str, price_tolerance: float = 0.01,
) -> ReconciliationReport:
    sections = parse_tos_export(tos_text)
    cash_rows = sections.get("Cash Balance", [])
    fills_rows = sections.get("Account Trade History", [])

    cash_candidates = extract_cash_movements(cash_rows)
    # Sort fills by (date, time) so claim-tracking is deterministic across
    # CSV row orderings: a TOS export where the afternoon row appears before
    # the morning row must still attribute the morning CLOSE to the morning
    # exit (adversarial review Batch 3 Round 6 Major 2). Stable sort preserves
    # original order when time strings tie.
    fills = sorted(extract_stock_fills(fills_rows), key=lambda f: (f.date, f.time))

    report = ReconciliationReport()
    conn = connect(db_path)
    try:
        for c in cash_candidates:
            if c.ref and find_by_ref(conn, c.ref) is not None:
                report.duplicate_cash_movements.append(c)
            else:
                report.new_cash_movements.append(c)

        within_batch_alloc: dict[int, int] = {}
        claimed_exit_ids: set[int] = set()
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
                # (date, qty, price) matches an UNCLAIMED recorded exit on a
                # CLOSED trade is already reconciled. When a current open
                # position exists for the ticker, we bound by its entry_date
                # (inclusive) so same-day close-then-reopen still routes the
                # morning close to history (Round 4 Major 2). Per-batch claim
                # tracking stops the same recorded exit from absorbing two
                # coincidentally matching CLOSE fills — the second falls
                # through to live allocation so a live same-day sale survives
                # (Round 5 Major 2).
                reference_entry_date = t.entry_date if t is not None else None
                claimed = _find_unclaimed_recorded_exit(
                    conn, ticker=f.ticker, date=f.date, qty=f.qty,
                    price=f.price, price_tolerance=price_tolerance,
                    on_or_before_date=reference_entry_date,
                    claimed=claimed_exit_ids,
                )
                if claimed is not None:
                    claimed_exit_ids.add(claimed)
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
    """True if a CLOSED trade exists matching (ticker, entry_date, qty, entry_price±tolerance)
    — i.e., an OPEN fill already reconciled in the journal before the trade closed out.

    Trades closed via the migration-0004 "erroneous INSERT" repair carry a
    trade_events note with a `correction` marker. Those synthetic closures
    represent trades that NEVER actually occurred, so they must not absorb
    real TOS OPEN fills as already-reconciled (adversarial review Batch 3
    Round 6 Major 1). Any closed trade with a correction note is excluded."""
    rows = conn.execute(
        """
        SELECT t.entry_price FROM trades t
        WHERE t.ticker=? AND t.entry_date=? AND t.initial_shares=? AND t.status='closed'
          AND NOT EXISTS (
            SELECT 1 FROM trade_events te
            WHERE te.trade_id = t.id
              AND te.event_type = 'note'
              AND json_extract(te.payload_json, '$.correction') IS NOT NULL
          )
        """,
        (ticker, date, qty),
    ).fetchall()
    return any(abs(r[0] - price) <= price_tolerance for r in rows)


def _find_unclaimed_recorded_exit(
    conn, *, ticker: str, date: str, qty: int, price: float,
    price_tolerance: float, on_or_before_date: str | None,
    claimed: set[int],
) -> int | None:
    """Return the id of an exit on a CLOSED trade that matches this fill by
    (exit_date, shares, exit_price±tolerance) AND hasn't been claimed yet in
    this reconciliation batch. `on_or_before_date` (inclusive) bounds which
    historical exits qualify — used to cover same-day close-then-reopen.

    Claim tracking matters at date granularity: if the same recorded exit
    coincidentally matches two CLOSE fills in one batch, only the first fill
    is treated as already_reconciled; subsequent fills fall through to live
    allocation so a live same-day sale isn't silently swallowed by a stale
    historical match (adversarial review Batch 3 Round 5 Major 2)."""
    sql = (
        "SELECT e.id, e.exit_price FROM exits e "
        "JOIN trades t ON t.id = e.trade_id "
        "WHERE t.ticker=? AND e.exit_date=? AND e.shares=? AND t.status='closed' "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM trade_events te "
        "  WHERE te.trade_id = t.id "
        "    AND te.event_type = 'note' "
        "    AND json_extract(te.payload_json, '$.correction') IS NOT NULL"
        ")"
    )
    params: list = [ticker, date, qty]
    if on_or_before_date is not None:
        sql += " AND e.exit_date <= ?"
        params.append(on_or_before_date)
    for exit_id, exit_price in conn.execute(sql, params).fetchall():
        if exit_id in claimed:
            continue
        if abs(exit_price - price) <= price_tolerance:
            return exit_id
    return None
