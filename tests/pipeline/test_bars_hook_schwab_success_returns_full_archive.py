"""Phase 16 / Arc 3 — the XMAX watchlist-thumbnail divergence root-cause fix.

Sibling of ``test_yf_window_fallback_returns_full_archive.py`` (the Phase 13
T1.SB0 Codex R3 Major #1 fix), but for the **Schwab-SUCCESS** path of the
pipeline ladder's ``_bars_hook``.

Root cause (hypothesis (a), confirmed): when ``_install_pipeline_marketdata_caches``
installs the Schwab market-data ladder on the pipeline's OhlcvCache, the
``_bars_hook`` returned the freshly-fetched Schwab window VERBATIM on the
schwab_api success path (``bars = window.to_dataframe()``). For a ticker whose
Schwab listing history is short (XMAX = 16 daily Schwab bars vs a 1260-row
legacy archive; TDAY = 138 vs 1260), ``to_dataframe()`` yields only that short
window. ``OhlcvCache._fetch_bars_window`` then slices ``[cutoff, end]`` but
cannot recover history absent from the returned frame, so the pipeline-rendered
watchlist THUMBNAIL drew ~16 sparse points while the web ``ticker_detail`` path
(no ladder → ``read_or_fetch_archive`` → 1260-row legacy archive → ~207 bars)
stayed rich. This VIOLATES the standing "cache hooks must return the FULL
archive; consumers slice" contract.

The yfinance-fallback path was ALREADY fixed (R3 Major #1) to return the full
archive via ``read_or_fetch_archive``; the Schwab-success path was not. This
file pins the symmetric fix and the discriminating convergence regression: the
ladder (thumbnail) path and the no-ladder (ticker_detail) path must yield the
SAME bar count for a ticker with a partial Schwab Shape-A file + a full legacy
archive.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

from swing.data.db import ensure_schema
from swing.integrations.schwab.models import (
    OhlcvBar,
    SchwabPriceHistoryWindow,
)


def _make_pipeline_cfg(db_path: Path, tmp_path: Path):
    """SimpleNamespace cfg shape consumed by ``_install_pipeline_marketdata_caches``
    + ``_bars_hook`` + ``OhlcvCache`` (mirrors
    tests/pipeline/test_bars_hook_requests_daily_frequency.py:_make_pipeline_cfg)."""
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


def _full_legacy_archive(end: pd.Timestamp, n_rows: int = 1200) -> pd.DataFrame:
    """The real legacy ``{TICKER}.parquet`` in-memory shape: DatetimeIndex +
    capitalized OHLCV columns, ~5y of business days."""
    idx = pd.bdate_range(end=end, periods=n_rows)
    closes = [100.0 + i * 0.05 for i in range(n_rows)]
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


def _short_schwab_window(ticker: str, end: pd.Timestamp, n_days: int = 16):
    """A SHORT Schwab window — the real XMAX shape (16 daily Schwab bars).
    Derived from the real ``XMAX.schwab_api.parquet`` schema (asof_date +
    lowercase OHLCV, here as OhlcvBar rows)."""
    days = pd.bdate_range(end=end, periods=n_days)
    bars = [
        OhlcvBar(
            asof_date=d.date().isoformat(),
            open=50.0 + i,
            high=51.0 + i,
            low=49.0 + i,
            close=50.5 + i,
            volume=10_000 + i,
        )
        for i, d in enumerate(days)
    ]
    return SchwabPriceHistoryWindow(ticker=ticker, bars=bars, provider="schwab_api")


def test_bars_hook_schwab_success_returns_full_archive_not_short_window(
    tmp_path: Path, monkeypatch,
):
    """Hypothesis (a) fix + discriminating convergence regression.

    The ladder stub returns a 16-bar Schwab window (the real XMAX shape) on the
    schwab_api SUCCESS path; a 1200-row legacy archive is the on-disk truth
    (here injected via a stubbed ``read_or_fetch_archive``). The pipeline ladder
    (thumbnail) path and the bare no-ladder (ticker_detail) path must converge on
    the SAME bar count over a 300-day window.

    Pre-fix: ``_bars_hook`` returns ``window.to_dataframe()`` (16 rows) → the
    ladder path's ``get_or_fetch`` returns ~16 bars while the no-ladder path
    returns ~207 → divergence; ``len(ladder_df) > 60`` FAILS.

    Post-fix: ``_bars_hook`` re-reads the FULL archive after the ladder
    fetch+persist → both paths return identical counts; ``len(ladder_df) > 60``
    passes and the two counts are equal.
    """
    from swing.pipeline.runner import _install_pipeline_marketdata_caches
    from swing.web.ohlcv_cache import OhlcvCache

    db_path = tmp_path / "arc3.db"
    ensure_schema(db_path).close()
    cfg = _make_pipeline_cfg(db_path, tmp_path)

    end = pd.Timestamp("2026-06-08")
    legacy = _full_legacy_archive(end=end, n_rows=1200)

    def _stub_read_or_fetch_archive(ticker, *, end_date, cache_dir, archive_history_days):
        return legacy.loc[legacy.index.date <= end_date].copy()

    def _stub_session(_now_dt):
        return end.date()

    # The full archive read used by BOTH the post-fix ladder hook (runner
    # binding) and the no-ladder path (ohlcv_cache binding). Stubbed identically
    # so any count divergence is attributable to the hook, not the data source.
    monkeypatch.setattr(
        "swing.pipeline.runner.read_or_fetch_archive", _stub_read_or_fetch_archive,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.read_or_fetch_archive", _stub_read_or_fetch_archive,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.last_completed_session", _stub_session,
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", _stub_session,
    )

    # Ladder stub: a SCHWAB SUCCESS returning only the short 16-bar window.
    def _stub_ladder_schwab_success(ticker, **_kwargs):
        return (_short_schwab_window(ticker, end=end, n_days=16), "schwab_api")

    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_window_via_ladder",
        _stub_ladder_schwab_success,
    )

    # Ladder (thumbnail) path.
    _price, ladder_cache, audit_conn = _install_pipeline_marketdata_caches(
        cfg, MagicMock(), pipeline_run_id=1,
    )
    assert ladder_cache is not None
    assert ladder_cache._ladder_bars_fetcher is not None
    ladder_df = ladder_cache.get_or_fetch(ticker="XMAX", window_days=300)

    # No-ladder (ticker_detail) path — same cfg, NO ladder installed.
    plain_cache = OhlcvCache(cfg)
    plain_df = plain_cache.get_or_fetch(ticker="XMAX", window_days=300)

    # Post-fix: the ladder/thumbnail path is NOT capped at the 16-bar Schwab
    # window — it reflects the full archive sliced to 300 calendar days.
    assert len(ladder_df) > 60, (
        f"ladder bars hook returned too few rows ({len(ladder_df)}); the "
        f"schwab_api success path truncated to the short Schwab window instead "
        f"of returning the full archive (full-archive-return contract)."
    )
    # Discriminating convergence regression: the thumbnail (ladder) and
    # ticker_detail (no-ladder) inputs MUST be the same bar count for a ticker
    # with a partial Schwab Shape-A file + a full legacy archive.
    assert len(ladder_df) == len(plain_df), (
        f"thumbnail (ladder) path {len(ladder_df)} bars != ticker_detail "
        f"(no-ladder) path {len(plain_df)} bars — surfaces diverge for the same "
        f"data_asof_date."
    )
    if audit_conn is not None:
        audit_conn.close()


def test_bars_hook_schwab_only_no_legacy_archive_falls_back_to_window(
    tmp_path: Path, monkeypatch,
):
    """Regression guard (Codex R1 MAJOR #1): for a Schwab-only ticker with NO
    legacy archive and an empty yfinance read, the full-archive read yields
    nothing — the hook MUST fall back to the Schwab window rather than return
    None (which would fail get_or_fetch and render no thumbnail at all). The
    fix must not regress a previously-rendering ticker to no render.
    """
    from swing.pipeline.runner import _install_pipeline_marketdata_caches

    db_path = tmp_path / "arc3-only.db"
    ensure_schema(db_path).close()
    cfg = _make_pipeline_cfg(db_path, tmp_path)
    end = pd.Timestamp("2026-06-08")

    # The full-archive read returns NOTHING (no legacy archive, yfinance empty).
    def _empty_archive(ticker, *, end_date, cache_dir, archive_history_days):
        return None

    monkeypatch.setattr(
        "swing.pipeline.runner.read_or_fetch_archive", _empty_archive,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.last_completed_session", lambda _n: end.date(),
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", lambda _n: end.date(),
    )
    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_window_via_ladder",
        lambda ticker, **_k: (_short_schwab_window(ticker, end=end, n_days=16),
                              "schwab_api"),
    )

    _price, ladder_cache, audit_conn = _install_pipeline_marketdata_caches(
        cfg, MagicMock(), pipeline_run_id=1,
    )
    # The hook falls back to the Schwab window and keeps the 'schwab_api'
    # provenance (those bars ARE Schwab's).
    hook_bars, hook_provider = ladder_cache._ladder_bars_fetcher("NEWLY")
    assert hook_provider == "schwab_api"
    assert len(hook_bars) == 16
    # And get_or_fetch must NOT raise / return empty — no regression to None.
    df = ladder_cache.get_or_fetch(ticker="NEWLY", window_days=300)
    assert not df.empty
    assert len(df) == 16
    if audit_conn is not None:
        audit_conn.close()
