"""D86 (sg-label arc T4) -- the trade-event input domain at BOTH record services.

One canonical date grammar at the shared normaliser
(`swing.trades.exit._normalize_trade_event_date_to_iso`, imported by
`record_entry`) and a finite-price refusal at `record_entry` and
`record_exit` together, never one side.

PRE-FIX (measured on this box, Python 3.14): `date.fromisoformat` ACCEPTS the
compact `20261019` and the week date `2026-W01-1` (-> 2025-12-29), and
`datetime.fromisoformat` ACCEPTS `20261019T160000`; the helper then stored the
RAW string as the prefix (`20261019T16:00:00`). `inf` was admitted as a price
on both services.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.entry import EntryRequest, record_entry
from swing.trades.exit import ExitReason, ExitRequest, record_exit
from tests.trades.test_entry import _pretrade_kwargs
from tests.trades.test_exit import _seed_active_trade

_CANON = "YYYY-MM-DD"


def _counts(db: Path) -> tuple[int, int]:
    c = sqlite3.connect(str(db))
    try:
        return (c.execute("SELECT COUNT(*) FROM trades").fetchone()[0],
                c.execute("SELECT COUNT(*) FROM fills").fetchone()[0])
    finally:
        c.close()


@pytest.fixture
def exit_world(tmp_path: Path):
    db = tmp_path / "d86_exit.db"
    conn = ensure_schema(db)
    tid = int(_seed_active_trade(conn, ticker="AAPL", current_size=100.0))
    yield conn, db, tid
    conn.close()


@pytest.fixture
def entry_world(tmp_path: Path):
    db = tmp_path / "d86_entry.db"
    conn = ensure_schema(db)
    yield conn, db
    conn.close()


def _exit_req(tid: int, *, date: str = "2026-05-10",
              price: float = 10.0) -> ExitRequest:
    return ExitRequest(
        trade_id=tid, exit_date=date, exit_price=price, shares=10,
        reason=ExitReason.MANUAL, notes=None, rationale="manual",
        event_ts="2026-05-10T15:00:00",
    )


def _entry_req(*, date: str = "2026-04-15", price: float = 180.0) -> EntryRequest:
    return EntryRequest(
        ticker="AAPL", entry_date=date, entry_price=price,
        shares=5, initial_stop=170.0, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        rationale="d86", event_ts="2026-04-15T09:30:00",
        **_pretrade_kwargs(),
    )


# --- 4a / 4c / 4d: the exit side ---------------------------------------------

@pytest.mark.parametrize("raw", ["20261019", "2026-W01-1", "20261019T160000"],
                         ids=["4a-compact", "4c-week", "4d-compact-T"])
def test_4acd_record_exit_refuses_non_canonical_dates(exit_world, raw):
    """PRE-FIX: each is accepted and a fill stored with the raw prefix.
    POST-FIX: ValueError naming the canonical form; zero fills inserted."""
    conn, db, tid = exit_world
    before = _counts(db)
    with pytest.raises(ValueError) as info:
        record_exit(conn, _exit_req(tid, date=raw))
    assert _CANON in str(info.value), str(info.value)
    assert raw in str(info.value)
    assert _counts(db) == before


# --- 4b / 4c / 4d: the entry side --------------------------------------------

@pytest.mark.parametrize("raw", ["20261019", "2026-W01-1"],
                         ids=["4b-compact", "4c-week"])
def test_4bc_record_entry_refuses_non_canonical_dates(entry_world, raw):
    """PRE-FIX: accepted; `trades.entry_date` stored verbatim. POST-FIX:
    ValueError naming the canonical form; no trade row."""
    conn, db = entry_world
    with pytest.raises(ValueError) as info:
        record_entry(conn, _entry_req(date=raw), soft_warn=4, hard_cap=6,
                     force=False)
    assert _CANON in str(info.value), str(info.value)
    assert _counts(db) == (0, 0)


def test_4d_record_entry_refuses_compact_t_form(entry_world):
    """Entry already refuses ANY T-form (its date-only guard); kept as the
    both-services pin for 4d."""
    conn, db = entry_world
    with pytest.raises(ValueError):
        record_entry(conn, _entry_req(date="20261019T160000"), soft_warn=4,
                     hard_cap=6, force=False)
    assert _counts(db) == (0, 0)


# --- 4e / 4f: the finite-price refusal ---------------------------------------

def test_4e_record_exit_refuses_inf_price(exit_world):
    """PRE-FIX: a fill row with price=inf. POST-FIX: ExitPriceRefusedError
    (a ValueError) naming `finite`; zero fills."""
    conn, db, tid = exit_world
    before = _counts(db)
    with pytest.raises(ValueError) as info:
        record_exit(conn, _exit_req(tid, price=float("inf")))
    assert type(info.value).__name__ == "ExitPriceRefusedError"
    assert "finite" in str(info.value)
    assert _counts(db) == before


@pytest.mark.parametrize("price", [float("inf"), float("-inf"), float("nan"),
                                   0.0, -1.0],
                         ids=["inf", "-inf", "nan", "0", "-1"])
def test_4f_record_entry_refuses_non_finite_or_non_positive_price(
        entry_world, price):
    """PRE-FIX: `inf` writes a trade + fill (the NaN case reached an
    IntegrityError at the NOT NULL; `-inf`/0/-1 hit the stop comparison or a
    CHECK). POST-FIX: ValueError naming the domain; zero rows."""
    conn, db = entry_world
    with pytest.raises(ValueError) as info:
        record_entry(conn, _entry_req(price=price), soft_warn=4, hard_cap=6,
                     force=False)
    assert "entry price must be a finite number > 0" in str(info.value), (
        str(info.value))
    assert _counts(db) == (0, 0)


# --- 4g: regression keepers ----------------------------------------------------

@pytest.mark.parametrize("raw, stored", [
    ("2026-10-19", "2026-10-19T16:00:00"),
    ("2026-10-19T09:31:00", "2026-10-19T09:31:00"),
    ("2026-10-19T09:31:00.123456", "2026-10-19T09:31:00.123456"),
    ("2026-10-19T09:31", "2026-10-19T09:31"),
])
def test_4g_canonical_exit_dates_accepted_unchanged(exit_world, raw, stored):
    conn, db, tid = exit_world
    record_exit(conn, _exit_req(tid, date=raw))
    c = sqlite3.connect(str(db))
    try:
        got = c.execute("SELECT fill_datetime FROM fills WHERE action != 'entry' "
                        "ORDER BY fill_id DESC LIMIT 1").fetchone()[0]
    finally:
        c.close()
    assert got == stored


def test_4g_canonical_entry_date_accepted_unchanged(entry_world):
    conn, db = entry_world
    result = record_entry(conn, _entry_req(date="2026-10-19"), soft_warn=4,
                          hard_cap=6, force=False)
    row = conn.execute("SELECT entry_date, entry_price FROM trades WHERE id = ?",
                       (result.trade_id,)).fetchone()
    assert tuple(row) == ("2026-10-19", 180.0)


@pytest.mark.parametrize("raw", ["2026-02-30", "2026-13-01"])
def test_4g_shape_valid_but_calendar_invalid_still_refused(exit_world, raw):
    conn, db, tid = exit_world
    with pytest.raises(ValueError):
        record_exit(conn, _exit_req(tid, date=raw))


@pytest.mark.parametrize("raw", ["2026-10-19T09:31:00+00:00",
                                 "2026-10-19T09:31:00Z"])
def test_4g_tz_aware_still_refused(exit_world, raw):
    conn, db, tid = exit_world
    with pytest.raises(ValueError):
        record_exit(conn, _exit_req(tid, date=raw))


def test_4g_finite_exit_price_still_recorded(exit_world):
    conn, db, tid = exit_world
    result = record_exit(conn, _exit_req(tid, price=0.01))
    assert result.exit_id is not None
