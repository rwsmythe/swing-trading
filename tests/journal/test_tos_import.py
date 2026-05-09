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
REAL_WORLD_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "tos" / "real-world-2026-05-08.csv"
)


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


# ---------------------------------------------------------------------------
# 3e.12 — real-world 7-day Schwab/TOS export reconciliation
#
# These tests exercise the operator's actual export shape (sanitized): the
# `Account Trade History` section uses a single `Exec Time` column instead of
# separate `Date` + `Time`; `Qty` is signed (`+7`, `-3`); dates are MDY-2yr
# (`5/8/26`). Pre-fix `extract_stock_fills` returned `[]` because `date_str`
# was empty (no `Date`/`DATE` column) — silent zero on every reconcile.
# Per operator clarification 2026-05-08 ("the whole point of reconciliation
# is to check for existence AND correct values") these tests run the FULL
# pipeline (extract → reconcile → matched / price_mismatch / unmatched routing)
# against a seeded test DB, not just extraction in isolation.
# ---------------------------------------------------------------------------


def _seed_real_world_open_positions(conn: sqlite3.Connection) -> dict[str, int]:
    """Seed the four operator-confirmed OPEN trades (LAR / CVGI / VSAT / YOU)
    plus the SGML round-trip OPEN at TOS prices. Returns ticker -> trade_id."""
    return {
        "LAR": _seed_entry(
            conn, ticker="LAR", entry_date="2026-05-08",
            entry_price=11.7066, shares=7, initial_stop=7.00,
        ),
        "CVGI": _seed_entry(
            conn, ticker="CVGI", entry_date="2026-05-08",
            entry_price=5.2244, shares=20, initial_stop=3.67,
        ),
        "VSAT": _seed_entry(
            conn, ticker="VSAT", entry_date="2026-05-06",
            entry_price=65.685, shares=2, initial_stop=54.11,
        ),
        "YOU": _seed_entry(
            conn, ticker="YOU", entry_date="2026-05-04",
            entry_price=56.295, shares=2, initial_stop=45.38,
        ),
        "SGML": _seed_entry(
            conn, ticker="SGML", entry_date="2026-05-07",
            entry_price=23.87, shares=3, initial_stop=11.63,
        ),
    }


def test_extract_stock_fills_from_real_world_csv():
    """Pre-fix: returns 0 fills because `Date`/`DATE` columns absent (real
    export uses `Exec Time`). Post-fix: returns the 6 STOCK fills from
    Account Trade History with normalized ISO dates and unsigned qty."""
    text = REAL_WORLD_FIXTURE.read_text(encoding="utf-8")
    sections = parse_tos_export(text)
    fills = list(extract_stock_fills(sections.get("Account Trade History", [])))
    # Pre-fix: extract returns [] (date_str empty + signed-qty `-3` filtered).
    # Post-fix: 6 fills (5 BUY OPEN + 1 SELL CLOSE for SGML).
    assert len(fills) == 6, (
        f"expected 6 fills from real-world CSV; got {len(fills)}. "
        f"Pre-fix the parser returns [] because the real export uses "
        f"`Exec Time` (combined date+time) and signed `Qty` (+7 / -3) — "
        f"`row.get('Date')` returns None and `qty <= 0` skips SELL fills."
    )
    by_ticker = {f.ticker: f for f in fills}
    assert set(by_ticker) == {"LAR", "SGML", "CVGI", "VSAT", "YOU"}, (
        f"expected tickers LAR/SGML/CVGI/VSAT/YOU; got {sorted(by_ticker)}"
    )
    # Date normalization: M/D/YY -> YYYY-MM-DD so reconcile_tos's strict
    # equality match against journal entry_date works.
    lar = by_ticker["LAR"]
    assert lar.date == "2026-05-08", f"expected 2026-05-08; got {lar.date!r}"
    assert lar.qty == 7, f"expected qty=7 (abs of '+7'); got {lar.qty}"
    assert lar.open_close == "OPEN" and lar.side == "BUY"
    # Signed-qty SELL: TOS Qty=`-3` must extract as qty=3 + open_close=CLOSE
    # (Side='SELL' + Pos Effect='TO CLOSE' both supply direction; the qty
    # field's sign is informational only).
    sgml_fills = [f for f in fills if f.ticker == "SGML"]
    assert len(sgml_fills) == 2, (
        f"expected SGML round-trip (BUY+3 + SELL-3) -> 2 fills; "
        f"got {len(sgml_fills)}"
    )
    sgml_close = next(f for f in sgml_fills if f.open_close == "CLOSE")
    assert sgml_close.qty == 3, (
        f"expected unsigned qty=3 from signed `-3`; got {sgml_close.qty}. "
        f"Pre-fix `int('-3') == -3` would route this through the `qty <= 0` "
        f"early-return and the SELL fill would never be extracted."
    )
    assert sgml_close.side == "SELL" and sgml_close.date == "2026-05-08"


