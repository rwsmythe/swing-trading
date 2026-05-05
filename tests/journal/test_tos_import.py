"""TOS reconciliation parser + matcher."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.journal.tos_import import (
    parse_tos_export, reconcile_tos, ReconciliationReport,
    extract_cash_movements, extract_stock_fills,
)


FIXTURE = Path(__file__).parent.parent / "fixtures" / "tos" / "synthetic-tos.csv"


def _seed_entry(
    conn: sqlite3.Connection, *, ticker: str, entry_date: str,
    entry_price: float, shares: int, initial_stop: float,
) -> int:
    """Insert a trade row + entry-fill bypassing the Sub-B B.1 pre-trade
    required-fields gate (these reconciliation tests don't exercise the
    entry-form validator). Mirrors tests/trades/test_exit.py's
    _seed_active_trade pattern: insert_trade_with_event in 'entered' state
    + an entry-fill so the current_size denorm is correct.
    """
    event_ts = f"{entry_date}T09:30:00"
    trade = Trade(
        id=None, ticker=ticker, entry_date=entry_date,
        entry_price=entry_price, initial_shares=shares,
        initial_stop=initial_stop, current_stop=initial_stop,
        state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at=event_ts,
    )
    with conn:
        tid = insert_trade_with_event(
            conn, trade, event_ts=event_ts, rationale="seed",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=tid,
                fill_datetime=event_ts, action="entry",
                quantity=float(shares), price=entry_price,
            ),
            event_ts=event_ts,
        )
    return tid


def _seed_exit(
    conn: sqlite3.Connection, *, trade_id: int, exit_date: str,
    exit_price: float, shares: int, reason: str = "target",
) -> None:
    """Insert a non-entry fill + transition state to closed when fully
    exited. Skips the exit-service's typed-reason / state-machine plumbing
    for these reconciliation tests; the matcher reads fills + state.
    """
    event_ts = f"{exit_date}T15:30:00"
    with conn:
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=trade_id,
                fill_datetime=event_ts, action="exit",
                quantity=float(shares), price=exit_price, reason=reason,
            ),
            event_ts=event_ts,
        )
        row = conn.execute(
            "SELECT initial_shares, "
            "  COALESCE((SELECT SUM(quantity) FROM fills "
            "            WHERE trade_id = ? AND action != 'entry'), 0) "
            "FROM trades WHERE id = ?",
            (trade_id, trade_id),
        ).fetchone()
        if row is not None and row[1] >= row[0]:
            conn.execute(
                "UPDATE trades SET state='closed' WHERE id=?", (trade_id,),
            )


def test_parse_extracts_cash_section():
    sections = parse_tos_export(FIXTURE.read_text(encoding="utf-8"))
    assert "Cash Balance" in sections
    cash_rows = sections["Cash Balance"]
    assert len(cash_rows) == 2


def test_extract_cash_movements_handles_amount_formats():
    text = FIXTURE.read_text(encoding="utf-8")
    sections = parse_tos_export(text)
    movements = list(extract_cash_movements(sections["Cash Balance"]))
    assert len(movements) == 2
    by_kind = {m.kind for m in movements}
    assert by_kind == {"deposit", "withdraw"}
    deposit = next(m for m in movements if m.kind == "deposit")
    assert deposit.amount == 500.0
    assert deposit.ref == "DEP-001"
    withdraw = next(m for m in movements if m.kind == "withdraw")
    assert withdraw.amount == 100.0


def test_extract_cash_movements_skips_trade_rows_and_accepts_crc():
    """TOS exports include trade settlements in the Cash Balance section as
    negative-amount rows with TYPE='TRD'. These must NOT be classified as
    cash movements — the trade is already tracked via the Account Trade
    History section + the trades table; importing it here would
    double-decrement equity (operator-surfaced 2026-04-30 against the
    4/30 statement importing the CC purchase as a withdrawal).

    Discriminator: with the bug present, a TRD row's negative amount
    classifies as 'withdraw' and shows up in the extracted list
    alongside the legitimate CRC (cash-receipt / transfer-in) deposit.
    With the fix, only the CRC row imports.

    Real-world fixture shape — mirrors the 9-column header the operator's
    Schwab/TOS export emits (Misc Fees + Commissions & Fees columns
    present), unlike the simpler 7-column synthetic fixture. If
    extract_cash_movements grew column-position sensitivity (instead of
    DictReader name-keyed access), this test would catch the regression.
    """
    csv_text = (
        "Cash Balance\n"
        "\n"
        "DATE,TIME,TYPE,REF #,DESCRIPTION,Misc Fees,Commissions & Fees,AMOUNT,BALANCE\n"
        "4/29/26,19:00:00,BAL,,Cash balance at start of day 30.04 CST,,,,1002.39\n"
        '4/30/26,06:18:31,TRD,="1006193131983",BOT +5 CC @26.9699,,,-134.85,867.54\n'
        '4/29/26,20:49:54,CRC,="117872135649","Tfr from external bank 100.0 US$",,,100.00,967.54\n'
    )
    sections = parse_tos_export(csv_text)
    movements = list(extract_cash_movements(sections["Cash Balance"]))
    # Exactly the CRC deposit; TRD must be filtered.
    assert len(movements) == 1, (
        f"expected 1 movement (CRC deposit only); got {len(movements)}: "
        f"{[(m.kind, m.amount, m.note) for m in movements]}. With the bug "
        f"present, the TRD row's -$134.85 amount classifies as a "
        f"$134.85 withdrawal, doubling the cash-flow record (the trade "
        f"is also tracked via Account Trade History → trades table)."
    )
    m = movements[0]
    assert m.kind == "deposit", f"expected deposit (CRC transfer-in); got {m.kind!r}"
    assert m.amount == 100.0, f"expected 100.00; got {m.amount}"
    assert m.ref == "117872135649", f"expected CRC ref; got {m.ref!r}"


def test_extract_stock_fills_filters_options():
    text = FIXTURE.read_text(encoding="utf-8")
    sections = parse_tos_export(text)
    fills = list(extract_stock_fills(sections["Account Trade History"]))
    assert len(fills) == 2
    assert all(f.ticker == "AAPL" for f in fills)
    assert {f.open_close for f in fills} == {"OPEN", "CLOSE"}


def test_reconcile_reports_mismatched_and_dedup(tmp_path: Path):
    from swing.data.db import ensure_schema
    db = tmp_path / "swing.db"
    ensure_schema(db).close()

    text = FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    assert isinstance(report, ReconciliationReport)
    assert len(report.new_cash_movements) == 2
    assert len(report.unmatched_open_fills) == 1
    assert len(report.unmatched_close_fills) == 1
    assert report.matched_fills == []


def test_reconcile_matches_close_to_prior_open_trade(tmp_path: Path):
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()

    conn = sqlite3.connect(db)
    try:
        _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-15",
            entry_price=180.0, shares=5, initial_stop=170.0,
        )
    finally:
        conn.close()

    text = FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    assert len(report.matched_fills) == 2
    assert len(report.unmatched_close_fills) == 0


def test_reconcile_within_batch_cumulative_overfill(tmp_path: Path):
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-15",
            entry_price=180.0, shares=5, initial_stop=170.0,
        )
    finally:
        conn.close()

    tos_text = (
        "Cash Balance\n\n"
        "DATE,TIME,TYPE,REF #,DESCRIPTION,AMOUNT,BALANCE\n\n"
        "Account Trade History\n\n"
        "Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,Net Price,Order Type,DATE,TIME\n"
        "STOCK,SELL,3,TO CLOSE,AAPL,--,--,--,$190.00,--,LMT,2026-04-22,15:30:00\n"
        "STOCK,SELL,3,TO CLOSE,AAPL,--,--,--,$191.00,--,LMT,2026-04-23,15:30:00\n"
    )
    report = reconcile_tos(db_path=db, tos_text=tos_text)
    assert len(report.matched_fills) == 1
    assert len(report.unmatched_close_fills) == 1


def test_reconcile_close_overfill_flagged(tmp_path: Path):
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-15",
            entry_price=180.0, shares=3, initial_stop=170.0,
        )
    finally:
        conn.close()
    text = FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    assert len(report.unmatched_open_fills) == 1
    assert len(report.unmatched_close_fills) == 1


def test_reconcile_closed_then_reopened_ticker_routes_close_to_history(tmp_path: Path):
    """Adversarial review Batch 3 Round 2 Major 2: a historical CLOSE fill for
    an old closed trade must be recognized as already-reconciled even when a
    NEW open position exists for the same ticker. The prior code bound CLOSE
    fills to find_any_open_trade first and only fell back to _matches_recorded_exit
    when no open trade existed, misallocating historical closes to the new
    position whenever a ticker was closed-then-reopened."""
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        tid = _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-01",
            entry_price=170.0, shares=5, initial_stop=160.0,
        )
        _seed_exit(
            conn, trade_id=tid, exit_date="2026-04-10",
            exit_price=175.0, shares=5,
        )
        # Reopen the ticker at a different price/date.
        _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-15",
            entry_price=180.0, shares=5, initial_stop=170.0,
        )
    finally:
        conn.close()

    # TOS statement contains ONLY the OLD exit (already recorded against the
    # first, now-closed trade). The new open position at $180 is a red herring.
    tos_text = (
        "Cash Balance\n\n"
        "DATE,TIME,TYPE,REF #,DESCRIPTION,AMOUNT,BALANCE\n\n"
        "Account Trade History\n\n"
        "Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,Net Price,Order Type,DATE,TIME\n"
        "STOCK,SELL,5,TO CLOSE,AAPL,--,--,--,$175.00,--,LMT,2026-04-10,15:30:00\n"
    )
    report = reconcile_tos(db_path=db, tos_text=tos_text)
    assert len(report.already_reconciled_fills) == 1
    assert len(report.matched_fills) == 0
    assert len(report.unmatched_close_fills) == 0


def test_reconcile_same_day_close_then_reopen_routes_close_to_history(tmp_path: Path):
    """Adversarial review Batch 3 Round 4 Major 2: a same-day round trip
    (open + close morning, reopen afternoon — all on one calendar date) must
    still recognize a re-imported TOS CLOSE fill as already_reconciled. The
    on_or_before_date bound uses `<=` rather than `<` because date-granularity
    storage can't distinguish morning from afternoon; the t.status='closed'
    join filter still prevents live allocations on the current open trade from
    being misclassified."""
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        # Morning: open + close (same date).
        tid = _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-17",
            entry_price=180.0, shares=5, initial_stop=170.0,
        )
        _seed_exit(
            conn, trade_id=tid, exit_date="2026-04-17",
            exit_price=182.0, shares=5,
        )
        # Afternoon: reopen same ticker, same calendar date.
        _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-17",
            entry_price=181.0, shares=5, initial_stop=171.0,
        )
    finally:
        conn.close()

    # Re-import the morning CLOSE only.
    tos_text = (
        "Cash Balance\n\n"
        "DATE,TIME,TYPE,REF #,DESCRIPTION,AMOUNT,BALANCE\n\n"
        "Account Trade History\n\n"
        "Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,Net Price,Order Type,DATE,TIME\n"
        "STOCK,SELL,5,TO CLOSE,AAPL,--,--,--,$182.00,--,LMT,2026-04-17,11:30:00\n"
    )
    report = reconcile_tos(db_path=db, tos_text=tos_text)
    assert len(report.already_reconciled_fills) == 1
    assert len(report.matched_fills) == 0
    assert len(report.unmatched_close_fills) == 0


def test_reconcile_second_matching_close_falls_through_to_live_allocation(tmp_path: Path):
    """Adversarial review Batch 3 Round 5 Major 2: if two CLOSE fills share
    (ticker, date, qty, price) with a single recorded historical exit, only
    the first claims the exit as already_reconciled. The second falls through
    to live allocation against the current open position so a live same-day
    sale cannot be silently swallowed by a coincidental historical match."""
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        # Morning closed round-trip at $182 x 5sh on 2026-04-17.
        tid = _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-17",
            entry_price=180.0, shares=5, initial_stop=170.0,
        )
        _seed_exit(
            conn, trade_id=tid, exit_date="2026-04-17",
            exit_price=182.0, shares=5,
        )
        # Afternoon reopen, 10 shares so it can absorb a live 5-share sale.
        _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-17",
            entry_price=181.0, shares=10, initial_stop=171.0,
        )
    finally:
        conn.close()

    # Two CLOSE fills that BOTH happen to match the morning exit signature.
    # The first claims the historical exit; the second must allocate live.
    tos_text = (
        "Cash Balance\n\n"
        "DATE,TIME,TYPE,REF #,DESCRIPTION,AMOUNT,BALANCE\n\n"
        "Account Trade History\n\n"
        "Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,Net Price,Order Type,DATE,TIME\n"
        "STOCK,SELL,5,TO CLOSE,AAPL,--,--,--,$182.00,--,LMT,2026-04-17,11:30:00\n"
        "STOCK,SELL,5,TO CLOSE,AAPL,--,--,--,$182.00,--,LMT,2026-04-17,14:30:00\n"
    )
    report = reconcile_tos(db_path=db, tos_text=tos_text)
    assert len(report.already_reconciled_fills) == 1
    assert len(report.matched_fills) == 1
    assert len(report.unmatched_close_fills) == 0


def test_reconcile_ignores_correction_closed_trades_for_open_matching(tmp_path: Path):
    """Adversarial review Batch 3 Round 6 Major 1: a trade that was closed via
    the preflight repair path (UPDATE status='closed' + trade_events.note with
    json_extract payload_json $.correction IS NOT NULL) must NOT absorb real
    TOS OPEN fills as already_reconciled — no real fill ever occurred for that
    row."""
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        # Simulate an erroneous row repaired via the preflight guidance:
        # state='closed' + paired correction note, one transaction.
        # B.9: 'status' column dropped (migration 0014); use 'state' + the
        # NOT-NULL Phase 7 lifecycle columns (trade_origin,
        # pre_trade_locked_at, current_size).
        with conn:
            conn.execute(
                """INSERT INTO trades (ticker, entry_date, entry_price, initial_shares,
                   initial_stop, current_stop, state, watchlist_entry_target,
                   watchlist_initial_stop, notes,
                   trade_origin, pre_trade_locked_at, current_size)
                   VALUES ('AAPL', '2026-04-15', 180.0, 5, 170.0, 170.0, 'closed',
                           NULL, NULL, NULL,
                           'manual_off_pipeline', '2026-04-15T09:30:00', 0)"""
            )
            trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO trade_events (trade_id, ts, event_type, payload_json)
                   VALUES (?, ?, 'note',
                   json_object('correction', 'erroneous duplicate'))""",
                (trade_id, "2026-04-18T10:00:00"),
            )
    finally:
        conn.close()

    # TOS carries only the OPEN side — fixture's "AAPL 2026-04-15 $180 x 5sh"
    # which would normally land in already_reconciled against a legitimately
    # closed trade but must NOT be absorbed by the corrected one.
    tos_text = (
        "Cash Balance\n\n"
        "DATE,TIME,TYPE,REF #,DESCRIPTION,AMOUNT,BALANCE\n\n"
        "Account Trade History\n\n"
        "Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,Net Price,Order Type,DATE,TIME\n"
        "STOCK,BUY,5,TO OPEN,AAPL,--,--,--,$180.00,--,LMT,2026-04-15,09:30:00\n"
    )
    report = reconcile_tos(db_path=db, tos_text=tos_text)
    assert len(report.already_reconciled_fills) == 0
    assert len(report.unmatched_open_fills) == 1


