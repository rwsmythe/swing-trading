# Schwabdev API Call Methods

**Source URL:** https://tylerebowers.github.io/Schwabdev/pages/api.html
**Library:** schwabdev — Python wrapper around the Schwab Trader API
**Extraction date:** 2026-05-13
**Companion specs:** `reference/schwab-api/account-specification.md` (13 trader endpoints), `reference/schwab-api/market-data-specification.md` (10 market-data endpoints)
**Cross-reference role:** This file is the **primary integration surface** for swing-trading hookup — every method here maps directly to a Schwab REST endpoint already captured in the companion specs.

---

## General Notes (verbatim from source)

- **API Keys:** Requires both "Accounts and Trading Production" and "Market Data Production" APIs enabled on the Schwab developer account.
- **Response Format:** All methods return `requests.Response`. Check `.ok` (boolean for 200-range codes) and call `.json()` to extract the response body.
- **Rate Limit:** Maximum **120 API requests per minute** (applies wrapper-wide).
- **Datetime Format:** Accepts both Python `datetime` objects and ISO-format strings (`yyyy-MM-dd'T'HH:mm:ss.SSSZ` for timestamps, `yyyy-MM-dd` for date-only).
- **Lists/Strings:** Accepts comma-separated strings OR Python list objects (e.g., `"AAPL,AMD"` or `["AAPL", "AMD"]`).
- **Streaming Advisory:** For continuous market data, use the streaming service instead of looping API endpoints. The `quotes()`, `quote()`, and `price_history()` methods carry an explicit "do NOT use in loops" warning.

> **Auth note (operator-flagged):** The source page does NOT document per-endpoint OAuth scope requirements or special auth-header behavior at the wrapper level. The wrapper attaches authentication uniformly to every call (token management is handled by the `Client` constructor / authentication flow, documented elsewhere). The only auth-adjacent guidance on this page is the API-key enablement note above and the wrapper-wide 120 req/min rate limit. Per-endpoint rate-limit notes that DO appear are captured verbatim under the affected methods (Orders: `place_order`; Quotes: `quotes`/`quote`; Price History: `price_history`).

---

## Overview Table

| Method | Wraps endpoint | Returns |
| --- | --- | --- |
| `linked_accounts()` | GET /accounts/linkedaccounts | `requests.Response` (list of `{accountNumber, hashValue}`) |
| `account_details_all(fields=None)` | GET /accounts | `requests.Response` (list of account dicts) |
| `account_details(account_hash, fields=None)` | GET /accounts/{accountHash} | `requests.Response` (single account dict) |
| `account_orders(account_hash, from_entered_time, to_entered_time, max_results=None, status=None)` | GET /accounts/{accountHash}/orders | `requests.Response` (list of orders) |
| `account_orders_all(from_entered_time, to_entered_time, max_results=None, status=None)` | GET /orders | `requests.Response` (list of orders across all linked accounts) |
| `place_order(account_hash, order)` | POST /accounts/{accountHash}/orders | `requests.Response`; order ID via `resp.headers['location']` |
| `order_details(account_hash, order_id)` | GET /accounts/{accountHash}/orders/{orderId} | `requests.Response` (single order dict) |
| `cancel_order(account_hash, order_id)` | DELETE /accounts/{accountHash}/orders/{orderId} | `requests.Response` (empty on success) |
| `replace_order(account_hash, order_id, order)` | PUT /accounts/{accountHash}/orders/{orderId} | `requests.Response` |
| `preview_order(account_hash, order)` | POST /accounts/{accountHash}/previewOrder | `requests.Response` (preview JSON) |
| `transactions(account_hash, start_date, end_date, types, symbol=None)` | GET /accounts/{accountHash}/transactions | `requests.Response` (list of transactions) |
| `transaction_details(account_hash, transaction_id)` | GET /accounts/{accountHash}/transactions/{transactionId} | `requests.Response` (single transaction) |
| `preferences()` | GET /userpreference/streamersubscriptionkeys | `requests.Response` (user preference / streamer info) |
| `quotes(symbols=None, fields=None, indicative=False)` | GET /marketdata/quotes | `requests.Response` (dict keyed by symbol) |
| `quote(symbol_id, fields=None)` | GET /marketdata/quotes/{symbolId} | `requests.Response` (single symbol dict) |
| `option_chains(symbol, ...)` | GET /marketdata/chains | `requests.Response` (call/put exp date maps) |
| `option_expiration_chain(symbol)` | GET /marketdata/chains/expirations | `requests.Response` (list of expirations) |
| `price_history(symbol, ...)` | GET /marketdata/pricehistory | `requests.Response` (candles array) |
| `movers(symbol, sort=None, frequency=None)` | GET /marketdata/movers | `requests.Response` (screeners array) |
| `market_hours(symbols, date=None)` | GET /marketdata/hours | `requests.Response` (market hours keyed by market type) |
| `market_hour(market_id, date=None)` | GET /marketdata/hours/{marketId} | `requests.Response` (single market type hours) |
| `instruments(symbol, projection)` | GET /instruments | `requests.Response` (instruments array) |
| `instrument_cusip(cusip_id)` | GET /instruments | `requests.Response` (instruments array matching CUSIP) |

