"""Slice 1 — A-3 web market-data ladder install + L9 gates (production-path)."""
from __future__ import annotations

import dataclasses
import threading
from unittest.mock import MagicMock

from swing.web.app import create_app


def _production_cfg(base_cfg):
    """Return a cfg with production env + ladder enabled (no live network)."""
    schwab = dataclasses.replace(
        base_cfg.integrations.schwab,
        environment="production", marketdata_ladder_enabled=True,
    )
    integ = dataclasses.replace(base_cfg.integrations, schwab=schwab)
    return dataclasses.replace(base_cfg, integrations=integ)


def _seed_open_trade(cfg, ticker: str) -> None:
    """Seed one open ('managing') trade so the L9 scope gate ATTEMPTS Schwab.

    Goes through the production ``insert_trade_with_event`` repo function (the
    web conftest's autouse ``_auto_entry_fill_after_insert_trade`` fixture pairs
    the entry fill so the row is a valid open-state trade). No hand-rolled SQL
    (synthetic-fixture-vs-emitter drift gotcha)."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos import trades as trades_repo

    trade = Trade(
        id=None, ticker=ticker, entry_date="2026-05-04", entry_price=120.50,
        initial_shares=100, initial_stop=115.00, current_stop=118.00,
        state="managing", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trades_repo.insert_trade_with_event(
                conn, trade, event_ts="2026-05-04T09:30:00",
            )
    finally:
        conn.close()


def test_sandbox_app_constructs_no_client_no_hooks(seeded_db):
    cfg, _ = seeded_db  # default env == 'sandbox'
    app = create_app(cfg)
    assert app.state.schwab_client is None
    assert app.state.price_cache._ladder_fetcher is None
    assert app.state.ohlcv_cache._ladder_bars_fetcher is None


def test_production_app_installs_both_hooks(seeded_db, monkeypatch, tmp_path):
    cfg, _ = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Slice 2 seed writes sidecar here
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "id-xxxx")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "secret-xxxx")
    fake_client = MagicMock(name="schwab_client")
    monkeypatch.setattr(
        "swing.web.app.construct_authenticated_client",
        lambda *a, **k: fake_client,
    )
    app = create_app(_production_cfg(cfg))
    assert app.state.schwab_client is fake_client
    assert app.state.price_cache._ladder_fetcher is not None
    assert app.state.ohlcv_cache._ladder_bars_fetcher is not None


def _install_hooks(cfg, monkeypatch, fake_client, tmp_path):
    """Build a production app with the ladder installed, returning the app.

    BOTH USERPROFILE and HOME are monkeypatched to tmp_path so the P14.N7
    seed call (Slice 2) writes the liveness sidecar under tmp_path, never the
    operator's real ~/swing-data."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "id-xxxx")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "secret-xxxx")
    monkeypatch.setattr(
        "swing.web.app.construct_authenticated_client", lambda *a, **k: fake_client,
    )
    app = create_app(_production_cfg(cfg))
    return app


def test_web_bars_hook_schwab_success_returns_full_archive(
    seeded_db, monkeypatch, tmp_path,
):
    """Phase 16 Arc 3 (Codex R2 MAJOR #1): the WEB app's ladder bars hook had
    the same `window.to_dataframe()` truncation as the pipeline hook. For a
    short-listed ticker the ticker_detail JIT path (which uses the web app's
    `ohlcv_cache.get_or_fetch`) would render from the short Schwab window. The
    shared `resolve_full_archive_bars` helper must make the web hook return the
    FULL archive too — converging every surface.
    """
    import pandas as pd

    from swing.integrations.schwab.models import (
        OhlcvBar,
        SchwabPriceHistoryWindow,
    )

    cfg, _ = seeded_db
    _seed_open_trade(cfg, "AAA")  # open trade → scope gate ATTEMPTS Schwab

    end = pd.Timestamp("2026-06-08")
    full_archive = pd.DataFrame(
        {
            "Open": [100.0 + i for i in range(200)],
            "High": [101.0 + i for i in range(200)],
            "Low": [99.0 + i for i in range(200)],
            "Close": [100.5 + i for i in range(200)],
            "Volume": [1000 + i for i in range(200)],
        },
        index=pd.bdate_range(end=end, periods=200),
    )
    short_schwab = SchwabPriceHistoryWindow(
        ticker="AAA",
        bars=[
            OhlcvBar(asof_date=d.date().isoformat(), open=1.0, high=1.0,
                     low=1.0, close=1.0, volume=1)
            for d in pd.bdate_range(end=end, periods=16)
        ],
        provider="schwab_api",
    )

    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_window_via_ladder",
        lambda ticker, **_k: (short_schwab, "schwab_api"),
    )
    # The web hook's _yf_window_fallback imports these locally → patch source.
    monkeypatch.setattr(
        "swing.data.ohlcv_archive.read_or_fetch_archive",
        lambda ticker, *, end_date, cache_dir, archive_history_days: (
            full_archive.loc[full_archive.index.date <= end_date].copy()
        ),
    )
    monkeypatch.setattr(
        "swing.evaluation.dates.last_completed_session", lambda _n: end.date(),
    )
    monkeypatch.setattr(
        "swing.web.ohlcv_cache.last_completed_session", lambda _n: end.date(),
    )

    app = _install_hooks(cfg, monkeypatch, MagicMock(), tmp_path)
    bars_df, provider_tag = app.state.ohlcv_cache._ladder_bars_fetcher("AAA")
    assert provider_tag == "schwab_api"
    # NOT the 16-bar Schwab window — the full archive.
    assert len(bars_df) == 200


