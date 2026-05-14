# Schwabdev Client Class

**Source:** https://tylerebowers.github.io/Schwabdev/pages/client.html
**Extracted:** 2026-05-13
**Library:** `schwabdev` — Python wrapper around the Schwab Trader API
**Scope of this page:** Client class initialization, OAuth/token lifecycle, and high-level usage. Individual API call signatures (market data, accounts, trading) live on the *API Calls* page of the Schwabdev docs and are **not enumerated here** — this page is the OAuth/lifecycle reference.

---

## Overview

`schwabdev` exposes two top-level client classes:

- **`schwabdev.Client`** — synchronous client (requests-style call sites).
- **`schwabdev.ClientAsync`** — asynchronous client (awaitable call sites, additional `parsed` parameter).

Both classes are the user-facing entry point. The library handles OAuth token acquisition, persistence, and auto-refresh internally; the operator instantiates the client once with credentials and the library transparently maintains a valid `access_token` (30-minute lifetime) and `refresh_token` (7-day lifetime) thereafter.

**Verbatim minimal instantiation:**

```python
import schwabdev
client = schwabdev.Client(app_key, app_secret)
```

```python
client = schwabdev.ClientAsync(app_key, app_secret)
```

---

## Constructor

### `schwabdev.Client` (synchronous)

```python
schwabdev.Client(
    app_key: str,
    app_secret: str,
    callback_url: str = "https://127.0.0.1",
    tokens_db: str = "~/.schwabdev/tokens.db",
    encryption: str | None = None,
    timeout: int = 10,
    call_on_auth: function | None = None,
    open_browser_for_auth: bool = True,
)
```

### `schwabdev.ClientAsync` (asynchronous)

```python
schwabdev.ClientAsync(
    app_key: str,
    app_secret: str,
    callback_url: str = "https://127.0.0.1",
    tokens_db: str = "~/.schwabdev/tokens.db",
    encryption: str | None = None,
    timeout: int = 10,
    call_on_auth: function | None = None,
    parsed: bool = False,
)
```

**Verbatim full-parameter examples from the docs:**

```python
client = schwabdev.Client(
    app_key,
    app_secret,
    callback_url="https://127.0.0.1",
    tokens_db="~/.schwabdev/tokens.db",
    encryption=None,
    timeout=10,
    call_on_auth=None,
    open_browser_for_auth=True
)
```

```python
client = schwabdev.ClientAsync(
    app_key,
    app_secret,
    callback_url="https://127.0.0.1",
    tokens_db="~/.schwabdev/tokens.db",
    encryption=None,
    timeout=10,
    call_on_auth=None,
    parsed = False,
)
```

### Constructor parameters

| Parameter | Type | Default | Required | Description |
|---|---|---|---|---|
| `app_key` | `str` | — | yes | Schwab developer-portal *app key* credential. |
| `app_secret` | `str` | — | yes | Schwab developer-portal *app secret* credential. |
| `callback_url` | `str` | `"https://127.0.0.1"` | no | OAuth callback URL registered with the Schwab developer app. Must exactly match the URL configured on the app in the developer portal. |
| `tokens_db` | `str` | `"~/.schwabdev/tokens.db"` | no | Filesystem path to the token-store database. Created on first use. **Multiple client instances must share this path** to avoid token conflicts (concurrent instances without a shared store will fight over refreshes). |
| `encryption` | `str \| None` | `None` | no | Fernet encryption key (string form) used to encrypt the token store at rest. `None` = unencrypted on-disk. See *Encryption* below. |
| `timeout` | `int` | `10` | no | HTTP request timeout in seconds applied to all underlying API calls. |
| `call_on_auth` | `function \| None` | `None` | no | Custom callback invoked when the library needs the user to complete the OAuth authorization flow. Receives one argument (the authorization URL to visit) and must **return** the full callback URL (or the `code` query parameter) after the user signs in. When `None`, the default flow either opens a browser (if `open_browser_for_auth=True` on `Client`) or prints the URL and waits for stdin input. See *OAuth flow* below. |
| `open_browser_for_auth` | `bool` | `True` | no | **Synchronous `Client` only.** When `True`, the library auto-launches the system default browser to the authorization URL. When `False`, the URL is printed for the operator to open manually. Has no effect when `call_on_auth` is supplied. |
| `parsed` | `bool` | `False` | no | **`ClientAsync` only.** When `True`, API responses are returned pre-parsed as Python `dict`/`list` JSON objects instead of raw HTTP response objects. Overridable per-call. |

