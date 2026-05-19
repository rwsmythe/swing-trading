"""Phase 13 T1.SB0 — shape-parity discriminating test for OhlcvCache.get_or_fetch.

Plan §G.0 T-T1.SB0.2 acceptance: DataFrames identical between cache + legacy paths.

Adaptation note (recon §2.D + §9): plan template uses
``fetch_daily_bars(ticker='AAPL', lookback_days=180, ...)`` which TypeErrors —
``fetch_daily_bars`` takes ``n_bars`` not ``lookback_days``. This test compares
against ``PriceFetcher.get(ticker, lookback_days, as_of_date=None)`` instead —
the actual legacy callsite delegate used at
``swing/pipeline/runner.py:1323`` inside ``_step_charts``.

Adaptation note (recon §2.D): plan template imports ``load_cfg`` from
``swing.config`` — actual function name is ``load``. Test uses ``load``
+ a local minimal-config helper (mirroring ``tests/web/conftest.py:test_cfg``).

The test monkeypatches ``read_or_fetch_archive`` at BOTH module-level import
sites so PriceFetcher + OhlcvCache see identical fixture data — proves
end-to-end shape equivalence (columns + index + values).
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from swing.config import load
from tests.cli.test_cli_eval import _minimal_config


def _make_cfg(tmp_path: Path):
    """Construct a minimal Config rooted at tmp_path (mirrors tests/web/conftest.py:test_cfg)."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    return load(cfg_path)


def _fixture_daily_bars(*, end: pd.Timestamp, n_rows: int = 240) -> pd.DataFrame:
    """Construct a deterministic OHLCV DataFrame with capitalized columns + DatetimeIndex.

    Mirrors the shape returned by ``read_or_fetch_archive`` — the source-of-truth
    shape both ``PriceFetcher.get`` and ``OhlcvCache.get_or_fetch`` slice over.
    """
    idx = pd.date_range(end=end, periods=n_rows, freq="B")
    # Deterministic non-trivial OHLCV (rising trend with realistic spreads).
    closes = [100.0 + i * 0.1 for i in range(n_rows)]
    opens = [c - 0.05 for c in closes]
    highs = [c + 0.30 for c in closes]
    lows = [c - 0.30 for c in closes]
    volumes = [1_000_000 + i * 100 for i in range(n_rows)]
    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=idx,
    )
    return df


