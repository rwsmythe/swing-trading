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


import pandas as pd


def _mk_batch_frame(tickers_dates: dict, *, missing: tuple = (), include_adj=True,
                    dates: list | None = None):
    """Build a probe-shaped group_by='ticker' MultiIndex batch frame.

    tickers_dates: {ticker: [date, ...]} for present (valid) tickers.
    missing: tickers that are PRESENT-BUT-ALL-NAN (the probe-confirmed F6 shape).
    include_adj: include an 'Adj Close' column (present-and-dropped on the real path).
    dates: explicit index dates — REQUIRED when tickers_dates is empty (a
        missing-only frame) so the frame has ROWS (Codex R2 Major #1: a 0-row
        frame is `.empty`, which `_fetch_chunk` treats as a whole-chunk failure
        BEFORE per-ticker all-NaN extraction can run; passing `dates` gives the
        all-NaN frame a real dated index so it exercises the F6 path, not the
        empty-response path).
    """
    all_tickers = list(tickers_dates.keys()) + list(missing)
    # Union of all dates (yfinance aligns the batch on a shared index), plus any
    # explicit `dates` so a missing-only frame still has rows.
    all_dates = sorted(
        {d for ds in tickers_dates.values() for d in ds} | set(dates or [])
    )
    index = pd.to_datetime(all_dates)
    fields = ["Open", "High", "Low", "Close", "Volume"]
    if include_adj:
        fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    cols = pd.MultiIndex.from_product([all_tickers, fields])
    df = pd.DataFrame(index=index, columns=cols, dtype=float)
    for t, ds in tickers_dates.items():
        present = pd.to_datetime(ds)
        for f in fields:
            df.loc[present, (t, f)] = 100.0 if f != "Volume" else 1000.0
    # `missing` tickers stay all-NaN (present-but-all-NaN — F6 shape).
    return df


def test_extract_valid_subframe_drops_adj_close_and_tz(monkeypatch):
    from datetime import date as _date
    frame = _mk_batch_frame({"AAPL": [_date(2026, 6, 10)]}, include_adj=True)
    sub = mod._extract_ticker_subframe(frame, "AAPL")
    assert sub is not None
    assert list(sub.columns) == ["Open", "High", "Low", "Close", "Volume"]  # Adj Close dropped
    assert "Adj Close" not in sub.columns


def test_extract_missing_ticker_is_all_nan_returns_none(monkeypatch):
    """F6: present-but-all-NaN subframe -> fallback (None), NOT a write."""
    from datetime import date as _date
    frame = _mk_batch_frame({"AAPL": [_date(2026, 6, 10)]}, missing=("ZZZZINVALID",))
    assert mod._extract_ticker_subframe(frame, "ZZZZINVALID") is None


def test_extract_missing_ohlcv_column_returns_none():
    """A subframe lacking a required OHLCV column -> fallback."""
    from datetime import date as _date
    idx = pd.to_datetime([_date(2026, 6, 10)])
    # AAPL present but with NO 'Close' column (only Open/High/Low/Volume).
    cols = pd.MultiIndex.from_product([["AAPL"], ["Open", "High", "Low", "Volume"]])
    frame = pd.DataFrame(100.0, index=idx, columns=cols)
    assert mod._extract_ticker_subframe(frame, "AAPL") is None


