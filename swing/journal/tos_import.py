"""TOS Account Statement reconciliation.

Parser splits the multi-section export by labels. Extractors consume normalized
columns and yield CashMovement / TosFill records. `reconcile_tos` returns a
ReconciliationReport — caller (CLI) decides what to commit.

Phase 9 Sub-bundle B (T-B.2) extends ``reconcile_tos`` with an optional
emitter seam: when a caller supplies ``run_id`` + ``emitter``, each
detected discrepancy is forwarded to the emitter callable so the service
layer (``swing/trades/reconciliation.py:run_tos_reconciliation``) can
persist ``reconciliation_discrepancies`` rows inside the outer BEGIN
IMMEDIATE transaction per spec §3.3.3. When ``run_id`` + ``emitter`` are
None, behavior matches the pre-refactor regression-clean baseline —
``ReconciliationReport`` is the canonical return shape and the existing
CLI invocation continues to work.

The function also accepts EITHER ``db_path`` (legacy path: function opens
its own conn) OR ``conn`` (Phase 9 service-layer path: caller owns the
conn + the surrounding transaction).
"""
from __future__ import annotations

import csv
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from io import StringIO
from pathlib import Path

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
    # Real-world Schwab/TOS multi-day exports include Equities and Profits
    # and Losses sections AFTER Account Trade History. Without recognizing
    # them as section boundaries, parse_tos_export accumulates their rows
    # into the trailing buffer of the previous label — inflating any
    # row-count diagnostic and feeding non-fill rows into
    # extract_stock_fills (which then filters them by Spread != 'STOCK',
    # but the row-count signal for the operator is misleading).
    "Equities",
    "Profits and Losses",
    # Crypto Statements is the canonical label for the quoted, bank-name-
    # bearing header line in the real-world export. `_section_label_for_line`
    # bridges the volatile line text to this stable canonical name; the
    # canonical name belongs in the recognized-section list so it does not
    # diverge from the registry of valid labels.
    "Crypto Statements",
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
class FillDecision:
    """Per-fill reconciliation outcome with journal-vs-TOS price visibility.

    Populated alongside the matched/unmatched/price_mismatch/already_reconciled
    bucket lists so `--verbose` CLI output can surface the journal entry_price
    that participated in each routing decision. The operator-actionable
    invariant — 'reconciliation checks existence AND correct values' — needs
    this view: existence-only matching cannot show whether the journal price
    agrees with the broker fill.

    `journal_price` is set for OPEN matched / OPEN price_mismatch decisions
    (where a single trade-row entry_price drove the routing). It is None for
    CLOSE-side matches via cumulative-allocation, unmatched fills, and
    already_reconciled cases — those don't compare against a single journal
    entry_price.
    """
    fill: TosFill
    outcome: str  # matched | price_mismatch | unmatched_open | unmatched_close | already_reconciled
    journal_price: float | None
    tolerance: float


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
    # Parallel detail list — one entry per processed fill in encounter order
    # — for `swing tos-import --verbose`. Always populated so CLI verbose
    # mode never has to second-guess existence; default CLI output ignores
    # it so byte-identical default behavior is preserved.
    fill_decisions: list[FillDecision] = field(default_factory=list)


def _section_label_for_line(stripped: str) -> str | None:
    """Return the canonical section label this line opens, or None.

    Schwab/TOS multi-day exports CSV-quote any header that contains an
    internal comma (the Crypto Statements header wraps the bank name and
    its trailing comma in double quotes — `\"Crypto # (Crypto offered by
    Charles Schwab Premier Bank, SSB) Statements\"`). The bank-name
    substring varies; collapse all such variants to a single canonical
    `Crypto Statements` label by pattern. All other section labels are
    bare strings — but quote-stripping is harmless and protects against
    future Schwab/TOS quoting drift.
    """
    s = stripped.strip('"').strip()
    if not s:
        return None
    if s in _SECTION_LABELS:
        return s
    if s.startswith("Crypto") and s.endswith("Statements"):
        return "Crypto Statements"
    return None


