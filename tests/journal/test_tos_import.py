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