---

## Token manager — `client.tokens`

The constructed client exposes a token-manager attribute as `client.tokens`. This is the canonical interface for inspecting the current OAuth state.

### Attributes on `client.tokens`

| Attribute | Type | Description |
|---|---|---|
| `client.tokens.access_token` | `str` | Currently-valid access token. Valid for **30 minutes**. The library refreshes automatically before expiry. |
| `client.tokens.refresh_token` | `str` | Currently-valid refresh token. Valid for **7 days**. The library schedules a refresh-token rotation **30 minutes before** the 7-day expiry. After expiry, full re-authorization (browser/`call_on_auth` flow) is required. |

**Reading tokens (verbatim):**

```python
client.tokens.access_token
client.tokens.refresh_token
```

---

## Methods

### `client.update_tokens`

```python
client.update_tokens(force_refresh_token: bool = False) -> None
```

Updates the access token (and optionally the refresh token).

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `force_refresh_token` | `bool` | `False` | When `True`, forces rotation of the *refresh token* (not just the access token) regardless of remaining validity. Use this to manually rotate the refresh token before its 7-day expiry. |

**Behavior:**

- With `force_refresh_token=False` (default), the call obtains a fresh **access token** using the current refresh token. This is what the library invokes automatically every ~30 minutes.
- With `force_refresh_token=True`, the call rotates the **refresh token** itself. Operators rarely need to invoke this directly — the library schedules this 30 minutes before refresh-token expiry — but it is the manual escape hatch if you want to re-anchor the 7-day window earlier.

**Verbatim usage:**

```python
client.update_tokens(force_refresh_token=True)
```

---

## OAuth flow

### Default (no `call_on_auth`)

On first instantiation (or when both tokens are expired/missing):

1. The library logs an authorization URL.
2. If `open_browser_for_auth=True` (sync `Client` only), the system default browser is launched to that URL.
3. The operator signs in via the Schwab portal and authorizes the app.
4. Schwab redirects to `callback_url` with a `code` query parameter.
5. The library captures the resulting URL (the exact capture mechanism varies — see `call_on_auth` for custom capture).
6. The library exchanges the `code` for an access/refresh token pair and persists them to `tokens_db`.

After this one-time interactive bootstrap, the library auto-maintains both tokens on the schedule below.

### Auto-refresh schedule

- **Access token** (30-minute validity): refreshed proactively before expiry using the current refresh token.
- **Refresh token** (7-day validity): the library "will start the process 30 minutes before the refresh token will expire" — i.e. it schedules a full refresh-token rotation in the last 30 minutes of the 7-day window.
- **If the refresh token expires** without a successful rotation (e.g. process was offline), the next API call cannot recover silently — the operator must re-run the interactive authorization flow.

### `call_on_auth` — custom OAuth-callback capture

Signature contract (callback supplied to the constructor):

```python
def my_capture(authorization_url: str) -> str:
    # 1. Present `authorization_url` to the user however you wish
    #    (web form, headless browser, paste-into-stdin, native UI, ...).
    # 2. After the user signs in, Schwab redirects to your callback_url
    #    with a `?code=...` query string.
    # 3. Capture that redirected URL (or just the `code` parameter) and return it.
    return full_redirected_url_or_code_string
```

- The callback receives **one argument**: the URL the user must visit to authorize.
- The callback must **return** either:
  - the full callback URL after redirect (preferred — the library parses the `code` out of it), **or**
  - the bare `code` value extracted from the callback URL's query string.
- A worked example lives at `capture_callback.py` in the schwabdev repository examples directory (not reproduced inline on the Client page).

This is the integration point for: headless servers, GUI-wrapped applications, automated test harnesses, container deployments where no browser is available, or any environment where the default "open browser + paste redirect URL" interaction is unsuitable.

---

## Encryption (Fernet)

The `encryption` parameter accepts a `cryptography.fernet.Fernet` key (string form) and, when supplied, encrypts the on-disk token store at `tokens_db`.

### Key generation pattern

```python
from cryptography.fernet import Fernet

key = Fernet.generate_key()        # bytes
encryption_key = key.decode()      # str — pass this to schwabdev.Client(encryption=...)
```

