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


@dataclass(frozen=True)
class SchwabQuoteResponse:
    """Mapped single-symbol quote payload from `Client.quotes(...)` (T-C.1).

    Per plan §E.3 + §H.7. Schwab returns a dict keyed by symbol; each entry
    carries last/bid/ask/mark + a quote-as-of timestamp + a delayed flag.

    Fields:
      symbol: ticker symbol (e.g., 'AAPL').
      last_price: primary consumed field; written to PriceCache via ladder.
      bid: best bid at quote_time.
      ask: best ask at quote_time.
      mark: midpoint or Schwab-computed mark; may be None.
      quote_time: ISO ms string (mapper converts from `quoteTimeInLong` epoch
        ms OR `quoteTime` ISO string).
      delayed: informational; default-tier accounts receive 15-min-delayed
        quotes per spec §A.1 Q12 default disposition.
    """

    symbol: str
    last_price: float
    bid: float
    ask: float
    mark: float | None
    quote_time: str
    delayed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(
                "SchwabQuoteResponse.symbol must be non-empty str"
            )
        if not isinstance(self.last_price, (int, float)) or isinstance(
            self.last_price, bool,
        ):
            raise ValueError(
                f"SchwabQuoteResponse.last_price must be number; "
                f"got {type(self.last_price).__name__}"
            )
        if not math.isfinite(float(self.last_price)):
            raise ValueError(
                f"SchwabQuoteResponse.last_price must be finite (not "
                f"NaN/inf); got {self.last_price!r}"
            )
        if self.last_price < 0:
            raise ValueError(
                f"SchwabQuoteResponse.last_price must be >= 0; "
                f"got {self.last_price!r}"
            )
        for fname, fval in (("bid", self.bid), ("ask", self.ask)):
            if not isinstance(fval, (int, float)) or isinstance(fval, bool):
                raise ValueError(
                    f"SchwabQuoteResponse.{fname} must be number; "
                    f"got {type(fval).__name__}"
                )
            if not math.isfinite(float(fval)):
                raise ValueError(
                    f"SchwabQuoteResponse.{fname} must be finite (not "
                    f"NaN/inf); got {fval!r}"
                )
        if self.mark is not None:
            if not isinstance(self.mark, (int, float)) or isinstance(
                self.mark, bool,
            ):
                raise ValueError(
                    f"SchwabQuoteResponse.mark must be number or None; "
                    f"got {type(self.mark).__name__}"
                )
            if not math.isfinite(float(self.mark)):
                raise ValueError(
                    f"SchwabQuoteResponse.mark must be finite or None; "
                    f"got {self.mark!r}"
                )
        if not isinstance(self.quote_time, str):
            raise ValueError(
                "SchwabQuoteResponse.quote_time must be str"
            )
        if not isinstance(self.delayed, bool):
            raise ValueError(
                f"SchwabQuoteResponse.delayed must be bool; "
                f"got {type(self.delayed).__name__}"
            )


@dataclass(frozen=True)
class OhlcvBar:
    """Single daily/intraday OHLCV bar — mapped from one Schwab price_history
    candle (T-C.1).

    Per plan §H.7 row "SchwabPriceHistoryWindow per-bar invariants". `asof_date`
    is ISO date string (`YYYY-MM-DD`); mapper converts Schwab's `datetime`
    field (epoch ms) into ISO date in UTC.

    Invariants enforced at `__post_init__`:
      - `low <= min(open, close)` — Schwab data should always satisfy; reject
        if violated (signals a malformed candle / parser error).
      - `high >= max(open, close)` — same reasoning.
      - `volume >= 0` — defensive (Schwab uses 0 for no-trade bars).
      - all OHLC values finite (no NaN/inf).
    """

    asof_date: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    def __post_init__(self) -> None:
        if not isinstance(self.asof_date, str) or len(self.asof_date) < 10:
            raise ValueError(
                f"OhlcvBar.asof_date must be ISO date (YYYY-MM-DD or longer); "
                f"got {self.asof_date!r}"
            )
        for fname, fval in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
        ):
            if not isinstance(fval, (int, float)) or isinstance(fval, bool):
                raise ValueError(
                    f"OhlcvBar.{fname} must be number; "
                    f"got {type(fval).__name__}"
                )
            if not math.isfinite(float(fval)):
                raise ValueError(
                    f"OhlcvBar.{fname} must be finite (not NaN/inf); "
                    f"got {fval!r}"
                )
        if not isinstance(self.volume, (int, float)) or isinstance(
            self.volume, bool,
        ):
            raise ValueError(
                f"OhlcvBar.volume must be number; "
                f"got {type(self.volume).__name__}"
            )
        if self.volume < 0:
            raise ValueError(
                f"OhlcvBar.volume must be >= 0; got {self.volume!r}"
            )
        # Per-bar invariants: low ≤ min(open, close); high ≥ max(open, close).
        oc_min = min(self.open, self.close)
        oc_max = max(self.open, self.close)
        if self.low > oc_min:
            raise ValueError(
                f"OhlcvBar invariant violated: low ({self.low}) must be "
                f"<= min(open, close) ({oc_min}); date={self.asof_date}"
            )
        if self.high < oc_max:
            raise ValueError(
                f"OhlcvBar invariant violated: high ({self.high}) must be "
                f">= max(open, close) ({oc_max}); date={self.asof_date}"
            )