def parse_tos_export(text: str) -> dict[str, list[dict]]:
    """Split multi-section TOS export into section -> row-dicts."""
    lines = text.splitlines()
    sections: dict[str, list[dict]] = {}
    cur_label: str | None = None
    cur_buf: list[str] = []

    def flush():
        if cur_label is None or not cur_buf:
            return
        clean = [line for line in cur_buf if line.strip()]
        if not clean:
            return
        reader = csv.DictReader(StringIO("\n".join(clean)))
        sections[cur_label] = [dict(r) for r in reader]

    for line in lines:
        stripped = line.strip()
        section_label = _section_label_for_line(stripped)
        if section_label is not None:
            flush()
            cur_label = section_label
            cur_buf = []
        elif stripped.startswith("#"):
            continue
        else:
            cur_buf.append(line)
    flush()
    return sections


def _normalize_date(raw: str) -> str:
    """Normalize a TOS-export date string to ISO YYYY-MM-DD.

    Real-world Schwab/TOS exports emit dates as `M/D/YY` (e.g. `5/8/26`);
    the synthetic fixture uses ISO `YYYY-MM-DD`. `reconcile_tos` matches
    fills against journal `entry_date`, which is stored ISO — without
    normalization the M/D/YY-formatted real-world fills never match an
    ISO-formatted journal row even when the underlying date is identical.

    Returns the input unchanged if it does not match a known format, so
    unexpected shapes propagate to the caller rather than silently
    masquerading as a valid date.
    """
    s = (raw or "").strip()
    if not s:
        return s
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        pass
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return s


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
    """Extract deposits/withdrawals from the Cash Balance section.

    Skips:
      - empty TYPE (e.g., the TOTAL row at the bottom)
      - BAL (start-of-day balance line)
      - TRD (trade settlement — already tracked via Account Trade History
        → trades table; importing it here double-decrements cash. Surfaced
        2026-04-30 against the 4/30 Schwab/TOS export where a CC purchase
        appeared as a -$134.85 row under TYPE=TRD).

    Note: this is a denylist, not an allowlist. Future TOS TYPE codes
    that are also non-cash-flow events (and aren't TRD/BAL) would
    silently misclassify here. Allowlist hardening deferred until
    additional drift surfaces — keeps known cash types (DEP, WD, CRC,
    INT, DIV, JNL, FEE, ADJ, etc.) flowing through as before without
    risk of silently dropping a legitimate cash movement.
    """
    out: list[CashMovement] = []
    for row in rows:
        ttype = (row.get("TYPE") or "").strip()
        if ttype in ("", "BAL", "TRD"):
            continue
        amount = _parse_tos_amount(row.get("AMOUNT", ""))
        if amount == 0.0:
            continue
        # TOS REF #s arrive in Excel-style "force-as-text" form, e.g.
        # `="1006193131983"`. Strip the `=` sigil first, then any
        # surrounding quotes — order matters: the prior `.strip('"')`
        # before `.replace("=", "")` left the leading quote intact
        # because `=` was at the boundary instead of `"`.
        ref_raw = (row.get("REF #") or "").strip().strip("=").strip('"')
        ref = ref_raw or None
        kind = "deposit" if amount > 0 else "withdraw"
        out.append(CashMovement(
            id=None, date=(row.get("DATE") or "").strip(),
            kind=kind, amount=abs(amount), ref=ref,
            note=(row.get("DESCRIPTION") or "").strip() or None,
        ))
    return out


