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

from typing import Any

from swing.integrations.schwab.client import SchwabSchemaParityError
from swing.integrations.schwab.models import (
    SchwabAccountResponse,
    SchwabOrderResponse,
    SchwabTransactionResponse,
)


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

        out.append(SchwabOrderResponse(
            order_id=order_id,
            status=status,
            enter_time=entered_time,
            instrument_symbol=str(symbol),
            instruction=instruction,
            quantity=quantity,
            order_type=order_type,
            price=price,
        ))
    return out


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


__all__ = [
    "map_account_details_to_equity_snapshot_inputs",
    "map_account_linked_to_hash_set",
    "map_orders_to_fill_candidates",
    "map_transactions_to_cash_movement_candidates",
]
