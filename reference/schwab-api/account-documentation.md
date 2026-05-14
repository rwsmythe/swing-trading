# Schwab Trader API — Accounts and Trading Production Documentation

**Source:** https://developer.schwab.com/products/trader-api-individual/details/documentation/Retail%20Trader%20API%20Production
**Extracted:** 2026-05-13
**Product:** Trader API - Individual (Retail Trader API Production)

---

## Schwab & API Security

Schwab uses the OAuth 2 authorization framework over HTTPS to provide delegated access to APIs, replacing username+password with encrypted access tokens.

**Standards references:**
- OAuth 2 — https://tools.ietf.org/html/rfc6749
- Bearer Token — https://tools.ietf.org/html/rfc6750

Bearer tokens are used for the OAuth `authorization_code` Grant Type.

---

## Three Legged Workflow

Three Legged OAuth allows Users to grant an App permission to access Protected Resources (e.g., account information) without disclosing credentials. OAuth directs Users to Schwab's **Login Micro Site (LMS)** to perform the **Consent and Grant (CAG)** process, where the User selects which accounts to share with the Application. On completion, the User is redirected back to the Application.

### Key Terms

#### App
OAuth registration is managed by Apps on the Dev Portal. Apps are owned by a Company and manage Application access to Protected Resource data.

- **Client ID & Client Secret** — Unique string values generated when the App is registered with the OAuth server. Identify and control App access to Protected Resources. Permissions to use an API Product are tied to the App and its Client ID. The Client Secret must never be exposed outside the OAuth Flow / Dev Portal and should be stored securely.
- **Callback URL** (`redirect_uri`) — Used to redirect the User and OAuth Flow back to the Application; the URL "host" of the Application's landing page.
  - Must be HTTPS.
  - Multiple URLs supported, comma-separated.
  - 255-character limit on the field including all URLs.
  - Localhost Callback URL allowed: `https://127.0.0.1`
- **Display Name** — Established at App creation; shown to the User during CAG to confirm consent is granted to the appropriate App.
- **Environment** — Sandbox (test data) or Production (live data). The Trader API Sandbox environments will be available later this year.
- **Product Subscription** — Apps may subscribe to a single API Product (e.g., Trader API - Individual).

#### Third-Party Application (User-Agent / "Application")
Any website, stand-alone application, or HTTP platform that uses an OAuth Bearer token to access Protected Resource data on behalf of a User. Distinct from the "App" defined above.

#### CAG — Consent and Grant
Using LMS, Schwab Users approve Application access and select the accounts they wish to link.

#### LMS — Login Micro Site
A website where Users log into Schwab directly from an Application to perform CAG activities.

#### LOB — Line of Business
Owner of an API Product or functional grouping of APIs on Schwab's Dev Portal (e.g., Data Aggregation Services, Tax Services). Companies may request access to API Products owned by an LOB.

#### Roles
IETF's OAuth 2 framework defines four Roles (e.g., Resource Owner / User) referenced throughout this documentation.

#### User
The Protected Resource Owner who authorizes Application access. Used interchangeably with: Schwab Client, Resource Owner, End User, App User. Reference: https://tools.ietf.org/html/rfc6749#section-1.1

#### Token
Several token types are used in OAuth 2 Flows; all are string values representing scope, lifetime, and other attributes.

- **Access Token** — Used in place of username+password to access a User's Protected Resources. **A Trader API access token is valid for 30 minutes after creation.**
- **Bearer Token** — The Access Token in the context of an API call; passed in the Authorization header as `Bearer {access_token_value}`.
- **Refresh Token** — Renews access to a User's Protected Resources. Used (at any time before/after access_token expiration) to request a new Access Token without repeating the full Flow. Provided alongside the initial Access Token. **A Trader API refresh token is valid for 7 days after creation.** Upon expiration, a new refresh token must be created via the `authorization_code` Grant Type (CAG/LMS).

### Three Legged Flow Entities

- **Resource Owner (User)** — Schwab Client who owns and grants access to Protected Resources.
- **OAuth Client (App)** — The Dev Portal App. Uses its Client ID and Client Secret to request access to Protected Resources on behalf of the User.
- **User-Agent (3rd-party application)** — The Application/website the Resource Owner uses to interact with Schwab APIs.
- **Authorization Server (OAuth server)** — Authenticates OAuth Clients and issues Tokens.
- **Resource Server** — Schwab server hosting Protected Resources (financial account information).

