# Schwab API Sub-bundle A — Task T-A.0.b operator-paired live verification recon

**Purpose:** Capture phase-1 pre-check findings from the two operator-supplied reference distillations (`reference/schwab-api/` upstream REST API + `reference/schwabdev/` Python wrapper) so subsequent Sub-bundle A tasks consume the verified surface — and bank deviations from the writing-plans plan §E.1 synthesized signatures for the V2.1 §VII.F amendment channel.

**Status:** Phase 1 = COMPLETE (this doc). Phase 2 = PENDING — live paste-back flow against operator's production-tier Schwab account, scheduled after T-A.4 ships the `swing schwab setup` CLI.

**Plan reference:** `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` §E.1 + §E.6 + §F.1 + §H.1 + §H.2 (Tasks T-A.3..T-A.5 consumers).

**Operator-supplied distillations consumed:**

- `reference/schwab-api/{account,market-data}-{documentation,specification}.md` (commit `829dffd`; 4 files / 3996 lines; Schwab Developer Portal upstream REST API).
- `reference/schwabdev/{setup-guide,client,api-calls,examples,orders,streaming,troubleshooting}.md` (commit `62f5dde`; 7 files; tylerebowers/Schwabdev wrapper docs).

---

## §1 Schwab upstream REST API observations (from `reference/schwab-api/`)

| Observation | Value | Source |
|---|---|---|
| Trader API base URL (Q8) | `https://api.schwabapi.com/trader/v1` | account-specification.md L19 |
| OAuth authorize URL | `GET https://api.schwabapi.com/v1/oauth/authorize?client_id=...&redirect_uri=...` | account-documentation.md L91 |
| OAuth token URL | `POST https://api.schwabapi.com/v1/oauth/token` | account-documentation.md L107, L161 |
| OAuth revoke URL | NOT DOCUMENTED in distilled refs (spec §6 expects `POST /v1/oauth/revoke`) | — |
| OAuth scope default (Q14) | `"api"` (single value, returned in token + refresh responses) | account-documentation.md L129, L181 |
| Refresh-token rotation (Q15) | **YES** — Schwab rotates refresh_token on every refresh exchange; new 7-day lifetime each time | account-documentation.md L182 |
| Accounts-linked endpoint (Q3) | `GET /accounts/accountNumbers` → JSON array `[{accountNumber, hashValue}, ...]`; multi-account supported | account-specification.md L66, L102-108 |
| Account-details endpoint | `GET /accounts/{accountNumber}` (path uses hashValue) | account-specification.md L68 |
| Account-balances/positions | `GET /accounts` | account-specification.md L67 |

**Q3 multi-account note:** the operator may have multiple linked accounts; the endpoint returns an array. T-A.4's "pick primary" logic (plan §H.1) needs operator confirmation at phase 2 of which account_hash gets persisted to `cfg.integrations.schwab.account_hash`. Single-account operator → auto-pick; multi-account → CLI prompt (plan §H.1 binding).

---

## §2 schwabdev library observations (from `reference/schwabdev/`)

### §2.1 Client constructor — canonical 8-param signature (`client.md` L37-46 verbatim)

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

### §2.2 OAuth paste-back flow is embedded in `Client.__init__` — NO separate `auth.manual_flow(...)` callable

Per `setup-guide.md` L73-84 + `client.md` L160-169: the OAuth interactive flow runs at `Client(...)` construction time when no tokens DB is present. Sequence:

1. Constructor prints the consent URL.
2. If `open_browser_for_auth=True` (default), auto-launches the operator's browser.
3. Operator signs in at Schwab → browser redirects to the operator-registered callback URL (e.g. `https://127.0.0.1`).
4. Browser displays a "can't be reached" page (no local listener) — operator **copies the full URL out of the browser address bar**.
5. Operator pastes the URL into the terminal where the Client constructor is blocking on `input()`.
6. schwabdev parses the `code` query param + POSTs to `/v1/oauth/token` for tokens + persists to `tokens_db`.
7. Constructor returns a `Client` instance with `client.tokens` populated.

**Subsequent constructions** (tokens DB present): loads tokens; schedules auto-refresh of access_token every 30 minutes + refresh_token 30 minutes before its 7-day expiry.

