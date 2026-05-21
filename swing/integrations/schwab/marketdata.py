"""Schwab Market Data API endpoint wrappers (Phase 11 Sub-bundle C T-C.1).

Two functions, one per Market Data API endpoint consumed in V1:

  - ``get_quotes_batch(client, conn, symbols, *, surface, environment,
    pipeline_run_id)`` → ``dict[str, SchwabQuoteResponse]``
  - ``get_price_history(client, conn, symbol, *, period_type, period,
    frequency_type, frequency, start_dt, end_dt, surface, environment,
    pipeline_run_id)`` → ``SchwabPriceHistoryWindow``

Each function mirrors Sub-bundle B's `trader.py` audit-lifecycle harness:

  1. Server-stamps ``ts`` at handler entry (Phase 8 server-stamping discipline).
  2. Invokes ``ensure_schwab_log_redaction_factory_installed()`` BEFORE every
     schwabdev call (Sub-bundle A M#2 family defense — factory may have been
     replaced by another library since install).
  3. INSERTs in-flight audit row via ``audit_service.record_call_start``.
  4. Times the schwabdev call wrapped in ``_suppress_transport_debug_logs()``.
  5. Extracts JSON payload via ``response.json()`` if Response-like; raw dict
     fallback for test stubs.
  6. On HTTP-level failure (401/429/4xx/5xx): classify + record_call_finish
     with the right status string (Sub-bundle B R1 M#3 family) + raise typed
     ``SchwabApiError`` subclass.
  7. Computes signature_hash off the response shape (drift-detection).
  8. Runs mapper (validates shape + content) — may raise
     ``SchwabSchemaParityError`` or ``SchwabApiError(204)`` (empty-bars
     transient).
  9. On mapper exception: record_call_finish(status='error') + raise.
  10. record_call_finish(status='success', ...) ONLY after ALL validation
      passes (Sub-bundle A M#3 family — audit-success-fire ordering).

Single-Client-instance discipline (Sub-bundle B forward-binding lesson #3 +
recon doc §1 obs 10): this module does NOT instantiate ``schwabdev.Client(...)``
— the caller passes an existing instance. Verified via the
``test_no_snake_case_price_history_kwargs_in_marketdata_calls`` source-grep
test which also implicitly verifies no ``schwabdev.Client(`` substring.

CamelCase kwarg discipline (Sub-bundle B 2026-05-14 gate-caught defect):
schwabdev 2.5.x `Client.price_history` uses 8 camelCase kwargs (periodType /
period / frequencyType / frequency / startDate / endDate /
needExtendedHoursData / needPreviousClose); only ``symbol`` is positional.
``Client.quotes`` uses 3 snake_case kwargs (symbols / fields / indicative).
The discriminating signature-pin test fires if either changes (per
``tests/integrations/test_schwab_marketdata_kwarg_signatures.py``).
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
    map_price_history_to_window,
    map_quotes_to_price_cache_entries,
)
from swing.integrations.schwab.models import (
    SchwabPriceHistoryWindow,
    SchwabQuoteResponse,
)

log = logging.getLogger(__name__)


# ============================================================================
# Helpers (mirror trader.py — kept local to avoid premature extraction; if
# duplication grows, T-C.2 or a follow-up bundle extracts to a shared
# `_endpoint_call.py` per dispatch brief pre-emption #10 guidance).
# ============================================================================


def _redacted_excerpt(exc: BaseException, *, max_chars: int = 80) -> str:
    """Sanitize exception message for audit-row write.

    REDACT FIRST (full message, bounded by global redactor's 500-char cap),
    TRUNCATE AFTER (audit-column budget). Mirrors trader.py contract verbatim.
    """
    raw = f"{type(exc).__name__}: {exc!s}"
    redacted = _redact_error_message_for_audit(raw)
    return redacted[:max_chars]


def _now_ms_iso() -> str:
    """Server-stamp at handler entry (matches Phase 8 + trader.py format)."""
    return datetime.now().isoformat(timespec="microseconds")


def _extract_response_payload(
    raw: Any, *, endpoint: str,
) -> tuple[Any, int | None, int | None]:
    """Extract (payload, http_status, rate_limit_remaining) from schwabdev result.

    schwabdev returns ``requests.Response`` objects; tests stub with raw
    payloads (dict). Tolerate both — same algorithm as trader.py.
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
    http_status: int | None,
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


def _compute_signature_hash(payload: Any, *, endpoint: str) -> str:
    """Per plan §H.9 — SHA-256 of canonicalized structural fingerprint.

    NOT body bytes — drift-detection only. Endpoint-specific structural
    extraction for the two Market Data endpoints:

      - marketdata.quotes: sorted symbol keys + per-symbol structural keys
        of the first symbol's payload (if any).
      - marketdata.pricehistory: top-level keys + `empty` flag + first-candle
        keys + candle count.
    """
    def _sorted_keys(d: Any) -> list[str]:
        if isinstance(d, dict):
            return sorted(d.keys())
        return []

    if endpoint == "marketdata.quotes":
        if isinstance(payload, dict):
            symbols = sorted(payload.keys())
            first_sym = symbols[0] if symbols else None
            first_payload = payload.get(first_sym) if first_sym else None
            first_keys = _sorted_keys(first_payload)
            # Also capture nested 'quote' keys if present (one common shape).
            nested_keys: list[str] = []
            if isinstance(first_payload, dict):
                nested = first_payload.get("quote")
                if isinstance(nested, dict):
                    nested_keys = _sorted_keys(nested)
            fp = {
                "endpoint": endpoint,
                "len": len(symbols),
                "first_keys": first_keys,
                "first_quote_keys": nested_keys,
            }
        else:
            fp = {"endpoint": endpoint, "len": 0, "first_keys": []}
    elif endpoint == "marketdata.pricehistory":
        top_keys = _sorted_keys(payload)
        candles = payload.get("candles", []) if isinstance(payload, dict) else []
        candles_len = len(candles) if isinstance(candles, list) else 0
        first_candle_keys = (
            _sorted_keys(candles[0])
            if candles_len and isinstance(candles[0], dict)
            else []
        )
        empty_flag = (
            bool(payload.get("empty", False)) if isinstance(payload, dict) else False
        )
        fp = {
            "endpoint": endpoint,
            "top_keys": top_keys,
            "candles_len": candles_len,
            "first_candle_keys": first_candle_keys,
            "empty": empty_flag,
        }
    else:
        fp = {"endpoint": endpoint, "top_keys": _sorted_keys(payload)}

    return hashlib.sha256(
        json.dumps(fp, sort_keys=True).encode("utf-8"),
    ).hexdigest()


# ============================================================================
# Endpoint wrappers
# ============================================================================


def get_quotes_batch(
    client: Any,
    conn: sqlite3.Connection,
    symbols: list[str],
    *,
    surface: str,
    environment: str,
    pipeline_run_id: int | None = None,
    fields: str | None = None,
) -> dict[str, SchwabQuoteResponse]:
    """Fetch `Client.quotes(symbols=symbols, fields=fields)`. Returns mapped dict.

    Per plan §E.3 + §E.4 (partial-response handling) + T-C.0.b recon §3.2.
    Schwab returns a dict keyed by symbol; some symbols may resolve to error
    envelopes (per-symbol partial failures). Mapper emits the OK subset; failed
    symbols are marked for yfinance fallback by the caller (ladder layer at
    T-C.3).

    Audit row status disposition:
      - 'success' if at least one symbol mapped successfully (even if some
        failed at the per-symbol partial-response level).
      - 'error' if ALL symbols failed (mapper returns empty dict).
      - HTTP-level failures (401/429/4xx) → 'auth_failed'/'rate_limited'/'error'
        per typed exception subclass.

    The audit ``error_message`` excerpt captures the per-symbol breakdown when
    a partial response occurred (e.g., "1/2 OK; failed: BADX") — under the
    no-token-leak contract (no token bytes, no account_hash).

    Schwabdev kwarg discipline: ``symbols`` + ``fields`` + ``indicative`` are
    ALL snake_case per `api-calls.md` L298 — SAFE from the Sub-bundle B
    camelCase trap family.

    Raises:
        SchwabAuthError on 401.
        SchwabRateLimitError on 429.
        SchwabApiError on other failures.
        SchwabSchemaParityError on top-level shape mismatch.
    """
    if not isinstance(symbols, list) or not symbols:
        raise SchwabApiError(
            0, "get_quotes_batch: symbols must be non-empty list[str]"
        )
    for s in symbols:
        if not isinstance(s, str) or not s:
            raise SchwabApiError(
                0,
                f"get_quotes_batch: each symbol must be non-empty str; "
                f"got {type(s).__name__}"
            )

    requested = list(symbols)

    def _client_method() -> Any:
        # schwabdev's `quotes` accepts list (per `api-calls.md` L307);
        # snake_case kwargs verified by signature-pin test.
        return client.quotes(symbols=requested, fields=fields)

    def _mapper(payload: Any) -> dict[str, SchwabQuoteResponse]:
        return map_quotes_to_price_cache_entries(payload)

    # Custom finish-hook for partial-response audit messaging.
    def _finish_hook(
        mapped: dict[str, SchwabQuoteResponse],
    ) -> tuple[str, str | None]:
        """Compute (audit_status, error_message) for the success/partial path.

        - All requested symbols mapped → ('success', None).
        - Some failed → ('success', '<n>/<N> OK; failed: <syms>').
        - None mapped → ('error', '0/<N> OK; failed: <syms>').
        """
        ok_count = len(mapped)
        n_total = len(requested)
        ok_syms = set(mapped.keys())
        failed = [s for s in requested if s not in ok_syms]
        if ok_count == n_total:
            return ("success", None)
        # Redact + truncate the failed-symbol list for the audit excerpt.
        failed_excerpt = ", ".join(failed[:5])
        if len(failed) > 5:
            failed_excerpt += f", +{len(failed) - 5} more"
        msg = f"{ok_count}/{n_total} OK; failed: {failed_excerpt}"
        msg = _redact_error_message_for_audit(msg)[:80]
        return (("success" if ok_count > 0 else "error"), msg)

    return _call_endpoint(
        client_method=_client_method,
        endpoint="marketdata.quotes",
        conn=conn,
        surface=surface,
        environment=environment,
        pipeline_run_id=pipeline_run_id,
        mapper=_mapper,
        finish_hook=_finish_hook,
        client=client,
    )


def get_price_history(
    client: Any,
    conn: sqlite3.Connection,
    symbol: str,
    *,
    period_type: str | None = None,
    period: int | None = None,
    frequency_type: str | None = None,
    frequency: int | None = None,
    start_dt: datetime | int | None = None,
    end_dt: datetime | int | None = None,
    surface: str,
    environment: str,
    pipeline_run_id: int | None = None,
) -> SchwabPriceHistoryWindow:
    """Fetch `Client.price_history(symbol, periodType=..., ...)`.

    Per plan §E.3 + §E.5 + §H.6.4 + T-C.0.b recon §3.3.

    **CamelCase kwarg discipline (BINDING):** schwabdev 2.5.x uses 8 camelCase
    kwargs (periodType / period / frequencyType / frequency / startDate /
    endDate / needExtendedHoursData / needPreviousClose); only ``symbol`` is
    positional. Same defect family as Sub-bundle B's gate-caught
    ``account_orders(maxResults=...)``. Signature-pin test fires if schwabdev
    changes.

    `start_dt` / `end_dt` accept ``datetime | int | None`` per `api-calls.md`
    L432-433 — pass straight through (schwabdev handles datetime→ms internally).
    Per recon §3.1 + §5.B: the `_schwab_iso` helper from trader.py is NOT
    applicable here (price_history takes datetime/int, not ISO string).

    Empty-bars transient handling (spec §E.5 + §H.6.4): if mapper detects
    `empty=true` OR `candles=[]`, it raises ``SchwabApiError(204, 'empty
    bars')``. The audit row closes with `status='error'` +
    `error_message='empty bars (transient)'`. Ladder (T-C.3) catches + falls
    back to yfinance.

    Raises:
        SchwabAuthError on 401.
        SchwabRateLimitError on 429.
        SchwabApiError on other failures + on empty-bars transient (status=204).
        SchwabSchemaParityError on top-level shape mismatch.
    """
    if not isinstance(symbol, str) or not symbol:
        raise SchwabApiError(
            0, "get_price_history: symbol must be non-empty str"
        )

    def _client_method() -> Any:
        # **camelCase BINDING — see module docstring + signature-pin test.**
        return client.price_history(
            symbol,
            periodType=period_type,
            period=period,
            frequencyType=frequency_type,
            frequency=frequency,
            startDate=start_dt,
            endDate=end_dt,
        )

    def _mapper(payload: Any) -> SchwabPriceHistoryWindow:
        return map_price_history_to_window(payload, ticker=symbol)

    return _call_endpoint(
        client_method=_client_method,
        endpoint="marketdata.pricehistory",
        conn=conn,
        surface=surface,
        environment=environment,
        pipeline_run_id=pipeline_run_id,
        mapper=_mapper,
        finish_hook=None,
        client=client,
        # Empty-bars: mapper raises SchwabApiError(204) — caller's path
        # records as 'error' with 'empty bars (transient)'.
        empty_bars_error_message="empty bars (transient)",
    )


# ============================================================================
# Shared audit-lifecycle harness (mirror of trader.py:_call_endpoint adapted
# for marketdata endpoints with finish-hook for partial-response messaging)
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
    finish_hook=None,
    client: Any = None,
    empty_bars_error_message: str | None = None,
):
    """Invoke the schwabdev method + thread through the audit lifecycle.

    Order of operations (BINDING per Sub-bundle A M#1+M#2+M#3 + Sub-bundle B
    R1 M#3 families):

      1. Server-stamp start_ts BEFORE any I/O.
      2. ``ensure_schwab_log_redaction_factory_installed()`` (M#2 defense).
      3. INSERT in-flight audit row (record_call_start).
      4. Time the schwabdev call inside ``_suppress_transport_debug_logs()``.
      5. On schwabdev exception: classify + record_call_finish + raise.
      6. Extract payload + http_status + rate_limit_remaining.
      7. If http_status >= 400: classify + record_call_finish(failure) + raise.
      8. Compute signature_hash (drift-detection).
      9. Run mapper. May raise:
         - SchwabApiError(204, 'empty bars'): empty-bars transient — record
           audit 'error' with empty_bars_error_message + raise.
         - SchwabSchemaParityError: shape mismatch — record audit 'error'.
         - ValueError/TypeError: per-bar invariant violation — wrap as parity.
     10. Optional finish_hook: customize the success-path status + error_message
         (used by quotes for partial-response messaging).
     11. record_call_finish(status=..., signature_hash=..., http_status=...).
     12. Return mapper output.

    The audit-success-fire happens ONLY after step 9 succeeds + after step 10's
    finish_hook (if any) computed its disposition (M#3 family).
    """
    # Phase 13 hotfix (2026-05-20 post-T3.SB2 merge): use the canonical
    # ``audit_service._SCHWAB_API_SURFACE_VALUES`` 4-tuple (mirrors the v20
    # schema CHECK widening at T-A.1.1 that added 'trade_entry'/'trade_exit').
    # Inert today (T3.SB1/T3.SB2 consume only Trader API, not Market Data),
    # but defensive parity with trader._call_endpoint keeps the two surface
    # guards in lock-step for future review/charts paths that may consume
    # marketdata with the new surfaces. Per CLAUDE.md gotcha "Schema-coverage
    # Python constant is NOT necessarily the manual-input allowlist".
    if surface not in audit_service._SCHWAB_API_SURFACE_VALUES:
        raise SchwabApiError(
            0,
            f"_call_endpoint: surface must be one of "
            f"{audit_service._SCHWAB_API_SURFACE_VALUES}; got {surface!r}"
        )
    if environment not in ("sandbox", "production"):
        raise SchwabApiError(
            0,
            f"_call_endpoint: environment must be 'sandbox'|'production'; "
            f"got {environment!r}"
        )

    start_ts = _now_ms_iso()
    # M#2 family — re-wrap factory if a third-party library replaced it.
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

    # Step 6.
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
        exc_cls, status_str = _classify_http_failure(http_status)
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
    except SchwabApiError as exc:
        # The empty-bars transient path raises SchwabApiError(204, 'empty bars').
        # Per spec §E.5 + §H.6.4: record audit 'error' with verbatim message,
        # then re-raise so caller (ladder) can catch + fall back to yfinance.
        is_empty_bars = (
            exc.status_code == 204
            and empty_bars_error_message is not None
        )
        audit_message = (
            empty_bars_error_message
            if is_empty_bars else _redacted_excerpt(exc)
        )
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=http_status,
            response_time_ms=elapsed_ms,
            rate_limit_remaining=rate_limit_remaining,
            signature_hash=sig,
            status="error",
            error_message=audit_message,
        )
        raise
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

    # Step 10 — optional finish hook for partial-response messaging (quotes).
    if finish_hook is not None:
        finish_status, finish_message = finish_hook(mapped)
    else:
        finish_status, finish_message = ("success", None)

    # Step 11 — final audit close. ALL validation passed.
    audit_service.record_call_finish(
        conn,
        call_id=call_id,
        http_status=http_status if http_status is not None else 200,
        response_time_ms=elapsed_ms,
        rate_limit_remaining=rate_limit_remaining,
        signature_hash=sig,
        status=finish_status,
        error_message=finish_message,
    )
    return mapped


__all__ = [
    "get_price_history",
    "get_quotes_batch",
]