### OAuth Flow — Sequence Diagram

[sequence diagram — see source HTML; no extractable text content. The flow is described step-by-step below in Steps 1–4.]

---

## Step 1: App Authorization

Authorizes a specific App to access Protected Resources on behalf of the Resource Owner. The Application passes registered App parameters to direct the Flow to LMS. After CAG completes in LMS, an Authorization Code (`code`) is returned in the landing URL via redirect. The `code` is used in Step 2 to create the initial Refresh and Access Tokens.

Following CAG activities:
- An Authorization Code will be provided and can be exchanged for an Access Token in Step 2.
- The Access Token can be used to call API Product endpoints after the Flow completes. Valid for 30 minutes.
- Once a Refresh Token is invalidated or expired (7 days), CAG must be completed again to restart the OAuth flow.

**Request Template — Authorization URL**

```http
GET https://api.schwabapi.com/v1/oauth/authorize?client_id={CONSUMER_KEY}&redirect_uri={APP_CALLBACK_URL}
```

**Response Template — Final landing URL**

```
https://{APP_CALLBACK_URL}/?code={AUTHORIZATION_CODE_GENERATED}&session={SESSION_ID}
```

The website will redirect to a 404 page, but the address bar will contain the `code` needed for the next step.

---

## Step 2: Access Token Creation

```
POST https://api.schwabapi.com/v1/oauth/token
```

Exchanges the `code` (authorization_code) returned above for the initial `access_token`. An Access Token is valid for 30 minutes.

**Important:** The `code` within this request must be URL-decoded prior to making the request (e.g., should end in `@` instead of `%40`).

**Request Example (cURL):**

```bash
curl -X POST https://api.schwabapi.com/v1/oauth/token \
  -H 'Authorization: Basic {BASE64_ENCODED_Client_ID:Client_Secret}' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=authorization_code&code={AUTHORIZATION_CODE_VALUE}&redirect_uri=https://example_url.com/callback_example'
```

**Response Example:**

```json
{
  "expires_in": 1800,
  "token_type": "Bearer",
  "scope": "api",
  "refresh_token": "{REFRESH_TOKEN_HERE}",
  "access_token": "{ACCESS_TOKEN_HERE}",
  "id_token": "{JWT_HERE}"
}
```

- `expires_in` — Seconds the `access_token` is valid for (1800 = 30 min).
- `refresh_token` — Valid for 7 days.
- `access_token` — Valid for 30 minutes.

---

## Step 3: Make an API Call

API Product calls use the following authorization header format:

```
Authorization: Bearer {access_token}
```

Example:

```
Authorization: Bearer I0.kC95zyI039S-YTEw=
```

---

## Step 4: Refresh an Access Token (with existing Refresh Token)

```
POST https://api.schwabapi.com/v1/oauth/token
```

Renews access to a User's Protected Resources before, or soon after, the current `access_token` expires.

**Request Example (cURL):**

```bash
curl -X POST https://api.schwabapi.com/v1/oauth/token \
  -H 'Authorization: Basic {BASE64_ENCODED_Client_ID:Client_Secret}' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=refresh_token&refresh_token={REFRESH_TOKEN_GENERATED_FROM_PRIOR_STEP}'
```

**Response Example:**

```json
{
  "expires_in": 1800,
  "token_type": "Bearer",
  "scope": "api",
  "refresh_token": "{REFRESH_TOKEN_HERE}",
  "access_token": "{NEW_ACCESS_TOKEN_HERE}",
  "id_token": "{JWT_HERE}"
}
```

Same field semantics as Step 2: `refresh_token` valid for 7 days; `access_token` valid for 30 minutes.

---

## Should I Refresh or Restart OAuth?

The Refresh Token step (Step 4) **can be executed before an Access Token expires**.

**Refresh Token (Step 4) is NO LONGER AVAILABLE once the Refresh Token is:**
- Expired (after 7 days), OR
- Invalidated (e.g., User password reset).

**If the refresh token is no longer valid, App Authorization (Step 1) and Access Token Creation (Step 2) MUST be repeated to restart the OAuth Flow.**

---

## Place Order Samples

Examples specific to orders for use in Schwab Trader API POST and PUT Order endpoints. Order entry is only available for `assetType` `'EQUITY'` and `'OPTION'` at this time.