**Method count:** 23 wrapper methods mapping to 23 Schwab REST endpoints (matches 13 trader + 10 market-data total).

---

## Accounts

### `linked_accounts()`

Wraps **GET /accounts/linkedaccounts**.

```python
client.linked_accounts()
```

| Param | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |

(No parameters.)

**Returns:** `requests.Response`. JSON body is a list of dicts with `accountNumber` and `hashValue`. The `hashValue` is the `account_hash` consumed by every other per-account endpoint.

---

### `account_details_all(fields=None)`

Wraps **GET /accounts**.

```python
client.account_details_all(fields=None)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `fields` | `str \| None` | `None` | No | Optional field expansion | `"positions"` to include current positions |

**Returns:** `requests.Response`. JSON body is a list of account detail dicts (one per linked account).

---

### `account_details(account_hash, fields=None)`

Wraps **GET /accounts/{accountHash}**.

```python
client.account_details(account_hash, fields=None)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `account_hash` | `str` | — | Yes | Account hash from `linked_accounts()` | — |
| `fields` | `str \| None` | `None` | No | Optional field expansion | `"positions"` to include current positions |

**Returns:** `requests.Response`. JSON body is a single account detail dict.

---

## Orders

### `account_orders(account_hash, from_entered_time, to_entered_time, max_results=None, status=None)`

Wraps **GET /accounts/{accountHash}/orders**.

```python
client.account_orders(account_hash, from_entered_time, to_entered_time, max_results=None, status=None)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `account_hash` | `str` | — | Yes | Account hash | — |
| `from_entered_time` | `datetime \| str` | — | Yes | Lower bound, inclusive. Format `yyyy-MM-dd'T'HH:mm:ss.SSSZ` | — |
| `to_entered_time` | `datetime \| str` | — | Yes | Upper bound. Same format | — |
| `max_results` | `int \| None` | `None` (server default 3000) | No | Cap on result count | — |
| `status` | `str \| None` | `None` | No | Filter by status | `AWAITING_PARENT_ORDER`, `AWAITING_CONDITION`, `AWAITING_STOP_CONDITION`, `AWAITING_MANUAL_REVIEW`, `ACCEPTED`, `AWAITING_UR_OUT`, `PENDING_ACTIVATION`, `QUEUED`, `WORKING`, `REJECTED`, `PENDING_CANCEL`, `CANCELED`, `PENDING_REPLACE`, `REPLACED`, `FILLED`, `EXPIRED`, `NEW`, `AWAITING_RELEASE_TIME`, `PENDING_ACKNOWLEDGEMENT`, `PENDING_RECALL`, `UNKNOWN` |

**Returns:** `requests.Response`. JSON body is a list of order dicts for the specified account.

---

### `account_orders_all(from_entered_time, to_entered_time, max_results=None, status=None)`

Wraps **GET /orders**.

```python
client.account_orders_all(from_entered_time, to_entered_time, max_results=None, status=None)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `from_entered_time` | `datetime \| str` | — | Yes | Lower bound. Format `yyyy-MM-dd'T'HH:mm:ss.SSSZ` | — |
| `to_entered_time` | `datetime \| str` | — | Yes | Upper bound. Same format | — |
| `max_results` | `int \| None` | `None` (server default 3000) | No | Cap on result count | — |
| `status` | `str \| None` | `None` | No | Filter by status | Same set as `account_orders()` |

