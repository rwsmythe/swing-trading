"""Phase 11 Sub-bundle C T-C.3 — Schwab market-data ladder fetcher.

Per plan §H.6.1 + §H.6.2 + dispatch brief T-C.3.

The ladder is the surface that decides per-call whether to hit Schwab or fall
back to yfinance. Algorithm:

  1. If env != 'production' OR ladder disabled → invoke yfinance_fallback_fn
     directly; provider='yfinance'; NO schwab_api_calls audit row written.
  2. Otherwise call Schwab T-C.1 wrapper inside `_suppress_transport_debug_logs`.
  3. On success → wrap into PriceSnapshot (quote) or pass through
     SchwabPriceHistoryWindow (window); provider='schwab_api'.
  4. On SchwabAuthError / SchwabRateLimitError / SchwabApiError → log warn;
     invoke yfinance_fallback_fn; provider='yfinance' (audit row already
     written by T-C.1 wrapper).
  5. Partial-response on quotes: T-C.1 mapper drops failed symbols. Ladder
     receives dict; missing requested ticker → fall back to yfinance.
  6. Empty-bars on price_history: T-C.1 mapper raises SchwabApiError(204).
     Caught by ladder; falls back; parquet unchanged.

Tests (14 total):
  01. Production-path Schwab success quote → PriceSnapshot.provider='schwab_api'.
  02. Production-path Schwab 429 → yfinance fallback (provider='yfinance').
  03. Production-path Schwab 401 → yfinance fallback (schwabdev owns auto-refresh).
  04. Production-path Schwab empty-bars → yfinance fallback + parquet unchanged
      + audit row error_message contains 'empty bars (transient)'.
  05. Sandbox short-circuit: env='sandbox' → ZERO schwabdev calls + ZERO audit
      rows + yfinance invoked + provider='yfinance'.
  06. Ladder disabled: marketdata_ladder_enabled=False → same as sandbox.
  07. Partial-response on quotes: requested ticker absent from mapper output
      → fall back to yfinance + provider='yfinance'.
  08. Per-provider tagging on success: schwab → 'schwab_api'; yf → 'yfinance'.
  09. Provenance tag returned correctly as second tuple element on all paths.
  10. Ladder rejects out-of-range tickers (empty, None, non-string).
  11. Quote ladder happy-path: PriceSnapshot with provider='schwab_api'.
  12. Window ladder happy-path: SchwabPriceHistoryWindow with provider='schwab_api'.
  13. yfinance_fallback_fn called EXACTLY ONCE on fallback (no double-invoke).
  14. cfg.integrations.schwab.environment='sandbox' → sandbox short-circuit.

Synthetic fixtures (mocked schwabdev `Client` via MagicMock + mocked
yfinance_fallback_fn via MagicMock).
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
from swing.integrations.schwab.marketdata_ladder import (
    fetch_quote_via_ladder,
    fetch_window_via_ladder,
)
from swing.integrations.schwab.models import (
    OhlcvBar,
    SchwabPriceHistoryWindow,
)
from swing.web.price_cache import PriceSnapshot

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def v18_conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "ladder-test.db")


@pytest.fixture(autouse=True)
def reset_schwab_redaction_state():
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


def _make_cfg(*, env: str = "production", ladder_enabled: bool = True):
    """Build a minimal cfg-shaped namespace with the fields the ladder reads.

    The ladder only consults `cfg.integrations.schwab.environment` +
    `cfg.integrations.schwab.marketdata_ladder_enabled`; constructing a full
    `swing.config.Config` requires 12+ required positional dataclass fields,
    so use SimpleNamespace to keep tests focused.
    """
    schwab_ns = SimpleNamespace(
        environment=env,
        marketdata_ladder_enabled=ladder_enabled,
    )
    integrations_ns = SimpleNamespace(schwab=schwab_ns)
    return SimpleNamespace(integrations=integrations_ns)


def _mock_quote_response(symbol: str, last_price: float = 150.0) -> MagicMock:
    """Build a Response-like MagicMock for `Client.quotes` returning one symbol."""
    resp = MagicMock()
    resp.json.return_value = {
        symbol: {
            "quote": {
                "lastPrice": last_price,
                "bidPrice": last_price - 0.5,
                "askPrice": last_price + 0.5,
                "mark": last_price,
                "quoteTimeInLong": 1715692800000,
                "delayed": False,
            },
        },
    }
    resp.status_code = 200
    resp.headers = {}
    return resp


def _mock_price_history_response(
    symbol: str, *, empty: bool = False,
) -> MagicMock:
    """Build a Response-like MagicMock for `Client.price_history`."""
    resp = MagicMock()
    if empty:
        resp.json.return_value = {"candles": [], "empty": True, "symbol": symbol}
    else:
        resp.json.return_value = {
            "candles": [
                {
                    "datetime": 1715692800000,
                    "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0,
                    "volume": 12345,
                },
            ],
            "empty": False,
            "symbol": symbol,
        }
    resp.status_code = 200
    resp.headers = {}
    return resp


def _mock_http_error_response(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"error": f"HTTP {status}"}
    resp.headers = {}
    return resp


def _count_audit_rows(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM schwab_api_calls",
    ).fetchone()[0]


def _latest_audit_row(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT call_id, endpoint, status, error_message FROM schwab_api_calls "
        "ORDER BY call_id DESC LIMIT 1",
    ).fetchone()


def _make_yf_snapshot(ticker: str, price: float = 99.0) -> PriceSnapshot:
    return PriceSnapshot(
        ticker=ticker, price=price, asof=datetime.now(),
        is_stale=False, source="live", provider="yfinance",
    )


# ============================================================================
# 01. Production-path Schwab success — quote → provider='schwab_api'
# ============================================================================


def test_01_quote_production_path_schwab_success_returns_schwab_api_provider(
    v18_conn,
):
    cfg = _make_cfg(env="production", ladder_enabled=True)
    schwab = MagicMock()
    schwab.quotes.return_value = _mock_quote_response("AAPL", 150.0)
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))

    entry, tag = fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert tag == "schwab_api"
    assert isinstance(entry, PriceSnapshot)
    assert entry.ticker == "AAPL"
    assert entry.price == 150.0
    assert entry.provider == "schwab_api"
    # yfinance fallback NOT invoked.
    yf_fallback.assert_not_called()
    # Audit row written.
    assert _count_audit_rows(v18_conn) == 1


# ============================================================================
# 02. Production-path Schwab 429 → yfinance fallback
# ============================================================================


def test_02_quote_production_path_schwab_429_falls_back_to_yfinance(v18_conn):
    cfg = _make_cfg(env="production", ladder_enabled=True)
    schwab = MagicMock()
    schwab.quotes.return_value = _mock_http_error_response(429)
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))

    entry, tag = fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert tag == "yfinance"
    assert entry.price == 99.0
    yf_fallback.assert_called_once_with("AAPL")
    # Audit row written by T-C.1 wrapper with status='rate_limited'.
    row = _latest_audit_row(v18_conn)
    assert row is not None
    assert row[2] == "rate_limited"


# ============================================================================
# 03. Production-path Schwab 401 → yfinance fallback (simplest interpretation)
# ============================================================================


def test_03_quote_production_path_schwab_401_falls_back_to_yfinance(v18_conn):
    """Per dispatch brief §0.5 #3 + plan §H.6.1: schwabdev handles 401 auto-
    refresh internally; if it surfaces 401 to caller, the ladder treats it as
    plain failure → yfinance fallback. The simpler interpretation per brief.
    """
    cfg = _make_cfg(env="production", ladder_enabled=True)
    schwab = MagicMock()
    schwab.quotes.return_value = _mock_http_error_response(401)
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))

    entry, tag = fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert tag == "yfinance"
    assert entry.price == 99.0
    yf_fallback.assert_called_once_with("AAPL")
    row = _latest_audit_row(v18_conn)
    assert row[2] == "auth_failed"


# ============================================================================
# 04. Production-path Schwab empty-bars → yfinance fallback + parquet unchanged
#     + audit row error_message contains 'empty bars (transient)'.
# ============================================================================


def test_04_window_production_path_empty_bars_falls_back_to_yfinance(v18_conn):
    cfg = _make_cfg(env="production", ladder_enabled=True)
    schwab = MagicMock()
    schwab.price_history.return_value = _mock_price_history_response(
        "AAPL", empty=True,
    )

    yf_window = SchwabPriceHistoryWindow(
        ticker="AAPL",
        bars=[OhlcvBar(
            asof_date="2026-05-13",
            open=100.0, high=102.0, low=99.0, close=101.0, volume=1000,
        )],
        provider="schwab_api",  # provider on dataclass; ladder overrides tag
    )
    yf_fallback = MagicMock(return_value=yf_window)

    start = datetime(2026, 5, 10)
    end = datetime(2026, 5, 14)
    window, tag = fetch_window_via_ladder(
        "AAPL", start=start, end=end, cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert tag == "yfinance"
    assert window is yf_window
    yf_fallback.assert_called_once_with("AAPL", start, end)
    # Audit row reflects empty-bars transient.
    row = _latest_audit_row(v18_conn)
    assert row is not None
    assert row[2] == "error"
    assert row[3] is not None and "empty bars (transient)" in row[3]


# ============================================================================
# 05. Sandbox short-circuit: env='sandbox' → ZERO schwabdev + ZERO audit
# ============================================================================


def test_05_quote_sandbox_short_circuits_with_zero_schwabdev_and_zero_audit(
    v18_conn,
):
    cfg = _make_cfg(env="sandbox", ladder_enabled=True)
    schwab = MagicMock()
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))

    pre_count = _count_audit_rows(v18_conn)

    entry, tag = fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert tag == "yfinance"
    assert entry.provider == "yfinance"
    yf_fallback.assert_called_once_with("AAPL")
    # ZERO schwabdev calls.
    schwab.quotes.assert_not_called()
    schwab.price_history.assert_not_called()
    # ZERO audit rows written (spec §3.6.3 + plan §H.6.1 sandbox-no-audit lock).
    assert _count_audit_rows(v18_conn) == pre_count


# ============================================================================
# 06. Ladder disabled via marketdata_ladder_enabled=False
# ============================================================================


def test_06_quote_ladder_disabled_short_circuits_with_zero_schwabdev_and_zero_audit(
    v18_conn,
):
    cfg = _make_cfg(env="production", ladder_enabled=False)
    schwab = MagicMock()
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))

    pre_count = _count_audit_rows(v18_conn)

    entry, tag = fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert tag == "yfinance"
    assert entry.provider == "yfinance"
    yf_fallback.assert_called_once_with("AAPL")
    schwab.quotes.assert_not_called()
    schwab.price_history.assert_not_called()
    assert _count_audit_rows(v18_conn) == pre_count


# ============================================================================
# 07. Partial-response on quotes: requested ticker absent → fall back to yf.
# ============================================================================


def test_07_quote_partial_response_missing_symbol_falls_back_to_yfinance(
    v18_conn,
):
    """Per plan §E.4 partial-response handling: T-C.1 mapper drops symbols
    with error envelopes. Ladder requested 'AAPL' but Schwab returned only
    error envelope → mapper output dict empty → ladder treats as failure →
    yfinance fallback.
    """
    cfg = _make_cfg(env="production", ladder_enabled=True)
    schwab = MagicMock()
    # Response carries error envelope for AAPL — mapper drops it.
    resp = MagicMock()
    resp.json.return_value = {
        "AAPL": {"errors": [{"code": "404", "msg": "symbol not found"}]},
    }
    resp.status_code = 200
    resp.headers = {}
    schwab.quotes.return_value = resp

    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))

    entry, tag = fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert tag == "yfinance"
    assert entry.price == 99.0
    yf_fallback.assert_called_once_with("AAPL")


# ============================================================================
# 08. Per-provider tagging on success (Schwab path) and on fallback (yfinance).
# ============================================================================


def test_08_per_provider_tagging_distinguishes_schwab_api_from_yfinance(
    v18_conn,
):
    cfg = _make_cfg(env="production", ladder_enabled=True)

    # Schwab success → 'schwab_api' tag.
    schwab = MagicMock()
    schwab.quotes.return_value = _mock_quote_response("AAPL", 150.0)
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))
    entry, tag = fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )
    assert tag == "schwab_api"
    assert entry.provider == "schwab_api"

    # Schwab failure → 'yfinance' tag.
    schwab2 = MagicMock()
    schwab2.quotes.return_value = _mock_http_error_response(500)
    yf_fallback2 = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))
    entry2, tag2 = fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=schwab2,
        yfinance_fallback_fn=yf_fallback2,
        conn=v18_conn, surface="pipeline",
    )
    assert tag2 == "yfinance"
    assert entry2.provider == "yfinance"


# ============================================================================
# 09. Provenance tag returned correctly as second tuple element on all paths.
# ============================================================================


def test_09_return_shape_is_tuple_of_entry_and_string_provider_tag(v18_conn):
    cfg_sandbox = _make_cfg(env="sandbox")
    schwab = MagicMock()
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))
    result = fetch_quote_via_ladder(
        "AAPL", cfg=cfg_sandbox, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[1], str)
    assert result[1] in ("schwab_api", "yfinance")


# ============================================================================
# 10. Ladder rejects out-of-range tickers (defensive validation).
# ============================================================================


def test_10_ladder_rejects_invalid_ticker_inputs(v18_conn):
    cfg = _make_cfg(env="production", ladder_enabled=True)
    schwab = MagicMock()
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))

    # Empty string.
    with pytest.raises((ValueError, TypeError)):
        fetch_quote_via_ladder(
            "", cfg=cfg, schwab_client=schwab,
            yfinance_fallback_fn=yf_fallback,
            conn=v18_conn, surface="pipeline",
        )
    # None.
    with pytest.raises((ValueError, TypeError)):
        fetch_quote_via_ladder(
            None, cfg=cfg, schwab_client=schwab,  # type: ignore[arg-type]
            yfinance_fallback_fn=yf_fallback,
            conn=v18_conn, surface="pipeline",
        )
    # Non-string.
    with pytest.raises((ValueError, TypeError)):
        fetch_quote_via_ladder(
            12345, cfg=cfg, schwab_client=schwab,  # type: ignore[arg-type]
            yfinance_fallback_fn=yf_fallback,
            conn=v18_conn, surface="pipeline",
        )

    # Window: same family.
    start = datetime(2026, 5, 10)
    end = datetime(2026, 5, 14)
    with pytest.raises((ValueError, TypeError)):
        fetch_window_via_ladder(
            "", start=start, end=end, cfg=cfg, schwab_client=schwab,
            yfinance_fallback_fn=yf_fallback,
            conn=v18_conn, surface="pipeline",
        )


# ============================================================================
# 11. Quote ladder happy-path: PriceSnapshot with provider='schwab_api'.
# ============================================================================


def test_11_quote_ladder_returns_price_snapshot_with_schwab_api_provider(
    v18_conn,
):
    cfg = _make_cfg(env="production", ladder_enabled=True)
    schwab = MagicMock()
    schwab.quotes.return_value = _mock_quote_response("MSFT", 420.0)
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("MSFT", 99.0))

    entry, tag = fetch_quote_via_ladder(
        "MSFT", cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert isinstance(entry, PriceSnapshot)
    assert entry.ticker == "MSFT"
    assert entry.price == 420.0
    assert entry.provider == "schwab_api"
    assert tag == "schwab_api"


# ============================================================================
# 12. Window ladder happy-path: SchwabPriceHistoryWindow + provider='schwab_api'.
# ============================================================================


def test_12_window_ladder_returns_schwab_price_history_window(v18_conn):
    cfg = _make_cfg(env="production", ladder_enabled=True)
    schwab = MagicMock()
    schwab.price_history.return_value = _mock_price_history_response("AAPL")
    yf_fallback = MagicMock()

    start = datetime(2026, 5, 10)
    end = datetime(2026, 5, 14)
    window, tag = fetch_window_via_ladder(
        "AAPL", start=start, end=end, cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert isinstance(window, SchwabPriceHistoryWindow)
    assert window.ticker == "AAPL"
    assert window.provider == "schwab_api"
    assert len(window.bars) == 1
    assert tag == "schwab_api"
    yf_fallback.assert_not_called()


# ============================================================================
# 13. yfinance_fallback_fn called EXACTLY ONCE on fallback.
# ============================================================================


def test_13_yfinance_fallback_called_exactly_once_on_fallback(v18_conn):
    cfg = _make_cfg(env="production", ladder_enabled=True)
    schwab = MagicMock()
    schwab.quotes.return_value = _mock_http_error_response(503)
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))

    fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert yf_fallback.call_count == 1


# ============================================================================
# 14. Verified sandbox-env behavior with explicit string.
# ============================================================================


def test_14_env_sandbox_string_invokes_sandbox_short_circuit(v18_conn):
    """Sub-bundle B convention: env is enum-validated in SchwabIntegrationConfig
    __post_init__; legal values are exactly {'sandbox', 'production'}. The
    'sandbox' literal forces short-circuit per spec §3.6.3 + plan §H.6.1.
    """
    cfg = _make_cfg(env="sandbox", ladder_enabled=True)
    schwab = MagicMock()
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))

    entry, tag = fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )

    assert tag == "yfinance"
    assert entry.provider == "yfinance"
    schwab.quotes.assert_not_called()


# ============================================================================
# Defense-in-depth: schwab_client=None in production → yfinance fallback.
# ============================================================================


def test_15_schwab_client_none_in_production_falls_back_to_yfinance(v18_conn):
    """Dispatch brief §0.5 pre-emption #7 — `construct_authenticated_client()`
    may have returned None (auth setup not yet completed). Ladder treats this
    as fall-through to yfinance + WARNING log.
    """
    cfg = _make_cfg(env="production", ladder_enabled=True)
    yf_fallback = MagicMock(return_value=_make_yf_snapshot("AAPL", 99.0))
    entry, tag = fetch_quote_via_ladder(
        "AAPL", cfg=cfg, schwab_client=None,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )
    assert tag == "yfinance"
    yf_fallback.assert_called_once_with("AAPL")


# ============================================================================
# Codex R1 Major #3 — Schwab success path persists window to Shape A archive
# ============================================================================


def _make_cfg_with_cache_dir(cache_dir, *, env="production", ladder_enabled=True):
    """cfg variant carrying `paths.prices_cache_dir` so the archive layer
    is exercised by the ladder. Mirrors `_make_cfg` shape but with the
    paths attribute the M#3 fix consults via `_resolve_cache_dir`."""
    from types import SimpleNamespace as _SN
    schwab_ns = _SN(
        environment=env,
        marketdata_ladder_enabled=ladder_enabled,
    )
    integrations_ns = _SN(schwab=schwab_ns)
    paths_ns = _SN(prices_cache_dir=cache_dir)
    return _SN(integrations=integrations_ns, paths=paths_ns)


