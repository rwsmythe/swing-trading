"""TOS reconciliation parser + matcher."""
from __future__ import annotations

from pathlib import Path

from swing.journal.tos_import import (
    parse_tos_export, reconcile_tos, ReconciliationReport,
    extract_cash_movements, extract_stock_fills,
)


FIXTURE = Path(__file__).parent.parent / "fixtures" / "tos" / "synthetic-tos.csv"


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
    from swing.trades.entry import EntryRequest, record_entry

    db = tmp_path / "swing.db"
    ensure_schema(db).close()

    import sqlite3
    conn = sqlite3.connect(db)
    try:
        record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=5, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="seed",
            event_ts="2026-04-15T09:30:00",
        ), soft_warn=10, hard_cap=10, force=False)
    finally:
        conn.close()

    text = FIXTURE.read_text(encoding="utf-8")
    report = reconcile_tos(db_path=db, tos_text=text)
    assert len(report.matched_fills) == 2
    assert len(report.unmatched_close_fills) == 0


def test_reconcile_within_batch_cumulative_overfill(tmp_path: Path):
    from swing.data.db import ensure_schema
    from swing.trades.entry import EntryRequest, record_entry

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=5, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="seed",
            event_ts="2026-04-15T09:30:00",
        ), soft_warn=10, hard_cap=10, force=False)
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
    from swing.trades.entry import EntryRequest, record_entry

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=3, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="seed",
            event_ts="2026-04-15T09:30:00",
        ), soft_warn=10, hard_cap=10, force=False)
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
    from swing.trades.entry import EntryRequest, record_entry
    from swing.trades.exit import ExitReason, ExitRequest, record_exit

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        tid = record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-01", entry_price=170.0,
            shares=5, initial_stop=160.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="first",
            event_ts="2026-04-01T09:30:00",
        ), soft_warn=10, hard_cap=10, force=False).trade_id
        record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-10", exit_price=175.0,
            shares=5, reason=ExitReason.TARGET, notes=None,
            rationale="first-close", event_ts="2026-04-10T15:30:00",
        ))
        # Reopen the ticker at a different price/date.
        record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=5, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="reopen",
            event_ts="2026-04-15T09:30:00",
        ), soft_warn=10, hard_cap=10, force=False)
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
    from swing.trades.entry import EntryRequest, record_entry
    from swing.trades.exit import ExitReason, ExitRequest, record_exit

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        # Morning: open + close (same date).
        tid = record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-17", entry_price=180.0,
            shares=5, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="am",
            event_ts="2026-04-17T09:45:00",
        ), soft_warn=10, hard_cap=10, force=False).trade_id
        record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-17", exit_price=182.0,
            shares=5, reason=ExitReason.TARGET, notes=None,
            rationale="am-close", event_ts="2026-04-17T11:30:00",
        ))
        # Afternoon: reopen same ticker, same calendar date.
        record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-17", entry_price=181.0,
            shares=5, initial_stop=171.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="pm",
            event_ts="2026-04-17T14:00:00",
        ), soft_warn=10, hard_cap=10, force=False)
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
    from swing.trades.entry import EntryRequest, record_entry
    from swing.trades.exit import ExitReason, ExitRequest, record_exit

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        # Morning closed round-trip at $182 x 5sh on 2026-04-17.
        tid = record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-17", entry_price=180.0,
            shares=5, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="am",
            event_ts="2026-04-17T09:45:00",
        ), soft_warn=10, hard_cap=10, force=False).trade_id
        record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-17", exit_price=182.0,
            shares=5, reason=ExitReason.TARGET, notes=None,
            rationale="am-close", event_ts="2026-04-17T11:30:00",
        ))
        # Afternoon reopen, 10 shares so it can absorb a live 5-share sale.
        record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-17", entry_price=181.0,
            shares=10, initial_stop=171.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="pm",
            event_ts="2026-04-17T14:00:00",
        ), soft_warn=10, hard_cap=10, force=False)
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


def test_reconcile_does_not_swallow_fill_that_matches_current_open_lot(tmp_path: Path):
    """Adversarial review Batch 3 Round 3 Major 2: _matches_recorded_exit must
    not over-classify a CLOSE fill as already_reconciled when the recorded exit
    actually belongs to the CURRENT open trade's lot. When a prior closed trade
    shares (ticker, date, qty, price) coincidence with a recorded exit on the
    current open trade, the fill should allocate to the current open lot, not
    be silently swallowed into already_reconciled_fills."""
    from swing.data.db import ensure_schema
    from swing.trades.entry import EntryRequest, record_entry
    from swing.trades.exit import ExitReason, ExitRequest, record_exit

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        # Open trade (the one the CLOSE fill should allocate to).
        tid = record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=5, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="current",
            event_ts="2026-04-15T09:30:00",
        ), soft_warn=10, hard_cap=10, force=False).trade_id
        # Partial exit already recorded against the current open trade.
        # If the reorder blindly matched any recorded exit, a re-imported
        # TOS CLOSE at the same date/qty/price would be swallowed.
        record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-22", exit_price=190.0,
            shares=3, reason=ExitReason.TARGET, notes=None,
            rationale="partial", event_ts="2026-04-22T15:30:00",
        ))
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
    from swing.trades.entry import EntryRequest, record_entry
    from swing.trades.exit import ExitReason, ExitRequest, record_exit

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    import sqlite3
    conn = sqlite3.connect(db)
    try:
        tid = record_entry(conn, EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=5, initial_stop=170.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="seed",
            event_ts="2026-04-15T09:30:00",
        ), soft_warn=10, hard_cap=10, force=False).trade_id
        record_exit(conn, ExitRequest(
            trade_id=tid, exit_date="2026-04-22", exit_price=190.0,
            shares=5, reason=ExitReason.TARGET, notes=None,
            rationale="seed-close", event_ts="2026-04-22T15:30:00",
        ))
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