### §2.3 Tokens object surface (`client.md` L108-124)

Access via `client.tokens.<attribute>`:
- `client.tokens.access_token` — str; 30-min lifetime.
- `client.tokens.refresh_token` — str; 7-day lifetime.

**No separable `Tokens` class signature is enumerated in the docs** — it's an attribute-bag exposed on Client. T-A.6 status CLI reads via this surface.

### §2.4 Force-refresh (`client.md` L130-154 + `troubleshooting.md` L45-58)

```python
client.update_tokens(force_refresh_token: bool = False) -> None
```

- Default behavior: lazy refresh of access_token on first API call.
- `force_refresh_token=True`: re-runs the browser OAuth dance (rotates BOTH access and refresh tokens).
- Resolution path for `unsupported_token_type` error per troubleshooting.md L55-58: `client.update_tokens(force_refresh_token=True)`.

### §2.5 No `revoke()` method exposed

`client.md` does NOT enumerate a `revoke()` method on Client OR on `client.tokens`. Per plan §E.6 fallback path: T-A.5's `revoke_and_delete(...)` issues a manual `requests.post()` to `POST /v1/oauth/revoke` with Basic-auth (client_id + client_secret) + the refresh_token in body; tolerates failure; proceeds with sidecar delete regardless.

### §2.6 Tokens DB schema — INCONSISTENCY in schwabdev's own docs

- `client.md` L41: default is `~/.schwabdev/tokens.db` (SQLite implied).
- `troubleshooting.md` L60, L204: refers to `tokens.json` (file-format implied; "delete + re-auth" recovery).

**Resolution:** PHASE-2 LIVE VERIFICATION needed. Implementer at phase 2 runs `swing schwab setup` against operator's account + inspects the actual on-disk file format. Plan §F.1 assumes SQLite per COA B; if reality is JSON, the project does NOT migrate (plan §F.1: "Schema: owned by schwabdev. NOT enumerated here.") — only T-A.6 status surface needs adjustment to read the actual format.

### §2.7 Rate limits (`client.md` L255-265)

| Limit | Threshold | Response |
|---|---:|---|
| API calls per minute (all endpoints) | 120 | HTTP 429 |
| Order-related API calls per day | 4,000 | HTTP 429 |
| Concurrent streamed tickers | 500 | (V2; streaming OUT OF SCOPE V1) |

No internal retry-with-backoff in schwabdev. Project handles at audit-row layer per plan §H.4.3.

### §2.8 Multi-Client file-locking — SILENT

`client.md` L228-234: "Multiple clients can be run at the same time, though they must share the same `tokens_db` file to avoid token conflicts." No `threading.RLock` or `BEGIN EXCLUSIVE` mentioned in schwabdev's docs.

**Resolution:** plan §F.1 + §A.2 already commit to defensive concurrency handling (`SchwabPipelineActiveError` cross-surface exclusion per §H.10). T-A.5 + T-A.10 pipeline-active exclusion tests cover.

### §2.9 Callback URL — trailing-slash gotcha + paste-back format

- `troubleshooting.md` L72-78: registered callback MUST NOT have trailing slash. (Operator-side advisory; ensure `cfg.integrations.schwab.callback_url` default rejects trailing slash at `__post_init__`.)
- `setup-guide.md` L23-26: callback URLs MUST be HTTPS + localhost. Multiple callbacks comma-separated at Schwab Developer Portal app.
- Operator's two registered callbacks: `https://127.0.0.1` (root) + `https://127.0.0.1:8182` (port-bound). V1 PASTE-ONLY uses the root form (matches schwabdev's default — `client.md` L41 confirms `callback_url="https://127.0.0.1"`).

### §2.10 `capture_callback.py` example — explicitly OUT OF SCOPE V1

`examples.md` L629-777 documents a local HTTPS listener (`https://127.0.0.1:7777`) that auto-captures the redirect via `call_on_auth=` injection. Requires self-signed cert at `~/.schwabdev/localhost.crt` + `.key`. V1 plan §A.1 Q13 PASTE-ONLY → V2 candidate. (No code surface in Sub-bundle A consumes `call_on_auth`.)