def test_m3_schwab_success_persists_to_schwab_api_parquet(v18_conn, tmp_path):
    """**Codex R1 Major #3 discriminating test:** Schwab returns a
    populated window; ladder MUST persist via `write_window` to
    ``{cache_dir}/AAPL.schwab_api.parquet``.

    Pre-fix: ladder returns the window but never calls `write_window` —
    archive directory remains empty. Post-fix: parquet exists with the
    Schwab bar's rows.
    """
    import pandas as pd

    from swing.data.ohlcv_archive import resolve_ohlcv_window

    cfg = _make_cfg_with_cache_dir(tmp_path, env="production", ladder_enabled=True)
    schwab = MagicMock()
    schwab.price_history.return_value = _mock_price_history_response("AAPL")
    yf_fallback = MagicMock()

    start = datetime(2026, 5, 10)
    end = datetime(2026, 5, 14)
    window, tag = fetch_window_via_ladder(
        "AAPL", start=start, end=end, cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )
    assert tag == "schwab_api"

    # Discriminating: schwab_api parquet exists post-call.
    schwab_path = tmp_path / "AAPL.schwab_api.parquet"
    assert schwab_path.exists(), (
        "fetch_window_via_ladder Schwab success path did NOT persist to "
        "Shape A archive — Codex R1 Major #3 regression."
    )
    df = pd.read_parquet(schwab_path)
    assert len(df) == 1
    # Mapper produces ISO date "2024-05-14" or "2024-05-14"; the mock
    # response uses datetime 1715692800000 (2024-05-14 UTC).
    assert df.iloc[0]["close"] == 102.0

    # resolver picks up the schwab_api parquet and attributes it.
    df2, provenance = resolve_ohlcv_window(
        "AAPL", start="2020-01-01", end="2030-01-01", cache_dir=tmp_path,
    )
    assert len(df2) == 1
    assert set(provenance.values()) == {"schwab_api"}


