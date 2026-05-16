"""Phase 12 Sub-sub-bundle C.D T-D.6.1 — `get_account_orders_audited` wrapper.

Per plan §E.6.1 (Codex R2 Major #2 fix + R4 Major #3 implementation-seam
explicit clause).

Tests cover:
  - Backward compat: existing ``get_account_orders`` shipped signature +
    return shape unchanged (return type is ``list[SchwabOrderResponse]``;
    no kwarg additions); audit row still written.
  - NEW ``get_account_orders_audited`` returns
    ``tuple[int, list[SchwabOrderResponse]]``; the int is the
    ``schwab_api_calls.call_id`` PK and a row exists at that id.
  - Shared helper ``_call_endpoint`` opt-in ``return_call_id`` kwarg:
    True branch returns ``(call_id, mapped)``; default-False branch
    returns ``mapped`` only.
  - Failure path: audited wrapper re-raises typed Schwab exceptions
    cleanly + closes the audit row via ``record_call_finish`` with
    ``status='error'`` / ``'auth_failed'`` / ``'rate_limited'``.

Race-free guarantee — T-D.6's ``BackfillPipelineActiveError`` rejects
backfill entry while pipeline runs; the audit-row INSERT inside
``_call_endpoint`` is the only writer for the call_id range used by
backfill iterations.
"""
from __future__ import annotations

import inspect
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab import client as schwab_client_module
from swing.integrations.schwab import trader as trader_module
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabAuthError,
    SchwabRateLimitError,
)
from swing.integrations.schwab.models import SchwabOrderResponse
from swing.integrations.schwab.trader import (
    _call_endpoint,
    get_account_orders,
    get_account_orders_audited,
)

# ============================================================================
# Fixtures (mirrors test_schwab_trader.py)
# ============================================================================


@pytest.fixture
def v18_conn(tmp_path: Path) -> sqlite3.Connection:
    """v18+ DB with foreign_keys=ON."""
    return ensure_schema(tmp_path / "schwab-trader-audited-test.db")


@pytest.fixture(autouse=True)
def reset_schwab_redaction_state():
    """Clear process-global redaction state between tests."""
    original_factory = logging.getLogRecordFactory()
    original_installed = schwab_client_module._FACTORY_INSTALLED
    original_orig = schwab_client_module._ORIGINAL_RECORD_FACTORY
    original_secrets = set(schwab_client_module._GLOBAL_KNOWN_SECRETS)

    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._FACTORY_INSTALLED = False
    schwab_client_module._ORIGINAL_RECORD_FACTORY = None
    logging.setLogRecordFactory(logging.LogRecord)

    yield

    logging.setLogRecordFactory(original_factory)
    schwab_client_module._FACTORY_INSTALLED = original_installed
    schwab_client_module._ORIGINAL_RECORD_FACTORY = original_orig
    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._GLOBAL_KNOWN_SECRETS.update(original_secrets)


def _mock_response(json_value, *, status_code: int = 200, headers=None):
    resp = MagicMock()
    resp.json.return_value = json_value
    resp.status_code = status_code
    resp.headers = headers or {}
    return resp


def _audit_row(conn: sqlite3.Connection, call_id: int) -> tuple:
    return conn.execute(
        "SELECT call_id, ts, endpoint, http_status, response_time_ms, "
        "rate_limit_remaining, signature_hash, status, error_message, "
        "surface, environment FROM schwab_api_calls WHERE call_id = ?",
        (call_id,),
    ).fetchone()


def _latest_call_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT call_id FROM schwab_api_calls ORDER BY call_id DESC LIMIT 1",
    ).fetchone()
    return row[0] if row else None


def _orders_payload():
    return [
        {
            "orderId": 7777,
            "status": "FILLED",
            "enteredTime": "2026-05-13T10:30:00Z",
            "orderType": "MARKET",
            "orderLegCollection": [
                {
                    "instruction": "BUY",
                    "quantity": 25,
                    "instrument": {"symbol": "CVGI"},
                },
            ],
        },
    ]


# ============================================================================
# Test 1 — `get_account_orders` signature byte-for-byte preserved
# ============================================================================


