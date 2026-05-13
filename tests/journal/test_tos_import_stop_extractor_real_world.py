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
    # Codex R1 Major #2 contract (recon doc §2.D): the CC winning
    # continuation has Spread="" (the third line `,,,,,,,,,,,20.51,STP,,`);
    # the predecessor row carries `TRG BY #1006193131983` in Spread which
    # MUST NOT leak as the order_id. Either way, cc_order_id is None.
    assert cc_order_id is None
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


# ---------------------------------------------------------------------------
# §4 — Codex R1 Major #1 regression: duplicate-unnamed-column robustness.
# Schwab/TOS Account Order History uses TWO unnamed columns; a future Schwab
# drift adding a THIRD unnamed column (or shuffling positions) MUST NOT
# regress the STP-marker scan. The post-fix parser renames every duplicate /
# empty header to ``col_<idx>`` + scans EVERY such slot for the STP marker.
# Pre-fix the parser relied on a narrow ``row[""]`` lookup which DictReader
# collapsed to a single column slot.
# ---------------------------------------------------------------------------


_EXTRA_UNNAMED_COLUMN_FIXTURE = (
    "Account Order History\n"
    # THREE unnamed columns (one between Notes/Time Placed, one between
    # PRICE/TIF, one between TIF/Status) — Schwab drift simulation.
    "Notes,,Time Placed,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,"
    "Type,PRICE,,TIF,,Status\n"
    # Header row + continuation: identical shape with one extra blank
    # cell to keep the STP marker in a positional unnamed slot.
    ",,5/11/26 23:09:41,STOCK,SELL,-20,TO CLOSE,CVGI,,,STOCK,~,MKT,GTC,,WORKING\n"
    ",,,RE #1006290692715,,,,,,,,4.36,STP,STD,,\n"
)


def test_extract_stop_orders_extra_unnamed_column_drift() -> None:
    """Codex R1 Major #1 regression: a Schwab export with an EXTRA blank
    header column inserted into the Account Order History block MUST NOT
    regress the STP marker scan. Pre-fix the parser relied on
    ``row[""]`` which DictReader collapsed to the last unnamed column —
    a shifted STP slot silently broke marker detection. Post-fix all
    duplicate/empty headers are renamed to ``col_<idx>`` + the marker
    scan iterates every such slot.
    """
    sections = parse_tos_export(_EXTRA_UNNAMED_COLUMN_FIXTURE)
    rows = sections["Account Order History"]
    stops = extract_stop_orders(rows)
    assert stops == {"CVGI": (4.36, "1006290692715")}, (
        f"expected CVGI stop extracted under extra-blank-column drift; "
        f"got {stops!r}"
    )


# ---------------------------------------------------------------------------
# §5 — Codex R1 Major #2 regression: ``TRG BY #...`` MUST NOT leak as
# the stop's order_id. Builds a synthetic 2-line group whose continuation
# row carries the trigger reference in Spread + a numeric STP price.
# Pre-fix ``_clean_order_id("TRG BY #999")`` returned ``"TRG BY #999"``;
# post-fix it returns ``None``.
# ---------------------------------------------------------------------------


_TRG_BY_ONLY_CONTINUATION_FIXTURE = (
    "Account Order History\n"
    "Notes,,Time Placed,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,"
    "Type,PRICE,,TIF,Status\n"
    # Header row (MKT WORKING) + a single continuation row whose Spread
    # carries TRG BY #999 (NOT a RE # prefix) AND a numeric STP price.
    # Pre-fix the order_id would have leaked as 'TRG BY #999'.
    ",,5/11/26 23:09:41,STOCK,SELL,-20,TO CLOSE,XYZ,,,STOCK,~,MKT,GTC,WORKING\n"
    ",,,TRG BY #999,,,,,,,,50.00,STP,STD,\n"
)


def test_extract_stop_orders_trg_by_only_in_continuation_returns_none_order_id() -> None:
    """Codex R1 Major #2 contract: a continuation row carrying ONLY
    ``TRG BY #...`` (no ``RE #`` prefix) is a trigger-order reference,
    NOT a stop order id. ``_clean_order_id`` MUST reject it and the
    emitted stop MUST have ``order_id=None``.

    Pre-fix the order_id was leaked literally as ``"TRG BY #999"`` —
    downstream callers would have surfaced it as if it were a Schwab
    order id, silently misrepresenting the broker order chain in any
    operator-visible artifact (discrepancy delta_text, audit emit JSON).
    """
    sections = parse_tos_export(_TRG_BY_ONLY_CONTINUATION_FIXTURE)
    rows = sections["Account Order History"]
    stops = extract_stop_orders(rows)
    assert "XYZ" in stops, stops
    xyz_price, xyz_order_id = stops["XYZ"]
    assert xyz_price == 50.00
    # Critical: TRG BY reference MUST NOT leak as order_id.
    assert xyz_order_id is None, (
        f"_clean_order_id leaked TRG BY reference as order_id={xyz_order_id!r}; "
        f"expected None per recon doc §2.D contract"
    )


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
