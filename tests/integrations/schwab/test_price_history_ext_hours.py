# tests/integrations/schwab/test_price_history_ext_hours.py
import inspect

import schwabdev


def test_price_history_signature_accepts_ext_hours_kwargs():
    """L5 signature-pin: schwabdev 3.0.5's price_history MUST accept
    needExtendedHoursData + needPreviousClose, or our wrapper's kwargs would
    raise TypeError at runtime (cassettes stub the call and won't catch it)."""
    sig = inspect.signature(schwabdev.Client.price_history)
    params = set(sig.parameters)
    assert "needExtendedHoursData" in params
    assert "needPreviousClose" in params


def test_wrapper_passes_need_extended_hours_false(monkeypatch):
    """The wrapper's _client_method MUST forward needExtendedHoursData=False
    (and needPreviousClose=False). OLD path omitted both -> Schwab server
    default needExtendedHoursData=true folds ext-hours prints. NEW path pins
    them off."""
    import swing.integrations.schwab.marketdata as md

    captured = {}

    class _FakeClient:
        def price_history(self, symbol, **kwargs):
            captured.update(kwargs)
            captured["symbol"] = symbol
            # Return a minimal candle envelope the mapper would accept.
            return type("Resp", (), {"status_code": 200, "json": lambda self: {
                "candles": [{"datetime": 0, "open": 10.0, "high": 11.0,
                             "low": 9.0, "close": 10.5, "volume": 100}],
                "empty": False}})()

    # Drive only the inner _client_method closure: assert the kwargs reach it.
    md_call = md._build_price_history_client_method(
        _FakeClient(), "AAPL",
        period_type="year", period=1, frequency_type="daily", frequency=1,
        start_dt=0, end_dt=1,
    )
    md_call()
    assert captured["needExtendedHoursData"] is False
    assert captured["needPreviousClose"] is False
