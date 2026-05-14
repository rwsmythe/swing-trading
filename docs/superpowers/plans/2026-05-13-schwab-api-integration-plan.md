# Schwab API Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `copowers:executing-plans` (which wraps `superpowers:subagent-driven-development` with adversarial Codex MCP review) to execute each sub-bundle as a SEPARATE dispatch. Tasks use checkbox (`- [ ]`) syntax for tracking. Dispatch order is **A → B → C → D**; sub-bundle inter-dependencies enumerated in §0.

**Goal:** Lock V1 architecture, file map, migration 0018 SQL, endpoint reference, sub-bundle decomposition, and per-task acceptance criteria for the Schwab Developer Portal API integration. Spec at `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`) is the canonical scope source; this plan converts spec architecture into executable sub-bundle dispatches.

**Architecture:** Thin project-side wrapper around `schwabdev` (Tyler Bowers; community-maintained Schwab Developer Portal Python wrapper) at `swing/integrations/schwab/`; per-environment SQLite token DB managed by schwabdev's `Tokens` class; OAuth 2.0 paste-back setup flow only (V1; schwabdev does not ship a localhost listener); new `schwab_api_calls` audit table with INSERT-in-flight + UPDATE-on-completion lifecycle; pipeline integration via two new steps (`_step_schwab_snapshot` + `_step_schwab_orders`) inserted AFTER `_step_recommendations` and BEFORE `_step_charts`; Market Data API ladder over yfinance via per-`(ticker, provider)` parquet shape (Shape A per spec §3.8.2); source-ladder write path INHERITED from Phase 9 Sub-bundle C (`record_snapshot(source='schwab_api', ...)` + `run_schwab_reconciliation(...)`); production-only domain writes gated caller-side on `cfg.integrations.schwab.environment == 'production'`.

**Tech Stack:** Python 3.14; `schwabdev` (NEW runtime dependency); `requests` (transitive); existing project stack — FastAPI + HTMX (web; not touched V1); SQLite + custom migration runner (Phase 9 `_apply_migration` discipline); `pytest-recording` (cassette-driven HTTP tests; Finviz precedent); `pyarrow` (Shape A parquet-per-(ticker, provider); already present via `swing/data/ohlcv_archive.py`).

---

## §0 Sub-bundle decomposition + dispatch ordering

### §0.1 Final shape: 4 sub-bundles

| # | Sub-bundle | Scope summary | Inter-bundle deps |
|---|---|---|---|
| **A** | schwabdev wrap + auth + migration 0018 + `schwab_api_calls` audit infrastructure + CLI `schwab setup/refresh/logout/status` (skeleton; full status surface in D) | Foundational. Lands migration 0018, the new `swing/integrations/schwab/` sub-package, the `schwabdev` runtime dependency, the OAuth paste-back flow, the per-env SQLite token DB resolution, sandbox-vs-production cfg field, audit-row INSERT/UPDATE service, `pyproject.toml` dep bump. | NONE (foundational). |
| **B** | Trader API endpoint methods + `_step_schwab_snapshot` + `_step_schwab_orders` + `run_schwab_reconciliation` service + sandbox-gating discipline + CLI `schwab fetch --snapshot/--orders/--all` + `SchwabPipelineActiveError` cross-surface exclusion | Wires snapshot writes via `record_snapshot(source='schwab_api', ...)` and reconciliation writes via new `run_schwab_reconciliation()` service paralleling `run_tos_reconciliation`. Reuses Phase 9 Sub-bundle B discrepancy-emit machinery (no new types). | Depends on A (audit infra + auth + migration). |
| **C** | Market Data API endpoint methods + Shape A parquet-per-(ticker, provider) persistence + `PriceCache` `provider` field + `OhlcvCache`/`ohlcv_archive` per-provider files + ladder integration into `_step_evaluate` + `_step_charts` + `swing schwab fetch --verify-marketdata` CLI subcommand + sandbox cache short-circuit | Implements V1 INCLUDE branch per spec §3.8. Wraps existing cache fetcher paths in a "Schwab → yfinance fallback" ladder. yfinance gotcha-hardened code path preserved as fallback. | Depends on A (audit infra + auth). Independent of B. |
| **D** | `swing schwab status` full per-environment surface + `briefing.md` "Schwab integration: degraded" banner + E2E happy-path integration test (mirror Phase 9 Sub-bundle E precedent) + cycle-checklist updates + CLAUDE.md additions + Phase 11 hand-off prep | Polish + observability + handoff. Closes the arc. | Depends on A + B + C. |

### §0.2 Rationale for 4 sub-bundles (vs spec §0.7's 3-5 estimate)

- **Why not 3:** auth + audit infra (Bundle A) cannot share a dispatch with Trader API consumption (Bundle B) because the audit-row UPDATE lifecycle is the contract that Bundle B's `_step_schwab_*` calls consume, and the migration must land first. Market Data path (Bundle C) is a cache-layer rewrite scope-distinct from Trader API; mixing into one dispatch produces an unwieldy implementer payload (>40 tasks; >150 expected tests).
- **Why not 5:** spec §0.7 sketched a separate "audit + observability" Sub-bundle D. Under COA B that scope collapses — schwabdev owns most of the auth surface; the audit-row INSERT/UPDATE service is small enough to ship with A; the `swing schwab status` per-environment polish is a cosmetic CLI surface best bundled with the closer (Bundle D). 4 bundles balances dispatch granularity against orchestrator overhead (each dispatch is one Codex review chain; minimizing dispatches reduces redundant Codex context-reload cost).
- **Phase 9 + Phase 10 arc precedent:** 5-bundle Phase 9 + 5-bundle Phase 10 each accumulated ~500 fast tests; Schwab is smaller scope than Phase 9 + 10. 4 bundles, ~230-350 fast tests projected (mid-range +280), matches the empirical ratio.

### §0.3 Dispatch ordering — STRICT A → B → C → D