**Returns:** `requests.Response`. JSON body is a list of order dicts spanning ALL linked accounts.

---

### `place_order(account_hash, order)`

Wraps **POST /accounts/{accountHash}/orders**.

```python
client.place_order(account_hash, order)
```

| Param | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `account_hash` | `str` | — | Yes | Account hash |
| `order` | `dict` | — | Yes | Order payload (see Schwab orders documentation / `orders.md` for full schema) |

**Returns:** `requests.Response`. Order ID is **NOT** in the JSON body — it must be extracted from the `location` response header:

```python
order_id = resp.headers.get('location', '/').split('/')[-1]
```

**Rate limit (verbatim):** 120 requests/minute.

---

### `order_details(account_hash, order_id)`

Wraps **GET /accounts/{accountHash}/orders/{orderId}**.

```python
client.order_details(account_hash, order_id)
```

| Param | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `account_hash` | `str` | — | Yes | Account hash |
| `order_id` | `int` | — | Yes | Order ID |

**Returns:** `requests.Response`. JSON body is a single order detail dict.

---

### `cancel_order(account_hash, order_id)`

Wraps **DELETE /accounts/{accountHash}/orders/{orderId}**.

```python
client.cancel_order(account_hash, order_id)
```

| Param | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `account_hash` | `str` | — | Yes | Account hash |
| `order_id` | `int` | — | Yes | Order ID |

**Returns:** `requests.Response`. Typically empty body on success — rely on `.ok` / status code.

---

### `replace_order(account_hash, order_id, order)`

Wraps **PUT /accounts/{accountHash}/orders/{orderId}**.

```python
client.replace_order(account_hash, order_id, order)
```

| Param | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `account_hash` | `str` | — | Yes | Account hash |
| `order_id` | `int` | — | Yes | ID of order to replace |
| `order` | `dict` | — | Yes | New order payload (replaces existing) |

**Returns:** `requests.Response`.

---

### `preview_order(account_hash, order)`

Wraps **POST /accounts/{accountHash}/previewOrder**.

```python
client.preview_order(account_hash, order)
```

| Param | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `account_hash` | `str` | — | Yes | Account hash |
| `order` | `dict` | — | Yes | Order payload to preview (NOT submit) |

**Returns:** `requests.Response`. JSON body contains preview data — fees, validation messages, projected balances.

---

## Transactions

### `transactions(account_hash, start_date, end_date, types, symbol=None)`

Wraps **GET /accounts/{accountHash}/transactions**.

```python
client.transactions(account_hash, start_date, end_date, types, symbol=None)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `account_hash` | `str` | — | Yes | Account hash | — |
| `start_date` | `datetime \| str` | — | Yes | Lower bound. Format `yyyy-MM-dd'T'HH:mm:ss.SSSZ` | — |
| `end_date` | `datetime \| str` | — | Yes | Upper bound. Same format | — |
| `types` | `list \| str` | — | Yes | One or more transaction types | `TRADE`, `RECEIVE_AND_DELIVER`, `DIVIDEND_OR_INTEREST`, `ACH_RECEIPT`, `ACH_DISBURSEMENT`, `CASH_RECEIPT`, `CASH_DISBURSEMENT`, `ELECTRONIC_FUND`, `WIRE_OUT`, `WIRE_IN`, `JOURNAL`, `MEMORANDUM`, `MARGIN_CALL`, `MONEY_MARKET`, `SMA_ADJUSTMENT` |
| `symbol` | `str \| None` | `None` | No | Filter by symbol (URL-encode special characters) | — |

**Returns:** `requests.Response`. JSON body is a list of transaction dicts.

---

### `transaction_details(account_hash, transaction_id)`

Wraps **GET /accounts/{accountHash}/transactions/{transactionId}**.

```python
client.transaction_details(account_hash, transaction_id)
```

| Param | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `account_hash` | `str` | — | Yes | Account hash |
| `transaction_id` | `str` | — | Yes | Transaction ID |

**Returns:** `requests.Response`. JSON body is a single transaction detail dict.

---

## User Preference

### `preferences()`

Wraps **GET /userpreference/streamersubscriptionkeys**.

```python
client.preferences()
```

(No parameters.)

**Returns:** `requests.Response`. JSON body includes `accounts`, `streamerInfo` (host/port/keys used by the streaming WebSocket client), and `offers`.

---

## Quotes

### `quotes(symbols=None, fields=None, indicative=False)`

Wraps **GET /marketdata/quotes**.

```python
client.quotes(symbols=None, fields=None, indicative=False)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `symbols` | `list \| str \| None` | `None` | No (effectively yes) | One or more symbols. Accepts `["AAPL","AMD"]` or `"AAPL,AMD"` | — |
| `fields` | `str \| None` | `None` | No | Field selection | `"all"` (default), `"quote"`, `"fundamental"` |
| `indicative` | `bool` | `False` | No | Indicative quote flag | — |