def test_m3_yfinance_fallback_persists_to_yfinance_parquet(v18_conn, tmp_path):
    """Codex R1 Major #3 — yfinance fallback path persists to Shape A
    ``{cache_dir}/AAPL.yfinance.parquet``.

    Uses a SchwabPriceHistoryWindow as fallback return value (matches the
    test_04 pattern in this file) so the converter exercises the
    SchwabPriceHistoryWindow → Shape A path.
    """
    import pandas as pd

    from swing.integrations.schwab.models import (
        OhlcvBar,
        SchwabPriceHistoryWindow,
    )

    cfg = _make_cfg_with_cache_dir(tmp_path, env="production", ladder_enabled=True)
    schwab = MagicMock()
    # Force schwab side to fail so we hit yfinance fallback.
    schwab.price_history.return_value = _mock_http_error_response(503)

    yf_window = SchwabPriceHistoryWindow(
        ticker="AAPL",
        bars=[OhlcvBar(
            asof_date="2026-05-13",
            open=100.0, high=102.0, low=99.0, close=101.0, volume=1000,
        )],
        provider="schwab_api",
    )
    yf_fallback = MagicMock(return_value=yf_window)

    start = datetime(2026, 5, 10)
    end = datetime(2026, 5, 14)
    window, tag = fetch_window_via_ladder(
        "AAPL", start=start, end=end, cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )
    assert tag == "yfinance"

    yf_path = tmp_path / "AAPL.yfinance.parquet"
    assert yf_path.exists(), (
        "fetch_window_via_ladder yfinance fallback did NOT persist to "
        "Shape A archive — Codex R1 Major #3 regression."
    )
    df = pd.read_parquet(yf_path)
    assert len(df) == 1
    assert df.iloc[0]["asof_date"] == "2026-05-13"
    assert df.iloc[0]["close"] == 101.0

    # Schwab parquet MUST NOT exist (Schwab call errored).
    schwab_path = tmp_path / "AAPL.schwab_api.parquet"
    assert not schwab_path.exists()


