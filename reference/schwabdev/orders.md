# Schwabdev Orders

**Source:** https://tylerebowers.github.io/Schwabdev/pages/orders.html
**Extraction date:** 2026-05-13
**Library:** schwabdev — Python wrapper around the Schwab Trader API
**Cross-reference:** Companion to `reference/schwab-api/account-specification.md` and `reference/schwab-api/account-documentation.md` (Schwab portal POST `/accounts/{accountNumber}/orders`).

---

## Helper Functions

The schwabdev client exposes five order-lifecycle helpers. Each takes the encrypted `account_hash` (NOT the plain account number) returned by `client.account_linked()` / `client.accounts_numbers()`.

```python
client.place_order(account_hash: str, order: dict) -> Response
client.order_details(account_hash: str, order_id: int) -> Response
client.cancel_order(account_hash: str, order_id: int) -> Response
client.replace_order(account_hash: str, order_id: int, order: dict) -> Response
client.preview_order(account_hash: str, order: dict) -> Response
```

### Response Handling

`place_order` does **NOT** return the order_id in the response body. Schwab returns it in the `Location` HTTP response header. Extract via:

```python
resp = client.place_order(account_hash, order)
order_id = resp.headers.get('location', '/').split('/')[-1]
# Check resp.status_code (201 Created on success per Schwab spec)
```

### OAuth / Auth Scope / Idempotency

**The schwabdev orders page documents no order-specific OAuth scope, no auth header behavior, no idempotency key, and no client-side replay guard.** Authentication is handled at client construction time (refresh-token rotation; OAuth bearer header set transparently by the schwabdev client on every request).

There is no idempotency-token mechanism in either the schwabdev client surface or the underlying Schwab API. Network-level retries on `place_order` could double-fill — caller is responsible for replay protection.

---

## Rate Limits & Constraints

Verbatim from source:

> "There is a limit of **120 orders per minute** and **4000 orders per day**."

- Orders support **equities and options only** via this surface.
- **Fractional orders unsupported.**

---

## Enums & Constants

The schwabdev page surfaces the following enum values across the recipes (no top-level Python `Enum` class — values are string literals embedded in payload dicts):

### orderType

| Constant | Value |
| --- | --- |
| MARKET | `"MARKET"` |
| LIMIT | `"LIMIT"` |
| STOP | `"STOP"` |
| STOP_LIMIT | `"STOP_LIMIT"` |
| TRAILING_STOP | `"TRAILING_STOP"` |
| NET_DEBIT | `"NET_DEBIT"` |
| NET_CREDIT | `"NET_CREDIT"` |

### session

| Constant | Value |
| --- | --- |
| NORMAL | `"NORMAL"` |

(The Schwab portal docs additionally enumerate AM, PM, SEAMLESS — but schwabdev examples only show NORMAL.)

### duration

| Constant | Value |
| --- | --- |
| DAY | `"DAY"` |
| GOOD_TILL_CANCEL | `"GOOD_TILL_CANCEL"` |

### instruction (equity)

| Constant | Value |
| --- | --- |
| BUY | `"BUY"` |
| SELL | `"SELL"` |

### instruction (option)

| Constant | Value |
| --- | --- |
| BUY_TO_OPEN | `"BUY_TO_OPEN"` |
| SELL_TO_OPEN | `"SELL_TO_OPEN"` |

(BUY_TO_CLOSE / SELL_TO_CLOSE not shown in schwabdev examples but valid per Schwab spec.)

### orderStrategyType

| Constant | Value |
| --- | --- |
| SINGLE | `"SINGLE"` |
| TRIGGER | `"TRIGGER"` |
| OCO | `"OCO"` |

### complexOrderStrategyType

| Constant | Value |
| --- | --- |
| NONE | `"NONE"` |
| CUSTOM | `"CUSTOM"` |

### assetType (instrument)

| Constant | Value |
| --- | --- |
| EQUITY | `"EQUITY"` |
| OPTION | `"OPTION"` |

### Trailing-stop link fields

