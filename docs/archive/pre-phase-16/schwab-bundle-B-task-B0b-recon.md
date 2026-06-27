# Schwab API Sub-bundle B — Task T-B.0.b operator-paired live verification recon

**Purpose:** Capture phase-1 pre-check findings from `reference/schwabdev/api-calls.md` + `reference/schwab-api/account-{documentation,specification}.md` so Sub-bundle B endpoint wiring consumes the verified Trader-API surface — and bank deviations from the writing-plans plan §E.2 synthesized signatures for the V2.1 §VII.F amendment channel.

**Status:** Phase 1 = COMPLETE (this doc). Phase 2 = DEFERRED — live Trader-API cassette recording against the operator's production-tier Schwab account is scheduled post-T-B.1 ship; cassette-dependent acceptance criteria for T-B.3 + T-B.4 + T-B.5 + T-B.7 stay synthetic-fixture-driven until that pairing happens.

**Plan reference:** `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` §E.2 + §E.8 + §H.4 + §H.5 (Tasks T-B.1..T-B.4 consumers).

**Operator-supplied distillations consumed:**

- `reference/schwab-api/account-documentation.md` + `account-specification.md` — Schwab Developer Portal Trader API canonical docs.
- `reference/schwabdev/api-calls.md` (25 KB) — schwabdev 2.5.x wrapper method → REST endpoint mapping (23 methods total; Bundle B consumes 4).

---

## §1 Sub-bundle B trader-method surface (post-pre-check)

| Logical name | schwabdev method (verified `api-calls.md`) | HTTP verb + path | Required params | Optional params | Project consumer |
|---|---|---|---|---|---|
| `accounts.linked` | `Client.account_linked()` | `GET /accounts/accountNumbers` | — | — | T-A.4 setup (`auth.py`) + future `swing schwab status` |
| `accounts.details` | `Client.account_details(account_hash, fields=None)` | `GET /accounts/{accountHash}` | `account_hash` | `fields='positions'` | T-B.3 `_step_schwab_snapshot`; CLI `fetch --snapshot` |
| `accounts.orders.list` | `Client.account_orders(account_hash, from_entered_time, to_entered_time, max_results=None, status=None)` | `GET /accounts/{accountHash}/orders` | `account_hash`, `from_entered_time`, `to_entered_time` | `max_results`, `status` | T-B.4 `_step_schwab_orders` (status=None → fetches all); CLI `fetch --orders` |
| `accounts.transactions.list` | `Client.transactions(account_hash, start_date, end_date, types, symbol=None)` | `GET /accounts/{accountHash}/transactions` | `account_hash`, `start_date`, `end_date`, **`types`** | `symbol` | T-B.4 `_step_schwab_orders` (types=full-set); CLI `fetch --orders` |

**Key pre-check observations:**

1. **`account_orders` `status` param NULL fetches ALL statuses** per `api-calls.md` L124 (entire 21-value enum); matches plan §H.4.2 step 6 "status_filter=None ... gives reconciliation full coverage". Acceptable verbatim.
2. **`transactions` REQUIRES the `types` param** (per `api-calls.md` L256). Plan §E.2 row 4 + §H.4.2 step 9 had `type_filter='ALL'` which is wrong — Schwab REST does NOT accept a literal `'ALL'`; the operator-side equivalent is "pass the full list of all 16 enum values". **Plan-text amendment banked (§5 §A below).**
3. **All four methods return `requests.Response`** (NOT raw dicts). Wrapper must call `.json()` + verify HTTP status from the Response object. The auth.py T-A.4 `_stub_call_account_linked` already tolerates both raw-payload + `.json()`-callable; trader.py will mirror.
4. **`account_details(fields='positions')`** is the canonical positions-fetcher per Schwab REST; plan §E.2 row 2 specifies this kwarg. NLV (`net_liquidating_value`) lives under `securitiesAccount.currentBalances.liquidationValue` in the real response (per Schwab Developer Portal account-specification.md aggregateBalance / currentBalances schema; verified at phase 2 once cassette is recorded).
5. **Datetime format for orders/transactions:** `yyyy-MM-dd'T'HH:mm:ss.SSSZ` (with milliseconds + literal Z UTC indicator) per `api-calls.md` L121-122 + L254-255. schwabdev accepts both `datetime` objects + pre-formatted strings; the wrapper formats consistently using `datetime.isoformat()` with `'T'` separator + millisecond precision + `'Z'` suffix.