def test_get_account_orders_signature_unchanged():
    """BINDING backward-compat regression test (plan §E.6.1 acceptance #3).

    The shipped wrapper's parameter list + return annotation MUST match
    the pre-T-D.6.1 baseline. Existing callsites at
    ``swing/pipeline/runner.py`` + ``swing/trades/schwab_reconciliation.py``
    rely on this exact signature.
    """
    sig = inspect.signature(get_account_orders)
    params = list(sig.parameters)
    assert params == [
        "client",
        "conn",
        "account_hash",
        "from_entered_time",
        "to_entered_time",
        "surface",
        "environment",
        "pipeline_run_id",
        "status",
        "max_results",
    ]
    # Return annotation textually pins list[SchwabOrderResponse].
    assert "list" in str(sig.return_annotation)
    assert "SchwabOrderResponse" in str(sig.return_annotation)
    # No new kwargs leaked from refactor.
    assert "return_call_id" not in params


# ============================================================================
# Test 2 — Backward-compat: `get_account_orders` returns list only
# ============================================================================


def test_get_account_orders_returns_list_with_audit_row(v18_conn):
    """Existing wrapper continues to return `list[SchwabOrderResponse]`
    (NOT a tuple) and the audit row is still written with status='success'.
    """
    client = MagicMock()
    client.account_orders.return_value = _mock_response(_orders_payload())

    orders = get_account_orders(
        client, v18_conn,
        account_hash="abc...64charhash",
        from_entered_time=datetime(2026, 5, 7, tzinfo=UTC),
        to_entered_time=datetime(2026, 5, 14, tzinfo=UTC),
        surface="cli", environment="production",
    )

    # Not a tuple — must be list of SchwabOrderResponse.
    assert isinstance(orders, list)
    assert len(orders) == 1
    assert isinstance(orders[0], SchwabOrderResponse)

    # Audit row preserved.
    call_id = _latest_call_id(v18_conn)
    assert call_id is not None
    row = _audit_row(v18_conn, call_id)
    assert row[2] == "accounts.orders.list"
    assert row[7] == "success"


# ============================================================================
# Test 3 — New audited wrapper returns (call_id, orders) tuple
# ============================================================================


def test_get_account_orders_audited_returns_tuple_with_call_id(v18_conn):
    """Plan §E.6.1 acceptance #1 + #5 first bullet.

    Returns ``tuple[int, list[SchwabOrderResponse]]`` where the int is the
    persisted ``schwab_api_calls.call_id`` PK.
    """
    client = MagicMock()
    client.account_orders.return_value = _mock_response(_orders_payload())

    result = get_account_orders_audited(
        client, v18_conn,
        account_hash="abc...64charhash",
        from_entered_time=datetime(2026, 5, 7, tzinfo=UTC),
        to_entered_time=datetime(2026, 5, 14, tzinfo=UTC),
        surface="cli", environment="production",
    )

    assert isinstance(result, tuple)
    assert len(result) == 2
    call_id, orders = result
    assert isinstance(call_id, int)
    assert isinstance(orders, list)
    assert len(orders) == 1
    assert isinstance(orders[0], SchwabOrderResponse)

    # The returned call_id MUST correspond to a real audit row.
    row = _audit_row(v18_conn, call_id)
    assert row is not None
    assert row[0] == call_id
    assert row[2] == "accounts.orders.list"
    assert row[7] == "success"

    # And it's the most recent audit row (no race; only writer in test).
    assert _latest_call_id(v18_conn) == call_id


def test_get_account_orders_audited_empty_response(v18_conn):
    """Empty list is a valid happy path; tuple shape still observed."""
    client = MagicMock()
    client.account_orders.return_value = _mock_response([])

    call_id, orders = get_account_orders_audited(
        client, v18_conn,
        account_hash="abc...64charhash",
        from_entered_time="2026-05-07T00:00:00.000Z",
        to_entered_time="2026-05-14T00:00:00.000Z",
        surface="cli", environment="production",
    )
    assert isinstance(call_id, int)
    assert orders == []
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "success"


# ============================================================================
# Test 4 — Shared helper opt-in return_call_id branches
# ============================================================================


def test_call_endpoint_return_call_id_true_returns_tuple(v18_conn):
    """Plan §E.6.1 acceptance #2 — opt-in kwarg returns tuple branch."""
    client = MagicMock()
    response = _mock_response([])

    result = _call_endpoint(
        client_method=lambda: response,
        endpoint="accounts.orders.list",
        conn=v18_conn,
        surface="cli",
        environment="production",
        pipeline_run_id=None,
        mapper=lambda payload: [],  # passthrough; mirrors orders mapper for []
        client=client,
        return_call_id=True,
    )

    assert isinstance(result, tuple)
    assert len(result) == 2
    call_id, mapped = result
    assert isinstance(call_id, int)
    assert mapped == []
    assert _audit_row(v18_conn, call_id) is not None