| Constant | Value |
| --- | --- |
| stopPriceLinkBasis | `"BID"` (others MARK/ASK/LAST per Schwab spec; only BID shown here) |
| stopPriceLinkType | `"VALUE"` (others PERCENT/TICK per Schwab spec; only VALUE shown here) |

**Gap-coverage vs Schwab portal Spec page:** schwabdev surfaces orderType / orderStrategyType / complexOrderStrategyType / instruction / assetType / duration enum values used in real payloads. The Schwab portal Spec page itself was incomplete on these — schwabdev fills the gap operationally (by example) but is NOT exhaustive (e.g., does not show every legal value for `session` or every `instruction` variant).

---

## JSON Payload Recipes

All payloads below are **verbatim** from the schwabdev orders page. Pass each dict as the `order` argument to `client.place_order(account_hash, order)`.

### Market Buy — 10 AMD shares

```json
{
  "orderType": "MARKET",
  "session": "NORMAL",
  "duration": "DAY",
  "orderStrategyType": "SINGLE",
  "orderLegCollection": [
    {
      "instruction": "BUY",
      "quantity": 10,
      "instrument": {
        "symbol": "AMD",
        "assetType": "EQUITY"
      }
    }
  ]
}
```

### Limit Buy — 4 INTC @ $10.00

```json
{
  "orderType": "LIMIT",
  "session": "NORMAL",
  "duration": "DAY",
  "orderStrategyType": "SINGLE",
  "price": "10.00",
  "orderLegCollection": [
    {
      "instruction": "BUY",
      "quantity": 4,
      "instrument": {
        "symbol": "INTC",
        "assetType": "EQUITY"
      }
    }
  ]
}
```

### Sell Options — 3 contracts (open short put)

```json
{
  "orderType": "LIMIT",
  "session": "NORMAL",
  "price": 1.0,
  "duration": "GOOD_TILL_CANCEL",
  "orderStrategyType": "SINGLE",
  "complexOrderStrategyType": "NONE",
  "orderLegCollection": [
    {
      "instruction": "SELL_TO_OPEN",
      "quantity": 3,
      "instrument": {
        "symbol": "AAPL  240517P00190000",
        "assetType": "OPTION"
      }
    }
  ]
}
```

### Buy Options — 3 contracts (open long put)

```json
{
  "orderType": "LIMIT",
  "session": "NORMAL",
  "price": 0.1,
  "duration": "GOOD_TILL_CANCEL",
  "orderStrategyType": "SINGLE",
  "complexOrderStrategyType": "NONE",
  "orderLegCollection": [
    {
      "instruction": "BUY_TO_OPEN",
      "quantity": 3,
      "instrument": {
        "symbol": "AAPL  240517P00190000",
        "assetType": "OPTION"
      }
    }
  ]
}
```

### Vertical Put Spread — buy 2 / sell 2 (debit)

```json
{
  "orderType": "NET_DEBIT",
  "session": "NORMAL",
  "price": "0.10",
  "duration": "DAY",
  "orderStrategyType": "SINGLE",
  "orderLegCollection": [
    {
      "instruction": "BUY_TO_OPEN",
      "quantity": 2,
      "instrument": {
        "symbol": "XYZ   240315P00045000",
        "assetType": "OPTION"
      }
    },
    {
      "instruction": "SELL_TO_OPEN",
      "quantity": 2,
      "instrument": {
        "symbol": "XYZ   240315P00043000",
        "assetType": "OPTION"
      }
    }
  ]
}
```

### Conditional Order (One-Triggers-Another) — TRIGGER

Parent buy fills → child sell submitted.

```json
{
  "orderType": "LIMIT",
  "session": "NORMAL",
  "price": "34.97",
  "duration": "DAY",
  "orderStrategyType": "TRIGGER",
  "orderLegCollection": [
    {
      "instruction": "BUY",
      "quantity": 10,
      "instrument": {
        "symbol": "XYZ",
        "assetType": "EQUITY"
      }
    }
  ],
  "childOrderStrategies": [
    {
      "orderType": "LIMIT",
      "session": "NORMAL",
      "price": "42.03",
      "duration": "DAY",
      "orderStrategyType": "SINGLE",
      "orderLegCollection": [
        {
          "instruction": "SELL",
          "quantity": 10,
          "instrument": {
            "symbol": "ABC",
            "assetType": "EQUITY"
          }
        }
      ]
    }
  ]
}
```