- Persist the key **outside** the token DB (env var, OS keyring, separate secure store). Losing the key means the token DB cannot be decrypted and the operator must re-run the full OAuth bootstrap.
- A worked end-to-end example lives at `encrypted_db_setup.py` in the schwabdev repository examples directory (not reproduced inline on the Client page).

### When to use

- Multi-user host / shared filesystem deployments.
- Compliance requirements that prohibit storing OAuth refresh tokens in plaintext on disk.
- Defense-in-depth against filesystem-level credential exfiltration.

For a single-operator local install with filesystem ACLs on the home directory, `encryption=None` (the default) is acceptable.

---

## Token-store sharing (multiple instances)

> "Multiple clients can be run at the same time, though they must share the same `tokens_db` file to avoid token conflicts."

Concurrent `Client` / `ClientAsync` instances on the same Schwab app must point at the **same `tokens_db` path**. Otherwise each instance independently refreshes — and Schwab's OAuth server invalidates the prior refresh token on each rotation — causing instances to evict each other in a refresh thrash.

The page does **not** document an internal locking mechanism for concurrent writers; thread-safety beyond the single-process auto-refresh thread is the operator's responsibility (external lockfile, single-leader pattern, or restricting concurrent rotation to a single dedicated instance).

---

## Logging

Schwabdev uses the Python standard-library `logging` module for all information, warning, and error messages — including authentication events (token refresh, OAuth bootstrap, rotation scheduling).

**Verbatim guidance:**

> "You can change the level of logging by setting `logging.basicConfig(level=logging.XXXX)`"

```python
import logging
logging.basicConfig(level=logging.INFO)     # or DEBUG / WARNING / ERROR
```

There is no schwabdev-specific logger configuration knob on the Client page beyond standard `logging` levels.

---

## Rate limits

Imposed by the Schwab API (not by the schwabdev wrapper):

| Limit | Threshold |
|---|---|
| API requests per minute (all endpoints) | **120** |
| Order-related API calls per day | **4,000** |
| Concurrent streamed tickers | **500** |

Exceeding any limit returns **HTTP 429**. The Client page does not document an internal retry-with-backoff mechanism — operators must handle 429 responses at the application layer.

---

## Sync vs Async — usage differences

| Aspect | `Client` (sync) | `ClientAsync` |
|---|---|---|
| Call style | Blocking | `await ...` |
| Auto-launch browser | `open_browser_for_auth: bool = True` parameter | Not applicable — relies on `call_on_auth` or default URL print |
| Response parsing toggle | n/a (returns raw response objects) | `parsed: bool = False` constructor parameter; when `True`, returns `dict`/`list` JSON; overridable per-call |
| Other parameters | Identical | Identical |
| Token store | `tokens_db` (same default path, same Fernet encryption option) | Same |

Both classes share identical OAuth/token semantics, the same `client.tokens` attribute surface, and the same `update_tokens(force_refresh_token=...)` method.

---

## API call surface (not on this page)

The Client page itself does **not** enumerate the per-endpoint API method signatures (e.g. `account_linked`, `account_details`, `account_details_all`, `get_quotes`, `quote`, `price_history`, `option_chains`, `option_expiration_chain`, `movers`, `market_hours`, `instruments`, `account_orders`, `account_orders_all`, `order_place`, `order_details`, `order_cancel`, `order_replace`, `transactions`, `preferences`, etc.).

> "All calls can be found in the 'API Calls' documentation tab and are also outlined in `/docs/examples/api_demo.py`."

For per-endpoint signatures, see the *API Calls* page of the Schwabdev docs (separate distillation) and the upstream `/docs/examples/api_demo.py`.

The Client page also does not document the streamer (`client.stream` or similar) interface — that lives on the dedicated *Stream* page of the Schwabdev docs.

---

## Exceptions

The Client page does **not** enumerate specific exception types raised by the constructor or `update_tokens`. Operators integrating against the library should treat OAuth-bootstrap failures and refresh failures as recoverable-by-re-authorization conditions and surface 429s from API calls as rate-limit-backoff signals.

---

## Items the page references but does not reproduce inline

These exist in the schwabdev repository's `docs/examples/` directory and are referenced from the Client page but not embedded:

- `capture_callback.py` — worked `call_on_auth` example.
- `encrypted_db_setup.py` — worked Fernet-encrypted token store setup.
- `api_demo.py` — outlines all per-endpoint API call signatures.

To capture those, fetch the repository directly (they are not within the Client page's content scope).