---

## §2 Plan §E.2 reconciliation — 2 falsifications + 4 confirmations

| Plan §E.2 claim | schwabdev actual | Status | Resolution |
|---|---|---|---|
| `Client.account_details(account_hash, fields=['positions'])` (fields is a LIST) | `fields=None \| str` per L102 — single string, not list | **FALSIFIED (cosmetic)** | Pass `fields='positions'` (string). Plan amendment §5 §B. |
| `Client.transactions(..., type_filter='ALL')` (kwarg name + literal "ALL") | Actual kwarg `types: list \| str` REQUIRED; values are the 16-enum set | **FALSIFIED (semantic)** | Pass list of all 16 enum values; bound names as a module constant `_TRANSACTION_TYPES_ALL`. Plan amendment §5 §A. |
| `Client.account_orders(..., status_filter=None)` (kwarg name) | Actual kwarg `status: str \| None` | **FALSIFIED (cosmetic)** | Use `status=None`. Plan amendment §5 §C. |
| Plan §E.2 dataclass `SchwabAccountResponse.net_liquidating_value` | Lives under `securitiesAccount.currentBalances.liquidationValue` per Schwab REST | **CORRECT ✓** | Mapper navigates the nested path; falls back to other balance fields if absent (phase 2 will confirm exact nesting). |
| Plan §E.2 dataclass `SchwabOrderResponse.status` enum (WORKING/FILLED/etc.) | 21-value enum per `api-calls.md` L124 (broader than plan's 5 values) | **PARTIAL** | Wrapper accepts ANY string from Schwab; mapper preserves it verbatim. The dataclass `__post_init__` validator widens to the schwabdev-documented 21-value set; downstream reconciliation only acts on `FILLED`, `WORKING`, `WAIT_TRG`. |
| Plan §E.2 dataclass `SchwabTransactionResponse.type` enum | 16-value enum per `api-calls.md` L256 | **CORRECT ✓** | Validator widens to all 16 values. |
| `Client.account_linked()` success: list of `{accountNumber, hashValue}` dicts | Confirmed at T-A.0.b §6.bis.1 live verification | **CORRECT ✓** | T-A.4 already consumes; T-B.1 re-uses (single source of truth in T-B.1 `get_accounts_linked`). |
| Rate limits 120/min + 4000 orders/day | Confirmed `api-calls.md` L168 + `client.md` L255-265 | **CORRECT ✓** | Bundle B handles at audit layer; out-of-scope V1 to retry-with-backoff beyond the once-retry per plan §H.4 step 6. |

---

## §3 Trader-method param plumbing notes (T-B.1 implementation)

### §3.1 Datetime stamping discipline

Both `account_orders` + `transactions` require date-range params:

- `account_orders`: `from_entered_time` + `to_entered_time` (millisecond ISO 8601 with Z).
- `transactions`: `start_date` + `end_date` (same format).

Plan §H.4.2 computes the range as `period_end = last_completed_session(datetime.now())`, `period_start = period_end - lookback_days`. The wrapper formats both endpoints' ranges identically using a helper `_to_schwab_iso(dt: datetime) -> str` that emits `'2026-05-14T00:00:00.000Z'`-shaped strings; `period_start` is at midnight UTC of its date; `period_end` is at 23:59:59.999Z of its date (inclusive end).

### §3.2 `types` enum constant (transactions)

The full 16-value list per `api-calls.md` L256:

```python
_TRANSACTION_TYPES_ALL: list[str] = [
    "TRADE", "RECEIVE_AND_DELIVER", "DIVIDEND_OR_INTEREST",
    "ACH_RECEIPT", "ACH_DISBURSEMENT",
    "CASH_RECEIPT", "CASH_DISBURSEMENT",
    "ELECTRONIC_FUND", "WIRE_OUT", "WIRE_IN",
    "JOURNAL", "MEMORANDUM", "MARGIN_CALL",
    "MONEY_MARKET", "SMA_ADJUSTMENT",
    # NOTE: api-calls.md L256 enumerates 15 in the row; spec §3.3.1 +
    # Schwab Developer Portal allow `TRADE_CORRECTION` too. V1 V2-fence:
    # Bundle B consumes the documented 15; spec amendment fence holds.
]
```

V1 implementation passes the documented 15 (defense-in-depth: ALL is the operator's intent + the 15 are documented; a 16th appearing in Schwab's response is preserved by the wrapper but NOT requested in the type filter).

### §3.3 `status` enum (orders dataclass `__post_init__`)

Per `api-calls.md` L124, the 21-value status set:

```
AWAITING_PARENT_ORDER, AWAITING_CONDITION, AWAITING_STOP_CONDITION,
AWAITING_MANUAL_REVIEW, ACCEPTED, AWAITING_UR_OUT, PENDING_ACTIVATION,
QUEUED, WORKING, REJECTED, PENDING_CANCEL, CANCELED, PENDING_REPLACE,
REPLACED, FILLED, EXPIRED, NEW, AWAITING_RELEASE_TIME,
PENDING_ACKNOWLEDGEMENT, PENDING_RECALL, UNKNOWN
```

Plus the `WAIT_TRG` value observed in Phase 9 Sub-bundle E real-world fixtures (CLAUDE.md gotcha "Schwab/TOS Account Order History uses multi-line order groups"). The wrapper widens the enum to 22 values (defense-in-depth; future-proof against schwabdev's documentation lag).

### §3.4 `instruction` + `order_type` enums (orders dataclass)

`api-calls.md` does NOT enumerate these — they live in Schwab Developer Portal `orders.md` per `reference/schwabdev/orders.md`:

- `instruction`: `BUY`, `SELL`, `BUY_TO_OPEN`, `BUY_TO_CLOSE`, `SELL_TO_OPEN`, `SELL_TO_CLOSE`, `BUY_TO_COVER`, `SELL_SHORT`.
- `order_type`: `MARKET`, `LIMIT`, `STOP`, `STOP_LIMIT`, `TRAILING_STOP`, `TRAILING_STOP_LIMIT`, `MARKET_ON_CLOSE`, `LIMIT_ON_CLOSE`, `CABINET`, `NON_MARKETABLE`, `NET_DEBIT`, `NET_CREDIT`, `NET_ZERO`, `EXERCISE`.

The wrapper widens both validators to these explicit sets; future Schwab additions will surface as `ValueError` on `__post_init__` which is the right failure mode for an audit-row writer.

---

## §4 Per-task impact within Sub-bundle B

### T-B.1 (Trader API endpoint methods + mappers) — IMPLEMENT verbatim against verified surface

Each of 4 trader methods follows the audit-row INSERT-then-UPDATE pattern from auth.py T-A.4 + T-A.5:

```
1. start_ts = _now_ms_iso() (server-stamp at handler entry)
2. ensure_schwab_log_redaction_factory_installed() (Layer-2 re-wrap defense)
3. call_id = audit_service.record_call_start(conn, ts, endpoint, pipeline_run_id, surface, environment)
4. construction_start = time.monotonic()
5. try:
6.   with _suppress_transport_debug_logs():
7.     response = client.<schwabdev_method>(*args)
8.   payload = response.json() if hasattr(response, 'json') else response
9.   http_status = response.status_code if hasattr(response, 'status_code') else 200
10. except exception types -> redact + record_call_finish + raise mapped Schwab exception
11. validate response shape + signature_hash
12. record_call_finish(status='success', signature_hash, http_status, elapsed_ms)
13. return mapped dataclass via mappers.py helper
```

**Discriminating tests** (Sub-bundle A Codex M#1 family pre-emption — silent-failure post-call validation):
- Stub schwabdev call to return a Response-like object whose `.json()` returns an error envelope (dict with `errors` key); assert wrapper raises `SchwabApiError` + audit row `status='auth_failed'` (NOT `success`).
- Stub schwabdev call to return an empty list when the project expects a populated one (orders.list, transactions.list); under spec rules, empty IS a valid response (no orders for the period) — wrapper records `success` with `signature_hash` computed off the empty structure.
- 401 HTTP status → mapped to `SchwabAuthError` + audit `auth_failed`.
- 429 → `SchwabRateLimitError` + audit `rate_limited`.

### T-B.2 + T-B.6 + T-B.8 — proceed using stubbed schwabdev calls (no live cassette needed)

These tasks are surface-discipline tests (sandbox-gating + pipeline-active exclusion + sentinel-leak audit Trader-API coverage). All three are exercised against synthetic responses + the existing test infrastructure from Sub-bundle A.

### T-B.3 + T-B.4 + T-B.5 + T-B.7 — synthetic-fixture-driven until operator-paired cassette recording

- T-B.3 `_step_schwab_snapshot` uses synthetic `accounts.details` response fixture (single account; `liquidationValue` populated; `positions` list non-empty).
- T-B.4 `_step_schwab_orders` uses synthetic `accounts.orders.list` + `accounts.transactions.list` + `accounts.details` fixtures.
- T-B.5 CLI `swing schwab fetch` exercises against synthetic fixtures (no `--live` mode V1).
- T-B.7 integration test is fixture-driven (mirrors Phase 9 Sub-bundle E E2E pattern).

**Live-cassette recording** (T-B.0.b phase 2) records the actual Trader-API responses against the operator's production account post-T-B.1 ship for forward V2 use; V1 Sub-bundle B ships with synthetic-fixture coverage as the binding test surface.

---

## §5 Banked V2.1 §VII.F amendment candidates (5 plan deviations)

Per project methodology-correction protocol (V2.1 §VII.F) — orchestrator triages post-Sub-bundle-B-ship.

**§A.** Plan §E.2 row 4 (`Client.transactions(..., type_filter='ALL')`) — kwarg is `types: list | str` REQUIRED, not `type_filter`. Wrapper passes the full 15-value enum constant `_TRANSACTION_TYPES_ALL`. Plan-text amendment: change kwarg name + value semantics.

**§B.** Plan §E.2 row 2 (`Client.account_details(account_hash, fields=['positions'])`) — `fields` is `str | None`, not list. Wrapper passes `fields='positions'`. Plan-text amendment: change list-syntax → string.

**§C.** Plan §E.2 row 3 (`Client.account_orders(..., status_filter=None)`) — kwarg is `status: str | None`, not `status_filter`. Wrapper passes `status=None`. Plan-text amendment: rename kwarg.

**§D.** Plan §H.4.2 step 6 + §H.4.2 step 9 inherit the same `type_filter='ALL'` / `status_filter=None` cosmetic issues from §E.2. Same fix.

**§E.** Plan §E.2 `SchwabOrderResponse.status` 5-value enum — schwabdev documents 21 values (plus `WAIT_TRG` from Phase 9 Sub-bundle E real-world observation). Wrapper widens validator to 22 values. Plan-text amendment: enumerate the widened set.

---

## §6 Phase-2 (live) verification still pending

Phase 2 runs post-T-B.1 ship (paired session with operator's production-tier credentials at `~/swing-data/schwab-tokens.production.db`). Captures:

1. **`accounts.details` actual response shape** — confirm `securitiesAccount.currentBalances.liquidationValue` path; record sanitized cassette under `tests/integrations/cassettes/schwab/accounts_details.yaml`.
2. **`accounts.orders.list` actual response shape** — confirm order-dict shape; record cassette (status filter all; 7-day window).
3. **`accounts.transactions.list` actual response shape** — confirm transaction-dict shape; verify `types` param accepts the documented enum list; record cassette.
4. **HTTP response headers** — verify rate-limit header presence/absence (`X-RateLimit-Remaining` or similar); confirms `rate_limit_remaining` audit-column behavior.
5. **Empty-response transient handling** — confirm whether empty orders/transactions returns `[]` (clean), `null`, or an error envelope.

Phase-2 output: append findings to this doc as §6.bis (under header `## §6.bis Phase-2 live observations`) + commit as `docs(schwab-api): T-B.0.b phase-2 live observations` (mirroring T-A.0.b §6.bis pattern).

---

## §7 Implementation deviations binding for Sub-bundle B (LOCKED at this dispatch)

This recon doc supersedes the affected plan sections for the duration of Sub-bundle B execution. Per the project's recon-doc-supersession pattern (Phase 9 Sub-bundle D recon doc precedent at `docs/phase9-bundle-D-task-D0-recon.md` §3 + Phase 9 Sub-bundle E parser recon at `docs/phase9-bundle-E-task-E3-parser-recon.md` + Sub-bundle A T-A.0.b recon §7).

**T-B.1 ships:**
- `get_accounts_linked(client)` consuming `Client.account_linked()`.
- `get_account_details(client, account_hash, fields='positions')` consuming `Client.account_details(account_hash, fields='positions')`.
- `get_account_orders(client, account_hash, from_entered_time, to_entered_time, status=None, max_results=None)` consuming `Client.account_orders(...)`.
- `get_account_transactions(client, account_hash, start_date, end_date, types=<full-list>, symbol=None)` consuming `Client.transactions(...)`.

Plan-text amendments routed through V2.1 §VII.F post-ship.
