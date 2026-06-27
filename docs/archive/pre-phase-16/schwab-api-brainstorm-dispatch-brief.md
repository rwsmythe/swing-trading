# Schwab API Integration Brainstorm — Implementer Brief

**Audience:** Fresh Claude Code instance dispatched as the Schwab API integration brainstorm implementer. No prior conversation context.

**Mission:** Produce a design spec for integrating the Charles Schwab Developer Portal API into the Swing Trading project. The spec defines V1 scope (auth flow, endpoints consumed, write paths into already-shipped Phase 9 source-ladder, audit+observability surfaces) + open questions for orchestrator triage. **DO NOT lock schema** — schema decisions are deferred to writing-plans, but the spec MAY enumerate likely new tables/columns as candidates for the writing-plans dispatch to firm up.

**Expected duration:** 90–180 minutes including 3–6 adversarial Codex rounds. Schwab API is larger scope than Finviz (full OAuth 2.0 flow + refresh-token rotation + multi-endpoint consumption + multi-account considerations + the source-ladder write path) — expect Codex to find auth-flow + secret-storage + rate-limit + reconciliation-precedence issues at brainstorm time.

**Sequencing context:** Phase 10 closed at `38dbac3` (Sub-bundle E + arc closer at `d560218`). Post-Phase-10 infrastructure bundle SHIPPED at `27ce96f` (cleanup-script `-DeregisterFirst` + pytest-xdist baseline at 6.56× speedup); housekeeping at `9d4edfc`; this handoff at `c4252d3`. Schema v17 stable; ruff 18 (E501 only); ~3286 fast tests on main HEAD; fast suite default `-n auto` at ~63s. Phase 9 + Phase 10 together installed the source-ladder + reconciliation + metrics-dashboard infrastructure that consumes Schwab data the moment it lands. **The Schwab API arc is the next major operator-paced milestone.**

---

## §0 Read first (in order)

1. **`CLAUDE.md`** at repo root — status line through `9d4edfc`; full Gotchas section. The Finviz API integration gotcha family + the Phase 9 Sub-bundle A "user-config.toml monkeypatch" gotcha + the "Service-layer `with conn:`" + "External-API empty-result" + "Session-anchor read/write mismatch" gotchas are the closest precedents for Schwab API work.
2. **`docs/orchestrator-context.md`** — durable orchestrator-role conventions; Codex-driven discipline; retention + archive split.
3. **`docs/orchestrator-handoff-2026-05-13-schwab-api.md`** — the post-Phase-10-close handoff brief. §4 enumerates dispatch dimensions + recommended option. Treat its dimension list as starting taxonomy, not closed scope.
4. **`docs/phase3e-todo.md`** top entries 2026-05-13 (post-infra-bundle-ship + Phase 10 Sub-bundle E ship + Phase 10 closer section line 1788+ — Phase 11 candidates pre-banked include Schwab inception-CSV + `account_equity_snapshots.equity_dollars` cash-basis-vs-MTM ambiguity + orphan discrepancy detail surface).
5. **`docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md`** (merged `002338a`) — closest already-shipped API integration precedent. Mirror its format for §A resolved-during-planning items + §E endpoint reference + §G cassette runbook + §H algorithm spec + §K verification gates. The Schwab API spec **inherits** Finviz's token-redaction discipline (urllib3 DEBUG-log suppression + cassette `filter_query_parameters` + `__str__` contract on exceptions) verbatim — call this out explicitly in the spec.
6. **`swing/integrations/finviz_api.py`** + **`tests/integrations/test_finviz_api*.py`** — read all ~830 lines to internalize the cassette + signature-hash + drift-detection + concurrency-exclusion patterns. Schwab will be a sibling module (`swing/integrations/schwab.py` or sub-package; brainstorm picks).
7. **`swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql`** — schema already supports `'schwab_api'` source on both `account_equity_snapshots` (line 332 CHECK) and `reconciliation_runs` (line 194 CHECK). The UNIQUE INDEX `ux_account_equity_snapshots_date_source` on `(snapshot_date, source)` enables per-source coexistence on the same date. **The source-ladder write path is ALREADY DESIGNED at the schema level** — Schwab API integration consumes this; it does NOT re-design it.
8. **`swing/data/repos/account_equity_snapshots.py`** — `_SOURCE_PRECEDENCE = {schwab_api: 0, tos_csv: 1, manual: 2}` is already encoded; `get_latest_snapshot_on_or_before(with_provenance=True)` already returns `(winner, suppressed)` for source-ladder UI rendering. Read-side resolution is shipped.
9. **`swing/trades/account_equity_snapshots.py`** — `record_snapshot(source: str = "manual", ...)` is the service the API write path will call (with `source="schwab_api"`, `source_artifact_path=<schwab_api_call_id_or_url>`). **CallerHeldTransactionError** discipline applies — caller must NOT hold an open transaction when calling.
10. **`swing/trades/reconciliation.py`** + **`swing/journal/tos_import.py`** — Phase 9 Sub-bundle B + E reconciliation surface. Schwab API may write a `reconciliation_runs` row with `source='schwab_api'` (CHECK enum already permits) bypassing the TOS CSV parser entirely — brainstorm picks the architecture.
11. **`docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`** §3.2 source-ladder + §3.3 reconciliation-run lifecycle + §A.9 source-ladder + Phase 9 Sub-bundle C T-C.6 equity_delta wiring at `swing/trades/reconciliation.py` — the reconciliation surface that Schwab API outputs feed into.
12. **One prior brainstorm spec for format reference** — `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; the most recent multi-source brainstorm spec). Mirror its section structure: §A resolved items / §B file map / §C SQL deferred / §D open questions / §E endpoint / §F write-path / §G adversarial / §H verification.

---

## §0 Skill posture

- Invoke **`copowers:brainstorming`** (which wraps `superpowers:brainstorming` with adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:writing-plans` — no schema-locking + no task decomposition. The orchestrator dispatches writing-plans separately AFTER brainstorm spec lands + operator triages open questions.
- DO NOT invoke `superpowers:executing-plans` or `superpowers:test-driven-development` — design-only.
- DO NOT invoke `superpowers:using-git-worktrees` — no code changes; spec doc commit only on `main`.

