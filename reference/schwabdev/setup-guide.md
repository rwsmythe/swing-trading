# Schwabdev Setup Guide

**Source:** https://tylerebowers.github.io/Schwabdev/pages/setupguide.html
**Library:** schwabdev — Python wrapper around the Schwab Trader API
**Extracted:** 2026-05-13
**Tutorial video:** https://youtu.be/69cniU1CTf8

---

## 1. Schwab Developer Account & App Registration

### 1.1 Create developer account
- Sign up at **https://developer.schwab.com/login**.
- **Use the same email as your Schwab brokerage account.** (Required for the developer-account-to-brokerage-account binding.)

### 1.2 Request API product access
- Request access to **Trader API - Individual**:
  https://developer.schwab.com/products/trader-api--individual

### 1.3 Create the developer app
- Apps dashboard: **https://developer.schwab.com/dashboard/apps**
- Create a new **Schwab individual developer app**.
- **Callback URL:** `https://127.0.0.1`
  - Callback URLs **must be HTTPS and localhost addresses**.
  - Multiple callbacks can be used by separating them with commas.
  - Example with port: `https://127.0.0.1:7777`
- **Add BOTH API products to the app:**
  - **Accounts and Trading Production**
  - **Market Data Production**
  - Both are needed for full functionality.
  - If you didn't add them during app creation: Apps Dashboard → View Details → Modify App → APIs.

### 1.4 Wait for app approval
- App status must be **"Ready for use"** (this can take a couple of days).
- **"Approved - Pending" will NOT work.**

### 1.5 Enable Thinkorswim (TOS)
- Enable **TOS** ([Thinkorswim](https://www.schwab.com/trading/thinkorswim)) for your Schwab account.
- Required for orders and other API calls.
- Enable by logging into your Schwab account on a TOS platform.

---

## 2. Install schwabdev

### 2.1 Pip install

```bash
pip install schwabdev
```

- You may need to use `pip3` instead of `pip`.
- **Schwabdev requires Python 3.11 or higher.**

### 2.2 Platform notes

**macOS — install Python certificates:**

```bash
open /Applications/Python\ 3.11/Install\ Certificates.command
```

- Replace `3.11` with the Python version you are using.
- If you haven't installed Python certificates (or aren't sure), this is required.

**Linux:**
- It is recommended to use a virtual environment.

---

## 3. First-Run Authorization (OAuth Flow)

The schwabdev `Client(...)` constructor drives the three-legged OAuth bootstrap on first invocation.

### 3.1 Steps emitted by the library on first run

1. **Run your script.** schwabdev prints a sign-in link to the terminal.
2. **Open the generated link** and sign in to your Schwab account.
3. **Agree to the terms** when prompted.
4. **Select the account(s)** you want the app to have access to.
5. After the browser redirects to your callback URL (e.g. `https://127.0.0.1/...`), **copy the entire URL from the browser's address bar** and **paste it back into the terminal** where schwabdev is waiting.

> Verbatim from the page:
> *"The first time you run, you will have to sign in to your Schwab account using the generated link in the terminal. After signing in, agree to the terms, and select account(s). Then you will have to copy the link in the address bar and paste it into the terminal."*

### 3.2 Starter code

```python
import schwabdev  # import the package

client = schwabdev.Client("Your app key", "Your app secret")  # create a client
print(client.quotes("AMD").json())  # make api calls
```

- Pass `app_key` (positional 1) and `app_secret` (positional 2) directly to `schwabdev.Client(...)`.
- Callback URL is configured on the developer-app side (Step 1.3); not all examples on this page pass it explicitly.

### 3.3 Storing credentials safely

- If you are storing your code in a GitHub repo, use **[python-dotenv](https://pypi.org/project/python-dotenv/)** to store your keys.
- See the `.env`-pattern example: https://tylerebowers.github.io/Schwabdev/pages/examples.html

---

## 4. Dependencies

| Package | Purpose | Default? |
|---|---|---|
| `tzdata` | Timezone data | Yes |
| `requests` | HTTP requests (API calls) | Yes |
| `websockets` | Streaming | Yes |
| `cryptography` | Encryption of the token database | Optional |
| `aiohttp` | Asynchronous HTTP requests (async client) | **Not** included by default |

---

## 5. Resources & Support

- **YouTube tutorial:** https://youtu.be/69cniU1CTf8
- **Discord group:** https://discord.gg/m7SSjr9rs9
- **Examples folder:** https://github.com/tylerebowers/Schwabdev/blob/main/docs/examples/
- **ChatGPT assistant:** https://chatgpt.com/g/g-697d2ca9a1188191920e9c3c1eedc4f8-schwabdev-assistant — "generally works well and can be a good starting point."
- **Schwab developer login:** https://developer.schwab.com/login
- **Trader API - Individual product page:** https://developer.schwab.com/products/trader-api--individual
- **Apps dashboard:** https://developer.schwab.com/dashboard/apps

---

## 6. What this page does NOT cover

The following items were **NOT documented on the setup guide page** and must be sourced from other schwabdev pages (likely the Client/API reference, examples page, or the source code):

- **Token storage file path / filename** (commonly `tokens.json` in schwabdev, but not stated on this page).
- **Token file schema** (fields, encryption envelope).
- **7-day refresh-token expiry** behavior and re-authorization cadence (not mentioned here).
- **Auto-refresh behavior of the access token** (interval, threading model, hook points).
- **Full `schwabdev.Client(...)` constructor signature** beyond `app_key` + `app_secret` — optional kwargs like `tokens_file`, `callback_url`, `timeout`, `capture_callback`, `update_tokens_auto`, logging hooks, etc. are not enumerated on this page.
- **Logging setup** (no logging section on this page).
- **Post-install verification steps** beyond the `client.quotes("AMD").json()` smoke call in the starter snippet.

Cross-reference the schwabdev API reference and `docs/examples/` for the items above.
