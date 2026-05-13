"""Phase 9 Sub-bundle E — T-E.3: Account Order History multi-line parser fix.

Real-world Schwab/TOS Account Order History uses 2- and 3-line groups per
working order — header line carries the dated MKT/STOCK shell, continuation
line(s) carry the STP trigger price, order_id (``RE #...``), and optional
``TRG BY #...`` conditional reference. Bundle B's single-row matcher per
spec §6.2 missed these entirely, producing 5 false-positive ``stop_mismatch``
emits during Sub-bundle B + C operator-witnessed gates.

This file pins the new multi-line grouping logic against the 4 real-world
sample exports (sanitized copies under ``tests/fixtures/tos/``) AND verifies
backwards compatibility with the synthetic single-row format used by
Bundle B (``test_tos_import_reconciliation_extension.py:_TOS_STOP_ORDER_TEMPLATE``).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.journal.tos_import import (
    extract_stop_orders,
    parse_tos_export,
    reconcile_tos,
)


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "tos"


def _load_order_rows(fixture_name: str) -> list[dict]:
    """Read a sanitized real-world fixture and return its Account Order
    History rows as dicts (one dict per CSV row)."""
    path = FIXTURES_DIR / fixture_name
    text = path.read_text(encoding="utf-8-sig")
    sections = parse_tos_export(text)
    return sections.get("Account Order History", [])


# ---------------------------------------------------------------------------
# §1 — real-world fixture extraction (multi-line groups)
# ---------------------------------------------------------------------------


def test_extract_stop_orders_2026_05_12_five_working_stops() -> None:
    """5/12 export carries 5 working stops (CVGI/DHC/VSAT/LAR/YOU) across
    multi-line groups — LAR has a continuation row WITHOUT ``RE #``
    (order_id falls back to None)."""
    rows = _load_order_rows("schwab-real-world-2026-05-12.csv")
    stops = extract_stop_orders(rows)
    assert stops == {
        "CVGI": (4.36, "1006290692715"),
        "DHC": (7.62, "1006300018355"),
        "VSAT": (63.23, "1006300018356"),
        "LAR": (7.00, None),
        "YOU": (54.06, "1006250248383"),
    }


def test_extract_stop_orders_2026_04_15_empty_section() -> None:
    """4/15 export has an empty Account Order History (header only) →
    extractor returns an empty dict gracefully."""
    rows = _load_order_rows("schwab-real-world-2026-04-15.csv")
    stops = extract_stop_orders(rows)
    assert stops == {}


def test_extract_stop_orders_2026_04_30_base_prefix_skipped() -> None:
    """4/30 export's CC working order is a 3-line group: header (MKT) +
    BASE-6.74 STP STD continuation + 20.51 STP continuation (absolute
    trigger). Parser MUST prefer the numeric (non-``BASE-``-prefixed)
    20.51 trigger over the 6.74 reference base."""
    rows = _load_order_rows("schwab-real-world-2026-04-30.csv")
    stops = extract_stop_orders(rows)
    # CC at 20.51 (absolute trigger) NOT 6.74 (BASE- reference).
    # DHC at 7.06 (RE #...) is also a working stop in this export.
    assert "CC" in stops
    cc_price, cc_order_id = stops["CC"]
    assert cc_price == 20.51
    assert "DHC" in stops
    dhc_price, dhc_order_id = stops["DHC"]
    assert dhc_price == 7.06
    assert dhc_order_id == "1006137040023"


def test_extract_stop_orders_2026_05_08_wait_trg_and_working() -> None:
    """5/8 export carries both Status=WORKING and Status=WAIT TRG rows;
    both are placed-but-not-yet-filled stops and MUST be included.
    CANCELED rows (SGML repeated entries) MUST be excluded."""
    rows = _load_order_rows("schwab-real-world-2026-05-08.csv")
    stops = extract_stop_orders(rows)
    # Working stops: LAR(WORKING, 7.00 no RE#), DHC(WAIT TRG, 7.49),
    # VSAT(WAIT TRG, 54.11), CVGI(WORKING, 3.67 no RE#), YOU(WORKING, 54.06).
    assert stops == {
        "LAR": (7.00, None),
        "DHC": (7.49, "1006250248363"),
        "VSAT": (54.11, "1006251280277"),
        "CVGI": (3.67, None),
        "YOU": (54.06, "1006250248383"),
    }
    # CANCELED-status SGML entries (5 of them) MUST NOT appear.
    assert "SGML" not in stops


# ---------------------------------------------------------------------------
# §2 — backwards compatibility with the synthetic single-row format
# ---------------------------------------------------------------------------


_SYNTHETIC_TEMPLATE = """\
Account Order History
Notes,Time Placed,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Order Type,TIF,Mark,Status
,2026-05-12 09:30:00,STOCK,SELL,-{qty},TO CLOSE,{ticker},,,STOCK,{price:.4f},STP,GTC,11.00,WORKING
"""


def test_extract_stop_orders_synthetic_single_row_format() -> None:
    """Bundle B's synthetic single-row format MUST still work — the row
    has Status=WORKING + Type=STOCK + Order Type=STP all in one row."""
    text = _SYNTHETIC_TEMPLATE.format(qty=10, ticker="ABC", price=9.00)
    sections = parse_tos_export(text)
    rows = sections["Account Order History"]
    stops = extract_stop_orders(rows)
    assert stops == {"ABC": (9.00, None)}


# ---------------------------------------------------------------------------
# §3 — full reconciliation against a fixture-DB journal: ZERO stop_mismatch
# when journal stops match the broker-side stops (the operator-witnessed
# gate's central assertion — pre-fix this emitted 5 false positives).
# ---------------------------------------------------------------------------


@pytest.fixture
def db_with_schema(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


def _seed_entry(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    entry_date: str,
    entry_price: float,
    shares: int,
    initial_stop: float,
) -> int:
    event_ts = f"{entry_date}T09:30:00"
    trade = Trade(
        id=None,
        ticker=ticker,
        entry_date=entry_date,
        entry_price=entry_price,
        initial_shares=shares,
        initial_stop=initial_stop,
        current_stop=initial_stop,
        state="entered",
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        notes=None,
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
                fill_id=None,
                trade_id=tid,
                fill_datetime=event_ts,
                action="entry",
                quantity=float(shares),
                price=entry_price,
            ),
            event_ts=event_ts,
        )
    return tid


def _make_capture_emitter():
    captured: list[dict] = []

    def _emit(**kw):
        captured.append(kw)
        return len(captured)

    return captured, _emit


def test_reconcile_2026_05_12_zero_stop_mismatch_when_stops_match(
    db_with_schema: Path,
) -> None:
    """Operator's 5/12 gate fixture against a journal that mirrors the
    actual broker state — 5 open trades with stops matching the Schwab
    working stops exactly: DHC $7.62, YOU $54.06, VSAT $63.23, CVGI $4.36,
    LAR $7.00. Post-T-E.3 the parser extracts all 5 working stops →
    ZERO ``stop_mismatch`` discrepancies (operator-acknowledged-immaterial
    workflow can stand down)."""
    conn = sqlite3.connect(db_with_schema)
    try:
        _seed_entry(
            conn, ticker="DHC", entry_date="2026-04-27",
            entry_price=10.00, shares=39, initial_stop=7.62,
        )
        _seed_entry(
            conn, ticker="YOU", entry_date="2026-04-27",
            entry_price=60.00, shares=5, initial_stop=54.06,
        )
        _seed_entry(
            conn, ticker="VSAT", entry_date="2026-04-27",
            entry_price=70.00, shares=2, initial_stop=63.23,
        )
        _seed_entry(
            conn, ticker="CVGI", entry_date="2026-04-27",
            entry_price=5.30, shares=20, initial_stop=4.36,
        )
        _seed_entry(
            conn, ticker="LAR", entry_date="2026-05-08",
            entry_price=11.73, shares=7, initial_stop=7.00,
        )
        text = (FIXTURES_DIR / "schwab-real-world-2026-05-12.csv").read_text(
            encoding="utf-8-sig",
        )
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        sms = [c for c in captured if c["discrepancy_type"] == "stop_mismatch"]
        assert sms == [], (
            f"expected ZERO stop_mismatch emits, got {len(sms)}: "
            f"{[(c['ticker'], c.get('delta_text')) for c in sms]}"
        )
    finally:
        conn.close()


def test_reconcile_2026_04_30_cc_uses_absolute_trigger_not_base(
    db_with_schema: Path,
) -> None:
    """4/30 CC working stop is a 3-line group: BASE-6.74 (reference)
    then 20.51 (absolute trigger). Journal carries CC at initial_stop
    $20.51 (matching the absolute trigger). Pre-T-E.3 the parser missed
    the multi-line group entirely → ``stop_mismatch`` (no broker stop)
    emit. Post-T-E.3 it extracts 20.51 → ZERO emit on CC."""
    conn = sqlite3.connect(db_with_schema)
    try:
        _seed_entry(
            conn, ticker="CC", entry_date="2026-04-28",
            entry_price=27.25, shares=5, initial_stop=20.51,
        )
        text = (FIXTURES_DIR / "schwab-real-world-2026-04-30.csv").read_text(
            encoding="utf-8-sig",
        )
        captured, emit = _make_capture_emitter()
        reconcile_tos(conn=conn, tos_text=text, run_id=1, emitter=emit)
        sms = [c for c in captured if c["discrepancy_type"] == "stop_mismatch"]
        # CC must NOT be in the emits. DHC is in 4/30 too but no journal
        # entry → that's an orphan-broker-stop emit; we just assert CC's
        # absence (the brief calls out CC specifically).
        cc_emits = [c for c in sms if c["ticker"] == "CC"]
        assert cc_emits == [], (
            f"expected ZERO stop_mismatch on CC (absolute trigger 20.51 "
            f"matches journal); got {cc_emits}"
        )
    finally:
        conn.close()
