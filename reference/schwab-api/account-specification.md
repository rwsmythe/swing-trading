# Schwab Trader API - Account Access and User Preferences

> Distilled reference for the Retail Trader API (Production tier).
>
> **Source HTML:** `reference/SchwabAPI/websites/AccountSpecification/Trader API - Individual _ Products _ Charles Schwab Developer Portal.html`
> **Source URL:** https://developer.schwab.com/products/trader-api-individual/details/specifications/Retail%20Trader%20API%20Production
> **Extracted:** 2026-05-13
> **API title:** Trader API - Account Access and User Preferences
> **Version:** 1.0.0   *   **OpenAPI:** OAS3   *   **Contact:** TraderAPI@Schwab.com

## Overview

APIs to access Account Balances and Positions, and to perform trading activities.

Account numbers in plain text MUST NOT be used outside headers or request/response bodies - consumers first call `GET /accounts/accountNumbers` to obtain plain-text and encrypted pairs (`accountNumber` / `hashValue`), then use the encrypted hash as `{accountNumber}` in every other path-param call.

### Server

- `https://api.schwabapi.com/trader/v1`

### Authentication

- OAuth 2.0 bearer token (Authorize button in the live portal). All endpoints require an `Authorization: Bearer <token>` header. The HTML dump does not document the full OAuth flow inline; see the dedicated Authentication API spec page in this repo (`reference/schwab-api/` sibling docs from the 4-agent distillation) for token-exchange details.

### Global response headers

- `Schwab-Client-CorrelId` (success responses) / `Schwab-Client-CorrelID` (error responses, capitalized differently in the source spec) - auto-generated correlation ID returned on every response, type `string`.

### Global error response shape

All error responses (400, 401, 403, 404, 500, 503) share this body schema (`application/json`):

```json
{
  "message": "string",
  "errors": ["string"]
}
```

Per-endpoint sections below carry the per-code description text; the meanings are uniform across endpoints:

- **400** - validation problem with the request
- **401** - authorization token invalid OR no accessible accounts for the third-party app
- **403** - caller forbidden from this service
- **404** - resource not found
- **500** - unexpected server error
- **503** - server has a temporary problem responding

### Source-spec gap (read this before consuming enums)

The static HTML rendering collapses the Schema-panel enum lists for most order-domain types. The HTML carries only `Array [ N ]` placeholders - the individual values are NOT present anywhere in the dump because the Swagger UI loads them on click. See Appendix A for the full list of enum types and their value counts.

**Recoverable enums (full value lists materialized inline by the dump):**

- `status` (query param on `GET /accounts/{n}/orders` and `GET /orders`) - full 21-value list inline in those endpoint sections.
- `types` (query param on `GET /accounts/{n}/transactions`) - full 15-value list inline in that endpoint section.

**Not recoverable from this HTML** (require the live portal or the OpenAPI JSON): every Schema-panel-only enum. Example values shown in the response bodies below illustrate ONE valid value per enum field (e.g., `"session": "NORMAL"`); they are not the complete list. Cross-reference the live Swagger UI or the published OpenAPI document before relying on them.

---

## Endpoint index