def test_ohlcv_cache_get_or_fetch_shape_matches_legacy_price_fetcher(
    tmp_path: Path, monkeypatch
):
    """Shape parity (T-T1.SB0.2 acceptance): OhlcvCache.get_or_fetch returns a
    DataFrame identical (columns + index + values) to PriceFetcher.get for
    the same ticker + window.

    Plant a fixture archive via monkeypatch; instantiate both surfaces; compare.

    Pre-implementation: fails with AttributeError (no get_or_fetch method).
    Post-implementation: passes with identical DataFrames.
    """
    from swing.prices import PriceFetcher
    from swing.web.ohlcv_cache import OhlcvCache

    cfg = _make_cfg(tmp_path)
    # End at a fixed past date (so action_session_for_run / last_completed_session
    # don't drift the resolved 'effective' date out of the fixture's range).
    end = pd.Timestamp("2026-04-30")
    fixture_df = _fixture_daily_bars(end=end, n_rows=300)

    def _stub_read_or_fetch_archive(ticker, *, end_date, cache_dir, archive_history_days):
        # Mimic the helper's contract: full-history DataFrame ending at end_date.
        # The caller slices; we return the full archive.
        return fixture_df.loc[fixture_df.index.date <= end_date].copy()

    # Both surfaces resolve `as_of_date=None` via session helpers that consult
    # `datetime.now()`. Pin the resolved session to a deterministic date.
    fixed_session = end.date()

    def _stub_last_completed_session(now_dt):
        return fixed_session

    # Patch both name bindings so PriceFetcher (via swing.prices) +
    # OhlcvCache.get_or_fetch (via swing.web.ohlcv_cache) see the same fixture.
    monkeypatch.setattr(
        "swing.prices.read_or_fetch_archive", _stub_read_or_fetch_archive
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.read_or_fetch_archive",
        _stub_read_or_fetch_archive,
        raising=False,  # Attribute does not exist yet (pre-implementation).
    )
    # Pin session anchor. PriceFetcher's `_resolve_asof` performs a deferred
    # `from swing.evaluation.dates import last_completed_session` inside the
    # function body, so patching `swing.prices.last_completed_session` does NOT
    # affect that path. Patch the canonical source in
    # `swing.evaluation.dates` instead — both PriceFetcher (via deferred
    # import) and OhlcvCache (via module-level import) resolve to the stub.
    monkeypatch.setattr(
        "swing.evaluation.dates.last_completed_session",
        _stub_last_completed_session,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", _stub_last_completed_session,
        raising=False,
    )

    cache = OhlcvCache(cfg=cfg)
    cache_df = cache.get_or_fetch(ticker="AAPL", window_days=180)

    fetcher = PriceFetcher(
        cache_dir=cfg.paths.prices_cache_dir,
        archive_history_days=cfg.archive.archive_history_days,
    )
    legacy_df = fetcher.get("AAPL", lookback_days=180, as_of_date=None)

    assert list(cache_df.columns) == ["Open", "High", "Low", "Close", "Volume"], (
        f"cache columns drift: {list(cache_df.columns)}"
    )
    assert list(legacy_df.columns) == ["Open", "High", "Low", "Close", "Volume"], (
        f"legacy columns drift: {list(legacy_df.columns)}"
    )
    assert isinstance(cache_df.index, pd.DatetimeIndex), (
        f"cache index type drift: {type(cache_df.index).__name__}"
    )
    pd.testing.assert_frame_equal(cache_df, legacy_df, check_exact=False, rtol=1e-9)


def test_ohlcv_cache_get_or_fetch_returns_dataframe_with_capitalized_columns_and_datetime_index(
    tmp_path: Path, monkeypatch
):
    """Surface invariant (T-T1.SB0.2 acceptance + cross-bundle pin precursor):
    the get_or_fetch return type/shape is the surface T2.SB2 + T2.SB3 + T3.SB3
    will consume.

    Discriminator: any drift from capitalized-OHLCV + DatetimeIndex breaks the
    classifier/render_chart contract at the existing ``_step_charts`` callsite.
    """
    from swing.web.ohlcv_cache import OhlcvCache

    cfg = _make_cfg(tmp_path)
    end = pd.Timestamp("2026-04-30")
    fixture_df = _fixture_daily_bars(end=end, n_rows=300)

    def _stub(ticker, *, end_date, cache_dir, archive_history_days):
        return fixture_df.loc[fixture_df.index.date <= end_date].copy()

    def _stub_session(now_dt):
        return end.date()

    monkeypatch.setattr(
        "swing.web.ohlcv_cache.read_or_fetch_archive", _stub, raising=False,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", _stub_session, raising=False,
    )

    cache = OhlcvCache(cfg=cfg)
    df = cache.get_or_fetch(ticker="MSFT", window_days=200)

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert len(df) > 0
    # Window cap: calendar-day lookback (matches PriceFetcher.get semantics).
    # Within tolerance of business-day count for a 200-day calendar window
    # (~145 business days; allow ±5 for boundary effects).
    cutoff = end.date() - timedelta(days=200)
    assert all(d.date() >= cutoff for d in df.index)
    assert all(d.date() <= end.date() for d in df.index)


