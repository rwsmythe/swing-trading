"""Schwab API in-memory response dataclasses (Phase 11 Sub-bundle B T-B.1).

These dataclasses model the SHAPE of mapped Schwab API responses BEFORE
they are folded into project domain rows (account_equity_snapshots,
reconciliation_runs, etc.). They are NOT persisted to the DB — the
persisted shapes live in `swing/data/models.py` (e.g., `SchwabApiCall`
audit-row dataclass).

Per plan §H.7 + §A.9 #1: every new dataclass has a `__post_init__`
validator rejecting invalid input at construction time. The Sub-bundle B
mappers at `mappers.py` raise `SchwabSchemaParityError` (with redacted
message) on shape errors BEFORE constructing the dataclass; the dataclass
validators are defense-in-depth on top.

Enums per plan §H.7 + T-B.0.b recon doc §3 (widened from plan §E.2's
synthesized 5-value subset to the documented 21-value set per
`reference/schwabdev/api-calls.md` L124 + the `WAIT_TRG` observed in
Phase 9 Sub-bundle E real-world fixtures = 22 total).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# Per `reference/schwabdev/api-calls.md` L124 + Phase 9 Sub-bundle E
# real-world fixture observation: WAIT_TRG (placed-but-not-yet-armed
# conditional). 22-value set.
_SCHWAB_ORDER_STATUSES = frozenset({
    "AWAITING_PARENT_ORDER", "AWAITING_CONDITION", "AWAITING_STOP_CONDITION",
    "AWAITING_MANUAL_REVIEW", "ACCEPTED", "AWAITING_UR_OUT", "PENDING_ACTIVATION",
    "QUEUED", "WORKING", "REJECTED", "PENDING_CANCEL", "CANCELED",
    "PENDING_REPLACE", "REPLACED", "FILLED", "EXPIRED", "NEW",
    "AWAITING_RELEASE_TIME", "PENDING_ACKNOWLEDGEMENT", "PENDING_RECALL",
    "UNKNOWN",
    "WAIT_TRG",  # observed in real-world fixtures (Phase 9 Sub-bundle E)
})


# Per `reference/schwabdev/orders.md` documented instruction enum.
_SCHWAB_ORDER_INSTRUCTIONS = frozenset({
    "BUY", "SELL",
    "BUY_TO_OPEN", "BUY_TO_CLOSE",
    "SELL_TO_OPEN", "SELL_TO_CLOSE",
    "BUY_TO_COVER", "SELL_SHORT",
    # Empty string occurs when schwabdev passes through Schwab's
    # response without an instruction — defensive accept-with-warning
    # at mapper layer; validator rejects empty here (mapper handles).
})


# Per `reference/schwabdev/orders.md` documented order_type enum.
_SCHWAB_ORDER_TYPES = frozenset({
    "MARKET", "LIMIT", "STOP", "STOP_LIMIT",
    "TRAILING_STOP", "TRAILING_STOP_LIMIT",
    "MARKET_ON_CLOSE", "LIMIT_ON_CLOSE",
    "CABINET", "NON_MARKETABLE",
    "NET_DEBIT", "NET_CREDIT", "NET_ZERO",
    "EXERCISE",
})


# Per `reference/schwabdev/api-calls.md` L256. The 15 V1 documented values.
_SCHWAB_TRANSACTION_TYPES = frozenset({
    "TRADE", "RECEIVE_AND_DELIVER", "DIVIDEND_OR_INTEREST",
    "ACH_RECEIPT", "ACH_DISBURSEMENT",
    "CASH_RECEIPT", "CASH_DISBURSEMENT",
    "ELECTRONIC_FUND", "WIRE_OUT", "WIRE_IN",
    "JOURNAL", "MEMORANDUM", "MARGIN_CALL",
    "MONEY_MARKET", "SMA_ADJUSTMENT",
    # `TRADE_CORRECTION` added for defense-in-depth (Schwab Developer
    # Portal documents it; reference is silent — accept on read but do
    # not request).
    "TRADE_CORRECTION",
})


@dataclass(frozen=True)
class SchwabAccountResponse:
    """Mapped Schwab account-details payload (`Client.account_details(...)`).

    Per plan §E.2 dataclass spec + T-B.0.b recon §3.

    Fields:
      account_hash: operator's encrypted account identifier.
      net_liquidating_value: primary consumed field; written as
        `equity_dollars` via Phase 9 Sub-bundle C `record_snapshot()`.
      cash: V1 informational.
      buying_power: V1 informational; may be negative for margin.
      positions: opaque V1 (list of dicts); passed to reconciliation
        for position_qty_mismatch checks at T-B.4.
      recorded_at: server-stamped ISO ms at construction.
    """

    account_hash: str
    net_liquidating_value: float
    cash: float
    buying_power: float
    positions: list = field(default_factory=list)
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.account_hash, str) or not self.account_hash:
            raise ValueError(
                "SchwabAccountResponse.account_hash must be non-empty str"
            )
        for fname, fval in (
            ("net_liquidating_value", self.net_liquidating_value),
            ("cash", self.cash),
            ("buying_power", self.buying_power),
        ):
            if not isinstance(fval, (int, float)) or isinstance(fval, bool):
                raise ValueError(
                    f"SchwabAccountResponse.{fname} must be finite number; "
                    f"got {type(fval).__name__}"
                )
            if not math.isfinite(float(fval)):
                raise ValueError(
                    f"SchwabAccountResponse.{fname} must be finite (not "
                    f"NaN/inf); got {fval!r}"
                )
        if not isinstance(self.positions, list):
            raise ValueError(
                f"SchwabAccountResponse.positions must be list; "
                f"got {type(self.positions).__name__}"
            )
        if not isinstance(self.recorded_at, str):
            raise ValueError(
                "SchwabAccountResponse.recorded_at must be str"
            )


@dataclass(frozen=True)
class SchwabOrderResponse:
    """Mapped single-order payload from `Client.account_orders(...)`.

    Per plan §E.2 + T-B.0.b recon §3.3 + §3.4 enum widening.
    """

    order_id: str
    status: str
    enter_time: str
    instrument_symbol: str
    instruction: str
    quantity: float
    order_type: str
    price: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, str) or not self.order_id:
            raise ValueError(
                "SchwabOrderResponse.order_id must be non-empty str"
            )
        if self.status not in _SCHWAB_ORDER_STATUSES:
            raise ValueError(
                f"SchwabOrderResponse.status must be in "
                f"{sorted(_SCHWAB_ORDER_STATUSES)[:5]}... ({len(_SCHWAB_ORDER_STATUSES)} total); "
                f"got {self.status!r}"
            )
        # Instruction may be empty in non-leg-bearing orders; allow blank
        # but reject other unknown values defensively.
        if (
            self.instruction
            and self.instruction not in _SCHWAB_ORDER_INSTRUCTIONS
        ):
            raise ValueError(
                f"SchwabOrderResponse.instruction must be empty or in "
                f"{sorted(_SCHWAB_ORDER_INSTRUCTIONS)[:5]}...; "
                f"got {self.instruction!r}"
            )
        if (
            self.order_type
            and self.order_type not in _SCHWAB_ORDER_TYPES
        ):
            raise ValueError(
                f"SchwabOrderResponse.order_type must be empty or in "
                f"{sorted(_SCHWAB_ORDER_TYPES)[:5]}...; "
                f"got {self.order_type!r}"
            )
        if not isinstance(self.quantity, (int, float)) or isinstance(
            self.quantity, bool,
        ):
            raise ValueError(
                f"SchwabOrderResponse.quantity must be number; "
                f"got {type(self.quantity).__name__}"
            )
        if not math.isfinite(float(self.quantity)) or self.quantity < 0:
            raise ValueError(
                f"SchwabOrderResponse.quantity must be non-negative finite; "
                f"got {self.quantity!r}"
            )
        if self.price is not None:
            if not isinstance(self.price, (int, float)) or isinstance(
                self.price, bool,
            ):
                raise ValueError(
                    f"SchwabOrderResponse.price must be number or None; "
                    f"got {type(self.price).__name__}"
                )
            if not math.isfinite(float(self.price)) or self.price < 0:
                raise ValueError(
                    f"SchwabOrderResponse.price must be non-negative finite; "
                    f"got {self.price!r}"
                )


@dataclass(frozen=True)
class SchwabTransactionResponse:
    """Mapped single-transaction payload from `Client.transactions(...)`.

    Per plan §E.2 + T-B.0.b recon §3.2.
    """

    transaction_id: str
    transaction_date: str  # ISO date YYYY-MM-DD
    type: str
    net_amount: float
    description: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.transaction_id, str) or not self.transaction_id:
            raise ValueError(
                "SchwabTransactionResponse.transaction_id must be non-empty str"
            )
        if not isinstance(self.transaction_date, str) or len(self.transaction_date) < 10:
            raise ValueError(
                f"SchwabTransactionResponse.transaction_date must be ISO date "
                f"(YYYY-MM-DD or longer); got {self.transaction_date!r}"
            )
        if self.type not in _SCHWAB_TRANSACTION_TYPES:
            raise ValueError(
                f"SchwabTransactionResponse.type must be in "
                f"{sorted(_SCHWAB_TRANSACTION_TYPES)[:5]}... "
                f"({len(_SCHWAB_TRANSACTION_TYPES)} total); got {self.type!r}"
            )
        if not isinstance(self.net_amount, (int, float)) or isinstance(
            self.net_amount, bool,
        ):
            raise ValueError(
                f"SchwabTransactionResponse.net_amount must be number; "
                f"got {type(self.net_amount).__name__}"
            )
        if not math.isfinite(float(self.net_amount)):
            raise ValueError(
                f"SchwabTransactionResponse.net_amount must be finite; "
                f"got {self.net_amount!r}"
            )
        if self.description is not None and not isinstance(self.description, str):
            raise ValueError(
                f"SchwabTransactionResponse.description must be str or None; "
                f"got {type(self.description).__name__}"
            )


__all__ = [
    "SchwabAccountResponse",
    "SchwabOrderResponse",
    "SchwabTransactionResponse",
    "_SCHWAB_ORDER_INSTRUCTIONS",
    "_SCHWAB_ORDER_STATUSES",
    "_SCHWAB_ORDER_TYPES",
    "_SCHWAB_TRANSACTION_TYPES",
]
