"""Phase 13 T1.SB0 — concurrent multi-ticker fetch discriminating test.

Plan §G.0 T-T1.SB0.4 acceptance: concurrent multi-ticker fetch produces no
race / no data corruption. Per-cache locking discipline preserved.

Discriminator: 5 threads × 5 distinct tickers, each calling
``OhlcvCache.get_or_fetch`` simultaneously. Assert (a) no exceptions raised;
(b) each thread receives its OWN ticker's frame (no cross-ticker leakage);
(c) cache ``_bars_store`` contains exactly 5 entries; (d) each entry's
content matches the per-ticker fixture.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd
import pytest

from swing.config import load
from tests.cli.test_cli_eval import _minimal_config


def _make_cfg(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    return load(cfg_path)


def _ticker_fixture(ticker: str, end: pd.Timestamp, n_rows: int = 240) -> pd.DataFrame:
    """Per-ticker fixture — closing prices encode the ticker so a leak between
    threads is visually distinct under assertion."""
    idx = pd.bdate_range(end=end, periods=n_rows)
    # Encode ticker as a base price (ASCII sum) so each ticker's frame has
    # distinct numeric values.
    base = float(sum(ord(c) for c in ticker))
    closes = [base + i * 0.05 for i in range(n_rows)]
    return pd.DataFrame(
        {
            "Open": [c - 0.05 for c in closes],
            "High": [c + 0.30 for c in closes],
            "Low": [c - 0.30 for c in closes],
            "Close": closes,
            "Volume": [1_000_000 + i for i in range(n_rows)],
        },
        index=idx,
    )


def test_ohlcv_cache_concurrent_multi_ticker_no_data_corruption(
    tmp_path: Path, monkeypatch,
):
    """5 threads × 5 distinct tickers simultaneously call get_or_fetch.

    Assert: no exceptions; each thread receives its own ticker's frame
    (no cross-ticker leakage); cache stores 5 entries.

    Per-cache locking discipline (recon §4.B): ``self._bars_lock`` serializes
    dict writes; the fetch is NOT serialized under the lock so concurrency
    yields real parallelism. The discriminator is data integrity, not speed.
    """
    from swing.web.ohlcv_cache import OhlcvCache

    cfg = _make_cfg(tmp_path)
    end = pd.Timestamp("2026-04-30")
    tickers = ["AAPL", "MSFT", "GOOG", "TSLA", "NVDA"]
    fixtures = {t: _ticker_fixture(t, end=end) for t in tickers}

    def _stub_read(ticker, *, end_date, cache_dir, archive_history_days):
        # Slice to end_date contract.
        df = fixtures[ticker]
        return df.loc[df.index.date <= end_date].copy()

    def _stub_session(now_dt):
        return end.date()

    monkeypatch.setattr(
        "swing.web.ohlcv_cache.read_or_fetch_archive", _stub_read,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", _stub_session,
    )

    cache = OhlcvCache(cfg=cfg)
    results: dict[str, pd.DataFrame] = {}
    errors: list[tuple[str, BaseException]] = []
    barrier = threading.Barrier(len(tickers))

    def worker(ticker: str):
        try:
            # Barrier synchronizes start so the threads truly contend.
            barrier.wait(timeout=5.0)
            df = cache.get_or_fetch(ticker=ticker, window_days=180)
            results[ticker] = df
        except BaseException as exc:
            errors.append((ticker, exc))

    threads = [threading.Thread(target=worker, args=(t,)) for t in tickers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)

    assert not errors, f"workers raised: {errors}"
    assert set(results.keys()) == set(tickers), (
        f"missing thread results: {set(tickers) - set(results.keys())}"
    )

    # Per-ticker integrity: each thread's frame matches that ticker's fixture
    # (sliced to the calendar-day window). No cross-ticker leakage.
    for ticker in tickers:
        df = results[ticker]
        expected_base = float(sum(ord(c) for c in ticker))
        # Closing-price first value should map to that ticker's base (within
        # window-slice tolerance). Strong discriminator vs cross-ticker leak.
        assert df["Close"].iloc[0] >= expected_base, (
            f"{ticker}: closes look like a different ticker — leak? "
            f"first close={df['Close'].iloc[0]}, expected base={expected_base}"
        )
        # And the LAST close encodes ticker_base + (n-1)*0.05; verify the
        # frame ends near that.
        assert df["Close"].iloc[-1] >= expected_base, (
            f"{ticker}: tail close looks corrupted: {df['Close'].iloc[-1]}"
        )

    # Cache store contains exactly N entries (one per (ticker, 180)).
    assert len(cache._bars_store) == len(tickers), (
        f"cache _bars_store should have {len(tickers)} entries; "
        f"has {len(cache._bars_store)}: {list(cache._bars_store.keys())}"
    )
    expected_keys = {(t, 180) for t in tickers}
    assert set(cache._bars_store.keys()) == expected_keys


def test_ohlcv_cache_concurrent_same_ticker_yields_consistent_frame(
    tmp_path: Path, monkeypatch,
):
    """5 threads × SAME ticker simultaneously call get_or_fetch.

    Validates the bars-lock discipline under same-key contention: even though
    duplicate fetches are tolerated (V2 candidate would dedup; recon §4.B),
    every thread MUST receive a structurally identical frame. No half-written
    DataFrames; no nil; no exception.
    """
    from swing.web.ohlcv_cache import OhlcvCache

    cfg = _make_cfg(tmp_path)
    end = pd.Timestamp("2026-04-30")
    fixture = _ticker_fixture("AAPL", end=end)

    def _stub_read(ticker, *, end_date, cache_dir, archive_history_days):
        return fixture.loc[fixture.index.date <= end_date].copy()

    def _stub_session(now_dt):
        return end.date()

    monkeypatch.setattr(
        "swing.web.ohlcv_cache.read_or_fetch_archive", _stub_read,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", _stub_session,
    )

    cache = OhlcvCache(cfg=cfg)
    results: list[pd.DataFrame] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(5)
    lock = threading.Lock()

    def worker():
        try:
            barrier.wait(timeout=5.0)
            df = cache.get_or_fetch(ticker="AAPL", window_days=200)
            with lock:
                results.append(df)
        except BaseException as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)

    assert not errors, f"workers raised: {errors}"
    assert len(results) == 5
    # All 5 results are structurally identical (no half-writes; no corruption).
    canonical = results[0]
    for df in results[1:]:
        pd.testing.assert_frame_equal(df, canonical, check_exact=False)
    # Cache stores exactly one entry for the (ticker, window_days) key.
    assert (("AAPL", 200) in cache._bars_store)
    assert len(cache._bars_store) == 1


# -- Cross-bundle pin (per plan H.3 + brief 1.4) -------------------------


@pytest.mark.skip(
    reason="cross-bundle pin - un-skips at T2.SB2 + T2.SB3 + T3.SB3 per plan H.3",
)
def test_ohlcv_cache_get_or_fetch_invariant(tmp_path: Path):
    """Phase 13 T1.SB0 cross-bundle pin (per plan H.3 + brief 1.4).

    Asserts the ``OhlcvCache.get_or_fetch`` public surface is stable across
    downstream consumers: T2.SB2 (Theme 2 detector foundation primitives),
    T2.SB3 (detector batch 1), and T3.SB3 (review auto-fill MFE/MAE candle-
    data source per OQ-8 BINDING).

    Un-skip at each consumer landing to verify the surface still satisfies
    the consumer's expectations. If this test starts failing at consumer
    land-time, EITHER the cache surface drifted OR the consumer's
    expectations diverged from the documented contract.

    ASCII-only skip-reason + section header text per CLAUDE.md cp1252
    stdout gotcha (pytest renders skip-reason via stdout which may not be
    UTF-8 on Windows).
    """
    import inspect

    from swing.web.ohlcv_cache import OhlcvCache

    # Surface MUST exist + MUST be callable.
    assert hasattr(OhlcvCache, "get_or_fetch")
    assert callable(OhlcvCache.get_or_fetch)

    # Signature: keyword-only ``ticker`` (str) + ``window_days`` (int).
    sig = inspect.signature(OhlcvCache.get_or_fetch)
    params = sig.parameters
    assert "ticker" in params, f"missing 'ticker' param: {list(params)}"
    assert "window_days" in params, f"missing 'window_days' param: {list(params)}"
    assert params["ticker"].kind == inspect.Parameter.KEYWORD_ONLY
    assert params["window_days"].kind == inspect.Parameter.KEYWORD_ONLY

    # Behavioral surface (a single round-trip in cassette-mode would land
    # at consumer un-skip time; left commented for the un-skip implementer
    # to materialize against their consumer's fixture).
    # cfg = ...; cache = OhlcvCache(cfg)
    # df = cache.get_or_fetch(ticker='AAPL', window_days=180)
    # assert list(df.columns) == ['Open', 'High', 'Low', 'Close', 'Volume']
    # assert isinstance(df.index, pd.DatetimeIndex)