@dataclass(frozen=True)
class SchwabPriceHistoryWindow:
    """Mapped price-history window from `Client.price_history(...)` (T-C.1).

    Per plan §E.3 + §H.7. Carries the full bars list + ticker + provider tag.
    Provider is hardcoded to `'schwab_api'` for instances emitted by this
    mapper (distinguishes from yfinance-fallback path at the ladder layer).

    Invariants:
      - bars sorted by asof_date ascending (mapper enforces; validator pins).
      - each bar passes OhlcvBar's __post_init__.
      - provider non-empty (validator pins).
    """

    ticker: str
    bars: list[OhlcvBar] = field(default_factory=list)
    provider: str = "schwab_api"

    def __post_init__(self) -> None:
        if not isinstance(self.ticker, str) or not self.ticker:
            raise ValueError(
                "SchwabPriceHistoryWindow.ticker must be non-empty str"
            )
        if not isinstance(self.bars, list):
            raise ValueError(
                f"SchwabPriceHistoryWindow.bars must be list; "
                f"got {type(self.bars).__name__}"
            )
        if not isinstance(self.provider, str) or not self.provider:
            raise ValueError(
                "SchwabPriceHistoryWindow.provider must be non-empty str"
            )
        # bars sorted by asof_date ascending.
        prior: str | None = None
        for bar in self.bars:
            if not isinstance(bar, OhlcvBar):
                raise ValueError(
                    f"SchwabPriceHistoryWindow.bars must contain OhlcvBar; "
                    f"got {type(bar).__name__}"
                )
            if prior is not None and bar.asof_date < prior:
                raise ValueError(
                    f"SchwabPriceHistoryWindow.bars must be sorted by "
                    f"asof_date ascending; saw {prior!r} before "
                    f"{bar.asof_date!r}"
                )
            prior = bar.asof_date

    def to_dataframe(self):
        """Convert bars to a DataFrame matching the legacy yfinance in-memory
        shape consumed by the OHLCV cache + chart-step downstream code.

        Returns a DataFrame with:
          - DatetimeIndex (named ``Date``) parsed from ``OhlcvBar.asof_date``;
          - CAPITALIZED OHLCV columns (``Open``/``High``/``Low``/``Close``/
            ``Volume``) matching what ``swing/pipeline/ohlcv.py:compute_smas``
            and ``swing/web/ohlcv_cache.py`` consume from the legacy
            ``_yf_download_window`` shape.

        This is the in-memory shape, NOT the Shape A on-disk shape. Use
        ``swing.integrations.schwab.marketdata_ladder._schwab_window_to_shape_a_df``
        (or the inline equivalent in the ladder) when persisting via
        ``swing.data.ohlcv_archive.write_window``.

        Codex R1 Major #4: previously the OhlcvCache ladder hook called
        ``window.to_dataframe()`` but this method did not exist, breaking
        the Schwab success path in ``swing/pipeline/runner.py:_bars_hook``.
        Empty bars list → empty DataFrame with the canonical column set
        (defensive; mapper raises before this for empty Schwab responses).
        """
        import pandas as pd  # lazy: keep models.py lightweight

        if not self.bars:
            return pd.DataFrame(
                columns=["Open", "High", "Low", "Close", "Volume"],
            )

        idx = pd.to_datetime([bar.asof_date for bar in self.bars])
        idx.name = "Date"
        return pd.DataFrame(
            {
                "Open": [bar.open for bar in self.bars],
                "High": [bar.high for bar in self.bars],
                "Low": [bar.low for bar in self.bars],
                "Close": [bar.close for bar in self.bars],
                "Volume": [bar.volume for bar in self.bars],
            },
            index=idx,
        )


__all__ = [
    "OhlcvBar",
    "SchwabAccountResponse",
    "SchwabOrderResponse",
    "SchwabPriceHistoryWindow",
    "SchwabQuoteResponse",
    "SchwabTransactionResponse",
    "_SCHWAB_ORDER_INSTRUCTIONS",
    "_SCHWAB_ORDER_STATUSES",
    "_SCHWAB_ORDER_TYPES",
    "_SCHWAB_TRANSACTION_TYPES",
]