def extract_stock_fills(
    rows: Iterable[dict], *, _skip_log: dict[str, int] | None = None,
) -> list[TosFill]:
    """Extract STOCK fills from the Account Trade History section.

    Two real-world export shapes are supported:

    1. Synthetic / pre-2026-05 shape — separate `DATE`/`Date` and
       `TIME`/`Time` columns; unsigned `Qty`.
    2. Schwab/TOS 2026-era multi-day Account Statement export — single
       combined `Exec Time` column (e.g. `5/8/26 06:52:18`); signed `Qty`
       (`+7` for BUY, `-3` for SELL); MDY-2yr dates.

    Pre-fix the parser only handled shape (1). Against shape (2) every row
    failed the `date_str` predicate (no `Date` column in the dict) AND the
    SELL fills additionally tripped the `qty <= 0` filter (`int('-3')` is
    -3) — net result was a silent zero-fill output the operator surfaced
    on 2026-05-08. Fix: prefer `Exec Time` (split on first space), fall
    back to `Date`+`Time`; normalize the date to ISO; take `abs(qty)` so
    the side comes from the canonical `Side`/`Pos Effect` columns rather
    than the qty sign.
    """
    def _bump(reason: str) -> None:
        if _skip_log is not None:
            _skip_log[reason] = _skip_log.get(reason, 0) + 1

    out: list[TosFill] = []
    for row in rows:
        spread = (row.get("Spread") or "").strip().upper()
        if spread not in ("", "STOCK"):
            _bump("non_stock_spread")
            continue
        exp = (row.get("Exp") or "").strip()
        if exp and exp != "--":
            _bump("option_with_expiry")
            continue
        ticker = (row.get("Symbol") or "").strip().upper()
        if not ticker:
            _bump("empty_ticker")
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
            # `int('+7')` -> 7, `int('-3')` -> -3; abs() so the SELL fill
            # survives the qty-positivity check below. Side direction is
            # carried by the `Side` / `Pos Effect` columns (canonical).
            qty = abs(int(row.get("Qty") or row.get("QTY") or 0))
        except ValueError:
            _bump("qty_parse_error")
            continue
        price = _parse_tos_amount(row.get("Price") or row.get("PRICE") or "")
        # Account Trade History on multi-day exports collapses date+time
        # into a single `Exec Time` cell (`M/D/YY HH:MM:SS`). Prefer that
        # when present; fall back to legacy split columns otherwise.
        exec_time = (row.get("Exec Time") or row.get("EXEC TIME") or "").strip()
        if exec_time:
            parts = exec_time.split(" ", 1)
            date_str = parts[0]
            time_str = parts[1].strip() if len(parts) > 1 else ""
        else:
            date_str = (row.get("Date") or row.get("DATE") or "").strip()
            time_str = (row.get("Time") or row.get("TIME") or "").strip()
        date_str = _normalize_date(date_str)
        if qty <= 0:
            # Post-`abs()` qty is non-negative — `qty <= 0` reduces to
            # `qty == 0`. Name the reason accordingly so the verbose
            # operator-facing diagnostic isn't misleading (Codex R2 Minor 2).
            _bump("qty_zero")
            continue
        if not date_str:
            _bump("empty_date")
            continue
        out.append(TosFill(
            date=date_str, side=side, open_close=oc,
            ticker=ticker, qty=qty, price=price, time=time_str,
        ))
    return out


