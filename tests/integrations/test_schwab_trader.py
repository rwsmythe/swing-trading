"""Phase 11 T-B.1 — Schwab Trader API endpoint wrappers + mappers.

Per plan §E.2 + §H.4 + §B.1 file map + T-B.0.b recon doc §3 + §5.

Tests cover:
  - One happy-path test per endpoint (4 wrappers × `accounts.linked` /
    `accounts.details` / `accounts.orders.list` / `accounts.transactions.list`).
  - Sub-bundle A M#1 family — silent-failure post-call validation
    (each wrapper rejects response shapes where the schwabdev call returned
    a success-looking Response but the payload diverges from expected).
  - Sub-bundle A M#2 family — `ensure_schwab_log_redaction_factory_installed()`
    is invoked BEFORE every schwabdev call (factory-replacement defense).
  - Sub-bundle A M#3 family — audit-success-fire ordering: `status='success'`
    fires ONLY after ALL validation passes; pre-success rejection paths
    fire `status='auth_failed'`/`'rate_limited'`/`'error'`.
  - HTTP failure mapping: 401 → SchwabAuthError + audit `auth_failed`;
    429 → SchwabRateLimitError + audit `rate_limited`; 500 → SchwabApiError
    + audit `error`.
  - Datetime ISO formatting (`_schwab_iso` helper).
  - Empty-list happy path (orders / transactions with no rows in period).
  - Mapper shape errors raise `SchwabSchemaParityError` AND record audit
    `status='error'` with `signature_hash` populated (request shape was
    valid; mapper rejected payload).

The tests use SYNTHETIC fixtures (not cassettes) per T-B.0.b §4 — live-
cassette recording is deferred to phase 2 post-T-B.1 ship per dispatch
brief §2.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab import client as schwab_client_module
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabAuthError,
    SchwabRateLimitError,
    SchwabSchemaParityError,
)
from swing.integrations.schwab.models import (
    SchwabAccountResponse,
    SchwabOrderResponse,
    SchwabTransactionResponse,
)
from swing.integrations.schwab.trader import (
    TRANSACTION_TYPES_ALL,
    _schwab_iso,
    get_account_details,
    get_account_orders,
    get_account_transactions,
    get_accounts_linked,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def v18_conn(tmp_path: Path) -> sqlite3.Connection:
    """v18 DB with foreign_keys=ON."""
    return ensure_schema(tmp_path / "schwab-trader-test.db")


@pytest.fixture(autouse=True)
def reset_schwab_redaction_state():
    """Per T-A.10 fixture pattern — clear process-global redaction state
    between tests so prior tests' registrations cannot mask current-test
    bugs.
    """
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
    """Build a Response-like MagicMock returning the supplied json + status."""
    resp = MagicMock()
    resp.json.return_value = json_value
    resp.status_code = status_code
    resp.headers = headers or {}
    return resp


def _audit_row(conn: sqlite3.Connection, call_id: int) -> tuple:
    """Fetch the persisted audit row by call_id."""
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


# ============================================================================
# Tests 1-4 — Happy paths per endpoint
# ============================================================================


def test_01_get_accounts_linked_happy_path(v18_conn):
    """Map list of {accountNumber, hashValue} dicts → list of hashValues."""
    client = MagicMock()
    client.linked_accounts.return_value = _mock_response(
        [
            {"accountNumber": "12345678", "hashValue": "abc...64charhash"},
        ],
    )

    hashes = get_accounts_linked(
        client, v18_conn,
        surface="cli", environment="production",
    )
    assert hashes == ["abc...64charhash"]

    # Audit row written + status='success' + signature_hash populated.
    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[2] == "accounts.linked"
    assert row[7] == "success"
    assert row[6] is not None and len(row[6]) == 64  # signature_hash
    assert row[3] == 200  # http_status


def test_02_get_account_details_happy_path(v18_conn):
    """Map nested securitiesAccount.currentBalances.liquidationValue → NLV."""
    client = MagicMock()
    client.account_details.return_value = _mock_response({
        "securitiesAccount": {
            "currentBalances": {
                "liquidationValue": 2014.36,
                "cashBalance": 100.0,
                "buyingPower": 4000.0,
            },
            "positions": [
                {"instrument": {"symbol": "AAPL"}, "longQuantity": 10},
            ],
        },
    })

    resp = get_account_details(
        client, v18_conn,
        account_hash="abc...64charhash",
        surface="pipeline", environment="production",
        pipeline_run_id=None,
    )
    assert isinstance(resp, SchwabAccountResponse)
    assert resp.net_liquidating_value == 2014.36
    assert resp.cash == 100.0
    assert resp.buying_power == 4000.0
    assert len(resp.positions) == 1
    # Verify the schwabdev call was made with fields='positions'.
    client.account_details.assert_called_once_with(
        "abc...64charhash", fields="positions",
    )


def test_03_get_account_orders_happy_path(v18_conn):
    """Empty list is a valid happy path (no orders in period)."""
    client = MagicMock()
    client.account_orders.return_value = _mock_response([])

    orders = get_account_orders(
        client, v18_conn,
        account_hash="abc...64charhash",
        from_entered_time=datetime(2026, 5, 7, tzinfo=UTC),
        to_entered_time=datetime(2026, 5, 14, tzinfo=UTC),
        surface="cli", environment="production",
    )
    assert orders == []
    # Verify ISO format was passed in.
    args, kwargs = client.account_orders.call_args
    assert args[0] == "abc...64charhash"
    assert args[1] == "2026-05-07T00:00:00.000Z"
    assert args[2] == "2026-05-14T00:00:00.000Z"
    assert kwargs.get("status") is None


def test_04_get_account_orders_populated_response(v18_conn):
    """Single order with full leg structure maps cleanly."""
    client = MagicMock()
    client.account_orders.return_value = _mock_response([
        {
            "orderId": 1001,
            "status": "FILLED",
            "enteredTime": "2026-05-10T10:30:00Z",
            "orderType": "MARKET",
            "orderLegCollection": [
                {
                    "instruction": "BUY",
                    "quantity": 50,
                    "instrument": {"symbol": "AAPL"},
                },
            ],
        },
    ])

    orders = get_account_orders(
        client, v18_conn,
        account_hash="abc...64charhash",
        from_entered_time="2026-05-07T00:00:00.000Z",
        to_entered_time="2026-05-14T00:00:00.000Z",
        surface="cli", environment="production",
    )
    assert len(orders) == 1
    o = orders[0]
    assert isinstance(o, SchwabOrderResponse)
    assert o.order_id == "1001"
    assert o.status == "FILLED"
    assert o.instruction == "BUY"
    assert o.quantity == 50.0
    assert o.instrument_symbol == "AAPL"


def test_05_get_account_transactions_happy_path(v18_conn):
    """Transactions list maps + audit success."""
    client = MagicMock()
    client.transactions.return_value = _mock_response([
        {
            "transactionId": "T123",
            "transactionDate": "2026-05-12T15:00:00Z",
            "type": "ACH_RECEIPT",
            "netAmount": 500.0,
            "description": "ACH deposit",
        },
    ])

    txs = get_account_transactions(
        client, v18_conn,
        account_hash="abc...64charhash",
        start_date="2026-05-07T00:00:00.000Z",
        end_date="2026-05-14T00:00:00.000Z",
        surface="cli", environment="production",
    )
    assert len(txs) == 1
    t = txs[0]
    assert isinstance(t, SchwabTransactionResponse)
    assert t.transaction_id == "T123"
    assert t.type == "ACH_RECEIPT"
    assert t.net_amount == 500.0
    # Verify default types arg = full list.
    args, kwargs = client.transactions.call_args
    assert args[3] == TRANSACTION_TYPES_ALL


# ============================================================================
# Tests 6-7 — M#1 family: silent-failure post-call validation
# ============================================================================


def test_06_accounts_linked_empty_list_audit_fails_not_success(v18_conn):
    """`auth.py D2` reaffirmation — empty list means auth failure.

    Sub-bundle A M#3 family: validate response content BEFORE firing the
    success audit. Empty list MUST raise + record `status='error'` (NOT
    success-then-error which silently logs a successful call).
    """
    client = MagicMock()
    client.linked_accounts.return_value = _mock_response([])

    with pytest.raises(SchwabSchemaParityError):
        get_accounts_linked(
            client, v18_conn,
            surface="cli", environment="production",
        )

    call_id = _latest_call_id(v18_conn)
    assert call_id is not None
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "error"  # NOT 'success'


def test_07_accounts_details_missing_balances_audit_fails(v18_conn):
    """Mapper rejection on missing liquidationValue/equity raises + audit error.

    Discriminating: pre-fix M#3 ordering would fire `status='success'`
    on the call_id, then raise in the mapper without rolling back. Post-fix:
    `record_call_finish(status='success', ...)` is gated on mapper success.
    """
    client = MagicMock()
    client.account_details.return_value = _mock_response({
        "securitiesAccount": {},  # missing currentBalances + aggregateBalance
    })

    with pytest.raises(SchwabSchemaParityError):
        get_account_details(
            client, v18_conn,
            account_hash="abc...64charhash",
            surface="pipeline", environment="production",
        )
    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "error"  # success was never fired


# ============================================================================
# Tests 8-10 — HTTP failure mapping
# ============================================================================


def test_08_http_401_maps_to_auth_error_and_audit_auth_failed(v18_conn):
    """401 → SchwabAuthError + audit `auth_failed`. Closes M#1 family."""
    client = MagicMock()
    client.account_details.return_value = _mock_response(
        {"errors": [{"message": "Unauthorized"}]},
        status_code=401,
    )

    with pytest.raises(SchwabAuthError) as exc_info:
        get_account_details(
            client, v18_conn,
            account_hash="abc...64charhash",
            surface="pipeline", environment="production",
        )
    assert exc_info.value.status_code == 401
    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "auth_failed"
    assert row[3] == 401  # http_status preserved on audit row
    # error_message is redacted but non-empty.
    assert row[8] is not None and len(row[8]) > 0