### §2.11 7-day refresh expiry — no programmatic workaround (`troubleshooting.md` L64-68)

> "Known limitation: Schwab refresh tokens expire in 7 days. ... There is no programmatic extension — operator MUST re-authenticate via browser flow at least once per 7 days."

Confirmed. T-A.6 status surface MUST display refresh_token validity time-remaining (plan §K.A S5 acceptance) so operator can self-schedule re-auth.

---

## §3 Plan §E.1 reconciliation — 3 falsifications + 5 confirmations

| Plan §E.1 claim | schwabdev actual | Status | Resolution |
|---|---|---|---|
| `schwabdev.auth.manual_flow(app_key, app_secret, callback_url, tokens_db)` callable | NO such module/function; paste-back is embedded in `Client.__init__` only | **FALSIFIED** | T-A.3/T-A.4 wrap `schwabdev.Client(...)` construction directly; plan amendment candidate §A. |
| `tokens_file` kwarg | Actual kwarg is `tokens_db` (`client.md` L41) | **FALSIFIED** | All Sub-bundle A code uses `tokens_db`; plan amendment candidate §B. |
| `Tokens.revoke()` method | NOT exposed | **FALSIFIED** | T-A.5 issues manual `POST /v1/oauth/revoke` per plan §E.6 fallback; plan amendment candidate §C. |
| `Tokens.update_tokens(force_refresh_token=False)` | Confirmed (`client.md` L130-154) | **CORRECT** ✓ | T-A.5 consumes verbatim. |
| `client.tokens.access_token` / `.refresh_token` attribute access | Confirmed (`client.md` L108-124) | **CORRECT** ✓ | T-A.6 reads via these. |
| Per-env tokens DB (sandbox/production separation) | `tokens_db=` accepts arbitrary path → plan §F.1 per-env pattern works as-is | **CORRECT** ✓ | T-A.3 path resolution unchanged. |
| 7-day refresh expiry forces full re-auth | Confirmed (`troubleshooting.md` L64-68) | **CORRECT** ✓ | T-A.6 surfaces; operator-action in §I.1. |
| Trailing-slash gotcha on callback URL | Documented (`troubleshooting.md` L72-78) | **CORRECT** ✓ | T-A.2 `SchwabConfig.callback_url.__post_init__` rejects trailing slash. |
| Rate limits 120/min + 4000 orders/day | Confirmed (`client.md` L255-265) | **CORRECT** ✓ | Sub-bundle B handles at audit layer. |
| Multi-Client file-locking semantics | SILENT in schwabdev | matches plan §A.2 assumption | Project handles defensively via `SchwabPipelineActiveError`. |

---

## §4 Per-task impact within Sub-bundle A

### T-A.1 (dependency pin) — UNCHANGED
Pin remains `schwabdev>=2.4.0,<3.0.0`. Acceptance: `import schwabdev; assert schwabdev.__version__ within pin range`.

### T-A.2 (cfg cascade `SchwabConfig`) — ADD `callback_url` field
Per §2.9 above. Plan §A.6 enumerated 5 fields (`environment`, `account_hash`, `lookback_days`, `timeout_seconds`, `marketdata_ladder_enabled`). **Add 6th field: `callback_url: str = 'https://127.0.0.1'`** with `__post_init__` validator rejecting empty string / trailing slash / non-HTTPS / non-localhost. T-A.2's +10 tests grows to +12 (2 new validator tests). Banked as V2.1 §VII.F amendment §D below.

### T-A.3 (sub-package skeleton + SchwabClient wrapper) — wrap `schwabdev.Client(...)` directly
Plan §H.3 already says "wrap `schwabdev.Client(...)`" — implementation uses the 8-param constructor signature verbatim. `SchwabClient.__init__` accepts `app_key`, `app_secret`, `callback_url` (from cfg), `tokens_db` (per-env path), `timeout` (from cfg), `open_browser_for_auth=True` (V1 default), `call_on_auth=None` (V1 paste-only). The exception hierarchy is unchanged.