- **A is BLOCKING for B + C** — migration 0018 lands `schwab_api_calls` table; B+C wrap calls in the audit lifecycle; cannot run without it. A also lands the `cfg.integrations.schwab.environment` field that B's sandbox-gate and C's cache-short-circuit both read.
- **B and C are FUNCTIONALLY INDEPENDENT** but SHARE FILES (Codex R1 Minor #5 surfaced). Both bundles extend `swing/cli/schwab.py` (B adds `fetch --snapshot|--orders|--all` Click options; C adds `fetch --verify-marketdata` Click option) AND both extend `swing/integrations/schwab/mappers.py` (B adds Trader response mappers; C adds Market Data response mappers). The Click options are non-overlapping (different flag names + handlers); the mapper functions are also non-overlapping. **Sequential B → C dispatch avoids merge conflicts trivially.** Operator-witnessed gates require manual Schwab API verification at Task 0.b in EACH dispatch, and operator cannot reasonably run two paired-verification sessions simultaneously. Sequential B → C is the realistic ordering for that reason too. **No technical reason to enforce B before C** other than (a) shared-file merge convenience + (b) operator-bandwidth.
- **D is BLOCKING on all three** — E2E integration test exercises the full happy-path (auth → snapshot → orders → reconciliation → market-data cache → briefing render); needs all upstream surfaces shipped.

### §0.4 Per-bundle Codex round estimates

Based on Phase 9 + Phase 10 + Finviz precedent:
- A: 4-5 rounds (schwabdev wrapping discipline + per-env config + audit lifecycle + migration are 4 axes of attack; expect Codex to find ≥1 issue per).
- B: 3-4 rounds (Trader API endpoint wiring is well-understood; sandbox-gating discipline is well-trodden post-spec).
- C: 4-5 rounds (cache layer rewrite is the largest novel scope; ladder semantics + parquet shape A persistence + yfinance fallback discipline + sandbox short-circuit each invite Codex attention).
- D: 2-3 rounds (mostly polish + E2E + docs).

**Total estimate: ~13-17 Codex rounds across the arc**, matching Phase 9 (19) + Phase 10 (13).

### §0.5 Test-count projection per bundle

| Bundle | Tests added (CORRECTED per Codex R1 Major #8 + R10 Minor #1 range widening for A) | Cumulative running total (from baseline 3287) |
|---|---|---|
| A | +100..+135 (R10 Minor #1 widened upper bound from 125 to 135; cumulative R7-R9 redactor-design iterations pushed A to +126) | 3387..3422 |
| B | +75..+95 | 3462..3517 |
| C | +60..+80 | 3522..3597 |
| D | +15..+30 | 3537..3627 |
| **Arc total** | **+250..+340** | **~3537..~3627** |

(Per-bundle §Tasks-* sections enumerate per-task test counts that sum to mid-range estimates after R2-R9 Codex iterations: A=126; B=80; C=68; D=19; total=293. Range bounds above accommodate further Codex-round-driven discovery + integration-test scope expansion. Per Phase 9 + 10 precedent, actual lands at the upper end.)

Per Phase 9 + 10 precedent, actual lands at upper end (Phase 9 was +503 vs +260 projection; Phase 10 was +494 vs +285 projection). Realistic upper-bound for Schwab arc: ~3600-3700 main HEAD post-D.

### §0.6 Sub-bundle scope shrink under COA B

Per dispatch brief §0.3a + §0.7: spec §0.7's per-bundle scope estimate assumed COA C (roll our own OAuth + token storage + file-lock). COA B substitutes schwabdev for those three surfaces, materially shrinking Sub-bundle A:

- **Spec §3.2.1 OAuth flow (~step 4 HTTPS listener + step 7 token exchange + step 10 sidecar write) → schwabdev's `auth.manual_flow()` + `Tokens(tokens_db=...)` paste-back constructor.** Net A scope: 1 wrapper function around schwabdev's manual flow, NOT a from-scratch OAuth implementation. **Tasks saved: ~6-8 T-A.* tasks (custom OAuth + listener + cert + state-file write/atomic-replace + refresh-loop + file-lock).** Replaced by 1-2 tasks (schwabdev wrapping + paste-back UX polish).
- **Spec §3.2.2 sidecar JSON file format + schema → schwabdev SQLite DB.** Net A scope: zero design work on the token-store schema (schwabdev owns it).
- **Spec §3.2.4 file-lock cross-platform shim → schwabdev's `RLock` + SQLite `BEGIN EXCLUSIVE`.** **Tasks saved: 2-3 T-A.* tasks** (file-lock shim + cross-platform tests + concurrent-refresh race regression). Replaced by 1 task (verify schwabdev's concurrency model satisfies our `SchwabConcurrentRefreshError` contract; document the inheritance).

Sub-bundles B+C are unaffected by COA B (they consume the auth surface, not design it).

### §0.7 Brief deviations from dispatch brief

Plan deviates from dispatch brief in ONE direction worth flagging here (full list in §3.X-flagged sections):
- Brief §0.7 estimated "Likely Sub-bundle D: Audit trail + observability + `swing schwab status`". Plan FOLDS that scope into Sub-bundle A (audit infra) + Sub-bundle D-polish (status full surface). Justified because A must land the audit-row contract that B+C consume; splitting it from B+C would require A to ship a stub-only audit and then re-touch A's files during D, breaking the file-isolation discipline the orchestrator enforces.

---

## §A Resolved-during-planning items

### §A.0 Empirical schema verification (BINDING — verified at plan-authoring time)

Per dispatch brief §0.6, the plan §A locks the following empirical findings at HEAD `9fd50e6`:

1. **Migration 0017 is the latest.** `ls swing/data/migrations/00*.sql | tail -1` returns `0017_phase9_risk_policy_and_reconciliation.sql`. **Migration 0018 is the next available number.**
2. **`schwab_api_calls` table is NEW.** `grep -i schwab_api_calls swing/data/migrations/*.sql` returns nothing.
3. **`account_equity_snapshots.schwab_account_hash` column is NEW.** `grep -i schwab_account_hash swing/data/migrations/*.sql` returns nothing.
4. **`reconciliation_runs.schwab_api_call_id` column is NEW.** Same grep returns nothing.
5. **CHECK enums already permit `'schwab_api'`:**
   - `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql:194` — `reconciliation_runs.source IN ('tos_csv', 'schwab_api', 'manual', 'system_audit')`.
   - `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql:332` — `account_equity_snapshots.source IN ('manual', 'schwab_api', 'tos_csv')`.
   - **NO ALTER on either CHECK enum is needed for migration 0018.**
6. **`EXPECTED_SCHEMA_VERSION = 17`** at `swing/data/db.py:19`. **Migration 0018 lands version 18; plan T-A.7 bumps the constant.**
7. **No FK CASCADE risk** introduced by 0018 ALTERs. `schwab_account_hash` is `TEXT NULL`; `schwab_api_call_id` is `INTEGER NULL` with optional FK to `schwab_api_calls(call_id)` (plan elects ADD FK with `ON DELETE SET NULL` — see §C.3 below; FK is non-cascading so no risk).

### §A.1 Q1-Q17 disposition wiring (per dispatch brief §0.3)

All 17 operator-confirmed dispositions wired into plan acceptance criteria. Summary:

| # | Question | Disposition | Plan section wiring |
|---|---|---|---|
| **Q1** | Schwab Dev Portal app status | Production-tier approved; sandbox-registration deferred to executing-plans Task 0.b | §7 §A.3; §K Task 0.b; default `environment='production'` in cfg cascade |
| **Q2** | Token encryption | V1 plaintext (schwabdev plaintext mode); V2 Fernet candidate documented | §A.6; §H §2.1 setup |
| **Q3** | Multi-account | V1 single-primary | §A.5; T-A.4 setup flow elects primary account_hash |
| **Q4** | Streaming | V1 batch-poll only | §A.10; spec §1.2 disclaim consumed verbatim |
| **Q5** | Operator UI | V1 CLI-only | §A.10; no HTMX surfaces |
| **Q6** | Schwab inception-CSV | Separate dispatch | §A.11; phase3e-todo backlog reference |
| **Q7** | TOS deprecation | V1 fallback retained | §A.4; reconciliation parser unchanged |
| **Q8** | Sandbox vs prod HTTP differentiation | DEFERRED to Task 0.b | §D.1 open question; plan-author synthesizes default `base_url` derivation in §H §H.3 |
| **Q9** | Cash-basis manual snapshot retention | Retained | §A.4; existing CLI surface unchanged |
| **Q10** | Pipeline step ordering | AFTER `_step_recommendations`, BEFORE `_step_charts` | §H §H.4 ordering algorithm |
| **Q11** | Market-data ladder V1 INCLUDE | V1 INCLUDE | Sub-bundle C scope; §H §H.6 |
| **Q12** | Premium-tier Market Data | DEFERRED to Task 0.b | §D.2 open question; default = default-tier delayed quotes |
| **Q13** | OAuth callback | LOCKED paste-back-only V1 by COA B (Q18 supersession); operator-UX-friction observation only at Task 0.b (residual; Codex R1 Minor #2 wording fix) | §D.3 residual observation; §H §H.1 setup algorithm |
| **Q14** | OAuth scope-string | DEFERRED to Task 0.b | §D.4 open question; default `readonly` per Schwab convention |
| **Q15** | Refresh-token rotation | DEFERRED to Task 0.b | §D.5 open question; schwabdev handles rotation explicitly per `tokens.py:207` |
| **Q16** | `schwab_account_hash` V1 add | V1 ADD on `account_equity_snapshots` | §C.2 migration; §A.7 forward-prep multi-account |
| **Q17** | Market Data rate limits | DEFERRED to Task 0.b | §D.6 open question; synthesized default = Trader-API-comparable |

### §A.2 Q18 build-vs-buy — COA B (`schwabdev`) LOCKED

Per dispatch brief §0.3a (operator-confirmed 2026-05-13 post-brainstorm-gap triage):

**Library:** [`schwabdev`](https://github.com/tylerebowers/Schwabdev) added as project runtime dependency (NOT dev-extra). Pinned version range: `schwabdev>=2.4.0,<3.0.0` (T-A.1 verifies latest published version at executing-plans time; pins to a minor-version range to allow patch-version uptake while gating major-version bumps).

**Wrapping discipline:** new `swing/integrations/schwab/` sub-package wraps `schwabdev.Client` thinly. Concretely (algorithm in §H):

- New `SchwabClient` wrapper class at `swing/integrations/schwab/client.py` holds an instance of `schwabdev.Client` (composition, NOT subclassing).
- Every `SchwabClient.<endpoint_method>()` invocation wraps the underlying `schwabdev.client.<endpoint_method>` call in:
  1. Pre-call: INSERT `schwab_api_calls` row with `status='in_flight'`.
  2. Call: invoke schwabdev method inside `with _suppress_transport_debug_logs():` block (URL still contains `account_hash` segment which is sensitive).
  3. Post-call: UPDATE audit row with HTTP status + response_time_ms + signature_hash + status enum.
  4. Domain-write path (Bundle B + C only): if response→domain mapping succeeds and we're in production env, invoke `record_snapshot(source='schwab_api', ...)` or `run_schwab_reconciliation(...)`; then UPDATE audit row with `linked_*_id`.
- Token storage = schwabdev's per-env SQLite DB at `~/swing-data/schwab-tokens.{sandbox,production}.db` (path passed as constructor parameter `tokens_db=...`).
- Token redaction discipline extends to schwabdev's loggers + known caveat at `schwabdev/tokens.py:~338` which logs `response.text` on auth failure (could include token-related error details). **§K T-A.10 sentinel-leak audit test asserts schwabdev's logger output is also token-redaction-safe.**

**Spec sections SUPERSEDED by COA B** (per dispatch brief §0.3a verbatim, restated here for plan-internal record):

| Spec section | COA B disposition |
|---|---|
| §3.1 module layout | Thin wrapper around `schwabdev.Client`; sub-package shape unchanged. |
| §3.2.1 setup flow | Paste-back only V1 (`localhost` variant DROPPED). |
| §3.2.2 token storage | Per-env SQLite DB via `schwabdev.tokens.Tokens(tokens_db=...)`; sidecar JSON DROPPED. |
| §3.2.3 token refresh | Schwabdev's hybrid lazy + proactive `_checker()` + 61s/3630s thresholds. **Better than spec.** |
| §3.2.4 concurrency | Schwabdev's `RLock` + SQLite `BEGIN EXCLUSIVE`; custom file-lock shim DROPPED. |
| §3.2.5 revocation | `swing schwab logout` deletes the per-env SQLite DB file atomically (rename-then-unlink). |
| §3.3 endpoint catalogs | Call schwabdev method signatures; raw HTTP details inside schwabdev. Plan §E enumerates schwabdev call signatures + our normalization mappers. |
| §3.5 CLI surface | `swing schwab setup` wraps `schwabdev.auth.manual_flow()`; `refresh` wraps `update_tokens(force_refresh_token=True)`; `status` reads from `schwab_api_calls` + schwabdev's `Tokens` DB metadata. |
| §5 token redaction | Cassette discipline same; sentinel-leak audit EXTENDS to schwabdev's loggers per §A.2 above. |
| §3.6 audit lifecycle | UNCHANGED. Wrap every schwabdev call with INSERT/UPDATE pattern. |
| §3.6.3 production-only domain writes | UNCHANGED. Caller-side gate before invoking schwabdev calls OR before invoking record_snapshot/run_schwab_reconciliation. |
| §3.7 source-ladder write path | UNCHANGED. Schwabdev returns parsed dicts; mapper.py emits normalized dataclasses; service-layer calls `record_snapshot` verbatim. |
| §3.8 market-data ladder | UNCHANGED in design. Schwab-via-schwabdev first; yfinance fallback same. Shape A persistence locked per §A.8. |
| Q2 token encryption | OPTIONAL Fernet encryption now available V1 via schwabdev's `encryption=<key>` constructor; plan recommends V1 plaintext + V2 Fernet (per spec disposition). |
| Q13 callback localhost vs paste | LOCKED paste-back-only V1 (schwabdev does not ship a localhost listener). |
| Q15 refresh-token rotation | Schwabdev's tokens.py:207 handles rotation explicitly; Task 0.b operator-witnessed verification simplified. |

**Spec sections UNAFFECTED by COA B** (plan implements per spec verbatim): §3.4 pipeline integration; §3.6 audit-trail completeness contract; §3.6.2 audit-write surface boundary (web_page_render UNAUDITED V1); §3.6.3 production-only domain writes; §3.7 source-ladder; §3.8 market-data ladder design; §4 schema candidates; §6 failure-mode catalog; §7 operator setup flow; §9 watch items.

### §A.3 Production-only domain writes — V1 default `environment='production'`

Per dispatch brief §0.3 Q1 + spec §3.6.3 + §10.1: operator's Schwab Developer Portal app is approved at production tier. V1 default for `cfg.integrations.schwab.environment` is `'production'` (NOT `'sandbox'` as spec §3.2.1 step 2 default had it pre-Q1-resolution). Sandbox registration is deferred to executing-plans Task 0.b operator decision — if operator elects to register a sandbox app for cassette-recording purposes, Task 0.b runbook covers; otherwise Task 0.b's cassette-recording session uses production-tier credentials directly with sentinel-redacted bodies.

**Sandbox vs production behavior matrix per surface (CLARIFIED per Codex R1 Major #2 — three distinct surface-level policies; do NOT conflate):**

| Surface | Sandbox behavior | Production behavior | Spec ref |
|---|---|---|---|
| `_step_schwab_snapshot` (pipeline Trader API) | CALL Schwab; WRITE `schwab_api_calls` audit; SKIP `record_snapshot()` (no domain row); `linked_snapshot_id` stays NULL | CALL; WRITE audit; WRITE domain via `record_snapshot(source='schwab_api', ...)`; UPDATE `linked_snapshot_id` | §3.6.3; §H.4.1 |
| `_step_schwab_orders` (pipeline Trader API) | CALL; WRITE audit (×3 calls); SKIP `run_schwab_reconciliation()` | CALL; WRITE audit; WRITE `reconciliation_runs` + discrepancies; UPDATE `linked_reconciliation_run_id` | §3.6.3; §H.4.2 |
| `PriceCache` / `OhlcvCache` cache-fill in `_step_evaluate` + `_step_charts` (pipeline Market Data) | **SKIP Schwab entirely**; fall through directly to yfinance; **NO audit row written** for the Schwab call (it never happens) | CALL Schwab via ladder; WRITE audit; on success WRITE cache+parquet; on failure FALL BACK to yfinance | §3.6.3; §3.8; §H.6.1; §H.6.2 |
| `swing schwab fetch --snapshot` / `--orders` / `--all` (CLI Trader API) | CALL; WRITE audit; SKIP domain (same as pipeline counterparts) | CALL; WRITE audit; WRITE domain | §3.6.3; §H.4 |
| `swing schwab fetch --verify-marketdata` (CLI Market Data verification mode) | CALL Schwab; WRITE audit; SKIP cache writes (verification-only by design — operator-invoked diagnostic, NOT a cache-warm path) | CALL Schwab; WRITE audit; SKIP cache writes (same as sandbox — the `--verify-marketdata` flag is env-independent verification-only) | §3.6.3 final bullet |

Rationale per surface:
- **Trader API surfaces** call Schwab in sandbox because audit-row + signature_hash drift detection is the value of running a sandbox-mode call; domain-write skip is the gate.
- **Market-data cache-fill in pipeline** SKIPs Schwab in sandbox because the ladder caller has no use for a sandbox-quote-value-going-into-cache — operators expect real prices in cache; falling through to yfinance gives consistent behavior across env-flips without polluting cache or audit.
- **`--verify-marketdata`** is an OPERATOR-INVOKED diagnostic for cassette recording + endpoint shape verification. Env-independent: always calls + always audits + always skips cache. Operator explicitly invokes this when they want to verify the Schwab path is healthy without committing data.

Discriminating test patterns (§K T-B.7 + T-C.3 + T-C.5 acceptance):

- **Trader API sandbox-gate:** plant `cfg.integrations.schwab.environment = 'sandbox'`; run `_step_schwab_snapshot` against a cassette returning known NLV; assert `schwab_api_calls` row exists with `status='success'` AND `account_equity_snapshots` table has ZERO rows added for the call's `snapshot_date`.
- **Trader API production-path:** plant `environment = 'production'`; same cassette; assert `account_equity_snapshots` row exists with `equity_dollars` matching cassette NLV value + `linked_snapshot_id` populated.
- **Market-data cache-fill sandbox short-circuit:** plant `environment = 'sandbox'`; invoke `PriceCache.get_latest('AAPL')`; assert ZERO new `schwab_api_calls` rows AND `PriceCacheEntry.provider == 'yfinance'`.
- **`--verify-marketdata` env-independence:** plant both env values; run `swing schwab fetch --verify-marketdata --symbols AAPL`; assert audit row written in BOTH cases + ZERO cache writes in both cases.

### §A.4 Source-ladder consumer inheritance — VERBATIM

Per dispatch brief §0.4 + spec §1.3 #1 + §3.7. Plan consumes Phase 9 Sub-bundle C source-ladder write helpers WITHOUT MODIFICATION:

- `swing/data/repos/account_equity_snapshots.py:_SOURCE_PRECEDENCE` (line 38) — `{schwab_api: 0, tos_csv: 1, manual: 2}` — VERIFIED at planning time; ladder permits Schwab winning over manual + TOS for the same date.
- `swing/data/repos/account_equity_snapshots.py:get_latest_snapshot_on_or_before` (line 130) — `with_provenance=True` returns `(winner, suppressed)` for source-ladder UI; consumed transparently by Phase 10 capital-friction PROVISIONAL/LIVE badge.
- `swing/trades/account_equity_snapshots.py:record_snapshot` (line 66) — accepts `source: str` parameter; UPSERT semantics on `(snapshot_date, source)` already shipped; `CallerHeldTransactionError` discipline already in force (caller must NOT hold an open transaction; service owns BEGIN IMMEDIATE / COMMIT / ROLLBACK).
- `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql:194 + 332` — CHECK enums already permit `'schwab_api'` per §A.0 #5.

**Plan acceptance criteria (BINDING; Codex R1 watch-item 1 attack surface):**

- Every Schwab API snapshot write call site (`_step_schwab_snapshot`; CLI `swing schwab fetch --snapshot`) invokes `record_snapshot(conn, equity_dollars=<NLV>, snapshot_date=<last_completed_session(now)>, source='schwab_api', source_artifact_path=f'schwab_api:call/{call_id}', recorded_by='schwab_api', notes=None)` verbatim. NO new write paths.
- Every Schwab API reconciliation write call site invokes the NEW service-layer function `run_schwab_reconciliation(...)` at `swing/trades/schwab_reconciliation.py` (new file; mirrors `run_tos_reconciliation` shape verbatim per §B.2 + §H.5). NO new precedence-resolution code; NO modification to `_SOURCE_PRECEDENCE`; NO modification to `get_latest_snapshot_on_or_before`.
- Reconciliation discrepancy emission uses Phase 9 Sub-bundle B's `MATERIAL_BY_TYPE` lookup + 10-type enum + 5-resolution enum AS-SHIPPED. **No new discrepancy types.** Plan §H §H.5 enumerates which existing types Schwab data emits: `close_price_mismatch`, `entry_price_mismatch`, `stop_mismatch`, `position_qty_mismatch`, `cash_movement_mismatch`, `equity_delta`, `unmatched_open_fill`, `unmatched_close_fill`. (Per spec §3.7: `sector_tamper` + `snapshot_mismatch` are NOT Schwab-emitted — those are operator-tamper and manual-entry families respectively.)

### §A.5 Multi-account V1 single-primary-account (Q3 default)

Plan implements: at `swing schwab setup`, after schwabdev's `manual_flow()` completes + `Tokens` DB persists, CLI calls `schwabdev.Client.account_linked()` (or equivalent — verify at Task 0.b per §D.4) to fetch the linked-account-hash set. If multiple hashes returned, CLI prompts operator to pick a primary; persists choice via `swing config set integrations.schwab.account_hash <hash>` (NEW config field; §A.6 enumerates the cfg cascade additions). If single hash returned, auto-picks; informs operator.

Primary account_hash is read by `_step_schwab_snapshot` + `_step_schwab_orders` + every `swing schwab fetch` subcommand from `cfg.integrations.schwab.account_hash`. **No env-derivation:** account_hash is associated with the schwabdev tokens DB (one hash per env per registered app); per-env tokens DB keeps the hash bound to its env naturally. Multi-account V2 = separate dispatch (per Q3 default).

### §A.6 `cfg.integrations.schwab` cfg cascade (NEW)

Per Phase 5 + Phase 9 cfg-cascade precedent (`swing/config.py:Config` dataclass + `[integrations.<name>]` TOML section + Phase 5 user-config override cascade + `swing config show` + `swing config set` CLI plumbing).

**New cfg sub-dataclass** at `swing/config.py` (T-A.2 implements):

| Field | Type | Default | Source | Sensitivity |
|---|---|---|---|---|
| `environment` | `Literal['sandbox', 'production']` | `'production'` | user-config.toml `[integrations.schwab].environment` | NON-sensitive (cfg-public; not in tokens DB) |
| `account_hash` | `str \| None` | `None` (operator picks at setup) | user-config.toml | sensitive — surfaces masked in `swing config show` (per Phase 5 FIELD_REGISTRY pattern) |
| `lookback_days` | `int` | `7` (matches TOS path; spec §3.4.1 default) | user-config.toml | NON-sensitive |
| `timeout_seconds` | `float` | `30.0` (mirrors Finviz default) | swing.config.toml (tracked) | NON-sensitive |
| `marketdata_ladder_enabled` | `bool` | `True` (V1 INCLUDE per Q11) | swing.config.toml | NON-sensitive |

**NOT in cfg cascade (operator NEVER edits these):**
- `client_id`, `client_secret`, `access_token`, `refresh_token`, `access_token_expires_at`, `refresh_token_expires_at` — all owned by schwabdev's per-env Tokens DB at `~/swing-data/schwab-tokens.{env}.db`. Operator rotates via `swing schwab setup`/`logout`.

**`swing config show` masking discipline** (§K T-A.6 acceptance criterion):
- `account_hash` rendered as `1A2***9F` (first 3 + asterisks + last 2 chars; mirror spec §3.5 mock).
- Other Schwab cfg fields rendered verbatim (none are sensitive).

### §A.7 `account_equity_snapshots.schwab_account_hash` column V1 ADD (Q16 disposition)

Per dispatch brief §0.3 Q16 + spec §10.16 + §4.3. Migration 0018 ALTERs `account_equity_snapshots` with `schwab_account_hash TEXT NULL` (NULL-permissible). V1 single-account: column populated with the single primary account_hash for every `source='schwab_api'` row; NULL for `source IN ('manual','tos_csv')` rows. Forward-prep for V2 multi-account dispatch (which will add UNIQUE INDEX scoping + per-account snapshot read paths).

Discriminating test pattern (§K T-A.5 acceptance criterion):
- Insert `source='manual'` snapshot → `schwab_account_hash` is NULL.
- Insert `source='schwab_api'` snapshot via Bundle B's `_step_schwab_snapshot` → `schwab_account_hash` is populated with the primary account_hash value.
- Phase 10 capital-friction read path (which already consumes `get_latest_snapshot_on_or_before(with_provenance=True)`) is UNCHANGED — no read-side change required.

### §A.8 Market-data ladder persistence Shape A LOCKED (spec §3.8.2 default)

Plan locks **Shape A: parquet-per-(ticker, provider)**. Files at `swing-data/ohlcv-archive/{TICKER}.{PROVIDER}.parquet`. Resolver function at `swing/data/ohlcv_archive.py:resolve_ohlcv_window(ticker, start, end)` reads both Schwab + yfinance parquet files (if present), picks higher-precedence row per `(ticker, asof_date)` via `_SOURCE_PRECEDENCE_MARKET_DATA = {'schwab_api': 0, 'yfinance': 1}`.

**Rationale:**
- Cleanest separation; resolver code is small (~50 LOC merge function).
- No SQL migration for the OHLCV path (migration 0018 stays scoped to audit + ALTERs; no `ohlcv_cache_persistent` table).
- Per-provider files are operator-greppable (`ls swing-data/ohlcv-archive/*.schwab_api.parquet` enumerates Schwab-sourced cache).
- Matches Phase 9 Sub-bundle C source-ladder pattern (lower-integer wins; provenance available at read time).
- Avoids the migration + CHECK enum work Shape B would entail.
- Lower complexity than Shape C (provider column inside single parquet; archive helper merge complexity).

**Downstream impact:** Sub-bundle C scope includes:
- New `_SOURCE_PRECEDENCE_MARKET_DATA` constant at `swing/data/ohlcv_archive.py` (or shared module if `PriceCache` consumes it too).
- Filename change in `swing/data/ohlcv_archive.py` from `{TICKER}.parquet` to `{TICKER}.{PROVIDER}.parquet`. **Backward-compat migration step (T-C.4)**: rename existing `{TICKER}.parquet` to `{TICKER}.yfinance.parquet` at first read (idempotent; one-time per ticker; no data loss).
- New resolver function `resolve_ohlcv_window(ticker, start, end)` merging the two providers.
- `PriceCache` (`swing/web/price_cache.py`) gains a `provider` field on `PriceCacheEntry` dataclass DISTINCT from the existing `source` TTL-state field (per spec §3.8.2 — NO renaming of `source` field; existing test fixtures depend on it).
- Cache-fill fetcher path becomes "try schwabdev market-data → on failure/empty/rate-limit fall back to yfinance". Cache entry tagged with `provider`.
- Sandbox short-circuit: under `environment='sandbox'`, cache fetcher SKIPS schwabdev call (cache populated by yfinance only); per spec §3.6.3.

### §A.9 Phase 9 + Phase 10 inherited disciplines (BINDING)

Per dispatch brief §0.5 (11 lessons) + CLAUDE.md gotchas through `9d4edfc`. Plan acceptance criteria for the executing-plans implementer:

1. **`__post_init__` validator pattern on all new dataclasses.** New: `SchwabApiCall`, `SchwabAccountResponse`, `SchwabOrderResponse`, `SchwabTransactionResponse`, `SchwabQuoteResponse`, `SchwabPriceHistoryWindow`, `PriceCacheEntry` (extension; existing field), `OhlcvCacheEntry`. Each rejects NaN/inf/out-of-range values at construction. §H §H.7 enumerates per-dataclass validator rules.
2. **Service-layer transaction discipline.** New services: `record_schwab_api_call_start` (audit-row INSERT), `record_schwab_api_call_finish` (audit-row UPDATE), `run_schwab_reconciliation` (mirrors `run_tos_reconciliation`). All three OWN BEGIN IMMEDIATE / COMMIT / ROLLBACK; all three REJECT caller-held transactions (raise `CallerHeldTransactionError`); none auto-detect. **NEW Codex watch item:** also covers `update_schwab_api_call_linked_id` (the post-domain-write linkage UPDATE) — same contract.
3. **NO `INSERT OR REPLACE` on `schwab_api_calls`.** Audit-trail table; UPSERT (if needed for any reason) MUST be SELECT-then-UPDATE-or-INSERT. **Plan acceptance:** NO `REPLACE INTO` or `INSERT OR REPLACE` SQL anywhere in §C.1 or anywhere the executing-plans implementer touches the audit table. Discriminating test at T-A.9 plants an in-flight row + finishes it via UPDATE; asserts PK unchanged (REPLACE semantics would re-issue PK).
4. **Server-stamping discipline at handler entry.** CLI surface (Bundle A T-A.4 setup; T-A.5 refresh; T-A.8 status; Bundle B T-B.5 fetch subcommands) server-stamps `ts` (now_ms) + `pipeline_run_id` (if applicable) + `surface` (`'pipeline'` or `'cli'`) at handler entry. NO hidden inputs (N/A here — CLI; no HTMX forms V1).
5. **Composition-surface enumeration via `^def` grep, NOT memory-enumerate.** Spec section + plan section enumerating "every call site of schwabdev calls" MUST be grep-verified before locking; orchestrator brief locks the grep command pattern. Plan §K T-A.10 sentinel-leak audit grep pattern enumerated.
6. **Empirical verification of brief assertions before locking.** Plan §A.0 verifies the 7 brief claims at HEAD `9fd50e6`. Executing-plans implementer re-verifies at dispatch time (HEAD may have advanced).
7. **HTMX browser-only failure surfaces.** Plan does NOT introduce new HTMX surfaces (Q5: V1 CLI-only). Briefing.md degraded banner is a Markdown render, NOT an HTMX form. NO operator-witnessed browser gate required for any sub-bundle.
8. **Test fixtures exercising `write_user_overrides` MUST monkeypatch USERPROFILE + HOME.** Applies to TWO distinct surfaces (CORRECTED per Codex R1 Minor #1 — earlier text excluded schwabdev path; both surfaces require monkeypatch for different reasons):
   - **(a) user-config.toml write path** (`write_user_overrides`): Phase 9 Sub-bundle A lesson — tests that write `cfg.integrations.schwab.environment` or `account_hash` through `apply_overrides` would otherwise pollute the operator's real `~/swing-data/user-config.toml`. Affected tests: T-A.2 (cfg cascade), T-A.3 (CLI config-set tests), T-A.4 (setup writes account_hash).
   - **(b) schwabdev Tokens DB path resolution** (`_user_home()` helper): tests that exercise `Path(_user_home()) / "swing-data" / f"schwab-tokens.{env}.db"` resolution would otherwise create a real `schwab-tokens.*.db` file under the operator's actual home. Affected tests: T-A.3 (SchwabClient constructor), T-A.4 (setup persists Tokens DB), T-A.5 (refresh/logout reads Tokens DB).
   - Both monkeypatch both `USERPROFILE` AND `HOME` to a tmp_path fixture at test setup. Discriminating regression test (Phase 9 lesson 8 pattern): after each affected test, assert the operator's real `~/swing-data/` is unchanged.
9. **Session-anchor read/write predicate alignment.** `_step_schwab_snapshot` calls `record_snapshot(snapshot_date=last_completed_session(datetime.now()))` (backward-looking writer). Phase 10 capital-friction read predicate uses `get_latest_snapshot_on_or_before(asof_date=last_completed_session(datetime.now()))` ALSO backward-looking (verified at planning time). **Predicates align.** Discriminating round-trip test at T-B.3 writes a snapshot via `_step_schwab_snapshot` + immediately reads via Phase 10 capital-friction VM + asserts LIVE-badge appears.
10. **`or None` vs `or ''` discipline for nullable text columns with CHECK constraints.** `schwab_api_calls.error_message` is nullable TEXT (NO CHECK enum); `error_message` defaults `None` not empty string (form-input fallback gotcha; if a CLI flag could surface here, use `value if value else None` pattern). N/A for V1 — `error_message` is server-stamped from exception body, never operator-input.
11. **`executescript()` implicit-COMMIT gotcha — CORRECTED per Codex R1 Critical #1.** The current `_apply_migration` runner does `try: executescript; commit; except: rollback;` but does NOT issue an explicit `BEGIN` — CLAUDE.md's gotcha text described a DESIRED state, not the actual runner. Migration 0018 SQL FILE ITSELF opens with `BEGIN;` and closes with `COMMIT;` to make the transaction explicit so the runner's rollback can actually undo partial DDL on failure. See §C.4 for the corrected disposition + discriminating test pattern. **Forward-binding lesson for future migrations 0019+:** mirror the BEGIN/COMMIT discipline at the migration-file level until/unless the runner is updated.

### §A.10 Out-of-scope reaffirmations

Spec §1.2 + dispatch brief §3 disclaim consumed verbatim. **Plan acceptance criteria assert NO code path lands for the following:**

- Automated order placement (POST `/trader/v1/accounts/{hash}/orders`).
- Order cancellation (DELETE `/trader/v1/accounts/{hash}/orders/{id}`).
- WebSocket streaming endpoints.
- Option chains / fundamentals / instruments lookup.
- Schwab inception-CSV historical ingestion (separate dispatch per phase3e-todo 2026-05-12 entry).
- TOS CSV reconciliation deprecation (V2 candidate; V1 retains as fallback per Q7).
- Web UI for Schwab management (Q5; V2 candidate).
- Multi-account scoping (Q3; V2 candidate).

Plan §B READ-ONLY list explicitly enumerates Phase 6 + Phase 7 + Phase 8 + Phase 9 entities as out-of-scope; no modifications outside `swing/integrations/schwab/`, the new repo, the new migration, the new pipeline-step additions, the new CLI group, the new config sub-dataclass fields.

### §A.11 Operator-attention items surfaced

Per dispatch brief §0.8 + spec §8.6 + §10. Items surfaced in plan §D as open questions for executing-plans Task 0.b operator-paired verification (6 items: Q8/Q12/Q13-residual/Q14/Q15/Q17). Items surfaced INLINE in plan (not §D — these are decided in this plan):

- **Production-only domain writes discriminating test pattern** — §K T-B.7 enumerates exact contract (assert audit row written + domain table unchanged under sandbox env).
- **Q1 production-tier disposition wired** — §A.3 + default cfg cascade default `environment='production'`; T-A.4 setup runs against production-tier credentials by default.
- **Q11 V1 INCLUDE market-data ladder design surface** — §A.8 Shape A LOCKED; Sub-bundle C scope is large but bounded (cache layer rewrite + new resolver + provider-tagged parquet files).
- **Q16 `schwab_account_hash` V1 ADD** — §A.7 + §C.2 migration.

### §A.12 Decisions firmed up during planning

| # | Item (per spec §8.6) | Decision |
|---|---|---|
| 1 | §4.3 ALTER `schwab_account_hash` on `account_equity_snapshots` | V1 ADD (per Q16). |
| 2 | §4.4 market-data persistence shape | Shape A (parquet-per-(ticker, provider)). |
| 3 | §3.3.1 endpoint shapes | Synthesized in §E; verify at Task 0.b. |
| 4 | §3.3.1 scope strings | Default `readonly`; verify at Task 0.b (§D.4). |
| 5 | §3.5 CLI subcommand-body design | §H §H.1-§H.2 algorithm specs. |
| 6 | §3.4.1 ALTER `schwab_api_call_id` on `reconciliation_runs` | V1 ADD with FK to `schwab_api_calls(call_id)` and `ON DELETE SET NULL` (per §C.3 + §A.0 #7). |
| 7 | §3.6 `schwab_api_calls` DDL | §C.1 canonical SQL. |
| 8 | §3.2.4 file-lock cross-platform shim | **DROPPED** (COA B inherits schwabdev's `RLock` + SQLite `BEGIN EXCLUSIVE`). |
| 9 | §3.2.1 callback-URL HTTPS-vs-HTTP | **N/A** under COA B (paste-back-only V1; no callback URL listener). |
| 10 | §7 cycle-checklist exact wording | §I per-line wording. |
| 11 | Test fixtures (sanitized cassettes; sentinel-leak audit fixtures; Task 0.b runbook) | §G cassette runbook + §K T-A.10 sentinel-leak audit. |
| 12 | Integration test E2E | §K T-D.3 mirrors `tests/integration/test_phase9_full_happy_path.py` shape. |

---

## §B File map

### §B.1 New files (CREATE)

**Sub-package `swing/integrations/schwab/`** (Bundle A T-A.3):

| File | Responsibility |
|---|---|
| `swing/integrations/schwab/__init__.py` | Re-exports `SchwabClient`, exception classes (`SchwabConfigMissingError`, `SchwabApiError`, `SchwabRateLimitError`, `SchwabAuthError`, `SchwabRefreshTokenExpiredError`, `SchwabSchemaParityError`, `SchwabConcurrentRefreshError`, `SchwabPipelineActiveError`), `_SOURCE_PRECEDENCE_MARKET_DATA` (Bundle C; lands in A as stub then populated in C). |
| `swing/integrations/schwab/auth.py` | Thin wrapper around `schwabdev.auth.manual_flow()` + `schwabdev.tokens.Tokens` (paste-back-only V1 per COA B). Owns: `setup_paste_flow(cfg, environment, client_id, client_secret) -> SchwabAuthResult`; `force_refresh(cfg, environment) -> None`; `revoke_and_delete(cfg, environment) -> None`. Each function wraps schwabdev calls in `_suppress_transport_debug_logs()` + INSERT/UPDATE audit-row lifecycle. |
| `swing/integrations/schwab/client.py` | `SchwabClient` thin wrapper around `schwabdev.Client`. Composition (NOT subclassing). Holds: `_cfg: SchwabConfig`, `_schwabdev_client: schwabdev.Client`, `last_rate_limit_remaining: int \| None`. Public methods proxy to schwabdev with audit lifecycle + token redaction + production-only gating. Defines `_suppress_transport_debug_logs()` context manager (Finviz pattern mirror; includes schwabdev's own logger names per §A.2 caveat). Defines exception hierarchy mirror Finviz precedent (each exception's `__str__` redacts URL + body bytes). |
| `swing/integrations/schwab/trader.py` | Trader API endpoint methods (Bundle B). Public functions: `get_accounts_linked(client)`, `get_account_details(client, account_hash)`, `get_account_orders(client, account_hash, from_dt, to_dt, status_filter)`, `get_account_transactions(client, account_hash, start_date, end_date, type_filter)`. Each: invokes corresponding schwabdev method; INSERT in-flight audit row pre-call; UPDATE post-call with status + signature_hash. Returns normalized dataclasses (NOT raw JSON). |
| `swing/integrations/schwab/marketdata.py` | Market Data API endpoint methods (Bundle C). Public functions: `get_quotes_batch(client, symbols)`, `get_price_history(client, symbol, period_type, period, freq_type, freq, start_dt, end_dt)`. Same audit-lifecycle pattern. Returns normalized dataclasses. |
| `swing/integrations/schwab/mappers.py` | Pure functions mapping schwabdev response dicts → project dataclasses. Functions: `map_account_details_to_equity_snapshot_inputs(response_dict, account_hash) -> SchwabAccountResponse`; `map_orders_to_fill_candidates(orders_dict) -> list[SchwabOrderResponse]`; `map_transactions_to_cash_movement_candidates(tx_dict) -> list[SchwabTransactionResponse]`; `map_quotes_to_price_cache_entries(quotes_dict) -> dict[str, SchwabQuoteResponse]`; `map_price_history_to_window(history_dict, ticker) -> SchwabPriceHistoryWindow`. NO HTTP; NO DB. |
| `swing/integrations/schwab/pipeline_steps.py` | Pipeline step functions `_step_schwab_snapshot(conn, cfg, pipeline_run_id, schwab_client)` + `_step_schwab_orders(conn, cfg, pipeline_run_id, schwab_client)` (Bundle B T-B.3 + T-B.4). Sandbox-gating discipline. |
| `swing/integrations/schwab/marketdata_ladder.py` | Bundle C. Source-ladder fetcher functions: `fetch_quote_via_ladder(ticker, cfg, schwab_client, yfinance_fallback_fn) -> tuple[PriceCacheEntry, str]`; `fetch_window_via_ladder(ticker, start, end, cfg, schwab_client, yfinance_fallback_fn) -> tuple[OhlcvWindow, str]`. Tries Schwab first under production env; falls back to yfinance on any of (empty response, rate limit, auth failure, 5xx). Returns the entry + the provider tag (`'schwab_api'` or `'yfinance'`). |

**Data repo**:

| File | Responsibility |
|---|---|
| `swing/data/repos/schwab_api_calls.py` | Repo-layer SQL functions (caller-controlled tx; mirror Phase 9 `account_equity_snapshots.py` discipline). Functions: `insert_in_flight(conn, *, ts, endpoint, pipeline_run_id, surface, environment) -> int` (returns call_id); `update_call_outcome(conn, *, call_id, http_status, response_time_ms, rate_limit_remaining, signature_hash, status, error_message) -> None`; `update_call_linked_snapshot(conn, *, call_id, snapshot_id) -> None`; `update_call_linked_reconciliation_run(conn, *, call_id, reconciliation_run_id) -> None`; `list_recent_calls(conn, *, since_ts, surface_filter, environment_filter, limit) -> list[SchwabApiCall]`; `get_call(conn, *, call_id) -> SchwabApiCall \| None`; `count_calls_by_status(conn, *, status_filter, since_ts) -> int`. |

**Data model**:

| File | Responsibility |
|---|---|
| `swing/data/models.py` (MODIFY — add new dataclass + extend existing) | Add `SchwabApiCall` dataclass with `__post_init__` validation (`call_id: int`; `ts: str` ISO ms; `endpoint: str` in known set; `http_status: int \| None`; `response_time_ms: int \| None`; `rate_limit_remaining: int \| None`; `signature_hash: str \| None`; `status: str` in known set; `error_message: str \| None`; `linked_snapshot_id: int \| None`; `linked_reconciliation_run_id: int \| None`; `pipeline_run_id: int \| None`; `surface: str` in `{pipeline, cli}`; `environment: str` in `{sandbox, production}`). ALSO extend existing `ReconciliationRun` dataclass with `schwab_api_call_id: int \| None = None` field per R2 Major #5 (minimal extension; matches migration 0018 ALTER on `reconciliation_runs`). |

**Service layer**:

| File | Responsibility |
|---|---|
| `swing/integrations/schwab/audit_service.py` | Service-layer transactional wrappers around the audit repo. Functions (R3 Minor #1 update — `link_snapshot` REPLACED by combined `link_snapshot_and_stamp_account_hash` per R2 Major #3): `record_call_start(conn, *, ts, endpoint, pipeline_run_id, surface, environment) -> int` (owns BEGIN IMMEDIATE; rejects caller-held tx; returns call_id); `record_call_finish(conn, *, call_id, http_status, response_time_ms, rate_limit_remaining, signature_hash, status, error_message) -> None` (owns BEGIN IMMEDIATE); `link_snapshot_and_stamp_account_hash(conn, *, call_id, snapshot_id, account_hash) -> None` (combined tx2 per §H.4.1 step 8d + §H.4.1.bis); `link_reconciliation_run(conn, *, call_id, reconciliation_run_id) -> None`. All reject caller-held tx; all raise `CallerHeldTransactionError` on caller-held tx. |
| `swing/trades/schwab_reconciliation.py` | NEW service-layer function `run_schwab_reconciliation(conn, *, account_hash, period_start, period_end, schwab_orders_response, schwab_transactions_response, schwab_account_response, pipeline_run_id, schwab_api_call_id) -> int`. Returns `reconciliation_run_id`. Mirrors `swing/trades/reconciliation.py:run_tos_reconciliation` shape verbatim — owns BEGIN IMMEDIATE; rejects caller-held tx; reuses Phase 9 `MATERIAL_BY_TYPE` lookup + `RESOLUTION_TYPES` + discrepancy-emit machinery. Bundle B T-B.4. |

**Migration**:

| File | Responsibility |
|---|---|
| `swing/data/migrations/0018_schwab_integration.sql` | CREATE TABLE `schwab_api_calls` (14 columns; PK + indexes; FK candidates to `pipeline_runs`/`account_equity_snapshots`/`reconciliation_runs` with `ON DELETE SET NULL` per §C.3). ALTER `account_equity_snapshots ADD COLUMN schwab_account_hash TEXT NULL`. ALTER `reconciliation_runs ADD COLUMN schwab_api_call_id INTEGER NULL` (FK candidate per §C.3). UPDATE schema_version = 18. Atomic landing per `_apply_migration` runner. |

**CLI**:

| File | Responsibility |
|---|---|
| `swing/cli/schwab.py` (NEW) | New `@click.group("schwab")` under main CLI. Subcommands: `setup`, `refresh`, `fetch`, `status`, `logout`. Each subcommand is a thin handler; delegates to `swing/integrations/schwab/{auth,pipeline_steps,...}.py` for actual work. Bundle A lands `setup`, `refresh`, `logout`, `status` (skeleton); Bundle B lands `fetch [--snapshot|--orders|--all]`; Bundle C lands `fetch --verify-marketdata`; Bundle D polishes `status` full surface. |

**Tests** (test files mirror source files; T-A.* through T-D.* enumerate):

| File | Bundle | Responsibility |
|---|---|---|
| `tests/integrations/test_schwab_auth.py` | A | OAuth paste-back flow unit tests (mocked schwabdev); refresh flow; revoke; per-env tokens DB path resolution. |
| `tests/integrations/test_schwab_client.py` | A | `SchwabClient` constructor + `_suppress_transport_debug_logs()` discipline + exception `__str__` redaction contracts. |
| `tests/integrations/test_schwab_audit_lifecycle.py` | A | Audit-row INSERT/UPDATE lifecycle; `record_call_start`/`record_call_finish` transactional contracts; `CallerHeldTransactionError` discriminating tests; linked-id UPDATEs. |
| `tests/integrations/test_schwab_token_redaction_audit.py` | A | End-to-end sentinel-leak audit (sentinel injected into token bytes; greps log records + DB rows for sentinel; ZERO matches). Covers schwabdev's loggers per §A.2 caveat. |
| `tests/integrations/test_schwab_repo.py` | A | Repo-layer SQL functions; index existence; FK behaviors. |
| `tests/cli/test_schwab_cli.py` | A | `swing schwab setup` (paste flow with stubbed schwabdev); `refresh`; `logout`; `status` skeleton. |
| `tests/integrations/test_schwab_migration_0018.py` | A | Migration 0018 atomic landing; rollback-on-failure regression; ALTER column behaviors. |
| `tests/integrations/test_schwab_trader.py` | B | Trader API methods (cassette-driven). |
| `tests/integrations/test_schwab_mappers.py` | B/C | Mapper functions (pure-function tests; no I/O). |
| `tests/integrations/test_schwab_pipeline_steps.py` | B | `_step_schwab_snapshot` + `_step_schwab_orders` (cassette-driven). |
| `tests/trades/test_schwab_reconciliation.py` | B | `run_schwab_reconciliation` service (mirrors `test_tos_reconciliation` pattern). |
| `tests/integrations/test_schwab_sandbox_gating.py` | B | Production-only domain writes discriminating tests. |
| `tests/integrations/test_schwab_pipeline_active_exclusion.py` | B | `SchwabPipelineActiveError` CLI hard-exclusion tests (mirrors Finviz pattern). |
| `tests/integrations/test_schwab_marketdata.py` | C | Market Data API methods (cassette-driven). |
| `tests/integrations/test_schwab_marketdata_ladder.py` | C | Ladder fetcher functions (Schwab-first; yfinance fallback; sandbox short-circuit; empty-response transient handling). |
| `tests/data/test_ohlcv_archive_shape_a.py` | C | Shape A parquet-per-(ticker, provider) persistence; resolver merge function; backward-compat rename. |
| `tests/web/test_price_cache_provider_field.py` | C | `PriceCacheEntry.provider` field; ladder integration; sandbox short-circuit. |
| `tests/integration/test_schwab_full_happy_path.py` | D | E2E happy-path (mirrors `tests/integration/test_phase9_full_happy_path.py`). |
| `tests/web/test_briefing_schwab_section.py` | D | Briefing rendering with Schwab snapshot value + degraded banner. |

**Cassettes**:

| Path | Bundle | Responsibility |
|---|---|---|
| `tests/integrations/cassettes/schwab_oauth_token_initial.yaml` | A | OAuth code-exchange cassette (filter_post_data_parameters covers `code`, `client_id`, `client_secret`; response-body redactor masks tokens). |
| `tests/integrations/cassettes/schwab_oauth_token_refresh.yaml` | A | OAuth refresh-token-exchange cassette. |
| `tests/integrations/cassettes/schwab_oauth_token_refresh_with_rotation.yaml` | A | OAuth refresh with new refresh_token in response (Q15 rotation case; cassette deferred to Task 0.b if Schwab does not rotate in operator's tier). |
| `tests/integrations/cassettes/schwab_oauth_revoke.yaml` | A | Token revocation cassette. |
| `tests/integrations/cassettes/schwab_accounts_linked.yaml` | A | `Client.account_linked()` cassette (returns the account_hash set). |
| `tests/integrations/cassettes/schwab_account_details.yaml` | B | `Client.account_details(account_hash)` cassette (returns NLV + balances). |
| `tests/integrations/cassettes/schwab_account_orders.yaml` | B | `Client.account_orders(...)` cassette. |
| `tests/integrations/cassettes/schwab_account_transactions.yaml` | B | `Client.transactions(...)` cassette. |
| `tests/integrations/cassettes/schwab_quotes_batch.yaml` | C | `Client.quotes(symbols=...)` cassette. |
| `tests/integrations/cassettes/schwab_price_history_aapl.yaml` | C | `Client.price_history(symbol=AAPL, ...)` cassette. |

### §B.2 Modified files (MODIFY)

| File | Bundle | Modification |
|---|---|---|
| `swing/config.py` | A | Add `SchwabConfig` sub-dataclass under `Config.integrations`; per §A.6 field list; `__post_init__` validators (e.g., `environment` ∈ `{sandbox, production}`; `lookback_days >= 1`; `timeout_seconds > 0`). |
| `swing/config.py` (FIELD_REGISTRY entry) | A | Add `account_hash` to FIELD_REGISTRY with `masked=True` (mirror Finviz precedent for sensitive fields). |
| `swing.config.toml` | A | Add `[integrations.schwab]` section with `timeout_seconds = 30.0`, `marketdata_ladder_enabled = true`, comment annotations. `environment`, `account_hash`, `lookback_days` are user-config-only (NOT in tracked TOML). |
| `swing/data/db.py` | A | Bump `EXPECTED_SCHEMA_VERSION = 17` → `18` (single line; T-A.7). |
| `swing/cli/__init__.py` (or wherever main CLI assembles groups) | A | Wire in `from swing.cli.schwab import schwab_group; main.add_command(schwab_group)`. |
| `pyproject.toml` | A | Add `schwabdev>=2.4.0,<3.0.0` to `[project.dependencies]`. Add `pytest-recording>=0.13` to `[project.optional-dependencies].dev` (if not already present from Finviz dispatch — Finviz did add it; T-A.1 verifies). |
| `swing/pipeline/runner.py` | B | Add `_step_schwab_snapshot` + `_step_schwab_orders` invocations between existing `_step_recommendations` + `_step_charts` per §H §H.4 ordering. Add new lease-status fields `schwab_snapshot_status` + `schwab_orders_status` (Finviz precedent at `_step_finviz_fetch` for lease-status pattern). |
| `swing/web/price_cache.py` | C | Add `provider` field to `PriceCacheEntry` dataclass (Optional `str | None`; values `'schwab_api'` or `'yfinance'`). Modify cache-fill fetcher path to invoke ladder. Sandbox short-circuit guard. |
| `swing/data/ohlcv_cache.py` | C | Modify cache-fill fetcher path to invoke ladder. Sandbox short-circuit guard. |
| `swing/data/ohlcv_archive.py` | C | Filename convention change to `{TICKER}.{PROVIDER}.parquet`. Add `resolve_ohlcv_window(ticker, start, end) -> tuple[pd.DataFrame, dict[str, str]]` merge function. Add `_SOURCE_PRECEDENCE_MARKET_DATA` constant. Backward-compat: at first read of a ticker with no `*.schwab_api.parquet` and an existing `{TICKER}.parquet`, rename to `{TICKER}.yfinance.parquet` (one-shot; idempotent). |
| `docs/cycle-checklist.md` | D | Add Schwab section per §I. |
| `CLAUDE.md` | D | Add Schwab gotchas + reference pointers per §J. |
| `swing/pipeline/runner.py` (briefing render) | D | Add "Schwab integration: degraded" banner emission when last `schwab_api_calls` row's `status != 'success'` per spec §3.4.4 + §7.2. |
| `swing/data/repos/reconciliation.py` | B | Multi-touchpoint extension for the new migration 0018 `reconciliation_runs.schwab_api_call_id` column (R2 Major #5 + R3 Major #3 fix): (a) extend `_RUN_SELECT_COLUMNS` to include the new column; (b) extend `_row_to_run` mapper to populate dataclass field; (c) extend `insert_run` (actual function name) to accept `schwab_api_call_id: int \| None = None` kwarg + include in INSERT column list; (d) reader functions `get_run` / `list_recent_runs` round-trip via updated mapper. All other functions consumed verbatim. |

### §B.3 READ-ONLY (no modifications outside scope)

Explicit READ-ONLY list (per spec §3.7 + dispatch brief §0.4 + dispatch brief §5 watch-item 18 phase-isolation):

- `swing/data/repos/account_equity_snapshots.py` — consumed via `record_snapshot()` only.
- `swing/trades/account_equity_snapshots.py` — consumed via `record_snapshot()` only.
- `swing/trades/reconciliation.py` — `run_tos_reconciliation` shape mirrored in new file; NOT touched.
- `swing/journal/tos_import.py` — TOS path stays as V1 fallback per Q7; NOT touched.
- (R5 Minor #1: `swing/data/repos/reconciliation.py` is NOT in READ-ONLY list — see §B.2 row + T-B.4 for the targeted-modification scope; this prior placeholder removed to avoid contradictory categorization. Discrepancy-emit functions in that file — `insert_discrepancy`, `get_discrepancy`, `list_discrepancies_for_run`, `list_unresolved_material_for_active_trades`, `list_unresolved_material_for_closed_trades` — ARE consumed verbatim; the modification is confined to the run-side helpers per §B.2.)
- `swing/data/repos/hypothesis_status_history.py` — Phase 9 Sub-bundle C; not touched.
- `swing/data/repos/sector_industry_evaluation.py` — Phase 9 Sub-bundle D; not touched.
- `swing/web/view_models/metrics/*.py` — Phase 10 metrics surfaces; not touched.
- `swing/data/repos/{review_log,daily_management,trades,fills,...}` — Phase 6/7/8 entities; not touched.
- All Phase 6+7+8 templates + view models; not touched.
- Existing migrations 0001-0017; not touched.

---

## §C Migration 0018 SQL (canonical reference; T-A.7 implements verbatim)

### §C.1 Canonical SQL — single atomic migration file

`swing/data/migrations/0018_schwab_integration.sql`:

**Atomicity discipline.** The current `_apply_migration` runner at `swing/data/db.py:91-134` does `try: executescript(sql); conn.commit() except: conn.rollback()` BUT does NOT issue an explicit `BEGIN` before `executescript`. Per CLAUDE.md gotcha "Python sqlite3 `executescript()` issues an implicit COMMIT before running its script; each statement runs in autocommit mode and `conn.rollback()` cannot undo successful intermediate statements", the runner-level rollback does NOT actually undo partial DDL applied before a mid-script failure. **Fix at the migration-file level (per Codex R1 Critical #1):** migration 0018 SQL itself opens with `BEGIN;` and closes with `COMMIT;`. Inside the explicit transaction the statements run as a single atomic unit; on mid-script failure the BEGIN's transaction is still open + the runner's `conn.rollback()` undoes the partial state. T-A.7 discriminating test plants a malformed 0018 with deliberate fail-mid-sequence + asserts schema_version still 17 + table absent + `conn.in_transaction == False` after failure. **This is a NEW discipline on the migration file (not on the runner)** — future migrations should mirror.

```sql
-- 0018_schwab_integration.sql
-- Lands schwab_api_calls audit table + ALTERs on account_equity_snapshots and
-- reconciliation_runs for V1 Schwab API integration.
-- Atomic via explicit BEGIN; ... COMMIT; per Codex R1 Critical #1 +
-- CLAUDE.md gotcha "executescript() implicit COMMIT". Runner-level
-- conn.rollback() can undo partial DDL only when the SQL itself opens
-- an explicit transaction.
-- Bumps schema_version 17 -> 18.

BEGIN;

CREATE TABLE schwab_api_calls (
    call_id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                            TEXT NOT NULL,
    endpoint                      TEXT NOT NULL,
    http_status                   INTEGER,
    response_time_ms              INTEGER,
    rate_limit_remaining          INTEGER,
    signature_hash                TEXT,
    status                        TEXT NOT NULL,
    error_message                 TEXT,
    linked_snapshot_id            INTEGER,
    linked_reconciliation_run_id  INTEGER,
    pipeline_run_id               INTEGER,
    surface                       TEXT NOT NULL,
    environment                   TEXT NOT NULL,

    CHECK (status IN (
        'in_flight', 'success', 'error',
        'auth_failed', 'rate_limited', 'concurrent_refresh'
    )),
    CHECK (surface IN ('pipeline', 'cli')),
    CHECK (environment IN ('sandbox', 'production')),
    CHECK (endpoint IN (
        'oauth.code_exchange', 'oauth.refresh', 'oauth.revoke',
        'accounts.linked', 'accounts.details',
        'accounts.orders.list', 'accounts.transactions.list',
        'marketdata.quotes', 'marketdata.pricehistory'
    )),

    FOREIGN KEY (linked_snapshot_id)
        REFERENCES account_equity_snapshots(snapshot_id)
        ON DELETE SET NULL,
    FOREIGN KEY (linked_reconciliation_run_id)
        REFERENCES reconciliation_runs(run_id)
        ON DELETE SET NULL,
    FOREIGN KEY (pipeline_run_id)
        REFERENCES pipeline_runs(run_id)
        ON DELETE SET NULL
);

CREATE INDEX ix_schwab_api_calls_ts
    ON schwab_api_calls(ts);

CREATE INDEX ix_schwab_api_calls_status_ts
    ON schwab_api_calls(status, ts);

CREATE INDEX ix_schwab_api_calls_pipeline_run_id_ts
    ON schwab_api_calls(pipeline_run_id, ts);

CREATE INDEX ix_schwab_api_calls_surface_ts
    ON schwab_api_calls(surface, ts);

ALTER TABLE account_equity_snapshots
    ADD COLUMN schwab_account_hash TEXT;

ALTER TABLE reconciliation_runs
    ADD COLUMN schwab_api_call_id INTEGER
        REFERENCES schwab_api_calls(call_id) ON DELETE SET NULL;

UPDATE schema_version SET version = 18;

COMMIT;
```

### §C.2 Column rationale + design notes

**`schwab_api_calls.status` enum.** Six values per spec §3.6 column-shape sketch:
- `in_flight`: pre-call row exists; HTTP call has not yet completed.
- `success`: HTTP 200; response processed; payload mapped successfully.
- `error`: non-200 HTTP OR network failure OR mapper-side failure (e.g., empty `/pricehistory` data array per §3.8.6).
- `auth_failed`: 400 invalid_grant / 401 invalid_client / 401 refresh_token expired / 403 insufficient_scope.
- `rate_limited`: 429 after Retry-After-respecting retry exhausted.
- `concurrent_refresh`: schwabdev's `RLock` + SQLite `BEGIN EXCLUSIVE` raised contention (mapped to `SchwabConcurrentRefreshError`).

**`schwab_api_calls.endpoint` enum.** Logical endpoint name (NOT raw URL — URL contains `account_hash` segment which is sensitive per §A.2). 9 V1 values enumerated in CHECK constraint above. Adding endpoints in V2 requires schema migration (CHECK enum). Plan acceptance: T-A.1 verifies the 9 schwabdev method names map exactly to these enum values.

**`schwab_api_calls.surface` enum.** Per spec §3.6.2 audit-write surface boundary — `'pipeline'` and `'cli'` are the only V1-INSERT-eligible values. `'web_page_render'` is reserved for V2 but NOT in V1 CHECK enum (since V1 INSERT path never writes it; CHECK rejects it explicitly, matching the policy lock). V2 candidate path expands the CHECK enum AND introduces a batched-writer.

**`schwab_api_calls.environment` enum.** Two values; matches `cfg.integrations.schwab.environment` cascade.

**`schwab_api_calls.linked_*_id` columns.** Nullable with FK `ON DELETE SET NULL`. Rationale: domain-write callsite UPDATEs the audit row AFTER the snapshot/reconciliation_run is INSERTed; if a downstream operator-action deletes a snapshot or reconciliation_run row, the audit row's pointer becomes NULL (provenance still recoverable via `source_artifact_path` URI on the domain row, which carries `"schwab_api:call/{call_id}"` — the reverse pointer).

**`schwab_api_calls.signature_hash` column.** SHA-256 of canonicalized response (Finviz precedent at `_compute_schema_signature`). Format: column-set + first-row fingerprint, NOT body bytes; drift detection only. Plan §H §H.9 specifies signature algorithm.

**`schwab_api_calls.error_message` column.** Nullable; NEVER includes token / refresh_token / client_secret / account_hash bytes. Plan §H §H.8 + sentinel-leak audit (§K T-A.10) cover the redaction contract.

**Indexes.** Four indexes serve the canonical V1 query patterns:
- `(ts)` — ordered enumeration for `swing schwab status` recent-call display.
- `(status, ts)` — `count_calls_by_status` for `status` per-surface summary.
- `(pipeline_run_id, ts)` — pipeline-run-specific audit chase.
- `(surface, ts)` — `swing schwab status` per-surface breakdown.

### §C.3 FK CASCADE risk analysis

Per spec §A.0 #7 + dispatch brief §8: "If migration 0018 ALTER candidates surface FK CASCADE risk, halt + surface to orchestrator."

Audit:
- `schwab_api_calls.linked_snapshot_id → account_equity_snapshots(snapshot_id) ON DELETE SET NULL`: if a snapshot row is deleted, the audit row's pointer is nulled; audit row preserved. **Safe.**
- `schwab_api_calls.linked_reconciliation_run_id → reconciliation_runs(run_id) ON DELETE SET NULL`: same pattern. **Safe.**
- `schwab_api_calls.pipeline_run_id → pipeline_runs(run_id) ON DELETE SET NULL`: same. **Safe.**
- `account_equity_snapshots.schwab_account_hash`: scalar column; no FK. **Safe.**
- `reconciliation_runs.schwab_api_call_id → schwab_api_calls(call_id) ON DELETE SET NULL`: if an audit row is deleted (V1: never; V2 candidate retention/pruning), the reconciliation_run's FK pointer is nulled; reconciliation_run preserved. **Safe.** (The reciprocal `linked_reconciliation_run_id` would auto-null on the other side via its own FK rule.)

**No CASCADE rules anywhere in 0018.** Per CLAUDE.md gotcha + Phase 9 Sub-bundle A discipline, `INSERT OR REPLACE` on FK-referenced tables would CASCADE-WIPE child rows; that gotcha is the rationale for the explicit `ON DELETE SET NULL` choice everywhere. No `ON DELETE CASCADE` anywhere; no `INSERT OR REPLACE` anywhere in §C.1 or in any service-layer path touching `schwab_api_calls`.

### §C.4 Atomic-landing discipline

**Corrected per Codex R1 Critical #1.** Plan-author's initial assumption that `_apply_migration` issues an explicit `BEGIN` was wrong — the runner at `swing/data/db.py:91-134` does `try: executescript(sql); conn.commit() except: conn.rollback() finally: restore PRAGMA foreign_keys` but has NO explicit `BEGIN`. CLAUDE.md's gotcha text ("the migration-runner wrapper MUST issue explicit BEGIN + executescript + COMMIT") describes a DESIRED future-state discipline that was NOT actually implemented at the runner level; instead, the runner's rollback discipline relies on the migration file's own explicit transaction boundaries.

**Plan disposition:** migration 0018 SQL itself opens with `BEGIN;` and closes with `COMMIT;` (see §C.1). Inside the explicit transaction the statements run atomically; on mid-script failure the BEGIN's transaction is still open + the runner's `conn.rollback()` undoes the partial state. **No runner-level changes required** — this is purely a migration-file-level discipline. T-A.7 acceptance:

- Migration 0018 SQL starts with `BEGIN;` and ends with `COMMIT;` (verified by `grep -n '^BEGIN;\|^COMMIT;' swing/data/migrations/0018_*.sql`).
- Bumping `EXPECTED_SCHEMA_VERSION` to 18 + landing 0018 is a SINGLE COMMIT in git.
- Discriminating regression test: plant a malformed 0018 fixture with deliberate fail-mid-sequence (e.g., bad INDEX definition after CREATE TABLE); invoke `_apply_migration`; assert post-failure `schema_version` row is STILL 17 (rollback succeeded) AND `schwab_api_calls` table does NOT exist (rollback succeeded) AND `conn.in_transaction == False`.
- Additional discriminating test: plant 0018 WITHOUT the leading `BEGIN;` (i.e., autocommit mode); plant deliberate fail-mid-sequence; assert post-failure `schwab_api_calls` table DOES exist (CHECK constraint violation rolled back, but CREATE TABLE persisted in autocommit) — this is the failing test that locks the BEGIN-discipline contract; canonical 0018 (WITH BEGIN) passes; canonical-minus-BEGIN-fixture fails. Documents the discipline by counter-example.

**Forward-relevance for future migrations:** all future migrations (0019+) should also open with `BEGIN;` and close with `COMMIT;` until/unless the runner is updated to issue these itself. Add to §J.7 CLAUDE.md note (Bundle D T-D.4).

### §C.5 Backup gate — does NOT fire for 17→18 (CORRECTED per Codex R1 Major #1)

Plan-author's initial assumption was wrong. Reading `swing/data/db.py` reveals that the backup gate `MigrationBackupRequiredException` machinery is **version-specific** — it fires only for known migration transitions where the spec author elected to back up (Phase 7 13→14; Phase 8 15→16; Phase 9 16→17 explicit gates wired via per-version conditions in the migration runner). For 17→18 the existing gate code does NOT trigger. The dispatch brief §8 explicitly states "the Phase 7 backup gate fires on target_version >= 14 from current_version == 13 only — moot here".

**Plan disposition:**

- **NO backup gate is wired for 0018.** Adding a new gate is technically simple (one line in `_apply_migration`'s per-version conditional ladder) but is OUT-OF-SCOPE for this writing-plans phase — the runner-level work belongs to a runner-hardening dispatch, not the Schwab integration arc.
- **Operator-manual backup recommended** before first `swing db-migrate` run that lands 0018. §I.1 setup section adds an explicit note: "Before first run, copy `%USERPROFILE%/swing-data/swing.db` to `swing.db.pre-phase11.backup` as a recovery snapshot."
- T-D.7 (formerly "verify backup gate fires") is REMOVED. Bundle D T-D.7 scope is reassigned to: verify migration 0018 was applied atomically AND verify operator-facing migration warning message includes the manual-backup recommendation.
- **V2 candidate:** runner-hardening dispatch that adds a per-version-by-default backup gate ladder. Tracked at `docs/phase3e-todo.md` post-Phase-11.

**Discriminating test pattern (T-A.7 acceptance addendum):** plant `schema_version=17`; invoke `_apply_migration(<0018>)`; assert NO `MigrationBackupRequiredException` raised AND NO backup file written to `swing-data/`. This locks the disposition (gate-doesn't-fire) by counter-example.

---

## §D Open questions for orchestrator triage (BINDING for executing-plans Task 0.b)

Six items deferred to executing-plans Task 0.b operator-paired live verification. Plan §D enumerates each with:
- The exact question.
- Why it cannot be locked at writing-plans time (dependency on operator-paired live access to Schwab).
- The Task 0.b verification step.
- The plan-author's synthesized default behavior used in V1 until verified.

### §D.1 Q8: Sandbox vs production HTTP-layer differentiation

- **Question:** Does Schwab use distinct base URLs / path prefixes / scope strings / token TTLs between sandbox and production?
- **Why deferred:** Schwab Developer Portal sandbox documentation is paywall-gated; cannot verify without operator-paired access. Per-env sidecar shape is LOCKED (per §A.2 + spec §3.2.7) — the LOCKED disposition is per-env tokens DBs + cfg.integrations.schwab.environment cascade. **What REMAINS open:** the API-side HTTP-layer differentiation.
- **Task 0.b verification step:** operator runs `swing schwab setup --environment sandbox` (if sandbox app registered) + `swing schwab fetch --snapshot` against sandbox; compares response shape + base URL + scope behavior against production. Records observations in `docs/superpowers/specs/2026-05-13-schwab-api-design.md` §10.8 capture-needs followup.
- **Plan-author synthesized default:** `SchwabClient` constructor accepts `base_url` parameter; default derives from `cfg.integrations.schwab.environment` mapping `{sandbox: 'https://api-sandbox.schwabapi.com', production: 'https://api.schwabapi.com'}` (synthesized; verify at Task 0.b — schwabdev's own base URL handling may differ). If schwabdev uses a single base URL regardless of env, the cfg field is informational; if it uses distinct URLs, plan-author writing-plans-time guess matches schwabdev's actual base URLs.

### §D.2 Q12: Premium-tier Schwab Market Data endpoints

- **Question:** Does operator's Schwab Market Data subscription tier permit `/marketdata/v1/quotes` + `/marketdata/v1/{symbol}/pricehistory` at default-tier, or are these premium-tier only?
- **Why deferred:** Schwab subscription tier is operator-account-specific; not synthesizable from public docs alone.
- **Task 0.b verification step:** operator runs `swing schwab fetch --verify-marketdata --symbols AAPL` post-Sub-bundle-C-merge; verifies 200 OK + non-empty data; if 403 insufficient_scope or subscription-required error, escalates back to orchestrator for operator decision (upgrade subscription OR defer market-data ladder to V2; effectively flips Q11 to EXCLUDE post-fact).
- **Plan-author synthesized default:** assume default-tier permits both endpoints (Schwab's documented developer-tier supports both; live verification confirms).

### §D.3 Q13 residual: OAuth callback localhost vs paste

- **Question:** Under COA B, schwabdev's `auth.manual_flow()` is paste-back-only. Is paste-back actually the operator-friction-acceptable path, or does operator find it annoying enough to want localhost-listener support deferred-to-V2?
- **Why deferred:** Operator UX preference; not a technical question. Mostly closed by Q18 COA B choice (operator confirmed paste-back acceptable 2026-05-13).
- **Task 0.b verification step:** operator runs `swing schwab setup --environment production` (real production-tier credentials) end-to-end; subjectively rates paste-back UX.
- **Plan-author synthesized default:** V1 paste-back only; localhost listener V2 candidate if operator surfaces friction.

### §D.4 Q14: OAuth scope-string composition

- **Question:** What is the exact scope string Schwab requires? Default synthesis: `readonly` (Schwab convention; matches schwab-py default). May actually be `Trader.Read MarketData.Read` (space-separated; resource-server convention) or path-segment-style or some other value.
- **Why deferred:** Schwab Developer Portal does not publish scope strings publicly; visible only at app-registration time + via empirical 200-OK testing.
- **Task 0.b verification step:** operator records the scope string visible at Schwab Developer Portal app config page; updates the constant in `swing/integrations/schwab/auth.py` if different from synthesized default; cassette-records first successful call to verify scope.
- **Plan-author synthesized default:** `readonly` constant string passed to `schwabdev.auth.manual_flow(scope='readonly')` (parameter name verify at Task 0.b; schwabdev API may have changed).

### §D.5 Q15: Refresh-token rotation behavior

- **Question:** Does Schwab rotate the refresh_token on every refresh (returns NEW refresh_token in response), or only when TTL nears expiry, or never during the refresh_token TTL?
- **Why deferred:** Schwab does not publish rotation policy; visible only via empirical observation across multiple refresh cycles.
- **Task 0.b verification step:** operator runs `swing schwab refresh` repeatedly across multiple sessions; observes via `swing schwab status` whether the schwabdev Tokens DB's `refresh_token` value mutates; records observation. Schwabdev handles both cases automatically per `tokens.py:207` (`if new_refresh_token: self.refresh_token = new_refresh_token`); our wrapping discipline is unaffected. **Cassette discipline at Task 0.b: record one cassette per case observed** (rotation-yes vs rotation-no; either or both).
- **Plan-author synthesized default:** assume rotation occurs (defensive); cassette `schwab_oauth_token_refresh_with_rotation.yaml` exercises the rotation path; if Schwab does not rotate, the cassette is renamed/duplicated to cover the no-rotation case as well.

### §D.6 Q17: Market Data API rate limits

- **Question:** Does Schwab Market Data API publish distinct rate limits from Trader API's ~120 req/min? If yes, what value + window?
- **Why deferred:** Schwab does not publish Market Data API rate limits publicly.
- **Task 0.b verification step:** during operator-paired cassette-recording session (Sub-bundle C), operator runs `swing schwab fetch --verify-marketdata --symbols A,B,C,...` with progressively-larger symbol counts; observes 429 onset threshold; records.
- **Plan-author synthesized default:** assume "~Trader API limits or looser"; if Task 0.b reveals tighter limits, writing-plans Sub-bundle C tightens cache fetch policy (per-page fetches deferred to first-page-load only; subsequent web requests serve cache only).

### §D.7 Open-question summary

| Code | Question | Default | Task 0.b verifier (sub-bundle) |
|---|---|---|---|
| Q8 | base URL / scope / TTL differentiation | env → URL map (synthesized) | B (during operator-paired snapshot/orders cassette session) |
| Q12 | premium-tier endpoint access | default-tier sufficient | C (during operator-paired market-data session) |
| Q13-residual | paste-back UX acceptable | yes | A (during operator-paired setup session) |
| Q14 | OAuth scope-string | `readonly` | A (during operator-paired setup session) |
| Q15 | refresh-token rotation cadence | rotation occurs (defensive) | A (during operator-paired refresh exercise) |
| Q17 | Market Data rate limits | Trader-API-comparable | C (during operator-paired market-data session) |

**Plan acceptance criteria:** each sub-bundle's Task 0.b runbook (§G + §K) covers the corresponding open questions; executing-plans implementer HALTS at Task 0.b until operator-paired verification completes. Plan does NOT lock any of these answers at writing-plans time.

---

## §E Endpoint reference (synthesized; verify at Task 0.b)

Per dispatch brief §0.3a + COA B: this section enumerates **schwabdev Client method signatures** + the project-side normalization mappers. Raw HTTP details (URL pattern, headers, query params, body shapes) live in schwabdev's own documentation; this section captures what OUR code calls + how we adapt the return shape.

`[VERIFY]` tag on any synthesized shape — operator-paired Task 0.b verification required before cassette recording.

### §E.1 OAuth flow (Bundle A; auth.py)

| schwabdev call | Purpose | Project consumer | Return shape (synthesized) | Failure modes |
|---|---|---|---|---|
| `schwabdev.auth.manual_flow(app_key, app_secret, callback_url, tokens_db)` `[VERIFY]` | Run paste-back OAuth flow; print consent URL; await operator paste of authorization code; exchange code for tokens; persist to per-env SQLite DB at `tokens_db` path | `swing/integrations/schwab/auth.py:setup_paste_flow(...)` | `Tokens` object exposing `access_token`, `refresh_token`, `access_token_expires_at`, `refresh_token_expires_at` | 400 invalid_grant; 401 invalid_client; user-cancel; network failure |
| `Tokens.update_tokens(force_refresh_token=False)` `[VERIFY]` | Lazy refresh on first call to schwabdev `Client` method; force refresh if flagged | `swing/integrations/schwab/auth.py:force_refresh(...)` | None (mutates Tokens DB in place) | 400 invalid_grant; 401 refresh_token expired → `SchwabRefreshTokenExpiredError` |
| `Tokens.revoke()` `[VERIFY]` | Best-effort revocation POST to Schwab; clear Tokens DB | `swing/integrations/schwab/auth.py:revoke_and_delete(...)` | None | network failure tolerated; CLI proceeds with sidecar delete regardless |

The method names + parameter shapes above are synthesized from schwabdev's README at `https://github.com/tylerebowers/Schwabdev` (last reviewed at planning time). Task 0.b verification confirms: (a) parameter names match installed schwabdev version; (b) `manual_flow` blocks on input AS EXPECTED (paste-back UX); (c) `tokens_db` parameter accepts a `pathlib.Path` argument; (d) the Tokens DB schema matches what we read in `swing schwab status`. If schwabdev's API has drifted by the time Sub-bundle A dispatches, T-A.1 pins a known-working version + T-A.10 adds a schwabdev-API-shape regression test.

### §E.2 Trader API (Bundle B; trader.py)

Each method invokes schwabdev's corresponding client method inside the audit-row lifecycle wrapper.

| Logical name | schwabdev method `[VERIFY]` | Project consumer | Mapper | Failure modes |
|---|---|---|---|---|
| `accounts.linked` | `Client.account_linked()` | `swing schwab setup` (one-time at end of paste-back flow); CLI `status` | `map_account_linked_to_hash_set(response_dict) -> list[str]` | 401 expired; 403 scope |
| `accounts.details` | `Client.account_details(account_hash, fields=['positions'])` | `_step_schwab_snapshot`; CLI `fetch --snapshot` | `map_account_details_to_equity_snapshot_inputs(response_dict, account_hash) -> SchwabAccountResponse` | 401; 403; 404 invalid account_hash |
| `accounts.orders.list` | `Client.account_orders(account_hash, from_entered_time=ISO, to_entered_time=ISO, status_filter=None)` | `_step_schwab_orders`; CLI `fetch --orders` | `map_orders_to_fill_candidates(orders_dict) -> list[SchwabOrderResponse]` | 401; 403; 429 |
| `accounts.transactions.list` | `Client.transactions(account_hash, start_date, end_date, type_filter='ALL')` | `_step_schwab_orders` (combined call); CLI `fetch --orders` | `map_transactions_to_cash_movement_candidates(tx_dict) -> list[SchwabTransactionResponse]` | 401; 403; 429 |

`SchwabAccountResponse` dataclass (Bundle B; data/models.py) fields:
- `account_hash: str` — operator's encrypted account identifier (per §A.2 vocabulary).
- `net_liquidating_value: float` — primary field consumed as `equity_dollars` in `record_snapshot()`. `__post_init__` validator rejects NaN/inf.
- `cash: float` — V1 informational; not currently consumed by any project surface (V2 candidate).
- `buying_power: float` — V1 informational.
- `positions: list[dict]` — opaque V1; passed to `run_schwab_reconciliation` for position_qty_mismatch checks. Bundle B T-B.4 mapper logic enumerates per-position parsing.
- `recorded_at: str` — server-stamped ISO ms.

`SchwabOrderResponse` dataclass fields:
- `order_id: str` (Schwab's order_id).
- `status: str` — `WORKING` | `FILLED` | `CANCELED` | `WAIT_TRG` | other. V1 only consumes `FILLED` for fill-matching + `WORKING`/`WAIT_TRG` for stop-tracking.
- `enter_time: str` — ISO ms (per `from_entered_time` request param's response correspondent).
- `instrument_symbol: str`.
- `instruction: str` — `BUY` | `SELL` | `BUY_TO_OPEN` | `SELL_TO_CLOSE` | etc.
- `quantity: float`.
- `order_type: str` — `LIMIT` | `MARKET` | `STOP` | etc.
- `price: float | None` — limit price or stop trigger (depends on `order_type`).
- `__post_init__` validator: `quantity >= 0`, price non-negative (if present), enum-membership for `status`/`instruction`/`order_type`.

`SchwabTransactionResponse` dataclass fields:
- `transaction_id: str`.
- `transaction_date: str` — ISO date.
- `type: str` — `TRADE` | `DIV` | `INTEREST` | `TRANSFER` | etc.
- `net_amount: float` — signed (positive = inflow, negative = outflow).
- `description: str | None`.
- `__post_init__` validator: enum-membership; net_amount finite.

### §E.3 Market Data API (Bundle C; marketdata.py)

| Logical name | schwabdev method `[VERIFY]` | Project consumer | Mapper | Failure modes |
|---|---|---|---|---|
| `marketdata.quotes` | `Client.quotes(symbols=['A','B','C',...])` | `PriceCache` cache-fill via ladder | `map_quotes_to_price_cache_entries(quotes_dict) -> dict[str, SchwabQuoteResponse]` | 401; 403; 429; partial response |
| `marketdata.pricehistory` | `Client.price_history(symbol, period_type='day', period=10, frequency_type='daily', frequency=1, start_datetime=ms, end_datetime=ms)` `[VERIFY]` | `OhlcvCache` cache-fill via ladder | `map_price_history_to_window(history_dict, ticker) -> SchwabPriceHistoryWindow` | 401; 403; 429; empty data array (transient per CLAUDE.md gotcha) |

`SchwabQuoteResponse` dataclass fields:
- `symbol: str`.
- `last_price: float` — primary consumed field.
- `bid: float`.
- `ask: float`.
- `mark: float | None`.
- `quote_time: str` — ISO ms; Schwab's quote-as-of timestamp.
- `delayed: bool` — Schwab indicates delayed quotes for default-tier accounts; flag is informational; default-tier acceptable per §A.1 Q12 default.
- `__post_init__` validator: `last_price >= 0`; finite values.

`SchwabPriceHistoryWindow` dataclass fields:
- `ticker: str`.
- `bars: list[OhlcvBar]` — each: `(asof_date: str, open: float, high: float, low: float, close: float, volume: int)`.
- `provider: str` — hardcoded `'schwab_api'` for instances from this mapper.
- `__post_init__` validator: per-bar invariants (`low <= min(open, close)`; `high >= max(open, close)`; volume >= 0); bars sorted by asof_date.

Note on schwabdev's `Client.price_history(...)` parameter naming: schwabdev may surface the parameters as either snake_case (`period_type`) or camelCase (`periodType`); T-A.1 verifies + pins. The mapper is parameter-name-agnostic.

### §E.4 Partial-response handling on `marketdata.quotes`

Per spec §3.8.6 + §6: Schwab's `Client.quotes(symbols=...)` returns a dict keyed by symbol; some symbols may resolve to error objects rather than quote shapes. Mapper splits the response:

- For each input symbol: if response carries a fully-populated `last_price`/`bid`/`ask` shape, emit `SchwabQuoteResponse`.
- If response carries an error shape (or symbol is absent from the response keys), mark the symbol for yfinance fallback at the ladder layer.
- Audit row `error_message` excerpt captures the per-symbol breakdown (e.g., "3/5 symbols OK; failed: XYZ (404), ABC (timeout)") — under the no-token-leak contract (no token bytes, no client_secret, no account_hash).
- Audit-row status: `'success'` if at least one symbol resolved; `'error'` if all symbols failed.

### §E.5 Empty `pricehistory` response

Per spec §3.8.6 + CLAUDE.md gotcha "External-API empty-result must be treated as transient when write-through-caching":

- If `Client.price_history(...)` returns an empty `bars` array, mapper raises a synthetic `SchwabApiError(status_code=204, body_excerpt="empty bars")` (status_code 204 = "no content" semantic; project-internal sentinel — actual HTTP status may be 200).
- Caller (ladder) catches; records `schwab_api_calls.status='error'` with `error_message="empty bars (transient)"`; falls back to yfinance.
- DOES NOT clobber the OHLCV archive entry for that ticker (per gotcha).
- yfinance fallback inherits its existing empty-result-transient-handling (already correct at `swing/data/ohlcv_archive.py`).

### §E.6 OAuth revocation endpoint

Per spec §6 (POST `/v1/oauth/revoke`):
- schwabdev's `Tokens.revoke()` (or equivalent — verify at Task 0.b; revocation endpoint may not be exposed in schwabdev's public API; if not, our `swing/integrations/schwab/auth.py:revoke_and_delete(...)` issues a manual `requests.post()` to the documented revoke URL with the bearer token + Basic-auth, then deletes the Tokens DB regardless of response).
- Failure tolerated; CLI proceeds with sidecar delete (matches spec §3.2.5).
- Audit row written with `endpoint='oauth.revoke'`; `status='success'` on 200 or `status='error'` on non-200 — but operator-facing outcome (sidecar delete) succeeds either way.

### §E.7 schwabdev surface NOT consumed in V1

Explicit OUT-OF-SCOPE list (mirror spec §3.3.3):

- `Client.order_place(...)` — automated order placement. OUT OF SCOPE per §A.10.
- `Client.order_cancel(...)` — order cancellation. OUT OF SCOPE.
- `Client.user_preference(...)` — V2 candidate.
- `Client.instruments(...)` — V2 candidate.
- `Client.option_chains(...)` — OUT OF SCOPE (equities-only project).
- `Client.market_hours(...)` — V2 candidate per spec §3.3.2 (NOT consumed V1; no callsite; no cassette V1).
- streaming endpoints (`StreamerSocket`, `Streamer`, ...) — V2 candidate.

Plan acceptance: NO call to any of the above schwabdev methods anywhere in `swing/integrations/schwab/` V1 code. §K T-A.10 grep audit verifies (grep `Client.order_place\|Client.order_cancel\|StreamerSocket` in `swing/integrations/schwab/**/*.py` returns no matches).

### §E.8 Verification at executing-plans Task 0.b

Each `[VERIFY]`-tagged shape requires operator-paired live verification before cassette recording. Task 0.b runbook per sub-bundle (§G):

- Bundle A T-A.0.b: verify OAuth flow + Tokens DB schema + `account_linked` shape.
- Bundle B T-B.0.b: verify `account_details` + `account_orders` + `transactions` shapes.
- Bundle C T-C.0.b: verify `quotes` + `price_history` shapes.

---

## §F File + per-env tokens DB conventions

### §F.1 Per-environment tokens DB resolution (COA B SQLite)

Per dispatch brief §0.3a + spec §3.2.2 (COA B disposition):

- Location: `~/swing-data/schwab-tokens.{environment}.db` where `{environment}` ∈ `{sandbox, production}`. Path resolved via the project's existing `_user_home()`-equivalent (mirror Phase 9 Sub-bundle A `_user_home()` pattern); reads `USERPROFILE` on Windows, `HOME` on POSIX. Test fixture monkeypatch discipline per CLAUDE.md gotcha — any test that exercises this path resolution MUST monkeypatch both `USERPROFILE` AND `HOME` to a tmp_path.
- Per-env separation: running `swing schwab setup --environment production` creates `schwab-tokens.production.db`; running with `--environment sandbox` creates `schwab-tokens.sandbox.db`. Files are independent; can coexist; one operator can hold both.
- Schema: owned by schwabdev. NOT enumerated here. The project does NOT migrate or back up the schwabdev Tokens DB. Operator-side recovery is "delete + re-run `swing schwab setup`".
- Concurrency: schwabdev's `threading.RLock` (in-process) + SQLite `BEGIN EXCLUSIVE` (cross-process) handle refresh races. Our wrapping discipline (§H §H.1) wraps schwabdev's refresh-attempt in a try/except → maps any contention exception to our `SchwabConcurrentRefreshError` for surface to the audit table.
- Atomic-write: owned by schwabdev (SQLite-internal; no cross-device-link gotcha since the DB file lives on the same volume as the rest of `swing-data/`).

### §F.2 `.gitignore` patterns (T-A.0 covers)

`.gitignore` MUST include the following patterns before Sub-bundle A ships:

```
# Schwab per-env tokens DBs (managed by schwabdev; plaintext OAuth state V1)
swing-data/schwab-tokens.*.db
swing-data/schwab-tokens.*.db-journal
swing-data/schwab-tokens.*.db-shm
swing-data/schwab-tokens.*.db-wal

# Schwab API audit DB backups (created pre-migration by _apply_migration runner)
swing-pre-phase11-schwab-migration-*.db
```

Discriminating regression test pattern (T-A.0 acceptance):
- `git check-ignore -v` returns non-empty for `swing-data/schwab-tokens.sandbox.db`, `swing-data/schwab-tokens.production.db`, `swing-data/schwab-tokens.production.db-journal`, `swing-data/schwab-tokens.production.db-wal`, `swing-data/schwab-tokens.production.db-shm`.

Operator's `swing-data/` is normally outside the repo per CLAUDE.md DB-location invariant. A misconfigured operator copy could risk a leak. The `.gitignore` lines are defense-in-depth.

### §F.3 Tokens DB revocation (T-A.5 covers)

Per spec §3.2.5 + COA B disposition (`swing schwab logout`):
1. CLI attempts `schwabdev.Tokens.revoke()` (or fallback manual POST per §E.6); failure tolerated.
2. CLI atomically renames `schwab-tokens.{env}.db` to `schwab-tokens.{env}.db.deleted-<timestamp>` in the SAME directory (per CLAUDE.md `os.replace` cross-device-link gotcha — temp file MUST be in destination dir).
3. CLI unlinks the renamed file (or leaves the rename in place for operator recovery window; design choice per T-A.5 acceptance — plan recommends LEAVING the renamed file for a 24h recovery window; operator can purge via separate cleanup).
4. Subsequent API calls fall back to PROVISIONAL state.

Per-env naming prevents cross-env collision: revoking sandbox does not touch production's tokens DB.

### §F.4 cfg cascade — user-config.toml vs swing.config.toml split

Per §A.6 cfg fields:

| Field | Tracked file | Operator-edit? |
|---|---|---|
| `environment` | user-config.toml (operator-edited; cfg cascade) | Yes |
| `account_hash` | user-config.toml | Yes (set via `swing config set` after setup picks primary) |
| `lookback_days` | user-config.toml | Yes |
| `timeout_seconds` | `swing.config.toml` (tracked; defaults) | No (defaults are sufficient) |
| `marketdata_ladder_enabled` | `swing.config.toml` | No (operator can override in user-config if needed) |

Discipline: `client_id`, `client_secret`, and all token fields LIVE ONLY in the schwabdev Tokens DB. ZERO Schwab token bytes ever land in `user-config.toml` or `swing.config.toml`. T-A.10 sentinel-leak audit asserts.

---

## §G Cassette-generation runbook (operator-paired live verification)

Mirror Finviz `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` §G runbook. Cassette recording for Schwab is HIGHER-RISK than Finviz because (a) OAuth flow cassettes contain the most sensitive secrets in V1 (initial code exchange returns access_token + refresh_token in plaintext body); (b) Schwab API URLs contain `account_hash` segments that are operator-identifying; (c) schwabdev has its own logger surface that requires audit per §A.2.

### §G.1 Pre-flight (Bundle A T-A.0.b operator-paired)

Operator runs (operator-paired with implementer; in elevated terminal):

```
# 1. Confirm Schwab Developer Portal app status (Q1).
#    Operator visits https://developer.schwab.com/ -> apps -> confirms production-tier approval.

# 2. Pin a known-working schwabdev version (T-A.1 acceptance).
pip install 'schwabdev>=2.4.0,<3.0.0'
python -c "import schwabdev; print(schwabdev.__version__)"
#    Record version in plan §A.2 commit-time annotation.

# 3. Verify schwabdev's manual_flow signature matches §E.1.
python -c "import schwabdev; import inspect; print(inspect.signature(schwabdev.auth.manual_flow))"

# 4. Walk through paste-back flow (cassette-driven OFF; live API).
swing schwab setup --environment production --record-cassettes /tmp/schwab-cassette-rec/
#    -> CLI prints consent URL
#    -> operator opens URL in browser; logs in to Schwab; approves
#    -> Schwab redirects to operator's configured callback URL (browser may 404 on the redirect; operator copies the 'code=...' query param from URL bar)
#    -> operator pastes the authorization_code into CLI prompt
#    -> CLI completes OAuth code exchange + persists schwabdev Tokens DB at ~/swing-data/schwab-tokens.production.db
#    -> CLI emits success message; reports active account_hash count

# 5. Save the recorded cassettes (with redaction at record-time per §G.3 below).
```

### §G.2 Per-endpoint cassette recording (Bundle A T-A.10; Bundle B T-B.0.b; Bundle C T-C.0.b)

For each `[VERIFY]`-tagged endpoint in §E, operator runs the corresponding `swing schwab fetch ...` subcommand with the `--record-cassette <path>` flag (NEW; T-A.4 implements as opt-in flag that activates `pytest-recording`'s VCR recording mode). The CLI:

1. Invokes the schwabdev method.
2. Records the request + response to `<path>` via `pytest-recording`'s VCR.py.
3. Applies redaction filters BEFORE writing the cassette file to disk (per §G.3).
4. Prints the recorded cassette path; operator verifies it contains NO token bytes.

### §G.3 Token redaction at record time

Per spec §5 + Finviz precedent + COA B caveat (schwabdev's own logger). Cassettes use the `pytest-recording` plugin's VCR.py configuration:

```python
# conftest.py (Bundle A T-A.10 implements)
@pytest.fixture
def vcr_config():
    return {
        "filter_headers": ["authorization", "cookie", "set-cookie"],
        "filter_query_parameters": [
            "code", "refresh_token", "client_id", "client_secret",
            "redirect_uri", "access_token", "auth",
        ],
        "filter_post_data_parameters": [
            "code", "refresh_token", "client_id", "client_secret",
            "redirect_uri",
        ],
        "before_record_response": _redact_schwab_response_body,
    }
```

`_redact_schwab_response_body` (Bundle A T-A.10 implements) masks the following substrings in any response body before the cassette is written:
- `access_token` field values → `<REDACTED>`.
- `refresh_token` field values → `<REDACTED>`.
- `client_secret` field values → `<REDACTED>`.
- `accountNumber` / `account_number` field values (Schwab returns plaintext account numbers paired with hashes) → `<REDACTED>`.
- `accountHash` / `account_hash` field values → `<HASHED_REDACTED>` (preserve in test fixtures via `<HASHED_REDACTED_PRIMARY>` placeholder so tests can pattern-match the slot).
- Any 32+ hex-char token-like substring NOT inside a `<REDACTED>` block → `<REDACTED>`.

### §G.4 Re-recording trigger

Re-record per-endpoint cassette when:
- Schwab upstream API changes shape (live test `test_schwab_api_live.py` fails with shape diff).
- schwabdev library upgrade introduces request/response shape drift.
- Operator's account_hash changes (e.g., new brokerage account; multi-account V2 — not V1).

Re-recording procedure: operator runs `swing schwab fetch --record-cassette tests/integrations/cassettes/<name>.yaml --environment production`; commits the new cassette (verified token-redacted via T-A.10 sentinel-leak audit before commit).

### §G.5 Operator-attention items for Task 0.b session

Before Task 0.b session begins, orchestrator confirms:
- Operator's production-tier Schwab Developer Portal app is approved (Q1).
- Operator has access to a Schwab brokerage account login.
- Operator-paired session window has ≥ 2 hours blocked (cassette recording, refresh-rotation observation, market-data endpoint verification).
- Tested test corpus baseline: `pytest -m "not slow" -q` green at HEAD before dispatch.

Items operator records during Task 0.b:
- Verification observations for the 6 §D open questions.
- Schwab's actual scope-string format (§D.4).
- Schwab's refresh-token rotation behavior (§D.5).
- Schwab's market-data rate-limit threshold (§D.6).
- Any schwabdev API drift from synthesized signatures (§E.1).

---

## §H Algorithm spec (per surface + per bundle)

### §H.1 OAuth paste-back setup flow (Bundle A T-A.4)

Algorithm for `swing schwab setup --environment {sandbox,production}`:

1. Server-stamp `start_ts = now_ms()`.
2. Read `cfg.integrations.schwab.environment` cascade; CLI flag `--environment` overrides for this invocation.
3. Refuse to proceed if pipeline is `state='running'` per spec §3.2.4 (b) UNLESS `--force` flag passed (mirrors `SchwabPipelineActiveError`).
4. Prompt for `client_id`, `client_secret` (text input; secret echoing disabled via `click.prompt(..., hide_input=True)`).
5. Resolve target tokens DB path: `path = Path(_user_home()) / "swing-data" / f"schwab-tokens.{environment}.db"`.
6. Construct `tokens_db_parent = path.parent`; ensure dir exists.
7. INSERT `schwab_api_calls` row with `endpoint='oauth.code_exchange'`, `status='in_flight'`, `surface='cli'`, `environment=<env>`, `pipeline_run_id=NULL`, `ts=start_ts`.
8. Invoke `with _suppress_transport_debug_logs(): schwabdev.auth.manual_flow(app_key=client_id, app_secret=client_secret, callback_url='https://127.0.0.1', tokens_db=str(path))`.
   - schwabdev prints consent URL; awaits operator paste of authorization code via stdin.
   - schwabdev exchanges code for tokens; persists to SQLite DB at `path`.
9. On success: UPDATE audit row with `http_status=200`, `status='success'`, `response_time_ms=<elapsed>`, `signature_hash=<sha256_of_response_envelope>`. Compute envelope per §H.9.
10. On `schwabdev.exceptions.AuthError` (or whatever schwabdev raises): UPDATE audit row with `status='auth_failed'`, `error_message=<redacted excerpt>`. Raise `SchwabAuthError` from CLI; exit with non-zero status.
11. On schwabdev call success path: invoke `accounts.linked` (separate `swing/integrations/schwab/trader.py:get_accounts_linked()` call which itself wraps INSERT/UPDATE for `endpoint='accounts.linked'`); CLI receives hash set.
12. If multiple hashes returned: CLI prompts operator to pick a primary. Set `cfg.integrations.schwab.account_hash` via the standard cfg-set path (`swing/config_user.py:write_user_overrides({"integrations.schwab.account_hash": <hash>})`). Note: this routes through user-config.toml (per CLAUDE.md gotcha, monkeypatch USERPROFILE+HOME in tests — applies to `tests/cli/test_schwab_cli.py:test_setup_picks_primary_account_hash`).
13. If single hash: auto-set; inform operator.
14. Emit success message (per spec §3.2.1 step 11): "Setup complete. Tokens DB written at `<path>`. To activate this env: `swing config set integrations.schwab.environment <env>`. Then verify with `swing schwab status`."
15. CRITICAL: emit final advisory line (per spec §3.2.6): "WARNING: schwab-tokens.{env}.db contains plaintext OAuth state. Do not back this file up to cloud storage / shared filesystems. To revoke: 'swing schwab logout'."

Discriminating test pattern (T-A.4): stub schwabdev.auth.manual_flow to return a known Tokens shape; assert (a) audit row written with `status='success'`; (b) tokens DB file exists at expected path; (c) primary account_hash cfg cascade written; (d) success message printed; (e) advisory warning printed.

### §H.2 Force-refresh CLI (Bundle A T-A.5)

Algorithm for `swing schwab refresh`:

1. Server-stamp `start_ts`.
2. Resolve active env per cfg cascade.
3. Resolve tokens DB path.
4. INSERT `schwab_api_calls` row with `endpoint='oauth.refresh'`, `status='in_flight'`, `surface='cli'`.
5. Construct `schwabdev.tokens.Tokens(tokens_db=str(path))`; invoke `tokens.update_tokens(force_refresh_token=True)`.
6. Wrap in `try/except` for: `schwabdev.exceptions.RefreshTokenExpired` (or equivalent) → map to `SchwabRefreshTokenExpiredError`; `schwabdev.exceptions.AuthError` → `SchwabAuthError`; `requests.RequestException` → `SchwabApiError`; concurrent-refresh exception → `SchwabConcurrentRefreshError`.
7. UPDATE audit row with final outcome.
8. If success: emit "Refresh complete. New access_token valid for <N>m <N>s."
9. If `SchwabRefreshTokenExpiredError`: emit operator-actionable "Refresh token has expired or been revoked. Run `swing schwab setup --environment <env>` to re-auth."

### §H.3 SchwabClient base URL resolution (§D.1 deferred verification)

Algorithm for `SchwabClient.__init__`:

```
def __init__(self, cfg, environment, conn):
    self._cfg = cfg.integrations.schwab
    self._environment = environment  # 'sandbox' or 'production'
    self._conn = conn  # for audit-row INSERT/UPDATE

    # Resolve tokens DB path
    self._tokens_db_path = (
        Path(_user_home()) / "swing-data" / f"schwab-tokens.{environment}.db"
    )

    # Resolve base URL from env (Task 0.b verifies; default synthesized)
    self._base_url = self._resolve_base_url(environment)

    # Construct schwabdev Client (composition)
    self._schwabdev_client = schwabdev.Client(
        app_key=...,  # read from Tokens DB at first refresh
        app_secret=...,
        callback_url='https://127.0.0.1',
        tokens_db=str(self._tokens_db_path),
        # base_url=self._base_url  # if schwabdev supports; else our wrapper handles
    )
```

`_resolve_base_url(env)` returns:
- `'sandbox'` → `'https://api-sandbox.schwabapi.com'` (SYNTHESIZED; Task 0.b verifies; per §D.1)
- `'production'` → `'https://api.schwabapi.com'` (matches public Schwab API docs)

If Task 0.b verification shows the sandbox URL differs, T-A.3 acceptance test pins the actual value + fixture updates the constant.

### §H.4 Pipeline step ordering + algorithm

Per spec §3.4.1 + §3.4.2. New steps:

#### §H.4.1 `_step_schwab_snapshot(conn, cfg, pipeline_run_id)` (Bundle B T-B.3)

```
1. Read cfg.integrations.schwab.environment; cfg.integrations.schwab.account_hash.
2. If account_hash is None: log WARNING; update lease.schwab_snapshot_status='skipped_no_account_hash'; return.
3. Construct SchwabClient(cfg, environment, conn).
4. Audit-row INSERT for endpoint='accounts.details' via record_call_start; capture call_id.
5. Invoke trader.get_account_details(client, account_hash). Wraps schwabdev.Client.account_details(...).
6. On schwabdev exception:
   - 401 expired access_token: auto-refresh once (re-invoke); on second 401, raise SchwabAuthError + audit status='auth_failed'.
   - 429: retry once with Retry-After respect (mirror Finviz pattern); on second 429, raise SchwabRateLimitError + audit status='rate_limited'.
   - 5xx / network: SchwabApiError + audit status='error'.
   - All exceptions update audit row via record_call_finish; pipeline step continues per §3.4.4 with lease.schwab_snapshot_status='failed'.
7. On success: mapper produces SchwabAccountResponse. record_call_finish with status='success', signature_hash.
8. Production-only gate (per §A.3 + §3.6.3):
   IF environment == 'production':
     a. Compute snapshot_date = last_completed_session(datetime.now()).
     b. Invoke service-layer record_snapshot(conn,
            equity_dollars=response.net_liquidating_value,
            snapshot_date=snapshot_date,
            source='schwab_api',
            source_artifact_path=f'schwab_api:call/{call_id}',
            recorded_by='schwab_api',
            notes=None).
        Note: service owns BEGIN IMMEDIATE; conn MUST NOT have open tx at this call site.
     c. Capture returned snapshot.snapshot_id.
     d. Invoke combined post-write linkage service:
        audit_service.link_snapshot_and_stamp_account_hash(
            conn,
            call_id=call_id,
            snapshot_id=snapshot_id,
            account_hash=cfg.integrations.schwab.account_hash,
        )
        Service owns ONE BEGIN IMMEDIATE; performs BOTH UPDATEs atomically:
          - UPDATE schwab_api_calls SET linked_snapshot_id = ? WHERE call_id = ?
          - UPDATE account_equity_snapshots SET schwab_account_hash = ? WHERE snapshot_id = ?
        ONE tx2 covers both side-effects (R2 Major #3 fix — reduces blast
        radius from two crash windows to one).
   IF environment == 'sandbox':
     - Skip record_snapshot entirely.
     - Audit row remains with status='success' + linked_snapshot_id=NULL.
9. Update lease.schwab_snapshot_status='completed'.

**§H.4.1.bis Crash-window + same-day-UPSERT provenance asymmetry (Codex R1 Major #4 + R2 Major #3 + R3 Major #4 disposition):**

**Same-day-UPSERT provenance asymmetry (per Codex R3 Major #4):**

`record_snapshot()` UPSERTs on `(snapshot_date, source)` per Phase 9 Sub-bundle C contract — re-recording for the same date keeps the existing `snapshot_id` but OVERWRITES `source_artifact_path`. Consequence: if two `_step_schwab_snapshot` calls (or pipeline + `swing schwab fetch --snapshot`) both write for the same `snapshot_date`:
- Both audit rows in `schwab_api_calls` link to the SAME `snapshot_id` via `linked_snapshot_id` (a successful tx2 on each).
- The snapshot's `source_artifact_path` URI points back to ONLY the LATEST call (most recent UPSERT wins on that column).
- Bidirectional provenance is therefore ASYMMETRIC: audit-row-to-snapshot is many-to-one (multiple audit rows can share one snapshot); snapshot-to-audit-row via URI is one-to-one-and-latest.

**Plan disposition (ACCEPT — this is correct behavior for the source-ladder UPSERT contract; clarify acceptance in S7 + here):**
- This is NOT a bug; it is the deliberate consequence of Phase 9 source-ladder's per-`(date, source)` PK preservation. Multiple recordings on the same date for the same source represent operator/pipeline replays; the latest write reflects current Schwab API state; older audit rows preserve their HTTP transcripts but no longer own the snapshot's reverse URI.
- §K.2 S7 acceptance UPDATED: "snapshot URI references AN EXISTING call_id (the latest writer); audit rows whose `linked_snapshot_id` matches the snapshot but whose call_id is NOT the URI's referenced one are ACCEPTABLE (informational; represent earlier-same-day writes); ZERO orphans (URIs that reference nonexistent call_ids)."
- §K.2 S7 + §H.4.1.bis discriminating test patterns updated below.

---

**Crash-window between steps b/c and d (Codex R1 Major #4 + R2 Major #3 disposition):**

Steps 8b (record_snapshot in tx1) and 8d (combined audit-link + account_hash-stamp in tx2) are separate transactions because record_snapshot REJECTS caller-held tx (Phase 9 Sub-bundle C `CallerHeldTransactionError` contract; CANNOT combine into one BEGIN IMMEDIATE). This admits a narrow crash window: a process crash between tx1 commit + tx2 commit leaves a valid `account_equity_snapshots` row (`source_artifact_path='schwab_api:call/{call_id}'`) but BOTH (a) the audit row's `linked_snapshot_id` is NULL AND (b) the snapshot row's `schwab_account_hash` is NULL.

**R2 Major #3 mitigation:** combining the two side-effects into ONE tx2 (per step 8d above) ensures both NULL cases occur TOGETHER if at all — never one without the other. Reduces the operator-visible recovery surface to a single check.

**Plan disposition (ACCEPT-WITH-RATIONALE):**
- Provenance is still recoverable via `source_artifact_path` URI: scan `account_equity_snapshots WHERE source_artifact_path LIKE 'schwab_api:call/%'` to find domain rows paired with audit rows; the URI's `{call_id}` is the reverse pointer.
- Reciprocal: scan `reconciliation_runs WHERE source_artifact_path LIKE 'schwab_api:call/%' AND schwab_api_call_id IS NULL` to find reconciliation rows whose paired audit row missed its tx2.
- `schwab_account_hash` is recoverable: the URI identifies the call_id; the audit row's `environment` field identifies the env; the operator's `cfg.integrations.schwab.account_hash` was the active value at the time (single-account V1; doesn't change without explicit operator action via `swing config set`). Recovery query: `UPDATE account_equity_snapshots SET schwab_account_hash = ? WHERE source_artifact_path LIKE 'schwab_api:call/%' AND schwab_account_hash IS NULL`.
- §K.2 S7 (audit-row pairing integrity) acceptance UPDATED to: zero stuck-`in_flight` rows; orphaned successful-but-NULL-linked rows ACCEPTABLE (INFO log entry at `swing schwab status` execution, NOT a failure mode). NULL `schwab_account_hash` on `source='schwab_api'` snapshot rows is ALSO ACCEPTABLE (same INFO log entry).
- **Operator-facing recovery procedure** added to §I.4 "Emergency recovery" section: `swing schwab audit relink` (V2 candidate CLI subcommand; deferred to Phase 11 V2 backlog at phase3e-todo) scans for unlinked audit rows + unstampped account_hash + backfills BOTH from `source_artifact_path` + cfg.account_hash. V1 omits the subcommand; operator can run a two-statement SQL update if needed.

Alternatives considered + rejected:
- **(a) Combine into a single tx by relaxing the CallerHeldTransactionError contract on record_snapshot.** REJECTED — Phase 9 Sub-bundle C locked the contract; reversing it requires a Phase 9 dispatch revision. Not Schwab's job.
- **(b) Compensating transaction on crash detection at next pipeline run.** Possible but adds machinery for a vanishingly rare event (process crash mid-pipeline mid-step). V2 candidate via the `swing schwab audit relink` subcommand above.
- **(c) Best-effort UPDATE inside record_snapshot's tx via a callback parameter.** Violates separation of concerns (Phase 9 service is generic; should not know about Schwab audit table).

Discriminating test (T-A.9): simulate the crash window via test fixture (commit tx1; raise during tx2; resume); assert audit row is `status='success'` + `linked_snapshot_id=NULL` + domain row exists with parseable URI; assert provenance chase reconciles both directions.
```

#### §H.4.2 `_step_schwab_orders(conn, cfg, pipeline_run_id)` (Bundle B T-B.4)

```
1. Read cfg.integrations.schwab.environment; account_hash; lookback_days.
2. If account_hash is None: skip; lease.schwab_orders_status='skipped_no_account_hash'; return.
3. Compute period_end = last_completed_session(datetime.now()); period_start = period_end - lookback_days.
4. Construct SchwabClient.
5. Audit-row INSERT for endpoint='accounts.orders.list'; capture orders_call_id.
6. trader.get_account_orders(client, account_hash, from_entered_time=period_start.isoformat(), to_entered_time=period_end.isoformat(), status_filter=None).
   - Status filter NULL fetches all WORKING+FILLED+CANCELED+WAIT_TRG to give reconciliation full coverage.
7. On success: orders_response: list[SchwabOrderResponse]. record_call_finish.
8. Audit-row INSERT for endpoint='accounts.transactions.list'; capture tx_call_id.
9. trader.get_account_transactions(client, account_hash, start_date=period_start, end_date=period_end, type_filter='ALL').
10. On success: tx_response: list[SchwabTransactionResponse]. record_call_finish.
11. Audit-row INSERT for endpoint='accounts.details'; capture details_call_id.
    (Re-fetch account details to capture the period-end NLV for equity_delta discrepancy emission, mirroring TOS reconciliation's account-summary read.)
12. trader.get_account_details(client, account_hash).
13. On all-three success: production-only gate:
    IF environment == 'production':
      a. Invoke run_schwab_reconciliation(conn,
             account_hash=account_hash,
             period_start=period_start,
             period_end=period_end,
             schwab_orders_response=orders_response,
             schwab_transactions_response=tx_response,
             schwab_account_response=account_response,
             pipeline_run_id=pipeline_run_id,
             schwab_api_call_id=details_call_id  # OR most-recent of the three; design choice T-B.4).
         Service owns BEGIN IMMEDIATE.
      b. Capture reconciliation_run_id.
      c. UPDATE schwab_api_calls SET linked_reconciliation_run_id = reconciliation_run_id WHERE call_id IN (orders_call_id, tx_call_id, details_call_id).
         (Three audit rows link to ONE reconciliation_run.)
    IF environment == 'sandbox':
      - Skip run_schwab_reconciliation.
14. Update lease.schwab_orders_status='completed'.
```

#### §H.4.3 Step ordering injection point

Modify `swing/pipeline/runner.py` to insert two new steps between `_step_recommendations` and `_step_charts`:

```
_step_finviz_fetch
  _step_evaluate
    _step_daily_management
      _step_watchlist
        _step_recommendations
          _step_schwab_snapshot     <-- NEW
            _step_schwab_orders     <-- NEW
              _step_charts
                _step_export
                  _step_review_log_cadence
```

Rationale per spec §3.4.2 LOCKED:
- BEFORE `_step_charts`: charts can include current-stop overlays from Schwab-detected stop drift (V1 reserves the option; not consumed V1).
- BEFORE `_step_export`: briefing.md + briefing.html render includes LIVE-badge equity figure + reconciliation discrepancy summary automatically.
- AFTER `_step_recommendations`: recommendations consume capital_friction inputs from a snapshot existing at run-start (V2 candidate to move BEFORE recommendations once metric-coupling stabilizes).

Failure tolerance per §3.4.4: both Schwab steps record `schwab_api_calls.status` + `lease.schwab_*_status='failed'`; do NOT abort pipeline; continue to next step.

### §H.5 `run_schwab_reconciliation` service algorithm (Bundle B T-B.4)

Mirrors `swing/trades/reconciliation.py:run_tos_reconciliation` shape verbatim per §A.4. New file: `swing/trades/schwab_reconciliation.py`.

Algorithm:

```
def run_schwab_reconciliation(
    conn,
    *,
    account_hash,
    period_start,
    period_end,
    schwab_orders_response,
    schwab_transactions_response,
    schwab_account_response,
    pipeline_run_id,
    schwab_api_call_id,
) -> int:  # returns reconciliation_run_id

    # 1. Reject caller-held transaction (Phase 9 Sub-bundle B + 8 R3-R4 lesson).
    if conn.in_transaction:
        raise CallerHeldTransactionError(...)

    # 2. Open BEGIN IMMEDIATE.
    conn.execute("BEGIN IMMEDIATE")

    try:
        # 3. INSERT reconciliation_runs row via repo.insert_run (actual function
        #    name verified at swing/data/repos/reconciliation.py:104; NOT
        #    insert_reconciliation_run as earlier drafts incorrectly stated —
        #    R3 Major #3 correction).
        run_id = repo.insert_run(conn,
            source='schwab_api',
            account_hash=account_hash,
            period_start=period_start,
            period_end=period_end,
            source_artifact_path=f'schwab_api:call/{schwab_api_call_id}',
            schwab_api_call_id=schwab_api_call_id,
            account_equity_journal=<journal-side equity sum>,
            account_equity_source=schwab_account_response.net_liquidating_value,
            equity_delta=<journal-side - source-side>,  # per Phase 9 Sub-bundle C T-C.6 sign convention
            state='running',
            started_ts=now_ms(),
        )

        # 4. Per-discrepancy emit (reuse Phase 9 Sub-bundle B emit machinery):
        # 4a. Stop mismatch:
        for journal_trade in list_open_trades_in_period(conn, period_start, period_end):
            schwab_working_stop = find_working_stop_in_orders(
                schwab_orders_response, journal_trade.ticker
            )
            if schwab_working_stop is not None:
                if abs(schwab_working_stop.price - journal_trade.current_stop) > 0.01:
                    repo.insert_reconciliation_discrepancy(conn,
                        run_id=run_id,
                        type='stop_mismatch',
                        field_name='current_stop',
                        ticker=journal_trade.ticker,
                        expected=str(journal_trade.current_stop),
                        actual=str(schwab_working_stop.price),
                        material=MATERIAL_BY_TYPE['stop_mismatch'],
                        ...)

        # 4b. Position qty mismatch:
        for journal_trade in list_open_trades_in_period(conn, ...):
            schwab_position_qty = find_position_qty(
                schwab_account_response.positions, journal_trade.ticker
            )
            if schwab_position_qty != journal_trade.qty:
                repo.insert_reconciliation_discrepancy(conn,
                    type='position_qty_mismatch', ...)

        # 4c. Fill matching (close_price_mismatch / entry_price_mismatch /
        #     unmatched_open_fill / unmatched_close_fill):
        for journal_fill in list_fills_in_period(conn, period_start, period_end):
            schwab_fill = match_to_schwab_order(schwab_orders_response, journal_fill)
            if schwab_fill is None:
                if journal_fill.side == 'open':
                    insert_discrepancy(type='unmatched_open_fill', ...)
                else:
                    insert_discrepancy(type='unmatched_close_fill', ...)
            elif abs(schwab_fill.price - journal_fill.price) > 0.01:
                kind = 'close_price_mismatch' if journal_fill.side == 'close' \
                       else 'entry_price_mismatch'
                insert_discrepancy(type=kind, ...)

        # 4d. Cash movement mismatch (deposits / transfers):
        for journal_cm in list_cash_movements_in_period(conn, ...):
            schwab_tx = match_to_schwab_transaction(schwab_transactions_response, journal_cm)
            if schwab_tx is None:
                # No corresponding source-side tx -> emit
                insert_discrepancy(type='cash_movement_mismatch', ...)
            elif abs(schwab_tx.net_amount - journal_cm.amount) > 0.01:
                insert_discrepancy(type='cash_movement_mismatch', ...)

        # 4e. Equity delta (per Phase 9 Sub-bundle C T-C.6):
        IF abs(equity_delta) > 10.00:  # $10 threshold; per spec §3.2 LOCK
            insert_discrepancy(type='equity_delta',
                expected=str(journal_equity),
                actual=str(schwab_account_response.net_liquidating_value),
                material=...)

        # 5. UPDATE state='completed', finished_ts.
        repo.update_reconciliation_run_state(conn, run_id=run_id, state='completed', finished_ts=now_ms())

        conn.execute("COMMIT")
        return run_id

    except Exception:
        conn.execute("ROLLBACK")
        # Per spec §3.3.3 preserve run row with state='failed' (Phase 9 Sub-bundle B pattern)?
        # Phase 9 actually does ROLLBACK + UPDATE state='failed' in a SEPARATE transaction.
        # T-B.4 mirrors that pattern exactly: outer rollback first, then a new BEGIN
        # IMMEDIATE to UPDATE the now-non-existent run_id... wait, run_id INSERT was rolled back.
        # Correct pattern: if INSERT succeeded but discrepancy emission failed, run_row gets
        # UPDATEd to state='failed' in a SEPARATE successive transaction (Phase 9 Sub-bundle
        # B precedent at swing/trades/reconciliation.py:run_tos_reconciliation). T-B.4
        # acceptance: discriminating test plants a deliberate failure mid-discrepancy-emit,
        # asserts reconciliation_run row exists with state='failed' (NOT rolled-back/absent),
        # AND no orphan discrepancies attributed to the run.
        raise
```

### §H.6 Market-data ladder algorithm (Bundle C T-C.3 + T-C.4)

#### §H.6.1 `fetch_quote_via_ladder(ticker, cfg, schwab_client, yfinance_fallback_fn)` (Bundle C)

```
def fetch_quote_via_ladder(ticker, cfg, schwab_client, yfinance_fallback_fn):
    env = cfg.integrations.schwab.environment

    # Sandbox short-circuit per spec §3.6.3:
    if env != 'production' or not cfg.integrations.schwab.marketdata_ladder_enabled:
        entry = yfinance_fallback_fn(ticker)
        return (entry, 'yfinance')

    # Try Schwab first.
    try:
        with _suppress_transport_debug_logs():
            response = schwab_client.get_quotes_batch([ticker])
        quote = response.get(ticker)
        if quote is None:
            # Symbol not in response (partial-response handling per §E.4)
            raise SchwabApiError(404, "symbol not in response")
        entry = PriceCacheEntry(
            ticker=ticker,
            last_price=quote.last_price,
            bid=quote.bid,
            ask=quote.ask,
            provider='schwab_api',
            source='live',  # existing TTL-state field; UNCHANGED
            fetched_at=now_ms(),
        )
        return (entry, 'schwab_api')
    except (SchwabAuthError, SchwabApiError, SchwabRateLimitError) as exc:
        log.warning("Schwab market-data fetch failed for %s; falling back to yfinance: %s", ticker, exc)
        entry = yfinance_fallback_fn(ticker)
        return (entry, 'yfinance')
```

#### §H.6.2 `fetch_window_via_ladder(ticker, start, end, cfg, schwab_client, yfinance_fallback_fn)` (Bundle C)

```
def fetch_window_via_ladder(ticker, start, end, cfg, schwab_client, yfinance_fallback_fn):
    env = cfg.integrations.schwab.environment
    if env != 'production' or not cfg.integrations.schwab.marketdata_ladder_enabled:
        return (yfinance_fallback_fn(ticker, start, end), 'yfinance')

    try:
        with _suppress_transport_debug_logs():
            schwab_window = schwab_client.get_price_history(ticker, start, end)
        # Empty-bars check per §E.5 (handled inside mapper; raises SchwabApiError(204, ...))
        return (schwab_window, 'schwab_api')
    except (SchwabAuthError, SchwabApiError, SchwabRateLimitError) as exc:
        log.warning("Schwab pricehistory failed for %s; falling back to yfinance: %s", ticker, exc)
        return (yfinance_fallback_fn(ticker, start, end), 'yfinance')
```

#### §H.6.3 OHLCV archive Shape A persistence (Bundle C T-C.2)

```
# swing/data/ohlcv_archive.py (modified)
_SOURCE_PRECEDENCE_MARKET_DATA = {'schwab_api': 0, 'yfinance': 1}

def write_window(ticker, window, provider):
    """Write window (DataFrame) to per-(ticker, provider) parquet.

    Append-or-fall-back per CLAUDE.md gotcha + Codex R1 Major #7 fix:
    empty-window check fires BEFORE any write so the existing parquet
    is not clobbered with empty content. Caller (ladder) is responsible
    for ensuring this function only runs on non-empty windows in normal
    flow; this guard is defense-in-depth.
    """
    if window is None or len(window) == 0:
        # NO clobber. Caller already records audit row status='error'.
        return
    path = ARCHIVE_DIR / f"{ticker}.{provider}.parquet"
    _atomic_parquet_write(path, window.to_dataframe() if hasattr(window, 'to_dataframe') else window)

def resolve_ohlcv_window(ticker, start, end):
    """Read both providers' parquet files (if present); merge; filter to window.

    Returns (DataFrame filtered to [start, end], provenance: dict[asof_date, provider]).
    Codex R1 Minor #4: explicit start <= asof_date <= end filter at end.
    """
    # Read both providers' parquet files (if present).
    rows_by_date_by_provider = {}
    for provider in ('schwab_api', 'yfinance'):
        path = ARCHIVE_DIR / f"{ticker}.{provider}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            for row in df.itertuples():
                rows_by_date_by_provider.setdefault(row.asof_date, {})[provider] = row

    # Merge: for each date, pick lowest precedence (= highest priority).
    merged = []
    provenance = {}
    for asof_date in sorted(rows_by_date_by_provider.keys()):
        # Codex R1 Minor #4 fix: filter to [start, end] BEFORE selecting winner.
        if not (start <= asof_date <= end):
            continue
        candidates = rows_by_date_by_provider[asof_date]
        winner_provider = min(candidates.keys(),
                              key=lambda p: _SOURCE_PRECEDENCE_MARKET_DATA[p])
        merged.append(candidates[winner_provider])
        provenance[asof_date] = winner_provider

    return (pd.DataFrame(merged), provenance)

def _backward_compat_rename(ticker):
    """One-shot rename of {TICKER}.parquet -> {TICKER}.yfinance.parquet (T-C.2).

    Codex R1 Major #6 fix: handle the both-files-exist case (partial prior run).
    NO data loss path:
      - If new file (yfinance.parquet) absent + old file present: rename via os.replace.
      - If new file present + old file present: MERGE-AND-QUARANTINE:
        - Read both DataFrames.
        - Concat-deduplicate on asof_date (keep yfinance.parquet's row on conflict —
          assumes yfinance.parquet is the more-recent state; old {TICKER}.parquet was
          the pre-shape-A snapshot).
        - Write merged back to yfinance.parquet via _atomic_parquet_write.
        - Rename old to {TICKER}.parquet.orphan-{timestamp}.parquet (operator-visible
          quarantine; informational only — never read by resolver) so operator can
          inspect post-fact if needed.
      - If new file present + old file absent: no-op (already migrated).
      - If both absent: no-op (no historical data; first-fetch case).
    """
    old_path = ARCHIVE_DIR / f"{ticker}.parquet"
    new_path = ARCHIVE_DIR / f"{ticker}.yfinance.parquet"
    if old_path.exists() and not new_path.exists():
        # Use os.replace (same volume; safe per CLAUDE.md gotcha).
        os.replace(old_path, new_path)
    elif old_path.exists() and new_path.exists():
        # Both exist — merge-and-quarantine to avoid silent data drop.
        old_df = pd.read_parquet(old_path)
        new_df = pd.read_parquet(new_path)
        merged = pd.concat([old_df, new_df]).drop_duplicates(subset=['asof_date'], keep='last')
        _atomic_parquet_write(new_path, merged)
        timestamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
        os.replace(old_path, ARCHIVE_DIR / f"{ticker}.parquet.orphan-{timestamp}.parquet")
    # else: no-op
```

**Discriminating tests (T-C.2 acceptance — extended per Codex R1 Major #6 + Major #7 + Minor #4):**
- Empty-window write: invoke `write_window(ticker, empty_df, 'schwab_api')`; assert NO parquet file created OR existing parquet UNCHANGED.
- Backward-compat both-files-exist: plant `{TICKER}.parquet` (pre-migration content) + `{TICKER}.yfinance.parquet` (post-migration content with overlapping dates); invoke `_backward_compat_rename`; assert merged content exists in `{TICKER}.yfinance.parquet`, orphan file exists at `{TICKER}.parquet.orphan-*.parquet`, no data loss.
- Backward-compat idempotency: invoke `_backward_compat_rename` twice; second invocation is no-op.
- Window filter: plant rows at dates `[2026-01-01, 2026-01-15, 2026-02-01]`; invoke `resolve_ohlcv_window(ticker, start='2026-01-10', end='2026-01-20')`; assert ONLY the 2026-01-15 row returned.

#### §H.6.4 Empty-response transient handling

Per §E.5 + CLAUDE.md gotcha "External-API empty-result must be treated as transient":

- Schwab's `Client.price_history(...)` returning empty bars → mapper raises `SchwabApiError(204, "empty bars")`.
- Caller catches; audit row `status='error'`, `error_message="empty bars (transient)"`.
- Ladder falls back to yfinance.
- Neither parquet file is touched (NO clobber).
- Discriminating test (T-C.5): plant a Schwab response with empty bars; assert `schwab_api_calls` row has `error_message="empty bars (transient)"`; assert `{TICKER}.schwab_api.parquet` is UNCHANGED (or absent if first-call); assert ladder returns yfinance-tagged entry.

### §H.7 New dataclasses + `__post_init__` validators (per §A.9 lesson #1)

Per §B.1 + §E. Each new dataclass MUST have a `__post_init__` validator rejecting invalid input:

- `SchwabApiCall` (audit-row dataclass): `endpoint` in known set; `status` in known set; `surface` in `{pipeline, cli}`; `environment` in `{sandbox, production}`; `http_status` is `None` or `100 <= http_status < 600`; `response_time_ms` is `None` or `>= 0`; `signature_hash` is `None` or matches `^[0-9a-f]{64}$`.
- `SchwabAccountResponse`: `net_liquidating_value` finite; `cash` finite; `buying_power` finite (negative permitted for margin); `recorded_at` ISO ms.
- `SchwabOrderResponse`: `status` enum; `instruction` enum; `order_type` enum; `quantity >= 0`; `price >= 0` if non-None.
- `SchwabTransactionResponse`: `type` enum; `net_amount` finite; ISO date format.
- `SchwabQuoteResponse`: `last_price >= 0`; bid/ask finite.
- `SchwabPriceHistoryWindow`: per-bar invariants (low ≤ min(open,close); high ≥ max(open,close); volume ≥ 0); bars sorted.
- `PriceCacheEntry` (extension; existing field): new `provider: str | None` field in `{None, 'schwab_api', 'yfinance'}`. Existing field validators preserved.

### §H.8 Token redaction in audit `error_message` + logging.Filter for schwabdev loggers

**Three-layer redaction discipline (per Codex R1 Major #5 + R2 Major #1 disposition):**

**Layer 0 — known-value exact-replace from runtime context (Codex R2 Major #1 + R4 Major #1):**

**Known-secret slots (5; R4 Major #1 fix — `authorization_code` REMOVED from the registry).** The OAuth authorization_code is paste-back-collected by `schwabdev.auth.manual_flow()`'s own stdin prompt; the project wrapper never observes the raw code as a Python string (schwabdev consumes it internally and immediately exchanges for tokens). Without observation, the code cannot be registered. **Mitigation:** (a) the code is single-use + immediately invalidated by the token exchange; (b) schwabdev's logger surface is audited for any `code=...`-shaped substring leak (T-A.10 dedicated test). The wrapper's known-secret registry covers the 5 LONG-LIVED secrets that have replay value: `client_id`, `client_secret`, `access_token`, `refresh_token`, `account_hash`.

```python
def _make_redactor(known_secrets: Iterable[str]) -> Callable[[str], str]:
    """Build a redactor closure that exact-replaces every known sensitive
    value before heuristic regexes. Codex R2 Major #1: arbitrary sentinels
    (e.g., 'SENTINEL_DO_NOT_LEAK') are too short for the heuristic patterns;
    runtime context (client_id, client_secret, access_token, refresh_token,
    account_hash) is the authoritative long-lived-secret redaction set.
    `authorization_code` is OMITTED per R4 Major #1 — it is paste-back-only
    inside schwabdev's manual_flow; never observable to the wrapper. T-A.10
    has a separate test verifying schwabdev does not log `code=`-shaped
    substrings.

    `known_secrets` must be the live operator-supplied values at call time —
    NOT placeholder strings. Caller (SchwabClient) provides via context.
    """
    nonempty = [s for s in known_secrets if s and len(s) >= 4]
    def redact(message: str) -> str:
        if not message:
            return message
        excerpt = message[:500]
        for secret in nonempty:
            excerpt = excerpt.replace(secret, "<REDACTED>")
        # Then heuristic patterns (Layer 1, retained as defense-in-depth):
        excerpt = re.sub(r"[a-fA-F0-9]{32,}", "<REDACTED>", excerpt)
        excerpt = re.sub(r"[A-Za-z0-9+/=]{24,}", "<REDACTED>", excerpt)
        return excerpt
    return redact
```

**Layer 1 — heuristic regex redactor (defense-in-depth; folded into Layer 0):**

(Inlined inside `_make_redactor` above. Standalone variant `_redact_error_message_for_audit` is kept as a Layer-1-only fallback for code paths that don't have runtime context, e.g., test fixtures.)

All audit-row `error_message` writes pass through `_make_redactor(known_secrets)` populated from the SchwabClient's active runtime values.

**Layer 2 — `logging.setLogRecordFactory` redaction at record-creation time (R7 Critical #1 redesign):** (Bundle A T-A.10):

The `_suppress_transport_debug_logs()` context manager from §A.2 + Finviz precedent suppresses urllib3 DEBUG-level lines by raising the level to WARNING. But schwabdev's `tokens.py` around line 338 logs `response.text` on auth failure at WARNING or ERROR level (per spec §A.2 caveat) — level-suppression does NOT catch this.

**Earlier R5/R6 designs ALL incorrectly assumed `logging.Filter` attached to a parent or root logger would mutate records emitted by child loggers during propagation.** Per Python's `Logger.callHandlers()` source: during propagation, the call traverses ancestor HANDLERS but does NOT re-apply ancestor logger filters. So a filter attached to the ROOT logger does not fire on records emitted by `schwabdev.tokens` etc.

**Correct V1 approach (Codex R7 Critical #1 fix): `logging.setLogRecordFactory()` redaction at record-creation time.** Every `LogRecord` (regardless of which logger emits or which handler captures) is constructed via `logging.LogRecord.__init__`, which is invoked by the factory registered via `setLogRecordFactory()`. Wrapping the factory with a schwabdev-aware redactor mutates the record BEFORE any handler sees it. Works with stdlib handlers, `pytest`'s `caplog` LogCaptureHandler, third-party handlers, custom handlers — single source of truth.

```python
_ORIGINAL_RECORD_FACTORY: Callable | None = None
_FACTORY_INSTALLED = False
_FACTORY_LOCK = threading.Lock()

_FACTORY_DEPTH = threading.local()  # thread-local recursion guard

def _schwab_record_factory(*args, **kwargs):
    """LogRecord factory wrapping the original. Redacts msg+args at
    creation time for any record whose name starts with 'schwabdev'.
    Non-schwabdev records pass through with a single startswith check.

    R9 Major #1 recursion guard: if a third-party LogRecord factory
    captures our factory as their `orig` and our `ensure_*` later wraps
    them again, the chain `ours -> theirs -> ours -> theirs ...` would
    infinite-recurse. Thread-local `_FACTORY_DEPTH.in_call` short-circuits
    any re-entry from within an active redaction pass — inner re-entrant
    call returns the unmutated record (it has already been redacted by
    the outer pass; double-redaction is safe but wasted work).

    Reads _GLOBAL_KNOWN_SECRETS via _make_redactor_from_global() snapshot
    (taken at every call; thread-safe via the registry lock inside the
    redactor closure).
    """
    if getattr(_FACTORY_DEPTH, 'in_call', False):
        # Re-entry detected. R10 Major #1 fix: do NOT call
        # `_ORIGINAL_RECORD_FACTORY` here — under the adversarial
        # third-party-wraps-our-factory scenario, _ORIGINAL is the third
        # party which calls back into us → loop. Call the stdlib LogRecord
        # constructor directly; it cannot route through any factory.
        # The outer-pass redaction has already mutated the outermost record;
        # this inner call just creates a record that nothing reads (its
        # only consumer is the third-party wrapper that triggered the
        # recursion, and they're already getting the outer redacted result
        # back through the call chain).
        return logging.LogRecord(*args, **kwargs)
    _FACTORY_DEPTH.in_call = True
    try:
        record = _ORIGINAL_RECORD_FACTORY(*args, **kwargs)
        if not record.name.startswith(_SCHWABDEV_LOGGER_PREFIX):
            return record
        redactor = _make_redactor_from_global()
        # Force message interpolation now (so record.msg substitution is final).
        msg = record.getMessage()
        record.msg = redactor(msg)
        record.args = ()  # message already interpolated
        return record
    finally:
        _FACTORY_DEPTH.in_call = False

# Tag for chain detection (R9 Major #1 defense-in-depth).
_schwab_record_factory._is_schwab_factory = True

def _install_schwab_log_redaction_factory_once() -> None:
    """Install the LogRecord factory wrapper EXACTLY ONCE per process.
    Idempotent. Stores original factory in _ORIGINAL_RECORD_FACTORY for
    pass-through. R7 Critical #1 fix replacing the prior root-logger-filter
    approach which was incorrect (filters on ancestor loggers do not fire
    during propagation per Python `Logger.callHandlers()` semantics).
    """
    global _ORIGINAL_RECORD_FACTORY, _FACTORY_INSTALLED
    with _FACTORY_LOCK:
        if _FACTORY_INSTALLED:
            return
        _ORIGINAL_RECORD_FACTORY = logging.getLogRecordFactory()
        logging.setLogRecordFactory(_schwab_record_factory)
        _FACTORY_INSTALLED = True

def ensure_schwab_log_redaction_factory_installed() -> None:
    """Re-install Schwab's redaction factory if another library replaced it.

    R8 Major #2 fix: `logging.setLogRecordFactory()` is process-global; any
    other library calling it AFTER our install silently disables our
    redaction. SchwabClient calls this before every schwabdev API
    invocation; it checks the current factory and re-wraps if needed.

    Idempotent under repeat calls when factory IS already ours. When factory
    has been replaced, captures the current factory as the new "original"
    + reinstalls our wrapper around it so we redact + still pass through to
    whatever the other library wanted.
    """
    global _ORIGINAL_RECORD_FACTORY, _FACTORY_INSTALLED
    with _FACTORY_LOCK:
        current = logging.getLogRecordFactory()
        if current is _schwab_record_factory:
            return  # ours; intact
        # Someone else replaced it. Wrap their factory + reinstall ours.
        _ORIGINAL_RECORD_FACTORY = current
        logging.setLogRecordFactory(_schwab_record_factory)
        _FACTORY_INSTALLED = True  # R11 Minor #2 — invariant cleanup
```

**Process-global invariant:** `_schwab_record_factory` is the active `logging.getLogRecordFactory()` for the lifetime of any Schwab API call. SchwabClient calls `ensure_schwab_log_redaction_factory_installed()` BEFORE every schwabdev call (single function-call cost; ~microseconds). If another library has called `logging.setLogRecordFactory()` in the interim, our wrapper is re-installed around theirs (their factory becomes our new "original" pass-through). Discriminating test: install Schwab factory; install a NO-OP third-party factory; call `ensure_schwab_log_redaction_factory_installed()`; emit `schwabdev.tokens` record with sentinel; assert sentinel redacted.

(The `SchwabLogRedactionFilter` class from prior rounds is RETIRED — it was the wrong API. The factory approach replaces it entirely. `_SCHWABDEV_LOGGER_PREFIX` constant + `_GLOBAL_KNOWN_SECRETS` registry + `register_schwab_secrets()` + `_make_redactor_from_global()` all retained unchanged.)

Process-global registry discipline (per Codex R3 Major #2 — process-global UNION registry; never narrowed):

```python
_SCHWABDEV_LOGGER_PREFIX = 'schwabdev'

# Process-global registry: a single set of all sensitive values seen this
# process. Lifecycle = process lifetime; never narrowed. Multiple SchwabClient
# instances (sandbox + production, or sequential setup/refresh/status invocations)
# all CONTRIBUTE secrets to this set; the LogRecord factory consults the full
# set at record-creation time (R9 Minor #1 wording fix; R7 redesign moved from
# logger-filter to factory-wrapper). Narrowing the registry per-client would
# erase earlier clients' secrets — R3 Major #2.
_GLOBAL_KNOWN_SECRETS: set[str] = set()
(Prior R5/R6 drafts declared `_GLOBAL_FILTER: SchwabLogRedactionFilter | None`; retired per R7. Factory state is `_FACTORY_INSTALLED: bool` + `_ORIGINAL_RECORD_FACTORY: Callable | None` declared at the Layer 2 factory block above.)
_GLOBAL_FILTER_LOCK = threading.Lock()

def register_schwab_secrets(secrets: Iterable[str]) -> None:
    """Add operator-supplied sensitive values to the global redaction set.

    Called at SchwabClient construction, OAuth setup, refresh — anywhere a
    new secret enters the runtime. Idempotent under repeat registration.
    Never removes secrets.
    """
    with _GLOBAL_FILTER_LOCK:
        for s in secrets:
            if s and len(s) >= 4:
                _GLOBAL_KNOWN_SECRETS.add(s)

(The prior `_install_schwab_log_redaction_filter_once()` function — which attached `SchwabLogRedactionFilter` to the root logger — is RETIRED per R7 Critical #1. Replaced by `_install_schwab_log_redaction_factory_once()` above. Implementers MUST use the factory approach; do NOT build the root-logger-filter design described in R5/R6 commit drafts.)

def _make_redactor_from_global() -> Callable[[str], str]:
    """Build a redactor closure that reads _GLOBAL_KNOWN_SECRETS at each call.
    Snapshots the set at message-redaction time so secrets registered AFTER
    redactor construction are picked up on the next log record.
    """
    def redact(message: str) -> str:
        if not message:
            return message
        excerpt = message[:500]
        # Snapshot at call time for safety with concurrent register_schwab_secrets().
        with _GLOBAL_FILTER_LOCK:
            secrets = list(_GLOBAL_KNOWN_SECRETS)
        for s in secrets:
            excerpt = excerpt.replace(s, "<REDACTED>")
        excerpt = re.sub(r"[a-fA-F0-9]{32,}", "<REDACTED>", excerpt)
        excerpt = re.sub(r"[A-Za-z0-9+/=]{24,}", "<REDACTED>", excerpt)
        return excerpt
    return redact
```

**Discipline:** SchwabClient construction calls `register_schwab_secrets([...client's secrets...])` THEN `_install_schwab_log_redaction_factory_once()`. The factory install is a true singleton per process; the registry is additive; the factory reads the registry on every LogRecord creation. Sandbox client + production client + setup CLI + refresh CLI all contribute to the same registry; ALL secrets remain redacted for the lifetime of the process. **R8 Major #2 defense:** SchwabClient additionally invokes `ensure_schwab_log_redaction_factory_installed()` BEFORE every schwabdev API call; this re-wraps the factory if a third-party library has replaced `logging.getLogRecordFactory()` since install. Microsecond-cost check; idempotent when factory is intact.

T-A.10 acceptance:
- `_install_schwab_log_redaction_factory_once()` invoked at SchwabClient construction (R7 Critical #1 redesign — switched from logger-filter to `logging.setLogRecordFactory` because filters on ancestor loggers are NOT applied during propagation per Python `Logger.callHandlers()` semantics); true singleton-per-process via the `_FACTORY_INSTALLED` flag; the factory's redactor reads `_GLOBAL_KNOWN_SECRETS` (process-additive, never narrowed) at each LogRecord creation so secrets registered later are picked up automatically. SchwabClient construction also calls `register_schwab_secrets([...])` to contribute its secrets to the registry.
- Discriminating test #1: inject a NON-token-shaped sentinel (e.g., `"SENTINEL_DO_NOT_LEAK"` — 20 chars, alphanumeric) as a stand-in for `access_token`; trigger schwabdev's auth-failure log path; assert sentinel does NOT appear in any captured log record from `schwabdev.*` loggers. Verifies Layer 0 known-secret exact-replace works for short sentinels that bypass heuristic regex.
- Discriminating test #2: inject sentinels at all 5 long-lived known-secret slots (client_id, client_secret, access_token, refresh_token, account_hash) per R5 Major #1 alignment; each non-token-shaped; grep ALL log records + ALL audit `error_message` columns for each sentinel; ZERO matches. Authorization-code is covered by a SEPARATE non-leak test (per T-A.10 R4 Major #1 disposition) since it is never registered in `_GLOBAL_KNOWN_SECRETS` (paste-back-only inside schwabdev's manual_flow).
- Discriminating test #3 (R8 Minor #3 wording fix): refresh produces new access_token; assert `register_schwab_secrets([new_token])` adds it to `_GLOBAL_KNOWN_SECRETS` (read at record-creation time by the factory); emit a record containing BOTH old + new tokens; assert BOTH redacted (proves the global registry holds the UNION, never narrowed).
- Layer 0 covers known-value exact-replace (catches short sentinels); Layer 1 covers heuristic regex; Layer 2 applies Layer 0+1 to schwabdev's own logger output. All three required.

Sentinel-leak audit test (T-A.10) plants sentinels at multiple injection points + greps the audit-table column + the captured log records for each sentinel; ZERO matches across ALL surfaces.

### §H.9 Signature hash algorithm

Per spec §3.6 column + Finviz `_compute_schema_signature` precedent:

```python
def compute_signature_hash(response_dict: dict, endpoint: str) -> str:
    """SHA-256 of canonicalized response shape (column-set + first-row fingerprint).
    NOT body bytes — drift detection only."""
    # Extract structural fingerprint:
    # - For accounts.details: sorted top-level keys + 'positions' length.
    # - For orders.list: sorted keys of first order (if any) + list length.
    # - For quotes: sorted keys of first symbol entry + symbol count.
    # - For pricehistory: sorted top-level keys + bars length.
    # - For oauth.* : just sorted top-level keys (NOT token bytes).
    fingerprint = json.dumps(_extract_structural_fingerprint(response_dict, endpoint), sort_keys=True)
    return hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()
```

Signature drift between calls triggers an INFO log entry ("Schwab response shape changed for endpoint=<X>: signature was <old>, now <new>") + a CLAUDE.md gotcha note. Operator-actionable observation surface only; not blocking.

### §H.10 `SchwabPipelineActiveError` cross-surface exclusion (Bundle B T-B.5)

Algorithm for CLI `swing schwab fetch [--snapshot|--orders|--all]`:

```python
def _check_pipeline_not_running(conn):
    row = conn.execute(
        "SELECT run_id FROM pipeline_runs WHERE state = 'running' LIMIT 1"
    ).fetchone()
    if row is not None:
        raise SchwabPipelineActiveError(
            f"Pipeline run {row[0]} is currently in flight. Refusing to run "
            f"schwab fetch. Wait for pipeline to complete or kill it (CLI exit non-zero)."
        )
```

Invoked at entry of every CLI subcommand that touches `account_equity_snapshots`/`reconciliation_runs` OR rewrites the tokens DB:

**Protected (5; check + raise unless `--force`):**
- `swing schwab fetch --snapshot`: check + raise → CLI exit 1 with operator-actionable message. NO `--force` override (domain writes are unsafe under concurrent pipeline).
- `swing schwab fetch --orders`: check + raise. NO `--force`.
- `swing schwab fetch --all`: check + raise. NO `--force`.
- `swing schwab logout`: check + raise UNLESS `--force` passed (per spec §3.2.4 (b)).
- `swing schwab setup`: check + raise UNLESS `--force` (rewrites tokens DB; pipeline mid-fetch could read partial state).

**Safe (3; NO check):**
- `swing schwab status`: read-only.
- `swing schwab refresh`: tokens-DB-only write; schwabdev's `RLock` + SQLite `BEGIN EXCLUSIVE` handle concurrent refresh races (per spec §3.2.4 (a) + COA B disposition).
- `swing schwab fetch --verify-marketdata`: verification-only; cache writes skipped regardless of env.

Discriminating test (T-B.6): plant a `pipeline_runs` row with `state='running'`; invoke each CLI subcommand; assert SchwabPipelineActiveError raised for the 5 protected ones (3 NO-`--force` + 2 with `--force` override available); assert NO error for the 3 safe ones. **5 protected + 3 safe = 8 CLI subcommands total** (corrects Codex R1 Major #3 where T-B.6 text said "ALL 6" + listed refresh as protected).

---

## §I `docs/cycle-checklist.md` updates (Bundle D T-D.2 binding spec)

Per spec §7.4 + §7.1 + §7.2. Insertions to `docs/cycle-checklist.md`:

### §I.1 One-time setup section (NEW; add after existing "Initial setup" section)

```markdown
### Schwab API integration (one-time)

After project install + before first pipeline run:

1. **Register Schwab Developer Portal app.**
   - Visit https://developer.schwab.com/.
   - Create new app; name e.g. "Swing Trading Personal".
   - Request Trader API + Market Data API access.
   - Configure callback URL to `https://127.0.0.1` (paste-back flow; no listener required).
   - Note `client_id` + `client_secret`.
   - Await production-tier approval (Schwab review; days to weeks).

2. **Run setup:**
   ```
   swing schwab setup --environment production
   # -> prompts for client_id + client_secret
   # -> prints consent URL
   # -> open URL in browser, log in, approve
   # -> browser redirects to https://127.0.0.1/?code=<CODE>... (404 page; copy the 'code' query param from URL bar)
   # -> paste authorization code at CLI prompt
   # -> CLI persists tokens DB at ~/swing-data/schwab-tokens.production.db
   # -> CLI prompts to pick primary account_hash if multiple
   # -> CLI writes integrations.schwab.account_hash to user-config.toml
   ```

3. **Activate environment:**
   ```
   swing config set integrations.schwab.environment production
   swing schwab status   # confirm tokens DB valid; account_hash set
   ```

4. **Verify first fetch:**
   ```
   swing schwab fetch --snapshot   # writes one account_equity_snapshot row
   swing schwab fetch --orders     # writes one reconciliation_run + any discrepancies
   ```

5. **(Optional) Sandbox mode for cassette recording:**
   ```
   swing schwab setup --environment sandbox   # separate sandbox app credentials
   # Sandbox is verification-only: API calls + audit rows; ZERO domain writes.
   ```
```

### §I.2 Daily cycle section (NEW; add to existing "Daily" subsection)

```markdown
- **Verify briefing.md Schwab section.** Each pipeline run's `briefing.md` now includes a "Schwab integration" section reporting latest equity snapshot + reconciliation discrepancy count. If banner "Schwab integration: degraded" appears, run `swing schwab status` to diagnose.
```

### §I.3 Weekly cycle section (NEW)

```markdown
- **Verify Schwab refresh_token validity.** Run `swing schwab status` weekly. Schwab production-tier refresh_tokens have ~90-day TTL; sandbox-tier ~7 days. If `refresh_token: valid (N days remaining)` shows < 14 days, plan to run `swing schwab setup` again to re-bootstrap before expiry.
```

### §I.4 Emergency recovery section (NEW)

```markdown
- **Schwab refresh_token expired or revoked at Schwab Developer Portal:**
  ```
  swing schwab logout
  swing schwab setup --environment production
  swing schwab fetch --snapshot   # verify recovery
  ```

- **Schwab Developer Portal app reapproval / scope change:**
  ```
  swing schwab logout
  swing schwab setup --environment production
  ```

- **Tokens DB corruption:**
  ```
  rm ~/swing-data/schwab-tokens.production.db
  swing schwab setup --environment production
  ```
```

---

## §J `CLAUDE.md` additions (Bundle D T-D.4 binding spec)

Per spec §3.2.6 + project-internal gotcha catalog discipline. Bundle D T-D.4 adds the following entries to `CLAUDE.md`'s **Gotchas** section (verbatim where bracketed; orchestrator-final wording in implementer dispatch):

### §J.1 Schwab tokens DB location + plaintext-state hazard

```
- **Schwab tokens DB stored at `~/swing-data/schwab-tokens.{env}.db`; plaintext OAuth state at rest V1.** Per-environment SQLite databases managed by `schwabdev`'s `Tokens` class hold `client_id` + `client_secret` + `access_token` + `refresh_token` as plaintext columns. ACL via Windows user-profile inheritance OR POSIX `chmod 600` is the only V1 protection. Filesystem-level threat model: anyone with read access to the file can impersonate the operator's Schwab API session until refresh_token TTL expires or operator revokes via Schwab Developer Portal. `.gitignore` patterns at `swing-data/schwab-tokens.*.db` (+ `-journal`/`-shm`/`-wal` SQLite-internal files) cover the file family. V2 hardening (post-Phase-11 dispatch): schwabdev's optional `encryption=<key>` constructor parameter wraps the DB in Fernet AES-128 encryption-at-rest; operator-paired key management.
```

### §J.2 Schwab CLI vs pipeline concurrency exclusion (`SchwabPipelineActiveError`)

```
- **Schwab CLI subcommands that write to `account_equity_snapshots` / `reconciliation_runs` REFUSE while pipeline is `state='running'`.** Mirror of Finviz `FinvizPipelineActiveError` precedent. Affected subcommands: `swing schwab fetch --snapshot|--orders|--all`; also `setup`/`logout` (without `--force`). Safe subcommands: `status` (read-only); `refresh` (tokens DB only); `fetch --verify-marketdata` (no cache writes). CLI surface checks `SELECT run_id FROM pipeline_runs WHERE state = 'running' LIMIT 1`; raises `SchwabPipelineActiveError` if non-empty. Discipline reason: concurrent pipeline + CLI snapshot UPSERTs both UPDATE the same `(snapshot_date, source='schwab_api')` row with `source_artifact_path` overwriting last-writer-wins; audit row pairings drift.
```

### §J.3 Schwab production-only domain writes gate

```
- **Schwab API integration writes domain rows ONLY when `cfg.integrations.schwab.environment == 'production'`.** Under `environment='sandbox'`, the pipeline + CLI `fetch` subcommands invoke schwabdev API calls + write `schwab_api_calls` audit rows + capture `signature_hash` for drift detection — but the `record_snapshot(source='schwab_api', ...)` + `run_schwab_reconciliation(...)` calls are SHORT-CIRCUITED (audit row written; domain row not written; audit row's `linked_*_id` remains NULL). Market-data ladder also short-circuits under sandbox — `PriceCache`/`OhlcvCache` fall through directly to yfinance. Rationale: sandbox-environment responses contain synthetic Schwab data; without the gate, the source-ladder would have Schwab winning over manual/TOS and silently contaminate production metrics (Phase 10 LIVE-badge equity), reconciliation discrepancies, and cohort analysis. Discriminating tests: `test_schwab_sandbox_gating.py:test_snapshot_under_sandbox_writes_audit_skips_domain` + `test_orders_under_sandbox_writes_audit_skips_domain` + `test_marketdata_cache_under_sandbox_falls_through_to_yfinance`.
```

### §J.4 schwabdev wrapping discipline + logger caveat + LogRecordFactory redaction (R9 Minor #2 — final factory-based design)

```
- **schwabdev's own loggers must be covered by content-redacting `logging.setLogRecordFactory` wrapper (NOT level suppression and NOT a logger-attached `logging.Filter`).** Level-suppression via `_suppress_transport_debug_logs()` only mutes DEBUG-level urllib3 lines; schwabdev's `tokens.py` around line 338 logs `response.text` on auth failure at WARNING/ERROR level (per spec §A.2 caveat), which level-suppression does NOT catch. A `logging.Filter` attached to ancestor loggers does NOT fire for records emitted by child loggers during propagation (per Python `Logger.callHandlers()` semantics — only ancestor HANDLERS run on propagated records, not ancestor filters). The project installs `_schwab_record_factory` via `logging.setLogRecordFactory()` ONCE per process at SchwabClient construction; the factory mutates `LogRecord.msg` for records whose name starts with `schwabdev` at record-CREATION time, BEFORE any handler/logger sees it. The factory redactor scrubs the LogRecord via a process-global registry that (a) exact-replaces 5 long-lived known-secret slots: `client_id`, `client_secret`, `access_token`, `refresh_token`, `account_hash` (`authorization_code` covered separately by non-leak test since it is paste-back-only inside schwabdev's `manual_flow`); and (b) applies heuristic regex for 32+ hex-char and 24+ base64-char sequences as defense-in-depth. Thread-local recursion guard (`_FACTORY_DEPTH.in_call`) defends against third-party LogRecord factory chaining patterns that could otherwise infinite-recurse. `ensure_schwab_log_redaction_factory_installed()` is called by SchwabClient before every schwabdev API call to detect + recover from third-party factory replacements. Sentinel-leak audit test at `tests/integrations/test_schwab_token_redaction_audit.py` plants NON-token-shaped sentinels at all 5 long-lived slots + greps all log records (including schwabdev's WARNING/ERROR-level output) + all audit `error_message` columns + stdout + stderr; ZERO matches asserted. Separate authorization-code non-leak test asserts no `code=...` substring in any captured surface.
```

### §J.5 Schwab cassette runbook pointer

```
- **Schwab cassette staleness runbook.** If `tests/integrations/test_schwab_*_live.py` (slow-marked) fails on response-shape diff after a Schwab upstream change OR schwabdev library upgrade, re-record cassettes per `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` §G runbook. Operator-paired session required (no automated cassette regeneration; live API access needed). Cassette filter-list at `tests/conftest.py:vcr_config` covers `authorization` header, OAuth query+POST params (`code`, `refresh_token`, `client_id`, `client_secret`, `redirect_uri`), and response-body redaction of `access_token` / `refresh_token` / `accountNumber` / `accountHash` substrings + any 32+ hex-char token-like sequences.
```

### §J.6 Source-artifact reference URI shape

```
- **Schwab API source-artifact reference shape locked.** Every `account_equity_snapshots` row written via `source='schwab_api'` carries `source_artifact_path = "schwab_api:call/{call_id}"` (URI-style opaque reference to the corresponding `schwab_api_calls` audit row). Every `reconciliation_runs` row written via `source='schwab_api'` carries the same URI shape PLUS the FK column `schwab_api_call_id`. Reverse pointer: `schwab_api_calls.linked_snapshot_id` (FK to `account_equity_snapshots(snapshot_id)`; `ON DELETE SET NULL`) + `linked_reconciliation_run_id` (FK to `reconciliation_runs(run_id)`; `ON DELETE SET NULL`). Provenance chase is bidirectional. Do NOT use the raw Schwab API URL (contains `account_hash` segment).
```

---

## §K Verification gates (executing-plans implementer; binding per sub-bundle)

Each sub-bundle has a per-bundle verification gate. ALL sub-bundle gates must PASS before the bundle merges to main.

### §K.1 Sub-bundle A verification gate (5 surfaces)

| Surface | Gate criteria | Witness |
|---|---|---|
| S1 (inline pytest+ruff+migration) | `pytest -m "not slow" -q` green at +N tests; ruff baseline unchanged at 18; `pytest tests/integrations/test_schwab_migration_0018.py` green; `swing db-migrate` runs cleanly + EXPECTED_SCHEMA_VERSION = 18 | inline pytest output |
| S2 (operator-paired OAuth flow) | Operator runs `swing schwab setup --environment production` end-to-end; tokens DB persisted; account_hash captured; advisory warning printed; sentinel-leak audit GREEN | Chrome MCP **NOT REQUIRED** — CLI-driven; operator-paired terminal session |
| S3 (`swing schwab refresh` round-trip) | After S2, operator runs `swing schwab refresh`; access_token mutates; audit row `endpoint='oauth.refresh', status='success'` written | terminal session |
| S4 (`swing schwab logout`) | After S3, operator runs `swing schwab logout`; tokens DB renamed to `*.deleted-<ts>`; advisory message printed; subsequent `swing schwab status` reports PROVISIONAL state | terminal session |
| S5 (audit row lifecycle integrity) | After full A+S2+S3+S4 flow, `sqlite3` query on `schwab_api_calls` shows 4-5 rows total (code_exchange + accounts.linked + refresh + revoke), all with `status` ∈ `{success, error, auth_failed}` (no stuck `in_flight`); per-row `surface='cli'`, `environment='production'`, `linked_*_id=NULL` (none linked yet) | sqlite3 query |

**Operator-witnessed gate: NOT REQUIRED** for Sub-bundle A web-render surfaces (no HTMX changes; CLI-only). T-A.10 sentinel-leak audit fixture is the binding regression coverage.

### §K.2 Sub-bundle B verification gate (7 surfaces)

| Surface | Gate criteria |
|---|---|
| S1 (inline pytest+ruff+migration) | `pytest -m "not slow" -q` green at +N tests; ruff 18 |
| S2 (`_step_schwab_snapshot` production-path) | Operator runs full pipeline under `environment='production'`; `briefing.md` shows Schwab snapshot value matching live API NLV; `account_equity_snapshots` row inserted with `source='schwab_api'`, `source_artifact_path='schwab_api:call/{call_id}'`, `schwab_account_hash` populated; reciprocal `schwab_api_calls.linked_snapshot_id` populated (or recoverably NULL per §H.4.1.bis crash-window disposition). NB: `account_equity_snapshots` does NOT have a `schwab_api_call_id` column — provenance is via `source_artifact_path` URI + reciprocal FK on audit table (R2 Major #4 wording fix). |
| S3 (`_step_schwab_orders` production-path) | Same pipeline run produces `reconciliation_runs` row with `source='schwab_api'`; expected discrepancies (or zero discrepancies) match operator's actual brokerage state; `schwab_api_call_id` FK populated on reconciliation_runs row |
| S4 (sandbox short-circuit) | Operator flips `environment` to sandbox; runs pipeline; verifies audit rows written + ZERO new `account_equity_snapshots` or `reconciliation_runs` rows |
| S5 (`SchwabPipelineActiveError`) | Operator starts pipeline; in second terminal runs `swing schwab fetch --snapshot`; verifies exit non-zero + operator-actionable message |
| S6 (Phase 10 capital-friction LIVE badge) | After S2, operator visits `/metrics/capital-friction`; LIVE badge displays Schwab-sourced equity value (consume Phase 10 source-ladder transparently) |
| S7 (audit-row pairing integrity) | Post-pipeline, `sqlite3` query asserts: (a) zero `status='in_flight'` rows in steady state (stuck-in-flight is unrecoverable; crash recovery does NOT auto-finalize per spec §3.6.1 final paragraph); (b) every `account_equity_snapshots` row with `source='schwab_api'` has a parseable `source_artifact_path = 'schwab_api:call/{call_id}'` where the referenced call_id exists. **ACCEPTABLE cases per §H.4.1.bis (informational; INFO log entry, NOT a failure):** (1) crash-window successful-but-NULL-linked rows (R1 Major #4); (2) snapshot row with NULL `schwab_account_hash` paired with NULL `linked_snapshot_id` on its audit row, occurring together (R2 Major #3 combined-tx2); (3) **same-day-UPSERT provenance asymmetry (R3 Major #4): multiple audit rows can share `linked_snapshot_id=N` (multiple replays on same date) while the snapshot's URI references only the LATEST writer's call_id — this is the Phase 9 source-ladder UPSERT contract operating correctly; S7 verifies the URI references an existing call_id but does NOT require unique reciprocal ownership.** |

### §K.3 Sub-bundle C verification gate (6 surfaces)

| Surface | Gate criteria |
|---|---|
| S1 (inline pytest+ruff) | green; ruff 18; shape A persistence tests at `test_ohlcv_archive_shape_a.py` green |
| S2 (backward-compat rename) | Operator runs pipeline once; verifies existing `{TICKER}.parquet` files renamed to `{TICKER}.yfinance.parquet`; no data loss |
| S3 (ladder integration `_step_evaluate`) | Pipeline run under production env populates `PriceCache` entries with `provider='schwab_api'` for tickers where Schwab succeeded; `provider='yfinance'` for fallback cases; observable via cache log line |
| S4 (`fetch --verify-marketdata` CLI) | Operator runs `swing schwab fetch --verify-marketdata --symbols AAPL,MSFT`; receives 200 + non-empty quotes + audit rows written for both `marketdata.quotes` + per-symbol `marketdata.pricehistory`; NO cache writes (verification mode) |
| S5 (empty-response transient handling) | Plant cassette returning empty `pricehistory`; assert audit row `status='error'` + `error_message="empty bars (transient)"`; assert parquet UNCHANGED; assert ladder returns yfinance entry |
| S6 (sandbox cache short-circuit) | Operator flips env to sandbox; verifies `_step_evaluate` cache fills are all `provider='yfinance'` (Schwab path skipped); no `marketdata.*` rows in `schwab_api_calls` |

### §K.4 Sub-bundle D verification gate (4 surfaces)

| Surface | Gate criteria |
|---|---|
| S1 (inline pytest+ruff) | green; E2E test `tests/integration/test_schwab_full_happy_path.py` green |
| S2 (`swing schwab status` full surface) | After A+B+C ship, operator runs `swing schwab status`; output matches spec §3.5 sketch (env active line; client_id masked; account_hash masked; access_token valid-for; refresh_token valid; last-call summary; per-surface counts; reconciliation summary) |
| S3 (briefing degraded banner) | Plant audit row with `status='error'` for most-recent `marketdata.quotes` call; render briefing.md; verify "Schwab integration: degraded" banner present |
| S4 (E2E happy-path integration test) | `pytest tests/integration/test_schwab_full_happy_path.py -v` exercises auth → snapshot → orders → market-data cache → briefing render in one transactional test (mirror Phase 9 Sub-bundle E precedent at `tests/integration/test_phase9_full_happy_path.py`) |

### §K.5 Cross-bundle pins

Per Phase 10 Sub-bundle A T-A.7 precedent (cross-bundle pin with `@pytest.mark.skip` un-skipped at later bundle):

- **T-A.10 sentinel-leak audit cross-bundle pin:** A's sentinel-leak audit test asserts ZERO sentinel matches in `schwab_api_calls.error_message` + ALL log records. The test is marked `@pytest.mark.skip(reason="Cross-bundle pin: full coverage requires Trader API calls from Bundle B + Market Data calls from Bundle C")` for the Bundle-B + Bundle-C surfaces. Bundle B T-B.8 un-skips Trader-API portions; Bundle C T-C.7 un-skips Market-Data-API portions; Bundle D T-D.5 verifies full coverage.

### §K.6 Task 0.b operator-paired verification (per sub-bundle dispatch)

Each sub-bundle's executing-plans dispatch begins with Task 0.b operator-paired live verification per spec §10 + §G runbook. Sub-bundle dispatch HALTS at Task 0.b until:
- Operator confirms Schwab Developer Portal app status (Q1; A T-A.0.b only).
- Operator pairs through cassette recording for the bundle's `[VERIFY]`-tagged endpoints.
- Operator records observations for Q8/Q12/Q13/Q14/Q15/Q17 in the bundle's recon doc (NEW pattern per Phase 9 Sub-bundle D T-D.0 recon-doc-supersession precedent).
- Operator confirms ALL 4 §A.9 inheritance disciplines are satisfied by bundle's tests + acceptance criteria.

---

## §Tasks per sub-bundle

Per writing-plans format: T-A.1, T-A.2, ... T-D.N. Each task has: scope; files touched; tests added (count estimate); discriminating-test pattern; acceptance criteria; commit message stem.

### §Tasks-A: Sub-bundle A (foundational: schwabdev wrap + auth + migration 0018 + audit infrastructure)

**Dispatch scope summary:** Foundational; lands `schwabdev` runtime dep, OAuth paste-back flow, per-env tokens DB resolution, migration 0018 (`schwab_api_calls` table + 2 ALTERs + schema_version 17→18), audit-row INSERT/UPDATE service, `cfg.integrations.schwab` cascade, `swing schwab setup/refresh/logout/status` (skeleton). NO Trader API consumption; NO Market Data consumption; NO pipeline integration. Sentinel-leak audit at T-A.10 is BINDING acceptance criterion.

**Tasks:**

#### T-A.0 .gitignore patterns

- **Scope:** Add `.gitignore` patterns for Schwab tokens DBs + audit backup files.
- **Files touched:** `.gitignore` (1 line group append).
- **Tests added:** +2 (T-A.0 verifies `git check-ignore -v` matches for 5 sample paths per §F.2).
- **Discriminating test pattern:** `subprocess.run(["git", "check-ignore", "-v", "swing-data/schwab-tokens.production.db"])` returns exit 0 + non-empty stdout.
- **Acceptance criteria:** ALL 5 sample paths from §F.2 produce check-ignore matches.
- **Commit message stem:** `chore(schwab): add .gitignore patterns for tokens DBs + audit backups`.

#### T-A.0.b Operator-paired live verification (Task 0.b)

- **Scope:** Per §G.1 + §G.5. Operator-paired live OAuth flow + Tokens DB schema verification + Q1/Q13/Q14/Q15 observations.
- **Files touched:** NONE (verification only).
- **Tests added:** 0 (verification produces fixture data + cassettes consumed by subsequent tasks).
- **Acceptance criteria:** Operator confirms schwabdev API signatures match §E.1 OR records drift in recon doc `docs/phase11-bundle-A-task-A0b-recon.md`. Verification of: (a) `schwabdev.auth.manual_flow` signature; (b) Tokens DB schema; (c) `Client.account_linked()` response shape; (d) scope-string default; (e) refresh-token rotation behavior.
- **Commit message stem:** `docs(schwab-api): T-A.0.b recon doc with operator-paired live verification observations`.

#### T-A.1 Dependency pinning + schwabdev version verification

- **Scope:** Add `schwabdev>=2.4.0,<3.0.0` to `pyproject.toml` `[project.dependencies]`. Verify installed version matches synthesized §E signatures.
- **Files touched:** `pyproject.toml`.
- **Tests added:** +1 (T-A.1: `import schwabdev; assert schwabdev.__version__ matches pin range`).
- **Acceptance criteria:** `pip install -e .` succeeds; `pytest tests/integrations/test_schwab_dependency_pin.py` green.
- **Commit message stem:** `chore(schwab): pin schwabdev runtime dependency`.

#### T-A.2 cfg cascade — `cfg.integrations.schwab` sub-dataclass

- **Scope:** Add `SchwabConfig` sub-dataclass under `Config.integrations` per §A.6. Fields: `environment`, `account_hash`, `lookback_days`, `timeout_seconds`, `marketdata_ladder_enabled`. `__post_init__` validators. FIELD_REGISTRY entry for `account_hash` masked.
- **Files touched:** `swing/config.py`; `swing.config.toml` (`[integrations.schwab]` section); `swing/config_show.py` (FIELD_REGISTRY).
- **Tests added:** +10 (cascade default; user-config override; `__post_init__` validators for each field; FIELD_REGISTRY masking on `account_hash`).
- **Discriminating test pattern:** plant `cfg.integrations.schwab.environment = 'invalid'`; assert ValueError raised.
- **Acceptance criteria:** All 10 tests green; `swing config show` masks `account_hash` (e.g., `1A2***9F`); `swing config show` does NOT show any schwabdev token fields (those are in tokens DB, not cfg).
- **Commit message stem:** `feat(schwab): cfg.integrations.schwab cascade with sub-dataclass + FIELD_REGISTRY`.

#### T-A.3 Sub-package skeleton + exception hierarchy + `SchwabClient` wrapper

- **Scope:** Create `swing/integrations/schwab/{__init__.py, client.py, auth.py}`. Define exception classes (`SchwabConfigMissingError`, `SchwabApiError`, `SchwabRateLimitError`, `SchwabAuthError`, `SchwabRefreshTokenExpiredError`, `SchwabSchemaParityError`, `SchwabConcurrentRefreshError`, `SchwabPipelineActiveError`). Implement `_suppress_transport_debug_logs()` context manager (mirror Finviz; extend logger list to include schwabdev's). Implement `SchwabClient.__init__` per §H.3.
- **Files touched:** `swing/integrations/schwab/__init__.py`, `client.py`, `auth.py` (skeleton only — full setup/refresh/logout flow in T-A.4/T-A.5).
- **Tests added:** +12 (exception `__str__` contracts for redaction; `SchwabClient.__init__` resolves per-env tokens DB path with USERPROFILE+HOME monkeypatch; `_suppress_transport_debug_logs` mutes all 5 logger names).
- **Discriminating test pattern:** instantiate each exception with a sample URL containing `account_hash` segment; assert `str(exc)` does NOT contain the hash.
- **Acceptance criteria:** All 12 tests green.
- **Commit message stem:** `feat(schwab): sub-package skeleton + exception hierarchy + transport-debug-log suppression`.

#### T-A.4 OAuth paste-back setup flow

- **Scope:** Implement `auth.py:setup_paste_flow(...)` per §H.1. CLI command `swing schwab setup`. Algorithm: prompt for client_id/client_secret; invoke `schwabdev.auth.manual_flow(...)` paste-back; persist Tokens DB; invoke `trader.get_accounts_linked()` (placeholder until T-B.1; T-A.4 stubs the return); pick primary; cfg-cascade write; emit success + advisory.
- **Files touched:** `swing/integrations/schwab/auth.py`; `swing/cli/schwab.py` (NEW; `setup` subcommand); `swing/cli/__init__.py` (wire group).
- **Tests added:** +15 (paste flow with stubbed schwabdev; single-hash auto-pick; multi-hash prompt; missing client_id error; cfg-cascade write; advisory message printed; USERPROFILE+HOME monkeypatch; `--force` override of pipeline-active check; audit-row INSERT/UPDATE).
- **Discriminating test pattern:** stub `schwabdev.auth.manual_flow` to raise `AuthError`; assert CLI exits non-zero + audit row `status='auth_failed'` + error message redacted.
- **Acceptance criteria:** All 15 tests green; manual operator-paired flow at T-A.0.b runs end-to-end against production tier.
- **Commit message stem:** `feat(schwab): swing schwab setup with OAuth paste-back flow + audit lifecycle`.

#### T-A.5 Force-refresh + logout + revocation CLI

- **Scope:** Implement `auth.py:force_refresh(...)` per §H.2 + `auth.py:revoke_and_delete(...)` per §F.3. CLI commands `swing schwab refresh` + `swing schwab logout`.
- **Files touched:** `swing/integrations/schwab/auth.py`; `swing/cli/schwab.py`.
- **Tests added:** +10 (refresh success; refresh expired refresh_token; refresh-with-rotation cassette; logout deletes tokens DB; logout with revocation network failure tolerated; logout `--force` override under pipeline-active; setup `--force` override; refresh is concurrent-safe — no `--force` flag; refresh under pipeline-active returns OK; tokens DB schema verification).
- **Discriminating test pattern:** plant `pipeline_runs` row with `state='running'`; invoke `swing schwab logout` without `--force`; assert `SchwabPipelineActiveError` raised. THEN invoke `swing schwab refresh` (Codex R1 Minor #3: refresh has NO `--force` flag — concurrent-safe); assert NO error.
- **Acceptance criteria:** All 10 tests green.
- **Commit message stem:** `feat(schwab): swing schwab refresh + logout subcommands with audit lifecycle`.

#### T-A.6 `swing schwab status` skeleton

- **Scope:** Implement `swing/cli/schwab.py:status_cmd`. Reads cfg-active env + tokens DB metadata + `schwab_api_calls` recent rows; emits per spec §3.5 mock output (skeleton — Bundle D T-D.1 polishes full surface).
- **Files touched:** `swing/cli/schwab.py`.
- **Tests added:** +8 (env active line; tokens DB present/absent; masked client_id; masked account_hash; access_token validity time-remaining; refresh_token validity; no token bytes in output).
- **Discriminating test pattern:** plant a known-sentinel token in tokens DB; run `swing schwab status`; grep stdout for sentinel; assert ZERO matches.
- **Acceptance criteria:** All 8 tests green.
- **Commit message stem:** `feat(schwab): swing schwab status CLI skeleton with masking discipline`.

#### T-A.7 Migration 0018 + EXPECTED_SCHEMA_VERSION bump (CORRECTED per Codex R1 Critical #1 + R2 Major #2)

- **Scope:** Implement `swing/data/migrations/0018_schwab_integration.sql` per §C.1 with explicit `BEGIN;` and `COMMIT;` framing the script. Bump `EXPECTED_SCHEMA_VERSION = 17 → 18` at `swing/data/db.py:19`. NO backup gate fires per §C.5 (gate is version-specific; 17→18 not wired; operator-manual backup recommended per §I.1).
- **Files touched:** `swing/data/migrations/0018_schwab_integration.sql` (NEW); `swing/data/db.py` (1 line change).
- **Tests added:** +10 (migration applies cleanly; rollback-on-malformed-migration; FK constraints active; CHECK enums reject invalid values; INDEX existence; ALTER columns NULL-permissible; schema_version row updated; BEGIN/COMMIT markers present in SQL; canonical-minus-BEGIN-fixture FAILS rollback per Codex R1 Critical #1 counter-example; no backup file written for 17→18 per Codex R1 Major #1 counter-example).
- **Discriminating test pattern (canonical):** plant a malformed 0018 fixture with deliberate fail-mid-sequence; invoke `_apply_migration`; assert post-failure `schema_version` still 17 + `schwab_api_calls` table does NOT exist + `conn.in_transaction == False`.
- **Discriminating test pattern (counter-example for BEGIN discipline):** plant 0018 WITHOUT leading `BEGIN;` (autocommit mode); plant deliberate fail-mid-sequence; assert post-failure `schwab_api_calls` table DOES exist (CHECK constraint violation rolled back, but CREATE TABLE persisted in autocommit). Locks the BEGIN/COMMIT discipline contract.
- **Discriminating test pattern (no-backup-gate-fires):** plant `schema_version=17`; invoke `_apply_migration(<0018>)`; assert NO `MigrationBackupRequiredException` raised AND NO `swing-pre-phase11-schwab-migration-*.db` file written under `swing-data/`. Locks the gate-doesn't-fire disposition.
- **Acceptance criteria:** All 10 tests green; `swing db-migrate` runs cleanly; no FK CASCADE risk per §C.3 verified.
- **Commit message stem:** `feat(schwab): migration 0018 schwab_api_calls + ALTER columns + schema_version 17->18 with explicit BEGIN/COMMIT`.

#### T-A.8 Repo layer + dataclass

- **Scope:** Implement `swing/data/repos/schwab_api_calls.py` per §B.1 + `SchwabApiCall` dataclass in `swing/data/models.py` per §H.7. Repo functions are caller-controlled tx (mirror Phase 9 repo discipline).
- **Files touched:** `swing/data/repos/schwab_api_calls.py` (NEW); `swing/data/models.py` (extend).
- **Tests added:** +18 (`SchwabApiCall.__post_init__` validators (8 fields × validator); repo function `insert_in_flight` returns call_id; `update_call_outcome` UPDATEs in place (no PK reissue — discriminating test for INSERT OR REPLACE prohibition); linked_id UPDATEs; list_recent_calls ordering; count_calls_by_status filter; FK behavior).
- **Discriminating test pattern:** call `insert_in_flight` + `update_call_outcome`; assert PK of resulting row matches the returned call_id from INSERT (would fail if `INSERT OR REPLACE` accidentally introduced).
- **Acceptance criteria:** All 18 tests green.
- **Commit message stem:** `feat(schwab): schwab_api_calls repo + SchwabApiCall dataclass with validators`.

#### T-A.9 Audit service-layer wrappers

- **Scope:** Implement `swing/integrations/schwab/audit_service.py` per §B.1. Service functions: `record_call_start`, `record_call_finish`, `link_snapshot_and_stamp_account_hash` (NEW combined — per R2 Major #3 fix; one tx2 covers both linked_snapshot_id UPDATE on audit row + schwab_account_hash UPDATE on snapshot row), `link_reconciliation_run`. Each OWNS BEGIN IMMEDIATE; REJECTS caller-held tx; raises `CallerHeldTransactionError`.
- **Files touched:** `swing/integrations/schwab/audit_service.py` (NEW).
- **Tests added:** +16 (each service owns its tx; rejects caller-held tx per Phase 9 lesson; in-flight INSERT round-trips to update_call_outcome UPDATE without PK reissue; concurrent INSERT/UPDATE serializes; rollback-on-failure leaves consistent state; `link_snapshot_and_stamp_account_hash` atomically updates BOTH tables in one tx; crash-window discriminating test per R1 Major #4 simulation).
- **Discriminating test pattern:** open conn.execute("BEGIN"); invoke `record_call_start`; assert `CallerHeldTransactionError` raised; commit conn; retry; succeeds. Crash-window simulation: commit tx1 (snapshot INSERT); simulate process kill before tx2; resume; assert audit `status='success'` + `linked_snapshot_id=NULL` AND snapshot row `schwab_account_hash=NULL` SIMULTANEOUSLY (never one without the other per R2 Major #3 combined-tx).
- **Acceptance criteria:** All 16 tests green.
- **Commit message stem:** `feat(schwab): audit service-layer wrappers with caller-held-tx rejection + combined link/stamp tx`.

#### T-A.10 Token redaction audit (sentinel-leak) + three-layer redactor + cassette filter config (UPDATED per Codex R3 Major #1)

- **Scope:** Implement the three-layer redactor (per §H.8 Layer 0/1/2) + cassette filter + schwabdev LogRecord factory wrapper. Layer 0 = `_make_redactor(known_secrets)` closure with exact-replace from runtime context (5 long-lived known-secret slots per R4 Major #1: client_id, client_secret, access_token, refresh_token, account_hash; authorization_code separately covered by non-leak test); Layer 1 = heuristic regex (hex 32+, base64 24+); Layer 2 = `_schwab_record_factory` installed via `logging.setLogRecordFactory()` (R7 Critical #1 redesign — switched from logger-filter to factory wrapper since filters on ancestor loggers do not fire during propagation per Python `Logger.callHandlers()` semantics) backed by process-global registry (per R3 Major #2 — union of all secrets seen this process, NEVER narrowed) with re-install via `ensure_schwab_log_redaction_factory_installed()` (R8 Major #2 — defends against third-party libraries replacing the factory). Implement `tests/integrations/test_schwab_token_redaction_audit.py` mirroring Finviz precedent + extending to schwabdev coverage.
- **Files touched:** `tests/integrations/test_schwab_token_redaction_audit.py` (NEW); `tests/conftest.py` (extend `vcr_config` fixture per §G.3); `swing/integrations/schwab/client.py` (defines `_make_redactor_from_global`, `register_schwab_secrets`, `_schwab_record_factory`, `_install_schwab_log_redaction_factory_once`, `_GLOBAL_KNOWN_SECRETS`, `_FACTORY_INSTALLED`, `_ORIGINAL_RECORD_FACTORY` per §H.8 R7 Critical #1 redesign — switched to `logging.setLogRecordFactory` because logger filters do not fire during propagation); `swing/integrations/schwab/auth.py` (registers secrets at setup + refresh time).
- **Tests added:** +24 (per §H.8 three-layer contract; R4 + R7 + R8 + R9 additions):
  - L0 exact-replace: NON-token-shaped sentinel (e.g., `SENTINEL_DO_NOT_LEAK` — 20 chars, alphanumeric) injected as `access_token`; trigger schwabdev auth-failure log path; assert sentinel does NOT appear in any captured log record from schwabdev.* loggers.
  - L0 multi-slot coverage: inject distinct non-token-shaped sentinels at ALL 5 long-lived known-secret slots (client_id, client_secret, access_token, refresh_token, account_hash); grep ALL log records + audit `error_message` columns; ZERO matches for each sentinel. (Authorization code is excluded per R4 Major #1 — separately covered below.)
  - **Authorization-code non-leak test (R4 Major #1 + R5 Minor #3 stdout/stderr extension):** invoke `swing schwab setup` against a fixture that returns a known authorization_code value (e.g., `AUTH_CODE_DO_NOT_LEAK_4XYZ`); capture ALL log records emitted by schwabdev.* loggers + project loggers during the setup flow PLUS captured stdout + stderr (via `capsys`/`capfd`) PLUS Click runner output (via `CliRunner(mix_stderr=False).invoke(...)` if T-A.4 uses click testing); grep all four surfaces for `code=AUTH_CODE_DO_NOT_LEAK_4XYZ` AND for `AUTH_CODE_DO_NOT_LEAK_4XYZ` standalone substring; assert ZERO matches. R5 Minor #3 — covers the case where schwabdev's paste-back interaction prints to stdout/stderr instead of going through a logger. If schwabdev's behavior changes in a future version + this test fails, the V2 fix is to wrap `manual_flow` with a stdin/stdout intercept that captures the code BEFORE schwabdev sees it + adds to the known-secrets registry.
  - L0 refresh-secret union: simulate refresh producing a new access_token while old token still present in earlier log entries; assert BOTH old + new tokens are redacted from a subsequent log capture (R3 Major #2 union-discipline test).
  - L0 cross-client union: simulate sandbox + production SchwabClient construction in same process (different secret sets); assert ALL secrets from both clients are redacted from log capture regardless of which client emitted (R3 Major #2 cross-client discipline test).
  - **L0 + L2 test-contamination guard (R4 Major #3 + R8 Major #1 update for factory design):** pytest fixture `reset_schwab_redaction_state` (autouse-per-test-or-explicit; renamed from R4's `reset_schwab_secrets_registry`) does THREE things before each redaction test: (1) clears `_GLOBAL_KNOWN_SECRETS`; (2) restores the LogRecord factory via `logging.setLogRecordFactory(_ORIGINAL_RECORD_FACTORY)` if installed; (3) resets `_FACTORY_INSTALLED = False`. Tests use UNIQUE-PER-TEST sentinels (e.g., `SENTINEL_{test_name}_{uuid4_hex[:8]}`) so prior tests' registrations cannot mask current-test bugs. Discriminating test asserts: (a) WITHOUT `register_schwab_secrets()` AND without `_install_schwab_log_redaction_factory_once()`, the redactor MISSES the sentinel (proves the test would fail if the SUT forgot to register OR forgot to install factory); (b) with explicit setup-then-emit, redaction works. This forces both registration AND factory-install into the test path.
  - L1 heuristic regex: 32-hex-char token-like string + 24-base64-char token-like string in log emit; assert both redacted.
  - L2 `_schwab_record_factory` installed via `logging.setLogRecordFactory` ONCE per process per §H.8 R7 Critical #1 redesign. Assert `logging.getLogRecordFactory() is _schwab_record_factory` after install; assert factory mutates records whose name starts with 'schwabdev' and passes through non-schwabdev records unchanged.
  - L2 lazily-created sub-logger discriminating test (R5 Major #2 + R6 Major #1 + R7 Critical #1): AFTER `_install_schwab_log_redaction_factory_once()` has fired, construct a fake sub-logger `schwabdev.unlisted_future_module` (NEVER previously instantiated) AND emit its FIRST LogRecord containing a registered sentinel; capture via `caplog` + custom test handler attached to the sub-logger directly; assert sentinel does NOT appear in EITHER capture surface. Validates factory-level install catches lazily-created sub-loggers BEFORE any handler sees the record (R7 Critical #1 corrects the prior R6 root-logger-filter approach which would fail this test because filters on ancestor loggers do not fire during propagation).
  - L2 caplog-coverage test (R7 Critical #1 additional case): emit from `schwabdev.tokens` (a likely-used sub-logger) with a registered sentinel; assert `caplog.text` does NOT contain the sentinel. Verifies pytest's LogCaptureHandler also sees the redacted record (because the factory mutated the record at creation time, before caplog's handler captured it).
  - L2 factory-chaining defense test (R8 Major #2): install Schwab factory + register a sentinel; install a NO-OP "third-party" factory via `logging.setLogRecordFactory(lambda *a,**kw: orig(*a,**kw))`; call `ensure_schwab_log_redaction_factory_installed()`; emit `schwabdev.tokens` record with sentinel; assert sentinel does NOT appear in the captured record. Verifies the re-wrap path activates correctly.
  - L2 factory-replacement detection test (R8 Major #2): install Schwab; register sentinel; install third-party factory; emit `schwabdev.tokens` WITHOUT calling `ensure_schwab_log_redaction_factory_installed()` first; assert the sentinel LEAKS (counter-example: proves the ensure-step is required). Then call `ensure_*` + emit again; assert sentinel redacted.
  - L2 recursion-guard discriminating test (R9 Major #1 + R10 Major #1): construct an adversarial scenario where third-party captures `orig = logging.getLogRecordFactory()` after Schwab install (so their `orig` IS `_schwab_record_factory`) + then sets `logging.setLogRecordFactory(third_party_wrapper)` where the wrapper calls its captured `orig(...)`; call `ensure_schwab_log_redaction_factory_installed()`; emit `schwabdev.tokens` record with sentinel; assert (a) NO `RecursionError` raised; (b) sentinel redacted in the outermost record handed to handlers; (c) emit completes in bounded time (≤ 1ms for a single record); (d) the recursion fallback path returns a `logging.LogRecord` instance (NOT routed through `_ORIGINAL_RECORD_FACTORY` per R10 Major #1 fix — verified via mock + call-count assertion that `_ORIGINAL_RECORD_FACTORY` is called EXACTLY ONCE (outer pass) for one emit, not unbounded times).
  - Cassette filter strips authorization header.
  - Cassette filter strips POST body parameters (`code`, `refresh_token`, `client_id`, `client_secret`).
  - Cassette response-body redactor masks `access_token`/`refresh_token`/`accountNumber`/`accountHash` substrings.
  - Audit-row `error_message` column: inject sentinel into schwabdev exception body; assert audit row's error_message does NOT contain sentinel (Layer 0 + Layer 1 both apply at audit-write time).
  - `swing schwab status` output: inject sentinel into masked-value-render path; assert stdout does NOT contain sentinel.
  - Cross-bundle pins: B/C surfaces (Trader API + Market Data API) marked `@pytest.mark.skip(reason='Cross-bundle pin: un-skip at T-B.8 + T-C.7')`.
- **Discriminating test pattern:** for each redaction surface, plant non-token-shaped sentinel at known-secret slot + invoke surface + assert `sentinel not in <captured surface output>`.
- **Acceptance criteria:** All 24 tests green; cross-bundle pins added for B+C surfaces.
- **Commit message stem:** `feat(schwab): three-layer sentinel-token-leak audit + process-global redactor registry + schwabdev logger coverage`.

**Sub-bundle A test count estimate: +126 fast tests** (R1 baseline +110 → +112 R1; +114 R2; +122 R4; +125 R7+R8; +126 R9 after T-A.10 +24, adding recursion-guard discriminating test).

### §Tasks-B: Sub-bundle B (Trader API + snapshot + orders + reconciliation + sandbox-gating)

**Dispatch scope summary:** Wires snapshot + orders + reconciliation domain writes via existing Phase 9 source-ladder helpers; introduces `_step_schwab_snapshot` + `_step_schwab_orders` pipeline steps with explicit ordering per §H.4.3; new service `run_schwab_reconciliation` mirrors `run_tos_reconciliation`; production-only domain writes gate per §A.3 + §H.4.1; `SchwabPipelineActiveError` cross-surface exclusion per §H.10.

**Tasks:**

#### T-B.0.b Operator-paired live verification (Task 0.b)

- **Scope:** Per §G.2 + §E.2 + §K.6. Cassette recording for `accounts.details`, `accounts.orders.list`, `accounts.transactions.list`; Q8 base-URL verification.
- **Acceptance criteria:** Operator-paired recon doc `docs/phase11-bundle-B-task-B0b-recon.md` records observations.
- **Commit message stem:** `docs(schwab-api): T-B.0.b recon doc with Trader API operator-paired observations`.

#### T-B.1 Trader API endpoint methods + mappers

- **Scope:** Implement `swing/integrations/schwab/trader.py` + `mappers.py` per §E.2. Functions: `get_accounts_linked`, `get_account_details`, `get_account_orders`, `get_account_transactions`. Each wraps schwabdev call in audit-row INSERT-then-UPDATE.
- **Files touched:** `swing/integrations/schwab/trader.py` (NEW); `swing/integrations/schwab/mappers.py` (extend).
- **Tests added:** +16 (cassette-driven per endpoint; mapper per response shape; `__post_init__` validators for response dataclasses; 401 auto-refresh-once-then-fail; 429 retry-once-then-fail; partial-response on orders/transactions).
- **Acceptance criteria:** All 16 tests green; cassettes redacted per T-A.10.
- **Commit message stem:** `feat(schwab): Trader API endpoint methods + response mappers`.

#### T-B.2 Sandbox-gating discriminating tests (cross-cutting)

- **Scope:** Discriminating tests asserting production-only domain writes gate per §A.3.
- **Files touched:** `tests/integrations/test_schwab_sandbox_gating.py` (NEW).
- **Tests added:** +6 (snapshot under sandbox writes audit + skips domain; orders under sandbox writes audit + skips domain; CLI fetch under sandbox skips domain; cfg cascade flip activates production-mode domain writes; sandbox + production cassettes share signature_hash pattern; cfg override `--environment` flag flips behavior).
- **Discriminating test pattern:** per §A.3 — plant env='sandbox' + run pipeline; assert audit row exists with `status='success'` + ZERO new rows in `account_equity_snapshots` for that snapshot_date.
- **Acceptance criteria:** All 6 tests green.
- **Commit message stem:** `feat(schwab): sandbox-gating discriminating tests for production-only domain writes`.

#### T-B.3 `_step_schwab_snapshot` pipeline step

- **Scope:** Implement `swing/integrations/schwab/pipeline_steps.py:_step_schwab_snapshot` per §H.4.1. Wires into `swing/pipeline/runner.py` after `_step_recommendations`. Adds `schwab_snapshot_status` lease field.
- **Files touched:** `swing/integrations/schwab/pipeline_steps.py` (NEW); `swing/pipeline/runner.py` (extend).
- **Tests added:** +13 (happy-path snapshot write under production; sandbox short-circuit per T-B.2; 401 auto-refresh + retry; 429 records rate_limited; missing account_hash logs warning + lease status; production-path session-anchor round-trip with Phase 10 capital-friction LIVE badge via `get_latest_snapshot_on_or_before`; same-day-replay-provenance-asymmetry test per R4 Minor #2 + §H.4.1.bis).
- **Discriminating round-trip test (per §A.9 #9):** invoke `_step_schwab_snapshot` against a cassette returning known NLV; verify `account_equity_snapshots` row inserted with expected snapshot_date; immediately read via Phase 10 capital-friction VM; assert LIVE-badge appears with the value.
- **Same-day-replay discriminating test (per R4 Minor #2):** invoke `_step_schwab_snapshot` twice in the same test with TWO distinct cassettes (call_id=N, then call_id=N+1) both for the same `snapshot_date`; assert: (a) ONE `account_equity_snapshots` row exists (snapshot_id preserved per UPSERT); (b) TWO `schwab_api_calls` rows exist, BOTH with `linked_snapshot_id = snapshot_id`; (c) the snapshot's `source_artifact_path = 'schwab_api:call/(N+1)'` (LATEST writer wins per Phase 9 UPSERT contract; R3 Major #4 acceptance). Validates the documented same-day provenance asymmetry as expected behavior.
- **Acceptance criteria:** All 13 tests green. (R5 Minor #2 count fix.)
- **Commit message stem:** `feat(schwab): _step_schwab_snapshot pipeline step with production-only gate`.

#### T-B.4 `_step_schwab_orders` + `run_schwab_reconciliation` service

- **Scope:** Implement `_step_schwab_orders` per §H.4.2 + `swing/trades/schwab_reconciliation.py:run_schwab_reconciliation` per §H.5. Reuses Phase 9 Sub-bundle B emit machinery + discrepancy types.
- **Files touched:** `swing/integrations/schwab/pipeline_steps.py` (extend); `swing/trades/schwab_reconciliation.py` (NEW); `swing/data/repos/reconciliation.py` (multi-touchpoint extension per R3 Major #3: (a) `_RUN_SELECT_COLUMNS` adds `schwab_api_call_id`; (b) `_row_to_run` populates new dataclass field; (c) `insert_run` accepts `schwab_api_call_id: int | None = None` kwarg + includes in INSERT column list; (d) `get_run` + `list_recent_runs` round-trip via updated mapper); `swing/data/models.py` (extend `ReconciliationRun` dataclass with `schwab_api_call_id: int | None = None` field at the END of field ordering — preserves existing positional dataclass instantiations).
- **Tests added:** +20 (per-discrepancy emit tests: stop_mismatch, position_qty_mismatch, close_price_mismatch, entry_price_mismatch, unmatched_open_fill, unmatched_close_fill, cash_movement_mismatch, equity_delta; caller-held-tx rejection; INSERT-then-UPDATE state='failed' on mid-emit failure; MATERIAL_BY_TYPE inheritance from Phase 9; ON_DELETE_SET_NULL on schwab_api_call_id; 3-call audit-row linkage to 1 reconciliation_run_id).
- **Discriminating test pattern:** plant deliberate failure mid-discrepancy-emit; assert reconciliation_run row exists with state='failed' (per spec §3.3.3 PRESERVE pattern); assert no orphan discrepancies attributed to the run; assert FK back-pointers intact.
- **Acceptance criteria:** All 20 tests green.
- **Commit message stem:** `feat(schwab): _step_schwab_orders + run_schwab_reconciliation service`.

#### T-B.5 CLI `swing schwab fetch` subcommands

- **Scope:** Implement `swing schwab fetch [--snapshot|--orders|--all]` per §3.5 + §H.10. Each invokes the corresponding pipeline-step logic via lock-free path (mirror Finviz `_perform_finviz_fetch_no_lease`); enforces `SchwabPipelineActiveError`.
- **Files touched:** `swing/cli/schwab.py` (extend).
- **Tests added:** +10 (per subcommand: pipeline-active hard exclusion; happy-path produces audit row; sandbox-mode short-circuits domain write; --all invokes both snapshot + orders; exit codes).
- **Acceptance criteria:** All 10 tests green.
- **Commit message stem:** `feat(schwab): swing schwab fetch CLI subcommands with pipeline-active exclusion`.

#### T-B.6 `SchwabPipelineActiveError` cross-surface tests (CORRECTED per Codex R1 Major #3)

- **Scope:** Discriminating tests per §H.10 covering the FIVE protected CLI subcommands + THREE safe subcommands.
- **Files touched:** `tests/integrations/test_schwab_pipeline_active_exclusion.py` (NEW).
- **Tests added:** +10 (5 protected: setup-without-force RAISES; logout-without-force RAISES; fetch --snapshot RAISES; fetch --orders RAISES; fetch --all RAISES; 2 force-override: setup --force OK; logout --force OK; 3 safe: status OK; refresh OK; fetch --verify-marketdata OK). (R2 Minor #2: count corrected from +9 to +10; the prior "1 refresh negative" item was redundant with the "3 safe" group.)
- **Acceptance criteria:** All 10 tests green. NO test attempts to verify `refresh` as protected (per §H.10 corrected disposition).
- **Commit message stem:** `feat(schwab): SchwabPipelineActiveError discriminating tests across 5 protected + 3 safe surfaces`.

#### T-B.7 Production-only domain writes integration test

- **Scope:** Full-pipeline integration test mirroring Phase 9 Sub-bundle E pattern. Cassette-driven; runs full pipeline under `environment='production'` AND `environment='sandbox'`; asserts domain writes occur in production AND are skipped in sandbox.
- **Files touched:** `tests/integration/test_schwab_pipeline_production_only_gate.py` (NEW).
- **Tests added:** +4 (production produces domain rows; sandbox produces audit rows + ZERO domain rows; same cassette under both env yields identical schwab_api_calls signature hashes; lease status transitions correctly).
- **Acceptance criteria:** All 4 tests green; serves as Bundle D T-D.3 integration test foundation.
- **Commit message stem:** `test(schwab): production-only domain writes integration test under both envs`.

#### T-B.8 Sentinel-leak audit Bundle B coverage (un-skip)

- **Scope:** Un-skip cross-bundle pin at T-A.10 for Trader-API portions. Extend audit to cover Trader API audit rows + reconciliation_runs rows.
- **Files touched:** `tests/integrations/test_schwab_token_redaction_audit.py` (un-skip).
- **Tests added:** +4 (Trader API call sentinel coverage).
- **Acceptance criteria:** Pre-existing skipped tests now green.
- **Commit message stem:** `test(schwab): un-skip sentinel-leak audit Bundle B coverage`.

**Sub-bundle B test count estimate: +80 fast tests** (R1 baseline +78 → +79 after T-B.6 +10 vs prior +9 per R2 Minor #2; → +80 after T-B.3 +13 vs prior +12 per R4 Minor #2 same-day-replay test).

### §Tasks-C: Sub-bundle C (Market Data API + cache layer ladder Shape A)

**Dispatch scope summary:** Implements V1 INCLUDE branch per spec §3.8. Shape A persistence (parquet-per-(ticker, provider)). Wraps existing cache fetcher paths in a "Schwab → yfinance fallback" ladder. yfinance gotcha-hardened code path preserved as fallback. Sandbox short-circuit. `--verify-marketdata` CLI subcommand.

**Tasks:**

#### T-C.0.b Operator-paired live verification (Task 0.b)

- **Scope:** Cassette recording for `marketdata.quotes` + `marketdata.pricehistory`; Q12 + Q17 verification.
- **Acceptance criteria:** Recon doc with observations.
- **Commit message stem:** `docs(schwab-api): T-C.0.b recon doc with Market Data API observations`.

#### T-C.1 Market Data API endpoint methods + mappers

- **Scope:** Implement `swing/integrations/schwab/marketdata.py` per §E.3.
- **Files touched:** `swing/integrations/schwab/marketdata.py` (NEW); `mappers.py` (extend).
- **Tests added:** +12 (cassette-driven per endpoint; mappers; partial-response on quotes; empty-bars on pricehistory; rate-limit handling).
- **Acceptance criteria:** All 12 tests green.
- **Commit message stem:** `feat(schwab): Market Data API endpoint methods + mappers`.

#### T-C.2 OHLCV archive Shape A persistence + backward-compat rename + window-filter + empty-write-guard (UPDATED per Codex R1 Major #6 + Major #7 + Minor #4; R2 Minor #1)

- **Scope:** Modify `swing/data/ohlcv_archive.py` per §H.6.3 (post-R1 strengthening). Filename change `{TICKER}.parquet` → `{TICKER}.{PROVIDER}.parquet`. `_SOURCE_PRECEDENCE_MARKET_DATA` constant. `resolve_ohlcv_window` merge function WITH window-filter step. `_backward_compat_rename` handles 4 cases (old-only / both / new-only / neither) with MERGE-AND-QUARANTINE when both files exist. `write_window` guards against empty-window clobber BEFORE any write.
- **Files touched:** `swing/data/ohlcv_archive.py`.
- **Tests added:** +18 (R1 baseline +14 + R2 +4 new):
  - Write Schwab; write yfinance.
  - Resolve merges per precedence.
  - Resolve handles only-one-provider-present.
  - Resolve handles both-providers-present + same-date conflict (Schwab wins).
  - Resolve handles missing-bars-in-one-provider.
  - `_backward_compat_rename` cases: (a) old-only → renames; (b) BOTH exist → MERGE-AND-QUARANTINE + orphan file present + no data loss (R2 Minor #1 new acceptance); (c) new-only → no-op; (d) neither → no-op.
  - Backward-compat idempotency: invoke twice; second invocation no-op.
  - `write_window` empty-window-guard: invoke with empty df; assert NO file created OR existing UNCHANGED (R1 Major #7).
  - `write_window` empty-window-guard with existing file: invoke with empty df on top of populated parquet; assert file UNCHANGED.
  - Window-filter in `resolve_ohlcv_window`: plant rows at `[2026-01-01, 2026-01-15, 2026-02-01]`; query `start='2026-01-10', end='2026-01-20'`; assert ONLY the 2026-01-15 row returned (R1 Minor #4).
  - rename on same volume per `os.replace` gotcha.
  - per-provider file independence.
- **Discriminating test pattern (per §A.9 #11):** plant empty Schwab response; assert `{TICKER}.schwab_api.parquet` is NOT clobbered; yfinance fallback returns un-clobbered data.
- **Acceptance criteria:** All 18 tests green.
- **Commit message stem:** `feat(schwab): OHLCV archive Shape A parquet-per-(ticker, provider) + backward-compat merge-or-quarantine + window-filter + empty-write guard`.

#### T-C.3 Market-data ladder fetcher

- **Scope:** Implement `swing/integrations/schwab/marketdata_ladder.py` per §H.6.1 + §H.6.2. Functions: `fetch_quote_via_ladder`, `fetch_window_via_ladder`. Sandbox short-circuit. yfinance fallback discipline.
- **Files touched:** `swing/integrations/schwab/marketdata_ladder.py` (NEW).
- **Tests added:** +14 (production-path Schwab success; production-path Schwab 429 → yfinance; production-path Schwab 401 → auto-refresh → success; production-path Schwab empty-bars → yfinance; sandbox short-circuit; ladder enabled/disabled flag; partial-response on quotes per §E.4; per-provider tagging; provenance dict returned correctly; ladder rejects out-of-range tickers).
- **Discriminating test pattern:** plant Schwab cassette returning empty bars; assert ladder returns yfinance result + audit row `status='error'` + parquet UNCHANGED.
- **Acceptance criteria:** All 14 tests green.
- **Commit message stem:** `feat(schwab): market-data ladder fetcher with sandbox short-circuit + yfinance fallback`.

#### T-C.4 `PriceCache` + `OhlcvCache` integration

- **Scope:** Modify `swing/web/price_cache.py` + `swing/data/ohlcv_cache.py` to invoke ladder fetcher. Add `provider` field to `PriceCacheEntry` per §A.8. Sandbox short-circuit guard.
- **Files touched:** `swing/web/price_cache.py`; `swing/data/ohlcv_cache.py`.
- **Tests added:** +10 (PriceCacheEntry.provider field; cache-fill via ladder under production; cache-fill via yfinance under sandbox; provider tagged on entry; existing TTL-state `source` field preserved unchanged; cache miss invokes ladder; cache hit returns existing entry without re-fetching; provider value distinct from source value).
- **Acceptance criteria:** All 10 tests green; existing test fixtures for `source` field unchanged.
- **Commit message stem:** `feat(schwab): PriceCache + OhlcvCache integration with market-data ladder`.

#### T-C.5 `swing schwab fetch --verify-marketdata` CLI subcommand

- **Scope:** Implement `swing schwab fetch --verify-marketdata [--symbols SYM1,SYM2]` per spec §3.6.3. Issues `/quotes` + `/pricehistory` calls under active env; audit rows written; cache writes SKIPPED regardless of env (verification-only).
- **Files touched:** `swing/cli/schwab.py` (extend).
- **Tests added:** +6 (production env produces audit rows + no cache writes; sandbox env produces audit rows + no cache writes; --symbols flag parses comma-separated list; default symbol AAPL; partial-response surfaces in CLI output; 401/429 handled).
- **Acceptance criteria:** All 6 tests green.
- **Commit message stem:** `feat(schwab): swing schwab fetch --verify-marketdata CLI subcommand`.

#### T-C.6 Pipeline integration — `_step_evaluate` + `_step_charts` ladder injection

- **Scope:** Modify existing callsites in `_step_evaluate` + `_step_charts` to invoke `PriceCache.get_latest()` / `OhlcvCache.get_window()` (which now route through the ladder). NO new pipeline step (per spec §3.4.1). NO step ordering change.
- **Files touched:** `swing/pipeline/runner.py` (no new step; verify ladder consumption through existing cache-call boundaries; minor adjustments only).
- **Tests added:** +4 (existing pipeline tests continue to pass; ladder consumption observable through audit rows; sandbox short-circuit verified at pipeline level; cache hit rate after first run is high).
- **Acceptance criteria:** Full pipeline run produces audit rows for market-data calls; existing tests stay green.
- **Commit message stem:** `feat(schwab): wire market-data ladder into _step_evaluate + _step_charts via cache layer`.

#### T-C.7 Sentinel-leak audit Bundle C coverage (un-skip)

- **Scope:** Un-skip cross-bundle pin at T-A.10 for Market-Data portions.
- **Files touched:** `tests/integrations/test_schwab_token_redaction_audit.py` (un-skip).
- **Tests added:** +4 (Market Data API call sentinel coverage; per-symbol breakdown in error_message redacted; quote response body redacted).
- **Acceptance criteria:** Pre-existing skipped tests now green.
- **Commit message stem:** `test(schwab): un-skip sentinel-leak audit Bundle C coverage`.

**Sub-bundle C test count estimate: +68 fast tests** (R1 baseline +64 → +68 after T-C.2 +18 vs prior +14).

### §Tasks-D: Sub-bundle D (polish + briefing + CLAUDE.md + E2E + Phase 11 hand-off)

**Dispatch scope summary:** Closes the arc. Full `swing schwab status` per-environment surface; briefing.md "Schwab integration: degraded" banner; cycle-checklist updates; CLAUDE.md additions; E2E happy-path integration test mirroring Phase 9 Sub-bundle E precedent; Phase 11 hand-off prep.

**Tasks:**

#### T-D.1 `swing schwab status` full surface

- **Scope:** Extend `swing/cli/schwab.py:status_cmd` (T-A.6 skeleton) to render the full output per spec §3.5 mock. Per-environment counts; recent-calls summary; reconciliation summary; degraded indicator.
- **Files touched:** `swing/cli/schwab.py`.
- **Tests added:** +10 (rendering with valid tokens + recent calls; PROVISIONAL state; LIVE state; degraded state per recent error; per-environment counts; reconciliation summary; sentinel-leak coverage; correct masking; correct call counts; CLI exit code 0).
- **Acceptance criteria:** All 10 tests green.
- **Commit message stem:** `feat(schwab): swing schwab status full per-environment surface`.

#### T-D.2 `docs/cycle-checklist.md` updates

- **Scope:** Per §I. Add Schwab one-time setup section + daily/weekly/recovery additions.
- **Files touched:** `docs/cycle-checklist.md`.
- **Tests added:** 0 (documentation; verify-by-inspection in PR review).
- **Acceptance criteria:** All §I bullets present + properly formatted; renders cleanly in Markdown preview.
- **Commit message stem:** `docs(schwab): cycle-checklist updates per §I`.

#### T-D.3 E2E happy-path integration test

- **Scope:** New integration test at `tests/integration/test_schwab_full_happy_path.py` mirroring `tests/integration/test_phase9_full_happy_path.py` shape. Exercises full A+B+C workflow in a single test. Cassette-driven.
- **Files touched:** `tests/integration/test_schwab_full_happy_path.py` (NEW).
- **Tests added:** +1 (single comprehensive E2E test exercises: OAuth setup → snapshot → orders → reconciliation → market-data cache fill → briefing render).
- **Acceptance criteria:** Test green; runtime < 5s (xdist-friendly).
- **Commit message stem:** `test(schwab): E2E happy-path integration test`.

#### T-D.4 `CLAUDE.md` additions

- **Scope:** Per §J. Add 6 gotcha entries.
- **Files touched:** `CLAUDE.md`.
- **Tests added:** 0.
- **Acceptance criteria:** All 6 §J entries present + properly formatted.
- **Commit message stem:** `docs(schwab): CLAUDE.md gotchas per §J`.

#### T-D.5 Briefing.md "Schwab integration: degraded" banner

- **Scope:** Modify briefing render path in `swing/pipeline/runner.py` (or wherever briefing.md is composed). Add conditional banner emission per spec §3.4.4 + §7.2.
- **Files touched:** `swing/pipeline/runner.py` (briefing render section).
- **Tests added:** +6 (banner present when most-recent schwab_api_calls row's status != 'success'; banner absent when status='success'; banner survives multiple runs; banner specifies endpoint name; banner is generic, no token bytes; banner counted toward existing briefing test coverage).
- **Acceptance criteria:** All 6 tests green.
- **Commit message stem:** `feat(schwab): briefing.md degraded banner when last call failed`.

#### T-D.6 Phase 11 hand-off prep

- **Scope:** Add Phase 11 closure entry to `docs/phase3e-todo.md` (or equivalent backlog file). Document Phase 11 arc closer aggregate. Surface V2 candidates (Q3 multi-account; Q4 streaming; Q5 web UI; Q6 inception-CSV ingestion; Q7 TOS deprecation; Q2 token encryption).
- **Files touched:** `docs/phase3e-todo.md`.
- **Tests added:** 0.
- **Acceptance criteria:** Phase 11 SHIPPED entry follows Phase 9 + Phase 10 precedent format; V2 candidates explicitly enumerated.
- **Commit message stem:** `docs(schwab): Phase 11 hand-off prep + V2 candidate backlog`.

#### T-D.7 Verify migration 0018 atomicity discipline + operator-facing manual-backup recommendation

- **Scope (CORRECTED per Codex R1 Major #1 — backup gate does NOT fire for 17→18 per §C.5):** verify migration 0018's BEGIN/COMMIT atomicity discipline holds end-to-end (T-A.7 lands the test; T-D.7 verifies the discipline survives later edits) AND verify the operator-facing migration warning message includes the manual-backup recommendation per §I.1.
- **Files touched:** none (verification only).
- **Tests added:** +2 (`tests/data/test_migration_0018_atomicity.py::test_explicit_begin_commit_preserved` + `tests/cli/test_db_migrate_warning.py::test_warns_to_manual_backup_pre_17_18`).
- **Discriminating test pattern:** grep migration 0018 SQL for `^BEGIN;` and `^COMMIT;` markers; assert both present. Verify CLI warning text contains the manual-backup recommendation substring.
- **Acceptance criteria:** Both tests green; migration applies cleanly under `swing db-migrate` invocation.
- **Commit message stem:** `test(schwab): verify migration 0018 BEGIN/COMMIT discipline + manual-backup warning`.

**Sub-bundle D test count estimate: +19 fast tests.**

### Arc-cumulative test count estimate

- A: +126 (R9-updated)
- B: +80 (R4-updated)
- C: +68 (R2-updated)
- D: +19
- **Total: +293 fast tests** across the arc (within +250..+340 §0.5 projection; matches Phase 9 + 10 precedent).

---

## §L Watch items for executing-plans dispatch (per-bundle dispatch briefs inherit)

Per dispatch brief §5 watch-items, the executing-plans implementer's dispatch brief MUST enumerate these for Codex round attention. Restated here for plan-internal record:

1. Source-ladder consumer inheritance verbatim per §A.4 (R1 attack surface).
2. Production-only domain writes discriminating tests per §A.3 + T-B.2 + T-B.7.
3. Migration 0018 atomic landing per §C.4 + T-A.7.
4. `schwab_api_calls` audit lifecycle per §H.4.1 step 4-5 + T-A.9 service contracts.
5. Token redaction inheritance per §J.4 + §H.8 + T-A.10 sentinel-leak audit.
6. Per-env tokens DB isolation per §F.1 + COA B SQLite vs spec sidecar JSON.
7. OAuth refresh-token rotation per §D.5 + §E.1 (schwabdev handles).
8. `SchwabPipelineActiveError` per §H.10 + T-B.6.
9. Empty-API-response transient handling per §E.5 + §H.6.4 + T-C.3.
10. Market-data ladder Shape A per §A.8 + T-C.2 + T-C.4 + downstream cache impact.
11. `schwab_api_calls` audit-write surface boundary per spec §3.6.2 (pipeline + CLI only; web_page_render NOT in V1 INSERT path).
12. Sub-bundle decomposition rationale per §0.2; inter-bundle deps per §0.3.
12a. COA B integration completeness per §A.2 supersession table.
12b. schwabdev wrapping discipline per §J.4 + T-A.10 schwabdev logger coverage.
13. Q1 production-tier wired per §A.3 + default cfg cascade `environment='production'`.
14. Q11 V1 INCLUDE market-data ladder design surface per §A.8 + Sub-bundle C scope.
15. Q16 `schwab_account_hash` V1 ADD per §A.7 + §C.1.
16. 6 deferred-to-Task-0.b items per §D + §K.6.
17. Test fixture USERPROFILE+HOME monkeypatch per §A.9 #8 + §F.1.
18. Phase isolation preserved per §B.3 READ-ONLY list.
19. Cassette discipline for OAuth flow per §G.3 + T-A.10.
20. Test count projection per sub-bundle per §0.5 + per-bundle §Tasks-* totals.

### §L.1 Codex round attention concentrations (per bundle)

- **Bundle A R1 attack surface:** schwabdev wrapping discipline (does the wrapper miss a schwabdev API method? does the audit lifecycle fire on every call? does schwabdev's logger leak tokens?); migration 0018 atomicity; per-env cfg cascade integration.
- **Bundle B R1 attack surface:** Phase 9 source-ladder consumer fidelity (does `_step_schwab_snapshot` invoke `record_snapshot` verbatim per §A.4?); production-only gate (does sandbox actually skip domain writes?); `run_schwab_reconciliation` mirrors `run_tos_reconciliation` (caller-held-tx rejection; state='failed' preserve pattern; discrepancy emit per type).
- **Bundle C R1 attack surface:** Shape A persistence integrity (backward-compat rename idempotency; resolver merge correctness; empty-response transient); ladder sandbox short-circuit; PriceCache provider field DISTINCT from existing source field.
- **Bundle D R1 attack surface:** E2E happy-path coverage; briefing banner emission discipline; CLAUDE.md + cycle-checklist completeness.

---

## §M Spec coverage matrix (self-review checklist)

Per writing-plans skill §Self-Review: verify each spec section maps to a plan task.

| Spec § | Topic | Plan coverage |
|---|---|---|
| §1.1 | What spec produces | §0 + §A |
| §1.2 | What spec does NOT produce (V1 OUT-OF-SCOPE) | §A.10 |
| §1.3 | Binding constraints | §A.4 + §A.8 + §A.9 |
| §1.4 | V1 INCLUDE market-data ladder | §A.8 + Sub-bundle C |
| §1.5 | Schwab Trader + Market Data API surface | §E |
| §1.6 | What Schwab does NOT replace V1 | §A.10 + §I.4 |
| §2 | Vocabulary | §A.2 + §E.1 + §F.1 |
| §3.1 | Module layout | §B.1 + §A.2 (COA B supersession) |
| §3.2.1 | OAuth setup flow | §H.1 + T-A.4; COA B → paste-back only |
| §3.2.2 | Token storage | §F.1 + §A.2; COA B → SQLite DB |
| §3.2.3 | Token refresh | §H.2 + T-A.5; COA B → schwabdev hybrid |
| §3.2.4 | Concurrency | §F.1; COA B → RLock + SQLite BEGIN EXCLUSIVE |
| §3.2.5 | Revocation | §F.3 + T-A.5 |
| §3.2.6 | Sidecar footgun guards | §F.2 + §J.1 |
| §3.2.7 | Active-environment selection | §A.6 + §F.4 |
| §3.3.1 | Trader API endpoints | §E.2 + T-B.1 |
| §3.3.2 | Market Data API endpoints | §E.3 + T-C.1 |
| §3.3.3 | Endpoints NOT consumed | §E.7 + §A.10 |
| §3.4.1 | New pipeline steps | §H.4 + T-B.3 + T-B.4 |
| §3.4.2 | Step ordering | §H.4.3 |
| §3.4.3 | Lease-fenced semantics | §H.4.1 + §H.4.2 |
| §3.4.4 | Failure tolerance | §H.4 + T-D.5 + §6 inherited |
| §3.4.5 | CLI vs pipeline coordination | §H.10 + T-B.6 |
| §3.5 | CLI surface | §B.1 + T-A.4/T-A.5/T-A.6 + T-B.5 + T-C.5 + T-D.1 |
| §3.6 | Audit table | §C.1 + T-A.7 + T-A.8 |
| §3.6.1 | Audit lifecycle | §H.4.1 + T-A.9 |
| §3.6.2 | Audit-write surface boundary | §C.2 (CHECK enum surface); §L.11 |
| §3.6.3 | Production-only domain writes | §A.3 + T-B.2 + T-B.7 + §J.3 |
| §3.7 | Source-ladder write path inheritance | §A.4 + §H.5 |
| §3.8 | Market-data ladder | §A.8 + §H.6 + Sub-bundle C |
| §4.1 | `schwab_api_calls` cardinality | §C.1 + §C.2 |
| §4.2 | No OAuth state table | §F.1 + §A.2 |
| §4.3 | ALTER columns | §C.1 + §A.7 + §A.12 #1 + #6 |
| §4.4 | Market-data schema | §A.8 (Shape A) |
| §4.5 | Schema version bump | T-A.7 |
| §5 | Token redaction discipline | §G.3 + §H.8 + §J.4 + T-A.10 |
| §6 | Failure-mode catalog | §H.4 + §H.6 + §6 inherited |
| §7.1 | One-time setup | §H.1 + §I.1 |
| §7.2 | Daily cycle | §I.2 |
| §7.3 | Refresh-failure recovery | §I.4 + T-A.5 |
| §7.4 | Cycle-checklist updates | §I |
| §8 | Capture-needs feedback | §A.11 + §A.12 |
| §9 | Adversarial watch items | §L |
| §10 | Open questions Q1-Q17 | §A.1 + §D + Q18 §A.2 |
| §11 | Spec self-review | §M |
| §12 | References | §N below |

**Coverage gaps:** none identified at planning time. Plan §0-§M covers all spec sections + the Q18 COA B addendum.

---

## §N References

**Spec:**
- `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (commit `585556f`; the canonical spec).

**Dispatch brief:**
- `docs/schwab-api-writing-plans-dispatch-brief.md` (the brief operating this plan).

**Plan format precedents:**
- `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (2257 lines; multi-sub-bundle precedent).
- `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (3443 lines; closest already-shipped API-integration precedent).

**COA B library:**
- https://github.com/tylerebowers/Schwabdev (schwabdev runtime dependency; reviewed at planning time for API surface).

**Source-ladder consumers (binding inheritance):**
- `swing/data/repos/account_equity_snapshots.py` (`_SOURCE_PRECEDENCE` at line 38; `get_latest_snapshot_on_or_before` at line 130).
- `swing/trades/account_equity_snapshots.py` (`record_snapshot` at line 66; `CallerHeldTransactionError` at line 39).
- `swing/trades/reconciliation.py` (`run_tos_reconciliation` shape; `DISCREPANCY_TYPES` + `MATERIAL_BY_TYPE` + `RESOLUTION_TYPES`).

**Schema baseline (already permits `'schwab_api'`):**
- `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql:194` (`reconciliation_runs.source`).
- `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql:332` (`account_equity_snapshots.source`).

**Finviz integration precedent (cassette + token-redaction + concurrency-exclusion patterns):**
- `swing/integrations/finviz_api.py` (276 lines).
- `tests/integrations/test_finviz_api_cassette.py` + `test_finviz_api_live.py` + `test_finviz_pipeline_step.py` + `test_finviz_token_redaction_audit.py`.

**Phase 10 metrics consumer (no changes needed):**
- `swing/web/routes/metrics.py`.
- `swing/web/view_models/metrics/capital_friction.py` (PROVISIONAL/LIVE badge consumer).

**CLAUDE.md gotchas (cited throughout):**
- External-API empty-result transient handling.
- Service-layer `with conn:` transaction discipline.
- INSERT OR REPLACE cascade-wipe prohibition.
- Session-anchor read/write predicate alignment.
- USERPROFILE+HOME monkeypatch in tests.
- `os.replace` cross-device-link safety.
- `executescript()` implicit-COMMIT runner discipline.
- yfinance gotcha hardening (preserved via fallback path).

**Orchestrator handoff:**
- `docs/orchestrator-handoff-2026-05-13-schwab-api.md`.

---

## §O Done criteria (executing-plans dispatch closure)

Per dispatch brief §6. Each sub-bundle dispatch closure:

1. All §Tasks-* tasks complete with green tests.
2. Codex review converges to NO_NEW_CRITICAL_MAJOR (≥3 rounds typical per bundle; budget MAX_ROUNDS=5).
3. Operator-witnessed gate per §K.* surface table PASSES.
4. Single integration commit to main with no co-author footer; no `--no-verify`; no amending.
5. Return report covers: per-bundle ship state + Codex history + brief deviations + new gotchas promoted + V2 candidates banked + cross-bundle pin status.

Arc closure (after Sub-bundle D ships):
- `~3286 + ~271 ≈ ~3557` fast tests green on main.
- Schema_version = 18.
- Ruff baseline unchanged at 18.
- Phase 11 (Schwab API integration) labeled SHIPPED in `docs/phase3e-todo.md`.
- V2 candidate dispatches enumerated for orchestrator triage.

Plan complete.

