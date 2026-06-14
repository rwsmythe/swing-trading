"""Arc 8 — trailing-bar NaN-Close write barrier.

The run-#99 shape: yfinance returns a trailing bar with NaN `Close` while
Open/High/Low/Volume are PRESENT (the adjusted-close derivation artifact).
The barrier trims trailing ragged rows (any of OHLC NaN) at the fetch
boundary; interior ragged rows are PRESERVED (the Phase-15 bad-bar-accept
posture for HISTORICAL bars is unchanged). Volume-only-NaN does NOT trim.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from swing.data import ohlcv_archive as mod


def _flat_frame(rows: dict) -> pd.DataFrame:
    """Build a flat single-ticker OHLCV frame: {date: (O, H, L, C, V)}; any
    field may be float('nan')."""
    idx = pd.to_datetime(sorted(rows))
    data = {c: [] for c in ("Open", "High", "Low", "Close", "Volume")}
    for d in sorted(rows):
        o, h, l, c, v = rows[d]
        data["Open"].append(o)
        data["High"].append(h)
        data["Low"].append(l)
        data["Close"].append(c)
        data["Volume"].append(v)
    return pd.DataFrame(data, index=idx)


NAN = float("nan")


# ----- pure helper unit tests -------------------------------------------------

def test_trim_single_trailing_ragged_close_only():
    """(#99) single trailing NaN-Close row (O/H/L/V present) -> trimmed; clean
    prefix retained; count == 1."""
    d1, d2 = date(2026, 6, 9), date(2026, 6, 10)
    df = _flat_frame({
        d1: (10.0, 11.0, 9.0, 10.5, 1000),
        d2: (10.5, 11.5, 10.0, NAN, 1200),  # trailing ragged
    })
    trimmed, n = mod._trim_trailing_ragged(df)
    assert n == 1
    assert [d.date() for d in trimmed.index] == [d1]


def test_trim_multiple_consecutive_trailing_ragged():
    """(c) multiple consecutive trailing ragged rows -> ALL trimmed."""
    d1, d2, d3 = date(2026, 6, 8), date(2026, 6, 9), date(2026, 6, 10)
    df = _flat_frame({
        d1: (10.0, 11.0, 9.0, 10.5, 1000),
        d2: (10.5, 11.5, 10.0, NAN, 1200),  # ragged
        d3: (NAN, 11.0, 10.0, 10.0, 1100),  # ragged (Open NaN)
    })
    trimmed, n = mod._trim_trailing_ragged(df)
    assert n == 2
    assert [d.date() for d in trimmed.index] == [d1]


def test_trim_interior_nan_preserved_discriminator():
    """(d) an INTERIOR NaN-Close row is PRESERVED — this FAILS under an
    over-eager drop-all-NaN-rows implementation."""
    d1, d2, d3 = date(2026, 6, 8), date(2026, 6, 9), date(2026, 6, 10)
    df = _flat_frame({
        d1: (10.0, 11.0, 9.0, 10.5, 1000),
        d2: (10.5, 11.5, 10.0, NAN, 1200),  # INTERIOR ragged
        d3: (10.0, 11.0, 10.0, 10.8, 1100),  # clean trailing
    })
    trimmed, n = mod._trim_trailing_ragged(df)
    assert n == 0
    assert [d.date() for d in trimmed.index] == [d1, d2, d3]


def test_trim_volume_only_nan_not_trimmed():
    """(i) a trailing row with ONLY Volume NaN (OHLC present) is NOT trimmed."""
    d1, d2 = date(2026, 6, 9), date(2026, 6, 10)
    df = _flat_frame({
        d1: (10.0, 11.0, 9.0, 10.5, 1000),
        d2: (10.5, 11.5, 10.0, 10.8, NAN),  # volume-only NaN
    })
    trimmed, n = mod._trim_trailing_ragged(df)
    assert n == 0
    assert [d.date() for d in trimmed.index] == [d1, d2]


def test_trim_all_rows_ragged_to_empty():
    """All-ragged frame trims to EMPTY; count == len."""
    d1, d2 = date(2026, 6, 9), date(2026, 6, 10)
    df = _flat_frame({
        d1: (10.0, 11.0, 9.0, NAN, 1000),
        d2: (10.5, 11.5, 10.0, NAN, 1200),
    })
    trimmed, n = mod._trim_trailing_ragged(df)
    assert n == 2
    assert trimmed.empty
    assert list(trimmed.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_trim_clean_frame_unchanged():
    d1, d2 = date(2026, 6, 9), date(2026, 6, 10)
    df = _flat_frame({
        d1: (10.0, 11.0, 9.0, 10.5, 1000),
        d2: (10.5, 11.5, 10.0, 10.8, 1200),
    })
    trimmed, n = mod._trim_trailing_ragged(df)
    assert n == 0
    pd.testing.assert_frame_equal(trimmed, df)


def test_trim_trailing_inf_close_phase18():
    """Phase 18 18-A: a trailing +inf Close is NON-FINITE -> trimmed. The shared
    is_finite_ohlc uses math.isfinite (matching the engine gate), a strict
    superset of the old isna()-only check, which would have KEPT the inf row.
    Locks the beneficial broadening; the NaN cases above still pass identically."""
    d1, d2 = date(2026, 6, 9), date(2026, 6, 10)
    df = _flat_frame({
        d1: (10.0, 11.0, 9.0, 10.5, 1000),
        d2: (10.5, 11.5, 10.0, float("inf"), 1200),  # trailing non-finite (inf)
    })
    trimmed, n = mod._trim_trailing_ragged(df)
    assert n == 1
    assert [d.date() for d in trimmed.index] == [d1]


def test_trim_empty_frame_is_noop():
    df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    trimmed, n = mod._trim_trailing_ragged(df)
    assert n == 0
    assert trimmed.empty


# ----- Phase 18 18-B: shape-agnostic column tuple (lowercase Shape-A) ----------

def test_trim_lowercase_shape_a_trailing_nan_phase18b():
    """Phase 18 18-B: the Shape-A (ladder) frame uses LOWERCASE open/high/low/close.
    The generalized barrier trims a trailing Close=NaN row (the 06-10 artifact)
    when handed the lowercase column tuple, via the SAME is_finite_ohlc predicate.
    PRE-FIX (capitalized-only detection) the lowercase frame's ohlc list is EMPTY
    -> the barrier no-ops -> n == 0 (the NaN row survives)."""
    df = pd.DataFrame({
        "asof_date": ["2026-06-09", "2026-06-10"],
        "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.0, 10.0],
        "close": [10.5, float("nan")], "volume": [1000, 1200],
    })
    trimmed, n = mod._trim_trailing_ragged(
        df, columns=("open", "high", "low", "close"))
    assert n == 1
    assert list(trimmed["asof_date"]) == ["2026-06-09"]


def test_trim_lowercase_shape_a_interior_nan_preserved_phase18b():
    """LOCK 4: interior non-finite bar PRESERVED; only trailing trimmed."""
    df = pd.DataFrame({
        "asof_date": ["2026-06-08", "2026-06-09", "2026-06-10"],
        "open": [10.0, float("nan"), 10.5], "high": [11.0, 11.0, 11.5],
        "low": [9.0, 9.0, 10.0], "close": [10.5, 10.6, 10.7], "volume": [1, 2, 3],
    })
    trimmed, n = mod._trim_trailing_ragged(
        df, columns=("open", "high", "low", "close"))
    assert n == 0  # trailing row is finite -> nothing trimmed; interior NaN kept
    assert len(trimmed) == 3


def test_trim_lowercase_shape_a_volume_only_nan_exempt_phase18b():
    """Volume-only-NaN trailing row is NOT trimmed (volume excluded from the tuple)."""
    df = pd.DataFrame({
        "asof_date": ["2026-06-09", "2026-06-10"],
        "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.0, 10.0],
        "close": [10.5, 10.7], "volume": [1000, float("nan")],
    })
    trimmed, n = mod._trim_trailing_ragged(
        df, columns=("open", "high", "low", "close"))
    assert n == 0
    assert len(trimmed) == 2


def test_trim_capitalized_default_unchanged_phase18b():
    """Behavior-preserving: existing capitalized callers (default arg) still work
    with NO columns= passed -> identical to the pre-18-B barrier."""
    d1, d2 = date(2026, 6, 9), date(2026, 6, 10)
    df = _flat_frame({
        d1: (10.0, 11.0, 9.0, 10.5, 1000),
        d2: (10.5, 11.5, 10.0, float("nan"), 1200),
    })
    trimmed, n = mod._trim_trailing_ragged(df)  # no columns= -> capitalized default
    assert n == 1
    assert [d.date() for d in trimmed.index] == [d1]


# ----- serial path integration ------------------------------------------------

def _flat_yf_frame(rows: dict) -> pd.DataFrame:
    """Like _flat_frame but with the 'Adj Close' column yfinance returns (and
    _yf_download_window drops)."""
    base = _flat_frame(rows)
    base.insert(4, "Adj Close", base["Close"].values)
    return base


def test_yf_download_window_trims_trailing_ragged(monkeypatch):
    """The serial fetch wrapper trims trailing ragged rows from its return —
    one site covering BOTH serial branches."""
    d1, d2 = date(2026, 6, 9), date(2026, 6, 10)
    frame = _flat_yf_frame({
        d1: (10.0, 11.0, 9.0, 10.5, 1000),
        d2: (10.5, 11.5, 10.0, NAN, 1200),  # trailing ragged
    })
    monkeypatch.setattr(mod.yf, "download", lambda *a, **k: frame)
    out = mod._yf_download_window("AAA", start=d1, end=d2)
    assert [d.date() for d in out.index] == [d1]
    assert list(out.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_full_refresh_trims_trailing_ragged_writes_clean_prefix(tmp_path, monkeypatch):
    """(a) full-refresh path: trailing ragged trimmed, clean prefix written +
    meta stamped."""
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    frame = _flat_yf_frame({
        FIXED - timedelta(days=2): (10.0, 11.0, 9.0, 10.5, 1000),
        FIXED - timedelta(days=1): (10.2, 11.2, 9.5, 10.6, 1100),
        FIXED: (10.5, 11.5, 10.0, NAN, 1200),  # trailing ragged
    })
    monkeypatch.setattr(mod.yf, "download", lambda *a, **k: frame)
    out = mod.read_or_fetch_archive("AAA", end_date=FIXED, cache_dir=tmp_path,
                                    archive_history_days=1260)
    assert FIXED not in [d.date() for d in out.index]
    arch = pd.read_parquet(tmp_path / "AAA.parquet")
    assert FIXED not in [d.date() for d in arch.index]
    # meta IS stamped (a full-refresh that wrote a clean prefix)
    meta = json.loads((tmp_path / "AAA.meta.json").read_text())
    assert meta["last_full_refresh_date"] == FIXED.isoformat()


def test_gap_trims_only_tail(tmp_path, monkeypatch):
    """(b) multi-day gap window with only the tail ragged -> prefix appended,
    tail trimmed."""
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    # Seed an archive ending 3 days ago, full-refreshed 1 day ago (NOT due).
    seed = _flat_frame({FIXED - timedelta(days=3): (8.0, 8.0, 8.0, 8.0, 50)})
    seed.to_parquet(tmp_path / "AAA.parquet")
    (tmp_path / "AAA.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (FIXED - timedelta(days=1)).isoformat()})
    )
    gap = _flat_yf_frame({
        FIXED - timedelta(days=2): (10.0, 11.0, 9.0, 10.5, 1000),
        FIXED - timedelta(days=1): (10.2, 11.2, 9.5, 10.6, 1100),
        FIXED: (10.5, 11.5, 10.0, NAN, 1200),  # trailing ragged
    })
    monkeypatch.setattr(mod.yf, "download", lambda *a, **k: gap)
    mod.read_or_fetch_archive("AAA", end_date=FIXED, cache_dir=tmp_path,
                              archive_history_days=1260)
    arch = pd.read_parquet(tmp_path / "AAA.parquet")
    arch_dates = [d.date() for d in arch.index]
    assert FIXED not in arch_dates
    assert (FIXED - timedelta(days=1)) in arch_dates  # clean prefix appended
    assert (FIXED - timedelta(days=3)) in arch_dates   # original retained
    mod._full_refresh_stagger_enabled.cache_clear()


def test_gap_trim_to_empty_no_write(tmp_path, monkeypatch):
    """(e) gap fetch trimmed to EMPTY -> no write, archive byte-identical, meta
    unchanged."""
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    seed = _flat_frame({FIXED - timedelta(days=2): (8.0, 8.0, 8.0, 8.0, 50)})
    seed.to_parquet(tmp_path / "AAA.parquet")
    (tmp_path / "AAA.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (FIXED - timedelta(days=1)).isoformat()})
    )
    before_bytes = (tmp_path / "AAA.parquet").read_bytes()
    before_meta = (tmp_path / "AAA.meta.json").read_text()
    # gap = only a single ragged row at FIXED -> trims to empty
    gap = _flat_yf_frame({FIXED: (10.5, 11.5, 10.0, NAN, 1200)})
    monkeypatch.setattr(mod.yf, "download", lambda *a, **k: gap)
    mod.read_or_fetch_archive("AAA", end_date=FIXED, cache_dir=tmp_path,
                              archive_history_days=1260)
    assert (tmp_path / "AAA.parquet").read_bytes() == before_bytes
    assert (tmp_path / "AAA.meta.json").read_text() == before_meta
    mod._full_refresh_stagger_enabled.cache_clear()


def test_full_refresh_trim_to_empty_falls_back(tmp_path, monkeypatch):
    """(f) full-refresh fetch trimmed to EMPTY -> existing F6 empty handling: no
    archive clobber, meta stays stale (retry next call)."""
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    # Seed an archive that is full-refresh-DUE (8 days since refresh).
    seed = _flat_frame({FIXED - timedelta(days=8): (8.0, 8.0, 8.0, 8.0, 50)})
    seed.to_parquet(tmp_path / "AAA.parquet")
    (tmp_path / "AAA.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (FIXED - timedelta(days=8)).isoformat()})
    )
    before_bytes = (tmp_path / "AAA.parquet").read_bytes()
    before_meta = (tmp_path / "AAA.meta.json").read_text()
    # full-refresh fetch returns only a ragged row -> trims to empty -> empty F6.
    fr = _flat_yf_frame({FIXED: (10.5, 11.5, 10.0, NAN, 1200)})
    monkeypatch.setattr(mod.yf, "download", lambda *a, **k: fr)
    out = mod.read_or_fetch_archive("AAA", end_date=FIXED, cache_dir=tmp_path,
                                    archive_history_days=1260)
    assert out is not None and not out.empty  # served from retained archive
    assert (tmp_path / "AAA.parquet").read_bytes() == before_bytes
    assert (tmp_path / "AAA.meta.json").read_text() == before_meta
    mod._full_refresh_stagger_enabled.cache_clear()


# ----- warm batch path --------------------------------------------------------

def _batch_frame(per_ticker: dict) -> pd.DataFrame:
    """{ticker: {date: (o,h,l,c,v)}} -> group_by='ticker' MultiIndex batch frame
    with an Adj Close column (the real yf.download batch shape)."""
    all_dates = sorted({d for rows in per_ticker.values() for d in rows})
    idx = pd.to_datetime(all_dates)
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    cols = pd.MultiIndex.from_product([list(per_ticker), fields])
    df = pd.DataFrame(index=idx, columns=cols, dtype=float)
    for t, rows in per_ticker.items():
        for d, (o, h, l, c, v) in rows.items():
            ts = pd.Timestamp(d)
            df.loc[ts, (t, "Open")] = o
            df.loc[ts, (t, "High")] = h
            df.loc[ts, (t, "Low")] = l
            df.loc[ts, (t, "Close")] = c
            df.loc[ts, (t, "Adj Close")] = c
            df.loc[ts, (t, "Volume")] = v
    return df


def test_warm_report_has_trailing_nan_trimmed_field():
    """(h) additive field defaults to 0."""
    assert mod.WarmReport().trailing_nan_trimmed == 0


def _seed_gap(d, ticker, FIXED):
    """Seed `ticker` as a NOT-due gap cohort member (archive 3d old, refreshed 1d)."""
    seed = _flat_frame({FIXED - timedelta(days=3): (8.0, 8.0, 8.0, 8.0, 50)})
    seed.to_parquet(d / f"{ticker}.parquet")
    (d / f"{ticker}.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (FIXED - timedelta(days=1)).isoformat()})
    )


def test_warm_gap_trims_trailing_ragged(tmp_path, monkeypatch):
    """A warm gap subframe with a trailing ragged row -> trimmed before merge;
    archive gets the clean prefix, NOT the ragged row; report counts the trim;
    the ticker is NOT routed to fallback."""
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    _seed_gap(tmp_path, "AAA", FIXED)
    batch = _batch_frame({"AAA": {
        FIXED - timedelta(days=2): (10.0, 11.0, 9.0, 10.5, 1000),
        FIXED - timedelta(days=1): (10.2, 11.2, 9.5, 10.6, 1100),
        FIXED: (10.5, 11.5, 10.0, NAN, 1200),  # trailing ragged
    }})
    monkeypatch.setattr(mod.yf, "download", lambda *a, **k: batch)
    report = mod.warm_archives_batch(["AAA"], cache_dir=tmp_path,
                                     archive_history_days=1260, end_date=FIXED)
    arch = pd.read_parquet(tmp_path / "AAA.parquet")
    arch_dates = [d.date() for d in arch.index]
    assert FIXED not in arch_dates
    assert (FIXED - timedelta(days=1)) in arch_dates
    assert report.trailing_nan_trimmed == 1
    assert "AAA" not in report.fallback
    mod._full_refresh_stagger_enabled.cache_clear()


def test_warm_trim_to_empty_skips_without_fallback(tmp_path, monkeypatch):
    """A warm gap subframe whose ONLY new row is ragged -> trims to empty ->
    skip-without-fallback: no merge, archive unchanged, ticker NOT in fallback,
    trim counted."""
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    _seed_gap(tmp_path, "AAA", FIXED)
    before = (tmp_path / "AAA.parquet").read_bytes()
    batch = _batch_frame({"AAA": {FIXED: (10.5, 11.5, 10.0, NAN, 1200)}})
    monkeypatch.setattr(mod.yf, "download", lambda *a, **k: batch)
    report = mod.warm_archives_batch(["AAA"], cache_dir=tmp_path,
                                     archive_history_days=1260, end_date=FIXED)
    assert (tmp_path / "AAA.parquet").read_bytes() == before
    assert "AAA" not in report.fallback
    assert report.trailing_nan_trimmed == 1
    mod._full_refresh_stagger_enabled.cache_clear()


def test_warm_serial_parity_with_ragged_tail(tmp_path, monkeypatch):
    """(g) warm-ON archives are data-content-identical to serial-path archives
    over a fixture whose tail is ragged — the trim fires identically on both."""
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    warm_dir = tmp_path / "warm"
    serial_dir = tmp_path / "serial"
    warm_dir.mkdir(); serial_dir.mkdir()
    _seed_gap(warm_dir, "AAA", FIXED)
    _seed_gap(serial_dir, "AAA", FIXED)

    rows = {
        FIXED - timedelta(days=2): (10.0, 11.0, 9.0, 10.5, 1000),
        FIXED - timedelta(days=1): (10.2, 11.2, 9.5, 10.6, 1100),
        FIXED: (10.5, 11.5, 10.0, NAN, 1200),  # ragged tail
    }

    def fake_download(arg, **kwargs):
        if isinstance(arg, str):
            return _flat_yf_frame(rows)            # serial single-ticker shape
        return _batch_frame({"AAA": rows})          # warm batch shape

    monkeypatch.setattr(mod.yf, "download", fake_download)
    mod.warm_archives_batch(["AAA"], cache_dir=warm_dir,
                            archive_history_days=1260, end_date=FIXED)
    mod.read_or_fetch_archive("AAA", end_date=FIXED, cache_dir=serial_dir,
                              archive_history_days=1260)
    cols = ["Open", "High", "Low", "Close", "Volume"]
    warm_arch = pd.read_parquet(warm_dir / "AAA.parquet").sort_index()
    serial_arch = pd.read_parquet(serial_dir / "AAA.parquet").sort_index()
    pd.testing.assert_frame_equal(
        warm_arch[cols], serial_arch[cols], check_dtype=False, check_freq=False,
    )
    assert FIXED not in [d.date() for d in warm_arch.index]
    mod._full_refresh_stagger_enabled.cache_clear()


def test_merge_gap_fresh_empty_does_not_write(tmp_path, monkeypatch):
    """Codex R1 MAJOR — when a trailing trim leaves a warm gap subframe with
    ONLY overlap rows (<= latest_stored), nothing is fresh; _merge_gap_subframe
    must NOT rewrite the archive, matching the serial gap path's
    no-write-when-nothing-fresh (the trim-to-empty parity-by-construction)."""
    FIXED = date(2026, 6, 10)
    archive = _flat_frame({
        FIXED - timedelta(days=3): (1.0, 1.0, 1.0, 50.0, 10),
        FIXED - timedelta(days=2): (1.0, 1.0, 1.0, 51.0, 11),
    })
    archive.to_parquet(tmp_path / "DEEP.parquet")
    calls: list[int] = []
    monkeypatch.setattr(mod, "_write_archive_atomic", lambda *a, **k: calls.append(1))
    # sub carries ONLY an overlap row (<= latest_stored FIXED-2); nothing fresh.
    sub = _flat_frame({FIXED - timedelta(days=2): (9.0, 9.0, 9.0, 999.0, 99)})
    mod._merge_gap_subframe(tmp_path, "DEEP", sub, archive_history_days=1260)
    assert calls == []  # no write when nothing is fresh