---

## §1 Strategic context (ORCHESTRATOR-DISTILLED — what's NOT in the docs)

The Schwab API integration is **not** a greenfield project. Phase 9 already built the consumption infrastructure assuming a future API source. Treat the following as **BINDING design constraints** — they are not derivable from Schwab Developer Portal docs alone.

### §1.1 Source-ladder is ALREADY designed and shipped — Schwab API CONSUMES it; do NOT re-design

Per §0 reads 7+8+9: `account_equity_snapshots.source` and `reconciliation_runs.source` CHECK enums already permit `'schwab_api'`; UNIQUE INDEX `(snapshot_date, source)` enables per-source coexistence; `_SOURCE_PRECEDENCE = {schwab_api: 0, tos_csv: 1, manual: 2}` already encoded; `record_snapshot(source=...)` already polymorphic. Phase 9 Sub-bundle C explicitly designed `with_provenance=True` mode for the eventual Schwab API ladder.

**Implication:** the Schwab API write path is NOT inventing source-ladder semantics. It calls `record_snapshot(source='schwab_api', ...)` for equity snapshots; for reconciliation runs it inserts a row with `source='schwab_api'` directly via the existing repo. The brainstorm should **explicitly disclaim** any re-design of the source-ladder — that's spec §11.4 + Phase 9 Sub-bundle C T-C.6 territory, locked.

What IS new design surface:
- Mapping Schwab API responses → existing `AccountEquitySnapshot` + `Fill` + `Discrepancy` field shapes.
- Deciding when an API-sourced snapshot SHOULD vs SHOULD NOT supersede a same-date `'manual'` snapshot (default per ladder: yes, source-ladder resolves at read time; but UI-render-side surfacing is open).
- Deciding API-sourced reconciliation_run cadence + `period_start` / `period_end` semantics (Schwab API can return up-to-the-minute, not 7-day-window-only like the Account Statement CSV).
- The audit trail for every API call (mirror `finviz_api_calls` table or extend; brainstorm picks).

### §1.2 Phase 10 metrics-dashboard surfaces consume Schwab API data the moment it lands

Phase 10 Sub-bundle D shipped `/metrics/capital-friction` with PROVISIONAL/LIVE dynamic badge: PROVISIONAL when no `account_equity_snapshots` row exists ≤ asof_date; LIVE when one does. Currently 3 manual snapshots exist (operator-stamped via `/account/snapshot` form). **Once Schwab API writes a snapshot per pipeline run, the surface effectively never goes PROVISIONAL** — Schwab API integration closes the LIVE-badge stickiness gap in steady state.

Phase 10 metrics surfaces that depend on `account_equity_snapshots` consume the source-ladder transparently via `get_latest_snapshot_on_or_before` — no code changes needed in metrics surfaces when Schwab API rows arrive.

**Implication:** Schwab API integration does NOT need to design new metrics surfaces. Capture-needs feedback for Phase 10 metrics dashboard is **null** for V1 — the consumers are already in place.

### §1.3 Schwab Developer Portal access is operator-gated; live verification is BLOCKING

