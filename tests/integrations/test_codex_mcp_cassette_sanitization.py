"""Phase 13 T2.SB1 task T-A.1.4 — codex_mcp_pattern_review cassette
sanitization tests.

Per plan §G.1 T-A.1.4 Step 1 + spec §A.10 + post-Phase-12 forward-binding
lesson #2. Mirrors ``test_pattern_labeler_cassette_sanitization.py`` for
the OpenAI / Codex MCP cassette domain.
"""
from __future__ import annotations

from types import SimpleNamespace

from tests.integrations._cassette_sanitization import (
    FILTER_HEADERS_CODEX,
    FILTER_QUERY_PARAMETERS_SHARED,
    codex_mcp_vcr_config,
    redact_codex_mcp_response,
    sanitize_codex_mcp_request,
)

SENTINEL_API_KEY = "sk-proj-deadbeefcafebabe1234567890abcdef1234567890"
SENTINEL_HEX_TOKEN = "f" * 40
SENTINEL_BASE64_TOKEN = "WXYZabcdefghijklmnopqrstuvwxyz0123456789ABC="
SENTINEL_CHATCMPL_ID = "chatcmpl-XYZsensitive_id_string"
SENTINEL_SESSION_ID = "sess_01ABCdeadbeef_sensitive"


def test_codex_mcp_response_body_redacts_api_key() -> None:
    """OpenAI / Codex MCP ``api_key`` field value redacted."""
    body_json = (
        f'{{"api_key": "{SENTINEL_API_KEY}", "model": "gpt-5"}}'
    )
    response = {"body": {"string": body_json}}
    sanitized = redact_codex_mcp_response(response)
    raw = sanitized["body"]["string"]
    assert SENTINEL_API_KEY not in raw
    assert '"api_key": "<REDACTED>"' in raw


def test_codex_mcp_response_body_redacts_session_id() -> None:
    """Codex MCP ``session_id`` field value redacted."""
    body_json = f'{{"session_id": "{SENTINEL_SESSION_ID}", "ok": true}}'
    response = {"body": {"string": body_json}}
    sanitized = redact_codex_mcp_response(response)
    raw = sanitized["body"]["string"]
    assert SENTINEL_SESSION_ID not in raw
    assert '"session_id": "<REDACTED>"' in raw


def test_codex_mcp_response_body_redacts_chatcmpl_id() -> None:
    """OpenAI completion id (chatcmpl-*) masked for privacy."""
    body_json = (
        f'{{"id": "{SENTINEL_CHATCMPL_ID}", "object": "chat.completion"}}'
    )
    response = {"body": {"string": body_json}}
    sanitized = redact_codex_mcp_response(response)
    raw = sanitized["body"]["string"]
    assert SENTINEL_CHATCMPL_ID not in raw
    assert "<REDACTED_chatcmpl_id>" in raw


def test_codex_mcp_response_body_scrubs_token_shaped_substrings() -> None:
    """Heuristic 32+ hex / 24+ base64 scrub catches token-shape substrings."""
    body_json = (
        f'{{"trace": "{SENTINEL_HEX_TOKEN}", '
        f'"tok": "{SENTINEL_BASE64_TOKEN}", "ok": true}}'
    )
    response = {"body": {"string": body_json}}
    sanitized = redact_codex_mcp_response(response)
    raw = sanitized["body"]["string"]
    assert SENTINEL_HEX_TOKEN not in raw
    assert SENTINEL_BASE64_TOKEN not in raw


def test_codex_mcp_request_uri_scrubs_token_substrings() -> None:
    """``before_record_request`` removes token-shape substrings from URI."""
    fake_request = SimpleNamespace(
        uri=f"https://api.openai.com/v1/chat/completions/{SENTINEL_HEX_TOKEN}",
    )
    sanitized = sanitize_codex_mcp_request(fake_request)
    assert SENTINEL_HEX_TOKEN not in sanitized.uri
    assert "<hex-token>" in sanitized.uri


def test_codex_mcp_vcr_config_includes_required_headers() -> None:
    """VCR config exposes ``filter_headers`` containing all required scrubs."""
    config = codex_mcp_vcr_config()
    headers_set = set(config["filter_headers"])
    for required in (
        "authorization",
        "x-api-key",
        "openai-organization",
        "x-codex-session-id",
    ):
        assert required in headers_set, (
            f"codex_mcp_vcr_config missing header filter {required!r}"
        )


def test_codex_mcp_vcr_config_wires_before_record_callbacks() -> None:
    """VCR config wires both ``before_record_request`` +
    ``before_record_response`` callables.
    """
    config = codex_mcp_vcr_config()
    assert callable(config["before_record_request"])
    assert callable(config["before_record_response"])


def test_codex_mcp_filter_constants_are_immutable_snapshots() -> None:
    """``FILTER_HEADERS_CODEX`` + ``FILTER_QUERY_PARAMETERS_SHARED`` are
    tuples (not lists).
    """
    assert isinstance(FILTER_HEADERS_CODEX, tuple)
    assert isinstance(FILTER_QUERY_PARAMETERS_SHARED, tuple)
