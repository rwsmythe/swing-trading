"""Slice 1b — OQ-10 rate-limit header-name capture diagnostic (no value leak)."""
from __future__ import annotations

import logging

from swing.integrations.schwab import marketdata


class _Resp:
    def __init__(self, headers):
        self.status_code = 200
        self.headers = headers

    def json(self):
        return {"ok": True}


def test_capture_logs_header_keys_when_no_known_header(caplog):
    marketdata._reset_header_capture_for_tests()  # clear the once-per-process flag
    with caplog.at_level(logging.INFO, logger="swing.integrations.schwab.marketdata"):
        marketdata._extract_response_payload(
            _Resp({"X-Mystery-Budget": "118", "Content-Type": "application/json"}),
            endpoint="quotes",
        )
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "X-Mystery-Budget" in msgs        # the KEY is surfaced for OQ-10 confirmation
    assert "118" not in msgs                  # the VALUE is NEVER logged


def test_no_capture_when_known_header_present(caplog):
    marketdata._reset_header_capture_for_tests()
    with caplog.at_level(logging.INFO, logger="swing.integrations.schwab.marketdata"):
        _payload, _status, remaining = marketdata._extract_response_payload(
            _Resp({"X-RateLimit-Remaining": "42"}), endpoint="quotes",
        )
    assert remaining == 42
    assert "header-name capture" not in " ".join(r.getMessage() for r in caplog.records)
