"""Schwab API arc-closer Sub-bundle D Task T-D.5 — degraded-banner unit tests.

Plan §Tasks-D T-D.5 + dispatch brief §0.9 + §5.2 T-D.5 row + spec §3.4.4 + §7.2:

Conditional banner emitted by `render_briefing_md(vm)` when the most-recent
`schwab_api_calls` row's `status != 'success'`. Banner copy (verbatim per
spec §7.2 wording):

  > **Schwab integration: degraded** — most recent API call to `<endpoint>`
  > did not succeed. Run `swing schwab status` to diagnose.

Six discriminating tests:

  1. Banner present when most-recent call is `status='error'`.
  2. Banner ABSENT when zero `schwab_api_calls` rows yet (false-positive
     guard per dispatch brief §5.2 T-D.5 pre-emption — predicate MUST NOT
     fire on zero-rows-yet state).
  3. Banner ABSENT when most-recent call is `status='success'`.
  4. Banner survives multiple rows when latest is failure (latest wins).
  5. Banner cites the endpoint name of the failing call.
  6. Banner is generic — no token bytes; no `error_message` body content
     (operator runs `swing schwab status` for details).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.schwab_api_calls import insert_in_flight, update_call_outcome
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model
from swing.rendering.briefing_md import render_briefing_md


# Banner-copy literals — single source of truth per spec §3.4.4 / §7.2.
BANNER_TITLE_SUBSTRING = "Schwab integration: degraded"
BANNER_CTA_SUBSTRING = "swing schwab status"


def _bootstrap_db(tmp_path: Path) -> sqlite3.Connection:
    """Create an isolated SQLite DB at v18 schema."""
    db_path = tmp_path / "swing.db"
    return ensure_schema(db_path)


def _plant_call(
    conn: sqlite3.Connection,
    *,
    ts: str,
    endpoint: str,
    status: str,
    error_message: str | None = None,
) -> int:
    """Insert one schwab_api_calls row with terminal status (no in-flight tail)."""
    call_id = insert_in_flight(
        conn,
        ts=ts,
        endpoint=endpoint,
        pipeline_run_id=None,
        surface="cli",
        environment="production",
    )
    update_call_outcome(
        conn,
        call_id=call_id,
        http_status=200 if status == "success" else 500,
        response_time_ms=100,
        rate_limit_remaining=None,
        signature_hash=None,
        status=status,
        error_message=error_message,
    )
    conn.commit()
    return call_id


def _minimal_inputs(*, schwab_degraded_endpoint: str | None = None) -> BriefingInputs:
    """Build the minimum BriefingInputs that renders cleanly. Most domain
    fields are empty so the banner predicate is the only behavior under test.
    """
    return BriefingInputs(
        action_session_date="2026-05-14",
        data_asof_date="2026-05-13",
        generated_at="2026-05-14T08:00:00",
        weather=None,
        weather_is_stale=True,
        equity=2000.0,
        open_count=0,
        soft_warn=4,
        hard_cap=6,
        last_pipeline_ts="2026-05-14T08:00:00",
        pipeline_is_stale=False,
        current_session_match=True,
        recommendations=[],
        open_trades=[],
        schwab_degraded_endpoint=schwab_degraded_endpoint,
    )


def _render_with_predicate(conn: sqlite3.Connection) -> str:
    """Apply the same predicate the production composition surface
    (`_step_export`) uses — invoke `is_schwab_degraded`, propagate the
    endpoint name (or None) into BriefingInputs, build VM, render md.
    """
    from swing.data.repos.schwab_api_calls import is_schwab_degraded

    degraded, endpoint = is_schwab_degraded(conn)
    inputs = _minimal_inputs(
        schwab_degraded_endpoint=(endpoint if degraded else None),
    )
    vm = build_briefing_view_model(inputs)
    return render_briefing_md(vm)


# ============================================================================
# Test 1 — Banner PRESENT when most-recent call status='error'.
# ============================================================================

def test_banner_present_when_most_recent_call_status_error(
    tmp_path: Path,
) -> None:
    conn = _bootstrap_db(tmp_path)
    try:
        _plant_call(
            conn,
            ts="2026-05-14T07:00:00",
            endpoint="accounts.details",
            status="error",
            error_message="upstream 500",
        )
        md = _render_with_predicate(conn)
        assert BANNER_TITLE_SUBSTRING in md
        assert BANNER_CTA_SUBSTRING in md
        assert "accounts.details" in md
    finally:
        conn.close()


# ============================================================================
# Test 2 — Banner ABSENT when zero rows yet (false-positive guard per §5.2).
# ============================================================================

def test_banner_absent_when_no_schwab_api_calls_rows_yet(
    tmp_path: Path,
) -> None:
    conn = _bootstrap_db(tmp_path)
    try:
        # Sanity: zero rows planted.
        n = conn.execute("SELECT COUNT(*) FROM schwab_api_calls").fetchone()[0]
        assert n == 0
        md = _render_with_predicate(conn)
        assert BANNER_TITLE_SUBSTRING not in md
    finally:
        conn.close()


# ============================================================================
# Test 3 — Banner ABSENT when most-recent call status='success'.
# ============================================================================

def test_banner_absent_when_most_recent_call_status_success(
    tmp_path: Path,
) -> None:
    conn = _bootstrap_db(tmp_path)
    try:
        _plant_call(
            conn,
            ts="2026-05-14T07:00:00",
            endpoint="accounts.details",
            status="success",
        )
        md = _render_with_predicate(conn)
        assert BANNER_TITLE_SUBSTRING not in md
    finally:
        conn.close()


# ============================================================================
# Test 4 — Banner survives 3-row history when latest is failure (latest wins).
# ============================================================================

def test_banner_survives_multiple_pipeline_runs_when_recent_failure_persists(
    tmp_path: Path,
) -> None:
    conn = _bootstrap_db(tmp_path)
    try:
        _plant_call(
            conn,
            ts="2026-05-14T05:00:00",
            endpoint="accounts.details",
            status="success",
        )
        _plant_call(
            conn,
            ts="2026-05-14T06:00:00",
            endpoint="accounts.details",
            status="success",
        )
        _plant_call(
            conn,
            ts="2026-05-14T07:00:00",
            endpoint="marketdata.quotes",
            status="error",
            error_message="rate limit",
        )
        md = _render_with_predicate(conn)
        assert BANNER_TITLE_SUBSTRING in md
        # Latest endpoint wins.
        assert "marketdata.quotes" in md
    finally:
        conn.close()


# ============================================================================
# Test 5 — Banner specifies endpoint name of the failing call.
# ============================================================================

def test_banner_specifies_endpoint_name(tmp_path: Path) -> None:
    conn = _bootstrap_db(tmp_path)
    try:
        _plant_call(
            conn,
            ts="2026-05-14T07:00:00",
            endpoint="marketdata.quotes",
            status="error",
        )
        md = _render_with_predicate(conn)
        assert BANNER_TITLE_SUBSTRING in md
        assert "marketdata.quotes" in md
    finally:
        conn.close()


# ============================================================================
# Test 6 — Banner is generic — no token bytes, no error_message body.
# ============================================================================

def test_banner_is_generic_no_token_bytes_no_error_message_body(
    tmp_path: Path,
) -> None:
    conn = _bootstrap_db(tmp_path)
    try:
        sentinel_token_substring = "ACCESS_TOKEN_BYTES_xyz"
        sentinel_error_body = (
            f"upstream returned: {sentinel_token_substring} bearer-leak text"
        )
        _plant_call(
            conn,
            ts="2026-05-14T07:00:00",
            endpoint="accounts.details",
            status="error",
            error_message=sentinel_error_body,
        )
        md = _render_with_predicate(conn)
        assert BANNER_TITLE_SUBSTRING in md
        # CRITICAL: banner copy must NOT echo error_message body content.
        assert sentinel_token_substring not in md
        assert "bearer-leak" not in md
    finally:
        conn.close()
