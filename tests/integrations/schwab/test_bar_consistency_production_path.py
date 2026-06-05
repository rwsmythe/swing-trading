# tests/integrations/schwab/test_bar_consistency_production_path.py
"""A genuinely inconsistent candle (high below max(open,close)) fed through the
REAL get_price_history wrapper must: (1) raise SchwabBarConsistencyError (proving
_call_endpoint caught it as SchwabApiError, NOT re-wrapped as
SchwabSchemaParityError); (2) close the schwab_api_calls audit row with
status='error' + a message containing 'OHLC consistency'."""
import pytest

from swing.data.db import ensure_schema  # builds + migrates a fresh DB (returns conn)
from swing.integrations.schwab.client import (
    SchwabBarConsistencyError,
    SchwabSchemaParityError,
)
from swing.integrations.schwab.marketdata import get_price_history


class _FakeClient:
    """Returns a single ext-hours-inconsistent candle (high 12.00 < close 12.50)."""

    def price_history(self, symbol, **kwargs):
        class _Resp:
            status_code = 200

            def json(self):
                return {"candles": [{"datetime": 1_700_000_000_000,
                                     "open": 12.00, "high": 12.00,
                                     "low": 11.50, "close": 12.50,
                                     "volume": 1000}], "empty": False,
                        "symbol": symbol}
        return _Resp()


def test_contaminated_candle_raises_typed_and_audits(tmp_path):
    conn = ensure_schema(tmp_path / "swing.db")  # creates + migrates; has schwab_api_calls
    with pytest.raises(SchwabBarConsistencyError) as ei:
        get_price_history(
            _FakeClient(), conn, "AAPL",
            period_type="year", period=1, frequency_type="daily", frequency=1,
            start_dt=None, end_dt=None,
            surface="cli", environment="production", pipeline_run_id=None,
        )
    assert not isinstance(ei.value, SchwabSchemaParityError)  # NOT re-wrapped
    row = conn.execute(
        "SELECT status, error_message FROM schwab_api_calls "
        "ORDER BY call_id DESC LIMIT 1").fetchone()
    assert row[0] == "error"
    assert "OHLC consistency" in (row[1] or "")