### One-Cancels-Other (OCO) — bracket exit

Profit-target limit on one side; stop-limit on the other. Either fill cancels the sibling.

```json
{
  "orderStrategyType": "OCO",
  "childOrderStrategies": [
    {
      "orderType": "LIMIT",
      "session": "NORMAL",
      "price": "45.97",
      "duration": "DAY",
      "orderStrategyType": "SINGLE",
      "orderLegCollection": [
        {
          "instruction": "SELL",
          "quantity": 2,
          "instrument": {
            "symbol": "XYZ",
            "assetType": "EQUITY"
          }
        }
      ]
    },
    {
      "orderType": "STOP_LIMIT",
      "session": "NORMAL",
      "price": "37.00",
      "stopPrice": "37.03",
      "duration": "DAY",
      "orderStrategyType": "SINGLE",
      "orderLegCollection": [
        {
          "instruction": "SELL",
          "quantity": 2,
          "instrument": {
            "symbol": "ABC",
            "assetType": "EQUITY"
          }
        }
      ]
    }
  ]
}
```

### One-Triggers-One-Cancels-Other (OTOCO) — entry + bracket

Parent buy fills → child OCO (target + stop) submitted. This is the canonical "enter with brackets pre-armed" recipe.

```json
{
  "orderStrategyType": "TRIGGER",
  "session": "NORMAL",
  "duration": "DAY",
  "orderType": "LIMIT",
  "price": 14.97,
  "orderLegCollection": [
    {
      "instruction": "BUY",
      "quantity": 5,
      "instrument": {
        "assetType": "EQUITY",
        "symbol": "XYZ"
      }
    }
  ],
  "childOrderStrategies": [
    {
      "orderStrategyType": "OCO",
      "childOrderStrategies": [
        {
          "orderStrategyType": "SINGLE",
          "session": "NORMAL",
          "duration": "GOOD_TILL_CANCEL",
          "orderType": "LIMIT",
          "price": 15.27,
          "orderLegCollection": [
            {
              "instruction": "SELL",
              "quantity": 5,
              "instrument": {
                "assetType": "EQUITY",
                "symbol": "ABC"
              }
            }
          ]
        },
        {
          "orderStrategyType": "SINGLE",
          "session": "NORMAL",
          "duration": "GOOD_TILL_CANCEL",
          "orderType": "STOP",
          "stopPrice": 11.27,
          "orderLegCollection": [
            {
              "instruction": "SELL",
              "quantity": 5,
              "instrument": {
                "assetType": "EQUITY",
                "symbol": "IJK"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### Trailing Stop — 10 XYZ, $10 trail off bid

```json
{
  "complexOrderStrategyType": "NONE",
  "orderType": "TRAILING_STOP",
  "session": "NORMAL",
  "stopPriceLinkBasis": "BID",
  "stopPriceLinkType": "VALUE",
  "stopPriceOffset": 10,
  "duration": "DAY",
  "orderStrategyType": "SINGLE",
  "orderLegCollection": [
    {
      "instruction": "SELL",
      "quantity": 10,
      "instrument": {
        "symbol": "XYZ",
        "assetType": "EQUITY"
      }
    }
  ]
}
```

### Iron Condor — 4-leg option combo (CUSTOM complex strategy)

Template form — operator substitutes `price`, `quantity`, and four option symbols.

```json
{
  "orderStrategyType": "SINGLE",
  "orderType": "NET_CREDIT",
  "price": "price",
  "orderLegCollection": [
    {
      "instruction": "SELL_TO_OPEN",
      "quantity": "quantity",
      "instrument": {
        "assetType": "OPTION",
        "symbol": "short_call_symbol"
      }
    },
    {
      "instruction": "BUY_TO_OPEN",
      "quantity": "quantity",
      "instrument": {
        "assetType": "OPTION",
        "symbol": "long_call_symbol"
      }
    },
    {
      "instruction": "SELL_TO_OPEN",
      "quantity": "quantity",
      "instrument": {
        "assetType": "OPTION",
        "symbol": "short_put_symbol"
      }
    },
    {
      "instruction": "BUY_TO_OPEN",
      "quantity": "quantity",
      "instrument": {
        "assetType": "OPTION",
        "symbol": "long_put_symbol"
      }
    }
  ],
  "complexOrderStrategyType": "CUSTOM",
  "duration": "DAY",
  "session": "NORMAL"
}
```

---

## Cross-Reference: Schwab Portal Sample-Order Coverage

The Schwab portal documentation we captured at `reference/schwab-api/account-documentation.md` shows 7 sample order types. Mapping to schwabdev recipes:

| Schwab portal sample | schwabdev recipe (this doc) |
| --- | --- |
| Buy Market: Stock | Market Buy — 10 AMD |
| Buy Limit: Single Option | Buy Options — 3 contracts |
| Buy Limit: Vertical Call Spread | Vertical Put Spread (analogous; substitute calls) |
| Conditional Order: One Triggers Another | Conditional Order (TRIGGER) |
| Conditional Order: One Cancels Another | One-Cancels-Other (OCO) |
| Conditional Order: One Triggers a One Cancels Another | One-Triggers-One-Cancels-Other (OTOCO) |
| Sell Trailing Stop: Stock | Trailing Stop — 10 XYZ |

**schwabdev adds:** Limit Buy stock, Sell Options (open short), and Iron Condor 4-leg combo. Together the two sources cover the full DST + Minervini swing-trading operational surface (market entry, limit entry, single-target sell, OCO bracket, OTOCO bracket-on-entry, trailing-stop exit) plus options/spreads.

---

## Notes

### Option Symbol Format

21-character fixed-width string:

```
[Underlying: 6 chars space-padded] [Expiration: YYMMDD] [Call/Put: C or P] [Strike × 1000: 8 chars zero-padded]
```

Example: `AAPL  240517P00190000` = AAPL 2024-05-17 $190.00 Put.
Example: `XYZ   240315P00045000` = XYZ 2024-03-15 $45.00 Put.

### Price Field Types

The page mixes string and numeric `price` values across recipes (`"10.00"` in limit buy; `1.0` in sell options; `14.97` in OTOCO). Both forms accepted. **Recommendation:** standardize on string-formatted decimals to avoid float-precision surprises at the cents level.

### Validation Behavior

**No client-side validation helpers documented on this page.** The schwabdev client appears to pass `order` dicts through to the Schwab endpoint unchanged. All field-shape / enum-value / cross-field validation is performed server-side by Schwab; errors surface via HTTP status codes and response body.

---

## Extraction Gaps

The following were NOT documented in the source page; consult Schwab's official Trader API spec at `reference/schwab-api/account-specification.md` for canonical detail:

- Full enum tables for `session` (Schwab spec: NORMAL / AM / PM / SEAMLESS)
- Full enum tables for `instruction` covering BUY_TO_CLOSE / SELL_TO_CLOSE (option-close legs)
- Full enum tables for `stopPriceLinkBasis` (MARK / ASK / BID / LAST / TRIGGER / LAST_INDEX)
- Full enum tables for `stopPriceLinkType` (VALUE / PERCENT / TICK)
- Full enum tables for `complexOrderStrategyType` (NONE / COVERED / VERTICAL / BACK_RATIO / CALENDAR / DIAGONAL / STRADDLE / STRANGLE / COLLAR_SYNTHETIC / BUTTERFLY / CONDOR / IRON_CONDOR / VERTICAL_ROLL / COLLAR_WITH_STOCK / DOUBLE_DIAGONAL / UNBALANCED_BUTTERFLY / UNBALANCED_CONDOR / UNBALANCED_IRON_CONDOR / UNBALANCED_VERTICAL_ROLL / MUTUAL_FUND_SWAP / CUSTOM)
- OAuth scope requirements per endpoint
- Idempotency mechanisms
- Field constraints (price precision, quantity bounds, max legs per order)
- Order-status enums (returned by `order_details`)
- Server-side validation error catalog
- Retry / replay-protection guidance
