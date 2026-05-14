# Schwab Trader API — Market Data Specification

| Source URL | `https://developer.schwab.com/products/trader-api-individual/details/specifications/Market Data Production` |
|---|---|
| Extraction date | 2026-05-13 |
| API title | Market Data |
| API version | `1.0.0` |
| OpenAPI version | OAS3 |
| Description | APIs to access Market Data (Trader API — Market data) |
| Server (production base URL) | `https://api.schwabapi.com/marketdata/v1` |
| Contact | "Schwab Trader API team" (no email surfaced in spec) |
| Auth | OAuth2 via "Authorize" button in Swagger UI. The exposed security scheme name is not enumerated inline in this rendering — the same access token used for the Trader (Accounts & Trading) API authenticates Market Data calls. Bearer token in `Authorization: Bearer <access_token>`. |
| Rate limits | Not documented inline in this page. |
| Global error response shape | JSON `{ "errors": [ { "id": "<uuid>", "status": "<code>", "title": "<short>", "detail": "<long>", "source": { "header"\|"pointer"\|"parameter": ... } } ] }` — used uniformly for 400/401/404/500. |
| Common response headers | `Schwab-Client-CorrelId` (string, GUID; per-request correlation id) and `Schwab-Resource-Version` (integer/string; API resource version) appear on most 2xx + error responses. |

## Endpoint index