**Returns:** `requests.Response`. JSON body is a dict keyed by symbol.

**Rate limit (verbatim):** 120 requests/minute. **Do NOT use in loops for market data — use streaming instead.**

---

### `quote(symbol_id, fields=None)`

Wraps **GET /marketdata/quotes/{symbolId}**.

```python
client.quote(symbol_id, fields=None)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `symbol_id` | `str` | — | Yes | Single symbol. **Note:** For futures, use `quotes()` instead — the path-param form has special character handling | — |
| `fields` | `str \| None` | `None` | No | Field selection | `"all"` (default), `"quote"`, `"fundamental"` |

**Returns:** `requests.Response`. JSON body is the single-symbol quote dict.

**Rate limit (verbatim):** 120 requests/minute.

---

## Option Chains

### `option_chains(symbol, contractType=None, strikeCount=None, includeUnderlyingQuote=None, strategy=None, interval=None, strike=None, range=None, fromDate=None, toDate=None, volatility=None, underlyingPrice=None, interestRate=None, daysToExpiration=None, expMonth=None, optionType=None, entitlement=None)`

Wraps **GET /marketdata/chains**.

```python
client.option_chains(
    symbol,
    contractType=None,
    strikeCount=None,
    includeUnderlyingQuote=None,
    strategy=None,
    interval=None,
    strike=None,
    range=None,
    fromDate=None,
    toDate=None,
    volatility=None,
    underlyingPrice=None,
    interestRate=None,
    daysToExpiration=None,
    expMonth=None,
    optionType=None,
    entitlement=None,
)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `symbol` | `str` | — | Yes | Underlying symbol (e.g., `"AAPL"` or `"$SPX"`) | — |
| `contractType` | `str \| None` | `None` | No | Filter | `"ALL"`, `"CALL"`, `"PUT"` |
| `strikeCount` | `int \| None` | `None` | No | Strikes above/below ATM | — |
| `includeUnderlyingQuote` | `bool \| None` | `None` | No | Include underlying quote in payload | — |
| `strategy` | `str \| None` | `None` | No | Analytical strategy | `SINGLE`, `ANALYTICAL`, `COVERED`, `VERTICAL`, `CALENDAR`, `STRANGLE`, `STRADDLE`, `BUTTERFLY`, `CONDOR`, `DIAGONAL`, `COLLAR`, `ROLL` |
| `interval` | `float \| None` | `None` | No | Strike interval for spreads | — |
| `strike` | `float \| None` | `None` | No | Specific strike filter | — |
| `range` | `str \| None` | `None` | No | Moneyness filter | e.g., `ITM`, `ATM`, `OTM` |
| `fromDate` | `datetime \| str \| None` | `None` | No | Lower expiration bound; not earlier than today. Format `yyyy-MM-dd` | — |
| `toDate` | `datetime \| str \| None` | `None` | No | Upper expiration bound. Format `yyyy-MM-dd` | — |
| `volatility` | `float \| None` | `None` | No | Volatility for ANALYTICAL strategy | — |
| `underlyingPrice` | `float \| None` | `None` | No | Underlying price for ANALYTICAL | — |
| `interestRate` | `float \| None` | `None` | No | Interest rate for ANALYTICAL | — |
| `daysToExpiration` | `int \| None` | `None` | No | DTE filter | — |
| `expMonth` | `str \| None` | `None` | No | Expiration month | `JAN`–`DEC` |
| `optionType` | `str \| None` | `None` | No | Option type filter | — |
| `entitlement` | `str \| None` | `None` | No | Entitlement code | `PN`, `NP`, `PP` |

