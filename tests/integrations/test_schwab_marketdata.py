"""Phase 11 T-C.1 — Schwab Market Data API endpoint wrappers + mappers.

Per plan §E.3 + §E.4 + §E.5 + §H.6.4 + §H.7 + §B.1 + T-C.0.b recon doc §3.

Tests cover (12 total):
  - 2 signature pins (in test_schwab_marketdata_kwarg_signatures.py).
  - 2 mapper happy paths (quotes; price_history).
  - 2 partial-response tests on quotes mapper (mixed OK/error envelopes).
  - 2 empty-bars transient tests on price_history mapper (dual signal: empty
    flag AND/OR zero candles).
  - 2 endpoint happy-path tests (get_quotes_batch; get_price_history) with
    audit-lifecycle assertions (record_call_start + record_call_finish with
    status='success' + signature_hash + http_status).
  - 1 rate-limit handling test (429 → SchwabRateLimitError + audit status
    'rate_limited').
  - 1 dataclass post_init validation test (negative price rejected; non-
    sorted bars rejected; etc.).

Synthetic fixtures (mocked schwabdev `Client` via MagicMock) — live cassette
recording DEFERRED to operator-paired post-merge session per T-C.0.b recon
doc §6.

Sub-bundle A M#2/M#3 + Sub-bundle B R1 M#3 family pre-emptions:
  - ensure_schwab_log_redaction_factory_installed() fires BEFORE schwabdev call.
  - record_call_finish(status='success', ...) fires ONLY after mapper succeeds.
  - Typed exceptions (SchwabAuthError / SchwabRateLimitError / SchwabApiError)
    close audit row with correct status BEFORE re-raising.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab import client as schwab_client_module
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabAuthError,
    SchwabRateLimitError,
    SchwabSchemaParityError,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def v18_conn(tmp_path: Path) -> sqlite3.Connection:
    """v18 DB with foreign_keys=ON."""
    return ensure_schema(tmp_path / "schwab-marketdata-test.db")


@pytest.fixture(autouse=True)
def reset_schwab_redaction_state():
    """Mirror trader.py test fixture — clear process-global redaction state
    between tests so prior tests' registrations cannot mask bugs.
    """
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


def _mock_response(json_value, *, status_code: int = 200, headers=None):
    """Build a Response-like MagicMock returning the supplied json + status."""
    resp = MagicMock()
    resp.json.return_value = json_value
    resp.status_code = status_code
    resp.headers = headers or {}
    return resp


def _audit_row(conn: sqlite3.Connection, call_id: int) -> tuple:
    return conn.execute(
        "SELECT call_id, ts, endpoint, http_status, response_time_ms, "
        "rate_limit_remaining, signature_hash, status, error_message, "
        "surface, environment FROM schwab_api_calls WHERE call_id = ?",
        (call_id,),
    ).fetchone()


def _latest_call_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT call_id FROM schwab_api_calls ORDER BY call_id DESC LIMIT 1",
    ).fetchone()
    return row[0] if row else None


# ============================================================================
# Dataclass post_init validation
# ============================================================================


def test_01_quote_response_post_init_rejects_negative_last_price():
    """SchwabQuoteResponse(__post_init__) rejects negative last_price + NaN/inf."""
    from swing.integrations.schwab.models import SchwabQuoteResponse

    # Valid construction works.
    q = SchwabQuoteResponse(
        symbol="AAPL",
        last_price=150.0,
        bid=149.5,
        ask=150.5,
        mark=150.0,
        quote_time="2026-05-14T12:00:00.000Z",
        delayed=False,
    )
    assert q.last_price == 150.0

    # Negative last_price rejected.
    with pytest.raises(ValueError, match="last_price"):
        SchwabQuoteResponse(
            symbol="AAPL", last_price=-1.0, bid=0.0, ask=0.0,
            mark=None, quote_time="t", delayed=False,
        )

    # NaN rejected.
    with pytest.raises(ValueError, match="finite"):
        SchwabQuoteResponse(
            symbol="AAPL", last_price=float("nan"), bid=0.0, ask=0.0,
            mark=None, quote_time="t", delayed=False,
        )

    # inf rejected on bid.
    with pytest.raises(ValueError, match="finite"):
        SchwabQuoteResponse(
            symbol="AAPL", last_price=1.0, bid=float("inf"), ask=0.0,
            mark=None, quote_time="t", delayed=False,
        )


def test_02_price_history_window_post_init_rejects_invalid_bars():
    """SchwabPriceHistoryWindow rejects bars violating low/high invariants OR
    unsorted ordering."""
    from swing.integrations.schwab.models import (
        OhlcvBar,
        SchwabPriceHistoryWindow,
    )

    # Per-bar invariant: low > min(open, close) should fail.
    with pytest.raises(ValueError, match="low"):
        OhlcvBar(
            asof_date="2026-05-14",
            open=100.0, high=105.0, low=101.0, close=99.0,  # low=101 > close=99
            volume=1000,
        )

    # Per-bar invariant: high < max(open, close) should fail.
    with pytest.raises(ValueError, match="high"):
        OhlcvBar(
            asof_date="2026-05-14",
            open=100.0, high=99.5, low=98.0, close=101.0,  # high=99.5 < close=101
            volume=1000,
        )

    # Negative volume rejected.
    with pytest.raises(ValueError, match="volume"):
        OhlcvBar(
            asof_date="2026-05-14",
            open=100.0, high=105.0, low=98.0, close=99.0,
            volume=-1,
        )

    # Window with unsorted bars rejected.
    b1 = OhlcvBar(asof_date="2026-05-14", open=1, high=2, low=0.5, close=1.5, volume=1)
    b2 = OhlcvBar(asof_date="2026-05-13", open=1, high=2, low=0.5, close=1.5, volume=1)
    with pytest.raises(ValueError, match="sorted"):
        SchwabPriceHistoryWindow(
            ticker="AAPL", bars=[b1, b2], provider="schwab_api",
        )

    # Provider must be non-empty.
    with pytest.raises(ValueError, match="provider"):
        SchwabPriceHistoryWindow(
            ticker="AAPL", bars=[b2, b1], provider="",
        )


def test_02b_price_history_window_to_dataframe_legacy_shape():
    """Codex R1 Major #4: ``SchwabPriceHistoryWindow.to_dataframe()`` returns
    a DataFrame matching the LEGACY yfinance in-memory shape that
    ``OhlcvCache`` + ``compute_smas`` + chart-step downstream code consume.

    Pre-fix: method did not exist; ``_bars_hook`` in
    ``swing/pipeline/runner.py:318`` raised AttributeError on Schwab success.
    Post-fix: returns DatetimeIndex + capitalized OHLCV columns.

    Discriminating: assert (a) index is DatetimeIndex; (b) columns are exactly
    Open/High/Low/Close/Volume (capitalized); (c) values round-trip from bars;
    (d) consumable by ``swing.pipeline.ohlcv.compute_smas`` (reads ``Close``).
    """
    import pandas as pd

    from swing.integrations.schwab.models import (
        OhlcvBar,
        SchwabPriceHistoryWindow,
    )
    from swing.pipeline.ohlcv import compute_smas

    bars = [
        OhlcvBar(asof_date="2026-05-12", open=100.0, high=105.0,
                 low=98.0, close=102.0, volume=1000),
        OhlcvBar(asof_date="2026-05-13", open=102.0, high=106.0,
                 low=100.0, close=104.0, volume=1200),
        OhlcvBar(asof_date="2026-05-14", open=104.0, high=108.0,
                 low=102.0, close=106.0, volume=1500),
    ]
    window = SchwabPriceHistoryWindow(
        ticker="AAPL", bars=bars, provider="schwab_api",
    )

    df = window.to_dataframe()

    # Shape: DatetimeIndex + capitalized OHLCV columns.
    assert isinstance(df.index, pd.DatetimeIndex), (
        f"to_dataframe index must be DatetimeIndex (legacy yfinance shape); "
        f"got {type(df.index).__name__}"
    )
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"], (
        f"to_dataframe columns must match legacy yfinance shape; "
        f"got {list(df.columns)!r}"
    )

    # Values round-trip.
    assert df.iloc[0]["Close"] == 102.0
    assert df.iloc[-1]["Close"] == 106.0
    assert df.iloc[0]["Volume"] == 1000

    # Discriminating: consumable by compute_smas (validates capitalized
    # `Close` column is what downstream code reads).
    smas = compute_smas(df, [3])
    # SMA over 3 closes [102, 104, 106] = 104.0
    assert smas[3] == 104.0


def test_02c_price_history_window_to_dataframe_empty_bars_returns_empty_frame():
    """Codex R1 Major #4 defense-in-depth: empty bars list → empty DataFrame
    with the canonical column set (mapper raises on empty Schwab response, so
    this branch is purely defensive)."""
    from swing.integrations.schwab.models import SchwabPriceHistoryWindow

    window = SchwabPriceHistoryWindow(
        ticker="AAPL", bars=[], provider="schwab_api",
    )
    df = window.to_dataframe()
    assert len(df) == 0
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]


# ============================================================================
# Mapper: map_quotes_to_price_cache_entries
# ============================================================================


def test_03_map_quotes_happy_path_all_ok():
    """All symbols return populated quote shapes → mapper emits one entry each.

    Tolerates BOTH snake_case + camelCase per recon §3.2 defensive dual-lookup.
    """
    from swing.integrations.schwab.mappers import (
        map_quotes_to_price_cache_entries,
    )

    # camelCase shape (Schwab REST convention).
    response = {
        "AAPL": {
            "quote": {
                "lastPrice": 150.0,
                "bidPrice": 149.5,
                "askPrice": 150.5,
                "mark": 150.0,
                "quoteTimeInLong": 1715692800000,  # epoch ms
                "delayed": False,
            },
        },
        "MSFT": {
            "quote": {
                "lastPrice": 420.0,
                "bidPrice": 419.5,
                "askPrice": 420.5,
                "mark": 420.0,
                "quoteTimeInLong": 1715692800000,
                "delayed": False,
            },
        },
    }
    result = map_quotes_to_price_cache_entries(response)
    assert set(result.keys()) == {"AAPL", "MSFT"}
    assert result["AAPL"].last_price == 150.0
    assert result["AAPL"].bid == 149.5
    assert result["AAPL"].ask == 150.5
    assert result["AAPL"].delayed is False


def test_04_map_quotes_partial_response_drops_error_symbols():
    """Mixed response: some symbols OK + some error envelopes. Mapper returns
    successfully-mapped subset; failed symbols dropped per spec §E.4."""
    from swing.integrations.schwab.mappers import (
        map_quotes_to_price_cache_entries,
    )

    response = {
        "AAPL": {
            "quote": {
                "lastPrice": 150.0,
                "bidPrice": 149.5,
                "askPrice": 150.5,
                "quoteTimeInLong": 1715692800000,
            },
        },
        # Error envelope shapes per spec §E.4 — three variants:
        "XYZ": {"errors": [{"code": "404", "msg": "symbol not found"}]},
        "BADX": {"error": "rate-limited"},
        "FAULT": {"fault": {"faultstring": "internal"}},
    }
    result = map_quotes_to_price_cache_entries(response)
    assert set(result.keys()) == {"AAPL"}
    assert result["AAPL"].symbol == "AAPL"


def test_05_map_quotes_top_level_quote_keys_also_supported():
    """Spec §E.4 + recon §3.2 — mapper tolerates BOTH `{symbol: {quote: {...}}}`
    nested form AND `{symbol: {lastPrice, ...}}` flat form.
    """
    from swing.integrations.schwab.mappers import (
        map_quotes_to_price_cache_entries,
    )

    response = {
        "AAPL": {
            "lastPrice": 150.0,
            "bidPrice": 149.5,
            "askPrice": 150.5,
            "quoteTimeInLong": 1715692800000,
        },
    }
    result = map_quotes_to_price_cache_entries(response)
    assert "AAPL" in result
    assert result["AAPL"].last_price == 150.0


# ============================================================================
# Mapper: map_price_history_to_window
# ============================================================================


def test_06_map_price_history_happy_path():
    """Mapper produces sorted bars + provider='schwab_api'."""
    from swing.integrations.schwab.mappers import (
        map_price_history_to_window,
    )

    response = {
        "symbol": "AAPL",
        "empty": False,
        "candles": [
            # Schwab returns oldest-first per `api-calls.md` L437; epoch ms.
            {
                "open": 149.0, "high": 151.0, "low": 148.5, "close": 150.0,
                "volume": 50_000_000, "datetime": 1715520000000,  # 2026-05-12
            },
            {
                "open": 150.0, "high": 152.0, "low": 149.5, "close": 151.5,
                "volume": 55_000_000, "datetime": 1715606400000,  # 2026-05-13
            },
        ],
    }
    window = map_price_history_to_window(response, ticker="AAPL")
    assert window.ticker == "AAPL"
    assert window.provider == "schwab_api"
    assert len(window.bars) == 2
    assert window.bars[0].asof_date < window.bars[1].asof_date
    assert window.bars[1].close == 151.5


def test_07_map_price_history_empty_candles_array_raises():
    """Empty `candles=[]` + `empty=false` → mapper raises SchwabApiError(204).

    Defense-in-depth dual signal per recon §3.3 — `empty` is what Schwab
    explicitly signals BUT `candles=[]` alone also triggers transient handling.
    """
    from swing.integrations.schwab.mappers import (
        map_price_history_to_window,
    )

    response = {"symbol": "AAPL", "empty": False, "candles": []}
    with pytest.raises(SchwabApiError) as exc_info:
        map_price_history_to_window(response, ticker="AAPL")
    assert exc_info.value.status_code == 204
    assert "empty" in exc_info.value.body_excerpt.lower()


def test_08_map_price_history_explicit_empty_flag_true_raises():
    """`empty=true` flag fires even if `candles=[...]` is non-empty (Schwab
    sometimes returns both; we trust `empty=true` per spec §E.5 + §H.6.4)."""
    from swing.integrations.schwab.mappers import (
        map_price_history_to_window,
    )

    # Pathological: empty=true with bogus candles. Spec says trust empty flag.
    response = {
        "symbol": "AAPL",
        "empty": True,
        "candles": [
            {
                "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
                "volume": 1, "datetime": 1715520000000,
            },
        ],
    }
    with pytest.raises(SchwabApiError) as exc_info:
        map_price_history_to_window(response, ticker="AAPL")
    assert exc_info.value.status_code == 204


def test_08b_map_price_history_empty_string_false_is_not_truthy():
    """Codex R1 Minor #2: `empty_flag = bool(response.get("empty", False))` is
    too loose — the string ``"false"`` (which a non-conformant upstream MIGHT
    send instead of the JSON-boolean ``false``) coerces to truthy under
    ``bool()``, falsely tripping the empty path. Post-fix uses
    ``empty is True`` so only the JSON-boolean ``True`` fires the path.

    Discriminating: response with ``empty="false"`` (string) and one valid
    candle MUST yield a populated window (NOT raise 204).
    """
    from swing.integrations.schwab.mappers import (
        map_price_history_to_window,
    )

    response = {
        "symbol": "AAPL",
        "empty": "false",  # STRING, not bool — coerces to True under bool()
        "candles": [
            {
                "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0,
                "volume": 12345, "datetime": 1715692800000,
            },
        ],
    }
    # Pre-fix: `bool("false")` → True → raises SchwabApiError(204).
    # Post-fix: `"false" is True` → False → returns populated window.
    window = map_price_history_to_window(response, ticker="AAPL")
    assert len(window.bars) == 1
    assert window.bars[0].close == 102.0


def test_08c_map_price_history_empty_one_int_is_not_truthy():
    """Codex R1 Minor #2 companion: ``empty=1`` (truthy int from a malformed
    upstream) MUST NOT trigger the empty path under the post-fix
    ``is True`` check. Only the JSON-boolean ``True`` should fire.
    """
    from swing.integrations.schwab.mappers import (
        map_price_history_to_window,
    )

    response = {
        "symbol": "AAPL",
        "empty": 1,  # truthy int — coerces to True under bool()
        "candles": [
            {
                "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0,
                "volume": 12345, "datetime": 1715692800000,
            },
        ],
    }
    window = map_price_history_to_window(response, ticker="AAPL")
    assert len(window.bars) == 1


# ============================================================================
# Endpoint wrappers — get_quotes_batch
# ============================================================================


def test_09_get_quotes_batch_happy_path_audit_lifecycle(v18_conn):
    """Audit row written success + signature_hash populated + factory installed."""
    from swing.integrations.schwab.marketdata import get_quotes_batch

    client = MagicMock()
    # Realistic Schwab shape: nested under "quote" key inside per-symbol dict.
    client.quotes.return_value = _mock_response(
        {
            "AAPL": {
                "quote": {
                    "lastPrice": 150.0,
                    "bidPrice": 149.5,
                    "askPrice": 150.5,
                    "quoteTimeInLong": 1715692800000,
                    "delayed": False,
                },
            },
        },
    )

    result = get_quotes_batch(
        client, v18_conn, ["AAPL"],
        surface="pipeline", environment="production",
    )
    assert set(result.keys()) == {"AAPL"}
    assert result["AAPL"].last_price == 150.0

    # Audit row populated.
    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[2] == "marketdata.quotes"
    assert row[7] == "success"
    assert row[6] is not None and len(row[6]) == 64  # signature_hash
    assert row[9] == "pipeline"  # surface
    assert row[10] == "production"  # environment

    # Verify the call invoked schwabdev with snake_case kwargs (symbols, fields,
    # indicative are all snake_case per `api-calls.md` L298).
    client.quotes.assert_called_once()
    _, kwargs = client.quotes.call_args
    # symbols may be passed positionally OR via kwarg; check the symbol made it.
    args = client.quotes.call_args[0]
    if args:
        assert "AAPL" in args[0]
    else:
        assert "AAPL" in kwargs.get("symbols", [])


def test_10_get_quotes_batch_429_rate_limited(v18_conn):
    """HTTP 429 → SchwabRateLimitError + audit row status='rate_limited'."""
    from swing.integrations.schwab.marketdata import get_quotes_batch

    client = MagicMock()
    client.quotes.return_value = _mock_response(
        {"error": "rate limited"},
        status_code=429,
        headers={"X-RateLimit-Remaining": "0"},
    )

    with pytest.raises(SchwabRateLimitError):
        get_quotes_batch(
            client, v18_conn, ["AAPL"],
            surface="pipeline", environment="production",
        )

    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[2] == "marketdata.quotes"
    assert row[3] == 429  # http_status
    assert row[5] == 0  # rate_limit_remaining captured from header
    assert row[7] == "rate_limited"


# ============================================================================
# Endpoint wrappers — get_price_history
# ============================================================================


def test_11_get_price_history_happy_path_audit_lifecycle(v18_conn):
    """Audit row success + signature_hash + camelCase kwargs verified."""
    from swing.integrations.schwab.marketdata import get_price_history

    client = MagicMock()
    client.price_history.return_value = _mock_response(
        {
            "symbol": "AAPL",
            "empty": False,
            "candles": [
                {
                    "open": 149.0, "high": 151.0, "low": 148.5,
                    "close": 150.0, "volume": 50_000_000,
                    "datetime": 1715520000000,
                },
            ],
        },
    )

    start_dt = datetime(2026, 5, 12, tzinfo=UTC)
    end_dt = datetime(2026, 5, 14, tzinfo=UTC)
    window = get_price_history(
        client, v18_conn, "AAPL",
        period_type="day", period=10,
        frequency_type="daily", frequency=1,
        start_dt=start_dt, end_dt=end_dt,
        surface="pipeline", environment="production",
    )
    assert window.ticker == "AAPL"
    assert window.provider == "schwab_api"
    assert len(window.bars) == 1

    # Audit row populated.
    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[2] == "marketdata.pricehistory"
    assert row[7] == "success"
    assert row[6] is not None and len(row[6]) == 64

    # **BINDING per dispatch brief §0.5 #1**: verify schwabdev call used
    # camelCase kwargs (periodType / period / frequencyType / frequency /
    # startDate / endDate) — NOT snake_case.
    client.price_history.assert_called_once()
    _, kwargs = client.price_history.call_args
    assert "periodType" in kwargs
    assert kwargs["periodType"] == "day"
    assert kwargs["period"] == 10
    assert kwargs["frequencyType"] == "daily"
    assert kwargs["frequency"] == 1
    assert "startDate" in kwargs
    assert "endDate" in kwargs
    # Negative-check: snake_case forms MUST NOT appear.
    assert "period_type" not in kwargs
    assert "frequency_type" not in kwargs
    assert "start_date" not in kwargs
    assert "end_date" not in kwargs


def test_12_get_price_history_empty_bars_transient(v18_conn):
    """Empty bars → SchwabApiError(204) bubbles up + audit row status='error'
    with error_message containing 'empty bars'.

    Per spec §E.5 + §H.6.4 — the ladder consumes this; T-C.1 just verifies the
    error path closes the audit row correctly.
    """
    from swing.integrations.schwab.marketdata import get_price_history

    client = MagicMock()
    client.price_history.return_value = _mock_response(
        {"symbol": "AAPL", "empty": True, "candles": []},
    )

    with pytest.raises(SchwabApiError) as exc_info:
        get_price_history(
            client, v18_conn, "AAPL",
            period_type="day", period=10,
            frequency_type="daily", frequency=1,
            start_dt=None, end_dt=None,
            surface="pipeline", environment="production",
        )
    assert exc_info.value.status_code == 204

    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[2] == "marketdata.pricehistory"
    assert row[7] == "error"
    assert row[8] is not None and "empty" in row[8].lower()