### T-A.4 (OAuth paste-back setup flow) — INSTANTIATE `schwabdev.Client(...)`; no `auth.manual_flow` call
**Falsification #1 impact.** Implementation must:
1. CLI prompts for `client_id` + `client_secret` (interactive — never stored in cfg).
2. `swing schwab setup` instantiates `schwabdev.Client(app_key=client_id, app_secret=client_secret, callback_url=cfg.callback_url, tokens_db=resolved_per_env_path, open_browser_for_auth=True)`.
3. schwabdev's constructor prints consent URL + opens browser + blocks on stdin paste.
4. Operator pastes the redirected URL — constructor returns a Client instance.
5. Wrapper calls `client.account_linked()` (real method per plan §E.2; verified in `api-calls.md`) to obtain the `[{accountNumber, hashValue}, ...]` array.
6. Auto-pick (single account) or prompt (multi-account); persist chosen `hashValue` to `user-config.toml` via cfg cascade write.
7. Emit success advisory.

Audit-row INSERT-then-UPDATE wraps the Client construction call (audit `endpoint='oauth.paste_flow'`).

### T-A.5 (force-refresh + logout) — manual revoke POST
**Falsification #3 impact.** Force-refresh consumes `client.update_tokens(force_refresh_token=True)` verbatim per §2.4 — CONFIRMED. Revoke uses manual POST per §2.5 — already in plan §E.6 as fallback; promoted to primary path.

`revoke_and_delete(...)` implementation:
1. Read current refresh_token from `client.tokens.refresh_token`.
2. `requests.post('https://api.schwabapi.com/v1/oauth/revoke', data={'token': refresh_token, 'token_type_hint': 'refresh_token'}, auth=(client_id, client_secret), timeout=cfg.timeout_seconds)` (basic-auth per Schwab OAuth 2.0 standard).
3. Audit row written with `endpoint='oauth.revoke'`; `status='success'` on HTTP 200 OR `status='error'` on non-200 — operator-facing outcome (sidecar delete) succeeds either way.
4. `os.replace(tokens_db_path, tokens_db_path + '.deleted-<ts>')` (per CLAUDE.md `os.replace` cross-device-link gotcha — same-volume; OK).
5. Leave renamed file 24h for recovery window per plan §F.3.

### T-A.6 (status CLI) — tokens DB schema introspection
**§2.6 inconsistency impact.** Status implementation must handle BOTH `.db` (SQLite) AND `.json` flavors gracefully. Phase-2 live verification will land the canonical answer; until then, T-A.6 reads `client.tokens.access_token` + `.refresh_token` via the schwabdev Client attribute surface (which abstracts over the on-disk format).

### T-A.7..T-A.10 — UNCHANGED
Migration 0018 (T-A.7), audit repo (T-A.8), audit service (T-A.9), token redactor (T-A.10) are downstream-of-schwabdev surface and unaffected by these falsifications. Cassette recording at T-A.10 + phase 2 will use whatever real surface schwabdev exposes.

---

## §5 Phase-2 (live) verification still pending

Phase 2 runs after T-A.4 ships `swing schwab setup` CLI. Operator-paired session captures:

1. **Tokens DB on-disk format** — SQLite (`.db` per `client.md`) or JSON (`tokens.json` per `troubleshooting.md`)? Inspect file post-setup.
2. **`client.account_linked()` actual response** — confirm response shape matches Schwab REST `[{accountNumber, hashValue}, ...]`. Capture sanitized cassette.
3. **`update_tokens(force_refresh_token=True)` behavior** — does access_token rotate? Does refresh_token also rotate (Schwab does per upstream §1; schwabdev should reflect)?
4. **`POST /v1/oauth/revoke` actual response** — capture HTTP response shape; flag if non-200 (acceptable per plan §E.6 — tolerated).
5. **Operator's number of linked accounts (Q3)** — single vs multi-account; informs T-A.4 prompt behavior tested with real data.

Phase-2 output: append findings to this doc as §6 (under header `## §6 Phase-2 live observations`) + commit as `docs(schwab-api): T-A.0.b phase-2 live observations`.

---

## §6 Banked V2.1 §VII.F amendment candidates (3 plan deviations)