The Schwab Developer Portal (https://developer.schwab.com/) requires:
- A registered Schwab brokerage account.
- A registered Developer App (client_id + client_secret).
- App approval status (Schwab review process; can take days-to-weeks for production tier).
- Sandbox vs production API access (Schwab offers sandbox for development).

**The brainstorm dispatch CANNOT verify any of these** — implementer has no Schwab account. Mirror the Finviz precedent at §A.1 (Finviz Elite docs were behind login → plan synthesized endpoint shape from public knowledge → §D OPEN QUESTION FOR ORCHESTRATOR + Task 0.b live verification gate at executing-plans). The Schwab brainstorm spec MUST:

1. Synthesize endpoint shape from publicly-documented Schwab Trader API surface (POST /v1/oauth/token, GET /trader/v1/accounts/{accountNumber}, GET /trader/v1/accounts/{accountNumber}/orders, GET /trader/v1/accounts/{accountNumber}/transactions, etc. — verify exact paths against Schwab's published OpenAPI spec or community-maintained references).
2. Flag any synthesis as **§D open question for orchestrator** with concrete operator-actionable question (e.g., "Operator: verify the GET /accounts response contains a `currentBalances.liquidationValue` field by hand-running curl OR paste the OpenAPI spec section").
3. Defer cassette recording to executing-plans Task 0.b (operator-paired live API call against operator's sandbox or production tokens).

### §1.4 Auth flow is OAuth 2.0 — significantly more complex than Finviz's query-param token

Finviz: single-token, append `&auth=<token>` to every request, redact via `filter_query_parameters` + urllib3 DEBUG-log suppression. **Schwab: OAuth 2.0 authorization-code flow** — operator-driven browser redirect to Schwab login → consent screen → callback URL receives authorization code → POST /v1/oauth/token exchanges code for access_token (1-hour TTL by default) + refresh_token (7-day or 90-day TTL depending on tier). Refresh-token rotation: subsequent POSTs with `grant_type=refresh_token` return new access_token (and SOMETIMES new refresh_token).

The brainstorm spec MUST design:

1. **Initial-setup flow** — operator runs `swing schwab setup` (or similar CLI command); the command opens browser to Schwab consent URL; receives callback at localhost:N (or paste-token-back); POST exchanges; persists access_token + refresh_token + expiry to user-config.toml or a sidecar state file.
2. **Token-refresh flow** — automatic when access_token expires; if refresh_token also expired, ALERT operator + fall back to PROVISIONAL state (mirror Phase 10 PROVISIONAL/LIVE badge family).
3. **Token storage discipline** — at minimum mirror Finviz's user-config.toml gotcha (USERPROFILE+HOME monkeypatch in tests; redaction at every log boundary; mask in `swing config show`). Open question: **encrypted at rest** (Windows DPAPI / `keyring` lib) vs plaintext (Finviz precedent)? Brainstorm picks default + flags for orchestrator triage.

### §1.5 Schwab API endpoints needed for V1 — minimal viable consumption

Schwab exposes TWO separate API surfaces under the same OAuth 2.0 auth (same client_id + access_token):

**(a) Trader API** (`https://api.schwabapi.com/trader/v1/`) — account-data layer:

- **POST /v1/oauth/token** — auth flow (initial code exchange + refresh; common to both APIs).
- **GET /trader/v1/accounts** — list operator's linked Schwab accounts; needed for account-hash discovery on first-setup.
- **GET /trader/v1/accounts/{accountNumber}** — current balances (Net Liquidating Value, cash, buying power) for `account_equity_snapshots` write.
- **GET /trader/v1/accounts/{accountNumber}/orders** — placed orders (working stops, filled orders) for `reconciliation_runs` source replacing the TOS Account Order History parser.
- **GET /trader/v1/accounts/{accountNumber}/transactions** — historical fills + cash movements for `cash_movements` reconciliation + (optionally) historical trade-history seeding (V2 candidate per phase3e-todo Schwab inception-CSV ingestion).

**(b) Market Data API** (`https://api.schwabapi.com/marketdata/v1/`) — market-data layer:

- **GET /marketdata/v1/quotes** (or `/quotes/{symbol}`) — last/bid/ask/mark for one or many symbols. Project candidate: replace/precede yfinance in `PriceCache` (live quotes during session + after-hours).
- **GET /marketdata/v1/pricehistory** — historical daily/intraday OHLCV. Project candidate: replace/precede yfinance in `OhlcvCache` (SMA inputs + chart rendering).
- **GET /marketdata/v1/markets/{market}/hours** — market-hours metadata. Project candidate: complement to existing `exchange_calendars` lib (probably not needed V1; flag as low-priority).

**Operator-elective in V1:** see §1.9 + §2.9 Q11 — `schwab_api > yfinance` market-data source-ladder is a real candidate for V1 inclusion (operator surfaced this dimension at brainstorm-dispatch time). The brainstorm spec MUST surface this as a first-class V1-or-V2 decision, not silently defer.

Likely NOT needed V1:

- Streaming endpoints (real-time quotes via WebSocket, order updates) — V2 candidate per handoff brief §E4.
- Order placement / cancellation — explicit OUT-OF-SCOPE; Schwab API integration is READ-ONLY in V1 (the project is operator-discretion-trade-execution; automated order placement is OUT of scope per §3 below).
- Option chains / fundamentals / instruments lookup — V2 candidates; brainstorm explicitly defers.

### §1.6 Multi-account is a real scope question

Schwab supports multiple linked accounts per OAuth app (operator may have a brokerage account + IRA + joint account). Project current state: single-account; `account_equity_snapshots` table has NO `account_hash` column (just `equity_dollars` + `snapshot_date` + `source`). Multi-account support requires schema extension (V1 candidate: new column on snapshot table; V2 candidate: separate `accounts` table).

Operator-decision: V1 single-primary-account-only (simpler; matches current state) or V1 multi-account (broader; needs schema work)? Brainstorm flags as **§D open question** (default recommendation: V1 single-account; operator selects primary account at `swing schwab setup` time; multi-account = V2).

### §1.7 Rate limits — Schwab posts numbers but verify

Schwab Trader API rate limits (per Schwab developer docs, subject to verification): ~120 requests per minute per app; per-account limits may apply. Pipeline cadence is daily so single-fetch-per-run is comfortably within. CLI `swing schwab fetch` (if exists) is operator-triggered + low-volume.

Mirror Finviz §A.4 + §E.6: single attempt; on 429 parse `Retry-After`, wait + retry once, then give up + record `status='error'`. **DO NOT design retry-loops for V1** — daily cadence + low-volume CLI invocations don't warrant.

### §1.8 Cash-basis-vs-MTM ambiguity is RESOLVED by Schwab API

Phase 9 Sub-bundle C return report (2026-05-12 entry in phase3e-todo) banked the `account_equity_snapshots.equity_dollars` cash-basis-vs-MTM semantic ambiguity as a V2 candidate. **Schwab API resolves this by returning Net Liquidating Value (NLV)** authoritatively per-call. Brainstorm spec calls out: API-sourced snapshots are unambiguously NLV (or whatever Schwab's exact field semantics — verify at live verification gate); V1 may still allow operator to record cash-basis manual snapshots for back-recording, with the source-ladder ensuring Schwab values dominate when both exist.

### §1.9 What Schwab API does NOT replace in V1 (with one operator-flagged elective)

**Locked NOT-REPLACED in V1:**

- **Finviz Elite candidate-screen** — Finviz is the screening source; Schwab is the brokerage source. Different layers; Schwab does NOT replace Finviz. Schwab Market Data API has no equivalent screen-builder surface.
- **Manual `daily_management_records` capture** — Phase 8 surface is operator-driven post-trade-management observation; not an API surface.
- **Manual `review_log` capture** — Phase 6 + Phase 9 reviews are operator-judgment surfaces; not an API surface.
- **TOS Account Statement CSV reconciliation** — Phase 9 Sub-bundle B + E + Sub-bundle E T-E.3 multi-line parser stays in V1 as a fallback path for any account/period Schwab API doesn't cover OR when API is degraded. Defer V2 deprecation question to a follow-up dispatch.

**Operator-flagged elective for V1 (pending brainstorm decision per §2.9 Q11):**

- **yfinance market-data cache (`PriceCache` + `OhlcvCache`) as the second tier in a `schwab_api > yfinance` source-ladder.** Operator surfaced this dimension at brainstorm-dispatch time. The pattern would mirror the equity-snapshot ladder shipped at Phase 9 Sub-bundle C (§1.1 above):
  - `PriceCache.get_latest(ticker)` tries Schwab `/quotes` first; falls back to yfinance on failure / quota / no-tokens.
  - `OhlcvCache.get_window(ticker, start, end)` tries Schwab `/pricehistory` first; falls back to yfinance.
  - Cache rows tagged with `source` so a Schwab response is not clobbered by a stale yfinance response (and the read-side resolution prefers the higher-source row when both are fresh-enough).
  - Empty-API-response handling per CLAUDE.md gotcha "External-API empty-result must be treated as transient when write-through-caching": Schwab transient empty does NOT auto-fallback to a yfinance-write-through; it logs + records `schwab_api_calls.status='error'` + the read-side ladder serves the most-recent non-empty value.
  - Probably bumps the brainstorm spec to ~800-1100 lines (vs ~600-900 without market-data ladder). Probably bumps the eventual writing-plans + executing-plans cycle by 1-2 sub-bundles (a "Sub-bundle X market-data ladder" sub-bundle).
  - **Default recommendation per §2.9 Q11:** brainstorm spec MUST surface this as a first-class operator-elective open question with concrete tradeoff sketch. The default I recommend operator triage to: **V1 INCLUDE market-data ladder** for two reasons: (a) yfinance is the project's most fragile external dependency per CLAUDE.md gotchas (4+ documented yfinance regressions); replacing the primary path with a paid broker-grade source materially improves data quality + reduces ops surprises. (b) The cache architecture changes are localized to `PriceCache` + `OhlcvCache`; the source-ladder pattern from Phase 9 Sub-bundle C transfers cleanly. **But operator decides** — V1 EXCLUDE keeps Schwab arc tightly account-data-focused + ships sooner; market-data ladder becomes a clean follow-on dispatch.

The spec MUST treat this dimension as binding scope-decision input — not silently defer or silently include. Brainstorm flags concrete consequences of either choice (V1 INCLUDE vs V1 EXCLUDE) so operator can decide at orchestrator-triage time post-brainstorm.

---

## §2 Brainstorm scope (in scope)

Produce a design spec at `docs/superpowers/specs/2026-05-14-schwab-api-design.md` (or YYYY-MM-DD of brainstorm-completion-date) covering:

### §2.1 — Auth flow + token storage

- Initial-setup CLI flow (browser-redirect vs paste-token; localhost callback port choice; consent-URL scope-string composition).
- Token storage location + format (user-config.toml `[integrations.schwab]` section vs sidecar JSON state file at `%USERPROFILE%/swing-data/schwab-state.json`; pick + justify).
- Token-refresh flow (background-on-pipeline-run vs lazy-on-first-API-call; pick + justify).
- Token expiry detection + alerting (where the operator finds out a refresh failed — CLI exit code, `pipeline_runs.errors`, web banner, daily-management surface).
- Encrypted-at-rest disposition (DEFAULT V1: plaintext per Finviz precedent + add explicit V2 hardening note for `keyring` / DPAPI).
- Revocation flow (operator runs `swing schwab logout` → deletes stored tokens; future API calls fall back to PROVISIONAL).

### §2.2 — Endpoint reference (synthesized; verify at executing-plans Task 0.b)

For each endpoint in §1.5:

- HTTP method + URL pattern.
- Required headers (`Authorization: Bearer <access_token>`; `Content-Type: application/json` for POSTs).
- Query/path parameters.
- Expected response shape (JSON; spec calls out the specific fields project consumes).
- Failure modes (401 = expired; 403 = insufficient scope; 429 = rate limit; 5xx = retry).

Mirror Finviz §E format. Where any endpoint shape is uncertain, flag as **§D open question** + propose concrete operator verification step.

### §2.3 — Pipeline integration architecture

- New pipeline step(s): `_step_schwab_snapshot` (writes equity snapshot per run); optionally `_step_schwab_orders` (writes reconciliation_run per run); optionally `_step_schwab_fills` (V2 candidate or V1?).
- Step ordering relative to existing pipeline (`_step_finviz_fetch` is FIRST in `swing/pipeline/runner.py`; Schwab steps land WHERE relative to candidate evaluation? after `_step_evaluate`? after `_step_export`?).
- Lease-fenced semantics (mirror Finviz §A.13 shadow-promote-then-audit; Schwab writes are DB-only, no filesystem CSV — atomicity is single-transaction per repo + audit-row insert).
- Token-refresh-on-step-entry (defensive: refresh if access_token expires within 60s).
- Failure tolerance (does Schwab step failure abort the pipeline run, or does it record `status='error'` and continue? Mirror Finviz: continue-with-error is the precedent).
- CLI surface: `swing schwab fetch [--snapshot|--orders|--all]` (mirror `swing finviz fetch` + `status` group; brainstorm picks subcommand shape).

### §2.4 — Source-ladder write path (binding contract — DO NOT re-design)

Per §1.1: spec explicitly calls out:

- Equity snapshot write: `record_snapshot(conn, equity_dollars=<NLV_from_API>, source='schwab_api', source_artifact_path=<reference_to_audit_row>, recorded_by='schwab_api', notes=<optional>)`. UPSERT semantics already exist; no new code needed in the service layer.
- Reconciliation-run write: `INSERT INTO reconciliation_runs (..., source='schwab_api', ...)` via `swing.data.repos.reconciliation` (Phase 9 Sub-bundle B repo). Discrepancy emit semantics unchanged.
- Source-ladder UI rendering: existing `with_provenance=True` mode at `get_latest_snapshot_on_or_before` returns `(winner, suppressed)`; UI surfaces (Phase 10 capital-friction LIVE badge) consume this transparently. Brainstorm spec **explicitly defers** any change to UI rendering to a separate dispatch.

### §2.5 — Audit trail + observability

- New audit table candidate: `schwab_api_calls` (mirror `finviz_api_calls` from migration 0015; columns: `call_id`, `ts`, `endpoint`, `status`, `response_time_ms`, `rate_limit_remaining`, `signature_hash` of response, `error_message`). Schema decision deferred to writing-plans; spec proposes the column shape.
- New status-surface candidate: `swing schwab status` CLI command — mirrors `swing finviz status`; reads recent `schwab_api_calls` rows.
- Token-state observability — does `swing schwab status` report token expiry / refresh-token validity / last successful auth? Brainstorm picks.

### §2.6 — Migration + schema posture

- `EXPECTED_SCHEMA_VERSION` likely bumps from 17 → 18.
- Likely new tables (writing-plans firms up):
  - `schwab_oauth_state` (refresh_token, access_token, expiry, last_refresh_at, account_hash) — operator-encrypted-at-rest open question.
  - `schwab_api_calls` (audit trail per §2.5).
- Likely new columns (writing-plans firms up):
  - `account_equity_snapshots.schwab_account_hash TEXT NULL` (only populated for source='schwab_api' rows).
  - Possibly: `reconciliation_runs.schwab_api_call_id` (FK to audit table).
- Brainstorm explicitly does NOT lock CHECK constraints, FK cascade rules, or indexes. Those are writing-plans territory.

### §2.7 — Token redaction discipline (binding inheritance from Finviz)

Spec **explicitly inherits** from Finviz §E.7 + §A.12:

- All exception `__str__` MUST never include access_token, refresh_token, or client_secret bytes.
- `urllib3.connectionpool` + `requests.packages.urllib3.connectionpool` DEBUG-log suppression context manager wrapping all HTTP calls.
- Cassette `filter_headers=['authorization']` + `filter_query_parameters` for any token-bearing query string.
- Sentinel-token-leak audit test (mirror `tests/integrations/test_finviz_token_redaction_audit.py`) — end-to-end fetch + grep all log records + DB rows for sentinel.
- `swing config show` masks Schwab fields (V2 hardening if `[integrations.schwab]` is added to FIELD_REGISTRY; V1 keeps Finviz precedent — Schwab fields outside FIELD_REGISTRY).

### §2.8 — Operator setup flow + cycle-checklist update

- One-time setup steps: register Schwab Developer App, register callback URL, run `swing schwab setup`, paste authorization code, system persists tokens.
- Daily cycle: pipeline auto-fetches; operator sees PROVISIONAL → LIVE badge transition; CLI `swing schwab status` confirms last-call success.
- Token-refresh-failure recovery: alert message + operator runs `swing schwab refresh` (manual) or `swing schwab setup` (re-auth from scratch).
- Spec calls out the `docs/cycle-checklist.md` updates needed (deferred to writing-plans implementation; spec just enumerates).

### §2.9 — Open questions for orchestrator triage (BINDING — every unresolved decision goes here)

Likely categories (extend or refine — not exhaustive):

- **Q1: Schwab Developer Portal status** — Has operator already registered an app? Has it received production-tier approval? OR is sandbox the V1 target? **Operator-actionable; blocks executing-plans Task 0.b live verification**.
- **Q2: Token storage encryption** — plaintext (Finviz precedent) vs encrypted (Windows DPAPI / cross-platform `keyring`)? Default recommendation: V1 plaintext + V2 hardening note; operator may override.
- **Q3: Multi-account support** — V1 single-primary-account or V1 multi-account? Default recommendation per §1.6: V1 single-account.
- **Q4: Streaming vs batch-poll** — V1 batch-poll only; V1 streaming (V2 candidate per handoff brief §E4)? Default recommendation: V1 batch-poll.
- **Q5: Operator-facing UI** — CLI-only V1 or web form for token-refresh / account-selection? Default recommendation: V1 CLI-only; web UI = V2.
- **Q6: Schwab inception-CSV ingestion** — bundle into V1 brainstorm scope (richer historical seed than 7-day Account Statement) OR separate dispatch (V2 candidate per phase3e-todo 2026-05-12 entry)? Default recommendation: separate dispatch; keep this brainstorm focused on live API V1.
- **Q7: TOS CSV deprecation timing** — once Schwab API ships, is TOS CSV reconciliation deprecated (V2 candidate) or stays as fallback path? Default recommendation: stays as fallback V1; deprecation = V2.
- **Q8: Sandbox vs production toggle** — config-driven (`cfg.integrations.schwab.environment = "sandbox"|"production"`) or two separate auth flows? Default recommendation: config-driven; brainstorm flags.
- **Q9: Cash-basis manual snapshot retention** — once Schwab API writes NLV snapshots, does operator retain ability to record cash-basis manual snapshots? Default recommendation: yes (operator may want to back-record cash basis for historical periods); source-ladder resolves at read time.
- **Q10: Pipeline-step ordering** — Schwab snapshot/orders steps land WHERE in the pipeline? Default recommendation: after `_step_evaluate`, before `_step_export` (so briefing.md can include LIVE badge + reconciliation-discrepancy summary).
- **Q11: Market-data source-ladder (`schwab_api > yfinance`) inclusion in V1** — operator-flagged at brainstorm-dispatch time per §1.9. Brainstorm spec MUST present concrete tradeoff:
  - **V1 INCLUDE**: spec extends to `PriceCache` + `OhlcvCache` ladder design + `/quotes` + `/pricehistory` endpoint sections + new pipeline-step or cache-layer integration design + cassette patterns for both endpoints. Adds ~200-400 lines to spec. Adds 1-2 sub-bundles to eventual writing-plans + executing-plans cycle. Operator data-quality benefit: removes yfinance as primary source for the project's most-consumed external data. Default per §1.9: orchestrator recommends INCLUDE.
  - **V1 EXCLUDE**: spec keeps Schwab arc account-data-focused (snapshots + orders + transactions). Market-data ladder = clean follow-on dispatch (similar shape to Phase 9 Sub-bundle C: separate brainstorm + writing-plans + executing-plans). Schwab arc ships sooner. Operator data-quality benefit: deferred.
  - **Operator decides at orchestrator-triage time post-brainstorm.** If brainstorm dispatch lands BEFORE operator decides, brainstorm picks one + flags the chosen branch's design + explicitly notes the alternate-branch deferred design.

Each open question structured per orchestrator-context conventions: **question + tradeoff sketch + your recommendation + which decision-source the operator needs to consult**.

---

## §3 OUT OF SCOPE (do not do)

- **Schema-locking** — no `CREATE TABLE` SQL; no FK cascade rules; no CHECK constraints; no indexes. That's writing-plans territory. Spec MAY enumerate likely new columns/tables as candidates but explicitly defer.
- **Code drafting** — no Python class definitions; no test code; no CLI command body code. The spec describes intent + architecture + open questions ONLY.
- **Sub-bundle decomposition** — that's writing-plans output. Brainstorm spec MAY group V1 into 2-4 logical phases (e.g., "auth + setup", "snapshot integration", "orders + reconciliation", "polish + handoff") but does NOT formalize as sub-bundles.
- **Order placement / cancellation** — Schwab API supports POST /accounts/{accountNumber}/orders; this project is operator-discretion + manual order placement at the broker. Automated order placement is **explicitly OUT OF SCOPE**. Brainstorm spec MUST explicitly disclaim this.
- **Option chains / fundamentals / instruments / streaming WebSocket endpoints** — out of V1 scope. V2 candidates; brainstorm explicitly defers.
- **Schwab Market Data API (`/quotes`, `/pricehistory`) — CONDITIONAL OUT-OF-SCOPE**: by default LOCKED OUT of V1; **but §2.9 Q11 surfaces this as operator-elective**. If operator triages V1 INCLUDE at post-brainstorm review, the writing-plans dispatch picks up market-data ladder scope. Brainstorm spec MUST present both branches per §1.9 + §2.9 Q11 — DO NOT silently lock either way.
- **Re-litigating source-ladder semantics** — already shipped per §1.1; brainstorm explicitly inherits.
- **Re-litigating reconciliation discrepancy types** — Phase 9 Sub-bundle B locked the 5 discrepancy types (close_price_mismatch, entry_price_mismatch, stop_mismatch, position_qty_mismatch, cash_movement_mismatch); Sub-bundle C added equity_delta + Sub-bundle D added sector_tamper. Schwab API may emit ANY of these existing types but does NOT introduce new types in V1.
- **Phase 11 candidate triage** — phase3e-todo enumerates Phase 11 candidates separate from Schwab API. Brainstorm focuses on Schwab.

---

## §4 Binding conventions

- **Branch:** `main`. Single commit for spec landing (no rogue commits; brainstorm session has no other artifacts).
- **Commit message:** `docs(schwab-api): integration brainstorm spec`. No Claude co-author footer. No `--no-verify`. No amending.
- **Spec location:** `docs/superpowers/specs/<YYYY-MM-DD>-schwab-api-design.md` where date is brainstorm-completion-date.
- **Spec format:** mirror `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; the most recent multi-source brainstorm spec). Section-numbered; locked decisions called out explicitly with rationale; open questions enumerated for orchestrator triage in §2.9.
- **Spec line target:** ~600–1100 lines. Tight is better than padded; if exceeding 1100, re-scope.
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. Default `MAX_ROUNDS=5`; if a 6th round produces ≤1 new Major + 0 new Critical, accept-with-rationale + document.
- **Schema posture:** spec proposes schema candidates (table names, column names, broad type) but does NOT lock SQL. Writing-plans owns the SQL.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **Source-ladder is consumed not designed.** Does the spec re-design source-ladder semantics? It MUST NOT — already shipped per §1.1 + §0 reads 7+8+9. Spec should explicitly inherit.
2. **Token redaction inherited verbatim from Finviz.** Are exception `__str__` contracts + urllib3 DEBUG-log suppression + cassette filter_headers + sentinel-leak audit explicitly called out? Or is the spec silently re-inventing?
3. **OAuth refresh-token rotation handled.** Does the spec address refresh_token expiry + Schwab's documented behavior of SOMETIMES rotating the refresh_token on POST /oauth/token? If silent, FAIL — operator's `swing schwab refresh` would silently leak the old refresh_token validity.
4. **Token storage discipline matches Phase 9 Sub-bundle A gotcha.** Does spec call out the user-config.toml USERPROFILE+HOME monkeypatch test discipline? Or assume tests "just work"?
5. **Multi-account question surfaced.** §1.6 + §2.9 Q3. Does the spec explicitly flag the question with default recommendation OR silently assume single-account?
6. **Order placement explicit-disclaim.** §3 disclaims POST /orders. Does the spec ALSO disclaim in §2 / §1 surfaces, or could a careless reader infer the architecture extends to order placement?
7. **Pipeline step ordering justified.** §2.3. Does the spec pick a pipeline step ordering AND justify it (not just enumerate options)?
8. **Failure tolerance matches Finviz precedent.** Does Schwab step failure abort the run or record `status='error'` and continue? Default per Finviz: continue. Spec must explicitly call out and not silently diverge.
9. **Sandbox vs production toggle.** §2.9 Q8. Does the spec design a clean toggle OR conflate them?
10. **Operator setup flow is concrete.** Can a fresh operator follow §2.8 + §2.1 setup steps without external Schwab docs reference? Specifically, does §2.1 enumerate the consent-URL scope strings + callback URL format + the `swing schwab setup` interactive prompts?
11. **Audit trail completeness.** §2.5. Does `schwab_api_calls` table candidate cover EVERY API call (not just snapshot-fetch — also auth-token-exchange, refresh-token-exchange, accounts-list)?
12. **Source-artifact reference shape for `record_snapshot`.** §2.4. What's the `source_artifact_path` value for a Schwab API snapshot? URL? Audit row ID? Combined? Spec must pick one.
13. **Cash-basis-vs-NLV semantics resolution.** §1.8 + §2.9 Q9. Does spec explicitly note that `account_equity_snapshots.equity_dollars` semantics REMAINS ambiguous at the column level (V2 follow-up) but is RESOLVED in practice by source-ladder + provenance?
14. **Empty-API-response handling.** Per CLAUDE.md gotcha "External-API empty-result must be treated as transient when write-through-caching" — does spec address how an empty Schwab response (e.g., transient outage) interacts with `record_snapshot` UPSERT? The append-or-fall-back pattern means: do NOT call `record_snapshot` on empty response; record `schwab_api_calls.status='error'` instead.
15. **Multi-account schema impact deferred.** §1.6 + §2.6. If multi-account = V1, schema changes are non-trivial (account_hash column on snapshots; possibly accounts table). Brainstorm flags impact for writing-plans without locking.
16. **JS-test-harness gap awareness.** No proposed surface uses HTMX form submission or HX-Redirect that would surface JS-test-harness-gap regression — Schwab integration is mostly CLI-driven; if any web surface is proposed, flag operator-witnessed gate requirement.
17. **CLI vs pipeline concurrency exclusion** (per Finviz §A.14). Does spec call out the `FinvizPipelineActiveError` precedent for `swing schwab fetch` while pipeline running? OR is it deemed unnecessary because Schwab writes are DB-only (no canonical filesystem artifact)?
18. **TOCTOU on token expiry.** Defensive token-refresh-on-step-entry (refresh if expires within 60s) — is the 60s window justified? Does spec account for clock-skew? OR for the operator running `swing schwab fetch` from CLI back-to-back where the second call's token is mid-expiry?
19. **Market-data ladder coherence with equity-snapshot ladder (§2.9 Q11 V1-INCLUDE branch only).** If brainstorm picks V1 INCLUDE for market-data ladder, does the design borrow the same `_SOURCE_PRECEDENCE` integer-lower-wins pattern from `swing/data/repos/account_equity_snapshots.py`? Does it use the same `with_provenance=True` dual-return shape so UI surfaces can render "Schwab quote at $X.XX superseded yfinance quote at $Y.YY (Δ=ZZ%)"? Inconsistent ladder semantics across two surfaces is a Codex-catchable smell.
20. **Empty-API-response handling for market-data ladder (V1 INCLUDE only).** Per CLAUDE.md gotcha — Schwab transient empty for `/pricehistory` MUST NOT auto-clobber yfinance OHLCV cache. The cache layer's source-tagged storage + the read-side ladder's "most-recent non-empty per source" semantics need explicit spec coverage.
21. **Premium-tier endpoint cost awareness (V1 INCLUDE only).** Schwab Market Data API may have premium-tier-only endpoints (e.g., real-time quotes vs delayed). Spec calls out the operator's tier (sandbox / Schwab brokerage account default tier / paid market-data subscription) + which endpoints are guaranteed at default-tier vs require subscription upgrade. Flag as operator-actionable §2.9 question.

---

## §6 Done criteria

1. Spec at `docs/superpowers/specs/<YYYY-MM-DD>-schwab-api-design.md` covering §2.1–§2.9.
2. Brainstorm went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`.
3. Spec section structure mirrors Phase 9 brainstorm spec format; locked decisions vs open questions explicitly delimited.
4. Single commit landed: `docs(schwab-api): integration brainstorm spec`.
5. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Schwab API integration brainstorm

### Spec location
`docs/superpowers/specs/<YYYY-MM-DD>-schwab-api-design.md` ({line count} lines)
Commit: {sha} `docs(schwab-api): integration brainstorm spec`

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR (after R{n})

### Three highest-leverage design decisions
1. ...
2. ...
3. ...

### Auth + token storage decision summary
- Initial-setup flow: {browser-redirect vs paste-token; localhost callback port choice}
- Token storage location: {user-config.toml vs sidecar JSON file}
- Refresh strategy: {background vs lazy}
- Encrypted at rest: {plaintext default per Finviz precedent / DPAPI / keyring}
- Revocation flow: {description}

### Pipeline integration decision summary
- New steps: `_step_schwab_snapshot` / `_step_schwab_orders` / etc.
- Step ordering: {justification}
- Failure tolerance: {abort vs continue}
- CLI surface: `swing schwab {fetch|status|setup|refresh|logout}` (whichever subset)

### Schema candidates (deferred to writing-plans)
- New tables: `schwab_oauth_state`, `schwab_api_calls`, ...
- New columns: `account_equity_snapshots.schwab_account_hash`, ...
- EXPECTED_SCHEMA_VERSION bump: 17 → 18

### Open questions for orchestrator triage (§2.9)
1. Q1: Schwab Developer Portal app status — {default: operator must verify before executing-plans}
2. Q2: Token storage encryption — {default recommendation: V1 plaintext}
3. Q3: Multi-account support — {default: V1 single-account}
4. Q4: Streaming vs batch-poll — {default: V1 batch-poll}
5. Q5: Operator UI — {default: V1 CLI-only}
6. Q6: Inception-CSV ingestion — {default: separate dispatch}
7. Q7: TOS CSV deprecation timing — {default: stays as V1 fallback}
8. Q8: Sandbox vs production toggle — {chosen architecture}
9. Q9: Cash-basis manual snapshot retention — {default: yes}
10. Q10: Pipeline step ordering — {chosen ordering with justification}
11. Q11: Market-data source-ladder (`schwab_api > yfinance`) V1 INCLUDE vs V1 EXCLUDE — {chosen branch + concrete consequences of unchosen branch}

### Inherited disciplines from Finviz precedent (verbatim)
- urllib3 DEBUG-log suppression context manager.
- Cassette `filter_headers=['authorization']` + `filter_query_parameters`.
- Sentinel-token-leak audit test pattern.
- Exception `__str__` contract.
- CLI vs pipeline concurrency exclusion (or explicit disclaim — see §5 watch item 17).

### Capture-needs feedback
- For Phase 8 brainstorm: {none — Phase 8 already shipped}
- For Phase 9 brainstorm: {none — Phase 9 already shipped}
- For Phase 10 metrics: {none — Phase 10 surfaces consume source-ladder transparently}
- For writing-plans dispatch: {enumerate everything writing-plans needs to firm up}
```

---

## §8 If you get stuck

- If §1 strategic-context constraints conflict with what Schwab Developer Portal docs propose, **§1 wins** (project state is authoritative; Schwab API docs describe possibilities, not requirements).
- If a Codex round produces a finding you can't disposition without operator input, **ACCEPT-with-rationale + flag explicitly in spec's §2.9 "open questions" section + return report**. Do not stall waiting for orchestrator clarification — the spec is design-stage; open questions are the right disposition for unresolved choices.
- If the spec exceeds ~1100 lines, you're probably over-designing — re-scope by deferring more to writing-plans (e.g., precise endpoint response shapes can be summary tables vs full JSON shape).
- DO NOT propose schema SQL. DO NOT write Python code. If you start drafting `CREATE TABLE schwab_oauth_state (...)` or `class SchwabClient:` then stop — those belong in writing-plans / executing-plans.
- If Schwab API publicly-documented endpoint shapes contradict each other across community-maintained references, **synthesize a working assumption + flag as §2.9 open question for operator-paired live verification at executing-plans Task 0.b** (mirror Finviz §A.1 precedent).
- If you encounter the "live API access blocks design verification" pattern (mirror Finviz §A.1), document the synthesis assumption + propose a Task 0.b live-verification gate for executing-plans dispatch — DO NOT halt the brainstorm.
- If operator-decision-pending scope grows large (>15 open questions), re-scope: brainstorm should resolve clear V1 architectural choices + leave only operator-judgment-or-Schwab-portal-verification questions open. Architectural sprawl in §2.9 is a brainstorm-quality smell.