| # | Method | Path | Tag |
|---|---|---|---|
| 1 | GET | [`/quotes`](#1-get-quotes) | Quotes |
| 2 | GET | [`/{symbol_id}/quotes`](#2-get-symbol_idquotes) | Quotes |
| 3 | GET | [`/chains`](#3-get-chains) | Option Chains |
| 4 | GET | [`/expirationchain`](#4-get-expirationchain) | Option Expiration Chain |
| 5 | GET | [`/pricehistory`](#5-get-pricehistory) | PriceHistory |
| 6 | GET | [`/movers/{symbol_id}`](#6-get-moverssymbol_id) | Movers |
| 7 | GET | [`/markets`](#7-get-markets) | MarketHours |
| 8 | GET | [`/markets/{market_id}`](#8-get-marketsmarket_id) | MarketHours |
| 9 | GET | [`/instruments`](#9-get-instruments) | Instruments |
| 10 | GET | [`/instruments/{cusip_id}`](#10-get-instrumentscusip_id) | Instruments |

All endpoints are GET; full URL = `{server}{path}`, e.g. `https://api.schwabapi.com/marketdata/v1/quotes`.

---

## 1. GET /quotes

**Tag:** Quotes — "Get Quotes Web Service."

**Summary:** Get Quotes by list of symbols.

### Query parameters

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbols` | string | no (but required to get data) | — | Comma-separated list of symbol(s) to look up a quote. Example: `MRAD,EATOF,EBIZ,AAPL,BAC,AAAHX,AAAIX,$DJI,$SPX,MVEN,SOBS,TOITF,CNSWF,AMZN 230317C01360000,DJX 231215C00290000,/ESH23,./ADUF23C0.55,AUD/CAD`. Supports equities, mutual funds, indices, OCC option symbols (with embedded space), futures (`/<root><month><year>`), future-option chains (`./<root><month><year>C<strike>`), and forex pairs (`<base>/<quote>`). |
| `fields` | string | no | `all` | Comma-separated subset of root nodes to return. Allowed roots: `quote`, `fundamental`, `extended`, `reference`, `regular`. Omit for full response. |
| `indicative` | boolean | no | — | If `true`, includes indicative ETF quote (`$<SYMBOL>.IV`) alongside each ETF in the request. Allowed: `true`, `false`. Example: `false`. |

### Responses

| Status | Description | Media type |
|---|---|---|
| 200 | Quote Response — discriminated by `assetMainType` per symbol | `application/json` |
| 400 | Bad Request (missing header, invalid `fields`, validation failures on `symbols`/`cusips`/`ssids`) | `application/json` |
| 401 | Unauthorized | `application/json` |
| 500 | Internal Server Error | `application/json` |

#### 200 response shape

Top-level object is a map keyed by symbol; each value is a per-asset-class quote envelope. Discriminator field: `assetMainType` (observed values in the example response include `EQUITY`, `MUTUAL_FUND`, `INDEX`, `OPTION`, `FOREX`, `FUTURE`).

Common envelope fields (all asset classes):

```json
{
  "assetMainType": "EQUITY|MUTUAL_FUND|INDEX|OPTION|FOREX|FUTURE",
  "symbol": "AAPL",
  "realtime": true,
  "ssid": 1973757747,
  "quoteType": "NBBO",
  "reference": { "cusip": "037833100", "description": "Apple Inc", "exchange": "Q", "exchangeName": "NASDAQ" },
  "quote":     { /* asset-class-specific quote fields */ },
  "regular":   { /* equities only: regularMarket* fields */ },
  "fundamental": { /* avg10DaysVolume, divAmount, peRatio, etc. */ }
}
```

EQUITY `quote` block (key fields):

```json
{
  "52WeekHigh": 169, "52WeekLow": 1.1,
  "askMICId": "MEMX", "askPrice": 168.41, "askSize": 400, "askTime": 1644854683672,
  "bidMICId": "IEGX", "bidPrice": 168.40, "bidSize": 400, "bidTime": 1644854683633,
  "closePrice": 177.57, "highPrice": 169, "lowPrice": 167.09,
  "lastMICId": "XADF", "lastPrice": 168.405, "lastSize": 200,
  "mark": 168.405, "markChange": -9.165, "markPercentChange": -5.161,
  "netChange": -9.165, "netPercentChange": -5.161,
  "openPrice": 167.37,
  "quoteTime": 1644854683672, "tradeTime": 1644854683408,
  "securityStatus": "Normal",
  "totalVolume": 22361159,
  "volatility": 0.0347
}
```

EQUITY `regular` block:

```json
{
  "regularMarketLastPrice": 168.405, "regularMarketLastSize": 2,
  "regularMarketNetChange": -9.165, "regularMarketPercentChange": -5.161,
  "regularMarketTradeTime": 1644854683408
}
```

EQUITY `fundamental` block (also surfaced for MUTUAL_FUND):

```json
{
  "avg10DaysVolume": 1, "avg1YearVolume": 0,
  "divAmount": 1.1, "divFreq": 0, "divPayAmount": 0, "divYield": 1.1,
  "eps": 0, "fundLeverageFactor": 1.1, "peRatio": 1.1,
  "divPayDate": "2021-10-29T05:00:00Z",
  "nextDivExDate": "2022-01-31T06:00:00Z",
  "nextDivPayDate": "2022-01-31T06:00:00Z"
}
```

OPTION `quote` block (key fields seen in example): `delta`, `gamma`, `theta`, `vega`, `rho`, `openInterest`, `timeValue`, `theoreticalOptionValue`, `theoreticalVolatility`, `volatility`, `bidPrice`, `askPrice`, `lastPrice`, `markPrice`, plus a `reference` block carrying `contractType` (`C`/`P`), `expirationDay`/`Month`/`Year`, `strikePrice`, `multiplier`, `underlying`, `deliverables`.

FOREX `quote` block: `52WeekHigh`/`Low`, `askPrice`, `bidPrice`, `lastPrice`, `mark`, `openPrice`, `closePrice`, `highPrice`, `lowPrice`, `netChange`, `netPercentChange`, `quoteTime`, `tradeTime`, `tick`, `tickAmount`, `totalVolume`, `securityStatus`. FOREX `reference` carries `marketMaker`, `tradingHours`, `isTradable`.

FUTURE `quote` block: `askPrice`/`Size`/`Time`, `bidPrice`/`Size`/`Time`, `closePrice`, `futurePercentChange`, `highPrice`/`lowPrice`, `lastPrice`/`Size`, `openInterest`, `openPrice`, `mark`, `quoteTime`, `settleTime`, `tick`, `tickAmount`, `totalVolume`, `tradeTime`, `securityStatus`. FUTURE `reference` carries `futureActiveSymbol`, `futureExpirationDate`, `futureIsActive`, `futureIsTradable`, `futureMultiplier`, `futurePriceFormat`, `futureSettlementPrice`, `futureTradingHours`, `product`.

INDEX `quote` block: `52WeekHigh`/`Low`, `closePrice`, `highPrice`, `lastPrice`, `lowPrice`, `netChange`, `netPercentChange`, `openPrice`, `securityStatus`, `totalVolume`, `tradeTime`.

#### Error response example (400)

```json
{
  "errors": [
    { "id": "6808262e-...", "status": "400", "title": "Bad Request", "detail": "Missing header", "source": { "header": "Authorization" } },
    { "id": "0be22ae7-...", "status": "400", "title": "Bad Request", "detail": "Search combination should have min of 1.", "source": { "pointer": ["/data/attributes/symbols", "/data/attributes/cusips", "/data/attributes/ssids"] } },
    { "id": "28485414-...", "status": "400", "title": "Bad Request", "detail": "valid fields should be any of all,fundamental,reference,extended,quote,regular or empty value", "source": { "parameter": "fields" } }
  ]
}
```

### Response headers (2xx + 4xx)

| Header | Type | Description |
|---|---|---|
| `Schwab-Client-CorrelId` | string | Unique correlation id for the request (GUID). |
| `Schwab-Resource-Version` | string | Requested API version (present on 4xx; not always on 2xx). |

---

## 2. GET /{symbol_id}/quotes

**Tag:** Quotes (single-symbol shortcut for endpoint 1).

**Summary:** Get Quote by single symbol.

### Path parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `symbol_id` | string | yes | Symbol of instrument. Example: `TSLA`. |

### Query parameters

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `fields` | string | no | `all` | Comma-separated subset of root nodes to return (`quote`, `fundamental`, `extended`, `reference`, `regular`). Omit for full response. |

### Responses

| Status | Description | Media type |
|---|---|---|
| 200 | Quote Response (same discriminated-union shape as endpoint 1, but the top-level object is keyed by the single requested symbol) | `application/json` |
| 400 / 401 / 404 / 500 | Standard error envelope | `application/json` |

> **Source-rendering note (extraction artifact, 2026-05-13):** The "Search by symbol AAPL" example value rendered in the Schwab Swagger UI for `GET /{symbol_id}/quotes` is the **price-history candles example** (same JSON body as `GET /pricehistory`), not a single-symbol quote. This is a documentation defect in the source page, not in this distillation. Treat the actual response shape as a single-key version of the endpoint-1 response.

### Response headers

| Header | Type | Description |
|---|---|---|
| `Schwab-Client-CorrelId` | string | Per-request correlation GUID. |
| `Schwab-Resource-Version` | string | API resource version (on 4xx). |

---

## 3. GET /chains

**Tag:** Option Chains — "Get Option Chains Web Service."

**Summary:** Get option chain for an optionable symbol — includes information on options contracts for each expiration.

### Query parameters

| Name | Type | Required | Default | Allowed values | Description |
|---|---|---|---|---|---|
| `symbol` | string | yes | — | — | Enter one symbol. Example: `AAPL`. |
| `contractType` | string | no | — | `CALL`, `PUT`, `ALL` | Contract type filter. |
| `strikeCount` | integer | no | — | — | Number of strikes to return above and below at-the-money. |
| `includeUnderlyingQuote` | boolean | no | — | `true`, `false` | Include the underlying instrument's quote in the response. |
| `strategy` | string | no | `SINGLE` | `SINGLE`, `ANALYTICAL`, `COVERED`, `VERTICAL`, `CALENDAR`, `STRANGLE`, `STRADDLE`, `BUTTERFLY`, `CONDOR`, `DIAGONAL`, `COLLAR`, `ROLL` | `ANALYTICAL` enables theoretical-value calc inputs (`volatility`, `underlyingPrice`, `interestRate`, `daysToExpiration`). |
| `interval` | number (double) | no | — | — | Strike interval for spread strategy chains (see `strategy`). |
| `strike` | number (double) | no | — | — | Strike price filter. |
| `range` | string | no | — | (ITM/NTM/OTM-style codes) | Range filter (ITM / NTM / OTM, etc.). |
| `fromDate` | string (`date`) | no | — | `yyyy-MM-dd` | From-date filter. |
| `toDate` | string (`date`) | no | — | `yyyy-MM-dd` | To-date filter. |
| `volatility` | number (double) | no | — | — | Volatility input (only for `strategy=ANALYTICAL`). |
| `underlyingPrice` | number (double) | no | — | — | Underlying price input (only for `strategy=ANALYTICAL`). |
| `interestRate` | number (double) | no | — | — | Interest-rate input (only for `strategy=ANALYTICAL`). |
| `daysToExpiration` | integer (int32) | no | — | — | Days-to-expiration input (only for `strategy=ANALYTICAL`). |
| `expMonth` | string | no | — | `JAN, FEB, MAR, APR, MAY, JUN, JUL, AUG, SEP, OCT, NOV, DEC, ALL` | Expiration month filter. |
| `optionType` | string | no | — | — | Option type filter. |
| `entitlement` | string | no | — | `PN`, `NP`, `PP` | Applies only with a retail token — `PP` = PayingPro, `NP` = NonPro, `PN` = NonPayingPro. |

### Responses

| Status | Description | Media type |
|---|---|---|
| 200 | Option chain returned successfully | `application/json` |
| 400 / 401 / 404 / 500 | Standard error envelope | `application/json` |

#### 200 response shape (high-level)

```json
{
  "symbol": "string",
  "status": "string",
  "underlying": {
    "ask": 0, "askSize": 0, "bid": 0, "bidSize": 0,
    "change": 0, "close": 0, "delayed": true, "description": "string",
    "exchangeName": "IND", "fiftyTwoWeekHigh": 0, "fiftyTwoWeekLow": 0,
    "highPrice": 0, "last": 0, "lowPrice": 0,
    "mark": 0, "markChange": 0, "markPercentChange": 0,
    "openPrice": 0, "percentChange": 0,
    "quoteTime": 0, "tradeTime": 0,
    "symbol": "string", "totalVolume": 0
  },
  "strategy": "SINGLE",
  "interval": 0,
  "isDelayed": true,
  "isIndex": true,
  "daysToExpiration": 0,
  "interestRate": 0,
  "underlyingPrice": 0,
  "volatility": 0,
  "callExpDateMap": {
    "<expDate>:<dte>": {
      "<strike>": [
        {
          "putCall": "CALL|PUT",
          "symbol": "string",
          "description": "string",
          "exchangeName": "string",
          "bidPrice": 0, "askPrice": 0, "lastPrice": 0, "markPrice": 0,
          "bidSize": 0, "askSize": 0, "lastSize": 0,
          "highPrice": 0, "lowPrice": 0, "openPrice": 0, "closePrice": 0,
          "totalVolume": 0,
          "tradeDate": 0, "quoteTimeInLong": 0, "tradeTimeInLong": 0,
          "netChange": 0, "volatility": 0,
          "delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0,
          "timeValue": 0, "openInterest": 0,
          "isInTheMoney": true,
          "theoreticalOptionValue": 0, "theoreticalVolatility": 0,
          "isMini": true, "isNonStandard": true,
          "optionDeliverablesList": [
            { "symbol": "string", "assetType": "string", "deliverableUnits": "string", "currencyType": "string" }
          ],
          "strikePrice": 0,
          "expirationDate": "string",
          "daysToExpiration": 0,
          "expirationType": "M",
          "lastTradingDay": 0,
          "multiplier": 0,
          "settlementType": "A",
          "deliverableNote": "string",
          "isIndexOption": true,
          "percentChange": 0, "markChange": 0, "markPercentChange": 0,
          "isPennyPilot": true, "intrinsicValue": 0,
          "optionRoot": "string"
        }
      ]
    }
  },
  "putExpDateMap": { /* same shape as callExpDateMap */ }
}
```

### Response headers

Same as endpoints above: `Schwab-Client-CorrelId` (GUID), `Schwab-Resource-Version` (resource version on 4xx).

---

## 4. GET /expirationchain

**Tag:** Option Expiration Chain — "Get Option Expiration Chain Web Service."

**Summary:** Get Option Expiration (Series) information for an optionable symbol. Does **not** include individual options contracts for the underlying.

### Query parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `symbol` | string | yes | Single symbol. Example: `AAPL`. |

### Responses

| Status | Description | Media type |
|---|---|---|
| 200 | Expiration chain returned successfully | `application/json` |
| 400 / 401 / 404 / 500 | Standard error envelope | `application/json` |

#### 200 response shape

```json
{
  "expirationList": [
    { "expirationDate": "2022-01-07", "daysToExpiration": 2,   "expirationType": "W", "standard": true },
    { "expirationDate": "2022-01-21", "daysToExpiration": 16,  "expirationType": "S", "standard": true },
    { "expirationDate": "2022-03-18", "daysToExpiration": 72,  "expirationType": "S", "standard": true },
    { "expirationDate": "2022-09-16", "daysToExpiration": 254, "expirationType": "S", "standard": true }
    /* ... */
  ]
}
```

`expirationType` codes observed in the example: `W` (weekly), `S` (standard monthly/quarterly). `standard: true` indicates a regular (non-non-standard) series.

### Response headers

Same as endpoints above.

---

## 5. GET /pricehistory

**Tag:** PriceHistory — "Get Price History Web Service."

**Summary:** Get historical Open, High, Low, Close, and Volume for a given frequency (i.e., aggregation) for a single symbol. Frequency available is dependent on `periodType` selected. Datetime values are EPOCH milliseconds.

### Query parameters

| Name | Type | Required | Default | Allowed values | Description |
|---|---|---|---|---|---|
| `symbol` | string | **yes** | — | — | Equity symbol to look up. Example: `AAPL`. |
| `periodType` | string | no | (varies; see below) | `day`, `month`, `year`, `ytd` | The chart period being requested. |
| `period` | integer (int32) | no | depends on `periodType` | depends on `periodType` | Number of chart-period units to retrieve. Per-`periodType` allowed values: `day` → `1, 2, 3, 4, 5, 10` (default `10`). `month` → `1, 2, 3, 6` (default `1`). `year` → `1, 2, 3, 5, 10, 15, 20` (default `1`). `ytd` → `1` (default `1`). |
| `frequencyType` | string | no | depends on `periodType` | `minute`, `daily`, `weekly`, `monthly` | Time frequency type. Per-`periodType` allowed values: `day` → `minute` (default `minute`). `month` → `daily, weekly` (default `weekly`). `year` → `daily, weekly, monthly` (default `monthly`). `ytd` → `daily, weekly` (default `weekly`). |
| `frequency` | integer (int32) | no | `1` | depends on `frequencyType` | Time-frequency duration. Per-`frequencyType` allowed values: `minute` → `1, 5, 10, 15, 30` (default `1`). `daily` → `1` (default `1`). `weekly` → `1` (default `1`). `monthly` → `1` (default `1`). |
| `startDate` | integer (int64) | no | (computed from `endDate − period`, skipping weekends/holidays) | EPOCH ms | Start of range; e.g. `1451624400000`. |
| `endDate` | integer (int64) | no | (previous business day's market close) | EPOCH ms | End of range. |
| `needExtendedHoursData` | boolean | no | — | `true`, `false` | Include extended-hours bars. |
| `needPreviousClose` | boolean | no | — | `true`, `false` | Include previous close price/date in response (`previousClose`, `previousCloseDate`). |

#### Constraint matrix (binding for callers)

| `periodType` | Allowed `period` | Default `period` | Allowed `frequencyType` | Default `frequencyType` | Allowed `frequency` |
|---|---|---|---|---|---|
| `day`   | 1, 2, 3, 4, 5, 10 | 10 | `minute`                  | `minute`  | 1, 5, 10, 15, 30 |
| `month` | 1, 2, 3, 6        | 1  | `daily`, `weekly`         | `weekly`  | 1 |
| `year`  | 1, 2, 3, 5, 10, 15, 20 | 1 | `daily`, `weekly`, `monthly` | `monthly` | 1 |
| `ytd`   | 1                 | 1  | `daily`, `weekly`         | `weekly`  | 1 |

### Responses

| Status | Description | Media type |
|---|---|---|
| 200 | All candles for the given date range | `application/json` |
| 400 / 401 / 404 / 500 | Standard error envelope | `application/json` |

#### 200 response shape

```json
{
  "symbol": "AAPL",
  "empty": false,
  "previousClose": 174.56,
  "previousCloseDate": 1639029600000,
  "candles": [
    { "open": 175.01, "high": 175.15, "low": 175.01, "close": 175.04, "volume": 10719, "datetime": 1639137600000 },
    { "open": 175.08, "high": 175.09, "low": 175.05, "close": 175.05, "volume": 500,   "datetime": 1639137660000 }
    /* ... */
  ]
}
```

Field types: all OHLC values are numbers; `volume` is integer; `datetime` is EPOCH ms.

### Response headers

`Schwab-Client-CorrelId` (GUID), `Schwab-Resource-Version` (on 4xx).

---

## 6. GET /movers/{symbol_id}

**Tag:** Movers — "Get Movers Web Service."

**Summary:** Get a list of top-10 securities movement for a specific index.

### Path parameters

| Name | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `symbol_id` | string | yes | `$DJI`, `$COMPX`, `$SPX`, `NYSE`, `NASDAQ`, `OTCBB`, `INDEX_ALL`, `EQUITY_ALL`, `OPTION_ALL`, `OPTION_PUT`, `OPTION_CALL` | Index / aggregate symbol to query. Example: `$DJI`. |

### Query parameters

| Name | Type | Required | Default | Allowed values | Description |
|---|---|---|---|---|---|
| `sort`      | string  | no | — | `VOLUME`, `TRADES`, `PERCENT_CHANGE_UP`, `PERCENT_CHANGE_DOWN` | Sort attribute. Example: `VOLUME`. |
| `frequency` | integer (int32) | no | `0` | `0`, `1`, `5`, `10`, `30`, `60` | Direction-of-movers filter window (minutes); `0` = no frequency filter. |

### Responses

| Status | Description | Media type |
|---|---|---|
| 200 | Movers returned successfully | `application/json` |
| 400 / 401 / 404 / 500 | Standard error envelope | `application/json` |

#### 200 response shape

```json
{
  "screeners": [
    { "change": 10, "description": "Dow jones", "direction": "up", "last": 100, "symbol": "$DJI", "totalVolume": 100 },
    { "change": 10, "description": "Dow jones", "direction": "up", "last": 100, "symbol": "$DJI", "totalVolume": 100 }
    /* ... */
  ]
}
```

`direction`: `up` | `down`. `change` is a numeric delta (units: same as the underlying price). `last` is the latest price. `totalVolume` is an integer.

### Response headers

`Schwab-Client-CorrelId` (GUID). `Schwab-Resource-Version` is **not** listed for 2xx on this endpoint (still appears on 4xx).

---

## 7. GET /markets

**Tag:** MarketHours — "Get MarketHours Web Service."

**Summary:** Get Market Hours for dates in the future across different markets.

### Query parameters

| Name | Type | Required | Default | Allowed values | Description |
|---|---|---|---|---|---|
| `markets` | array[string] (`form`, comma-separated) | **yes** | — | `equity`, `option`, `bond`, `future`, `forex` | List of markets. Example: `markets=equity,option`. |
| `date`    | string (`date`)                          | no      | current day | `YYYY-MM-DD` (current day → 1 year out) | Date of interest. Defaults to current day if omitted. |

### Responses

| Status | Description | Media type |
|---|---|---|
| 200 | OK — keyed map of market → product-class → hours record | `application/json` |
| 400 / 401 / 404 / 500 | Standard error envelope | `application/json` |

#### 200 response shape

```json
{
  "equity": {
    "EQ": {
      "date": "2022-04-14",
      "marketType": "EQUITY",
      "product": "EQ",
      "productName": "equity",
      "isOpen": true,
      "sessionHours": {
        "preMarket":     [ { "start": "2022-04-14T07:00:00-04:00", "end": "2022-04-14T09:30:00-04:00" } ],
        "regularMarket": [ { "start": "2022-04-14T09:30:00-04:00", "end": "2022-04-14T16:00:00-04:00" } ],
        "postMarket":    [ { "start": "2022-04-14T16:00:00-04:00", "end": "2022-04-14T20:00:00-04:00" } ]
      }
    }
  },
  "option": {
    "EQO": {
      "date": "2022-04-14", "marketType": "OPTION", "product": "EQO", "productName": "equity option",
      "isOpen": true,
      "sessionHours": { "regularMarket": [ { "start": "2022-04-14T09:30:00-04:00", "end": "2022-04-14T16:00:00-04:00" } ] }
    },
    "IND": {
      "date": "2022-04-14", "marketType": "OPTION", "product": "IND", "productName": "index option",
      "isOpen": true,
      "sessionHours": { "regularMarket": [ { "start": "2022-04-14T09:30:00-04:00", "end": "2022-04-14T16:15:00-04:00" } ] }
    }
  }
}
```

Outer keys (`equity`, `option`, ...) mirror the requested `markets` values. Inner keys are product-class codes (e.g., `EQ` for equity, `EQO` / `IND` for option product classes). Each `sessionHours.*` value is an array of `{start, end}` ISO-8601 timestamps with timezone offsets.

### Response headers

`Schwab-Client-CorrelId` (GUID) — wording on this endpoint says "generated GUID can be used to track an individual service call if support is needed".

---

## 8. GET /markets/{market_id}

**Tag:** MarketHours (single-market shortcut for endpoint 7).

**Summary:** Get Market Hours for dates in the future for a single market.

### Path parameters

| Name | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `market_id` | string | yes | `equity`, `option`, `bond`, `future`, `forex` | Market id. |

### Query parameters

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `date` | string (`date`) | no | current day | `YYYY-MM-DD`. Valid range: current day to 1 year forward. Defaults to current day if omitted. |

### Responses

| Status | Description | Media type |
|---|---|---|
| 200 | OK — same shape as endpoint 7, scoped to the requested market | `application/json` |
| 400 / 401 / 404 / 500 | Standard error envelope | `application/json` |

#### 200 response shape

```json
{
  "equity": {
    "EQ": {
      "date": "2022-04-14",
      "marketType": "EQUITY",
      "exchange": "NULL",
      "category": "NULL",
      "product": "EQ",
      "productName": "equity",
      "isOpen": true,
      "sessionHours": {
        "preMarket":     [ { "start": "2022-04-14T07:00:00-04:00", "end": "2022-04-14T09:30:00-04:00" } ],
        "regularMarket": [ { "start": "2022-04-14T09:30:00-04:00", "end": "2022-04-14T16:00:00-04:00" } ],
        "postMarket":    [ { "start": "2022-04-14T16:00:00-04:00", "end": "2022-04-14T20:00:00-04:00" } ]
      }
    }
  }
}
```

Note: the per-product-class record on this endpoint additionally surfaces `exchange` and `category` fields (each can be the literal string `"NULL"` per the example).

### Response headers

`Schwab-Client-CorrelId` (GUID).

---

## 9. GET /instruments

**Tag:** Instruments — "Get Instruments Web Service."

**Summary:** Get Instruments details by symbols and projections. Use `projection=fundamental` for fundamental data.

### Query parameters

| Name | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `symbol`     | string | **yes** | — | Symbol(s) of security. (Comma-separated supported per the Swagger UI example query.) |
| `projection` | string | **yes** | `symbol-search`, `symbol-regex`, `desc-search`, `desc-regex`, `search`, `fundamental` | Search-type. |

### Responses

| Status | Description | Media type |
|---|---|---|
| 200 | OK | `application/json` |
| 400 / 401 / 404 / 500 | Standard error envelope | `application/json` |

#### 200 response shape

```json
{
  "instruments": [
    { "cusip": "037833100", "symbol": "AAPL", "description": "Apple Inc",      "exchange": "NASDAQ", "assetType": "EQUITY" },
    { "cusip": "060505104", "symbol": "BAC",  "description": "Bank Of America Corp", "exchange": "NYSE",   "assetType": "EQUITY" }
  ]
}
```

When `projection=fundamental`, each instrument record carries an additional `fundamental` block (shape mirrors the `fundamental` block in `GET /quotes`).

### Response headers

| Header | Type | Description |
|---|---|---|
| `Schwab-Resource-Version` | integer | Desired/returned version of the API resource. Example: `3`. |
| `Schwab-Client-CorrelId`  | string  | Per-request correlation GUID. |

---

## 10. GET /instruments/{cusip_id}

**Tag:** Instruments (lookup by CUSIP).

**Summary:** Get basic instrument details by CUSIP.

### Path parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `cusip_id` | string | yes | CUSIP of a security. |

### Responses

| Status | Description | Media type |
|---|---|---|
| 200 | OK — single instrument record | `application/json` |
| 400 / 401 / 404 / 500 | Standard error envelope | `application/json` |

#### 200 response shape

```json
{
  "cusip": "037833100",
  "symbol": "AAPL",
  "description": "Apple Inc",
  "exchange": "NASDAQ",
  "assetType": "EQUITY"
}
```

### Response headers

| Header | Type | Description |
|---|---|---|
| `Schwab-Resource-Version` | integer | Desired/returned version of the API resource. Example: `3`. |
| `Schwab-Client-CorrelId`  | string  | Per-request correlation GUID. |

---

## Cross-cutting notes

- **`Schwab-Client-CorrelId`** is universally present on both 2xx and error responses; the API documentation describes it as "Used to identify an individual request throughout the lifetime of the request and across systems" (sometimes phrased as "GUID can be used to track an individual service call if support is needed").
- **`Schwab-Resource-Version`** appears explicitly on Instruments endpoints (9, 10) for 2xx, and on most 4xx envelopes; it identifies the requested/returned API resource version (integer-typed; example value `3`).
- **Standard error envelope** (same shape on all endpoints; see endpoint 1 for the canonical example):
  ```json
  {
    "errors": [
      {
        "id":     "<uuid>",
        "status": "<numeric-or-numeric-string>",
        "title":  "<short title>",
        "detail": "<long detail>",
        "source": { "header" | "pointer" | "parameter": ... }
      }
    ]
  }
  ```
- **Auth scope:** the Swagger UI exposes a single `Authorize` action covering all endpoints; the same OAuth2 access token used for the Trader API (orders + accounts) is reused for Market Data. The detailed scope name is not surfaced inline on this page.
- **Server (production base URL):** `https://api.schwabapi.com/marketdata/v1` — there is exactly one server entry in the spec; no sandbox URL is listed on this page.

## Extraction limitations (flagged 2026-05-13)

1. **EP2 example body is mis-rendered upstream.** The Schwab Swagger UI displays the `GET /pricehistory` candles JSON as the "Search by symbol AAPL" example for `GET /{symbol_id}/quotes`. The true response shape for EP2 is a single-key version of EP1's discriminated-union response — see "Source-rendering note" inline.
2. **Detailed per-asset-class schemas** for the `GET /quotes` discriminated union are inferred from the example response (which surfaces EQUITY, MUTUAL_FUND, INDEX, OPTION, FOREX, FUTURE variants). The Swagger UI's "Schema" tab content for each asset class was not separately captured beyond the key fields documented above. If a strict per-asset-class schema is required, fetch the underlying OpenAPI JSON (the rendered HTML does not include it as a downloadable artifact on this page).
3. **No global rate-limit or quota documentation** appears on the Market Data Production page; rate limits, when published, live elsewhere on the developer portal.
4. **No OAuth scope strings** are enumerated inline; the page only exposes the "Authorize" UI action.
5. **No documented SLA / staleness guarantees** (real-time vs. delayed) other than the per-quote `realtime` and `isDelayed` boolean fields.