Per project methodology-correction protocol (V2.1 §VII.F) — orchestrator triages post-Sub-bundle-A-ship.

**§A.** Plan §E.1 row 1 (`schwabdev.auth.manual_flow(...)`) — DELETE row; replace with single row describing `schwabdev.Client(...)` 8-param constructor + embedded paste-back flow. Reference `client.md` L37-46 verbatim.

**§B.** Plan §E.1 + §F.1 + §H.1 + §H.3 — every reference to `tokens_file` REPLACED with `tokens_db`. (Quick global find/replace within those sections.)

**§C.** Plan §E.1 row 3 (`Tokens.revoke()`) — change "[VERIFY]" to "NOT EXPOSED — manual POST per §E.6". Move §E.6's fallback path to primary.

**§D.** Plan §A.6 + §Tasks-A T-A.2 — add `callback_url: str = 'https://127.0.0.1'` as the 6th SchwabConfig field; T-A.2 acceptance test count grows +10 → +12; validator rejects trailing slash + non-HTTPS + non-localhost.

---

## §6.bis Phase-2 live verification observations (2026-05-14)

Operator-paired live OAuth paste-back flow executed against operator's actual Schwab production-tier app. Two attempts:

**Attempt 1** (audit `call_id=1` + `2`, manually corrected to `auth_failed` post-hoc) — operator pasted the redirected URL outside Schwab's ~30-second `code` validity window. schwabdev returned `unsupported_token_type / AuthorizationCode has expired`, printed a 2nd consent URL, and the operator's 2nd paste also failed. schwabdev's `Client.__init__` returned WITHOUT raising despite both failures. Our wrapper's success-path audit fire (no token validation) marked both rows `status='success'`. Then `client.account_linked()` returned a dict error envelope; `accounts[0]` blew up with `KeyError: 0`. Hotfix `bdf82da` (D1+D2+D3) addressed:

- **D1:** verify `client.tokens.access_token` is populated post-Client construction; treat empty as `auth_failed`.
- **D2:** validate `client.account_linked()` returns a list of dicts with `hashValue`; reject error envelopes.
- **D3:** move `connect()` (schema-version check) BEFORE the credential prompts (UX — fail fast on v17 mismatch before wasting operator typing).

Cleanup script at `scripts/fix_phase2_misleading_audit_rows.py` corrected `call_id=1` + `2` to `status='auth_failed'`.

**Attempt 2** (audit `call_id=3` + `4`) — operator pasted within window, full flow succeeded.

### §6.bis.1 Live observations confirmed

| Item | Live observed value | Resolves recon doc item |
|---|---|---|
| Tokens DB on-disk format | **JSON** (NOT SQLite); file starts `{"access_token_issued": "<ISO>", "refresh_token_issued": "<ISO>", "token_dictionary": {"expires_in": 1800, ...}}` | §2.6 inconsistency RESOLVED |
| File size at first-success | 957 bytes | — |
| schwabdev kwarg | `tokens_file=` (NOT `tokens_db=`) | §6 §B amendment CONFIRMED via live schwabdev 2.5.1 inspection |
| schwabdev 2.5.1 signature | `(app_key, app_secret, callback_url='https://127.0.0.1', tokens_file='tokens.json', timeout=10, capture_callback=False, use_session=True, call_on_notify=None)` | DEVIATES from distilled `client.md` (which is STALE relative to installed lib) |
| `access_token` TTL | `expires_in=1800` (30 minutes) | §2.3 CONFIRMED |
| Schwab `code` expiry window | ~30 seconds from redirect (Attempt 1 failure confirms) | New live observation |
| Auto-launch browser | Worked (despite `open_browser_for_auth=` no longer being a kwarg in 2.5.1 — must be default-on internally) | — |
| Callback Schwab picked | `https://127.0.0.1` root (NOT `:8182` port-bound) | V1 paste-only flow validated |
| Redirected URL shape | `https://127.0.0.1/?code=<URL-encoded>&session=<UUID>` | `session` UUID query param NOT documented in distilled refs |
| `client.account_linked()` success shape | List of dicts with `accountNumber` + `hashValue` (matches Schwab REST §1) | schwabdev passes through unchanged |
| Operator's linked accounts | Single (auto-pick fired; multi-account prompt untested live) | Q3 RESOLVED for operator |
| `account_hash` length | 64 chars | New live observation |
| CLI auto-pick echo masking | `E8F...0676` (first-3 + `...` + last-4) | DIVERGES from FIELD_REGISTRY masking |
| FIELD_REGISTRY masked render | `E8F***76` (first-3 + `***` + last-2) | MATCHES plan §A.6 mock `1A2***9F` exactly |
| Audit row count after success | 4 rows in `schwab_api_calls`: 2 corrected-to-`auth_failed` + 2 `success` | T-A.8 + T-A.9 lifecycle working end-to-end |
| `~/swing-data/user-config.toml` | `[integrations.schwab].account_hash` set to 64-char hashValue | T-A.2 + T-A.4 cfg-cascade write working |

