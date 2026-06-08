# tests/integrations/schwab/test_quote_fields_live.py
import pytest

pytestmark = pytest.mark.slow


def test_recorded_quote_carries_regular_session_fields():
    """OQ-3 validation: a recorded live quote (cassette) MUST contain the two
    regular-session fields the B2 mapper consumes -- regularMarketLastPrice +
    regularMarketTradeTime. They live in the `regular` sub-block (a sibling of
    `quote`) which ships ONLY under fields="all"; under fields="quote" the block
    is absent and the mapper drops every Schwab quote to yfinance. There is NO
    regularMarketBidPrice/AskPrice in the Schwab schema (bid/ask are left None;
    only last_price is consumed downstream). Record with --fields all (the
    recorder default), OR accept the yfinance-drop (OQ-3 operator decision)."""
    from pathlib import Path
    cassette = Path(__file__).parent / "cassettes" / "quote_regular_fields.yaml"
    assert cassette.exists(), "record the live quote cassette first (runbook)"
    text = cassette.read_text()
    for field in ("regularMarketLastPrice", "regularMarketTradeTime"):
        assert field in text, (
            f"{field} absent under the chosen fields= selection -- the `regular` "
            f"block ships only under fields=all; B2 would drop every Schwab "
            f"quote to yfinance. Use --fields all or accept the drop (OQ-3).")
