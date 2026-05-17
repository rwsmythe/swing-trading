"""Schwab API response → project dataclass mappers (Phase 11 Sub-bundle B T-B.1).

Pure functions: NO HTTP, NO DB, NO logging. Mappers transform schwabdev JSON
responses (raw dicts/lists) into the project's typed dataclasses defined at
`swing/data/models.py`. Each mapper:
- Tolerates absent / null fields where Schwab's schema permits them.
- Raises `SchwabSchemaParityError` (NOT KeyError / TypeError) when a REQUIRED
  field is missing or malformed — preserves the project's redacted-message
  exception contract per CLAUDE.md gotcha "all exceptions __str__ MUST redact
  hash-shaped substrings".

Per plan §E.2 + §B.1 file map + T-B.0.b recon doc §3 + §5 (banked plan
deviations from `fields=list` → `fields=str`; `type_filter='ALL'` → `types=list`).

The mapper functions are consumed by `trader.py` AFTER the schwabdev call
returns + AFTER the audit row's success has been recorded — the audit-row
classifier MUST short-circuit on shape errors BEFORE the success-fire (per
Sub-bundle A M#3 family lesson "audit-success-fire ordering"). Trader.py
calls these mappers inside a try/except that converts ValueError /
SchwabSchemaParityError into a redacted audit_failed close + raise.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabSchemaParityError,
)
from swing.integrations.schwab.models import (
    OhlcvBar,
    SchwabAccountResponse,
    SchwabExecutionLeg,
    SchwabOrderResponse,
    SchwabPriceHistoryWindow,
    SchwabQuoteResponse,
    SchwabTransactionResponse,
)

_log = logging.getLogger(__name__)


def _require(d: Any, key: str, *, ctx: str) -> Any:
    """Return d[key] or raise SchwabSchemaParityError with a redacted message."""
    if not isinstance(d, dict):
        raise SchwabSchemaParityError(
            f"{ctx}: expected dict; got {type(d).__name__}"
        )
    if key not in d:
        raise SchwabSchemaParityError(f"{ctx}: missing required key {key!r}")
    return d[key]


def _opt(d: Any, key: str, default: Any = None) -> Any:
    """Return d.get(key, default) safely (None if d is not a dict)."""
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def map_account_linked_to_hash_set(response: Any) -> list[str]:
    """Map `Client.account_linked()` response → list of hashValue strings.

    Schwab Developer Portal /accounts/accountNumbers returns a JSON array of
    `{accountNumber, hashValue}` dicts (single-account → list of length 1;
    multi-account → length > 1). Per Sub-bundle A T-A.0.b §6.bis.1 live
    verification.

    Raises `SchwabSchemaParityError` if shape diverges.
    """
    if not isinstance(response, list):
        raise SchwabSchemaParityError(
            f"account_linked: expected list, got {type(response).__name__}"
        )
    out: list[str] = []
    for i, entry in enumerate(response):
        h = _opt(entry, "hashValue")
        if not isinstance(h, str) or not h:
            raise SchwabSchemaParityError(
                f"account_linked[{i}]: missing or empty hashValue"
            )
        out.append(h)
    return out


def map_account_details_to_equity_snapshot_inputs(
    response: Any, account_hash: str,
) -> SchwabAccountResponse:
    """Map `Client.account_details(account_hash, fields='positions')` → SchwabAccountResponse.

    NLV path per Schwab Developer Portal account-specification.md (verified
    via plan §E.2 + recon §3 §1):
      response['securitiesAccount']['currentBalances']['liquidationValue']

    Falls back to `currentBalances.equity` then `aggregateBalance.liquidationValue`
    if `liquidationValue` is absent (defense-in-depth for cassette variance).
    Cash + buying-power follow the same path under `currentBalances.cashBalance`
    + `currentBalances.buyingPower`.

    Positions are returned opaquely (list of dicts) — reconciliation uses
    them via the orders mapper's position-matching helper at T-B.4.

    Raises `SchwabSchemaParityError` if neither `currentBalances` nor
    `aggregateBalance` is present.
    """
    if not isinstance(response, dict):
        raise SchwabSchemaParityError(
            f"account_details: expected dict, got {type(response).__name__}"
        )

    sec = response.get("securitiesAccount") or response  # tolerate flat vs nested
    cb = _opt(sec, "currentBalances", {})
    agg = _opt(sec, "aggregateBalance", {})

    # NLV resolution ladder.
    nlv = (
        _opt(cb, "liquidationValue")
        if isinstance(cb, dict) and "liquidationValue" in cb
        else _opt(cb, "equity")
        if isinstance(cb, dict) and "equity" in cb
        else _opt(agg, "liquidationValue")
    )
    if nlv is None:
        raise SchwabSchemaParityError(
            "account_details: liquidationValue / equity not found in "
            "currentBalances or aggregateBalance"
        )

    cash = _opt(cb, "cashBalance") if isinstance(cb, dict) else None
    buying_power = _opt(cb, "buyingPower") if isinstance(cb, dict) else None
    positions = _opt(sec, "positions", [])
    if positions is None:
        positions = []

    from swing.data.datetime_helpers import now_ms

    return SchwabAccountResponse(
        account_hash=account_hash,
        net_liquidating_value=float(nlv),
        cash=float(cash) if cash is not None else 0.0,
        buying_power=float(buying_power) if buying_power is not None else 0.0,
        positions=list(positions),
        recorded_at=now_ms(),
    )


def map_orders_to_fill_candidates(response: Any) -> list[SchwabOrderResponse]:
    """Map `Client.account_orders(...)` response → list of SchwabOrderResponse.

    Schwab returns a list of order dicts; per `api-calls.md` L126. Each order
    has order_id, status, enteredTime, orderLegCollection[0].instruction +
    .quantity + .instrument.symbol, orderType, price.

    Empty list returned for "no orders in period" (NOT an error — production
    state). Caller treats `[]` as success.

    Per-order fields per Schwab Developer Portal account-specification.md
    Order schema. Mapper extracts the FIRST leg only (V1 single-leg trades
    matched by reconciliation); multi-leg orders pass through with the
    first-leg's metadata + the dataclass `notes` field documenting truncation
    is OUT OF SCOPE V1 (operator V2-defers complex options).
    """
    if response is None:
        return []
    if not isinstance(response, list):
        raise SchwabSchemaParityError(
            f"account_orders: expected list, got {type(response).__name__}"
        )

    out: list[SchwabOrderResponse] = []
    for i, raw in enumerate(response):
        if not isinstance(raw, dict):
            raise SchwabSchemaParityError(
                f"account_orders[{i}]: expected dict, got {type(raw).__name__}"
            )
        order_id_raw = _opt(raw, "orderId")
        if order_id_raw is None:
            raise SchwabSchemaParityError(
                f"account_orders[{i}]: missing orderId"
            )
        order_id = str(order_id_raw)

        status = _opt(raw, "status")
        if not isinstance(status, str) or not status:
            raise SchwabSchemaParityError(
                f"account_orders[{i}]: missing or empty status"
            )

        entered_time = _opt(raw, "enteredTime") or _opt(raw, "enterTime") or ""

        legs = _opt(raw, "orderLegCollection", [])
        # Codex R1 M#9 — mapper resilience. Real-world Schwab order responses
        # may include order types without an orderLegCollection (e.g., parent
        # conditional orders, multi-leg options legs that we drop because
        # equities-only). Rather than failing the entire orders fetch on a
        # single non-leg row, SKIP the row with a structured log entry. The
        # audit row's signature_hash continues to be shape-derived so drift
        # is still observable; downstream reconciliation simply has one
        # fewer matchable order.
        if not isinstance(legs, list) or not legs:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "map_orders_to_fill_candidates: skipping order %s (idx=%d) "
                "with missing/empty orderLegCollection",
                order_id, i,
            )
            continue
        leg0 = legs[0]
        if not isinstance(leg0, dict):
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "map_orders_to_fill_candidates: skipping order %s (idx=%d) "
                "with non-dict orderLegCollection[0]",
                order_id, i,
            )
            continue
        instruction = _opt(leg0, "instruction", "")
        quantity = float(_opt(leg0, "quantity", 0) or 0)
        instrument = _opt(leg0, "instrument", {})
        symbol = _opt(instrument, "symbol", "") if isinstance(instrument, dict) else ""

        order_type = _opt(raw, "orderType", "")
        price_raw = _opt(raw, "price")
        if price_raw is None:
            # Stop-trigger lives under stopPrice for STOP-family orders.
            price_raw = _opt(raw, "stopPrice")
        price: float | None = (
            float(price_raw) if price_raw is not None else None
        )

        # Sub-bundle 1 T-1.3 — extract orderActivityCollection[].executionLegs[]
        # per spec §4.3 + §5.3 mapper-coherence rule. Defensive parsing
        # (never raises on malformed leg); coherence check distinguishes
        # legitimate partial fills from malformed leg totals.
        executions = _extract_executions_from_order_raw(
            raw, order_id=order_id,
        )

        out.append(SchwabOrderResponse(
            order_id=order_id,
            status=status,
            enter_time=entered_time,
            instrument_symbol=str(symbol),
            instruction=instruction,
            quantity=quantity,
            order_type=order_type,
            price=price,
            executions=executions,
        ))
    return out


def _extract_executions_from_order_raw(
    raw: dict, *, order_id: str,
) -> list[SchwabExecutionLeg] | None:
    """Sub-bundle 1 T-1.3 — extract orderActivityCollection[].executionLegs[]
    legs from a single Schwab order dict.

    Per spec §4.3 + §5.3 mapper-coherence rule:

    1. ``orderActivityCollection`` missing / non-list / empty → ``None``
       (V1 backward compat: legacy mapper path; sandbox; older responses).
    2. Per activity: non-dict → skip + warn; non-EXECUTION activityType →
       skip silently.
    3. Per leg under EXECUTION activity: non-dict → skip + warn; dataclass
       validator raises → drop leg + warn; remaining legs preserved.
    4. After collecting: if collected list empty → ``None`` (no legs
       survived).
    5. **Coherence check (spec §5.3):** if non-empty AND ``filledQuantity``
       is present AND ``abs(sum(legs.quantity) - filledQuantity) >= 1e-9``
       → log WARNING (with order_id + observed sum + filledQuantity) +
       collapse to ``None``. Otherwise return the collected list.
    6. ``filledQuantity`` absent: permissive — treat legs as authoritative;
       no coherence check fires.

    Plan-author lock (plan §A.1.3): ``filled_quantity`` is NOT added to
    SchwabOrderResponse — derived implicitly at mapper coherence-check time
    + discarded. Comparator uses ``_resolve_match_quantity`` for
    ``sum(legs.quantity)`` (T-1.5). Minimizes dataclass surface area +
    preserves 8-positional backward compat.
    """
    activities = _opt(raw, "orderActivityCollection")
    if not isinstance(activities, list) or not activities:
        return None

    filled_qty_raw = _opt(raw, "filledQuantity")
    try:
        filled_qty: float | None = (
            float(filled_qty_raw) if filled_qty_raw is not None else None
        )
    except (TypeError, ValueError):
        filled_qty = None

    collected: list[SchwabExecutionLeg] = []
    for ai, activity in enumerate(activities):
        if not isinstance(activity, dict):
            _log.warning(
                "map_orders_to_fill_candidates: order %s activity[%d] "
                "non-dict (%s); skipping",
                order_id, ai, type(activity).__name__,
            )
            continue
        if activity.get("activityType") != "EXECUTION":
            # Silent skip for non-EXECUTION (ORDER_ACTION etc.) — Schwab
            # emits these for cancel / replace events that are not
            # execution-grain data.
            continue
        legs = activity.get("executionLegs", [])
        if not isinstance(legs, list):
            _log.warning(
                "map_orders_to_fill_candidates: order %s activity[%d] "
                "executionLegs non-list (%s); skipping",
                order_id, ai, type(legs).__name__,
            )
            continue
        for li, leg_raw in enumerate(legs):
            if not isinstance(leg_raw, dict):
                _log.warning(
                    "map_orders_to_fill_candidates: order %s "
                    "activity[%d].executionLegs[%d] non-dict (%s); skipping",
                    order_id, ai, li, type(leg_raw).__name__,
                )
                continue
            # Codex R1 Major #2 fix — preserve dataclass bool-as-number
            # rejection contract. `float(True)` / `int(True)` would slip
            # past `SchwabExecutionLeg.__post_init__`'s `isinstance(x, bool)`
            # guard, so reject bool inputs BEFORE coercion (mapper-layer
            # defense-in-depth mirroring the spec §4.3 dataclass validator
            # contract). Booleans here are extraordinarily unlikely in
            # Schwab production responses (numeric fields are always
            # numbers), but the project's pattern is to keep the validator
            # contract honest end-to-end.
            raw_leg_id = leg_raw.get("legId", 0)
            raw_price = leg_raw.get("price", 0)
            raw_quantity = leg_raw.get("quantity", 0)
            raw_mismarked = leg_raw.get("mismarkedQuantity")
            raw_instrument_id = leg_raw.get("instrumentId")
            if (
                isinstance(raw_leg_id, bool)
                or isinstance(raw_price, bool)
                or isinstance(raw_quantity, bool)
                or (raw_mismarked is not None and isinstance(raw_mismarked, bool))
                or (
                    raw_instrument_id is not None
                    and isinstance(raw_instrument_id, bool)
                )
            ):
                _log.warning(
                    "map_orders_to_fill_candidates: order %s "
                    "activity[%d].executionLegs[%d] carries bool-as-number "
                    "field (defense-in-depth reject pre-coercion); dropping leg",
                    order_id, ai, li,
                )
                continue
            try:
                leg = SchwabExecutionLeg(
                    leg_id=int(raw_leg_id),
                    price=float(raw_price),
                    quantity=float(raw_quantity),
                    mismarked_quantity=(
                        float(raw_mismarked) if raw_mismarked is not None else None
                    ),
                    instrument_id=(
                        int(raw_instrument_id)
                        if raw_instrument_id is not None
                        else None
                    ),
                    time=str(leg_raw.get("time", "")),
                )
            except (ValueError, TypeError) as exc:
                # Defense-in-depth per spec §4.3 — dataclass validator
                # rejected the leg shape. Drop + warn; remaining legs may
                # still surface.
                _log.warning(
                    "map_orders_to_fill_candidates: order %s "
                    "activity[%d].executionLegs[%d] failed validator (%s); "
                    "dropping leg",
                    order_id, ai, li, type(exc).__name__,
                )
                continue
            collected.append(leg)

    if not collected:
        return None

    # Coherence check (spec §5.3): if filledQuantity present + legs sum
    # diverges, collapse to None + warn. Comparator's Path B branch then
    # emits unmatched_*_fill with execution_unavailable=true sentinel
    # rather than auto-correcting from potentially-malformed leg data.
    if filled_qty is not None:
        legs_sum = sum(leg.quantity for leg in collected)
        if abs(legs_sum - filled_qty) >= 1e-9:
            _log.warning(
                "map_orders_to_fill_candidates: order %s coherence-check "
                "failed: sum(legs.quantity)=%g != filledQuantity=%g; "
                "collapsing executions=None",
                order_id, legs_sum, filled_qty,
            )
            return None

    return collected


def map_transactions_to_cash_movement_candidates(
    response: Any,
) -> list[SchwabTransactionResponse]:
    """Map `Client.transactions(...)` response → list of SchwabTransactionResponse.

    Schwab returns a list of transaction dicts. V1 emits cash-movement-related
    types (ACH_*, CASH_*, WIRE_*, JOURNAL, ELECTRONIC_FUND) + TRADE for
    fill matching; mapper preserves ALL types (consumer at T-B.4 filters).

    Empty list returned for "no transactions in period" (production state).

    Per `api-calls.md` L258 + Schwab Developer Portal transaction schema.
    Mapper extracts: transactionId / transactionDate / type / netAmount /
    description.
    """
    if response is None:
        return []
    if not isinstance(response, list):
        raise SchwabSchemaParityError(
            f"transactions: expected list, got {type(response).__name__}"
        )

    out: list[SchwabTransactionResponse] = []
    for i, raw in enumerate(response):
        if not isinstance(raw, dict):
            raise SchwabSchemaParityError(
                f"transactions[{i}]: expected dict, got {type(raw).__name__}"
            )
        tx_id_raw = _opt(raw, "transactionId") or _opt(raw, "activityId")
        if tx_id_raw is None:
            raise SchwabSchemaParityError(
                f"transactions[{i}]: missing transactionId/activityId"
            )

        tx_date_raw = (
            _opt(raw, "transactionDate")
            or _opt(raw, "tradeDate")
            or _opt(raw, "settlementDate")
        )
        if not isinstance(tx_date_raw, str) or not tx_date_raw:
            raise SchwabSchemaParityError(
                f"transactions[{i}]: missing transactionDate"
            )
        # Normalize to ISO date (first 10 chars of ISO datetime).
        tx_date = tx_date_raw[:10]

        tx_type = _opt(raw, "type", "")
        if not isinstance(tx_type, str) or not tx_type:
            raise SchwabSchemaParityError(
                f"transactions[{i}]: missing or empty type"
            )

        net_amt_raw = _opt(raw, "netAmount", 0)
        try:
            net_amount = float(net_amt_raw)
        except (TypeError, ValueError) as exc:
            raise SchwabSchemaParityError(
                f"transactions[{i}]: netAmount not numeric: {net_amt_raw!r}"
            ) from exc

        description = _opt(raw, "description")

        out.append(SchwabTransactionResponse(
            transaction_id=str(tx_id_raw),
            transaction_date=tx_date,
            type=tx_type,
            net_amount=net_amount,
            description=description,
        ))
    return out


def _coerce_quote_time(raw: Any) -> str:
    """Convert Schwab quote-time field to ISO string.

    Schwab returns `quoteTimeInLong` (epoch ms int) OR `quoteTime` (ISO string)
    depending on field selection. Defensive dual-form support:
      - int → format as ISO ms in UTC.
      - str → pass through unchanged.
      - None → empty string (mapper-tolerant; validator allows empty str).
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        try:
            dt = datetime.fromtimestamp(float(raw) / 1000.0, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return str(raw)
        ms = f"{dt.microsecond // 1000:03d}"
        return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{ms}Z"
    return str(raw)


def map_quotes_to_price_cache_entries(
    response: Any,
) -> dict[str, SchwabQuoteResponse]:
    """Map `Client.quotes(symbols=...)` response → dict[symbol, SchwabQuoteResponse].

    Per plan §E.3 + §E.4 + T-C.0.b recon §3.2. Schwab returns a dict keyed by
    symbol; some symbols may resolve to error envelopes rather than quote
    shapes (partial-response handling per spec §3.8.6).

    Mapper splits the response:
      - For each input symbol with a fully-populated quote shape (lastPrice
        / bidPrice / askPrice or snake_case equivalents) → emit
        `SchwabQuoteResponse`. Tolerates BOTH nested `{symbol: {quote: {...}}}`
        AND flat `{symbol: {lastPrice, ...}}` per recon §3.2 defensive dual
        lookup.
      - For each input symbol with an error envelope (`errors`/`error`/`fault`
        top-level keys) OR symbol-absent → DO NOT emit; symbol marked for
        yfinance fallback at the ladder layer.

    Returns the successfully-mapped subset (dict, possibly empty).

    Raises `SchwabSchemaParityError` only if the TOP-LEVEL response is not a
    dict — per-symbol parity errors are tolerated (logged + dropped).

    Audit-row composition (caller's responsibility): the caller (marketdata.py
    `get_quotes_batch`) inspects the mapper's return value vs the requested
    symbol set + composes the error_message excerpt + sets audit status to
    'success' if any symbol mapped, 'error' if all failed.
    """
    if response is None:
        return {}
    if not isinstance(response, dict):
        raise SchwabSchemaParityError(
            f"quotes: expected dict, got {type(response).__name__}"
        )

    def _looks_like_error_envelope(d: Any) -> bool:
        return isinstance(d, dict) and any(
            k in d for k in ("errors", "error", "fault")
        )

    out: dict[str, SchwabQuoteResponse] = {}
    for symbol, payload in response.items():
        if not isinstance(symbol, str) or not symbol:
            continue
        if not isinstance(payload, dict):
            _log.warning(
                "map_quotes_to_price_cache_entries: dropping %s "
                "(non-dict payload: %s)",
                symbol, type(payload).__name__,
            )
            continue
        # Error envelope short-circuit — Schwab partial-response per spec §E.4.
        # Check the OUTER payload first (some Schwab variants put errors under
        # the symbol key directly).
        if _looks_like_error_envelope(payload):
            _log.info(
                "map_quotes_to_price_cache_entries: dropping %s "
                "(error envelope)",
                symbol,
            )
            continue

        # Dual-form support: nested `{quote: {...}}` OR flat.
        body = payload.get("quote") if isinstance(payload.get("quote"), dict) else payload
        # Defensive: nested form may carry the error envelope under `quote`.
        if _looks_like_error_envelope(body):
            _log.info(
                "map_quotes_to_price_cache_entries: dropping %s "
                "(nested error envelope)",
                symbol,
            )
            continue

        # Defensive dual-lookup per recon §3.2 — camelCase Schwab convention
        # primary, snake_case alternates accepted for forward-compat.
        last_price = body.get("lastPrice")
        if last_price is None:
            last_price = body.get("last_price")
        bid = body.get("bidPrice")
        if bid is None:
            bid = body.get("bid")
        ask = body.get("askPrice")
        if ask is None:
            ask = body.get("ask")
        mark = body.get("mark")
        quote_time_raw = (
            body.get("quoteTimeInLong")
            or body.get("quoteTime")
            or body.get("quote_time")
        )
        delayed_raw = body.get("delayed")

        # Tolerate absent fields by dropping the symbol — partial response.
        if last_price is None or bid is None or ask is None:
            _log.info(
                "map_quotes_to_price_cache_entries: dropping %s "
                "(missing last/bid/ask)",
                symbol,
            )
            continue

        try:
            entry = SchwabQuoteResponse(
                symbol=str(symbol),
                last_price=float(last_price),
                bid=float(bid),
                ask=float(ask),
                mark=float(mark) if mark is not None else None,
                quote_time=_coerce_quote_time(quote_time_raw),
                delayed=bool(delayed_raw) if delayed_raw is not None else False,
            )
        except (ValueError, TypeError) as exc:
            _log.warning(
                "map_quotes_to_price_cache_entries: dropping %s "
                "(__post_init__ rejected: %s)",
                symbol, type(exc).__name__,
            )
            continue
        out[str(symbol)] = entry
    return out


def map_price_history_to_window(
    response: Any, ticker: str,
) -> SchwabPriceHistoryWindow:
    """Map `Client.price_history(...)` response → SchwabPriceHistoryWindow (T-C.1).

    Per plan §E.3 + §E.5 + §H.6.4 + recon §3.3. Schwab returns a dict with
    shape `{"candles": [...], "symbol": ..., "empty": bool}` per
    `reference/schwabdev/api-calls.md` L437.

    **Dual empty-signal check** per recon §3.3 + spec §H.6.4 defense-in-depth:
    if `len(candles) == 0` OR `response['empty'] is True` → raise synthetic
    `SchwabApiError(status_code=204, body_excerpt='empty bars')`. The 204 code
    is a project-internal sentinel ("no content"); the real HTTP status is
    typically 200. Caller (ladder) catches + records audit `status='error'`
    + falls back to yfinance per CLAUDE.md gotcha "External-API empty-result
    must be treated as transient".

    Per-bar mapping (each candle dict):
      open/high/low/close: float.
      volume: int.
      datetime: epoch ms → ISO date (UTC) for `OhlcvBar.asof_date`.

    Bars sorted by asof_date ascending (Schwab returns oldest-first; we
    enforce defensively via Python sort).

    Raises:
      SchwabApiError(204, 'empty bars'): empty signal.
      SchwabSchemaParityError: top-level shape diverges.
      ValueError / TypeError: per-bar invariant violation (propagated from
        OhlcvBar.__post_init__ — caller's audit-error path catches).
    """
    if not isinstance(ticker, str) or not ticker:
        raise SchwabSchemaParityError(
            "price_history: ticker arg must be non-empty str"
        )
    if not isinstance(response, dict):
        raise SchwabSchemaParityError(
            f"price_history: expected dict, got {type(response).__name__}"
        )

    candles = response.get("candles", [])
    # Codex R1 Minor #2: `bool(...)` would treat "false" / 0 / "anything"
    # as truthy/falsy by Python coercion rules; only the JSON-boolean true
    # should trigger the empty-flag path. Use explicit identity check.
    empty_flag = response.get("empty") is True

    if not isinstance(candles, list):
        raise SchwabSchemaParityError(
            f"price_history: 'candles' must be list, "
            f"got {type(candles).__name__}"
        )

    # **Dual signal** — either empty=true OR no candles fires the transient
    # path. Spec §H.6.4 + recon §3.3 binding.
    if empty_flag or len(candles) == 0:
        raise SchwabApiError(204, "empty bars")

    bars: list[OhlcvBar] = []
    for i, c in enumerate(candles):
        if not isinstance(c, dict):
            raise SchwabSchemaParityError(
                f"price_history.candles[{i}]: expected dict, "
                f"got {type(c).__name__}"
            )
        try:
            dt_ms = c.get("datetime")
            if dt_ms is None:
                raise SchwabSchemaParityError(
                    f"price_history.candles[{i}]: missing 'datetime'"
                )
            try:
                asof_date = (
                    datetime.fromtimestamp(float(dt_ms) / 1000.0, tz=UTC)
                    .date()
                    .isoformat()
                )
            except (TypeError, ValueError, OverflowError, OSError) as exc:
                raise SchwabSchemaParityError(
                    f"price_history.candles[{i}]: invalid 'datetime' "
                    f"{dt_ms!r}: {type(exc).__name__}"
                ) from exc

            open_v = float(_require(c, "open", ctx=f"candles[{i}]"))
            high_v = float(_require(c, "high", ctx=f"candles[{i}]"))
            low_v = float(_require(c, "low", ctx=f"candles[{i}]"))
            close_v = float(_require(c, "close", ctx=f"candles[{i}]"))
            volume_raw = c.get("volume", 0)
            volume_v = int(volume_raw) if volume_raw is not None else 0
        except SchwabSchemaParityError:
            raise

        bars.append(OhlcvBar(
            asof_date=asof_date,
            open=open_v,
            high=high_v,
            low=low_v,
            close=close_v,
            volume=volume_v,
        ))

    # Defensive sort — Schwab returns oldest-first but we enforce.
    bars.sort(key=lambda b: b.asof_date)
    return SchwabPriceHistoryWindow(
        ticker=ticker,
        bars=bars,
        provider="schwab_api",
    )


__all__ = [
    "map_account_details_to_equity_snapshot_inputs",
    "map_account_linked_to_hash_set",
    "map_orders_to_fill_candidates",
    "map_price_history_to_window",
    "map_quotes_to_price_cache_entries",
    "map_transactions_to_cash_movement_candidates",
]
