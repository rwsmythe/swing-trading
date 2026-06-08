# tests/integrations/schwab/test_quote_regular_session.py
"""Slice-B quote-mapper regular-session sourcing (OQ-3 A-lite).

The Schwab `/quotes` per-symbol payload nests the regular-session fields in a
`regular` sub-block that is a SIBLING of `quote` (NOT inside it), returned only
under `fields="all"` -- see the captured spec
`reference/schwab-api/market-data-specification.md:102-104`. The block is
`{regularMarketLastPrice, regularMarketLastSize, regularMarketNetChange,
regularMarketPercentChange, regularMarketTradeTime}` -- there is NO
`regularMarketBidPrice`/`AskPrice`/`Mark`.

These fixtures mirror that REAL nested shape (the prior fixtures wrongly nested
`regularMarket*` inside `quote`, masking the wrong-sub-block read; only the live
recorder caught it). The mapper sources `last_price`/`quote_time` from the
`regular` block, gates on `regularMarketLastPrice` only, and leaves `bid`/`ask`/
`mark` as `None` (unused downstream; never the ext-hours-tainted bare `quote`
fields -- L1).
"""
from swing.integrations.schwab.mappers import map_quotes_to_price_cache_entries


def _resp(symbol, *, quote=None, regular=None, extended=None):
    """Build the real per-symbol envelope. `quote`/`regular`/`extended` are
    SIBLING sub-blocks (the live `fields="all"` shape)."""
    payload = {"symbol": symbol}
    if quote is not None:
        payload["quote"] = quote
    if regular is not None:
        payload["regular"] = regular
    if extended is not None:
        payload["extended"] = extended
    return {symbol: payload}


def test_regular_block_maps_successfully():
    """A quote WITH a `regular` sibling block maps: last_price comes from
    regularMarketLastPrice (NOT the ext-hours quote.lastPrice), bid/ask/mark are
    None. FAILS pre-fix (mapper read regularMarket* from the `quote` body, found
    nothing, dropped) / PASSES post-fix."""
    out = map_quotes_to_price_cache_entries(_resp(
        "AAPL",
        quote={  # ext-hours book -- must NEVER surface (L1)
            "lastPrice": 999.99, "bidPrice": 999.0, "askPrice": 1000.0,
            "mark": 999.99,
        },
        regular={
            "regularMarketLastPrice": 150.25,
            "regularMarketLastSize": 50,
            "regularMarketNetChange": 6.6,
            "regularMarketPercentChange": 2.1,
            "regularMarketTradeTime": 1_700_000_000_000,
        },
    ))
    assert "AAPL" in out
    entry = out["AAPL"]
    assert entry.last_price == 150.25     # regular, not the ext-hours 999.99
    assert entry.last_price != 999.99
    assert entry.bid is None              # no regular-session bid; never ext-hours
    assert entry.ask is None
    assert entry.mark is None
    assert entry.quote_time  # populated from regularMarketTradeTime


def test_regular_block_snake_case_forward_compat():
    """Snake_case fwd-compat fallbacks within the `regular` block still map."""
    out = map_quotes_to_price_cache_entries(_resp(
        "AAPL",
        regular={
            "regular_market_last_price": 150.25,
            "regular_market_trade_time": 1_700_000_000_000,
        },
    ))
    assert "AAPL" in out
    assert out["AAPL"].last_price == 150.25


def test_fields_quote_only_no_regular_block_is_dropped():
    """A `fields="quote"`-only payload (a `quote` block, NO `regular` block) ->
    DROPPED to yfinance: no regular-session provenance, and the bare
    quote.lastPrice is the ext-hours print (L1). The ext-hours sentinel must
    never surface."""
    out = map_quotes_to_price_cache_entries(_resp(
        "AAPL",
        quote={"lastPrice": 999.99, "bidPrice": 999.0, "askPrice": 1000.0},
    ))
    assert "AAPL" not in out  # dropped (no regular block)


def test_ext_hours_only_payload_is_dropped():
    """An extended-hours-only payload (an `extended` block, no `regular`) ->
    DROPPED (L1: never surface the ext-hours book)."""
    out = map_quotes_to_price_cache_entries(_resp(
        "AAPL",
        extended={"lastPrice": 999.99, "bidPrice": 999.0, "askPrice": 1000.0,
                  "tradeTime": 1_700_000_000_000},
    ))
    assert "AAPL" not in out  # dropped (no regular-session provenance)


def test_regular_block_missing_last_price_is_dropped():
    """A `regular` block present but WITHOUT regularMarketLastPrice -> DROPPED
    (gate is on regularMarketLastPrice only; without it there is no priced
    value)."""
    out = map_quotes_to_price_cache_entries(_resp(
        "AAPL",
        regular={"regularMarketTradeTime": 1_700_000_000_000,
                 "regularMarketNetChange": 6.6},
    ))
    assert "AAPL" not in out


def test_error_envelope_is_dropped():
    """A per-symbol error envelope still drops (unchanged)."""
    out = map_quotes_to_price_cache_entries(
        {"BADX": {"errors": [{"id": "x", "status": "404", "title": "Not Found"}]}},
    )
    assert "BADX" not in out


def test_non_dict_payload_is_dropped():
    """A non-dict per-symbol payload still drops (unchanged)."""
    out = map_quotes_to_price_cache_entries({"AAPL": "not-a-dict"})
    assert "AAPL" not in out