**Returns:** `requests.Response`. JSON body contains `callExpDateMap` and `putExpDateMap` keyed by expiration.

---

### `option_expiration_chain(symbol)`

Wraps **GET /marketdata/chains/expirations** (often documented by Schwab as `/expirationchain`).

```python
client.option_expiration_chain(symbol)
```

| Param | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `symbol` | `str` | — | Yes | Underlying symbol, e.g., `"AAPL"` |

**Returns:** `requests.Response`. JSON body is a list of expiration entries (date, type, settlement, days-to-expiration).

---

## Price History

### `price_history(symbol, periodType=None, period=None, frequencyType=None, frequency=None, startDate=None, endDate=None, needExtendedHoursData=None, needPreviousClose=None)`

Wraps **GET /marketdata/pricehistory**.

```python
client.price_history(
    symbol,
    periodType=None,
    period=None,
    frequencyType=None,
    frequency=None,
    startDate=None,
    endDate=None,
    needExtendedHoursData=None,
    needPreviousClose=None,
)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `symbol` | `str` | — | Yes | Equity symbol (e.g., `"AAPL"`) | — |
| `periodType` | `str \| None` | `None` | No | Period unit | `"day"`, `"month"`, `"year"`, `"ytd"` |
| `period` | `int \| None` | `None` | No | Count of periodType units. **Allowed values depend on periodType:** | `day`: 1, 2, 3, 4, 5, 10 (default 10); `month`: 1, 2, 3, 6 (default 1); `year`: 1, 2, 3, 5, 10, 15, 20 (default 1); `ytd`: 1 (default 1) |
| `frequencyType` | `str \| None` | `None` | No | Candle bucket unit. **Depends on periodType:** | `day`: `"minute"`; `month`: `"daily"`, `"weekly"`; `year` / `ytd`: `"daily"`, `"weekly"`, `"monthly"` |
| `frequency` | `int \| None` | `None` | No | Candle bucket size. **Depends on frequencyType:** | `minute`: 1, 5, 10, 15, 30; `daily`/`weekly`/`monthly`: 1 |
| `startDate` | `datetime \| int \| None` | `None` | No | UNIX epoch (ms) or `datetime` | — |
| `endDate` | `datetime \| int \| None` | `None` | No | UNIX epoch (ms) or `datetime` | — |
| `needExtendedHoursData` | `bool \| None` | `None` (False) | No | Include pre/post-market | — |
| `needPreviousClose` | `bool \| None` | `None` (False) | No | Include previousClose / previousCloseDate | — |

**Returns:** `requests.Response`. JSON body is `{"candles": [{open, high, low, close, volume, datetime}, ...], "symbol": ..., "empty": bool}`.

**Rate limit (verbatim):** 120 requests/minute. **Do NOT use in loops — use streaming instead.**

---

## Movers

### `movers(symbol, sort=None, frequency=None)`

Wraps **GET /marketdata/movers**.

```python
client.movers(symbol, sort=None, frequency=None)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `symbol` | `str` | — | Yes | Index / venue identifier | `$DJI`, `$COMPX`, `$SPX`, `NYSE`, `NASDAQ`, `OTCBB`, `INDEX_ALL`, `EQUITY_ALL`, `OPTION_ALL`, `OPTION_PUT`, `OPTION_CALL` |
| `sort` | `str \| None` | `None` | No | Sort key | `VOLUME`, `TRADES`, `PERCENT_CHANGE_UP`, `PERCENT_CHANGE_DOWN` |
| `frequency` | `int \| None` | `None` | No | Lookback window (minutes) | `0` (default), `1`, `5`, `10`, `30`, `60` |

**Returns:** `requests.Response`. JSON body is `{"screeners": [...]}`.

---

## Market Hours

### `market_hours(symbols, date=None)`

Wraps **GET /marketdata/hours**.