| # | Method | Path | Summary |
|---|---|---|---|
| 1 | `GET` | [`/accounts/accountNumbers`](#get-accounts-accountumbers) | Get list of account numbers and their encrypted values |
| 2 | `GET` | [`/accounts`](#get-accounts) | Get linked account(s) balances and positions for the logged in user. |
| 3 | `GET` | [`/accounts/{accountNumber}`](#get-accounts-accountumber) | Get a specific account balance and positions for the logged in user. |
| 4 | `GET` | [`/accounts/{accountNumber}/orders`](#get-accounts-accountumber-orders) | Get all orders for a specific account. |
| 5 | `POST` | [`/accounts/{accountNumber}/orders`](#post-accounts-accountumber-orders) | Place order for a specific account. |
| 6 | `GET` | [`/accounts/{accountNumber}/orders/{orderId}`](#get-accounts-accountumber-orders-orderd) | Get a specific order by its ID, for a specific account |
| 7 | `DELETE` | [`/accounts/{accountNumber}/orders/{orderId}`](#delete-accounts-accountumber-orders-orderd) | Cancel an order for a specific account |
| 8 | `PUT` | [`/accounts/{accountNumber}/orders/{orderId}`](#put-accounts-accountumber-orders-orderd) | Replace order for a specific account |
| 9 | `GET` | [`/orders`](#get-orders) | Get all orders for all accounts |
| 10 | `POST` | [`/accounts/{accountNumber}/previewOrder`](#post-accounts-accountumber-previewrder) | Preview order for a specific account. |
| 11 | `GET` | [`/accounts/{accountNumber}/transactions`](#get-accounts-accountumber-transactions) | Get all transactions information for a specific account. |
| 12 | `GET` | [`/accounts/{accountNumber}/transactions/{transactionId}`](#get-accounts-accountumber-transactions-transactiond) | Get specific transaction information for a specific account |
| 13 | `GET` | [`/userPreference`](#get-userreference) | Get user preference information for the logged in user. |

---

## `GET /accounts/accountNumbers` <a id="get-accounts-accountumbers"></a>

**Get list of account numbers and their encrypted values**

Account numbers in plain text cannot be used outside of headers or request/response bodies. As the first step consumers must invoke this service to retrieve the list of plain text/encrypted value pairs, and use encrypted account values for all subsequent calls for any accountNumber request.

- **operationId:** `Accounts-getAccountNumbers`

### Responses

- **200** (success) - List of valid "accounts", matching the provided input parameters.
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

**Success response example:**

```json
[
  {
    "accountNumber": "string",
    "hashValue": "string"
  }
]
```

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

### Notes

- This is the **bootstrap endpoint**. The `hashValue` returned is the encrypted form used as `{accountNumber}` in every other path-param call.

---

## `GET /accounts` <a id="get-accounts"></a>

**Get linked account(s) balances and positions for the logged in user.**

All the linked account information for the user logged in. The
balances on these accounts are displayed by default however the positions
on these accounts will be displayed based on the "positions" flag.

- **operationId:** `Accounts-getAccounts`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `fields` | query | string | no |  | This allows one to determine which fields they want returned. Possible value in this String can be: positions Example: fields=positions |

### Responses

- **200** (success) - List of valid "accounts", matching the provided input parameters.
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

**Success response example:**

```json
[
  {
    "securitiesAccount": {
      "accountNumber": "string",
      "roundTrips": 0,
      "isDayTrader": false,
      "isClosingOnlyRestricted": false,
      "pfcbFlag": false,
      "positions": [
        {
          "shortQuantity": 0,
          "averagePrice": 0,
          "currentDayProfitLoss": 0,
          "currentDayProfitLossPercentage": 0,
          "longQuantity": 0,
          "settledLongQuantity": 0,
          "settledShortQuantity": 0,
          "agedQuantity": 0,
          "instrument": {
            "cusip": "string",
            "symbol": "string",
            "description": "string",
            "instrumentId": 0,
            "netChange": 0,
            "type": "SWEEP_VEHICLE"
          },
          "marketValue": 0,
          "maintenanceRequirement": 0,
          "averageLongPrice": 0,
          "averageShortPrice": 0,
          "taxLotAverageLongPrice": 0,
          "taxLotAverageShortPrice": 0,
          "longOpenProfitLoss": 0,
          "shortOpenProfitLoss": 0,
          "previousSessionLongQuantity": 0,
          "previousSessionShortQuantity": 0,
          "currentDayCost": 0
        }
      ],
      "initialBalances": {
        "accruedInterest": 0,
        "availableFundsNonMarginableTrade": 0,
        "bondValue": 0,
        "buyingPower": 0,
        "cashBalance": 0,
        "cashAvailableForTrading": 0,
        "cashReceipts": 0,
        "dayTradingBuyingPower": 0,
        "dayTradingBuyingPowerCall": 0,
        "dayTradingEquityCall": 0,
        "equity": 0,
        "equityPercentage": 0,
        "liquidationValue": 0,
        "longMarginValue": 0,
        "longOptionMarketValue": 0,
        "longStockValue": 0,
        "maintenanceCall": 0,
        "maintenanceRequirement": 0,
        "margin": 0,
        "marginEquity": 0,
        "moneyMarketFund": 0,
        "mutualFundValue": 0,
        "regTCall": 0,
        "shortMarginValue": 0,
        "shortOptionMarketValue": 0,
        "shortStockValue": 0,
        "totalCash": 0,
        "isInCall": 0,
        "unsettledCash": 0,
        "pendingDeposits": 0,
        "marginBalance": 0,
        "shortBalance": 0,
        "accountValue": 0
      },
      "currentBalances": {
        "availableFunds": 0,
        "availableFundsNonMarginableTrade": 0,
        "buyingPower": 0,
        "buyingPowerNonMarginableTrade": 0,
        "dayTradingBuyingPower": 0,
        "dayTradingBuyingPowerCall": 0,
        "equity": 0,
        "equityPercentage": 0,
        "longMarginValue": 0,
        "maintenanceCall": 0,
        "maintenanceRequirement": 0,
        "marginBalance": 0,
        "regTCall": 0,
        "shortBalance": 0,
        "shortMarginValue": 0,
        "sma": 0,
        "isInCall": 0,
        "stockBuyingPower": 0,
        "optionBuyingPower": 0
      },
      "projectedBalances": {
        "availableFunds": 0,
        "availableFundsNonMarginableTrade": 0,
        "buyingPower": 0,
        "buyingPowerNonMarginableTrade": 0,
        "dayTradingBuyingPower": 0,
        "dayTradingBuyingPowerCall": 0,
        "equity": 0,
        "equityPercentage": 0,
        "longMarginValue": 0,
        "maintenanceCall": 0,
        "maintenanceRequirement": 0,
        "marginBalance": 0,
        "regTCall": 0,
        "shortBalance": 0,
        "shortMarginValue": 0,
        "sma": 0,
        "isInCall": 0,
        "stockBuyingPower": 0,
        "optionBuyingPower": 0
      }
    }
  }
]
```

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

### Notes

- `fields=positions` is the only documented value; omitting `fields` returns balances only (positions array is suppressed). `securitiesAccount` contains `initialBalances`, `currentBalances`, `projectedBalances` (different field sets per balance bucket) plus the `positions` array.

---

## `GET /accounts/{accountNumber}` <a id="get-accounts-accountumber"></a>

**Get a specific account balance and positions for the logged in user.**

Specific account information with balances and positions.
The balance information on these accounts is displayed by default but
Positions will be returned based on the "positions" flag.

- **operationId:** `Accounts-getAccount`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `accountNumber` | path | string | yes |  | The encrypted ID of the account |
| `fields` | query | string | no |  | This allows one to determine which fields they want returned. Possible values in this String can be: positions Example: fields=positions |

### Responses

- **200** (success) - A valid account, matching the provided input parameters
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

**Success response example:**

```json
{
  "securitiesAccount": {
    "accountNumber": "string",
    "roundTrips": 0,
    "isDayTrader": false,
    "isClosingOnlyRestricted": false,
    "pfcbFlag": false,
    "positions": [
      {
        "shortQuantity": 0,
        "averagePrice": 0,
        "currentDayProfitLoss": 0,
        "currentDayProfitLossPercentage": 0,
        "longQuantity": 0,
        "settledLongQuantity": 0,
        "settledShortQuantity": 0,
        "agedQuantity": 0,
        "instrument": {
          "cusip": "string",
          "symbol": "string",
          "description": "string",
          "instrumentId": 0,
          "netChange": 0,
          "type": "SWEEP_VEHICLE"
        },
        "marketValue": 0,
        "maintenanceRequirement": 0,
        "averageLongPrice": 0,
        "averageShortPrice": 0,
        "taxLotAverageLongPrice": 0,
        "taxLotAverageShortPrice": 0,
        "longOpenProfitLoss": 0,
        "shortOpenProfitLoss": 0,
        "previousSessionLongQuantity": 0,
        "previousSessionShortQuantity": 0,
        "currentDayCost": 0
      }
    ],
    "initialBalances": {
      "accruedInterest": 0,
      "availableFundsNonMarginableTrade": 0,
      "bondValue": 0,
      "buyingPower": 0,
      "cashBalance": 0,
      "cashAvailableForTrading": 0,
      "cashReceipts": 0,
      "dayTradingBuyingPower": 0,
      "dayTradingBuyingPowerCall": 0,
      "dayTradingEquityCall": 0,
      "equity": 0,
      "equityPercentage": 0,
      "liquidationValue": 0,
      "longMarginValue": 0,
      "longOptionMarketValue": 0,
      "longStockValue": 0,
      "maintenanceCall": 0,
      "maintenanceRequirement": 0,
      "margin": 0,
      "marginEquity": 0,
      "moneyMarketFund": 0,
      "mutualFundValue": 0,
      "regTCall": 0,
      "shortMarginValue": 0,
      "shortOptionMarketValue": 0,
      "shortStockValue": 0,
      "totalCash": 0,
      "isInCall": 0,
      "unsettledCash": 0,
      "pendingDeposits": 0,
      "marginBalance": 0,
      "shortBalance": 0,
      "accountValue": 0
    },
    "currentBalances": {
      "availableFunds": 0,
      "availableFundsNonMarginableTrade": 0,
      "buyingPower": 0,
      "buyingPowerNonMarginableTrade": 0,
      "dayTradingBuyingPower": 0,
      "dayTradingBuyingPowerCall": 0,
      "equity": 0,
      "equityPercentage": 0,
      "longMarginValue": 0,
      "maintenanceCall": 0,
      "maintenanceRequirement": 0,
      "marginBalance": 0,
      "regTCall": 0,
      "shortBalance": 0,
      "shortMarginValue": 0,
      "sma": 0,
      "isInCall": 0,
      "stockBuyingPower": 0,
      "optionBuyingPower": 0
    },
    "projectedBalances": {
      "availableFunds": 0,
      "availableFundsNonMarginableTrade": 0,
      "buyingPower": 0,
      "buyingPowerNonMarginableTrade": 0,
      "dayTradingBuyingPower": 0,
      "dayTradingBuyingPowerCall": 0,
      "equity": 0,
      "equityPercentage": 0,
      "longMarginValue": 0,
      "maintenanceCall": 0,
      "maintenanceRequirement": 0,
      "marginBalance": 0,
      "regTCall": 0,
      "shortBalance": 0,
      "shortMarginValue": 0,
      "sma": 0,
      "isInCall": 0,
      "stockBuyingPower": 0,
      "optionBuyingPower": 0
    }
  }
}
```

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

---

## `GET /accounts/{accountNumber}/orders` <a id="get-accounts-accountumber-orders"></a>

**Get all orders for a specific account.**

All orders for a specific account. Orders retrieved can be filtered based on input parameters below. Maximum date range is 1 year.

- **operationId:** `Orders-getOrdersByPathParam`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `accountNumber` | path | string | yes |  | The encrypted ID of the account |
| `maxResults` | query | integer ($int64) | no |  | The max number of orders to retrieve. Default is 3000. |
| `fromEnteredTime` | query | string | yes |  | Specifies that no orders entered before this time should be returned. Valid ISO-8601 formats are : yyyy-MM-dd'T'HH:mm:ss.SSSZ Example fromEnteredTime is '2024-03-29T00:00:00.000Z'. 'toEnteredTime' must also be set. |
| `toEnteredTime` | query | string | yes |  | Specifies that no orders entered after this time should be returned.Valid ISO-8601 formats are : yyyy-MM-dd'T'HH:mm:ss.SSSZ . Example toEnteredTime is '2024-04-28T23:59:59.000Z'. 'fromEnteredTime' must also be set. |
| `status` | query | string | no |  | Specifies that only orders of this status should be returned. |

**`status` available values:**

`AWAITING_PARENT_ORDER, AWAITING_CONDITION, AWAITING_STOP_CONDITION, AWAITING_MANUAL_REVIEW, ACCEPTED, AWAITING_UR_OUT, PENDING_ACTIVATION, QUEUED, WORKING, REJECTED, PENDING_CANCEL, CANCELED, PENDING_REPLACE, REPLACED, FILLED, EXPIRED, NEW, AWAITING_RELEASE_TIME, PENDING_ACKNOWLEDGEMENT, PENDING_RECALL, UNKNOWN`

### Responses

- **200** (success) - A List of orders for the account, matching the provided input parameters
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

**Success response example:**

```json
[
  {
    "session": "NORMAL",
    "duration": "DAY",
    "orderType": "MARKET",
    "cancelTime": "2026-05-14T08:44:00.774Z",
    "complexOrderStrategyType": "NONE",
    "quantity": 0,
    "filledQuantity": 0,
    "remainingQuantity": 0,
    "requestedDestination": "INET",
    "destinationLinkName": "string",
    "releaseTime": "2026-05-14T08:44:00.774Z",
    "stopPrice": 0,
    "stopPriceLinkBasis": "MANUAL",
    "stopPriceLinkType": "VALUE",
    "stopPriceOffset": 0,
    "stopType": "STANDARD",
    "priceLinkBasis": "MANUAL",
    "priceLinkType": "VALUE",
    "price": 0,
    "taxLotMethod": "FIFO",
    "orderLegCollection": [
      {
        "orderLegType": "EQUITY",
        "legId": 0,
        "instrument": {
          "cusip": "string",
          "symbol": "string",
          "description": "string",
          "instrumentId": 0,
          "netChange": 0,
          "type": "SWEEP_VEHICLE"
        },
        "instruction": "BUY",
        "positionEffect": "OPENING",
        "quantity": 0,
        "quantityType": "ALL_SHARES",
        "divCapGains": "REINVEST",
        "toSymbol": "string"
      }
    ],
    "activationPrice": 0,
    "specialInstruction": "ALL_OR_NONE",
    "orderStrategyType": "SINGLE",
    "orderId": 0,
    "cancelable": false,
    "editable": false,
    "status": "AWAITING_PARENT_ORDER",
    "enteredTime": "2026-05-14T08:44:00.774Z",
    "closeTime": "2026-05-14T08:44:00.774Z",
    "tag": "string",
    "accountNumber": 0,
    "orderActivityCollection": [
      {
        "activityType": "EXECUTION",
        "executionType": "FILL",
        "quantity": 0,
        "orderRemainingQuantity": 0,
        "executionLegs": [
          {
            "legId": 0,
            "price": 0,
            "quantity": 0,
            "mismarkedQuantity": 0,
            "instrumentId": 0,
            "time": "2026-05-14T08:44:00.774Z"
          }
        ]
      }
    ],
    "replacingOrderCollection": [
      "string"
    ],
    "childOrderStrategies": [
      "string"
    ],
    "statusDescription": "string"
  }
]
```

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

### Notes

- `fromEnteredTime` / `toEnteredTime` use ISO-8601 `yyyy-MM-dd'T'HH:mm:ss.SSSZ`. Endpoint description states **maximum date range 1 year**. The `maxResults` default is **3000**.

---

## `POST /accounts/{accountNumber}/orders` <a id="post-accounts-accountumber-orders"></a>

**Place order for a specific account.**

Place an order for a specific account.

- **operationId:** `Orders-placeOrder`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `accountNumber` | path | string | yes |  | The encrypted ID of the account The new Order Object. |

### Request body

- **Content-Type:** `application/json`
- Body: Order object (schema below). Enum field values shown are illustrative only - the full enum lists are not exposed in the source HTML (see Overview > Source-spec gap).

**Example body / schema:**

```json
{
  "session": "NORMAL",
  "duration": "DAY",
  "orderType": "MARKET",
  "cancelTime": "2026-05-14T08:44:00.780Z",
  "complexOrderStrategyType": "NONE",
  "quantity": 0,
  "filledQuantity": 0,
  "remainingQuantity": 0,
  "destinationLinkName": "string",
  "releaseTime": "2026-05-14T08:44:00.780Z",
  "stopPrice": 0,
  "stopPriceLinkBasis": "MANUAL",
  "stopPriceLinkType": "VALUE",
  "stopPriceOffset": 0,
  "stopType": "STANDARD",
  "priceLinkBasis": "MANUAL",
  "priceLinkType": "VALUE",
  "price": 0,
  "taxLotMethod": "FIFO",
  "orderLegCollection": [
    {
      "orderLegType": "EQUITY",
      "legId": 0,
      "instrument": {
        "cusip": "string",
        "symbol": "string",
        "description": "string",
        "instrumentId": 0,
        "netChange": 0,
        "type": "SWEEP_VEHICLE"
      },
      "instruction": "BUY",
      "positionEffect": "OPENING",
      "quantity": 0,
      "quantityType": "ALL_SHARES",
      "divCapGains": "REINVEST",
      "toSymbol": "string"
    }
  ],
  "activationPrice": 0,
  "specialInstruction": "ALL_OR_NONE",
  "orderStrategyType": "SINGLE",
  "orderId": 0,
  "cancelable": false,
  "editable": false,
  "status": "AWAITING_PARENT_ORDER",
  "enteredTime": "2026-05-14T08:44:00.780Z",
  "closeTime": "2026-05-14T08:44:00.780Z",
  "accountNumber": 0,
  "orderActivityCollection": [
    {
      "activityType": "EXECUTION",
      "executionType": "FILL",
      "quantity": 0,
      "orderRemainingQuantity": 0,
      "executionLegs": [
        {
          "legId": 0,
          "price": 0,
          "quantity": 0,
          "mismarkedQuantity": 0,
          "instrumentId": 0,
          "time": "2026-05-14T08:44:00.780Z"
        }
      ]
    }
  ],
  "replacingOrderCollection": [
    "string"
  ],
  "childOrderStrategies": [
    "string"
  ],
  "statusDescription": "string"
}
```

### Responses

- **201** (success) - Empty response body if an order was successfully placed/created.
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

### Notes

- Returns `201 Created`. The response body is empty per the spec; the new order's identifier is conveyed via a `Location` response header (commonly observed Schwab behavior; the HTML dump only enumerates `Schwab-Client-CorrelId`).

---

## `GET /accounts/{accountNumber}/orders/{orderId}` <a id="get-accounts-accountumber-orders-orderd"></a>

**Get a specific order by its ID, for a specific account**

Get a specific order by its ID, for a specific account

- **operationId:** `Orders-getOrder`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `accountNumber` | path | string | yes |  | The encrypted ID of the account |
| `orderId` | path | integer ($int64) | yes |  | The ID of the order being retrieved. |

### Responses

- **200** (success) - An order object, matching the input parameters
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

**Success response example:**

```json
{
  "session": "NORMAL",
  "duration": "DAY",
  "orderType": "MARKET",
  "cancelTime": "2026-05-14T08:44:00.786Z",
  "complexOrderStrategyType": "NONE",
  "quantity": 0,
  "filledQuantity": 0,
  "remainingQuantity": 0,
  "requestedDestination": "INET",
  "destinationLinkName": "string",
  "releaseTime": "2026-05-14T08:44:00.786Z",
  "stopPrice": 0,
  "stopPriceLinkBasis": "MANUAL",
  "stopPriceLinkType": "VALUE",
  "stopPriceOffset": 0,
  "stopType": "STANDARD",
  "priceLinkBasis": "MANUAL",
  "priceLinkType": "VALUE",
  "price": 0,
  "taxLotMethod": "FIFO",
  "orderLegCollection": [
    {
      "orderLegType": "EQUITY",
      "legId": 0,
      "instrument": {
        "cusip": "string",
        "symbol": "string",
        "description": "string",
        "instrumentId": 0,
        "netChange": 0,
        "type": "SWEEP_VEHICLE"
      },
      "instruction": "BUY",
      "positionEffect": "OPENING",
      "quantity": 0,
      "quantityType": "ALL_SHARES",
      "divCapGains": "REINVEST",
      "toSymbol": "string"
    }
  ],
  "activationPrice": 0,
  "specialInstruction": "ALL_OR_NONE",
  "orderStrategyType": "SINGLE",
  "orderId": 0,
  "cancelable": false,
  "editable": false,
  "status": "AWAITING_PARENT_ORDER",
  "enteredTime": "2026-05-14T08:44:00.786Z",
  "closeTime": "2026-05-14T08:44:00.786Z",
  "tag": "string",
  "accountNumber": 0,
  "orderActivityCollection": [
    {
      "activityType": "EXECUTION",
      "executionType": "FILL",
      "quantity": 0,
      "orderRemainingQuantity": 0,
      "executionLegs": [
        {
          "legId": 0,
          "price": 0,
          "quantity": 0,
          "mismarkedQuantity": 0,
          "instrumentId": 0,
          "time": "2026-05-14T08:44:00.786Z"
        }
      ]
    }
  ],
  "replacingOrderCollection": [
    "string"
  ],
  "childOrderStrategies": [
    "string"
  ],
  "statusDescription": "string"
}
```

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

---

## `DELETE /accounts/{accountNumber}/orders/{orderId}` <a id="delete-accounts-accountumber-orders-orderd"></a>

**Cancel an order for a specific account**

Cancel a specific order for a specific account

- **operationId:** `Orders-cancelOrder`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `accountNumber` | path | string | yes |  | The encrypted ID of the account |
| `orderId` | path | integer ($int64) | yes |  | The ID of the order being cancelled |

### Responses

- **200** (success) - Empty response body if an order was successfully canceled.
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

### Notes

- Returns `200` with an empty body when the cancel succeeds.

---

## `PUT /accounts/{accountNumber}/orders/{orderId}` <a id="put-accounts-accountumber-orders-orderd"></a>

**Replace order for a specific account**

Replace an existing order for an account. The existing order will be replaced by the new order. Once replaced, the old order will be canceled and a new order will be created.

- **operationId:** `Orders-replaceOrder`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `accountNumber` | path | string | yes |  | The encrypted ID of the account |
| `orderId` | path | integer ($int64) | yes |  | The ID of the order being retrieved. The Order Object. |

### Request body

- **Content-Type:** `application/json`
- Body: Order object - same schema as `POST /accounts/{accountNumber}/orders`. The existing order is canceled and a new one created.

**Example body / schema:**

```json
{
  "session": "NORMAL",
  "duration": "DAY",
  "orderType": "MARKET",
  "cancelTime": "2026-05-14T08:44:00.795Z",
  "complexOrderStrategyType": "NONE",
  "quantity": 0,
  "filledQuantity": 0,
  "remainingQuantity": 0,
  "destinationLinkName": "string",
  "releaseTime": "2026-05-14T08:44:00.795Z",
  "stopPrice": 0,
  "stopPriceLinkBasis": "MANUAL",
  "stopPriceLinkType": "VALUE",
  "stopPriceOffset": 0,
  "stopType": "STANDARD",
  "priceLinkBasis": "MANUAL",
  "priceLinkType": "VALUE",
  "price": 0,
  "taxLotMethod": "FIFO",
  "orderLegCollection": [
    {
      "orderLegType": "EQUITY",
      "legId": 0,
      "instrument": {
        "cusip": "string",
        "symbol": "string",
        "description": "string",
        "instrumentId": 0,
        "netChange": 0,
        "type": "SWEEP_VEHICLE"
      },
      "instruction": "BUY",
      "positionEffect": "OPENING",
      "quantity": 0,
      "quantityType": "ALL_SHARES",
      "divCapGains": "REINVEST",
      "toSymbol": "string"
    }
  ],
  "activationPrice": 0,
  "specialInstruction": "ALL_OR_NONE",
  "orderStrategyType": "SINGLE",
  "orderId": 0,
  "cancelable": false,
  "editable": false,
  "status": "AWAITING_PARENT_ORDER",
  "enteredTime": "2026-05-14T08:44:00.795Z",
  "closeTime": "2026-05-14T08:44:00.795Z",
  "accountNumber": 0,
  "orderActivityCollection": [
    {
      "activityType": "EXECUTION",
      "executionType": "FILL",
      "quantity": 0,
      "orderRemainingQuantity": 0,
      "executionLegs": [
        {
          "legId": 0,
          "price": 0,
          "quantity": 0,
          "mismarkedQuantity": 0,
          "instrumentId": 0,
          "time": "2026-05-14T08:44:00.795Z"
        }
      ]
    }
  ],
  "replacingOrderCollection": [
    "string"
  ],
  "childOrderStrategies": [
    "string"
  ],
  "statusDescription": "string"
}
```

### Responses

- **201** (success) - Empty response body if an order was successfully replaced/created.
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

### Notes

- Returns `201 Created`. The replacement cancels the old order and creates a new one with the new identifier conveyed via a `Location` header.

---

## `GET /orders` <a id="get-orders"></a>

**Get all orders for all accounts**

Get all orders for all accounts

- **operationId:** `Orders-getOrdersByQueryParam`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `maxResults` | query | integer ($int64) | no |  | The max number of orders to retrieve. Default is 3000. |
| `fromEnteredTime` | query | string | yes |  | Specifies that no orders entered before this time should be returned. Valid ISO-8601 formats are- yyyy-MM-dd'T'HH:mm:ss.SSSZ Date must be within 60 days from today's date. 'toEnteredTime' must also be set. |
| `toEnteredTime` | query | string | yes |  | Specifies that no orders entered after this time should be returned.Valid ISO-8601 formats are - yyyy-MM-dd'T'HH:mm:ss.SSSZ. 'fromEnteredTime' must also be set. |
| `status` | query | string | no |  | Specifies that only orders of this status should be returned. |

**`status` available values:**

`AWAITING_PARENT_ORDER, AWAITING_CONDITION, AWAITING_STOP_CONDITION, AWAITING_MANUAL_REVIEW, ACCEPTED, AWAITING_UR_OUT, PENDING_ACTIVATION, QUEUED, WORKING, REJECTED, PENDING_CANCEL, CANCELED, PENDING_REPLACE, REPLACED, FILLED, EXPIRED, NEW, AWAITING_RELEASE_TIME, PENDING_ACKNOWLEDGEMENT, PENDING_RECALL, UNKNOWN`

### Responses

- **200** (success) - A List of orders for the specified account or if its not mentioned,
for all the linked accounts, matching the provided input parameters.
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

**Success response example:**

```json
[
  {
    "session": "NORMAL",
    "duration": "DAY",
    "orderType": "MARKET",
    "cancelTime": "2026-05-14T08:44:00.802Z",
    "complexOrderStrategyType": "NONE",
    "quantity": 0,
    "filledQuantity": 0,
    "remainingQuantity": 0,
    "requestedDestination": "INET",
    "destinationLinkName": "string",
    "releaseTime": "2026-05-14T08:44:00.802Z",
    "stopPrice": 0,
    "stopPriceLinkBasis": "MANUAL",
    "stopPriceLinkType": "VALUE",
    "stopPriceOffset": 0,
    "stopType": "STANDARD",
    "priceLinkBasis": "MANUAL",
    "priceLinkType": "VALUE",
    "price": 0,
    "taxLotMethod": "FIFO",
    "orderLegCollection": [
      {
        "orderLegType": "EQUITY",
        "legId": 0,
        "instrument": {
          "cusip": "string",
          "symbol": "string",
          "description": "string",
          "instrumentId": 0,
          "netChange": 0,
          "type": "SWEEP_VEHICLE"
        },
        "instruction": "BUY",
        "positionEffect": "OPENING",
        "quantity": 0,
        "quantityType": "ALL_SHARES",
        "divCapGains": "REINVEST",
        "toSymbol": "string"
      }
    ],
    "activationPrice": 0,
    "specialInstruction": "ALL_OR_NONE",
    "orderStrategyType": "SINGLE",
    "orderId": 0,
    "cancelable": false,
    "editable": false,
    "status": "AWAITING_PARENT_ORDER",
    "enteredTime": "2026-05-14T08:44:00.802Z",
    "closeTime": "2026-05-14T08:44:00.802Z",
    "tag": "string",
    "accountNumber": 0,
    "orderActivityCollection": [
      {
        "activityType": "EXECUTION",
        "executionType": "FILL",
        "quantity": 0,
        "orderRemainingQuantity": 0,
        "executionLegs": [
          {
            "legId": 0,
            "price": 0,
            "quantity": 0,
            "mismarkedQuantity": 0,
            "instrumentId": 0,
            "time": "2026-05-14T08:44:00.802Z"
          }
        ]
      }
    ],
    "replacingOrderCollection": [
      "string"
    ],
    "childOrderStrategies": [
      "string"
    ],
    "statusDescription": "string"
  }
]
```

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

### Notes

- `fromEnteredTime` / `toEnteredTime` use ISO-8601 `yyyy-MM-dd'T'HH:mm:ss.SSSZ`. The parameter description states **date must be within 60 days from today's date** (note: this differs from the per-account endpoint's 1-year description - verify against live behavior).

---

## `POST /accounts/{accountNumber}/previewOrder` <a id="post-accounts-accountumber-previewrder"></a>

**Preview order for a specific account.**

Preview an order for a specific account.

- **operationId:** `Orders-previewOrder`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `accountNumber` | path | string | yes |  | The encrypted ID of the account The Order Object. |

### Request body

- **Content-Type:** `application/json`
- Body: Order object - same caller-supplied schema as `POST /accounts/{accountNumber}/orders`; the server returns a richer preview response (see schema below).

**Example body / schema:**

```json
{
  "orderId": 0,
  "orderStrategy": {
    "accountNumber": "string",
    "advancedOrderType": "NONE",
    "closeTime": "2026-05-14T08:44:00.811Z",
    "enteredTime": "2026-05-14T08:44:00.811Z",
    "orderBalance": {
      "orderValue": 0,
      "projectedAvailableFund": 0,
      "projectedBuyingPower": 0,
      "projectedCommission": 0
    },
    "orderStrategyType": "SINGLE",
    "orderVersion": 0,
    "session": "NORMAL",
    "status": "AWAITING_PARENT_ORDER",
    "allOrNone": true,
    "discretionary": true,
    "duration": "DAY",
    "filledQuantity": 0,
    "orderType": "MARKET",
    "orderValue": 0,
    "price": 0,
    "quantity": 0,
    "remainingQuantity": 0,
    "sellNonMarginableFirst": true,
    "settlementInstruction": "REGULAR",
    "strategy": "NONE",
    "amountIndicator": "DOLLARS",
    "orderLegs": [
      {
        "askPrice": 0,
        "bidPrice": 0,
        "lastPrice": 0,
        "markPrice": 0,
        "projectedCommission": 0,
        "quantity": 0,
        "finalSymbol": "string",
        "legId": 0,
        "assetType": "EQUITY",
        "instruction": "BUY"
      }
    ]
  },
  "orderValidationResult": {
    "alerts": [
      {
        "validationRuleName": "string",
        "message": "string",
        "activityMessage": "string",
        "originalSeverity": "ACCEPT",
        "overrideName": "string",
        "overrideSeverity": "ACCEPT"
      }
    ],
    "accepts": [
      {
        "validationRuleName": "string",
        "message": "string",
        "activityMessage": "string",
        "originalSeverity": "ACCEPT",
        "overrideName": "string",
        "overrideSeverity": "ACCEPT"
      }
    ],
    "rejects": [
      {
        "validationRuleName": "string",
        "message": "string",
        "activityMessage": "string",
        "originalSeverity": "ACCEPT",
        "overrideName": "string",
        "overrideSeverity": "ACCEPT"
      }
    ],
    "reviews": [
      {
        "validationRuleName": "string",
        "message": "string",
        "activityMessage": "string",
        "originalSeverity": "ACCEPT",
        "overrideName": "string",
        "overrideSeverity": "ACCEPT"
      }
    ],
    "warns": [
      {
        "validationRuleName": "string",
        "message": "string",
        "activityMessage": "string",
        "originalSeverity": "ACCEPT",
        "overrideName": "string",
        "overrideSeverity": "ACCEPT"
      }
    ]
  },
  "commissionAndFee": {
    "commission": {
      "commissionLegs": [
        {
          "commissionValues": [
            {
              "value": 0,
              "type": "COMMISSION"
            }
          ]
        }
      ]
    },
    "fee": {
      "feeLegs": [
        {
          "feeValues": [
            {
              "value": 0,
              "type": "COMMISSION"
            }
          ]
        }
      ]
    },
    "trueCommission": {
      "commissionLegs": [
        {
          "commissionValues": [
            {
              "value": 0,
              "type": "COMMISSION"
            }
          ]
        }
      ]
    }
  }
}
```

### Responses

- **200** (success) - An order object, matching the input parameters
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

**`200` response schema (Order preview):**

```json
{
  "orderId": 0,
  "orderStrategy": {
    "accountNumber": "string",
    "advancedOrderType": "NONE",
    "closeTime": "2026-05-14T08:44:00.813Z",
    "enteredTime": "2026-05-14T08:44:00.813Z",
    "orderBalance": {
      "orderValue": 0,
      "projectedAvailableFund": 0,
      "projectedBuyingPower": 0,
      "projectedCommission": 0
    },
    "orderStrategyType": "SINGLE",
    "orderVersion": 0,
    "session": "NORMAL",
    "status": "AWAITING_PARENT_ORDER",
    "allOrNone": true,
    "discretionary": true,
    "duration": "DAY",
    "filledQuantity": 0,
    "orderType": "MARKET",
    "orderValue": 0,
    "price": 0,
    "quantity": 0,
    "remainingQuantity": 0,
    "sellNonMarginableFirst": true,
    "settlementInstruction": "REGULAR",
    "strategy": "NONE",
    "amountIndicator": "DOLLARS",
    "orderLegs": [
      {
        "askPrice": 0,
        "bidPrice": 0,
        "lastPrice": 0,
        "markPrice": 0,
        "projectedCommission": 0,
        "quantity": 0,
        "finalSymbol": "string",
        "legId": 0,
        "assetType": "EQUITY",
        "instruction": "BUY"
      }
    ]
  },
  "orderValidationResult": {
    "alerts": [
      {
        "validationRuleName": "string",
        "message": "string",
        "activityMessage": "string",
        "originalSeverity": "ACCEPT",
        "overrideName": "string",
        "overrideSeverity": "ACCEPT"
      }
    ],
    "accepts": [
      {
        "validationRuleName": "string",
        "message": "string",
        "activityMessage": "string",
        "originalSeverity": "ACCEPT",
        "overrideName": "string",
        "overrideSeverity": "ACCEPT"
      }
    ],
    "rejects": [
      {
        "validationRuleName": "string",
        "message": "string",
        "activityMessage": "string",
        "originalSeverity": "ACCEPT",
        "overrideName": "string",
        "overrideSeverity": "ACCEPT"
      }
    ],
    "reviews": [
      {
        "validationRuleName": "string",
        "message": "string",
        "activityMessage": "string",
        "originalSeverity": "ACCEPT",
        "overrideName": "string",
        "overrideSeverity": "ACCEPT"
      }
    ],
    "warns": [
      {
        "validationRuleName": "string",
        "message": "string",
        "activityMessage": "string",
        "originalSeverity": "ACCEPT",
        "overrideName": "string",
        "overrideSeverity": "ACCEPT"
      }
    ]
  },
  "commissionAndFee": {
    "commission": {
      "commissionLegs": [
        {
          "commissionValues": [
            {
              "value": 0,
              "type": "COMMISSION"
            }
          ]
        }
      ]
    },
    "fee": {
      "feeLegs": [
        {
          "feeValues": [
            {
              "value": 0,
              "type": "COMMISSION"
            }
          ]
        }
      ]
    },
    "trueCommission": {
      "commissionLegs": [
        {
          "commissionValues": [
            {
              "value": 0,
              "type": "COMMISSION"
            }
          ]
        }
      ]
    }
  }
}
```

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

### Notes

- Preview is a dry-run - no order is placed. The response carries `orderValidationResult` with `alerts` / `accepts` / `rejects` / `reviews` / `warns` arrays plus `commissionAndFee` projecting commissions and fees per leg.

---

## `GET /accounts/{accountNumber}/transactions` <a id="get-accounts-accountumber-transactions"></a>

**Get all transactions information for a specific account.**

All transactions for a specific account. Maximum number of transactions in response is 3000. Maximum date range is 1 year.

- **operationId:** `Transactions-getTransactionsByPathParam`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `accountNumber` | path | string | yes |  | The encrypted ID of the account |
| `startDate` | query | string | yes |  | Specifies that no transactions entered before this time should be returned. Valid ISO-8601 formats are : yyyy-MM-dd'T'HH:mm:ss.SSSZ . Example start date is '2024-03-28T21:10:42.000Z'. The 'endDate' must also be set. |
| `endDate` | query | string | yes |  | Specifies that no transactions entered after this time should be returned.Valid ISO-8601 formats are : yyyy-MM-dd'T'HH:mm:ss.SSSZ . Example start date is '2024-05-10T21:10:42.000Z'. The 'startDate' must also be set. |
| `symbol` | query | string | no |  | It filters all the transaction activities based on the symbol specified. NOTE: If there is any special character in the symbol, please send th encoded value. |
| `types` | query | string | yes |  | Specifies that only transactions of this status should be returned. |

**`types` available values:**

`TRADE, RECEIVE_AND_DELIVER, DIVIDEND_OR_INTEREST, ACH_RECEIPT, ACH_DISBURSEMENT, CASH_RECEIPT, CASH_DISBURSEMENT, ELECTRONIC_FUND, WIRE_OUT, WIRE_IN, JOURNAL, MEMORANDUM, MARGIN_CALL, MONEY_MARKET, SMA_ADJUSTMENT`

### Responses

- **200** (success) - A List of orders for the account, matching the provided input
parameters
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

**Success response example:**

```json
[
  {
    "activityId": 0,
    "time": "2026-05-14T08:44:00.822Z",
    "user": {
      "cdDomainId": "string",
      "login": "string",
      "type": "ADVISOR_USER",
      "userId": 0,
      "systemUserName": "string",
      "firstName": "string",
      "lastName": "string",
      "brokerRepCode": "string"
    },
    "description": "string",
    "accountNumber": "string",
    "type": "TRADE",
    "status": "VALID",
    "subAccount": "CASH",
    "tradeDate": "2026-05-14T08:44:00.822Z",
    "settlementDate": "2026-05-14T08:44:00.822Z",
    "positionId": 0,
    "orderId": 0,
    "netAmount": 0,
    "activityType": "ACTIVITY_CORRECTION",
    "transferItems": [
      {
        "instrument": {
          "cusip": "string",
          "symbol": "string",
          "description": "string",
          "instrumentId": 0,
          "netChange": 0,
          "type": "SWEEP_VEHICLE"
        },
        "amount": 0,
        "cost": 0,
        "price": 0,
        "feeType": "COMMISSION",
        "positionEffect": "OPENING"
      }
    ]
  }
]
```

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

### Notes

- `startDate` / `endDate` use ISO-8601 `yyyy-MM-dd'T'HH:mm:ss.SSSZ`. **Max date range: 1 year. Max transactions in response: 3000.** Required `types` parameter selects a single TransactionType; consumers wanting multiple types need to issue one call per type (the spec does not indicate comma-separated support).

---

## `GET /accounts/{accountNumber}/transactions/{transactionId}` <a id="get-accounts-accountumber-transactions-transactiond"></a>

**Get specific transaction information for a specific account**

Get specific transaction information for a specific account

- **operationId:** `Transactions-getTransactionsById`

### Parameters

| Name | In | Type | Required | Default | Description |
|---|---|---|---|---|---|
| `accountNumber` | path | string | yes |  | The encrypted ID of the account |
| `transactionId` | path | integer ($int64) | yes |  | The ID of the transaction being retrieved. |

### Responses

- **200** (success) - A List of orders for the account, matching the provided input parameters
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

**Success response example:**

```json
[
  {
    "activityId": 0,
    "time": "2026-05-14T08:44:00.826Z",
    "user": {
      "cdDomainId": "string",
      "login": "string",
      "type": "ADVISOR_USER",
      "userId": 0,
      "systemUserName": "string",
      "firstName": "string",
      "lastName": "string",
      "brokerRepCode": "string"
    },
    "description": "string",
    "accountNumber": "string",
    "type": "TRADE",
    "status": "VALID",
    "subAccount": "CASH",
    "tradeDate": "2026-05-14T08:44:00.826Z",
    "settlementDate": "2026-05-14T08:44:00.826Z",
    "positionId": 0,
    "orderId": 0,
    "netAmount": 0,
    "activityType": "ACTIVITY_CORRECTION",
    "transferItems": [
      {
        "instrument": {
          "cusip": "string",
          "symbol": "string",
          "description": "string",
          "instrumentId": 0,
          "netChange": 0,
          "type": "SWEEP_VEHICLE"
        },
        "amount": 0,
        "cost": 0,
        "price": 0,
        "feeType": "COMMISSION",
        "positionEffect": "OPENING"
      }
    ]
  }
]
```

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

---

## `GET /userPreference` <a id="get-userreference"></a>

**Get user preference information for the logged in user.**

Get user preference information for the logged in user.

- **operationId:** `UserPreference-getUserPreference`

### Responses

- **200** (success) - List of user preference values.
- **400** (error) - An error message indicating the validation problem with the request.
- **401** (error) - An error message indicating either authorization token is invalid or there are no accounts the caller is allowed to view or use for trading that are registered with the provided third party application
- **403** (error) - An error message indicating the caller is forbidden from accessing this service
- **404** (error) - An error message indicating the resource is not found
- **500** (error) - An error message indicating there was an unexpected server error
- **503** (error) - An error message indicating server has a temporary problem responding

**Success response example:**

```json
[
  {
    "accounts": [
      {
        "accountNumber": "string",
        "primaryAccount": false,
        "type": "string",
        "nickName": "string",
        "accountColor": "string",
        "displayAcctId": "string",
        "autoPositionEffect": false
      }
    ],
    "streamerInfo": [
      {
        "streamerSocketUrl": "string",
        "schwabClientCustomerId": "string",
        "schwabClientCorrelId": "string",
        "schwabClientChannel": "string",
        "schwabClientFunctionId": "string"
      }
    ],
    "offers": [
      {
        "level2Permissions": false,
        "mktDataPermission": "string"
      }
    ]
  }
]
```

### Response headers

All responses (success and error) include `Schwab-Client-CorrelId` / `Schwab-Client-CorrelID` (string, auto-generated correlation ID). No other response headers are documented in the source HTML for this endpoint.

### Notes

- `streamerInfo` provides the WebSocket endpoint plus client correlation IDs needed to subscribe to the Schwab Streaming API. `offers` includes the Level-2 permission flag and market-data permission descriptor.

---

## Appendix A - Schema-side enum reference (counts only)

The following enum types are referenced inside Order / Transaction / Preview / Instrument schemas. The source HTML carries only the **count** of values, not the values themselves (see Overview > Source-spec gap). Refer to the live Swagger UI or the published OpenAPI JSON to enumerate them.

| Type | Used in | # values |
|---|---|---|
| `session` | order | 4 |
| `duration` | order | 8 |
| `orderType` | order | 15 |
| `orderTypeRequest` | order (input-only; no `UNKNOWN`) | 14 |
| `complexOrderStrategyType` | order | 21 |
| `requestedDestination` | order | 12 |
| `stopPriceLinkBasis` | order | 9 |
| `stopPriceLinkType` | order | 3 |
| `stopPriceOffset` | order | 5 |
| `stopType` | order | 5 |
| `priceLinkBasis` | order | 9 |
| `priceLinkType` | order | 3 |
| `taxLotMethod` | order | 7 |
| `specialInstruction` | order | 3 |
| `orderStrategyType` | order | 9 |
| `status` | order (response + query param) | 21 |
| `amountIndicator` | previewOrder | 5 |
| `settlementInstruction` | previewOrder | 4 |
| `OrderValidationDetail` | previewOrder.orderValidationResult | 5 |
| `APIRuleAction` | previewOrder | 5 |
| `FeeLeg` | previewOrder.commissionAndFee | 25 |
| `FeeValue` | previewOrder.commissionAndFee | 25 |
| `FeeType` | previewOrder.commissionAndFee | 25 |
| `CollectiveInvestment` | instrument | 10 |
| `instruction` | order leg | 10 |
| `assetType` | previewOrder.orderLegs[].assetType | 11 |
| `apiOrderStatus` | misc | 21 |
| `TransactionType` | transactions.type | 15 |
| `AccountNumberHash` | accountNumbers response model | 4 |

**Status enum values (recoverable from query-param dropdown):** `AWAITING_PARENT_ORDER`, `AWAITING_CONDITION`, `AWAITING_STOP_CONDITION`, `AWAITING_MANUAL_REVIEW`, `ACCEPTED`, `AWAITING_UR_OUT`, `PENDING_ACTIVATION`, `QUEUED`, `WORKING`, `REJECTED`, `PENDING_CANCEL`, `CANCELED`, `PENDING_REPLACE`, `REPLACED`, `FILLED`, `EXPIRED`, `NEW`, `AWAITING_RELEASE_TIME`, `PENDING_ACKNOWLEDGEMENT`, `PENDING_RECALL`, `UNKNOWN`.

**TransactionType enum values (recoverable from query-param dropdown):** `TRADE`, `RECEIVE_AND_DELIVER`, `DIVIDEND_OR_INTEREST`, `ACH_RECEIPT`, `ACH_DISBURSEMENT`, `CASH_RECEIPT`, `CASH_DISBURSEMENT`, `ELECTRONIC_FUND`, `WIRE_OUT`, `WIRE_IN`, `JOURNAL`, `MEMORANDUM`, `MARGIN_CALL`, `MONEY_MARKET`, `SMA_ADJUSTMENT`.

## Appendix B - Order object schema (place / replace request body, GET response element)

The Order object below is the canonical request body for `POST /accounts/{n}/orders` and `PUT /accounts/{n}/orders/{orderId}`, and the canonical element of the response array for `GET /accounts/{n}/orders`, `GET /orders`, and the response object for `GET /accounts/{n}/orders/{orderId}`. Field values shown are example placeholders; enum fields show one valid value each (full enum lists not recoverable from this HTML - see Overview).

```json
{
  "session": "NORMAL",
  "duration": "DAY",
  "orderType": "MARKET",
  "cancelTime": "2026-05-14T08:44:00.780Z",
  "complexOrderStrategyType": "NONE",
  "quantity": 0,
  "filledQuantity": 0,
  "remainingQuantity": 0,
  "destinationLinkName": "string",
  "releaseTime": "2026-05-14T08:44:00.780Z",
  "stopPrice": 0,
  "stopPriceLinkBasis": "MANUAL",
  "stopPriceLinkType": "VALUE",
  "stopPriceOffset": 0,
  "stopType": "STANDARD",
  "priceLinkBasis": "MANUAL",
  "priceLinkType": "VALUE",
  "price": 0,
  "taxLotMethod": "FIFO",
  "orderLegCollection": [
    {
      "orderLegType": "EQUITY",
      "legId": 0,
      "instrument": {
        "cusip": "string",
        "symbol": "string",
        "description": "string",
        "instrumentId": 0,
        "netChange": 0,
        "type": "SWEEP_VEHICLE"
      },
      "instruction": "BUY",
      "positionEffect": "OPENING",
      "quantity": 0,
      "quantityType": "ALL_SHARES",
      "divCapGains": "REINVEST",
      "toSymbol": "string"
    }
  ],
  "activationPrice": 0,
  "specialInstruction": "ALL_OR_NONE",
  "orderStrategyType": "SINGLE",
  "orderId": 0,
  "cancelable": false,
  "editable": false,
  "status": "AWAITING_PARENT_ORDER",
  "enteredTime": "2026-05-14T08:44:00.780Z",
  "closeTime": "2026-05-14T08:44:00.780Z",
  "accountNumber": 0,
  "orderActivityCollection": [
    {
      "activityType": "EXECUTION",
      "executionType": "FILL",
      "quantity": 0,
      "orderRemainingQuantity": 0,
      "executionLegs": [
        {
          "legId": 0,
          "price": 0,
          "quantity": 0,
          "mismarkedQuantity": 0,
          "instrumentId": 0,
          "time": "2026-05-14T08:44:00.780Z"
        }
      ]
    }
  ],
  "replacingOrderCollection": [
    "string"
  ],
  "childOrderStrategies": [
    "string"
  ],
  "statusDescription": "string"
}
```

**Field cheat sheet** (types inferred from example values; consult live Swagger / published OpenAPI JSON for authoritative types):

- `session` (string enum, 4 values) - order session window
- `duration` (string enum, 8 values) - time-in-force
- `orderType` (string enum, 15 values) - MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP, etc. (only the example value `MARKET` is materialized in the HTML)
- `cancelTime` (ISO-8601 datetime) - optional GTC cancel-at
- `complexOrderStrategyType` (string enum, 21 values) - `NONE` / spread / strangle / etc.
- `quantity` / `filledQuantity` / `remainingQuantity` (number)
- `requestedDestination` (string enum, 12 values; response-side - present on `GET /accounts/{n}/orders` schema, NOT on the place-order body example)
- `destinationLinkName` (string)
- `releaseTime` (ISO-8601)
- `stopPrice` (number); `stopPriceLinkBasis` / `stopPriceLinkType` / `stopPriceOffset` (string enums + number) - link a stop to a reference
- `stopType` (string enum, 5 values) - example `STANDARD`
- `price` (number); `priceLinkBasis` / `priceLinkType` (string enums) - link a limit to a reference
- `taxLotMethod` (string enum, 7 values) - example `FIFO`
- `orderLegCollection` (array of OrderLeg objects):
  - `orderLegType` (string enum) - example `EQUITY`
  - `legId` (integer)
  - `instrument`: `{ cusip, symbol, description, instrumentId, netChange, type }` - `type` is an assetType enum, 11 values; example `SWEEP_VEHICLE`
  - `instruction` (string enum, 10 values) - example `BUY`
  - `positionEffect` (string enum) - example `OPENING`
  - `quantity` (number)
  - `quantityType` (string enum) - example `ALL_SHARES`
  - `divCapGains` (string enum) - example `REINVEST`
  - `toSymbol` (string) - for mutual fund exchange instructions
- `activationPrice` (number)
- `specialInstruction` (string enum, 3 values) - example `ALL_OR_NONE`
- `orderStrategyType` (string enum, 9 values) - example `SINGLE`
- `orderId` (integer)
- `cancelable` / `editable` (boolean) - response-side
- `status` (string enum, 21 values) - see status enum list in Appendix A above for the full list
- `enteredTime` / `closeTime` (ISO-8601) - response-side
- `accountNumber` (integer in body, encrypted hash in URL path)
- `orderActivityCollection` (array) - response-side; each entry has `activityType` (`EXECUTION` example), `executionType` (`FILL` example), `quantity`, `orderRemainingQuantity`, and `executionLegs[]` with `legId` / `price` / `quantity` / `mismarkedQuantity` / `instrumentId` / `time`
- `replacingOrderCollection` / `childOrderStrategies` (arrays of strings) - for replace and conditional / OCO / Trigger flows
- `statusDescription` (string) - response-side
- `tag` (string) - present in `GET /accounts/{n}/orders` response (not in the place-order example body)

**Divergences between place-order body and get-order response:**

- `GET` response adds `requestedDestination` and `tag` fields.
- `POST` body example carries the same status / response-side fields (`cancelable`, `editable`, `status`, `enteredTime`, `closeTime`, `orderActivityCollection`, etc.) but these are server-populated on response, not caller-supplied. Treat the schema as a superset; consumers should send only the fields the platform expects on input.

## Appendix C - Preview order response schema highlights

`POST /accounts/{n}/previewOrder` returns a richer object than placeOrder/getOrder:

- `orderId` (integer)
- `orderStrategy` - flattened order view including:
  - `accountNumber`, `advancedOrderType` (example `NONE`), `closeTime`, `enteredTime`
  - `orderBalance`: `{ orderValue, projectedAvailableFund, projectedBuyingPower, projectedCommission }`
  - `orderStrategyType` (example `SINGLE`), `orderVersion`
  - `session`, `status` (response-side status enum), `allOrNone`, `discretionary`, `duration`
  - `filledQuantity`, `orderType`, `orderValue`, `price`, `quantity`, `remainingQuantity`
  - `sellNonMarginableFirst` (boolean), `settlementInstruction` (string enum, 4 values; example `REGULAR`), `strategy` (example `NONE`)
  - `amountIndicator` (string enum, 5 values; example `DOLLARS`)
  - `orderLegs[]`: `{ askPrice, bidPrice, lastPrice, markPrice, projectedCommission, quantity, finalSymbol, legId, assetType (enum, 11 values, example EQUITY), instruction (enum, 10 values, example BUY) }`
- `orderValidationResult`: object with five parallel arrays (`alerts`, `accepts`, `rejects`, `reviews`, `warns`), each entry: `{ validationRuleName, message, activityMessage, originalSeverity (APIRuleAction enum, 5 values, example ACCEPT), overrideName, overrideSeverity (APIRuleAction enum) }`
- `commissionAndFee`: object with three parallel sub-objects:
  - `commission.commissionLegs[].commissionValues[]`: `{ value (number), type (FeeType enum, 25 values, example COMMISSION) }`
  - `fee.feeLegs[].feeValues[]`: same shape as commissionValues
  - `trueCommission.commissionLegs[].commissionValues[]`: same shape

## Appendix D - Transaction object schema

Element shape for `GET /accounts/{n}/transactions` and `GET /accounts/{n}/transactions/{transactionId}`:

- `activityId` (integer)
- `time` (ISO-8601)
- `user`: `{ cdDomainId, login, type (example ADVISOR_USER), userId, systemUserName, firstName, lastName, brokerRepCode }`
- `description` (string)
- `accountNumber` (string - the encrypted hash)
- `type` (TransactionType enum, 15 values; values listed in Appendix A)
- `status` (example `VALID` - enum size not surfaced in HTML)
- `subAccount` (example `CASH` - enum)
- `tradeDate` (ISO-8601)
- `settlementDate` (ISO-8601)
- `positionId` (integer)
- `orderId` (integer)
- `netAmount` (number)
- `activityType` (example `ACTIVITY_CORRECTION` - enum)
- `transferItems[]`: `{ instrument: { cusip, symbol, description, instrumentId, netChange, type (assetType enum) }, amount, cost, price, feeType (FeeType enum, 25 values, example COMMISSION), positionEffect (example OPENING) }`

## Appendix E - UserPreference object schema

Response array element for `GET /userPreference`:

- `accounts[]`: `{ accountNumber (plain text), primaryAccount (boolean), type (string), nickName (string), accountColor (string), displayAcctId (string), autoPositionEffect (boolean) }`
- `streamerInfo[]`: `{ streamerSocketUrl, schwabClientCustomerId, schwabClientCorrelId, schwabClientChannel, schwabClientFunctionId }` - all strings; required to bootstrap the Schwab Streaming WebSocket API.
- `offers[]`: `{ level2Permissions (boolean), mktDataPermission (string) }`
