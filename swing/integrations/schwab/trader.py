"""Schwab Trader API endpoint wrappers (Phase 11 Sub-bundle B T-B.1).

Four functions, one per Trader API endpoint consumed in V1:
  - `get_accounts_linked(client, conn, *, surface, environment, pipeline_run_id)`
  - `get_account_details(client, conn, account_hash, *, ...)`
  - `get_account_orders(client, conn, account_hash, from_dt, to_dt, *, ...)`
  - `get_account_transactions(client, conn, account_hash, start_dt, end_dt, *, ...)`

Each function:
  1. Server-stamps `ts` at handler entry (Phase 8 server-stamping discipline).
  2. Invokes `ensure_schwab_log_redaction_factory_installed()` BEFORE every
     schwabdev call (Sub-bundle A M#2 family pre-emption — factory-replacement
     defense; the factory may have been replaced by another library since
     install).
  3. INSERTs in-flight audit row via `audit_service.record_call_start`.
  4. Times the schwabdev call; wraps in `_suppress_transport_debug_logs()`.
  5. Extracts JSON payload via `response.json()` if Response-like; raw dict
     fallback for test stubs.
  6. Validates response shape AND content BEFORE firing the success audit
     (Sub-bundle A M#3 family — audit-success-fire MUST follow ALL
     validation; pre-success rejection paths fire `record_call_finish(
     status='error'/'auth_failed'/'rate_limited')` and raise).
  7. Computes signature_hash off the response shape (drift-detection).
  8. Records success via `record_call_finish` + returns mapped dataclass.

Single-Client-instance discipline (per dispatch brief §0.6 + plan §A.2):
trader.py does NOT instantiate `schwabdev.Client(...)` — it consumes the
existing instance passed by the caller (auth.py constructs it inside
`setup_paste_flow` / `force_refresh`; pipeline-step + CLI consumers
construct it on demand via the schwabdev `Client(...)` constructor).

`reference/schwabdev/api-calls.md` is the canonical source for method
signatures + return shapes. T-B.0.b recon doc §3 enumerates the 5 plan
deviations (kwarg names + value semantics).
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime
from typing import Any

from swing.integrations.schwab import audit_service
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabAuthError,
    SchwabRateLimitError,
    SchwabSchemaParityError,
    _redact_error_message_for_audit,
    _suppress_transport_debug_logs,
    ensure_schwab_log_redaction_factory_installed,
)
from swing.integrations.schwab.mappers import (
    map_account_details_to_equity_snapshot_inputs,
    map_account_linked_to_hash_set,
    map_orders_to_fill_candidates,
    map_transactions_to_cash_movement_candidates,
)
from swing.integrations.schwab.models import (
    SchwabAccountResponse,
    SchwabOrderResponse,
    SchwabTransactionResponse,
)

log = logging.getLogger(__name__)


# Per `api-calls.md` L256 documented transaction-type enum (15 V1 values).
# `_step_schwab_orders` invokes `get_account_transactions` with this list
# (matching plan §H.4.2 step 9 intent "type_filter='ALL'" — schwabdev requires
# an explicit list/str per recon §3.2 + §5 §A).
TRANSACTION_TYPES_ALL: list[str] = [
    "TRADE", "RECEIVE_AND_DELIVER", "DIVIDEND_OR_INTEREST",
    "ACH_RECEIPT", "ACH_DISBURSEMENT",
    "CASH_RECEIPT", "CASH_DISBURSEMENT",
    "ELECTRONIC_FUND", "WIRE_OUT", "WIRE_IN",
    "JOURNAL", "MEMORANDUM", "MARGIN_CALL",
    "MONEY_MARKET", "SMA_ADJUSTMENT",
]


# Redaction helper for audit error_message — mirrors auth.py:_redacted_excerpt
# (Sub-bundle A M#1 + R3 M#1 family — redact-then-truncate; CLAUDE.md gotcha
# "Redact-then-truncate audit-error ordering").
def _redacted_excerpt(exc: BaseException, *, max_chars: int = 80) -> str:
    """Sanitize exception message for audit-row write.

    REDACT FIRST (full message, bounded by _make_redactor's 500-char cap),
    TRUNCATE AFTER (audit-column budget). Mirrors auth.py contract verbatim.
    """
    raw = f"{type(exc).__name__}: {exc!s}"
    redacted = _redact_error_message_for_audit(raw)
    return redacted[:max_chars]


def _now_ms_iso() -> str:
    """Server-stamp at handler entry (matches Phase 8 + auth.py format)."""
    return datetime.now().isoformat(timespec="microseconds")


def _schwab_iso(dt: datetime | str) -> str:
    """Format a datetime as Schwab's `yyyy-MM-dd'T'HH:mm:ss.SSSZ` string.

    Per `api-calls.md` L121-122 + L254-255. Accepts a `datetime` or pre-
    formatted string (passes pre-formatted strings through unchanged so
    callers can pass either).

    Implementation note: schwabdev's underlying request layer accepts both
    `datetime` objects + pre-formatted strings, but we normalize to a
    string at the wrapper layer so audit-row inputs + signature_hash
    computation are deterministic across caller types.
    """
    if isinstance(dt, str):
        return dt
    # Strip tzinfo if naive; schwabdev expects UTC.
    if dt.tzinfo is not None:
        from datetime import UTC
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    # `2026-05-14T00:00:00.000Z` shape.
    ms = f"{dt.microsecond // 1000:03d}"
    return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{ms}Z"


def _extract_response_payload(
    raw: Any, *, endpoint: str,
) -> tuple[Any, int | None, int | None]:
    """Extract (payload, http_status, rate_limit_remaining) from schwabdev result.

    schwabdev returns `requests.Response` objects; tests stub with raw payloads
    (list/dict). Tolerate both.

    Returns:
        (payload, http_status, rate_limit_remaining). http_status is None when
        the result lacks `.status_code` (raw-payload stubs); rate_limit_remaining
        is None when no `X-RateLimit-Remaining` header is present.
    """
    if hasattr(raw, "json") and callable(raw.json):
        try:
            payload = raw.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise SchwabApiError(
                getattr(raw, "status_code", 0) or 0,
                f"<{endpoint}: response.json() decode failure: "
                f"{type(exc).__name__}>",
            ) from exc
    else:
        payload = raw

    http_status: int | None = getattr(raw, "status_code", None)
    if http_status is not None and not isinstance(http_status, int):
        http_status = None

    rate_limit_remaining: int | None = None
    headers = getattr(raw, "headers", None)
    if headers is not None:
        for header_name in (
            "X-RateLimit-Remaining",
            "X-Rate-Limit-Remaining",
            "Schwab-Client-RateLimit-Remaining",
        ):
            try:
                v = headers.get(header_name)
            except AttributeError:
                v = None
            if v is not None:
                try:
                    rate_limit_remaining = int(v)
                    break
                except (TypeError, ValueError):
                    rate_limit_remaining = None

    return payload, http_status, rate_limit_remaining


def _classify_http_failure(
    http_status: int | None, body_excerpt: str, *, endpoint: str,
) -> tuple[type[SchwabApiError], str]:
    """Map HTTP failure status → (exception class, audit status string).

    401 → SchwabAuthError + 'auth_failed'.
    429 → SchwabRateLimitError + 'rate_limited'.
    Other non-2xx → SchwabApiError + 'error'.
    """
    if http_status == 401:
        return (SchwabAuthError, "auth_failed")
    if http_status == 429:
        return (SchwabRateLimitError, "rate_limited")
    return (SchwabApiError, "error")


def _compute_signature_hash(
    payload: Any, *, endpoint: str,
) -> str:
    """Per plan §H.9 — SHA-256 of canonicalized structural fingerprint.

    NOT body bytes — drift-detection only.

    Endpoint-specific structural extraction:
      - accounts.linked: sorted top-level keys of each entry + list length.
      - accounts.details: sorted top-level keys + positions length.
      - accounts.orders.list: sorted keys of first order (if any) + list length.
      - accounts.transactions.list: sorted keys of first tx (if any) + list length.
    """
    def _sorted_dict_keys(d: Any) -> list[str]:
        if isinstance(d, dict):
            return sorted(d.keys())
        return []

    if endpoint == "accounts.linked":
        n = len(payload) if isinstance(payload, list) else 0
        first_keys = _sorted_dict_keys(payload[0]) if n else []
        fp = {"endpoint": endpoint, "len": n, "first_keys": first_keys}
    elif endpoint == "accounts.details":
        # Nested at securitiesAccount in real responses; tolerate flat.
        sec = (
            payload.get("securitiesAccount")
            if isinstance(payload, dict) else None
        ) or payload
        top_keys = _sorted_dict_keys(sec)
        positions = sec.get("positions", []) if isinstance(sec, dict) else []
        fp = {
            "endpoint": endpoint,
            "top_keys": top_keys,
            "positions_len": len(positions) if isinstance(positions, list) else 0,
        }
    elif endpoint in ("accounts.orders.list", "accounts.transactions.list"):
        n = len(payload) if isinstance(payload, list) else 0
        first_keys = (
            _sorted_dict_keys(payload[0]) if n and isinstance(payload[0], dict)
            else []
        )
        fp = {"endpoint": endpoint, "len": n, "first_keys": first_keys}
    else:
        fp = {"endpoint": endpoint, "top_keys": _sorted_dict_keys(payload)}

    return hashlib.sha256(
        json.dumps(fp, sort_keys=True).encode("utf-8"),
    ).hexdigest()


# ============================================================================
# Endpoint wrappers
# ============================================================================


def get_accounts_linked(
    client: Any,
    conn: sqlite3.Connection,
    *,
    surface: str,
    environment: str,
    pipeline_run_id: int | None = None,
) -> list[str]:
    """Fetch `Client.account_linked()`. Returns list of hashValue strings.

    Audit endpoint: `accounts.linked`. Sub-bundle A's `auth.py:setup_paste_flow`
    already invokes `client.account_linked()` directly via the `_stub_*` seam;
    Sub-bundle B's `get_accounts_linked` is the canonical wrapper for the
    `swing schwab status` + future re-discovery flows.

    Raises:
        SchwabAuthError on 401 / shape errors / empty list.
        SchwabRateLimitError on 429.
        SchwabApiError on other failures.
    """
    return _call_endpoint(
        client_method=lambda: client.account_linked(),
        endpoint="accounts.linked",
        conn=conn,
        surface=surface,
        environment=environment,
        pipeline_run_id=pipeline_run_id,
        mapper=_map_accounts_linked_with_empty_check,
        client=client,
    )


def _map_accounts_linked_with_empty_check(payload: Any) -> list[str]:
    """Mapper wrapper that also rejects empty list (auth.py D2 lesson)."""
    hashes = map_account_linked_to_hash_set(payload)
    if not hashes:
        raise SchwabSchemaParityError(
            "accounts.linked: returned empty list; expected at least 1 account"
        )
    return hashes


def get_account_details(
    client: Any,
    conn: sqlite3.Connection,
    account_hash: str,
    *,
    surface: str,
    environment: str,
    pipeline_run_id: int | None = None,
    fields: str | None = "positions",
) -> SchwabAccountResponse:
    """Fetch `Client.account_details(account_hash, fields=fields)`.

    Default `fields='positions'` per `api-calls.md` L102 (fetches positions
    alongside balances; needed for reconciliation position-qty checks at
    T-B.4).

    Plan §E.2 row 2 deviation banked (T-B.0.b recon §5 §B): fields is
    `str | None`, NOT `list[str]`. Wrapper passes the string.
    """
    if not isinstance(account_hash, str) or not account_hash:
        raise SchwabApiError(
            0, "account_details: account_hash must be non-empty str"
        )

    return _call_endpoint(
        client_method=lambda: client.account_details(account_hash, fields=fields),
        endpoint="accounts.details",
        conn=conn,
        surface=surface,
        environment=environment,
        pipeline_run_id=pipeline_run_id,
        mapper=lambda p: map_account_details_to_equity_snapshot_inputs(
            p, account_hash=account_hash,
        ),
        client=client,
    )


def get_account_orders(
    client: Any,
    conn: sqlite3.Connection,
    account_hash: str,
    from_entered_time: datetime | str,
    to_entered_time: datetime | str,
    *,
    surface: str,
    environment: str,
    pipeline_run_id: int | None = None,
    status: str | None = None,
    max_results: int | None = None,
) -> list[SchwabOrderResponse]:
    """Fetch ``Client.account_orders(...)`` via schwabdev's 21-status enum wrapper.

    Plan §E.2 row 3 deviation banked (T-B.0.b recon §5 §C): kwarg is `status`,
    NOT `status_filter`. Wrapper passes verbatim.

    Default `status=None` fetches ALL statuses per `api-calls.md` L124 (the
    21-value enum); matches plan §H.4.2 step 6 intent "give reconciliation
    full coverage".
    """
    if not isinstance(account_hash, str) or not account_hash:
        raise SchwabApiError(
            0, "account_orders: account_hash must be non-empty str"
        )

    from_str = _schwab_iso(from_entered_time)
    to_str = _schwab_iso(to_entered_time)

    return _call_endpoint(
        # NOTE: schwabdev 2.5.1 uses camelCase kwarg `maxResults` — NOT
        # `max_results`. Live verification 2026-05-14 caught this mismatch
        # via TypeError. Discriminating test at
        # tests/integrations/test_schwab_trader_kwarg_signatures.py pins
        # all 4 trader methods against inspect.signature(schwabdev.Client.X).
        client_method=lambda: client.account_orders(
            account_hash, from_str, to_str,
            status=status, maxResults=max_results,
        ),
        endpoint="accounts.orders.list",
        conn=conn,
        surface=surface,
        environment=environment,
        pipeline_run_id=pipeline_run_id,
        mapper=map_orders_to_fill_candidates,
        client=client,
    )


def get_account_transactions(
    client: Any,
    conn: sqlite3.Connection,
    account_hash: str,
    start_date: datetime | str,
    end_date: datetime | str,
    *,
    surface: str,
    environment: str,
    pipeline_run_id: int | None = None,
    types: list[str] | None = None,
    symbol: str | None = None,
) -> list[SchwabTransactionResponse]:
    """Fetch `Client.transactions(account_hash, start_date, end_date, types=types, symbol=symbol)`.

    Plan §E.2 row 4 deviation banked (T-B.0.b recon §5 §A): kwarg is `types`
    (REQUIRED list of enum values), NOT `type_filter='ALL'`. When caller
    omits, defaults to TRANSACTION_TYPES_ALL (the documented 15-value set).
    """
    if not isinstance(account_hash, str) or not account_hash:
        raise SchwabApiError(
            0, "transactions: account_hash must be non-empty str"
        )

    types_arg: list[str] = list(types) if types is not None else list(TRANSACTION_TYPES_ALL)
    start_str = _schwab_iso(start_date)
    end_str = _schwab_iso(end_date)

    return _call_endpoint(
        client_method=lambda: client.transactions(
            account_hash, start_str, end_str, types_arg, symbol=symbol,
        ),
        endpoint="accounts.transactions.list",
        conn=conn,
        surface=surface,
        environment=environment,
        pipeline_run_id=pipeline_run_id,
        mapper=map_transactions_to_cash_movement_candidates,
        client=client,
    )


# ============================================================================
# Shared audit-lifecycle harness (DRY across the 4 endpoint wrappers)
# ============================================================================


def _call_endpoint(
    *,
    client_method,
    endpoint: str,
    conn: sqlite3.Connection,
    surface: str,
    environment: str,
    pipeline_run_id: int | None,
    mapper,
    client: Any = None,
):
    """Invoke the schwabdev method + thread through the audit lifecycle.

    Order of operations (BINDING per Sub-bundle A M#1 + M#2 + M#3 families):
      1. Server-stamp start_ts BEFORE any I/O.
      2. ensure_schwab_log_redaction_factory_installed() (M#2 defense).
      3. INSERT in-flight audit row (record_call_start).
      4. Time the schwabdev call inside _suppress_transport_debug_logs().
      5. On schwabdev exception: classify → record_call_finish(error/auth/rate) + raise.
      6. Extract payload + http_status + rate_limit_remaining.
      7. If http_status >= 400: classify + record_call_finish(failure) + raise.
      8. Compute signature_hash (drift-detection).
      9. Run mapper (validates shape AND content) — may raise SchwabSchemaParityError.
     10. On mapper exception: record_call_finish(error) + raise.
     11. record_call_finish(status='success', signature_hash, http_status, response_time_ms).
     12. Return mapper output.

    The audit-success-fire happens ONLY after step 9 succeeds (M#3 family).
    """
    if surface not in ("pipeline", "cli"):
        raise SchwabApiError(
            0, f"_call_endpoint: surface must be 'pipeline'|'cli'; got {surface!r}"
        )
    if environment not in ("sandbox", "production"):
        raise SchwabApiError(
            0,
            f"_call_endpoint: environment must be 'sandbox'|'production'; "
            f"got {environment!r}"
        )

    start_ts = _now_ms_iso()
    # M#2 family defense — re-wrap factory if a third-party library replaced it.
    ensure_schwab_log_redaction_factory_installed()

    call_id = audit_service.record_call_start(
        conn,
        ts=start_ts,
        endpoint=endpoint,
        pipeline_run_id=pipeline_run_id,
        surface=surface,
        environment=environment,
    )

    construction_start = time.monotonic()
    raw: Any = None
    try:
        with _suppress_transport_debug_logs():
            raw = client_method()
    except SchwabApiError as exc:
        # schwabdev or wrapper raised one of our typed errors directly.
        # Codex R1 M#3 fix: MUST close the audit row before re-raising,
        # otherwise the in_flight row never transitions. Classify the
        # status from the typed exception subclass.
        elapsed_ms = int((time.monotonic() - construction_start) * 1000)
        if isinstance(exc, SchwabAuthError):
            status_str = "auth_failed"
        elif isinstance(exc, SchwabRateLimitError):
            status_str = "rate_limited"
        else:
            status_str = "error"
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=getattr(exc, "status_code", None),
            response_time_ms=elapsed_ms,
            rate_limit_remaining=None,
            signature_hash=None,
            status=status_str,
            error_message=_redacted_excerpt(exc),
        )
        raise
    except BaseException as exc:
        elapsed_ms = int((time.monotonic() - construction_start) * 1000)
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=None,
            response_time_ms=elapsed_ms,
            rate_limit_remaining=None,
            signature_hash=None,
            status="error",
            error_message=_redacted_excerpt(exc),
        )
        log.warning(
            "schwab %s call failed during schwabdev invocation: %s",
            endpoint, type(exc).__name__,
        )
        raise SchwabApiError(
            0,
            f"<{endpoint}: schwabdev invocation failed: {type(exc).__name__}>",
        ) from exc

    elapsed_ms = int((time.monotonic() - construction_start) * 1000)

    # Step 6 — payload + status + rate_limit.
    try:
        payload, http_status, rate_limit_remaining = _extract_response_payload(
            raw, endpoint=endpoint,
        )
    except SchwabApiError as exc:
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=getattr(raw, "status_code", None),
            response_time_ms=elapsed_ms,
            rate_limit_remaining=None,
            signature_hash=None,
            status="error",
            error_message=_redacted_excerpt(exc),
        )
        raise

    # Step 7 — HTTP-level failures (auth/rate/error). Validate BEFORE mapper.
    if http_status is not None and http_status >= 400:
        exc_cls, status_str = _classify_http_failure(
            http_status, str(payload)[:200], endpoint=endpoint,
        )
        body_excerpt = (
            _redact_error_message_for_audit(json.dumps(payload, default=str)[:200])
            if payload is not None else ""
        )
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=http_status,
            response_time_ms=elapsed_ms,
            rate_limit_remaining=rate_limit_remaining,
            signature_hash=None,
            status=status_str,
            error_message=_redact_error_message_for_audit(
                f"HTTP {http_status}: {body_excerpt}"
            )[:80],
        )
        raise exc_cls(http_status, body_excerpt)

    # Step 8 — signature hash (drift-detection).
    sig = _compute_signature_hash(payload, endpoint=endpoint)

    # Step 9 — mapper. Validates shape + content.
    try:
        mapped = mapper(payload)
    except SchwabSchemaParityError as exc:
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=http_status,
            response_time_ms=elapsed_ms,
            rate_limit_remaining=rate_limit_remaining,
            signature_hash=sig,
            status="error",
            error_message=_redacted_excerpt(exc),
        )
        raise
    except (ValueError, TypeError, KeyError) as exc:
        # Defensive: dataclass __post_init__ + mapper-internal validators
        # may raise other typed errors. Treat as schema-parity error.
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=http_status,
            response_time_ms=elapsed_ms,
            rate_limit_remaining=rate_limit_remaining,
            signature_hash=sig,
            status="error",
            error_message=_redacted_excerpt(exc),
        )
        raise SchwabSchemaParityError(
            f"<{endpoint}: response mapping failed: {type(exc).__name__}>"
        ) from exc

    # Step 10 — silent-failure post-call token-state validation (Sub-bundle A
    # M#1 family extension; Codex R1 M#4 fix). If the schwabdev client's
    # access_token has been explicitly cleared (set to None or empty string)
    # between call construction + completion, the call's "success" is
    # suspect — treat as auth_failed. Tolerates MagicMock + similar test
    # stubs that auto-generate child attrs (the check fires ONLY on
    # explicit clearance; not on type-mismatch — production schwabdev sets
    # a real string, MagicMock returns a child MagicMock).
    if client is not None and hasattr(client, "tokens"):
        access = getattr(client.tokens, "access_token", "<missing-sentinel>")
        # Fire only on explicit clear-to-None or clear-to-empty-string.
        # A child MagicMock attribute will be truthy and not equal "" so
        # passes through.
        if access is None or access == "":
            audit_service.record_call_finish(
                conn,
                call_id=call_id,
                http_status=http_status,
                response_time_ms=elapsed_ms,
                rate_limit_remaining=rate_limit_remaining,
                signature_hash=sig,
                status="auth_failed",
                error_message=(
                    "<post-call client.tokens.access_token cleared "
                    "(None/empty); schwabdev may have silently dropped "
                    "auth state>"
                ),
            )
            raise SchwabAuthError(
                401,
                f"<{endpoint}: post-call token state invalid>",
            )

    # Step 11 — success audit close. ALL validation passed.
    audit_service.record_call_finish(
        conn,
        call_id=call_id,
        http_status=http_status if http_status is not None else 200,
        response_time_ms=elapsed_ms,
        rate_limit_remaining=rate_limit_remaining,
        signature_hash=sig,
        status="success",
        error_message=None,
    )
    return mapped


__all__ = [
    "TRANSACTION_TYPES_ALL",
    "get_account_details",
    "get_account_orders",
    "get_account_transactions",
    "get_accounts_linked",
]
