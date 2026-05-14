# Schwab API Integration — Design Spec (Brainstorm Output)

**Baseline:** `main` at HEAD `c4252d3` (post-Phase-10-close orchestrator handoff brief). Schema_version = 17 stable; ~3286 fast tests green; ruff 18 (E501 only); fast suite default `-n auto` at ~63s. Phase 10 shipped at `38dbac3` (Sub-bundle E + arc closer at `d560218`); post-Phase-10 infra bundle shipped at `27ce96f` (cleanup-script `-DeregisterFirst` + pytest-xdist baseline). Phase 9 + Phase 10 together installed the source-ladder + reconciliation + metrics-dashboard infrastructure that consumes Schwab data the moment it lands.

**Goal:** Lock V1 ARCHITECTURE + AUTH FLOW + ENDPOINT CATALOG + PIPELINE INTEGRATION + AUDIT SURFACE + OPERATOR SETUP for Schwab Developer Portal API consumption. Source-ladder write path is INHERITED from Phase 9 Sub-bundle C — Schwab API integration consumes it; does NOT re-design. Schwab Market Data API ladder over yfinance is **V1 INCLUDE** per operator-flagged dimension at brief §1.9. RESEARCH-AND-LOCK posture: architecture + interfaces + operator-actionable open questions, NOT migration SQL, NOT code.

**Brief:** `docs/schwab-api-brainstorm-dispatch-brief.md` (commit `c4252d3`).

**Scope inputs (binding, not re-derived):**
- Phase 9 Sub-bundle A + C source-ladder shipped (`_SOURCE_PRECEDENCE = {schwab_api: 0, tos_csv: 1, manual: 2}` at `swing/data/repos/account_equity_snapshots.py:38`; `record_snapshot(source=...)` polymorphic at `swing/trades/account_equity_snapshots.py:66`).
- Phase 9 Sub-bundle B reconciliation surface (`reconciliation_runs.source ∈ {'tos_csv', 'schwab_api', 'manual', 'system_audit'}` CHECK; `reconciliation_discrepancies` 10-type enum + 5-resolution enum already inclusive of every type Schwab will emit).
- Phase 10 Sub-bundle D capital-friction PROVISIONAL/LIVE dynamic badge consuming `get_latest_snapshot_on_or_before(with_provenance=True)` transparently.
- Finviz Elite API integration shipped 2026-05-06 at `002338a` (`swing/integrations/finviz_api.py:1-276`; `_step_finviz_fetch` at `swing/pipeline/runner.py:1620`; CLI vs pipeline concurrency exclusion via `FinvizPipelineActiveError`; user-config.toml `[integrations.finviz]` token; cassette `filter_query_parameters` + urllib3 DEBUG-log suppression).
- Operator already on Schwab brokerage; Dev Portal app registration is operator-actionable (open question Q1).
- v1.2 §7.8 / §7.9 framework-research-loop posture: operator-discretion order placement; automated order placement OUT OF SCOPE.

---

## §1 Background, framing, and binding constraints

### §1.1 What this spec produces

A locked V1 architecture (§3) covering: OAuth 2.0 authorization-code flow + token storage shape (sidecar JSON state file); endpoint catalog for Trader API + Market Data API surfaces (§3.3); pipeline step ordering + failure tolerance (§3.4); CLI surface (§3.5); audit-trail table + observability shape (§3.6); explicit inheritance of the Phase 9 source-ladder write path (§3.7); V1-INCLUDE market-data ladder design mirroring the equity-snapshot ladder pattern (§3.8). Schema-candidate sketches (§4) — column names + broad types + cardinality, NOT DDL. Token redaction discipline inheritance from Finviz (§5). Failure-mode catalog per HTTP status (§6). Operator setup flow (§7). Capture-needs feedback for already-shipped phases (§8). Open questions for orchestrator triage (§10).

### §1.2 What this spec does NOT produce (out of scope per brief §3)

Migration SQL (no `CREATE TABLE`, no FK cascade rules, no CHECK constraints, no indexes — writing-plans territory). Python code (no class definitions, no test bodies, no CLI command bodies — writing-plans / executing-plans territory). Sub-bundle decomposition (writing-plans output; spec MAY group V1 into 2-4 logical implementation phases but does NOT formalize as sub-bundles). Re-litigation of source-ladder semantics (already shipped per §1.3). Re-litigation of reconciliation discrepancy types (Phase 9 Sub-bundle B locked 10 types + 5 resolutions; Schwab MAY emit any existing type but does NOT introduce new types in V1). **Automated order placement** (POST /accounts/{accountNumber}/orders) — explicitly OUT OF SCOPE; this project is operator-discretion order placement at the broker. **Streaming endpoints** (WebSocket real-time quotes / order updates) — V2 candidate. **Option chains / fundamentals / instruments lookup** — V2 candidates. **Schwab inception-CSV historical ingestion** — separate dispatch per phase3e-todo 2026-05-12 entry. **TOS CSV reconciliation deprecation** — V2 follow-up; V1 retains TOS path as fallback.

### §1.3 Binding constraints (orchestrator-distilled, not re-derived)

Per brief §1.1–§1.9, the following are accepted as design inputs without re-justification:

1. **Source-ladder is consumed, NOT re-designed.** `_SOURCE_PRECEDENCE = {schwab_api: 0, tos_csv: 1, manual: 2}` is encoded at `swing/data/repos/account_equity_snapshots.py:38`. The CHECK enum on `account_equity_snapshots.source` (`'manual', 'schwab_api', 'tos_csv'`) and `reconciliation_runs.source` (`'tos_csv', 'schwab_api', 'manual', 'system_audit'`) already permit Schwab values. UNIQUE INDEX `ux_account_equity_snapshots_date_source` on `(snapshot_date, source)` enables per-source coexistence on the same date. `get_latest_snapshot_on_or_before(with_provenance=True)` already returns `(winner, suppressed)` for source-ladder UI rendering. **Schwab API integration calls `record_snapshot(source='schwab_api', ...)`; it does NOT touch the precedence map, the CHECK enum, or the read-side resolver.**
2. **Phase 10 metrics dashboard consumers are already in place.** PROVISIONAL/LIVE badge at `/metrics/capital-friction` consumes the source-ladder transparently. The moment Schwab API writes a snapshot per pipeline run, the LIVE badge sticks in steady state. **Capture-needs feedback for Phase 10 metrics is null for V1.**
3. **Schwab Developer Portal access is operator-gated; live verification is BLOCKING for executing-plans Task 0.b.** Mirror Finviz §A.1 precedent: synthesize endpoint shapes from public Schwab Trader API + Market Data API surface documentation; flag synthesis as §10 open questions; defer cassette recording to executing-plans Task 0.b paired-operator live verification.
4. **Cash-basis-vs-MTM resolved by API.** Schwab API returns Net Liquidating Value authoritatively per-call. V1 retains operator's ability to record cash-basis manual snapshots for back-recording (source-ladder resolves at read time). The column-level semantic ambiguity at `account_equity_snapshots.equity_dollars` remains a V2 column-formalization candidate (phase3e-todo 2026-05-12 entry) — Schwab integration does NOT close that V2 question.
5. **Rate limits low-cardinality at our cadence — but Market Data API has separate limits (verify at Task 0.b).** Schwab Trader API documents ~120 req/min per app. Schwab Market Data API may have DIFFERENT and POSSIBLY-LOWER limits per Schwab Developer Portal docs (per Codex R3 Major-3 — live-verify at Task 0.b; flag as §10 Q17 below). Pipeline cadence is daily; CLI is operator-triggered. V1 batching policy: `GET /marketdata/v1/quotes?symbols=A,B,C,...` (Schwab supports comma-separated symbols batching per public docs); `GET /pricehistory` is per-ticker but cache window is multi-bar → high hit-rate after first run per ticker. V1 mirrors Finviz §A.4 + §E.6: single attempt; on 429 parse `Retry-After`, wait + retry once, then give up + record `status='rate_limited'`. **NO retry loops in V1.** Rate-limit response on Market Data API independently of Trader API: each surface trips its own 429 → falls back to yfinance (V1 INCLUDE) for that ticker / window; Trader API auth + snapshot continue unaffected.
6. **Multi-account is V1 single-primary-account** (per §10 Q3 default). Operator selects primary account_hash at `swing schwab setup` time. Multi-account = V2 (schema impact: new account_hash column on snapshots + future-look accounts table).

### §1.4 Operator-flagged dimension: Schwab Market Data API ladder over yfinance — V1 INCLUDE

Per brief §1.9 + §2.9 Q11: operator surfaced `schwab_api > yfinance` market-data source-ladder as a real V1 candidate. Brainstorm dispatch's default recommendation: **V1 INCLUDE**. This spec writes the INCLUDE branch + explicitly flags the EXCLUDE branch's deferred design in §10 Q11.

V1 INCLUDE rationale (re-stated from brief §1.9 for spec record):

- yfinance is the project's most fragile external dependency (4+ documented regressions in CLAUDE.md gotchas: `threads=` kwarg removed from `Ticker.history()`; `group_by='column'` MultiIndex return; `history(interval='1d')` partial-bar inclusion; empty-result-vs-transient ambiguity).
- Replacing the primary path with a paid broker-grade source materially improves data quality + reduces ops surprises.
- The source-ladder pattern from Phase 9 Sub-bundle C transfers cleanly to `PriceCache` + `OhlcvCache` — same precedence-map shape, same with-provenance read mode, same "Schwab fresh wins / yfinance fresh fallback" semantics.
- Cache architecture changes are localized to two existing cache modules + their write-path callers.

V1 INCLUDE spec impact: +200-400 lines of spec body (§3.8 market-data ladder + §3.3 Market Data endpoint detail + §4.4 market-data schema candidates + §5/§6 redaction/failure inheritance to market-data path + §8 capture-needs adjustments). +1-2 sub-bundles in eventual writing-plans + executing-plans cycle.

**Operator override available at orchestrator-triage time post-brainstorm** (§10 Q11). If operator triages V1 EXCLUDE: §3.8 + market-data parts of §3.3 + §4.4 collapse into a "deferred to follow-on dispatch" subsection; the rest of the spec is unaffected.

### §1.5 Schwab Trader API + Market Data API surface (synthesized; live-verify at Task 0.b)

Schwab exposes TWO API surfaces under one OAuth 2.0 auth (same client_id + access_token):

**(a) Trader API** — base URL `https://api.schwabapi.com/trader/v1/` — account-data layer.
**(b) Market Data API** — base URL `https://api.schwabapi.com/marketdata/v1/` — market-data layer.

Both surfaces share token auth via `Authorization: Bearer <access_token>` header. V1 endpoint set is enumerated in §3.3. **All endpoint paths + response field names are synthesized from publicly-documented Schwab Trader / Market Data references** (Schwab Developer Portal, community-maintained wrappers like `schwab-py`, `schwabdev`); each is flagged as live-verify-at-Task-0.b. The brainstorm explicitly does NOT assert Schwab's exact JSON field names without operator paired-verification.

### §1.6 What Schwab API does NOT replace in V1 (locked)

Per brief §1.9 + this spec §1.3 + §10 Q7:

- **Finviz Elite candidate-screen** — Finviz is the screening source; Schwab is the brokerage source. Different layers; Schwab Market Data API has no equivalent screen-builder surface. Locked.
- **Manual `daily_management_records` capture** (Phase 8) — operator-driven post-trade-management observation; not an API surface. Locked.
- **Manual `review_log` capture** (Phase 6 + Phase 9) — operator-judgment surface; not an API surface. Locked.
- **TOS Account Statement CSV reconciliation path** (Phase 9 Sub-bundle B + E) — stays as V1 fallback for any account/period Schwab API doesn't cover OR when API is degraded. V2 deprecation question deferred (§10 Q7 default: stays as V1 fallback).
- **`exchange_calendars` library** (NYSE session-hours metadata) — `/marketdata/v1/markets/{market}/hours` is informational complement; V1 does NOT replace `exchange_calendars`.

---

## §2 Vocabulary anchored against shipped surfaces

