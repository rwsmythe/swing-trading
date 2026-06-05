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
