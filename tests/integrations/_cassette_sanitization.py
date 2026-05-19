"""Phase 13 T2.SB1 task T-A.1.4 — cassette sanitization filters.

Per plan §A.10 + spec §A.10 + post-Phase-12 forward-binding lesson #2:
``before_record_request`` (URI/path) + ``before_record_response`` (body)
filters for two NEW cassette domains:

  - ``pattern_labeler``: any HTTP traffic the Claude Code ``Agent`` tool
    issues when invoking the ``pattern-labeler`` subagent (Anthropic API
    endpoints; auth headers + message-content PII).
  - ``codex_mcp_pattern_review``: any HTTP traffic the copowers Codex MCP
    server issues when running the 2nd-reviewer dispatch (OpenAI API
    endpoints + Codex telemetry).

Both domains share the SAME defense-in-depth approach as the Schwab
cassette infrastructure shipped at post-Phase-12 Sub-bundle 1
(``tests/conftest.py`` precedent):

  1. Header-level filter list (``filter_headers``).
  2. Response-body field-value scrub for known long-lived secret slots.
  3. Heuristic regex scrub for 32+ hex / 24+ base64 token-shape runs.

Standalone recording scripts at ``scripts/record_pattern_labeler_cassettes.py``
+ ``scripts/record_codex_mcp_pattern_review_cassettes.py`` consume these
filters via direct import (NOT through ``@pytest.mark.vcr(record_mode=
'new_episodes')`` per post-Phase-12 lesson #3).
"""
from __future__ import annotations

import contextlib
import re
from typing import Any

# ============================================================================
# Shared token-shape patterns (mirrors `tests/conftest.py` Schwab precedent).
# ============================================================================

_TOKEN_HEX_PATTERN = re.compile(rb"\b[a-fA-F0-9]{32,}\b")
_TOKEN_B64_PATTERN = re.compile(rb"\b[A-Za-z0-9+/]{24,}={0,2}\b")
_HEX_URI_PATTERN = re.compile(r"\b[a-fA-F0-9]{32,}\b")
_BASE64_URI_PATTERN = re.compile(r"\b[A-Za-z0-9+/=]{40,}={0,2}\b")

# ============================================================================
# Field-value scrubs for known long-lived secret slots in JSON response bodies.
#
# pattern_labeler (Anthropic API): api_key, anthropic-version (sometimes
# echoes auth state); message.id, message.usage telemetry (not secret per se
# but operator-traceable; scrub for privacy).
#
# codex_mcp_pattern_review (OpenAI / Codex MCP): api_key, session_id, model
# invocation parameters, completion usage metrics.
# ============================================================================

_RESPONSE_FIELD_SCRUBBERS_CLAUDE: tuple[tuple[re.Pattern[bytes], bytes], ...] = (
    (
        re.compile(rb'("api_key"\s*:\s*)"[^"]+"'),
        rb'\1"<REDACTED>"',
    ),
    (
        re.compile(rb'("x-api-key"\s*:\s*)"[^"]+"'),
        rb'\1"<REDACTED>"',
    ),
    (
        re.compile(rb'("anthropic-version"\s*:\s*)"[^"]+"'),
        rb'\1"<REDACTED>"',
    ),
    (
        # Anthropic message ids are not strictly secret but operator-traceable.
        re.compile(rb'("id"\s*:\s*)"(msg_[^"]+)"'),
        rb'\1"<REDACTED_msg_id>"',
    ),
)

_RESPONSE_FIELD_SCRUBBERS_CODEX: tuple[tuple[re.Pattern[bytes], bytes], ...] = (
    (
        re.compile(rb'("api_key"\s*:\s*)"[^"]+"'),
        rb'\1"<REDACTED>"',
    ),
    (
        re.compile(rb'("session_id"\s*:\s*)"[^"]+"'),
        rb'\1"<REDACTED>"',
    ),
    (
        re.compile(rb'("authorization"\s*:\s*)"[^"]+"'),
        rb'\1"<REDACTED>"',
    ),
    (
        # OpenAI completion ids similar privacy posture.
        re.compile(rb'("id"\s*:\s*)"(chatcmpl-[^"]+)"'),
        rb'\1"<REDACTED_chatcmpl_id>"',
    ),
)


# ============================================================================
# Filter list constants (consumed by `vcr_config` + recording scripts).
# ============================================================================

FILTER_HEADERS_CLAUDE: tuple[str, ...] = (
    "authorization",
    "x-api-key",
    "anthropic-version",
    "anthropic-beta",
    "anthropic-dangerous-direct-browser-access",
    "cookie",
    "set-cookie",
)

FILTER_HEADERS_CODEX: tuple[str, ...] = (
    "authorization",
    "x-api-key",
    "openai-organization",
    "openai-project",
    "x-codex-session-id",
    "cookie",
    "set-cookie",
)

FILTER_QUERY_PARAMETERS_SHARED: tuple[str, ...] = (
    "api_key",
    "access_token",
    "session_id",
    "auth",
)


