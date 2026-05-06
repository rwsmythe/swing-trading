"""End-to-end token-leak audit.

Runs the full happy-path + error-path fetch cycle with a SENTINEL token, then
greps every captured log record + every persisted DB row + every committed
cassette file for the sentinel literal. Test fails if found anywhere.

This is a defense-in-depth invariant test; runs in fast suite. The cassette
sweep covers the ENTIRE tests/integrations/cassettes/ directory tree.
"""
from __future__ import annotations

import io
import logging
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from swing.config import FinvizIntegrationConfig
from swing.data.db import ensure_schema
from swing.data.repos.finviz_api_calls import list_recent_calls
from swing.integrations.finviz_api import (
    FinvizApiError,
    FinvizClient,
    FinvizConfigMissingError,
)

_SENTINEL = "TOK-SENTINEL-DO-NOT-LEAK-9f8e7d6c5b4a"


def _client_with_sentinel():
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Stub:
        finviz: FinvizIntegrationConfig

    @dataclass(frozen=True)
    class _Cfg:
        integrations: _Stub

    return FinvizClient(_Cfg(  # type: ignore[arg-type]
        integrations=_Stub(finviz=FinvizIntegrationConfig(
            token=_SENTINEL, screen_query="v=152", timeout_seconds=5,
        )),
    ))


def test_sentinel_token_absent_from_logs_on_error_path(caplog) -> None:
    """Discriminating: a network error caught + logged MUST NOT include the token literal."""
    import requests
    with patch(
        "swing.integrations.finviz_api.requests.get",
        side_effect=requests.ConnectionError(f"some-error-mentioning-{_SENTINEL}"),
    ):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(FinvizApiError):
                _client_with_sentinel().fetch_screen()
    full_log = "\n".join(r.getMessage() for r in caplog.records)
    assert _SENTINEL not in full_log


def test_sentinel_token_absent_from_db_row_on_error_path(tmp_path: Path) -> None:
    """Discriminating: pipeline step records error_message; sentinel must NOT appear."""
    from datetime import datetime
    from swing.data.models import FinvizApiCall
    from swing.data.repos.finviz_api_calls import insert_call
    from swing.integrations.finviz_api import FinvizApiError

    conn = ensure_schema(tmp_path / "swing.db")
    try:
        try:
            raise FinvizApiError(0, f"some body containing {_SENTINEL}")
        except FinvizApiError as exc:
            insert_call(conn, FinvizApiCall(
                call_id=None,
                ts=datetime.now().isoformat(timespec="seconds"),
                screen_query="v=152",
                status="error", row_count=None, response_time_ms=None,
                rate_limit_remaining=None, signature_hash=None,
                error_message=f"{type(exc).__name__}: {exc}",
            ))
        rows = list_recent_calls(conn)
        assert _SENTINEL not in (rows[0].error_message or "")
        assert "FinvizApiError" in (rows[0].error_message or "")
    finally:
        conn.close()


def test_sentinel_token_absent_from_urllib3_debug_logs(caplog) -> None:
    """Codex R1 Major-2 fix: even with `urllib3.connectionpool` set to DEBUG,
    the sentinel token must NOT appear in captured log records.
    """
    import requests

    logging.getLogger("urllib3.connectionpool").setLevel(logging.DEBUG)
    logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.DEBUG)

    captured_urls: list[str] = []

    def _fake_get(url, *a, **kw):
        captured_urls.append(url)
        raise requests.ConnectionError("simulated network failure")

    with patch("swing.integrations.finviz_api.requests.get", _fake_get):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(FinvizApiError):
                _client_with_sentinel().fetch_screen()

    assert captured_urls, "test setup error: requests.get not invoked"
    assert _SENTINEL in captured_urls[0], (
        "test setup error: client did not actually pass token to URL "
        "(can't validate redaction)"
    )

    full_log = "\n".join(
        f"{r.name}: {r.getMessage()}" for r in caplog.records
    )
    assert _SENTINEL not in full_log, (
        f"Token sentinel leaked into log records:\n{full_log[:1000]}"
    )


def test_sentinel_token_absent_from_committed_cassettes() -> None:
    """Cassette sweep: NO committed cassette file may contain the project's
    test-sentinel-token (the recording-time token used in cassette recordings).
    """
    cassette_root = Path("tests/integrations/cassettes")
    if not cassette_root.exists():
        pytest.skip("No cassettes recorded yet (Tasks 3+4 not run)")
    leaks: list[str] = []
    for f in cassette_root.rglob("*.yaml"):
        text = f.read_text(errors="replace")
        if "test-sentinel-token" in text:
            leaks.append(str(f))
    assert not leaks, f"Token leaked into cassettes: {leaks}"