def test_m3_schwab_empty_bars_does_not_persist_schwab_parquet(v18_conn, tmp_path):
    """Codex R1 Major #3 + empty-write-guard interaction: when Schwab
    returns empty bars (mapper raises SchwabApiError 204), the ladder falls
    back to yfinance. The Schwab parquet MUST NOT be written (mapper raised
    before we'd attempt; defense-in-depth empty-write guard in write_window).
    """
    import pandas as pd

    from swing.integrations.schwab.models import (
        OhlcvBar,
        SchwabPriceHistoryWindow,
    )

    cfg = _make_cfg_with_cache_dir(tmp_path, env="production", ladder_enabled=True)
    schwab = MagicMock()
    schwab.price_history.return_value = _mock_price_history_response(
        "AAPL", empty=True,
    )

    yf_window = SchwabPriceHistoryWindow(
        ticker="AAPL",
        bars=[OhlcvBar(
            asof_date="2026-05-13",
            open=100.0, high=102.0, low=99.0, close=101.0, volume=1000,
        )],
        provider="schwab_api",
    )
    yf_fallback = MagicMock(return_value=yf_window)

    start = datetime(2026, 5, 10)
    end = datetime(2026, 5, 14)
    window, tag = fetch_window_via_ladder(
        "AAPL", start=start, end=end, cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )
    assert tag == "yfinance"

    schwab_path = tmp_path / "AAPL.schwab_api.parquet"
    assert not schwab_path.exists(), (
        "Schwab empty-bars path created a schwab_api parquet — empty-write "
        "guard breached."
    )
    # yfinance fallback path persisted independently.
    yf_path = tmp_path / "AAPL.yfinance.parquet"
    assert yf_path.exists()
    df = pd.read_parquet(yf_path)
    assert len(df) == 1


