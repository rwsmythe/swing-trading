"""Phase 13 T1.SB0 gate-fix — T-GF2.1 daily-kwargs forwarding through ladder.

Recon doc: docs/phase13-t1-sb0-gate-fix-recon.md §4.A fix shape D.

Root cause established at T-GF1 (commit d440578): `_bars_hook` at
swing/pipeline/runner.py:383-410 calls fetch_window_via_ladder with start=None,
end=None AND NO period_type/period/frequency_type/frequency kwargs. The wrapper
forwards all-None to schwabdev, which defaults to periodType=day, period=10,
frequencyType=minute, frequency=1 — returning ~3000 intraday minute candles
instead of daily bars. The chart-step renders the resulting DataFrame as a
dense compressed cluster with intraday 00:00 x-axis labels and per-minute
volume scale (operator-witnessed S3 regression 2026-05-18 PM on CVGI).

The fix extends `fetch_window_via_ladder` to accept period_type/period/
frequency_type/frequency kwargs (defaulting to None for backward compat) and
forward them verbatim to `get_price_history`, which already forwards to
schwabdev via the camelCase kwarg discipline at
swing/integrations/schwab/marketdata.py:377-387.

These tests assert the FORWARDING is intact end-to-end from
`fetch_window_via_ladder` → `get_price_history` → schwabdev's
`client.price_history(periodType=..., period=..., frequencyType=..., frequency=...)`
call. Pre-fix: `fetch_window_via_ladder` lacks the kwargs (TypeError on call).
Post-fix: kwargs flow through verbatim.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab import client as schwab_client_module
from swing.integrations.schwab.marketdata_ladder import fetch_window_via_ladder


@pytest.fixture
def v18_conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "ladder-daily-kwargs-test.db")


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


def _make_cfg():
    schwab_ns = SimpleNamespace(
        environment="production",
        marketdata_ladder_enabled=True,
    )
    integrations_ns = SimpleNamespace(schwab=schwab_ns)
    return SimpleNamespace(integrations=integrations_ns)


def _mock_daily_response(symbol: str = "AAPL"):
    """One-day daily-bar response shaped like Schwab's price_history."""
    resp = MagicMock()
    resp.json.return_value = {
        "candles": [
            {
                "datetime": 1715731200000,  # 2026-05-15 (UTC midnight ms)
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 1_234_567,
            },
        ],
        "empty": False,
        "symbol": symbol,
    }
    resp.status_code = 200
    resp.headers = {}
    return resp


def test_fetch_window_via_ladder_forwards_daily_period_kwargs_to_client(
    v18_conn,
):
    """T-GF2.1 (RED pre-fix, GREEN post-fix): explicit daily kwargs
    `period_type='year', period=5, frequency_type='daily', frequency=1`
    passed to `fetch_window_via_ladder` must propagate verbatim through
    `get_price_history` into the schwabdev camelCase call.

    Discriminator pre-fix: `fetch_window_via_ladder` signature does not
    accept the four period/frequency kwargs → TypeError at call time.

    Discriminator post-fix: the four kwargs reach schwabdev's
    `client.price_history(..., periodType='year', period=5,
    frequencyType='daily', frequency=1)` invocation.

    Closes the Schwab `price_history` minute-default footgun documented at
    docs/phase13-t1-sb0-gate-fix-recon.md §2.B (recon root cause) and the
    failure mode operator-witnessed at the S3 visual gate 2026-05-18 PM
    (CVGI Shape A parquet contaminated with ~278 minute-bars per date).
    """
    cfg = _make_cfg()
    schwab = MagicMock()
    schwab.price_history.return_value = _mock_daily_response("AAPL")
    yf_fallback = MagicMock()  # MUST NOT be invoked on Schwab success.

    window, tag = fetch_window_via_ladder(
        "AAPL",
        start=None,
        end=None,
        cfg=cfg,
        schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn,
        surface="pipeline",
        period_type="year",
        period=5,
        frequency_type="daily",
        frequency=1,
    )

    assert tag == "schwab_api"
    yf_fallback.assert_not_called()
    # The fix's key invariant: schwabdev call MUST receive camelCase daily
    # kwargs explicitly (NOT all-None which triggers Schwab's intraday
    # minute-default footgun).
    schwab.price_history.assert_called_once()
    _, call_kwargs = schwab.price_history.call_args
    assert call_kwargs.get("periodType") == "year", (
        f"periodType must be forwarded as 'year' so Schwab does NOT default "
        f"to periodType='day' (which forces frequencyType='minute'). "
        f"Actual call_kwargs: {call_kwargs!r}"
    )
    assert call_kwargs.get("period") == 5, (
        f"period must be forwarded as 5 (5 years of daily bars matching "
        f"cfg.archive.archive_history_days ~ 1260 trading days). "
        f"Actual call_kwargs: {call_kwargs!r}"
    )
    assert call_kwargs.get("frequencyType") == "daily", (
        f"frequencyType must be forwarded as 'daily' to override Schwab's "
        f"intraday minute default. Actual call_kwargs: {call_kwargs!r}"
    )
    assert call_kwargs.get("frequency") == 1, (
        f"frequency must be forwarded as 1 (only allowed value for "
        f"frequencyType='daily' per reference/schwabdev/api-calls.md:431). "
        f"Actual call_kwargs: {call_kwargs!r}"
    )


def test_fetch_window_via_ladder_no_period_kwargs_preserves_legacy_none_forwarding(
    v18_conn,
):
    """Backward-compat: when period/frequency kwargs omitted (the existing
    contract before this fix), `fetch_window_via_ladder` continues to
    forward all-None to schwabdev. This keeps existing callsites that don't
    yet specify daily-bar kwargs (e.g., test fixtures) unbroken.

    The fix is ADDITIVE — new kwargs default to None; legacy callers see no
    behavior change. Only the `_bars_hook` callsite at
    swing/pipeline/runner.py:_install_pipeline_marketdata_caches is updated
    to pass explicit daily kwargs (T-GF2.2).
    """
    cfg = _make_cfg()
    schwab = MagicMock()
    schwab.price_history.return_value = _mock_daily_response("AAPL")
    yf_fallback = MagicMock()

    window, tag = fetch_window_via_ladder(
        "AAPL",
        start=None,
        end=None,
        cfg=cfg,
        schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn,
        surface="pipeline",
        # NO period/frequency kwargs supplied (legacy contract).
    )

    assert tag == "schwab_api"
    schwab.price_history.assert_called_once()
    _, call_kwargs = schwab.price_history.call_args
    # Legacy contract: all-None forwarded; Schwab applies its own defaults
    # (which is the FOOTGUN at the heart of this gate-fix when the caller
    # actually wanted daily bars; T-GF2.2 closes the footgun at the
    # `_bars_hook` callsite by passing the daily kwargs explicitly).
    assert call_kwargs.get("periodType") is None
    assert call_kwargs.get("period") is None
    assert call_kwargs.get("frequencyType") is None
    assert call_kwargs.get("frequency") is None