# ============================================================================
# Sanitization functions — VCR before_record_request + before_record_response.
# ============================================================================


def _scrub_response_body(
    response: dict[str, Any],
    field_scrubbers: tuple[tuple[re.Pattern[bytes], bytes], ...],
) -> dict[str, Any]:
    """Shared scrubber for ``before_record_response`` payloads.

    Mutates the response in-place + returns it. Applies known-field scrubs
    first (preserving JSON shape with ``<REDACTED>`` placeholder), then
    heuristic token-shape regex scrubs (32+ hex / 24+ base64).
    """
    body = response.get("body", {})
    raw = body.get("string") if isinstance(body, dict) else None
    if raw is None:
        return response
    if isinstance(raw, str):
        raw_bytes = raw.encode("utf-8", errors="replace")
        was_str = True
    elif isinstance(raw, (bytes, bytearray)):
        raw_bytes = bytes(raw)
        was_str = False
    else:
        return response

    for pattern, replacement in field_scrubbers:
        raw_bytes = pattern.sub(replacement, raw_bytes)
    raw_bytes = _TOKEN_HEX_PATTERN.sub(b"<REDACTED>", raw_bytes)
    raw_bytes = _TOKEN_B64_PATTERN.sub(b"<REDACTED>", raw_bytes)

    body["string"] = (
        raw_bytes.decode("utf-8", errors="replace") if was_str else raw_bytes
    )
    response["body"] = body
    return response


def redact_pattern_labeler_response(response: dict[str, Any]) -> dict[str, Any]:
    """``before_record_response`` for pattern_labeler cassettes.

    Anthropic API response body sanitization.
    """
    return _scrub_response_body(response, _RESPONSE_FIELD_SCRUBBERS_CLAUDE)


def redact_codex_mcp_response(response: dict[str, Any]) -> dict[str, Any]:
    """``before_record_response`` for codex_mcp_pattern_review cassettes.

    OpenAI / Codex MCP response body sanitization.
    """
    return _scrub_response_body(response, _RESPONSE_FIELD_SCRUBBERS_CODEX)


def _sanitize_request_uri(request: Any) -> Any:
    """Shared URI scrubber for ``before_record_request`` payloads.

    Removes token-shape substrings (32+ hex / 40+ base64) from
    ``request.uri``. Mutates the request in-place if possible + returns it
    per vcrpy contract.
    """
    uri = getattr(request, "uri", None) or ""
    if not uri:
        return request
    sanitized = _HEX_URI_PATTERN.sub("<hex-token>", uri)
    sanitized = _BASE64_URI_PATTERN.sub("<base64-token>", sanitized)
    if sanitized != uri:
        with contextlib.suppress(AttributeError):
            # vcrpy Request is mutable on supported versions; tolerate the
            # unlikely read-only shape by no-op + post-record sentinel audit.
            request.uri = sanitized
    return request


def sanitize_pattern_labeler_request(request: Any) -> Any:
    """``before_record_request`` for pattern_labeler cassettes."""
    return _sanitize_request_uri(request)


def sanitize_codex_mcp_request(request: Any) -> Any:
    """``before_record_request`` for codex_mcp_pattern_review cassettes."""
    return _sanitize_request_uri(request)


# ============================================================================
# VCR config builders (consumed by recording scripts + per-cassette fixtures).
# ============================================================================


def pattern_labeler_vcr_config() -> dict[str, Any]:
    """Per spec §A.10: pattern_labeler cassette VCR filter config.

    Returns a dict compatible with VCR.py's ``use_cassette(**config)``.
    """
    return {
        "filter_headers": list(FILTER_HEADERS_CLAUDE),
        "filter_query_parameters": list(FILTER_QUERY_PARAMETERS_SHARED),
        "filter_post_data_parameters": list(FILTER_QUERY_PARAMETERS_SHARED),
        "before_record_request": sanitize_pattern_labeler_request,
        "before_record_response": redact_pattern_labeler_response,
    }


def codex_mcp_vcr_config() -> dict[str, Any]:
    """Per spec §A.10: codex_mcp_pattern_review cassette VCR filter config."""
    return {
        "filter_headers": list(FILTER_HEADERS_CODEX),
        "filter_query_parameters": list(FILTER_QUERY_PARAMETERS_SHARED),
        "filter_post_data_parameters": list(FILTER_QUERY_PARAMETERS_SHARED),
        "before_record_request": sanitize_codex_mcp_request,
        "before_record_response": redact_codex_mcp_response,
    }


__all__ = [
    "FILTER_HEADERS_CLAUDE",
    "FILTER_HEADERS_CODEX",
    "FILTER_QUERY_PARAMETERS_SHARED",
    "codex_mcp_vcr_config",
    "pattern_labeler_vcr_config",
    "redact_codex_mcp_response",
    "redact_pattern_labeler_response",
    "sanitize_codex_mcp_request",
    "sanitize_pattern_labeler_request",
]
