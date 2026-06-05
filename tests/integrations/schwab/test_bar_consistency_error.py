# tests/integrations/schwab/test_bar_consistency_error.py
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabBarConsistencyError,
)


def test_bar_consistency_error_is_schwab_api_error():
    """OQ-4: subclass SchwabApiError so the ladder's
    `except (SchwabAuthError, SchwabRateLimitError, SchwabApiError)` catches
    it (clean yfinance fallback, not the opaque catch-all)."""
    exc = SchwabBarConsistencyError("2026-06-04", "low (12.5) must be <= min(...)")
    assert isinstance(exc, SchwabApiError)


def test_bar_consistency_error_carries_readable_message_and_attrs():
    exc = SchwabBarConsistencyError("2026-06-04", "high (12.0) < max(open,close) (12.5)")
    assert exc.asof_date == "2026-06-04"
    # str must be readable for the audit error_message (OHLC detail carries no
    # account_hash, so a readable message is redaction-safe).
    assert "OHLC consistency" in str(exc)
    assert "2026-06-04" in str(exc)
    # SchwabApiError consumers may read these attributes.
    assert exc.status_code == 422
    assert exc.body_excerpt == ""