def test_reconcile_claim_order_is_deterministic_across_csv_ordering(tmp_path: Path):
    """Adversarial review Batch 3 Round 6 Major 2: claim tracking must not be
    sensitive to CSV row ordering. The morning CLOSE (11:30) must claim the
    historical exit regardless of whether the afternoon row (14:30) appears
    first in the TOS export — reconcile_tos sorts fills by (date, time) before
    processing."""
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        tid = _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-17",
            entry_price=180.0, shares=5, initial_stop=170.0,
        )
        _seed_exit(
            conn, trade_id=tid, exit_date="2026-04-17",
            exit_price=182.0, shares=5,
        )
        _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-17",
            entry_price=181.0, shares=10, initial_stop=171.0,
        )
    finally:
        conn.close()

    # CSV intentionally reverses chronological order (14:30 row before 11:30).
    # After (date, time) sort, the 11:30 row processes first and claims the
    # historical exit; the 14:30 row falls through to live allocation.
    tos_text = (
        "Cash Balance\n\n"
        "DATE,TIME,TYPE,REF #,DESCRIPTION,AMOUNT,BALANCE\n\n"
        "Account Trade History\n\n"
        "Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,Net Price,Order Type,DATE,TIME\n"
        "STOCK,SELL,5,TO CLOSE,AAPL,--,--,--,$182.00,--,LMT,2026-04-17,14:30:00\n"
        "STOCK,SELL,5,TO CLOSE,AAPL,--,--,--,$182.00,--,LMT,2026-04-17,11:30:00\n"
    )
    report = reconcile_tos(db_path=db, tos_text=tos_text)
    assert len(report.already_reconciled_fills) == 1
    assert len(report.matched_fills) == 1
    assert len(report.unmatched_close_fills) == 0