def test_call_endpoint_return_call_id_default_returns_mapped_only(v18_conn):
    """Plan §E.6.1 acceptance #2 — default-False preserves existing signature."""
    client = MagicMock()
    response = _mock_response([])

    result = _call_endpoint(
        client_method=lambda: response,
        endpoint="accounts.orders.list",
        conn=v18_conn,
        surface="cli",
        environment="production",
        pipeline_run_id=None,
        mapper=lambda payload: [],
        client=client,
        # return_call_id NOT supplied — must default to False.
    )

    assert result == []
    # Audit row is still written.
    assert _latest_call_id(v18_conn) is not None


def test_call_endpoint_signature_has_return_call_id_default_false():
    """Discriminating: `return_call_id` MUST be a keyword-only kwarg with
    default False (preserves backward-compat at the helper level).
    """
    sig = inspect.signature(_call_endpoint)
    assert "return_call_id" in sig.parameters
    param = sig.parameters["return_call_id"]
    assert param.default is False
    # Keyword-only (mirrors all other helper params).
    assert param.kind == inspect.Parameter.KEYWORD_ONLY


# ============================================================================
# Test 5 — Failure path: audited wrapper closes audit row + re-raises
# ============================================================================


def test_get_account_orders_audited_http_401_audit_auth_failed(v18_conn):
    """HTTP 401 on audited wrapper raises SchwabAuthError AND records
    `status='auth_failed'` on the audit row (per existing Sub-bundle B
    typed-error audit-close discipline gotcha).
    """
    client = MagicMock()
    client.account_orders.return_value = _mock_response(
        {"error": "unauthorized"}, status_code=401,
    )

    with pytest.raises(SchwabAuthError):
        get_account_orders_audited(
            client, v18_conn,
            account_hash="abc...64charhash",
            from_entered_time="2026-05-07T00:00:00.000Z",
            to_entered_time="2026-05-14T00:00:00.000Z",
            surface="cli", environment="production",
        )

    call_id = _latest_call_id(v18_conn)
    assert call_id is not None
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "auth_failed"
    assert row[3] == 401  # http_status


def test_get_account_orders_audited_http_429_audit_rate_limited(v18_conn):
    """HTTP 429 path closes the audit row with `status='rate_limited'`."""
    client = MagicMock()
    client.account_orders.return_value = _mock_response(
        {"error": "rate limited"}, status_code=429,
    )

    with pytest.raises(SchwabRateLimitError):
        get_account_orders_audited(
            client, v18_conn,
            account_hash="abc...64charhash",
            from_entered_time="2026-05-07T00:00:00.000Z",
            to_entered_time="2026-05-14T00:00:00.000Z",
            surface="cli", environment="production",
        )

    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "rate_limited"
    assert row[3] == 429


def test_get_account_orders_audited_schwabdev_raises_typed_error_closes_audit(
    v18_conn,
):
    """If schwabdev itself raises a typed SchwabApiError (e.g. transport
    failure), the audited wrapper MUST close the audit row before
    propagating (Sub-bundle B R1 M#3 / Typed audit-row close gotcha).
    """
    client = MagicMock()
    client.account_orders.side_effect = SchwabApiError(0, "<transport-fail>")

    with pytest.raises(SchwabApiError):
        get_account_orders_audited(
            client, v18_conn,
            account_hash="abc...64charhash",
            from_entered_time="2026-05-07T00:00:00.000Z",
            to_entered_time="2026-05-14T00:00:00.000Z",
            surface="cli", environment="production",
        )

    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "error"


# ============================================================================
# Test 6 — Audited wrapper exported in __all__ for clean import surface
# ============================================================================


def test_get_account_orders_audited_in_module_all_export():
    """The new wrapper SHOULD be in trader.__all__ so external consumers
    (backfill at T-D.8) get a clean ``from swing.integrations.schwab.trader
    import get_account_orders_audited`` import without bypassing __all__.
    """
    assert "get_account_orders_audited" in trader_module.__all__
