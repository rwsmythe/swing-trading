"""Phase 13 T3.SB3 T-B.3.2 — MFE/MAE from OhlcvCache + Phase 8 source-ladder.

Covers spec §6.3 + plan §E.3 LOCK:
  * Source 1 (Phase 8 ``daily_management_records``) wins when daily-management
    coverage exists for the trade.
  * Source 2 (OhlcvCache daily-bar synthesis) fires only when Phase 8
    coverage is absent.
  * ``mfe_pct = max(daily highs since entry) / entry_price - 1``.
  * ``mae_pct = min(daily lows since entry) / entry_price - 1``.
  * Per-row failure isolation (T2.SB5 R1 M#1 forward-binding lesson #2) —
    malformed Phase 8 row OR malformed OhlcvCache bar must NOT poison the
    helper's return.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from swing.data.db import connect, ensure_schema


def _insert_trade(conn: sqlite3.Connection, **overrides: Any) -> int:
    defaults = dict(
        ticker="XYZ",
        entry_date="2026-05-01",
        entry_price=20.0,
        initial_shares=100,
        initial_stop=18.0,
        current_stop=18.0,
        state="entered",
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at="2026-05-01T09:30:00",
        current_size=100.0,
    )
    defaults.update(overrides)
    cols = ", ".join(defaults)
    placeholders = ", ".join("?" * len(defaults))
    cursor = conn.execute(
        f"INSERT INTO trades ({cols}) VALUES ({placeholders})",
        tuple(defaults.values()),
    )
    return cursor.lastrowid


def _insert_dmr_snapshot(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    review_date: str,
    data_asof_session: str,
    intraday_high: float | None,
    intraday_low: float | None,
    is_superseded: int = 0,
    mfe_mae_precision_level: str = "daily_approximate",
) -> None:
    conn.execute(
        "INSERT INTO daily_management_records ("
        "trade_id, record_type, review_date, data_asof_session, created_at, "
        "mfe_mae_precision_level, is_superseded, "
        "intraday_high, intraday_low"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            trade_id, "daily_snapshot", review_date, data_asof_session,
            f"{review_date}T17:00:00",
            mfe_mae_precision_level, is_superseded,
            intraday_high, intraday_low,
        ),
    )


class _StubOhlcvCache:
    """Minimal OhlcvCache-shape stub yielding the supplied DataFrame.

    Mirrors the real ``OhlcvCache.get_or_fetch`` raise-on-empty contract so
    fallthrough semantics + per-row failure isolation can be exercised
    without standing up the full cache.
    """

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = frames
        self.calls: list[tuple[str, int]] = []

    def get_or_fetch(self, *, ticker: str, window_days: int = 180) -> pd.DataFrame:
        self.calls.append((ticker.upper(), int(window_days)))
        frame = self._frames.get(ticker.upper())
        if frame is None or frame.empty:
            raise ValueError(f"No data for {ticker.upper()}")
        return frame.copy()


def _ohlcv_frame(rows: list[tuple[str, float, float, float, float, int]]) -> pd.DataFrame:
    """Build an OHLCV DataFrame with DatetimeIndex + capitalized columns.

    Each row: (iso_date, open, high, low, close, volume).
    """
    df = pd.DataFrame(
        rows, columns=["date", "Open", "High", "Low", "Close", "Volume"],
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "auto_fill.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    yield conn
    conn.close()


# --- (a) Source 1 (Phase 8) wins when daily-management coverage exists ---


def test_compute_mfe_mae_prefers_phase_8_when_dmr_coverage_exists(
    db: sqlite3.Connection,
) -> None:
    from swing.data.repos.trades import get_trade
    from swing.trades.review_auto_fill import compute_mfe_mae_from_ohlcv_cache

    trade_id = _insert_trade(
        db, ticker="XYZ", entry_date="2026-05-01", entry_price=20.0,
    )
    # Phase 8 records yield max-high = 25.0 + min-low = 17.0.
    _insert_dmr_snapshot(
        db, trade_id=trade_id, review_date="2026-05-02",
        data_asof_session="2026-05-02",
        intraday_high=22.0, intraday_low=19.0,
    )
    _insert_dmr_snapshot(
        db, trade_id=trade_id, review_date="2026-05-03",
        data_asof_session="2026-05-03",
        intraday_high=25.0, intraday_low=17.0,
    )
    db.commit()
    trade = get_trade(db, trade_id)

    # OhlcvCache present but should NOT be consulted (Phase 8 wins).
    cache = _StubOhlcvCache({
        "XYZ": _ohlcv_frame([
            ("2026-05-02", 20.0, 99.0, 1.0, 21.0, 1000),  # garbage to detect leak
        ]),
    })

    mfe_pct, mae_pct = compute_mfe_mae_from_ohlcv_cache(db, trade, cache)
    assert mfe_pct == pytest.approx((25.0 / 20.0) - 1.0)
    assert mae_pct == pytest.approx((17.0 / 20.0) - 1.0)
    # Phase 8 path → cache must not be invoked.
    assert cache.calls == []


# --- (b) Source 2 (OhlcvCache) fires when Phase 8 coverage is absent ---


def test_compute_mfe_mae_falls_through_to_ohlcv_cache_when_no_phase_8(
    db: sqlite3.Connection,
) -> None:
    from swing.data.repos.trades import get_trade
    from swing.trades.review_auto_fill import compute_mfe_mae_from_ohlcv_cache

    trade_id = _insert_trade(
        db, ticker="ABC", entry_date="2026-05-01", entry_price=10.0,
    )
    db.commit()
    trade = get_trade(db, trade_id)
    # No daily_management_records seeded → fallthrough to OhlcvCache.
    cache = _StubOhlcvCache({
        "ABC": _ohlcv_frame([
            ("2026-05-01", 10.0, 12.0, 9.0, 11.0, 1000),
            ("2026-05-02", 11.0, 14.0, 8.0, 13.0, 1000),
            ("2026-05-03", 13.0, 15.0, 7.0, 12.0, 1000),
        ]),
    })

    mfe_pct, mae_pct = compute_mfe_mae_from_ohlcv_cache(db, trade, cache)
    # max(High) since entry = 15.0; min(Low) since entry = 7.0.
    assert mfe_pct == pytest.approx((15.0 / 10.0) - 1.0)
    assert mae_pct == pytest.approx((7.0 / 10.0) - 1.0)
    assert cache.calls and cache.calls[0][0] == "ABC"


# --- (c) MFE pct formula correctness ---


def test_compute_mfe_mae_mfe_pct_formula_is_max_high_over_entry_minus_one(
    db: sqlite3.Connection,
) -> None:
    from swing.data.repos.trades import get_trade
    from swing.trades.review_auto_fill import compute_mfe_mae_from_ohlcv_cache

    # entry_price = 50.0; max high since entry = 65.0 → mfe = 0.30.
    trade_id = _insert_trade(
        db, ticker="DEF", entry_date="2026-04-01", entry_price=50.0,
    )
    db.commit()
    trade = get_trade(db, trade_id)
    cache = _StubOhlcvCache({
        "DEF": _ohlcv_frame([
            ("2026-04-01", 50.0, 55.0, 48.0, 52.0, 1000),
            ("2026-04-15", 52.0, 65.0, 49.0, 60.0, 2000),
            ("2026-04-30", 60.0, 62.0, 55.0, 58.0, 1500),
        ]),
    })
    mfe_pct, _ = compute_mfe_mae_from_ohlcv_cache(db, trade, cache)
    assert mfe_pct == pytest.approx(0.30)


# --- (d) MAE pct formula correctness ---


def test_compute_mfe_mae_mae_pct_formula_is_min_low_over_entry_minus_one(
    db: sqlite3.Connection,
) -> None:
    from swing.data.repos.trades import get_trade
    from swing.trades.review_auto_fill import compute_mfe_mae_from_ohlcv_cache

    # entry_price = 100.0; min low since entry = 85.0 → mae = -0.15.
    trade_id = _insert_trade(
        db, ticker="GHI", entry_date="2026-04-01", entry_price=100.0,
    )
    db.commit()
    trade = get_trade(db, trade_id)
    cache = _StubOhlcvCache({
        "GHI": _ohlcv_frame([
            ("2026-04-01", 100.0, 102.0, 99.0, 101.0, 1000),
            ("2026-04-10", 101.0, 105.0, 85.0, 90.0, 5000),
            ("2026-04-20", 90.0, 95.0, 88.0, 93.0, 2000),
        ]),
    })
    _, mae_pct = compute_mfe_mae_from_ohlcv_cache(db, trade, cache)
    assert mae_pct == pytest.approx(-0.15)


# --- (e) Per-row failure isolation in DMR cohort (T2.SB5 R1 M#1) ---


def test_compute_mfe_mae_skips_dmr_row_with_null_high_and_low(
    db: sqlite3.Connection,
) -> None:
    """A DMR row missing intraday_high AND intraday_low (e.g. pipeline
    couldn't compute high/low for the day) must be skipped, not crash the
    helper. Other rows in the cohort continue to contribute."""
    from swing.data.repos.trades import get_trade
    from swing.trades.review_auto_fill import compute_mfe_mae_from_ohlcv_cache

    trade_id = _insert_trade(
        db, ticker="JKL", entry_date="2026-05-01", entry_price=10.0,
    )
    _insert_dmr_snapshot(
        db, trade_id=trade_id, review_date="2026-05-02",
        data_asof_session="2026-05-02",
        intraday_high=12.0, intraday_low=9.0,
    )
    # Malformed-ish row: high/low both NULL (no usable data).
    _insert_dmr_snapshot(
        db, trade_id=trade_id, review_date="2026-05-03",
        data_asof_session="2026-05-03",
        intraday_high=None, intraday_low=None,
    )
    _insert_dmr_snapshot(
        db, trade_id=trade_id, review_date="2026-05-04",
        data_asof_session="2026-05-04",
        intraday_high=15.0, intraday_low=8.0,
    )
    db.commit()
    trade = get_trade(db, trade_id)
    cache = _StubOhlcvCache({})

    mfe_pct, mae_pct = compute_mfe_mae_from_ohlcv_cache(db, trade, cache)
    # max(12, 15) = 15 → mfe = 0.50; min(9, 8) = 8 → mae = -0.20.
    assert mfe_pct == pytest.approx(0.50)
    assert mae_pct == pytest.approx(-0.20)


# --- (f) Phase 8 source ignores superseded rows ---


def test_compute_mfe_mae_phase_8_source_ignores_superseded_rows(
    db: sqlite3.Connection,
) -> None:
    from swing.data.repos.trades import get_trade
    from swing.trades.review_auto_fill import compute_mfe_mae_from_ohlcv_cache

    trade_id = _insert_trade(
        db, ticker="MNO", entry_date="2026-05-01", entry_price=10.0,
    )
    # Superseded row with extreme values must NOT pollute the aggregate.
    # Different precision_level keeps the UNIQUE constraint
    # (trade_id, data_asof_session, mfe_mae_precision_level) happy while
    # representing a tier-upgrade history for the same session.
    _insert_dmr_snapshot(
        db, trade_id=trade_id, review_date="2026-05-02",
        data_asof_session="2026-05-02",
        intraday_high=99.0, intraday_low=0.5, is_superseded=1,
        mfe_mae_precision_level="daily_approximate",
    )
    _insert_dmr_snapshot(
        db, trade_id=trade_id, review_date="2026-05-02",
        data_asof_session="2026-05-02",
        intraday_high=12.0, intraday_low=9.0,
        mfe_mae_precision_level="intraday_estimated",
    )
    db.commit()
    trade = get_trade(db, trade_id)
    cache = _StubOhlcvCache({})

    mfe_pct, mae_pct = compute_mfe_mae_from_ohlcv_cache(db, trade, cache)
    assert mfe_pct == pytest.approx((12.0 / 10.0) - 1.0)
    assert mae_pct == pytest.approx((9.0 / 10.0) - 1.0)


# --- (g) OhlcvCache fallthrough on cache.get_or_fetch raise returns
#         (0.0, 0.0) — graceful no-data path (form still renders) ---


def test_compute_mfe_mae_returns_zero_zero_when_no_data_anywhere(
    db: sqlite3.Connection,
) -> None:
    """Per-row failure isolation extends to the helper-level fallthrough: if
    Phase 8 has no rows AND OhlcvCache.get_or_fetch raises, return (0.0,
    0.0) so the form-render path does not crash on the no-data trade."""
    from swing.data.repos.trades import get_trade
    from swing.trades.review_auto_fill import compute_mfe_mae_from_ohlcv_cache

    trade_id = _insert_trade(
        db, ticker="PQR", entry_date="2026-05-01", entry_price=10.0,
    )
    db.commit()
    trade = get_trade(db, trade_id)
    cache = _StubOhlcvCache({})  # raises ValueError on any lookup

    mfe_pct, mae_pct = compute_mfe_mae_from_ohlcv_cache(db, trade, cache)
    assert mfe_pct == 0.0
    assert mae_pct == 0.0


# --- (h) OhlcvCache slice respects entry_date ---


def test_compute_mfe_mae_ohlcv_source_slices_from_entry_date(
    db: sqlite3.Connection,
) -> None:
    """Bars BEFORE entry_date must NOT contribute to MFE/MAE (only the
    post-entry window matters per spec §6.3)."""
    from swing.data.repos.trades import get_trade
    from swing.trades.review_auto_fill import compute_mfe_mae_from_ohlcv_cache

    trade_id = _insert_trade(
        db, ticker="STU", entry_date="2026-04-15", entry_price=10.0,
    )
    db.commit()
    trade = get_trade(db, trade_id)
    # Pre-entry row carries extreme values that must be ignored.
    cache = _StubOhlcvCache({
        "STU": _ohlcv_frame([
            ("2026-04-01", 5.0, 99.0, 0.5, 5.0, 1000),  # PRE-entry; ignore
            ("2026-04-15", 10.0, 11.0, 9.5, 10.5, 1000),
            ("2026-05-01", 10.5, 13.0, 9.0, 12.0, 1000),
        ]),
    })
    mfe_pct, mae_pct = compute_mfe_mae_from_ohlcv_cache(db, trade, cache)
    # Only post-entry highs/lows considered:
    #   highs = [11.0, 13.0] → max = 13.0 → mfe = 0.30
    #   lows  = [9.5, 9.0]   → min = 9.0  → mae = -0.10
    assert mfe_pct == pytest.approx(0.30)
    assert mae_pct == pytest.approx(-0.10)


# --- (i) Helper accepts cache=None and returns (0.0, 0.0) when Phase 8
#         absent (web form may construct ohlcv_cache lazily) ---


def test_compute_mfe_mae_returns_zero_zero_when_cache_is_none(
    db: sqlite3.Connection,
) -> None:
    from swing.data.repos.trades import get_trade
    from swing.trades.review_auto_fill import compute_mfe_mae_from_ohlcv_cache

    trade_id = _insert_trade(
        db, ticker="VWX", entry_date="2026-05-01", entry_price=10.0,
    )
    db.commit()
    trade = get_trade(db, trade_id)

    mfe_pct, mae_pct = compute_mfe_mae_from_ohlcv_cache(db, trade, None)
    assert mfe_pct == 0.0
    assert mae_pct == 0.0