def test_reconcile_does_not_swallow_fill_that_matches_current_open_lot(tmp_path: Path):
    """Adversarial review Batch 3 Round 3 Major 2: _matches_recorded_exit must
    not over-classify a CLOSE fill as already_reconciled when the recorded exit
    actually belongs to the CURRENT open trade's lot. When a prior closed trade
    shares (ticker, date, qty, price) coincidence with a recorded exit on the
    current open trade, the fill should allocate to the current open lot, not
    be silently swallowed into already_reconciled_fills."""
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        # Open trade (the one the CLOSE fill should allocate to).
        tid = _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-15",
            entry_price=180.0, shares=5, initial_stop=170.0,
        )
        # Partial exit already recorded against the current open trade.
        # If the reorder blindly matched any recorded exit, a re-imported
        # TOS CLOSE at the same date/qty/price would be swallowed.
        _seed_exit(
            conn, trade_id=tid, exit_date="2026-04-22",
            exit_price=190.0, shares=3,
        )
    finally:
        conn.close()

    # Re-importing the same CLOSE a second time: the recorded exit belongs to
    # the CURRENT open trade, not a prior closed one. The fill's date
    # (2026-04-22) is after the current open's entry (2026-04-15), so the
    # before_date filter excludes the match and the fill should attempt to
    # allocate against the current open trade (where it overfills — only 2
    # shares remain — and lands in unmatched_close_fills). It must NOT land in
    # already_reconciled_fills.
    tos_text = (
        "Cash Balance\n\n"
        "DATE,TIME,TYPE,REF #,DESCRIPTION,AMOUNT,BALANCE\n\n"
        "Account Trade History\n\n"
        "Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,Net Price,Order Type,DATE,TIME\n"
        "STOCK,SELL,3,TO CLOSE,AAPL,--,--,--,$190.00,--,LMT,2026-04-22,15:30:00\n"
    )
    report = reconcile_tos(db_path=db, tos_text=tos_text)
    # Live exit on current open lot — exceeds remaining-shares budget on
    # repeated import, so it flags as unmatched rather than already-reconciled.
    assert len(report.already_reconciled_fills) == 0
    # 3 + 3 = 6 > initial_shares=5, so the second allocation overflows.
    assert len(report.unmatched_close_fills) == 1