def reconcile_tos(
    *,
    db_path: Path | None = None,
    tos_text: str,
    price_tolerance: float = 0.01,
    conn: sqlite3.Connection | None = None,
    run_id: int | None = None,
    emitter: Callable[..., int] | None = None,
) -> ReconciliationReport:
    """Reconcile a TOS Account Statement against the journal.

    Args:
        db_path: legacy path — function opens its own connection. Mutually
            exclusive with ``conn``.
        tos_text: full TOS CSV content (multi-section export).
        price_tolerance: dollar threshold for price-mismatch detection;
            strict-greater-than convention at the comparison site (existing
            ``swing/journal/tos_import.py:365``). LOCKED at 0.01 USD default
            for V1 per plan T-B.3 (Codex R2 Major #3 fix banked in plan §A).
        conn: Phase 9 service-layer path — caller owns the conn AND the
            surrounding ``BEGIN IMMEDIATE`` transaction per spec §3.3.3.
            Mutually exclusive with ``db_path``.
        run_id: parent ``reconciliation_runs.run_id`` for the emit seam.
            Required when ``emitter`` is provided; harmless when both None.
        emitter: callable invoked once per detected discrepancy. Signature:
            ``emitter(*, discrepancy_type, run_id, **fields) -> int``.
            Returns the inserted ``discrepancy_id`` (or any int — the
            return value is currently informational; future readers may
            use it for cross-discrepancy linking). When None, no emit
            happens — legacy regression-clean behavior is preserved.

    Returns:
        ``ReconciliationReport`` dataclass with the matched / unmatched /
        price_mismatch / already_reconciled bucket lists + cash movement
        lists + per-fill ``FillDecision`` trail. Return shape is preserved
        from the pre-refactor baseline.

    The emitter is Phase 9's seam between detection and persistence. T-B.2
    establishes the seam; T-B.3..T-B.6 wire individual discrepancy types
    through it.
    """
    if (db_path is None) == (conn is None):
        raise ValueError(
            "reconcile_tos requires exactly one of {db_path, conn}; got "
            f"db_path={db_path!r}, conn={conn!r}"
        )
    if emitter is not None and run_id is None:
        raise ValueError("emitter requires run_id (parent reconciliation_runs row)")

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
    owns_conn = conn is None
    if owns_conn:
        conn = connect(db_path)
    try:
        for c in cash_candidates:
            if c.ref and find_by_ref(conn, c.ref) is not None:
                report.duplicate_cash_movements.append(c)
            else:
                report.new_cash_movements.append(c)

        within_batch_alloc: dict[int, int] = {}
        claimed_exit_ids: set[int] = set()

        def _record(f: TosFill, outcome: str, journal_price: float | None) -> None:
            report.fill_decisions.append(FillDecision(
                fill=f, outcome=outcome,
                journal_price=journal_price, tolerance=price_tolerance,
            ))

        for f in fills:
            if f.open_close == "OPEN":
                t = find_open_trade_by_match(
                    conn, ticker=f.ticker, entry_date=f.date,
                    initial_shares=f.qty,
                )
                if t is not None:
                    if abs(t.entry_price - f.price) > price_tolerance:
                        report.price_mismatch_fills.append(f)
                        _record(f, "price_mismatch", t.entry_price)
                    else:
                        report.matched_fills.append(f)
                        _record(f, "matched", t.entry_price)
                    continue
                # No open trade matched. Check historical (closed) trades —
                # re-importing an old TOS statement is a routine case, and
                # already-reconciled fills shouldn't be reported as unmatched.
                if _matches_closed_trade(
                    conn, ticker=f.ticker, date=f.date, qty=f.qty,
                    price=f.price, side="OPEN", price_tolerance=price_tolerance,
                ):
                    report.already_reconciled_fills.append(f)
                    _record(f, "already_reconciled", None)
                else:
                    report.unmatched_open_fills.append(f)
                    _record(f, "unmatched_open", None)
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
                    _record(f, "already_reconciled", None)
                    continue
                if t is None:
                    report.unmatched_close_fills.append(f)
                    _record(f, "unmatched_close", None)
                    continue
                # Phase 7 B.9: exits table dropped (migration 0014). Sum
                # quantities of all non-entry fills (trim/exit/stop) — that
                # equals "shares already sold against this trade" under the
                # long-only convention.
                sold_in_db = conn.execute(
                    "SELECT COALESCE(SUM(quantity), 0) FROM fills "
                    "WHERE trade_id = ? AND action != 'entry'",
                    (t.id,),
                ).fetchone()[0]
                already_allocated = within_batch_alloc.get(t.id or 0, 0)
                cumulative = sold_in_db + already_allocated + f.qty
                if cumulative > t.initial_shares:
                    report.unmatched_close_fills.append(f)
                    _record(f, "unmatched_close", None)
                else:
                    report.matched_fills.append(f)
                    _record(f, "matched", None)
                    within_batch_alloc[t.id or 0] = already_allocated + f.qty
    finally:
        if owns_conn:
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
    # Phase 7 B.9: status column dropped (migration 0014). closed-or-reviewed
    # are both terminal lifecycle states; either qualifies an OPEN fill as
    # already-reconciled against the matching closed trade.
    rows = conn.execute(
        """
        SELECT t.entry_price FROM trades t
        WHERE t.ticker=? AND t.entry_date=? AND t.initial_shares=?
          AND t.state IN ('closed', 'reviewed')
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
    # Phase 7 B.9: exits table dropped — read non-entry fills directly.
    # `e.exit_date` mapped to YYYY-MM-DD prefix of fills.fill_datetime
    # (which is ISO-8601 'YYYY-MM-DDTHH:MM:SS' per migration 0014 backfill).
    # `e.shares`/`e.exit_price` map to fills.quantity/fills.price.
    # `t.status='closed'` becomes the terminal-state predicate
    # (closed-or-reviewed) per Sub-B B.7 vocab.
    sql = (
        "SELECT f.fill_id, f.price FROM fills f "
        "JOIN trades t ON t.id = f.trade_id "
        "WHERE t.ticker=? AND substr(f.fill_datetime, 1, 10)=? "
        "  AND f.quantity=? AND f.action != 'entry' "
        "  AND t.state IN ('closed', 'reviewed') "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM trade_events te "
        "  WHERE te.trade_id = t.id "
        "    AND te.event_type = 'note' "
        "    AND json_extract(te.payload_json, '$.correction') IS NOT NULL"
        ")"
    )
    params: list = [ticker, date, qty]
    if on_or_before_date is not None:
        sql += " AND substr(f.fill_datetime, 1, 10) <= ?"
        params.append(on_or_before_date)
    for fill_id, fill_price in conn.execute(sql, params).fetchall():
        if fill_id in claimed:
            continue
        if abs(fill_price - price) <= price_tolerance:
            return fill_id
    return None