| Term | Definition (this spec) | Anchor / shipped surface |
|---|---|---|
| **Schwab Trader API** | Schwab Developer Portal account-data API surface (balances, orders, transactions); base URL `https://api.schwabapi.com/trader/v1/`. | Schwab Developer Portal docs (operator-actionable; brainstorm synthesizes endpoint shapes). |
| **Schwab Market Data API** | Schwab Developer Portal market-data API surface (quotes, price history, market hours); base URL `https://api.schwabapi.com/marketdata/v1/`. | Schwab Developer Portal docs. |
| **OAuth 2.0 authorization-code flow** | Operator-driven browser redirect → Schwab consent screen → callback receives `authorization_code` → POST `/v1/oauth/token` exchanges code for `access_token` + `refresh_token`. | RFC 6749 §4.1 + Schwab Developer Portal auth docs. |
| **`access_token`** | Short-TTL bearer token (Schwab default ~30 min; verify at Task 0.b); appended to every API call as `Authorization: Bearer <token>`. | Schwab API auth docs. |
| **`refresh_token`** | Long-TTL token (Schwab default 7 days for "personal" tier; ~90 days for "production" tier — verify); exchanged for fresh `access_token` via `grant_type=refresh_token`. Schwab MAY rotate the `refresh_token` on each exchange — V1 MUST update the stored value if the response carries a new one. | RFC 6749 §6 + Schwab. |
| **`schwab-state.{env}.json`** | Per-environment sidecar JSON state file at `%USERPROFILE%/swing-data/schwab-state.sandbox.json` OR `schwab-state.production.json` holding `access_token`, `refresh_token`, `access_token_expires_at`, `refresh_token_expires_at` (best-effort), `account_hash`, `last_refresh_at`, `last_successful_call_at`, `environment` (`sandbox`|`production`), `client_id`, `client_secret`. NOT user-config.toml — that file is operator-edited config; sidecar is system-managed state. Per-environment separation is V1 default per §3.2.1 step 10 + Codex R2 Major-5. See §3.2. |
| **`account_hash`** | Schwab's encrypted account identifier used in URL paths (NOT the bare account number). Returned by GET `/trader/v1/accounts/accountNumbers` (or equivalent endpoint — live-verify shape at Task 0.b). Operator's primary account_hash persisted in `schwab-state.{env}.json` at setup time. |
| **`schwab_api_calls`** | Audit-trail table (mirror Finviz's `finviz_api_calls`) recording every API invocation including auth-token-exchange + refresh-token-exchange. Schema candidate sketched in §4.2 — DDL deferred to writing-plans. |
| **`source_artifact_path` for Schwab snapshot** | Opaque URI-style reference of the form `schwab_api:call/{call_id}` (where `{call_id}` is the `schwab_api_calls.call_id` PK), enabling provenance chase from the snapshot back to the audit row. NOT the response URL (would leak path + may include `account_hash`). |
| **PROVISIONAL → LIVE badge** | Phase 10 Sub-bundle D capital-friction surface UI state. PROVISIONAL = no `account_equity_snapshots` row ≤ asof_date; LIVE = one exists. Schwab API integration closes the LIVE-badge stickiness gap by writing a snapshot per successful pipeline run. |
| **`schwab_api > yfinance` market-data ladder (V1 INCLUDE branch)** | Source-ladder pattern mirroring Phase 9 Sub-bundle C equity-snapshot ladder: per-cache `_SOURCE_PRECEDENCE_MARKET_DATA = {schwab_api: 0, yfinance: 1}`; primary path tries Schwab first, falls back to yfinance; cache entries tagged with a NEW `provider` field (distinct from existing in-memory TTL-state markers, which the current code happens to call `source`); read-side resolver prefers higher-source-precedence row when both providers have entries for the same `(ticker, asof_date)`. Concrete refactor surface (rename collisions, persistence-shape choices A/B/C, method-name details) deferred to writing-plans per §3.8.2. |

---

## §3 V1 architecture (LOCKED defaults; alternatives in §10)

### §3.1 Module layout — `swing/integrations/schwab/` sub-package

Schwab is a multi-endpoint + multi-API-surface integration (Trader API + Market Data API). Single-file shape (Finviz precedent at `swing/integrations/finviz_api.py:1-276`) does not fit. Locked: **sub-package layout** under `swing/integrations/schwab/`:

- `__init__.py` — re-exports the public `SchwabClient`, exception classes, and the token-state load/save helpers.
- `auth.py` — OAuth 2.0 authorization-code flow + token-refresh logic + `schwab-state.{env}.json` load/save discipline. Owns the `Authorization: Bearer` header construction.
- `client.py` — `SchwabClient` HTTP wrapper. Mirrors `FinvizClient` shape (token-redaction discipline, urllib3 DEBUG-log suppression, typed exceptions). Holds endpoint-set constants.
- `trader.py` — Trader API endpoint methods (`get_accounts`, `get_account_balances`, `get_orders`, `get_transactions`). Each method returns a normalized dataclass (NOT raw JSON).
- `marketdata.py` — Market Data API endpoint methods (`get_quote`, `get_quotes_batch`, `get_price_history`, `get_market_hours`). Returns normalized dataclasses. **Only present in V1 INCLUDE branch** (this spec writes it; V1 EXCLUDE collapses to a sub-package stub).
- `mappers.py` — pure functions mapping Schwab API response JSON → existing project dataclass shapes (`AccountEquitySnapshot`, `Fill`, `Discrepancy` field shapes, `PriceCache` entries, `OhlcvCache` window). Decouples HTTP/JSON layer from project domain layer.

Test layout mirrors Finviz precedent (`tests/integrations/test_schwab_*.py`): cassette-driven `test_schwab_api_cassette.py` (one cassette per endpoint); `test_schwab_auth.py` for OAuth flow + refresh logic; `test_schwab_mappers.py` for response-shape projections; `test_schwab_token_redaction_audit.py` end-to-end sentinel-leak audit (mirror Finviz's audit test).

### §3.2 Auth flow + token storage

#### §3.2.1 Initial setup flow — `swing schwab setup`

LOCKED default — **two first-class variants** chosen via `--callback {localhost,paste}` flag (default `localhost`). Both variants are supported V1 because Schwab Developer Portal app's redirect-URI registration may not accept loopback HTTPS in every operator environment (corp networks, OS firewalls, self-signed-cert browser warnings) — paste-code is the always-works fallback.

**`localhost` variant** — mirrors community Schwab wrappers (`schwab-py` `easy_client` style).

Flow:

1. Operator runs `swing schwab setup` (default — equivalent to `--callback localhost`).
2. CLI prompts for: `client_id`, `client_secret`, `callback_url` (default `https://127.0.0.1:8765/callback`), `environment` (`sandbox`|`production`, **default `sandbox` per §10 Q1 — operator must explicitly type `production` to opt in once their Schwab app has production-tier approval**).
3. CLI constructs the consent URL: `https://api.schwabapi.com/v1/oauth/authorize?response_type=code&client_id=<client_id>&redirect_uri=<callback_url>&scope=<scope_string>` (scope string live-verified at Task 0.b — synthesized default `readonly` per Schwab convention; **flag in §10 Q14** with operator-actionable verification step).
4. CLI starts a one-shot local HTTPS listener on `127.0.0.1:8765` using a self-signed cert (generated on-the-fly into tmp; deleted on exit). Opens default browser to consent URL. CLI emits explicit operator advisory about the browser self-signed-cert warning ("you'll see a `Your connection isn't private` page — click `Advanced → Proceed`; this is expected").
5. Operator logs in to Schwab + approves consent.
6. Schwab redirects to `https://127.0.0.1:8765/callback?code=<authorization_code>`. Listener captures code; returns 200 + "You may close this tab" page.
7. CLI POSTs `https://api.schwabapi.com/v1/oauth/token` with `grant_type=authorization_code` + `code` + `redirect_uri` + Basic-auth `client_id:client_secret`.
8. Response (synthesized; live-verify): `{access_token, refresh_token, expires_in, token_type: "Bearer"}`. CLI computes `access_token_expires_at = now + expires_in - 60s` (60s safety margin; see §3.2.3).
9. CLI calls GET `/trader/v1/accounts/accountNumbers` (or equivalent — live-verify endpoint name + shape at Task 0.b; flag §10 Q14) to fetch operator's `account_hash` set. If multiple accounts returned, CLI prompts operator to pick a primary (V1 single-primary per §10 Q3).
10. CLI writes the per-environment sidecar file at `%USERPROFILE%/swing-data/schwab-state.{environment}.json` (i.e., `schwab-state.sandbox.json` OR `schwab-state.production.json`) with all fields above + `client_id` + `client_secret` (NOT in user-config.toml — see §3.2.2). **Per-environment file separation is the V1 default per Codex R2 Major-5** — if operator's Schwab Developer App is separate per environment (likely; Schwab Developer Portal typically issues distinct apps for sandbox vs production), the per-environment file shape avoids clobbering one environment's tokens when re-running setup for the other. Task 0.b confirms whether sandbox + production can be unified into a single file at the API layer. File permissions: best-effort owner-read-only on POSIX; on Windows the user-profile ACL inheritance is the default protection (no platform-specific hardening V1; §10 Q2 covers DPAPI hardening V2).
11. CLI emits success message + advises operator to run `swing schwab status` to verify.

**`paste` variant `[VERIFY]`** — operator runs `swing schwab setup --callback paste`. Implementability depends on Schwab Developer Portal support for one of three concrete out-of-band mechanisms (Codex R2 Major-4 flag — none of these is guaranteed; Task 0.b verifies which works):

- **(i)** Schwab supports an OOB redirect URI value like `urn:ietf:wg:oauth:2.0:oob` (RFC-blessed OAuth OOB convention; some providers honor it; many no longer). Schwab presents the authorization code in the consent flow as visible text the operator copies.
- **(ii)** Schwab permits an operator-controlled redirect URL that exposes the `code` query parameter as page content (e.g., operator runs a simple static page with JS that displays `window.location.search`). Requires operator to host such a page OR run a temporary tool.
- **(iii)** Schwab's consent flow displays the `code` directly on a final consent-page redirect when it cannot reach the registered callback URL. Behavior varies.

If NONE of (i)/(ii)/(iii) is supported at Task 0.b, `paste` variant is DROPPED from V1 and `localhost` becomes the only path. Spec acceptance: paste mode is a designed-but-pending-verification fallback, NOT a guaranteed-shipping feature.

Flow when implementable:
- 4'. CLI prints the consent URL + advises operator to open it in a browser (no listener started).
- 5'. Operator logs in + approves; Schwab presents code via one of (i)/(ii)/(iii) per Task 0.b verification.
- 6'. Operator copies the `code` value + pastes it back into the CLI prompt.

Both variants converge at step 7 onward. Operator's app registration on Schwab Developer Portal must list whichever callback URL the operator intends to use (or both if Schwab permits multiple redirect URIs per app — verify at Task 0.b).

#### §3.2.2 Token storage — sidecar JSON file, NOT user-config.toml

LOCKED default. Rationale:

- `user-config.toml` is operator-edited; Schwab tokens are system-managed (rewritten on every refresh; potentially several times per day if pipeline runs multiple times). Mixing operator-edited config with system-rotated state invites accidental clobbering (per Phase 9 Sub-bundle A `tomli_w.dump` strips-comments gotcha — operator's TOML comments would silently lose every refresh cycle).
- Sidecar JSON file is platform-conventional for OAuth state (mirrors `schwab-py`, `schwabdev`, Google API client libs, GitHub CLI, etc.).
- **Atomic-write discipline (per-env naming)**: refresh writes to `schwab-state.{env}.json.tmp` in the SAME directory (e.g., `schwab-state.sandbox.json.tmp` OR `schwab-state.production.json.tmp`), then `os.replace(tmp, final)` per CLAUDE.md cross-device-link gotcha. Per Codex R4 Major-2: per-env temp names prevent cross-env collisions during concurrent refreshes. NEVER use `shutil.move` expecting overwrite on Windows.
- **client_id + client_secret stored in the same sidecar file** for V1. Rationale: they are operator-Schwab-Dev-Portal-issued credentials that bind to the same OAuth app as the tokens; co-locating simplifies the "logout" flow (single-file delete = clean slate) + matches `schwab-py` convention.

**This is a HIGHER-RISK posture than Finviz, NOT a clean inheritance.** Finviz stored a single revocable query-param token. Schwab plaintext-at-rest sidecar holds: `client_secret` (operator-irrevocable except via Schwab Developer Portal re-issue) + `refresh_token` (7-day or 90-day TTL with broad replay value) + `access_token` (short-TTL, low value) + `account_hash` (operator-identifying). Anyone who reads `schwab-state.{env}.json` can impersonate the operator's Schwab API session until refresh_token TTL expires or operator revokes via portal. V1 acceptance: filesystem-ACL protection alone; operator-actionable threat model (single-operator personal machine; not shared filesystem; not committed to git — see §3.2.6 below). **V2 hardening promoted to high priority** (§10 Q2): platform-specific encryption-at-rest (DPAPI on Windows; `keyring` cross-platform), AT MINIMUM for `client_secret` + `refresh_token` (access_token's short TTL makes plaintext acceptable post-refresh-encryption-V2).

#### §3.2.3 Token-refresh strategy — lazy-on-first-API-call, proactive 60s safety margin

LOCKED default — mirrors Finviz client pattern (lazy fetch; defensive read).

- Every API call enters the path through `SchwabClient.ensure_authorized()`: reads `schwab-state.{env}.json`; checks `access_token_expires_at`; if `now >= access_token_expires_at` OR `(access_token_expires_at - now) < 60s`, refreshes.
- Refresh POSTs `https://api.schwabapi.com/v1/oauth/token` with `grant_type=refresh_token` + stored `refresh_token` + Basic-auth `client_id:client_secret`.
- Response handling: update `access_token` + `access_token_expires_at`; **if response carries a new `refresh_token`, update the stored value AND log the rotation event** (Schwab may rotate refresh tokens per their docs — V1 must handle, NOT silently leak validity of the old refresh token). See §10 Q15.
- If refresh fails with 401 (refresh_token expired or revoked): raise `SchwabRefreshTokenExpiredError`; CLI emits operator-actionable message ("run `swing schwab setup` to re-auth"); pipeline step records `status='auth_failed'` + continues per §3.4.4 failure tolerance.
- If refresh fails with 5xx or network error: raise `SchwabApiError`; pipeline step records `status='error'`.
- TOCTOU on token expiry: 60s safety margin handles clock-skew + back-to-back CLI invocations where the second call's token is mid-expiry. Per §10 watch-item 18 the 60s window is justified: pipeline step duration < 60s typical; CLI duration < 5s typical; 60s comfortably exceeds both.

#### §3.2.4 Concurrency on token refresh + mutating CLI surfaces

**Two distinct concurrency surfaces — V1 design splits them deliberately.**

**(a) Token refresh — file-lock on sidecar (always-on; covers all surfaces).**

A concurrent refresh race COULD occur if the operator runs `swing schwab fetch` while the pipeline's `_step_schwab_*` is mid-call. Both surfaces would read the same sidecar file + both might refresh. Schwab MAY accept both refreshes (returning two new access_tokens; the first becomes orphaned) OR Schwab may reject the second (invalidating the refresh_token). **V1 mitigation: file-lock on `schwab-state.{env}.json` during refresh** — acquire OS advisory file-lock (Windows `msvcrt.locking` / POSIX `fcntl.flock`); refresh + write under lock; release. Lock timeout: 30s; on timeout raise `SchwabConcurrentRefreshError` + pipeline step continues with `status='error'` per §3.4.4.

**(b) Mutating CLI fetches — pipeline-active hard exclusion for `--orders` and `--all`; concurrent-safe for `--snapshot` and `status`.**

LOCKED per Major-finding triage:

- `swing schwab fetch --orders` and `swing schwab fetch --all`: writes `reconciliation_runs` rows (which do NOT have UPSERT-on-(period, source) semantics — every invocation creates a new run_id). Concurrent pipeline + CLI fetches would produce duplicate runs for the same period covering the same data, polluting the discrepancy timeline. **V1 mitigation: `SchwabPipelineActiveError` mirror of Finviz precedent at `swing/integrations/finviz_api.py:90-94`** — CLI refuses if a `pipeline_runs` row with `state='running'` exists; operator advised to wait or kill the pipeline.
- `swing schwab fetch --snapshot`: writes `account_equity_snapshots` via UPSERT-on-`(snapshot_date, source)` (PK-preserving SELECT-then-UPDATE-or-INSERT at `swing/data/repos/account_equity_snapshots.py:81`). **However, concurrent pipeline + CLI snapshot writes for the same `(snapshot_date, 'schwab_api')` BOTH UPDATE the same row, leaving the `source_artifact_path` + `recorded_at` + `recorded_by` from the LAST writer to win — while both surfaces' `schwab_api_calls` audit rows would link to the same `snapshot_id` with one provenance pointer mismatched from its own audit row** (Codex R2 Major-3). **V1 mitigation: same hard exclusion** — CLI refuses if a pipeline run is `state='running'`. Operator advised to wait or kill the pipeline.
- `swing schwab status`: read-only on `schwab_api_calls` + `schwab-state.{env}.json`. **Concurrent-safe; NO exclusion.**
- `swing schwab refresh`: write to `schwab-state.{env}.json` only (no DB writes). Protected by the (a) file-lock; **concurrent-safe; NO pipeline-active exclusion.**
- `swing schwab logout`: revocation + sidecar delete (§3.2.5). **Concurrent-with-pipeline UNSAFE** (pipeline mid-fetch could 401 mid-step); CLI refuses while pipeline running OR proceeds with explicit `--force` flag. Default: refuse.
- `swing schwab setup`: rewrites sidecar from scratch. Concurrent-with-pipeline UNSAFE for the same reason as `logout`. Default: refuse with `--force` override.

#### §3.2.5 Revocation — `swing schwab logout`

LOCKED. Operator runs `swing schwab logout`. CLI:

1. Best-effort POST to Schwab's token-revocation endpoint (live-verify at Task 0.b; synthesized `https://api.schwabapi.com/v1/oauth/revoke`). Failure tolerated — proceeds regardless.
2. Deletes `schwab-state.{env}.json` atomically (rename to `schwab-state.{env}.json.deleted-<ts>` first, then unlink; preserves a brief recovery window on accidental invocation). Per-env naming prevents cross-env collision on the deleted-marker per Codex R4 Major-2. `.gitignore` patterns from §3.2.6 cover the deleted markers via the `swing-data/schwab-state*.json` glob — orphan markers from a crashed logout cannot escape into git.
3. Logs the revocation event (operator-visible).
4. Subsequent API calls fall back to PROVISIONAL state (Phase 10 capital-friction badge); operator runs `swing schwab setup` to re-auth.

#### §3.2.6 Sidecar file footgun guards (V1)

LOCKED. The plaintext sidecar's blast radius requires these guardrails ship V1 (writing-plans firms up exact implementation):

- `.gitignore` MUST list a permissive pattern covering ALL sidecar variants BEFORE V1 ships: `swing-data/schwab-state*` (matches `schwab-state.sandbox.json`, `schwab-state.production.json`, `*.tmp` atomic-write intermediates, `*.deleted-<ts>` revocation orphans, and any future variant — per Codex R3 Major-2 + R4 Major-2). Operator's `swing-data/` is normally outside the repo per CLAUDE.md DB-location invariant, but a misconfigured operator copy could risk a leak. Writing-plans includes a discriminating test: `git check-ignore -v` returns non-empty for `swing-data/schwab-state.sandbox.json`, `swing-data/schwab-state.production.json`, `swing-data/schwab-state.production.json.tmp`, AND `swing-data/schwab-state.production.json.deleted-20260513T120000Z`.
- `swing schwab setup` emits a final advisory line: `WARNING: schwab-state.{env}.json contains plaintext OAuth secrets. Do not back this file up to cloud storage / shared filesystems. To revoke: 'swing schwab logout'.`
- `swing schwab status` reports the absolute path of `schwab-state.{env}.json` + permissions check result.
- File permissions: best-effort owner-read-only on POSIX (`chmod 600`); on Windows the user-profile ACL inheritance is the default protection (no platform-specific hardening V1; §10 Q2 covers DPAPI hardening V2).

#### §3.2.7 Active-environment selection — `cfg.integrations.schwab.environment` (single source of truth)

LOCKED per Codex R3 Major-1. The per-environment sidecar shape from §3.2.1 + the sandbox-verification-only contract from §3.6.3 both require a single authoritative answer to "which environment is active right now?".

- **Single source of truth:** `cfg.integrations.schwab.environment` ∈ `{sandbox, production}` in user-config.toml; default `production`. Writing-plans firms up the config schema + cfg-cascade integration (Phase 5 precedent).
- **Sidecar path resolution:** every consumer derives sidecar path as `~/swing-data/schwab-state.{cfg.integrations.schwab.environment}.json`.
- **CLI per-invocation override:** every `swing schwab <subcommand>` accepts `--environment {sandbox,production}` flag. Override takes precedence over cfg for that invocation only; does NOT mutate cfg or user-config.toml.
- **Pipeline:** reads cfg only; cannot be overridden mid-pipeline. To run a sandbox-mode pipeline, operator flips cfg to `sandbox`, runs pipeline, flips back. (Sandbox pipeline = verification-only; no domain writes per §3.6.3.)
- **`swing schwab setup --environment <env>`:** creates the sidecar file BUT does NOT update `cfg.integrations.schwab.environment` automatically. Operator runs `swing config set integrations.schwab.environment <env>` to flip the active env. This avoids the footgun of `setup --environment sandbox` silently flipping the active env away from production.
- **`swing schwab status`:** reports BOTH the cfg-active env AND the set of sidecar files present on disk ("active env: production; sidecar files: schwab-state.sandbox.json (last refreshed 2026-05-10), schwab-state.production.json (last refreshed 2026-05-13)").

### §3.3 Endpoint catalog (V1; live-verify at executing-plans Task 0.b)

Each endpoint flagged with `[VERIFY]` requires operator paired-verification at Task 0.b before its cassette can be recorded. Endpoint shapes synthesized from public references; live response may differ.

#### §3.3.1 Trader API endpoints (V1; account-data)

| Method + Path | Purpose | Required input | Project consumer | Failure modes |
|---|---|---|---|---|
| **POST `/v1/oauth/token`** `[VERIFY]` | OAuth code exchange + refresh | `grant_type` + (`code`+`redirect_uri`) OR (`refresh_token`); Basic-auth `client_id:client_secret` | `auth.py` | 400 invalid_grant; 401 invalid_client; 5xx |
| **GET `/trader/v1/accounts/accountNumbers`** `[VERIFY]` | Discover account_hash set | `Authorization: Bearer` only | `swing schwab setup` (one-time) | 401 expired; 403 scope |
| **GET `/trader/v1/accounts/{account_hash}`** `[VERIFY]` | Account balances (Net Liq Value, cash, buying power) | `account_hash` path param; `fields=positions` optional | `_step_schwab_snapshot` → `record_snapshot(source='schwab_api', equity_dollars=<NLV>, ...)` | 401; 403; 404 invalid account_hash |
| **GET `/trader/v1/accounts/{account_hash}/orders`** `[VERIFY]` | Working orders + filled orders (supplements / primary when API is available; TOS Account Order History parser stays as V1 fallback per §10 Q7) | `account_hash`; optional `fromEnteredTime` + `toEnteredTime` ISO datetimes; optional `status` filter | `_step_schwab_orders` → emits `reconciliation_runs(source='schwab_api')` + per-discrepancy as needed | 401; 403; 429 |
| **GET `/trader/v1/accounts/{account_hash}/transactions`** `[VERIFY]` | Historical fills + cash movements | `account_hash`; `startDate` + `endDate` ISO dates; optional `type` filter | `_step_schwab_orders` (combined call); cash_movement_mismatch detection | 401; 403; 429 |
| **POST `/v1/oauth/revoke`** `[VERIFY]` | Token revocation | `token` + Basic-auth | `swing schwab logout` | best-effort; failure tolerated |

#### §3.3.2 Market Data API endpoints (V1 INCLUDE; per §10 Q11)

| Method + Path | Purpose | Required input | Project consumer | Failure modes |
|---|---|---|---|---|
| **GET `/marketdata/v1/quotes`** `[VERIFY]` | Last/bid/ask/mark for one or many symbols (batched) | `symbols=AAPL,MSFT,...` query param | `PriceCache.get_latest(ticker)` (primary path); fallback yfinance on failure | 401; 403; 429; partial responses (some tickers OK + some errored) |
| **GET `/marketdata/v1/{symbol}/pricehistory`** `[VERIFY]` | Historical OHLCV (daily / intraday) | `symbol` path or query; `periodType` + `period` OR `frequencyType` + `frequency` + `startDate` + `endDate` | `OhlcvCache.get_window(ticker, start, end)` (primary path); fallback yfinance | 401; 403; 429; empty data array (treat as transient per CLAUDE.md gotcha — see §3.8.6) |
| **GET `/marketdata/v1/markets/{market}/hours`** | (V2 candidate — listed for completeness; NOT consumed V1; no callsite; no cassette V1) | — | — | — |

Streaming WebSocket endpoints — explicitly OUT OF SCOPE per §1.2 + §10 Q4.

#### §3.3.3 Endpoint NOT consumed in V1

- **POST `/trader/v1/accounts/{account_hash}/orders`** — automated order placement. **EXPLICITLY OUT OF SCOPE per §1.2.** This project is operator-discretion order placement at the broker UI. Brainstorm spec MUST NOT propose architecture that "could easily extend" to order placement — the boundary is by design.
- **DELETE `/trader/v1/accounts/{account_hash}/orders/{order_id}`** — order cancellation. OUT OF SCOPE for the same reason.
- **GET `/trader/v1/userPreference`** — user preferences. V2 candidate only if a use case emerges.
- **GET `/marketdata/v1/instruments`** — instrument search / fundamentals. V2 candidate.
- **GET `/marketdata/v1/chains`** — option chains. OUT OF SCOPE (project is equities-only).
- **WebSocket streaming endpoints** — V2 candidate per §10 Q4.

### §3.4 Pipeline integration architecture

#### §3.4.1 New pipeline steps (V1)

LOCKED default — **two new steps; market-data path is cache-layer-internal (NOT a separate step)**:

1. **`_step_schwab_snapshot`** — calls Trader API `GET /accounts/{account_hash}` → maps response to `equity_dollars` (Net Liq Value field; live-verify field name at Task 0.b) → calls `record_snapshot(conn, equity_dollars=..., source='schwab_api', source_artifact_path=f"schwab_api:call/{call_id}", recorded_by='schwab_api', notes=None)`.
2. **`_step_schwab_orders`** — calls Trader API `GET /accounts/{account_hash}/orders` + `GET /accounts/{account_hash}/transactions` for the period `(last_completed_session(now) - lookback_days, last_completed_session(now))` (default `lookback_days=7` matching TOS path semantics; configurable in user-config.toml). Maps responses → `reconciliation_runs(source='schwab_api')` + per-discrepancy rows via existing `swing/data/repos/reconciliation.py` API. Reuses every Phase 9 Sub-bundle B/E discrepancy type (no new types).

**Market-data integration (V1 INCLUDE branch only) is NOT a separate pipeline step.** The Schwab tier of `PriceCache` + `OhlcvCache` is consulted on-demand inside the existing `_step_evaluate` + `_step_charts` fetch boundaries (the same callsites that currently invoke yfinance). See §3.8 for the cache-rewrite design surface.

#### §3.4.2 Step ordering — after `_step_recommendations`, before `_step_charts`

LOCKED default (per §10 Q10):

```
_step_finviz_fetch
  → _step_evaluate
    → _step_daily_management
      → _step_watchlist
        → _step_recommendations
          → _step_schwab_snapshot     ← NEW (Trader API; equity NLV)
            → _step_schwab_orders     ← NEW (Trader API; orders + transactions)
              → _step_charts
                → _step_export
                  → _step_review_log_cadence
```

Rationale:
- BEFORE `_step_charts`: ensures `_step_charts` can include current-stop overlays informed by Schwab-detected stop drift if a discrepancy emitter wants to feed back (V1 does NOT; reserves the option).
- BEFORE `_step_export`: `briefing.md` + `briefing.html` rendering happens at export time; placing Schwab steps before export means the LIVE-badge equity figure + reconciliation-discrepancy summary land in the briefing automatically (no separate render path).
- AFTER `_step_recommendations`: recommendations consume capital_friction inputs; placing Schwab snapshot AFTER recommendations means V1 recommendations see whatever snapshot existed at run-start (matches current state). V2 candidate to move BEFORE recommendations once metric-coupling stabilizes; flagged at §8 capture-needs + §10 Q10.

#### §3.4.3 Lease-fenced semantics

Schwab pipeline steps execute inside the existing pipeline lease (`swing/pipeline/lease.py`). Writes are DB-only (no filesystem CSV like Finviz). Atomicity per step:

- `_step_schwab_snapshot`: SchwabClient call → audit-row INSERT (status='success' OR 'error') → IF success: `record_snapshot()` via service-layer (owns its own BEGIN IMMEDIATE per Phase 9 Sub-bundle C contract). Service-layer's CallerHeldTransactionError contract means `_step_schwab_snapshot` MUST NOT hold an open transaction across the snapshot call — it doesn't, by design.
- `_step_schwab_orders`: SchwabClient calls → audit-row INSERTs → IF success: `run_schwab_reconciliation()` (new service-layer function paralleling `swing/trades/reconciliation.py:run_tos_reconciliation`; owns BEGIN IMMEDIATE; emits `reconciliation_runs` + per-discrepancy rows). Service-layer transactional discipline mirrors Phase 9 Sub-bundle B exactly.

#### §3.4.4 Failure tolerance — continue-with-error (Finviz precedent)

LOCKED default. Schwab step failure:

- Records `schwab_api_calls.status='error'` (or `'auth_failed'` for refresh-token-expired) + error message excerpt.
- Updates `lease.status(schwab_snapshot_status='failed')` (new status field added to lease).
- Does NOT abort the pipeline run; continues to the next step.
- Matches Finviz pattern at `swing/pipeline/runner.py:285-294` exactly.

Operator-facing surfacing: `swing schwab status` reports recent failures; `briefing.md` includes a "Schwab integration: degraded" banner if last call failed (V1 mirrors Phase 10's PROVISIONAL/LIVE badge — under-the-hood the badge resolves "no fresh schwab_api snapshot today" → PROVISIONAL without any new code).

#### §3.4.5 CLI vs pipeline coordination — references §3.2.4

LOCKED design — split-by-surface per §3.2.4 (b). Summary table:

| CLI surface | Concurrent-with-pipeline | Rationale |
|---|---|---|
| `swing schwab fetch --snapshot` | REFUSED (`SchwabPipelineActiveError`) | snapshot UPSERT preserves PK but `source_artifact_path` / `recorded_at` overwritten by last writer; provenance pointer mismatch vs paired audit row (Codex R2 Major-3) |
| `swing schwab fetch --orders` | REFUSED (`SchwabPipelineActiveError`) | reconciliation_runs INSERT-only; duplicates pollute |
| `swing schwab fetch --all` | REFUSED (`SchwabPipelineActiveError`) | includes both `--snapshot` and `--orders` |
| `swing schwab status` | SAFE | read-only |
| `swing schwab refresh` | SAFE | file-lock on sidecar |
| `swing schwab logout` | REFUSED unless `--force` | pipeline mid-fetch would 401 mid-step |
| `swing schwab setup` | REFUSED unless `--force` | rewrites sidecar from scratch |

### §3.5 CLI surface — `swing schwab {setup, refresh, fetch, status, logout}`

LOCKED default subcommand set:

| Subcommand | Purpose | Touches |
|---|---|---|
| `swing schwab setup` | First-time OAuth flow (§3.2.1) | `schwab-state.{env}.json` (create) |
| `swing schwab refresh` | Force token refresh; manual recovery path | `schwab-state.{env}.json` (update) |
| `swing schwab fetch [--snapshot \| --orders \| --all]` | Operator-triggered fetch; default `--all` | `schwab_api_calls`, `account_equity_snapshots`, `reconciliation_runs`, `reconciliation_discrepancies` |
| `swing schwab status` | Token-state + last-call summary | read-only |
| `swing schwab logout` | Revocation + sidecar delete (§3.2.5) | `schwab-state.{env}.json` (delete) |

**Output of `swing schwab status`** (proposed shape — verify operator-facing wording in writing-plans):

```
Schwab integration: LIVE (production)
  client_id:        AB***XY (masked)
  account_hash:     1A2***9F (masked; primary)
  access_token:     valid for 27m 14s
  refresh_token:    valid (last_refresh: 2026-05-13 09:15 UTC)
  last successful call: GET /trader/v1/accounts/{hash} at 2026-05-13 09:15 UTC
  recent errors:    0 in last 24h, 1 in last 7d (see swing schwab fetch --verbose)
  snapshots written: 14 in last 30 days
  reconciliation_runs (schwab_api): 12 in last 30 days; 3 unresolved material discrepancies
```

Token + secret values are MASKED at display time (`AB***XY`); sentinel-leak audit test (§5) covers this surface.

### §3.6 Audit trail + observability — new `schwab_api_calls` table

LOCKED column-shape sketch (schema DDL deferred to writing-plans):

| Column | Type | Purpose |
|---|---|---|
| `call_id` | INTEGER PK autoincrement | surrogate |
| `ts` | TEXT NOT NULL | ISO datetime ms-precision; call invocation timestamp |
| `endpoint` | TEXT NOT NULL | logical endpoint name (e.g., `accounts.get`, `accounts.orders.list`, `oauth.refresh`, `marketdata.quotes`, `marketdata.pricehistory`); NOT the raw URL (would leak account_hash) |
| `http_status` | INTEGER nullable | HTTP response status code; NULL on network failure |
| `response_time_ms` | INTEGER nullable | round-trip ms |
| `rate_limit_remaining` | INTEGER nullable | best-effort from response header |
| `signature_hash` | TEXT nullable | SHA-256 of canonicalized response shape (Finviz pattern — column-set + first-row fingerprint, NOT body bytes; drift detection) |
| `status` | TEXT NOT NULL | `in_progress`, `success`, `error`, `auth_failed`, `rate_limited`, `concurrent_refresh` |
| `error_message` | TEXT nullable | short excerpt; NEVER includes token, refresh_token, client_secret, account_hash |
| `linked_snapshot_id` | INTEGER nullable | FK candidate → `account_equity_snapshots(snapshot_id)` (FK rule deferred to writing-plans); UPDATEd post-domain-write per §3.6.1 |
| `linked_reconciliation_run_id` | INTEGER nullable | FK candidate → `reconciliation_runs(run_id)`; UPDATEd post-domain-write |
| `pipeline_run_id` | INTEGER nullable | FK candidate → `pipeline_runs(run_id)` — NULL when call originates from CLI / web-page render |
| `surface` | TEXT NOT NULL | `pipeline`, `cli` — clarifies where the call originated. V2 reserved value `web_page_render` (NOT used by V1 INSERT path per §3.6.2; the column type accommodates the V2 value without schema bump). |
| `environment` | TEXT NOT NULL | `sandbox` or `production` |

#### §3.6.1 Audit-row insert/update lifecycle — handles in-flight + partial-failure

LOCKED sequence per round-1 Codex Major-finding #8:

1. **Pre-call** (before HTTP request): INSERT audit row with `status='in_progress'`, `linked_*_id=NULL`, all known metadata populated (`ts`, `endpoint`, `pipeline_run_id`, `surface`, `environment`).
2. **HTTP request** issued; response received OR exception raised.
3. **On HTTP-level outcome**: UPDATE the audit row's `http_status`, `response_time_ms`, `rate_limit_remaining`, `signature_hash`, and `status` ∈ `{success, error, auth_failed, rate_limited, concurrent_refresh}`. After this UPDATE, the audit row's HTTP-layer state is final.
4. **On success path that triggers a domain write** (snapshot or reconciliation_run): the domain-write service is invoked; service writes its row; CALLER then UPDATEs the audit row's `linked_snapshot_id` (or `linked_reconciliation_run_id`) with the new row's PK.
5. **On domain-write failure** (rare; would be a programming error since domain-write services have their own try/except): the audit row is UPDATEd to `status='error'` with `error_message` describing the post-HTTP failure; `linked_*_id` remains NULL. The audit row records "HTTP succeeded; domain write failed."

**Recovery from in-flight rows on next pipeline run:** a row stuck at `status='in_progress'` means the process crashed between steps 1 and 3. `swing schwab status` reports these as "stuck in-progress" entries; pipeline `_step_schwab_*` ignores them (defensive — never time-out-and-retry via DB state; HTTP layer is the authoritative ground truth at the time of the next call).

**Coverage requirement (§9 watch-item 11) — NARROWED per Codex R2 Major-1:** EVERY pipeline-surface + CLI-surface API call writes an audit row, including OAuth token-exchange + token-refresh originating from those surfaces. Auth calls have NULL `linked_*_id` permanently. This is the audit-trail completeness contract for the auditable units of behavior in V1: **pipeline-run + CLI-invocation**. Web-page-render cache-fill API calls are an EXPLICITLY-UNAUDITED V1 surface — see §3.6.2 below.

#### §3.6.2 Audit-write surface boundary — pipeline + CLI synchronous; web-page-render EXPLICITLY-UNAUDITED V1

LOCKED per Codex R1 Major-2/3 + R2 Major-1/2.

V1 INCLUDE branch wires Schwab market-data into `PriceCache` + `OhlcvCache`; those caches are read from web-page render paths (dashboard, watchlist, trade-detail, chart) — potentially many cache-miss reads per page load × N tickers. If every cache miss triggered a synchronous `schwab_api_calls` DB write under a SQLite executor thread, two problems arise: (a) audit-row cardinality explodes (many rows per operator page load); (b) SQLite write lock contention against the pipeline writer + web-form-POST writers harms responsiveness.

**Policy:**

- **`pipeline` surface calls** (`_step_schwab_snapshot`, `_step_schwab_orders`, and cache-misses originating from `_step_evaluate`/`_step_charts`): SYNCHRONOUS audit write per §3.6.1. These are bounded per pipeline run (see §4.1 cardinality).
- **`cli` surface calls** (`swing schwab fetch`, `swing schwab refresh`, `swing schwab setup`, `swing schwab logout`): SYNCHRONOUS audit write. Bounded per CLI invocation.
- **`web_page_render` surface calls** (any cache miss in `PriceCache`/`OhlcvCache` arising from an HTTP request handler — dashboard, charts, etc.): **NO `schwab_api_calls` rows written.** Cache miss falls through to the underlying source (Schwab API → yfinance fallback) but the call is NOT persisted to the audit table. V1 acceptance: this surface is EXPLICITLY-UNAUDITED. Refresh failures or rate-limit responses on this path are surfaced via in-process WARNING-level logs only; web-process console / log file is the operator-visible artifact.
  - **NO cross-process CLI surfacing.** Earlier draft proposed surfacing web-render counters via `swing schwab status`; that is not implementable — the CLI process cannot read the FastAPI web process's in-memory state. The CLI's `swing schwab status` reports pipeline + CLI audit rows only.
  - **V2 candidates** (deferred — operator triages if web-render audit observability becomes operationally important):
    - (a) Batched-summary writer thread in the web process flushes one summary `schwab_api_calls` row per (date, surface, endpoint) tuple every 30-60s.
    - (b) Web-process exposes a debug endpoint `/admin/schwab-counters` returning a JSON snapshot of in-memory counters; CLI fetches via HTTP.

### §3.6.3 Production-only domain writes — sandbox is VERIFICATION-ONLY

LOCKED per Codex R3 Critical-1. Without this gate, sandbox-environment responses (synthetic Schwab data; NLV figures unrelated to operator's real account; possibly fake order/transaction rows) would land in `account_equity_snapshots`/`reconciliation_runs`/`reconciliation_discrepancies` AND win the source-ladder (Schwab beats manual/TOS in `_SOURCE_PRECEDENCE`) — silently contaminating production metrics (Phase 10 LIVE-badge equity), reconciliation discrepancies, and any downstream cohort analysis.

**Binding contract:**

- The active environment is read at every Schwab entry point from `cfg.integrations.schwab.environment` (see Major-1 below + §10 Q8) plus optional per-invocation override `--environment`.
- IF active environment == `production`: pipeline `_step_schwab_snapshot` + `_step_schwab_orders` perform domain writes via `record_snapshot()` + `run_schwab_reconciliation()` as designed in §3.7.
- IF active environment == `sandbox`: domain-write services ARE NOT CALLED. The Schwab steps still issue the API calls + record `schwab_api_calls` rows + capture `signature_hash` for drift detection + record HTTP outcomes. **Output is verification-only**: operator sees that the integration is wired correctly + can `sqlite3` query the audit table to read sandbox response signatures, but ZERO domain rows arise.
- Market-data ladder (V1 INCLUDE): IF `environment='sandbox'`, the cache-fill Schwab path is SHORT-CIRCUITED in normal operation — `PriceCache` / `OhlcvCache` callers fall through directly to yfinance. Sandbox quotes/pricehistory are NOT cached anywhere when fetched implicitly via cache miss. **However**, to enable Task 0.b cassette recording for `/quotes` and `/pricehistory` while operator's production-tier app approval is still pending, the spec defines an explicit audit-only verification path (per Codex R4 Major-1):
  - `swing schwab fetch --verify-marketdata [--symbols SYM1,SYM2,...]` (default symbols `AAPL`) issues `/quotes` AND `/pricehistory` calls against the supplied tickers under the active environment.
  - Audit rows are written (with `signature_hash`) for cassette recording + drift-detection.
  - Cache writes are SKIPPED regardless of environment (this flag is verification-only by design; under `production` env it also bypasses cache for the same reason — operator runs it intentionally to confirm endpoint shape, not to warm the cache).
  - This is a CLI-only path; pipeline never invokes the verification mode.
- CLI: `swing schwab fetch --snapshot` and `--orders` and `--all` MIRROR pipeline semantics — under sandbox env, audit row is written, domain write is SKIPPED. `swing schwab status` reports per-environment counts ("sandbox audit calls today: N; production: M").
- Promotion path: when operator's Schwab app receives production-tier approval (per §10 Q1), operator runs `swing schwab setup` again (different `environment` value); sandbox sidecar file is preserved; operator updates `cfg.integrations.schwab.environment = "production"` in user-config.toml to flip the active env; first production pipeline run starts producing real domain writes.

**Test discipline (writing-plans firms up):** discriminating fast test asserts that `_step_schwab_snapshot` invoked under `environment='sandbox'` writes a `schwab_api_calls` row but does NOT touch `account_equity_snapshots`. Discriminating fast test for `_step_schwab_orders` symmetric. Discriminating fast test for cache fill — `PriceCache.get_latest(ticker)` under sandbox returns the yfinance entry, not a Schwab entry, even if Schwab tokens are valid.

### §3.7 Source-ladder write path — INHERITED, NOT RE-DESIGNED

Per §1.3 #1 + brief §1.1: this spec explicitly disclaims re-design of source-ladder semantics. The Schwab API equity-snapshot write path is exactly:

```
record_snapshot(
    conn,
    equity_dollars=<NLV_from_API>,
    snapshot_date=<last_completed_session(now)>,
    source='schwab_api',
    source_artifact_path=f"schwab_api:call/{call_id}",
    recorded_by='schwab_api',
    notes=None,
)
```

UPSERT semantics already exist at `swing/data/repos/account_equity_snapshots.py:81` (SELECT-then-UPDATE-or-INSERT keyed on `(snapshot_date, source)`). Read-side resolution already exists at `get_latest_snapshot_on_or_before(with_provenance=True)`. The Phase 10 capital-friction PROVISIONAL/LIVE badge already consumes the resolved view transparently. **No new code in the source-ladder layer.**

Reconciliation write path:

```
run_schwab_reconciliation(
    conn,
    account_hash=<primary>,
    period_start=<last_completed_session(now) - lookback_days>,
    period_end=<last_completed_session(now)>,
    schwab_orders_response=<JSON>,
    schwab_transactions_response=<JSON>,
    schwab_account_response=<JSON>,
    pipeline_run_id=<int>,
)
```

This is a NEW service-layer function paralleling `swing/trades/reconciliation.py:run_tos_reconciliation`. It owns BEGIN IMMEDIATE; rejects caller-held tx. The discrepancy emitter logic mirrors Phase 9 Sub-bundle B exactly — same `MATERIAL_BY_TYPE` lookup, same `RESOLUTION_TYPES`, same `MATERIAL_BY_TYPE` keys (10 enum values — Schwab data covers `close_price_mismatch`, `entry_price_mismatch`, `stop_mismatch`, `position_qty_mismatch`, `cash_movement_mismatch`, `equity_delta`, and `unmatched_open_fill` / `unmatched_close_fill`; `sector_tamper` + `snapshot_mismatch` are not Schwab-emitted).

**Source-artifact reference shape (§9 watch-item 12 lock):** `source_artifact_path = "schwab_api:call/{call_id}"` URI-style opaque reference back to the audit row. NOT the response URL (would include `account_hash` path segment + leak). Reconciliation_run rows use the same shape.

### §3.8 Market-data source-ladder — V1 INCLUDE branch (per §10 Q11 default)

#### §3.8.1 Current cache architecture (HONEST baseline — these surfaces don't have multi-source semantics today)

Before writing-plans owns the rewrite, the spec must NOT pretend `PriceCache`/`OhlcvCache` already have ladder shape. They don't. Current state:

- **`PriceCache`** at `swing/web/price_cache.py` — in-memory TTL cache; entries carry a `source` field but its values are TTL-state markers (`live` / `last_close` / `last_close_market_closed`), NOT provider provenance. Backed by yfinance only via a single fetcher path.
- **`OhlcvCache`** at `swing/data/ohlcv_cache.py` — in-memory windowed cache + sliding-window breaker. Backed by `swing/data/ohlcv_archive.py` for persistence.
- **`swing/data/ohlcv_archive.py`** — persistent OHLCV archive; writes ONE `{TICKER}.parquet` file per ticker (single-source-implicit-yfinance); append-or-fall-back pattern per CLAUDE.md gotcha (transient empty does NOT clobber).

**Implication:** there is no "tag the existing rows with `source` + use the existing resolver" path. Writing-plans must design a NEW resolver boundary + a NEW persistence shape for at least one of the two caches (the in-memory `PriceCache` is in-memory-only so a `source` dimension is a dataclass-field addition; the on-disk `OhlcvCache` persistence at parquet-per-ticker is single-source-implicit).

#### §3.8.2 V1 INCLUDE design surface — what writing-plans owns

LOCKED scope-of-rewrite for the market-data ladder (DDL deferred to writing-plans):

- **New precedence map** — define `_SOURCE_PRECEDENCE_MARKET_DATA: dict[str, int] = {"schwab_api": 0, "yfinance": 1}` in a shared module so both caches consult the same constant. Mirrors `_SOURCE_PRECEDENCE` at `swing/data/repos/account_equity_snapshots.py:38` shape (lower-integer wins).
- **PriceCache refactor (in-memory; smaller scope)**:
  - `PriceCacheEntry` dataclass gains a `provider` field (values `schwab_api` | `yfinance`) DISTINCT from the existing `source` TTL-state field. NO renaming of the existing field (gotcha hazard: existing test fixtures depend on it).
  - Fetcher path becomes "try Schwab → on failure fall back to yfinance"; per-call cache row tagged with `provider`.
  - Read-side `get_latest(ticker)` returns the most-recently-fetched entry regardless of provider (in-memory cache has no cross-provider coexistence problem — last fetch wins). Provenance available via the new `provider` field.
- **OhlcvCache + persistence refactor (parquet-per-ticker today; bigger scope)**:
  - Writing-plans picks ONE of three shapes:
    - **A. Parquet-per-(ticker, provider)** — `{TICKER}.{PROVIDER}.parquet`; resolver fetches both, picks higher-precedence per `(ticker, asof_date)` row at read time. Simplest extension of current shape; no new SQL.
    - **B. Single SQLite-backed persistent OHLCV table** — `ohlcv_cache_persistent (ticker, asof_date, provider, open, high, low, close, volume, fetched_at)` with UNIQUE INDEX on `(ticker, asof_date, provider)`. Mirrors `ux_account_equity_snapshots_date_source`. Most consistent with Phase 9 source-ladder pattern; requires migration work.
    - **C. Keep parquet single-file + provider-tag column inside the parquet schema** — adds a `provider` column to each parquet row; archive helper merges Schwab + yfinance pulls into the per-ticker file. Lower migration cost than B; higher complexity in archive helper.
  - **Default recommendation** for writing-plans Task 0 design: **A. Parquet-per-(ticker, provider)** — cleanest separation; resolver code is small; no SQL migration; per-provider cache directories are operator-greppable.
- **Read-side resolver** (whatever persistence shape): function `resolve_ohlcv_window(ticker, start, end)` returns merged window with `provider` per-row; caller can request `with_provenance=True` to surface "Schwab had X bars; yfinance filled Y bars" for UI.

#### §3.8.3 V1 INCLUDE design — what V1 ladder semantics specifically lock

- `PriceCache.get_latest(ticker)` and `OhlcvCache.get_window(ticker, start, end)`:
  - Try Schwab API path first (if Schwab tokens valid + cached entry fresh OR refreshable).
  - On Schwab failure / empty-response / rate-limited: fall back to yfinance (existing path; unchanged from today).
  - Cache entry tagged with `provider` (schwab_api or yfinance).
  - Read-side resolution: when both providers have entries for the same `(ticker, asof_date)`, return the Schwab entry. Resolution at in-memory level for `PriceCache`; at parquet-merge or SQL-ORDER-BY for `OhlcvCache` depending on writing-plans persistence choice.

#### §3.8.4 yfinance fallback discipline — preserves existing CLAUDE.md gotcha-hardened code path

V1 EXCLUDE the temptation to delete the yfinance code path. yfinance stays as the secondary tier. This means:

- All existing yfinance gotchas remain relevant + the existing defensive guards stay in place (yfinance `threads=False`; `Ticker.history()` no-`threads`-kwarg; `group_by='column'` MultiIndex squeeze; `history(interval='1d')` partial-bar strip; empty-result transient-handling).
- Schwab path runs UNDER the same `with _suppress_transport_debug_logs()` boundaries that yfinance does NOT need (different log surface; Schwab tokens are header-based not query-string-based, but the discipline applies to any HTTP path that might log a token-bearing URL via requests internals — see §5).
- yfinance-only callsites that don't go through `PriceCache`/`OhlcvCache` (rare; spot-check at writing-plans-time) are NOT migrated V1.

#### §3.8.5 Pipeline integration — fetched on-demand inside `_step_evaluate` + `_step_charts`

NOT a separate `_step_schwab_marketdata`. Rationale:
- yfinance is already fetched inside `_step_evaluate` (price + OHLCV for evaluation criteria) and `_step_charts` (OHLCV for chart rendering).
- Wrapping the existing fetch boundary in a ladder-aware fetcher (try Schwab → fall back to yfinance) is a localized change.
- No new pipeline step → no new ordering question → no new lease-status field.

#### §3.8.6 Empty-response handling — append-or-fall-back per CLAUDE.md gotcha

Per CLAUDE.md gotcha "External-API empty-result must be treated as transient when write-through-caching":

- Schwab `GET /marketdata/v1/{symbol}/pricehistory` returning empty data array → DOES NOT clobber the OHLCV archive entry for that ticker. Records `schwab_api_calls.status='error'`; falls back to yfinance.
- Schwab `GET /marketdata/v1/quotes` returning partial response (some tickers OK + some errored) → process the OK tickers; mark the errored tickers for yfinance fallback; record one `schwab_api_calls` row with per-ticker breakdown in `error_message` excerpt (still under the no-token-leak contract).
- yfinance fallback inherits its existing empty-result-transient-handling (already correct).

#### §3.8.7 Schema + persistence impact (deferred to writing-plans)

Writing-plans firms up per §3.8.2:
- **`PriceCache`** — pure dataclass `provider` field addition; no schema work; no SQL.
- **`OhlcvCache` persistence** — writing-plans picks shape A / B / C per §3.8.2; default recommendation A (parquet-per-(ticker, provider)). If shape B (SQLite-backed) chosen → migration introduces `ohlcv_cache_persistent` table; `EXPECTED_SCHEMA_VERSION` bump accounts for it.

**V1 EXCLUDE branch (operator overrides §10 Q11):** §3.8 collapses to a single line: "yfinance remains the sole market-data source for V1; Schwab Market Data API ladder is deferred to a follow-on dispatch with separate brainstorm + writing-plans + executing-plans cycle." §3.3.2 Market Data API endpoint catalog rows become V2 candidates. §4.4 schema candidates become V2. The Schwab arc closes faster.

---

## §4 Schema candidates (DEFERRED to writing-plans; this spec sketches shapes only)

Per §3 of dispatch brief — NO `CREATE TABLE` SQL, NO FK cascade rules, NO CHECK constraints, NO indexes here. Writing-plans owns DDL.

### §4.1 New table candidate: `schwab_api_calls`

See §3.6 above for column-shape sketch (14 columns including `surface`). Cardinality estimate (after §3.6.2 audit-write boundary lock — web_page_render NOT recorded as DB rows; counter-only):

- **Pipeline surface:** 2 auth-related rows (refresh + accounts.get) + 2 domain rows (snapshot + orders) + 2-6 market-data rows (V1 INCLUDE: evaluate-time + charts-time cache fills; **assumes batched calls — `GET /marketdata/v1/quotes` accepts a comma-separated `symbols=` param for many tickers in one call per Codex R2 Minor-3; `GET /pricehistory` is per-ticker but only invoked on cache miss + cache window is multi-bar so daily hit-rate after first run is high**) = ~6-12 rows per pipeline run × ~250 sessions/year = ~1,500-3,000 rows/year.
- **CLI surface:** operator-frequency-dependent; estimate 1-5 invocations/week × ~3 rows/invocation = ~150-800 rows/year.
- **Setup surface:** 3-5 rows per `swing schwab setup` flow; rare.

**Revised V1 cardinality: ~2,000-4,000 rows/year** (assuming `/quotes` batching is implemented per writing-plans). If writing-plans elects per-ticker `/quotes` calls instead of batched, multiply pipeline-surface estimate by ~5-10× → ~10,000-30,000 rows/year. Still NOT high-cardinality at SQLite scale. Default indexes on `(ts)`, `(status, ts)`, `(pipeline_run_id, ts)` suffice. **V1 retention policy: KEEP ALL** (operator can query historical drift via `signature_hash` series; storage cost is trivial). Writing-plans considers `(surface, ts)` index for `swing schwab status` per-surface summaries.

**Operator can query the audit table directly** via `sqlite3` against the production DB for any longer-tail forensic questions; V1 does NOT need a structured retention/pruning policy. V2 candidate: if `signature_hash` series row count crosses some operator-visible threshold (e.g., 50,000 rows), add a `swing schwab audit prune --keep-days=N` CLI subcommand.

### §4.2 No new table for OAuth state — sidecar JSON file (§3.2.2)

LOCKED: OAuth state lives in `schwab-state.{env}.json`, NOT a `schwab_oauth_state` table. Rationale: frequently-rewritten + single-row + atomic-write semantics are filesystem-natural, NOT SQLite-natural. The audit trail of token refreshes lives in `schwab_api_calls` rows with `endpoint='oauth.refresh'`.

Alternative considered: `schwab_oauth_state` table for refresh durability across operator's filesystem reset. Rejected V1 — operator-actionable recovery is `swing schwab setup`. Operator backup of `schwab-state.{env}.json` is a footnote in §7 operator setup flow.

### §4.3 ALTER candidates on existing tables (DEFERRED)

V1 candidates the writing-plans dispatch firms up:

- **`account_equity_snapshots.schwab_account_hash`** TEXT nullable — populated only for `source='schwab_api'` rows; NULL for `source IN ('manual','tos_csv')`. Forward-prepares for multi-account V2 (§10 Q3). V1 single-account: column populated with single primary account_hash. Writing-plans decides whether V1 introduces this column or defers to V2 multi-account dispatch.
- **`reconciliation_runs.schwab_api_call_id`** INTEGER nullable, FK candidate → `schwab_api_calls(call_id)` — provides provenance chase from a reconciliation_run back to the audit row(s) that emitted it. Currently `reconciliation_runs.source_artifact_path` carries the `"schwab_api:call/{call_id}"` URI string; the FK column is a normalized alternative. Writing-plans decides URI-only vs URI+FK.

### §4.4 Market-data ladder schema candidates (V1 INCLUDE branch only)

Per §3.8.2: writing-plans picks one of three persistence shapes (A/B/C). Schema impact per shape:

- **Shape A (parquet-per-(ticker, provider))** — DEFAULT. NO new SQL table. NO schema migration. Filesystem-level layout change in `swing/data/ohlcv_archive.py`. `EXPECTED_SCHEMA_VERSION` may stay at 18 (or 17 if writing-plans avoids `schwab_api_calls` introduction — see §4.5).
- **Shape B (SQLite-backed `ohlcv_cache_persistent` table)** — `(ohlcv_id, ticker, asof_date, provider, open, high, low, close, volume, fetched_at)` + UNIQUE INDEX on `(ticker, asof_date, provider)` (mirrors `ux_account_equity_snapshots_date_source`). `provider` CHECK enum `IN ('schwab_api', 'yfinance')`. Schema bump candidate.
- **Shape C (parquet-per-ticker + provider column inside parquet)** — NO new SQL table. Parquet schema includes provider; archive helper merges.

`PriceCache` is in-memory only; no schema work regardless of shape choice.

### §4.5 Schema version bump

`EXPECTED_SCHEMA_VERSION` candidates bump 17 → 18 IF writing-plans elects to introduce `schwab_api_calls` table + any ALTER columns above. If V1 keeps the audit table out of SQL (e.g., logs-only — rejected here for queryability), schema may stay at 17. **Default: bump to 18 — `schwab_api_calls` is mandatory for §3.6 audit-trail completeness.**

---

## §5 Token redaction discipline — INHERITED VERBATIM from Finviz precedent

Per brief §5 watch-item 2 + §2.7: this spec **explicitly inherits** the Finviz token-redaction layered discipline. NOT silently re-inventing.

Layered redaction guards (verbatim from `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` §F + Finviz commit `002338a`):

1. **Exception `__str__` contracts.** Every Schwab exception class MUST follow the `FinvizApiError.__str__` pattern at `swing/integrations/finviz_api.py:66-78`: `__str__` includes status code + body length, NEVER the request URL, NEVER the response body verbatim, NEVER access_token / refresh_token / client_secret / account_hash bytes. Exception type names: `SchwabConfigMissingError`, `SchwabApiError`, `SchwabRateLimitError`, `SchwabAuthError`, `SchwabRefreshTokenExpiredError`, `SchwabSchemaParityError`, `SchwabConcurrentRefreshError`.
2. **urllib3 DEBUG-log suppression context manager.** Mirror `_suppress_transport_debug_logs()` at `swing/integrations/finviz_api.py:46-59` — force `urllib3.connectionpool` + `requests.packages.urllib3.connectionpool` loggers to WARNING level for the duration of every HTTP call. Required because `requests` internals can log `Sending request: <URL>` at DEBUG, and even though Schwab uses header-auth (NOT query-param auth like Finviz), the URL contains the `account_hash` path segment which is sensitive (Schwab's encrypted-account-identifier is operator-identifying). Same discipline applies to OAuth POST URLs that carry the authorization code mid-flow.
3. **Cassette filter discipline.** All Schwab cassettes (under `tests/integrations/cassettes/` mirroring Finviz layout):
   - `filter_headers=['authorization']` — strip the Bearer token header from recorded responses.
   - `filter_query_parameters=['code', 'refresh_token', 'client_id', 'client_secret', 'redirect_uri', 'access_token']` — strip every sensitive query param the OAuth flow / Trader API / Market Data API can carry. Loopback redirect_uri values may also embed operator-environment details (port, hostname); filter defensively.
   - `filter_post_data_parameters=['code', 'refresh_token', 'client_id', 'client_secret']` — POST `/oauth/token` body fields; filtered separately from query params.
   - Custom response-body redactor that masks `access_token`, `refresh_token`, `client_secret`, `client_id`, and `accountNumber` / `accountHash` substrings in any recorded response JSON. (Per Schwab response shape — POST `/oauth/token` body literally contains the tokens; account-list endpoint returns plaintext account numbers paired with account hashes.)
4. **Sentinel-token-leak audit test.** `tests/integrations/test_schwab_token_redaction_audit.py` — end-to-end fetch with a known-sentinel value injected as the token; greps all log records + all DB rows (`schwab_api_calls.error_message`, `pipeline_runs.error_message`, `reconciliation_runs.error_message`, ALL `notes` fields) for the sentinel; asserts ZERO matches. Mirror Finviz precedent at `tests/integrations/test_finviz_token_redaction_audit.py`.
5. **`swing config show` masking.** Schwab fields are in `schwab-state.{env}.json`, NOT in user-config.toml. `swing config show` (which reads user-config.toml fields via the FIELD_REGISTRY) does NOT need an extension for Schwab V1 — Schwab tokens are outside the config-show surface by design. V2 hardening: if any `[integrations.schwab]` keys land in user-config.toml (e.g., `environment`, `lookback_days`), they MUST be added to FIELD_REGISTRY with `masked=False` (those are non-sensitive); ZERO Schwab token bytes ever enter user-config.toml.
6. **`swing schwab status` masking.** Per §3.5 output sketch — `client_id` shown masked (`AB***XY`); `account_hash` shown masked; `access_token` shown as time-remaining only; `refresh_token` shown as validity only. Sentinel-audit covers this surface.

---

## §6 Failure-mode catalog

Per HTTP status × endpoint, what happens. V1 mirrors Finviz §A.4 "single retry on 429" + "continue-with-error" discipline.

| HTTP status | Endpoint class | Action |
|---|---|---|
| 200 | any | Process response; INSERT `schwab_api_calls(status='success')`; proceed. |
| 400 invalid_grant | `/v1/oauth/token` | Raise `SchwabAuthError`; pipeline step records `status='auth_failed'`; CLI emits "run `swing schwab setup` to re-auth"; continues. |
| 401 invalid_client | `/v1/oauth/token` | Raise `SchwabAuthError`; pipeline step records `status='auth_failed'`; same as above. |
| 401 expired access_token | any Trader/MarketData | Auto-refresh via `auth.py`; retry call ONCE; if still 401, raise + `status='auth_failed'`. |
| 401 refresh_token expired | `/v1/oauth/token` (refresh) | Raise `SchwabRefreshTokenExpiredError`; CLI emits operator-actionable message; pipeline step records `status='auth_failed'`; continues. |
| 403 insufficient_scope | any | Raise `SchwabApiError`; CLI advises operator to re-run `swing schwab setup` with updated scope. |
| 404 invalid account_hash | Trader API | Raise `SchwabApiError`; CLI advises operator to verify `account_hash` via `swing schwab status`. |
| 429 rate_limited | any | Parse `Retry-After` header; if 0 < retry_after <= 30s: sleep + retry once; on second 429: raise `SchwabRateLimitError` + `status='rate_limited'`. Mirror Finviz `_RETRY_AFTER_MAX_SECONDS = 30`. |
| 5xx server error | any | Raise `SchwabApiError`; `status='error'`; no retry V1 (matches Finviz). |
| Network failure (requests.RequestException) | any | Raise `SchwabApiError(0, "")` (mirror Finviz pattern at `swing/integrations/finviz_api.py:137-140`); `status='error'`. |
| Empty `data` in `/pricehistory` response (V1 INCLUDE) | Market Data | DO NOT clobber OHLCV archive (CLAUDE.md gotcha); fall back to yfinance; `status='error'`. |
| Partial response in `/quotes` (V1 INCLUDE) | Market Data | Process OK tickers; record errored tickers in `error_message` excerpt; partial success → `status='success'` with caveat. |

---

## §7 Operator setup flow + cycle-checklist update

### §7.1 One-time setup (operator-actionable)

1. **Schwab Developer Portal:**
   - Operator already has Schwab brokerage account (per §1.3 — flagged §10 Q1 for production-tier-approval status).
   - Operator registers a new Developer App at https://developer.schwab.com/ — picks a name (e.g., "Swing Trading Personal"); requests Trader API + Market Data API access scopes.
   - Operator notes `client_id` + `client_secret` from the app's credentials page.
   - Operator configures app's `Callback URL` to `https://127.0.0.1:8765/callback` (matches §3.2.1 default; alternative ports / out-of-band options per §10 Q13).
   - Operator awaits app-approval (Schwab review process; can take days-to-weeks for production tier; sandbox is immediate).

2. **First-run setup — sandbox (recommended initial path per §10 Q1):**
   ```
   swing schwab setup --environment sandbox
   # → prompts for client_id, client_secret, callback_url, environment (default: sandbox)
   # → opens browser to Schwab consent screen
   # → operator logs in + approves
   # → CLI persists schwab-state.sandbox.json
   # → CLI emits "Setup complete. Sidecar written. Active cfg env is still 'production' (default).
   #              To activate sandbox: 'swing config set integrations.schwab.environment sandbox'
   #              Then verify with 'swing schwab status'."
   ```

3. **Activate sandbox + verify (sandbox-mode produces audit rows but ZERO domain writes per §3.6.3):**
   ```
   swing config set integrations.schwab.environment sandbox
   swing schwab status            # confirm sandbox env active + sandbox sidecar valid
   swing schwab fetch --snapshot  # audit row written; account_equity_snapshots UNCHANGED
   swing schwab fetch --verify-marketdata --symbols AAPL  # if V1 INCLUDE — exercise /quotes + /pricehistory under sandbox; cache unchanged
   ```

4. **Once Schwab production-tier approval lands — repeat for production:**
   ```
   swing schwab setup --environment production
   # → operator pastes production client_id + client_secret
   # → CLI persists schwab-state.production.json (sandbox sidecar preserved)
   swing config set integrations.schwab.environment production
   swing schwab status            # confirm production env active
   swing schwab fetch --snapshot  # NOW writes a real account_equity_snapshots row
   ```

### §7.2 Daily cycle

- Pipeline auto-fetches at scheduled cadence (no operator action).
- `briefing.md` includes Schwab snapshot value + reconciliation discrepancy summary (rendered automatically once steps are wired).
- Operator visits `/metrics/capital-friction` — LIVE badge (not PROVISIONAL).
- If Schwab call failed: `briefing.md` includes "Schwab integration: degraded" banner; operator runs `swing schwab status` to diagnose.

### §7.3 Token-refresh-failure recovery

- Refresh-token expiry (Schwab default 7d / 90d depending on tier): operator runs `swing schwab refresh` (manual). If refresh succeeds: state restored. If refresh fails (refresh_token revoked or expired): operator runs `swing schwab setup` to re-auth from scratch.
- Sidecar file corruption / deletion: operator runs `swing schwab setup` to re-bootstrap.

### §7.4 `docs/cycle-checklist.md` updates needed (writing-plans implements)

- Add "Daily — verify `briefing.md` Schwab section" step (optional; operator-judgment).
- Add "Weekly — verify Schwab refresh_token validity via `swing schwab status`" step (mitigates 7d-tier refresh expiry on idle weeks).
- Add "After Schwab Developer Portal app re-approval / scope change — run `swing schwab logout` then `swing schwab setup`" emergency-recovery step.

---

## §8 Capture-needs feedback to existing phases

Per brief §7 return-report format. None of these are V1 blocking — informational for downstream-phase orchestrator triage.

### §8.1 Phase 6 (Review)
**None.** Phase 6 surfaces are operator-judgment only.

### §8.2 Phase 7 (Trade lifecycle state machine)
**None.** Phase 7 is internal to project's trade lifecycle; Schwab data flows through Phase 9 reconciliation surface, not directly into Phase 7 state transitions.

### §8.3 Phase 8 (Daily management)
**None.** Phase 8 is manual operator capture; Schwab API does not write daily_management_records.

### §8.4 Phase 9 (Risk policy + reconciliation)
**None.** Phase 9 explicitly designed for Schwab API as a V2-pluggable `source` value. Schwab integration consumes the surface as-shipped:
- `reconciliation_runs.source='schwab_api'` — CHECK enum already permits.
- `reconciliation_discrepancies` — 10 discrepancy types + 5 resolution types already cover Schwab cases (no new types V1 per §1.2 + §3.7).
- Phase 9 Sub-bundle C account_equity_snapshots write path consumed verbatim.
- Phase 9 Sub-bundle E E2E happy-path test pattern at `tests/integration/test_phase9_full_happy_path.py` is the model for Schwab E2E tests (writing-plans incorporates).

### §8.5 Phase 10 (Metrics dashboard)
**None.** Phase 10 surfaces consume source-ladder transparently via `get_latest_snapshot_on_or_before` (Sub-bundle D capital-friction LIVE badge; Sub-bundle E reconciliation-discrepancy banner). Schwab integration closes the LIVE-badge stickiness gap WITHOUT touching any metrics-surface code.

### §8.6 Writing-plans dispatch (for the Schwab arc itself)

Writing-plans needs to firm up:

1. **§4.3 ALTER `schwab_account_hash` on `account_equity_snapshots`** — V1 add OR defer to V2 multi-account dispatch.
2. **§4.4 market-data persistence shape** — `OhlcvCache` persistent backing add OR keep in-memory.
3. **§3.3.1 endpoint shapes** — Task 0.b operator-paired live verification for every `[VERIFY]`-tagged endpoint; cassette recording.
4. **§3.3.1 scope strings** — confirm Schwab's exact scope-string format (`readonly`? `Trader.Read`? `MarketData.Read`?) at Task 0.b.
5. **§3.5 CLI subcommand-body design** — `setup` flow's HTTPS listener + self-signed cert handling; `status` output format.
6. **§3.4.1 ALTER `schwab_account_hash` on `reconciliation_runs`** — V1 add (with FK to `schwab_api_calls`) OR keep URI-only.
7. **§3.6 `schwab_api_calls` DDL** — column types, CHECK constraints, indexes.
8. **§3.2.4 file-lock implementation** — Windows `msvcrt.locking` + POSIX `fcntl.flock` cross-platform shim.
9. **§3.2.1 callback-URL HTTPS-vs-HTTP** — Schwab may require HTTPS in production but accept HTTP for localhost in sandbox. Verify at Task 0.b.
10. **§7 cycle-checklist updates** — exact wording.
11. **Test fixtures** — sanitized cassettes; sentinel-leak audit fixtures; Task 0.b paired-verification runbook (mirror Finviz §G).
12. **Integration test E2E** — Phase 9 Sub-bundle E `tests/integration/test_phase9_full_happy_path.py` pattern; add Schwab steps to a parallel E2E happy-path.

---

## §9 Adversarial-review watch items (binding for Codex rounds)

Per brief §5 — 21 items. Restated here for spec-internal triage tracking. Findings against these watch items go to §10 open questions or fixed inline before commit.

1. Source-ladder is consumed, NOT designed (per §1.3 #1 + §3.7).
2. Token redaction inherited verbatim from Finviz (per §5).
3. OAuth refresh-token rotation handled (per §3.2.3 — `if response carries new refresh_token, update stored value`).
4. Token storage discipline matches Phase 9 Sub-bundle A monkeypatch gotcha (USERPROFILE+HOME) — applies to `schwab-state.{env}.json` tests; writing-plans implements `_user_home()`-equivalent for sidecar path resolution.
5. Multi-account question surfaced (§10 Q3 default V1 single-account).
6. Order placement explicit-disclaim (per §1.2 + §3.3.3 + §10 Q-implicit).
7. Pipeline step ordering justified (per §3.4.2 — AFTER `_step_recommendations`, BEFORE `_step_charts`; rationale enumerated; aligned with §3.4.1 + §10.10).
8. Failure tolerance matches Finviz precedent (continue-with-error per §3.4.4).
9. Sandbox vs production toggle (per §10 Q8 — per-environment sidecar file `schwab-state.{env}.json`; setup default `sandbox` per Codex R1 Major-6; HTTP-layer differentiation pending Task 0.b).
10. Operator setup flow concrete (per §7.1 + §3.2.1 — TWO first-class variants `localhost` (default) + `paste`-VERIFY; enumerates client_id, client_secret, callback_url, scope-string composition; flags scope-string verification at Task 0.b as §10 Q14).
11. Audit trail covers EVERY pipeline + CLI API call including auth + refresh (per §3.6.1 lifecycle + §3.6.2 surface boundary). Web-page-render surface explicitly UNAUDITED V1.
12. `source_artifact_path` shape locked: `"schwab_api:call/{call_id}"` per §3.7 + §2 vocabulary.
13. Cash-basis-vs-NLV semantics: `equity_dollars` column remains V2 ambiguity; resolved at provenance layer (per §1.3 #4).
14. Empty-API-response handling (per §3.4.4 + §3.8.6 + CLAUDE.md gotcha).
15. Multi-account schema impact (per §4.3 ALTER schwab_account_hash flag).
16. JS-test-harness gap awareness: Schwab is CLI-driven; no HTMX form surfaces in V1. NO operator-witnessed gate requirement.
17. CLI vs pipeline concurrency exclusion (per §3.2.4 — file-lock on sidecar for refresh + `SchwabPipelineActiveError` HARD exclusion on `fetch --snapshot`/`--orders`/`--all` + `logout`/`setup` unless `--force`).
18. TOCTOU on token expiry (per §3.2.3 — 60s safety margin justified).
19. Market-data ladder coherence with equity-snapshot ladder (per §3.8.1 + §3.8.2 — current caches do NOT yet have multi-source semantics; new `provider` field + persistence-shape choice A/B/C deferred to writing-plans; same `_SOURCE_PRECEDENCE` integer-lower-wins pattern adopted).
20. Empty-API-response handling for market-data ladder (per §3.8.6 — does NOT clobber yfinance archive).
21. Premium-tier endpoint cost awareness (per §10 Q12 — flagged operator-actionable).

---

## §10 Open questions for orchestrator triage

Each structured as: **question + tradeoff sketch + default recommendation + operator-decision source.**

### §10.1 Q1: Schwab Developer Portal app status

- **Question:** Has operator registered a Schwab Developer App? Has it received production-tier approval? OR is sandbox the V1 target?
- **Tradeoff:** Sandbox unblocks executing-plans Task 0.b immediately (Schwab provides sandbox-tier sandbox keys on app registration; no review delay). Production tier requires Schwab review; can take days-to-weeks; required for real account-data writes against operator's actual brokerage account.
- **Default recommendation:** Operator-actionable — start sandbox (registration today; Task 0.b verifiable in 1-2 days); promote to production when Schwab approves.
- **Decision source:** Operator + Schwab Developer Portal.

### §10.2 Q2: Token storage encryption at rest

- **Question:** Plaintext (Finviz precedent) vs encrypted (Windows DPAPI / cross-platform `keyring`)?
- **Tradeoff:** Plaintext mirrors Finviz; simpler V1; relies on filesystem ACL. Encrypted-at-rest hardens against accidental config-dir backup-to-cloud / shared-filesystem leak; `keyring` adds a dependency + has platform-specific failure modes (Linux requires DBus secrets service; not relevant Windows-only but worth noting).
- **Default recommendation:** V1 plaintext (Finviz precedent + posture). V2 hardening note: `keyring` cross-platform module.
- **Decision source:** Operator threat model.

### §10.3 Q3: Multi-account support

- **Question:** V1 single-primary-account or V1 multi-account?
- **Tradeoff:** Single-account simpler; matches current state; schema does NOT gain `schwab_account_hash` column V1. Multi-account requires schema work + per-account snapshot scoping + Phase 10 metrics per-account-or-aggregated-decision.
- **Default recommendation:** V1 single-primary-account. Operator selects at `swing schwab setup`. Multi-account = V2 separate dispatch.
- **Decision source:** Operator + brokerage account configuration.

### §10.4 Q4: Streaming vs batch-poll

- **Question:** V1 batch-poll only; V1 streaming?
- **Tradeoff:** Streaming would enable intraday tick-level price updates + order-fill push notifications. Adds WebSocket connection management + concurrent state. V1 cadence is daily; streaming has no V1 use case.
- **Default recommendation:** V1 batch-poll. Streaming = V2.
- **Decision source:** Operator.

### §10.5 Q5: Operator-facing UI

- **Question:** CLI-only V1 or web form for token-refresh / account-selection?
- **Tradeoff:** CLI-only matches Finviz precedent; simpler; no HTMX-form failure-surface family relevant. Web form adds operator convenience (no terminal needed for refresh) at HTMX gotcha + V1 scope cost.
- **Default recommendation:** V1 CLI-only. Web UI = V2.
- **Decision source:** Operator.

### §10.6 Q6: Schwab inception-CSV ingestion

- **Question:** Bundle Schwab inception-CSV (full pre-Phase-7 trade history seeding) into V1 brainstorm scope, OR separate dispatch?
- **Tradeoff:** Inception CSV is richer than 7-day Account Statement; would seed `cash_movements` + `account_equity_snapshots` historical series + reconcile fills against journal for pre-Phase-7 trade history. Scope balloons brainstorm + writing-plans + executing-plans cycle.
- **Default recommendation:** Separate dispatch per phase3e-todo 2026-05-12 entry. Keep this brainstorm focused on live API V1.
- **Decision source:** Operator + phase3e-todo backlog priority.

### §10.7 Q7: TOS CSV deprecation timing

- **Question:** Once Schwab API ships, is TOS CSV reconciliation deprecated (V2) or stays as fallback (V1)?
- **Tradeoff:** Deprecating TOS removes a code path; reduces maintenance surface. Keeping TOS preserves a fallback when Schwab is degraded or for any account/period Schwab API doesn't cover.
- **Default recommendation:** Stays as V1 fallback per brief §1.9. Deprecation = V2.
- **Decision source:** Operator + post-ship operational experience.

### §10.8 Q8: Sandbox vs production — HTTP-layer differentiation (per-env sidecar LOCKED)

- **Question:** How exactly do sandbox vs production differentiate at the HTTP layer? Per §3.2.1 + §3.2.7 the spec LOCKS per-environment sidecars (`schwab-state.sandbox.json` + `schwab-state.production.json`) as V1 default. What REMAINS open is the API-side differentiation: does Schwab use distinct base URLs (e.g., `https://api-sandbox.schwabapi.com/...`), distinct path prefixes, distinct OAuth apps per env (likely yes per Schwab Developer Portal convention), distinct scope strings, distinct token TTLs?
- **Tradeoff:** If Schwab honors a single base URL + same scope strings + distinct apps, the per-env sidecar shape is sufficient + nothing else changes. If Schwab uses path-prefix or distinct base URLs, the SchwabClient constructor + endpoint catalog must accept the env-derived base URL.
- **Default recommendation:** **LOCKED:** per-env sidecar + `cfg.integrations.schwab.environment` toggle. **OPEN at executing-plans Task 0.b:** the HTTP-layer differentiation (base URL / path / scope / TTL). Writing-plans constructor signature accepts `base_url` parameter derived from env at instantiation time.
- **Decision source:** Schwab Developer Portal sandbox docs + Task 0.b operator-witnessed verification.

### §10.9 Q9: Cash-basis manual snapshot retention

- **Question:** Once Schwab API writes NLV snapshots, does operator retain ability to record cash-basis manual snapshots?
- **Tradeoff:** Retaining gives operator a back-record path for historical periods + a way to seed cash-basis-only periods. Source-ladder resolves at read time — Schwab wins when both present at same date. No conflict.
- **Default recommendation:** Yes. Keep manual snapshot retention; document the cash-basis-vs-MTM ambiguity in operator docs (V2 column-formalization candidate per phase3e-todo).
- **Decision source:** Operator + phase3e-todo backlog.

### §10.10 Q10: Pipeline-step ordering

- **Question:** Schwab snapshot/orders steps land WHERE in the pipeline?
- **Tradeoff:** Default per §3.4.2 — after `_step_evaluate`, before `_step_export`. Justified by briefing-render-includes-Schwab-data goal. Alternative: AFTER `_step_export` — defers Schwab to "background sync" but loses briefing inclusion.
- **Default recommendation:** Per §3.4.2 — after `_step_recommendations`, before `_step_charts`. V2 candidate to move BEFORE recommendations once metric-coupling stabilizes.
- **Decision source:** Orchestrator (architectural).

### §10.11 Q11: Market-data source-ladder (V1 INCLUDE vs V1 EXCLUDE)

- **Question:** Include `schwab_api > yfinance` market-data ladder in V1, OR defer to follow-on dispatch?
- **Tradeoff:** V1 INCLUDE (this spec's chosen branch): +200-400 lines spec body; +1-2 sub-bundles writing-plans + executing-plans; data-quality upgrade primary path. V1 EXCLUDE: faster Schwab arc; clean follow-on dispatch shape.
- **Default recommendation:** V1 INCLUDE per brief §1.9 + this spec §1.4.
- **Decision source:** Operator. If operator overrides at post-brainstorm review → §3.8 + §3.3.2 + §4.4 collapse to deferred-V2 subsections; rest of spec unaffected.

### §10.12 Q12: Premium-tier Schwab Market Data endpoints (V1 INCLUDE branch only)

- **Question:** Schwab Market Data API may have premium-tier endpoints (real-time quotes vs delayed). What's operator's tier — Schwab brokerage account default + paid market-data subscription, or default-only?
- **Tradeoff:** Default-tier gives delayed quotes (Schwab convention ~15min delay) + basic `pricehistory`. Premium-tier (subscription upgrade) gives real-time quotes. Project cadence is daily-EOD, so delayed quotes are sufficient V1. Operator may want real-time intraday for the after-hours `PriceCache` warmup; V2 candidate.
- **Default recommendation:** V1 default-tier; live-verify default-tier endpoint set at Task 0.b. If endpoint requires subscription upgrade → operator-actionable upgrade-or-defer decision.
- **Decision source:** Operator + Schwab Developer Portal subscription configuration.

### §10.13 Q13: OAuth callback URL — localhost loopback vs out-of-band paste

- **Question:** Default callback `https://127.0.0.1:8765/callback` works if operator can run a one-shot HTTPS listener on that port. Some networks / corp environments may block loopback HTTPS or self-signed certs. Out-of-band paste alternative: Schwab redirects to a "display-code-only" page, operator copies code, pastes into CLI prompt.
- **Tradeoff:** Localhost callback is lower friction once working; HTTPS self-signed cert may trigger browser warning operator must dismiss. Out-of-band paste is more steps but works in any environment.
- **Default recommendation:** Localhost callback default (V1). Out-of-band paste available via `swing schwab setup --paste` flag if operator's environment blocks loopback. Writing-plans implements both.
- **Decision source:** Operator post-Task-0.b verification.

### §10.14 Q14: OAuth scope-string composition

- **Question:** What scope strings does Schwab require? Synthesized defaults: `readonly` (single token for both APIs) — operator-actionable live-verify at Task 0.b. May actually be: `Trader.Read MarketData.Read` (space-separated; resource-server convention), or path-segment-style, or other.
- **Tradeoff:** Wrong scope = 403 at every endpoint after setup. Right scope = first-time success.
- **Default recommendation:** Operator pairs at Task 0.b to verify actual scope string against Schwab's exact API behavior.
- **Decision source:** Schwab Developer Portal docs + Task 0.b verification.

### §10.15 Q15: Refresh-token rotation behavior — operator-witnessed at Task 0.b

- **Question:** Schwab's exact behavior on refresh-token rotation. Some OAuth providers rotate on every refresh; some rotate only when refresh_token TTL nears expiry; some never rotate during the refresh_token's TTL window. Project V1 design (§3.2.3) handles both — store new refresh_token IF present in response. But the cassette + test fixtures need a known canonical rotation case.
- **Tradeoff:** If Schwab never rotates during TTL, cassette for "rotation" case requires inducing TTL boundary OR mocking. If Schwab rotates on every refresh, cassette is trivial.
- **Default recommendation:** Document the design's robustness; defer rotation-fixture creation to executing-plans Task 0.b. The Task 0.b runbook MUST include "observe rotation behavior; record one cassette per case observed".
- **Decision source:** Schwab Developer Portal docs + Task 0.b operator-witnessed verification.

### §10.16 Q16: Account_hash persistence on `account_equity_snapshots` (V1 vs V2)

- **Question:** Add `schwab_account_hash` column on `account_equity_snapshots` in V1, or defer to V2 multi-account?
- **Tradeoff:** V1 adds column (NULL for non-schwab sources; populated for schwab_api). Forward-prepares multi-account. Minimal V1 scope creep. V2 defer keeps V1 column-count flat; multi-account dispatch adds the column then.
- **Default recommendation:** V1 ADD the column (NULL-permissible). Writing-plans firms up DDL. Forward-prep is cheap insurance.
- **Decision source:** Orchestrator (architectural).

### §10.17 Q17: Market Data API rate limits — independent of Trader API?

- **Question:** Does Schwab Market Data API publish a distinct rate-limit threshold from Trader API's ~120 req/min? If yes, what value + window?
- **Tradeoff:** If Market Data limits are tighter than Trader (e.g., 60 req/min combined or per-symbol limits), batched `/quotes` + cache-miss-only `/pricehistory` should stay within. If limits are looser or comparable, no concern. Hitting a Market Data 429 while Trader API stays unaffected validates the §1.3 #5 split-rate-limit assumption.
- **Default recommendation:** Synthesize "~Trader API limits or looser" V1; flag Task 0.b verification. If Task 0.b reveals tighter Market Data limits, writing-plans tightens fetch cadence (per-page fetches deferred to first-page-load only; subsequent web requests serve cache only).
- **Decision source:** Schwab Developer Portal docs + Task 0.b paired verification.

---

## §11 Self-review checklist (pre-commit)

LOCKED (claim the spec firmly stands on):

- [x] Spec section structure mirrors Phase 9 brainstorm spec format (§1 background / §2 vocab / §3 architecture / §4 schema candidates / §5 redaction / §6 failure / §7 operator setup / §8 capture-needs / §9 watch-items / §10 open questions / §11 self-review / §12 references).
- [x] Source-ladder explicitly disclaimed as re-design target (§1.3 #1 + §3.7).
- [x] OAuth refresh-token rotation handled by design (§3.2.3 — exact rotation cadence is §10 Q15 pending Task 0.b verification).
- [x] Token redaction inheritance from Finviz called out + EXTENDED with explicit higher-risk-deviation disclosure for client_secret + refresh_token co-storage (§3.2.2 + §5).
- [x] Audit trail covers auth calls; in-flight + linked-row UPDATE lifecycle defined (§3.6.1 + §9 watch-item 11 coverage requirement).
- [x] Audit-write surface boundary defined — web-page-render path is EXPLICITLY-UNAUDITED V1 (logs-only); CLI / pipeline surfaces SYNCHRONOUS audit; V2 candidates for batched-summary writer + debug endpoint enumerated (§3.6.2).
- [x] Sandbox-vs-production isolation: domain writes gated on `cfg.integrations.schwab.environment='production'`; sandbox is verification-only; market-data ladder short-circuits sandbox (§3.6.3 + §3.2.7).
- [x] Order placement explicit-disclaimed in §1.2 + §3.3.3.
- [x] Pipeline step ordering — single insertion point: AFTER `_step_recommendations`, BEFORE `_step_charts` (§3.4.2; aligned across §3.4.1 + §10.10).
- [x] No internal contradiction on `_step_schwab_marketdata` — NOT a pipeline step; integrated into cache layer (§3.4.1 + §3.8.3).
- [x] Failure tolerance matches Finviz continue-with-error (§3.4.4 + §6).
- [x] Operator setup flow concrete with paste-code first-class fallback (§3.2.1 + §10 Q13).
- [x] Multi-account question surfaced (§10 Q3 + §10 Q16).
- [x] CLI vs pipeline concurrency split-by-surface table (§3.2.4 + §3.4.5).
- [x] Empty-API-response handling per CLAUDE.md gotcha (§3.4.4 + §3.8.6).
- [x] No `CREATE TABLE` SQL drafted. No Python code drafted. (Schema candidate sketches in §4 are column-name + type only.)
- [x] No JS-test-harness gap concern (CLI-driven; web-page-render path defined to NOT introduce HTMX form surfaces; §9 watch-item 16).

PENDING (depends on open questions / Task 0.b verification — NOT a self-claim):

- [ ] Sandbox vs production base-URL / scope-string / per-environment-app differentiation — §10 Q8 open; framework locked, exact HTTP-layer differentiation pending Task 0.b.
- [ ] Premium-tier endpoint set — §10 Q12 operator-actionable.
- [ ] Schwab Developer App approval status — §10 Q1.
- [ ] Market-data ladder persistence shape (A vs B vs C) — §3.8.2 writing-plans decides; spec recommends A (parquet-per-(ticker, provider)).
- [ ] Account_hash-column-on-snapshots V1 vs V2 — §10 Q16 (default V1 ADD).
- [ ] `[VERIFY]`-tagged endpoint shapes — Task 0.b operator-paired verification before cassette recording.

LINE COUNT: spec ~900-950 lines post-Codex-R1-fixes. Within 600-1100 budget (brief §4).

---

## §12 References

**Brief:**
- `docs/schwab-api-brainstorm-dispatch-brief.md` (commit `c4252d3`).

**Spec format precedent:**
- `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; the most recent multi-source brainstorm spec).

**Closest already-shipped API integration precedent:**
- `swing/integrations/finviz_api.py` (276 lines; Finviz Elite API client).
- `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (Finviz integration plan; merged `002338a`).
- `tests/integrations/test_finviz_api_cassette.py` + `test_finviz_api_live.py` + `test_finviz_pipeline_step.py` + `test_finviz_token_redaction_audit.py` (Finviz test family — pattern model).

**Source-ladder consumer (binding inheritance):**
- `swing/data/repos/account_equity_snapshots.py` (`_SOURCE_PRECEDENCE` at line 38; `get_latest_snapshot_on_or_before` at line 130).
- `swing/trades/account_equity_snapshots.py` (`record_snapshot` service at line 66; `CallerHeldTransactionError` contract at line 39).
- `swing/trades/reconciliation.py` (`run_tos_reconciliation` shape; transactional contract; `DISCREPANCY_TYPES` + `MATERIAL_BY_TYPE` + `RESOLUTION_TYPES` at lines 42-82).

**Schema CHECK enum baseline (already permits `'schwab_api'`):**
- `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql:194` (`reconciliation_runs.source`).
- `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql:332` (`account_equity_snapshots.source`).

**Phase 10 metrics consumer (already in place; no changes needed):**
- `swing/web/routes/metrics.py` (Phase 10 routes).
- `swing/web/view_models/metrics/capital_friction.py` (PROVISIONAL/LIVE badge — consumes `get_latest_snapshot_on_or_before(with_provenance=True)`).

**CLAUDE.md gotchas relevant to Schwab integration:**
- "External-API empty-result must be treated as transient when write-through-caching" (§3.4.4 + §3.8.6).
- "Service-layer `with conn:` opens its own transaction" + "in_transaction auto-detect" (§3.4.3 + §3.7 — repo vs service contract).
- "Session-anchor read/write mismatch" (§3.4.1 — `_step_schwab_snapshot` uses `last_completed_session(now)` to match writer-side discipline).
- "Tests that exercise write_user_overrides must monkeypatch USERPROFILE AND HOME" (§9 watch-item 4 — applies to sidecar tests).
- "yfinance `threads=False` only on `yf.download()`" + 3 other yfinance regressions (§1.4 motivation for V1 INCLUDE market-data ladder; §3.8.4 preserves yfinance gotcha-hardened code path).
- "Python `or ""` idiom collides with SQL CHECK-constraint nullability" (writing-plans territory — applies to any new CHECK-constrained columns added).

**Orchestrator-context:**
- `docs/orchestrator-context.md` — durable orchestrator-role conventions.
- `docs/orchestrator-handoff-2026-05-13-schwab-api.md` — post-Phase-10-close handoff brief.
- `docs/phase3e-todo.md` — Phase 11 candidates pre-banked (Schwab inception-CSV / cash-basis-vs-MTM ambiguity / orphan-discrepancy detail surface).

**Schwab Developer Portal (operator-actionable; brainstorm synthesized from public references):**
- https://developer.schwab.com/ (developer portal entry).
- Schwab Trader API documented endpoints (operator-paired verification at executing-plans Task 0.b).
- Schwab Market Data API documented endpoints (operator-paired verification at Task 0.b).
- Community-maintained Python wrappers (reference only): `schwab-py`, `schwabdev`.