def test_ohlcv_cache_get_or_fetch_raises_value_error_on_empty_archive(
    tmp_path: Path, monkeypatch
):
    """Empty-archive contract (matches PriceFetcher.get's raise-on-empty
    behavior so ``_step_charts``'s ``except Exception`` produces
    ``chart_status='fetcher_failed'`` unchanged).

    Discriminator: silent ``None`` return would BREAK the existing
    ``_step_charts`` line 1322-1330 contract.
    """
    from swing.web.ohlcv_cache import OhlcvCache

    cfg = _make_cfg(tmp_path)

    def _stub_empty(ticker, *, end_date, cache_dir, archive_history_days):
        return None

    def _stub_session(now_dt):
        return pd.Timestamp("2026-04-30").date()

    monkeypatch.setattr(
        "swing.web.ohlcv_cache.read_or_fetch_archive", _stub_empty, raising=False,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", _stub_session, raising=False,
    )

    cache = OhlcvCache(cfg=cfg)
    with pytest.raises(ValueError, match="No data"):
        cache.get_or_fetch(ticker="DELISTED", window_days=180)


def test_ohlcv_cache_get_or_fetch_returns_defensive_copy(
    tmp_path: Path, monkeypatch,
):
    """Codex R3 Minor #1 fix (2026-05-18): the cached DataFrame is mutable;
    returning it by reference would let one consumer corrupt the value
    observed by later consumers within the TTL window.

    Discriminator: mutate the returned frame; a second call within TTL
    must return an UNCORRUPTED frame matching the original fixture.
    """
    from swing.web.ohlcv_cache import OhlcvCache

    cfg = _make_cfg(tmp_path)
    end = pd.Timestamp("2026-04-30")
    fixture_df = _fixture_daily_bars(end=end, n_rows=300)

    def _stub(ticker, *, end_date, cache_dir, archive_history_days):
        return fixture_df.loc[fixture_df.index.date <= end_date].copy()

    def _stub_session(now_dt):
        return end.date()

    monkeypatch.setattr(
        "swing.web.ohlcv_cache.read_or_fetch_archive", _stub, raising=False,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", _stub_session,
        raising=False,
    )

    cache = OhlcvCache(cfg=cfg)
    df1 = cache.get_or_fetch(ticker="AAPL", window_days=180)
    original_first_close = float(df1["Close"].iloc[0])

    # Mutate the returned frame in place (simulates a misbehaving consumer).
    df1.loc[df1.index[0], "Close"] = -999.0

    # Second call within TTL — MUST return uncorrupted value.
    df2 = cache.get_or_fetch(ticker="AAPL", window_days=180)
    assert float(df2["Close"].iloc[0]) == original_first_close, (
        "cache corruption — consumer mutation of df1 reached cached value"
    )
    # And df1 and df2 must NOT be the same object (defensive copy returned).
    assert df1 is not df2, (
        "cache returned same object reference — copy-on-read failed"
    )


def test_ohlcv_cache_get_or_fetch_caches_within_ttl(tmp_path: Path, monkeypatch):
    """Cache discipline (T-T1.SB0.2 acceptance + Phase 11 forward-binding lesson):
    second call within TTL returns the cached DataFrame WITHOUT re-invoking
    the archive helper.

    Discriminator: per-cache locking must serialize the cache-write inside
    ``self._bars_lock`` so the second call's cache scan sees the prior write.
    """
    from swing.web.ohlcv_cache import OhlcvCache

    cfg = _make_cfg(tmp_path)
    end = pd.Timestamp("2026-04-30")
    fixture_df = _fixture_daily_bars(end=end, n_rows=300)

    calls = {"n": 0}

    def _stub(ticker, *, end_date, cache_dir, archive_history_days):
        calls["n"] += 1
        return fixture_df.loc[fixture_df.index.date <= end_date].copy()

    def _stub_session(now_dt):
        return end.date()

    monkeypatch.setattr(
        "swing.web.ohlcv_cache.read_or_fetch_archive", _stub, raising=False,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", _stub_session, raising=False,
    )

    cache = OhlcvCache(cfg=cfg)
    df1 = cache.get_or_fetch(ticker="AAPL", window_days=180)
    df2 = cache.get_or_fetch(ticker="AAPL", window_days=180)

    assert calls["n"] == 1, "second call must hit cache (no re-fetch)"
    pd.testing.assert_frame_equal(df1, df2)