def test_reconcile_already_closed_trade_reports_as_already_reconciled(tmp_path: Path):
    """Adversarial review Batch 3 Major 1: re-importing a TOS statement after the
    trade is already fully reconciled (entry + exit both recorded) must NOT flag
    the fills as unmatched — instead, mark them as already_reconciled."""
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        tid = _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-15",
            entry_price=180.0, shares=5, initial_stop=170.0,
        )
        _seed_exit(
            conn, trade_id=tid, exit_date="2026-04-22",
            exit_price=190.0, shares=5,
        )
    finally:
        conn.close()

    # The fixture's OPEN (2026-04-15 @ $180, 5sh) matches the closed trade's entry,
    # and its CLOSE (2026-04-22 @ $190, 5sh) matches the recorded exit.
    text = FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    assert len(report.already_reconciled_fills) == 2
    assert len(report.unmatched_open_fills) == 0
    assert len(report.unmatched_close_fills) == 0
    assert len(report.matched_fills) == 0


# --- Phase 7 B.9 — exits-table → fills-repo migration discriminator ----------


def test_reconcile_close_fill_does_not_match_entry_fill_as_exit(tmp_path: Path):
    """B.9 discriminator: the migrated SQL must filter `f.action != 'entry'`
    when computing already-sold-shares (sold_in_db) and when scanning for
    historical claim matches (_find_unclaimed_recorded_exit). Pre-fix
    (without the action filter) the entry fill's quantity would count as
    'sold shares', immediately overflowing the cumulative budget on the
    first CLOSE fill and routing every legitimate exit to
    unmatched_close_fills.
    """
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        # Open trade with an entry-fill of 5 shares. No exit fills yet.
        _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-15",
            entry_price=180.0, shares=5, initial_stop=170.0,
        )
    finally:
        conn.close()

    # A single CLOSE fill matching the synthetic fixture's exit. Without
    # the `action != 'entry'` filter, sold_in_db would equal 5 (the
    # entry-fill's quantity), making cumulative = 5 + 5 = 10 > 5, so
    # the matcher would flag the legitimate exit as unmatched_close_fills.
    text = FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    # Both OPEN and CLOSE fills should reconcile cleanly.
    assert len(report.matched_fills) == 2, (
        f"expected 2 matched fills (OPEN + CLOSE); got {len(report.matched_fills)}. "
        "Pre-fix: the entry fill counted as already-sold shares, so the CLOSE "
        "overfilled the trade and routed to unmatched_close_fills."
    )
    assert len(report.unmatched_close_fills) == 0


