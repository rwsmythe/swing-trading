"""warm_archives_batch + the shared full-refresh predicate (Arc 6)."""
from __future__ import annotations

from datetime import date

from swing.data import ohlcv_archive as mod


def test_full_refresh_due_legacy_when_stagger_disabled():
    """stagger_enabled=False -> exact legacy `>= 7` behavior, no bucket gate."""
    today = date(2026, 6, 10)
    # 6 days since -> not due; 7 days -> due.
    assert mod._full_refresh_due("AAPL", date(2026, 6, 4), today, stagger_enabled=False) is False
    assert mod._full_refresh_due("AAPL", date(2026, 6, 3), today, stagger_enabled=False) is True


def _ticker_with_bucket(day_idx, *, equal):
    """First synthetic ticker whose crc32 bucket == day_idx (equal=True) or
    != day_idx (equal=False). Generated pool is large enough to cover every
    bucket regardless of the calendar date under test."""
    import zlib
    for i in range(1000):
        t = f"SYN{i:04d}"
        bucket = zlib.crc32(t.encode()) % 7
        if (bucket == day_idx) == equal:
            return t
    raise AssertionError("no ticker found (impossible across 1000 symbols)")


def test_full_refresh_due_stagger_bucket_gate():
    """stagger_enabled=True: a ticker `>= 7` due fires ONLY on its bucket day,
    where bucket = crc32(ticker) % 7 and day_idx = today.toordinal() % 7."""
    today = date(2026, 6, 10)
    day_idx = today.toordinal() % 7
    # Find a ticker whose bucket == day_idx (fires) and one whose bucket != day_idx (waits).
    on_day = _ticker_with_bucket(day_idx, equal=True)
    off_day = _ticker_with_bucket(day_idx, equal=False)
    last_full = date(2026, 6, 1)  # 9 days -> `>= 7` but `< 13`
    assert mod._full_refresh_due(on_day, last_full, today, stagger_enabled=True) is True
    assert mod._full_refresh_due(off_day, last_full, today, stagger_enabled=True) is False


def test_full_refresh_due_hard_ceiling_13_days_overrides_bucket():
    """>= 13 days stale -> due regardless of bucket (worst-case staleness bound)."""
    today = date(2026, 6, 10)
    day_idx = today.toordinal() % 7
    off_day = _ticker_with_bucket(day_idx, equal=False)
    # 13 days stale -> ceiling fires even though bucket != day_idx.
    assert mod._full_refresh_due(off_day, date(2026, 5, 28), today, stagger_enabled=True) is True


def test_full_refresh_due_not_due_under_7_days_either_mode():
    today = date(2026, 6, 10)
    assert mod._full_refresh_due("AAPL", date(2026, 6, 5), today, stagger_enabled=True) is False
    assert mod._full_refresh_due("AAPL", date(2026, 6, 5), today, stagger_enabled=False) is False
