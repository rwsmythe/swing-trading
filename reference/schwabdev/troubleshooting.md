# Schwabdev Troubleshooting

**Source:** https://tylerebowers.github.io/Schwabdev/pages/troubleshooting.html
**Extracted:** 2026-05-13
**Library:** schwabdev — Python wrapper around the Schwab Trader API
**Purpose:** Operator-priority capture of OAuth failure modes + general error troubleshooting. Integration code's error-handling layer depends on this verbatim coverage.

---

## Authentication & Authorization

### Issue: 401 Unauthorized — "Client not authorized"

Error body returned by the Schwab API:

```
{'errors': [{'id': 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX',
             'status': 401,
             'title': 'Unauthorized',
             'detail': 'Client not authorized'}]}
```

**Causes & Resolutions:**

1. **Missing API access on the app.** Add BOTH of these to your app at the Schwab developer portal:
   - `Accounts and Trading Production`
   - `Market Data Production`
2. **Expired access token.** Force a manual refresh:
   ```python
   client.update_tokens(force_access_token=True)
   ```

---

### Issue: 500 Server Error — "We are unable to complete your request..." / "Whitelabel Error Page..."

Returned during the auth flow or initial API call.

**Resolution:**
- Verify app status in the Schwab developer portal is `Ready for Use` (NOT `Approved - Pending`).
- Confirm the underlying brokerage account type is supported by the Schwab API.

---

### Issue: Invalid Refresh Token — `unsupported_token_type`

Error body:

```
{"error":"unsupported_token_type","error_description":"400 Bad Request...
```

**Cause:** Refresh token was created on a different machine, or the refresh token has been invalidated (e.g., password reset on the Schwab account, 7-day expiry hit, manual revocation).

**Resolution:** Force a fresh refresh-token grant (re-runs the browser OAuth dance):
```python
client.update_tokens(force_refresh_token=True)
```

Alternatively, edit / delete `tokens.json` directly to clear the stale refresh token, then re-run.

---

### Issue: Refresh Token Expiry (7-Day Schwab Limit)

**Known limitation:** Schwab refresh tokens expire in 7 days. This is shorter than the schwabdev developer would prefer; Schwab acknowledges the limitation. There is no programmatic extension — operator MUST re-authenticate via browser flow at least once per 7 days.

**Resolution:** Re-run the OAuth bootstrap (interactive browser flow) before the 7-day expiry, or handle the `unsupported_token_type` error path on next run by calling `client.update_tokens(force_refresh_token=True)`.

---

### Issue: Access Denied After Sign-In (Callback URL Mismatch)

Symptom: After completing the Schwab login + 2FA, the post-redirect page shows access denied or fails to parse.

**Cause:** Callback URL configured at the developer portal has a trailing `/` that doesn't match the library's expected callback string.

**Resolution:** Remove the trailing `/` from the callback URL in the Schwab developer portal app configuration. The callback URL must match exactly (no trailing slash).

---

## Symbol Format Issues

### Issue: 404 Not Found on Symbol Lookups

Error body:

```
{'errors': [{'id': '...', 'status': '404', 'title': 'Not Found'}]}
```

**Cause:** Symbol format does not match Schwab's expected encoding for the instrument class.

**Resolutions — symbol format reference:**

- **Index symbols** require `$` prefix:
  - `$SPX`, `$DJI`
- **Option contracts** — 21-character OSI format:
  - `"AAPL  240517P00190000"`
  - 6-char underlying symbol (space-padded) + 6-char expiration `YYMMDD` + 1-char `C`/`P` + 8-char strike (5 dollars + 3 decimals, no decimal point)
- **Futures**:
  - `'/ESUZ24'` — slash + root symbol + month code + 2-digit year
- **Futures options**:
  - `'./ESUZ24C4000'` — dot + slash + root + month code + year + `C`/`P` + strike

---

## Streaming & Network Issues

### Issue: SSL Certificate Verification Failed (macOS)

Error:

```
SSL: CERTIFICATE_VERIFY_FAILED - self-signed certificate in certificate chain
```

**Resolution (macOS):**
```bash
open /Applications/Python\ 3.12/Install\ Certificates.command
```

Adjust the Python version path to match your installation.

---

### Issue: WebSocket Streaming Error — `permessage-deflate` Unsupported

Error:

```
Unsupported extension: name = permessage-deflate, params = []
```

**Cause:** Proxy interference OR DNS resolution failure on the WebSocket endpoint.

**Resolutions:**
- Switch DNS servers — Google's public DNS (`8.8.8.8` / `8.8.4.4`) is known-working.
- Bypass or change the network proxy.

---

### Issue: Main Thread Closes Before Stream Initializes

Error:

```
can't register atexit after shutdown
```

**Cause:** Main thread exits before the streaming thread finishes initialization.

**Resolution:** Add a delay (e.g., `time.sleep(...)`) after starting the stream or sending the first stream request, so the stream thread has time to register its atexit hook before the interpreter shuts down.

---

## Data Size & Rate Limiting

### Issue: Body Buffer Overflow

Error body:

```
{'fault': {'faultstring': 'Body buffer overflow',
           'detail': {'errorcode': 'protocol.http.TooBigBody'}}}
```

**Cause:** API call returns more data than Schwab's response buffer permits.

**Example trigger:**
```python
print(client.option_chains("$SPX").json())
```
A full `$SPX` option chain blows the buffer.

**Resolution:** Add narrowing parameters to constrain the returned dataset (strike range, expiration filter, contract type, etc.).

---

## Registration & Support

### Issue: App Registration Stuck or Rejected

**Resolution:** Email Schwab directly at `traderapi@schwab.com`.

### Where to Get Help

- **Discord:** https://discord.gg/m7SSjr9rs9 — community channel for issues not documented here.

---

## Known Limitations (Summary)

- **7-day refresh token expiry.** Hard Schwab platform limit. No programmatic workaround — re-auth via browser OAuth flow at least once per week.
- **Body buffer overflow on wide queries.** Caller must narrow the request; library does not auto-paginate.

---

## Gaps vs. Operator's Requested OAuth Coverage

The source troubleshooting page does NOT explicitly document the following scenarios from the operator's requested coverage list — they are either implied by other entries or not addressed:

- **`tokens.json` corruption / version mismatch** — not explicitly addressed; fallback is `force_refresh_token=True` or manual `tokens.json` edit/delete per the "Invalid Refresh Token" entry.
- **Multiple concurrent Client instances fighting over the same token file** — NOT documented. Risk to manage at integration-layer (file-lock or single-Client-singleton discipline) since the library does not document file-locking semantics on `tokens.json`.
- **403 responses despite valid tokens** — NOT documented separately from 401. Treat as auth-scope mismatch (missing `Accounts and Trading Production` or `Market Data Production`) or app-status (`Approved - Pending` rather than `Ready for Use`) first; escalate to `traderapi@schwab.com` if persistent.
- **Browser doesn't redirect / paste-back parsing fails** — NOT documented separately; closest entry is the "Access Denied After Sign-In" callback-URL-trailing-slash case.
- **Password reset invalidation** — NOT named explicitly but falls under the "Invalid Refresh Token" generic resolution (re-auth via `force_refresh_token=True`).

These gaps should be covered by integration-layer defensive code + operator-runbook documentation, not assumed to live in the upstream troubleshooting page.