def test_reconcile_already_reconciled_match_uses_fill_id_not_exit_id(tmp_path: Path):
    """B.9 discriminator: _find_unclaimed_recorded_exit returns a fills.fill_id
    (NOT an exits.id, since the exits table no longer exists). The claim-
    tracking set must therefore key on the fill_id; if the migration left
    the SELECT on the dropped 'exits' table the call would raise
    OperationalError. Dual matching (fill ALSO claimed twice) must still
    fall through to live allocation as before.
    """
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        # Closed trade with a recorded exit (fills row, action='exit').
        tid = _seed_entry(
            conn, ticker="AAPL", entry_date="2026-04-15",
            entry_price=180.0, shares=5, initial_stop=170.0,
        )
        _seed_exit(
            conn, trade_id=tid, exit_date="2026-04-22",
            exit_price=190.0, shares=5,
        )
    finally:
        conn.close()

    # Re-import the matching CLOSE fill — must land in already_reconciled.
    tos_text = (
        "Cash Balance\n\n"
        "DATE,TIME,TYPE,REF #,DESCRIPTION,AMOUNT,BALANCE\n\n"
        "Account Trade History\n\n"
        "Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,Net Price,Order Type,DATE,TIME\n"
        "STOCK,SELL,5,TO CLOSE,AAPL,--,--,--,$190.00,--,LMT,2026-04-22,15:30:00\n"
    )
    report = reconcile_tos(db_path=db, tos_text=tos_text)
    assert len(report.already_reconciled_fills) == 1, (
        f"expected 1 already_reconciled fill; got {len(report.already_reconciled_fills)}. "
        "Pre-fix the SELECT targeted the dropped 'exits' table and would "
        "raise OperationalError instead of matching the fills row."
    )
    assert len(report.unmatched_close_fills) == 0
