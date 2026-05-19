"""Phase 13 T2.SB1 task T-A.1.4 — pattern_labeler cassette sanitization tests.

Per plan §G.1 T-A.1.4 Step 1: sentinel-leak audit tests per spec §A.10 +
post-Phase-12 forward-binding lesson #2. Plant known sentinel strings in
request URI + response body; assert sentinel absent post-sanitization.
"""
from __future__ import annotations

from types import SimpleNamespace

from tests.integrations._cassette_sanitization import (
    FILTER_HEADERS_CLAUDE,
    FILTER_QUERY_PARAMETERS_SHARED,
    pattern_labeler_vcr_config,
    redact_pattern_labeler_response,
    sanitize_pattern_labeler_request,
)

# ============================================================================
# Sentinel substrings planted in fake request/response payloads.
# ============================================================================

SENTINEL_API_KEY = "sk-ant-api03-deadbeefcafebabe1234567890abcdef1234567890"
SENTINEL_HEX_TOKEN = "a" * 40  # 32+ hex sentinel.
SENTINEL_BASE64_TOKEN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/=="  # 40+ base64.
SENTINEL_MESSAGE_ID = "msg_01XYZsensitive_id_string"


# ============================================================================
# Tests
# ============================================================================


def test_pattern_labeler_response_body_redacts_api_key() -> None:
    """Anthropic API ``api_key`` field value redacted to ``<REDACTED>``."""
    body_json = (
        f'{{"api_key": "{SENTINEL_API_KEY}", '
        f'"model": "claude-sonnet-4-6", "status": "ok"}}'
    )
    response = {"body": {"string": body_json}}
    sanitized = redact_pattern_labeler_response(response)
    raw = sanitized["body"]["string"]
    assert SENTINEL_API_KEY not in raw
    assert '"api_key": "<REDACTED>"' in raw


def test_pattern_labeler_response_body_scrubs_token_shaped_hex() -> None:
    """Heuristic 32+ hex scrub catches token-shaped substrings."""
    body_json = (
        f'{{"trace_id": "{SENTINEL_HEX_TOKEN}", '
        '"latency_ms": 1234, "model": "claude-sonnet-4-6"}'
    )
    response = {"body": {"string": body_json}}
    sanitized = redact_pattern_labeler_response(response)
    raw = sanitized["body"]["string"]
    assert SENTINEL_HEX_TOKEN not in raw
    assert "<REDACTED>" in raw


def test_pattern_labeler_response_body_scrubs_token_shaped_base64() -> None:
    """Heuristic 24+ base64 scrub catches token-shaped substrings."""
    body_json = (
        f'{{"session_token": "{SENTINEL_BASE64_TOKEN}", '
        '"status": "ok"}'
    )
    response = {"body": {"string": body_json}}
    sanitized = redact_pattern_labeler_response(response)
    raw = sanitized["body"]["string"]
    assert SENTINEL_BASE64_TOKEN not in raw


def test_pattern_labeler_response_redacts_message_id() -> None:
    """Anthropic message id (msg_*) gets masked for privacy."""
    body_json = (
        f'{{"id": "{SENTINEL_MESSAGE_ID}", "type": "message", '
        '"role": "assistant"}'
    )
    response = {"body": {"string": body_json}}
    sanitized = redact_pattern_labeler_response(response)
    raw = sanitized["body"]["string"]
    assert SENTINEL_MESSAGE_ID not in raw
    assert "<REDACTED_msg_id>" in raw


def test_pattern_labeler_request_uri_scrubs_token_shaped_substrings() -> None:
    """``before_record_request`` removes token-shape substrings from URI."""
    fake_request = SimpleNamespace(
        uri=f"https://api.anthropic.com/v1/messages/{SENTINEL_HEX_TOKEN}",
    )
    sanitized = sanitize_pattern_labeler_request(fake_request)
    assert SENTINEL_HEX_TOKEN not in sanitized.uri
    assert "<hex-token>" in sanitized.uri


def test_pattern_labeler_vcr_config_includes_required_headers() -> None:
    """VCR config exposes ``filter_headers`` containing all required scrubs."""
    config = pattern_labeler_vcr_config()
    headers_set = set(config["filter_headers"])
    for required in ("authorization", "x-api-key", "cookie"):
        assert required in headers_set, (
            f"pattern_labeler_vcr_config missing header filter {required!r}"
        )
    for required in ("api_key", "access_token"):
        assert required in set(config["filter_query_parameters"])


def test_pattern_labeler_vcr_config_wires_before_record_callbacks() -> None:
    """VCR config wires both ``before_record_request`` +
    ``before_record_response`` callables.
    """
    config = pattern_labeler_vcr_config()
    assert callable(config["before_record_request"])
    assert callable(config["before_record_response"])


def test_pattern_labeler_filter_constants_are_immutable_snapshots() -> None:
    """``FILTER_HEADERS_CLAUDE`` is a tuple (not list); prevents accidental
    mutation in test fixtures.
    """
    assert isinstance(FILTER_HEADERS_CLAUDE, tuple)
    assert isinstance(FILTER_QUERY_PARAMETERS_SHARED, tuple)


def test_pattern_labeler_response_with_bytes_body_handled_correctly() -> None:
    """Response body may be bytes (not str); scrubber handles both."""
    body_bytes = (
        b'{"api_key": "' + SENTINEL_API_KEY.encode() + b'", "ok": true}'
    )
    response = {"body": {"string": body_bytes}}
    sanitized = redact_pattern_labeler_response(response)
    raw = sanitized["body"]["string"]
    assert isinstance(raw, bytes)
    assert SENTINEL_API_KEY.encode() not in raw
    assert b"<REDACTED>" in raw


def test_pattern_labeler_response_missing_body_no_op() -> None:
    """Response without ``body`` field returned unchanged."""
    response = {"status": {"code": 500}}
    sanitized = redact_pattern_labeler_response(response)
    assert sanitized == response