def test_09_http_429_maps_to_rate_limit_error_and_audit_rate_limited(v18_conn):
    """429 → SchwabRateLimitError + audit `rate_limited` + rate_limit_remaining."""
    client = MagicMock()
    client.account_orders.return_value = _mock_response(
        {"error": "Too many requests"},
        status_code=429,
        headers={"X-RateLimit-Remaining": "0"},
    )

    with pytest.raises(SchwabRateLimitError):
        get_account_orders(
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
    assert row[5] == 0  # rate_limit_remaining


def test_10_http_500_maps_to_api_error_and_audit_error(v18_conn):
    """500 → SchwabApiError + audit `error`."""
    client = MagicMock()
    client.transactions.return_value = _mock_response(
        "Internal Server Error",
        status_code=500,
    )

    with pytest.raises(SchwabApiError):
        get_account_transactions(
            client, v18_conn,
            account_hash="abc...64charhash",
            start_date="2026-05-07T00:00:00.000Z",
            end_date="2026-05-14T00:00:00.000Z",
            surface="cli", environment="production",
        )
    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "error"
    assert row[3] == 500


# ============================================================================
# Test 11 — M#2 family: factory-replacement defense
# ============================================================================


def test_11_ensure_factory_called_before_each_schwabdev_invocation(
    v18_conn, monkeypatch,
):
    """Sub-bundle A M#2 family — `ensure_schwab_log_redaction_factory_installed()`
    MUST be invoked BEFORE every schwabdev call.

    Discriminating: install a NO-OP third-party factory between two
    successive trader calls; assert that the second call re-installs our
    wrapper around it (ensure_* runs before the schwabdev call). Without
    the ensure_* call, a previously-replaced factory would silently leave
    the Layer-2 redactor disabled for subsequent calls.
    """
    client = MagicMock()
    client.linked_accounts.return_value = _mock_response([
        {"accountNumber": "12345678", "hashValue": "abc...hash"},
    ])

    # First call — installs the factory via ensure_*.
    get_accounts_linked(
        client, v18_conn,
        surface="cli", environment="production",
    )
    factory_after_first = logging.getLogRecordFactory()
    assert factory_after_first is schwab_client_module._schwab_record_factory

    # Third party replaces the factory.
    def third_party_factory(*args, **kwargs):
        return logging.LogRecord(*args, **kwargs)

    logging.setLogRecordFactory(third_party_factory)
    assert logging.getLogRecordFactory() is not schwab_client_module._schwab_record_factory

    # Second trader call — ensure_* MUST re-wrap.
    get_accounts_linked(
        client, v18_conn,
        surface="cli", environment="production",
    )
    factory_after_second = logging.getLogRecordFactory()
    assert factory_after_second is schwab_client_module._schwab_record_factory


# ============================================================================
# Tests 12-13 — Datetime ISO formatting helper
# ============================================================================


def test_12_schwab_iso_normalizes_datetime_to_millisecond_z_format():
    """`_schwab_iso` produces `yyyy-MM-dd'T'HH:mm:ss.SSSZ` shape."""
    dt = datetime(2026, 5, 14, 13, 30, 45, 123456, tzinfo=UTC)
    s = _schwab_iso(dt)
    # microseconds 123456 → milliseconds 123.
    assert s == "2026-05-14T13:30:45.123Z"


def test_13_schwab_iso_passes_through_pre_formatted_strings():
    """Pre-formatted string passes through unchanged."""
    assert _schwab_iso("2026-05-07T00:00:00.000Z") == "2026-05-07T00:00:00.000Z"
    assert _schwab_iso("anything-the-caller-handed-in") == "anything-the-caller-handed-in"


# ============================================================================
# Test 14 — schwabdev exception surfaces as SchwabApiError + audit `error`
# ============================================================================


def test_14_schwabdev_raises_unexpected_exception_audit_records_error(v18_conn):
    """schwabdev itself raising (e.g., network failure) → audit `error` + SchwabApiError."""
    client = MagicMock()
    client.account_details.side_effect = ConnectionError("network down")

    with pytest.raises(SchwabApiError):
        get_account_details(
            client, v18_conn,
            account_hash="abc...64charhash",
            surface="pipeline", environment="production",
        )
    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "error"
    assert row[3] is None  # http_status absent
    # error_message includes class name + redacted message.
    assert "ConnectionError" in (row[8] or "")


# ============================================================================
# Test 15 — Surface validation
# ============================================================================


def test_15_invalid_surface_raises_api_error(v18_conn):
    """Surface MUST be in the canonical _SCHWAB_API_SURFACE_VALUES tuple;
    defensive guard at wrapper entry. Post-Phase-13 hotfix the allowed set
    is ('pipeline','cli','trade_entry','trade_exit') — 'bogus' still rejected.
    """
    client = MagicMock()
    with pytest.raises(SchwabApiError):
        get_accounts_linked(
            client, v18_conn,
            surface="bogus", environment="production",  # invalid surface
        )


# ============================================================================
# Tests 19 + 20 — Phase 13 hotfix (2026-05-20 post-T3.SB2 merge):
# ``_call_endpoint`` Python-side surface guard MUST mirror the canonical
# ``audit_service._SCHWAB_API_SURFACE_VALUES`` 4-tuple (and therefore the v20
# schema CHECK widening at T-A.1.1) — otherwise T3.SB1 entry auto-fill +
# T3.SB2 exit auto-fill paths silently short-circuit in production
# (SchwabApiError raised BEFORE record_call_start so no audit row written).
#
# Pre-fix arithmetic (line 527 pre-hotfix):
#   ``if "trade_entry" not in ("pipeline", "cli")`` → True → raises
#   ``SchwabApiError(0, "_call_endpoint: surface must be 'pipeline'|'cli';
#   got 'trade_entry'")`` → test FAILS on uncaught SchwabApiError.
#
# Post-fix arithmetic (line 527 post-hotfix):
#   ``if "trade_entry" not in audit_service._SCHWAB_API_SURFACE_VALUES``
#   (= ('pipeline','cli','trade_entry','trade_exit')) → False → proceeds →
#   ``record_call_start`` fires → mock client returns empty list → mapper
#   succeeds → ``record_call_finish(status='success')`` → audit row written
#   with ``surface='trade_entry'``.
#
# Discriminating: pre-fix tests fail with uncaught exception; post-fix audit
# row has the expected surface value. Per CLAUDE.md gotcha "Schema-coverage
# Python constant is NOT necessarily the manual-input allowlist — when
# widening a CHECK enum, audit every existing Python-side surface that
# validates against the constant" (T-A.1.5b R3 M#1 banked).
# ============================================================================


def test_19_call_endpoint_accepts_surface_trade_entry(v18_conn):
    """Phase 13 hotfix — surface='trade_entry' (T3.SB1 path) MUST pass guard."""
    client = MagicMock()
    client.account_orders.return_value = _mock_response([])

    orders = get_account_orders(
        client, v18_conn,
        account_hash="abc...64charhash",
        from_entered_time=datetime(2026, 5, 7, tzinfo=UTC),
        to_entered_time=datetime(2026, 5, 14, tzinfo=UTC),
        surface="trade_entry", environment="production",
    )
    assert orders == []
    call_id = _latest_call_id(v18_conn)
    assert call_id is not None
    row = _audit_row(v18_conn, call_id)
    assert row[9] == "trade_entry"  # surface column
    assert row[7] == "success"  # status column


def test_20_call_endpoint_accepts_surface_trade_exit(v18_conn):
    """Phase 13 hotfix — surface='trade_exit' (T3.SB2 path) MUST pass guard."""
    client = MagicMock()
    client.account_orders.return_value = _mock_response([])

    orders = get_account_orders(
        client, v18_conn,
        account_hash="abc...64charhash",
        from_entered_time=datetime(2026, 5, 7, tzinfo=UTC),
        to_entered_time=datetime(2026, 5, 14, tzinfo=UTC),
        surface="trade_exit", environment="production",
    )
    assert orders == []
    call_id = _latest_call_id(v18_conn)
    assert call_id is not None
    row = _audit_row(v18_conn, call_id)
    assert row[9] == "trade_exit"  # surface column
    assert row[7] == "success"  # status column


# ============================================================================
# Test 16 — transactions wrapper passes types=TRANSACTION_TYPES_ALL by default
# ============================================================================


def test_17_silent_failure_post_call_token_cleared_triggers_auth_failed(v18_conn):
    """Codex R1 M#4 — post-call token-state validation.

    Discriminating: client returns a successful Response, but post-call
    `client.tokens.access_token = None` (silent-failure simulation). Pre-fix
    the wrapper would record success; post-fix records 'auth_failed'.
    """
    client = MagicMock()
    # Set access_token to a real value at construction
    client.tokens.access_token = "real_token_pre_call"

    # Mock side_effect to clear the access_token after the call.
    def side_effect(*args, **kwargs):
        client.tokens.access_token = None
        resp = MagicMock()
        resp.json.return_value = [{"accountNumber": "x", "hashValue": "h"}]
        resp.status_code = 200
        resp.headers = {}
        return resp

    client.linked_accounts.side_effect = side_effect

    with pytest.raises(SchwabAuthError):
        get_accounts_linked(
            client, v18_conn,
            surface="cli", environment="production",
        )
    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "auth_failed"


def test_18_schwabdev_raises_typed_schwab_api_error_audit_closes_correctly(v18_conn):
    """Codex R1 M#3 — schwabdev raises a typed SchwabApiError (NOT a generic
    BaseException). Pre-fix the audit row was left stuck in_flight; post-fix
    the row closes correctly to 'auth_failed' / 'rate_limited' / 'error'.

    Discriminating: stub schwabdev call to raise SchwabAuthError directly.
    Assert: post-call the audit row's status is 'auth_failed' (NOT 'in_flight').
    """
    client = MagicMock()
    client.account_details.side_effect = SchwabAuthError(401, "stub auth fail")

    with pytest.raises(SchwabAuthError):
        get_account_details(
            client, v18_conn,
            account_hash="abc...64charhash",
            surface="pipeline", environment="production",
        )
    call_id = _latest_call_id(v18_conn)
    row = _audit_row(v18_conn, call_id)
    assert row[7] == "auth_failed"  # NOT 'in_flight'


def test_16_transactions_default_types_is_full_documented_set(v18_conn):
    """Per T-B.0.b recon §3.2 — `types` REQUIRED kwarg; wrapper defaults to
    the documented 15-value set. Verifies the plan §E.2 deviation
    (`type_filter='ALL'` → `types=<full-list>`) is implemented correctly.
    """
    client = MagicMock()
    client.transactions.return_value = _mock_response([])

    get_account_transactions(
        client, v18_conn,
        account_hash="abc...64charhash",
        start_date="2026-05-07T00:00:00.000Z",
        end_date="2026-05-14T00:00:00.000Z",
        surface="cli", environment="production",
    )
    args, _ = client.transactions.call_args
    # args = (account_hash, start_str, end_str, types_list, ...)
    types_arg = args[3]
    assert isinstance(types_arg, list)
    assert len(types_arg) == len(TRANSACTION_TYPES_ALL)
    assert "TRADE" in types_arg
    assert "ACH_RECEIPT" in types_arg
    assert "DIVIDEND_OR_INTEREST" in types_arg