def test_bars_hook_passes_explicit_daily_kwargs(seeded_db, monkeypatch, tmp_path):
    cfg, _ = seeded_db
    captured = {}

    def _fake_window(ticker, **kwargs):
        captured.update(kwargs)
        return (object(), "yfinance")

    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_window_via_ladder",
        _fake_window,
    )
    # seed AAA as the only open trade so the scope gate ATTEMPTS Schwab
    _seed_open_trade(cfg, "AAA")
    app = _install_hooks(cfg, monkeypatch, MagicMock(), tmp_path)
    app.state.ohlcv_cache._ladder_bars_fetcher("AAA")
    assert captured["period_type"] == "year"
    assert captured["period"] == 5
    assert captured["frequency_type"] == "daily"
    assert captured["frequency"] == 1
    assert captured["surface"] == "pipeline"
    assert captured["pipeline_run_id"] is None


def test_scope_gate_bypasses_schwab_for_non_open_trade(seeded_db, monkeypatch, tmp_path):
    cfg, _ = seeded_db
    calls = []
    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_quote_via_ladder",
        lambda ticker, **k: calls.append(ticker) or (MagicMock(price=1.0), "schwab_api"),
    )
    _seed_open_trade(cfg, "AAA")
    app = _install_hooks(cfg, monkeypatch, MagicMock(), tmp_path)
    # also stub the yfinance fallback so the bypass path needs no network
    monkeypatch.setattr(app.state.price_cache, "_fetch_live_price", lambda t: 9.0)
    _price, provider = app.state.price_cache._ladder_fetcher("ZZZ")  # not open
    assert provider == "yfinance"
    assert calls == []  # Schwab NEVER attempted for the non-open-trade ticker


def test_cooldown_after_consecutive_yfinance_fallbacks(seeded_db, monkeypatch, tmp_path):
    cfg, _ = seeded_db
    attempts = []
    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_quote_via_ladder",
        lambda ticker, **k: attempts.append(ticker) or (MagicMock(price=1.0), "yfinance"),
    )
    _seed_open_trade(cfg, "AAA")
    app = _install_hooks(cfg, monkeypatch, MagicMock(), tmp_path)
    monkeypatch.setattr(app.state.price_cache, "_fetch_live_price", lambda t: 9.0)
    hook = app.state.price_cache._ladder_fetcher
    for _ in range(3):       # _WEB_LADDER_FALLBACK_COOLDOWN_THRESHOLD
        hook("AAA")
    assert len(attempts) == 3
    hook("AAA")              # now in cooldown -> bypassed, NO new Schwab attempt
    assert len(attempts) == 3


def test_concurrent_misses_do_not_slip_past_cooldown(seeded_db, monkeypatch, tmp_path):
    cfg, _ = seeded_db
    attempts = []
    lock = threading.Lock()

    def _fetch(ticker, **k):
        with lock:
            attempts.append(ticker)
        return (MagicMock(price=1.0), "yfinance")

    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_quote_via_ladder", _fetch,
    )
    _seed_open_trade(cfg, "AAA")
    app = _install_hooks(cfg, monkeypatch, MagicMock(), tmp_path)
    monkeypatch.setattr(app.state.price_cache, "_fetch_live_price", lambda t: 9.0)
    hook = app.state.price_cache._ladder_fetcher
    for _ in range(3):
        hook("AAA")          # trip the cooldown
    threads = [threading.Thread(target=hook, args=("AAA",)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(attempts) == 3  # cooldown held under concurrency; no extra Schwab calls


def test_cfg_tier_credentials_construct_client_without_env(seeded_db, monkeypatch, tmp_path):
    cfg, _ = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Slice 2 seed writes sidecar here
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(
        "swing.web.app.resolve_credentials_env_or_prompt",
        lambda cfg, env, *, allow_prompt=False: ("cfg-id", "cfg-secret"),
    )
    fake = MagicMock()
    monkeypatch.setattr("swing.web.app.construct_authenticated_client", lambda *a, **k: fake)
    app = create_app(_production_cfg(cfg))
    assert app.state.schwab_client is fake  # cfg-tier creds construct the client


def test_open_trade_memo_db_error_degrades_to_yfinance(seeded_db, monkeypatch, tmp_path):
    # A DB error while refreshing the open-trade memo must NOT propagate out of
    # the hook; it degrades to yfinance with NO Schwab call (no row, no raise).
    cfg, _ = seeded_db
    calls = []
    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_quote_via_ladder",
        lambda ticker, **k: calls.append(ticker) or (MagicMock(price=1.0), "schwab_api"),
    )

    def _boom(_conn):
        raise RuntimeError("transient DB lock during pipeline write")

    monkeypatch.setattr("swing.data.repos.trades.list_open_trades", _boom)
    app = _install_hooks(cfg, monkeypatch, MagicMock(), tmp_path)
    monkeypatch.setattr(app.state.price_cache, "_fetch_live_price", lambda t: 9.0)
    _price, provider = app.state.price_cache._ladder_fetcher("AAA")  # must NOT raise
    assert provider == "yfinance"
    assert calls == []  # memo refresh failed -> empty scope -> Schwab not attempted