def test_reconcile_real_world_csv_full_pipeline_price_match(tmp_path: Path):
    """End-to-end reconcile against operator's sanitized 7-day export with
    journal entry_prices matching TOS exactly. All 6 fills must land in
    matched_fills (5 OPEN price-match + 1 CLOSE cumulative-allocation match
    for SGML). Discriminator: pre-fix `report.matched_fills == []`
    (operator's silent-zero symptom)."""
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()

    conn = sqlite3.connect(db)
    try:
        _seed_real_world_open_positions(conn)
    finally:
        conn.close()

    text = REAL_WORLD_FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    assert len(report.matched_fills) == 6, (
        f"expected matched=6 (5 OPEN + 1 CLOSE allocation); "
        f"got matched={len(report.matched_fills)}, "
        f"price_mismatch={len(report.price_mismatch_fills)}, "
        f"unmatched_open={len(report.unmatched_open_fills)}, "
        f"unmatched_close={len(report.unmatched_close_fills)}, "
        f"already_reconciled={len(report.already_reconciled_fills)}. "
        f"Pre-fix the parser drops every fill so matched is 0."
    )
    assert report.price_mismatch_fills == []
    assert report.unmatched_open_fills == []
    assert report.unmatched_close_fills == []


def test_reconcile_real_world_csv_price_mismatch_path(tmp_path: Path):
    """Seed CVGI with entry_price intentionally OFF by more than tolerance
    (5.50 vs TOS 5.2244, diff 0.2756 > 0.01). The CVGI fill MUST land in
    price_mismatch_fills, not matched_fills. Discriminator: existence-only
    matching would route this to matched even when journal price disagrees
    with broker fill — exactly the value-correctness gap the operator
    flagged ('the whole point of reconciliation is to check for existence
    AND correct values')."""
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()

    conn = sqlite3.connect(db)
    try:
        # All other tickers seeded at TOS prices so they route to matched.
        _seed_entry(conn, ticker="LAR", entry_date="2026-05-08",
                    entry_price=11.7066, shares=7, initial_stop=7.00)
        _seed_entry(conn, ticker="VSAT", entry_date="2026-05-06",
                    entry_price=65.685, shares=2, initial_stop=54.11)
        _seed_entry(conn, ticker="YOU", entry_date="2026-05-04",
                    entry_price=56.295, shares=2, initial_stop=45.38)
        _seed_entry(conn, ticker="SGML", entry_date="2026-05-07",
                    entry_price=23.87, shares=3, initial_stop=11.63)
        # CVGI deliberately mispriced.
        _seed_entry(conn, ticker="CVGI", entry_date="2026-05-08",
                    entry_price=5.50, shares=20, initial_stop=3.67)
    finally:
        conn.close()

    text = REAL_WORLD_FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    mismatch_tickers = {f.ticker for f in report.price_mismatch_fills}
    assert mismatch_tickers == {"CVGI"}, (
        f"expected CVGI in price_mismatch_fills (TOS=5.2244 vs journal=5.50, "
        f"diff=0.2756 > tolerance=0.01); got mismatch={mismatch_tickers}, "
        f"matched={[f.ticker for f in report.matched_fills]}"
    )
    matched_tickers = sorted(f.ticker for f in report.matched_fills)
    assert matched_tickers == ["LAR", "SGML", "SGML", "VSAT", "YOU"], (
        f"expected LAR + SGML(BUY) + SGML(SELL) + VSAT + YOU in matched; "
        f"got {matched_tickers}"
    )


def test_reconcile_real_world_csv_sgml_round_trip(tmp_path: Path):
    """Isolated test of the SGML BUY+3 (5/7) → SELL-3 (5/8) round-trip
    routing. The CLOSE fill must land in matched_fills via the CLOSE-side
    allocation path at swing/journal/tos_import.py:230-271, which calls
    find_any_open_trade and bounds cumulative-shares-sold by initial_shares.
    Discriminator: with the parser bug present the SELL fill is silently
    dropped (qty=`-3` int-parses to -3, `qty <= 0` returns early); the test
    would assert matched=2 but get matched=0."""
    from swing.data.db import ensure_schema

    db = tmp_path / "swing.db"
    ensure_schema(db).close()

    conn = sqlite3.connect(db)
    try:
        # Only SGML seeded — other 5 fills will fall through to unmatched
        # OPEN (irrelevant to this test's assertion scope).
        _seed_entry(conn, ticker="SGML", entry_date="2026-05-07",
                    entry_price=23.87, shares=3, initial_stop=11.63)
    finally:
        conn.close()

    text = REAL_WORLD_FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    sgml_matched = [f for f in report.matched_fills if f.ticker == "SGML"]
    sgml_open = next((f for f in sgml_matched if f.open_close == "OPEN"), None)
    sgml_close = next((f for f in sgml_matched if f.open_close == "CLOSE"), None)
    assert sgml_open is not None, (
        f"expected SGML BUY+3 in matched_fills (existence + price match); "
        f"got matched_tickers={[(f.ticker, f.open_close) for f in report.matched_fills]}"
    )
    assert sgml_close is not None, (
        f"expected SGML SELL-3 in matched_fills via CLOSE-allocation path; "
        f"got matched_tickers={[(f.ticker, f.open_close) for f in report.matched_fills]}, "
        f"unmatched_close_tickers={[(f.ticker, f.qty) for f in report.unmatched_close_fills]}. "
        f"Pre-fix the SELL-3 fill is filtered by `qty <= 0` and never reaches "
        f"reconcile_tos at all (would also fail the OPEN match for the same reason)."
    )
    assert sgml_close.qty == 3 and sgml_close.date == "2026-05-08"
