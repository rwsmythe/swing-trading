# tests/integrations/schwab/test_quote_regular_session.py
from swing.integrations.schwab.mappers import map_quotes_to_price_cache_entries


def _resp(symbol, body):
    return {symbol: {"symbol": symbol, "quote": body}}  # match the real envelope


def test_only_ext_hours_lastprice_is_dropped():
    """M1: a quote with ONLY lastPrice (no regularMarketLastPrice) is DROPPED
    (yfinance fallback) -- lastPrice is the ext-hours print (L1). A sentinel
    lastPrice that, if surfaced, would fail the assertion."""
    out = map_quotes_to_price_cache_entries(_resp("AAPL", {
        "lastPrice": 999.99,  # ext-hours sentinel -- must NEVER surface
        "bidPrice": 999.0, "askPrice": 1000.0,
    }))
    assert "AAPL" not in out  # dropped


def test_regular_last_with_regular_bid_ask_emits_regular_value():
    out = map_quotes_to_price_cache_entries(_resp("AAPL", {
        "lastPrice": 999.99,  # ext-hours -- must be ignored
        "regularMarketLastPrice": 150.25,
        "regularMarketTradeTime": 1_700_000_000_000,
        "regularMarketBidPrice": 150.20, "regularMarketAskPrice": 150.30,
    }))
    assert "AAPL" in out
    entry = out["AAPL"]
    assert entry.last_price == 150.25     # regular, not 999.99
    assert entry.last_price != 999.99


def test_regular_last_but_ext_hours_bid_ask_is_dropped():
    """A regular last present but NO regular bid/ask provenance -> drop (do not
    surface the extended-book bid/ask). See spec 4.2."""
    out = map_quotes_to_price_cache_entries(_resp("AAPL", {
        "regularMarketLastPrice": 150.25,
        "regularMarketTradeTime": 1_700_000_000_000,
        "bidPrice": 149.0, "askPrice": 151.0,  # ext-hours book only
    }))
    assert "AAPL" not in out  # dropped (no regular bid/ask)


def test_ext_hours_mark_never_surfaces():
    """Codex R2 MAJOR: the bare ext-hours `mark` must NEVER surface. With full
    regular last/bid/ask but only an ext-hours `mark` (no regularMarketMark),
    the emitted entry.mark is None -- not the ext-hours sentinel."""
    out = map_quotes_to_price_cache_entries(_resp("AAPL", {
        "regularMarketLastPrice": 150.25,
        "regularMarketTradeTime": 1_700_000_000_000,
        "regularMarketBidPrice": 150.20, "regularMarketAskPrice": 150.30,
        "mark": 999.99,  # ext-hours mark sentinel -- must NOT surface
    }))
    assert "AAPL" in out
    assert out["AAPL"].mark is None
    assert out["AAPL"].mark != 999.99


def test_regular_market_mark_surfaces():
    out = map_quotes_to_price_cache_entries(_resp("AAPL", {
        "regularMarketLastPrice": 150.25,
        "regularMarketTradeTime": 1_700_000_000_000,
        "regularMarketBidPrice": 150.20, "regularMarketAskPrice": 150.30,
        "regularMarketMark": 150.26, "mark": 999.99,
    }))
    assert out["AAPL"].mark == 150.26  # regular, not the ext-hours 999.99