### §6.bis.2 Browser-only failure modes observed

- **schwabdev's `Client.__init__` blocks on stdin** — `CliRunner.invoke(input=...)` covers in tests; live operator-paired flow blocks on `input()` inside schwabdev.
- **`schwabdev.Client(...)` does NOT raise on auth failure** — prints + retries + returns silently. Caller MUST verify post-construction state (`client.tokens.access_token` populated). Hotfix D1 codifies.
- **schwabdev passes through Schwab's error JSON unchanged** — `account_linked()` returns dict envelope rather than raising. Caller MUST validate shape. Hotfix D2 codifies.

### §6.bis.3 NEW deviations banked beyond §6 §A-§D (post-phase-2)

**§E (new, phase-2):** `schwabdev.Client(...)` 2.5.1 signature does NOT match `reference/schwabdev/client.md`. Distilled doc is STALE relative to installed library. **Implication:** `reference/schwabdev/` should carry a version-pinned header; future re-distill on each pin bump.

**§F (new, phase-2):** Tokens DB content is JSON despite our `.db` file-extension naming. Cosmetic mismatch. V2 candidate: rename to `schwab-tokens.{env}.json` for honesty, OR document the dissonance. V1 accepts.

**§G (new, phase-2):** Two masking surfaces with different rules:
- CLI auto-pick echo: `first-3 + ... + last-4` (renders `E8F...0676`).
- FIELD_REGISTRY render: `first-3 + *** + last-2` (renders `E8F***76`).
V2 cleanup: unify via shared helper.

**§H (new, phase-2):** schwabdev's stdin retry behavior on first paste-back failure prints "refresh token has expired!" + a 2nd consent URL + re-prompts. Operator's empty 2nd input → schwabdev silently returns without raising. Hotfix D1 covers; no further V1 action needed.

### §6.bis.4 Phase-2 audit-row evidence (post-hotfix)

```
(4, '2026-05-14T01:28:15', 'accounts.linked',     status='success',     http=200, error_message=None)
(3, '2026-05-14T01:27:39', 'oauth.code_exchange', status='success',     http=200, error_message=None)
(2, '2026-05-14T01:14:19', 'accounts.linked',     status='auth_failed', http=200, error_message=<corrected via cleanup script>)
(1, '2026-05-14T01:10:13', 'oauth.code_exchange', status='auth_failed', http=200, error_message=<corrected via cleanup script>)
```

All `error_message` values are short explanatory strings with NO token bytes — discriminating per T-A.10 sentinel-leak audit binding contract.

---

## §7 Implementation deviations binding for Sub-bundle A (LOCKED at this dispatch)

This recon doc supersedes the affected plan sections for the duration of Sub-bundle A execution. Per the project's recon-doc-supersession pattern (Phase 9 Sub-bundle D recon doc precedent at `docs/phase9-bundle-D-task-D0-recon.md` §3 note + Phase 9 Sub-bundle E parser recon at `docs/phase9-bundle-E-task-E3-parser-recon.md`).

T-A.2 ships 6 fields. T-A.3 wraps `schwabdev.Client(...)`. T-A.4 paste-back happens at Client construction. T-A.5 revoke uses manual POST. T-A.6 reads via `client.tokens.*`. Plan-text amendments (§6 above) routed through V2.1 §VII.F post-ship.
