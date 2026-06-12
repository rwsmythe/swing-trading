"""Phase 13 T1.SB0 gate-fix — T-GF2.2 + T-GF3 production-path regression.

Closes the operator-witnessed S3 visual chart regression observed on
2026-05-18 PM (CVGI Shape A parquet contaminated with ~278 minute-bars per
date). Recon at docs/phase13-t1-sb0-gate-fix-recon.md.

T-GF2.2 (this file): the `_bars_hook` closure installed by
`swing/pipeline/runner.py:_install_pipeline_marketdata_caches` MUST pass
explicit daily-bar period/frequency kwargs to `fetch_window_via_ladder` so
the underlying schwabdev `client.price_history` call returns DAILY bars,
not the server-default 10-day window of 1-minute intraday bars (recon §2.B
+ Schwab API table at reference/schwabdev/api-calls.md:425-435).

T-GF3 (this file): the second test plants a synthetic intraday-shaped
Schwab response + invokes the cache's get_or_fetch through the full
production data-derivation path; asserts that post-fix the cache's
returned DataFrame is a DAILY-shaped frame (no duplicate index entries
within a date) and that the schwabdev call was issued with daily kwargs.

The byte-parity test at
tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py does NOT
exercise the ladder path — it constructs a bare OhlcvCache without
installing a ladder bars fetcher, so the bug was invisible. This file
closes that blind spot.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab import client as schwab_client_module
from swing.integrations.schwab.models import (
    OhlcvBar,
    SchwabPriceHistoryWindow,
)
from swing.pipeline.runner import _install_pipeline_marketdata_caches


@pytest.fixture
def v18_db(tmp_path: Path) -> Path:
    """Create a v18+ schema DB; return its path (the runner re-opens
    its own connection inside _bars_hook, so we just need the path)."""
    conn = ensure_schema(tmp_path / "bars-hook-test.db")
    conn.close()
    return tmp_path / "bars-hook-test.db"


@pytest.fixture(autouse=True)
def reset_schwab_redaction_state():
    """Mirrors test_schwab_marketdata_ladder.py fixture — Schwab logger
    redaction factory leaks across tests if not reset."""
    original_factory = logging.getLogRecordFactory()
    original_installed = schwab_client_module._FACTORY_INSTALLED
    original_orig = schwab_client_module._ORIGINAL_RECORD_FACTORY
    original_secrets = set(schwab_client_module._GLOBAL_KNOWN_SECRETS)
    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._FACTORY_INSTALLED = False
    schwab_client_module._ORIGINAL_RECORD_FACTORY = None
    logging.setLogRecordFactory(logging.LogRecord)
    yield
    logging.setLogRecordFactory(original_factory)
    schwab_client_module._FACTORY_INSTALLED = original_installed
    schwab_client_module._ORIGINAL_RECORD_FACTORY = original_orig
    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._GLOBAL_KNOWN_SECRETS.update(original_secrets)


def _make_pipeline_cfg(db_path: Path, tmp_path: Path):
    """Minimal cfg shape consumed by `_install_pipeline_marketdata_caches` +
    `_bars_hook`. Mirrors the SimpleNamespace pattern used in
    tests/integrations/test_schwab_marketdata_ladder.py:_make_cfg.

    Adds the cfg.paths + cfg.web + cfg.archive fields the OhlcvCache /
    ladder consult during `_install_pipeline_marketdata_caches`.
    """
    paths_ns = SimpleNamespace(
        db_path=Path(db_path),
        prices_cache_dir=tmp_path / "prices-cache",
    )
    paths_ns.prices_cache_dir.mkdir(parents=True, exist_ok=True)
    schwab_ns = SimpleNamespace(
        environment="production",
        marketdata_ladder_enabled=True,
    )
    integrations_ns = SimpleNamespace(schwab=schwab_ns)
    web_ns = SimpleNamespace(
        ohlcv_cache_ttl_seconds=3600,
        max_concurrent_ohlcv_fetches=4,
        circuit_breaker_cooldown_seconds=60,
        db_busy_timeout_ms=30000,
    )
    archive_ns = SimpleNamespace(archive_history_days=1260)
    return SimpleNamespace(
        paths=paths_ns,
        integrations=integrations_ns,
        web=web_ns,
        archive=archive_ns,
    )


def _make_daily_schwab_window(ticker: str, n_days: int = 5):
    """Build a SchwabPriceHistoryWindow with `n_days` distinct daily bars."""
    bars = [
        OhlcvBar(
            asof_date=f"2026-05-{10 + i:02d}",
            open=100.0 + i,
            high=105.0 + i,
            low=99.0 + i,
            close=102.0 + i,
            volume=1_000_000 + i * 10_000,
        )
        for i in range(n_days)
    ]
    return SchwabPriceHistoryWindow(ticker=ticker, bars=bars, provider="schwab_api")


def test_bars_hook_invokes_ladder_with_daily_period_frequency_kwargs(
    v18_db, tmp_path, monkeypatch,
):
    """T-GF2.2 RED pre-fix, GREEN post-fix.

    Discriminator: monkeypatch fetch_window_via_ladder at the ladder
    module + at the runner-local lazy-import target. Invoke the
    OhlcvCache's installed ladder bars fetcher with one ticker. Assert
    that fetch_window_via_ladder received period_type='year', period=5,
    frequency_type='daily', frequency=1.

    Pre-fix: _bars_hook calls fetch_window_via_ladder(ticker, start=None,
    end=None, cfg=..., schwab_client=..., yfinance_fallback_fn=...,
    conn=..., surface=..., pipeline_run_id=...) — no period/frequency
    kwargs → assertion fails (recorded kwargs all None on the four
    period/frequency keys).

    Post-fix: _bars_hook passes period_type='year', period=5,
    frequency_type='daily', frequency=1 → assertion passes.
    """
    cfg = _make_pipeline_cfg(v18_db, tmp_path)
    schwab = MagicMock()  # the schwab_client; never actually invoked
    # because we monkeypatch fetch_window_via_ladder.

    recorded_kwargs: dict = {}

    def _fake_fetch_window_via_ladder(ticker, **kwargs):
        recorded_kwargs.update(kwargs)
        recorded_kwargs["__ticker__"] = ticker
        return (_make_daily_schwab_window(ticker), "schwab_api")

    # The runner imports fetch_window_via_ladder LAZILY inside
    # _install_pipeline_marketdata_caches (closure captures the name). Patch
    # at the source module so the lazy import binds the stub.
    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_window_via_ladder",
        _fake_fetch_window_via_ladder,
    )

    # Phase 16 Arc 3: the schwab-success bars path now re-reads the FULL archive
    # (full-archive-return contract). Stub that read + the session anchor so the
    # hook stays HERMETIC (no network) and returns a controlled non-empty daily
    # frame. The effective provider is then 'yfinance' (bars came from the
    # archive); the Schwab call still ran with daily kwargs (asserted below).
    _archive = pd.DataFrame(
        {"Open": [1.0, 2.0], "High": [1.0, 2.0], "Low": [1.0, 2.0],
         "Close": [1.0, 2.0], "Volume": [10, 20]},
        index=pd.to_datetime(["2026-05-10", "2026-05-11"]),
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.read_or_fetch_archive",
        lambda ticker, *, end_date, cache_dir, archive_history_days: _archive.copy(),
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.last_completed_session",
        lambda _now: pd.Timestamp("2026-05-11").date(),
    )

    price_cache, ohlcv_cache, _audit_conn = _install_pipeline_marketdata_caches(
        cfg=cfg,
        schwab_client=schwab,
        pipeline_run_id=42,
    )
    assert ohlcv_cache is not None, "OhlcvCache must be installed when schwab_client present"
    assert ohlcv_cache._ladder_bars_fetcher is not None, (
        "_install_pipeline_marketdata_caches must install ladder bars fetcher"
    )

    # Invoke the installed _bars_hook closure.
    result = ohlcv_cache._ladder_bars_fetcher("AAPL")
    bars_df, provider_tag = result

    # The schwab path returned the full archive (non-empty); the ladder still
    # ran with daily kwargs (asserted below). Because the returned bars now
    # originate from the archive, the effective provider is 'yfinance' (honest
    # provenance); the Schwab call + audit row still happened.
    assert provider_tag == "yfinance"
    assert isinstance(bars_df, pd.DataFrame)
    assert not bars_df.empty

    # The critical invariant — _bars_hook must request DAILY bars
    # explicitly, NOT inherit Schwab's intraday minute default.
    assert recorded_kwargs.get("period_type") == "year", (
        f"_bars_hook MUST pass period_type='year' to override Schwab's "
        f"periodType='day' default (which forces frequencyType='minute' per "
        f"reference/schwabdev/api-calls.md:430). Actual kwargs: "
        f"{recorded_kwargs!r}"
    )
    assert recorded_kwargs.get("period") == 5, (
        f"_bars_hook MUST pass period=5 (5 years of daily bars matching "
        f"cfg.archive.archive_history_days). Actual kwargs: {recorded_kwargs!r}"
    )
    assert recorded_kwargs.get("frequency_type") == "daily", (
        f"_bars_hook MUST pass frequency_type='daily' to get daily bars "
        f"(not 1-minute intraday). Actual kwargs: {recorded_kwargs!r}"
    )
    assert recorded_kwargs.get("frequency") == 1, (
        f"_bars_hook MUST pass frequency=1 (only valid value for "
        f"frequency_type='daily'). Actual kwargs: {recorded_kwargs!r}"
    )
    if _audit_conn is not None:
        _audit_conn.close()


def test_bars_hook_production_path_returns_daily_shaped_frame_no_duplicate_dates(
    v18_db, tmp_path, monkeypatch,
):
    """T-GF3: end-to-end production-path regression test.

    The byte-parity test at
    tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py does NOT
    exercise the ladder path (constructs bare OhlcvCache without
    set_ladder_bars_fetcher). This test closes that blind spot.

    Plants a SYNTHETIC intraday-shaped Schwab response (multiple bars per
    date — simulating the regression's minute-frequency-default footgun
    output) to PROVE the cache + ladder + hook plumbing rejects /
    surfaces the failure mode. But post-fix, the production code path
    issues daily kwargs so the actual Schwab response would be a daily-
    shape response — so we stub fetch_window_via_ladder to RETURN a
    daily-shaped response unconditionally (mimicking what Schwab would
    return when called with explicit daily kwargs).

    Discriminator: assert OhlcvCache.get_or_fetch returns a DataFrame
    where every index date is unique (no duplicate timestamps). Pre-fix:
    the ladder receives no daily kwargs → Schwab returns intraday minute
    candles → mapper produces ~3000 OhlcvBar rows with ~10 unique
    asof_dates → DataFrame has ~3000 rows with duplicate index
    timestamps. Post-fix: the ladder receives daily kwargs → Schwab
    returns daily bars → mapper produces N OhlcvBar rows with N unique
    asof_dates → DataFrame index has no duplicates.

    Phase 16 Arc 3 update: the schwab-success bars path now re-reads the FULL
    archive (full-archive-return contract) rather than returning the Schwab
    window verbatim, so the intraday-contaminated Schwab window can no longer
    reach ``get_or_fetch``'s render output at all. The daily-kwargs guarantee
    (the actual gate-fix invariant) is asserted by the sibling test
    ``test_bars_hook_invokes_ladder_with_daily_period_frequency_kwargs``; here
    we keep the hermetic ``get_or_fetch`` shape contract (a unique-index daily
    DataFrame) by stubbing ``read_or_fetch_archive`` to a controlled daily
    archive.
    """
    cfg = _make_pipeline_cfg(v18_db, tmp_path)
    schwab = MagicMock()

    # Arc 3: stub the full-archive read (+ session anchor) the schwab-success
    # path now consults, so the test is hermetic and the returned frame is a
    # controlled unique-index daily archive.
    _archive = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [101.0, 102.0, 103.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [100.5, 101.5, 102.5],
            "Volume": [1000, 1100, 1200],
        },
        index=pd.to_datetime(["2026-05-13", "2026-05-14", "2026-05-15"]),
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.read_or_fetch_archive",
        lambda ticker, *, end_date, cache_dir, archive_history_days: _archive.copy(),
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.last_completed_session",
        lambda _now: pd.Timestamp("2026-05-15").date(),
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session",
        lambda _now: pd.Timestamp("2026-05-15").date(),
    )

    def _shape_aware_fetch_window_via_ladder(ticker, **kwargs):
        """Production-shaped stub: return daily window IF caller passes
        the daily kwargs; return intraday-shaped window (one bar per
        minute) if caller falls back to all-None (the pre-fix bug).

        This shape-aware behavior mirrors what Schwab itself does —
        return whatever frequency the caller (implicitly) asked for.
        """
        ft = kwargs.get("frequency_type")
        if ft == "daily":
            return (_make_daily_schwab_window(ticker, n_days=5), "schwab_api")
        # Pre-fix branch: 1-minute intraday bars (10 days x ~390 bars).
        # We simulate with a much smaller intraday-shaped response (3
        # bars per day x 2 days = 6 total bars across 2 unique dates)
        # so the assertion catches the duplicate-date footgun without
        # needing thousands of bars.
        bars = []
        for d in range(2):
            for minute in range(3):
                bars.append(OhlcvBar(
                    asof_date=f"2026-05-{15 + d:02d}",
                    open=100.0 + minute,
                    high=101.0 + minute,
                    low=99.0 + minute,
                    close=100.5 + minute,
                    volume=100 + minute,
                ))
        return (SchwabPriceHistoryWindow(
            ticker=ticker, bars=bars, provider="schwab_api",
        ), "schwab_api")

    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_window_via_ladder",
        _shape_aware_fetch_window_via_ladder,
    )

    price_cache, ohlcv_cache, _audit_conn = _install_pipeline_marketdata_caches(
        cfg=cfg,
        schwab_client=schwab,
        pipeline_run_id=42,
    )
    assert ohlcv_cache is not None

    # Production-path invocation matches _step_charts at
    # swing/pipeline/runner.py:1328.
    bars_df = ohlcv_cache.get_or_fetch(ticker="AAPL", window_days=200)

    # PRIMARY ASSERTION: no duplicate index entries. Intraday minute
    # bars all on the same date would collapse to duplicate DatetimeIndex
    # timestamps via pd.to_datetime(asof_date_string) → midnight Timestamp.
    # A DataFrame with duplicate index timestamps for the same date is the
    # signature of the bug.
    assert bars_df.index.is_unique, (
        f"OhlcvCache.get_or_fetch must return a DataFrame with unique index "
        f"entries (daily bars). Duplicate index entries indicate intraday-"
        f"frequency contamination (the gate-fix's root cause). "
        f"Index: {list(bars_df.index[:10])}; total rows: {len(bars_df)}, "
        f"unique index entries: {bars_df.index.nunique()}"
    )

    # SECONDARY: at least 1 row, sane shape.
    assert not bars_df.empty
    assert list(bars_df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    if _audit_conn is not None:
        _audit_conn.close()