```python
client.market_hours(symbols, date=None)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `symbols` | `list \| str` | — | Yes | One or more market types | `equity`, `option`, `bond`, `future`, `forex` |
| `date` | `datetime \| str \| None` | `None` (today) | No | Date to query. Format `yyyy-MM-dd` | — |

**Returns:** `requests.Response`. JSON body is keyed by market type, each with session start/end times (pre-market, regular, post-market).

---

### `market_hour(market_id, date=None)`

Wraps **GET /marketdata/hours/{marketId}**.

```python
client.market_hour(market_id, date=None)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `market_id` | `str` | — | Yes | Single market type | `equity`, `option`, `bond`, `future`, `forex` |
| `date` | `datetime \| str \| None` | `None` (today) | No | Date to query. Format `yyyy-MM-dd` | — |

**Returns:** `requests.Response`. JSON body is the single market type's session hours.

---

## Instruments

### `instruments(symbol, projection)`

Wraps **GET /instruments**.

```python
client.instruments(symbol, projection)
```

| Param | Type | Default | Required | Description | Allowed |
| --- | --- | --- | --- | --- | --- |
| `symbol` | `str` | — | Yes | Symbol or search string (e.g., `"AAPL"`) | — |
| `projection` | `str` | — | Yes | Lookup style | `symbol-search`, `symbol-regex`, `desc-search`, `desc-regex`, `search`, `fundamental` |

**Returns:** `requests.Response`. JSON body is an `instruments` array with fundamental data when `projection="fundamental"`.

---

### `instrument_cusip(cusip_id)`

Wraps **GET /instruments** (CUSIP variant — same endpoint, path or query disambiguates).

```python
client.instrument_cusip(cusip_id)
```

| Param | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `cusip_id` | `str` | — | Yes | 9-character CUSIP (e.g., `"037833100"` for AAPL) |

**Returns:** `requests.Response`. JSON body is an `instruments` array containing the matching instrument(s).

---

## Quick Method-to-Endpoint Map (for dispatch briefs)

```
Trader API (account_hash from linked_accounts):
  linked_accounts            → GET    /accounts/linkedaccounts
  account_details_all        → GET    /accounts
  account_details            → GET    /accounts/{accountHash}
  account_orders             → GET    /accounts/{accountHash}/orders
  account_orders_all         → GET    /orders
  place_order                → POST   /accounts/{accountHash}/orders
  order_details              → GET    /accounts/{accountHash}/orders/{orderId}
  cancel_order               → DELETE /accounts/{accountHash}/orders/{orderId}
  replace_order              → PUT    /accounts/{accountHash}/orders/{orderId}
  preview_order              → POST   /accounts/{accountHash}/previewOrder
  transactions               → GET    /accounts/{accountHash}/transactions
  transaction_details        → GET    /accounts/{accountHash}/transactions/{transactionId}
  preferences                → GET    /userpreference/streamersubscriptionkeys

Market Data API:
  quotes                     → GET    /marketdata/quotes
  quote                      → GET    /marketdata/quotes/{symbolId}
  option_chains              → GET    /marketdata/chains
  option_expiration_chain    → GET    /marketdata/chains/expirations
  price_history              → GET    /marketdata/pricehistory
  movers                     → GET    /marketdata/movers
  market_hours               → GET    /marketdata/hours
  market_hour                → GET    /marketdata/hours/{marketId}
  instruments                → GET    /instruments
  instrument_cusip           → GET    /instruments
```

23 wrapper methods → 23 Schwab REST endpoints (13 trader + 10 market-data).

---

## Integration-side notes for swing-trading hookup

- `linked_accounts()` is the **first call** in any session — every other per-account method requires the `hashValue` it returns. Cache hashes per session; they are stable per Schwab login but treat as opaque.
- `place_order()` order-ID extraction is via the `location` response header (NOT JSON body). Any retry / idempotency wrapper must read the header BEFORE discarding `resp`.
- All `requests.Response` returns — integration code must call `.json()` defensively and check `.ok` first. Schwab error envelopes are returned with non-2xx status, so `.json()` on failure may return an error dict, not raise.
- Wrapper-wide 120 req/min rate-limit guidance applies across ALL endpoints (verbatim from source). Per-endpoint rate-limit notes flagged above (`place_order`, `quotes`, `quote`, `price_history`) repeat the same 120/min ceiling.
- The source page does NOT document OAuth scope granularity per endpoint. Auth is handled uniformly by the `Client` instance — token refresh, header attachment, scope assertion all live in the auth layer (covered by a sibling distillation page, not this one).
