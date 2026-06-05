# tests/integrations/schwab/test_mapper_float_normalization.py
import pytest

from swing.integrations.schwab.client import SchwabBarConsistencyError
from swing.integrations.schwab.mappers import map_price_history_to_window


def _envelope(open_, high, low, close):
    return {"candles": [{"datetime": 1_700_000_000_000, "open": open_,
                         "high": high, "low": low, "close": close,
                         "volume": 1000}], "empty": False, "symbol": "AAPL"}


def test_float_noise_rounds_clean():
    """M5: sub-ulp float noise must round clean (no raise). high=12.34,
    close=12.340000000001 -> post-round 12.34 == 12.34."""
    win = map_price_history_to_window(
        _envelope(12.30, 12.34, 12.29, 12.340000000001), "AAPL")
    assert win is not None
    bar = win.bars[0]
    assert bar.high == 12.34
    assert bar.close == 12.34


def test_cents_level_inconsistency_still_raises_typed():
    """A genuine ext-hours violation (high below max(open,close) by cents)
    must STILL raise -- as the typed SchwabBarConsistencyError, not a raw
    ValueError or SchwabSchemaParityError."""
    with pytest.raises(SchwabBarConsistencyError) as ei:
        map_price_history_to_window(_envelope(12.00, 12.00, 11.50, 12.50), "AAPL")
    assert ei.value.asof_date  # date populated
    assert "OHLC consistency" in str(ei.value)