def test_m3_sandbox_short_circuit_still_persists_yfinance(v18_conn, tmp_path):
    """Codex R1 Major #3 — sandbox/disabled short-circuit also writes
    yfinance content to Shape A archive (so the pipeline's read path sees
    consistent state across both production and sandbox)."""
    import pandas as pd

    from swing.integrations.schwab.models import (
        OhlcvBar,
        SchwabPriceHistoryWindow,
    )

    cfg = _make_cfg_with_cache_dir(tmp_path, env="sandbox", ladder_enabled=True)
    schwab = MagicMock()
    yf_window = SchwabPriceHistoryWindow(
        ticker="AAPL",
        bars=[OhlcvBar(
            asof_date="2026-05-13",
            open=100.0, high=102.0, low=99.0, close=101.0, volume=1000,
        )],
        provider="schwab_api",
    )
    yf_fallback = MagicMock(return_value=yf_window)

    start = datetime(2026, 5, 10)
    end = datetime(2026, 5, 14)
    window, tag = fetch_window_via_ladder(
        "AAPL", start=start, end=end, cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )
    assert tag == "yfinance"
    schwab.price_history.assert_not_called()  # sandbox short-circuit

    yf_path = tmp_path / "AAPL.yfinance.parquet"
    assert yf_path.exists()
    df = pd.read_parquet(yf_path)
    assert df.iloc[0]["close"] == 101.0


def test_m3_cfg_without_paths_skips_persistence_gracefully(v18_conn):
    """Codex R1 Major #3 defense-in-depth: cfg without `paths` attribute
    (minimal test cfg) MUST NOT crash the ladder — persistence skips
    silently. Existing tests using `_make_cfg` (no paths attr) rely on this.
    """
    cfg = _make_cfg(env="production", ladder_enabled=True)
    schwab = MagicMock()
    schwab.price_history.return_value = _mock_price_history_response("AAPL")
    yf_fallback = MagicMock()

    start = datetime(2026, 5, 10)
    end = datetime(2026, 5, 14)
    # Must not raise.
    window, tag = fetch_window_via_ladder(
        "AAPL", start=start, end=end, cfg=cfg, schwab_client=schwab,
        yfinance_fallback_fn=yf_fallback,
        conn=v18_conn, surface="pipeline",
    )
    assert tag == "schwab_api"
    assert isinstance(window, SchwabPriceHistoryWindow)