def test_extract_single_ticker_flat_frame_remnant():
    """A size-1 chunk may return a FLAT (non-MultiIndex) frame -> treat as that
    ticker's subframe (Codex R1 Minor #3)."""
    from datetime import date as _date
    idx = pd.to_datetime([_date(2026, 6, 10)])
    flat = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0],
         "Adj Close": [1.0], "Volume": [10]}, index=idx,
    )
    sub = mod._extract_ticker_subframe(flat, "AAPL")
    assert sub is not None
    assert list(sub.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_chunk_tickers_folds_lone_remnant():
    """Chunking avoids a trailing size-1 chunk by folding it into the previous."""
    chunks = mod._chunk_tickers([f"T{i}" for i in range(7)], chunk_size=3)
    # 7 / 3 would naively give [3,3,1]; fold the lone remnant -> [3,4] (no size-1 tail).
    assert all(len(c) > 1 for c in chunks) or len(chunks) == 1
    assert sum(len(c) for c in chunks) == 7


def test_fetch_chunk_whole_failure_routes_all_to_fallback(monkeypatch):
    """A yf.download raise -> every ticker in the chunk failed + chunk_failed=True,
    zero writes."""
    def boom(*a, **k):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(mod.yf, "download", boom)
    from datetime import date as _date
    extracted, failed, chunk_failed = mod._fetch_chunk(
        ["AAA", "BBB"], start=_date(2026, 6, 9), end=_date(2026, 6, 10),
    )
    assert extracted == {}
    assert set(failed) == {"AAA", "BBB"}
    assert chunk_failed is True


def test_fetch_chunk_all_nan_response_is_not_a_chunk_failure(monkeypatch):
    """Codex R1 Major #6: a VALID response where every ticker is present-but-all-NaN
    -> tickers in `failed` but chunk_failed=False (NOT a download failure). This
    keeps the #27 chunk_failures counter honest."""
    from datetime import date as _date
    def all_nan(arg, **k):
        # dates=[...] so the frame has a real dated row of all-NaN (NOT a 0-row
        # .empty frame, which would hit the whole-chunk-failure guard) — Codex R2 M1.
        return _mk_batch_frame({}, missing=("AAA", "BBB"), dates=[_date(2026, 6, 10)])
    monkeypatch.setattr(mod.yf, "download", all_nan)
    extracted, failed, chunk_failed = mod._fetch_chunk(
        ["AAA", "BBB"], start=_date(2026, 6, 9), end=_date(2026, 6, 10),
    )
    assert extracted == {}
    assert set(failed) == {"AAA", "BBB"}
    assert chunk_failed is False


def test_merge_gap_writes_no_meta_and_concats(tmp_path, monkeypatch):
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    _write_archive(tmp_path, "AAPL", FIXED - timedelta(days=1), FIXED - timedelta(days=2))
    sub = pd.DataFrame(
        {"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [20]},
        index=pd.to_datetime([FIXED]),
    )
    mod._merge_gap_subframe(tmp_path, "AAPL", sub, archive_history_days=1260)
    written = pd.read_parquet(tmp_path / "AAPL.parquet")
    assert FIXED in [d.date() for d in written.index]  # gap bar merged
    assert (FIXED - timedelta(days=1)) in [d.date() for d in written.index]  # old bar kept
    # Gap cohort writes NO meta (Arc 6 §4.4) — the file may exist from setup but
    # _merge_gap_subframe must NOT rewrite/refresh it. Assert content unchanged:
    import json
    meta = json.loads((tmp_path / "AAPL.meta.json").read_text())
    assert meta["last_full_refresh_date"] == (FIXED - timedelta(days=2)).isoformat()


def test_merge_gap_overlap_does_not_overwrite_existing_bars(tmp_path, monkeypatch):
    """Codex R1 Critical #1: a deep-band-style sub that overlaps existing
    archived rows (because the band window is wider than this ticker's own gap)
    must NOT overwrite those existing bars — only `> latest_stored` rows merge.
    Discriminating: the overlapping row carries a DIFFERENT Close than the
    archive; the archived value must survive (byte-parity with the serial
    `[latest+1, today]` gap fetch which never re-fetches the old bar).
    """
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    # Archive has two real bars; latest_stored = FIXED - 2.
    archive = pd.DataFrame(
        {"Open": [1.0, 1.0], "High": [1.0, 1.0], "Low": [1.0, 1.0],
         "Close": [50.0, 51.0], "Volume": [10, 11]},
        index=pd.to_datetime([FIXED - timedelta(days=3), FIXED - timedelta(days=2)]),
    )
    archive.to_parquet(tmp_path / "DEEP.parquet")
    # Wide-band sub: re-states the FIXED-2 bar (Close 999 — must be IGNORED) AND
    # adds the genuinely-new FIXED bar (Close 52 — must merge).
    sub = pd.DataFrame(
        {"Open": [9.0, 9.0], "High": [9.0, 9.0], "Low": [9.0, 9.0],
         "Close": [999.0, 52.0], "Volume": [99, 12]},
        index=pd.to_datetime([FIXED - timedelta(days=2), FIXED]),
    )
    mod._merge_gap_subframe(tmp_path, "DEEP", sub, archive_history_days=1260)
    written = pd.read_parquet(tmp_path / "DEEP.parquet").sort_index()
    by_date = {d.date(): c for d, c in written["Close"].items()}
    assert by_date[FIXED - timedelta(days=2)] == 51.0  # existing bar UNCHANGED (not 999)
    assert by_date[FIXED] == 52.0                       # new bar merged
    assert (FIXED - timedelta(days=3)) in by_date       # old bar retained


def test_write_full_refresh_writes_meta(tmp_path, monkeypatch):
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    sub = pd.DataFrame(
        {"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [20]},
        index=pd.to_datetime([FIXED]),
    )
    mod._write_full_refresh_subframe(tmp_path, "NEWBIE", sub, today_session=FIXED,
                                     archive_history_days=1260)
    import json
    meta = json.loads((tmp_path / "NEWBIE.meta.json").read_text())
    assert meta["last_full_refresh_date"] == FIXED.isoformat()
    assert (tmp_path / "NEWBIE.parquet").exists()


def test_warm_dry_run_does_no_fetch(tmp_path, monkeypatch):
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    _write_archive(tmp_path, "GAP1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))

    def boom(*a, **k):
        raise AssertionError("dry_run must NOT call yf.download")
    monkeypatch.setattr(mod.yf, "download", boom)

    report = mod.warm_archives_batch(
        ["GAP1", "NEWBIE"], cache_dir=tmp_path, archive_history_days=1260,
        end_date=FIXED, dry_run=True,
    )
    assert report.dry_run is True
    assert report.gap == 1
    assert report.full_refresh == 1
    mod._full_refresh_stagger_enabled.cache_clear()


def test_warm_populates_gap_so_serial_is_cache_hit(tmp_path, monkeypatch):
    """End-to-end: warm fills the gap, then read_or_fetch_archive does NO fetch."""
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    _write_archive(tmp_path, "GAP1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))

    def fake_download(chunk, **kwargs):
        return _mk_batch_frame({"GAP1": [FIXED]})

    monkeypatch.setattr(mod.yf, "download", fake_download)
    report = mod.warm_archives_batch(
        ["GAP1"], cache_dir=tmp_path, archive_history_days=1260, end_date=FIXED,
    )
    assert report.gap == 1
    assert report.fallback == []
    # Now the serial read must NOT fetch.
    def boom(*a, **k):
        raise AssertionError("serial read should be a cache-hit after warm")
    monkeypatch.setattr(mod.yf, "download", boom)
    df = mod.read_or_fetch_archive("GAP1", end_date=FIXED, cache_dir=tmp_path,
                                   archive_history_days=1260)
    assert df is not None and FIXED in [d.date() for d in df.index]
    mod._full_refresh_stagger_enabled.cache_clear()


def test_warm_all_nan_ticker_lands_in_fallback_archive_unchanged(tmp_path, monkeypatch):
    """F6 end-to-end: an all-NaN ticker -> WarmReport.fallback, archive+meta
    byte-unchanged."""
    from datetime import timedelta
    import json
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    _write_archive(tmp_path, "GAP1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))
    before = (tmp_path / "GAP1.parquet").read_bytes()
    before_meta = (tmp_path / "GAP1.meta.json").read_bytes()

    def fake_download(chunk, **kwargs):
        # GAP1 present-but-all-NaN (F6 shape) — dates=[FIXED] so it has a real
        # all-NaN row, exercising the F6 per-ticker path (not the empty-frame
        # whole-chunk-failure path) — Codex R2 M1.
        return _mk_batch_frame({}, missing=("GAP1",), dates=[FIXED])

    monkeypatch.setattr(mod.yf, "download", fake_download)
    report = mod.warm_archives_batch(
        ["GAP1"], cache_dir=tmp_path, archive_history_days=1260, end_date=FIXED,
    )
    assert "GAP1" in report.fallback
    assert (tmp_path / "GAP1.parquet").read_bytes() == before
    assert (tmp_path / "GAP1.meta.json").read_bytes() == before_meta
    mod._full_refresh_stagger_enabled.cache_clear()


def test_warm_on_off_archive_parity_including_deep_gap(tmp_path, monkeypatch):
    """Warm-ON archives are data-content-identical (value-level assert_frame_equal)
    to serial-path archives over the same fixtures. Discriminating: a deep-gap
    ticker stays INCREMENTAL (no meta, old bar retained) — a promotion bug
    (rejected R2-Major-1) would diverge meta + drop the old bar."""
    from datetime import timedelta
    import json

    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()

    warm_dir = tmp_path / "warm"
    serial_dir = tmp_path / "serial"
    warm_dir.mkdir(); serial_dir.mkdir()

    def seed(d):
        # DEEP: deep gap (latest 200d ago, full refresh only 2d ago -> NOT full-refresh-due).
        deep = pd.DataFrame(
            {"Open": [9.0], "High": [9.0], "Low": [9.0], "Close": [9.0], "Volume": [99]},
            index=pd.to_datetime([FIXED - timedelta(days=200)]),
        )
        deep.to_parquet(d / "DEEP.parquet")
        (d / "DEEP.meta.json").write_text(
            json.dumps({"last_full_refresh_date": (FIXED - timedelta(days=2)).isoformat()})
        )
    seed(warm_dir); seed(serial_dir)

    def fake_download(arg, **kwargs):
        # Codex R1 Major #1: the two paths call yf.download with DIFFERENT shapes.
        #   - WARM: list input  -> ticker-major group_by='ticker' MultiIndex batch.
        #   - SERIAL: str input -> flat single-ticker frame (the _yf_download_window
        #     shape that _squeeze_multiindex + the OHLCV select consume).
        # Both deliver the SAME DEEP bar at FIXED (Close 100, Volume 1000) so the
        # merged archives are value-identical.
        if isinstance(arg, str):
            return pd.DataFrame(
                {"Open": [100.0], "High": [100.0], "Low": [100.0], "Close": [100.0],
                 "Adj Close": [100.0], "Volume": [1000.0]},
                index=pd.to_datetime([FIXED]),
            )
        return _mk_batch_frame({"DEEP": [FIXED]})  # include_adj=True by default

    monkeypatch.setattr(mod.yf, "download", fake_download)

    # WARM path:
    mod.warm_archives_batch(["DEEP"], cache_dir=warm_dir,
                            archive_history_days=1260, end_date=FIXED)
    # SERIAL path (no warm):
    mod.read_or_fetch_archive("DEEP", end_date=FIXED, cache_dir=serial_dir,
                              archive_history_days=1260)

    warm_arch = pd.read_parquet(warm_dir / "DEEP.parquet").sort_index()
    serial_arch = pd.read_parquet(serial_dir / "DEEP.parquet").sort_index()
    # DATA-CONTENT parity: value-level frame equality (canonical column order +
    # sorted index). check_dtype=False because batch-vs-single yfinance returns can
    # differ in int/float Volume dtype — data-content parity is about VALUES, not
    # the parquet bytes (which are fragile across pandas write ordering).
    cols = ["Open", "High", "Low", "Close", "Volume"]
    pd.testing.assert_frame_equal(
        warm_arch[cols], serial_arch[cols], check_dtype=False, check_freq=False,
    )
    # The deep 200d bar is retained (NOT overwritten) and today's bar merged —
    # the C1 lock + the rejected-promotion foil (a full-refresh promotion would
    # tail(N) the single fetched bar, dropping the 200d bar, AND write meta).
    assert (FIXED - timedelta(days=200)) in [d.date() for d in warm_arch.index]
    assert FIXED in [d.date() for d in warm_arch.index]
    # Meta UNCHANGED under both (incremental gap writes no meta).
    warm_meta = json.loads((warm_dir / "DEEP.meta.json").read_text())
    serial_meta = json.loads((serial_dir / "DEEP.meta.json").read_text())
    assert warm_meta == serial_meta
    assert warm_meta["last_full_refresh_date"] == (FIXED - timedelta(days=2)).isoformat()
    mod._full_refresh_stagger_enabled.cache_clear()


def test_merge_gap_missing_archive_raises_no_truncated_write(tmp_path, monkeypatch):
    """Codex R1 Critical #2: if a gap-classified ticker's archive vanished by merge
    time, _merge_gap_subframe must NOT write a truncated sub-only archive (which
    the serial path could then serve as a cache-hit, masking data loss). Pure
    accelerator: raise so _warm_one_window routes the ticker to fallback and the
    serial path stays authoritative."""
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    sub = pd.DataFrame(
        {"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [20]},
        index=pd.to_datetime([FIXED]),
    )
    # No GONE.parquet on disk (archive missing at merge time).
    import pytest
    with pytest.raises(Exception):
        mod._merge_gap_subframe(tmp_path, "GONE", sub, archive_history_days=1260)
    assert not (tmp_path / "GONE.parquet").exists()  # NOTHING written


def test_warm_gap_archive_vanished_routes_to_fallback(tmp_path, monkeypatch):
    """End-to-end: a ticker classified as gap whose parquet is deleted before the
    merge lands in WarmReport.fallback, with NO truncated archive written."""
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    _write_archive(tmp_path, "GAP1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))

    real_extract = mod._extract_ticker_subframe

    def deleting_extract(frame, ticker):
        # Simulate the parquet vanishing between classify and merge.
        (tmp_path / "GAP1.parquet").unlink(missing_ok=True)
        return real_extract(frame, ticker)

    monkeypatch.setattr(mod, "_extract_ticker_subframe", deleting_extract)
    monkeypatch.setattr(mod.yf, "download", lambda *a, **k: _mk_batch_frame({"GAP1": [FIXED]}))
    report = mod.warm_archives_batch(
        ["GAP1"], cache_dir=tmp_path, archive_history_days=1260, end_date=FIXED,
    )
    assert "GAP1" in report.fallback
    assert not (tmp_path / "GAP1.parquet").exists()  # no truncated archive resurrected
    mod._full_refresh_stagger_enabled.cache_clear()


def test_classify_deep_band_threshold_is_trading_days_not_calendar(tmp_path, monkeypatch):
    """Codex R1 Major #3: the deep-gap collapse must trigger at > 30 TRADING days
    (spec §4.2), not at _calendar_window_for_trading_days(30) (~74 calendar days,
    because that helper adds a +30 fetch buffer). A ticker ~50 calendar days stale
    (~36 trading days) is DEEP under the spec but would stay a per-latest gap band
    under the calendar-buffer threshold."""
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()

    # ~50 calendar days (~36 trading days) stale -> DEEP under the trading-day rule.
    _write_archive(tmp_path, "MIDDEEP", FIXED - timedelta(days=50), FIXED - timedelta(days=2))
    # ~14 calendar days (~10 trading days) stale -> NEAR (own gap band).
    _write_archive(tmp_path, "NEARISH", FIXED - timedelta(days=14), FIXED - timedelta(days=2))

    report = mod._classify_warm_cohorts(
        ["MIDDEEP", "NEARISH"], cache_dir=tmp_path, today_session=FIXED,
        archive_history_days=1260, stagger_enabled=False,
    )
    assert "MIDDEEP" in report["deep_gap"], "50-cal-day (~36 trading-day) stale must be DEEP"
    assert "NEARISH" not in report["deep_gap"]
    assert (FIXED - timedelta(days=14)) in report["gap_bands"]  # NEARISH banded by latest
    mod._full_refresh_stagger_enabled.cache_clear()
