# tests/integrations/schwab/test_quote_fields_live.py
import pytest

pytestmark = pytest.mark.slow


def test_recorded_quote_carries_regular_session_fields():
    """OQ-3 validation: a recorded live quote (cassette) MUST contain ALL FOUR
    regular-session fields the B2 mapper consumes -- regularMarketLastPrice,
    regularMarketTradeTime, regularMarketBidPrice, regularMarketAskPrice. B2
    requires last AND bid AND ask, so if bid/ask are absent the mapper drops
    EVERY Schwab quote to yfinance (the path goes dead). Widen fields= until
    all four appear, OR (operator decision per OQ-3) accept the yfinance-drop."""
    from pathlib import Path
    cassette = Path(__file__).parent / "cassettes" / "quote_regular_fields.yaml"
    assert cassette.exists(), "record the live quote cassette first (runbook)"
    text = cassette.read_text()
    for field in ("regularMarketLastPrice", "regularMarketTradeTime",
                  "regularMarketBidPrice", "regularMarketAskPrice"):
        assert field in text, (
            f"{field} absent under the chosen fields= selection -- B2 would "
            f"drop every Schwab quote to yfinance. Widen fields= or accept "
            f"the drop (OQ-3 operator decision).")
