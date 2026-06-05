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
