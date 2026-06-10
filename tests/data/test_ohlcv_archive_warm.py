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


def test_stagger_resolver_returns_true_when_config_unreadable(monkeypatch):
    """_full_refresh_stagger_enabled returns True on any config exception."""
    mod._full_refresh_stagger_enabled.cache_clear()

    def boom():
        raise RuntimeError("no config")

    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", boom)
    assert mod._full_refresh_stagger_enabled() is True
    mod._full_refresh_stagger_enabled.cache_clear()


def test_stagger_resolver_reads_config_value(monkeypatch):
    mod._full_refresh_stagger_enabled.cache_clear()
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    assert mod._full_refresh_stagger_enabled() is False
    mod._full_refresh_stagger_enabled.cache_clear()


def test_read_or_fetch_archive_full_refresh_uses_shared_predicate(tmp_path, monkeypatch):
    """With stagger DISABLED, an 8-day-old meta still triggers full refresh
    (legacy `>= 7` preserved through the shared predicate)."""
    import json
    from datetime import timedelta
    import pandas as pd

    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    mod._full_refresh_stagger_enabled.cache_clear()
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)

    archive = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [10]},
        index=pd.to_datetime([FIXED - timedelta(days=1)]),
    )
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (FIXED - timedelta(days=8)).isoformat()})
    )

    called = {"full_start": None}

    def fake_download(ticker, **kwargs):
        called["full_start"] = kwargs.get("start")
        return pd.DataFrame(
            {"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [20]},
            index=pd.to_datetime([FIXED]),
        )

    monkeypatch.setattr(mod.yf, "download", fake_download)
    mod.read_or_fetch_archive("AAPL", end_date=FIXED, cache_dir=tmp_path, archive_history_days=1260)
    # full-refresh window start == today - calendar(1260); a gap fetch would use latest+1.
    expected = FIXED - timedelta(days=mod._calendar_window_for_trading_days(1260))
    assert called["full_start"] == expected
    mod._full_refresh_stagger_enabled.cache_clear()


def _write_archive(tmp_path, ticker, last_date, last_full_refresh_date=None):
    import json
    import pandas as pd
    df = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [10]},
        index=pd.to_datetime([last_date]),
    )
    df.to_parquet(tmp_path / f"{ticker}.parquet")
    if last_full_refresh_date is not None:
        (tmp_path / f"{ticker}.meta.json").write_text(
            json.dumps({"last_full_refresh_date": last_full_refresh_date.isoformat()})
        )


def test_classify_cohorts_cache_hit_gap_full(tmp_path, monkeypatch):
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    mod._full_refresh_stagger_enabled.cache_clear()
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)

    # FRESH: latest == today, recent full refresh -> cache-hit.
    _write_archive(tmp_path, "FRESH", FIXED, FIXED - timedelta(days=2))
    # GAP1: latest == today-1, recent full refresh -> gap, band latest=today-1.
    _write_archive(tmp_path, "GAP1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))
    # NEWBIE: no archive on disk -> full-refresh cohort.
    # (no file written for NEWBIE)
    # STALEFULL: latest==today but meta 8 days old -> full-refresh (>= 7 legacy).
    _write_archive(tmp_path, "STALEFULL", FIXED, FIXED - timedelta(days=8))

    report = mod._classify_warm_cohorts(
        ["FRESH", "GAP1", "NEWBIE", "STALEFULL"],
        cache_dir=tmp_path, today_session=FIXED, archive_history_days=1260,
        stagger_enabled=False,
    )
    assert report["cache_hit"] == ["FRESH"]
    assert "GAP1" in report["gap_bands"][FIXED - timedelta(days=1)]
    assert set(report["full_refresh"]) == {"NEWBIE", "STALEFULL"}
    mod._full_refresh_stagger_enabled.cache_clear()


def test_classify_gap_banding_deep_band_collapse(tmp_path, monkeypatch):
    """Tickers staler than GAP_DEEP_BAND_TRADING_DAYS collapse into ONE deep band."""
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()

    # Two near-current gaps (distinct bands) + two very-stale (collapse to deep band).
    _write_archive(tmp_path, "NEAR1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))
    _write_archive(tmp_path, "NEAR2", FIXED - timedelta(days=2), FIXED - timedelta(days=2))
    _write_archive(tmp_path, "DEEP1", FIXED - timedelta(days=200), FIXED - timedelta(days=2))
    _write_archive(tmp_path, "DEEP2", FIXED - timedelta(days=300), FIXED - timedelta(days=2))

    report = mod._classify_warm_cohorts(
        ["NEAR1", "NEAR2", "DEEP1", "DEEP2"],
        cache_dir=tmp_path, today_session=FIXED, archive_history_days=1260,
        stagger_enabled=False,
    )
    # NEAR1 + NEAR2 in their own per-latest bands; DEEP1+DEEP2 in the single deep band.
    assert "DEEP1" in report["deep_gap"] and "DEEP2" in report["deep_gap"]
    assert "NEAR1" not in report["deep_gap"] and "NEAR2" not in report["deep_gap"]
    mod._full_refresh_stagger_enabled.cache_clear()