**Throttle limits:** Trader API applications (Individual and Commercial) are limited in PUT/POST/DELETE order requests per minute per account, based on application properties specified during registration. Throttle limits can be set from 0 to 120 requests per minute per account. **GET order requests are unthrottled.** Contact TraderAPI@schwab.com for further info.

### Options Symbology

Format: `Underlying Symbol (6 chars incl. spaces) | Expiration (6 chars) | Call/Put (1 char) | Strike Price (5+3=8 chars)`

| Option Symbol | Stock | Expiration | Type | Strike |
|---|---|---|---|---|
| `XYZ   210115C00050000` | XYZ | 2021/01/15 | Call | $50.00 |
| `XYZ   210115C00055000` | XYZ | 2021/01/15 | Call | $55.00 |
| `XYZ   210115C00062500` | XYZ | 2021/01/15 | Call | $62.50 |

### Instruction Compatibility — EQUITY vs OPTION

| Instruction | EQUITY (Stocks & ETFs) | OPTION |
|---|---|---|
| BUY | ACCEPTED | REJECT |
| SELL | ACCEPTED | REJECT |
| BUY_TO_OPEN | REJECT | ACCEPTED |
| BUY_TO_COVER | ACCEPTED | REJECT |
| BUY_TO_CLOSE | REJECT | ACCEPTED |
| SELL_TO_OPEN | REJECT | ACCEPTED |
| SELL_SHORT | ACCEPTED | REJECT |
| SELL_TO_CLOSE | REJECT | ACCEPTED |

### Sample 1 — Buy Market: Stock

Buy 15 shares of XYZ at the Market good for the Day.

```json
{
  "orderType": "MARKET",
  "session": "NORMAL",
  "duration": "DAY",
  "orderStrategyType": "SINGLE",
  "orderLegCollection": [
    {
      "instruction": "BUY",
      "quantity": 15,
      "instrument": {
        "symbol": "XYZ",
        "assetType": "EQUITY"
      }
    }
  ]
}
```

### Sample 2 — Buy Limit: Single Option

Buy to open 10 contracts of the XYZ March 15, 2024 $50 CALL at a Limit of $6.45 good for the Day.

```json
{
  "complexOrderStrategyType": "NONE",
  "orderType": "LIMIT",
  "session": "NORMAL",
  "price": "6.45",
  "duration": "DAY",
  "orderStrategyType": "SINGLE",
  "orderLegCollection": [
    {
      "instruction": "BUY_TO_OPEN",
      "quantity": 10,
      "instrument": {
        "symbol": "XYZ   240315C00500000",
        "assetType": "OPTION"
      }
    }
  ]
}
```

### Sample 3 — Buy Limit: Vertical Call Spread

Buy to open 2 contracts of XYZ March 15, 2024 $45 Put and Sell to open 2 contracts of XYZ March 15, 2024 $43 Put at a LIMIT price of $0.10 good for the Day.

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

### Sample 4 — Conditional Order: One Triggers Another (1st Trigger Sequence)

Buy 10 shares of XYZ at Limit $34.97 good for the Day. If filled, immediately submit Sell 10 shares of XYZ at Limit $42.03 good for the Day.

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
            "symbol": "XYZ",
            "assetType": "EQUITY"
          }
        }
      ]
    }
  ]
}
```

### Sample 5 — Conditional Order: One Cancels Another (OCO)

Sell 2 shares of XYZ at Limit $45.97 AND Sell 2 shares of XYZ with Stop Limit (stop $37.03, limit $37.00). Both sent simultaneously; first fill cancels the other. Both good for the Day.

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
            "symbol": "XYZ",
            "assetType": "EQUITY"
          }
        }
      ]
    }
  ]
}
```

### Sample 6 — Conditional Order: One Triggers A One Cancels Another (1st Trigger OCO)

Buy 5 shares of XYZ at Limit $14.97 good for the Day. Once filled, two sell orders are immediately sent: Sell 5 shares at Limit $15.27 and Sell 5 shares with Stop $11.27. First fill cancels the other. Both Sell orders are Good till Cancel.

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
                "symbol": "XYZ"
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
                "symbol": "XYZ"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### Sample 7 — Sell Trailing Stop: Stock

Sell 10 shares of XYZ with a Trailing Stop where the trail is a -$10 offset from submission time. As price rises, the -$10 offset follows (e.g., $110 → $130 moves the trail to $120). If XYZ falls to the trail level or below, a Market order is submitted. Good for the Day.

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
